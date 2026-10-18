# -*- coding: utf-8 -*-
"""<惑星名> — <スーツ名>（7 頭身の雛形。v1.1）。

使い方: tools/astro/planets/<key>/ にコピーし（__init__.py も空で作る）、各関数を作り込む。
お手本は planets/earth/suit.py、説明は同じフォルダの README.md。この雛形のままでも検査は通る（約 840 キューブ）。

    python3 tools/astro/preview_astro.py suit <key>    # 絵を見る（build_preview/astro/suit_<key>.png）
    python3 tools/astro/check_astro_suits.py <key>     # 検査（7 頭身・細かさ・命名・アニメ）
    python3 tools/astro/gen_astro_suits.py <key>       # pack へ書き出す

座標: -Z が正面、右手が -X、足の裏 y=0、頭頂 y≈32。寸法は A.*（右側の値）。右側だけ作って名前の末尾を `_r` に →
左は自動で鏡映。回転: rx 正 = 上端が前へ / ry 正 = 正面が右(-X)を向く / rz 正 = 下端が右(-X)へ（右の部品なら外へ開く）。
"""
from __future__ import annotations

from astro_suit import (A, Suit, beam, bevel, cable, cbox, chamfer, layered_plate,  # noqa: F401
                        line_on, mirror_x, octa, piston, polyline, rbox, ring, rivets, rod,
                        sensor, stick, taper, vents)

LX = A.LEG_X            # 脚の軸 -2.15
TRIM = 0.26             # 金の縁の幅

# 塗りの上書き・追加（astro_paint.suit_styles(key) の上に重なる）。README §8
SUIT_STYLES = {
    # "plate": {"panel": 1},
    # "flame": {"glow": (255, 140, 40), "light": (255, 240, 200), "deep": (160, 40, 10)},
}

# 部位アニメ（Molang）。周波数は 30°/秒の倍数（12 秒ループの継ぎ目を検査が調べる）。`_r` は左へ自動で鏡映。README §9
SUIT_ANIMS = {
    "idle": {
        # "fx_spin_halo": {"rotation": [0, 0, "q.anim_time * 60.0"]},
    },
    "thrust": {},
    "sprint": {},
}


def build_suit(s: Suit):
    s.frame7()                   # 7 頭身の暗い機械の骨格（inner）。装甲で包む所は skip=("foot",) 等で省ける
    boots(s)
    legs(s)
    waist(s)
    torso(s)
    back(s)
    arms(s)
    shoulders(s)
    helmet(s)
    extra(s)


# ---------------------------------------------------------------------------
def boots(s):
    """サバトン: 足の殻・甲・二枚のつま先の板・踵の噴射口（骨格の足の上に被せる）。"""
    b = s.part("boots", "foot_r", "rightLeg")                       # pivot は足首（A.ANKLE）
    shell = bevel(b, (LX, 1.1, -0.85), (2.95, 1.45, 4.0), "plate", cut=0.4, axis="z")
    rivets(b, shell[0], "west", 3, edge="top", margin=0.32, span=(0.25, 0.75))
    rbox(b, (LX, 1.95, -1.95), (2.35, 0.5, 1.8), "plate2", rot=(-30, 0, 0))   # 甲
    rbox(b, (LX, 0.95, -3.2), (2.7, 0.9, 0.95), "plate2", rot=(-16, 0, 0))    # つま先の板 1
    rbox(b, (LX, 0.6, -4.0), (2.5, 0.66, 0.75), "plate", rot=(-26, 0, 0))     # つま先の板 2
    cbox(b, (LX, 0.32, -4.36), (2.2, 0.4, 0.32), "gold")
    cbox(b, (LX, 1.05, 1.3), (2.6, 1.5, 0.95), "plate_b")                     # 踵
    cbox(b, (LX, 0.75, 1.86), (0.9, 0.9, 0.2), "thruster")


