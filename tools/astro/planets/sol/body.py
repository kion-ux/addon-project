# -*- coding: utf-8 -*-
"""太陽（ソル・オーバードライブ）の全身モーション。武器は紅炎剣（kind greatsword、片手で持つ大剣）。

名前はそのまま `animation.astro.p.sol.<名前>` になり、スクリプトは body(p, "sol.combo1") のように呼ぶ。
向きは体の空間: dirv(f=前, u=上, r=右)。大剣は重いので、どの振りも「溜め → 全身で振り抜く → 残心」を長めに。

  combo1        右から左への重い横薙ぎ（腰ごと回す）
  combo2        左下から右上への逆袈裟の斬り上げ
  combo3        跳び上がって背中まで振りかぶり、真上から叩き斬る（三段目: 紅炎の弧）
  solar_flare   惑星技 ソーラー・フレア: 剣を天へ掲げ左の掌を前へ突き出して溜め（0〜0.4 秒）、
                前方を扇に薙ぎ払う（0.46 秒）
  corona_drive  機動技 コロナ・ドライブ: 剣を後ろ下へ引きずる前傾の突進、最後に斬り上げ（0.62 秒）
  prominence    空中技 プロミネンス・アーチ: 宙で三度、頭上から叩きつける（0.24 / 0.46 / 0.72 秒）
  nova_collapse 必殺 スーパーノヴァ（前半）: 身を丸めて恒星の核へ収縮する（膝を抱え、剣を抱き込む）
  nova_burst    必殺 スーパーノヴァ（後半）: 全身を大の字に開いて爆発する
"""
from __future__ import annotations

from astro_animlib import LEFT, RIGHT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(0, 44, 0), h=(0, -32, 0), w=(4, 0, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.45, u=0.2), arm=dirv(r=1.0, u=-0.2, f=0.05)),
            lA=aim(dirv(f=1.0, r=-0.4, u=-0.1)),
            rL=(14, 0, 7), lL=(-18, 0, -7), ground=True)
c1_hit = P(b=(6, -14, 0), h=(0, 12, 0), w=(8, 0, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.1, u=-0.05), edge=LEFT),
           lA=aim(dirv(f=-0.35, u=-1.0, r=-0.6)),
           rL=(24, 0, 7), lL=(-34, 0, -7), root_pos=(0, 0, -1.4), ground=True)
c1_follow = P(c1_hit, b=(8, -48, 0), h=(0, 36, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.2, u=-0.15), arm=dirv(r=-0.9, f=0.5, u=-0.3)))

c2_wind = P(b=(12, -34, 0), h=(0, 26, 0),
            rA=wield(blade=dirv(r=-0.75, u=-0.55, f=0.4), arm=dirv(f=1.0, u=-0.55, r=-0.25)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.45)),
            rL=(-24, 0, 7), lL=(16, 0, -7), ground=True)
c2_hit = P(b=(-8, 26, 0), h=(0, -20, 0),
           rA=wield(blade=dirv(r=0.55, u=0.75, f=0.45), arm=dirv(r=0.6, u=0.3, f=0.75)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-28, 0, 7), lL=(20, 0, -7), root_pos=(0, 0.6, -1.0), ground=True)
c2_follow = P(c2_hit, b=(-12, 38, 0), h=(-8, -28, 0),
              rA=wield(blade=dirv(r=0.5, u=0.85, f=-0.25), arm=dirv(r=0.85, u=0.5, f=0.1)))

c3_crouch = P(w=(14, 0, 0), h=(-10, 0, 0),
              rA=wield(blade=dirv(r=0.7, f=-0.5, u=-0.5), arm=dirv(r=0.8, u=-0.6, f=-0.1)),
              lA=aim(dirv(f=0.6, u=-0.6, r=-0.3)), rL=(-20, 0, 6), lL=(-20, 0, -6), ground=True)
