# -*- coding: utf-8 -*-
"""土星（クロノス）の全身モーション。書き方は astro_animlib の冒頭と planets/_template/README_weapon.md。

名前はそのまま `animation.astro.p.saturn.<名前>` になり、スクリプトは body(p, "saturn.<名前>") で呼ぶ。
武器（環刃 クロノス・リング、kind ring）は wield(blade=握りから環の中心への向き, edge=環の下側(-Y)の向き)。
環の面は blade と edge を含む面なので、**水平に薙ぐ時は edge を水平（LEFT / RIGHT）** にすると環が寝る。
向きは体の空間: dirv(f=前, u=上, r=右)。

  combo1       右から左への水平の薙ぎ（環を寝かせて前を払う）
  combo2       左下から右上への逆袈裟（環を立てて斬り上げる）
  combo3       環断: 腕を伸ばして環を水平に広げ、全身で一回転して周りを一周薙ぐ
  ring_throw   惑星技 リング・ソー: 体を右へひねって環を背に回し、円盤投げのように前へ放つ（0.3 秒で放す）
  ring_slide   機動技 リング・スライド: 環に乗って低く滑る構え（左足前・腕で釣り合い）→ 最後に横へ払う
  hex_cast     空中技 六角極渦: 環を頭上に水平に掲げて嵐を呼び、狙った地点へ振り下ろす（0.5 秒）
  horizon      必殺 クロノス・ホライズン: 環を天に掲げて時計の陣（〜1.5 秒）→ 右へ大きく溜め →
               2.2 秒で全身を使った水平の大一閃 → 残心
"""
from __future__ import annotations

from astro_animlib import LEFT, RIGHT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
# 1: 右から左へ、環を寝かせた水平の薙ぎ
c1_wind = P(b=(2, 40, 0), h=(0, -30, 0),
            rA=wield(blade=dirv(r=1.0, f=0.1, u=0.1), arm=dirv(r=0.8, u=-0.5, f=-0.2)),
            lA=aim(dirv(f=1.0, r=-0.4, u=-0.1)),
            rL=(14, 0, 6), lL=(-18, 0, -6), ground=True)
c1_hit = P(b=(6, -14, 0), h=(0, 12, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.15, u=-0.05), edge=LEFT),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.6)),
           rL=(24, 0, 6), lL=(-30, 0, -6), root_pos=(0, 0, -1.0), ground=True)
c1_follow = P(c1_hit, b=(8, -44, 0), h=(0, 34, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.35, u=-0.05), arm=dirv(r=-0.5, f=0.7, u=-0.5)))

# 2: 左下から右上へ、環を立てて斬り上げる
c2_wind = P(b=(12, -32, 0), h=(0, 26, 0),
            rA=wield(blade=dirv(r=-0.75, u=-0.55, f=0.4), arm=dirv(f=1.0, u=-0.6, r=-0.1)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)),
            rL=(-22, 0, 6), lL=(16, 0, -6), ground=True)
c2_hit = P(b=(-6, 24, 0), h=(0, -18, 0),
           rA=wield(blade=dirv(r=0.55, u=0.75, f=0.5), arm=dirv(r=0.8, u=0.1, f=0.6)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-28, 0, 6), lL=(20, 0, -6), root_pos=(0, 0.4, -0.8), ground=True)
c2_follow = P(c2_hit, b=(-10, 36, 0), h=(-6, -26, 0),
              rA=wield(blade=dirv(r=0.6, u=0.8, f=-0.1), arm=dirv(r=0.9, u=0.4, f=0.1)))

# 3: 環断（腕を右へ伸ばし、環を水平に広げて全身で一回転）
c3_out = P(rA=wield(blade=dirv(r=1.0, f=0.45, u=-0.05), edge=dirv(f=1.0, r=-0.3)),
           lA=aim(dirv(r=-1.0, u=-0.35, f=-0.2)), b=(8, 0, 0), h=(4, 0, 0),
           rL=(-16, 0, 10), lL=(16, 0, -10), root_pos=(0, -0.8, 0))
c3_wind = P(c3_out, root=(0, 40, 0), b=(8, 18, 0), h=(0, -16, 0))

# ---- 惑星技: リング・ソー（円盤投げ） -----------------------------------------
rt_wind = P(b=(-4, 52, 0), w=(6, 0, 0), h=(0, -44, 0),
            rA=wield(blade=dirv(r=0.4, f=-0.9, u=0.05), arm=dirv(r=1.0, f=-0.3, u=-0.35)),
            lA=aim(dirv(f=1.0, u=0.25, r=-0.2)),
            rL=(14, 0, 8), lL=(-22, 0, -8), ground=True)
rt_release = P(b=(10, -26, 0), w=(10, 0, 0), h=(-4, 22, 0),
               rA=wield(blade=dirv(f=1.0, u=0.05, r=-0.1), arm=dirv(f=1.0, r=0.25, u=-0.15)),
               lA=aim(dirv(f=-0.4, u=-1.0, r=-0.6)),
               rL=(26, 0, 6), lL=(-36, 0, -6), root_pos=(0, 0, -1.2), ground=True)
rt_follow = P(rt_release, b=(14, -40, 0), h=(-6, 34, 0),
              rA=wield(blade=dirv(f=0.4, r=-0.9, u=-0.3), arm=dirv(f=0.6, r=-0.6, u=-0.6)))

# ---- 機動技: リング・スライド ---------------------------------------------------
slide = P(w=(18, 0, 0), b=(0, 24, 0), h=(-14, -22, 0),
          rA=wield(blade=dirv(f=0.6, r=0.7, u=-0.25), arm=dirv(r=1.0, u=-0.45, f=-0.3)),
          lA=aim(dirv(f=1.0, r=-0.55, u=0.1), twist=20),
          rL=(26, 0, 12), lL=(-34, 0, -8), ground=True)
