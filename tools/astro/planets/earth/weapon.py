# -*- coding: utf-8 -*-
"""地球（ガイア）のナノウェポン「蒼星剣 ガイア・セイバー」と星核「地球核 アース・コア」。

ここは 8 人の惑星担当者が真似する見本。作り方の説明は planets/_template/README_weapon.md。

武器空間: 握りの中心 = 原点、刃先 = -Z、刃の幅 = ±Y、刃の平の法線 = ±X（16 単位 = 1 ブロック）。
手に持つと 0.9 倍（astro_hold.SPEC["sword"]）。握りの前後 ±2.9 は篭手に隠れるので、
鍔は z = -2.9 より先、柄頭は z = +2.9 より後ろに置く。

v1.1（7 頭身のスーツに合わせた細部）: 大きな形（全長・握り・鍔の幅）は v1.0 のまま、部品を細かく割った。
  form_0_grip    柄巻（暗い金属の節で 5 つに区切る）・リベット留めの金の口金・柄頭（光の線の入った
                 青い八角の台・金の冠・4 本の爪で留めた緑の宝玉）・宝玉の周りの光の軌道
                 └ fx_spin_moon   軌道を回る月の子機「ルナ・ビット」（月・機械の帯・外を向く目・アンテナ）
  form_1_guard   三層の十字の鍔
                   一段目: 青い主鍔。平に彫った暗い溝と光の芯・リベット・折れ目の金の帯・
                           先端の発振器（金の環 → 暗いノズル → 光）
                   二段目: 白い副鍔。刃側の金の縁・緑の大陸線。主鍔とは暗い継ぎ目と油圧シリンダーで繋ぐ
                   三段目: 柄の側へ流れる金の小翼
                 中央の台座（リベット）と、刃を受ける黒い襟（放熱の光）
                 └ fx_spin_globe  地球儀（自転）
                 └ fx_spin_bezel  地球儀を両面から挟む金の文字盤（光の目盛りが逆向きに回る）
  form_2_blade   刃（鍔から z 方向へ伸びる）: 鏡面の鋼の二枚・縁に沿う彫りの溝（切先で収束）・
                 発光の刃を留める発振器の歯・緑の大陸線の象嵌・暗い樋と機械の背骨（青い節）・
                 刃元の白い装甲（青い下段・リベット・大陸線）・切先
                 └ fx_glow_core   樋の芯を走る光（脈打つ）

細かい部品の作り方（見本）:
  * リベット・象嵌の線は、板を X 方向に **貫く** 細い箱で作る（1 個で両面に出る）。板の面より 0.04 以上
    外へ出す（同じ平面に重なる面は統合版でちらつく）。
  * 彫り込んだ溝は「暗い帯の上に、それより少しだけ外へ出た光の芯」の 2 段で。
  * 0.15 単位より細い部品は作らない（手に持つと 0.9 倍・テクスチャも 1〜2 テクセルになる）。
"""
from __future__ import annotations

import math

import astro_weapon as W
from astro_paint import core_styles, mix, weapon_styles

KIND = "sword"

# 刃の寸法（武器空間）
Z_BLADE0 = -6.4          # 刃の付け根（鍔の前）
Z_BLADE1 = -27.6         # 平行部の終わり
Z_TIP = -32.4            # 切先
HALF_W = 2.05            # 鋼の半幅（その外に発光の刃）
THICK = 0.9              # 刃の厚み（X）
GROOVE_Y = 1.55          # 縁に沿う彫りの溝の高さ（±Y）

EDGE = (88, 246, 204)    # 緑と青のあいだ（地球の発光色を海の青へ寄せた）

# 緑の大陸線（刃の平の象嵌）。(y, z) の点列。上側（+Y）と下側（-Y）で違う形にして、大陸の海岸線に見せる
CONTINENTS = (
    ((0.95, -9.0), (1.3, -10.3), (1.15, -11.6), (0.9, -12.4), (1.05, -14.0), (1.35, -14.8),
     (1.2, -16.4)),
    ((-1.25, -9.6), (-0.95, -10.8), (-1.05, -12.6), (-1.35, -13.5), (-1.2, -15.0), (-0.95, -15.9),
     (-1.1, -17.6)),
    ((1.0, -19.6), (1.32, -20.7), (1.1, -22.1)),
    ((-1.2, -21.1), (-0.95, -22.3), (-1.15, -23.5)),
)


def stud(bone, y, z, through, size=0.3, style="rivet"):
    """リベット: 板を X 方向に貫く小さな箱（through = 板の厚み + 0.08 以上。1 個で両面に頭が出る）。"""
    return W.cbox(bone, (0, y, z), (through, size, size), style, uv_scale=12)


