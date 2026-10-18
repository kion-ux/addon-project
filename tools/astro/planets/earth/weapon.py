# -*- coding: utf-8 -*-
"""地球（ガイア）のナノウェポン「蒼星剣 ガイア・セイバー」と星核「地球核 アース・コア」。

ここは 8 人の惑星担当者が真似する見本。作り方の説明は planets/_template/README_weapon.md。

武器空間: 握りの中心 = 原点、刃先 = -Z、刃の幅 = ±Y、刃の平の法線 = ±X（16 単位 = 1 ブロック）。
手に持つと 0.8 倍（astro_hold.SPEC["sword"]）。握りの前後 ±3.1 は篭手に隠れるので、
鍔は z = -3.4 より先、柄頭は z = +3.9 より後ろに置く。

  form_0_grip    柄巻・金の口金・柄頭（月の子機が周りを回る fx_spin_moon）
  form_1_guard   重ねた鍔（青の主翼と白の副翼）・中央の地球儀（fx_spin_globe、発光）・金の縁
  form_2_blade   刃（鍔から z 方向へ伸びる）: 鋼の二枚・暗い樋と光る芯・緑青に光る両刃・
                 機械の背骨（青い節）・刃元の白い装甲・切先
"""
from __future__ import annotations

import astro_weapon as W
from astro_paint import core_styles, mix, weapon_styles

KIND = "sword"

# 刃の寸法（武器空間）
Z_BLADE0 = -6.4          # 刃の付け根（鍔の前）
Z_BLADE1 = -27.6         # 平行部の終わり
Z_TIP = -32.4            # 切先
HALF_W = 2.05            # 鋼の半幅（その外に発光の刃）
THICK = 0.9              # 刃の厚み（X）

