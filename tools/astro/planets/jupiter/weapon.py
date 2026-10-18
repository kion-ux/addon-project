# -*- coding: utf-8 -*-
"""木星（ゼウス）のナノウェポン「雷霆鎚 ケラウノス」と星核「木星核 ジュピター・コア」。

武器空間: 握りの中心 = 原点、鎚頭 = -Z、打撃面 = ±Y、側面の法線 = ±X（16 単位 = 1 ブロック）。
手に持つと 0.9 倍（astro_hold.SPEC["hammer"]）。握りの前後 ±2.9 は篭手に隠れるので、
柄の口金は z = -3.2 より先、柄頭は z = +3.2 より後ろに置く。

  form_0_grip    柄巻・銅の口金・柄頭（電光の玉と小さな稲妻の爪）
  form_1_haft    帯（クリーム・褐色・錆色）を巻いた柄（z 方向へ伸びる）と鎚頭の根元の襟
  form_2_head    鎚頭: 中央の装甲の胴（両脇に木星の星核）・左右に銅の巻き線と光る芯（テスラコイル）・
                 重い端の冠
  form_3_strike  打撃面: 電光の発振器（回る放電の輪 fx_spin_emit_*、脈打つ芯 fx_glow_emit_*）
  form_4_fins    稲妻形のヒレ（鎚頭の先へ伸びる二枚のジグザグ）
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_paint import core_styles, mix, weapon_styles

KIND = "hammer"

CREAM = (234, 216, 184)
TAN = (201, 142, 90)
RUST = (217, 71, 43)
VOLT = (140, 236, 255)

ZH = -19.6               # 鎚頭の中心（z）
HY = 6.2                 # 鎚頭の半長（打撃面の y）

ICON = {"weapon": (90, 0, 45), "core": (25, -18, 0)}
# 一人称: 鎚頭が大きいので、照準から少し右下へ離す
HOLD = {"fp": {"at": (11.8, -11.0, 15.0)}}


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄巻・口金・柄頭
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.2), 1.85, 6.6, "wrap", uv_scale=8)
    for z in (-3.35, 3.55):
        W.octa(grip, (0, 0, z), 2.4, 0.7, "copper", uv_scale=8)
    W.octa(grip, (0, 0, 0.2), 2.05, 0.4, "copper", uv_scale=8)
    W.octa(grip, (0, 0, 4.5), 2.5, 1.2, "plate", uv_scale=8)                  # 柄頭
    W.octa(grip, (0, 0, 5.3), 1.9, 0.5, "frame", uv_scale=8)
    W.cbox(grip, (0, 0, 5.75), (1.25, 1.25, 0.8), "gem", rotation=(0, 0, 45), uv_scale=12)
    for s in (-1, 1):                                                          # 稲妻の爪
        W.polyline(grip, [(0, s * 1.0, 4.4), (0, s * 1.9, 5.2), (0, s * 1.5, 5.4), (0, s * 2.3, 6.4)],
                   0.4, 0.45, "volt", overlap=0.15, uv_scale=10)

    # =====================================================================
    #  form_1_haft — 帯を巻いた柄（木星の帯と縞）
    # =====================================================================
    haft = W.form(m, root, 1, "haft", (0, 0, -3.6))
    z0, z1 = -3.7, ZH + 2.9
    W.octa(haft, (0, 0, (z0 + z1) / 2), 1.55, z0 - z1, "frame", uv_scale=6)
    bands = ["zone", "belt", "zone", "rustband", "zone", "belt"]
    n = len(bands)
    for i, st in enumerate(bands):
        zc = z0 + (z1 - z0) * (i + 0.5) / n
        W.octa(haft, (0, 0, zc), 1.85, (z0 - z1) / n - 0.35, st, uv_scale=7)
    W.cbox(haft, (0, 0.95, (z0 + z1) / 2 - 0.4), (0.3, 0.2, z0 - z1 - 2.0), "volt", uv_scale=8)
    W.cbox(haft, (0, -0.95, (z0 + z1) / 2 - 0.4), (0.3, 0.2, z0 - z1 - 2.0), "volt", uv_scale=8)
    # 鎚頭の根元の襟（銅の八角と、柄を受ける四枚の爪）
    W.octa(haft, (0, 0, ZH + 3.1), 2.9, 0.9, "copper", uv_scale=8)
    for k in range(4):
        a = 45 + 90 * k
        r = math.radians(a)
        W.beam(haft, (-1.0 * math.sin(r), 1.0 * math.cos(r), ZH + 4.2),
               (-1.75 * math.sin(r), 1.75 * math.cos(r), ZH + 2.6), 0.55, 0.55, "plate2", uv_scale=8)

    # =====================================================================
    #  form_2_head — 鎚頭（中央の装甲の胴 + 左右のテスラコイル + 端の冠）
    # =====================================================================
    head = W.form(m, root, 2, "head", (0, 0, ZH))
    # 中央の胴: クリームの八角（側面に木星の星核）、錆色の縞
    W.bevel(head, (0, 0, ZH), (5.4, 3.6, 5.6), "plate", cut=1.0, axis="y", uv_scale=6)
    W.chamfer(head, (0, 0, ZH), (5.6, 0.8, 5.8), "rustband", cut=1.05, axis="y", uv_scale=6)
    for s in (-1, 1):
        W.octa(head, (s * 2.75, 0, ZH), 2.6, 0.4, "copper", axis="x", uv_scale=10)
        W.sphere(head, (s * 2.95, 0, ZH), 1.05, "globe", uv_scale=14)
    # テスラコイル（上下）: 光る芯に銅の巻き線
    for s in (-1, 1):
        W.octa(head, (0, s * 3.5, ZH), 3.4, 3.4, "volt_core", axis="y", uv_scale=6)
        for k in range(4):
            W.octa(head, (0, s * (2.15 + k * 0.82), ZH), 4.4 - k * 0.12, 0.5, "coil", axis="y", uv_scale=7)
        # 端の冠: 重い暗い金属の八角 + 帯の板
        W.octa(head, (0, s * 5.55, ZH), 5.8, 1.0, "frame", axis="y", uv_scale=6)
        W.octa(head, (0, s * 5.55, ZH), 6.05, 0.45, "belt", axis="y", uv_scale=6)

    # =====================================================================
    #  form_3_strike — 打撃面の電光の発振器（回る放電の輪 + 脈打つ芯）
    # =====================================================================
    strike = W.form(m, root, 3, "strike", (0, 0, ZH))
    for s, nm in ((-1, "lo"), (1, "hi")):
        y = s * HY
        W.octa(strike, (0, y, ZH), 4.8, 0.5, "copper", axis="y", uv_scale=8)
        gl = W.glow(m, strike, f"emit_{nm}", (0, y + s * 0.3, ZH))
        W.octa(gl, (0, y + s * 0.3, ZH), 3.3, 0.35, "energy", axis="y", uv_scale=8)
        W.cbox(gl, (0, y + s * 0.42, ZH), (1.3, 0.2, 1.3), "volt", rotation=(0, 45, 0), uv_scale=10)
        sp = W.spin(m, strike, f"emit_{nm}", (0, y + s * 0.6, ZH))
        W.ring(sp, (0, y + s * 0.6, ZH), 2.35, 8, (0, 0.2, 0.2), "glow", axis="y",
               styles=["glow", "glow_soft"], uv_scale=10)

    # =====================================================================
    #  form_4_fins — 稲妻形のヒレ（鎚頭の先 -Z へ。二枚が上下に開く）
    # =====================================================================
    fins = W.form(m, root, 4, "fins", (0, 0, ZH - 2.6))
    for s in (-1, 1):
        pts = [(0, s * 0.9, ZH - 2.4), (0, s * 2.9, ZH - 4.6), (0, s * 1.7, ZH - 4.9),
               (0, s * 3.9, ZH - 7.8)]
        W.polyline(fins, pts, 0.6, [2.0, 1.4, 1.0], "plate2", overlap=0.4, uv_scale=8)
        W.polyline(fins, [(0.34, p[1], p[2]) for p in pts], 0.12, [0.6, 0.45, 0.35], "volt",
                   overlap=0.25, uv_scale=10)
        W.polyline(fins, [(-0.34, p[1], p[2]) for p in pts], 0.12, [0.6, 0.45, 0.35], "volt",
                   overlap=0.25, uv_scale=10)
        W.cbox(fins, (0, s * 4.1, ZH - 8.1), (0.5, 0.5, 0.5), "volt", rotation=(45, 0, 0), uv_scale=10)
    W.octa(fins, (0, 0, ZH - 2.9), 1.8, 0.8, "copper", uv_scale=10)
    W.cbox(fins, (0, 0, ZH - 3.55), (1.0, 1.0, 0.7), "gem", rotation=(0, 0, 45), uv_scale=12)


def build_core(m, root):
    """木星核: 縞と大赤斑の光る球を、重い籠（縦の二重の輪と極の冠）が囲み、赤道の輪（細い環）が回る。
    その輪には四つのガリレオ衛星が乗っている。直径 6.6。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.95, "globe", uv_scale=16)
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 2.95, 12, (0, 0.55, 0.7), "frame", axis="x", uv_scale=8)
    W.ring(cage, (0, 0, 0), 2.95, 12, (0, 0.5, 0.62), "copper", axis="z", uv_scale=8)
    for s in (-1, 1):
        y = s * 3.15
        W.octa(cage, (0, y, 0), 1.8, 0.8, "plate", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.55, 0), 1.1, 0.4, "rustband", axis="y", uv_scale=10)
        W.cbox(cage, (0, y + s * 0.9, 0), (0.5, 0.5, 0.5), "gem", rotation=(0, 45, 0), uv_scale=12)
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    rb = W.spin(m, rings, "ring", (0, 0, 0), rotation=(12, 0, 0))
    W.ring(rb, (0, 0, 0), 2.45, 12, (0, 0.18, 0.4), "volt", axis="y", styles=["volt", "glow_soft"],
           uv_scale=10)
    for k, st in enumerate(("io", "europa", "ganymede", "callisto")):
        a = math.radians(k * 90 + 20)
        W.cbox(rb, (-2.45 * math.sin(a), 0, -2.45 * math.cos(a)), (0.6, 0.6, 0.6), st, uv_scale=14)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
