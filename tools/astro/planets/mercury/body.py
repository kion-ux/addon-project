# -*- coding: utf-8 -*-
"""水星（クイックシルバー）の全身モーション。武器は水銀刃 ヘルメス・エッジ（kind saber、片手の反りのある片刃）。

名前はそのまま `animation.astro.p.mercury.<名前>` になり、スクリプトは body(p, "mercury.combo1") のように呼ぶ。
最速の形態なので、どの振りも「溜めは短く、振り抜きは鋭く、残心で刃を流す」。体の向きは dirv(f=前, u=上, r=右)。

  combo1        右から左への鋭い横一閃（居合のように低く踏み込む）
  combo2        返しの逆袈裟（左下から右上へ）
  combo3        三段目「水銀の飛沫」: 腰を落とし、全身で一回転して前方を大きく薙ぐ
  flash_slash   惑星技 水銀閃: 抜刀の構え（0〜0.3 秒）→ 前傾で駆け抜ける（0.3〜0.5）→ 振り抜いた残心（0.5〜0.85）
  hermes_wings  機動技 ヘルメスの翼: 三度の斬撃（0.1 横薙ぎ / 0.5 斬り上げ / 0.9 振り下ろし）
  needle_rain   空中技 マーキュリー・レイン: 宙で身を反らし、左手を前下へ突き出して針を三度撃つ
  peri_draw     必殺 近日点突破（開幕）: 低い抜刀の構えで時を止める
  peri_finish   必殺 近日点突破（締め）: 刃を天へ振り上げ、一気に振り下ろして納める
  flourish      変身の締め: 刃を横へ払い、液体金属を振り落とす
"""
from __future__ import annotations

from astro_animlib import LEFT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ -------------------------------------------------------------
c1_wind = P(b=(4, 46, 0), h=(0, -34, 0), w=(8, 0, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.5, u=-0.05), arm=dirv(r=0.9, u=-0.35, f=0.15)),
            lA=aim(dirv(f=1.0, r=-0.3, u=-0.2)),
            rL=(16, 0, 8), lL=(-22, 0, -8), ground=True)
c1_hit = P(b=(8, -16, 0), h=(0, 14, 0), w=(10, 0, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.1, u=-0.08), edge=LEFT),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.6)),
           rL=(26, 0, 8), lL=(-38, 0, -8), root_pos=(0, 0, -1.6), ground=True)
c1_follow = P(c1_hit, b=(8, -50, 0), h=(0, 38, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.2, u=-0.15), arm=dirv(r=-0.9, f=0.5, u=-0.3)))

c2_wind = P(b=(12, -36, 0), h=(0, 28, 0),
            rA=wield(blade=dirv(r=-0.7, u=-0.6, f=0.4), arm=dirv(f=1.0, u=-0.55, r=-0.2)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.45)),
            rL=(-24, 0, 8), lL=(16, 0, -8), ground=True)
c2_hit = P(b=(-8, 28, 0), h=(0, -22, 0),
           rA=wield(blade=dirv(r=0.55, u=0.78, f=0.4), arm=dirv(r=0.6, u=0.3, f=0.75)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)),
           rL=(-28, 0, 8), lL=(20, 0, -8), root_pos=(0, 0.5, -1.0), ground=True)
c2_follow = P(c2_hit, b=(-12, 40, 0), h=(-8, -28, 0),
              rA=wield(blade=dirv(r=0.5, u=0.85, f=-0.2), arm=dirv(r=0.85, u=0.5, f=0.15)))

# 三段目: 腰を落として刃を右後ろへ寝かせ、左回りに一回転して薙ぐ
c3_coil = P(w=(18, 0, 0), b=(4, 40, 0), h=(-14, -30, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.6, u=-0.1), arm=dirv(r=0.9, u=-0.4, f=-0.1)),
            lA=aim(dirv(f=1.0, r=-0.5, u=-0.1)),
            rL=(20, 0, 12), lL=(-30, 0, -12), ground=True)
