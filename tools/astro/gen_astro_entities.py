# -*- coding: utf-8 -*-
"""アストロ・ナノギア — 宇宙からの侵略者（敵）・投射物・ホログラム標的・ダメージ表示。

書き出すもの（エンティティごと）:
  BP  entities/<id>.json                      振る舞い（体力・移動・AI・プロパティ・イベント）
  BP  loot_tables/entities/astro_<id>.json    ドロップ
  BP  spawn_rules/<id>.json                   自然スポーン（ドローン・センチネルのみ）
  RP  entity/<id>.entity.json                 クライアントエンティティ（材質・アニメ・描画）
  RP  models/entity/astro_<id>.geo.json       ジオメトリ geometry.astro.<id>
  RP  textures/entity/astro/<id>.png          テクスチャ（AstroPainter のセル塗り。発光は entity_emissive_alpha）
  RP  animations/astro_entities.animation.json
  RP  animation_controllers/astro_entities.animation_controllers.json
  RP  render_controllers/astro_entities.render_controllers.json

エンティティ:
  astro:void_drone       ヴォイド・ドローン   浮遊する装甲球。距離を取ってボルトを撃つ（invaders.js）
  astro:void_sentinel    ヴォイド・センチネル 逆関節の二足機兵。近接（バニラ AI）＋地を走る衝撃波（invaders.js）
  astro:nemesis          虚星王 ネメシス      ボス。浮遊する黒い星の機械。全ての攻撃は invaders.js
  astro:hologram_target  ホログラム標的       倒れない練習台（family astro_target）
  astro:void_bolt        ドローンのボルト（minecraft:projectile）
  astro:dmg_text         ダメージ数字の名札（空のジオメトリ、2 秒で消える）

スクリプトとの約束（packs/astro_BP/scripts/invaders.js）:
  プロパティ astro:mode（int）… アニメの状態。0 = 平常
     ドローン   1 溜め / 2 発射
     センチネル 1 振りかぶり（衝撃波の予告）/ 2 叩きつけ
     ネメシス   1 溜め / 2 光線 / 3 召喚 / 4 隕石 / 5 黒孔 / 6 突進 / 7 咆哮（第二形態へ）
  プロパティ astro:phase（int、ネメシスのみ）… 1 / 2
  イベント astro:engage / astro:disengage（ドローン: 交戦中は徘徊をやめる）

  python3 tools/astro/gen_astro_entities.py             生成
  python3 tools/astro/gen_astro_entities.py --preview   + build_preview/astro/enemy_<id>.png
  python3 tools/astro/gen_astro_entities.py --test      + invaders.js の Node スモークテスト
  （--only drone,sentinel … で絞れる。プレビューとテストは生成物を読む）
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import astro_common as AC  # noqa: E402
from astro_common import (BP, RP, SCRATCH, beam, box, cbox, line3, mat_cube,  # noqa: E402,F401
                          polyline, rbox, ring, write_json)
from astro_data import ENEMIES, NS  # noqa: E402
from astro_paint import EMI, SOFT, WHITE, AstroPainter, hash2, hexc, mix, shade, smooth  # noqa: E402
from mcmodel import Model  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

GEO_DIR = os.path.join(RP, "models", "entity")
TEX_DIR = os.path.join(RP, "textures", "entity", "astro")
ANIM_FILE = os.path.join(RP, "animations", "astro_entities.animation.json")
CTRL_FILE = os.path.join(RP, "animation_controllers", "astro_entities.animation_controllers.json")
RC_FILE = os.path.join(RP, "render_controllers", "astro_entities.render_controllers.json")

ENTITY_FMT = "1.20.80"

# ===========================================================================
#  配色（侵略者は紫黒の装甲・マゼンタの眼・菫色の噴射）
# ===========================================================================
HULL = (54, 40, 78)
HULL_L = (124, 100, 166)
HULL_D = (22, 15, 36)
HULL2 = (92, 80, 122)
FRAME = (36, 33, 48)
MAG = (255, 58, 206)          # 眼・発光（マゼンタ）
MAG_L = (255, 210, 246)
MAG_D = (110, 8, 94)
VIO = (170, 76, 255)          # 噴射・ボスの発光（菫）
VIO_L = (230, 204, 255)
VIO_D = (56, 14, 112)
SILVER = (170, 162, 200)
CYAN = (90, 232, 255)         # ホログラム
CYAN_L = (220, 255, 255)
CYAN_D = (10, 70, 96)


# ===========================================================================
#  ペインタ: AstroPainter に侵略者用の素材を足す
# ===========================================================================
class InvaderPainter(AstroPainter):
    """追加の kind:
      iris        眼の虹彩（放射状の筋・同心の明暗・全発光）
      singularity 特異点の瞳（中心が真黒、縁に白熱の降着円盤、外へ紫の滲み）
      holo        ホログラムの線（加算合成用: アルファは常に 255、明るさ = 不透明さ）
      holo_fill   ホログラムの面（暗いシアンに走査線と六角の格子）
      scale       鱗状の黒い装甲（ボスの外殻。発光するひびの継ぎ目）
    """

    def _uv(self, x, y, c):
        w, h = c["w"], c["h"]
        return (x + 0.5) / w * 2 - 1, (y + 0.5) / h * 2 - 1

    def k_iris(self, x, y, st, c):
        u, v = self._uv(x, y, c)
        r = math.hypot(u, v)
        glow = hexc(st["glow"])
        lt = hexc(st.get("light", mix(glow, WHITE, 0.7)))
        dp = hexc(st.get("deep", shade(glow, 0.3)))
        if r > 1.0:
            return shade(dp, 0.6), SOFT
        a = math.atan2(v, u)
        streak = 0.5 + 0.5 * math.sin(a * st.get("streaks", 11) + r * 6)
        col = mix(lt, glow, smooth(0.0, 0.55, r))
        col = mix(col, dp, smooth(0.55, 1.0, r) * 0.8)
        col = mix(col, shade(col, 0.62), streak * 0.35 * smooth(0.2, 0.9, r))
        if 0.62 < r < 0.7:
            col = mix(col, lt, 0.5)
        if abs(u + 0.32) < 0.12 and abs(v + 0.36) < 0.1:
            col = mix(col, WHITE, 0.8)
        return col, EMI

    def k_singularity(self, x, y, st, c):
        u, v = self._uv(x, y, c)
        r = math.hypot(u, v)
        glow = hexc(st["glow"])
        R0 = st.get("hole", 0.5)
        if r < R0:
            return (4, 0, 10), 255
        if r < R0 + 0.12:
            return mix(WHITE, glow, (r - R0) / 0.12 * 0.6), EMI
        a = math.atan2(v, u)
        swirl = 0.5 + 0.5 * math.sin(a * 3 + r * 14)
        col = mix(glow, shade(glow, 0.25), smooth(R0 + 0.1, 1.0, r))
        col = mix(col, WHITE, swirl * 0.25 * (1 - smooth(R0, 1.0, r)))
        return col, (EMI if r < 0.8 else 90)

    def k_holo(self, x, y, st, c):
        glow = hexc(st.get("glow", CYAN))
        lt = hexc(st.get("light", CYAN_L))
        w, h = c["w"], c["h"]
        across = (y / max(1, h - 1)) if w >= h else (x / max(1, w - 1))
        S = min(w, h)
        t = abs(across - 0.5) * 2
        col = mix(lt, glow, smooth(0.0, 0.9, t)) if S > 2 else mix(lt, glow, 0.4)
        k = st.get("k", 1.0)
        if (x + y + c["key"]) % 7 == 0:
            k *= 0.7
        return shade(col, k), 255

    def k_holo_fill(self, x, y, st, c):
        glow = hexc(st.get("glow", CYAN))
        k = st.get("k", 0.22)
        col = shade(glow, k)
        if y % 3 == 0:
            col = shade(glow, k * 1.9)
        q = (x * 0.577 + y) % 6
        if q < 0.6 or (x % 7 == 0):
            col = shade(glow, k * 1.6)
        return col, 255

    def k_scale(self, x, y, st, c):
        base = hexc(st["base"])
        glow = hexc(st.get("glow", VIO))
        lt = hexc(st.get("light", mix(base, WHITE, 0.3)))
        per = st.get("cell", 7)
        row = y // per
        xx = x + (per // 2 if row % 2 else 0)
        cx = xx % per
        cy = y % per
        col = mix(lt, base, smooth(0, per * 0.7, cy))
        if cy == per - 1 or cx == 0:
            if hash2(xx // per, row, c["seed"]) > 0.72:
                return mix(glow, WHITE, 0.2), SOFT
            return shade(base, 0.45), 255
        if cy == 0:
            col = mix(col, WHITE, 0.18)
        return col, 255


def inv_styles():
    """侵略者（ドローン・センチネル・ボス）の素材一式。"""
    hull = {"kind": "armor", "base": HULL, "light": HULL_L, "dark": HULL_D, "line": (10, 6, 18),
            "groove": (14, 9, 24)}
    hull2 = {"kind": "armor", "base": HULL2, "light": mix(HULL2, WHITE, 0.4), "dark": shade(HULL2, 0.6),
             "line": (18, 12, 28), "groove": (30, 22, 44)}
    st = {
        "hull": hull,
        "hull_p": dict(hull, panel=0),
        "hull2": hull2,
        "hull2_p": dict(hull2, panel=0, sheen=False),
        "hull_b": {"kind": "armor", "base": shade(HULL, 0.7), "light": shade(HULL_L, 0.75),
                   "dark": shade(HULL_D, 0.8), "panel": 0, "sheen": False, "line": (8, 4, 14)},
        "frame": {"kind": "frame", "base": FRAME, "light": (88, 82, 110), "line": (10, 8, 16)},
        "inner": {"kind": "inner", "base": (24, 18, 34), "glow": MAG, "line": (10, 6, 16),
                  "outline_k": 0.5, "bevel": False, "seam": 0.12},
        "chrome": {"kind": "chrome", "base": SILVER, "line": (40, 34, 56)},
        "trim": {"kind": "trim", "base": (150, 140, 186), "light": (238, 232, 255),
                 "dark": (78, 68, 108), "line": (28, 22, 42)},
        "glow": {"kind": "glowline", "glow": MAG, "light": MAG_L, "bevel": False, "outline": False},
        "glow_soft": {"kind": "glowline", "glow": MAG, "light": MAG_L, "bevel": False,
                      "outline": False, "emit": SOFT},
        "glow_v": {"kind": "glowline", "glow": VIO, "light": VIO_L, "bevel": False, "outline": False},
        "glow_vs": {"kind": "glowline", "glow": VIO, "light": VIO_L, "bevel": False,
                    "outline": False, "emit": SOFT},
        "eye": {"kind": "iris", "glow": MAG, "light": MAG_L, "deep": MAG_D, "bevel": False,
                "outline": False},
        "eye_v": {"kind": "iris", "glow": VIO, "light": VIO_L, "deep": VIO_D, "bevel": False,
                  "outline": False, "streaks": 17},
        "pupil": {"kind": "singularity", "glow": MAG, "bevel": False, "outline": False, "hole": 0.42},
        "pupil_v": {"kind": "singularity", "glow": (214, 120, 255), "bevel": False, "outline": False,
                    "hole": 0.48},
        "lens": {"kind": "visor", "glow": MAG, "light": MAG_L, "deep": MAG_D, "line": MAG_D,
                 "bevel": False},
        "visor": {"kind": "visor", "glow": MAG, "light": MAG_L, "deep": MAG_D, "line": MAG_D,
                  "bevel": False, "emit": 12},
        "vent": {"kind": "vent", "base": (34, 28, 46), "glow": MAG, "deep": MAG_D, "line": (10, 6, 16)},
        "vent_v": {"kind": "vent", "base": (30, 26, 44), "glow": VIO, "deep": VIO_D, "line": (10, 6, 16)},
        "thruster": {"kind": "thruster", "base": (52, 46, 68), "glow": VIO, "light": WHITE,
                     "deep": VIO_D, "line": (12, 8, 20), "bevel": False},
        "thruster_b": {"kind": "thruster", "base": (52, 46, 68), "glow": VIO, "light": WHITE,
                       "deep": VIO_D, "line": (12, 8, 20), "bevel": False, "faces": ("south",)},
        "flame": {"kind": "flame", "glow": VIO, "light": VIO_L, "deep": VIO_D, "bevel": False,
                  "outline": False},
        "void": {"kind": "void", "base": (8, 4, 18), "glow": VIO, "nebula": MAG, "outline": False,
                 "bevel": False},
        "dark": {"kind": "dark", "base": (22, 17, 32), "glow": VIO, "line": (4, 2, 8)},
        "dark2": {"kind": "dark", "base": (34, 28, 46), "glow": MAG, "line": (6, 4, 10)},
        "scale": {"kind": "scale", "base": (30, 24, 42), "light": (70, 60, 92), "glow": VIO,
                  "line": (6, 4, 10)},
        "crystal": {"kind": "crystal", "base": (128, 78, 200), "glow": VIO, "line": (40, 10, 70)},
        "energy": {"kind": "energy", "glow": MAG, "light": MAG_L, "outline": False, "bevel": False},
        "energy_v": {"kind": "energy", "glow": VIO, "light": VIO_L, "outline": False, "bevel": False},
        "blade": {"kind": "blade", "base": (120, 112, 150), "light": (226, 220, 248),
                  "dark": (60, 54, 84), "line": (20, 16, 30), "glint_period": 16},
        "edge": {"kind": "edge", "glow": MAG, "emit": 30, "outline": False, "bevel": False},
        "hazard": {"kind": "decal", "decal": "hazard", "c1": (210, 48, 168), "c2": (24, 16, 34),
                   "under": hull2},
        "serial": {"kind": "decal", "decal": "serial", "text": "VX-07", "color": MAG_L, "emit": SOFT,
                   "under": dict(hull, panel=0)},
        "lights": {"kind": "decal", "decal": "lights", "count": 3, "color": MAG,
                   "under": dict(hull2, panel=0)},
        "black": {"kind": "flat", "base": (6, 3, 12), "outline": False, "bevel": False},
        # ネメシス: 黒い装甲（照りの強い縁で形を読ませる）と、割れ目から光る虚空
        "nem_plate": {"kind": "armor", "base": (38, 28, 56), "light": (118, 98, 160), "dark": (14, 9, 24),
                      "line": (6, 3, 12), "groove": (12, 6, 22), "bolts": False, "bevel_hi": 0.4},
        "nem_plate2": {"kind": "armor", "base": (58, 44, 86), "light": (150, 128, 196), "dark": (20, 14, 34),
                       "line": (8, 4, 14), "groove": (24, 14, 40), "bolts": False, "bevel_hi": 0.4,
                       "stripe": {"dir": "h", "period": 12, "width": 1, "color": VIO, "glow": True,
                                  "emit": 60, "offset": 9}},
        "spine": {"kind": "armor", "base": (34, 26, 50), "light": (104, 86, 146), "dark": (12, 8, 22),
                  "line": (6, 3, 12), "panel": 0, "bevel_hi": 0.45},
        "void_core": {"kind": "void", "base": (40, 12, 84), "glow": (200, 96, 255), "nebula": (255, 80, 210),
                      "outline": False, "bevel": False},
    }
    return st


def holo_styles():
    st = inv_styles()
    base = {"kind": "armor", "base": (40, 52, 66), "light": (110, 136, 160), "dark": (18, 24, 32),
            "line": (8, 12, 18)}
    st.update({
        "pbase": base,
        "pbase2": {"kind": "armor", "base": (70, 84, 100), "light": (150, 170, 190), "dark": (34, 42, 52),
                   "line": (12, 16, 24)},
        "pframe": {"kind": "frame", "base": (34, 40, 50), "light": (90, 104, 120), "line": (10, 12, 16)},
        "pglow": {"kind": "glowline", "glow": CYAN, "light": CYAN_L, "bevel": False, "outline": False},
        "plens": {"kind": "iris", "glow": CYAN, "light": CYAN_L, "deep": CYAN_D, "bevel": False,
                  "outline": False, "streaks": 9},
        "pvent": {"kind": "vent", "base": (30, 36, 46), "glow": CYAN, "deep": CYAN_D, "line": (8, 10, 14)},
        "phazard": {"kind": "decal", "decal": "hazard", "c1": (240, 200, 60), "c2": (26, 30, 36),
                    "under": base},
        "pserial": {"kind": "decal", "decal": "serial", "text": "TGT-01", "color": CYAN_L, "emit": SOFT,
                    "under": dict(base, panel=0)},
        "holo": {"kind": "holo", "glow": CYAN, "light": CYAN_L, "bevel": False, "outline": False, "k": 0.62},
        "holo_dim": {"kind": "holo", "glow": CYAN, "light": CYAN_L, "bevel": False, "outline": False,
                     "k": 0.36},
        "holo_red": {"kind": "holo", "glow": (255, 60, 70), "light": (255, 170, 170), "bevel": False,
                     "outline": False, "k": 0.7},
        "holo_fill": {"kind": "holo_fill", "glow": CYAN, "bevel": False, "outline": False, "k": 0.12},
    })
    return st


# ===========================================================================
#  形の補助
# ===========================================================================
def _inset(cubes, axis_i, d):
    """重なる箱の、軸方向の面を d だけ引っ込める（同一平面の面が重なると実機でちらつく）。"""
    for c in cubes:
        c.size[axis_i] = round(c.size[axis_i] - d, 3)
        c.origin[axis_i] = round(c.origin[axis_i] + d / 2, 3)
    return cubes


def bevel(bone, centre, size, style, cut=0.5, axis="z", **kw):
    """astro_common.bevel（45° の面取り 6 個）。十字の 2 個目と稜の 4 本の軸方向の面を少し引っ込める。"""
    out = AC.bevel(bone, centre, size, style, cut=cut, axis=axis, **kw)
    i = AC.AX[axis]
    _inset(out[1:2], i, 0.04)
    _inset(out[2:], i, 0.08)
    return out


def chamfer(bone, centre, size, style, cut=0.5, axis="z", **kw):
    out = AC.chamfer(bone, centre, size, style, cut=cut, axis=axis, **kw)
    _inset(out[1:], AC.AX[axis], 0.04)
    return out


def octa(bone, centre, w, length, style, axis="z", **kw):
    out = AC.octa(bone, centre, w, length, style, axis=axis, **kw)
    _inset(out[1:], AC.AX[axis], 0.04)
    return out


def ball(bone, centre, r, style, **kw):
    """角を落とした球（7 個: 中心の立方体 + 3 方向の板 + 45° の板）。astro_weapon.sphere と同じ比率。"""
    d = 2 * r
    out = [cbox(bone, centre, (d * 0.66,) * 3, style, **kw)]
    for i in range(3):
        size = [d * 0.46] * 3
        size[i] = d
        out.append(cbox(bone, centre, size, style, **kw))
    for i, rr in enumerate(((45, 0, 0), (0, 45, 0), (0, 0, 45))):
        size = [d * 0.66] * 3
        size[i] = d * 0.86
        out.append(rbox(bone, centre, size, style, rot=rr, **kw))
    return out


def globe(bone, centre, r, n, style, styles=None, sy=1.0, caps=False, **kw):
    """横に輪切りした八角柱を積んだ球（n 段 × 6 個）。styles を渡すと段ごとに塗り分け。"""
    out = []
    H = 2 * r * sy
    t = H / n
    for i in range(n):
        dy = -H / 2 + t * (i + 0.5)
        rr = math.sqrt(max(0.0, r * r - (dy / sy) ** 2)) * 1.05
        w = 2 * rr
        c = (centre[0], centre[1] + dy, centre[2])
        st = styles[i] if styles else style
        if caps and i in (0, n - 1):      # 上下の端の段は 2 個の段々の面取り（数を節約）
            out += chamfer(bone, c, (w, t + 0.02, w), st, cut=w * 0.2, axis="y", **kw)
        else:
            out += bevel(bone, c, (w, t + 0.02, w), st, cut=w * 0.293, axis="y", **kw)
    return out


def V(*a):
    return np.array(a, float)


def unit(v):
    v = np.asarray(v, float)
    return v / (np.linalg.norm(v) or 1.0)


def slab(bone, p0, p1, w, t, normal, style, extend=0.0, **kw):
    """p0→p1 の板（幅 w・厚み t、厚みの向き = normal）。line3 の別名（沈め無し）。"""
    return line3(bone, p0, p1, normal, w, t, style, sink=0.0, extend=extend, **kw)


def spike(bone, p0, p1, w0, w1, n, style, normal=None, **kw):
    """p0→p1 へ先細りする角柱の列（n 区間）。トゲ・脚・触手に。"""
    p0, p1 = V(*p0), V(*p1)
    out = []
    for i in range(n):
        a = p0 + (p1 - p0) * (i / n)
        b = p0 + (p1 - p0) * ((i + 1) / n)
        w = w0 + (w1 - w0) * ((i + 0.5) / n)
        if normal is None:
            out.append(beam(bone, a, b, w, w, style, extend=0.3, **kw))
        else:
            out.append(slab(bone, a, b, w, w * 0.6, normal, style, extend=0.3, **kw))
    return out


def fit_density(m, base, max_atlas, ks=(2.0, 1.75, 1.5, 1.25, 1.0, 0.85, 0.75, 0.6, 0.5)):
    """できるだけ細かく、max_atlas に収まる最大の倍率で UV を詰める（astro_weapon._density と同じ探索）。"""
    m.max_atlas = tuple(max_atlas)
    orig = {id(c): (c.uv_scale or base) for c in m.all_cubes()}
    for k in ks:
        for c in m.all_cubes():
            c.uv_scale = max(1, int(round(orig[id(c)] * k)))
            c._scale = c.uv_scale
            c.uv = None
        m.uv_scale = max(1, int(round(base * k)))
        try:
            m.pack()
            m.texel_k = k
            return m
        except ValueError:
            continue
    raise ValueError(f"{m.identifier}: does not fit in {max_atlas}")


# ===========================================================================
#  ヴォイド・ドローン（HP 20）
#  直径 12 の装甲球。正面（-Z）にマゼンタの単眼、X 字に開く 4 枚のヒレと推進ポッド、
#  下面の推進ノズル、眼の下の双連装の発振器、後ろへ流れる触角。
# ===========================================================================
DRONE_C = (0.0, 10.0, 0.0)
DRONE_R = 6.2
DRONE_FINS = (40.0, 140.0, 220.0, 320.0)       # 正面から見た角度（+X から反時計回り）


def build_drone():
    m = Model(f"geometry.{NS}.void_drone", uv_scale=4, visible_bounds=(2.6, 2.4), vb_offset=(0, 0.7, 0),
              max_atlas=(512, 512))
    cx, cy, cz = DRONE_C
    R = DRONE_R
    root = m.bone("root", (0, 0, 0))
    body = m.bone("body", DRONE_C, parent="root")
    # --- 装甲球: 少し平たい 6 段の八角。上下の段は暗く、中央は明るい帯 ------
    globe(body, DRONE_C, R, 6, "hull", styles=["hull_b", "hull_p", "hull2_p", "hull2_p", "hull_p", "hull_b"],
          sy=0.9, caps=True)
    # 赤道の帯（眼の左右から後ろへ回る）と側面の排気口
    ring(body, DRONE_C, R + 0.3, 9, (0, 0.7, 1.1), "trim", axis="y", a0=56, a1=304)
    for s in (-1, 1):
        cbox(body, (s * (R + 0.5), cy - 1.6, cz + 0.6), (0.5, 1.8, 4.0), "vent")
        cbox(body, (s * (R + 0.42), cy + 1.5, cz + 0.6), (0.4, 0.45, 3.6), "glow_soft")
    # --- 眼の上: V 字の兜（怒った眉）と背のトサカ ------------------------
    brow = m.bone("brow", (0, cy + 3.8, -3.0), parent="body")
    for s in (-1, 1):
        rbox(brow, (s * 2.7, cy + 4.15, -4.55), (4.6, 1.2, 3.4), "hull2", rot=(34, s * 16, s * 19))
        rbox(brow, (s * 2.75, cy + 4.6, -6.0), (4.2, 0.45, 0.5), "glow", rot=(34, s * 16, s * 19))
        rbox(brow, (s * 4.9, cy + 2.4, -4.2), (1.4, 2.6, 2.8), "hull", rot=(10, s * -30, s * -12))
    crest = m.bone("crest", (0, cy + 5.4, 0), parent="body")
    polyline(crest, [V(0, cy + 4.6, -4.0), V(0, cy + 6.2, -0.6), V(0, cy + 6.5, 3.4), V(0, cy + 5.6, 7.6)],
             [1.8, 1.6, 1.0], [1.6, 1.8, 1.2], "hull")
    polyline(crest, [V(0, cy + 5.45, -3.4), V(0, cy + 7.05, -0.4), V(0, cy + 7.35, 3.3)],
             [0.5, 0.45], [0.4, 0.4], "glow", overlap=0.1)
    for s in (-1, 1):                    # トサカ脇の小さな背ビレ
        slab(crest, V(s * 1.0, cy + 6.0, 0.4), V(s * 2.2, cy + 7.6, 4.8), 1.6, 0.5, V(1, 0.3, 0), "hull2")
    # --- 眼: 銀の縁・暗い鏡筒・虹彩・瞳孔・四枚の瞼 -----------------------
    eye = m.bone("eye", (0, cy, -R), parent="body")
    ring(eye, (0, cy, -R - 0.05), 3.6, 10, (0, 1.0, 1.7), "trim", axis="z", phase=18)
    bevel(eye, (0, cy, -R + 0.3), (6.4, 6.4, 1.8), "frame", cut=1.9, axis="z")
    glow_b = m.bone("fx_eye_glow", (0, cy, -R - 0.6), parent="eye")
    cbox(glow_b, (0, cy, -R - 0.55), (5.0, 5.0, 0.4), "eye", uv_scale=8)
    cbox(glow_b, (0, cy, -R - 0.8), (2.2, 2.2, 0.3), "pupil", uv_scale=10)
    ring(eye, (0, cy, -R - 0.75), 2.62, 8, (0, 0.35, 0.3), "glow_soft", axis="z", phase=22.5)
    lids = m.bone("lids", (0, cy, -R), parent="eye")
    for k, (dx, dy) in enumerate(((0, 1), (0, -1), (1, 0), (-1, 0))):
        rot = (dy * -18, dx * -18, 0)
        sz = (4.4, 1.1, 1.5) if dy else (1.1, 4.4, 1.5)
        rbox(lids, (dx * 3.6, cy + dy * 3.6, -R - 0.6), sz, "hull2", rot=rot)
    # --- 下面: 推進ノズルと炎 ---------------------------------------------
    under = m.bone("under", (0, cy - R, 0), parent="body")
    octa(under, (0, cy - R * 0.9 + 0.1, 0.8), 4.4, 1.6, "frame", axis="y")
    cbox(under, (0, cy - R * 0.9 - 0.75, 0.8), (3.0, 0.4, 3.0), "thruster", rotation=(0, 45, 0))
    flame = m.bone("fx_flame", (0, cy - R * 0.9 - 0.9, 0.8), parent="under")
    cbox(flame, (0, cy - R * 0.9 - 2.7, 0.8), (1.8, 3.6, 1.8), "flame", rotation=(0, 45, 0))
    # 眼の下の双連装の発振器（ボルトの砲口）
    gun = m.bone("cannon", (0, cy - 3.6, -3.5), parent="body")
    rbox(gun, (0, cy - 4.0, -3.6), (4.8, 1.8, 3.4), "hull", rot=(-12, 0, 0))
    for s in (-1, 1):
        octa(gun, (s * 1.45, cy - 4.2, -6.2), 1.25, 4.4, "frame", axis="z")
        cbox(gun, (s * 1.45, cy - 4.2, -8.45), (0.8, 0.8, 0.3), "glow")
    # 後部の推進器（後ろ向きの小ノズル）と、後ろへ流れる二本の触角
    octa(body, (0, cy - 0.8, R * 0.95 + 0.3), 3.4, 1.8, "frame", axis="z")
    cbox(body, (0, cy - 0.8, R * 0.95 + 1.25), (2.2, 2.2, 0.2), "thruster_b")
    for s in (-1, 1):
        spike(body, (s * 2.2, cy + 3.6, 4.0), (s * 4.2, cy + 6.6, 10.6), 0.9, 0.35, 3, "frame")
        cbox(body, (s * 4.2, cy + 6.6, 10.6), (0.5, 0.5, 1.4), "glow", rotation=(-25, s * 15, 0))
    # --- 4 枚のヒレ（X 字。根元のポッド → 後ろへ反る二段の刃 → 光る前縁） ---
    for i, ang in enumerate(DRONE_FINS):
        a = math.radians(ang)
        d = V(math.cos(a), math.sin(a), 0.0)              # 外向き（正面から見た向き）
        t = V(-math.sin(a), math.cos(a), 0.0)             # 正面から見た接線
        root_p = V(*DRONE_C) + d * (R * 0.82) + V(0, 0, 1.4)
        fb = m.bone(f"fx_fin_{i}", tuple(np.round(root_p, 3)), parent="body")
        pod1 = root_p + d * 2.6
        octa(fb, tuple((root_p + pod1) / 2), 2.6, 2.6, "frame", axis="z")
        cbox(fb, tuple(pod1 + V(0, 0, 1.6)), (1.7, 1.7, 0.3), "thruster_b")
        tip_b = m.bone(f"fx_fin_{i}_tip", tuple(np.round(pod1, 3)), parent=f"fx_fin_{i}")
        # 刃の面: 正面から 45° 見える向き（法線 = 接線と後ろの間）
        n = unit(t * 0.7 + V(0, 0, 0.7))
        q0 = pod1 + d * 0.6
        q1 = pod1 + d * 4.6 + V(0, 0, 1.6)
        q2 = pod1 + d * 8.4 + V(0, 0, 5.4)
        q3 = pod1 + d * 10.2 + V(0, 0, 9.6)
        slab(tip_b, q0, q1, 4.2, 0.8, n, "hull2", extend=0.6)
        slab(tip_b, q1, q2, 3.2, 0.7, n, "hull", extend=0.6)
        slab(tip_b, q2, q3, 1.8, 0.6, n, "hull", extend=0.4)
        e = 1.0 if np.dot(np.cross(n, unit(q1 - q0)), V(0, 0, -1)) > 0 else -1.0
        side = unit(np.cross(n, unit(q1 - q0))) * e
        slab(tip_b, q0 + side * 2.0, q1 + side * 1.5, 0.4, 0.95, n, "glow_soft", extend=0.3)
        slab(tip_b, q1 + side * 1.5, q3 + side * 0.6, 0.4, 0.8, n, "glow", extend=0.3)
    fit_density(m, 4, (512, 512))
    return m


# ===========================================================================
#  ヴォイド・センチネル（HP 44、全高 2.6 ブロック）
#  逆関節（鳥脚）の二足機兵。猫背の胴・巨大な肩・横一文字の単眼スリット・前腕の刃。
#  ボーン: root / hips → torso → head, shoulder_* → arm_* → forearm_* → blade_* /
#          thigh_* → shin_* → ankle_* → foot_*（_r = 右 = -X、_l = 左 = +X）
# ===========================================================================
SENT_HIP = (5.0, 22.5, 0.6)
SENT_KNEE = (5.6, 14.0, -4.2)
SENT_ANKLE = (5.6, 6.2, 3.2)
SENT_BALL = (5.6, 1.7, 0.2)
SENT_TORSO_LEAN = 12.0


def build_sentinel():
    m = Model(f"geometry.{NS}.void_sentinel", uv_scale=3, visible_bounds=(3.6, 3.6), vb_offset=(0, 1.4, 0),
              max_atlas=(1024, 1024))
    m.bone("root", (0, 0, 0))
    # ---- 脚 ---------------------------------------------------------------
    for side, s in (("r", -1), ("l", 1)):
        H = V(s * SENT_HIP[0], *SENT_HIP[1:])
        K = V(s * SENT_KNEE[0], *SENT_KNEE[1:])
        A = V(s * SENT_ANKLE[0], *SENT_ANKLE[1:])
        F = V(s * SENT_BALL[0], *SENT_BALL[1:])
        out = V(s, 0, 0)
        th = m.bone(f"thigh_{side}", tuple(H), parent="root")
        beam(th, H + V(0, 0.8, 0), K, 4.4, 5.0, "hull", extend=1.0)
        d = unit(K - H)
        slab(th, H + d * 1.5 + out * 2.4, K - d * 1.2 + out * 2.4, 3.8, 0.8, out, "hull2")
        slab(th, H + d * 2.2 + out * 2.9, K - d * 2.5 + out * 2.9, 0.6, 0.3, out, "glow_soft")
        beam(th, H + V(0, -1, 2.4) - out * 1.0, K + V(0, 1.4, 1.6) - out * 1.0, 1.0, 1.0, "chrome")
        octa(th, tuple(H), 4.6, 3.2, "frame", axis="x")
        octa(th, tuple(H + out * 1.9), 3.2, 0.8, "trim", axis="x")
        sh = m.bone(f"shin_{side}", tuple(K), parent=f"thigh_{side}")
        beam(sh, K, A, 2.8, 3.2, "frame", extend=1.0)
        dk = unit(A - K)
        fwd = unit(np.cross(V(1, 0, 0), dk)) * -1
        if fwd[2] > 0:
            fwd = -fwd
        slab(sh, K + dk * 0.4 + fwd * 1.8, K + dk * 5.2 + fwd * 1.9, 3.6, 0.9, fwd, "hull2")
        slab(sh, K + dk * 5.0 + fwd * 1.6, A - dk * 0.8 + fwd * 1.5, 2.8, 0.8, fwd, "hull")
        bevel(sh, tuple(K + V(0, 0.2, -0.6)), (4.0, 4.0, 4.0), "hull2", cut=1.2, axis="x")
        beam(sh, K + V(0, -1.6, 1.6), A + V(0, 1.0, -0.6), 0.9, 0.9, "chrome")
        an = m.bone(f"ankle_{side}", tuple(A), parent=f"shin_{side}")
        beam(an, A, F, 2.6, 2.8, "hull", extend=0.8)
        octa(an, tuple(A), 3.2, 3.6, "frame", axis="x")
        da = unit(F - A)
        slab(an, A + da * 0.8 + V(0, 0, 1.45), F - da * 0.6 + V(0, 0, 1.4), 0.5, 0.3, V(0, 0, 1), "glow")
        ft = m.bone(f"foot_{side}", tuple(F), parent=f"ankle_{side}")
        cbox(ft, tuple(F + V(0, -0.5, -0.6)), (4.2, 1.8, 4.4), "hull")
        cbox(ft, tuple(F + V(0, 0.55, -0.8)), (3.2, 0.6, 3.0), "hull2_p")
        for t in (-1, 1):
            p0 = F + V(t * 1.3, -0.6, -2.2)
            p1 = F + V(t * 2.1, -1.2, -6.4)
            beam(ft, p0, p1, 1.5, 1.3, "hull2", extend=0.4)
            beam(ft, p1, p1 + V(t * 0.2, -0.3, -1.4), 0.9, 0.8, "chrome", extend=0.2)
        beam(ft, F + V(0, -0.4, 1.4), F + V(0, -1.2, 4.8), 1.2, 1.1, "frame", extend=0.3)
    # ---- 腰 ---------------------------------------------------------------
    hips = m.bone("hips", (0, 23.0, 0.4), parent="root")
    bevel(hips, (0, 23.8, 0.6), (9.6, 4.6, 6.6), "hull", cut=1.4, axis="z")
    rbox(hips, (0, 22.6, -3.0), (5.2, 4.4, 1.2), "hazard", rot=(-14, 0, 0))     # 前垂れ
    for t in (-1, 1):
        rbox(hips, (t * 3.6, 23.0, -2.8), (2.6, 3.6, 1.0), "hull2", rot=(-12, t * 18, 0))
    rbox(hips, (0, 22.8, 4.0), (7.0, 3.6, 1.0), "hull2", rot=(14, 0, 0))
    cbox(hips, (0, 27.0, 0.8), (6.2, 3.4, 4.6), "inner")                       # 腹のインナー
    cbox(hips, (0, 27.0, 3.4), (2.6, 4.4, 1.6), "frame")                       # 背骨
    # ---- 胴（猫背: 前へ 12° 倒す） -----------------------------------------
    torso = m.bone("torso", (0, 27.5, 0.6), parent="hips", rotation=(SENT_TORSO_LEAN, 0, 0))
    bevel(torso, (0, 31.6, 0.4), (12.4, 7.6, 8.2), "hull", cut=2.0, axis="z")
    chamfer(torso, (0, 35.9, 0.6), (15.4, 3.6, 8.8), "hull2", cut=0.8, axis="z")
    for k, y in enumerate((29.0, 30.6)):
        cbox(torso, (0, y, -3.95), (6.4 - k * 0.8, 1.2, 0.8), "hull2_p")
    rbox(torso, (0, 27.9, -3.2), (5.0, 1.2, 1.0), "hull_p", rot=(-20, 0, 0))
    # 胸の虚空炉（マゼンタの眼）
    ring(torso, (0, 33.2, -4.25), 2.35, 8, (0, 0.9, 1.0), "trim", axis="z", phase=22.5)
    cbox(torso, (0, 33.2, -4.35), (3.4, 3.4, 0.4), "eye", uv_scale=8)
    cbox(torso, (0, 33.2, -4.6), (1.3, 1.3, 0.3), "pupil", uv_scale=10)
    for t in (-1, 1):
        rbox(torso, (t * 4.8, 33.0, -3.6), (3.2, 5.2, 1.0), "hull2", rot=(0, t * -22, 0))
        cbox(torso, (t * 6.55, 31.5, 0.4), (0.8, 4.6, 5.6), "vent")
        rbox(torso, (t * 2.8, 37.7, -2.2), (3.2, 1.2, 3.0), "hull_p", rot=(18, 0, t * -10))  # 襟
    # 背中: 炉の箱と二本の排気筒
    cbox(torso, (0, 32.6, 5.6), (8.6, 8.0, 3.6), "hull")
    cbox(torso, (0, 32.6, 7.5), (5.0, 5.4, 0.4), "vent_v")
    for t in (-1, 1):
        octa(torso, (t * 2.8, 37.8, 6.4), 2.4, 4.6, "frame", axis="y")
        cbox(torso, (t * 2.8, 40.2, 6.4), (1.5, 0.3, 1.5), "thruster", rotation=(0, 45, 0))
    # ---- 頭（胴の傾きを打ち消して前を見る） ---------------------------------
    head = m.bone("head", (0, 37.0, -2.0), parent="torso", rotation=(-SENT_TORSO_LEAN + 2, 0, 0))
    bevel(head, (0, 39.0, -3.6), (7.2, 5.0, 7.6), "hull", cut=1.6, axis="z")
    cbox(head, (0, 39.3, -7.45), (6.4, 1.8, 0.3), "black")
    cbox(head, (0, 39.3, -7.6), (5.8, 0.8, 0.3), "visor", uv_scale=8)
    rbox(head, (0, 41.0, -6.6), (6.0, 1.0, 2.4), "hull2", rot=(28, 0, 0))     # 眉庇
    for t in (-1, 1):
        rbox(head, (t * 2.0, 37.2, -6.6), (3.4, 1.6, 2.4), "hull2", rot=(-10, t * 24, 0))   # 顎
        slab(head, V(t * 3.2, 40.2, -3.0), V(t * 4.6, 41.4, 3.6), 1.8, 0.5, V(1, 0, 0), "hull2")  # 耳のヒレ
        cbox(head, (t * 3.75, 38.2, -4.4), (0.4, 1.2, 2.4), "vent")
    slab(head, V(0, 41.2, -5.2), V(0, 42.6, 2.6), 1.2, 1.6, V(1, 0, 0), "hull2")             # トサカ
    slab(head, V(0, 41.8, -4.6), V(0, 43.2, 1.8), 0.4, 0.5, V(1, 0, 0), "glow")
    # ---- 肩と腕 -------------------------------------------------------------
    for side, s in (("r", -1), ("l", 1)):
        sp = V(s * 9.4, 35.4, 0.6)
        sh = m.bone(f"shoulder_{side}", tuple(sp), parent="torso")
        chamfer(sh, (s * 11.2, 37.4, 0.6), (7.4, 4.6, 8.8), "hull2", cut=0.9, axis="z",
                rot=(0, 0, s * 14))
        rbox(sh, (s * 11.4, 39.9, 0.6), (6.2, 1.2, 7.6), "hull", rot=(0, 0, s * 14))
        for k in range(2):
            rbox(sh, (s * (13.6 + k * 0.7), 34.2 - k * 2.2, 0.6), (2.8, 2.6, 7.4 - k * 1.2), "hull",
                 rot=(0, 0, s * (24 + k * 8)))
        for k, z in enumerate((-1.6, 2.8)):           # 肩の角（後ろ外へ反る）
            tip = V(s * (15.2 + k * 1.2), 46.2 - k * 1.8, z + 3.4)
            spike(sh, (s * 11.4, 40.0, z), tuple(tip), 2.0, 0.6, 3, "hull2")
            cbox(sh, tuple(tip), (0.6, 0.6, 0.6), "glow", rotation=(45, 0, 45))
        rbox(sh, (s * 14.4, 37.2, -3.8), (0.5, 3.6, 0.5), "glow", rot=(0, 0, s * 14))
        rbox(sh, (s * 11.2, 37.4, -3.85), (5.0, 2.8, 0.6), "serial" if s < 0 else "lights",
             rot=(0, 0, s * 14))
        ap = V(s * 10.6, 34.0, 0.6)
        arm = m.bone(f"arm_{side}", tuple(ap), parent=f"shoulder_{side}")
        octa(arm, (s * 11.6, 30.2, 0.6), 3.0, 7.6, "frame", axis="y")
        rbox(arm, (s * 13.1, 30.6, 0.6), (1.0, 5.4, 3.6), "hull", rot=(0, 0, s * 4))
        octa(arm, (s * 11.9, 26.4, 0.6), 3.4, 3.8, "frame", axis="x")
        octa(arm, (s * 11.9, 26.4, 0.6), 2.4, 4.2, "trim", axis="x")
        ep = V(s * 11.9, 26.4, 0.6)
        fa = m.bone(f"forearm_{side}", tuple(ep), parent=f"arm_{side}", rotation=(-14, 0, 0))
        bevel(fa, (s * 12.0, 21.8, 0.2), (4.6, 8.6, 5.0), "hull", cut=1.2, axis="y")
        cbox(fa, (s * (12.0 + 2.35), 21.6, -0.6), (0.3, 6.0, 0.6), "glow")
        cbox(fa, (s * 12.0, 21.0, -2.55), (3.0, 4.6, 0.3), "hull2_p")
        octa(fa, (s * 12.0, 17.0, 0.2), 3.0, 1.6, "frame", axis="y")
        for t in (-1, 0, 1):
            beam(fa, V(s * 12.0 + t * 1.0, 16.4, -0.4), V(s * 12.0 + t * 1.1, 13.4, -1.6), 0.8, 0.8,
                 "chrome", extend=0.3)
        bp = V(s * 14.5, 20.8, -1.0)
        bl = m.bone(f"blade_{side}", tuple(bp), parent=f"forearm_{side}")
        cbox(bl, tuple(bp + V(0, 1.4, 0.6)), (1.4, 5.0, 2.6), "frame")
        q0, q1, q2 = bp + V(0, 3.4, 1.4), bp + V(0, -6.0, -3.2), bp + V(0, -12.0, -8.4)
        slab(bl, q0, q1, 3.2, 0.7, V(1, 0, 0), "blade", extend=0.4)
        slab(bl, q1, q2, 2.2, 0.6, V(1, 0, 0), "blade", extend=0.4)
        e0 = unit(np.cross(V(1, 0, 0), unit(q1 - q0)))
        if e0[2] > 0:
            e0 = -e0
        slab(bl, q0 + e0 * 1.6, q1 + e0 * 1.6, 0.5, 0.8, V(1, 0, 0), "edge")
        e1 = unit(np.cross(V(1, 0, 0), unit(q2 - q1)))
        if e1[2] > 0:
            e1 = -e1
        slab(bl, q1 + e1 * 1.1, q2 + e1 * 0.2, 0.45, 0.7, V(1, 0, 0), "edge")
    fit_density(m, 3, (1024, 1024))
    return m


# ===========================================================================
#  虚星王 ネメシス（ボス、HP 480、全高約 4 ブロック）
#  浮遊する黒い星の機械。光の漏れる割れ目を持つ装甲殻の球（中は星の渦巻く虚空）、
#  正面の特異点の単眼（菫の虹彩・黒い瞳・回る降着円盤・V 字の瞼）、背後に扇状に広がる
#  9 本の黒い棘の光冠、傾いて回る二重の光輪、周りを巡る 6 枚の装甲片、下に垂れる 5 本の触手、
#  眼の左右から前へ曲がる大顎。
# ===========================================================================
NEM_C = (0.0, 34.0, 0.0)
NEM_R = 11.0
NEM_SPINES = 9
NEM_TENDRILS = 5
NEM_SHARDS = 6


def _sph(lon, lat, r=1.0, c=NEM_C):
    """球面上の点。lon 0 = 正面（-Z）、lon 90 = 右（-X）、lat 90 = 真上。"""
    a, b = math.radians(lon), math.radians(lat)
    n = V(-math.sin(a) * math.cos(b), math.sin(b), -math.cos(a) * math.cos(b))
    return V(*c) + n * r, n


def build_nemesis():
    m = Model(f"geometry.{NS}.nemesis", uv_scale=2, visible_bounds=(5.6, 5.4), vb_offset=(0, 2.2, 0),
              max_atlas=(1024, 1024))
    cx, cy, cz = NEM_C
    R = NEM_R
    m.bone("root", (0, 0, 0))
    body = m.bone("body", NEM_C, parent="root")
    # ---- 核: 星の渦巻く虚空の球 + 割れ目から光の漏れる装甲殻 ----------------
    core = m.bone("core", NEM_C, parent="body")
    ball(core, NEM_C, R - 0.7, "void_core", uv_scale=3)
    shell = m.bone("shell", NEM_C, parent="body")
    for lat in (-52, -18, 18, 52):
        for k in range(8):
            lon = 22.5 + 45 * k
            pc, n = _sph(lon, lat, R)
            front = math.degrees(math.acos(max(-1, min(1, -n[2]))))
            if front < 48:
                continue
            p0, _ = _sph(lon, lat - 15, R)
            p1, _ = _sph(lon, lat + 15, R)
            w = 2 * math.pi * R * math.cos(math.radians(lat)) / 8 * 0.84
            st = "nem_plate2" if (k + (lat > 0)) % 2 else "nem_plate"
            slab(shell, p0, p1, w, 1.8, n, st, extend=0.2)
    for sy_ in (-1, 1):                                    # 極の蓋
        octa(shell, (cx, cy + sy_ * (R - 0.2), cz), 7.4, 1.8, "nem_plate", axis="y")
        octa(shell, (cx, cy + sy_ * (R + 0.8), cz), 3.6, 0.6, "glow_v", axis="y")
    # ---- 単眼: 縁・虹彩・特異点の瞳・降着円盤・V 字の瞼 ---------------------
    ez = cz - R + 0.2
    eye = m.bone("eye", (cx, cy, ez), parent="body")
    ring(eye, (cx, cy, ez - 0.2), 7.7, 16, (0, 1.4, 2.4), "dark", axis="z", phase=11.25)
    ring(eye, (cx, cy, ez - 1.0), 6.9, 16, (0, 0.5, 0.6), "glow_vs", axis="z", phase=11.25)
    cbox(eye, (cx, cy, ez + 0.4), (12.6, 12.6, 1.4), "eye_v", uv_scale=6)
    cbox(eye, (cx, cy, ez - 0.45), (6.0, 6.0, 0.6), "pupil_v", uv_scale=8)
    for k in range(4):                                     # 虹彩の角を隠す暗い隅板
        a = 45 + 90 * k
        rbox(eye, (cx - 7.9 * math.sin(math.radians(a)), cy + 7.9 * math.cos(math.radians(a)), ez - 0.1),
             (4.6, 2.2, 1.2), "nem_plate", rot=(0, 0, a))
    disk = m.bone("fx_eye_ring", (cx, cy, ez - 0.9), parent="eye")
    ring(disk, (cx, cy, ez - 0.9), 3.9, 12, (0, 0.6, 0.4), "glow", axis="z", styles=["glow", "glow_v"])
    lids = m.bone("lids", (cx, cy, ez), parent="eye")
    for s_ in (-1, 1):
        # 上の瞼（中央へ下がる V 字）と下の瞼
        rbox(lids, (s_ * 4.2, cy + 6.6, ez - 0.6), (9.0, 2.4, 3.2), "hull2", rot=(-10, 0, s_ * 16))
        rbox(lids, (s_ * 4.6, cy + 7.9, ez + 0.2), (8.4, 1.6, 3.0), "nem_plate", rot=(-4, 0, s_ * 18))
        rbox(lids, (s_ * 4.4, cy - 6.9, ez - 0.4), (7.6, 2.0, 2.8), "hull2", rot=(10, 0, s_ * -12))
        rbox(lids, (s_ * 7.6, cy, ez - 0.2), (2.0, 7.0, 2.8), "nem_plate", rot=(0, s_ * 18, 0))
        rbox(lids, (s_ * 4.6, cy + 5.45, ez - 2.25), (6.6, 0.45, 0.4), "glow", rot=(-10, 0, s_ * 16))
    # ---- 大顎（眼の左右から前下へ曲がる） ------------------------------------
    for side, s_ in (("r", -1), ("l", 1)):
        mp = V(s_ * 8.6, cy - 4.0, cz - 6.0)
        mb = m.bone(f"fx_mandible_{side}", tuple(mp), parent="body")
        pts = [mp, mp + V(s_ * 3.2, -3.0, -3.4), mp + V(s_ * 2.6, -8.2, -7.4),
               mp + V(s_ * -0.6, -11.6, -10.4), mp + V(s_ * -3.4, -12.6, -11.4)]
        polyline(mb, pts, [3.6, 3.0, 2.2, 1.2], [3.0, 2.6, 2.0, 1.0], "hull2")
        polyline(mb, [pts[1] + V(0, 1.2, 0), pts[2] + V(0, 0.9, 0), pts[3] + V(0, 0.6, 0)],
                 [0.5, 0.4], [3.2, 2.4], "glow_v", overlap=0.1)
    # ---- 光冠: 背後に扇状に広がる黒い棘 --------------------------------------
    for i in range(NEM_SPINES):
        a = math.radians(-104 + 208 * i / (NEM_SPINES - 1))   # 0 = 真上
        d = unit(V(-math.sin(a), math.cos(a), 0.42))
        base = V(cx, cy, cz + 3.0) + d * (R - 2.0)
        L = 23.0 - 6.0 * abs(math.cos(a * 1.0)) * 0 - (5.0 if i % 2 else 0.0)
        sb = m.bone(f"fx_spine_{i}", tuple(np.round(base, 3)), parent="body")
        tip = base + d * L + V(0, 0, 3.0)
        bend = base + d * (L * 0.5) + V(0, 0, 1.0)
        nz = V(0, 0.0, 1.0)
        slab(sb, base, bend, 4.6, 1.6, nz, "spine", extend=0.4)
        slab(sb, bend, bend + (tip - bend) * 0.6, 3.0, 1.3, nz, "spine", extend=0.4)
        slab(sb, bend + (tip - bend) * 0.6, tip, 1.5, 1.0, nz, "spine", extend=0.2)
        slab(sb, base + d * 1.2 + V(0, 0, -0.9), tip - d * 2.5 + V(0, 0, -0.5), 0.4, 0.4, nz, "glow_vs")
        cbox(sb, tuple(tip), (1.1, 1.1, 1.1), "glow", rotation=(45, 0, 45))
    # ---- 二重の光輪（傾けた親ボーン → 自分の軸まわりに回る子ボーン） ---------------
    m.bone("ring_a", NEM_C, parent="body", rotation=(72, 0, 18))
    ra = m.bone("fx_ring_a", NEM_C, parent="ring_a")
    ring(ra, NEM_C, 19.0, 24, (0, 1.2, 2.2), "trim", axis="y", styles=["dark", "dark", "glow_v"])
    for k in range(4):
        p, _ = (V(cx - 19.2 * math.sin(math.radians(45 + 90 * k)), cy,
                  cz - 19.2 * math.cos(math.radians(45 + 90 * k))), None)
        cbox(ra, tuple(p), (2.6, 3.4, 2.6), "hull2", rotation=(0, 45 + 90 * k, 0))
        cbox(ra, tuple(p + V(0, 1.85, 0)), (1.2, 0.3, 1.2), "glow", rotation=(0, 45 + 90 * k, 0))
    m.bone("ring_b", NEM_C, parent="body", rotation=(-58, 0, -24))
    rb = m.bone("fx_ring_b", NEM_C, parent="ring_b")
    ring(rb, NEM_C, 15.6, 18, (0, 0.7, 1.0), "glow_v", axis="y", styles=["glow_v", "glow_vs"])
    # ---- 巡る装甲片 -----------------------------------------------------------
    orb = m.bone("fx_shards", NEM_C, parent="body")
    for i in range(NEM_SHARDS):
        a = math.radians(i * 360 / NEM_SHARDS + 30)
        h = (6.0, -5.0, 2.0, -8.0, 7.0, -2.0)[i]
        c = V(cx - 23.0 * math.sin(a), cy + h, cz - 23.0 * math.cos(a))
        sb = m.bone(f"fx_shard_{i}", tuple(np.round(c, 3)), parent="fx_shards")
        tilt = (20 + 15 * i, i * 360 / NEM_SHARDS + 30, 25 - 10 * i)
        rbox(sb, tuple(c), (3.2, 6.6, 1.6), "nem_plate2", rot=tilt)
        rbox(sb, tuple(c + V(0, 0.4, 0)), (1.8, 4.4, 2.0), "crystal", rot=tilt)
        rbox(sb, tuple(c + V(0, -3.6, 0)), (1.6, 2.2, 1.2), "hull2", rot=(tilt[0] + 30, tilt[1], tilt[2]))
    # ---- 触手（3 節。節ごとにボーン） -----------------------------------------
    for i in range(NEM_TENDRILS):
        a = math.radians(i * 360 / NEM_TENDRILS + 36)
        top = V(cx - 6.2 * math.sin(a), cy - R + 1.6, cz - 6.2 * math.cos(a) + 1.5)
        out = V(-math.sin(a), 0, -math.cos(a))
        parent = "body"
        p0 = top
        for k in range(3):
            seg = 8.0 - k * 1.6
            p1 = p0 + V(0, -seg, 0) + out * (1.4 - k * 0.9)
            tb = m.bone(f"fx_tendril_{i}_{k}", tuple(np.round(p0, 3)), parent=parent)
            w = 2.6 - k * 0.7
            beam(tb, p0, p1, w, w, "spine" if k else "nem_plate2", extend=0.4)
            octa(tb, tuple(p0), w + 0.9, 1.0, "trim" if k == 0 else "frame", axis="y")
            if k == 2:
                cbox(tb, tuple(p1 + V(0, -0.6, 0)), (1.2, 1.6, 1.2), "glow", rotation=(0, 45, 0))
            parent = f"fx_tendril_{i}_{k}"
            p0 = p1
    fit_density(m, 2, (1024, 1024))
    return m


# ===========================================================================
#  ホログラム標的（HP 200 を毎回満タンに戻す練習台）
#  投影台（不透明・entity_emissive_alpha）と、その上に浮かぶシアンの人型ワイヤーフレーム
#  （holo_* ボーン = 加算合成 entity_beam_additive）。胸に赤い照準、体を上下する走査の輪。
# ===========================================================================
def hexagon(bone, centre, W, h, style, **kw):
    """平らな六角柱（3 枚の板を 60° ずつ回す。上下の面は少しずつ引っ込めてちらつきを避ける）。"""
    out = []
    for k, a in enumerate((0, 60, 120)):
        c = rbox(bone, centre, (W / math.sqrt(3) + 0.02, h - 0.03 * k, W), style, rot=(0, a, 0), **kw)
        out.append(c)
    return out


def wire(bone, origin, size, t, style, fill=None, **kw):
    """箱の 12 本の稜を太さ t の角柱で。fill を渡すと少し小さい半透明の中身も。"""
    x0, y0, z0 = origin
    sx, sy, sz = size
    x1, y1, z1 = x0 + sx, y0 + sy, z0 + sz
    out = []
    for y in (y0, y1):
        for z in (z0, z1):
            out.append(cbox(bone, ((x0 + x1) / 2, y, z), (sx + t, t, t), style, **kw))
    for x in (x0, x1):
        for z in (z0, z1):
            out.append(cbox(bone, (x, (y0 + y1) / 2, z), (t, sy - t, t), style, **kw))
    for x in (x0, x1):
        for y in (y0, y1):
            out.append(cbox(bone, (x, y, (z0 + z1) / 2), (t, t, sz - t), style, **kw))
    if fill:
        out.append(cbox(bone, ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                        (sx - 0.6, sy - 0.6, sz - 0.6), fill, **kw))
    return out


def build_hologram():
    m = Model(f"geometry.{NS}.hologram_target", uv_scale=4, visible_bounds=(2.0, 2.8), vb_offset=(0, 1.2, 0),
              max_atlas=(512, 512))
    m.bone("root", (0, 0, 0))
    base = m.bone("base", (0, 0, 0), parent="root")
    hexagon(base, (0, 1.0, 0), 15.0, 2.0, "pbase")
    hexagon(base, (0, 2.3, 0), 12.0, 0.7, "pbase2")
    cbox(base, (0, 2.75, 0), (5.2, 0.3, 5.2), "plens", uv_scale=8)
    ring(base, (0, 2.75, 0), 3.0, 6, (0, 0.5, 0.4), "pglow", axis="y", phase=30)
    for k, a in enumerate((30, 150, 270)):
        r = math.radians(a)
        px, pz = -6.4 * math.sin(r), -6.4 * math.cos(r)
        cbox(base, (px, 3.6, pz), (1.4, 3.6, 1.4), "pframe", rotation=(0, a, 0))
        cbox(base, (px, 5.6, pz), (1.0, 0.6, 1.0), "pglow", rotation=(0, a, 0))
    cbox(base, (0, 1.0, -6.55), (6.0, 1.4, 0.3), "pserial")                       # 正面の型番
    for a in (120, 240):
        rbox(base, (-6.55 * math.sin(math.radians(a)), 1.0, -6.55 * math.cos(math.radians(a))),
             (6.0, 1.4, 0.3), "phazard", rot=(0, a, 0))
    # ---- ホログラム（加算合成） ------------------------------------------------
    holo = m.bone("holo_root", (0, 3.0, 0), parent="root")
    t = 0.45
    hb = m.bone("holo_body", (0, 15.0, 0), parent="holo_root")
    wire(hb, (-4, 15, -2), (8, 12, 4), t, "holo", fill="holo_fill")
    hh = m.bone("holo_head", (0, 27.0, 0), parent="holo_body")
    wire(hh, (-4, 27.2, -4), (8, 8, 8), t, "holo", fill="holo_fill")
    cbox(hh, (0, 31.2, -4.05), (5.0, 0.5, 0.3), "holo_dim")                        # 目の線
    for side, sx in (("r", -1), ("l", 1)):
        ha = m.bone(f"holo_arm_{side}", (sx * 5.2, 26.0, 0), parent="holo_body", rotation=(0, 0, sx * -6))
        wire(ha, (sx * 6.2 - 2, 15.2, -2), (4, 11.6, 4), t, "holo", fill="holo_fill")
        hl = m.bone(f"holo_leg_{side}", (sx * 2.0, 15.0, 0), parent="holo_root")
        wire(hl, (sx * 2.1 - 2, 3.2, -2), (4, 11.6, 4), t, "holo", fill="holo_fill")
    ret = m.bone("holo_reticle", (0, 21.5, -2.6), parent="holo_body")
    ring(ret, (0, 21.5, -2.6), 2.6, 6, (0, 0.4, 0.3), "holo_red", axis="z", phase=30)
    for k in range(4):
        a = 90 * k
        rbox(ret, (-3.6 * math.sin(math.radians(a)), 21.5 + 3.6 * math.cos(math.radians(a)), -2.6),
             (0.4, 1.6, 0.3), "holo_red", rot=(0, 0, a))
    cbox(ret, (0, 21.5, -2.7), (0.8, 0.8, 0.3), "holo_red")
    scan = m.bone("holo_scan", (0, 4.0, 0), parent="holo_root")
    ring(scan, (0, 4.0, 0), 7.0, 8, (0, 0.35, 0.5), "holo_dim", axis="y", phase=22.5)
    fit_density(m, 4, (512, 512))
    return m


# ===========================================================================
#  ヴォイド・ボルト（ドローンの投射物）と、ダメージ表示の空のジオメトリ
# ===========================================================================
def build_bolt():
    m = Model(f"geometry.{NS}.void_bolt", uv_scale=8, visible_bounds=(1, 1), vb_offset=(0, 0.2, 0),
              max_atlas=(128, 128))
    m.bone("root", (0, 0, 0))
    b = m.bone("body", (0, 2.0, 0), parent="root")
    cbox(b, (0, 2.0, 0), (1.4, 1.4, 6.0), "energy", rotation=(0, 0, 45))
    cbox(b, (0, 2.0, 0), (0.8, 0.8, 7.6), "glow")
    for k in range(2):
        cbox(b, (0, 2.0, -1.4 + k * 2.8), (2.4 - k * 0.8, 2.4 - k * 0.8, 0.4), "glow_soft",
             rotation=(0, 0, 45))
    fit_density(m, 8, (128, 128), ks=(1.0, 0.75, 0.5))
    return m


def build_dmg_text():
    m = Model(f"geometry.{NS}.dmg_text", uv_scale=1, visible_bounds=(1, 1), vb_offset=(0, 0.5, 0),
              max_atlas=(16, 16))
    m.bone("root", (0, 0, 0))
    m.tex_w = m.tex_h = 16
    return m


# ===========================================================================
#  プレビュー（hd_scene の規則でボーンを組み、X を鏡映して描く。holo_* は加算合成）
#  ※ hd_preview.render は x をもう一度反転しているので鏡像になる。ここは hd_scene.ortho と同じ向き
# ===========================================================================
def render(geo, tex_img, yaw=0.0, pitch=-12.0, size=360, pose=None, additive=("holo",),
           bg=(22, 20, 30), fit=None):
    from hd_scene import weapon_quads
    from hd_space import Rx, Ry
    tex = np.asarray(tex_img.convert("RGBA"), np.float32)
    th, tw = tex.shape[:2]
    quads = weapon_quads(geo, tex_img, None, pose or {}, tag=True)
    view = Rx(pitch) @ Ry(yaw)
    # 統合版の画面: +Z を向いて見るとき画面の右 = +X（右手系の素直な投影の鏡映。hd_scene.ortho / fp と同じ）。
    # yaw 0 で正面（-Z 側）から見て、右腕（-X）が画面の左に来る。
    pts = np.array([p for q in quads for p in q[0]]) @ view.T
    if fit is None:
        lo, hi = pts.min(axis=0), pts.max(axis=0)
        span = max(hi[0] - lo[0], hi[1] - lo[1]) or 1.0
        cx, cy = (hi[0] + lo[0]) / 2, (hi[1] + lo[1]) / 2
    else:
        span, cx, cy = fit
    S = size
    scale = S * 0.86 / span
    img = np.zeros((S, S, 3), np.float32)
    yy = np.linspace(0, 1, S)[:, None]
    img[:, :] = np.array(bg, np.float32) * (1.15 - 0.4 * yy)[:, :, None].repeat(S, 1)
    zbuf = np.full((S, S), 1e9, np.float32)
    light = unit((0.35, 0.8, -0.5))
    add_layer = []
    for pts3, uvs, _c, tag in quads:
        bone = tag.split("#")[0]
        P = [view @ np.asarray(p) for p in pts3]
        n = np.cross(P[1] - P[0], P[3] - P[0])
        nl = np.linalg.norm(n) or 1.0
        lit = 0.42 + 0.58 * abs(float(np.dot(n / nl, light)))
        scr = [((q[0] - cx) * scale + S / 2, S / 2 - (q[1] - cy) * scale, q[2]) for q in P]
        if any(bone.startswith(a) for a in additive):
            add_layer.append((scr, uvs, lit))
        else:
            _raster(img, zbuf, scr, uvs, lit, tex, tw, th, False)
    for scr, uvs, lit in add_layer:
        _raster(img, zbuf, scr, uvs, lit, tex, tw, th, True)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def _raster(img, zbuf, scr, uvs, lit, tex, tw, th, additive):
    S = img.shape[0]
    for tri in ((0, 1, 2), (0, 2, 3)):
        p0, p1, p2 = (scr[i] for i in tri)
        t0, t1, t2 = (uvs[i] for i in tri)
        minx = max(0, int(min(p0[0], p1[0], p2[0])))
        maxx = min(S - 1, int(max(p0[0], p1[0], p2[0])) + 1)
        miny = max(0, int(min(p0[1], p1[1], p2[1])))
        maxy = min(S - 1, int(max(p0[1], p1[1], p2[1])) + 1)
        if minx > maxx or miny > maxy:
            continue
        d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
        if abs(d) < 1e-9:
            continue
        ys, xs = np.mgrid[miny:maxy + 1, minx:maxx + 1].astype(np.float32)
        xs += 0.5
        ys += 0.5
        w0 = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / d
        w1 = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / d
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
        if not m.any():
            continue
        z = w0 * p0[2] + w1 * p1[2] + w2 * p2[2]
        sub = zbuf[miny:maxy + 1, minx:maxx + 1]
        m &= z < sub
        if not m.any():
            continue
        u = w0 * t0[0] + w1 * t1[0] + w2 * t2[0]
        v = w0 * t0[1] + w1 * t1[1] + w2 * t2[1]
        ui = np.clip(u.astype(int), 0, tw - 1)
        vi = np.clip(v.astype(int), 0, th - 1)
        tx = tex[vi, ui]
        reg = img[miny:maxy + 1, minx:maxx + 1]
        if additive:
            reg[m] = np.clip(reg[m] + tx[..., :3][m] * 0.85, 0, 255)
            continue
        m &= tx[..., 3] > 0
        emit = 1 - tx[..., 3:4] / 255
        col = tx[..., :3] * (lit * (1 - emit) + 1.12 * emit)
        reg[m] = np.clip(col[m], 0, 255)
        sub[m] = z[m]


def sheet(tiles, path, cols=4, label=None):
    w, h = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (w * cols, h * rows + (22 if label else 0)), (12, 12, 18))
    for k, t in enumerate(tiles):
        out.paste(t, ((k % cols) * w, (k // cols) * h + (22 if label else 0)))
    if label:
        ImageDraw.Draw(out).text((8, 4), label, fill=(230, 230, 240))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path)
    return path


# ===========================================================================
#  アニメーション（RP）。Molang の三角関数は度。q.life_time は秒。
# ===========================================================================
ANIMS: dict = {}
CTRLS: dict = {}


def f(x):
    return f"{x:g}"


def anim(name, bones, loop=True, length=None):
    a = {"loop": loop, "bones": bones}
    if length:
        a["animation_length"] = length
    ANIMS[f"animation.{NS}.{name}"] = a
    return f"animation.{NS}.{name}"


def keys(**tracks):
    """keys(rotation={0: [..], 0.2: [..]}, position=...) → Bedrock のキーフレーム辞書。"""
    out = {}
    for ch, kf in tracks.items():
        if isinstance(kf, dict):
            out[ch] = {f"{float(t):.2f}": v for t, v in sorted(kf.items())}
        else:
            out[ch] = kf
    return out


def controller(name, states, initial="default"):
    """states: {state: (anims, [(target, cond), ...], blend)}。"""
    out = {}
    for st, (anims, trans, blend) in states.items():
        d = {}
        if anims:
            d["animations"] = list(anims)
        if trans:
            d["transitions"] = [{t: c} for t, c in trans]
        if blend:
            d["blend_transition"] = blend
        out[st] = d
    CTRLS[f"controller.animation.{NS}.{name}"] = {"initial_state": initial, "states": out}
    return f"controller.animation.{NS}.{name}"


# 正面から見て反時計回りに回すと外へ開くヒレ（0,2）と、時計回りで開くヒレ（1,3）
FIN_SPREAD = (-1, 1, -1, 1)


def drone_anims():
    A = {}
    A["look"] = anim("void_drone.look", {"body": {"rotation": ["q.target_x_rotation", "q.target_y_rotation", 0]}})
    bones = {
        "body": {"position": [0, "math.sin(q.life_time * 120.0) * 0.9", 0],
                 "rotation": ["math.sin(q.life_time * 70.0) * 3.0", 0, "math.sin(q.life_time * 95.0) * 4.0"]},
        "fx_flame": {"scale": [1, "0.85 + math.sin(q.life_time * 2400.0) * 0.15", 1]},
        "fx_eye_glow": {"scale": ["1.0 + math.sin(q.life_time * 300.0) * 0.04",
                                  "1.0 + math.sin(q.life_time * 300.0) * 0.04", 1]},
    }
    for i in range(4):
        ph = i * 90
        bones[f"fx_fin_{i}"] = {"rotation": [0, 0, f"math.sin(q.life_time * 900.0 + {ph}.0) * 5.0"]}
        bones[f"fx_fin_{i}_tip"] = {"rotation": [0, 0, f"math.sin(q.life_time * 900.0 + {ph - 50}.0) * 7.0"]}
    A["idle"] = anim("void_drone.idle", bones)
    cb = {
        "fx_eye_glow": {"scale": ["1.18 + math.sin(q.anim_time * 2200.0) * 0.12",
                                  "1.18 + math.sin(q.anim_time * 2200.0) * 0.12", 1]},
        "lids": {"scale": [1.2, 1.2, 1]},
        "body": {"position": [0, 0, 0.8], "rotation": [-6, 0, 0]},
        "cannon": {"position": [0, 0, 0.7]},
    }
    for i in range(4):
        cb[f"fx_fin_{i}"] = {"rotation": [0, 0, FIN_SPREAD[i] * 14]}
        cb[f"fx_fin_{i}_tip"] = {"rotation": [0, 0, FIN_SPREAD[i] * 10]}
    A["charge"] = anim("void_drone.charge", cb)
    A["fire"] = anim("void_drone.fire", {
        "cannon": keys(position={0: [0, 0, 1.8], 0.25: [0, 0, 0]}),
        "body": keys(position={0: [0, 0, 1.4], 0.3: [0, 0, 0]}, rotation={0: [-10, 0, 0], 0.3: [0, 0, 0]}),
        "fx_eye_glow": keys(scale={0: [1.45, 1.45, 1], 0.35: [1, 1, 1]}),
    }, loop="hold_on_last_frame", length=0.4)
    A["death"] = anim("void_drone.death", {
        "body": keys(rotation={0: [0, 0, 0], 1.0: [70, 360, 40]}, position={0: [0, 0, 0], 1.0: [0, -6, 0]}),
        "fx_eye_glow": keys(scale={0: [1.4, 1.4, 1], 0.6: [0.2, 0.2, 1]}),
    }, loop="hold_on_last_frame", length=1.0)
    A["ctrl"] = controller("void_drone", {
        "default": ([], [("dead", "!q.is_alive"), ("charge", "v.mode == 1"), ("fire", "v.mode == 2")], 0),
        "charge": (["charge"], [("dead", "!q.is_alive"), ("fire", "v.mode == 2"), ("default", "v.mode == 0")], 0.15),
        "fire": (["fire"], [("dead", "!q.is_alive"), ("charge", "v.mode == 1"),
                            ("default", "v.mode == 0 && q.all_animations_finished")], 0.15),
        "dead": (["death"], [], 0.1),
    })
    return A


# 歩行の位相の進み（度 / q.modified_distance_moved の 1）。バニラの歩く mob・プレイヤー（cos(距離 × 38.17)）と
# 同じにすると、脚の振れ（SENT_SWING）と脚の長さで足の速さが体の進みに合う（足が滑らない。stride_check）
SENT_STEP_RATE = 38.17
SENT_SWING = 24.0       # 太ももの振れ幅（度、v.ms = 1 の時）
SENT_MS = 1.8           # v.ms = min(q.modified_move_speed × SENT_MS, 1)


def stride_check(geo):
    """足が地面を滑らないか: 足の速さ（脚の長さ × 振れ幅 × 位相の進み、距離 1 あたり）を、同じ式で見た
    バニラのプレイヤー（脚 12 px、振れ幅 1.4 rad × 速さ、38.17°）と比べる（v.ms がちょうど 1 になる速さで）。
    ±25% を超えたらエラー。"""
    b = {x["name"]: x for x in geo["bones"]}
    hip = b["thigh_r"]["pivot"][1]
    sole = min(c["origin"][1] for n in ("thigh_r", "shin_r", "ankle_r", "foot_r") for c in b[n].get("cubes", []))
    ms = 1.0 / SENT_MS
    mine = (hip - sole) * math.radians(SENT_SWING) * math.radians(SENT_STEP_RATE)
    vanilla = 12.0 * 1.4 * ms * math.radians(38.17)
    r = mine / vanilla
    return [] if 0.75 <= r <= 1.25 else [
        f"void_sentinel: feet move {r:.2f}x the body (leg {hip - sole:.1f}px, swing {SENT_SWING}deg, "
        f"{SENT_STEP_RATE}deg per unit walked) — they skate"]


def sentinel_anims():
    A = {}
    # 歩行: 位相 v.ph（歩いた距離 × SENT_STEP_RATE）、振れ幅 v.ms（速さ）。足は常に水平を保つ
    s_th = f"math.sin(v.ph) * {SENT_SWING:g} * v.ms"
    lift_r = "math.max(0.0, math.cos(v.ph))"
    lift_l = "math.max(0.0, -math.cos(v.ph))"
    bones = {
        "hips": {"position": [0, "-math.abs(math.cos(v.ph)) * 0.9 * v.ms", 0],
                 "rotation": ["math.sin(q.life_time * 90.0) * 1.2", 0, "math.sin(v.ph) * 3.0 * v.ms"]},
        "torso": {"rotation": ["math.sin(q.life_time * 90.0 + 40.0) * 1.5", "math.sin(v.ph) * 6.0 * v.ms", 0]},
        "head": {"rotation": [0, "math.sin(q.life_time * 36.0) * 14.0 * (1.0 - v.ms)", 0]},
        "arm_r": {"rotation": [f"-({s_th}) * 0.5", 0, 0]},
        "arm_l": {"rotation": [f"({s_th}) * 0.5", 0, 0]},
        "thigh_r": {"rotation": [f"-{s_th}", 0, 0]},
        "thigh_l": {"rotation": [s_th, 0, 0]},
        "shin_r": {"rotation": [f"{lift_r} * 34.0 * v.ms", 0, 0]},
        "shin_l": {"rotation": [f"{lift_l} * 34.0 * v.ms", 0, 0]},
        "ankle_r": {"rotation": [f"-{lift_r} * 22.0 * v.ms", 0, 0]},
        "ankle_l": {"rotation": [f"-{lift_l} * 22.0 * v.ms", 0, 0]},
        "foot_r": {"rotation": [f"({s_th}) - {lift_r} * 12.0 * v.ms", 0, 0]},
        "foot_l": {"rotation": [f"-({s_th}) - {lift_l} * 12.0 * v.ms", 0, 0]},
    }
    A["walk"] = anim("void_sentinel.walk", bones)
    A["swing"] = anim("void_sentinel.swing", {
        "arm_r": keys(rotation={0: [0, 0, 0], 0.16: [-125, 12, -24], 0.32: [-25, -18, 8], 0.55: [0, 0, 0]}),
        "forearm_r": keys(rotation={0: [0, 0, 0], 0.16: [-35, 0, 0], 0.32: [-10, 0, 0], 0.55: [0, 0, 0]}),
        "torso": keys(rotation={0: [0, 0, 0], 0.16: [-4, -18, 0], 0.32: [8, 22, 0], 0.55: [0, 0, 0]}),
    }, loop=False, length=0.55)
    up = {0: [0, 0, 0], 0.45: [-160, 0, 0], 0.8: [-172, 0, 0]}
    A["windup"] = anim("void_sentinel.windup", {
        "arm_r": keys(rotation={t: [v[0], 0, 14 if t else 0] for t, v in up.items()}),
        "arm_l": keys(rotation={t: [v[0], 0, -14 if t else 0] for t, v in up.items()}),
        "forearm_r": keys(rotation={0: [0, 0, 0], 0.45: [-24, 0, 0]}),
        "forearm_l": keys(rotation={0: [0, 0, 0], 0.45: [-24, 0, 0]}),
        "torso": keys(rotation={0: [0, 0, 0], 0.45: [-16, 0, 0], 0.8: [-18, 0, 0]}),
        "head": keys(rotation={0: [0, 0, 0], 0.45: [10, 0, 0]}),
        "hips": keys(position={0: [0, 0, 0], 0.45: [0, -1.6, 0]}),
        "thigh_r": keys(rotation={0: [0, 0, 0], 0.45: [-12, 0, 0]}),
        "thigh_l": keys(rotation={0: [0, 0, 0], 0.45: [-12, 0, 0]}),
        "shin_r": keys(rotation={0: [0, 0, 0], 0.45: [16, 0, 0]}),
        "shin_l": keys(rotation={0: [0, 0, 0], 0.45: [16, 0, 0]}),
    }, loop="hold_on_last_frame", length=0.8)
    A["slam"] = anim("void_sentinel.slam", {
        "arm_r": keys(rotation={0: [-172, 0, 14], 0.12: [-42, 0, 6], 0.5: [-42, 0, 6], 0.75: [0, 0, 0]}),
        "arm_l": keys(rotation={0: [-172, 0, -14], 0.12: [-42, 0, -6], 0.5: [-42, 0, -6], 0.75: [0, 0, 0]}),
        "forearm_r": keys(rotation={0: [-24, 0, 0], 0.12: [-8, 0, 0], 0.75: [0, 0, 0]}),
        "forearm_l": keys(rotation={0: [-24, 0, 0], 0.12: [-8, 0, 0], 0.75: [0, 0, 0]}),
        "torso": keys(rotation={0: [-18, 0, 0], 0.12: [30, 0, 0], 0.5: [26, 0, 0], 0.75: [0, 0, 0]}),
        "head": keys(rotation={0: [10, 0, 0], 0.12: [-22, 0, 0], 0.75: [0, 0, 0]}),
        "hips": keys(position={0: [0, -1.6, 0], 0.12: [0, -4.2, 0], 0.5: [0, -4.0, 0], 0.75: [0, 0, 0]}),
        "thigh_r": keys(rotation={0: [-12, 0, 0], 0.12: [-30, 0, 0], 0.5: [-28, 0, 0], 0.75: [0, 0, 0]}),
        "thigh_l": keys(rotation={0: [-12, 0, 0], 0.12: [-30, 0, 0], 0.5: [-28, 0, 0], 0.75: [0, 0, 0]}),
        "shin_r": keys(rotation={0: [16, 0, 0], 0.12: [40, 0, 0], 0.5: [38, 0, 0], 0.75: [0, 0, 0]}),
        "shin_l": keys(rotation={0: [16, 0, 0], 0.12: [40, 0, 0], 0.5: [38, 0, 0], 0.75: [0, 0, 0]}),
        "ankle_r": keys(rotation={0: [0, 0, 0], 0.12: [-14, 0, 0], 0.75: [0, 0, 0]}),
        "ankle_l": keys(rotation={0: [0, 0, 0], 0.12: [-14, 0, 0], 0.75: [0, 0, 0]}),
        "foot_r": keys(rotation={0: [12, 0, 0], 0.12: [4, 0, 0], 0.75: [0, 0, 0]}),
        "foot_l": keys(rotation={0: [12, 0, 0], 0.12: [4, 0, 0], 0.75: [0, 0, 0]}),
    }, loop="hold_on_last_frame", length=0.75)
    A["death"] = anim("void_sentinel.death", {
        "hips": keys(position={0: [0, 0, 0], 0.7: [0, -7, 0]}),
        "torso": keys(rotation={0: [0, 0, 0], 0.7: [38, 0, 10]}),
        "head": keys(rotation={0: [0, 0, 0], 0.7: [30, 20, 0]}),
        "arm_r": keys(rotation={0: [0, 0, 0], 0.7: [-30, 0, -20]}),
        "arm_l": keys(rotation={0: [0, 0, 0], 0.7: [-20, 0, 25]}),
        "thigh_r": keys(rotation={0: [0, 0, 0], 0.7: [-40, 0, 0]}),
        "thigh_l": keys(rotation={0: [0, 0, 0], 0.7: [-36, 0, 0]}),
        "shin_r": keys(rotation={0: [0, 0, 0], 0.7: [60, 0, 0]}),
        "shin_l": keys(rotation={0: [0, 0, 0], 0.7: [56, 0, 0]}),
    }, loop="hold_on_last_frame", length=0.7)
    A["ctrl"] = controller("void_sentinel", {
        "default": ([], [("dead", "!q.is_alive"), ("windup", "v.mode == 1"), ("slam", "v.mode == 2"),
                         ("swing", "v.attack_time > 0.0")], 0),
        "swing": (["swing"], [("dead", "!q.is_alive"), ("windup", "v.mode == 1"),
                              ("default", "q.all_animations_finished")], 0.1),
        "windup": (["windup"], [("dead", "!q.is_alive"), ("slam", "v.mode == 2"), ("default", "v.mode == 0")], 0.12),
        "slam": (["slam"], [("dead", "!q.is_alive"), ("windup", "v.mode == 1"),
                            ("default", "v.mode == 0 && q.all_animations_finished")], 0.05),
        "dead": (["death"], [], 0.1),
    })
    return A


NEM_DEATH = 0.9         # 普通の死のアニメ（秒）。死んだ mob が消えるまでの 1 秒より短く
NEM_DYING = 2.6         # スクリプトで死なせる時のアニメ（秒）= invaders.bossDeath の最後の大爆発（52 tick）
NEM_MODE_DYING = 8      # astro:mode の値（スクリプトが致命傷を止めて生きたまま入れる）


def nemesis_anims():
    A = {}
    T = "q.life_time"
    bones = {
        "body": {"position": [0, f"math.sin({T} * 60.0) * 1.6", 0],
                 "rotation": [f"math.sin({T} * 33.0) * 2.0", 0, f"math.sin({T} * 40.0) * 2.5"]},
        "fx_ring_a": {"rotation": [0, f"math.mod({T} * 50.0 * v.spd, 360.0)", 0]},
        "fx_ring_b": {"rotation": [0, f"-math.mod({T} * 74.0 * v.spd, 360.0)", 0]},
        "fx_shards": {"rotation": [0, f"math.mod({T} * 28.0 * v.spd, 360.0)", 0]},
        "fx_eye_ring": {"rotation": [0, 0, f"math.mod({T} * 140.0 * v.spd, 360.0)"]},
        "core": {"scale": [f"1.0 + math.sin({T} * 180.0) * 0.015"] * 3},
        "fx_mandible_r": {"rotation": [f"math.sin({T} * 70.0) * 3.0", 0, f"math.sin({T} * 50.0) * 4.0"]},
        "fx_mandible_l": {"rotation": [f"math.sin({T} * 70.0 + 30.0) * 3.0", 0, f"-math.sin({T} * 50.0) * 4.0"]},
    }
    for i in range(NEM_SHARDS):
        bones[f"fx_shard_{i}"] = {"position": [0, f"math.sin({T} * 90.0 + {i * 60}.0) * 1.6", 0],
                                  "rotation": [0, f"math.mod({T} * {40 + i * 9}.0, 360.0)", 0]}
    for i in range(NEM_SPINES):
        bones[f"fx_spine_{i}"] = {"rotation": [f"math.sin({T} * 55.0 + {i * 40}.0) * 3.0", 0,
                                               f"math.sin({T} * 45.0 + {i * 70}.0) * 2.5"]}
    for i in range(NEM_TENDRILS):
        for k in range(3):
            amp = 7 + k * 5
            bones[f"fx_tendril_{i}_{k}"] = {"rotation": [
                f"math.sin({T} * 85.0 * v.spd + {i * 72 + k * 55}.0) * {amp}.0", 0,
                f"math.cos({T} * 70.0 * v.spd + {i * 72 + k * 55}.0) * {amp * 0.7:g}"]}
    A["idle"] = anim("nemesis.idle", bones)
    A["look"] = anim("nemesis.look", {"body": {"rotation": ["math.clamp(q.target_x_rotation, -30.0, 30.0)",
                                                         "q.target_y_rotation", 0]}})
    spines_out = {f"fx_spine_{i}": {"scale": 1.12, "rotation": [-12, 0, 0]} for i in range(NEM_SPINES)}
    A["charge"] = anim("nemesis.charge", dict({
        "eye": {"scale": ["1.08 + math.sin(q.anim_time * 1800.0) * 0.06",
                          "1.08 + math.sin(q.anim_time * 1800.0) * 0.06", 1]},
        "lids": {"scale": [1.12, 1.3, 1]},
        "fx_ring_a": {"rotation": [0, "q.anim_time * 420.0", 0]},
        "fx_ring_b": {"rotation": [0, "-q.anim_time * 520.0", 0]},
        "fx_shards": {"scale": 0.82},
    }, **spines_out))
    A["beam"] = anim("nemesis.beam", {
        "eye": {"scale": [1.2, 1.2, 1]},
        "lids": {"scale": [1.2, 1.4, 1]},
        "body": {"rotation": [-5, 0, "math.sin(q.anim_time * 2400.0) * 1.2"]},
        "fx_mandible_r": {"rotation": [0, -16, 18]},
        "fx_mandible_l": {"rotation": [0, 16, -18]},
    })
    sm = {f"fx_tendril_{i}_0": keys(rotation={0: [0, 0, 0], 0.4: [-38, 0, 0]}) for i in range(NEM_TENDRILS)}
    A["summon"] = anim("nemesis.summon", dict({
        "fx_shards": keys(scale={0: [1, 1, 1], 0.4: [1.35, 1.1, 1.35]}),
        "lids": keys(scale={0: [1, 1, 1], 0.3: [1.1, 1.3, 1]}),
        "body": keys(rotation={0: [0, 0, 0], 0.4: [-10, 0, 0]}),
    }, **sm), loop="hold_on_last_frame", length=1.0)
    A["meteor"] = anim("nemesis.meteor", dict({
        "body": keys(rotation={0: [0, 0, 0], 0.5: [-24, 0, 0]}),
        "ring_a": keys(rotation={0: [0, 0, 0], 0.6: [-50, 0, 0]}),
        "ring_b": keys(rotation={0: [0, 0, 0], 0.6: [40, 0, 0]}),
    }, **{f"fx_spine_{i}": keys(scale={0: [1, 1, 1], 0.5: [1.2, 1.2, 1.2]}) for i in range(NEM_SPINES)}),
        loop="hold_on_last_frame", length=0.8)
    A["blackhole"] = anim("nemesis.blackhole", {
        "fx_shards": {"scale": 0.55, "rotation": [0, "q.anim_time * 600.0", 0]},
        "fx_ring_a": {"rotation": [0, "q.anim_time * 900.0", 0]},
        "fx_ring_b": {"rotation": [0, "-q.anim_time * 1100.0", 0]},
        "eye": {"scale": [0.9, 0.9, 1]},
        "lids": {"scale": [1.0, 0.7, 1]},
    })
    dash = {f"fx_tendril_{i}_{k}": {"rotation": [-38 + k * 12, 0, 0]} for i in range(NEM_TENDRILS) for k in range(3)}
    dash.update({f"fx_spine_{i}": {"rotation": [-22, 0, 0]} for i in range(NEM_SPINES)})
    dash["body"] = {"rotation": [24, 0, 0]}
    dash["fx_mandible_r"] = {"rotation": [0, -22, 22]}
    dash["fx_mandible_l"] = {"rotation": [0, 22, -22]}
    A["dash"] = anim("nemesis.dash", dash)
    A["roar"] = anim("nemesis.roar", dict({
        "body": {"position": ["math.sin(q.anim_time * 3000.0) * 0.8", 0, 0], "rotation": [-12, 0, 0]},
        "lids": {"scale": [1.25, 1.5, 1]},
        "eye": {"scale": [1.15, 1.15, 1]},
        "fx_mandible_r": {"rotation": [0, -28, 30]},
        "fx_mandible_l": {"rotation": [0, 28, -30]},
    }, **{f"fx_spine_{i}": {"scale": 1.25, "rotation": [-16, 0, 0]} for i in range(NEM_SPINES)}))
    def fall(t1):
        """崩れ落ちる（沈み・傾き・輪と破片が広がり・目が閉じる）を t1 秒で。"""
        return {
            "body": keys(position={0: [0, 0, 0], t1: [0, -10, 0]}, rotation={0: [0, 0, 0], t1: [30, 0, 20]}),
            "ring_a": keys(scale={0: [1, 1, 1], t1: [1.8, 1.8, 1.8]}),
            "ring_b": keys(scale={0: [1, 1, 1], t1: [2.2, 2.2, 2.2]}),
            "fx_shards": keys(scale={0: [1, 1, 1], t1: [2.4, 1.6, 2.4]}),
            "eye": keys(scale={0: [1.2, 1.2, 1], t1: [0.3, 0.3, 1]}),
        }
    # 普通の死（!q.is_alive）: 死んだ mob は 20 tick（1 秒）で煙になって消えるので、その前に終わる長さ
    A["death"] = anim("nemesis.death", fall(NEM_DEATH), loop="hold_on_last_frame", length=NEM_DEATH)
    # スクリプトで死なせる時（astro:mode = 8。生きたまま）: 2 秒かけて崩れ、invaders.bossDeath の最後の大爆発
    # （52 tick = 2.6 秒）で膨らんでから消える（全身 scale 0 のまま。スクリプトが entity.remove() する）
    dying = fall(2.0)
    dying["root"] = keys(scale={0: [1, 1, 1], 2.3: [1, 1, 1], 2.48: [1.15, 1.15, 1.15], NEM_DYING: [0, 0, 0]})
    A["dying"] = anim("nemesis.dying", dying, loop="hold_on_last_frame", length=NEM_DYING)
    modes = [("charge", 1), ("beam", 2), ("summon", 3), ("meteor", 4), ("blackhole", 5), ("dash", 6), ("roar", 7)]
    to_dying = [("dying", f"v.mode == {NEM_MODE_DYING}")]
    states = {"default": ([], [("dead", "!q.is_alive")] + to_dying + [(n, f"v.mode == {k}") for n, k in modes], 0)}
    for n, k in modes:
        tr = [("dead", "!q.is_alive")] + to_dying + [(o, f"v.mode == {j}") for o, j in modes if o != n]
        tr.append(("default", "v.mode == 0"))
        states[n] = ([n], tr, 0.2 if n != "dash" else 0.12)
    states["dead"] = (["death"], [], 0.2)
    states["dying"] = (["dying"], [], 0.2)      # 終わり（消えたまま。remove されるまで）
    A["ctrl"] = controller("nemesis", states)
    return A


def hologram_anims():
    A = {}
    T = "q.life_time"
    glitch = "(q.hurt_time > 0.0 ? 1.0 : (math.mod(q.life_time, 5.0) > 4.85 ? 0.5 : 0.0))"
    A["idle"] = anim("hologram_target.idle", {
        "holo_root": {"position": [f"math.sin({T} * 5000.0) * 0.9 * {glitch}", f"math.sin({T} * 100.0) * 0.4", 0],
                      "scale": [f"1.0 + math.sin({T} * 3700.0) * 0.08 * {glitch}", 1, 1]},
        "holo_scan": {"position": [0, f"math.mod({T} * 13.0, 31.0)", 0],
                      "scale": [f"1.0 - math.mod({T} * 13.0, 31.0) / 80.0", 1,
                                f"1.0 - math.mod({T} * 13.0, 31.0) / 80.0"]},
        "holo_reticle": {"rotation": [0, 0, f"math.mod({T} * 90.0, 360.0)"],
                         "scale": [f"1.0 + math.sin({T} * 240.0) * 0.06", f"1.0 + math.sin({T} * 240.0) * 0.06", 1]},
        "holo_arm_r": {"rotation": [f"math.sin({T} * 60.0) * 3.0", 0, 0]},
        "holo_arm_l": {"rotation": [f"-math.sin({T} * 60.0) * 3.0", 0, 0]},
        "holo_head": {"rotation": [0, f"math.sin({T} * 30.0) * 10.0", 0]},
    })
    return A


def bolt_anims():
    # 飛ぶ向き: バニラの矢・ロケット花火と同じ符号（ピッチも -q.target_x_rotation。+ だと下へ撃つ弾が上を向く）
    return {"move": anim("void_bolt.move", {"body": {"rotation": [
        "-q.target_x_rotation", "-q.target_y_rotation", "math.mod(q.life_time * 720.0, 360.0)"]}})}


# ===========================================================================
#  振る舞い（BP）
# ===========================================================================
def _no_friendly_fire():
    """侵略者どうし（ボルトの撃ち手を含む）は傷つけ合わない。"""
    return {"on_damage": {"filters": {"any_of": [
        {"test": "is_family", "subject": "other", "value": "astro_invader"},
        {"test": "is_family", "subject": "damager", "value": "astro_invader"}]}},
        "deals_damage": False}


def _mode_prop(hi):
    return {"astro:mode": {"type": "int", "range": [0, hi], "default": 0, "client_sync": True}}


def _player_targets(dist):
    return {"priority": 2, "must_see": True, "must_see_forget_duration": 6.0, "reselect_targets": True,
            "within_radius": dist, "entity_types": [
                {"filters": {"all_of": [{"test": "is_family", "subject": "other", "value": "player"},
                                        {"test": "has_ability", "subject": "other", "operator": "!=",
                                         "value": "instabuild"}]},
                 "max_dist": dist}]}


def _common(family, hp, box_w, box_h, loot, xp):
    c = {
        "minecraft:type_family": {"family": list(family) + ["monster", "mob"]},
        "minecraft:collision_box": {"width": box_w, "height": box_h},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:nameable": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True,
                                 "breathes_water": True},
        "minecraft:experience_reward": {"on_death": f"q.last_hit_by_player ? {xp} : 0"},
        "minecraft:loot": {"table": f"loot_tables/entities/{NS}_{loot}.json"},
    }
    return c


def entity_doc(ident, components, groups=None, events=None, props=None, spawnable=True):
    desc = {"identifier": f"{NS}:{ident}", "is_spawnable": spawnable, "is_summonable": True,
            "is_experimental": False}
    if props:
        desc["properties"] = props
    ent = {"description": desc}
    if groups:
        ent["component_groups"] = groups
    ent["components"] = components
    if events:
        ent["events"] = events
    return {"format_version": ENTITY_FMT, "minecraft:entity": ent}


def bp_drone():
    hp = ENEMIES["void_drone"]["health"]
    c = _common(["astro_invader", "astro_drone"], hp, 0.85, 0.95, "void_drone", 6)
    c.update({
        "minecraft:movement": {"value": 0.3},
        "minecraft:flying_speed": {"value": 0.16},
        "minecraft:movement.hover": {},
        "minecraft:navigation.hover": {"can_path_over_water": True, "can_sink": False, "can_pass_doors": False,
                                       "can_path_from_air": True, "avoid_water": True,
                                       "avoid_damage_blocks": True, "avoid_sun": False},
        "minecraft:can_fly": {},
        "minecraft:physics": {"has_gravity": False},
        "minecraft:jump.static": {},
        "minecraft:pushable": {"is_pushable": True, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 0.15},
        "minecraft:follow_range": {"value": 32, "max": 32},
        "minecraft:despawn": {"despawn_from_distance": {"min_distance": 48, "max_distance": 96}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:damage_sensor": {"triggers": [
            _no_friendly_fire(),
            {"cause": "fall", "deals_damage": False},
            {"cause": "fly_into_wall", "deals_damage": False}]},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": _player_targets(24),
        "minecraft:behavior.look_at_target": {"priority": 3},
        "minecraft:behavior.look_at_player": {"priority": 6, "look_distance": 16, "probability": 0.4},
    })
    groups = {
        "astro:roaming": {"minecraft:behavior.random_hover": {
            "priority": 8, "xz_dist": 10, "y_dist": 5, "y_offset": -1, "interval": 1, "hover_height": [2, 5]}},
    }
    events = {
        "minecraft:entity_spawned": {"add": {"component_groups": ["astro:roaming"]}},
        "astro:engage": {"remove": {"component_groups": ["astro:roaming"]}},
        "astro:disengage": {"add": {"component_groups": ["astro:roaming"]}},
    }
    return entity_doc("void_drone", c, groups, events, _mode_prop(3))


def bp_sentinel():
    hp = ENEMIES["void_sentinel"]["health"]
    c = _common(["astro_invader", "astro_sentinel"], hp, 1.3, 2.6, "void_sentinel", 10)
    c.update({
        "minecraft:attack": {"damage": 6},
        "minecraft:movement": {"value": 0.25},
        "minecraft:movement.basic": {},
        "minecraft:navigation.walk": {"can_path_over_water": True, "avoid_water": True, "can_walk": True,
                                      "avoid_damage_blocks": True},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": True},
        "minecraft:knockback_resistance": {"value": 0.6},
        "minecraft:follow_range": {"value": 32, "max": 32},
        "minecraft:despawn": {"despawn_from_distance": {"min_distance": 48, "max_distance": 96}},
        "minecraft:conditional_bandwidth_optimization": {},
        "minecraft:damage_sensor": {"triggers": [
            _no_friendly_fire(),
            {"cause": "fall", "damage_multiplier": 0.4}]},
        "minecraft:behavior.float": {"priority": 0},
        "minecraft:behavior.hurt_by_target": {"priority": 1},
        "minecraft:behavior.nearest_attackable_target": _player_targets(28),
        "minecraft:behavior.melee_attack": {"priority": 3, "speed_multiplier": 1.15, "track_target": True,
                                            "reach_multiplier": 1.6},
        "minecraft:behavior.random_stroll": {"priority": 6, "speed_multiplier": 0.8},
        "minecraft:behavior.look_at_player": {"priority": 7, "look_distance": 16},
        "minecraft:behavior.random_look_around": {"priority": 8},
    })
    return entity_doc("void_sentinel", c, props=_mode_prop(3))


def bp_nemesis():
    hp = ENEMIES["nemesis"]["health"]
    c = _common(["astro_invader", "astro_boss"], hp, 2.4, 3.8, "nemesis", 120)
    c.update({
        "minecraft:boss": {"should_darken_sky": True, "hud_range": 64},
        "minecraft:physics": {"has_gravity": False, "has_collision": True},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:fire_immune": True,
        "minecraft:persistent": {},
        "minecraft:follow_range": {"value": 64, "max": 64},
        "minecraft:damage_sensor": {"triggers": [
            _no_friendly_fire(),
            {"cause": "fall", "deals_damage": False},
            {"cause": "suffocation", "deals_damage": False},
            {"cause": "fly_into_wall", "deals_damage": False},
            {"cause": "drowning", "deals_damage": False},
            {"cause": "lava", "deals_damage": False},
            {"cause": "magma", "deals_damage": False},
            {"cause": "lightning", "damage_multiplier": 0.3}]},
    })
    props = _mode_prop(NEM_MODE_DYING)
    props["astro:phase"] = {"type": "int", "range": [1, 2], "default": 1, "client_sync": True}
    return entity_doc("nemesis", c, props=props)


def bp_hologram():
    hp = ENEMIES["hologram_target"]["health"]
    c = {
        "minecraft:type_family": {"family": ["astro_target", "mob"]},
        "minecraft:collision_box": {"width": 0.8, "height": 2.2},
        "minecraft:health": {"value": hp, "max": hp},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:knockback_resistance": {"value": 1.0},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:fire_immune": True,
        "minecraft:persistent": {},
        "minecraft:breathable": {"total_supply": 15, "suffocate_time": 0, "breathes_air": True,
                                 "breathes_water": True},
        "minecraft:damage_sensor": {"triggers": [
            {"cause": "fall", "deals_damage": False},
            {"cause": "suffocation", "deals_damage": False},
            {"cause": "drowning", "deals_damage": False},
            {"cause": "fire", "deals_damage": False},
            {"cause": "fire_tick", "deals_damage": False}]},
    }
    return entity_doc("hologram_target", c)


def bp_bolt():
    c = {
        "minecraft:type_family": {"family": ["astro_bolt", "inanimate"]},
        "minecraft:collision_box": {"width": 0.3, "height": 0.3},
        "minecraft:physics": {},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:conditional_bandwidth_optimization": {"default_values": {
            "max_optimized_distance": 80.0, "max_dropped_ticks": 5, "use_motion_prediction_hints": True}},
        "minecraft:projectile": {
            "on_hit": {"impact_damage": {"damage": 4, "knockback": True, "semi_random_diff_damage": False,
                                         "destroy_on_hit": True},
                       "remove_on_hit": {}},
            "power": 1.0, "gravity": 0.0, "inertia": 1.0, "liquid_inertia": 1.0,
            "uncertainty_base": 0.0, "uncertainty_multiplier": 0.0, "anchor": 1, "offset": [0, 0, 0],
            "should_bounce": False, "multiple_targets": False},
        "minecraft:timer": {"looping": False, "time": 4.0, "time_down_event": {"event": "astro:despawn"}},
    }
    return entity_doc("void_bolt", c, {"astro:despawn": {"minecraft:instant_despawn": {}}},
                      {"astro:despawn": {"add": {"component_groups": ["astro:despawn"]}}}, spawnable=False)


def bp_dmg_text():
    c = {
        "minecraft:type_family": {"family": ["astro_text", "inanimate"]},
        "minecraft:collision_box": {"width": 0.01, "height": 0.01},
        "minecraft:physics": {"has_gravity": False, "has_collision": False},
        "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
        "minecraft:damage_sensor": {"triggers": {"cause": "all", "deals_damage": False}},
        "minecraft:health": {"value": 1, "max": 1},
        "minecraft:nameable": {"always_show": True, "allow_name_tag_renaming": False},
        "minecraft:fire_immune": True,
        "minecraft:breathable": {"breathes_water": True, "breathes_air": True},
        "minecraft:timer": {"time": 2.0, "looping": False, "time_down_event": {"event": "astro:despawn"}},
    }
    return entity_doc("dmg_text", c, {"astro:despawn": {"minecraft:instant_despawn": {}}},
                      {"astro:despawn": {"add": {"component_groups": ["astro:despawn"]}}}, spawnable=False)


def loot_tables():
    def cells(lo, hi, looting=True):
        fn = [{"function": "set_count", "count": {"min": lo, "max": hi}}]
        if looting:
            fn.append({"function": "looting_enchant", "count": {"min": 0, "max": 1}})
        return {"type": "item", "name": f"{NS}:nano_cell", "weight": 1, "functions": fn}
    return {
        "void_drone": {"pools": [{"rolls": 1, "entries": [cells(1, 2)]}]},
        "void_sentinel": {"pools": [
            {"rolls": 1, "entries": [cells(2, 3)]},
            {"rolls": 1, "conditions": [{"condition": "random_chance_with_looting", "chance": 0.35,
                                         "looting_multiplier": 0.1}],
             "entries": [{"type": "item", "name": "minecraft:iron_ingot", "weight": 1,
                          "functions": [{"function": "set_count", "count": {"min": 1, "max": 2}}]}]}]},
        "nemesis": {"pools": [
            {"rolls": 1, "entries": [{"type": "item", "name": f"{NS}:solar_fragment", "weight": 1,
                                      "functions": [{"function": "set_count", "count": 2}]}]},
            {"rolls": 1, "entries": [cells(6, 10, looting=False)]},
            {"rolls": 1, "entries": [{"type": "item", "name": "minecraft:diamond", "weight": 1,
                                      "functions": [{"function": "set_count", "count": {"min": 1, "max": 3}}]}]}]},
    }


def spawn_rule(ident, weight, herd, density):
    return {"format_version": "1.8.0", "minecraft:spawn_rules": {
        "description": {"identifier": f"{NS}:{ident}", "population_control": "monster"},
        "conditions": [{
            "minecraft:spawns_on_surface": {},
            "minecraft:brightness_filter": {"min": 0, "max": 7, "adjust_for_weather": True},
            "minecraft:difficulty_filter": {"min": "easy", "max": "hard"},
            "minecraft:weight": {"default": weight},
            "minecraft:herd": {"min_size": herd[0], "max_size": herd[1]},
            "minecraft:density_limit": {"surface": density},
            "minecraft:biome_filter": {"all_of": [
                {"test": "has_biome_tag", "operator": "==", "value": "overworld"},
                {"test": "has_biome_tag", "operator": "!=", "value": "mushroom_island"}]},
        }]}}


# ===========================================================================
#  クライアント（RP）
# ===========================================================================
MAT_BODY = "entity_emissive_alpha_one_sided"     # 閉じた箱だけの体（裏面は描かない）
MAT_FX = "entity_emissive_alpha"                 # fx_* ボーン（薄いヒレ・輪・棘・触手）は両面
MAT_HOLO = "entity_beam_additive"                # ホログラム（加算合成・自己発光）

RENDER_CONTROLLERS = {
    f"controller.render.{NS}.invader": {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}, {"fx_*": "Material.fx"}],
        "textures": ["Texture.default"],
        # 被弾: 白っぽいマゼンタのフラッシュ / 溜め・第二形態: マゼンタの脈動（v.overlay）
        "is_hurt_color": {"r": 1.0, "g": 0.55, "b": 1.0, "a": 0.5},
        "overlay_color": {"r": 1.0, "g": 0.25, "b": 0.85, "a": "v.overlay"},
    },
    f"controller.render.{NS}.hologram": {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}, {"holo*": "Material.holo"}],
        "textures": ["Texture.default"],
        "is_hurt_color": {"r": 1.0, "g": 0.3, "b": 0.3, "a": 0.0},
    },
    f"controller.render.{NS}.plain": {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
    },
}


def client_doc(ident, materials, anims, animate, pre, rc, egg=None):
    d = {"identifier": f"{NS}:{ident}", "materials": materials,
         "textures": {"default": f"textures/entity/{NS}/{ident}"},
         "geometry": {"default": f"geometry.{NS}.{ident}"}}
    if anims:
        d["animations"] = anims
    scripts = {}
    if pre:
        scripts["pre_animation"] = pre
    if animate:
        scripts["animate"] = animate
    if scripts:
        d["scripts"] = scripts
    d["render_controllers"] = [rc]
    if egg:
        d["spawn_egg"] = {"base_color": egg[0], "overlay_color": egg[1]}
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": d}}


def clients():
    out = {}
    inv_mat = {"default": MAT_BODY, "fx": MAT_FX}
    A = drone_anims()
    out["void_drone"] = client_doc("void_drone", inv_mat, A, ["look", "idle", "ctrl"], [
        "v.mode = q.property('astro:mode');",
        "v.overlay = v.mode == 1 ? 0.16 + math.sin(q.life_time * 1440.0) * 0.12 : 0.0;",
    ], f"controller.render.{NS}.invader", ("#241A36", "#FF3CCE"))
    A = sentinel_anims()
    out["void_sentinel"] = client_doc("void_sentinel", inv_mat, A, ["walk", "ctrl"], [
        "v.mode = q.property('astro:mode');",
        f"v.ph = q.modified_distance_moved * {SENT_STEP_RATE:g};",
        f"v.ms = math.min(q.modified_move_speed * {SENT_MS:g}, 1.0);",
        "v.overlay = v.mode == 1 ? 0.12 + math.sin(q.life_time * 1800.0) * 0.1 : 0.0;",
    ], f"controller.render.{NS}.invader", ("#3A2E52", "#C24CFF"))
    A = nemesis_anims()
    out["nemesis"] = client_doc("nemesis", inv_mat, A, ["idle", "look", "ctrl"], [
        "v.mode = q.property('astro:mode');",
        "v.phase = q.property('astro:phase');",
        "v.spd = v.phase >= 2 ? 1.8 : 1.0;",
        "v.overlay = (v.mode == 1 || v.mode == 7) ? 0.18 + math.sin(q.life_time * 1600.0) * 0.12 : "
        "(v.phase >= 2 ? 0.06 + math.sin(q.life_time * 300.0) * 0.05 : 0.0);",
    ], f"controller.render.{NS}.invader", ("#0C0818", "#A040FF"))
    A = hologram_anims()
    out["hologram_target"] = client_doc("hologram_target", {"default": MAT_BODY, "holo": MAT_HOLO}, A,
                                        ["idle"], None, f"controller.render.{NS}.hologram",
                                        ("#1C3A48", "#6FF0FF"))
    A = bolt_anims()
    out["void_bolt"] = client_doc("void_bolt", {"default": MAT_FX}, A, ["move"], None,
                                  f"controller.render.{NS}.plain")
    out["dmg_text"] = client_doc("dmg_text", {"default": "entity_alphatest"}, None, None, None,
                                 f"controller.render.{NS}.plain")
    return out


# ===========================================================================
#  書き出し
# ===========================================================================
BUILDERS = {
    "void_drone": (build_drone, inv_styles, 11),
    "void_sentinel": (build_sentinel, inv_styles, 23),
    "nemesis": (build_nemesis, inv_styles, 37),
    "hologram_target": (build_hologram, holo_styles, 5),
    "void_bolt": (build_bolt, inv_styles, 3),
    "dmg_text": (build_dmg_text, None, 0),
}
BEHAVIOURS = {
    "void_drone": bp_drone, "void_sentinel": bp_sentinel, "nemesis": bp_nemesis,
    "hologram_target": bp_hologram, "void_bolt": bp_bolt, "dmg_text": bp_dmg_text,
}
SPAWN_RULES = {"void_drone": (12, (1, 2), 4), "void_sentinel": (5, (1, 1), 2)}


def write_models(only):
    models = {}
    for ident, (fn, styles, seed) in BUILDERS.items():
        if only and ident not in only:
            continue
        m = fn()
        geo_path = os.path.join(GEO_DIR, f"{NS}_{ident}.geo.json")
        tex_path = os.path.join(TEX_DIR, f"{ident}.png")
        os.makedirs(GEO_DIR, exist_ok=True)
        os.makedirs(TEX_DIR, exist_ok=True)
        if styles is None:
            write_json(geo_path, {"format_version": "1.12.0", "minecraft:geometry": [m.to_json()]})
            Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(tex_path)
        else:
            m.write(geo_path)
            p = InvaderPainter(m.tex_w, m.tex_h, seed)
            p.paint_model(m, styles())
            p.save(tex_path)
        models[ident] = m
        print(f"  {ident:16s} {len(m.bones):3d} bones {len(m.all_cubes()):4d} cubes  {m.tex_w}x{m.tex_h}"
              f" @x{m.uv_scale}")
    return models


def write_data():
    ANIMS.clear()
    CTRLS.clear()
    cl = clients()
    for ident, doc in cl.items():
        write_json(os.path.join(RP, "entity", f"{ident}.entity.json"), doc)
    write_json(ANIM_FILE, {"format_version": "1.8.0", "animations": dict(sorted(ANIMS.items()))})
    write_json(CTRL_FILE, {"format_version": "1.10.0", "animation_controllers": dict(sorted(CTRLS.items()))})
    write_json(RC_FILE, {"format_version": "1.10.0", "render_controllers": RENDER_CONTROLLERS})
    for ident, fn in BEHAVIOURS.items():
        write_json(os.path.join(BP, "entities", f"{ident}.json"), fn())
    for name, doc in loot_tables().items():
        write_json(os.path.join(BP, "loot_tables", "entities", f"{NS}_{name}.json"), doc)
    for ident, (w, herd, dens) in SPAWN_RULES.items():
        write_json(os.path.join(BP, "spawn_rules", f"{ident}.json"), spawn_rule(ident, w, herd, dens))
    print(f"  {len(cl)} client entities, {len(ANIMS)} animations, {len(CTRLS)} controllers, "
          f"{len(RENDER_CONTROLLERS)} render controllers, {len(loot_tables())} loot tables, "
          f"{len(SPAWN_RULES)} spawn rules")


# ===========================================================================
#  検査（validate_astro より細かい、このファイルの生成物だけの検査）
# ===========================================================================
def _molang_ok(sx):
    depth = 0
    for ch in sx:
        depth += ch == "("
        depth -= ch == ")"
        if depth < 0:
            return False
    return depth == 0


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def check():
    errs = []

    def load(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    anims = load(ANIM_FILE)["animations"]
    ctrls = load(CTRL_FILE)["animation_controllers"]
    rcs = load(RC_FILE)["render_controllers"]
    items = set()
    for fn in os.listdir(os.path.join(BP, "items")):
        if fn.endswith(".json"):
            items.add(load(os.path.join(BP, "items", fn))["minecraft:item"]["description"]["identifier"])
    for ident in BUILDERS:
        geo = load(os.path.join(GEO_DIR, f"{NS}_{ident}.geo.json"))["minecraft:geometry"][0]
        tw, th = geo["description"]["texture_width"], geo["description"]["texture_height"]
        im = Image.open(os.path.join(TEX_DIR, f"{ident}.png"))
        if im.size != (tw, th):
            errs.append(f"{ident}: texture {im.size} != {tw}x{th}")
        bones = {b["name"] for b in geo["bones"]}
        if geo["description"]["identifier"] != f"geometry.{NS}.{ident}":
            errs.append(f"{ident}: geometry id {geo['description']['identifier']}")
        for b in geo["bones"]:
            if b.get("parent") and b["parent"] not in bones:
                errs.append(f"{ident}: {b['name']} parent {b['parent']} missing")
            for c in b.get("cubes", []):
                for face, fuv in c["uv"].items():
                    u, v = fuv["uv"]
                    w, h = fuv["uv_size"]
                    if u < 0 or v < 0 or u + w > tw or v + h > th:
                        errs.append(f"{ident}: {b['name']} {face} uv outside")
        cl = load(os.path.join(RP, "entity", f"{ident}.entity.json"))["minecraft:client_entity"]["description"]
        beh = load(os.path.join(BP, "entities", f"{ident}.json"))["minecraft:entity"]
        props = set(beh["description"].get("properties", {}))
        amap = cl.get("animations", {})
        for key, aname in amap.items():
            if aname.startswith("controller."):
                if aname not in ctrls:
                    errs.append(f"{ident}: controller {aname} missing")
                    continue
                st = ctrls[aname]["states"]
                if ctrls[aname]["initial_state"] not in st:
                    errs.append(f"{aname}: initial state missing")
                for sn, sd in st.items():
                    for a in sd.get("animations", []):
                        if a not in amap:
                            errs.append(f"{aname}.{sn}: plays {a} which {ident} does not map")
                    for tr in sd.get("transitions", []):
                        for tgt in tr:
                            if tgt not in st:
                                errs.append(f"{aname}.{sn}: transition to unknown {tgt}")
                reach = {ctrls[aname]["initial_state"]}
                changed = True
                while changed:
                    changed = False
                    for sn in list(reach):
                        for tr in st[sn].get("transitions", []):
                            for tgt in tr:
                                if tgt not in reach:
                                    reach.add(tgt)
                                    changed = True
                for sn in st:
                    if sn not in reach:
                        errs.append(f"{aname}: state {sn} unreachable")
            elif aname not in anims:
                errs.append(f"{ident}: animation {aname} missing")
            else:
                for bn in anims[aname]["bones"]:
                    if bn not in bones:
                        errs.append(f"{ident}: {aname} animates missing bone {bn}")
        for key in cl.get("scripts", {}).get("animate", []):
            if key not in amap:
                errs.append(f"{ident}: animate {key} not mapped")
        for rc in cl["render_controllers"]:
            if rc not in rcs:
                errs.append(f"{ident}: render controller {rc} missing")
                continue
            for mm in rcs[rc]["materials"]:
                for mat in mm.values():
                    if mat.split(".", 1)[1] not in cl["materials"]:
                        errs.append(f"{ident}: {rc} uses {mat} but the client entity has no such material")
            for sx in _strings(rcs[rc]):
                for var in __import__("re").findall(r"v\.(\w+)", sx):
                    pre = " ".join(cl.get("scripts", {}).get("pre_animation", []))
                    if f"v.{var} =" not in pre:
                        errs.append(f"{ident}: {rc} reads v.{var} which pre_animation never sets")
        for sx in _strings(cl):
            if not _molang_ok(sx):
                errs.append(f"{ident}: unbalanced molang {sx[:60]}")
            for pn in __import__("re").findall(r"q\.property\('([^']+)'\)", sx):
                if pn not in props:
                    errs.append(f"{ident}: q.property('{pn}') not declared in BP")
        txt = json.dumps(beh)
        for lt in __import__("re").findall(r'"table": "([^"]+)"', txt):
            path = os.path.join(BP, lt)
            if not os.path.exists(path):
                errs.append(f"{ident}: loot {lt} missing")
                continue
            for sx in _strings(load(path)):
                if sx.startswith(f"{NS}:") and sx not in items:
                    errs.append(f"{lt}: unknown item {sx}")
        evs = beh.get("events", {})
        groups = beh.get("component_groups", {})
        for en, ev in evs.items():
            for op in ("add", "remove"):
                for g in ev.get(op, {}).get("component_groups", []):
                    if g not in groups:
                        errs.append(f"{ident}: event {en} uses unknown group {g}")
        for sx in _strings(beh):
            if sx.startswith("astro:") and sx not in evs and sx not in groups and sx not in props \
                    and sx != f"{NS}:{ident}":
                pass
    for name, a in anims.items():
        for sx in _strings(a):
            if not _molang_ok(sx):
                errs.append(f"{name}: unbalanced molang {sx[:60]}")
    import astro_animcheck as AK
    errs += AK.seam_errors(anims)
    errs += stride_check(load(os.path.join(GEO_DIR, f"{NS}_void_sentinel.geo.json"))["minecraft:geometry"][0])
    d = anims.get(f"animation.{NS}.nemesis.death", {}).get("animation_length", 0)
    if d > 0.95:
        errs.append(f"nemesis.death is {d}s: a dead mob vanishes after 1.0s")
    for name, c in ctrls.items():
        for sx in _strings(c):
            if not _molang_ok(sx):
                errs.append(f"{name}: unbalanced molang {sx[:60]}")
    for fn in os.listdir(os.path.join(BP, "spawn_rules")):
        ident = load(os.path.join(BP, "spawn_rules", fn))["minecraft:spawn_rules"]["description"]["identifier"]
        if ident.startswith(f"{NS}:") and not os.path.exists(os.path.join(BP, "entities", ident[6:] + ".json")):
            errs.append(f"spawn rule {fn}: unknown entity {ident}")
    for e in errs:
        print("  ERROR", e)
    print(f"  check: {len(errs)} error(s)")
    return not errs


# ===========================================================================
#  プレビュー（build_preview/astro/enemy_<id>.png）
# ===========================================================================
def _ternary(sx):
    """Molang の a ? b : c（入れ子・括弧あり）を Python の (b if a else c) に直す。"""
    out, i = "", 0
    while i < len(sx):
        if sx[i] == "(":
            depth, j = 1, i + 1
            while depth:
                depth += {"(": 1, ")": -1}.get(sx[j], 0)
                j += 1
            out += "(" + _ternary(sx[i + 1:j - 1]) + ")"
            i = j
        else:
            out += sx[i]
            i += 1
    depth = 0
    for k, ch in enumerate(out):
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "?" and depth == 0:
            cond, rest = out[:k], out[k + 1:]
            d2, q = 0, 0
            for j, c2 in enumerate(rest):
                d2 += {"(": 1, ")": -1}.get(c2, 0)
                if d2 == 0 and c2 == "?":
                    q += 1
                elif d2 == 0 and c2 == ":":
                    if q == 0:
                        return f"(({rest[:j]}) if ({cond}) else ({_ternary(rest[j + 1:])}))"
                    q -= 1
    return out


def molang(expr, env):
    """プレビュー用の小さな Molang 評価（数式・比較・論理・三項演算子）。失敗したら 0。"""
    if isinstance(expr, (int, float)):
        return float(expr)
    import re
    py = expr
    for a, b in (("math.sin(", "_sin("), ("math.cos(", "_cos("), ("math.max(", "max("), ("math.min(", "min("),
                 ("math.abs(", "abs("), ("math.mod(", "_mod("), ("math.clamp(", "_clamp("), ("&&", " and "),
                 ("||", " or ")):
        py = py.replace(a, b)
    py = re.sub(r"\b([qv])\.(\w+)", r"\1_\2", py)
    py = re.sub(r"!(?!=)", " not ", py)
    py = _ternary(py)
    g = {"_sin": lambda d: math.sin(math.radians(d)), "_cos": lambda d: math.cos(math.radians(d)),
         "_mod": math.fmod, "_clamp": lambda x, a, b: max(a, min(b, x)), "max": max, "min": min, "abs": abs}
    try:
        return float(eval(py, g, dict(env)))  # noqa: S307 (自分で書いた式だけ)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"preview molang: {expr} -> {py}: {exc}")


def sample_pose(ident, names, t, env):
    """ANIMS（animation.astro.<ident>.<名前>）を時刻 t で評価して足し合わせたボーンの姿勢。"""
    out = {}
    env = dict(env, q_anim_time=t)
    for n in names:
        a = ANIMS.get(f"animation.{NS}.{ident}.{n}")
        if a is None:
            raise KeyError(f"animation.{NS}.{ident}.{n}")
        for bone, tr in a.get("bones", {}).items():
            e = out.setdefault(bone, {"rotation": [0, 0, 0], "position": [0, 0, 0], "scale": [1, 1, 1]})
            for ch, v in tr.items():
                if isinstance(v, dict):
                    ts = sorted(v, key=float)
                    prev = max([k for k in ts if float(k) <= t] or [ts[0]], key=float)
                    nxt = min([k for k in ts if float(k) >= t] or [ts[-1]], key=float)
                    a0, a1 = v[prev], v[nxt]
                    k = 0.0 if nxt == prev else (t - float(prev)) / (float(nxt) - float(prev))
                    v = [molang(x, env) * (1 - k) + molang(y, env) * k for x, y in zip(a0, a1)] \
                        if isinstance(a0, list) else molang(a0, env)
                if not isinstance(v, list):
                    v = [v, v, v]
                vals = [molang(x, env) for x in v]
                if ch == "scale":
                    e["scale"] = [e["scale"][i] * vals[i] for i in range(3)]
                else:
                    e[ch] = [e[ch][i] + vals[i] for i in range(3)]
    return out


PREVIEWS = {
    # (yaw, pitch, [アニメ名], 時刻, 環境)
    "void_drone": [(0, -8, ["idle"], 0, {}), (35, -18, ["idle"], 0.4, {}), (100, -6, ["idle", "charge"], 0.3, {}),
                   (200, -12, ["idle"], 0, {}), (25, -10, ["idle", "fire"], 0.05, {})],
    "void_sentinel": [(0, -6, ["walk"], 0, {}), (35, -10, ["walk"], 0, {}),
                      (90, -4, ["walk"], 0, {"v_ph": 90, "v_ms": 1}), (200, -10, ["walk"], 0, {}),
                      (40, -8, ["windup"], 0.8, {}), (70, -6, ["slam"], 0.14, {}), (25, -10, ["swing"], 0.16, {})],
    "nemesis": [(0, -6, ["idle"], 0, {"q_life_time": 0.0}), (35, -14, ["idle"], 0, {"q_life_time": 1.2}),
                (90, -4, ["idle"], 0, {"q_life_time": 2.5}), (200, -14, ["idle"], 0, {"q_life_time": 3.1}),
                (30, -10, ["idle", "roar"], 0.5, {"q_life_time": 0.7}),
                (80, -6, ["idle", "dash"], 0.2, {"q_life_time": 1.7})],
    "hologram_target": [(0, -8, ["idle"], 0, {"q_life_time": 1.0}), (35, -16, ["idle"], 0, {"q_life_time": 1.4}),
                        (90, -4, ["idle"], 0, {"q_life_time": 0.2}), (200, -14, ["idle"], 0, {"q_life_time": 2.1})],
    "void_bolt": [(0, -8, [], 0, {}), (60, -30, [], 0, {}), (90, 0, [], 0, {})],
}
ENV0 = {"q_life_time": 0.0, "q_anim_time": 0.0, "v_ph": 0.0, "v_ms": 0.0, "v_spd": 1.0, "q_hurt_time": 0.0,
        "q_target_x_rotation": 0.0, "q_target_y_rotation": 0.0, "v_attack_time": 0.0, "v_mode": 0, "v_phase": 1}


def preview(only):
    if not ANIMS:
        write_data()
    os.makedirs(SCRATCH, exist_ok=True)
    for ident, views in PREVIEWS.items():
        if only and ident not in only:
            continue
        geo = json.load(open(os.path.join(GEO_DIR, f"{NS}_{ident}.geo.json"), encoding="utf-8"))
        geo = geo["minecraft:geometry"][0]
        tex = Image.open(os.path.join(TEX_DIR, f"{ident}.png"))
        tiles = []
        for yaw, pitch, names, t, env in views:
            pose = sample_pose(ident, names, t, dict(ENV0, **env))
            tiles.append(render(geo, tex, yaw, pitch, 380, pose=pose))
        path = os.path.join(SCRATCH, f"enemy_{ident}.png")
        sheet(tiles, path, cols=min(4, len(tiles)), label=f"{NS}:{ident}")
        print(f"  preview {path}")


def main(argv):
    only = None
    for a in argv:
        if a.startswith("--only"):
            only = set(a.split("=", 1)[1].split(",")) if "=" in a else None
    if only:
        only = {k for k in BUILDERS if any(o in k for o in only)}
    write_models(only)
    write_data()
    ok = check()
    if "--preview" in argv:
        preview(only)
    if "--test" in argv:
        ok = run_js_test() and ok
    return 0 if ok else 1


def run_js_test():
    return js_smoke_test()



# ===========================================================================
#  invaders.js のスモークテスト（@minecraft/server を動くスタブに差し替えて Node で走らせる）
# ===========================================================================
JS_SERVER = r"""
const G = globalThis;
G.__log = { particles: new Map(), sounds: new Map(), warns: [], props: new Map(), events: new Map(),
            dmg: new Map(), titles: [] };