EDGE = (88, 246, 204)    # 緑と青のあいだ（地球の発光色を海の青へ寄せた）


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄・口金・柄頭・月の子機
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.3), 1.75, 6.8, "wrap", uv_scale=8)
    for z, ln in ((-3.25, 0.7), (3.85, 0.7)):                 # 金の口金
        W.octa(grip, (0, 0, z), 2.3, ln, "gold", uv_scale=8)
    W.octa(grip, (0, 0, 0.3), 1.95, 0.45, "gold", uv_scale=8)  # 中ほどの細い帯（篭手の指の間から覗く）
    # 柄頭: 青い八角の台・金の冠・緑の宝玉
    W.octa(grip, (0, 0, 5.0), 2.7, 1.6, "plate", uv_scale=8)
    W.cbox(grip, (0, 0, 6.05), (2.0, 2.0, 0.6), "gold", rotation=(0, 0, 45), uv_scale=8)
    W.cbox(grip, (0, 0, 6.6), (1.2, 1.2, 0.8), "gem", rotation=(0, 0, 45), uv_scale=10)
    for s in (-1, 1):                                         # 柄頭の小さな翼（刃の幅の向き）
        W.beam(grip, (0, s * 1.2, 4.5), (0, s * 2.3, 5.9), 0.7, 0.8, "plate2", uv_scale=8)
    # 月の軌道（細い光の輪）と、そこを回る月の子機
    W.ring(grip, (0, 0, 5.0), 2.55, 14, (0, 0.16, 0.16), "glow_soft", axis="z")
    moon = W.spin(m, grip, "moon", (0, 0, 5.0))
    W.sphere(moon, (0, 2.55, 5.0), 0.62, "luna", uv_scale=10)

    # =====================================================================
    #  form_1_guard — 鍔と地球儀
    # =====================================================================
    guard = W.form(m, root, 1, "guard", (0, 0, -3.6))
    zc = -4.7
    W.bevel(guard, (0, 0, zc), (2.3, 4.6, 2.5), "plate", cut=0.55, axis="x", edge_style="plate_b",
            uv_scale=6)
    globe = W.spin(m, guard, "globe", (0, 0, zc))
    W.sphere(globe, (0, 0, zc), 1.5, "core", uv_scale=12)
    for s in (-1, 1):                                         # 地球儀の金の縁（両面）
        W.ring(guard, (s * 1.2, 0, zc), 1.72, 10, (0, 0.34, 0.36), "gold", axis="x", uv_scale=10)
    for s in (-1, 1):
        # 主翼（青）: 少し柄の側へ反って、先で刃の側へ折れる
        W.polyline(guard, [(0, s * 2.1, -4.1), (0, s * 4.6, -3.7), (0, s * 6.7, -4.6)],
                   [1.7, 1.35], [1.7, 1.25], "plate", uv_scale=6)
        W.beam(guard, (0, s * 2.4, -3.95), (0, s * 4.6, -3.62), 1.78, 0.32, "glow", uv_scale=8)
        W.beam(guard, (0, s * 4.6, -3.62), (0, s * 6.3, -4.35), 1.43, 0.28, "glow", uv_scale=8)
        # 翼端の金の爪（刃の向きへ）
        W.beam(guard, (0, s * 6.6, -4.4), (0, s * 7.1, -6.3), 0.9, 0.9, "gold", uv_scale=10)
        # 副翼（白）: 刃の付け根から前へ流れる
        W.polyline(guard, [(0, s * 1.9, -5.7), (0, s * 3.9, -6.2), (0, s * 5.2, -7.5)],
                   [1.25, 0.95], [1.1, 0.8], "plate2", uv_scale=8)
        W.beam(guard, (0, s * 5.2, -7.5), (0, s * 5.5, -8.7), 0.6, 0.55, "gold", uv_scale=10)
        # 鍔の付け根の金具
        W.cbox(guard, (0, s * 2.25, zc), (2.0, 0.6, 2.9), "frame", uv_scale=8)
    # 刃の発振器（刃を受ける黒い襟と放熱の光）
    W.cbox(guard, (0, 0, -6.15), (1.7, 3.6, 0.8), "frame", uv_scale=8)
    for s in (-1, 1):
        W.cbox(guard, (s * 0.86, 0, -6.15), (0.1, 2.6, 0.3), "energy", uv_scale=10)

    # =====================================================================
    #  form_2_blade — 刃（鍔から伸びる）
    # =====================================================================
    blade = W.form(m, root, 2, "blade", (0, 0, Z_BLADE0))
    L = Z_BLADE0 - Z_BLADE1
    zm = (Z_BLADE0 + Z_BLADE1) / 2
    for s in (-1, 1):
        # 鋼の二枚（樋の両側）
        W.cbox(blade, (0, s * (HALF_W + 0.35) / 2, zm), (THICK, HALF_W - 0.35, L), "blade", uv_scale=5)
        # 発光する刃（緑青）
        W.cbox(blade, (0, s * (HALF_W + 0.22), zm), (0.5, 0.46, L), "edge", uv_scale=6)
    # 暗い樋（一段くぼむ）と、その芯を走る光
    W.cbox(blade, (0, 0, zm - 0.6), (0.56, 0.78, L - 1.2), "dark", uv_scale=6)
    W.cbox(blade, (0, 0, zm - 1.6), (0.62, 0.2, L - 4.4), "energy", uv_scale=6)
    # 機械の背骨: 樋の上に並ぶ青い節（刃元から先へ小さくなる）と金の留め
    for i in range(5):
        z = -8.4 - i * 2.75
        k = 1.0 - i * 0.07
        W.cbox(blade, (0, 0, z), (1.32, 1.5 * k, 1.9 * k), "plate", uv_scale=8)
        W.cbox(blade, (0, 0, z - 1.05 * k), (1.36, 0.9 * k, 0.24), "gold", uv_scale=10)
    # 刃元の白い装甲（左右）と、その縁の発光
    for s in (-1, 1):
        W.cbox(blade, (0, s * 1.45, -7.35), (1.22, 1.9, 1.9), "plate2", uv_scale=8)
        W.beam(blade, (0, s * 0.6, -8.2), (0, s * 2.3, -8.75), 1.24, 0.22, "glow", uv_scale=10)
    # 切先: 鋼の三角と、刃先へ収束する発光の刃
    W.blade_point(blade, Z_BLADE1 + 0.05, HALF_W, Z_TIP, THICK, "blade_flat", layer=0.8, uv_scale=6)
    for s in (-1, 1):
        W.beam(blade, (0, s * (HALF_W + 0.22), Z_BLADE1 + 0.2), (0, s * 0.08, Z_TIP - 0.3), 0.5, 0.46,
               "edge", uv_scale=6, extend=0.3)
        W.beam(blade, (0, s * 0.39, Z_BLADE1 + 1.1), (0, 0, Z_BLADE1 - 1.0), 0.58, 0.3, "dark", uv_scale=8)


