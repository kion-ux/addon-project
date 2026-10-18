# -*- coding: utf-8 -*-
"""木星（ゼウス）の全身モーション。雷霆鎚 ケラウノス（kind hammer: 手首の角度 96°、腕を下ろすと鎚頭が前）。

名前はそのまま `animation.astro.p.jupiter.<名前>` になり、スクリプトは body(p, "jupiter.<名前>")。
向きは体の空間: dirv(f=前, u=上, r=右)。wield(blade=鎚頭の向き, arm=腕の向き / edge=打撃面の向き)。
重い武器なので、どの振りも「大きく溜めて → 体ごと振り抜き → 余韻で踏みとどまる」。

  combo1        右から左への重い横殴り（腰ごとひねる）
  combo2        左下から右上へのかち上げ
  combo3        跳び上がって両手で真上から叩きつける（三段目: 雷槌）
  keraunos      惑星技 雷霆: 鎚を天へ掲げて雷を受け、前へ突き出して放つ
  swingby       機動技 重力スイングバイ: 左の掌で重力の井戸を作り、鎚を引いて前傾で突き抜け、抜け際に薙ぐ
  storm_dive    空中技 大赤斑: 鎚を外へ伸ばし、嵐の渦の中で二回転しながら降りる
  storm_land    空中技の着地: 渦の底で鎚を地面へ叩きつける
  judgement     必殺 ガリレオの審判: 鎚を天へ掲げ、左手で四つの衛星を一つずつ指し示す
  thunderfall   必殺の締め: 跳び上がり、極大の雷霆とともに鎚を大地へ振り下ろして膝をつく
"""
from __future__ import annotations

from astro_animlib import DOWN, LEFT, H, P, aim, anim, dirv, flip, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(2, 44, 0), w=(4, 0, 0), h=(0, -32, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.45, u=0.25), arm=dirv(r=1.0, u=-0.2, f=-0.1)),
            lA=aim(dirv(f=1.0, r=-0.4, u=-0.1)),
            rL=(14, 0, 8), lL=(-18, 0, -8), ground=True)
c1_lift = P(b=(0, 20, 0), h=(0, -14, 0),
            rA=wield(blade=dirv(r=0.75, f=0.45, u=0.45), arm=dirv(r=0.9, u=-0.45, f=0.25)),
            lA=aim(dirv(f=1.0, r=-0.3, u=-0.3)), ground=True)
c1_hit = P(b=(8, -14, 0), w=(8, 0, 0), h=(0, 12, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.15, u=0.05), edge=LEFT),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.6)),
           rL=(24, 0, 8), lL=(-32, 0, -8), root_pos=(0, 0, -1.2), ground=True)
c1_follow = P(c1_hit, b=(8, -48, 0), h=(0, 36, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.3, u=-0.1), arm=dirv(r=-0.9, f=0.5, u=-0.3)))

c2_wind = P(b=(12, -34, 0), w=(8, 0, 0), h=(0, 26, 0),
            rA=wield(blade=dirv(r=-0.75, u=-0.55, f=0.4), arm=dirv(f=1.0, u=-0.6, r=-0.25)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)),
            rL=(-24, 0, 8), lL=(16, 0, -8), ground=True)
c2_hit = P(b=(-8, 22, 0), h=(0, -18, 0),
           rA=wield(blade=dirv(r=0.5, u=0.8, f=0.35), arm=dirv(r=0.65, u=0.3, f=0.7)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-28, 0, 8), lL=(20, 0, -8), root_pos=(0, 0.6, -0.8), ground=True)
c2_follow = P(c2_hit, b=(-12, 34, 0), h=(-8, -24, 0),
              rA=wield(blade=dirv(r=0.35, u=0.85, f=-0.35), arm=dirv(r=0.85, u=0.55, f=0.1)))

c3_up = P(b=(-16, 0, 0), h=(-18, 0, 0),
          rA=wield(blade=dirv(u=0.45, f=-0.9), arm=dirv(u=1.0, f=0.1, r=0.3)),
          lA=aim(dirv(u=1.0, f=0.35, r=-0.15)),
          rL=(-38, 0, 0), lL=(-12, 0, 0), root_pos=(0, 2.4, 0))
