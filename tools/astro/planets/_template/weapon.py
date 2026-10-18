# -*- coding: utf-8 -*-
"""<惑星> のナノウェポン「<武器名>」と星核「<コア名>」 — 雛形。

使い方: planets/<key>/ にコピーし、build_weapon / build_core を自分の武器に書き換える。
説明は planets/_template/README_weapon.md、お手本は planets/earth/weapon.py（蒼星剣 ガイア・セイバー）。

    python3 tools/astro/astro_weapon.py preview <key>      # 作って描く → build_preview/astro/weapon_<key>.png
    python3 tools/astro/gen_astro_weapons.py <key>         # pack へ書き出す（共有アニメは全惑星分を作り直す）

武器空間: 握りの中心 = 原点、刃先（穂先・鎚頭・銃口）= -Z、刃の幅 = ±Y（片刃は -Y が刃）、平の法線 = ±X。
16 単位 = 1 ブロック。手に持つと astro_hold.SPEC[kind]["scale"] 倍（剣・斧なら 0.9）。
握りの前後 ±GRIP_HALF/scale（剣なら ±2.9）は篭手に隠れる → 鍔はそれより -Z、柄頭はそれより +Z に。
回転は統合版の値そのまま（rx 正 = 上端が -Z へ / ry 正 = 正面が -X へ / rz 正 = 上端が -X へ）。
"""
from __future__ import annotations

import astro_weapon as W
from astro_paint import core_styles, weapon_styles

# 持ち方の種類。省略すると astro_data.PLANETS[key]["weapon"]["kind"]
# KIND = "sword"

# 持ち方の上書き（普通は書かない）。scale: 手に持った縮尺 / anchor: 握りの点（武器空間）/
# tp: {"fwd": 刃先の向き, "up": 武器の +Y の向き}（体の空間）/ fp: {"fwd", "flat", "at", "scale"}（カメラ空間）
# HOLD = {"scale": 0.9}
# CORE_HOLD = {}

# アイコンの撮り方 (yaw, pitch, 画面上の回転)。省略すると種類ごとの既定（剣は (90, 0, 45)）
# ICON = {"weapon": (90, 0, 45), "core": (25, -18, 0)}


def build_weapon(m, root):
    """root（ボーン名 origin）の下に form_<番号>_<名前> の部品ボーンを作り、その中にキューブを置く。
    番号の順に、持ち替えた瞬間ポップして現れる（同じ番号は同時）。pivot は「生えてくる根元」。"""
    # ---- form_0_grip: 柄（握りは篭手に隠れる。柄頭は +Z 側） ------------------------
    grip = W.form(m, root, 0, "grip", (0, 0, 0))
    W.octa(grip, (0, 0, 0.3), 1.7, 6.6, "wrap", uv_scale=8)          # 柄巻（八角柱）
    for z in (-3.2, 3.8):
        W.octa(grip, (0, 0, z), 2.2, 0.7, "gold", uv_scale=8)         # 口金
    W.octa(grip, (0, 0, 5.0), 2.3, 1.5, "plate", uv_scale=8)          # 柄頭
    W.cbox(grip, (0, 0, 6.2), (1.1, 1.1, 0.8), "gem", rotation=(0, 0, 45), uv_scale=10)

    # ---- form_1_guard: 鍔（刃の幅の向き ±Y に張る）と、中央の星核 ---------------------
    guard = W.form(m, root, 1, "guard", (0, 0, -3.6))
    W.bevel(guard, (0, 0, -4.6), (2.2, 4.2, 2.4), "plate", cut=0.5, axis="x", uv_scale=6)
    W.sphere(guard, (0, 0, -4.6), 1.3, "globe", uv_scale=14)          # 惑星の球（継ぎ目なく模様を貼る）
    for s in (-1, 1):
        W.beam(guard, (0, s * 2.0, -4.4), (0, s * 6.0, -4.0), 1.6, 1.4, "plate2", uv_scale=6)
        W.beam(guard, (0, s * 6.0, -4.0), (0, s * 6.6, -5.8), 1.0, 1.0, "gold", uv_scale=10)

    # ---- form_2_blade: 刃（鍔から -Z へ伸びる。FORM_AXES で z 方向に伸ばす） ----------
    blade = W.form(m, root, 2, "blade", (0, 0, -5.8))
    W.cbox(blade, (0, 0, -16.0), (0.8, 3.6, 20.4), "blade", uv_scale=5)
    for s in (-1, 1):
        W.cbox(blade, (0, s * 1.95, -16.0), (0.5, 0.4, 20.4), "edge", uv_scale=6)   # 発光の刃
    W.cbox(blade, (0, 0, -16.6), (0.86, 0.3, 17.0), "energy", uv_scale=6)          # 樋の光
    W.blade_point(blade, -26.15, 1.8, -30.0, 0.8, "blade_flat", layer=0.8, uv_scale=6)

    # ---- 回る部品は fx_spin_<名前>（WEAPON_ANIMS で回す。書かなければ既定で Z 軸まわり） ----
    ring = W.spin(m, guard, "ring", (0, 0, -4.6))
    W.ring(ring, (0, 0, -4.6), 3.0, 12, (0, 0.3, 0.4), "glow_soft", axis="z")