c3_out = P(w=(12, 0, 0), h=(-10, 0, 0),
           rA=wield(blade=dirv(r=1.0, f=0.4, u=-0.05), arm=dirv(r=1.0, f=0.3, u=-0.15)),
           lA=aim(dirv(r=-1.0, u=-0.4, f=-0.2)),
           rL=(-16, 0, 10), lL=(16, 0, -10))
c3_end = P(w=(16, 0, 0), b=(6, -30, 0), h=(-8, 24, 0),
           rA=wield(blade=dirv(r=-1.0, f=0.3, u=-0.25), arm=dirv(r=-0.85, f=0.5, u=-0.35)),
           lA=aim(dirv(f=-0.3, u=-1.0, r=-0.6)),
           rL=(22, 0, 10), lL=(-30, 0, -10), root_pos=(0, 0, -1.2), ground=True)

# ---- 惑星技 水銀閃 ----------------------------------------------------------------
fs_draw = P(w=(26, 0, 0), b=(0, 30, 0), h=(-24, -24, 0),
            rA=wield(blade=dirv(f=-0.8, r=0.55, u=-0.2), arm=dirv(f=0.2, u=-1.0, r=-0.3)),
            lA=aim(dirv(f=0.8, u=-0.6, r=-0.5), twist=20),
            rL=(28, 0, 10), lL=(-40, 0, -10), ground=True)
fs_dash = P(w=(36, 0, 0), b=(0, -10, 0), h=(-34, 8, 0),
            rA=wield(blade=dirv(f=-0.9, r=0.4, u=-0.2), arm=dirv(f=-0.3, u=-1.0, r=0.5)),
            lA=aim(dirv(f=-0.6, u=-0.6, r=-0.6)),
            rL=(-40, 0, 4), lL=(36, 0, -4))
fs_after = P(w=(20, 0, 0), b=(4, -46, 0), h=(-12, 36, 0),
             rA=wield(blade=dirv(r=-1.0, f=-0.25, u=-0.2), arm=dirv(r=-0.95, f=0.35, u=-0.2)),
             lA=aim(dirv(r=1.0, u=-0.7, f=-0.2)),
             rL=(30, 0, 12), lL=(-44, 0, -12), ground=True)

# ---- 機動技 ヘルメスの翼（三度の斬撃） -------------------------------------------
hw1 = P(b=(6, -28, 0), h=(0, 20, 0),
        rA=wield(blade=dirv(f=1.0, r=-0.3, u=-0.05), edge=LEFT),
        lA=aim(dirv(f=-0.4, u=-1.0, r=-0.6)), rL=(24, 0, 8), lL=(-30, 0, -8), ground=True)
hw2_pre = P(b=(10, -24, 0), h=(0, 18, 0),
            rA=wield(blade=dirv(r=-0.6, u=-0.7, f=0.35), arm=dirv(f=1.0, u=-0.6, r=-0.2)),
            lA=aim(dirv(f=0.4, u=-1.0, r=0.4)), rL=(-20, 0, 8), lL=(14, 0, -8), ground=True)
hw2 = P(b=(-12, 22, 0), h=(-6, -20, 0),
        rA=wield(blade=dirv(r=0.4, u=0.85, f=0.35), arm=dirv(r=0.55, u=0.45, f=0.7)),
        lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)), rL=(-30, 0, 8), lL=(22, 0, -8),
        root_pos=(0, 1.0, -0.6), ground=True)
hw3_pre = P(b=(-16, 0, 0), h=(-18, 0, 0),
            rA=wield(blade=dirv(u=0.6, f=-0.8), arm=dirv(u=1.0, f=0.15, r=0.3)),
            lA=aim(dirv(u=0.6, f=1.0, r=-0.2)), rL=(-30, 0, 0), lL=(-10, 0, 0), root_pos=(0, 1.6, 0))
hw3 = P(w=(30, 0, 0), h=(-24, 0, 0),
        rA=wield(blade=dirv(f=1.0, u=-0.3), arm=dirv(f=0.75, u=-0.66)),
        lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)),
        rL=(32, 0, 8), lL=(-44, 0, -8), root_pos=(0, 0, -1.8), ground=True)