c3_up = P(b=(-18, 0, 0), h=(-18, 0, 0),
          rA=wield(blade=dirv(u=0.5, f=-0.85), arm=dirv(u=1.0, f=0.1, r=0.3)),
          lA=aim(dirv(u=0.7, f=1.0, r=-0.2)),
          rL=(-40, 0, 0), lL=(-14, 0, 0), root_pos=(0, 2.6, 0))
c3_hit = P(w=(32, 0, 0), h=(-26, 0, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.3), arm=dirv(f=0.75, u=-0.66)),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
           rL=(34, 0, 8), lL=(-48, 0, -8), root_pos=(0, 0, -2.2), ground=True)

# ---- 惑星技 ソーラー・フレア -----------------------------------------------------
sf_raise = P(b=(-10, 28, 0), h=(-6, -22, 0),
             rA=wield(blade=dirv(u=1.0, f=-0.3, r=0.2), arm=dirv(u=1.0, r=0.4, f=0.05)),
             lA=aim(dirv(f=1.0, u=0.15, r=-0.15), twist=-30),
             rL=(16, 0, 10), lL=(-20, 0, -10), ground=True)
sf_hold = P(sf_raise, b=(-14, 34, 0), h=(-8, -26, 0),
            rA=wield(blade=dirv(u=0.85, f=-0.55, r=0.3), arm=dirv(u=1.0, r=0.5, f=-0.1)))
sf_hit = P(b=(8, -20, 0), h=(0, 16, 0), w=(10, 0, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.15, u=0.05), edge=LEFT),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.7)),
           rL=(26, 0, 10), lL=(-38, 0, -10), root_pos=(0, 0, -1.6), ground=True)
sf_follow = P(sf_hit, b=(8, -54, 0), h=(0, 40, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.3, u=-0.1), arm=dirv(r=-0.9, f=0.5, u=-0.25)))

# ---- 機動技 コロナ・ドライブ ------------------------------------------------------
cd_run = P(w=(30, 0, 0), h=(-30, 0, 0),
           lA=aim(dirv(f=1.0, u=0.2, r=-0.1), twist=30),
           rA=wield(blade=dirv(f=-0.85, u=-0.45, r=0.35), arm=dirv(f=-0.45, u=-1.0, r=0.45)),
           rL=(-34, 0, 3), lL=(30, 0, -3))
cd_rise = P(w=(-4, 0, 0), b=(-10, 10, 0), h=(-14, 0, 0),
            rA=wield(blade=dirv(f=0.65, u=0.75, r=0.15), arm=dirv(f=0.9, u=0.5, r=0.35)),
            lA=aim(dirv(f=-0.3, u=-1.0, r=-0.5)),
            rL=(-20, 0, 6), lL=(18, 0, -6), ground=True)
cd_follow = P(cd_rise, b=(-14, 14, 0), h=(-20, 0, 0),
              rA=wield(blade=dirv(u=1.0, f=-0.35, r=0.15), arm=dirv(u=1.0, f=0.3, r=0.4)))

# ---- 空中技 プロミネンス・アーチ（三度の振り下ろし） ----------------------------
pa_up = P(b=(-14, 0, 0), h=(-16, 0, 0),
          rA=wield(blade=dirv(u=0.65, f=-0.75), arm=dirv(u=1.0, f=0.1, r=0.35)),
          lA=aim(dirv(u=0.6, f=1.0, r=-0.3)),
          rL=(-44, 0, 4), lL=(-18, 0, -4))
pa_chop = P(b=(20, 0, 0), h=(-12, 0, 0),
            rA=wield(blade=dirv(f=1.0, u=-0.45), arm=dirv(f=0.9, u=-0.45)),
            lA=aim(dirv(f=-0.3, u=-1.0, r=-0.4)),
            rL=(-20, 0, 4), lL=(-46, 0, -4))
