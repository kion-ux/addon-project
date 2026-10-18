# -*- coding: utf-8 -*-
"""火星（アレス）のナノウェポン「軍神斧 アレス・ブレイカー」と星核「火星核 マーズ・コア」。

武器空間: 握りの中心 = 原点、斧頭 = -Z、刃 = -Y（片刃）、背のトゲ = +Y、平の法線 = ±X。
手に持つと 0.9 倍（astro_hold.SPEC["axe"]）。握りの前後 ±2.9 は篭手に隠れるので、
口金は z = -3.4 より先、柄頭は z = +3.9 より後ろに置く。

  form_0_grip    柄巻・真鍮の口金・重い柄頭（鈍い鉄の石突き）
  form_1_haft    鉄の柄・回る弾み車（fx_spin_gear）・柄に沿った杭打ち機（錆色の筒・赤熱の線・二本の棒）
  form_2_head    真紅の斧頭の台・窓から覗く火星（fx_spin_globe）・背の鈍いトゲ・先端の杭（pile。振ると突き出る）
  form_3_blade   三日月の刃（暗い鋼の放射状の板・溶岩のように赤熱した刃先・上下の角）。-Y へ伸びて現れる

星核: 錆色の火星（白い極冠）を、鋲の打たれた鉄の籠（縦の二重の輪・極の重い冠・赤道の留め具）が囲み、
傾いた真鍮の輪と、フォボス・ダイモスの小さな衛星が回る。
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_common import taper
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


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻・口金・重い柄頭
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.35), 1.75, 7.4, "wrap", uv_scale=8)
    for z, ln in ((-3.45, 0.7), (4.05, 0.7)):
        W.octa(grip, (0, 0, z), 2.3, ln, "brass", uv_scale=8)
    W.octa(grip, (0, 0, 0.35), 1.95, 0.45, "brass", uv_scale=8)
    W.octa(grip, (0, 0, 5.15), 2.5, 1.5, "plate", uv_scale=8)            # 柄頭
    W.cbox(grip, (0, 0, 5.15), (2.7, 0.5, 1.0), "frame", uv_scale=8)
    W.octa(grip, (0, 0, 6.05), 1.9, 0.4, "brass", uv_scale=8)
    W.cbox(grip, (0, 0, 6.65), (1.2, 1.2, 0.9), "iron", rotation=(0, 0, 45), uv_scale=8)   # 石突き

    # =====================================================================
    #  form_1_haft — 鉄の柄・弾み車・杭打ち機
    # =====================================================================
    haft = W.form(m, root, 1, "haft", (0, 0, -3.8))
    W.octa(haft, (0, 0, -9.4), 1.6, 11.4, "metal", uv_scale=6)
    for z in (-6.1, -13.4):
        W.octa(haft, (0, 0, z), 2.0, 0.5, "brass", uv_scale=8)
    gear = W.spin(m, haft, "gear", (0, 0, -4.7))
    W.ring(gear, (0, 0, -4.7), 1.4, 8, (0, 0.45, 0.55), "brass", axis="z", styles=["brass", "frame"],
           uv_scale=10)
    W.octa(gear, (0, 0, -4.7), 1.2, 0.4, "glow", uv_scale=10)
    # 杭打ち機: 柄の背（+Y）に沿う錆色の筒、両端の真鍮の蓋、柄への留め具、赤熱の線、斧頭へ伸びる二本の棒
    W.octa(haft, (0, 1.95, -9.2), 2.1, 6.0, "plate2", uv_scale=7)
    for z in (-6.35, -12.05):
        W.octa(haft, (0, 1.95, z), 2.35, 0.5, "brass", uv_scale=8)
        W.cbox(haft, (0, 0.95, z), (1.1, 1.1, 0.7), "frame", uv_scale=8)
    W.cbox(haft, (0, 1.95, -9.2), (2.25, 0.5, 3.4), "hazard", uv_scale=8)
    heat = W.glow(m, haft, "heat", (0, 3.05, -9.2))
    W.cbox(heat, (0, 3.02, -9.2), (0.36, 0.2, 4.4), "edge_hot", uv_scale=10)
    for x in (-0.55, 0.55):
        W.beam(haft, (x, 1.75, -12.3), (x, 1.2, -15.3), 0.42, 0.42, "iron", uv_scale=10)
    W.cbox(haft, (0, -0.95, -9.0), (0.9, 0.3, 2.6), "vent", uv_scale=10)   # 柄の腹の排気口

    # =====================================================================
    #  form_2_head — 斧頭の台・火星の窓・背のトゲ・杭
    # =====================================================================
    head = W.form(m, root, 2, "head", (0, 0, -14.9))
    W.bevel(head, (0, 0.3, Z_HEAD), (2.6, 4.2, 6.8), "plate", cut=0.7, axis="x", edge_style="plate_b",
            uv_scale=6)
    for z in (Z_HEAD + 3.55, Z_HEAD - 3.55):                                  # 台の上下の真鍮の帯
        W.cbox(head, (0, 0.3, z), (2.75, 3.6, 0.45), "brass", uv_scale=8)
    globe = W.spin(m, head, "globe", (0, 0.2, Z_HEAD))
    W.sphere(globe, (0, 0.2, Z_HEAD), 1.5, "globe", uv_scale=14)
    for s in (-1, 1):
        W.ring(head, (s * 1.32, 0.2, Z_HEAD), 1.72, 10, (0, 0.34, 0.3), "brass", axis="x", uv_scale=10)
    # 背の鈍いトゲ（真鍮の座金 → 先細りの鉄）
    W.octa(head, (0, 2.55, Z_HEAD + 0.4), 2.1, 0.55, "brass", axis="y", uv_scale=8)
    taper(head, (0, 2.6, Z_HEAD + 0.4), (0, 7.0, Z_HEAD + 1.6), 1.9, 0.45, 3, "steel", uv_scale=8)
    # 杭（先端から突き出る。振ると前へ打ち出す: WEAPON_ANIMS の swing）
    W.octa(head, (0, 0, Z_HEAD - 4.25), 2.0, 0.9, "frame", uv_scale=8)
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
    # 角（上下へ反り返る先）
    for s in (-1, 1):
        p0 = _yz(CO, RO - 2.0, s * 44)
        p1 = _yz(CO, RO - 1.2, s * 56)
        p2 = _yz(CO, RO - 1.8, s * 66)
        W.polyline(blade, [(0, p0[0], p0[1]), (0, p1[0], p1[1]), (0, p2[0], p2[1])], [0.86, 0.76],
                   [3.0, 1.2], "blade_body", uv_scale=6)
    # 赤熱した刃先（外の弧に沿って）
    pts = []
    for k in range(15):
        a = -63.0 + 126.0 * k / 14
        r = RO + 0.1 if abs(a) <= 46 else RO + 0.1 - (abs(a) - 46) * 0.1
        y, z = _yz(CO, r, a)
        pts.append((0, y, z))
    W.polyline(blade, pts, 1.05, 0.62, "edge_hot", uv_scale=8)
    # 刃の付け根の鋲の列と、放射状の溶岩のひび（両面）
    for a in (-36, -12, 12, 36):
        y, z = _yz(CO, _r_in(a) + 0.35, a)
        W.cbox(blade, (0, y, z), (1.04, 0.5, 0.5), "brass", rotation=(45, 0, 0), uv_scale=12)
    for a, r0, r1 in ((-26, 5.0, 7.4), (4, 4.6, 7.0), (30, 5.2, 7.6)):
        y0, z0 = _yz(CO, r0, a)
        y1, z1 = _yz(CO, r1, a + 6)
        W.beam(blade, (0, y0, z0), (0, y1, z1), 0.98, 0.3, "edge", uv_scale=10)
    # 刃と台の継ぎ目の鉄の帯
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
                                     "iron", "brass", "frame", "hazard", "phobos", "deimos")}


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
#  ループは 6 秒（idle_length）なので周波数は 60°/秒の倍数
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_gear": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "fx_spin_globe": {"rotation": ["q.anim_time * 60.0", 0, 0]},
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