def _common():
    return dict(
        zone={"kind": "armor", "base": CREAM, "light": (252, 244, 226), "dark": (186, 160, 124),
              "line": (110, 84, 60), "panel": 0,
              "stripe": {"dir": "h", "period": 6, "width": 2, "color": (214, 176, 128), "k": 0.7}},
        belt={"kind": "armor", "base": TAN, "light": (232, 186, 140), "dark": (150, 96, 58),
              "line": (92, 52, 28), "panel": 0,
              "stripe": {"dir": "h", "period": 5, "width": 2, "color": (176, 92, 54), "k": 0.75}},
        rustband={"kind": "armor", "base": RUST, "light": (246, 132, 96), "dark": (150, 44, 24),
                  "line": (90, 24, 12), "panel": 0},
        copper={"kind": "trim", "base": (206, 120, 70), "light": (255, 200, 150),
                "dark": (120, 58, 30), "line": (64, 28, 12)},
        coil={"kind": "trim", "base": (196, 110, 62), "light": (255, 188, 136),
              "dark": (110, 52, 26), "line": (60, 26, 10)},
        volt={"kind": "glowline", "glow": VOLT, "light": (236, 252, 255), "bevel": False,
              "outline": False},
        volt_core={"kind": "energy", "glow": (110, 210, 255), "light": (240, 252, 255),
                   "outline": False, "bevel": False},
        globe=W.globe_style("jupiter", emit=34, spin=-148),
        io={"kind": "armor", "base": (236, 206, 72), "panel": 0, "sheen": False,
            "stripe": {"dir": "d", "period": 4, "width": 1, "color": (214, 120, 40)}},
        europa={"kind": "armor", "base": (236, 228, 214), "panel": 0, "sheen": False,
                "stripe": {"dir": "a", "period": 5, "width": 1, "color": (160, 110, 80)}},
        ganymede={"kind": "armor", "base": (150, 146, 140), "panel": 0, "sheen": False},
        callisto={"kind": "armor", "base": (80, 72, 66), "panel": 0, "sheen": False, "noise": 10},
    )


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        energy={"glow": (120, 220, 255), "light": (240, 252, 255)},
        wrap={"base": (40, 28, 24), "strap": (190, 110, 64), "skin": (236, 222, 196)},
        gem={"glow": (120, 230, 255), "deep": (20, 60, 150)},
        glow_soft={"glow": VOLT},
        **_common(),
    )


def CORE_STYLES(key):
    return core_styles(key, gem={"glow": (255, 120, 70), "deep": (120, 26, 12)}, **_common())


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_emit_hi": {"rotation": [0, "q.anim_time * 180.0", 0]},
        "fx_spin_emit_lo": {"rotation": [0, "-q.anim_time * 180.0", 0]},
        "fx_glow_emit_hi": W.pulse_expr(360.0, 0.08),
        "fx_glow_emit_lo": W.pulse_expr(360.0, 0.08),
    },
    "swing": {
        # 振るたびに放電の輪が一気に回る
        "fx_spin_emit_hi": {"rotation": [0, "v.astro_sw * 720.0", 0]},   # 振り終わり（1）で整数周
        "fx_spin_emit_lo": {"rotation": [0, "-v.astro_sw * 720.0", 0]},
    },
    "form_axes": {"form_1_haft": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 40.0", 0]},
        "fx_spin_ring": {"rotation": [0, "-q.anim_time * 70.0", 0]},
    },
}