G.__handlers = {};
const timeouts = [];
const intervals = [];
export const system = {
  currentTick: 0,
  run(f) { timeouts.push({ due: this.currentTick + 1, f }); return 0; },
  runTimeout(f, t = 1) { timeouts.push({ due: this.currentTick + Math.max(1, t), f }); return 0; },
  runInterval(f, t = 1) { intervals.push({ every: Math.max(1, t), f }); return 0; },
  runJob() { }, clearRun() { },
  afterEvents: { scriptEventReceive: { subscribe(f) { G.__handlers.scriptEventReceive = f; } } },
  beforeEvents: { watchdogTerminate: { subscribe() { } }, startup: { subscribe() { } } },
};
G.__runTimers = (t) => {
  for (const iv of intervals) if (t % iv.every === 0) { try { iv.f(); } catch (e) { G.__log.warns.push("interval: " + e.stack); } }
  const due = timeouts.filter((x) => x.due <= t);
  for (const x of due) timeouts.splice(timeouts.indexOf(x), 1);
  for (const x of due) { try { x.f(); } catch (e) { G.__log.warns.push("timeout: " + e.stack); } }
};
const events = new Proxy({}, { get(_, name) { return { subscribe(f) { G.__handlers[name] = f; return f; }, unsubscribe() { } }; } });
export class MolangVariableMap {
  setFloat(k, v) { if (!Number.isFinite(v)) throw new Error(`non-finite molang ${k}=${v}`); }
  setColorRGB() { } setColorRGBA() { } setVector3() { }
}
export class ItemStack { constructor(typeId, amount = 1) { this.typeId = typeId; this.amount = amount; } }
export const EntityDamageCause = new Proxy({}, { get: (_, k) => String(k) });
export const GameMode = { survival: "survival", creative: "creative", adventure: "adventure", spectator: "spectator" };