def legs(s):
    """腿（縁取りの板）・膝（尖った膝当て + 外の油圧シリンダー）・脛（前の板 + V の稜 + 排気口）。"""
    t = s.part("legs", "thigh_r", "rightLeg", pivot=A.HIP)
    fr = layered_plate(t, (LX, 11.75, -1.82), (2.85, 4.3, 0.55), "plate2", top="plate",
                       rot=(-3, 0, 0), inset=0.3, trim="gold", rivet="rivet", n_rivets=3,
                       rivet_edge="top")
    line_on(t, fr["top"], "north", (0.74, 0.1), (0.74, 0.7), 0.18, 0.16, "glow")
    side = rbox(t, (LX - 1.78, 11.95, 0.05), (0.5, 4.4, 2.9), "plate", rot=(0, 0, -3))
    rivets(t, side, "west", 3, edge="bottom", margin=0.3)
    k = s.part("legs", "knee_r", "rightLeg", pivot=A.KNEE)
    kg = bevel(k, (LX, 8.45, -1.88), (2.3, 2.3, 0.8), "plate2", cut=0.38, axis="z")
    rbox(k, (LX, 9.55, -1.78), (1.55, 1.55, 0.7), "plate2", rot=(0, 0, 45))    # 上の尖り
    stick(k, kg[0], "north", 0.5, 0.06, (2.0, TRIM, 0.2), "gold", sink=0.05)
    rbox(k, (LX, 8.5, -2.38), (0.6, 0.6, 0.3), "gem", rot=(0, 0, 45))
    piston(k, (LX - 1.62, 10.9, 0.55), (LX - 1.5, 6.3, 0.45), r=0.27)          # 腿 → 脛
    g = s.part("legs", "shin_r", "rightLeg", pivot=A.KNEE)
    front = rbox(g, (LX, 4.75, -1.42), (2.75, 5.1, 0.55), "plate", rot=(4, 0, 0))
    stick(g, front, "north", 0.5, 0.04, (2.6, TRIM, 0.18), "gold", sink=0.05)
    line_on(g, front, "north", (0.1, 0.2), (0.14, 0.8), 0.18, 0.16, "glow")
    keel = rbox(g, (LX - 0.36, 4.95, -1.76), (0.78, 4.2, 0.48), "plate2", rot=(4, 24, 0))
    mirror_x(g, keel, about=LX)                                                  # 脚の中心で対称
    sd = rbox(g, (LX - 1.45, 4.85, -0.15), (0.45, 4.9, 2.7), "plate", rot=(0, 0, -4))
    sdr = rivets(g, sd, "west", 3, edge="bottom", margin=0.32)
    mirror_x(g, sd, sdr, about=LX)
    calf = rbox(g, (LX, 6.15, 1.62), (2.3, 2.5, 0.45), "plate_b", rot=(-12, 0, 0))
    vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))


def waist(s):
    """ベルト・留め金・細い前垂れ（腿の前を隠さない）・腰の脇の板・後ろ垂れ・外へ開く草摺。"""
    w = s.part("waist", "belt", "body")
    chamfer(w, (0, 16.95, 0.12), (6.7, 0.95, 4.5), "frame", cut=0.4, axis="y")
    bevel(w, (0, 16.95, -2.4), (1.8, 1.25, 0.5), "gold", cut=0.3, axis="z")
    fp = rbox(w, (0, 15.2, -2.08), (1.9, 2.5, 0.5), "plate2", rot=(-8, 0, 0))
    stick(w, fp, "north", 0.5, 0.06, (1.7, TRIM, 0.18), "gold", sink=0.05)
    hp = rbox(w, (-2.35, 15.75, -2.0), (2.1, 1.5, 0.45), "plate", rot=(-8, 14, 4))
    hpr = rivets(w, hp, "north", 2, edge="top", margin=0.3, span=(0.25, 0.75))
    mirror_x(w, hp, hpr)
    rs = rbox(w, (0, 15.05, 2.45), (4.6, 2.7, 0.5), "plate", rot=(14, 0, 0))
    rivets(w, rs, "south", 4, edge="top", margin=0.3)
    ts = s.part("waist", "tasset_r", w, pivot=(-3.35, 16.6, 0.0), rotation=(0, 0, 12))
    base = layered_plate(ts, (-3.75, 14.75, 0.0), (0.5, 3.5, 3.5), "plate", top="plate2",
                         face="west", inset=0.38, trim="gold", rivet="rivet", n_rivets=3,
                         rivet_edge="top")
    line_on(ts, base["top"], "west", (0.15, 0.4), (0.85, 0.4), 0.2, 0.16, "glow")