def build_core(m, root):
    """手のひらサイズ（直径 5〜7）。中心にその惑星の球、機械の枠、fx_spin_ の輪。30〜80 キューブ。"""
    cage = W.form(m, root, 1, "cage", (0, 0, 0))
    W.ring(cage, (0, 0, 0), 3.0, 16, (0, 0.5, 0.7), "frame", axis="z", uv_scale=8)
    for s in (-1, 1):
        W.octa(cage, (0, s * 3.1, 0), 1.5, 0.8, "plate", axis="y", uv_scale=10)
    globe = W.form(m, root, 0, "globe", (0, 0, 0))
    spin = W.spin(m, globe, "globe", (0, 0, 0))
    W.sphere(spin, (0, 0, 0), 1.7, "globe", uv_scale=16)
    rings = W.form(m, root, 2, "rings", (0, 0, 0))
    ra = W.spin(m, rings, "ring_a", (0, 0, 0))
    W.ring(ra, (0, 0, 0), 2.5, 14, (0, 0.34, 0.5), "gold", axis="x", styles=["gold", "glow"], uv_scale=10)
    rb = W.spin(m, rings, "ring_b", (0, 0, 0), rotation=(25, 0, 0))    # 静止の傾き → 首を振って回る
    W.ring(rb, (0, 0, 0), 2.1, 12, (0, 0.3, 0.4), "silver", axis="y", uv_scale=10)


# ---------------------------------------------------------------------------
#  塗り: 惑星の配色から作った一式（astro_paint.weapon_styles / core_styles）に上書きだけ書く。
#  関数にすると key（惑星）を受け取れる。globe_style は球に惑星の模様を貼る塗り。
# ---------------------------------------------------------------------------
def WEAPON_STYLES(key):
    return weapon_styles(key, globe=W.globe_style(key, emit=36))


def CORE_STYLES(key):
    return core_styles(key, globe=W.globe_style(key, emit=30))


# ---------------------------------------------------------------------------
#  アタッチャブルのアニメ（統合版のチャンネル。Molang 可）
#    q.anim_time  経過秒        v.astro_sw  攻撃の振り 0→1（c.owning_entity->v.attack_time）
#    v.astro_fp   一人称で 1     v.astro_usew  右クリック中 0→1（なめらか）
# ---------------------------------------------------------------------------
WEAPON_ANIMS = {
    "idle": {"fx_spin_ring": W.spin_expr("z", 90)},          # = {"rotation": [0, 0, "q.anim_time * 90"]}
    "swing": {"fx_spin_ring": {"rotation": [0, 0, "v.astro_sw * 360.0"]}},
    "form_axes": {"form_2_blade": "z"},                       # 刃は鍔から z 方向へ伸びる
    # "swing_root": {"rx": (34, 66)},                         # 手首の返しの角度（三人称, 一人称）の上書き
}

CORE_ANIMS = {
    "idle": {
        "fx_spin_globe": W.spin_expr("y", 45),
        "fx_spin_ring_a": W.spin_expr("y", 80),
        "fx_spin_ring_b": W.spin_expr("y", -120),
    },
}
