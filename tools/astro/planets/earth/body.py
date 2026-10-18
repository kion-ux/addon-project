# -*- coding: utf-8 -*-
"""地球（ガイア）の全身モーション。書き方は astro_animlib の冒頭と planets/_template/README_weapon.md。

名前はそのまま `animation.astro.p.earth.<名前>` になり、スクリプトは body(p, "combo1") のように呼ぶ。
武器（蒼星剣、kind sword）の向きは wield(blade=刃先の向き, edge=刃の向く側 / arm=腕の向き) で書く。
向きは体の空間: dirv(f=前, u=上, r=右)。

  combo1       右から左への横薙ぎ（刃を進む向きへ）
  combo2       左下から右上への逆袈裟
  combo3       跳び上がって真上からの兜割り（三段目: オーロラ斬）
  tidal_slash  惑星技 潮汐斬: 深く溜めて大きな三日月を描く薙ぎ払い
  charge       機動技 磁気圏突撃: 左腕を盾のように前へ、剣を低く引いて突っ込む
  luna_call    空中技 ルナ・フォール: 左手を天へ掲げて月を呼び、狙った所へ振り下ろす
  plant_sword  必殺技 ガイア・レゾナンス: 剣を天へ掲げ、片膝をついて大地に突き立てる
"""
from __future__ import annotations

from astro_animlib import DOWN, LEFT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(0, 38, 0), h=(0, -28, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.3, u=0.12), arm=dirv(r=1.0, u=-0.25, f=0.1)),
            lA=aim(dirv(f=1.0, r=-0.35, u=-0.15)),
            rL=(12, 0, 6), lL=(-16, 0, -6), ground=True)
c1_hit = P(b=(6, -12, 0), h=(0, 10, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.1), edge=LEFT),
           lA=aim(dirv(f=-0.35, u=-1.0, r=-0.6)),
           rL=(22, 0, 6), lL=(-30, 0, -6), root_pos=(0, 0, -1.0), ground=True)
c1_follow = P(c1_hit, b=(8, -42, 0), h=(0, 32, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.25, u=-0.12), edge=dirv(f=-0.5, r=-0.6)))

c2_wind = P(b=(10, -30, 0), h=(0, 24, 0),
            rA=wield(blade=dirv(r=-0.7, u=-0.6, f=0.45), arm=dirv(f=1.0, u=-0.5, r=-0.2)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)),
            rL=(-22, 0, 6), lL=(14, 0, -6), ground=True)
c2_hit = P(b=(-6, 22, 0), h=(0, -18, 0),
           rA=wield(blade=dirv(r=0.55, u=0.75, f=0.45), edge=dirv(u=0.5, r=0.6, f=-0.3)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-26, 0, 6), lL=(18, 0, -6), root_pos=(0, 0.4, -0.8), ground=True)
c2_follow = P(c2_hit, b=(-10, 34, 0), h=(-6, -26, 0),
              rA=wield(blade=dirv(r=0.5, u=0.85, f=-0.3), edge=dirv(u=0.3, r=0.6, f=-0.7)))

c3_up = P(b=(-14, 0, 0), h=(-16, 0, 0),
          rA=wield(blade=dirv(u=0.55, f=-0.85), arm=dirv(u=1.0, f=0.15, r=0.25)),
          lA=aim(dirv(u=0.55, f=1.0, r=-0.25)),
          rL=(-34, 0, 0), lL=(-10, 0, 0), root_pos=(0, 1.8, 0))
c3_hit = P(w=(28, 0, 0), h=(-24, 0, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.6), edge=DOWN),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
           rL=(30, 0, 8), lL=(-44, 0, -8), root_pos=(0, 0, -2.0), ground=True)

