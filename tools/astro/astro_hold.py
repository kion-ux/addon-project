# -*- coding: utf-8 -*-
"""アストロ・ナノギア — ナノウェポン／コアの「持ち方」（三人称 tp・一人称 fp）。

規則は tools/hyperdim/hd_space.py / hd_holds.py（Mojang 公式サンプルから逆算・検証済み）:
  * 武器空間: 握りの中心 = 原点、刃先（穂先・鎚頭・銃口）= -Z、+Y = 刃の幅（片刃の刃は -Y 側）、
    +X = 刃の平の法線。コアは球の中心 = 原点、+Y = 上。
  * 三人称は「バニラの持ち姿勢」の腕（右腕 rx = -18°、HOLDING_RX）のまま持つ。
    アストロには持ち姿勢の全身モーションが無い（hyperdim と違う）ので、腕は書き換えない。
    世界（体の空間: -Z 前・+Y 上・-X が右）で武器をどちらへ向けるか（frame）と、
    握りの点がメカの篭手の拳に来る位置（item_position）を逆算する。
  * 一人称はカメラ空間（+X 右・+Y 上・+Z 奥、目からの相対）で直接置く（fp_place）。
    手に何か持つと一人称の腕は描かれないので、画面の右下に収まる所へ置く。

メカの篭手（スーツの腕）は素の拳より約 1 単位大きい（各面 0.5 外へ）。握りは拳の中心のままだと
鍔や柄頭が篭手に埋まるので、拳の中心から少し外・下（GRIP_NUDGE）へずらしてある。
武器を作る側は「握りの周り z ∈ [-GRIP_HALF/scale, +GRIP_HALF/scale]（武器空間）は篭手に隠れる」
と思って、鍔をそれより先（-Z）、柄頭をそれより後ろ（+Z）に置く（planets/_template/README_weapon.md）。

公開 API:
  KINDS                         持ち方の種類（DESIGN.md §4.3 の 9 種 + "core"）
  REST_ARM                      三人称の右腕（バニラの持ち姿勢）
  hold(kind, scale=None, anchor=None)   -> {"kind", "arm_r", "tp": {rotation, position, scale},
                                            "fp": {...}, "scale", "anchor", "blade_arm", "flat_arm"}
  blade_in_arm(kind)            武器の -Z（刃先の向き）を右腕の局所座標（腕を下ろした静止姿勢）で
  spec(kind)                    種類ごとの既定値（scale・長さの目安・説明）
  world_point(...)              hd_holds.world_point の再輸出（検証用）

python3 tools/astro/astro_hold.py            全種類の持ち方を代役モデルで描く（build_preview/astro/holds.png）
python3 tools/astro/astro_hold.py sword ...  種類を絞る
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np  # noqa: E402

import astro_common as AC  # noqa: E402,F401  (sys.path に hyperdim と tools を足す)
from hd_holds import (fp_place, frame, frame_x, item_position, item_rotation,  # noqa: E402
                      world_point)
from hd_space import HOLDING_RX, rot  # noqa: E402

KINDS = ("saber", "scepter", "sword", "axe", "hammer", "ring", "crossbow", "trident", "greatsword", "core")
WEAPON_KINDS = KINDS[:-1]

REST_ARM = (HOLDING_RX, 0.0, 0.0)          # バニラの持ち姿勢（右腕 -18°）
GAUNTLET = 1.0                             # 篭手は素の拳より約 1 単位大きい
GRIP_HALF = 2.5                            # 篭手の拳の半幅（握りの前後がここまで隠れる）
GRIP_NUDGE = (-0.35, -0.35, 0.0)           # 握りを拳の中心から外（-X）・下へ（腕の静止座標）


def _n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------------------
#  種類ごとの設計
#    scale   アタッチャブルの縮尺（武器空間 → 手）。武器はこの縮尺で見える大きさを想定して作る
#    length  武器空間での全長の目安（柄頭〜刃先）。代役モデルとドキュメントに使う
#    tp      三人称: fwd = 刃先の向き（体の空間）、up = 武器の +Y を向けたい向き
#            （片刃は -Y が刃なので、up の逆が刃の向く側）、anchor = 握りの点（武器空間）
#    fp      一人称: fwd = 刃先の向き（カメラ空間）、flat = 武器の +X（平）を向けたい向き、
#            at = 握りの点を置く所（目からの相対）、scale
# ---------------------------------------------------------------------------
SPEC = {
    "saber": {
        "ja": "サーベル（片刃・細身。刃は -Y）", "scale": 0.8, "length": 28,
        "tp": {"fwd": (-0.18, -0.42, -0.89), "up": (0.0, 1.0, 0.0)},
        "fp": {"fwd": (-0.40, 0.66, 0.64), "flat": (0.35, 0.05, -1.0), "at": (10.5, -9.0, 14.5),
               "scale": 0.7},
    },
    "sword": {
        "ja": "騎士剣（両刃・幅広）", "scale": 0.8, "length": 32,
        "tp": {"fwd": (-0.12, -0.30, -0.95), "up": (0.0, 1.0, 0.0)},
        "fp": {"fwd": (-0.42, 0.68, 0.60), "flat": (0.35, 0.05, -1.0), "at": (10.5, -9.5, 14.5),
               "scale": 0.66},
    },
    "greatsword": {
        "ja": "片手持ちの大剣（長く重い）", "scale": 0.8, "length": 46,
        "tp": {"fwd": (-0.22, -0.40, -0.89), "up": (0.0, 1.0, 0.0)},
        "fp": {"fwd": (-0.48, 0.72, 0.50), "flat": (0.35, 0.05, -1.0), "at": (11.5, -10.5, 15.0),
               "scale": 0.56},
    },
    "scepter": {
        "ja": "王笏（長柄。頭が -Z）", "scale": 0.8, "length": 34,
        "anchor": (0.0, 0.0, 0.0),
        "tp": {"fwd": (-0.10, 0.62, -0.78), "up": (0.0, 0.78, 0.62)},
        "fp": {"fwd": (-0.30, 0.86, 0.42), "flat": (0.4, 0.0, -1.0), "at": (10.5, -10.5, 15.0),
               "scale": 0.62},
    },
    "axe": {
        "ja": "戦斧（柄の先に斧頭。刃は -Y）", "scale": 0.8, "length": 30,
        "tp": {"fwd": (-0.10, 0.40, -0.91), "up": (0.0, 0.91, 0.40)},
        "fp": {"fwd": (-0.36, 0.80, 0.48), "flat": (0.35, 0.05, -1.0), "at": (10.5, -10.0, 14.5),
               "scale": 0.62},
    },
    "hammer": {
        "ja": "鎚（柄の先に鎚頭。打撃面は ±Y）", "scale": 0.8, "length": 28,
        "tp": {"fwd": (-0.10, 0.40, -0.91), "up": (0.0, 0.91, 0.40)},
        "fp": {"fwd": (-0.36, 0.80, 0.48), "flat": (0.35, 0.05, -1.0), "at": (10.5, -10.0, 14.5),
               "scale": 0.6},
    },
    "ring": {
        "ja": "環刃（YZ 平面の大きな輪。握りは輪の内側の柄、輪の中心は -Z）", "scale": 0.72, "length": 22,
        "tp": {"fwd": (-0.08, 0.10, -1.0), "up": (0.0, 1.0, 0.0)},
        "fp": {"fwd": (-0.30, 0.45, 0.84), "flat": (0.6, 0.0, -1.0), "at": (11.0, -8.5, 15.0),
               "scale": 0.6},
    },
    "crossbow": {
        "ja": "弩（銃口が -Z、弓は ±X に張る、握りは銃床の下）", "scale": 0.75, "length": 22,
        "tp": {"fwd": (-0.06, -0.30, -0.95), "up": (0.0, 1.0, 0.0)},
        "fp": {"fwd": (-0.10, 0.10, 1.0), "flat": (1.0, 0.0, 0.1), "at": (8.5, -6.5, 14.0),
               "scale": 0.6},
    },
    "trident": {
        "ja": "三叉槍（長柄。穂先が -Z、握りは柄の中ほど）", "scale": 0.8, "length": 48,
        "tp": {"fwd": (-0.10, 0.72, -0.69), "up": (0.0, 0.69, 0.72)},
        "fp": {"fwd": (-0.32, 0.86, 0.40), "flat": (0.4, 0.0, -1.0), "at": (10.5, -11.0, 15.0),
               "scale": 0.58},
    },
    "core": {
        "ja": "惑星コア（中心 = 原点。拳の前に浮かせて持つ）", "scale": 0.9, "length": 7,
        # 三人称: 拳の中心から (外, 上, 前) にずらした所へ球の中心を置く（体の空間）
        "tp": {"fwd": (0.0, 0.0, -1.0), "up": (0.0, 1.0, 0.0), "float": (-0.4, 2.2, -5.4)},
        "fp": {"fwd": (-0.25, 0.05, 1.0), "flat": (1.0, 0.0, 0.25), "at": (8.5, -6.0, 15.0),
               "scale": 0.9},
    },
}
assert set(SPEC) == set(KINDS)


def spec(kind: str) -> dict:
    if kind not in SPEC:
        raise KeyError(f"unknown hold kind {kind!r} (one of {', '.join(KINDS)})")
    return SPEC[kind]


def _tf(r, p, s):
    return {"rotation": tuple(round(float(v), 2) for v in r),
            "position": tuple(round(float(v), 2) for v in p), "scale": round(float(s), 3)}


def hold(kind: str, scale: float | None = None, anchor=None, fp_scale: float | None = None,
         tp=None, fp=None) -> dict:
    """種類 kind の持ち方。scale / anchor / tp / fp で既定値を上書きできる（weapon.py の HOLD）。

    返り値:
      arm_r       三人称の右腕（REST_ARM）
      tp / fp     アタッチャブルの hold ボーンに書く {rotation, position, scale}
      blade_arm   武器の -Z を右腕の静止座標で（全身モーションで刃の向きから腕を解くのに使う）
      flat_arm    武器の +X を右腕の静止座標で
    """
    sp = dict(spec(kind))
    if tp:
        sp["tp"] = dict(sp["tp"], **tp)
    if fp:
        sp["fp"] = dict(sp["fp"], **fp)
    s = float(scale if scale is not None else sp["scale"])
    a = tuple(anchor if anchor is not None else sp.get("anchor", (0.0, 0.0, 0.0)))
    arm = REST_ARM
    t = sp["tp"]
    R_world = frame(_n(t["fwd"]), _n(t["up"]))
    ir = item_rotation(arm, R_world)
    if "float" in t:
        # コア: 拳の中心から float（体の空間）だけ離れた所に球の中心を浮かせる
        nudge = rot(*arm).T @ np.asarray(t["float"], float)
        ip = item_position(arm, ir, a, nudge=tuple(nudge), scale=s)
    else:
        ip = item_position(arm, ir, a, nudge=GRIP_NUDGE, scale=s)
    f = sp["fp"]
    fs = float(fp_scale if fp_scale is not None else f.get("scale", s))
    cam_R = frame_x(_n(f["fwd"]), _n(f["flat"]))
    fpd = fp_place(cam_R, f["at"], a, fs)
    R_arm_item = rot(*ir)              # 武器空間 → 腕の局所（静止姿勢）
    return {
        "kind": kind, "arm_r": arm, "scale": s, "anchor": a,
        "tp": _tf(ir, ip, s),
        "fp": _tf(fpd["rotation"], fpd["position"], fs),
        "blade_arm": tuple(float(v) for v in R_arm_item @ np.array([0.0, 0.0, -1.0])),
        "flat_arm": tuple(float(v) for v in R_arm_item @ np.array([1.0, 0.0, 0.0])),
        "up_arm": tuple(float(v) for v in R_arm_item @ np.array([0.0, 1.0, 0.0])),
        "cam_R": cam_R.tolist(),
    }


def blade_in_arm(kind: str, **kw) -> tuple:
    return hold(kind, **kw)["blade_arm"]


# ===========================================================================
#  検証用の代役モデル（種類ごとの大まかな形）と描画
# ===========================================================================
def stand_in(kind: str):
    """種類ごとの代役（形の目安）。astro_weapon の補助で作る。"""
    import astro_weapon as W
    m = W.new_model(f"geometry.astro.standin_{kind}", max_atlas=(512, 512))
    root = W.root_of(m)
    L = SPEC[kind]["length"]
    if kind == "core":
        g = W.form(m, root, 0, "globe")
        W.sphere(g, (0, 0, 0), 2.4, "gem")
        r = W.spin(m, root, "ring", (0, 0, 0))
        W.ring(r, (0, 0, 0), 3.2, 12, (0, 0.5, 0.6), "metal", axis="y")
        return m
    grip = W.form(m, root, 0, "grip")
    AC.octa(grip, (0, 0, 0.6), 1.6, 6.4, "wrap")
    AC.cbox(grip, (0, 0, 4.4), (2.2, 2.2, 1.4), "gold")
    head = W.form(m, root, 1, "head", (0, 0, -3.4))
    if kind in ("sword", "saber", "greatsword"):
        wid = {"saber": 2.2, "sword": 3.6, "greatsword": 5.4}[kind]
        AC.cbox(head, (0, 0, -3.6), (2.4, wid + 3.0, 1.4), "gold")
        blen = L - 9
        AC.cbox(head, (0, -0.4 if kind == "saber" else 0, -4.3 - blen / 2), (0.8, wid, blen), "blade")
        AC.cbox(head, (0, -0.4 - wid / 2 if kind == "saber" else 0, -4.3 - blen / 2), (0.9, 0.5, blen), "edge")
    elif kind in ("scepter", "trident"):
        AC.octa(head, (0, 0, -0.5 - (L * 0.6) / 2), 1.2, L * 0.6, "metal")
        AC.octa(head, (0, 0, 3.5 + 5), 1.2, 10 if kind == "trident" else 4, "metal")
        tip = -0.5 - L * 0.6
        if kind == "trident":
            for y in (-2.2, 0, 2.2):
                AC.cbox(head, (0, y, tip - 3), (0.8, 0.8, 6), "edge")
            AC.cbox(head, (0, 0, tip), (1.0, 5.4, 1.0), "gold")
        else:
            AC.cbox(head, (0, 0, tip - 2.4), (3.6, 3.6, 3.6), "gem", rotation=(0, 0, 45))
    elif kind in ("axe", "hammer"):
        AC.octa(head, (0, 0, -0.5 - (L - 8) / 2), 1.4, L - 8, "metal")
        tip = -0.5 - (L - 8)
        if kind == "axe":
            AC.cbox(head, (0, -3.0, tip + 3.0), (1.0, 6.0, 7.0), "blade")
            AC.cbox(head, (0, -6.1, tip + 3.0), (1.1, 0.5, 7.4), "edge")
        else:
            AC.cbox(head, (0, 0, tip + 2.5), (5.0, 10.0, 5.0), "metal")
            AC.cbox(head, (0, 0, tip + 2.5), (5.4, 1.0, 5.4), "edge")
    elif kind == "ring":
        W.ring(head, (0, 0, -11.5), 8.0, 20, (0, 1.4, 0.8), "blade", axis="x")
        W.ring(head, (0, 0, -11.5), 9.0, 20, (0, 0.6, 0.9), "edge", axis="x")
        AC.cbox(head, (0, 0, -3.4), (1.6, 2.6, 1.0), "gold")
    elif kind == "crossbow":
        AC.cbox(head, (0, 2.6, -6.0), (2.0, 2.2, 16.0), "metal")
        AC.cbox(head, (0, 2.6, -13.0), (16.0, 1.0, 1.4), "blade")
        AC.cbox(head, (0, 3.8, -6.0), (0.4, 0.4, 14.0), "edge")
    return m


def _styles():
    from hd_paint import HDPainter  # noqa: F401
    g = (120, 220, 255)
    return {
        "wrap": {"kind": "wrap", "base": (30, 28, 36), "strap": (80, 110, 200), "skin": (210, 210, 200)},
        "gold": {"kind": "gold", "base": (226, 172, 64), "light": (255, 236, 150), "dark": (150, 96, 28)},
        "blade": {"kind": "blade", "base": (176, 186, 204), "light": (238, 244, 252), "dark": (104, 112, 132)},
        "edge": {"kind": "edge", "glow": g, "emit": 60, "outline": False, "bevel": False},
        "metal": {"kind": "metal", "base": (62, 66, 84), "light": (120, 128, 150), "dark": (34, 36, 48)},
        "gem": {"kind": "gem", "glow": (90, 200, 255), "deep": (20, 60, 140)},
    }


def _write_stand_in(kind, out_dir):
    import astro_weapon as W
    from hd_paint import HDPainter
    m = stand_in(kind)
    m.pack()
    geo = os.path.join(out_dir, f"standin_{kind}.geo.json")
    tex = os.path.join(out_dir, f"standin_{kind}.png")
    m.write(geo)
    p = HDPainter(m.tex_w, m.tex_h, 7)
    p.paint_model(m, _styles())
    p.save(tex)
    W.validate_model(m, kind="core" if kind == "core" else "weapon", quiet=True)
    return geo, tex


def render_hold(geo, tex, kind, h=None, label=None, gauntlet=True):
    """三人称（斜め後ろ・正面）と一人称の 3 枚を横に並べた絵（PIL.Image）。"""
    from PIL import Image, ImageDraw
    import hd_scene as S
    h = h or hold(kind)
    a = {"hold": {"rotation": h["tp"]["rotation"], "position": h["tp"]["position"],
                  "scale": (h["tp"]["scale"],) * 3}}
    pose = {"rightArm": {"rotation": h["arm_r"]}}
    tiles = []
    for yaw, pitch in ((205, -10), (330, -12), (90, -6)):
        tiles.append(S.tp(geo, tex, pose, a, yaw=yaw, pitch=pitch, size=(300, 340), scale=7.0,
                          centre=(0, 15, -4)))
    af = {"hold": {"rotation": h["fp"]["rotation"], "position": h["fp"]["position"],
                   "scale": (h["fp"]["scale"],) * 3}}
    fp = S.fp(geo, tex, af, size=(480, 270))
    fpd = ImageDraw.Draw(fp)
    fpd.line((236, 135, 244, 135), fill=(255, 255, 255))
    fpd.line((240, 131, 240, 139), fill=(255, 255, 255))
    fp = fp.resize((604, 340))
    W_ = 300 * 3 + 604
    out = Image.new("RGB", (W_, 340), (14, 15, 20))
    for i, t in enumerate(tiles):
        out.paste(t, (i * 300, 0))
    out.paste(fp, (900, 0))
    d = ImageDraw.Draw(out)
    d.text((8, 6), label or kind, fill=(255, 255, 255))
    return out


def main(argv=None):
    from PIL import Image
    argv = list(sys.argv[1:] if argv is None else argv)
    kinds = [k for k in argv if k in KINDS] or list(KINDS)
    out_dir = os.path.join(AC.SCRATCH, "holds")
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for k in kinds:
        geo, tex = _write_stand_in(k, out_dir)
        h = hold(k)
        rows.append(render_hold(geo, tex, k, h, f"{k}  tp={h['tp']['rotation']} {h['tp']['position']}"))
        print(f"  {k:10s} tp rot {h['tp']['rotation']} pos {h['tp']['position']} s {h['tp']['scale']}"
              f" | fp rot {h['fp']['rotation']} pos {h['fp']['position']} s {h['fp']['scale']}")
    W_ = rows[0].size[0]
    sheet = Image.new("RGB", (W_, 340 * len(rows)), (14, 15, 20))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, i * 340))
    path = os.path.join(AC.SCRATCH, "holds.png" if len(kinds) == len(KINDS) else f"holds_{'_'.join(kinds)}.png")
    sheet.save(path)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