def build_core(m, root):
    """地球核: 光る地球儀を、ジャイロの籠（静止の外枠 + 回る二つの輪）が囲む。直径 6.4。"""
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    # 外枠: 正面向きの縦の輪（静止）と、上下の極の冠
    W.ring(cage, (0, 0, 0), 3.15, 16, (0, 0.5, 0.7), "frame", axis="z", uv_scale=8)
    for s in (-1, 1):
        y = s * 3.25
        W.octa(cage, (0, y, 0), 1.6, 0.8, "plate", axis="y", uv_scale=10)
        W.octa(cage, (0, y + s * 0.55, 0), 1.0, 0.5, "gold", axis="y", uv_scale=10)
        W.cbox(cage, (0, y + s * 0.95, 0), (0.42, 0.5, 0.42), "gem", rotation=(0, 45, 0), uv_scale=12)
        for a in (0, 90):                                    # 極から伸びるナノ回路の光
            W.cbox(cage, (0, y - s * 0.1, 0), (1.66 if a == 0 else 0.16, 0.14, 0.16 if a == 0 else 1.66),
                   "glow", uv_scale=12)
    for s in (-1, 1):                                        # 赤道の高さの留め具（左右）
        W.cbox(cage, (s * 3.15, 0, 0), (0.8, 1.0, 1.0), "plate2", uv_scale=10)
        W.cbox(cage, (s * 3.45, 0, 0), (0.3, 0.6, 0.6), "glow", uv_scale=12)
    # 地球儀（ゆっくり自転）
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.75, "core", uv_scale=14)
    # 回る輪 A: 縦の輪（YZ 平面）が鉛直軸まわりに回る
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    ra = W.spin(m, rings, "ring_a", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.6, 14, (0, 0.34, 0.55), "gold", axis="x", styles=["gold", "glow"], uv_scale=10)
    # 回る輪 B: 傾いた水平の輪（静止の傾き 28°）が首を振りながら回る
    rb = W.spin(m, rings, "ring_b", (0, 0, 0), rotation=(28, 0, 0))
    W.ring(rb, (0, 0, 0), 2.2, 12, (0, 0.3, 0.42), "silver", axis="y", styles=["silver", "glow_soft"],
           uv_scale=10)


# ---------------------------------------------------------------------------
#  塗り（astro_paint の惑星の配色から。上書きだけ書く）
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        edge={"glow": EDGE, "sat": 0.45, "emit": 40},
        energy={"glow": mix(EDGE, (120, 255, 170), 0.4)},
        wrap={"base": (20, 26, 44), "strap": (54, 104, 210), "skin": (226, 232, 240)},
        blade={"base": (186, 196, 214), "light": (244, 248, 255), "dark": (112, 122, 146),
               "line": (46, 54, 76)},
        blade_flat={"base": (184, 194, 212), "light": (240, 246, 255), "dark": (120, 130, 152)},
        dark={"base": (16, 22, 40), "glow": EDGE},
        core={"emit": 30, "halo": (120, 200, 255)},
        gem={"glow": (90, 255, 160)},
    )


def CORE_STYLES(key):
    return core_styles(key, core={"emit": 24, "halo": (130, 210, 255)})


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）。値は統合版のアニメのチャンネル（Molang 可）
#    v.astro_sw   攻撃の振り 0→1      v.astro_fp  一人称で 1      v.astro_usew  右クリック中 0→1
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_moon": {"rotation": [0, 0, "q.anim_time * 140.0"]},
        "fx_spin_globe": {"rotation": ["q.anim_time * 36.0", 0, 0]},
    },
    "swing": {
        # 振ると月が一周ぶん加速する
        "fx_spin_moon": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_blade": "z"},       # 刃は鍔から z 方向へ伸びる
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 45.0", 0]},
        "fx_spin_ring_a": {"rotation": [0, "q.anim_time * 80.0", 0]},
        "fx_spin_ring_b": {"rotation": [0, "-q.anim_time * 120.0", 0]},
    },
}