const FAMILIES = {
  "astro:void_drone": ["astro_invader", "astro_drone", "monster", "mob"],
  "astro:void_sentinel": ["astro_invader", "astro_sentinel", "monster", "mob"],
  "astro:nemesis": ["astro_invader", "astro_boss", "monster", "mob"],
  "astro:hologram_target": ["astro_target", "mob"],
  "minecraft:player": ["player", "mob"],
};
const HP = { "astro:void_drone": 20, "astro:void_sentinel": 44, "astro:nemesis": 480, "astro:hologram_target": 200 };
const PROPS = { "astro:void_drone": { "astro:mode": 0 }, "astro:void_sentinel": { "astro:mode": 0 },
                "astro:nemesis": { "astro:mode": 0, "astro:phase": 1 } };

let nextId = 1;
export class FakeEntity {
  constructor(dim, typeId, loc, hp) {
    this.id = String(nextId++);
    this.typeId = typeId;
    this.dimension = dim;
    this.location = { ...loc };
    this.vel = { x: 0, y: 0, z: 0 };
    this.hp = hp ?? HP[typeId] ?? 10; this.maxHp = this.hp;
    this.alive = true;
    this.rot = { x: 0, y: 0 };
    this.tags = new Set();
    this.props = new Map(Object.entries(PROPS[typeId] ?? {}));
    this.dyn = new Map();
    this.effects = [];
    this.nameTag = "";
    this.isOnGround = true; this.isSneaking = false;
    this.selectedSlotIndex = 0;
    this.inv = [];
    this.mode = "survival";
    this.born = system.currentTick;
    this.lastHurt = -99;
    this.onScreenDisplay = { setActionBar: (m) => { this.actionbar = m; }, setTitle: (t, o) => { this.title = t; G.__log.titles.push(t); } };
    dim.entities.push(this);
  }
  isValid() { return this.alive; }
  getComponent(name) {
    const e = this;
    if (name === "minecraft:health" && e.typeId !== "astro:void_bolt") {
      return { get currentValue() { return e.hp; }, get effectiveMax() { return e.maxHp; },
               setCurrentValue(v) { e.hp = Math.max(0, Math.min(e.maxHp, v)); return true; } };
    }
    if (name === "minecraft:projectile" && e.typeId === "astro:void_bolt" && !G.__noShoot) {
      return { owner: undefined, shoot(v) {
        for (const k of ["x", "y", "z"]) if (!Number.isFinite(v[k])) throw new Error("bad shoot");
        e.vel = { ...v }; e.projectile = this; } };
    }
    if (name === "minecraft:inventory") {
      return { container: { size: 36, getItem: (i) => e.inv[i], setItem: (i, it) => { e.inv[i] = it; } } };
    }
    return undefined;
  }
  hasComponent(n) { return !!this.getComponent(n); }
  getProperty(k) { if (!this.props.has(k)) throw new Error(`no property ${k} on ${this.typeId}`); return this.props.get(k); }
  setProperty(k, v) {
    if (!this.props.has(k)) throw new Error(`no property ${k} on ${this.typeId}`);
    if (!Number.isInteger(v)) throw new Error(`bad property value ${k}=${v}`);
    this.props.set(k, v);
    const key = `${this.typeId}|${k}`;
    if (!G.__log.props.has(key)) G.__log.props.set(key, new Set());
    G.__log.props.get(key).add(v);
  }
  triggerEvent(n) { const key = `${this.typeId}|${n}`; G.__log.events.set(key, (G.__log.events.get(key) ?? 0) + 1); }
  addTag(t) { this.tags.add(t); return true; } hasTag(t) { return this.tags.has(t); }
  removeTag(t) { return this.tags.delete(t); } getTags() { return [...this.tags]; }
  applyDamage(amount, opts) {
    if (!Number.isFinite(amount) || amount <= 0) throw new Error("bad damage " + amount);
    if (opts && opts.damagingEntity && !opts.damagingEntity.alive) throw new Error("damagingEntity invalid");
    this.hp -= amount;
    const src = opts?.damagingEntity?.typeId ?? "none";
    if (this.typeId === "minecraft:player") {
      const key = `${src}|${opts?.cause ?? "?"}`;
      G.__log.dmg.set(key, (G.__log.dmg.get(key) ?? 0) + amount);
    }
    G.__onHurt?.(this, amount, { cause: opts?.cause, damagingEntity: opts?.damagingEntity });
    return true;
  }
  applyImpulse(v) {
    if (this.typeId === "minecraft:player") throw new Error("applyImpulse on player");
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(v[k])) throw new Error("bad impulse");
    this.vel.x += v.x; this.vel.y += v.y; this.vel.z += v.z;
  }
  clearVelocity() { this.vel = { x: 0, y: 0, z: 0 }; }
  applyKnockback(dx, dz, h, v) {
    for (const x of [dx, dz, h, v]) if (!Number.isFinite(x)) throw new Error("bad knockback");
    this.vel = { x: dx * h, y: v, z: dz * h };
  }
  addEffect(id, ticks, o) { if (!Number.isFinite(ticks) || ticks <= 0) throw new Error("bad effect"); this.effects.push(id); }
  removeEffect() { }
  setRotation(r) { if (!Number.isFinite(r.x) || !Number.isFinite(r.y)) throw new Error("bad rotation"); this.rot = { ...r }; }
  getRotation() { return { ...this.rot }; }
  teleport(loc) { for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad teleport"); this.location = { ...loc }; }
  getViewDirection() { const y = this.rot.y * Math.PI / 180; return { x: -Math.sin(y), y: 0, z: Math.cos(y) }; }
  getVelocity() { return { ...this.vel }; }
  getHeadLocation() { return { x: this.location.x, y: this.location.y + 1.6, z: this.location.z }; }
  getDynamicProperty(k) { return this.dyn.get(k); } setDynamicProperty(k, v) { this.dyn.set(k, v); }
  remove() { this.alive = false; const a = this.dimension.entities; const i = a.indexOf(this); if (i >= 0) a.splice(i, 1); }
  kill() { this.hp = 0; }
  runCommand(c) { return {}; }
  getGameMode() { return this.mode; }
  sendMessage(m) { this.lastMessage = m; }
  playAnimation() { }
  matches(o) { return (o.families ?? []).every((f) => (FAMILIES[this.typeId] ?? []).includes(f)); }
}