# ---- 技 --------------------------------------------------------------------
ts_wind = P(b=(6, 56, 0), w=(10, 0, 0), h=(0, -42, 0),
            rA=wield(blade=dirv(r=0.8, f=-0.6, u=0.15), arm=dirv(r=1.0, u=-0.15, f=-0.1)),
            lA=aim(dirv(f=1.0, u=0.2, r=-0.25)),
            rL=(10, 0, 16), lL=(-22, 0, -14), ground=True)
ts_mid = P(ts_wind, b=(4, 2, 0), h=(0, -2, 0),
           rA=wield(blade=dirv(f=1.0, u=0.05, r=0.05), edge=LEFT),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.6)))
ts_follow = P(ts_wind, b=(6, -62, 0), h=(0, 46, 0),
              rA=wield(blade=dirv(r=-1.0, f=-0.3, u=0.05), edge=dirv(f=-1.0, r=-0.3)),
              lA=aim(dirv(r=0.6, f=-0.6, u=-0.7)))

charge = P(w=(26, 0, 0), h=(-28, 0, 0),
           lA=aim(dirv(f=1.0, u=0.15, r=-0.05), twist=40),
           rA=wield(blade=dirv(f=-0.6, u=-0.45, r=0.45), arm=dirv(f=-0.3, u=-1.0, r=0.35)),
           rL=(-34, 0, 2), lL=(30, 0, -2))

luna_up = P(b=(-8, 0, 0), h=(-30, 0, 0),
            lA=aim(dirv(u=1.0, f=0.25, r=0.15)),
            rA=wield(blade=dirv(r=0.8, u=-0.6, f=0.25), arm=dirv(r=0.8, u=-0.6)),
            rL=(-6, 0, 8), lL=(6, 0, -8), ground=True)
luna_down = P(luna_up, b=(12, 0, 0), h=(8, 0, 0),
              lA=aim(dirv(f=1.0, u=-0.3, r=-0.05)))

ps_raise = P(b=(-10, 0, 0), h=(-26, 0, 0),
             rA=wield(blade=dirv(u=1.0, f=-0.25), arm=dirv(u=1.0, f=0.35, r=0.2)),
             lA=aim(dirv(u=0.3, f=1.0, r=-0.3)), root_pos=(0, 0.8, 0))
ps_plant = P(w=(24, 0, 0), h=(-16, 0, 0),
             rA=wield(blade=dirv(f=0.12, u=-1.0), arm=dirv(f=1.0, u=-0.85)),
             lA=aim(dirv(f=0.35, u=-1.0, r=0.25)),
             rL=(58, 0, 6), lL=(-52, 0, -6), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.07: c1_wind, 0.17: c1_hit, 0.26: c1_follow,
                         0.36: P(c1_follow, b=(6, -38, 0)), 0.5: H}),
    "combo2": anim(0.5, {0.0: H, 0.08: c2_wind, 0.2: c2_hit, 0.3: c2_follow,
                         0.38: P(c2_follow, b=(-8, 30, 0)), 0.5: H}),
    "combo3": anim(0.7, {0.0: H, 0.16: c3_up, 0.3: c3_hit, 0.5: P(c3_hit, w=(26, 0, 0)), 0.7: H}),
    "tidal_slash": anim(0.85, {0.0: H, 0.12: ts_wind, 0.3: ts_mid, 0.42: ts_follow,
                               0.66: P(ts_follow, b=(6, -58, 0)), 0.85: H}),
    "charge": anim(0.9, {0.0: H, 0.1: charge, 0.45: P(charge, rL=(-30, 0, 2), lL=(26, 0, -2)),
                         0.75: charge, 0.9: H}),
    "luna_call": anim(0.9, {0.0: H, 0.16: luna_up, 0.45: P(luna_up, h=(-34, 0, 0)), 0.6: luna_down,
                            0.75: P(luna_down, b=(10, 0, 0)), 0.9: H}),
    "plant_sword": anim(1.4, {0.0: H, 0.28: ps_raise, 0.52: ps_plant, 1.15: P(ps_plant, w=(22, 0, 0)),
                              1.4: H}),
}