def inlay(bone, pts_yz, through, width=0.17, style="glow"):
    """平らな板に象嵌した光の線（大陸線）。点列は (y, z)。板を X 方向に貫く角柱で、両面に同じ線が出る。"""
    return W.polyline(bone, [(0, y, z) for y, z in pts_yz], through, width, style, uv_scale=12)


def build_weapon(m, root):
    # =====================================================================
    #  form_0_grip — 柄・口金・柄頭・月の子機
    # =====================================================================
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    # 柄巻: 青い革紐の八角柱を、暗い金属の節で 5 つに区切る（中ほどの帯だけ金。篭手の指の間から覗く）
    W.octa(grip, (0, 0, 0.3), 1.75, 6.0, "wrap", uv_scale=8)
    for z in (-1.75, -0.7, 1.3, 2.35):
        W.octa(grip, (0, 0, z), 1.9, 0.24, "frame_lt", uv_scale=10)
    W.octa(grip, (0, 0, 0.3), 1.95, 0.45, "gold", uv_scale=10)
    # 口金（前後）: 柄巻との間の暗い段・金の環・四方のリベット
    for z, step in ((-3.25, -2.75), (3.85, 3.35)):
        W.octa(grip, (0, 0, step), 2.0, 0.32, "frame", uv_scale=10)
        W.octa(grip, (0, 0, z), 2.3, 0.7, "gold", uv_scale=8)
        stud(grip, 0, z, 2.46, size=0.28)                                         # ±X の面
        W.cbox(grip, (0, 0, z), (0.28, 2.46, 0.28), "rivet", uv_scale=12)          # ±Y の面
    # 柄頭: 光の線の入った青い八角の台・暗い段・金の冠・4 本の爪で留めた緑の宝玉
    W.octa(grip, (0, 0, 4.9), 2.3, 1.4, "plate", uv_scale=8)
    W.cbox(grip, (0, 0, 4.9), (2.4, 0.18, 0.9), "glow", uv_scale=12)
    W.cbox(grip, (0, 0, 4.9), (0.18, 2.4, 0.9), "glow", uv_scale=12)
    W.octa(grip, (0, 0, 5.7), 1.8, 0.3, "frame", uv_scale=10)
    W.cbox(grip, (0, 0, 5.95), (1.8, 1.8, 0.5), "gold", rotation=(0, 0, 45), uv_scale=8)
    W.cbox(grip, (0, 0, 6.5), (1.1, 1.1, 0.8), "gem", rotation=(0, 0, 45), uv_scale=10)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        # 爪の先は宝玉の頂より低く（柄頭を v1.0 より長くしない。腰や胸に刺さる — README §3）
        W.beam(grip, (dx * 1.0, dy * 1.0, 6.05), (dx * 0.5, dy * 0.5, 6.7), 0.22, 0.22, "gold",
               uv_scale=12)
    # 月の軌道（細い光の輪。宝玉の冠の外を回る）
    W.ring(grip, (0, 0, 6.0), 1.9, 14, (0, 0.16, 0.16), "glow_soft", axis="z")
    # 月の子機ルナ・ビット: 軌道に乗って回る（スーツの肩の子機と同じ意匠を小さく）
    moon = W.spin(m, grip, "moon", (0, 0, 6.0))
    M = (0, 1.9, 6.0)
    W.sphere(moon, M, 0.55, "moon", uv_scale=14)
    W.ring(moon, M, 0.72, 8, (0, 0.16, 0.24), "gold", axis="y", uv_scale=12)      # 機械の帯
    W.octa(moon, (0, 2.5, 6.0), 0.42, 0.24, "frame", axis="y", uv_scale=12)       # 外を向く目
    W.cbox(moon, (0, 2.66, 6.0), (0.22, 0.15, 0.22), "glow", uv_scale=12)
    W.beam(moon, (0, 2.2, 6.35), (0, 2.6, 6.95), 0.16, 0.16, "gold", uv_scale=12)   # アンテナ

    # =====================================================================
    #  form_1_guard — 三層の十字の鍔と、中央の地球儀
    # =====================================================================
    guard = W.form(m, root, 1, "guard", (0, 0, -3.6))
    zc = -4.6
    # 中央の台座（側面から見ると八角形）と、上下のリベット
    W.bevel(guard, (0, 0, zc), (2.2, 4.4, 2.6), "plate", cut=0.6, axis="x", edge_style="plate_b",
            uv_scale=6)
    for s in (-1, 1):
        stud(guard, s * 2.0, zc, 2.3)
    globe = W.spin(m, guard, "globe", (0, 0, zc))
    W.sphere(globe, (0, 0, zc), 1.45, "globe", uv_scale=14)
    # 地球儀を両面から挟む金の文字盤（光の目盛りが地球儀と逆向きに回る）
    bezel = W.spin(m, guard, "bezel", (0, 0, zc))
    for s in (-1, 1):
        W.ring(bezel, (s * 1.12, 0, zc), 1.68, 12, (0, 0.34, 0.3), "gold", axis="x",
               styles=["gold", "gold", "glow"], uv_scale=10)
    for s in (-1, 1):
        # 一段目: 青い主鍔（太い角材の先を刃の側へ折る）
        W.cbox(guard, (0, s * 4.3, -4.2), (1.9, 4.6, 1.9), "plate", uv_scale=6)
        W.beam(guard, (0, s * 6.35, -4.2), (0, s * 7.5, -6.4), 1.7, 1.7, "plate", uv_scale=6)
        W.cbox(guard, (0, s * 4.35, -4.2), (1.98, 3.7, 0.66), "dark", uv_scale=10)      # 彫り込んだ溝
        W.cbox(guard, (0, s * 4.35, -4.2), (2.06, 3.3, 0.24), "glow", uv_scale=12)      # その芯の光
        W.cbox(guard, (0, s * 6.55, -4.15), (2.0, 0.5, 2.1), "gold", uv_scale=10)       # 折れ目の金の帯
        for y in (2.6, 5.6):                                                          # 溝の両側のリベット
            for z in (-3.55, -4.85):
                stud(guard, s * y, z, 2.0, size=0.28)
        # 先端の発振器: 金の環 → 暗いノズル → 光（刃の側を向く）
        W.beam(guard, (0, s * 7.5, -6.4), (0, s * 7.62, -7.0), 1.25, 1.25, "gold", uv_scale=10)
        W.beam(guard, (0, s * 7.62, -7.0), (0, s * 7.72, -7.5), 0.9, 0.9, "frame", uv_scale=10)
        W.beam(guard, (0, s * 7.72, -7.5), (0, s * 7.78, -7.85), 0.55, 0.55, "glow", uv_scale=12)
        # 主鍔と副鍔の間の暗い継ぎ目
        W.cbox(guard, (0, s * 4.1, -5.25), (1.6, 3.4, 0.4), "frame", uv_scale=10)
        # 二段目: 白い副鍔（刃の側に重ね、先を前へ流す）。刃側の縁の金と緑の大陸線
        W.cbox(guard, (0, s * 3.4, -5.85), (1.5, 3.2, 1.1), "plate2", uv_scale=8)
        W.beam(guard, (0, s * 4.9, -5.85), (0, s * 5.7, -7.6), 1.3, 1.0, "plate2", uv_scale=8)
        W.beam(guard, (0, s * 5.7, -7.6), (0, s * 5.85, -8.5), 0.7, 0.6, "gold", uv_scale=10, extend=0.2)
        W.cbox(guard, (0, s * 3.4, -6.32), (1.58, 2.8, 0.18), "gold", uv_scale=12)
        inlay(guard, [(s * 2.1, -5.55), (s * 2.8, -5.85), (s * 3.5, -5.6), (s * 4.4, -5.95)], 1.58)
        # 主鍔の折れ目から副鍔の先へ渡す油圧シリンダー（暗い筒 + 鋼の棒）
        W.beam(guard, (0, s * 6.35, -5.33), (0, s * 5.95, -6.1), 0.5, 0.5, "frame", uv_scale=12)
        W.beam(guard, (0, s * 6.0, -6.0), (0, s * 5.6, -6.8), 0.26, 0.26, "steel", uv_scale=12)
        # 三段目: 柄の側へ流れる金の小翼
        W.beam(guard, (0, s * 1.9, -3.4), (0, s * 3.9, -2.4), 1.1, 0.7, "gold", uv_scale=10)
        W.beam(guard, (0, s * 3.9, -2.4), (0, s * 4.5, -1.6), 0.7, 0.5, "gold", uv_scale=10)
    # 刃の発振器（刃を受ける黒い襟と放熱の光）
    W.cbox(guard, (0, 0, -6.2), (1.7, 3.8, 0.8), "frame", uv_scale=8)
    for s in (-1, 1):
        W.cbox(guard, (s * 0.88, 0, -6.2), (0.15, 2.8, 0.3), "energy", uv_scale=12)

    # =====================================================================
    #  form_2_blade — 刃（鍔から伸びる）
    # =====================================================================
    blade = W.form(m, root, 2, "blade", (0, 0, Z_BLADE0))
    L = Z_BLADE0 - Z_BLADE1
    zm = (Z_BLADE0 + Z_BLADE1) / 2
    for s in (-1, 1):
        # 鋼の二枚（樋の両側）と、発光する刃（緑青）
        W.cbox(blade, (0, s * (HALF_W + 0.45) / 2, zm), (THICK, HALF_W - 0.45, L), "blade", uv_scale=5)
        W.cbox(blade, (0, s * (HALF_W + 0.22), zm), (0.5, 0.46, L), "edge", uv_scale=6)
        # 縁に沿う彫りの溝（両面に出る暗い線。切先で刃先へ収束する）
        W.cbox(blade, (0, s * GROOVE_Y, zm - 0.4), (THICK + 0.08, 0.16, L - 2.6), "dark", uv_scale=10)
        W.beam(blade, (0, s * GROOVE_Y, Z_BLADE1 + 0.9), (0, s * 0.3, Z_TIP + 1.5), THICK + 0.08, 0.16,
               "dark", uv_scale=10)
        # 発光の刃を留める発振器の歯（3 単位おき）
        for i in range(6):
            W.cbox(blade, (0, s * 2.0, -9.4 - i * 3.0), (THICK + 0.12, 0.36, 0.56), "plate", uv_scale=12)
    # 緑の大陸線の象嵌
    for pts in CONTINENTS:
        inlay(blade, pts, THICK + 0.1)
    # 暗い樋（一段くぼむ）と、その芯を走る光（fx_glow_core で脈打つ）
    W.cbox(blade, (0, 0, zm - 0.6), (0.56, 0.98, L - 1.2), "dark", uv_scale=6)
    core = W.glow(m, blade, "core", (0, 0, zm - 1.4))
    W.cbox(core, (0, 0, zm - 1.4), (0.66, 0.3, L - 4.0), "energy", uv_scale=6)
    # 機械の背骨: 樋の上に並ぶ青い節（刃元から先へ小さくなる）。節ごとに光る切れ目
    for i in range(6):
        k = 1.0 - i * 0.075
        z = -8.9 - i * 2.55
        W.chamfer(blade, (0, 0, z), (1.36, 1.55 * k, 1.95 * k), "plate", cut=0.32, axis="x", uv_scale=8)
        W.cbox(blade, (0, 0, z - 0.25), (1.4, 0.95 * k, 0.22), "glow", uv_scale=10)
    # 刃元の白い装甲（左右）: 青い下段・縁の発光・リベット・大陸線
    for s in (-1, 1):
        W.cbox(blade, (0, s * 1.55, -7.5), (1.1, 2.2, 2.4), "plate_b", uv_scale=8)
        W.cbox(blade, (0, s * 1.5, -7.45), (1.24, 1.9, 2.1), "plate2", uv_scale=8)
        W.beam(blade, (0, s * 0.62, -8.45), (0, s * 2.4, -9.15), 1.26, 0.24, "glow", uv_scale=10)
        stud(blade, s * 2.05, -6.85, 1.32, size=0.28)
        inlay(blade, [(s * 0.8, -6.75), (s * 1.25, -7.15), (s * 1.1, -7.75), (s * 1.75, -8.05)], 1.32)
    # 切先: 鋼の三角と、刃先へ収束する発光の刃・樋の終わりの矢じり
    W.blade_point(blade, Z_BLADE1 + 0.05, HALF_W, Z_TIP, THICK, "blade_flat", layer=0.8, uv_scale=6)
    for s in (-1, 1):
        W.beam(blade, (0, s * (HALF_W + 0.22), Z_BLADE1 + 0.2), (0, s * 0.08, Z_TIP - 0.3), 0.5, 0.46,
               "edge", uv_scale=6, extend=0.3)
        W.beam(blade, (0, s * 0.49, Z_BLADE1 + 1.1), (0, 0, Z_BLADE1 - 1.2), 0.58, 0.34, "dark", uv_scale=8)