def torso(s):
    """胸（上が広い逆三角形）・V の胸板・中央の稜・星核・襟・脇の排気口・腹の三枚の板。"""
    c = s.part("torso", "chest", "body")
    up = bevel(c, (0, 24.2, 0.0), (9.2, 3.5, 5.0), "plate", cut=0.8, axis="y")
    bevel(c, (0, 21.6, -0.05), (7.2, 2.3, 4.6), "plate_b", cut=0.7, axis="y")
    sl = rbox(c, (-3.9, 22.15, 0.0), (0.5, 2.9, 4.0), "plate", rot=(0, 0, -24))
    pec = rbox(c, (-2.55, 24.2, -2.62), (3.55, 2.45, 0.55), "plate2", rot=(6, 17, 9))
    pt = stick(c, pec, "north", 0.5, 0.94, (3.4, TRIM, 0.18), "gold", sink=0.05)
    pr = rivets(c, pec, "north", 3, edge="bottom", margin=0.26, span=(0.2, 0.8))
    col = rbox(c, (-1.75, 26.25, 0.35), (1.45, 1.1, 3.6), "plate", rot=(0, 0, -24))
    sv = cbox(c, (-4.4, 23.7, 0.35), (0.4, 2.0, 2.4), "plate2")
    svv = vents(c, sv, "west", 3, box=(0.15, 0.2, 0.85, 0.8))
    mirror_x(c, sl, pec, pt, pr, col, sv, svv)
    rbox(c, (0, 24.35, -2.82), (1.25, 2.9, 0.5), "plate", rot=(-8, 0, 0))     # 中央の稜
    octa(c, (0, 22.75, -2.98), 2.25, 0.36, "gold", axis="z")                   # 星核の枠
    cbox(c, (0, 22.75, -3.12), (1.55, 1.55, 0.6), "core")                      # 星核（惑星の模様）
    gl = s.fx("glow", "core", c, pivot=(0, 22.75, -3.3))                       # 脈打つ光の輪
    ring(gl, (0, 22.75, -3.3), 1.22, 8, (0, 0.24, 0.24), "glow", axis="z")
    rivets(c, up[1], "south", 4, edge="top", margin=0.35, span=(0.12, 0.88))
    ab = s.part("torso", "abs", "body", pivot=(0, A.WAIST_Y, 0))               # 腹: 下ほど細い
    for i, (y, ww) in enumerate(((19.95, 4.0), (18.95, 3.6), (17.95, 3.2))):
        rbox(ab, (0, y, -1.98 + i * 0.05), (ww, 0.82, 0.48), ("plate2", "plate")[i % 2],
             rot=(-8, 0, 0))


