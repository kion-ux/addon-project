# -*- coding: utf-8 -*-
"""金星（モーニングスター）のナノウェポン「明星杖 ルシファー・セプター」と星核「金星核 ヴィーナス・コア」。

王笏（kind scepter）: 握りの中心 = 原点、頭 = -Z、平の法線 = ±X。手に持つと 0.9 倍。
握りの前後 ±2.9 は篭手に隠れるので、口金はそれより先・後ろに置く。
上の十字の横木と、その上の輪と星の頭とで、杖全体が金星の記号「♀」の形になる。

  form_0_shaft   金の柄（クリームの象嵌・金の口金・硫黄色の光の筋）、石突きの薔薇色の宝玉と小さな四芒星。
                 握りから両方向へ伸びる（form_axes z）
  form_1_cross   ♀ の横木: クリームと金の十字の腕（先に薔薇色の宝玉）、星を受ける金の萼（がく）
  form_2_star    八芒星の頭（fx_spin_star で回る）: 金の円盤に金星の球、♀ の細い輪、
                 白金に光る長い光条 4 本と金の短い光条 4 本
  form_3_clouds  頭を包んで回る雲の輪（fx_spin_clouds、静止の傾き 24°）: 金の細い輪とクリームの雲の玉 5 つ
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_paint import core_styles, weapon_styles

KIND = "scepter"

Z_STAR = -22.6          # 星の頭の中心
R_LONG, R_SHORT = 5.0, 3.6      # 光条の長さ（中心から）
R_CLOUD = 6.0           # 雲の輪の半径

STAR = (255, 240, 150)  # 明けの明星の白金の光
SULFUR = (226, 255, 96)


def _puff(bone, c, r, style, uv=10):
    """雲の玉（3 個: 中心の箱 + 縦横に寝かせた 45° の箱）。"""
    W.cbox(bone, c, (r * 1.4, r * 1.25, r * 1.4), style, uv_scale=uv)
    W.rbox(bone, c, (r * 1.15, r * 1.6, r * 1.15), style, rot=(0, 45, 0), uv_scale=uv)
    W.rbox(bone, (c[0], c[1], c[2]), (r * 1.7, r * 1.0, r * 1.0), style, rot=(45, 0, 0), uv_scale=uv)


def build_weapon(m, root):
    # =====================================================================
    #  form_0_shaft — 柄（握り・石突き・上の柄）
    # =====================================================================
    sh = W.form(m, root, 0, "shaft", (0, 0, 0))
    W.octa(sh, (0, 0, 0.0), 1.5, 5.8, "wrap", uv_scale=8)                      # 握り（篭手の中）
    for z, ln in ((-3.15, 0.7), (3.15, 0.7)):                                  # 握りの口金
        W.octa(sh, (0, 0, z), 2.0, ln, "gold", uv_scale=8)
    # 石突き: 金の柄 → クリームの象嵌 → 金の台 → 薔薇色の宝玉 → 小さな四芒星
    W.octa(sh, (0, 0, 5.6), 1.35, 4.2, "plate", uv_scale=8)
    W.octa(sh, (0, 0, 5.4), 1.45, 1.2, "plate2", uv_scale=8)
    W.octa(sh, (0, 0, 8.1), 2.1, 0.9, "gold", uv_scale=8)
    W.cbox(sh, (0, 0, 9.0), (1.3, 1.3, 1.3), "gem_accent", rotation=(45, 0, 0), uv_scale=12)
    for a in (0, 90):
        W.rbox(sh, (0, 0, 9.0), (0.3, 3.2, 0.3), "gold", rot=(a, 0, 0), uv_scale=12)
    # 上の柄: 金の柄にクリームの象嵌の帯と金の口金を交互に。平（±X）に硫黄色の光の筋
    W.octa(sh, (0, 0, -9.6), 1.3, 12.6, "plate", uv_scale=7)
    for z in (-6.2, -11.6):
        W.octa(sh, (0, 0, z), 1.42, 2.2, "plate2", uv_scale=8)                 # クリームの象嵌
    for z in (-4.4, -8.0, -13.3):
        W.octa(sh, (0, 0, z), 1.8, 0.5, "gold", uv_scale=8)                    # 金の口金
    for s in (-1, 1):
        W.cbox(sh, (s * 0.66, 0, -9.6), (0.08, 0.3, 11.0), "glow", uv_scale=10)

    # =====================================================================
    #  form_1_cross — ♀ の横木と、星を受ける萼
    # =====================================================================
    cr = W.form(m, root, 1, "cross", (0, 0, -15.0))
    W.bevel(cr, (0, 0, -15.0), (2.0, 2.4, 2.0), "gold", cut=0.5, axis="x", uv_scale=8)
    for s in (-1, 1):
        # 横木（クリームの腕に金の縁、先が少し星の側へ反る）
        W.beam(cr, (0, s * 1.0, -15.0), (0, s * 3.4, -15.3), 1.1, 1.1, "plate2", uv_scale=8)
        W.beam(cr, (0, s * 3.3, -15.3), (0, s * 4.4, -16.2), 0.9, 0.9, "gold", uv_scale=10, extend=0.2)
        W.cbox(cr, (0, s * 4.55, -16.45), (0.8, 0.8, 0.8), "gem_accent", rotation=(45, 0, 0),
               uv_scale=12)
        W.cbox(cr, (0, s * 2.2, -15.05), (1.16, 0.3, 1.16), "gold", uv_scale=10)        # 腕の金の帯
        # 萼（星を受ける金の花弁。上外へ開く）
        W.beam(cr, (0, s * 0.5, -15.6), (0, s * 1.9, -17.6), 0.8, 0.5, "gold", uv_scale=10)
        W.beam(cr, (s * 0.5, 0, -15.6), (s * 1.9, 0, -17.6), 0.5, 0.8, "plate2", uv_scale=10)
    W.cbox(cr, (0, 0, -16.4), (0.9, 0.9, 1.6), "energy", rotation=(0, 0, 45), uv_scale=10)  # 星へ昇る光

    # =====================================================================
    #  form_2_star — 回る八芒星の頭（金の円盤に金星の球、♀ の輪、光条）
    # =====================================================================
    st = W.form(m, root, 2, "star", (0, 0, -18.0))
    sp = W.spin(m, st, "star", (0, 0, Z_STAR))
    S = (0, 0, Z_STAR)
    W.octa(sp, S, 3.6, 0.55, "gold", axis="x", uv_scale=10)                    # 金の円盤（平 ±X）
    W.sphere(sp, S, 1.55, "globe", uv_scale=16)                               # 金星の球
    W.ring(sp, S, 3.05, 12, (0, 0.26, 0.34), "gold", axis="x", uv_scale=10)   # ♀ の輪
    for k in range(8):
        a = math.radians(k * 45)
        d = (0.0, math.sin(a), -math.cos(a))
        L = R_LONG if k % 2 == 0 else R_SHORT
        p0 = tuple(S[i] + d[i] * 1.5 for i in range(3))
        pm = tuple(S[i] + d[i] * (1.5 + (L - 1.5) * 0.55) for i in range(3))
        p1 = tuple(S[i] + d[i] * L for i in range(3))
        if k % 2 == 0:
            # 長い光条: 金の縁（太い）+ 白金に光る芯
            W.polyline(sp, [p0, pm, p1], [0.62, 0.58], [1.5, 0.6], "gold", uv_scale=10)
            W.polyline(sp, [p0, pm, p1], [0.72, 0.68], [0.8, 0.28], "star", uv_scale=10)
        else:
            W.polyline(sp, [p0, pm, p1], [0.5, 0.46], [1.1, 0.4], "gold", uv_scale=10)

    # =====================================================================
    #  form_3_clouds — 頭を包んで回る雲の輪（静止の傾き 24°）
    # =====================================================================
    cl = W.form(m, root, 3, "clouds", (0, 0, Z_STAR))
    rg = W.spin(m, cl, "clouds", (0, 0, Z_STAR), rotation=(24, 0, 0))
    W.ring(rg, S, R_CLOUD, 14, (0, 0.22, 0.26), "gold", axis="z", uv_scale=10)
    for k in range(5):
        a = math.radians(k * 72 + 18)
        c = (-R_CLOUD * math.sin(a), R_CLOUD * math.cos(a), Z_STAR)
        _puff(rg, c, 0.62 + 0.12 * (k % 2), "cloud")


def build_core(m, root):
    """金星核: 金色の雲の渦の球を、金の籠（正面の輪と極の冠）と、傾いて回る雲の輪が囲む。直径 6.6。"""
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    gs = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(gs, (0, 0, 0), 1.75, "globe", uv_scale=16)
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.2, 16, (0, 0.42, 0.6), "gold", axis="z", styles=["gold", "gold", "plate2"],
           uv_scale=8)
    for s in (-1, 1):
        y = s * 3.3
        W.octa(cage, (0, y, 0), 1.5, 0.7, "plate2", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.5, 0), 0.95, 0.4, "gold", axis="y", uv_scale=10)
        # 極の小さな四芒星（白金に光る）
        for a in (0, 90):
            W.rbox(cage, (0, y + s * 0.95, 0), (0.22, 1.1, 0.22), "star", rot=(0, a, 45 * s), uv_scale=12)
        W.cbox(cage, (s * 3.25, 0, 0), (0.7, 0.9, 0.9), "plate2", uv_scale=10)       # 赤道の留め具
        W.cbox(cage, (s * 3.6, 0, 0), (0.3, 0.55, 0.55), "gem_accent", rotation=(45, 0, 0), uv_scale=12)
    clouds = W.form(m, root, 2, "clouds", (0, 0, 0))
    rc = W.spin(m, clouds, "clouds", (0, 0, 0), rotation=(22, 0, 12))
    W.ring(rc, (0, 0, 0), 2.45, 12, (0, 0.2, 0.24), "gold", axis="y", uv_scale=10)
    for k in range(5):
        a = math.radians(k * 72)
        _puff(rc, (-2.45 * math.sin(a), 0, -2.45 * math.cos(a)), 0.38 + 0.08 * (k % 2), "cloud", uv=14)


# ---------------------------------------------------------------------------
#  塗り
# ---------------------------------------------------------------------------
_GOLD = {"kind": "trim", "base": (214, 146, 40), "light": (255, 240, 168), "dark": (128, 74, 18),
         "line": (78, 42, 10)}
_CLOUD = {"kind": "armor", "base": (255, 243, 214), "light": (255, 255, 248), "dark": (226, 200, 150),
          "line": (176, 134, 76), "panel": 0, "sheen": False, "outline": False, "bevel": False}
_STAR = {"kind": "glowline", "glow": STAR, "light": (255, 255, 236), "bevel": False, "outline": False}


def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        gold=dict(_GOLD),
        cloud=dict(_CLOUD),
        star=dict(_STAR),
        plate={"panel": 0},
        wrap={"base": (60, 36, 26), "strap": (236, 186, 90), "skin": (255, 236, 206)},
        energy={"glow": SULFUR},
        globe=W.globe_style("venus", emit=40),
    )


def CORE_STYLES(key):
    return core_styles(key, gold=dict(_GOLD), cloud=dict(_CLOUD), star=dict(_STAR),
                       globe=W.globe_style("venus", emit=34))


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_star": {"rotation": [0, 0, "q.anim_time * 60.0"]},
        "fx_spin_clouds": {"rotation": [0, 0, "-q.anim_time * 90.0"]},
    },
    "swing": {
        # 振ると星が一回転ぶん加速する
        "fx_spin_star": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_0_shaft": "z"},
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 40.0", 0]},
        "fx_spin_clouds": {"rotation": [0, "-q.anim_time * 90.0", 0]},
    },
}

ICON = {"weapon": (90, 0, 45), "core": (25, -18, 0)}
