# -*- coding: utf-8 -*-
"""天王星（ウラノス）の全身モーション。武器は傾天弩 ティルト・ボウガン（kind crossbow: 銃口 = 刃先の向き）。
書き方は astro_animlib の冒頭と planets/_template/README_weapon.md §9。向きは体の空間 dirv(f=前, u=上, r=右)。

  combo1        右から左へ、弓端の氷晶で横に払う
  combo2        左下から右上へ、弩を返して斬り上げる
  combo3        踏み込んで弩を突き出し、至近距離で撃つ（三段目: 氷晶散弾。反動で跳ね上がる）
  aim_shot      惑星技 絶対零度矢: 両手で目の高さに構え、狙い、撃つ（0.4 秒で発射。反動）
  roll / roll_l 機動技 98° ロール: 弩を胸に抱えて横倒しに一回転（前へ進む軸のまわりの横転。右へ / 左へ）
  rain_shot     空中技 ダイヤモンド・レイン: 宙で前上方へ二連射（0.3 秒・0.55 秒）
  tilt_cast     必殺 アクシアル・ティルト（前半）: 左手で世界を横へ傾ける。体ごと 98° の向きへ傾く
  zero_shot     必殺の締め: 片膝をついて構え、凍った敵を砕く一射（0.35 秒で発射。大きな反動）
"""
from __future__ import annotations

from astro_animlib import H, P, aim, anim, dirv, flip, wield

# 弩を支える左手（銃身の下へ）
SUPPORT = aim(dirv(f=1.0, u=0.05, r=-0.5), twist=20)

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(0, 40, 0), h=(0, -30, 0),
            rA=wield(blade=dirv(r=1.0, f=0.1, u=0.1), arm=dirv(r=1.0, u=-0.3, f=0.2)),
            lA=aim(dirv(f=1.0, r=-0.3, u=-0.2)), rL=(12, 0, 6), lL=(-16, 0, -6), ground=True)
c1_hit = P(b=(6, -10, 0), h=(0, 8, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.55, u=0.0), arm=dirv(f=1.0, r=0.15, u=-0.35)),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.6)), rL=(22, 0, 6), lL=(-30, 0, -6), root_pos=(0, 0, -1.0),
           ground=True)
c1_follow = P(c1_hit, b=(8, -40, 0), h=(0, 30, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.4, u=-0.05), arm=dirv(r=-0.7, f=0.7, u=-0.3)))

c2_wind = P(b=(10, -32, 0), h=(0, 24, 0),
            rA=wield(blade=dirv(r=-0.6, u=-0.7, f=0.5), arm=dirv(f=1.0, u=-0.6, r=-0.2)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)), rL=(-22, 0, 6), lL=(14, 0, -6), ground=True)
c2_hit = P(b=(-6, 24, 0), h=(0, -18, 0),
           rA=wield(blade=dirv(r=0.6, u=0.7, f=0.5), arm=dirv(r=0.7, u=0.2, f=0.7)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)), rL=(-26, 0, 6), lL=(18, 0, -6), root_pos=(0, 0.4, -0.8),
           ground=True)
c2_follow = P(c2_hit, b=(-10, 34, 0), h=(-6, -26, 0),
              rA=wield(blade=dirv(r=0.5, u=0.85, f=-0.1), arm=dirv(r=0.85, u=0.5, f=0.2)))

c3_load = P(b=(4, 20, 0), h=(0, -14, 0), w=(6, 0, 0),
            rA=wield(blade=dirv(f=1.0, u=0.1), arm=dirv(f=-0.5, u=-1.0, r=0.4)),
            lA=aim(dirv(f=1.0, u=-0.2, r=-0.1)), rL=(10, 0, 6), lL=(-14, 0, -6), ground=True)
c3_fire = P(w=(14, 0, 0), b=(4, -14, 0), h=(-6, 12, 0),
            rA=wield(blade=dirv(f=1.0, u=-0.05, r=0.05), arm=dirv(f=1.0, u=0.1, r=0.1)),
            lA=SUPPORT, rL=(30, 0, 6), lL=(-44, 0, -6), root_pos=(0, 0, -2.0), ground=True)
c3_kick = P(c3_fire, w=(-4, 0, 0), b=(-12, -10, 0), h=(-10, 10, 0),
            rA=wield(blade=dirv(f=1.0, u=0.75, r=0.1), arm=dirv(f=1.0, u=0.6, r=0.25)),
            root_pos=(0, 0, -0.8))

# ---- 惑星技: 構えて撃つ -------------------------------------------------------
aim_raise = P(b=(-4, 14, 0), h=(4, -10, 0),
              rA=wield(blade=dirv(f=1.0, u=0.15, r=0.1), arm=dirv(f=1.0, u=-0.1, r=0.35)),
              lA=aim(dirv(f=1.0, u=0.1, r=-0.45), twist=20), rL=(10, 0, 8), lL=(-14, 0, -8), ground=True)
aim_hold = P(aim_raise, b=(0, 18, 0), h=(6, -14, 0),
             rA=wield(blade=dirv(f=1.0, u=0.02), arm=dirv(f=1.0, u=0.05, r=0.3)),
             lA=aim(dirv(f=1.0, u=0.0, r=-0.5), twist=20))
aim_fire = P(aim_hold, b=(-10, 14, 0), h=(-4, -10, 0), root_pos=(0, 0, 0.8),
             rA=wield(blade=dirv(f=1.0, u=0.45, r=0.05), arm=dirv(f=1.0, u=0.35, r=0.3)),
             lA=aim(dirv(f=1.0, u=0.35, r=-0.45), twist=20))

