# -*- coding: utf-8 -*-
"""地球 — 蒼星機装 ガイア（Gaia Frame）。7 頭身スーツの「お手本」（v1.1）。

青（plate）と白（plate2）の騎士型。frame7 の暗い機械の骨格の上に、縁取りのある多層の装甲を重ねる:
V 字の金の角と緑のバイザーの小さな兜、白い面頬、襟、逆三角形の胸（白い V の胸板・金の縁・緑の大陸線・
胸の中央に地球の星核）、節の見える細い腰（白と青の腹の板・脇の油圧シリンダー）、金の留め金のベルト・
前垂れ・外へ開く草摺、三層の肩当て（リベット・紋章・センサー）、白い二の腕、肘当て、手首へ開く篭手、
指の関節まで作った拳と指の甲当て、腿の装甲、尖った膝当てと膝の脇のピストン、白い V の稜の脛当て、
ふくらはぎの排気口、足首のアクチュエーター、つま先の板が重なるサバトン、双発スラスターと排気スリットの
バックパック、雲のように白い二枚のマント、右肩を回る月の子機「ルナ・ビット」。

座標: 16 単位 = 1 ブロック、-Z が正面、右手が -X。寸法は astro_suit.A（7 頭身の目安）から取る。
右側だけ作り `_r` を付ける → 左は自動で鏡映。回転（統合版の rotation）: rx 正 = 上端が前へ /
ry 正 = 正面が右（-X）を向く（+X の端が前へ）/ rz 正 = 上端が +X へ（右側の部品なら下端が外へ開く）。
"""
from __future__ import annotations

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, finger_chain,  # noqa: F401
                        joint_drum, layered_plate, line_on, mirror_x, octa, piston, polyline,
                        rbox, ring, rivets, sensor, stick, taper, vents, greebles)

GOLD_W = 0.26          # 縁取りの幅
LX = A.LEG_X           # 脚の軸 -2.15

# ===========================================================================
#  塗り（astro_paint.suit_styles("earth") への上書き・追加）
# ===========================================================================
SUIT_STYLES = {
    "visor": {"glow": (80, 255, 196), "light": (226, 255, 244), "deep": (8, 96, 86),
              "emit": 20},
    "flame": {"glow": (96, 236, 255), "light": (236, 255, 255), "deep": (30, 120, 200)},
    "flame_core": {"kind": "flame", "glow": (200, 255, 255), "light": (255, 255, 255),
                   "deep": (90, 200, 255), "bevel": False, "outline": False},
    "thruster": {"glow": (96, 236, 255), "light": (240, 255, 255), "deep": (20, 90, 160)},
    "cape": {"kind": "cloth", "base": (238, 243, 250), "shadow": (150, 172, 214),
             "hem": None, "cloud": True, "outline": True, "line": (120, 140, 180),
             "outline_k": 0.5},
    "cape_top": {"kind": "cloth", "base": (238, 243, 250), "shadow": (150, 172, 214),
                 "hem": (226, 176, 70), "cloud": False, "outline": True,
                 "line": (120, 140, 180), "outline_k": 0.5},
    "serial": {"text": "GAIA-03", "under": {"kind": "armor", "base": (236, 242, 248),
                                             "panel": 0, "line": (80, 90, 110)},
               "ink": (40, 60, 110)},
    "hazard": {"c1": (84, 255, 146), "c2": (24, 34, 52)},
    "face": {"kind": "armor", "base": (214, 222, 236), "panel": 0, "line": (70, 80, 100)},
    "grille": {"kind": "vent", "base": (60, 70, 92), "glow": (34, 42, 60), "deep": (12, 16, 26),
               "slat": 2},
    "lamp": {"kind": "glowline", "glow": (255, 214, 96), "light": (255, 246, 214),
             "bevel": False, "outline": False},
}

# ===========================================================================
#  部位アニメ（Molang。q.anim_time は 12 秒でループするので周波数は 30°/秒の倍数に）
#  v.astro_air: 空中で 1 に近づく / v.astro_run: 疾走で 1 に近づく。`_r` は左へ自動で鏡映
# ===========================================================================
SUIT_ANIMS = {
    "idle": {
        "extra_cape_r": {"rotation": ["3.0 + math.sin(q.anim_time * 90.0) * 2.0", 0,
                                      "math.sin(q.anim_time * 60.0) * 1.2"]},
        "extra_cape2_r": {"rotation": ["4.0 + math.sin(q.anim_time * 90.0 - 60.0) * 3.0", 0, 0]},
        "fx_spin_luna": {"rotation": ["q.anim_time * 90.0", 0, 0]},
        "extra_luna": {"position": [0, "math.sin(q.anim_time * 120.0) * 0.3", 0]},
    },
    "thrust": {
        "extra_cape_r": {"rotation": ["v.astro_air * 26.0", 0, "-v.astro_air * 6.0"]},
        "extra_cape2_r": {"rotation": [
            "v.astro_air * (14.0 + math.sin(q.anim_time * 720.0) * 5.0)", 0, 0]},
    },
    "sprint": {
        "extra_cape_r": {"rotation": ["v.astro_run * 24.0", 0, "-v.astro_run * 4.0"]},
        "extra_cape2_r": {"rotation": [
            "v.astro_run * (12.0 + math.sin(q.anim_time * 900.0) * 4.0)", 0, 0]},
    },
}