export class FakeDimension {
  constructor(id) { this.id = id; this.entities = []; }
  spawnParticle(id, loc, vars) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad particle loc ${id}`);
    G.__log.particles.set(id, (G.__log.particles.get(id) ?? 0) + 1);
  }
  playSound(id, loc) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error(`bad sound loc ${id}`);
    G.__log.sounds.set(id, (G.__log.sounds.get(id) ?? 0) + 1);
  }
  getEntities(q = {}) {
    let list = this.entities.filter((e) => e.alive);
    if (q.type) list = list.filter((e) => e.typeId === q.type);
    if (q.families) list = list.filter((e) => q.families.every((f) => (FAMILIES[e.typeId] ?? []).includes(f)));
    if (q.tags) list = list.filter((e) => q.tags.every((t) => e.tags.has(t)));
    if (q.location && q.maxDistance !== undefined) {
      if (!Number.isFinite(q.maxDistance)) throw new Error("bad query");
      list = list.filter((e) => Math.hypot(e.location.x - q.location.x, e.location.y - q.location.y, e.location.z - q.location.z) <= q.maxDistance);
    }
    return list;
  }
  spawnEntity(type, loc) {
    for (const k of ["x", "y", "z"]) if (!Number.isFinite(loc[k])) throw new Error("bad spawn loc");
    if (!G.__entityIds.has(type)) throw new Error(`unknown entity ${type}`);
    return new FakeEntity(this, type, loc);
  }
  getBlock(loc) {
    const solid = loc.y < 64 || (G.__ceiling && loc.y >= 70 && loc.y < 71);
    return { typeId: solid ? "minecraft:stone" : "minecraft:air", isAir: !solid, isLiquid: false };
  }
}

const dims = { overworld: new FakeDimension("minecraft:overworld"), nether: new FakeDimension("minecraft:nether"),
               the_end: new FakeDimension("minecraft:the_end") };
G.__dims = dims;
G.__time = 18000;
export const world = {
  afterEvents: events, beforeEvents: events,
  getAllPlayers() { return Object.values(dims).flatMap((d) => d.entities.filter((e) => e.typeId === "minecraft:player" && e.alive)); },
  getPlayers() { return this.getAllPlayers(); },
  getDimension(id) { return dims[String(id).replace("minecraft:", "")]; },
  getEntity(id) { return Object.values(dims).flatMap((d) => d.entities).find((e) => e.id === id); },
  getTimeOfDay() { return G.__time; },
  getAbsoluteTime() { return system.currentTick; },
  getDynamicProperty() { return undefined; }, setDynamicProperty() { },
  sendMessage() { }, gameRules: {},
};
export default {};
"""

JS_UI = r"""
class Form { title() { return this; } body() { return this; } button() { return this; } toggle() { return this; }
  dropdown() { return this; } slider() { return this; } textField() { return this; }
  show() { return Promise.resolve({ canceled: true }); } }
export const ActionFormData = Form; export const ModalFormData = Form; export const MessageFormData = Form;
export const FormCancelationReason = {};
export default {};
"""

JS_TEST = r"""
import { FakeEntity, system } from "@minecraft/server";
const G = globalThis;
let seed = Number(process.env.ASTRO_SEED ?? 12345);
Math.random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
const origWarn = console.warn;
console.warn = (...a) => { G.__log.warns.push(a.join(" ")); };
const INV = await import("./invaders.js");
let fails = 0;
const fail = (m) => { fails++; console.log("  FAIL " + m); };
const ow = G.__dims.overworld;
G.__onHurt = (e, dmg, src) => { INV.onInvaderHurt(e, dmg, src); if (e.hp <= 0 && e.alive && e.typeId !== "minecraft:player") { INV.onInvaderDie(e, src); e.remove(); } };

function physics() {
  for (const d of Object.values(G.__dims)) {
    for (const e of [...d.entities]) {
      if (!e.alive) continue;
      if (e.typeId === "minecraft:player") {
        e.location.x += e.vel.x; e.location.y = Math.max(64, e.location.y + e.vel.y); e.location.z += e.vel.z;
        e.vel = { x: e.vel.x * 0.5, y: e.vel.y * 0.5 - 0.04, z: e.vel.z * 0.5 };
        e.isOnGround = e.location.y <= 64.001;
        continue;
      }
      if (e.typeId === "astro:void_bolt") {
        e.location.x += e.vel.x; e.location.y += e.vel.y; e.location.z += e.vel.z;
        if (e.projectile) {
          for (const p of d.entities.filter((x) => x.typeId === "minecraft:player")) {
            const c = { x: p.location.x, y: p.location.y + 1, z: p.location.z };
            if (Math.hypot(c.x - e.location.x, c.y - e.location.y, c.z - e.location.z) < 0.9) {
              p.applyDamage(4, { cause: "projectile", damagingEntity: e.projectile.owner?.alive ? e.projectile.owner : undefined });
              e.remove(); break;
            }
          }
          if (e.alive && (e.location.y < 64 || system.currentTick - e.born > 80)) e.remove();
        }
        continue;
      }
      e.location.x += e.vel.x; e.location.y += e.vel.y; e.location.z += e.vel.z;
      e.vel = { x: e.vel.x * 0.91, y: e.vel.y * 0.91, z: e.vel.z * 0.91 };
      if (e.typeId === "astro:void_sentinel" || e.typeId === "astro:hologram_target") { e.location.y = 64; e.vel.y = 0; }
      if (e.location.y < 64) { e.location.y = 64; e.vel.y = 0; }
    }
  }
}
function run(n, every = 1, each) {
  for (let i = 0; i < n; i++) {
    system.currentTick++;
    const t = system.currentTick;
    G.__runTimers(t);
    if (t % every === 0) INV.tickInvaders(t);
    physics();
    each?.(t);
  }
}
function clear() {
  for (const d of Object.values(G.__dims)) for (const e of [...d.entities]) e.remove();
  G.__log.dmg.clear(); G.__log.props.clear(); G.__log.events.clear(); G.__log.titles.length = 0;
}
function dmgFrom(type) { let s = 0; for (const [k, v] of G.__log.dmg) if (k.startsWith(type + "|")) s += v; return s; }
function invWarns() { return G.__log.warns.filter((w) => w.includes("[astro] invaders") || w.includes("Error")); }

// ---- 1) ドローン・センチネル・ネメシスと戦うプレイヤー（毎 tick 呼ぶ）-------------------------
for (const [label, every, noShoot] of [["every tick", 1, false], ["every 2 ticks + scripted bolts", 2, true]]) {
  clear();
  G.__noShoot = noShoot;
  const p = new FakeEntity(ow, "minecraft:player", { x: 0, y: 64, z: 0 }, 1e6);
  p.name = "Tester";
  const drone = new FakeEntity(ow, "astro:void_drone", { x: 6, y: 67, z: 6 });
  const sentinel = new FakeEntity(ow, "astro:void_sentinel", { x: 3, y: 64, z: 0 });
  const boss = new FakeEntity(ow, "astro:nemesis", { x: 0, y: 66, z: 12 });
  INV.onInvaderSpawn(drone); INV.onInvaderSpawn(sentinel); INV.onInvaderSpawn(boss);
  const warns0 = G.__log.warns.length;
  const t0 = system.currentTick;
  run(1200, every, (t) => {
    // プレイヤーはゆっくり円を描いて歩き、時々跳ぶ。500 tick 目にボスの体力を 45% に
    const k = t - t0;
    p.location.x = Math.cos(k / 120) * 2; p.location.z = Math.sin(k / 120) * 2;
    if (k % 97 === 0) { p.vel.y = 0.42; }
    if (k === 500) { boss.hp = boss.maxHp * 0.45; INV.onInvaderHurt(boss, 1, { cause: "entityAttack", damagingEntity: p }); }
    if (boss.hp < 20) boss.hp = 200;     // テスト中に落ちないように
  });
  const w = invWarns().slice(0, 5);
  if (G.__log.warns.length > warns0 && w.length) fail(`[${label}] warnings: ${w.join(" / ").slice(0, 800)}`);
  for (const [type, min] of [["astro:void_drone", 1], ["astro:void_sentinel", 1], ["astro:nemesis", 1]]) {
    const d = dmgFrom(type);
    if (d < min) fail(`[${label}] player took no damage from ${type}`);
  }
  const modes = G.__log.props.get("astro:nemesis|astro:mode") ?? new Set();
  for (const m of [1, 2, 3, 4, 5, 6, 7]) if (!modes.has(m)) fail(`[${label}] nemesis never entered mode ${m} (seen ${[...modes]})`);
  if (boss.props.get("astro:phase") !== 2) fail(`[${label}] nemesis did not enter phase 2`);
  const dm = G.__log.props.get("astro:void_drone|astro:mode") ?? new Set();
  if (!dm.has(1) || !dm.has(2)) fail(`[${label}] drone never charged/fired (${[...dm]})`);
  const sm = G.__log.props.get("astro:void_sentinel|astro:mode") ?? new Set();
  if (!sm.has(1) || !sm.has(2)) fail(`[${label}] sentinel never slammed (${[...sm]})`);
  if (!G.__log.events.get("astro:void_drone|astro:engage")) fail(`[${label}] drone never engaged`);
  const minions = ow.entities.filter((e) => e.tags.has("astro_minion")).length;
  if (minions > 6) fail(`[${label}] too many minions ${minions}`);
  const st = INV.invaderStats();
  console.log(`  ${label}: dmg drone ${dmgFrom("astro:void_drone").toFixed(0)} sentinel ${dmgFrom("astro:void_sentinel").toFixed(0)}` +
              ` nemesis ${dmgFrom("astro:nemesis").toFixed(0)} none ${dmgFrom("none").toFixed(0)} | boss modes ${[...modes].sort()} | ${JSON.stringify(st)}`);
  // ボスを倒す → 撃破演出 → 子機の撤退
  boss.hp = 1;
  boss.applyDamage(5, { cause: "entityAttack", damagingEntity: p });
  run(90, every);
  if (!G.__log.titles.some((t) => t.includes("撃破"))) fail(`[${label}] no defeat title`);
  const left = ow.entities.filter((e) => e.tags.has("astro_minion") && e.alive).length;
  if (left) fail(`[${label}] ${left} minions did not withdraw`);
  if (invWarns().length) fail(`[${label}] warnings after death: ${invWarns().join(" / ").slice(0, 600)}`);
  // ドローンの撃破
  for (const e of ow.entities.filter((x) => x.typeId === "astro:void_drone")) { e.hp = 1; e.applyDamage(3, { cause: "entityAttack", damagingEntity: p }); }
  run(20, every);
}

// ---- 2) ヴォイド・シグナルの決まり --------------------------------------------------------
clear();
G.__noShoot = false;
{
  const p = new FakeEntity(ow, "minecraft:player", { x: 0, y: 64, z: 0 }, 40);
  p.inv[0] = { typeId: "astro:void_signal", amount: 2 };
  G.__time = 6000;
  if (INV.summonNemesis(p)) fail("summoned during the day");
  G.__time = 18000;
  G.__ceiling = true;
  if (INV.summonNemesis(p)) fail("summoned under a roof");
  G.__ceiling = false;
  const ne = new FakeEntity(G.__dims.nether, "minecraft:player", { x: 0, y: 64, z: 0 }, 40);
  ne.inv[0] = { typeId: "astro:void_signal", amount: 1 };
  if (INV.summonNemesis(ne)) fail("summoned in the nether");
  if (!INV.summonNemesis(p)) fail("did not summon at night");
  if (p.inv[0]?.amount !== 1) fail("void signal not consumed");
  if (INV.summonNemesis(p)) fail("summoned twice during the sequence");
  run(80);
  const bosses = ow.entities.filter((e) => e.typeId === "astro:nemesis");
  if (bosses.length !== 1) fail(`expected 1 nemesis after summon, got ${bosses.length}`);
  if (INV.summonNemesis(p)) fail("summoned a second nemesis");
  if (!INV.summonNemesis(p, { force: true })) fail("force summon refused");
  run(80);
  p.mode = "creative";
  run(40);
}

// ---- 3) ホログラム標的 -------------------------------------------------------------------
clear();
{
  const p = new FakeEntity(ow, "minecraft:player", { x: 0, y: 64, z: 0 }, 40);
  const tg = INV.summonHologram(p);
  if (!tg) fail("hologram not spawned");
  else {
    tg.applyDamage(12, { cause: "entityAttack", damagingEntity: p });
    if (!tg.nameTag.includes("DPS") || !tg.nameTag.includes("12.0")) fail(`hologram nameTag: ${tg.nameTag}`);
    if (tg.hp !== tg.maxHp) fail("hologram not healed");
    run(140);
    if (!tg.nameTag.includes("0.0")) fail(`hologram text did not reset: ${tg.nameTag}`);
    tg.hp = 0;
    INV.onInvaderDie(tg, { cause: "entityAttack" });
    tg.remove();
    run(20);
    if (!ow.entities.some((e) => e.typeId === "astro:hologram_target")) fail("hologram did not come back");
  }
}
if (invWarns().length) fail(`warnings: ${invWarns().join(" / ").slice(0, 600)}`);
console.log("__USED__" + JSON.stringify({ particles: [...G.__log.particles.keys()], sounds: [...G.__log.sounds.keys()] }));
console.log(fails ? `  ${fails} failure(s)` : "  invaders.js: all checks passed");
process.exit(fails ? 1 : 0);
"""


def js_smoke_test():
    scripts = os.path.join(BP, "scripts")
    if not os.path.exists(os.path.join(scripts, "invaders.js")):
        print("  test: invaders.js missing")
        return False
    r = subprocess.run(["node", "--check", os.path.join(scripts, "invaders.js")], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr)
        return False
    entity_ids = []
    for fn in os.listdir(os.path.join(BP, "entities")):
        if fn.endswith(".json"):
            entity_ids.append(json.load(open(os.path.join(BP, "entities", fn), encoding="utf-8"))
                              ["minecraft:entity"]["description"]["identifier"])
    tmp = tempfile.mkdtemp(prefix="astro-inv-")
    try:
        with open(os.path.join(tmp, "package.json"), "w") as fh:
            json.dump({"name": "astro-inv-test", "type": "module"}, fh)
        for mod, src in (("@minecraft/server", JS_SERVER), ("@minecraft/server-ui", JS_UI)):
            d = os.path.join(tmp, "node_modules", *mod.split("/"))
            os.makedirs(d, exist_ok=True)
            pre = f"globalThis.__entityIds = new Set({json.dumps(entity_ids)});\n" if mod.endswith("server") else ""
            with open(os.path.join(d, "index.js"), "w", encoding="utf-8") as fh:
                fh.write(pre + src)
            with open(os.path.join(d, "package.json"), "w") as fh:
                json.dump({"name": mod, "type": "module", "main": "index.js"}, fh)
        shutil.copytree(scripts, os.path.join(tmp, "s"))
        with open(os.path.join(tmp, "s", "__test_invaders.js"), "w", encoding="utf-8") as fh:
            fh.write(JS_TEST)
        r = subprocess.run(["node", os.path.join(tmp, "s", "__test_invaders.js")], capture_output=True, text=True,
                           timeout=300, cwd=tmp)
        used = None
        for line in r.stdout.splitlines():
            if line.startswith("__USED__"):
                used = json.loads(line[8:])
            else:
                print(line)
        if r.returncode:
            print(r.stderr[-3000:])
            return False
        errs = []
        pdir = os.path.join(RP, "particles")
        particles = set()
        if os.path.isdir(pdir):
            for fn in os.listdir(pdir):
                if fn.endswith(".json"):
                    particles.add(json.load(open(os.path.join(pdir, fn), encoding="utf-8"))
                                  ["particle_effect"]["description"]["identifier"])
        sd = os.path.join(RP, "sounds", "sound_definitions.json")
        sounds = set(json.load(open(sd, encoding="utf-8"))["sound_definitions"]) if os.path.exists(sd) else set()
        for pid in used["particles"]:
            if particles and pid not in particles:
                errs.append(f"particle {pid} does not exist")
        for sid in used["sounds"]:
            if sounds and sid.startswith("astro.") and sid not in sounds:
                errs.append(f"sound {sid} does not exist")
        print(f"  used {len(used['particles'])} particles, {len(used['sounds'])} sounds"
              + ("" if particles else " (particles not generated yet: not checked)"))
        for e in errs:
            print("  FAIL", e)
        return not errs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