# ---- 機動技: 横倒しの一回転 ----------------------------------------------------
tuck = P(rA=wield(blade=dirv(u=1.0, f=0.3, r=-0.2), arm=dirv(f=0.6, u=-0.4, r=0.3)),
         lA=aim(dirv(f=1.0, u=0.2, r=-0.6), twist=30), h=(10, 0, 0))


def roll_frames(turns):
    """turns = -1 で右へ、+1 で左へ倒れ込む一回転（前へ進む軸のまわり）。"""
    end = 360.0 * turns
    fr = flip(0.04, 0.46, turns, "z", centre=15.0, steps=8, tuck=False, base=tuck)
    fr[0.0] = H
    fr[0.56] = P(rA=wield(blade=dirv(f=1.0, r=0.3, u=-0.2), arm=dirv(r=0.8, u=-0.6, f=0.2)),
                 lA=aim(dirv(r=-0.9, u=-0.5, f=0.2)), rL=(-20, 0, 12), lL=(20, 0, -12),
                 root=(0, 0, end), ground=True)
    fr[0.7] = P(root=(0, 0, end))
    return fr


# ---- 空中技: 前上方へ二連射 ----------------------------------------------------
rain_aim = P(b=(-12, 6, 0), h=(-24, -4, 0),
             rA=wield(blade=dirv(f=1.0, u=1.1, r=0.05), arm=dirv(f=1.0, u=0.6, r=0.35)),
             lA=aim(dirv(f=1.0, u=1.0, r=-0.4), twist=20), rL=(-30, 0, 6), lL=(10, 0, -6))
rain_kick = P(rain_aim, b=(-20, 6, 0), h=(-30, -4, 0),
              rA=wield(blade=dirv(f=0.6, u=1.2, r=0.05), arm=dirv(f=0.8, u=0.9, r=0.35)))

# ---- 必殺: 世界を傾ける → 砕く一射 ---------------------------------------------
tilt_reach = P(b=(-8, 12, 12), h=(-22, -10, 8),
               lA=aim(dirv(r=-0.55, u=1.0, f=0.35), twist=-40),
               rA=wield(blade=dirv(f=0.7, u=-0.3, r=0.6), arm=dirv(r=0.7, u=-0.7, f=0.1)),
               rL=(-6, 0, 12), lL=(6, 0, -12), ground=True)
tilt_turn = P(b=(6, -14, -22), h=(4, 12, -16),
              lA=aim(dirv(r=0.9, u=-0.45, f=0.55), twist=-90),
              rA=wield(blade=dirv(f=0.5, u=-0.5, r=0.7), arm=dirv(r=0.8, u=-0.6)),
              rL=(-10, 0, 16), lL=(10, 0, -6), root=(0, 0, -8), ground=True)
zero_aim = P(w=(16, 0, 0), h=(-14, 0, 0), b=(0, 16, 0),
             rA=wield(blade=dirv(f=1.0, u=0.05), arm=dirv(f=1.0, u=0.05, r=0.3)),
             lA=aim(dirv(f=1.0, u=0.0, r=-0.5), twist=20),
             rL=(58, 0, 6), lL=(-52, 0, -6), ground=True)
zero_fire = P(zero_aim, w=(4, 0, 0), b=(-12, 14, 0), h=(-18, 0, 0),
              rA=wield(blade=dirv(f=1.0, u=0.6, r=0.05), arm=dirv(f=1.0, u=0.45, r=0.3)),
              lA=aim(dirv(f=1.0, u=0.45, r=-0.45), twist=20), root_pos=(0, 0, 1.2))

BODY_ANIMS = {
    "combo1": anim(0.45, {0.0: H, 0.07: c1_wind, 0.16: c1_hit, 0.25: c1_follow,
                          0.34: P(c1_follow, b=(6, -36, 0)), 0.45: H}),
    "combo2": anim(0.45, {0.0: H, 0.08: c2_wind, 0.19: c2_hit, 0.28: c2_follow,
                          0.36: P(c2_follow, b=(-8, 30, 0)), 0.45: H}),
    "combo3": anim(0.65, {0.0: H, 0.12: c3_load, 0.22: c3_fire, 0.3: c3_kick,
                          0.48: P(c3_kick, b=(-6, -8, 0)), 0.65: H}),
    "aim_shot": anim(0.9, {0.0: H, 0.12: aim_raise, 0.3: aim_hold, 0.4: aim_hold, 0.46: aim_fire,
                           0.66: P(aim_hold, b=(-2, 16, 0)), 0.9: H}),
    "roll": anim(0.7, roll_frames(-1.0), kind="act"),          # 右へ転がる
    "roll_l": anim(0.7, roll_frames(1.0), kind="act"),         # 左へ転がる
    "rain_shot": anim(0.8, {0.0: H, 0.1: rain_aim, 0.28: rain_aim, 0.33: rain_kick, 0.48: rain_aim,
                            0.56: rain_kick, 0.68: P(rain_aim, b=(-8, 6, 0)), 0.8: H}),
    "tilt_cast": anim(1.2, {0.0: H, 0.18: tilt_reach, 0.5: P(tilt_reach, b=(-4, -22, -16)),
                            0.72: tilt_turn, 1.0: P(tilt_turn, root=(0, 0, -6)), 1.2: H}),
    "zero_shot": anim(0.9, {0.0: H, 0.14: zero_aim, 0.32: zero_aim, 0.37: zero_fire,
                            0.6: P(zero_fire, b=(-8, 14, 0)), 0.9: H}),
}