def build_core(m, root):
    """地球核: 光る地球儀を、ジャイロの籠（静止の外枠 + 回る二つの輪）が囲む。直径 6.4。
    北極の冠の外を月の子機ルナ・ビット（fx_spin_luna）が回る。"""
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
    for a in (45, 135, 225, 315):                            # 外枠を留めるボルト（輪を Z に貫いて両面に頭）
        x, y = -3.15 * math.sin(math.radians(a)), 3.15 * math.cos(math.radians(a))
        W.cbox(cage, (x, y, 0), (0.3, 0.3, 0.86), "rivet", uv_scale=14)
    # 地球儀（ゆっくり自転）
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.75, "globe", uv_scale=16)
    # 回る輪 A: 縦の輪（YZ 平面）が鉛直軸まわりに回る
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    ra = W.spin(m, rings, "ring_a", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.6, 14, (0, 0.34, 0.55), "gold", axis="x", styles=["gold", "glow"], uv_scale=10)
    # 回る輪 B: 傾いた水平の輪（静止の傾き 28°）が首を振りながら回る
    rb = W.spin(m, rings, "ring_b", (0, 0, 0), rotation=(28, 0, 0))
    W.ring(rb, (0, 0, 0), 2.2, 12, (0, 0.3, 0.42), "silver", axis="y", styles=["silver", "glow_soft"],
           uv_scale=10)
    # 月の子機ルナ・ビット: 北極の冠の外を小さく回る（外を向く光の目。右クリック中は輪と一緒に加速）
    luna = W.spin(m, rings, "luna", (0, 0, 0))
    W.sphere(luna, (0, 3.55, -1.6), 0.38, "moon", uv_scale=16)
    W.cbox(luna, (0, 3.55, -2.02), (0.22, 0.22, 0.15), "glow", uv_scale=16)


