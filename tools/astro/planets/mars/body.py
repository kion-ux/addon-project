# -*- coding: utf-8 -*-
"""火星（アレス）の全身モーション。書き方は astro_animlib の冒頭と planets/_template/README_weapon.md §9。

武器は軍神斧（kind axe: 手首の角度 96°。柄は前腕とほぼ直角）。wield(blade=斧頭の向き, edge=刃の向く側 /
arm=腕の向き)。向きは体の空間: dirv(f=前, u=上, r=右)。重い武器なので溜めは深く、振り抜きは大きく、
踏み込みは低く（ground=True で足を地に着ける）。

  combo1       右から左への重い横薙ぎ
  combo2       左下から右上への逆袈裟の斬り上げ
  combo3       跳び上がって真上から叩きつける（三段目: 杭打ち）
  storm_call   惑星技 赤砂嵐: 身を縮めて力を溜め、腕と斧を大きく広げて吼える
  warpath      機動技 ウォーパス: 左肩を前に低く突っ込み、最後に斧で打ち上げる
  olympus_dive 空中技 オリンポス・インパクト: 斧を頭上に振りかぶったまま真下へ落ちる
  olympus_land 空中技の着地: 片膝をつき、斧を地面に叩き込む
  moon_call    必殺 フォボス＆ダイモス: 左手を天へ掲げて衛星を呼び、標的を指し示す
  war_roar     必殺の締め・雄叫び: 胸を張り、斧と腕を広げて天へ吼える
"""
from __future__ import annotations

from astro_animlib import LEFT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(4, 44, 0), h=(0, -34, 0), w=(6, 0, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.35, u=0.25), arm=dirv(r=1.0, u=-0.2, f=0.05)),
            lA=aim(dirv(f=1.0, r=-0.4, u=-0.1)),
            rL=(14, 0, 8), lL=(-18, 0, -8), ground=True)
c1_lift = P(b=(2, 22, 0), h=(0, -16, 0),
            rA=wield(blade=dirv(r=0.7, u=0.7, f=0.2), arm=dirv(r=1.0, u=-0.35, f=0.2)),
            lA=aim(dirv(f=1.0, r=-0.3, u=-0.2)), rL=(8, 0, 6), lL=(-10, 0, -6), ground=True)
c1_hit = P(b=(8, -14, 0), h=(0, 12, 0), w=(10, 0, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.1, u=0.05), edge=LEFT),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.7)),
           rL=(24, 0, 8), lL=(-34, 0, -8), root_pos=(0, 0, -1.2), ground=True)
c1_follow = P(c1_hit, b=(10, -48, 0), h=(0, 36, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.2, u=-0.15), arm=dirv(r=-0.85, f=0.5, u=-0.3)))

c2_wind = P(b=(12, -34, 0), h=(0, 26, 0), w=(12, 0, 0),
            rA=wield(blade=dirv(r=-0.75, u=-0.55, f=0.35), arm=dirv(f=1.0, u=-0.6, r=-0.25)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.5)),
            rL=(-24, 0, 8), lL=(16, 0, -8), ground=True)
c2_hit = P(b=(-8, 24, 0), h=(0, -20, 0),
           rA=wield(blade=dirv(r=0.55, u=0.75, f=0.4), arm=dirv(r=0.65, u=0.25, f=0.7)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-28, 0, 8), lL=(20, 0, -8), root_pos=(0, 0.5, -1.0), ground=True)
c2_follow = P(c2_hit, b=(-12, 38, 0), h=(-8, -28, 0),
              rA=wield(blade=dirv(r=0.45, u=0.85, f=-0.25), arm=dirv(r=0.85, u=0.5, f=0.15)))

c3_up = P(b=(-16, 0, 0), h=(-18, 0, 0),
          rA=wield(blade=dirv(u=0.5, f=-0.85, r=0.1), arm=dirv(u=1.0, f=0.15, r=0.3)),
          lA=aim(dirv(u=1.0, f=0.3, r=-0.2)),
          rL=(-36, 0, 0), lL=(-12, 0, 0), root_pos=(0, 2.2, 0))
