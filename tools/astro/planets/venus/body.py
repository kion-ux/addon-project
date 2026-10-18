# -*- coding: utf-8 -*-
"""金星（モーニングスター）の全身モーション。書き方は astro_animlib の冒頭と planets/_template/README_weapon.md。

名前はそのまま `animation.astro.p.venus.<名前>` になり、スクリプトは body(p, "venus.combo1") のように呼ぶ。
武器は明星杖（kind scepter: 頭が -Z、手首の角度 110°）。wield(blade=星の頭の向き, arm=腕の向き) で書く。
向きは体の空間: dirv(f=前, u=上, r=右)。

  combo1       右後ろから左前へ、星の頭で弧を描く薙ぎ
  combo2       左下から右上へすくい上げ、頭上で星を返す
  combo3       星屑の花: 杖を高く掲げて爪先で一回転（ピルエット）し、前へ星を差し出す
  acid_cast    惑星技 アシッド・ヴェール: 杖を右肩の後ろへ引き、硫酸雲の弾を前へ放つ
  retrograde   機動技 レトログレード: 前傾して逆回り（時計回り）に二回転し、最後に杖で後ろへ投げ払う
  dive         空中技 グリーンハウス（前半）: 両手で杖を頭上へ → 星の頭を真下へ向けて急降下
  dome         空中技 グリーンハウス（着地）: 片膝をつき、杖を地に立てて左手を広げる（熱の天蓋）
  star_call    必殺 モーニングスター（溜め）: 両腕で杖を天へ掲げ、空を仰いで明星を呼ぶ
  star_fall    必殺（星光の柱）: 掲げた杖を前へ振り下ろし、柱を落とす所を指す
  rain         必殺（締め）: 両腕を大きく広げ、硫酸の雨を降らせる祝福の構え
"""
from __future__ import annotations

from astro_animlib import H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(0, 34, 0), h=(0, -26, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.25, u=0.35), arm=dirv(r=1.0, u=-0.35, f=0.1)),
            lA=aim(dirv(f=1.0, r=-0.4, u=-0.1)),
            rL=(10, 0, 6), lL=(-14, 0, -6), ground=True)
c1_hit = P(b=(6, -10, 0), h=(0, 8, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.15, u=0.2), arm=dirv(f=0.85, u=-0.3, r=0.15)),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.6)),
           rL=(20, 0, 6), lL=(-28, 0, -6), root_pos=(0, 0, -0.9), ground=True)
c1_follow = P(c1_hit, b=(8, -38, 0), h=(0, 28, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.35, u=0.25), arm=dirv(r=-0.75, f=0.6, u=-0.3)))

c2_wind = P(b=(10, -28, 0), h=(0, 22, 0),
            rA=wield(blade=dirv(r=-0.6, u=-0.55, f=0.55), arm=dirv(f=0.9, u=-0.6, r=-0.2)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)),
            rL=(-20, 0, 6), lL=(12, 0, -6), ground=True)
c2_hit = P(b=(-6, 20, 0), h=(-6, -16, 0),
           rA=wield(blade=dirv(r=0.45, u=0.85, f=0.3), arm=dirv(r=0.6, u=0.35, f=0.7)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-24, 0, 6), lL=(16, 0, -6), root_pos=(0, 0.4, -0.7), ground=True)
c2_follow = P(c2_hit, b=(-10, 30, 0), h=(-10, -24, 0),
              rA=wield(blade=dirv(u=1.0, r=0.2, f=-0.3), arm=dirv(r=0.7, u=0.6, f=0.2)))

# 星屑の花: 掲げて（0.12）→ 爪先立ちで一回転（0.14〜0.5、腕を外へ伸ばして星で円を描く）→ 前へ差し出す
c3_raise = P(b=(-8, 0, 0), h=(-18, 0, 0),
             rA=wield(blade=dirv(u=1.0, f=0.15, r=0.1), arm=dirv(u=1.0, f=0.3, r=0.35)),
             lA=aim(dirv(r=-1.0, u=0.25, f=0.2)),
             rL=(-8, 0, 4), lL=(6, 0, -4), root_pos=(0, 0.8, 0))
