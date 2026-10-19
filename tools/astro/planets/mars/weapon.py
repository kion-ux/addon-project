# -*- coding: utf-8 -*-
"""火星（アレス）のナノウェポン「軍神斧 アレス・ブレイカー」と星核「火星核 マーズ・コア」。

武器空間: 握りの中心 = 原点、斧頭 = -Z、刃 = -Y（片刃）、背のトゲ = +Y、平の法線 = ±X。
手に持つと 0.9 倍（astro_hold.SPEC["axe"]）。握りの前後 ±2.9 は篭手に隠れるので、
口金は z = -3.4 より先、柄頭は z = +3.9 より後ろに置く。

v1.1 の細部（7 頭身のスーツに合わせた作り込み）:
  form_0_grip    柄巻と暗い革の締め紐・鋲の打たれた真鍮の口金・真紅の柄頭（真鍮の鋲・赤熱の輪 fx_glow）・
                 鈍い鉄の石突き
  form_1_haft    鉄の柄（両面に溶岩の光る彫り溝）・鋲の真鍮の帯・歯の付いた弾み車（fx_spin_gear）・
                 柄に沿った杭打ち機（錆色の筒・冷却フィン・警告の帯・両脇の圧力計・赤熱の線・鋲の蓋・二本の棒）
  form_2_head    真紅の斧頭の台（真鍮の帯）・窓から覗く火星（fx_spin_globe）と両面の真鍮の輪・四隅の鋲・
                 光る彫り溝・上面の小さな発光器・背の鈍いトゲ（鉄の先）・先端の杭（pile。振ると突き出る）と鋲の案内輪
  form_3_blade   三日月の刃（暗い鋼の放射状の板・研いだ刃・溶岩のように脈打つ刃先 fx_glow_edge・上下の角と鉄の先）・
                 刃の付け根の真紅の当て板と真鍮の縁・鋲の列・刃先に沿う光る彫り溝と放射状のひび。-Y へ伸びて現れる

星核: 錆色の火星（白い極冠）を、鋲の打たれた鉄の籠（縦の二重の輪・極の重い冠・赤道の留め具）が囲み、
傾いた真鍮の輪と、フォボス・ダイモスの小さな衛星が回る。
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_common import cable, taper
from astro_paint import core_styles, weapon_styles
from planets.mars import suit as S

S.install_painter()          # 擦り傷・砂ぼこりの塗り（kind "ares"）と衛星の岩肌（"ares_rock"）

KIND = "axe"

Z_HEAD = -18.2               # 斧頭（火星の窓）の中心
CO = (-0.6, Z_HEAD)          # 三日月の刃の外の弧の中心 (y, z)
RO = 9.6                     # 外の弧の半径
CI = (4.6, Z_HEAD)           # 内の弧（えぐれ）の中心
RI = 8.4
EDGE = (255, 112, 36)        # 赤熱した刃先


def _yz(c, r, a):
    """(y, z) の中心 c から、-Y を 0°・-Z（先）を正にした角度 a（度）で r 離れた点。"""
    t = math.radians(a)
    return (c[0] - r * math.cos(t), c[1] - r * math.sin(t))


def _r_in(a):
    """角度 a の放射の線が、内の弧（えぐれ）と交わる半径。"""
    t = math.radians(a)
    d = (-math.cos(t), -math.sin(t))
    v = (CO[0] - CI[0], CO[1] - CI[1])
    b = v[0] * d[0] + v[1] * d[1]
    c = v[0] ** 2 + v[1] ** 2 - RI ** 2
    return -b + math.sqrt(b * b - c)


def _studs(bone, z, r, style="rivet", size=0.3, n=4, phase=0.0):
    """Z 軸の筒（口金・帯）の周りに打つ鋲（n 個。phase=0 で ±X・±Y）。"""
    for i in range(n):
        a = math.radians(phase + 360.0 * i / n)
        p = (r * math.cos(a), r * math.sin(a), z)
        W.cbox(bone, p, (size, size, size), style, rotation=(0, 0, phase + 360.0 * i / n),
               uv_scale=12)


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻・締め紐・鋲の口金・柄頭（鋲・赤熱の輪）・石突き
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.35), 1.75, 7.4, "wrap", uv_scale=8)
    for z in (-1.75, 2.4):                                                 # 暗い革の締め紐
        W.octa(grip, (0, 0, z), 1.92, 0.3, "dark", uv_scale=10)
    W.octa(grip, (0, 0, 0.35), 1.95, 0.45, "brass", uv_scale=8)
    for z in (-3.45, 4.05):                                                # 真鍮の口金と鋲
        W.octa(grip, (0, 0, z), 2.3, 0.7, "brass", uv_scale=8)
        _studs(grip, z, 1.2, "rivet", 0.28)
    W.octa(grip, (0, 0, 5.1), 2.5, 1.3, "plate", uv_scale=8)              # 柄頭
    W.cbox(grip, (0, 0, 5.1), (2.7, 0.5, 0.9), "frame", uv_scale=8)
    for sx in (-1, 1):
        for sy in (-1, 1):
            W.cbox(grip, (sx * 1.27, sy * 0.72, 5.1), (0.2, 0.3, 0.3), "brass", uv_scale=12)
    pom = W.glow(m, grip, "pommel", (0, 0, 5.86))
    W.octa(pom, (0, 0, 5.86), 2.2, 0.24, "edge_hot", uv_scale=10)
    W.octa(grip, (0, 0, 6.12), 1.9, 0.4, "brass", uv_scale=8)
    W.cbox(grip, (0, 0, 6.65), (1.2, 1.2, 0.9), "iron", rotation=(0, 0, 45), uv_scale=8)   # 石突き

    # =====================================================================
    #  form_1_haft — 鉄の柄・光る彫り溝・弾み車・杭打ち機
    # =====================================================================
    haft = W.form(m, root, 1, "haft", (0, 0, -3.8))
    W.octa(haft, (0, 0, -9.4), 1.6, 11.4, "metal", uv_scale=6)
    for z in (-6.1, -13.4):
        W.octa(haft, (0, 0, z), 2.0, 0.5, "brass", uv_scale=8)
        for sx in (-1, 1):
            W.cbox(haft, (sx * 1.02, -0.3, z), (0.2, 0.28, 0.28), "rivet", uv_scale=12)
    for sx in (-1, 1):                                                     # 両面の溶岩の彫り溝
        W.cbox(haft, (sx * 0.79, -0.25, -9.75), (0.18, 0.22, 6.4), "edge", uv_scale=10)
    gear = W.spin(m, haft, "gear", (0, 0, -4.7))
    W.ring(gear, (0, 0, -4.7), 1.4, 10, (0, 0.45, 0.55), "brass", axis="z", styles=["brass", "frame"],
           uv_scale=10)
    W.ring(gear, (0, 0, -4.7), 1.78, 10, (0.36, 0.34, 0.4), "iron", axis="z", phase=18.0,
           uv_scale=12)                                                   # 歯
    W.octa(gear, (0, 0, -4.7), 1.2, 0.4, "glow", uv_scale=10)
    # 杭打ち機: 柄の背（+Y）に沿う錆色の筒、両端の鋲の蓋、冷却フィン、警告の帯、圧力計、赤熱の線、
    # 柄への留め具、斧頭へ伸びる二本の棒
    W.octa(haft, (0, 1.95, -9.2), 2.1, 6.0, "plate2", uv_scale=7)
    for z in (-6.35, -12.05):
        W.octa(haft, (0, 1.95, z), 2.35, 0.5, "brass", uv_scale=8)
        W.cbox(haft, (0, 0.95, z), (1.1, 1.1, 0.7), "frame", uv_scale=8)
        for sx in (-1, 1):
            W.cbox(haft, (sx * 1.2, 2.3, z), (0.2, 0.28, 0.28), "rivet", uv_scale=12)
    for z in (-7.05, -11.35):
        W.octa(haft, (0, 1.95, z), 2.4, 0.26, "frame", uv_scale=10)
    W.cbox(haft, (0, 1.95, -9.2), (2.25, 0.5, 2.6), "hazard", uv_scale=8)
    for sx in (-1, 1):                                                     # 圧力計（両脇）
        W.octa(haft, (sx * 1.12, 2.15, -10.6), 0.9, 0.3, "iron", axis="x", uv_scale=12)
        W.cbox(haft, (sx * 1.3, 2.15, -10.6), (0.16, 0.4, 0.4), "glow", uv_scale=12)
    heat = W.glow(m, haft, "heat", (0, 3.05, -9.2))
    W.cbox(heat, (0, 3.02, -9.2), (0.36, 0.2, 4.4), "edge_hot", uv_scale=10)
    for x in (-0.55, 0.55):
        W.beam(haft, (x, 1.75, -12.3), (x, 1.2, -15.3), 0.42, 0.42, "iron", uv_scale=10)
    W.cbox(haft, (0, -0.95, -9.0), (0.9, 0.3, 2.6), "vent", uv_scale=10)   # 柄の腹の排気口
    # 蛇腹の油圧ホース（筒の前の蓋から斧頭の脇へ）
    cable(haft, [(1.0, 2.5, -12.2), (1.25, 2.1, -13.5), (1.05, 1.6, -14.7)], 0.3, "dark",
          rib="brass", rib_every=2, uv_scale=12)

    # =====================================================================
    #  form_2_head — 斧頭の台・火星の窓・鋲・彫り溝・発光器・背のトゲ・杭
    # =====================================================================
    head = W.form(m, root, 2, "head", (0, 0, -14.9))
    W.bevel(head, (0, 0.3, Z_HEAD), (2.6, 4.2, 6.8), "plate", cut=0.7, axis="x", edge_style="plate_b",
            uv_scale=6)
    for z in (Z_HEAD + 3.55, Z_HEAD - 3.55):                                  # 台の上下の真鍮の帯
        W.cbox(head, (0, 0.3, z), (2.75, 3.6, 0.45), "brass", uv_scale=8)
    globe = W.spin(m, head, "globe", (0, 0.2, Z_HEAD))
    W.sphere(globe, (0, 0.2, Z_HEAD), 1.5, "globe", uv_scale=14)
    for s in (-1, 1):
        x = s * 1.32
        W.ring(head, (x, 0.2, Z_HEAD), 1.72, 10, (0, 0.34, 0.3), "brass", axis="x", uv_scale=10)
        for dz in (-2.65, 2.65):                                           # 四隅の鋲
            for y in (-1.25, 1.75):
                W.cbox(head, (s * 1.36, y, Z_HEAD + dz), (0.2, 0.3, 0.3), "rivet", uv_scale=12)
        for z0, z1 in ((Z_HEAD + 2.0, Z_HEAD + 3.15), (Z_HEAD - 2.0, Z_HEAD - 3.15)):   # 光る彫り溝
            W.cbox(head, (s * 1.33, 0.2, (z0 + z1) / 2), (0.18, 0.2, abs(z1 - z0)), "edge",
                   uv_scale=12)
    for z in (Z_HEAD - 2.3, Z_HEAD + 2.5):                                  # 上面の小さな発光器
        W.cbox(head, (0, 2.44, z), (0.62, 0.16, 0.62), "dark", uv_scale=12)
        W.cbox(head, (0, 2.5, z), (0.32, 0.16, 0.32), "glow", uv_scale=12)
    # 背の鈍いトゲ（真鍮の座金 → 先細りの鉄 → 鉄の先）
    W.octa(head, (0, 2.55, Z_HEAD + 0.4), 2.1, 0.55, "brass", axis="y", uv_scale=8)
    taper(head, (0, 2.6, Z_HEAD + 0.4), (0, 7.0, Z_HEAD + 1.6), 1.9, 0.45, 3, "steel", uv_scale=8)
    W.octa(head, (0, 4.1, Z_HEAD + 0.82), 1.55, 0.3, "brass", axis="y", rot=(-15, 0, 0),
           uv_scale=10)
    W.cbox(head, (0, 7.05, Z_HEAD + 1.62), (0.5, 0.5, 0.5), "iron", rotation=(0, 45, 0), uv_scale=12)
    # 杭（先端から突き出る。振ると前へ打ち出す: WEAPON_ANIMS の swing）と鋲の案内輪
    W.octa(head, (0, 0, Z_HEAD - 4.25), 2.0, 0.9, "frame", uv_scale=8)
    _studs(head, Z_HEAD - 4.25, 1.05, "brass", 0.3, 4, 45.0)
    pile = W.part(m, head, "pile", (0, 0, Z_HEAD - 4.4))
    W.octa(pile, (0, 0, Z_HEAD - 5.3), 1.25, 2.0, "iron", uv_scale=8)
    W.octa(pile, (0, 0, Z_HEAD - 6.6), 0.95, 0.8, "steel", uv_scale=8)
    W.cbox(pile, (0, 0, Z_HEAD - 7.25), (0.6, 0.6, 0.6), "steel", rotation=(0, 0, 45), uv_scale=8)

    # =====================================================================
    #  form_3_blade — 三日月の刃（-Y へ伸びて現れる）
    # =====================================================================
    blade = W.form(m, root, 3, "blade", (0, -1.4, Z_HEAD))
    n = 11
    for i in range(n):
        a = -46.0 + 92.0 * i / (n - 1)
        y0, z0 = _yz(CO, _r_in(a) - 0.7, a)
        y1, z1 = _yz(CO, RO - 1.3, a)
        W.beam(blade, (0, y0, z0), (0, y1, z1), 0.9, 1.75, "blade_body", uv_scale=6)
        y2, z2 = _yz(CO, RO - 1.55, a)                                      # 研いだ刃（明るい鋼）
        y3, z3 = _yz(CO, RO, a)
        W.beam(blade, (0, y2, z2), (0, y3, z3), 0.7, 1.75, "blade", uv_scale=6)
    # 角（上下へ反り返る先）と鉄の先
    for s in (-1, 1):
        p0 = _yz(CO, RO - 2.0, s * 44)
        p1 = _yz(CO, RO - 1.2, s * 56)
        p2 = _yz(CO, RO - 1.8, s * 66)
        W.polyline(blade, [(0, p0[0], p0[1]), (0, p1[0], p1[1]), (0, p2[0], p2[1])], [0.86, 0.76],
                   [3.0, 1.2], "blade_body", uv_scale=6)
        W.cbox(blade, (0, p2[0], p2[1]), (0.95, 0.5, 0.5), "iron", rotation=(s * -66.0, 0, 0),
               uv_scale=12)
    # 赤熱した刃先（外の弧に沿って。ゆっくり脈打つ）
    eg = W.glow(m, blade, "edge", (0, CO[0], CO[1]))
    pts = []
    for k in range(15):
        a = -63.0 + 126.0 * k / 14
        r = RO + 0.1 if abs(a) <= 46 else RO + 0.1 - (abs(a) - 46) * 0.1
        y, z = _yz(CO, r, a)
        pts.append((0, y, z))
    W.polyline(eg, pts, 1.05, 0.62, "edge_hot", uv_scale=8)
    # 刃先に沿う光る彫り溝（両面に見える）と、放射状の溶岩のひび
    arc = [(0,) + _yz(CO, 6.95, -40.0 + 80.0 * k / 7) for k in range(8)]
    W.polyline(blade, arc, 0.98, 0.22, "edge", uv_scale=10)
    for a, r0, r1 in ((-26, 5.0, 7.4), (4, 4.6, 7.0), (30, 5.2, 7.6)):
        y0, z0 = _yz(CO, r0, a)
        y1, z1 = _yz(CO, r1, a + 6)
        W.beam(blade, (0, y0, z0), (0, y1, z1), 0.98, 0.3, "edge", uv_scale=10)
    # えぐれの縁の黒い鋼の帯（刃の内側の重ね）
    inner = [(0,) + _yz(CO, _r_in(a) - 0.55, a) for a in (-46, -34, -22, -10, 0, 10, 22, 34, 46)]
    W.polyline(blade, inner, 1.06, 0.4, "steel", uv_scale=10)
    # 刃の付け根: 鋲の列・真紅の当て板と真鍮の縁（両面）・鉄の帯
    for a in (-40, -27, -13, 0, 13, 27, 40):
        y, z = _yz(CO, _r_in(a) + 0.35, a)
        W.cbox(blade, (0, y, z), (1.04, 0.42, 0.42), "brass", rotation=(45, 0, 0), uv_scale=12)
    for s in (-1, 1):
        W.cbox(blade, (s * 0.55, -2.75, Z_HEAD), (0.24, 1.1, 5.6), "plate", uv_scale=8)
        W.cbox(blade, (s * 0.6, -3.22, Z_HEAD), (0.2, 0.24, 5.4), "brass", uv_scale=10)
    W.cbox(blade, (0, -2.1, Z_HEAD), (1.3, 0.8, 6.4), "frame", uv_scale=8)


def build_core(m, root):
    """火星核: 錆色の火星（白い極冠）を鋲の鉄の籠が囲み、真鍮の輪と二つの小さな衛星が回る。直径 ≒ 6.6。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.95, "globe", uv_scale=16)
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    # 縦の二重の輪（側面・正面）。鉄の帯に真鍮の鋲
    W.ring(cage, (0, 0, 0), 2.6, 12, (0, 0.5, 0.75), "iron", axis="x", uv_scale=8)
    W.ring(cage, (0, 0, 0), 2.6, 12, (0, 0.5, 0.75), "iron", axis="z", uv_scale=8)
    for a in (45, 135, 225, 315):
        t = math.radians(a)
        for p in ((0, 2.65 * math.cos(t), -2.65 * math.sin(t)), (-2.65 * math.sin(t), 2.65 * math.cos(t), 0)):
            W.cbox(cage, p, (0.5, 0.5, 0.5), "brass", rotation=(45, 45, 0), uv_scale=12)
    # 極の重い冠（上下）
    for s in (-1, 1):
        y = s * 2.95
        W.octa(cage, (0, y, 0), 2.1, 0.8, "plate", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.55, 0), 1.3, 0.45, "brass", axis="y", uv_scale=10)
        W.cbox(cage, (0, y + s * 0.95, 0), (0.6, 0.5, 0.6), "iron", rotation=(0, 45, 0), uv_scale=12)
    # 赤道の留め具（四方）
    for a in (45, 135, 225, 315):
        t = math.radians(a)
        p = (2.55 * math.sin(t), 0, 2.55 * math.cos(t))
        W.cbox(cage, p, (0.9, 1.1, 0.9), "plate2", rotation=(0, a, 0), uv_scale=10)
        W.cbox(cage, (p[0] * 1.13, 0, p[2] * 1.13), (0.5, 0.36, 0.5), "glow", rotation=(0, a, 0),
               uv_scale=12)
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    ra = W.spin(m, rings, "ring_a", (0, 0, 0), rotation=(16, 0, -10))
    W.ring(ra, (0, 0, 0), 3.15, 14, (0, 0.28, 0.42), "brass", axis="y", styles=["brass", "glow"],
           uv_scale=10)
    mo = W.spin(m, rings, "moons", (0, 0, 0), rotation=(-24, 0, 14))
    W.cbox(mo, (3.35, 0, 0), (0.85, 0.65, 0.7), "phobos", rotation=(20, 30, 10), uv_scale=12)
    W.cbox(mo, (3.25, 0.05, 0.15), (0.6, 0.6, 0.6), "phobos", rotation=(-10, 60, 40), uv_scale=12)
    W.cbox(mo, (-3.4, 0, 0), (0.5, 0.5, 0.5), "deimos", rotation=(45, 0, 45), uv_scale=12)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def _common():
    st = S.SUIT_STYLES
    return {k: dict(st[k]) for k in ("plate", "plate_b", "plate2", "plate2_b", "steel", "steel_b",
                                     "iron", "brass", "frame", "hazard", "phobos", "deimos",
                                     "rivet")}


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        **_common(),
        blade={"kind": "blade", "base": (176, 166, 160), "light": (246, 238, 228), "dark": (98, 88, 86),
               "line": (40, 32, 30), "glint_period": 22, "fuller": False},
        blade_body=S._armor((84, 74, 74), panel=0, outline=False, bevel=False, scratch=0.012,
                            dust_k=0.3, scratch_col=(200, 188, 180)),
        edge_hot={"glow": EDGE, "emit": 14, "sat": 0.55},
        edge={"glow": (255, 150, 60), "emit": 30, "sat": 0.4},
        metal={"base": (70, 62, 62), "light": (134, 122, 118), "dark": (36, 30, 30), "line": (16, 12, 12)},
        wrap={"base": (30, 24, 24), "strap": (150, 56, 34), "skin": (214, 196, 176)},
        dark={"base": (28, 22, 22), "glow": EDGE, "line": (8, 6, 6)},
        globe=W.globe_style("mars", emit=170),
        glow={"glow": (255, 128, 44)},
    )