# ===========================================================================
def build_suit(s: Suit):
    s.frame7(skip=("foot",))            # サバトンが足を包むので骨格の足は省く
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    cape(s)
    arms(s)
    hands(s)
    shoulders(s)
    helmet(s)
    luna_bit(s)


# ---------------------------------------------------------------------------
#  サバトン（足首から生える）
# ---------------------------------------------------------------------------
def boots(s):
    b = s.part("boots", "foot_r", "rightLeg")
    cbox(b, (LX, 0.16, -1.15), (2.95, 0.32, 5.9), "dark")                          # 靴底
    shell = bevel(b, (LX, 1.05, -0.75), (2.9, 1.5, 4.1), "plate", cut=0.42, axis="z")
    line_on(b, shell[0], "west", (0.12, 0.42), (0.9, 0.42), 0.2, 0.16, "glow")    # 外の発光線
    rivets(b, shell[0], "west", 3, edge="top", margin=0.32, span=(0.25, 0.75))
    # 甲（白）と、つま先の板が三枚重なる
    ins = rbox(b, (LX, 1.92, -1.95), (2.35, 0.5, 1.9), "plate2", rot=(-30, 0, 0))
    rivets(b, ins, "up", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    rbox(b, (LX, 1.0, -3.12), (2.7, 0.95, 1.05), "plate2", rot=(-16, 0, 0))
    cbox(b, (LX, 0.62, -3.66), (2.4, 0.3, 0.3), "dark")
    rbox(b, (LX, 0.62, -3.98), (2.5, 0.7, 0.8), "plate", rot=(-26, 0, 0))
    cbox(b, (LX, 0.32, -4.36), (2.2, 0.4, 0.34), "gold")                          # つま先の金具
    rbox(b, (LX, 0.95, -3.95), (0.5, 0.5, 0.3), "gem", rot=(0, 0, 45))
    # 踵（青）と噴射口
    cbox(b, (LX, 1.05, 1.25), (2.55, 1.5, 1.0), "plate_b")
    octa(b, (LX, 0.75, 1.92), 1.2, 0.5, "frame", axis="z")
    cbox(b, (LX, 0.75, 2.2), (0.9, 0.9, 0.16), "thruster")
    # 足首の外を守る小さな板（ドラムは見せる）
    rbox(b, (LX - 1.52, 2.55, 0.85), (0.32, 1.1, 1.3), "plate2", rot=(0, 0, -6))


# ---------------------------------------------------------------------------
#  脚（腿・膝・脛）
# ---------------------------------------------------------------------------
def legs(s):
    # 腿: 前の青い板（上に白い板）・外の白い装甲（型番）。後ろと内側は骨格を見せる
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.75, -1.82), (2.85, 4.3, 0.55), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="gold", trim_edge="bottom",
                       rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(t, fr["top"], "north", (0.74, 0.1), (0.74, 0.6), 0.18, 0.16, "glow")
    line_on(t, fr["top"], "north", (0.74, 0.6), (0.42, 0.86), 0.18, 0.16, "glow")
    side = rbox(t, (LX - 1.78, 11.38, 0.05), (0.5, 3.25, 2.9), "plate2", rot=(0, 0, -3),
                decals={"west": {"decal": "serial", "text": "GA-03", "ink": (40, 60, 110)}})
    rivets(t, side, "west", 3, edge="bottom", margin=0.3)
    cbox(t, (LX - 1.62, 9.62, 0.05), (0.42, 0.42, 2.7), "gold")
    sensor(t, (LX + 0.2, 13.45, -2.18), 0.3, "glow", "dark")
    # 膝: 尖った白い膝当て（金の縁・宝玉）と外の油圧シリンダー
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    kg = bevel(k, (LX, 8.45, -1.88), (2.3, 2.3, 0.8), "plate2", cut=0.38, axis="z")
    rbox(k, (LX, 9.55, -1.78), (1.55, 1.55, 0.7), "plate2", rot=(0, 0, 45))      # 上の尖り
    rbox(k, (LX, 7.25, -1.9), (1.2, 1.2, 0.6), "plate", rot=(0, 0, 45))          # 下の尖り
    stick(k, kg[0], "north", 0.5, 0.06, (2.0, GOLD_W, 0.2), "gold", sink=0.05)
    rbox(k, (LX, 8.5, -2.38), (0.6, 0.6, 0.3), "gem", rot=(0, 0, 45))
    rivets(k, kg[0], "north", 2, edge="top", margin=0.35, span=(0.18, 0.82))
    piston(k, (LX - 1.62, 10.9, 0.55), (LX - 1.5, 6.3, 0.45), r=0.27, style="frame",
           rod_style="chrome", cap_style="dark")
    # 脛: 前の青い板 + 白い V の稜（緑の大陸線）、両脇の板、ふくらはぎの排気口、外のヒレ
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.75, -1.42), (2.75, 5.1, 0.55), "plate", rot=(4, 0, 0))
    stick(g, front, "north", 0.5, 0.04, (2.6, GOLD_W, 0.18), "gold", sink=0.05)
    keel = rbox(g, (LX - 0.36, 4.95, -1.76), (0.78, 4.2, 0.48), "plate2", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)
    line_on(g, front, "north", (0.1, 0.18), (0.16, 0.55), 0.18, 0.16, "glow")
    line_on(g, front, "north", (0.16, 0.55), (0.08, 0.86), 0.18, 0.16, "glow")
    line_on(g, front, "north", (0.92, 0.3), (0.86, 0.7), 0.18, 0.16, "glow")
    sd = rbox(g, (LX - 1.45, 4.85, -0.15), (0.45, 4.9, 2.7), "plate", rot=(0, 0, -4))
    sdr = rivets(g, sd, "west", 3, edge="bottom", margin=0.32)
    mirror_x(g, sd, sdr, about=LX)
    calf = rbox(g, (LX, 6.15, 1.62), (2.3, 2.5, 0.45), "plate_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))
    fin = rbox(g, (LX - 1.86, 5.6, 0.75), (0.38, 3.3, 2.0), "plate2", rot=(-10, 0, -8))
    line_on(g, fin, "west", (0.15, 0.3), (0.85, 0.72), 0.18, 0.16, "glow")


# ---------------------------------------------------------------------------
#  腰（ベルト・留め金・前垂れ・腰の脇の板・草摺・後ろ垂れ）
# ---------------------------------------------------------------------------
def waist(s):
    w = s.part("waist", "belt", "body")
    chamfer(w, (0, 16.95, 0.12), (6.7, 0.95, 4.5), "frame", cut=0.4, axis="y")
    bevel(w, (0, 16.95, -2.4), (1.8, 1.25, 0.5), "gold", cut=0.3, axis="z")
    rbox(w, (0, 16.95, -2.72), (0.75, 0.75, 0.3), "gem", rot=(0, 0, 45))
    bl = rivets(w, w.cubes[0], "north", 3, edge="bottom", margin=0.48, span=(0.08, 0.3))
    mirror_x(w, bl)
    # 前垂れ（細い白の板。腿の前を隠さない幅）
    fp = rbox(w, (0, 15.2, -2.08), (1.9, 2.5, 0.5), "plate2", rot=(-8, 0, 0))
    stick(w, fp, "north", 0.5, 0.06, (1.7, GOLD_W, 0.18), "gold", sink=0.05)
    line_on(w, fp, "north", (0.5, 0.25), (0.5, 0.85), 0.2, 0.16, "glow")
    # 腰の脇の青い板（股関節の前を覆う）
    hp = rbox(w, (-2.35, 15.75, -2.0), (2.1, 1.5, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.3, span=(0.25, 0.75))
    mirror_x(w, hp, hpr)
    # 後ろ垂れ
    rs = rbox(w, (0, 15.05, 2.45), (4.6, 2.7, 0.5), "plate", rot=(14, 0, 0))
    cbox(w, (0, 14.0, 2.85), (3.0, 0.4, 0.3), "hazard")
    rivets(w, rs, "south", 4, edge="top", margin=0.3)
    # 草摺（腰の横。付け根で外へ開く。青の下板 + 白の上板 + 金の縁 + 発光線 + リベット）
    # 腿の外の装甲（y 13.55 まで）の上で終わり、篭手の内側（x -4.5）より内に収める
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 8))
    base = layered_plate(ts, (-3.62, 15.15, 0.0), (0.45, 2.8, 3.5), "plate", top="plate2",
                         face="west", inset=0.36, trim="gold", trim_edge="bottom",
                         rivet="rivet", n_rivets=3, rivet_edge="top")
    line_on(ts, base["top"], "west", (0.15, 0.45), (0.85, 0.45), 0.2, 0.16, "glow")
    cbox(ts, (-3.42, 16.3, 0.0), (0.5, 0.55, 1.6), "dark")                        # 蝶番