def back(s):
    """バックパック（スリット・ボルト・センサー）・ホース・双発スラスター（炎は fx_thrust）。"""
    bk = s.part("back", "pack", "body")
    pk = bevel(bk, (0, 22.3, 3.5), (4.2, 5.2, 2.0), "plate2", cut=0.6, axis="z")
    vents(bk, pk[0], "south", 4, box=(0.25, 0.3, 0.75, 0.7), rim="frame")
    rivets(bk, pk[0], "south", 8, edge="border", margin=0.28)
    sensor(bk, (0, 24.35, 4.52), 0.3, "glow", "dark", facing=1)
    hs = cable(bk, [(-1.6, 19.9, 3.6), (-2.9, 17.6, 2.4)], 0.3, "dark", sag=0.35, rib="frame_lt")
    mirror_x(bk, hs)
    th = s.part("back", "thruster_r", bk, pivot=(-1.4, 20.6, 4.5), rotation=(18, 0, -8))
    octa(th, (-1.4, 19.6, 4.5), 1.7, 2.0, "plate", axis="y")
    octa(th, (-1.4, 18.15, 4.5), 2.15, 1.0, "frame", axis="y")
    cbox(th, (-1.4, 17.66, 4.5), (1.5, 0.16, 1.5), "thruster")
    fx = s.fx("thrust", "r", th, pivot=(-1.4, 17.6, 4.5))                     # 炎は局所 -Y へ全長で
    taper(fx, (-1.4, 17.6, 4.5), (-1.4, 11.5, 4.5), 1.7, 0.36, 3, "flame")


def arms(s):
    """二の腕（白い板）・肘当て・手首へ開く篭手（縁・スリット・リベット）・手の甲（指は frame7）。"""
    X = A.UPPER_ARM_X
    ua = s.part("arms", "upper_r", "rightArm", pivot=A.SHOULDER)
    op = rbox(ua, (X - 1.32, 21.35, 0.0), (0.45, 3.2, 2.5), "plate2", rot=(0, 0, 3))
    rivets(ua, op, "west", 2, edge="bottom", margin=0.3, span=(0.3, 0.7))
    rbox(ua, (X + 0.05, 21.4, -1.38), (2.2, 2.9, 0.42), "plate2", rot=(-3, 0, 0))
    octa(ua, (X, 19.72, 0.02), 2.86, 0.32, "gold", axis="y")                   # 腕輪
    el = s.part("arms", "elbow_r", "rightArm", pivot=A.ELBOW)
    bevel(el, (A.ELBOW[0], 18.55, 1.62), (2.1, 1.9, 0.6), "plate", cut=0.3, axis="z")
    fa = s.part("arms", "vambrace_r", "rightArm", pivot=A.WRIST)
    F = A.FOREARM_X
    bevel(fa, (F, 17.15, 0.0), (2.85, 1.9, 2.95), "plate", cut=0.45, axis="y")
    bevel(fa, (F + 0.02, 15.7, 0.0), (3.2, 1.75, 3.25), "plate", cut=0.5, axis="y")
    ob = rbox(fa, (F - 1.72, 16.3, 0.0), (0.42, 3.1, 2.6), "plate2", rot=(0, 0, 5))
    rivets(fa, ob, "west", 3, edge="top", margin=0.28)
    fv = rbox(fa, (F + 0.02, 16.4, -1.66), (2.2, 1.9, 0.35), "plate2", rot=(-5, 0, 0))
    vents(fa, fv, "north", 3, box=(0.2, 0.2, 0.8, 0.8), w=0.18)
    octa(fa, (F + 0.04, 14.72, 0.0), 3.3, 0.34, "gold", axis="y")              # 袖口
    h = s.part("arms", "hand_r", "rightArm", pivot=A.WRIST)
    rbox(h, (-7.42, 13.62, 0.0), (0.36, 1.7, 2.3), "plate2", rot=(0, 0, 4))
    for zf in (-0.93, -0.31, 0.31, 0.93):                                       # 指の甲当て
        beam(h, (-7.26, 12.25, zf), (-6.76, 11.55, zf), 0.56, 0.22, "plate")