c3_out = P(rA=wield(blade=dirv(r=1.0, u=0.3, f=0.1), arm=dirv(r=1.0, u=0.1, f=0.15)),
           lA=aim(dirv(r=-1.0, u=0.3, f=0.1)), b=(-4, 0, 0), h=(-8, 0, 0),
           rL=(-4, 0, 6), lL=(30, 0, -4), root_pos=(0, 0.9, 0))
c3_offer = P(b=(10, -6, 0), h=(4, 0, 0),
             rA=wield(blade=dirv(f=1.0, u=0.15), arm=dirv(f=1.0, u=-0.1, r=0.1)),
             lA=aim(dirv(r=-1.0, u=-0.2, f=0.4)),
             rL=(22, 0, 6), lL=(-30, 0, -6), root_pos=(0, 0, -0.8), ground=True)

# ---- 惑星技 アシッド・ヴェール ----------------------------------------------
ac_wind = P(b=(-6, 30, 0), h=(0, -24, 0),
            rA=wield(blade=dirv(u=0.75, f=-0.55, r=0.35), arm=dirv(u=1.0, f=-0.15, r=0.45)),
            lA=aim(dirv(f=1.0, u=0.25, r=-0.15)),
            rL=(12, 0, 6), lL=(-16, 0, -6), ground=True)
ac_cast = P(b=(12, -18, 0), h=(-8, 16, 0),
            rA=wield(blade=dirv(f=1.0, u=0.2), arm=dirv(f=1.0, u=0.1, r=-0.05)),
            lA=aim(dirv(f=-0.3, u=-1.0, r=-0.45)),
            rL=(26, 0, 4), lL=(-36, 0, -4), root_pos=(0, 0, -1.2), ground=True)

# ---- 機動技 レトログレード（逆回り = 時計回りに二回転） ------------------------
rg_pose = P(w=(16, 0, 0), h=(-14, 0, 0),
            rA=wield(blade=dirv(r=1.0, f=0.15, u=0.1), arm=dirv(r=1.0, f=0.1, u=-0.1)),
            lA=aim(dirv(r=-1.0, u=-0.3, f=0.1)),
            rL=(-12, 0, 8), lL=(16, 0, -8))
rg_throw = P(w=(10, 0, 0), b=(0, 30, 0), h=(-6, -24, 0),
             rA=wield(blade=dirv(f=-0.8, u=0.2, r=0.45), arm=dirv(f=-0.55, u=-0.6, r=0.55)),
             lA=aim(dirv(f=1.0, u=0.1, r=-0.3)),
             rL=(16, 0, 6), lL=(-20, 0, -6), ground=True)


def _retro():
    fr = {0.0: H, 0.06: P(rg_pose, root=(0, 30, 0))}
    n = 8
    for i in range(1, n + 1):
        t = 0.06 + i * 0.07
        fr[round(t, 3)] = P(rg_pose, root=(0, 30 + i * 86.25, 0))      # 0.62 秒で 720°
    fr[0.7] = P(rg_throw, root=(0, 720, 0))
    fr[0.82] = P(rg_throw, root=(0, 720, 0), b=(0, 36, 0))
    fr[0.95] = P(root=(0, 720, 0))
    return fr


# ---- 空中技 グリーンハウス -----------------------------------------------------
dv_up = P(b=(-10, 0, 0), h=(-16, 0, 0),
          rA=wield(blade=dirv(u=1.0, f=0.15), arm=dirv(u=1.0, f=0.3, r=0.3)),
          lA=aim(dirv(u=1.0, f=0.3, r=-0.15)),
          rL=(-50, 0, 4), lL=(-22, 0, -4))
dv_down = P(w=(14, 0, 0), h=(14, 0, 0),
            rA=wield(blade=dirv(u=-1.0, f=0.3), arm=dirv(f=0.75, u=-0.6, r=0.2)),
            lA=aim(dirv(f=0.7, u=-0.7, r=-0.2)),
            rL=(-6, 0, 3), lL=(8, 0, -3))