# ---------------------------------------------------------------------------
#  胴（胸郭・胸板・星核・襟・脇の排気口・腹の板）
# ---------------------------------------------------------------------------
def torso(s):
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.2, 0.0), (9.2, 3.5, 5.0), "plate", cut=0.8, axis="y")      # 上が広い
    bevel(c, (0, 21.6, -0.05), (7.2, 2.3, 4.6), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.9, 22.15, 0.0), (0.5, 2.9, 4.0), "plate", rot=(0, 0, -24))    # 脇の斜面
    mirror_x(c, sl)
    # 白い V の胸板: 外へ開き、内側の端が前へ、下辺が中央へ（金の縁・緑の大陸線・リベット）
    pec = rbox(c, (-2.55, 24.2, -2.62), (3.55, 2.45, 0.55), "plate2", rot=(6, 17, 9))
    pt = stick(c, pec, "north", 0.5, 0.94, (3.4, GOLD_W, 0.18), "gold", sink=0.05)
    gl = [line_on(c, pec, "north", ab0, ab1, 0.18, 0.16, "glow") for ab0, ab1 in (
        ((0.92, 0.42), (0.6, 0.55)), ((0.6, 0.55), (0.42, 0.8)), ((0.6, 0.55), (0.25, 0.42)))]
    pr = rivets(c, pec, "north", 3, edge="bottom", margin=0.26, span=(0.2, 0.8))
    low = rbox(c, (-1.95, 21.95, -2.42), (3.3, 1.5, 0.5), "plate", rot=(-8, 12, 12))
    lr = rivets(c, low, "north", 2, edge="bottom", margin=0.28, span=(0.3, 0.75))
    mirror_x(c, pec, pt, gl, pr, low, lr)
    # 胸の中央の稜（青）: 胸板の間を縦に通り、下の星核へ
    kl = rbox(c, (0, 24.35, -2.82), (1.25, 2.9, 0.5), "plate", rot=(-8, 0, 0))
    stick(c, kl, "north", 0.5, 0.55, (0.3, 2.2, 0.16), "plate2", sink=0.06)
    # 星核: 黒い菱形の台 → 金の八角の枠 → 地球 → 脈打つ光の輪
    rbox(c, (0, 22.75, -2.72), (2.5, 2.5, 0.5), "dark", rot=(0, 0, 45))
    octa(c, (0, 22.75, -2.98), 2.25, 0.36, "gold", axis="z")
    cbox(c, (0, 22.75, -3.12), (1.55, 1.55, 0.6), "core")
    gl_ = s.fx("glow", "core", c, pivot=(0, 22.75, -3.3))
    ring(gl_, (0, 22.75, -3.3), 1.22, 8, (0, 0.24, 0.24), "glow", axis="z")
    # 襟（首の両脇に立ち上がる青の板 + 白の縁 + 金）
    col = rbox(c, (-1.75, 26.25, 0.35), (1.45, 1.1, 3.6), "plate", rot=(0, 0, -24))
    colt = stick(c, col, "up", 0.5, 0.5, (1.1, 3.3, 0.2), "plate2", sink=0.06)
    colg = stick(c, col, "west", 0.5, 0.06, (3.4, GOLD_W, 0.18), "gold", sink=0.05)
    cf = rbox(c, (-0.95, 25.95, -1.95), (1.6, 0.9, 0.45), "plate2", rot=(-20, 30, -10))
    mirror_x(c, col, colt, colg, cf)
    sensor(c, (-1.4, 25.25, -2.62), 0.26, "lamp", "dark")
    sensor(c, (1.4, 25.25, -2.62), 0.26, "glow", "dark")
    # 肩の付け根（肩当ての下）と脇の排気口
    yk = rbox(c, (-3.95, 25.95, 0.0), (2.0, 0.55, 3.5), "plate_b", rot=(0, 0, -8))
    sv = cbox(c, (-4.4, 23.7, 0.35), (0.4, 2.0, 2.4), "plate2")
    svv = vents(c, sv, "west", 3, box=(0.15, 0.2, 0.85, 0.8))
    mirror_x(c, yk, sv, svv)
    rivets(c, up[1], "south", 4, edge="top", margin=0.35, span=(0.12, 0.88))
    # 腹: 下ほど細い三枚の板（白・青・白）と中央の溝
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))
    for i, (y, ww, st) in enumerate(((19.95, 4.0, "plate2"), (18.95, 3.6, "plate"),
                                     (17.95, 3.2, "plate2"))):
        p = rbox(ab, (0, y, -1.98 + i * 0.05), (ww, 0.82, 0.48), st, rot=(-8, 0, 0))
        stick(ab, p, "north", 0.5, 0.5, (0.18, 0.6, 0.16), "dark", sink=0.08)
        r_ = rivets(ab, p, "north", 1, line=((0.12, 0.5), (0.12, 0.5)), size=0.22)
        mirror_x(ab, r_)
    cbox(ab, (0, 18.9, 2.08), (2.2, 2.6, 0.45), "plate_b")                          # 背の腰板


