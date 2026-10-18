# -*- coding: utf-8 -*-
"""海王星（トリトン）の全身モーション。深淵三叉槍 トリトン（kind trident: 手首の角度 118°。
腕を下ろすと穂先は前上、腕を高く上げると穂先は前下 = 槍を頭上に構えた形）。

名前はそのまま `animation.astro.p.neptune.<名前>` になり、スクリプトは body(p, "neptune.<名前>")。
向きは体の空間: dirv(f=前, u=上, r=右)。wield(blade=穂先の向き, arm=腕の向き)。
槍の技は「腰だめの突き」と「頭上からの突き下ろし」と「柄で薙ぐ」の三つが芯。

  combo1        腰だめから踏み込んで一突き
  combo2        右から左へ柄ごと薙ぎ払う
  combo3        頭上に振りかぶり、跳び込んで突き下ろす（三段目: 波濤突き）
  sonic_thrust  惑星技 超音速の風: 体を大きくひねって溜め、左の掌で狙いを付け、爆発的に踏み込んで突く
  vortex_dive   機動技 大暗斑: 身を沈めて渦へ飛び込み（前へ倒れ込む）、抜けた先で槍を外へ伸ばして一回転
  retro_throw   空中技 トリトンの逆行: 宙で槍を頭上に振りかぶり、真下へ投げ下ろす
  tempest_stir  必殺 アビサル・テンペスト（前半）: 槍を立てて大きく構え、渦潮をかき回しながら一回転
  tidal_crash   必殺の締め: 跳び上がって槍を頭上に構え、大津波とともに大地へ突き立てて膝をつく
"""
from __future__ import annotations

from astro_animlib import H, P, aim, anim, dirv, flip, wield

# ---- 三段コンボ -------------------------------------------------------------
# 一段目: 腰だめの突き（穂先は前、腕は下で少し後ろ。踏み込みと腰のひねりで突く）
c1_wind = P(b=(0, 34, 0), w=(-4, 0, 0), h=(0, -28, 0),
            rA=wield(blade=dirv(f=1.0, u=0.2, r=0.15), arm=dirv(f=-0.6, u=-0.8, r=0.25)),
            lA=aim(dirv(f=1.0, u=0.1, r=-0.35)),
            rL=(14, 0, 6), lL=(-12, 0, -6), root_pos=(0, 0, 0.6), ground=True)
c1_hit = P(b=(4, -20, 0), w=(12, 0, 0), h=(-6, 16, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.04), arm=dirv(f=-0.3, u=-1.0, r=0.05)),
           lA=aim(dirv(f=-0.5, u=-1.0, r=-0.55)),
           rL=(26, 0, 6), lL=(-36, 0, -6), root_pos=(0, 0, -1.8), ground=True)
c1_follow = P(c1_hit, b=(4, -14, 0), w=(8, 0, 0))

# 二段目: 右から左への薙ぎ（柄ごと体を回す）
c2_wind = P(b=(4, 46, 0), w=(6, 0, 0), h=(0, -34, 0),
            rA=wield(blade=dirv(r=1.0, f=0.25, u=0.15), arm=dirv(r=-0.35, u=-0.85, f=0.35)),
            lA=aim(dirv(f=1.0, u=0.05, r=-0.5)),
            rL=(12, 0, 8), lL=(-16, 0, -8), ground=True)
c2_mid = P(b=(6, 4, 0), w=(10, 0, 0), h=(0, -4, 0),
           rA=wield(blade=dirv(f=1.0, u=0.1), arm=dirv(f=-0.45, u=-0.9, r=0.1)),
           lA=aim(dirv(f=0.2, u=-1.0, r=-0.5)),
           rL=(20, 0, 8), lL=(-26, 0, -8), root_pos=(0, 0, -1.0), ground=True)
