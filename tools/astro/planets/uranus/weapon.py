# -*- coding: utf-8 -*-
"""天王星（ウラノス）のナノウェポン「傾天弩 ティルト・ボウガン」と星核「天王星核 ウラヌス・コア」（v1.1: 細部の作り込み）。

武器空間: 握りの中心 = 原点、銃口 = -Z、弓は ±X に張る、機関部は握りの上（+Y）。16 単位 = 1 ブロック。
手に持つと 0.85 倍（astro_hold.SPEC["crossbow"]）。握りの前後 ±3.1 は篭手に隠れる。

  form_0_grip    握り（溝のある芯・青緑の板と発光線・紺の口金）、握りと機関部の首と脇の油圧の管、
                 引き金と用心金、霜の輪と ◆ の宝玉と後ろへ伸びる氷の棘の握りの尻
  form_1_body    機関部: 面を切った淡い青緑の胴に彫った紺の溝、二層の側板（青緑 → 霜の縁 → 発光線）とリベットの列・
                 枠付きの排気スリット・霜の ◆、紺の矢溝と歯の並ぶレールと光る矢道、照門の ◆ と 98° 傾いた小さな環の照準
                 （fx_spin_sight）、下の氷晶の弾倉（窓から光る）、銃口の霜の覆いと左右の小さな放射器、
                 弓へ行くケーブル
  form_2_limbs   弓: 紺の弓台から ±X へ後ろへ反って張る二段の弓（霜の前縁・発光線・青緑の重ね板・◆・関節の軸）、
                 先端の滑車（ボルトの輪・光る軸）と氷晶の弓端、弦の留め具と光る弦（矢の尻へ）。形成で ±X へ「開く」
  form_3_bolt    装填された絶対零度の矢（氷の矢柄・霜の帯・光る象嵌・結晶の鏃・◆ の矢羽根・紺の筈。fx_glow_bolt で脈打つ）
  form_4_ring    銃口の前で 98° 傾いて回る小さな環（fx_spin_tilt: 光の帯・紺の帯と 5 つの氷の衛星 /
                 fx_spin_dust: 逆へ回る氷の塵）
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_common import cable, line_on, rivets, sensor, stick, vents
from astro_paint import core_styles, weapon_styles

from .suit import SUIT_STYLES, crystal, diamond, diamond_stack, moon

KIND = "crossbow"

Y0 = 3.5            # 機関部の中心の高さ（握りの上）
Z_BACK = -2.4       # 機関部の後端（これより後ろ・上は前腕と篭手に入る）
Z_FRONT = -12.4     # 弓台
Z_MUZ = -14.0       # 発射口
Z_RING = -16.2      # 傾いた環の中心
Z_NOCK = -3.5       # 弦を掛ける所（矢の尻）
TILT = (8, 26, 0)   # 環の傾き（98° の意匠: 縦に立ち、上が 8° 前へ、26° ひねる）

ICON = {"weapon": (24, -58, -38), "core": (28, -16, 0)}

# スーツと同じ素材（霜の白・紺・氷・結晶・縁）
_SHARED = {k: SUIT_STYLES[k] for k in ("frost", "frost_p", "navy", "rim", "ice", "crystal", "ringglow",
                                       "ringband", "gem", "glow")}
_SHARED["rivet"] = {"kind": "trim", "base": (186, 206, 216), "light": (246, 252, 255),
                    "dark": (96, 120, 138), "line": (36, 52, 66), "bevel": False}

FINE = 12           # 小物の uv_scale（1 単位あたりのテクセル）


# ===========================================================================
#  ナノウェポン
# ===========================================================================
def build_weapon(m, root):
    grip(m, root)
    body(m, root)
    limbs(m, root)
    bolt(m, root)
    tilt_ring(m, root)


def grip(m, root):
    """form_0_grip — 握り・口金・首と油圧の管・引き金と用心金・握りの尻。"""
    g = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(g, (0, 0, 0.0), 1.6, 5.2, "frame", uv_scale=8)                           # 溝のある握りの芯
    for s in (-1, 1):                                                                # 握りの青緑の板と発光線
        W.cbox(g, (s * 0.72, -0.1, 0.0), (0.3, 1.1, 4.4), "plate2", uv_scale=8)
        W.cbox(g, (s * 0.9, -0.1, 0.0), (0.12, 0.2, 3.6), "glow", uv_scale=FINE)
    for z in (-2.75, 2.75):
        W.octa(g, (0, 0, z), 2.0, 0.5, "navy", uv_scale=8)
    # 握りと機関部の首（紺）と、両脇を走る細い油圧の管
    W.beam(g, (0, 0.6, -3.2), (0, Y0 - 0.6, -4.2), 1.3, 1.5, "frame", uv_scale=8)
    for s in (-1, 1):
        cable(g, [(s * 0.78, 0.55, -2.4), (s * 0.82, 1.6, -3.4), (s * 0.7, Y0 - 1.25, -4.6)], 0.24,
              "navy", seg=0.9, uv_scale=FINE)
    # 用心金と引き金
    W.polyline(g, [(0, Y0 - 1.2, -5.8), (0, -0.8, -5.4), (0, -1.4, -3.6)], 0.5, 0.5, "navy", uv_scale=10)
    W.beam(g, (0, Y0 - 1.3, -4.5), (0, 0.4, -4.7), 0.45, 0.4, "rim", uv_scale=12)
    W.cbox(g, (0, -0.95, -4.95), (0.36, 0.3, 0.3), "rivet", uv_scale=FINE)
    # 握りの尻: 淡い八角 + 霜の輪 + ◆ の宝玉 + 後ろへ伸びる小さな氷の棘
    W.octa(g, (0, -0.05, 3.3), 1.7, 0.75, "plate2", uv_scale=8)
    W.octa(g, (0, -0.05, 3.0), 1.86, 0.22, "rim", uv_scale=FINE)
    diamond_stack(g, (0, -0.05, 3.72), [(1.0, 0.2, "frost"), (0.55, 0.2, "gem")], facing=1)
    crystal(g, (0, -0.05, 3.8), (0, -0.25, 1.0), 1.0, 0.36, "ice", tip=0.55, uv_scale=FINE)


def body(m, root):
    """form_1_body — 機関部（握りの前上。後端は篭手の前）。"""
    b = W.form(m, root, 1, "body", (0, Y0, Z_BACK))
    L = Z_BACK - Z_FRONT
    zc = (Z_BACK + Z_FRONT) / 2
    core = W.bevel(b, (0, Y0, zc), (2.8, 2.8, L), "plate", cut=0.65, axis="z", uv_scale=6)
    # 後端の蓋（紺）と ◆ の灯り
    W.cbox(b, (0, Y0, Z_BACK + 0.2), (2.4, 2.4, 0.5), "navy", uv_scale=8)
    diamond(b, (0, Y0, Z_BACK + 0.48), 1.0, 0.16, "glow", uv_scale=FINE)
    # 矢溝（紺）・光る矢道・レールの歯
    W.cbox(b, (0, Y0 + 1.5, zc - 0.6), (1.3, 0.45, L + 1.6), "navy", uv_scale=6)
    W.cbox(b, (0, Y0 + 1.74, zc - 0.6), (0.45, 0.16, L + 1.2), "energy", uv_scale=8)
    for k in range(5):
        z = Z_BACK - 1.6 - k * 1.85
        for s in (-1, 1):
            W.cbox(b, (s * 0.5, Y0 + 1.82, z), (0.24, 0.2, 0.55), "frame", uv_scale=FINE)
    # 胴の側面に彫った紺の溝（上下 2 本）
    for s in (-1, 1):
        face = "east" if s > 0 else "west"
        for bb in (0.3, 0.72):
            line_on(b, core[1], face, (0.08, bb), (0.92, bb), 0.16, 0.16, "navy", sink=0.1,
                    uv_scale=FINE)
    # 二層の側板: 青緑の板 → 霜の縁 → 発光線、リベットの列、霜の ◆、枠付きの排気スリット
    for s in (-1, 1):
        face = "east" if s > 0 else "west"
        sp = W.rbox(b, (s * 1.55, Y0 - 0.1, zc), (0.6, 2.3, L - 1.6), "plate2", rot=(0, 0, -12 * s),
                    uv_scale=6)
        stick(b, sp, face, 0.5, 0.94, (L - 1.8, 0.24, 0.16), "rim", sink=0.05, uv_scale=FINE)
        line_on(b, sp, face, (0.06, 0.66), (0.62, 0.66), 0.16, 0.16, "glow", uv_scale=FINE)
        rivets(b, sp, face, 5, edge="bottom", margin=0.24, span=(0.08, 0.92), size=0.22, h=0.15,
               style="rivet", uv_scale=FINE)
        diamond_stack(b, (s * 1.92, Y0 - 0.2, Z_BACK - 2.0), [(1.5, 0.25, "frost"), (0.7, 0.2, "gem")],
                      tilt=(0, 90, 0), facing=-s)
        vents(b, sp, face, 3, box=(0.68, 0.22, 0.92, 0.55), axis="v", w=0.2, uv_scale=FINE)
    # 下の竜骨と、氷晶の弾倉（紺の枠の窓から光る結晶）
    W.rbox(b, (0, Y0 - 1.55, Z_FRONT + 3.0), (1.7, 1.0, 5.0), "navy", rot=(-10, 0, 0), uv_scale=6)
    mz = -6.9
    W.cbox(b, (0, Y0 - 1.95, mz), (1.3, 1.5, 2.1), "navy", uv_scale=8)
    W.cbox(b, (0, Y0 - 2.05, mz), (1.42, 0.9, 1.5), "ice", uv_scale=FINE)
    for s in (-1, 1):
        W.cbox(b, (s * 0.72, Y0 - 2.05, mz), (0.16, 0.3, 1.2), "glow", uv_scale=FINE)
    crystal(b, (0, Y0 - 2.6, mz - 0.3), (0, -1.0, -0.45), 1.3, 0.5, "crystal", tip=0.5, uv_scale=FINE)
    # 照門: 立てた霜の ◆ と、その前の 98° 傾いた小さな環の照準
    W.cbox(b, (0, Y0 + 1.95, Z_BACK - 0.9), (0.6, 0.8, 0.8), "navy", uv_scale=10)
    diamond(b, (0, Y0 + 2.75, Z_BACK - 0.9), 1.6, 0.3, "frost", uv_scale=12)
    diamond(b, (0, Y0 + 2.75, Z_BACK - 1.1), 0.7, 0.2, "gem", uv_scale=14)
    SC = (0, Y0 + 2.45, Z_BACK - 3.4)
    W.cbox(b, (0, Y0 + 1.95, SC[2]), (0.4, 0.6, 0.4), "navy", uv_scale=FINE)
    sg = W.part(m, b, "sight", SC, rotation=(0, 70, 8))
    ss = W.spin(m, sg, "sight", SC)
    W.ring(ss, SC, 0.62, 8, (0, 0.18, 0.18), "ringglow", axis="z", uv_scale=FINE)
    W.cbox(ss, SC, (0.34, 0.34, 0.34), "gem", rotation=(45, 0, 45), uv_scale=FINE)
    # 銃口: 八角の発射口・霜の覆い・縁の光・四隅の小さな放射器
    W.octa(b, (0, Y0 + 0.6, Z_MUZ), 2.0, 1.4, "navy", uv_scale=8)
    W.octa(b, (0, Y0 + 0.6, Z_MUZ + 0.95), 2.2, 0.3, "rim", uv_scale=FINE)
    W.ring(b, (0, Y0 + 0.6, Z_MUZ - 0.75), 0.85, 8, (0, 0.24, 0.2), "glow", axis="z", uv_scale=12)
    for sx in (-1, 1):
        sensor(b, (sx * 0.82, Y0 + 0.6, Z_MUZ - 0.62), 0.2, "glow", "frame", uv_scale=FINE)
    # 機関部から弓台へのケーブル（垂れる）
    for s in (-1, 1):
        cable(b, [(s * 1.7, Y0 - 0.9, Z_FRONT + 3.2), (s * 1.95, Y0 - 0.4, Z_FRONT + 0.6)], 0.24,
              "navy", sag=0.25, seg=0.9, uv_scale=FINE)


def limbs(m, root):
    """form_2_limbs — 弓（±X へ開く）。"""
    lb = W.form(m, root, 2, "limbs", (0, Y0, Z_FRONT))
    W.bevel(lb, (0, Y0 + 0.1, Z_FRONT), (4.2, 2.4, 2.2), "navy", cut=0.5, axis="z", uv_scale=8)
    W.cbox(lb, (0, Y0 + 0.1, Z_FRONT - 1.12), (2.6, 0.3, 0.12), "glow", uv_scale=10)
    diamond_stack(lb, (0, Y0 + 0.1, Z_FRONT - 1.2), [(0.9, 0.2, "frost"), (0.45, 0.16, "gem")])
    for s in (-1, 1):
        base = (s * 1.9, Y0 + 0.2, Z_FRONT - 0.2)
        mid = (s * 5.0, Y0 + 0.5, Z_FRONT + 0.5)
        tip = (s * 8.0, Y0 + 0.7, Z_FRONT + 2.8)
        segs = W.polyline(lb, [base, mid, tip], [1.5, 1.15], [1.0, 0.8], "plate", uv_scale=8)
        W.polyline(lb, [(s * 1.9, Y0 + 0.25, Z_FRONT - 0.9), (s * 5.0, Y0 + 0.5, Z_FRONT - 0.2),
                        (s * 7.7, Y0 + 0.7, Z_FRONT + 2.0)], 0.4, 0.55, "frost", uv_scale=10)
        W.polyline(lb, [(s * 2.0, Y0 + 0.75, Z_FRONT - 0.1), (s * 5.0, Y0 + 0.95, Z_FRONT + 0.55),
                        (s * 7.6, Y0 + 1.1, Z_FRONT + 2.6)], 0.22, 0.16, "glow", uv_scale=12)
        # 重ね板（青緑）とリベット、関節の軸と霜の ◆
        for seg in segs:
            stick(lb, seg, "down", 0.5, 0.5, (1.0, 2.2, 0.2), "plate2", sink=0.05, uv_scale=8)
        W.octa(lb, (mid[0], mid[1] + 0.05, mid[2]), 1.1, 1.3, "frame", axis="y", uv_scale=10)
        diamond(lb, (mid[0], mid[1] + 0.72, mid[2]), 0.8, 0.2, "frost", (90, 0, 0), uv_scale=FINE)
        # 滑車（紺）・ボルトの輪・光る軸と氷晶の弓端
        W.octa(lb, tip, 1.5, 1.2, "navy", axis="y", uv_scale=10)
        W.octa(lb, (tip[0], tip[1] + 0.65, tip[2]), 0.8, 0.2, "glow", axis="y", uv_scale=12)
        W.ring(lb, (tip[0], tip[1] + 0.68, tip[2]), 0.62, 4, (0.2, 0.2, 0.16), "rivet", axis="y",
               phase=45, uv_scale=FINE)
        crystal(lb, (tip[0] + s * 0.3, tip[1], tip[2] + 0.2), (s * 0.85, 0.12, 0.5), 3.4, 0.95, "ice",
                uv_scale=10)
        crystal(lb, (tip[0] + s * 0.2, tip[1] + 0.2, tip[2] + 0.6), (s * 0.4, 0.5, 0.9), 1.6, 0.45,
                "crystal", tip=0.5, uv_scale=FINE)
        # 弦（滑車から矢の尻へ）と留め具
        W.beam(lb, (s * 7.8, Y0 + 0.75, Z_FRONT + 2.7), (s * 0.15, Y0 + 2.0, Z_NOCK), 0.18, 0.18, "edge",
               uv_scale=12)
        W.cbox(lb, (s * 7.55, Y0 + 0.78, Z_FRONT + 2.95), (0.4, 0.4, 0.4), "rim", uv_scale=FINE)


def bolt(m, root):
    """form_3_bolt — 装填された絶対零度の矢。"""
    YB = Y0 + 2.05
    bt = W.form(m, root, 3, "bolt", (0, YB, Z_NOCK))
    gb = W.glow(m, bt, "bolt", (0, YB, Z_NOCK - 5.0))
    W.beam(gb, (0, YB, Z_NOCK), (0, YB, Z_MUZ - 0.6), 0.34, 0.34, "ice", uv_scale=10)
    W.beam(gb, (0, YB + 0.12, Z_NOCK - 1.4), (0, YB + 0.12, Z_MUZ + 0.6), 0.16, 0.16, "energy",
           uv_scale=FINE)                                                                 # 光る象嵌
    for z in (Z_NOCK - 1.25, -9.2, Z_MUZ + 0.4):
        W.octa(gb, (0, YB, z), 0.5, 0.22, "frost", uv_scale=FINE)                      # 霜の帯
    crystal(gb, (0, YB, Z_MUZ - 0.4), (0, 0, -1), 2.6, 0.85, "crystal", tip=0.55, uv_scale=12)
    W.octa(gb, (0, YB, Z_MUZ - 0.45), 0.98, 0.3, "rim", uv_scale=FINE)
    diamond(gb, (0, YB, Z_NOCK - 0.6), 1.1, 0.16, "ice", (0, 90, 0), uv_scale=12)     # 矢羽根（縦）
    diamond(gb, (0, YB, Z_NOCK - 0.6), 1.1, 0.16, "ice", (90, 0, 0), uv_scale=12)     # 矢羽根（横）
    W.cbox(gb, (0, YB, Z_NOCK + 0.1), (0.42, 0.42, 0.3), "navy", uv_scale=FINE)          # 筈


def tilt_ring(m, root):
    """form_4_ring — 銃口の前で傾いて回る小さな環（光の帯・紺の帯・5 つの氷の衛星・逆へ回る氷の塵）。"""
    C = (0, Y0 + 0.6, Z_RING)
    rg = W.form(m, root, 4, "ring", C, rotation=TILT)
    sp = W.spin(m, rg, "tilt", C)
    W.ring(sp, C, 2.8, 20, (0, 0.36, 0.32), "ringglow", axis="z", styles=["ringglow"] * 3 + ["ice"],
           uv_scale=10)
    W.ring(sp, C, 2.25, 12, (0, 0.5, 0.46), "ringband", axis="z", styles=["ringband", "navy"],
           uv_scale=10)
    for k in range(5):
        a = math.radians(k * 72 + 30)
        M = (C[0] - 2.8 * math.sin(a), C[1] + 2.8 * math.cos(a), C[2])
        moon(sp, M, 0.4 if k % 2 else 0.33)
    du = W.spin(m, rg, "dust", C)
    W.ring(du, C, 3.35, 10, (0.36, 0.2, 0.2), "ice", axis="z", uv_scale=FINE)


# ===========================================================================
#  星核: 淡い青緑の天王星。98° 傾いて縦に立つ環が球の前を縦に横切り、紺の籠（正面向きの輪）が囲む。直径 6.6
# ===========================================================================
CORE_TILT = (8, 68, 0)      # 環と自転軸: 縦に立ち（側面向きに近い）、8° 傾く


def build_core(m, root):
    # 天王星（環と同じ傾いた軸で自転）
    globe = W.form(m, root, 0, "globe", (0, 0, 0), rotation=CORE_TILT)
    gs = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(gs, (0, 0, 0), 1.6, "globe", uv_scale=16)
    # 籠: 正面向きの輪（紺と青緑）・上下の極の冠（淡い八角 + 霜の ◆ + 宝玉）・左右の留め具と発光・リベット
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.1, 16, (0, 0.42, 0.7), "navy", axis="z", styles=["navy", "plate2"], uv_scale=8)
    W.ring(cage, (0, 0, 0), 3.1, 8, (0.22, 0.2, 0.86), "rim", axis="z", phase=11.25, uv_scale=14)
    for s in (-1, 1):
        y = s * 3.25
        W.octa(cage, (0, y, 0), 1.6, 0.8, "plate", axis="y", uv_scale=10)
        diamond(cage, (0, y + s * 0.7, 0), 1.1, 0.4, "frost", (0, 0, 0), uv_scale=14)
        W.cbox(cage, (0, y + s * 0.7, -0.25), (0.45, 0.45, 0.2), "gem", rotation=(0, 0, 45), uv_scale=14)
        W.cbox(cage, (s * 3.15, 0, 0), (0.7, 1.0, 1.0), "frost", uv_scale=10)
        W.cbox(cage, (s * 3.5, 0, 0), (0.2, 0.5, 0.5), "glow", uv_scale=12)
    # 環: 天王星と同じ軸で回る細い光の帯（暗い隙間を挟んで内に紺の帯）と、2 つの氷の衛星
    rings = W.form(m, root, 2, "rings", (0, 0, 0), rotation=CORE_TILT)
    ra = W.spin(m, rings, "ring", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.75, 16, (0, 0.26, 0.26), "ringglow", axis="z", styles=["ringglow", "ice"],
           uv_scale=10)
    W.ring(ra, (0, 0, 0), 2.25, 14, (0, 0.22, 0.34), "ringband", axis="z", uv_scale=10)
    for k in range(2):
        a = math.radians(k * 180 + 45)
        W.rbox(ra, (-2.75 * math.sin(a), 2.75 * math.cos(a), 0), (0.7, 0.7, 0.7), "crystal", rot=(45, 0, 45),
               uv_scale=14)


# ---------------------------------------------------------------------------
#  塗り（astro_paint の惑星の配色から。上書きだけ書く）
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        energy={"glow": (150, 244, 255), "light": (250, 255, 255)},
        edge={"glow": (150, 244, 255), "emit": 30, "sat": 0.4},
        wrap={"base": (22, 36, 54), "strap": (47, 159, 168), "skin": (214, 240, 246)},
        vent={"base": (40, 64, 90), "glow": (150, 244, 255), "deep": (14, 60, 90)},
        **_SHARED,
    )


def CORE_STYLES(key):
    return core_styles(key, globe=W.globe_style("uranus", emit=110, shade=0.3), **_SHARED)


# ---------------------------------------------------------------------------
#  アタッチャブルのアニメ
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_tilt": {"rotation": [0, 0, "q.anim_time * 120.0"]},
        "fx_spin_dust": {"rotation": [0, 0, "q.anim_time * -60.0"]},
        "fx_spin_sight": {"rotation": [0, 0, "q.anim_time * 180.0"]},
        "fx_glow_bolt": W.pulse_expr(180, 0.05),
    },
    "swing": {
        # 撃つたびに環が一回転ぶん加速する
        "fx_spin_tilt": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_limbs": "x", "form_3_bolt": "z"},   # 弓は ±X へ開き、矢は矢道に沿って伸びる
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": dict(W.spin_expr("z", 40), **W.pulse_expr(150, 0.03)),
        "fx_spin_ring": W.spin_expr("z", -90),
    },
}