pa_up2 = P(pa_up, b=(-8, -8, 0), rA=wield(blade=dirv(u=1.0, f=-0.2, r=0.1), arm=dirv(u=0.9, f=0.35, r=0.4)))
pa_chop2 = P(pa_chop, b=(18, -12, 0), rA=wield(blade=dirv(f=1.0, u=-0.4, r=-0.2), arm=dirv(f=0.9, u=-0.4, r=-0.1)))
pa_up3 = P(pa_up, b=(-20, 0, 0), h=(-22, 0, 0),
           rA=wield(blade=dirv(u=0.75, f=-0.65), arm=dirv(u=1.0, f=0.05, r=0.3)),
           rL=(-60, 0, 4), lL=(-30, 0, -4))
pa_slam = P(w=(28, 0, 0), b=(10, 0, 0), h=(-24, 0, 0),
            rA=wield(blade=dirv(f=1.0, u=-0.65), arm=dirv(f=0.8, u=-0.75)),
            lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
            rL=(-10, 0, 6), lL=(-50, 0, -6))

# ---- 必殺 スーパーノヴァ ---------------------------------------------------------
curl = P(b=(30, 0, 0), h=(26, 0, 0),
         rL=(-72, 0, 10), lL=(-72, 0, -10),
         lA=aim(dirv(r=0.85, f=0.55, u=0.2), twist=20),
         rA=wield(blade=dirv(u=-1.0, f=-0.25, r=0.25), arm=dirv(r=-0.55, f=0.8, u=-0.1)),
         root_pos=(0, 1.6, 0))
curl2 = P(curl, b=(38, 0, 0), h=(32, 0, 0), rL=(-82, 0, 8), lL=(-82, 0, -8), root_pos=(0, 2.0, 0))
nova = P(b=(-26, 0, 0), h=(-32, 0, 0),
         lA=aim(dirv(r=-1.0, u=0.55, f=0.1)),
         rA=wield(blade=dirv(r=0.55, u=0.85, f=0.05), arm=dirv(r=1.0, u=0.5, f=0.1)),
         rL=(6, 0, 20), lL=(6, 0, -20), root_pos=(0, 1.4, 0))

BODY_ANIMS = {
    "combo1": anim(0.55, {0.0: H, 0.1: c1_wind, 0.21: c1_hit, 0.3: c1_follow,
                          0.42: P(c1_follow, b=(6, -42, 0)), 0.55: H}),
    "combo2": anim(0.55, {0.0: H, 0.1: c2_wind, 0.22: c2_hit, 0.32: c2_follow,
                          0.42: P(c2_follow, b=(-10, 32, 0)), 0.55: H}),
    "combo3": anim(0.8, {0.0: H, 0.08: c3_crouch, 0.2: c3_up, 0.36: c3_hit,
                         0.58: P(c3_hit, w=(28, 0, 0)), 0.8: H}),
    "solar_flare": anim(0.95, {0.0: H, 0.12: sf_raise, 0.36: sf_hold, 0.46: sf_hit, 0.58: sf_follow,
                               0.78: P(sf_follow, b=(6, -46, 0)), 0.95: H}),
    "corona_drive": anim(0.9, {0.0: H, 0.08: cd_run, 0.3: P(cd_run, rL=(30, 0, 3), lL=(-34, 0, -3)),
                               0.5: cd_run, 0.62: cd_rise, 0.72: cd_follow, 0.9: H}),
    "prominence": anim(1.05, {0.0: H, 0.12: pa_up, 0.24: pa_chop, 0.34: pa_up2, 0.46: pa_chop2,
                              0.58: pa_up3, 0.72: pa_slam, 0.88: P(pa_slam, w=(24, 0, 0)), 1.05: H}),
    "nova_collapse": anim(1.7, {0.0: H, 0.3: curl, 1.2: curl2, 1.55: curl2, 1.7: H}),
    "nova_burst": anim(1.1, {0.0: curl2, 0.08: nova, 0.7: P(nova, b=(-20, 0, 0), h=(-26, 0, 0)),
                             1.1: H}),
}