# ---- 空中技 マーキュリー・レイン ----------------------------------------------------
nr_up = P(b=(-14, 0, 0), h=(-16, 0, 0),
          rA=wield(blade=dirv(r=0.7, u=-0.45, f=-0.55), arm=dirv(r=0.9, u=-0.5, f=-0.1)),
          lA=aim(dirv(f=0.8, u=0.5, r=-0.1)),
          rL=(-34, 0, 6), lL=(12, 0, -6))
nr_shot = P(b=(14, 0, 0), h=(10, 0, 0),
            rA=wield(blade=dirv(r=0.7, u=-0.45, f=-0.55), arm=dirv(r=0.9, u=-0.5, f=-0.1)),
            lA=aim(dirv(f=1.0, u=-0.75, r=-0.05), twist=-20),
            rL=(-30, 0, 6), lL=(16, 0, -6))

# ---- 必殺 近日点突破 ---------------------------------------------------------------
pd_low = P(w=(30, 0, 0), b=(0, 34, 0), h=(-30, -30, 0),
           rA=wield(blade=dirv(f=-0.85, r=0.45, u=-0.25), arm=dirv(f=0.25, u=-1.0, r=-0.35)),
           lA=aim(dirv(f=0.7, u=-0.5, r=-0.6), twist=25),
           rL=(36, 0, 12), lL=(-50, 0, -12), ground=True)
pf_up = P(b=(-14, 0, 0), h=(-30, 0, 0),
          rA=wield(blade=dirv(u=1.0, f=0.1), arm=dirv(u=1.0, f=0.35, r=0.25)),
          lA=aim(dirv(f=0.6, u=-0.6, r=-0.6), twist=20),
          rL=(-8, 0, 10), lL=(8, 0, -10), ground=True)
pf_down = P(w=(26, 0, 0), h=(-20, 0, 0),
            rA=wield(blade=dirv(f=0.9, u=-0.6, r=-0.15), arm=dirv(f=0.8, u=-0.6)),
            lA=aim(dirv(f=-0.3, u=-1.0, r=-0.6)),
            rL=(30, 0, 10), lL=(-42, 0, -10), ground=True)
pf_sheath = P(w=(10, 0, 0), b=(2, 20, 0), h=(-6, -14, 0),
              rA=wield(blade=dirv(f=-0.9, r=0.35, u=-0.3), arm=dirv(f=0.1, u=-1.0, r=-0.35)),
              lA=aim(dirv(f=0.4, u=-1.0, r=-0.3)),
              rL=(10, 0, 8), lL=(-14, 0, -8), ground=True)

# ---- 変身の締め ---------------------------------------------------------------------
fl_out = P(b=(-4, 10, 0), h=(-6, -6, 0),
           rA=wield(blade=dirv(r=1.0, f=0.3, u=-0.35), arm=dirv(r=1.0, u=-0.35, f=0.2)),
           lA=aim(dirv(f=0.6, u=-0.7, r=-0.4)), rL=(-10, 0, 10), lL=(10, 0, -10), ground=True)

# 自然体から最初の構えへ移る間に、刃を一度体の外（右前）へ出す（刃が胴を通らないように）
out_r = P(b=(0, 14, 0), rA=wield(blade=dirv(r=1.0, f=0.45, u=-0.35), arm=dirv(r=0.85, u=-0.5, f=0.35)))
out_low = P(w=(8, 0, 0), rA=wield(blade=dirv(r=0.9, f=0.2, u=-0.5), arm=dirv(r=0.7, u=-0.7, f=0.3)))

# 共通の「投げる」を水銀刃に合わせて（振りかぶりで拳を頭の右へ逃がす）
throw_wind = P(rA=wield(blade=dirv(u=0.55, f=-0.8, r=0.35), arm=dirv(u=1.0, f=-0.2, r=0.6)),
               lA=aim(dirv(f=1.0, u=0.15, r=-0.1)), b=(-6, 32, 0), h=(0, -26, 0), rL=(14, 0, 4),
               lL=(-20, 0, -4))