c3_over = P(c3_up, rA=wield(blade=dirv(u=0.85, f=0.45, r=0.15), arm=dirv(u=0.9, f=0.45, r=0.45)),
            b=(-6, 0, 0), root_pos=(0, 1.8, 0))
c3_hit = P(w=(32, 0, 0), h=(-26, 0, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.95), arm=dirv(f=1.0, u=-0.7)),
           lA=aim(dirv(f=0.7, u=-1.0, r=0.2)),
           rL=(-48, 0, 8), lL=(42, 0, -8), ground=True)

# ---- 惑星技: 赤砂嵐（溜めて吼える） -----------------------------------------
sc_gather = P(w=(18, 0, 0), h=(8, 0, 0),
              rA=wield(blade=dirv(u=1.0, f=0.25, r=-0.35), arm=dirv(f=1.0, u=-0.35, r=-0.45)),
              lA=aim(dirv(f=1.0, u=-0.2, r=0.55), twist=30),
              rL=(-22, 0, 12), lL=(18, 0, -12), ground=True)
sc_roar = P(b=(-14, 0, 0), h=(-26, 0, 0),
            rA=wield(blade=dirv(u=0.85, r=0.55, f=0.1), arm=dirv(r=1.0, u=0.35, f=0.2)),
            lA=aim(dirv(r=-1.0, u=0.35, f=0.2)),
            rL=(0, 0, 15), lL=(0, 0, -15), ground=True)

# ---- 機動技: ウォーパス（肩から突っ込んで打ち上げる） -----------------------
wp_ram = P(w=(28, 0, 0), b=(8, 36, 0), h=(-24, -30, 0),
           lA=aim(dirv(f=0.7, u=-0.55, r=0.35), twist=-30),
           rA=wield(blade=dirv(f=-0.55, u=0.35, r=0.6), arm=dirv(f=-0.45, u=-1.0, r=0.35)),
           rL=(-34, 0, 4), lL=(32, 0, -4))
wp_ram2 = P(wp_ram, rL=(28, 0, 4), lL=(-34, 0, -4))
wp_launch = P(b=(-14, -12, 0), h=(-20, 8, 0),
              rA=wield(blade=dirv(u=1.0, f=0.35, r=0.1), arm=dirv(f=0.8, u=0.6, r=0.25)),
              lA=aim(dirv(f=-0.3, u=-1.0, r=-0.5)),
              rL=(-30, 0, 6), lL=(26, 0, -6), root_pos=(0, 0.6, -0.8), ground=True)

# ---- 空中技: オリンポス・インパクト ------------------------------------------
od_raise = P(b=(-14, 0, 0), h=(-10, 0, 0),
             rA=wield(blade=dirv(u=0.45, f=-0.9, r=0.1), arm=dirv(u=1.0, f=0.1, r=0.3)),
             lA=aim(dirv(u=1.0, f=0.25, r=-0.25)),
             rL=(-44, 0, 6), lL=(-18, 0, -6))
od_fall = P(od_raise, b=(-6, 0, 0), h=(12, 0, 0), rL=(-36, 0, 6), lL=(-10, 0, -6),
            rA=wield(blade=dirv(u=0.8, f=-0.55, r=0.15), arm=dirv(u=1.0, f=0.3, r=0.3)))
ol_slam = P(w=(34, 0, 0), h=(-34, 0, 0), b=(4, 0, 0),
            rA=wield(blade=dirv(f=0.55, u=-1.0, r=0.05), arm=dirv(f=1.0, u=-0.85)),
            lA=aim(dirv(f=0.5, u=-1.0, r=-0.25)),
            rL=(62, 0, 8), lL=(-58, 0, -8), ground=True)

# ---- 必殺: 衛星を呼ぶ・雄叫び ---------------------------------------------
mc_call = P(b=(-12, 0, 0), h=(-36, 0, 0),
            lA=aim(dirv(u=1.0, f=0.2, r=0.15)),
            rA=wield(blade=dirv(r=0.8, u=-0.45, f=0.35), arm=dirv(r=0.75, u=-0.65)),
            rL=(-6, 0, 10), lL=(6, 0, -10), ground=True)