dm_kneel = P(w=(18, 0, 0), h=(-10, 0, 0),
             rA=wield(blade=dirv(u=1.0, f=0.1), arm=dirv(f=0.75, u=-0.45, r=0.35)),
             lA=aim(dirv(r=-1.0, u=0.45, f=0.35)),
             rL=(60, 0, 6), lL=(-56, 0, -6), ground=True)
dm_open = P(dm_kneel, w=(10, 0, 0), h=(-22, 0, 0),
            lA=aim(dirv(r=-1.0, u=0.75, f=0.1)))

# ---- 必殺 モーニングスター -------------------------------------------------------
sc_rise = P(b=(-12, 0, 0), h=(-34, 0, 0),
            rA=wield(blade=dirv(u=1.0, f=0.05), arm=dirv(u=1.0, f=0.2, r=0.3)),
            lA=aim(dirv(u=1.0, f=0.2, r=-0.35)),
            rL=(-4, 0, 9), lL=(4, 0, -9), ground=True)
sf_point = P(b=(14, -10, 0), h=(-4, 8, 0),
             rA=wield(blade=dirv(f=1.0, u=-0.25), arm=dirv(f=1.0, u=0.05, r=0.05)),
             lA=aim(dirv(f=-0.3, u=-1.0, r=-0.5)),
             rL=(24, 0, 6), lL=(-32, 0, -6), root_pos=(0, 0, -0.8), ground=True)
rn_bless = P(b=(-8, 0, 0), h=(-22, 0, 0),
             rA=wield(blade=dirv(u=0.85, r=0.45, f=0.1), arm=dirv(r=1.0, u=0.45, f=0.15)),
             lA=aim(dirv(r=-1.0, u=0.45, f=0.15)),
             rL=(-6, 0, 10), lL=(6, 0, -10), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.08: c1_wind, 0.18: c1_hit, 0.27: c1_follow,
                         0.37: P(c1_follow, b=(6, -34, 0)), 0.5: H}),
    "combo2": anim(0.5, {0.0: H, 0.08: c2_wind, 0.2: c2_hit, 0.3: c2_follow,
                         0.38: P(c2_follow, b=(-8, 26, 0)), 0.5: H}),
    "combo3": anim(0.75, {0.0: H, 0.12: c3_raise, 0.18: P(c3_out, root=(0, -20, 0)),
                          0.27: P(c3_out, root=(0, -130, 0)), 0.36: P(c3_out, root=(0, -240, 0)),
                          0.45: P(c3_out, root=(0, -330, 0)), 0.53: P(c3_offer, root=(0, -360, 0)),
                          0.66: P(c3_offer, root=(0, -360, 0), b=(8, -4, 0)),
                          0.75: P(root=(0, -360, 0))}),
    "acid_cast": anim(0.7, {0.0: H, 0.14: ac_wind, 0.26: ac_cast, 0.46: P(ac_cast, b=(10, -16, 0)),
                            0.7: H}),
    "retrograde": anim(0.95, _retro()),
    "dive": anim(1.2, {0.0: H, 0.14: dv_up, 0.3: dv_down, 1.0: P(dv_down, w=(18, 0, 0)), 1.2: H}),
    "dome": anim(0.9, {0.0: P(dm_kneel, w=(8, 0, 0), rL=(30, 0, 6), lL=(-30, 0, -6), ground=True),
                       0.06: dm_kneel, 0.3: dm_open, 0.66: P(dm_open, h=(-26, 0, 0)), 0.9: H}),
    "star_call": anim(1.6, {0.0: H, 0.28: sc_rise, 1.35: P(sc_rise, b=(-14, 0, 0), h=(-38, 0, 0)),
                            1.6: H}),
    "star_fall": anim(0.8, {0.0: P(sc_rise), 0.12: P(sc_rise, b=(-16, 0, 0)), 0.24: sf_point,
                            0.6: P(sf_point, b=(12, -8, 0)), 0.8: H}),
    "rain": anim(1.1, {0.0: H, 0.2: rn_bless, 0.85: P(rn_bless, h=(-26, 0, 0)), 1.1: H}),
}