# ---------------------------------------------------------------------------
#  塗り（astro_paint の惑星の配色から。上書きだけ書く）
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(
        key,
        edge={"glow": EDGE, "sat": 0.45, "emit": 40},
        energy={"glow": mix(EDGE, (120, 255, 170), 0.4)},
        wrap={"base": (20, 26, 44), "strap": (54, 104, 210), "skin": (226, 232, 240)},
        # 刃の平は鏡面（映り込みの地平線が刃に沿って走る）。切先は段で作るので平らな鋼で
        blade={"kind": "chrome", "base": (184, 204, 236), "light": (246, 250, 255), "line": (40, 52, 80)},
        blade_flat={"base": (176, 194, 222), "light": (236, 244, 255), "dark": (120, 134, 162)},
        dark={"base": (16, 22, 40), "glow": EDGE},
        globe=W.globe_style("earth", emit=36),
        moon=W.globe_style("luna", emit=255, halo=None),
        gem={"glow": (90, 255, 160)},
    )


def CORE_STYLES(key):
    return core_styles(key, globe=W.globe_style("earth", emit=30),
                       moon=W.globe_style("luna", emit=255, halo=None))


# ---------------------------------------------------------------------------
#  アニメ（アタッチャブル）。値は統合版のアニメのチャンネル（Molang 可）
#    v.astro_sw   攻撃の振り 0→1      v.astro_fp  一人称で 1      v.astro_usew  右クリック中 0→1
#  待機の q.anim_time は `q.anim_time * 度/秒` の形だけ。速さを 30°/秒の倍数にそろえると、
#  origin の呼吸（90°/秒）と合わせて待機ループが 12 秒になる（継ぎ目で部品が飛ばない）。
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {
        "fx_spin_moon": {"rotation": [0, 0, "q.anim_time * 150.0"]},       # 月の子機が軌道を回る
        "fx_spin_globe": {"rotation": ["q.anim_time * 30.0", 0, 0]},       # 地球儀の自転
        "fx_spin_bezel": {"rotation": ["-q.anim_time * 60.0", 0, 0]},      # 文字盤は逆向きに
        # 樋の芯の光が脈打つ（太さだけ。長さは変えない）
        "fx_glow_core": {"scale": ["1.0 + math.sin(q.anim_time * 240.0) * 0.14",
                                   "1.0 + math.sin(q.anim_time * 240.0) * 0.22", "1.0"]},
    },
    "swing": {
        # 振ると月が一周ぶん加速する
        "fx_spin_moon": {"rotation": [0, 0, "v.astro_sw * 360.0"]},
    },
    "form_axes": {"form_2_blade": "z"},       # 刃は鍔から z 方向へ伸びる
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": {"rotation": [0, "q.anim_time * 45.0", 0],
                          "scale": "1.0 + math.sin(q.anim_time * 150.0) * 0.04"},          # 球の脈動
        "fx_spin_ring_a": {"rotation": [0, "q.anim_time * 80.0", 0]},
        "fx_spin_ring_b": {"rotation": [0, "-q.anim_time * 120.0", 0]},
        "fx_spin_luna": {"rotation": [0, "q.anim_time * 120.0", 0]},
    },
}