# ---------------------------------------------------------------------------
#  背中（バックパック・排気スリット・双発スラスター・翼・ホース）
# ---------------------------------------------------------------------------
def back(s):
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.3, 3.5), (4.2, 5.2, 2.0), "plate2", cut=0.6, axis="z")
    rbox(bk, (0, 25.1, 3.2), (3.8, 0.8, 2.0), "plate", rot=(20, 0, 0))              # 上の蓋
    vents(bk, pk[0], "south", 4, box=(0.25, 0.3, 0.75, 0.7), rim="frame")
    cbox(bk, (0, 20.15, 4.52), (2.6, 0.4, 0.2), "hazard")
    rivets(bk, pk[0], "south", 8, edge="border", margin=0.28)
    sensor(bk, (0, 24.35, 4.52), 0.3, "glow", "dark", facing=1)
    st = cbox(bk, (-1.55, 22.3, 4.55), (0.36, 4.4, 0.16), "plate")                  # 青い縦の帯
    # 脇の推進剤タンク（八角の筒 + 蓋 + 金の帯）
    tk = octa(bk, (-2.32, 21.6, 3.85), 1.0, 3.0, "plate", axis="y")
    tk += octa(bk, (-2.32, 23.2, 3.85), 0.78, 0.3, "frame", axis="y")
    tk += octa(bk, (-2.32, 20.0, 3.85), 0.78, 0.3, "frame", axis="y")
    tk += octa(bk, (-2.32, 21.6, 3.85), 1.12, 0.3, "gold", axis="y")
    mirror_x(bk, st, tk)
    # ホース: バックパックの下から腰の両脇へ（垂れる蛇腹）
    hs = cable(bk, [(-1.6, 19.9, 3.6), (-2.9, 17.6, 2.4)], 0.3, "dark", sag=0.35,
               rib="frame_lt", rib_every=2)
    mirror_x(bk, hs)
    # スラスター（右。下後ろへ向ける）: 胴・金の帯・広がったベル・光る縁の輪・噴射口・炎
    th = s.part("back", "thruster_r", bk, pivot=(-1.4, 20.6, 4.5), rotation=(18, 0, -8))
    octa(th, (-1.4, 19.6, 4.5), 1.7, 2.0, "plate", axis="y")
    octa(th, (-1.4, 20.35, 4.5), 1.9, 0.32, "gold", axis="y")
    octa(th, (-1.4, 18.15, 4.5), 2.15, 1.0, "frame", axis="y")
    ring(th, (-1.4, 17.68, 4.5), 0.86, 8, (0, 0.24, 0.24), "glow", axis="y")
    cbox(th, (-1.4, 17.66, 4.5), (1.5, 0.16, 1.5), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.4, 17.6, 4.5))
    taper(fx, (-1.4, 17.6, 4.5), (-1.4, 11.5, 4.5), 1.7, 0.36, 3, "flame")
    taper(fx, (-1.4, 17.55, 4.5), (-1.4, 14.2, 4.5), 0.8, 0.22, 2, "flame_core", round_=False)
    # 翼（バックパックの上の角から後ろ上へ。飾り = 計測しない）
    wg = s.part("back", "wing_r", bk, pivot=(-1.9, 24.4, 4.2), ornament=True)
    beam(wg, (-1.9, 24.4, 4.3), (-3.7, 26.3, 6.0), 0.42, 1.1, "plate2")
    beam(wg, (-2.1, 23.6, 4.4), (-3.5, 24.9, 5.7), 0.38, 0.75, "plate")
    beam(wg, (-3.6, 26.15, 5.9), (-4.15, 26.75, 6.45), 0.38, 0.5, "gold")
    beam(wg, (-2.05, 24.92, 4.35), (-3.75, 26.7, 5.98), 0.46, 0.18, "glow")