slide2 = P(slide, b=(0, 30, 0), w=(22, 0, 0), rL=(30, 0, 12), lL=(-38, 0, -8))
slide_cut = P(w=(10, 0, 0), b=(4, -36, 0), h=(0, 28, 0),
              rA=wield(blade=dirv(f=0.4, r=-1.0), edge=dirv(f=1.0, r=0.2)),
              lA=aim(dirv(r=1.0, u=-0.5, f=-0.3)),
              rL=(18, 0, 8), lL=(-22, 0, -8), ground=True)

# ---- 空中技: 六角極渦 ------------------------------------------------------------
hx_up = P(b=(-10, 0, 0), h=(-34, 0, 0),
          rA=wield(blade=dirv(u=0.15, f=0.3, r=-1.0), arm=dirv(u=1.0, f=0.2, r=0.35)),
          lA=aim(dirv(u=0.9, f=0.4, r=-0.3)),
          rL=(-24, 0, 6), lL=(10, 0, -6))
hx_down = P(b=(16, 0, 0), h=(10, 0, 0),
            rA=wield(blade=dirv(f=1.0, u=-0.85, r=0.1), arm=dirv(f=1.0, u=-0.5, r=0.3)),
            lA=aim(dirv(f=1.0, u=-0.6, r=-0.2), twist=30),
            rL=(-30, 0, 8), lL=(18, 0, -8))

# ---- 必殺: クロノス・ホライズン ---------------------------------------------------
hz_raise = P(b=(-12, 0, 0), h=(-30, 0, 0),
             rA=wield(blade=dirv(u=0.2, f=0.2, r=-1.0), arm=dirv(u=1.0, f=0.25, r=0.35)),
             lA=aim(dirv(f=0.7, u=-0.3, r=-0.6), twist=20),
             rL=(-6, 0, 10), lL=(6, 0, -10), ground=True)
hz_hold = P(hz_raise, b=(-14, 0, 0), h=(-34, 0, 0),
            lA=aim(dirv(f=1.0, u=0.1, r=-0.3), twist=40))
hz_wind = P(b=(4, 64, 0), w=(10, 0, 0), h=(0, -52, 0),
            rA=wield(blade=dirv(r=0.6, f=-0.8, u=0.0), arm=dirv(r=1.0, f=-0.2, u=-0.3)),
            lA=aim(dirv(f=1.0, r=-0.5, u=0.05)),
            rL=(16, 0, 14), lL=(-30, 0, -12), ground=True)
hz_slash = P(b=(6, -30, 0), w=(12, 0, 0), h=(0, 26, 0),
             rA=wield(blade=dirv(f=1.0, r=-0.2, u=0.0), edge=LEFT),
             lA=aim(dirv(f=-0.4, u=-1.0, r=-0.6)),
             rL=(30, 0, 12), lL=(-40, 0, -12), root_pos=(0, 0, -1.4), ground=True)
hz_follow = P(hz_slash, b=(8, -70, 0), h=(0, 54, 0),
              rA=wield(blade=dirv(r=-1.0, f=-0.25, u=0.05), arm=dirv(r=-0.6, f=0.6, u=-0.4)),
              lA=aim(dirv(r=1.0, u=-0.6, f=-0.4)))
hz_zanshin = P(w=(16, 0, 0), b=(4, -40, 0), h=(-6, 30, 0),
               rA=wield(blade=dirv(r=-0.6, u=-0.6, f=0.3), arm=dirv(r=-0.2, f=0.4, u=-1.0)),
               lA=aim(dirv(r=0.6, u=-1.0, f=0.0)),
               rL=(24, 0, 10), lL=(-30, 0, -10), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.07: c1_wind, 0.17: c1_hit, 0.27: c1_follow,
                         0.38: P(c1_follow, b=(6, -40, 0)), 0.5: H}),
    "combo2": anim(0.5, {0.0: H, 0.08: c2_wind, 0.2: c2_hit, 0.3: c2_follow,
                         0.38: P(c2_follow, b=(-8, 32, 0)), 0.5: H}),
    "combo3": anim(0.65, {0.0: H, 0.08: c3_wind,
                          0.18: P(c3_out, root=(0, -60, 0)), 0.28: P(c3_out, root=(0, -170, 0)),
                          0.38: P(c3_out, root=(0, -280, 0)), 0.48: P(c3_out, root=(0, -360, 0)),
                          0.65: P(root=(0, -360, 0))}, blend=False),
    "ring_throw": anim(0.8, {0.0: H, 0.16: rt_wind, 0.3: rt_release, 0.42: rt_follow,
                             0.6: P(rt_follow, b=(10, -34, 0)), 0.8: H}),
    "ring_slide": anim(0.95, {0.0: H, 0.08: slide, 0.4: slide2, 0.62: slide,
                              0.72: slide_cut, 0.84: P(slide_cut, b=(4, -44, 0)), 0.95: H}),
    "hex_cast": anim(1.0, {0.0: H, 0.14: hx_up, 0.42: P(hx_up, h=(-38, 0, 0)), 0.52: hx_down,
                           0.75: P(hx_down, b=(14, 0, 0)), 1.0: H}),
    "horizon": anim(3.4, {0.0: H, 0.3: hz_raise, 1.3: hz_hold, 1.75: hz_wind,
                          2.05: P(hz_wind, b=(4, 70, 0)), 2.2: hz_slash, 2.34: hz_follow,
                          2.7: hz_zanshin, 3.15: P(hz_zanshin, b=(2, -34, 0)), 3.4: H}),
}
