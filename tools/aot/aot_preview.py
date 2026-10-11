# -*- coding: utf-8 -*-
"""モデルを PNG に描いて確かめる（Minecraft 無しで見た目を検証する）。

hyperdim の hd_preview（統合版と同じ回転規則・X 鏡映・発光 texel）で描く。
  python3 tools/aot/aot_preview.py titans     巨人 12 通り（正面・背面）
  python3 tools/aot/aot_preview.py soldiers   調査兵団 10 人
  python3 tools/aot/aot_preview.py gear       着る装備と手に持つもの
出力は build_preview/aot/*.png
"""
from __future__ import annotations

import json
import math
import os
import re
import sys

import aot_common as C
from hd_preview import render, sheet

GEO = C.GEO_DIR
TEX = C.TEX_DIR


class _M:
    """Molang の math.*（角度は度）。"""
    sin = staticmethod(lambda d: math.sin(math.radians(d)))
    cos = staticmethod(lambda d: math.cos(math.radians(d)))
    abs = staticmethod(abs)
    min = staticmethod(min)
    max = staticmethod(max)
    sqrt = staticmethod(math.sqrt)
    pow = staticmethod(math.pow)
    floor = staticmethod(math.floor)
    clamp = staticmethod(lambda v, a, b: max(a, min(b, v)))
    lerp = staticmethod(lambda a, b, t: a + (b - a) * t)
    mod = staticmethod(lambda a, b: a % b)


def molang(expr, env):
    """プレビュー用の小さな Molang 評価（??・math.*・q.*/v.*。三項演算子は扱わない）。"""
    if isinstance(expr, (int, float)):
        return float(expr)
    e = str(expr)
    e = re.sub(r"\b(v|variable)\.(\w+)\s*\?\?\s*(-?[\d.]+)",
               lambda m: f"({env.get('v.' + m.group(2), float(m.group(3)))})", e)
    e = re.sub(r"\b(v|variable)\.(\w+)", lambda m: f"({env.get('v.' + m.group(2), 0.0)})", e)
    e = re.sub(r"\b(q|query)\.(\w+)", lambda m: str(env.get("q." + m.group(2), 0.0)), e)
    e = e.replace("math.", "_M.").replace("&&", " and ").replace("||", " or ")
    try:
        return float(eval(e, {"_M": _M}))
    except Exception:
        return 0.0


def _pose(anim_file, name, t=0.0, env=None):
    """生成したアニメーションの時刻 t の姿勢（Molang も評価する）。"""
    path = os.path.join(C.RP, "animations", anim_file)
    if not os.path.exists(path):
        return {}
    clip = json.load(open(path, encoding="utf-8"))["animations"].get(name, {})
    env = dict(env or {})
    env.setdefault("q.anim_time", t)
    out = {}
    for bone, tracks in clip.get("bones", {}).items():
        e = out.setdefault(bone, {})
        for key in ("rotation", "position"):
            v = tracks.get(key)
            if isinstance(v, dict):
                k = min(v, key=lambda s: abs(float(s) - t))
                v = v[k]
                if isinstance(v, dict):
                    v = v.get("post", v.get("pre"))
            if isinstance(v, list):
                e[key] = [molang(c, env) for c in v]
    return out


def titan_poses(body="muscular", states=("idle", "walk", "attack", "swat", "grab", "eat", "kneel",
                                         "sleep", "dying", "leap", "blind")):
    """巨人の状態ごとの姿勢を横から・正面から描く（回転の向きの確認用）。"""
    from aot_models import titan_metrics
    m = titan_metrics(body)
    from gen_aot_anim import hand_angles
    from aot_common import BODIES as _B
    env = {"v.hip": m["hip"], "v.knee": m["knee"], "v.thigh": m["thigh"], "v.stride": 1.0,
           "q.modified_move_speed": 1.0, "q.modified_distance_moved": 2.0}
    for k, v in hand_angles()[_B.index(body)].items():
        env["v." + k] = v
    g = os.path.join(GEO, f"titan_{body}.geo.json")
    tx = os.path.join(TEX, f"titan_{body}_0.png")
    tiles = []
    for st in states:
        name = f"animation.aot.titan.{st}"
        doc = json.load(open(os.path.join(C.RP, "animations", "aot_entities.animation.json")))["animations"][name]
        t = float(doc.get("animation_length", 1.0)) * (0.55 if st in ("attack", "swat") else 1.0)
        p = _pose("aot_entities.animation.json", name, t, env)
        for yaw in (90, 20):
            tiles.append(render(g, tx, 240, yaw, -8, ss=2, pose=p, margin=0.04))
    sheet(tiles, os.path.join(C.SCRATCH, f"titan_poses_{body}.png"), cols=6)


def titans(views=((180, -6), (0, -6), (225, -14))):
    tiles = []
    for body in C.BODIES:
        for k in range(C.SKINS):
            g = os.path.join(GEO, f"titan_{body}.geo.json")
            t = os.path.join(TEX, f"titan_{body}_{k}.png")
            for yaw, pitch in views[:2] if k else views:
                tiles.append(render(g, t, 300, yaw, pitch, ss=2))
    sheet(tiles, os.path.join(C.SCRATCH, "titans.png"), cols=7)


def faces():
    tiles = []
    for body in C.BODIES:
        for k in range(C.SKINS):
            g = os.path.join(GEO, f"titan_{body}.geo.json")
            t = os.path.join(TEX, f"titan_{body}_{k}.png")
            hide = ["rightArm", "leftArm", "rightLeg", "leftLeg"]
            im = render(g, t, 520, 0, -4, ss=2, hide=hide)
            tiles.append(im.crop((100, 0, 420, 320)))
    sheet(tiles, os.path.join(C.SCRATCH, "titan_faces.png"), cols=6)


def soldiers(pose=None):
    tiles = []
    for key in C.SOLDIERS:
        g = os.path.join(GEO, f"{key}.geo.json")
        t = os.path.join(TEX, f"{key}.png")
        p = _pose("aot_entities.animation.json", pose) if pose else None
        tiles.append(render(g, t, 300, 160, -6, ss=2, pose=p))
        tiles.append(render(g, t, 300, 20, -6, ss=2, pose=p))
    sheet(tiles, os.path.join(C.SCRATCH, "soldiers.png"), cols=6)


def gear():
    tiles = []
    for name in ("wear_jacket", "wear_odm_gear", "wear_boots", "blades", "thunder_spear",
                 "prop_gas_canister", "prop_spare_blades", "prop_journal", "prop_flare_gun"):
        g = os.path.join(GEO, f"{name}.geo.json")
        t = os.path.join(TEX, f"{name}.png")
        for yaw, pitch in ((150, -10), (30, -10)):
            tiles.append(render(g, t, 280, yaw, pitch, ss=2))
    sheet(tiles, os.path.join(C.SCRATCH, "gear.png"), cols=6)


if __name__ == "__main__":
    what = sys.argv[1:] or ["titans", "faces", "soldiers", "gear"]
    for w in what:
        if w.startswith("soldiers:"):
            soldiers(w.split(":", 1)[1])
        elif w.startswith("poses:"):
            titan_poses(w.split(":", 1)[1])
        else:
            globals()[w]()