# ---------------------------------------------------------------------------
#  マント（雲のように白い二枚。上下 2 段で揺れる）
# ---------------------------------------------------------------------------
def cape(s):
    cp = s.part("extra", "cape_r", "body", pivot=(-3.75, 25.7, 2.95), rotation=(0, 0, 2))
    cbox(cp, (-3.75, 22.35, 3.0), (1.9, 6.7, 0.34), "cape_top")
    cbox(cp, (-3.75, 25.55, 2.82), (1.1, 0.8, 0.6), "gold")
    rbox(cp, (-3.75, 25.55, 2.45), (0.55, 0.55, 0.3), "gem", rot=(0, 0, 45))
    lo = s.part("extra", "cape2_r", cp, pivot=(-3.75, 19.1, 3.0))
    cbox(lo, (-3.8, 13.55, 3.0), (2.1, 11.1, 0.32), "cape")                        # 裾は少し広く


# ---------------------------------------------------------------------------
#  腕（二の腕・肘・篭手）
# ---------------------------------------------------------------------------
def arms(s):
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.32, 21.35, 0.0), (0.45, 3.2, 2.5), "plate2", rot=(0, 0, 3))
    line_on(ua, op, "west", (0.5, 0.12), (0.5, 0.88), 0.2, 0.16, "glow")
    rivets(ua, op, "west", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    upf = rbox(ua, (X + 0.05, 21.4, -1.38), (2.2, 2.9, 0.42), "plate2", rot=(-3, 0, 0))
    stick(ua, upf, "north", 0.5, 0.5, (0.5, 2.4, 0.16), "plate", sink=0.06)
    sensor(ua, (X + 0.05, 22.55, -1.66), 0.22, "glow", "dark")
    rbox(ua, (X + 0.05, 21.7, 1.36), (2.0, 2.3, 0.4), "plate_b", rot=(3, 0, 0))
    octa(ua, (X, 19.72, 0.02), 2.86, 0.32, "gold", axis="y")                       # 腕輪
    # 肘当て（後ろ）
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    cop = bevel(el, (A.ELBOW[0], 18.55, 1.62), (2.1, 1.9, 0.6), "plate", cut=0.3, axis="z")
    rivets(el, cop[0], "south", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    # 篭手: 手首へ向かって開く（青）+ 外の白い板（緑の線・リベット）+ 前の排気口 + 金の袖口
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    FX_ = A.FOREARM_X
    bevel(fa, (FX_, 17.15, 0.0), (2.85, 1.9, 2.95), "plate", cut=0.45, axis="y")
    lo = bevel(fa, (FX_ - 0.04, 15.7, 0.0), (3.0, 1.75, 3.15), "plate", cut=0.48, axis="y")
    ob = rbox(fa, (FX_ - 1.68, 16.3, 0.0), (0.42, 3.1, 2.6), "plate2", rot=(0, 0, 5))
    line_on(fa, ob, "west", (0.15, 0.25), (0.42, 0.8), 0.18, 0.16, "glow")
    line_on(fa, ob, "west", (0.58, 0.8), (0.85, 0.25), 0.18, 0.16, "glow")
    rivets(fa, ob, "west", 3, edge="top", margin=0.28)
    fv = rbox(fa, (FX_ - 0.02, 16.45, -1.62), (2.0, 2.2, 0.35), "plate2", rot=(-5, 0, 0))
    fvb = stick(fa, fv, "north", 0.5, 0.5, (1.3, 1.7, 0.18), "plate", sink=0.06)
    line_on(fa, fvb, "north", (0.3, 0.12), (0.55, 0.55), 0.16, 0.16, "glow")
    line_on(fa, fvb, "north", (0.55, 0.55), (0.45, 0.9), 0.16, 0.16, "glow")
    rivets(fa, fv, "north", 2, edge="bottom", margin=0.18, span=(0.12, 0.88), size=0.2)
    chamfer(fa, (FX_ - 0.04, 14.72, 0.0), (3.06, 0.34, 3.2), "gold", cut=0.4, axis="y")  # 袖口
    sensor(fa, (FX_ + 0.05, 15.5, 1.68), 0.26, "glow", "dark", facing=1)
    rivets(fa, lo[1], "south", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))


def hands(s):
    """手の甲の白い板と宝玉、指の甲当て（4 本の基節）、親指の当て。指そのものは frame7。"""
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    hb = rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate2", rot=(0, 0, 4))
    stick(h, hb, "west", 0.5, 0.55, (0.6, 0.6, 0.2), "gem", sink=0.05)
    for zf in (-0.93, -0.31, 0.31, 0.93):
        p0, p1 = (-6.98, 12.45, zf), (-6.48, 11.75, zf)
        n = (-0.81, -0.58, 0.0)
        o = 0.34
        beam(h, (p0[0] + n[0] * o, p0[1] + n[1] * o, zf), (p1[0] + n[0] * o, p1[1] + n[1] * o, zf),
             0.56, 0.22, "plate")
    rbox(h, (-5.62, 13.55, -1.72), (0.62, 0.9, 0.22), "plate", rot=(0, 0, -36))


# ---------------------------------------------------------------------------
#  肩（三層の肩当て）
# ---------------------------------------------------------------------------
def shoulders(s):
    p = s.part("shoulders", "pauldron_r", "rightArm")
    dome = bevel(p, (-7.2, 25.65, 0.0), (3.8, 2.4, 4.8), "plate", cut=0.75, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.45, 0.5, (2.4, 3.7, 0.3), "plate2", sink=0.1)
    stick(p, top, "up", 0.08, 0.5, (0.26, 3.7, 0.18), "gold", sink=0.08)
    rdg = stick(p, top, "up", 0.55, 0.5, (0.55, 3.9, 0.3), "plate", sink=0.08)       # 中央の稜
    line_on(p, rdg, "up", (0.5, 0.08), (0.5, 0.92), 0.18, 0.16, "glow")
    rivets(p, top, "up", 6, edge="border", margin=0.25, size=0.24)
    cbox(p, (-6.5, 24.2, 0.0), (2.2, 0.5, 3.8), "dark")                              # 裏の縁
    # 外の縁: 上・外へ反り返る白い板（上端に金）→ 肩の線を広く見せる
    rim = rbox(p, (-9.12, 25.35, 0.0), (0.45, 1.9, 4.9), "plate2", rot=(0, 0, -30))
    stick(p, rim, "up", 0.5, 0.5, (0.45, 4.9, 0.2), "gold", sink=0.05)
    rivets(p, rim, "west", 4, edge="bottom", margin=0.3, size=0.22)
    # 外へ開いて垂れる板（白・青）と金の縁、紋章、リベットの列
    l1 = rbox(p, (-8.62, 23.6, 0.0), (0.55, 2.3, 4.6), "plate2", rot=(0, 0, 15),
              decals={"west": {"decal": "emblem", "color": (84, 255, 146)}})
    stick(p, l1, "west", 0.5, 0.06, (4.4, GOLD_W, 0.18), "gold", sink=0.05)
    rivets(p, l1, "west", 5, edge="top", margin=0.24, size=0.22)
    l2 = rbox(p, (-8.8, 21.9, 0.05), (0.48, 1.55, 4.0), "plate", rot=(0, 0, 11))
    stick(p, l2, "west", 0.5, 0.08, (3.7, GOLD_W, 0.18), "gold", sink=0.05)
    rivets(p, l2, "west", 4, edge="top", margin=0.22, size=0.22)
    # 前後の小さな板とセンサー
    fr = rbox(p, (-7.25, 24.45, -2.45), (2.6, 1.3, 0.4), "plate_b", rot=(-12, 0, 0))
    sensor(p, (-7.6, 24.45, -2.7), 0.26, "lamp", "dark")
    rbox(p, (-7.25, 24.55, 2.45), (2.6, 1.3, 0.4), "plate_b", rot=(12, 0, 0))
    rbox(p, (-7.1, 26.95, 2.05), (0.42, 1.2, 1.6), "plate2", rot=(-25, 0, -10))       # 後ろのヒレ
    rivets(p, fr, "north", 2, edge="bottom", margin=0.22, span=(0.2, 0.45))


# ---------------------------------------------------------------------------
#  兜（ドーム・額・眉・面頬・顎・頬当て・耳・後頭部・しころ・V の角）とバイザー
# ---------------------------------------------------------------------------
def helmet(s):
    hz = A.HEAD_Z
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.65, hz + 0.3), (4.5, 1.7, 4.9), "plate", cut=0.6, axis="z")
    bevel(hm, (0, 31.62, hz + 0.45), (3.5, 0.9, 4.4), "plate", cut=0.32, axis="z")  # 冠
    cbox(hm, (0, 32.0, hz + 0.5), (0.8, 0.34, 3.9), "plate2")                       # 中央の稜
    rbox(hm, (0, 30.7, hz - 2.2), (4.2, 1.3, 0.5), "plate", rot=(-22, 0, 0))       # 額の斜面
    br = rbox(hm, (-1.05, 30.05, hz - 2.42), (2.1, 0.5, 0.5), "plate2", rot=(-8, 8, 9))
    sd = cbox(hm, (-2.12, 28.95, hz + 0.65), (0.42, 2.2, 3.5), "plate")             # こめかみ
    sdr = rivets(hm, sd, "west", 2, edge="top", margin=0.3, span=(0.3, 0.7), size=0.22)
    ck = rbox(hm, (-1.78, 28.4, hz - 1.15), (0.5, 2.0, 2.3), "plate", rot=(0, 20, -10))  # 頬当て
    ckg = stick(hm, ck, "west", 0.06, 0.5, (0.22, 1.8, 0.16), "gold", sink=0.05)
    ear = octa(hm, (-2.36, 29.15, hz + 0.65), 1.4, 0.34, "chrome", axis="x")       # 耳
    eg = cbox(hm, (-2.55, 29.15, hz + 0.65), (0.16, 0.5, 0.5), "glow")
    mirror_x(hm, br, sd, sdr, ck, ckg, ear, eg)
    # 面頬（白）: 中央の稜へ折れた V の板、頬の小さな吸気口、尖った顎
    fc = rbox(hm, (-0.62, 28.45, hz - 2.2), (1.3, 1.25, 0.42), "face", rot=(8, 26, 0))
    ch = rbox(hm, (-0.45, 27.75, hz - 1.98), (1.0, 0.7, 0.48), "face", rot=(0, 26, -22))
    mirror_x(hm, fc, ch)
    cbox(hm, (0, 28.5, hz - 2.5), (0.3, 1.2, 0.3), "plate2")
    # 後頭部（中央の稜が後ろへ降りる・小さな排気口）としころ
    bh = cbox(hm, (0, 29.1, hz + 2.6), (4.0, 2.4, 0.45), "plate")
    rbox(hm, (0, 31.3, hz + 2.55), (0.8, 1.6, 0.4), "plate2", rot=(35, 0, 0))
    vents(hm, bh, "south", 3, box=(0.3, 0.25, 0.7, 0.65), w=0.18)
    rbox(hm, (0, 28.05, hz + 2.62), (3.7, 0.75, 0.45), "plate_b", rot=(22, 0, 0))
    rbox(hm, (0, 27.55, hz + 2.75), (3.2, 0.62, 0.42), "plate", rot=(32, 0, 0))
    # V 字の角（金。飾り）と額の宝玉
    cr = s.part("helmet", "crest", "head", pivot=(0, 30.6, hz - 2.6), ornament=True)
    v = polyline(cr, [(-0.25, 30.55, hz - 2.62), (-1.3, 31.6, hz - 2.6), (-2.85, 33.7, hz - 2.4)],
                 [0.32, 0.24], [0.85, 0.5], "gold")
    mirror_x(cr, v)
    octa(cr, (0, 30.55, hz - 2.6), 1.15, 0.36, "gold", axis="z")
    rbox(cr, (0, 30.55, hz - 2.82), (0.72, 0.72, 0.3), "gem", rot=(0, 0, 45))
    taper(cr, (0, 32.2, hz + 2.2), (0, 31.5, hz + 3.9), 0.6, 0.24, 2, "plate2", round_=False)
    an = s.part("helmet", "antenna_r", "head", pivot=(-2.45, 29.6, hz + 0.9), ornament=True)
    taper(an, (-2.45, 29.6, hz + 0.95), (-2.75, 32.2, hz + 2.6), 0.32, 0.16, 2, "gold",
          round_=False)
    # バイザー: 暗い帯の上に、少し吊り上がった二つの緑の目
    vz = s.part("visor", "eye", "head")
    cbox(vz, (0, 29.5, hz - 2.3), (3.7, 0.72, 0.3), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.5, hz - 2.48))
    eye = rbox(fg, (-0.92, 29.5, hz - 2.48), (1.35, 0.34, 0.18), "visor", rot=(0, 8, 7))
    mirror_x(fg, eye)