mc_point = P(b=(8, 0, 0), h=(-4, 0, 0), w=(8, 0, 0),
             lA=aim(dirv(f=1.0, u=0.05, r=-0.05)),
             rA=wield(blade=dirv(u=0.9, f=0.25, r=0.35), arm=dirv(r=0.9, u=0.45, f=0.25)),
             rL=(-20, 0, 8), lL=(18, 0, -8), ground=True)
wr_roar = P(b=(-18, 0, 0), h=(-40, 0, 0),
            rA=wield(blade=dirv(u=1.0, r=0.4, f=0.1), arm=dirv(r=1.0, u=0.6, f=0.1)),
            lA=aim(dirv(r=-1.0, u=0.6, f=0.1)),
            rL=(-4, 0, 16), lL=(4, 0, -16), ground=True)

# ---- 共通の「投げる」を斧で（腕を右上へ逃がして、斧頭が兜に当たらないように） -----
th_wind = P(rA=wield(blade=dirv(u=0.55, f=-0.75, r=0.45), arm=dirv(u=0.75, f=-0.15, r=0.75)),
            lA=aim(dirv(f=1.0, u=0.15, r=-0.1)), b=(-6, 30, 0), h=(0, -24, 0), rL=(14, 0, 4),
            lL=(-20, 0, -4))
th_rel = P(rA=wield(blade=dirv(f=1.0, u=-0.1, r=0.1), arm=dirv(f=0.9, u=-0.1, r=0.4)),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.4)), b=(14, -22, 0), h=(-8, 20, 0),
           rL=(16, 0, 4), lL=(-30, 0, -4), root_pos=(0, -0.6, -1.0))

BODY_ANIMS = {
    "combo1": anim(0.55, {0.0: H, 0.05: c1_lift, 0.1: c1_wind, 0.21: c1_hit, 0.3: c1_follow,
                          0.4: P(c1_follow, b=(8, -44, 0)), 0.55: H}),
    "combo2": anim(0.55, {0.0: H, 0.1: c2_wind, 0.23: c2_hit, 0.33: c2_follow,
                          0.42: P(c2_follow, b=(-10, 34, 0)), 0.55: H}),
    "combo3": anim(0.8, {0.0: H, 0.18: c3_up, 0.27: c3_over, 0.34: c3_hit,
                         0.6: P(c3_hit, w=(30, 0, 0)), 0.8: H}),
    "storm_call": anim(0.95, {0.0: H, 0.14: sc_gather, 0.3: sc_roar,
                              0.72: P(sc_roar, b=(-16, 0, 0), h=(-30, 0, 0)), 0.95: H}),
    "warpath": anim(1.0, {0.0: H, 0.08: wp_ram, 0.28: wp_ram2, 0.48: wp_ram, 0.62: wp_ram2,
                          0.72: wp_launch, 0.86: P(wp_launch, b=(-16, -14, 0)), 1.0: H}),
    "olympus_dive": anim(1.4, {0.0: H, 0.12: od_raise, 0.4: od_fall, 1.3: od_fall, 1.4: H}),
    "olympus_land": anim(0.95, {0.0: P(ol_slam, w=(16, 0, 0), rL=(30, 0, 8), lL=(-30, 0, -8)),
                                0.06: ol_slam, 0.6: P(ol_slam, w=(30, 0, 0), h=(-30, 0, 0)), 0.95: H}),
    "moon_call": anim(1.5, {0.0: H, 0.25: mc_call, 0.8: P(mc_call, h=(-40, 0, 0)), 1.0: mc_point,
                            1.32: P(mc_point, b=(10, 0, 0)), 1.5: H}),
    "throw": anim(0.55, {0.0: H, 0.14: th_wind, 0.26: th_rel, 0.38: P(th_rel, b=(14, -20, 0)), 0.55: H}),
    "war_roar": anim(1.0, {0.0: H, 0.12: P(wr_roar, b=(10, 0, 0), h=(6, 0, 0)), 0.3: wr_roar,
                           0.78: P(wr_roar, h=(-44, 0, 0)), 1.0: H}),
}