c2_hit = P(c2_mid, b=(6, -44, 0), h=(0, 34, 0),
           rA=wield(blade=dirv(r=-1.0, f=0.4, u=0.05), arm=dirv(r=0.45, u=-0.85, f=0.2)),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.7)))

# 三段目: 頭上に振りかぶって跳び込み、突き下ろす（腕は上、穂先は前下）
c3_up = P(b=(-12, 22, 0), h=(-14, -16, 0),
          rA=wield(blade=dirv(f=1.0, u=0.35, r=0.1), arm=dirv(u=1.0, f=-0.45, r=0.35)),
          lA=aim(dirv(f=1.0, u=0.25, r=-0.25)),
          rL=(-36, 0, 2), lL=(-8, 0, -2), root_pos=(0, 1.8, 0.4))
c3_hit = P(w=(30, 0, 0), b=(4, -8, 0), h=(-26, 6, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.5), arm=dirv(u=0.85, f=0.25, r=0.35)),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
           rL=(30, 0, 8), lL=(-46, 0, -8), root_pos=(0, 0, -2.2), ground=True)

# ---- 惑星技 超音速の風（8 tick = 0.4 秒で放つ） -------------------------------------
st_coil = P(b=(6, 52, 0), w=(8, 0, 0), h=(0, -44, 0),
            rA=wield(blade=dirv(f=1.0, u=0.08), arm=dirv(f=-0.65, u=-0.55, r=0.55)),
            lA=aim(dirv(f=1.0, u=0.12, r=-0.1), twist=50),
            rL=(20, 0, 10), lL=(-22, 0, -10), root_pos=(0, -0.8, 1.0), ground=True)
st_lunge = P(b=(6, -26, 0), w=(20, 0, 0), h=(-14, 24, 0),
             rA=wield(blade=dirv(f=1.0, u=-0.02), arm=dirv(f=-0.25, u=-1.0, r=0.0)),
             lA=aim(dirv(f=-0.75, u=-0.55, r=-0.6)),
             rL=(36, 0, 6), lL=(-52, 0, -6), root_pos=(0, 0, -2.6), ground=True)

# ---- 機動技 大暗斑（6 tick で渦へ消え、抜けた先で一回転） -----------------------------
vd_crouch = P(w=(36, 0, 0), h=(-30, 0, 0),
              rA=wield(blade=dirv(f=1.0, u=-0.15), arm=dirv(f=-0.4, u=-1.0, r=0.1)),
              lA=aim(dirv(f=1.0, u=-0.35, r=-0.2)),
              rL=(-34, 0, 4), lL=(30, 0, -4), ground=True)
vd_dive = P(vd_crouch, root=(62, 0, 0), w=(20, 0, 0), h=(-40, 0, 0),
            lA=aim(dirv(f=1.0, u=0.1, r=-0.1)),
            rL=(10, 0, 4), lL=(16, 0, -4), root_pos=(0, -2.5, -3.0))
vd_out = P(rA=wield(blade=dirv(r=1.0, f=0.35, u=0.05), arm=dirv(r=-0.3, u=-0.9, f=0.3)),
           lA=aim(dirv(r=-1.0, u=-0.3, f=-0.1)), b=(6, 0, 0), rL=(-14, 0, 9), lL=(14, 0, -9),
           ground=True)
vd_frames = {0.0: H, 0.1: vd_crouch, 0.24: vd_dive}
vd_frames.update(flip(0.34, 0.72, 1.0, "y", steps=6, tuck=False, base=vd_out))
vd_frames[0.86] = H

# ---- 空中技 トリトンの逆行（8 tick = 0.4 秒で投げ下ろす） -----------------------------
rt_cock = P(b=(-16, 24, 0), h=(-22, -12, 0),
            rA=wield(blade=dirv(f=0.8, u=0.45, r=0.1), arm=dirv(u=1.0, f=-0.5, r=0.4)),
            lA=aim(dirv(f=1.0, u=-0.55, r=-0.15)),
            rL=(-22, 0, 4), lL=(12, 0, -4))
