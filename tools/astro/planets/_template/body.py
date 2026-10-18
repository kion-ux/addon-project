# -*- coding: utf-8 -*-
"""<惑星> の全身モーション — 雛形。planets/<key>/ にコピーして書き換える。

書き方の説明は planets/_template/README_weapon.md の §8〜、記法は tools/astro/astro_animlib.py の冒頭、
お手本は planets/earth/body.py。

    python3 tools/astro/gen_astro_anim.py --preview <key>.combo1 [--view q34|left|back|"200,-14"]
    python3 tools/astro/gen_astro_anim.py --describe <key>.combo1   # 腕と刃先が実際にどちらを向いたか
    python3 tools/astro/gen_astro_anim.py --check                   # 武器が体に入るコマの一覧

名前はそのまま animation.astro.p.<key>.<名前> になる（'.' は使わない）。スクリプトは body(p, "<key>.<名前>")。
combo1〜3 は通常攻撃の三段で自動で再生される。共通の名前（cast, slam …）をここに書くと、その惑星の時は
こちらが使われる（上書き）。

キー = {秒: 姿勢}。姿勢は P(...) で、書かなかった部位は自然体（H）。前の姿勢を土台にするなら P(前, rA=...)。
  rA / lA  腕。Euler (rx, ry, rz) か aim(向き) か（右腕だけ）wield(blade=刃先の向き, arm=腕の向き | edge=刃の向く側)
  b 体 / w 腰（上半身ごと）/ h 頭 / rL lL 脚 / root 全身の回転 / root_pos 全身の位置 / ground=True 足を地面に
  向きは dirv(f=前, u=上, r=右)。FWD BACK UP DOWN LEFT RIGHT もある。
"""
from __future__ import annotations

from astro_animlib import LEFT, H, P, aim, anim, dirv, wield

# ---- 三段コンボ（右の横薙ぎ → 左下からの斬り上げ → 跳んで振り下ろす） -------------------
# 振りかぶり・振り抜きは arm= で腕の置き場所を決め、当たる瞬間だけ edge= で刃を進む向きへ向けると素直になる
c1_wind = P(b=(0, 35, 0), h=(0, -26, 0),
            rA=wield(blade=dirv(r=1.0, f=-0.3, u=0.1), arm=dirv(r=1.0, u=-0.25, f=0.1)),
            lA=aim(dirv(f=1.0, r=-0.3, u=-0.15)), rL=(12, 0, 6), lL=(-16, 0, -6), ground=True)
c1_hit = P(b=(6, -12, 0), h=(0, 10, 0),
           rA=wield(blade=dirv(f=1.0, r=-0.1), edge=LEFT),
           lA=aim(dirv(f=-0.35, u=-1.0, r=-0.6)), rL=(22, 0, 6), lL=(-30, 0, -6), ground=True)
c1_follow = P(c1_hit, b=(8, -40, 0), h=(0, 30, 0),
              rA=wield(blade=dirv(r=-1.0, f=0.25, u=-0.1), arm=dirv(r=-0.9, f=0.45, u=-0.25)))

c2_wind = P(b=(10, -30, 0), h=(0, 24, 0),
            rA=wield(blade=dirv(r=-0.7, u=-0.6, f=0.45), arm=dirv(f=1.0, u=-0.5, r=-0.2)),
            lA=aim(dirv(f=0.3, u=-1.0, r=0.4)), rL=(-22, 0, 6), lL=(14, 0, -6), ground=True)
c2_hit = P(b=(-6, 22, 0), h=(0, -18, 0),
           rA=wield(blade=dirv(r=0.55, u=0.75, f=0.45), arm=dirv(r=0.6, u=0.25, f=0.75)),
           lA=aim(dirv(f=-0.2, u=-1.0, r=-0.5)), rL=(-26, 0, 6), lL=(18, 0, -6), ground=True)

c3_up = P(b=(-14, 0, 0), h=(-16, 0, 0),
          rA=wield(blade=dirv(u=0.55, f=-0.85), arm=dirv(u=1.0, f=0.15, r=0.25)),
          lA=aim(dirv(u=0.55, f=1.0, r=-0.25)), rL=(-34, 0, 0), lL=(-10, 0, 0), root_pos=(0, 1.8, 0))
c3_hit = P(w=(28, 0, 0), h=(-24, 0, 0),
           rA=wield(blade=dirv(f=1.0, u=-0.22), arm=dirv(f=0.75, u=-0.66)),
           lA=aim(dirv(f=-0.4, u=-1.0, r=-0.5)), rL=(30, 0, 8), lL=(-44, 0, -8), ground=True)

# ---- 技の例: 片手を前へ突き出して放つ ------------------------------------------------
blast = P(w=(8, 0, 0), h=(-6, 0, 0),
          lA=aim(dirv(f=1.0, u=0.1, r=-0.05), twist=60),
          rA=wield(blade=dirv(f=-0.4, u=-0.6, r=0.6), arm=dirv(r=0.7, u=-0.7)),
          rL=(16, 0, 6), lL=(-22, 0, -6), ground=True)

BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.07: c1_wind, 0.17: c1_hit, 0.26: c1_follow,
                         0.36: P(c1_follow, b=(6, -36, 0)), 0.5: H}),
    "combo2": anim(0.5, {0.0: H, 0.08: c2_wind, 0.2: c2_hit, 0.36: P(c2_hit, b=(-8, 28, 0)), 0.5: H}),
    "combo3": anim(0.7, {0.0: H, 0.16: c3_up, 0.3: c3_hit, 0.5: P(c3_hit, w=(26, 0, 0)), 0.7: H}),
    "blast": anim(0.7, {0.0: H, 0.1: blast, 0.5: P(blast, w=(6, 0, 0)), 0.7: H}),
}