throw_rel = P(rA=wield(blade=dirv(f=1.0, u=-0.1), arm=dirv(f=1.0, u=0.05, r=-0.05)),
              lA=aim(dirv(f=-0.3, u=-1.0, r=-0.4)), b=(14, -24, 0), h=(-8, 22, 0),
              rL=(16, 0, 4), lL=(-30, 0, -4), root_pos=(0, -0.6, -1.0))

BODY_ANIMS = {
    "throw": anim(0.55, {0.0: H, 0.06: P(out_r, rA=wield(blade=dirv(r=1.0, u=0.2, f=0.1),
                                                         arm=dirv(r=1.0, u=-0.2, f=0.2))),
                         0.14: throw_wind, 0.26: throw_rel, 0.38: P(throw_rel, b=(14, -22, 0)),
                         0.46: P(rA=wield(blade=dirv(f=0.7, u=-0.45, r=0.45), arm=dirv(r=0.55, u=-0.8, f=0.25)),
                                 b=(6, -8, 0), h=(-4, 8, 0)),
                         0.55: H}),
    "combo1": anim(0.45, {0.0: H, 0.03: out_r, 0.07: c1_wind, 0.15: c1_hit, 0.24: c1_follow,
                          0.33: P(c1_follow, b=(6, -40, 0)), 0.45: H}),
    "combo2": anim(0.45, {0.0: H, 0.07: c2_wind, 0.17: c2_hit, 0.26: c2_follow,
                          0.34: P(c2_follow, b=(-8, 32, 0)), 0.45: H}),
    "combo3": anim(0.7, {0.0: H, 0.04: out_r, 0.1: c3_coil, 0.16: P(c3_out, root=(0, 30, 0)),
                         0.24: P(c3_out, root=(0, -90, 0)), 0.32: P(c3_out, root=(0, -200, 0)),
                         0.4: P(c3_out, root=(0, -300, 0)),
                         0.48: P(c3_end, root=(0, -360, 0)),
                         0.6: P(c3_end, w=(12, 0, 0), root=(0, -360, 0)),
                         0.7: P(root=(0, -360, 0))}, blend=False),
    "flash_slash": anim(0.85, {0.0: H, 0.05: out_low, 0.12: fs_draw, 0.28: P(fs_draw, w=(30, 0, 0)),
                               0.34: fs_dash, 0.46: P(fs_dash, w=(32, 0, 0)), 0.52: fs_after,
                               0.72: P(fs_after, b=(4, -40, 0)), 0.85: H}),
    "hermes_wings": anim(1.2, {0.0: H, 0.04: P(c1_wind, root_pos=(0, 0.6, 0)), 0.1: hw1,
                               0.22: P(hw1, b=(6, -40, 0)), 0.42: hw2_pre, 0.52: hw2,
                               0.64: P(hw2, b=(-12, 30, 0)), 0.8: hw3_pre, 0.9: hw3,
                               1.04: P(hw3, w=(26, 0, 0)), 1.2: H}),
    "needle_rain": anim(1.3, {0.0: H, 0.05: out_r, 0.12: nr_up, 0.3: nr_shot, 0.42: nr_up, 0.6: nr_shot,
                              0.72: nr_up, 0.9: nr_shot, 1.1: P(nr_shot, b=(8, 0, 0)), 1.3: H}),
    "peri_draw": anim(0.9, {0.0: H, 0.2: pd_low, 0.7: P(pd_low, w=(32, 0, 0), h=(-34, -32, 0)),
                            0.9: P(pd_low, w=(28, 0, 0))}),
    "peri_finish": anim(1.1, {0.0: P(pd_low, w=(28, 0, 0)), 0.18: pf_up, 0.4: P(pf_up, b=(-16, 0, 0)),
                              0.5: pf_down, 0.72: P(pf_down, w=(28, 0, 0)), 0.9: pf_sheath, 1.1: H}),
    "flourish": anim(0.6, {0.0: H, 0.1: P(c2_wind, b=(6, -20, 0)), 0.22: fl_out,
                           0.42: P(fl_out, b=(-2, 16, 0)), 0.6: H}),
}