def shoulders(s):
    """三層の肩当て: 丸い上の殻 → 白い上板（縁・リベット）→ 外へ垂れる二枚の板（金の縁・リベット）。"""
    p = s.part("shoulders", "pauldron_r", "rightArm")                          # pivot = A.SHOULDER
    dome = bevel(p, (-7.0, 25.55, 0.0), (3.4, 2.3, 4.6), "plate", cut=0.75, axis="x",
                 rot=(0, 0, -14))
    top = stick(p, dome[0], "up", 0.45, 0.5, (2.4, 3.7, 0.3), "plate2", sink=0.1)
    rivets(p, top, "up", 6, edge="border", margin=0.25, size=0.24)
    cbox(p, (-6.4, 24.15, 0.0), (2.0, 0.5, 3.6), "dark")                        # 裏の縁
    l1 = rbox(p, (-8.35, 23.75, 0.0), (0.55, 2.3, 4.5), "plate2", rot=(0, 0, 15),
              decals={"west": {"decal": "emblem"}})
    stick(p, l1, "west", 0.5, 0.06, (4.3, TRIM, 0.18), "gold", sink=0.05)
    rivets(p, l1, "west", 5, edge="top", margin=0.24, size=0.22)
    l2 = rbox(p, (-8.55, 22.05, 0.05), (0.48, 1.55, 3.9), "plate", rot=(0, 0, 11))
    stick(p, l2, "west", 0.5, 0.08, (3.7, TRIM, 0.18), "gold", sink=0.05)
    sensor(p, (-7.4, 24.45, -2.4), 0.26, "glow", "dark")


def helmet(s):
    """小さな兜（A.HEAD_* の箱に収める）: ドーム・冠・額・こめかみ・頬当て・面頬・顎・後頭部・しころ・角（飾り）。"""
    hz = A.HEAD_Z
    hm = s.part("helmet", "dome", "head")
    bevel(hm, (0, 30.65, hz + 0.3), (4.5, 1.7, 4.9), "plate", cut=0.6, axis="z")
    bevel(hm, (0, 31.62, hz + 0.45), (3.5, 0.9, 4.4), "plate", cut=0.32, axis="z")
    rbox(hm, (0, 30.7, hz - 2.2), (4.2, 1.3, 0.5), "plate", rot=(-22, 0, 0))   # 額
    sd = cbox(hm, (-2.12, 28.95, hz + 0.65), (0.42, 2.2, 3.5), "plate")         # こめかみ
    ck = rbox(hm, (-1.78, 28.4, hz - 1.15), (0.5, 2.0, 2.3), "plate", rot=(0, 20, -10))
    fc = rbox(hm, (-0.62, 28.45, hz - 2.2), (1.3, 1.25, 0.42), "plate2", rot=(8, 26, 0))
    mirror_x(hm, sd, ck, fc)
    cbox(hm, (0, 29.1, hz + 2.6), (4.0, 2.4, 0.45), "plate")                     # 後頭部
    rbox(hm, (0, 28.05, hz + 2.62), (3.7, 0.75, 0.45), "plate_b", rot=(22, 0, 0))  # しころ
    cr = s.part("helmet", "crest", "head", pivot=(0, 30.6, hz - 2.6), ornament=True)  # 角は飾り
    v = polyline(cr, [(-0.25, 30.55, hz - 2.62), (-1.3, 31.6, hz - 2.6),
                      (-2.6, 33.2, hz - 2.4)], [0.32, 0.24], [0.8, 0.5], "gold")
    mirror_x(cr, v)
    vz = s.part("visor", "eye", "head")                                          # バイザー
    cbox(vz, (0, 29.5, hz - 2.3), (3.7, 0.72, 0.3), "dark")
    fg = s.fx("glow", "visor", vz, pivot=(0, 29.5, hz - 2.48))                   # 変身時に閃光
    eye = rbox(fg, (-0.92, 29.5, hz - 2.48), (1.35, 0.34, 0.18), "visor", rot=(0, 8, 7))
    mirror_x(fg, eye)


def extra(s):
    """惑星の意匠（環・衛星・光輪・マント）。extra_* と fx_spin_* は計測から外れる。earth の luna_bit / cape を参照。"""
    pass