c3_over = P(c3_up, b=(-6, 0, 0), root_pos=(0, 2.0, 0),
            rA=wield(blade=dirv(u=0.9, f=0.3, r=0.1), arm=dirv(u=0.9, f=0.45, r=0.4)))
c3_hit = P(w=(34, 0, 0), h=(-28, 0, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.7), arm=dirv(f=1.0, u=-0.45)),
           lA=aim(dirv(f=1.0, u=-0.7, r=-0.2)),
           rL=(34, 0, 9), lL=(-48, 0, -9), root_pos=(0, 0, -2.0), ground=True)

# ---- 惑星技 雷霆: 掲げて受け、突き出して放つ ----------------------------------------
k_raise = P(b=(-10, 8, 0), h=(-26, 0, 0),
            rA=wield(blade=dirv(u=1.0, f=0.15, r=0.05), arm=dirv(u=1.0, f=0.35, r=0.3)),
            lA=aim(dirv(r=-1.0, u=0.25, f=0.2)),
            rL=(-6, 0, 10), lL=(6, 0, -10), ground=True)
k_charge = P(k_raise, b=(-14, 10, 0), h=(-32, 0, 0),
             lA=aim(dirv(r=-1.0, u=0.45, f=0.1)))
k_point = P(b=(12, -12, 0), w=(6, 0, 0), h=(-6, 10, 0),
            rA=wield(blade=dirv(f=1.0, u=0.25, r=-0.05), arm=dirv(f=1.0, u=0.05, r=-0.2)),
            lA=aim(dirv(f=-0.3, u=-1.0, r=-0.5)),
            rL=(26, 0, 8), lL=(-34, 0, -8), root_pos=(0, 0, -1.0), ground=True)

# ---- 機動技 重力スイングバイ --------------------------------------------------------
s_well = P(b=(4, 22, 0), h=(0, -14, 0),
           lA=aim(dirv(f=1.0, u=0.15, r=0.1), twist=60),
           rA=wield(blade=dirv(f=-0.4, u=0.35, r=0.65), arm=dirv(r=0.75, u=-0.55, f=-0.35)),
           rL=(16, 0, 8), lL=(-22, 0, -8), ground=True)
s_dash = P(w=(30, 0, 0), h=(-30, 0, 0),
           rA=wield(blade=dirv(f=-0.5, u=-0.05, r=0.85), arm=dirv(f=-0.35, u=-1.0, r=0.5)),
           lA=aim(dirv(f=1.0, u=0.0, r=0.2), twist=60),
           rL=(-34, 0, 2), lL=(30, 0, -2))
s_sweep = P(b=(10, -42, 0), w=(14, 0, 0), h=(-10, 34, 0),
            rA=wield(blade=dirv(r=-1.0, f=0.25), arm=dirv(r=-0.75, f=0.6, u=-0.3)),
            lA=aim(dirv(r=0.5, f=-0.6, u=-0.7)),
            rL=(22, 0, 8), lL=(-28, 0, -8), ground=True)

# ---- 空中技 大赤斑: 鎚を外へ伸ばして回る / 着地の叩きつけ -----------------------------
spin_out = P(rA=wield(blade=dirv(r=1.0, f=0.4, u=0.05), arm=dirv(r=1.0, f=0.3, u=-0.1)),
             lA=aim(dirv(r=-1.0, u=-0.3, f=-0.2)), b=(6, 0, 0), h=(8, 0, 0),
             rL=(-18, 0, 8), lL=(-6, 0, -8))
dive = {0.0: H, 0.08: P(spin_out, root=(0, 20, 0))}
dive.update(flip(0.12, 1.02, -2.0, "y", base=spin_out, tuck=False, steps=12))
dive[1.2] = P(spin_out, root=(0, -720, 0), rA=wield(blade=dirv(u=0.6, f=-0.75, r=0.2),
                                                    arm=dirv(u=1.0, f=0.15, r=0.35)))