# ---------------------------------------------------------------------------
#  ルナ・ビット（右肩の外上を傾いた軌道で回る月の子機）
# ---------------------------------------------------------------------------
def luna_bit(s):
    # 軌道: 右肩の外上を中心に、内側（頭の方）へ 30° 傾けた縦の輪。月は潮汐固定（同じ面が肩を向く）
    C = (-10.6, 28.4, 0.4)
    lb = s.part("extra", "luna", "body", pivot=C, rotation=(0, 0, 30))
    sp = s.fx("spin", "luna", lb, pivot=C)
    M = (C[0], C[1] + 2.6, C[2])
    cbox(sp, M, (1.6, 1.6, 1.6), "luna")
    rbox(sp, M, (1.45, 1.45, 1.45), "luna", rot=(0, 45, 0))
    ring(sp, M, 1.15, 8, (0, 0.22, 0.32), "gold", axis="y")                        # 機械の輪
    octa(sp, (M[0] + 0.86, M[1], M[2]), 0.62, 0.26, "frame", axis="x")             # 肩を向く目
    cbox(sp, (M[0] + 0.98, M[1], M[2]), (0.18, 0.3, 0.3), "glow")
    taper(sp, (M[0], M[1] + 0.8, M[2]), (M[0] + 0.25, M[1] + 1.6, M[2] + 0.4), 0.2, 0.16, 1,
          "gold", round_=False)                                                       # アンテナ
