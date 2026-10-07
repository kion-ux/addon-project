# -*- coding: utf-8 -*-
"""武器が体にめり込んでいないかを、書き出した全身モーションの全コマで調べる。

hd_scene と同じ規則（回転の向き・bind のずれ・持ち方）でプレイヤーを組み、
アタッチャブルの表面を細かく点で取って、頭・胴・脚・（持っていない側の）腕の箱に
どれだけ入り込むかを測る。両手武器は左の拳と柄の握りの離れ具合も測る。
キーの間は統合版と同じ catmullrom で補間する。

    python3 tools/hyperdim/check_hd_clip.py              # 全武器の一覧
    python3 tools/hyperdim/check_hd_clip.py greataxe -v  # 1 武器のコマごとの内訳

めり込み（LIMIT px 超）か、左手が柄から GAP px 以上離れるモーションがあれば返り値 1。
"""
from __future__ import annotations

import sys

import numpy as np

import gen_hd_anim as GA
import hd_pose as HP
from hd_common import WEAPONS
from hd_scene import skeleton_world

LIMIT = HP.LIMIT
GAP = 2.0            # 拳（4px 角）の中心から柄までこれ以上離れたら「握れていない」
STEP = 0.02


def motions(name):
    """(名前, 長さ, 絶対値のキー, 構え中か, 両手を柄に置くか)。gen_hd_anim が書き出すものと同じ。"""
    out = []
    for anim, (length, frames, use, two) in GA.solved_motions(name).items():
        out.append((anim, length, frames, use, two))
    return out


def run(names, verbose=False):
    GA.prepare(names)
    bad = []
    for name in names:
        clouds = {False: HP.Cloud(GA.HOLDS, name, False, step=0.7, tags=verbose)}
        if GA.use_pose(name):
            clouds[True] = HP.Cloud(GA.HOLDS, name, True, step=0.7, tags=verbose)
        hold = GA.hold_pose(name)
        rows = []
        for anim, length, frames, use, two in motions(name):
            cloud = clouds[use]
            ts = [0.0] if length == 0 else list(np.arange(0.0, length + 1e-6, STEP))
            ts += [float(t) for t in frames]
            worst, wgap = (0.0, None, None, 0.0), (0.0, 0.0)
            for t in sorted(set(round(x, 4) for x in ts)):
                p = {k: tuple(v) for k, v in HP.sample(frames, hold, t).items()}
                d, gap = HP.check(cloud, name, p)
                if not two:
                    gap = 0.0
                if verbose and (d > LIMIT or gap > GAP):
                    (_d, _b, side), parts = HP.penetration(cloud, skeleton_world(HP.pose_of(p)), name, detail=True)
                    top = sorted(parts.items(), key=lambda kv: -kv[1])[:4]  # (部位, キューブ) ごと
                    print(f"    {name:11s} {anim:10s} t={t:5.3f} {d:4.1f}px gap {gap:4.1f}  "
                          + "  ".join(f"{wb}→{bb} {v:.1f}" for (bb, wb), v in top))
                if d > worst[0]:
                    worst = (d, None, None, t)
                if gap > wgap[0]:
                    wgap = (gap, t)
            rows.append((anim, worst, wgap))
            if worst[0] > LIMIT or wgap[0] > GAP:
                bad.append((name, anim, worst, wgap))
        flagged = []
        for a, w, g in rows:
            msg = []
            if w[0] > LIMIT:
                msg.append(f"{w[0]:.1f}px@{w[3]:.2f}")
            if g[0] > GAP:
                msg.append(f"gap {g[0]:.1f}@{g[1]:.2f}")
            if msg:
                flagged.append(f"{a}(" + " ".join(msg) + ")")
        print(f"  {name:11s} {len(rows):2d} motions  " + ("ok" if not flagged else "CLIP: " + ", ".join(flagged)))
    return bad


def main(argv):
    verbose = "-v" in argv
    names = [a for a in argv if not a.startswith("-")] or list(WEAPONS)
    return 1 if run(names, verbose) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