land_down = P(w=(32, 0, 0), h=(-26, 0, 0),
              rA=wield(blade=dirv(f=1.0, u=-0.72), arm=dirv(f=1.0, u=-0.55)),
              lA=aim(dirv(f=0.6, u=-1.0, r=0.2)),
              rL=(-46, 0, 8), lL=(40, 0, -8), ground=True)

# ---- 必殺 ガリレオの審判 ------------------------------------------------------------
j_raise = P(b=(-10, 0, 0), h=(-28, 0, 0),
            rA=wield(blade=dirv(u=1.0, f=0.1), arm=dirv(u=1.0, f=0.35, r=0.25)),
            lA=aim(dirv(f=1.0, u=0.35, r=-0.45)),
            rL=(-8, 0, 10), lL=(8, 0, -10), ground=True)
j_pt = [P(j_raise, lA=aim(dirv(f=1.0, u=u, r=r)), b=(-8, ry, 0), h=(-22, -ry * 0.6, 0))
        for r, u, ry in ((-0.6, 0.25, -12), (0.0, 0.15, 0), (0.5, 0.25, 10), (-0.2, 0.5, -4))]
t_jump = P(b=(-18, 0, 0), h=(-24, 0, 0),
           rA=wield(blade=dirv(u=0.4, f=-0.9), arm=dirv(u=1.0, f=0.1, r=0.3)),
           lA=aim(dirv(u=1.0, f=0.3, r=-0.2)),
           rL=(-40, 0, 0), lL=(-14, 0, 0), root_pos=(0, 3.2, 0))
t_over = P(t_jump, rA=wield(blade=dirv(u=0.9, f=0.35, r=0.1), arm=dirv(u=0.9, f=0.45, r=0.4)),
           b=(-6, 0, 0), root_pos=(0, 2.6, 0))
t_smash = P(w=(36, 0, 0), h=(-30, 0, 0), b=(4, 0, 0),
            rA=wield(blade=dirv(f=1.0, u=-0.75), arm=dirv(f=1.0, u=-0.6)),
            lA=aim(dirv(f=0.5, u=-1.0, r=0.3)),
            rL=(60, 0, 6), lL=(-54, 0, -6), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.55, {0.0: H, 0.045: c1_lift, 0.09: c1_wind, 0.2: c1_hit, 0.3: c1_follow,
                          0.4: P(c1_follow, b=(6, -44, 0)), 0.55: H}),
    "combo2": anim(0.55, {0.0: H, 0.09: c2_wind, 0.21: c2_hit, 0.31: c2_follow,
                          0.4: P(c2_follow, b=(-10, 30, 0)), 0.55: H}),
    "combo3": anim(0.8, {0.0: H, 0.16: c3_up, 0.26: c3_over, 0.34: c3_hit,
                         0.58: P(c3_hit, w=(32, 0, 0)), 0.8: H}),
    "keraunos": anim(0.95, {0.0: H, 0.14: k_raise, 0.36: k_charge, 0.46: k_point,
                            0.72: P(k_point, b=(10, -10, 0)), 0.95: H}),
    "swingby": anim(1.05, {0.0: H, 0.1: s_well, 0.4: P(s_well, lA=aim(dirv(f=1.0, u=0.2, r=0.1), twist=80)),
                           0.5: s_dash, 0.72: P(s_dash, rL=(-30, 0, 2), lL=(26, 0, -2)),
                           0.82: s_sweep, 0.95: P(s_sweep, b=(8, -38, 0)), 1.05: H}),
    "storm_dive": anim(1.2, dive),
    "storm_land": anim(0.7, {0.0: P(land_down, w=(12, 0, 0), ground=True), 0.06: land_down,
                             0.45: P(land_down, w=(28, 0, 0)), 0.7: H}),
    "judgement": anim(2.6, {0.0: H, 0.25: j_raise, 0.55: j_pt[0], 1.0: j_pt[1], 1.45: j_pt[2],
                            1.9: j_pt[3], 2.35: P(j_raise, b=(-12, 0, 0)), 2.6: j_raise}),
    "thunderfall": anim(1.3, {0.0: j_raise, 0.2: t_jump, 0.32: t_over, 0.42: t_smash,
                              0.95: P(t_smash, w=(32, 0, 0)), 1.3: H}),
}