rt_throw = P(w=(34, 0, 0), b=(8, -12, 0), h=(4, 6, 0),
             rA=wield(blade=dirv(f=0.35, u=-1.0), arm=dirv(f=0.9, u=0.35, r=0.15)),
             lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
             rL=(-44, 0, 6), lL=(-12, 0, -4))

# ---- 必殺 アビサル・テンペスト ------------------------------------------------------
# 前半: 槍を立てて構え（腕を下ろすと穂先は上）、渦潮をかき回しながら一回転
ts_stance = P(rA=wield(blade=dirv(u=1.0, f=0.15, r=0.35), arm=dirv(r=0.7, u=-0.7, f=0.1)),
              lA=aim(dirv(f=0.6, u=0.55, r=-0.7), twist=30), b=(-8, 0, 0), h=(-20, 0, 0),
              rL=(-6, 0, 14), lL=(6, 0, -14), ground=True)
ts_frames = {0.0: H, 0.25: ts_stance, 0.5: P(ts_stance, h=(-28, 0, 0), b=(-10, 0, 0))}
ts_frames.update(flip(0.6, 1.4, 1.0, "y", steps=8, tuck=False,
                      base=P(ts_stance, rA=wield(blade=dirv(u=0.85, r=0.6), arm=dirv(r=0.9, u=-0.45)),
                             lA=aim(dirv(r=-1.0, u=0.2, f=0.1)))))
ts_frames[1.6] = P(ts_stance, root=(0, 360, 0))

# 締め: 跳び上がって頭上に構え、大地へ突き立てて膝をつく
tc_up = P(b=(-14, 0, 0), h=(-28, 0, 0),
          rA=wield(blade=dirv(f=1.0, u=0.2, r=0.15), arm=dirv(u=1.0, f=-0.3, r=0.35)),
          lA=aim(dirv(u=0.8, f=0.6, r=-0.3)),
          rL=(-40, 0, 2), lL=(-14, 0, -2), root_pos=(0, 3.2, 0))
tc_plant = P(w=(30, 0, 0), h=(-18, 0, 0),
             rA=wield(blade=dirv(f=0.2, u=-1.0), arm=dirv(f=1.0, u=0.25, r=0.2)),
             lA=aim(dirv(f=0.3, u=-1.0, r=0.35)),
             rL=(60, 0, 6), lL=(-54, 0, -6), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.08: c1_wind, 0.18: c1_hit, 0.3: c1_follow, 0.5: H}),
    "combo2": anim(0.55, {0.0: H, 0.09: c2_wind, 0.18: c2_mid, 0.27: c2_hit,
                          0.4: P(c2_hit, b=(6, -40, 0)), 0.55: H}),
    "combo3": anim(0.75, {0.0: H, 0.18: c3_up, 0.32: c3_hit, 0.55: P(c3_hit, w=(28, 0, 0)), 0.75: H}),
    "sonic_thrust": anim(0.95, {0.0: H, 0.14: st_coil, 0.32: P(st_coil, b=(6, 56, 0), h=(0, -48, 0)),
                                0.4: st_lunge, 0.66: P(st_lunge, w=(18, 0, 0), b=(6, -22, 0)),
                                0.95: H}),
    "vortex_dive": anim(0.86, vd_frames),
    "retro_throw": anim(0.8, {0.0: H, 0.16: rt_cock, 0.32: P(rt_cock, b=(-18, 30, 0)),
                              0.4: rt_throw, 0.58: P(rt_throw, w=(30, 0, 0)), 0.8: H}),
    "tempest_stir": anim(1.6, ts_frames),
    "tidal_crash": anim(1.1, {0.0: H, 0.22: tc_up, 0.4: P(tc_up, root_pos=(0, 3.6, -0.6)),
                              0.52: tc_plant, 0.92: P(tc_plant, w=(26, 0, 0)), 1.1: H}),
}
