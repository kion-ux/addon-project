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
from astro_common import (BP, RP, SCRATCH, beam, bevel, box, cbox, chamfer, line3, mat_cube,  # noqa: E402,F401
                          octa, polyline, rbox, ring, write_json)
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
        "holo": {"kind": "holo", "glow": CYAN, "light": CYAN_L, "bevel": False, "outline": False},
        "holo_dim": {"kind": "holo", "glow": CYAN, "light": CYAN_L, "bevel": False, "outline": False,
                     "k": 0.55},
        "holo_red": {"kind": "holo", "glow": (255, 80, 90), "light": (255, 210, 210), "bevel": False,
                     "outline": False},
        "holo_fill": {"kind": "holo_fill", "glow": CYAN, "bevel": False, "outline": False, "k": 0.16},
    })
    return st


# ===========================================================================
#  形の補助
# ===========================================================================
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
#  プレビュー（hd_scene の規則でボーンを組み、X を鏡映して描く。holo_* は加算合成）
# ===========================================================================
def render(geo, tex_img, yaw=0.0, pitch=-12.0, size=360, pose=None, additive=("holo",),
           bg=(22, 20, 30), fit=None):
    from hd_scene import weapon_quads
    from hd_space import Rx, Ry
    tex = np.asarray(tex_img.convert("RGBA"), np.float32)
    th, tw = tex.shape[:2]
    quads = weapon_quads(geo, tex_img, None, pose or {}, tag=True)
    view = Rx(pitch) @ Ry(yaw)
    pts = np.array([p for q in quads for p in q[0]]) @ view.T
    pts[:, 0] *= -1
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
        for q in P:
            q[0] *= -1
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