def CORE_STYLES(key):
    return core_styles(key, **_common(), globe=W.globe_style("mars", emit=170))


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）。v.astro_sw 攻撃の振り 0→1 / v.astro_usew 右クリック中 0→1
#  待機の q.anim_time は `q.anim_time * 度/秒` の形だけ（速さは 60°/秒の倍数にそろえてループを短く）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_gear": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "fx_spin_globe": {"rotation": ["q.anim_time * 60.0", 0, 0]},
        "fx_glow_heat": W.pulse_expr(180, 0.06),
        "fx_glow_pommel": W.pulse_expr(120, 0.05),
        "fx_glow_edge": W.pulse_expr(60, 0.012),      # 刃先の溶岩がゆっくり脈打つ（弧の中心まわり）
    },
    "swing": {
        # 振り下ろした瞬間に杭が打ち出され、弾み車が一回転する
        "pile": {"position": [0, 0, "-math.pow(math.sin(v.astro_sw * 180.0), 3.0) * 2.4"]},
        "fx_spin_gear": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_1_haft": "z", "form_3_blade": "y"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 60.0", 0]},
        "fx_spin_ring_a": {"rotation": [0, "-q.anim_time * 120.0", 0]},
        "fx_spin_moons": {"rotation": [0, "q.anim_time * 180.0", 0]},
    },
}
