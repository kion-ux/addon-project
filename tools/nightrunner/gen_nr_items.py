# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 武器以外のアイテム（素材・戦利品・回復・注射薬・弾・紙幣・道具）。

nr_spec_catalog の `MATERIAL_ITEMS` + `ITEMS`（`all_items()`）の全部について書く:

| 書くもの | 場所 |
|---|---|
| BP アイテム（format 1.21.120、content.md §3） | `packs/nightrunner_BP/items/misc/<key>.json`（このフォルダは全部この生成器のもの） |
| 作業台のレシピ（spec に `recipe` があるものだけ。tags + unlock 付き） | `packs/nightrunner_BP/recipes/misc/<key>.json`（同上） |
| アイコン 32×32（numpy で 4 倍に描いて縮める） | `packs/nightrunner_RP/textures/nr/items/<key>.png` |
| item_texture の断片 `nr_<key>` | `.frag/item_texture/gen_nr_items.json` |
| 言語の断片 `item.nr:<key>`（と `.name`） | `.frag/lang/gen_nr_items.json` |
| 確認用のコンタクトシート | `build_preview/nightrunner/item_icons.png`（スロットの灰色・暗い背景・等倍） |

BP アイテムの決め方（スクリプトとの約束。scripts/data/items.js の `engine_consumes` / `use_seconds` に同じ値が出る）:

* **使って減る回復・注射薬・食べ物**（`use.type` が heal / immunity / stamina / food / buff / inhibitor）は
  vanilla のりんごと同じ `minecraft:food`（`can_always_eat: true`）+ `minecraft:use_modifiers`（`use_ticks` / 20 秒）
  + `minecraft:use_animation` にする。**使い終わるとエンジンが 1 個減らす**ので、スクリプトは
  `world.afterEvents.itemCompleteUse` で効果を与えるだけ（自分で減らさない）。タグ `nr:engine_consumed`。
* 道具（grapple / glide / uv_light / zoom / terminal / lockpick / repair）は `minecraft:food` を付けない。
  使った瞬間に `itemUse` が来るだけで、減らすならスクリプト（ロックピックが折れる・修理キットを使い切る）。
  グラップリングフックは spec の `cooldown_ticks` で `minecraft:cooldown`（category `nr:grapple`）。
* 弾のうち、spec の飛び道具（`PROJECTILES[*].pickup`）が拾い直せるもの（矢・ボルト）は
  `minecraft:projectile`（`nr:proj_arrow` / `nr:proj_bolt`）を持つ（`minecraft:shooter` の弾にできる）。
* タグ: `nr:item`、`nr:<kind>`、`nr:use_<type>`、`nr:engine_consumed`、食べ物は `minecraft:is_food`。
  レア度は `minecraft:rarity`（legendary は epic + `minecraft:glint`）。カスタムコンポーネントは付けない
  （付けるとスクリプトが登録していない名前で読み込みエラーになる）。
* 表示名は `item.nr:<key>`（content.md §3.2）。メニューは素材・戦利品・紙幣が items、使う物は equipment。

アイコンの画家（このファイルの `Icon`）: 1 枚を 128×128 で描いて 32×32 に縮める。形は符号付き距離（SDF、
単位はアイコンの px、内側が負）で作り、面の向き（縁の丸み・円柱・ドーム）から左上の光で陰影と照りを付け、
nr_paint の fbm / セルノイズで錆・布・紙・骨・肉の質感を足す。縮めた後に 1px の暗い縁取り（隣の色を暗くした色）と、
光る部分（UV・抑制血清・変異）のにじみを付ける。乱数は key の crc32 から（決定的）。

使い方: `python3 tools/nightrunner/gen_nr_items.py [--only key,key] [--sheet-only]`
（普通は build_nr.py から。NR_PREVIEW=1 でなくてもコンタクトシートは描く。安い）。
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import (BP, HERE, RP, SCRATCH, frag, stable_hash, write_json)  # noqa: E402
from nr_paint import fbm2, worley2  # noqa: E402

PRODUCER = "gen_nr_items"
ICON = 32                 # 仕上がりの大きさ（HyperDim と同じ 32×32。アトラスの上限 256 の内）
SS = 4                    # 描く倍率（128×128 で描いて縮める）
ITEM_FORMAT = "1.21.120"
RECIPE_FORMAT = "1.20.10"
ITEM_DIR = os.path.join(BP, "items", "misc")
RECIPE_DIR = os.path.join(BP, "recipes", "misc")
TEX_DIR = os.path.join(RP, "textures", "nr", "items")
TEX_REF = "textures/nr/items/"
SHEET = os.path.join(SCRATCH, "item_icons.png")

f32 = np.float32


# ===========================================================================
#  spec
# ===========================================================================
def load_spec():
    """nr_spec.py があればそれ、無ければ二つの spec を一つの名前空間に（gen_nr_data_js と同じ）。"""
    if os.path.exists(os.path.join(HERE, "nr_spec.py")):
        import nr_spec
        return nr_spec
    import types
    import nr_spec_catalog
    import nr_spec_zombies
    ns = types.SimpleNamespace()
    for mod in (nr_spec_catalog, nr_spec_zombies):
        for name in getattr(mod, "__all__", [n for n in dir(mod) if not n.startswith("_")]):
            setattr(ns, name, getattr(mod, name))
    return ns


# ===========================================================================
#  BP アイテムの規則（scripts/data/items.js も同じ関数を使う）
# ===========================================================================
ENGINE_USES = ("heal", "immunity", "stamina", "food", "buff", "inhibitor")   # minecraft:food で減る
# 使う時のバニラの腕の動き（プレイヤーの全身のモーションはスクリプトが use.anim を playAnimation する）
USE_ANIMATION = {"canned_food": "eat", "chocolate_bar": "eat", "uv_shroom": "eat", "painkillers": "eat",
                 "energy_drink": "drink"}
FOODS = ("canned_food", "chocolate_bar", "uv_shroom")      # minecraft:is_food を付ける
RARITY_MAP = {"common": None, "uncommon": "uncommon", "rare": "rare", "epic": "epic", "legendary": "epic"}


def _use(it) -> dict:
    return it.get("use") or {}


def engine_consumes(it) -> bool:
    """True = BP の minecraft:food で、使い終わるとエンジンが 1 個減らす。"""
    return _use(it).get("type") in ENGINE_USES


def use_seconds(it) -> float:
    """使い終わるまでの秒（minecraft:use_modifiers.use_duration）。道具は 0（即時の itemUse）。"""
    if not engine_consumes(it):
        return 0.0
    return round(float(_use(it).get("use_ticks", 32)) / 20.0, 3)


def projectile_for(it, S):
    """拾い直せる飛び道具（PROJECTILES[*].pickup）がこのアイテムなら、その飛び道具の ID。"""
    hits = [p["id"] for p in S.PROJECTILES if p.get("pickup") == it["id"]]
    return hits[0] if hits else None


def item_json(it, S) -> dict:
    key, use = it["key"], _use(it)
    kind = it["kind"]
    menu = {"category": "items" if kind in ("material", "trophy", "currency") else "equipment"}
    if key in FOODS or key == "energy_drink":
        menu["group"] = "minecraft:itemGroup.name.miscFood"
    elif projectile_for(it, S):
        menu["group"] = "minecraft:itemGroup.name.arrow"
    comps = {
        "minecraft:icon": f"nr_{key}",
        "minecraft:display_name": {"value": f"item.{it['id']}"},
        "minecraft:max_stack_size": int(it["stack"]),
    }
    tags = ["nr:item", f"nr:{kind}"]
    if use.get("type"):
        tags.append(f"nr:use_{use['type']}")
    if engine_consumes(it):
        comps["minecraft:use_modifiers"] = {"use_duration": use_seconds(it), "movement_modifier": 0.35}
        comps["minecraft:use_animation"] = USE_ANIMATION.get(key, "none")
        food = {"can_always_eat": True, "nutrition": int(use.get("food", 0)),
                "saturation_modifier": float(use.get("saturation", 0.0))}
        comps["minecraft:food"] = food
        tags.append("nr:engine_consumed")
    if key in FOODS:
        tags.append("minecraft:is_food")
    if use.get("cooldown_ticks"):
        comps["minecraft:cooldown"] = {"category": f"nr:{use['type']}",
                                       "duration": round(use["cooldown_ticks"] / 20.0, 3)}
    if use.get("type") in ("grapple", "uv_light"):
        comps["minecraft:hand_equipped"] = True
    proj = projectile_for(it, S)
    if proj:
        comps["minecraft:projectile"] = {"projectile_entity": proj}
    rar = RARITY_MAP.get(it.get("rarity", "common"))
    if rar:
        comps["minecraft:rarity"] = rar
    if it.get("rarity") == "legendary":
        comps["minecraft:glint"] = True
    comps["minecraft:tags"] = {"tags": tags}
    return {"format_version": ITEM_FORMAT,
            "minecraft:item": {"description": {"identifier": it["id"], "menu_category": menu},
                               "components": comps}}


def recipe_json(it) -> dict | None:
    r = it.get("recipe")
    if not r:
        return None
    if r["type"] == "shaped":
        refs = [r["keys"][ch] for row in r["pattern"] for ch in row if ch != " "]
    else:
        refs = [i for i, _ in r["ingredients"]]
    unlock_ref = next((x for x in refs if x.startswith("nr:")), refs[0])
    body = {"description": {"identifier": f"nr:craft_{it['key']}"}, "tags": ["crafting_table"]}
    if r["type"] == "shaped":
        body["pattern"] = list(r["pattern"])
        body["key"] = {ch: {"item": ref} for ch, ref in r["keys"].items()}
    else:
        body["ingredients"] = [({"item": i, "count": n} if n > 1 else {"item": i}) for i, n in r["ingredients"]]
    body["unlock"] = [{"item": unlock_ref}]
    body["result"] = {"item": it["id"], "count": int(r.get("count", 1))}
    kind = "minecraft:recipe_shaped" if r["type"] == "shaped" else "minecraft:recipe_shapeless"
    return {"format_version": RECIPE_FORMAT, kind: body}


# ===========================================================================
#  アイコンの画家
# ===========================================================================
def C(c) -> np.ndarray:
    """'#rrggbb' / (r, g, b) 0..255 → 0..1 の float32[3]。"""
    if isinstance(c, np.ndarray):
        return c.astype(f32)
    if isinstance(c, str):
        c = c.lstrip("#")
        c = tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return np.array(c, dtype=f32) / f32(255.0)


def mix(a, b, t):
    a = C(a) if not isinstance(a, np.ndarray) else a
    b = C(b) if not isinstance(b, np.ndarray) else b
    t = np.asarray(t, dtype=f32)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


_L = np.array([-0.5, -0.72, 0.95], dtype=f32)
LIGHT = _L / np.linalg.norm(_L)
_H = LIGHT + np.array([0, 0, 1], dtype=f32)
HALF = _H / np.linalg.norm(_H)
AMBIENT = 0.38


class Axis:
    """線分 (x0, y0)→(x1, y1) に沿った座標。t は始点からの距離（px）、off は進む向きの右手側（画面）へのずれ。"""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = float(x0), float(y0)
        dx, dy = x1 - x0, y1 - y0
        self.len = math.hypot(dx, dy)
        self.ux, self.uy = dx / self.len, dy / self.len
        self.nx, self.ny = -self.uy, self.ux          # 画面で進む向きの右（y が下なので時計回り 90 度）
        self.deg = math.degrees(math.atan2(dy, dx))

    def p(self, t, off=0.0):
        return (self.x0 + self.ux * t + self.nx * off, self.y0 + self.uy * t + self.ny * off)


class Icon:
    def __init__(self, key: str):
        self.key = key
        self.seed = stable_hash(key) % 99991
        n = ICON * SS
        self.n = n
        yy, xx = np.mgrid[0:n, 0:n].astype(f32)
        self.X = (xx + 0.5) / SS
        self.Y = (yy + 0.5) / SS
        self.col = np.zeros((n, n, 3), f32)      # 乗算済みの色
        self.a = np.zeros((n, n), f32)
        self.gl = np.zeros((n, n), f32)          # 発光の強さ
        self.glc = np.zeros((n, n, 3), f32)      # 発光の色（強さを掛けた和）
        self._k = 0

    # ---- 乱数・模様 -----------------------------------------------------
    def sd(self, k=0):
        self._k += 1
        return (self.seed * 31 + k * 977 + self._k * 7919) % 2147483
    def noise(self, scale=4.0, octaves=4, rot=0.0, stretch=1.0, k=0, x=None, y=None):
        """fbm（0..1、平均 0.5）。scale = 基本の模様の大きさ（px）、stretch > 1 で rot の向きに伸ばす。"""
        X = self.X if x is None else x
        Y = self.Y if y is None else y
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        u = (X * c + Y * s) / (scale * stretch)
        v = (-X * s + Y * c) / scale
        return fbm2(u, v, self.sd(k), octaves=octaves)

    def cells(self, scale=3.0, k=0):
        F1, F2, cid, _vx, _vy = worley2(self.X / scale, self.Y / scale, self.sd(k))
        return F1, F2, cid

    def grain(self, amt=0.06, scale=0.7, k=0):
        return 1.0 + (self.noise(scale, 2, k=k) - 0.5) * 2 * amt

    # ---- 形（SDF） --------------------------------------------------------
    def local(self, cx, cy, rot=0.0):
        r = math.radians(rot)
        c, s = math.cos(r), math.sin(r)
        dx, dy = self.X - cx, self.Y - cy
        return dx * c + dy * s, -dx * s + dy * c

    def circle(self, cx, cy, r):
        return np.hypot(self.X - cx, self.Y - cy) - r

    def ellipse(self, cx, cy, rx, ry, rot=0.0):
        x, y = self.local(cx, cy, rot)
        k = np.hypot(x / rx, y / ry)
        g = np.hypot(x / (rx * rx), y / (ry * ry))
        return np.where(k < 1e-4, -min(rx, ry), (k - 1) * k / np.maximum(g, 1e-6))

    def box(self, cx, cy, w, h, r=0.0, rot=0.0):
        x, y = self.local(cx, cy, rot)
        r = min(r, w / 2, h / 2)
        qx = np.abs(x) - w / 2 + r
        qy = np.abs(y) - h / 2 + r
        return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r

    def abox(self, ax: Axis, t0, t1, w, r=0.0, off=0.0):
        """軸に沿った箱（t0〜t1、幅 w）。"""
        cx, cy = ax.p((t0 + t1) / 2, off)
        return self.box(cx, cy, t1 - t0, w, r, ax.deg)

    def seg(self, x0, y0, x1, y1, r0, r1=None):
        r1 = r0 if r1 is None else r1
        bx, by = x1 - x0, y1 - y0
        px, py = self.X - x0, self.Y - y0
        bb = bx * bx + by * by
        h = np.clip((px * bx + py * by) / max(bb, 1e-9), 0, 1)
        return np.hypot(px - bx * h, py - by * h) - (r0 + (r1 - r0) * h)

    def path(self, pts, r0, r1=None):
        """折れ線の太線（r0→r1 へ全長で細る）。"""
        r1 = r0 if r1 is None else r1
        lens = [math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)]
        tot = max(sum(lens), 1e-6)
        d = None
        acc = 0.0
        for i in range(len(pts) - 1):
            ra = r0 + (r1 - r0) * acc / tot
            acc += lens[i]
            rb = r0 + (r1 - r0) * acc / tot
            s = self.seg(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], ra, rb)
            d = s if d is None else np.minimum(d, s)
        return d

    def poly(self, pts):
        """多角形（凹でもよい）の正確な SDF。"""
        P = np.asarray(pts, dtype=f32)
        X, Y = self.X, self.Y
        d = (X - P[0, 0]) ** 2 + (Y - P[0, 1]) ** 2
        s = np.ones_like(X)
        n = len(P)
        j = n - 1
        for i in range(n):
            ex, ey = P[j, 0] - P[i, 0], P[j, 1] - P[i, 1]
            wx, wy = X - P[i, 0], Y - P[i, 1]
            h = np.clip((wx * ex + wy * ey) / max(ex * ex + ey * ey, 1e-9), 0, 1)
            bx, by = wx - ex * h, wy - ey * h
            d = np.minimum(d, bx * bx + by * by)
            c1 = Y >= P[i, 1]
            c2 = Y < P[j, 1]
            c3 = ex * wy > ey * wx
            flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
            s = np.where(flip, -s, s)
            j = i
        return s * np.sqrt(d)

    @staticmethod
    def smin(a, b, k=1.0):
        h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
        return b * (1 - h) + a * h - k * h * (1 - h)

    @staticmethod
    def union(*ds):
        out = ds[0]
        for d in ds[1:]:
            out = np.minimum(out, d)
        return out

    @staticmethod
    def cut(a, b):
        return np.maximum(a, -b)

    @staticmethod
    def inter(a, b):
        return np.maximum(a, b)

    def rough(self, d, amt=0.6, scale=1.6, k=0):
        """縁をがたがたにする（ちぎれ・焦げ・ほつれ）。"""
        return d + (self.noise(scale, 3, k=k) - 0.5) * 2 * amt

    # ---- 塗り --------------------------------------------------------------
    def _normal(self, d, light, bevel, axis, profile):
        n = self.n
        if light == "flat":
            return None
        if light == "cyl":
            ax = axis
            px, py = self.X - ax.x0, self.Y - ax.y0
            perp = px * ax.nx + py * ax.ny
            inside = np.maximum(-d, 1e-3)
            u = np.clip(perp / (np.abs(perp) + inside), -0.995, 0.995)
            if bevel:
                # 端（帽子）の丸みも少し
                pass
            nz = np.sqrt(1 - u * u)
            return np.stack([u * ax.nx, u * ax.ny, nz], -1).astype(f32)
        t = np.clip(-d / max(bevel, 1e-3), 0, 1)
        if profile == "round":
            h = bevel * np.sqrt(np.clip(1 - (1 - t) ** 2, 0, 1))
        elif profile == "soft":
            h = bevel * smooth(0, 1, t)
        else:
            h = bevel * t
        gy, gx = np.gradient(h, 1.0 / SS)
        N = np.stack([-gx, -gy, np.ones((n, n), f32)], -1)
        N /= np.linalg.norm(N, axis=-1, keepdims=True)
        return N.astype(f32)

    def fill(self, d, color, *, light="bevel", bevel=1.2, axis=None, profile="round", tex=None,
             spec=0.25, shine=18, spec_col=None, alpha=1.0, glow=0.0, glow_col=None, emit=0.0,
             contrast=1.0):
        """d の内側を塗る。color は色か (H, W, 3) の配列。light: flat / bevel / cyl（axis が要る）。
        tex は明るさの倍率（配列）。glow はにじみ（縮めた後）、emit は陰影を無視して明るく光らせる割合。"""
        cov = np.clip(0.5 - d * SS, 0, 1) * np.asarray(alpha, dtype=f32)
        if not np.any(cov > 0):
            return cov
        base = C(color) if not isinstance(color, np.ndarray) or color.ndim == 1 else color.astype(f32)
        if base.ndim == 1:
            base = np.broadcast_to(base, (self.n, self.n, 3))
        col = base.copy() if base.flags.writeable is False else base * 1.0
        if tex is not None:
            col = col * np.asarray(tex, dtype=f32)[..., None]
        N = self._normal(d, light, bevel, axis, profile)
        if N is not None:
            ndl = N @ LIGHT
            sh = AMBIENT + (1 - AMBIENT) * np.maximum(ndl, 0) / LIGHT[2]
            if contrast != 1.0:
                sh = 1.0 + (sh - 1.0) * contrast
            col = col * sh[..., None]
            if spec > 0:
                ndh = np.maximum(N @ HALF, 0)
                base_s = float(HALF[2]) ** shine
                s = np.maximum(ndh ** shine - base_s, 0) / (1 - base_s)
                sc = np.ones(3, f32) if spec_col is None else C(spec_col)
                col = col + (s * spec)[..., None] * sc
        if emit > 0:
            col = col * (1 - emit) + base * emit * 1.15
        col = np.clip(col, 0, 1)
        c3 = cov[..., None]
        self.col = col * c3 + self.col * (1 - c3)
        self.a = cov + self.a * (1 - cov)
        if glow > 0:
            g = cov * f32(glow)
            gc = C(glow_col) if glow_col is not None else (base if base.ndim == 1 else None)
            if gc is None:
                self.glc += base * g[..., None]
            else:
                self.glc += gc * g[..., None]
            self.gl += g
        return cov

    def stroke(self, d, width, color, **kw):
        kw.setdefault("light", "flat")
        return self.fill(np.abs(d) - width / 2, color, **kw)

    def line(self, pts, width, color, r1=None, **kw):
        kw.setdefault("light", "flat")
        return self.fill(self.path(pts, width / 2, None if r1 is None else r1), color, **kw)

    def tint(self, mask, color, amt=1.0, mode="mul"):
        """今の絵の上に色を乗せる（mask 0..1。透明な所は変えない）。mode: mul / mix / add。"""
        m = np.clip(np.asarray(mask, f32) * amt, 0, 1)[..., None] * (self.a[..., None] > 0)
        c = C(color)
        a3 = self.a[..., None]
        if mode == "mul":
            self.col = self.col * (1 - m) + self.col * c * m
        elif mode == "mix":
            self.col = self.col * (1 - m) + c * a3 * m
        else:
            self.col = np.clip(self.col + c * a3 * m, 0, 1)

    def shade(self, mask, k):
        """今の絵を暗く（k > 0）／明るく（k < 0）。"""
        m = np.clip(np.asarray(mask, f32), 0, 1)
        self.col = np.clip(self.col * (1 - k * m)[..., None], 0, 1)

    def shadow(self, d, dx=0.55, dy=0.75, k=0.45, soft=0.8):
        """これから描く形 d の影を、今の絵の上に落とす（右下へずらしてぼかす）。"""
        cov = np.clip(0.5 - d * SS, 0, 1)
        sx, sy = int(round(dx * SS)), int(round(dy * SS))
        sh = np.zeros_like(cov)
        n = self.n
        sh[max(sy, 0):n + min(sy, 0), max(sx, 0):n + min(sx, 0)] = \
            cov[max(-sy, 0):n - max(sy, 0), max(-sx, 0):n - max(sx, 0)]
        sh = _blur(sh, max(1, int(soft * SS)))
        self.col = self.col * (1 - k * sh)[..., None]

    def lin(self, x0, y0, x1, y1, c0, c1):
        """直線のグラデーション（色の配列）。"""
        dx, dy = x1 - x0, y1 - y0
        t = np.clip(((self.X - x0) * dx + (self.Y - y0) * dy) / (dx * dx + dy * dy), 0, 1)
        return mix(c0, c1, t)

    # ---- 仕上げ（32px） --------------------------------------------------------
    def finish(self, outline=0.32, sharpen=0.35) -> Image.Image:
        n, s = ICON, SS
        a = self.a.reshape(n, s, n, s).mean((1, 3))
        col = self.col.reshape(n, s, n, s, 3).mean((1, 3))
        rgb = col / np.maximum(a, 1e-6)[..., None]
        solid = a >= 0.5
        # 少しだけ鮮明に（縮小のぼけを戻す）
        if sharpen > 0:
            bl = _blur3(rgb, solid)
            rgb = np.where(solid[..., None], np.clip(rgb + sharpen * (rgb - bl), 0, 1), rgb)
        out = np.zeros((n, n, 4), f32)
        out[..., :3] = rgb
        out[..., 3] = solid
        # 縁取り: 透明で、上下左右に塗った所がある画素 = 隣の色を暗くした色
        if outline is not None:
            nb = np.zeros((n, n, 3), f32)
            cnt = np.zeros((n, n), f32)
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                m = np.roll(solid, (dy, dx), (0, 1))
                c = np.roll(rgb, (dy, dx), (0, 1))
                if dy == 1:
                    m[0, :] = False
                if dy == -1:
                    m[-1, :] = False
                if dx == 1:
                    m[:, 0] = False
                if dx == -1:
                    m[:, -1] = False
                nb += c * m[..., None]
                cnt += m
            ring = (~solid) & (cnt > 0)
            oc = nb / np.maximum(cnt, 1)[..., None] * outline
            out[ring, :3] = oc[ring]
            out[ring, 3] = 1.0
        else:
            ring = np.zeros((n, n), bool)
        # 発光のにじみ
        if self.gl.max() > 0:
            g = self.gl.reshape(n, s, n, s).mean((1, 3))
            gc = self.glc.reshape(n, s, n, s, 3).mean((1, 3)) / np.maximum(g, 1e-6)[..., None]
            gb = _blur(g, 1)
            gb = (_blur(gb, 1) + gb) * 0.5
            gcb = np.stack([_blur(gc[..., i] * g, 2) for i in range(3)], -1) / np.maximum(_blur(g, 2), 1e-6)[..., None]
            gcb = np.clip(gcb, 0, 1)
            # 縁取りの画素は光の色へ寄せる
            w = np.clip(gb * 2.2, 0, 1) * ring
            out[..., :3] = out[..., :3] * (1 - w[..., None]) + np.clip(gcb * 0.85, 0, 1) * w[..., None]
            # 何も無い所に薄い光
            empty = (~solid) & (~ring)
            ga = np.clip(gb * 1.6, 0, 0.62) * empty
            ga = np.where(ga < 0.12, 0, ga)
            out[..., :3] = np.where((ga > 0)[..., None], gcb, out[..., :3])
            out[..., 3] = np.where(ga > 0, ga, out[..., 3])
        img = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
        img[img[..., 3] == 0, :3] = 0
        return Image.fromarray(img, "RGBA")


def _blur(a, r):
    """箱ぼかし（半径 r、2 回で三角に近く）。"""
    if r <= 0:
        return a
    out = a.astype(f32)
    for _ in range(2):
        for ax in (0, 1):
            p = np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(out.ndim)], mode="edge")
            c = np.cumsum(p, axis=ax, dtype=np.float64)
            sl_hi = [slice(None)] * out.ndim
            sl_lo = [slice(None)] * out.ndim
            sl_hi[ax] = slice(2 * r + 1, None)
            sl_lo[ax] = slice(0, -2 * r - 1)
            out = ((c[tuple(sl_hi)] - c[tuple(sl_lo)]) / (2 * r + 1)).astype(f32)
    return out


def _blur3(rgb, mask):
    """3×3 の平均（mask の外は使わない）。"""
    n = rgb.shape[0]
    acc = np.zeros_like(rgb)
    cnt = np.zeros((n, n), f32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            m = np.roll(mask, (dy, dx), (0, 1))
            acc += np.roll(rgb, (dy, dx), (0, 1)) * m[..., None]
            cnt += m
    return acc / np.maximum(cnt, 1)[..., None]


# ===========================================================================
#  よく使う質感
# ===========================================================================
STEEL = "#9ea4a9"
STEEL_DK = "#5b6166"
STEEL_HI = "#dfe4e8"
BRASS = "#c9a33f"
COPPER = "#b9693a"
RUST = "#8a4a22"
RUST_DK = "#5a2c14"
BONE = "#dcd2b2"
BLOOD = "#6e0d0d"
BLACK_PL = "#26282c"
TAPE = "#9fa3a8"


def metal_tex(ic, rot=0.0, amt=0.12, k=0):
    """擦った金属（向きのある細かい筋）。"""
    return 1.0 + (ic.noise(1.6, 3, rot=rot, stretch=5.0, k=k) - 0.5) * 2 * amt + \
        (ic.noise(5.0, 3, k=k + 1) - 0.5) * amt


def rust_mask(ic, d, edge=2.0, amt=0.55, k=0):
    """縁から入る錆の斑（0..1）。"""
    n = ic.noise(2.6, 4, k=k)
    e = smooth(edge, 0.0, -d)
    return np.clip(smooth(0.55, 0.75, n + e * amt) , 0, 1)


def cloth_tex(ic, rot=0.0, amt=0.18, k=0):
    """布の織り目とたるみの皺。"""
    folds = ic.noise(4.0, 3, rot=rot, stretch=3.0, k=k)
    weave = ic.noise(0.6, 2, k=k + 1)
    return 1.0 + (folds - 0.5) * 2 * amt + (weave - 0.5) * 0.12


def glass_streak(ic, ax: Axis, t0, t1, off, w=0.55, a=0.6, col="#ffffff"):
    x0, y0 = ax.p(t0, off)
    x1, y1 = ax.p(t1, off)
    ic.fill(ic.seg(x0, y0, x1, y1, w), col, light="flat", alpha=a)


# ===========================================================================
#  アイコン（spec の icon の説明をなぞる）
# ===========================================================================
PAINTERS = {}


def painter(key):
    def deco(fn):
        PAINTERS[key] = fn
        return fn
    return deco


# --- 素材 -------------------------------------------------------------------
@painter("scrap")
def p_scrap(ic):
    # 奥の曲がった鋼板（2 枚の面で折れ目を作る）
    back = ic.rough(ic.poly([(2.6, 16.5), (15.5, 5.0), (26.5, 9.5), (29.0, 17.5), (17.0, 26.0), (8.0, 23.0)]),
                    0.35, 1.4)
    upper = ic.poly([(0, 0), (32, 0), (32, 7.0), (5.0, 26.0), (0, 26)])
    col = mix(STEEL, "#7d8388", np.clip(ic.inter(back, -upper) < 0, 0, 1) * 0.0 + (upper > 0) * 0.6)
    rm = rust_mask(ic, back, 2.6, 0.6, k=1)
    col = mix(col, mix(RUST, "#b56a2c", ic.noise(1.2, 2, k=2)), rm)
    ic.fill(back, col, bevel=0.9, tex=metal_tex(ic, 25, 0.1, k=3), spec=0.35, shine=22)
    # 折れ目の線
    ic.stroke(ic.seg(5.0, 26.0, 27.5, 8.0, 0), 0.5, "#3c4045", alpha=0.55)
    ic.fill(ic.inter(ic.seg(5.6, 25.0, 27.0, 8.6, 0.45), back), "#e6ecef", light="flat", alpha=0.45)
    # 手前の青く塗った板（剥げて地金と錆が出る）
    front = ic.rough(ic.poly([(4.0, 24.0), (14.5, 15.5), (26.5, 20.0), (19.5, 30.0), (8.5, 29.5)]), 0.3, 1.2, k=4)
    ic.shadow(front, 0.5, 0.8, 0.5)
    chip = smooth(0.56, 0.62, ic.noise(2.2, 4, k=5) + smooth(1.6, 0, -front) * 0.35)
    col = mix("#2e63a8", STEEL, chip)
    col = mix(col, RUST, chip * smooth(0.5, 0.65, ic.noise(1.5, 3, k=6)))
    ic.fill(front, col, bevel=0.9, tex=ic.grain(0.08, 1.0, k=7), spec=0.3)
    # 六角ボルト（ねじの軸 → 頭）
    ax = Axis(14.0, 18.5, 22.5, 9.5)
    shank = ic.abox(ax, 0.0, 9.0, 3.3, 0.8)
    ic.shadow(shank, 0.5, 0.8, 0.5)
    t = ((ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy)
    threads = 1.0 + 0.32 * np.sign(np.sin(t * 2 * math.pi / 1.05))
    ic.fill(shank, "#8d9398", light="cyl", axis=ax, tex=threads, spec=0.55, shine=26)
    hx, hy = ax.p(9.6)
    head = ic.poly([(hx + 4.4 * math.cos(math.radians(a + 10)), hy + 4.4 * math.sin(math.radians(a + 10)))
                    for a in range(0, 360, 60)])
    ic.shadow(head, 0.6, 0.8, 0.55)
    ic.fill(head, "#a3a9ae", bevel=1.4, profile="lin", tex=metal_tex(ic, 0, 0.1, k=8), spec=0.6, shine=20)
    ic.fill(ic.circle(hx, hy, 2.0), "#8a9095", bevel=0.8, spec=0.4)
    ic.tint(rust_mask(ic, head, 1.5, 0.5, k=9) * (head < 0), RUST, 0.6, "mix")


@painter("rags")
def p_rags(ic):
    blob = ic.smin(ic.smin(ic.ellipse(15.5, 19.5, 12.0, 8.0, -12), ic.ellipse(11.0, 13.0, 6.5, 5.5, -20), 2.0),
                   ic.ellipse(21.5, 13.5, 6.5, 5.5, 15), 2.0)
    blob = ic.rough(blob, 0.45, 1.3)
    stain = smooth(0.55, 0.68, ic.noise(4.0, 4, k=1)) * smooth(10, 2, np.hypot(ic.X - 20, ic.Y - 21))
    col = mix("#d8d0bb", "#bfb59d", ic.noise(3.0, 3, k=2))
    col = mix(col, "#7a5634", stain * 0.75)
    ic.fill(blob, col, bevel=3.2, profile="soft", tex=cloth_tex(ic, -20, 0.22, k=3), spec=0.05)
    # 灰色の布の帯と結び目
    band = ic.inter(ic.rough(ic.box(16.0, 17.0, 30, 6.0, 0, -42), 0.35, 1.0, k=4), blob - 0.6)
    ic.shadow(band, 0.4, 0.6, 0.35)
    ic.fill(band, "#7c8189", bevel=1.6, profile="soft", tex=cloth_tex(ic, 48, 0.25, k=5), spec=0.05)
    # 垂れた端（ほつれ）
    for pts, k in (([(15.0, 18.5), (12.0, 23.5), (9.0, 29.0)], 6), ([(17.5, 19.0), (21.0, 24.0), (24.5, 29.5)], 7)):
        tail = ic.rough(ic.path(pts, 2.0, 1.2), 0.4, 0.9, k=k)
        ic.shadow(tail, 0.4, 0.6, 0.35)
        ic.fill(tail, "#80858d", bevel=1.2, tex=cloth_tex(ic, 60, 0.2, k=k + 10), spec=0.05)
    for x0, y0, x1, y1 in ((8.8, 28.8, 7.6, 30.6), (9.6, 29.0, 9.8, 31.0), (24.2, 29.3, 23.2, 31.0),
                           (25.0, 29.2, 26.0, 30.8)):
        ic.line([(x0, y0), (x1, y1)], 0.55, "#6c7178")
    knot = ic.rough(ic.ellipse(16.2, 17.6, 3.6, 3.0, -30), 0.3, 0.9, k=8)
    ic.shadow(knot, 0.5, 0.7, 0.45)
    ic.fill(knot, "#868b93", bevel=2.6, tex=cloth_tex(ic, 10, 0.25, k=9), spec=0.08)
    ic.stroke(ic.ellipse(16.2, 17.6, 1.8, 1.2, -30), 0.5, "#4c5056", alpha=0.7)


@painter("alcohol")
def p_alcohol(ic):
    ax = Axis(16, 30, 16, 1)
    body = ic.smin(ic.box(16, 21.5, 11.6, 15.0, 2.4), ic.poly([(10.6, 16.5), (21.4, 16.5), (18.1, 10.5), (13.9, 10.5)]),
                   1.2)
    neck = ic.box(16, 8.0, 4.4, 6.5, 0.8)
    bottle = ic.smin(body, neck, 0.8)
    liquid = ic.inter(bottle, -(ic.Y - 15.2) * 1.0)       # 液面より下
    glass = mix("#4a2208", "#6a330c", smooth(0.4, 0.7, ic.noise(5, 3, k=1)))
    ic.fill(bottle, glass, light="cyl", axis=ax, spec=0.9, shine=40, spec_col="#ffd2a0")
    ic.fill(liquid, "#8a4510", light="cyl", axis=ax, alpha=0.55, spec=0.0)
    ic.stroke(ic.inter(ic.Y - 15.2, bottle + 0.5), 0.35, "#c07a2c", alpha=0.6)
    # 口の輪とコルク
    lip = ic.box(16, 5.2, 5.4, 1.8, 0.7)
    ic.fill(lip, "#5c2a0a", bevel=0.8, spec=0.8, shine=30)
    cork = ic.box(16, 3.0, 3.6, 3.4, 0.9)
    ic.shadow(cork, 0.3, 0.5, 0.3)
    ic.fill(cork, mix("#b8925a", "#8a6634", ic.noise(0.8, 3, k=2)), bevel=1.2, spec=0.05)
    # 手書きのラベル「消毒用」
    label = ic.inter(ic.box(16, 22.0, 12.0, 7.6, 0.4), body + 0.15)
    ic.fill(label, mix("#efe9da", "#d8cfb8", ic.noise(2.0, 3, k=3)), light="cyl", axis=ax, spec=0.1)
    for y, xs in ((20.4, ((11.6, 13.4), (14.2, 16.0), (16.9, 19.0))), (23.4, ((12.2, 15.4), (16.2, 19.6)))):
        for x0, x1 in xs:
            ic.line([(x0, y + 0.3), ((x0 + x1) / 2, y - 0.5), (x1, y + 0.2)], 0.7, "#2a2622")
    ic.fill(ic.box(12.2, 22.0, 0.8, 7.0), "#b0281c", light="flat", alpha=0.0)
    # ガラスの照り
    glass_streak(ic, ax, 4.0, 13.0, -3.6, 0.55, 0.65)
    glass_streak(ic, ax, 15.5, 20.5, -1.2, 0.35, 0.55)
    glass_streak(ic, ax, 3.5, 13.0, 4.6, 0.32, 0.35, "#ffb070")


@painter("chemicals")
def p_chemicals(ic):
    body = ic.box(16.5, 20.0, 19.5, 18.5, 2.8)
    handle = ic.cut(ic.box(20.5, 10.0, 10.0, 6.4, 2.6), ic.box(20.5, 10.6, 5.4, 2.2, 1.0))
    can = ic.union(body, ic.inter(handle, ic.Y - 12.5 + 0 * ic.X))
    dirt = smooth(0.5, 0.75, ic.noise(3.0, 4, k=1))
    col = mix("#e7e5da", "#b9b39a", dirt * 0.6 + smooth(4, 0, -can) * 0.0)
    ic.fill(can, col, bevel=2.2, profile="soft", tex=ic.grain(0.05, 1.2, k=2), spec=0.35, shine=16)
    # 側面の縦の溝
    for x in (9.4, 23.6):
        ic.stroke(ic.box(x, 21.0, 1.4, 12.5, 0.7), 0.45, "#9c9888", alpha=0.85)
    # 青いキャップと注ぎ口
    spout = ic.box(10.8, 10.4, 4.0, 3.2, 0.6, -12)
    ic.fill(spout, "#d9d6c8", bevel=0.8)
    cap = ic.box(10.4, 8.4, 5.6, 3.6, 0.9, -12)
    ic.shadow(cap, 0.3, 0.6, 0.35)
    ridges = 1.0 + 0.18 * np.sign(np.sin(ic.local(10.4, 8.4, -12)[0] * 2 * math.pi / 1.1))
    ic.fill(cap, "#2a62d4", bevel=1.0, tex=ridges, spec=0.5, shine=20)
    # 黄色い危険の菱形
    dia = ic.box(16.8, 21.0, 9.6, 9.6, 0.5, 45)
    ic.fill(dia, "#f2c21b", light="flat", tex=ic.grain(0.05, 1.0, k=3))
    ic.stroke(ic.box(16.8, 21.0, 8.0, 8.0, 0.3, 45), 0.7, "#1b1a17")
    ic.fill(ic.seg(16.8, 17.4, 16.8, 21.3, 0.8, 0.55), "#1b1a17", light="flat")
    ic.fill(ic.circle(16.8, 23.4, 0.85), "#1b1a17", light="flat")
    # 垂れた緑の液
    drip = ic.union(ic.path([(8.6, 10.6), (7.6, 13.0), (7.7, 17.0)], 0.75, 0.55), ic.circle(7.7, 18.2, 1.25))
    ic.fill(drip, "#6fd03a", bevel=0.9, spec=0.9, shine=30, glow=0.25, glow_col="#8cff4a")
    ic.tint(smooth(1.8, 0, np.hypot(ic.X - 9.0, ic.Y - 12.0)) * (body < 0), "#7fbf40", 0.25, "mix")


@painter("blades")
def p_blades(ic):
    # 包丁の先（奥）
    knife = ic.poly([(6.0, 26.5), (11.8, 27.5), (13.6, 5.0), (12.4, 3.0)])
    col = ic.lin(6, 27, 13, 3, "#6f777e", "#aab2b8")
    ic.fill(knife, col, bevel=0.7, profile="lin", tex=metal_tex(ic, -80, 0.12, k=1), spec=0.6, shine=24)
    ic.line([(11.9, 27.0), (13.4, 5.2)], 0.55, "#eef3f6", alpha=0.85)
    ic.tint(rust_mask(ic, knife, 1.2, 0.4, k=2) * (knife < 0), RUST, 0.5, "mix")
    # カッターの刃（折り線付き）
    cut = ic.box(17.0, 13.5, 18.0, 5.4, 0.3, -48)
    cut = ic.cut(cut, ic.poly([(23.5, 3.0), (30, 3.0), (30, 9.5)]))
    ic.shadow(cut, 0.5, 0.7, 0.5)
    ic.fill(cut, "#c3cad0", bevel=0.6, profile="lin", tex=metal_tex(ic, -48, 0.1, k=3), spec=0.7, shine=26)
    lx, ly = ic.local(17.0, 13.5, -48)
    snap = np.abs(((lx + ly * 0.6) % 3.2) - 1.6) - 1.35
    ic.fill(ic.inter(-snap - 0.0, cut + 0.4) * 0 + ic.inter(np.abs(((lx + ly * 0.6) % 3.2) - 1.6) - 0.22 + 0 * lx,
                                                            cut + 0.5), "#6e767c", light="flat", alpha=0.8)
    ic.line([(10.4, 21.2), (24.0, 6.0)], 0.5, "#ffffff", alpha=0.8)
    # 鋸の歯の破片（手前）
    saw_body = ic.box(18.0, 23.5, 19.0, 5.0, 0.4, -10)
    lx, ly = ic.local(18.0, 23.5, -10)
    teeth = ic.inter(np.abs(((lx + 30) % 2.4) - 1.2) * 1.4 + (ly - 2.5) - 1.6, -(ly - 2.4) + 0)
    saw = ic.union(saw_body, ic.inter(teeth, ic.box(18.0, 26.0, 18.6, 3.2, 0, -10)))
    ic.shadow(saw, 0.5, 0.8, 0.55)
    col = mix("#5d656c", "#8c949a", ic.noise(3, 3, k=4))
    col = mix(col, RUST, rust_mask(ic, saw, 1.6, 0.5, k=5) * 0.8)
    ic.fill(saw, col, bevel=0.7, profile="lin", tex=metal_tex(ic, -10, 0.12, k=6), spec=0.5, shine=22)
    ic.fill(ic.circle(11.6, 22.6, 0.9), "#2a2d30", light="flat")
    ic.fill(ic.circle(24.4, 20.4, 0.9), "#2a2d30", light="flat")
    ic.line([(9.0, 21.6), (27.0, 18.4)], 0.45, "#e8eef2", alpha=0.6)


@painter("duct_tape")
def p_duct_tape(ic):
    cx, cy = 14.8, 14.8
    side = ic.circle(cx + 2.6, cy + 2.6, 12.0)
    ic.fill(side, "#6c7075", bevel=1.0, spec=0.2, tex=1.0 + 0.08 * np.sin(np.hypot(ic.X - cx - 2.6, ic.Y - cy - 2.6) * 7))
    # 外側の側面をつなぐ帯
    band = ic.inter(ic.seg(cx, cy, cx + 2.6, cy + 2.6, 12.0), -(ic.circle(cx, cy, 12.0)))
    ic.fill(band, "#7a7e84", light="flat")
    face = ic.cut(ic.circle(cx, cy, 12.0), ic.circle(cx, cy, 5.9))
    r = np.hypot(ic.X - cx, ic.Y - cy)
    rings = 1.0 + 0.05 * np.sin(r * 6.3) + (ic.noise(0.7, 2, k=1) - 0.5) * 0.12
    ic.fill(face, mix("#b7bbc0", "#9da2a8", ic.noise(4, 3, k=2)), bevel=1.6, profile="soft", tex=rings,
            spec=0.45, shine=18)
    core = ic.cut(ic.circle(cx, cy, 5.9), ic.circle(cx, cy, 4.6))
    ic.fill(core, mix("#9a744a", "#7b5a36", ic.noise(1.0, 3, k=3)), bevel=0.8, spec=0.05)
    inner = ic.inter(ic.circle(cx, cy, 4.6), -ic.circle(cx + 1.7, cy + 1.7, 4.6))
    ic.fill(inner, "#4a3420", light="flat")
    # めくれて垂れた端
    tongue = ic.rough(ic.poly([(20.5, 23.2), (25.9, 18.6), (28.6, 22.5), (27.8, 30.6), (21.6, 30.8)]), 0.35, 0.8, k=4)
    ic.shadow(tongue, 0.4, 0.6, 0.45)
    lx, ly = ic.local(24.5, 25, 80)
    ic.fill(tongue, ic.lin(23, 21, 25, 31, "#c3c7cc", "#8e9399"), bevel=0.7,
            tex=1.0 + (ic.noise(0.5, 2, k=5) - 0.5) * 0.18 + 0.05 * np.sin(lx * 9), spec=0.3)
    ic.line([(21.2, 30.6), (22.6, 29.8), (23.6, 30.7), (24.8, 29.9), (26.0, 30.7), (27.5, 30.0)], 0.5, "#5e6267")


@painter("battery")
def p_battery(ic):
    ax1 = Axis(7.6, 26.5, 18.6, 7.0)
    w = 7.4
    for off, body_c, band_c, k in ((0.0, "#202226", "#d4741e", 1), (7.5, "#26303b", "#3f8fd6", 2)):
        ax = Axis(*ax1.p(0, off), *ax1.p(ax1.len, off))
        cell = ic.abox(ax, 0.8, 20.6, w, 1.2)
        ic.shadow(cell, 0.5, 0.7, 0.45)
        t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
        col = mix(body_c, band_c, (t > 14.5).astype(f32))
        ic.fill(cell, col, light="cyl", axis=ax, spec=0.6, shine=26, tex=ic.grain(0.05, 1.0, k=k))
        # − 側の銀の底、＋ 側の端子
        neg = ic.abox(ax, 0.8, 2.0, w - 0.2, 0.9)
        ic.fill(neg, "#b9bfc4", light="cyl", axis=ax, spec=0.7, shine=30)
        pos = ic.abox(ax, 20.4, 22.2, 2.8, 0.6)
        ic.fill(pos, "#c8ced2", light="cyl", axis=ax, spec=0.8, shine=30)
        if k == 1:      # 錆びた端子
            ic.tint((neg < 0) * smooth(0.45, 0.6, ic.noise(1.0, 3, k=9)), RUST, 0.85, "mix")
    # テープの帯
    mid = Axis(*ax1.p(10.0, -1.5), *ax1.p(10.0, 10.5))
    tape = ic.rough(ic.abox(mid, -0.3, 12.0, 4.6, 0.4), 0.25, 0.9, k=3)
    ic.shadow(tape, 0.4, 0.6, 0.4)
    ic.fill(tape, TAPE, bevel=0.8, tex=cloth_tex(ic, mid.deg, 0.12, k=4), spec=0.35)
    # 赤と黒の導線
    for pts, c, k in (([ax1.p(22.0, 0.0), (21.0, 3.0), (26.0, 2.2), (29.0, 6.0)], "#1c1c1e", 5),
                      ([ax1.p(22.0, 7.5), (26.5, 10.0), (28.0, 14.5), (29.6, 18.0)], "#c2241f", 6)):
        wire = ic.path(pts, 0.75)
        ic.shadow(wire, 0.4, 0.5, 0.4)
        ic.fill(wire, c, bevel=0.7, spec=0.6, shine=24)
        ic.fill(ic.circle(pts[-1][0], pts[-1][1], 0.85), "#d98c4a", bevel=0.6, spec=0.7)


@painter("gunpowder_pouch")
def p_gunpowder(ic):
    # こぼれた火薬（奥）
    pile = ic.rough(ic.ellipse(9.0, 28.0, 7.0, 2.6), 0.4, 0.7, k=1)
    ic.fill(pile, mix("#1a1918", "#3a3836", smooth(0.62, 0.8, ic.noise(0.45, 2, k=2))), bevel=1.2, spec=0.15)
    pouch = ic.smin(ic.ellipse(16.5, 21.0, 10.4, 8.0), ic.poly([(11.8, 16.0), (21.2, 16.0), (18.4, 10.6), (14.6, 10.6)]),
                    2.2)
    pouch = ic.rough(pouch, 0.25, 1.0, k=3)
    weave = 1.0 + 0.14 * np.sin(ic.X * math.pi * 2 / 1.1) * np.sin(ic.Y * math.pi * 2 / 1.1)
    folds = 1.0 + (ic.noise(2.2, 3, rot=90, stretch=3.5, k=4) - 0.5) * 0.5 * smooth(20, 11, ic.Y)
    ic.shadow(pouch, 0.5, 0.7, 0.4)
    ic.fill(pouch, mix("#b9996a", "#94774c", ic.noise(3.0, 3, k=5)), bevel=4.0, profile="soft",
            tex=weave * folds * ic.grain(0.08, 0.9, k=6), spec=0.04)
    # 口のひだ
    ruff = ic.rough(ic.poly([(13.4, 11.2), (12.2, 6.0), (14.6, 7.6), (16.0, 4.6), (17.6, 7.2), (20.2, 5.4),
                             (19.6, 11.2)]), 0.3, 0.7, k=7)
    ic.fill(ruff, "#a88b5c", bevel=1.3, tex=1.0 + (ic.noise(0.8, 3, rot=90, stretch=4, k=8) - 0.5) * 0.5,
            spec=0.03)
    ic.fill(ic.ellipse(16.2, 6.4, 2.6, 0.9), "#141312", light="flat", alpha=0.9)
    # 縛った紐と蝶結び
    tie = ic.box(16.4, 11.4, 9.2, 2.0, 1.0)
    ic.shadow(tie, 0.3, 0.5, 0.4)
    lx, _ly = ic.local(16.4, 11.4, 0)
    ic.fill(tie, "#ddc893", bevel=0.9, tex=1.0 + 0.2 * np.sign(np.sin((lx + ic.Y) * 2.6)), spec=0.1)
    for e in (ic.cut(ic.ellipse(22.4, 12.6, 2.4, 1.6, 30), ic.ellipse(22.4, 12.6, 1.2, 0.6, 30)),
              ic.path([(20.6, 12.2), (22.0, 15.6), (21.4, 17.6)], 0.5)):
        ic.fill(e, "#d4bd86", bevel=0.6, spec=0.1)
    # 赤い「火気厳禁」の判
    stamp = ic.cut(ic.circle(18.6, 21.6, 3.9), ic.circle(18.6, 21.6, 2.8))
    worn = smooth(0.35, 0.5, ic.noise(0.9, 3, k=9))
    ic.fill(stamp, "#b3201c", light="flat", alpha=0.85, tex=1.0)
    ic.fill(ic.inter(ic.union(ic.box(18.6, 21.6, 3.4, 0.9), ic.box(18.6, 21.6, 0.9, 3.4)), stamp * 0 - 0.1 +
                     ic.circle(18.6, 21.6, 2.4) * 0), "#b3201c", light="flat", alpha=0.85)
    ic.tint((ic.circle(18.6, 21.6, 4.2) < 0) * (1 - worn), "#b9996a", 0.55, "mix")
    # 粒
    for x, y in ((14.0, 29.5), (16.2, 30.2), (4.0, 29.8), (3.2, 26.8), (12.6, 25.9)):
        ic.fill(ic.circle(x, y, 0.55), "#232120", light="flat")


@painter("mutated_tissue")
def p_tissue(ic):
    blob = ic.smin(ic.smin(ic.circle(12.8, 19.0, 8.6), ic.circle(20.2, 16.8, 7.6), 3.0), ic.circle(16.8, 24.0, 6.4), 3.0)
    blob = ic.rough(blob, 1.2, 2.4, k=1)
    col = mix("#5c0d14", "#a8343c", smooth(0.35, 0.7, ic.noise(2.6, 4, k=2)))
    col = mix(col, "#d98a8a", smooth(0.68, 0.85, ic.noise(1.4, 3, k=3)) * 0.5)
    ic.fill(blob, col, bevel=4.0, profile="soft", spec=0.9, shine=34, spec_col="#ffe0e0",
            tex=1.0 + (ic.noise(1.0, 3, k=4) - 0.5) * 0.35)
    # 血管
    for pts in ([(6.0, 20.0), (9.5, 18.0), (12.0, 21.0), (15.5, 20.0)], [(18.0, 12.0), (19.0, 15.5), (23.5, 17.0)],
                [(13.0, 27.5), (15.0, 25.0), (19.5, 26.5)]):
        ic.fill(ic.inter(ic.path(pts, 0.42), blob + 0.6), "#3a0b2c", light="flat", alpha=0.75)
    # 黄緑の瘤（脈打つ。光る）
    for cx, cy, r in ((10.0, 15.2, 3.8), (21.6, 13.0, 3.1), (19.0, 22.6, 2.6), (12.4, 24.2, 2.1), (25.0, 19.0, 1.6)):
        d = ic.circle(cx, cy, r)
        ic.shadow(d, 0.4, 0.6, 0.4)
        ic.fill(d, mix("#a5c92e", "#e2ff74", smooth(r, 0, np.hypot(ic.X - cx + r * 0.3, ic.Y - cy + r * 0.3))),
                bevel=r, spec=0.95, shine=40, glow=0.45, glow_col="#c8ff3c", emit=0.25)
    # 白い菌糸
    for pts in ([(10.0, 15.0), (7.0, 12.4), (5.4, 13.4)], [(10.4, 15.4), (13.0, 11.0), (15.6, 10.4)],
                [(21.6, 13.0), (24.4, 10.2), (26.6, 11.6)], [(19.0, 22.6), (22.2, 26.4), (25.2, 25.0)],
                [(12.4, 24.2), (8.4, 26.4)]):
        ic.line(pts, 0.5, "#f1eee0", alpha=0.85)


@painter("infected_trophy")
def p_infected_trophy(ic):
    # 下顎の骨（U 字）と、両端から上へ伸びる枝
    arch = ic.inter(ic.cut(ic.ellipse(15.0, 10.0, 12.6, 14.0), ic.ellipse(15.0, 9.0, 7.6, 9.0)), -(ic.Y - 9.0))
    rami = ic.union(ic.box(4.0, 8.0, 4.0, 10.0, 1.6, -8), ic.box(26.0, 8.0, 4.0, 10.0, 1.6, 8))
    cond = ic.union(ic.circle(3.4, 3.4, 2.2), ic.circle(26.6, 3.4, 2.2))
    jaw = ic.smin(ic.smin(arch, rami, 1.0), cond, 1.0)
    pores = 1.0 + (ic.noise(0.6, 2, k=1) - 0.5) * 0.25
    col = mix(BONE, "#b5a77f", smooth(0.5, 0.75, ic.noise(3.0, 4, k=2)))
    col = mix(col, "#5a2416", smooth(0.62, 0.75, ic.noise(2.4, 4, k=3)) * 0.85)
    ic.fill(jaw, col, bevel=2.2, tex=pores, spec=0.2, shine=14)
    # 歯（内側の縁に沿って。1 本抜け、1 本黄ばむ）
    for i, ang in enumerate(np.linspace(200, 340, 9)):
        if i == 6:
            continue
        a = math.radians(ang)
        x, y = 15.0 + 8.6 * math.cos(a) * 1.0, 9.0 + 9.9 * math.sin(-a)
        tooth = ic.box(x, y, 2.0, 3.0, 0.8, ang + 90)
        ic.shadow(tooth, 0.3, 0.5, 0.35)
        tc = "#d9c88a" if i == 3 else "#f2ecd8"
        ic.fill(tooth, tc, bevel=0.9, spec=0.5, shine=24)
    # 針金と名札
    ic.line([(26.4, 11.5), (27.6, 15.5), (25.4, 19.6)], 0.55, "#8d9297", r1=0.3)
    tag = ic.rough(ic.box(21.5, 24.5, 12.0, 7.6, 1.0, -12), 0.15, 0.8, k=4)
    tag = ic.cut(tag, ic.poly([(26.5, 26.0), (28.5, 25.0), (29.0, 30.0), (25.0, 30.0)]))
    ic.shadow(tag, 0.5, 0.8, 0.5)
    ic.fill(tag, "#e9edf0", bevel=0.7, spec=0.4, tex=ic.grain(0.04, 1.0, k=5))
    stripe = ic.inter(ic.box(21.0, 22.0, 12.4, 2.6, 0, -12), tag)
    ic.fill(stripe, "#2a5bb6", light="flat")
    for y0 in (24.6, 26.4):
        ic.fill(ic.inter(ic.box(19.4, y0 + 0.6, 7.0, 0.8, 0, -12), tag + 0.4), "#3b3f45", light="flat", alpha=0.8)
    ic.fill(ic.circle(25.0, 20.6, 0.7), "#5c6066", light="flat")
    ic.tint((tag < 0) * smooth(0.6, 0.75, ic.noise(1.4, 3, k=6)), "#6a2a1a", 0.6)


@painter("volatile_trophy")
def p_volatile_trophy(ic):
    # 紫に光る神経の束（後ろ）
    for pts, k in (([(8.0, 17.0), (5.0, 21.0), (6.6, 25.0), (3.6, 29.4)], 1),
                   ([(10.0, 18.6), (9.4, 23.2), (11.6, 26.6), (10.4, 30.6)], 2),
                   ([(7.0, 15.0), (3.0, 16.0), (1.8, 20.4)], 3)):
        nerve = ic.path(pts, 1.1, 0.45)
        ic.fill(nerve, "#b05cf0", bevel=0.8, spec=0.6, glow=0.9, glow_col="#c070ff", emit=0.45)
        ic.line(pts, 0.4, "#f0d6ff", alpha=0.85, emit=0.8)
    # 頭骨のかけら（頭頂・眼窩・上顎）
    skull = ic.smin(ic.ellipse(14.5, 11.0, 10.4, 8.4, -12), ic.box(21.0, 16.5, 11.0, 6.4, 2.0, 18), 2.4)
    skull = ic.cut(ic.rough(skull, 0.4, 1.2, k=4), ic.poly([(3.0, 15.0), (8.0, 21.0), (2.0, 24.0)]))
    F1, F2, _ = ic.cells(3.2, k=5)
    cracks = smooth(0.12, 0.0, F2 - F1)
    col = mix("#cbbd9c", "#8f8164", smooth(0.45, 0.8, ic.noise(3.0, 4, k=6)))
    ic.fill(skull, col, bevel=3.0, tex=(1.0 - 0.45 * cracks) * (1 + (ic.noise(0.6, 2, k=7) - 0.5) * 0.2),
            spec=0.25, shine=16)
    ic.tint((skull < 0) * smooth(0.6, 0.72, ic.noise(2.0, 4, k=8)), "#1c1012", 0.75)
    # 眼窩（奥でかすかに光る）
    sock = ic.ellipse(12.4, 11.6, 3.6, 2.9, -15)
    ic.fill(sock, "#140c12", bevel=2.0, profile="lin", contrast=-0.6)
    ic.fill(ic.circle(12.0, 11.9, 1.0), "#c070ff", light="flat", glow=0.6, emit=1.0)
    # 牙（長い 2 本と小さい歯）
    for pts in ([(17.6, 18.6), (20.6, 19.0), (19.0, 29.6)], [(24.0, 19.8), (26.6, 20.6), (25.4, 27.2)],
                [(21.2, 19.4), (23.0, 19.6), (22.0, 22.6)]):
        f = ic.poly(pts)
        ic.shadow(f, 0.4, 0.6, 0.45)
        ic.fill(f, ic.lin(pts[0][0], pts[0][1], pts[2][0], pts[2][1], "#e9e0c6", "#fbf8ee"), bevel=0.8,
                profile="lin", spec=0.7, shine=28)
    ic.tint((ic.circle(19.4, 20.4, 2.0) < 0), "#5a1010", 0.5)


@painter("apex_trophy")
def p_apex_trophy(ic):
    rot = -14
    cx, cy = 14.0, 17.0

    def P(x, y):
        r = math.radians(rot)
        return (cx + x * math.cos(r) - y * math.sin(r), cy + x * math.sin(r) + y * math.cos(r))
    centrum = ic.box(*P(0, 5.0), 13.0, 9.0, 3.6, rot)
    arch = ic.cut(ic.circle(*P(0, -3.0), 6.4), ic.circle(*P(0, -2.6), 3.0))
    trans_l = ic.seg(*P(-4.0, -3.2), *P(-11.5, -5.4), 2.4, 1.4)
    trans_r = ic.seg(*P(4.0, -3.2), *P(11.0, -5.4), 2.4, 1.4)
    spine = ic.seg(*P(0, -8.0), *P(0, -14.0), 2.2, 1.0)
    bone = ic.smin(ic.smin(ic.smin(centrum, arch, 1.2), ic.union(trans_l, trans_r), 1.2), spine, 1.2)
    col = mix("#d8cca8", "#a8987a", smooth(0.45, 0.8, ic.noise(3.0, 4, k=1)))
    ic.fill(bone, col, bevel=2.6, tex=1.0 + (ic.noise(0.55, 2, k=2) - 0.5) * 0.3, spec=0.25)
    # 脊柱管の奥が橙に脈打つ
    canal = ic.circle(*P(0, -2.6), 3.0)
    ic.fill(canal, "#ff8a1e", light="flat", glow=1.0, glow_col="#ff7a10", emit=1.0)
    ic.fill(ic.circle(*P(0.5, -2.2), 1.6), "#ffd27a", light="flat", emit=1.0)
    # 赤黒い結晶（右上から生える）
    shards = [([(17.0, 13.8), (21.6, 2.6), (25.6, 5.4), (21.4, 15.4)], (19.2, 14.6), (23.6, 4.0)),
              ([(20.6, 17.4), (29.4, 9.6), (30.4, 14.2), (23.4, 19.6)], (22.0, 18.6), (29.9, 11.9)),
              ([(15.0, 10.6), (16.0, 4.2), (19.0, 8.6), (17.6, 12.6)], (16.4, 11.6), (16.6, 6.0))]
    for pts, base, tip in shards:
        d = ic.poly(pts)
        ic.shadow(d, 0.5, 0.7, 0.55)
        ax = Axis(*base, *tip)
        px = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
        col = mix("#8e1420", "#360309", (px > 0).astype(f32))
        ic.fill(d, col, bevel=0.6, profile="lin", spec=0.9, shine=40, spec_col="#ffb0a0")
        ic.line([base, ((base[0] + tip[0]) / 2 + 0.3, (base[1] + tip[1]) / 2), tip], 0.55, "#ff9a2a",
                glow=0.8, glow_col="#ff8018", emit=1.0)


@painter("inhibitor")
def p_inhibitor(ic):
    ax = Axis(4.2, 28.0, 28.4, 3.8)
    pad = ic.abox(ax, 0.0, 1.4, 7.2, 0.6)
    rod = ic.abox(ax, 1.0, 9.0, 2.0, 0.4)
    ic.fill(rod, "#d5dbe0", light="cyl", axis=ax, spec=0.5)
    ic.fill(pad, "#2c2f34", bevel=0.6, spec=0.4)
    flange = ic.abox(ax, 8.6, 10.0, 10.0, 0.6)
    ic.fill(flange, "#c4c9cd", bevel=0.6, spec=0.8, shine=30)
    barrel = ic.abox(ax, 9.8, 23.2, 6.4, 0.9)
    ic.fill(barrel, "#bcd6e6", light="cyl", axis=ax, spec=0.9, shine=40)
    liq = ic.abox(ax, 11.8, 22.6, 4.8, 0.4)
    ic.fill(liq, "#28b8ff", light="cyl", axis=ax, spec=0.3, glow=0.9, glow_col="#30c0ff", emit=0.55)
    glass_streak(ic, ax, 12.5, 22.0, -0.4, 0.45, 0.8, "#e8fbff")
    ic.fill(ic.abox(ax, 11.0, 12.0, 5.4, 0.3), "#1d1f22", light="cyl", axis=ax)     # 押し子のゴム
    for tt in (14.0, 16.0, 18.0, 20.0):
        x0, y0 = ax.p(tt, -3.1)
        x1, y1 = ax.p(tt, -1.4)
        ic.line([(x0, y0), (x1, y1)], 0.45, "#16181b")
    for t0 in (10.0, 21.9):
        ic.fill(ic.abox(ax, t0, t0 + 1.3, 7.2, 0.4), "#d9dde0", light="cyl", axis=ax, spec=0.9, shine=34)
    ic.fill(ic.abox(ax, 23.0, 25.2, 3.2, 0.5), "#c9ced2", light="cyl", axis=ax, spec=0.8)
    cap = ic.abox(ax, 25.0, ax.len, 2.4, 1.1)
    ic.fill(cap, "#e46a2a", light="cyl", axis=ax, spec=0.5)


@painter("uv_shroom")
def p_uv_shroom(ic):
    soil = ic.rough(ic.ellipse(16.0, 27.4, 11.5, 3.8), 0.6, 1.0, k=1)
    ic.fill(soil, mix("#3b2a1c", "#22170f", ic.noise(1.0, 3, k=2)), bevel=1.6, spec=0.5, shine=30,
            tex=1.0 + (ic.noise(0.5, 2, k=3) - 0.5) * 0.4)
    for (sx, sy, tx, ty, w, cr, ch, k) in ((12.0, 27.0, 10.6, 9.6, 1.4, 6.6, 4.2, 4),
                                           (20.6, 27.0, 21.4, 15.0, 1.2, 5.0, 3.2, 5)):
        stalk = ic.path([(sx, sy), ((sx + tx) / 2 + 0.8, (sy + ty) / 2), (tx, ty)], w, w * 0.8)
        ic.shadow(stalk, 0.4, 0.5, 0.35)
        ic.fill(stalk, "#e8e3e6", light="cyl", axis=Axis(sx, sy, tx, ty), spec=0.4,
                tex=1.0 + (ic.noise(0.7, 2, rot=90, stretch=4, k=k) - 0.5) * 0.2)
        gill = ic.ellipse(tx, ty + 0.4, cr * 0.92, 1.5)
        ic.fill(gill, "#c86bff", light="flat", glow=1.0, glow_col="#b860ff", emit=1.0,
                tex=1.0 + 0.25 * np.sin((ic.X - tx) * 5.0))
        cap = ic.inter(ic.ellipse(tx, ty, cr, ch), ic.Y - ty - 0.2)
        ic.shadow(cap, 0.4, 0.6, 0.4)
        ic.fill(cap, mix("#5c4a72", "#9a86b0", smooth(ch, -ch, ic.Y - ty)), bevel=ch * 0.9, spec=0.6, shine=24,
                tex=1.0 + (ic.noise(1.0, 3, k=k + 3) - 0.5) * 0.25)
        for i in range(3):
            ic.fill(ic.circle(tx - cr * 0.4 + i * cr * 0.4, ty - ch * 0.45 + (i % 2) * 0.6, 0.45), "#d9c8ee",
                    light="flat", alpha=0.85)
    ic.fill(ic.ellipse(16.0, 26.8, 8.0, 1.0), "#9a50e0", light="flat", alpha=0.0, glow=0.35)


@painter("bandage")
def p_bandage(ic):
    # 垂れた端（後ろ）
    tail = ic.rough(ic.path([(16.0, 22.0), (21.5, 24.5), (25.5, 25.0), (29.4, 28.6)], 2.6, 2.2), 0.3, 0.9, k=1)
    ic.shadow(tail, 0.4, 0.6, 0.35)
    gauze = 1.0 + 0.10 * np.sin(ic.X * 5.5) * np.sin(ic.Y * 5.5) + (ic.noise(0.6, 2, k=2) - 0.5) * 0.12
    ic.fill(tail, "#ece9e0", bevel=1.2, tex=gauze, spec=0.08)
    ic.tint((tail < 0) * smooth(0.55, 0.7, ic.noise(2.0, 4, k=3)), "#a8402e", 0.45)
    # 巻いた本体（奥の円・つなぎ・手前の面）
    back = ic.circle(17.0, 18.4, 9.0)
    ic.fill(back, "#d3d0c6", bevel=1.0, tex=gauze)
    link = ic.inter(ic.seg(12.0, 13.6, 17.0, 18.4, 9.0), -ic.circle(12.0, 13.6, 9.0))
    ic.fill(link, "#dedbd2", light="cyl", axis=Axis(16.0, 9.0, 8.0, 17.0), tex=gauze, spec=0.1)
    face = ic.circle(12.0, 13.6, 9.0)
    r = np.hypot(ic.X - 12.0, ic.Y - 13.6)
    ang = np.arctan2(ic.Y - 13.6, ic.X - 12.0)
    spiral = 1.0 - 0.10 * (np.sin(r * 4.6 - ang * 0.73) > 0.55)
    ic.fill(face, "#f4f2ec", bevel=1.6, profile="soft", tex=spiral * gauze, spec=0.1)
    ic.fill(ic.circle(12.0, 13.6, 1.2), "#b7b2a6", bevel=0.6)
    ic.tint((face < 0) * smooth(0.6, 0.72, ic.noise(1.8, 4, k=4)) * smooth(9, 4, r), "#b0503a", 0.3)
    # 安全ピン
    pin = Axis(20.6, 26.4, 28.0, 22.6)
    for off in (-0.7, 0.7):
        x0, y0 = pin.p(0.6, off)
        x1, y1 = pin.p(7.4, off)
        ic.line([(x0, y0), (x1, y1)], 0.55, "#d8dde1")
    coil = ic.cut(ic.circle(*pin.p(0.4), 1.4), ic.circle(*pin.p(0.4), 0.7))
    ic.fill(coil, "#cfd4d8", bevel=0.5, spec=0.8)
    ic.fill(ic.abox(pin, 6.6, 8.6, 2.6, 0.6), "#b7bdc2", bevel=0.6, spec=0.8)


@painter("medkit")
def p_medkit(ic):
    handle = ic.cut(ic.box(16.0, 8.4, 11.0, 6.0, 2.4), ic.box(16.0, 9.4, 6.6, 3.0, 1.0))
    ic.fill(ic.inter(handle, ic.Y - 10.0 + 0 * ic.X), "#1e1f22", bevel=1.0, spec=0.4)
    box = ic.box(16.0, 19.6, 26.4, 17.4, 2.6)
    ic.shadow(box, 0.3, 0.5, 0.3)
    col = mix("#c4161a", "#8e0e12", smooth(0.5, 0.8, ic.noise(3.0, 4, k=1)) * 0.5)
    ic.fill(box, col, bevel=2.0, profile="soft", spec=0.55, shine=22, tex=ic.grain(0.05, 1.2, k=2))
    ic.stroke(ic.Y - 14.2 + 0 * ic.X, 0.55, "#5a0608", alpha=0.85 * 1.0)
    ic.fill(ic.inter(ic.box(16.0, 14.2, 30, 0.5), box + 0.6), "#e8504c", light="flat", alpha=0.0)
    # 留め金（右は外れている）
    ic.fill(ic.box(8.6, 14.2, 2.6, 3.2, 0.5), "#c9ced2", bevel=0.6, spec=0.8)
    ic.fill(ic.box(24.6, 15.4, 2.6, 3.2, 0.5, 35), "#c9ced2", bevel=0.6, spec=0.8)
    # 白い十字
    cross = ic.union(ic.box(16.0, 20.6, 10.2, 3.6, 0.5), ic.box(16.0, 20.6, 3.6, 10.2, 0.5))
    ic.shadow(cross, 0.3, 0.4, 0.3)
    ic.fill(cross, "#f6f3ec", bevel=0.8, spec=0.3)
    # はみ出した包帯
    band = ic.rough(ic.path([(22.0, 14.4), (26.0, 13.2), (29.0, 14.6), (30.2, 17.6)], 1.3, 1.0), 0.2, 0.8, k=3)
    ic.shadow(band, 0.3, 0.5, 0.35)
    ic.fill(band, "#f1eee6", bevel=0.8, tex=1.0 + 0.1 * np.sin(ic.X * 5) * np.sin(ic.Y * 5))
    ic.tint((box < 0) * smooth(0.62, 0.75, ic.noise(2.4, 4, k=4)), "#3a0a0a", 0.4)


@painter("immunity_booster")
def p_immunity(ic):
    ax = Axis(12.6, 29.6, 19.4, 2.4)
    vial = ic.abox(ax, 0.6, 20.0, 10.0, 2.4)
    ic.fill(vial, "#c9d6e8", light="cyl", axis=ax, spec=0.9, shine=40)
    liq = ic.abox(ax, 1.6, 15.5, 8.4, 1.8)
    ic.fill(liq, "#8a3cff", light="cyl", axis=ax, spec=0.4, glow=0.85, glow_col="#a050ff", emit=0.5)
    ic.stroke(ic.abox(ax, 15.2, 15.8, 8.2, 0.2), 0.3, "#d8b8ff", alpha=0.8)
    label = ic.abox(ax, 5.2, 12.0, 10.2, 0.4)
    ic.fill(label, "#f2f1ec", light="cyl", axis=ax, spec=0.15)
    # UV の文字
    def T(t, o):
        return ax.p(t, o)
    for pts in ([T(10.6, -2.6), T(7.4, -2.6), T(7.4, -0.6), T(10.6, -0.6)],
                [T(10.6, 0.6), T(7.2, 1.6), T(10.6, 2.8)]):
        ic.line(pts, 0.75, "#7a2ee0")
    glass_streak(ic, ax, 2.0, 18.5, -3.4, 0.5, 0.7)
    crimp = ic.abox(ax, 19.4, 20.8, 8.6, 0.4)
    ic.fill(crimp, "#9aa1a7", light="cyl", axis=ax, spec=0.7)
    cap = ic.abox(ax, 20.4, 26.6, 10.8, 1.4)
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    ridges = 1.0 + 0.14 * np.sign(np.sin(o * 2 * math.pi / 1.3))
    ic.fill(cap, "#c3c9ce", light="cyl", axis=ax, tex=ridges * metal_tex(ic, ax.deg, 0.08, k=1), spec=0.9, shine=34)


def _rounds(ic, n, start, step, ang, case_len, case_w, tip_len, tip_c, *, neck_w=None, shoulder=0.0,
            lead=None, k=0):
    """薬莢の弾を並べる（後ろから手前へ）。"""
    for i in range(n):
        bx, by = start[0] + step[0] * i, start[1] + step[1] * i
        ax = Axis(bx, by, bx + math.cos(math.radians(ang)), by + math.sin(math.radians(ang)))
        nw = neck_w or case_w
        parts = [ic.abox(ax, 0.0, case_len, case_w, 0.5)]
        if shoulder > 0:
            a0, a1 = ax.p(case_len, -case_w / 2), ax.p(case_len, case_w / 2)
            b0, b1 = ax.p(case_len + shoulder, -nw / 2), ax.p(case_len + shoulder, nw / 2)
            parts.append(ic.poly([a0, b0, b1, a1]))
            parts.append(ic.abox(ax, case_len + shoulder - 0.1, case_len + shoulder + 2.2, nw, 0.2))
        body = ic.union(*parts)
        ic.shadow(body, 0.6, 0.8, 0.55)
        neck_end = case_len + (shoulder + 2.2 if shoulder > 0 else 0.0)
        tx0, ty0 = ax.p(neck_end - 0.2)
        tx1, ty1 = ax.p(neck_end + tip_len)
        tip = ic.seg(tx0, ty0, tx1, ty1, nw / 2 - 0.1, 0.35)
        c = "#8c9196" if (lead is not None and i == lead) else tip_c
        ic.fill(tip, c, light="cyl", axis=ax, spec=0.8, shine=30)
        ic.fill(body, BRASS, light="cyl", axis=ax, spec=0.95, shine=34, spec_col="#fff2c0",
                tex=metal_tex(ic, ax.deg, 0.06, k=k + i))
        ic.fill(ic.abox(ax, 0.0, 0.9, case_w + 0.4, 0.3), "#a07c28", light="cyl", axis=ax, spec=0.6)
        ic.fill(ic.abox(ax, 1.0, 1.5, case_w - 0.2, 0.1), "#6e5418", light="cyl", axis=ax, alpha=0.8)


@painter("ammo_pistol")
def p_ammo_pistol(ic):
    _rounds(ic, 5, (6.0, 26.6), (4.4, -1.6), -62, 7.2, 4.2, 4.2, COPPER, lead=2)


@painter("ammo_shotgun")
def p_ammo_shotgun(ic):
    for i in range(3):
        bx, by = 6.0 + i * 6.6, 29.5 - i * 2.6
        ax = Axis(bx, by, bx + math.cos(math.radians(-66)), by + math.sin(math.radians(-66)))
        hull = ic.abox(ax, 4.6, 20.0, 6.4, 0.9)
        base = ic.abox(ax, 0.0, 5.4, 6.8, 0.7)
        ic.shadow(ic.union(hull, base), 0.6, 0.8, 0.55)
        t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
        o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
        ribs = 1.0 + 0.10 * np.sign(np.sin(o * 2 * math.pi / 1.2))
        ic.fill(hull, "#b8221e", light="cyl", axis=ax, tex=ribs, spec=0.5, shine=24)
        ic.fill(base, BRASS, light="cyl", axis=ax, spec=0.95, shine=34, spec_col="#fff2c0")
        ic.fill(ic.abox(ax, 0.0, 0.9, 7.2, 0.3), "#9a7826", light="cyl", axis=ax)
        top = ic.abox(ax, 18.4, 20.0, 6.4, 0.6)
        if i == 1:     # 口が開いて粒が見える
            ic.fill(top, "#2a0c0a", light="flat")
            for o2 in (-1.6, 0.0, 1.6):
                px, py = ax.p(19.0, o2)
                ic.fill(ic.circle(px, py, 0.9), "#9aa0a6", bevel=0.8, spec=0.8)
            for o2 in (-3.3, 3.3):
                x0, y0 = ax.p(19.4, o2)
                x1, y1 = ax.p(21.0, o2 * 1.2)
                ic.line([(x0, y0), (x1, y1)], 0.8, "#a01c18")
        else:
            ic.fill(top, "#8e1916", light="cyl", axis=ax)
            cx, cy = ax.p(19.5)
            for a in (0, 60, 120):
                r = math.radians(a + ax.deg)
                ic.line([(cx - math.cos(r) * 2.6, cy - math.sin(r) * 2.6 * 0.4),
                         (cx + math.cos(r) * 2.6, cy + math.sin(r) * 2.6 * 0.4)], 0.4, "#5a0c0a", alpha=0.9)


@painter("ammo_rifle")
def p_ammo_rifle(ic):
    _rounds(ic, 3, (5.4, 29.6), (5.6, -1.8), -60, 12.4, 4.4, 7.4, "#c46a34", neck_w=3.0, shoulder=1.6)


@painter("bolt")
def p_bolt(ic):
    ax = Axis(5.0, 27.2, 27.4, 4.8)
    # 羽根（上下 2 枚と真ん中の 1 枚）
    for side in (-1, 1):
        pts = [ax.p(1.0, side * 1.0), ax.p(2.0, side * 4.4), ax.p(6.6, side * 4.0), ax.p(8.4, side * 1.0)]
        v = ic.poly(pts)
        ic.fill(v, "#e8c21c", bevel=0.8, profile="lin", spec=0.4, tex=ic.grain(0.06, 1.0, k=1 + side))
        ic.stroke(ic.poly(pts), 0.35, "#a8860c", alpha=0.6)
    shaft = ic.abox(ax, 0.4, 19.6, 2.8, 0.6)
    ic.shadow(shaft, 0.4, 0.6, 0.4)
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    ribs = 1.0 + 0.30 * np.sign(np.sin((t + o * 0.9) * 2 * math.pi / 1.7))
    ic.fill(shaft, "#5e6469", light="cyl", axis=ax, tex=ribs, spec=0.5)
    ic.fill(ic.abox(ax, 1.0, 7.0, 0.9, 0.3), "#d8b318", light="flat")
    head = ic.poly([ax.p(18.6, -2.2), ax.p(ax.len, 0.0), ax.p(18.6, 2.2)])
    ic.shadow(head, 0.4, 0.6, 0.4)
    ic.fill(head, mix("#e6ecf0", "#8d959b", (o > 0).astype(f32)), bevel=0.5, profile="lin", spec=0.8, shine=30)
    ic.fill(ic.abox(ax, 0.0, 0.9, 3.0, 0.3), "#3c4145", light="flat")


@painter("survivor_arrow")
def p_survivor_arrow(ic):
    ax = Axis(3.4, 28.6, 28.8, 3.2)
    for side in (-1, 1):
        pts = [ax.p(1.2, side * 0.7), ax.p(1.8, side * 3.6), ax.p(6.8, side * 3.4), ax.p(8.6, side * 0.7)]
        v = ic.poly(pts)
        ic.fill(v, "#e2582a", bevel=0.6, profile="lin", spec=0.35, tex=ic.grain(0.08, 0.8, k=2 + side))
        ic.stroke(v, 0.35, "#9a3010", alpha=0.6)
    shaft = ic.abox(ax, 0.2, 29.0, 1.9, 0.9)
    ic.shadow(shaft, 0.4, 0.6, 0.35)
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    nodes = 1.0 - 0.28 * (np.abs(((t + 1.0) % 7.0) - 3.5) > 3.05)
    ic.fill(shaft, "#cdb46a", light="cyl", axis=ax, tex=nodes * metal_tex(ic, ax.deg, 0.08, k=4), spec=0.3)
    ic.fill(ic.abox(ax, 0.0, 0.8, 2.4, 0.4), "#3b2a1a", light="flat")
    head = ic.poly([ax.p(27.4, -2.2), ax.p(ax.len + 0.4, 0.0), ax.p(27.4, 2.2), ax.p(28.2, 0.0)])
    ic.shadow(head, 0.4, 0.6, 0.4)
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    ic.fill(head, mix("#e3e8eb", "#80888e", (o > 0).astype(f32)), bevel=0.4, profile="lin", spec=0.8, shine=30)
    for tt in (26.2, 27.4):
        ic.fill(ic.abox(ax, tt, tt + 0.7, 2.6, 0.3), "#8e9499", light="cyl", axis=ax, spec=0.7)


@painter("money")
def p_money(ic):
    def note(cx, cy, rot, k, top=False):
        d = ic.box(cx, cy, 25.0, 12.6, 0.5, rot)
        if top:
            burn = ic.circle(cx + 13.4 * math.cos(math.radians(rot)) - 6.4 * math.sin(math.radians(-rot)) * 0,
                             cy - 7.2, 5.4)
            burn = ic.rough(ic.circle(27.6, 6.0, 5.2), 0.8, 1.0, k=k + 7)
            d = ic.cut(d, burn + 1.2)
        ic.shadow(d, 0.4, 0.6, 0.35)
        lx, ly = ic.local(cx, cy, rot)
        crumple = ic.noise(2.0, 4, k=k)
        col = mix("#a9bb92", "#8aa278", smooth(0.3, 0.7, crumple))
        ic.fill(d, col, bevel=0.6, tex=1.0 + (crumple - 0.5) * 0.35, spec=0.05)
        frame = ic.box(cx, cy, 22.0, 9.6, 0.4, rot)
        ic.stroke(frame, 0.5, "#4f6b46", alpha=0.75)
        ox = cx + 5.6 * math.cos(math.radians(rot))
        oy = cy + 5.6 * math.sin(math.radians(rot))
        ic.fill(ic.inter(ic.ellipse(ox, oy, 3.0, 3.6, rot), d), "#5f7a52", bevel=0.8, alpha=0.85)
        vx = cx - 7.0 * math.cos(math.radians(rot))
        vy = cy - 7.0 * math.sin(math.radians(rot))
        ic.fill(ic.inter(ic.box(vx, vy, 3.4, 2.2, 0.3, rot), d), "#4f6b46", light="flat", alpha=0.8)
        if top:
            edge = ic.inter(np.abs(burn + 1.2) - 0.9, ic.box(cx, cy, 25.0, 12.6, 0.5, rot))
            ic.fill(edge, "#241612", light="flat")
            ic.fill(ic.inter(np.abs(burn + 1.2) - 0.35, ic.box(cx, cy, 25.0, 12.6, 0.5, rot)), "#ff7a20",
                    light="flat", glow=0.4, emit=1.0, alpha=0.9)
        return d
    note(16.0, 19.8, -26, 1)
    note(15.4, 17.6, -16, 2)
    top = note(16.4, 15.6, -22, 3, top=True)
    band = ic.inter(ic.box(13.6, 17.0, 2.6, 30.0, 0.8, -22 + 0), ic.box(15.6, 17.4, 30, 14.6, 0, -22))
    ic.shadow(band, 0.3, 0.5, 0.35)
    ic.fill(band, "#b0492e", light="cyl", axis=Axis(12.6, 6.0, 18.0, 28.0), spec=0.5, shine=20)


# --- 回復・食べ物 ----------------------------------------------------------------
@painter("energy_drink")
def p_energy_drink(ic):
    ax = Axis(14.2, 30.4, 18.4, 1.8)
    body = ic.abox(ax, 2.0, 24.6, 14.4, 1.6)
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    dent = np.exp(-(((t - 12.0) / 3.0) ** 2 + ((o - 4.2) / 2.2) ** 2))
    ic.fill(body, "#17181c", light="cyl", axis=ax, spec=1.0, shine=44, tex=1.0 - 0.35 * dent)
    ic.fill(ic.inter(ic.ellipse(*ax.p(11.4, 3.8), 1.0, 2.2, ax.deg), body), "#7a7f88", light="flat", alpha=0.7)
    # 縁と底の銀
    ic.fill(ic.abox(ax, 0.6, 2.6, 13.2, 1.0), "#b8bec4", light="cyl", axis=ax, spec=0.9, shine=34)
    neck = ic.poly([ax.p(24.4, -7.2), ax.p(26.4, -5.8), ax.p(26.4, 5.8), ax.p(24.4, 7.2)])
    ic.fill(neck, "#c4cacf", light="cyl", axis=ax, spec=0.9, shine=34)
    lid = ic.ellipse(*ax.p(26.6), 1.6, 5.9, ax.deg)
    ic.fill(lid, "#9aa1a7", bevel=0.8, spec=0.6)
    tab = ic.ellipse(*ax.p(27.6, 1.0), 1.2, 1.6, ax.deg)
    ic.fill(tab, "#dfe4e8", bevel=0.6, spec=0.9)
    ic.fill(ic.ellipse(*ax.p(26.4, -2.2), 0.8, 1.4, ax.deg), "#202226", light="flat")
    # 黄緑の稲妻のロゴ
    def T(tt, oo):
        return ax.p(tt, oo)
    bolt = ic.poly([T(20.0, -1.0), T(13.4, -4.0), T(13.8, -0.2), T(6.0, 1.6), T(12.0, -0.2), T(11.6, -3.6)][::1])
    bolt = ic.poly([T(21.0, -1.6), T(13.0, -4.4), T(13.6, -0.8), T(5.4, 2.2), T(11.2, 0.8), T(10.8, 4.2),
                    T(17.4, 1.2), T(16.6, -0.6)])
    ic.fill(bolt, "#b6ff2e", light="cyl", axis=ax, spec=0.4, glow=0.25, glow_col="#a0ff20", emit=0.35)
    ic.stroke(ic.abox(ax, 3.4, 3.8, 14.4, 0.2), 0.4, "#b6ff2e", alpha=0.8)


@painter("canned_food")
def p_canned_food(ic):
    body = ic.union(ic.box(16.0, 21.0, 19.6, 15.0, 0.6), ic.ellipse(16.0, 28.2, 9.8, 2.8))
    ax = Axis(16.0, 30.0, 16.0, 12.0)
    ribs = 1.0 + 0.10 * np.sign(np.sin(ic.Y * 2 * math.pi / 1.6))
    ic.fill(body, "#b9bec3", light="cyl", axis=ax, tex=ribs, spec=0.9, shine=36)
    # 半分剥げたラベル
    tear = ic.rough(ic.X - 21.0 - (ic.Y - 21.0) * 0.4, 1.0, 1.0, k=1)
    label = ic.inter(ic.inter(body + 0.0, ic.box(16.0, 21.4, 21.0, 11.4)), tear)
    ic.fill(label, "#d4622a", light="cyl", axis=ax, spec=0.25, tex=ic.grain(0.06, 1.0, k=2))
    ic.fill(ic.inter(ic.box(16.0, 16.4, 21, 1.4), label), "#f1e3c4", light="cyl", axis=ax, spec=0.2)
    ic.fill(ic.inter(ic.box(16.0, 26.4, 21, 1.4), label), "#f1e3c4", light="cyl", axis=ax, spec=0.2)
    ic.fill(ic.inter(ic.ellipse(12.4, 21.4, 4.0, 3.0), label), "#7a3010", light="cyl", axis=ax, alpha=0.9)
    ic.fill(ic.inter(ic.ellipse(12.4, 21.4, 2.4, 1.6), label), "#e3a050", light="flat", alpha=0.9)
    ic.stroke(tear, 0.4, "#f3e2c8", alpha=0.85 * (label < 0.6) * (label > -1.2))
    # 開いた口と豆
    rim = ic.ellipse(16.0, 13.6, 9.8, 3.6)
    ic.fill(rim, "#d5dade", bevel=0.6, spec=0.9)
    mouth = ic.ellipse(16.0, 13.7, 8.6, 2.8)
    ic.fill(mouth, "#8c3412", light="flat")
    for bx, by in ((11.6, 13.4), (14.4, 12.6), (17.4, 13.0), (20.4, 13.8), (13.2, 14.8), (16.4, 14.9),
                   (19.2, 12.4), (9.4, 13.9), (22.2, 13.2)):
        bean = ic.inter(ic.ellipse(bx, by, 1.5, 0.95, 20), mouth)
        ic.fill(bean, "#c86e34", bevel=0.9, spec=0.8, shine=28)
    # 半開きの蓋
    lid = ic.rough(ic.ellipse(19.6, 7.6, 8.8, 3.4, -24), 0.25, 0.6, k=3)
    ic.shadow(lid, 0.3, 0.6, 0.45)
    ic.fill(lid, "#c7ccd0", bevel=1.0, spec=0.9, shine=30, tex=1.0 + 0.08 * np.sin(np.hypot(ic.X - 19.6, ic.Y - 7.6) * 3))


@painter("chocolate_bar")
def p_chocolate(ic):
    ax = Axis(4.0, 28.6, 28.0, 4.0)
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    bar = ic.abox(ax, 12.0, 32.0, 10.0, 0.8)
    bite = ic.union(ic.circle(*ax.p(31.4, -3.2), 3.2), ic.circle(*ax.p(32.2, 1.6), 3.0), ic.circle(*ax.p(30.0, 4.6), 2.2))
    bar = ic.cut(bar, bite)
    # 板チョコの区画
    seg_t = np.abs(((t - 12.0) % 4.4) - 2.2)
    seg_o = np.abs(o) - 0.0
    grooves = (seg_t > 1.85) | (np.abs(o) < 0.3)
    ic.fill(bar, "#5a3017", bevel=0.9, profile="lin", spec=0.45, shine=26, tex=1.0 - 0.35 * grooves)
    ic.fill(ic.inter(np.abs(bite - 0.25) - 0.25, bar + 0.1), "#7a4426", light="flat", alpha=0.9)
    # 赤い包み紙（破れて口が開く）
    wrap = ic.rough(ic.abox(ax, 0.0, 17.6, 11.2, 0.8), 0.15, 0.8, k=1)
    edge = ic.rough(t - 17.0 - 1.2 * np.sin(o * 2.2), 0.6, 0.8, k=2)
    wrap = ic.inter(wrap, edge)
    ic.shadow(wrap, 0.4, 0.6, 0.4)
    crinkle = 1.0 + (ic.noise(1.2, 3, k=3) - 0.5) * 0.45
    ic.fill(wrap, "#c81d27", light="cyl", axis=ax, spec=0.8, shine=30, tex=crinkle)
    stripe = ic.inter(ic.abox(ax, 6.0, 9.0, 12.0, 0.0), wrap)
    ic.fill(stripe, "#f4ecd8", light="cyl", axis=ax, spec=0.4, tex=crinkle)
    ic.fill(ic.inter(ic.abox(ax, 0.0, 1.6, 12.0), wrap + 0.2), "#8e0f16", light="flat")
    ic.stroke(edge, 0.45, "#e9e2d6", alpha=0.8 * (wrap < 0.5))


@painter("painkillers")
def p_painkillers(ic):
    ax = Axis(12.0, 29.0, 12.0, 4.0)
    body = ic.box(12.2, 19.4, 12.6, 16.0, 1.6)
    ic.fill(body, "#d9701a", light="cyl", axis=ax, spec=0.9, shine=36, spec_col="#ffe0b0")
    for px, py in ((9.6, 25.0), (13.4, 24.2), (11.0, 22.0), (14.6, 26.8), (8.8, 27.2)):
        ic.fill(ic.inter(ic.circle(px, py, 1.4), body + 0.8), "#a04a10", light="flat", alpha=0.6)
    label = ic.box(12.2, 18.2, 12.8, 7.6, 0.3)
    ic.fill(label, "#f3f1ea", light="cyl", axis=ax, spec=0.2)
    ic.line([(8.4, 15.6), (15.8, 20.8)], 0.9, "#1a1a1a")
    ic.line([(15.6, 15.4), (8.8, 21.0)], 0.9, "#1a1a1a")
    glass_streak(ic, ax, 3.0, 9.0, -4.2, 0.45, 0.6)
    cap = ic.box(12.2, 9.4, 13.6, 4.8, 1.0)
    ic.shadow(cap, 0.3, 0.5, 0.35)
    ic.fill(cap, "#f4f4f0", light="cyl", axis=ax, spec=0.5, tex=1.0 - 0.12 * (np.sin(ic.X * 2 * math.pi / 1.4) > 0.3))
    for cx, cy, rx, ry, rot in ((23.4, 26.4, 4.0, 2.5, -10), (25.6, 20.6, 3.4, 2.2, 30)):
        pill = ic.ellipse(cx, cy, rx, ry, rot)
        ic.shadow(pill, 0.4, 0.6, 0.45)
        ic.fill(pill, "#f5f3ec", bevel=1.6, profile="soft", spec=0.4)
        lx, ly = ic.local(cx, cy, rot)
        ic.fill(ic.inter(np.abs(lx) - 0.25, pill + 0.6), "#b9b5aa", light="flat", alpha=0.8)


def _injector(ic, liquid, glow, symbol, k=0):
    """注射薬（自動注射器）: 黒いゴムの頭に白い印、色の付いた薬液、銀の口、針。"""
    ax = Axis(4.0, 4.4, 28.0, 28.4)
    barrel = ic.abox(ax, 8.0, 22.4, 7.4, 1.2)
    ic.fill(barrel, "#d6dee4", light="cyl", axis=ax, spec=0.9, shine=40)
    liq = ic.abox(ax, 9.0, 21.6, 5.6, 0.8)
    ic.fill(liq, liquid, light="cyl", axis=ax, spec=0.35, glow=glow, emit=0.3 + glow * 0.3)
    glass_streak(ic, ax, 9.6, 21.0, -2.0, 0.45, 0.75)
    for tt in (12.0, 15.0, 18.0):
        x0, y0 = ax.p(tt, 3.6)
        x1, y1 = ax.p(tt, 2.0)
        ic.line([(x0, y0), (x1, y1)], 0.45, "#1a1c1f")
    ic.fill(ic.abox(ax, 22.2, 24.0, 4.4, 0.6), "#c9ced2", light="cyl", axis=ax, spec=0.9, shine=34)
    nx0, ny0 = ax.p(23.8)
    nx1, ny1 = ax.p(ax.len - 0.4)
    ic.fill(ic.seg(nx0, ny0, nx1, ny1, 0.55, 0.3), "#e4e9ec", light="cyl", axis=ax, spec=1.0, shine=40)
    head = ic.abox(ax, 0.0, 9.0, 11.6, 3.0)
    ic.shadow(head, 0.4, 0.6, 0.45)
    ic.fill(head, "#1d1e21", bevel=1.6, profile="soft", spec=0.35, shine=18, tex=ic.grain(0.08, 0.9, k=k))
    cx, cy = ax.p(4.4)
    symbol(ic, cx, cy)


def _sym_shield(ic, cx, cy):
    d = ic.poly([(cx - 3.0, cy - 3.0), (cx + 3.0, cy - 3.0), (cx + 2.8, cy + 0.6), (cx, cy + 3.4), (cx - 2.8, cy + 0.6)])
    ic.fill(d, "#f4f4f2", bevel=0.6, spec=0.3)
    ic.fill(ic.box(cx, cy - 0.2, 0.9, 4.0), "#1d1e21", light="flat", alpha=0.9)


def _sym_fist(ic, cx, cy):
    d = ic.union(ic.box(cx, cy + 0.8, 5.6, 4.0, 1.2), *[ic.circle(cx - 2.0 + i * 1.35, cy - 1.4, 0.95) for i in range(4)])
    ic.fill(d, "#f4f4f2", bevel=0.6, spec=0.3)
    ic.line([(cx - 2.4, cy + 0.4), (cx + 0.6, cy + 1.2)], 0.5, "#1d1e21")


def _sym_eye(ic, cx, cy):
    d = ic.inter(ic.circle(cx, cy - 2.6, 4.3), ic.circle(cx, cy + 2.6, 4.3))
    ic.fill(d, "#f4f4f2", bevel=0.4, spec=0.3)
    ic.fill(ic.circle(cx, cy, 1.4), "#1d1e21", light="flat")
    ic.fill(ic.circle(cx - 0.4, cy - 0.4, 0.45), "#f4f4f2", light="flat")


@painter("fortify_booster")
def p_fortify(ic):
    _injector(ic, "#9aa3ab", 0.0, _sym_shield, k=1)


@painter("champion_booster")
def p_champion(ic):
    _injector(ic, "#e0242f", 0.15, _sym_fist, k=2)


@painter("hunter_booster")
def p_hunter(ic):
    _injector(ic, "#36f06a", 0.9, _sym_eye, k=3)


# --- 道具 -----------------------------------------------------------------------
@painter("grappling_hook")
def p_grappling(ic):
    ax = Axis(5.0, 21.0, 29.0, 5.0)
    grip = ic.box(8.6, 24.8, 4.6, 9.6, 1.4, 22)
    ic.shadow(grip, 0.4, 0.6, 0.4)
    lx, ly = ic.local(8.6, 24.8, 22)
    grid = 1.0 - 0.16 * ((np.sin(lx * 4.2) > 0.4) | (np.sin(ly * 4.2) > 0.4))
    ic.fill(grip, BLACK_PL, bevel=1.0, tex=grid, spec=0.3)
    ic.fill(ic.box(12.6, 21.4, 1.0, 2.6, 0.4, 20), "#3a3e43", bevel=0.4, spec=0.5)          # 引き金
    body = ic.abox(ax, 0.6, 14.0, 5.8, 1.0)
    ic.shadow(body, 0.5, 0.7, 0.45)
    ic.fill(body, "#3c4146", bevel=1.0, tex=metal_tex(ic, ax.deg, 0.1, k=1), spec=0.6, shine=24)
    for tt, oo in ((2.0, -1.8), (2.0, 1.8), (12.2, -1.8), (12.2, 1.8)):
        ic.fill(ic.circle(*ax.p(tt, oo), 0.55), "#a8aeb3", bevel=0.4, spec=0.8)
    tape = ic.rough(ic.abox(ax, 8.4, 10.6, 6.6, 0.3), 0.2, 0.7, k=2)
    ic.fill(tape, TAPE, bevel=0.6, tex=cloth_tex(ic, ax.deg + 90, 0.1, k=3), spec=0.3)
    # ワイヤーの巻き胴
    sc = ax.p(5.0, -4.2)
    spool = ic.circle(*sc, 4.0)
    ic.shadow(spool, 0.4, 0.6, 0.45)
    r = np.hypot(ic.X - sc[0], ic.Y - sc[1])
    ic.fill(spool, "#b9c0c6", bevel=1.0, spec=0.8, shine=30, tex=1.0 - 0.18 * (np.sin(r * 7.0) > 0.5))
    ic.fill(ic.circle(*sc, 1.3), "#5b6166", bevel=0.6, spec=0.7)
    barrel = ic.abox(ax, 13.6, 19.6, 2.8, 0.5)
    ic.fill(barrel, "#878d92", light="cyl", axis=ax, spec=0.7, shine=28)
    shaft = ic.abox(ax, 19.4, 22.6, 1.5, 0.4)
    ic.fill(shaft, "#c8ced3", light="cyl", axis=ax, spec=0.8)
    tip = ax.p(22.4)
    for side in (-1, 1):
        claw = ic.path([tip, ax.p(25.6, side * 2.6), ax.p(24.2, side * 4.8)], 0.8, 0.4)
        ic.shadow(claw, 0.3, 0.5, 0.4)
        ic.fill(claw, "#d7dde1", bevel=0.6, spec=0.9, shine=30)
    claw = ic.path([tip, ax.p(26.4, 0.0), ax.p(27.6, -0.8)], 0.85, 0.4)
    ic.fill(claw, "#e6ebee", bevel=0.6, spec=0.9, shine=30)
    ic.line([ax.p(16.0, 2.2), ax.p(20.0, 3.2), (17.4, 21.6), (13.0, 26.6)], 0.45, "#c6c9cc", alpha=0.9)


@painter("paraglider")
def p_paraglider(ic):
    # 吊り紐（翼の下から荷物へ）
    for sx, sy, ex, ey in ((5.0, 13.6, 13.6, 23.4), (10.0, 11.8, 14.4, 23.0), (22.0, 11.8, 17.6, 23.0),
                           (27.0, 13.6, 18.4, 23.4), (16.0, 11.2, 16.0, 22.6)):
        ic.line([(sx, sy), (ex, ey)], 0.5, "#d6d2c4", alpha=0.95)
    # 翼（三日月）とセルの継ぎ目・継ぎ当て
    wing = ic.cut(ic.ellipse(16.0, 13.6, 15.0, 10.2), ic.ellipse(16.0, 17.6, 14.0, 11.0))
    wing = ic.inter(wing, ic.Y - 15.6 + 0 * ic.X)
    ang = np.degrees(np.arctan2(ic.Y - 22.0, ic.X - 16.0))
    cell = np.floor((ang + 180.0) / 13.0).astype(int)
    pal = [C("#3a68a8"), C("#c9b48f"), C("#3a68a8"), C("#7e8a94"), C("#3a68a8"), C("#b8432e"), C("#3a68a8"),
           C("#c9b48f"), C("#3a68a8"), C("#7e8a94"), C("#3a68a8"), C("#c9b48f"), C("#3a68a8"), C("#7e8a94")]
    col = np.zeros((ic.n, ic.n, 3), f32)
    for i in range(len(pal)):
        col[cell == i] = pal[i]
    col[cell >= len(pal)] = pal[0]
    ic.fill(wing, col, bevel=2.0, profile="soft", tex=cloth_tex(ic, 0, 0.12, k=1), spec=0.15)
    seams = np.abs(((ang + 180.0) % 13.0) - 6.5) > 6.0
    ic.fill(ic.inter(wing, (~seams) * 1.0 - 0.5 + 0 * ic.X), "#203a60", light="flat", alpha=0.0)
    ic.tint((wing < 0) * seams, "#141e2c", 0.55)
    # 荷物（背負い袋）と黄色いベルト
    pack = ic.box(16.0, 26.4, 10.4, 7.6, 2.0)
    ic.shadow(pack, 0.4, 0.6, 0.4)
    ic.fill(pack, "#4d5240", bevel=1.6, profile="soft", tex=cloth_tex(ic, 0, 0.15, k=2), spec=0.08)
    for x in (13.2, 18.8):
        ic.fill(ic.inter(ic.box(x, 26.4, 1.8, 9.0), pack + 0.3), "#e7bd1e", bevel=0.5, spec=0.2)
        ic.fill(ic.box(x, 25.0, 2.4, 1.6, 0.3), "#c9ced2", bevel=0.4, spec=0.8)
    ic.fill(ic.box(16.0, 22.8, 6.4, 1.6, 0.6), "#5c6150", bevel=0.6)


@painter("uv_flashlight")
def p_uv_flashlight(ic):
    ax = Axis(4.0, 28.0, 27.6, 4.4)
    # 予備の電池（下側）
    batt = ic.abox(ax, 6.2, 13.8, 3.0, 0.8, off=3.6)
    ic.fill(batt, "#e7c21a", light="cyl", axis=Axis(*ax.p(0, 3.6), *ax.p(1, 3.6)), spec=0.6)
    ic.fill(ic.abox(ax, 13.2, 13.9, 3.0, 0.3, off=3.6), "#202226", light="flat")
    tail = ic.abox(ax, 0.0, 2.8, 5.6, 1.0)
    ic.fill(tail, "#4a4f55", light="cyl", axis=ax, spec=0.7)
    ic.fill(ic.circle(*ax.p(0.2), 1.2), "#202226", bevel=0.8)
    body = ic.abox(ax, 2.6, 17.4, 5.0, 0.6)
    o = (ic.X - ax.x0) * ax.nx + (ic.Y - ax.y0) * ax.ny
    t = (ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy
    knurl = 1.0 - 0.16 * ((np.sin((t + o) * 4.5) > 0.3) ^ (np.sin((t - o) * 4.5) > 0.3)) * (t > 3.5) * (t < 9.0)
    ic.fill(body, "#25272c", light="cyl", axis=ax, tex=knurl, spec=0.8, shine=34)
    head = ic.poly([ax.p(17.0, -2.5), ax.p(22.0, -4.3), ax.p(22.0, 4.3), ax.p(17.0, 2.5)])
    ic.fill(head, "#2a2c31", light="cyl", axis=ax, spec=0.8, shine=34)
    bezel = ic.abox(ax, 21.8, 23.4, 9.0, 0.6)
    ic.fill(bezel, "#55595f", light="cyl", axis=ax, spec=0.9, shine=34)
    lens = ic.ellipse(*ax.p(23.6), 1.5, 4.0, ax.deg)
    ic.fill(lens, "#b066ff", light="flat", glow=1.0, glow_col="#a050ff", emit=1.0)
    for oo in (-2.0, 0.0, 2.0):
        ic.fill(ic.circle(*ax.p(23.7, oo), 0.55), "#f4e6ff", light="flat", emit=1.0, glow=0.6)
    # テープ
    for tt in (7.6, 12.0):
        tp = ic.rough(ic.abox(ax, tt, tt + 1.8, 0.0 + 10.0, 0.3, off=1.6), 0.2, 0.6, k=int(tt))
        ic.fill(tp, TAPE, bevel=0.6, tex=cloth_tex(ic, ax.deg + 90, 0.1, k=int(tt) + 1), spec=0.3)


@painter("lockpick")
def p_lockpick(ic):
    # テンションレンチ（L 字）
    wrench = ic.path([(9.6, 27.4), (24.4, 12.6), (26.8, 14.6)], 0.62)
    ic.shadow(wrench, 0.4, 0.6, 0.45)
    ic.fill(wrench, "#9aa1a7", bevel=0.6, spec=0.9, shine=30)
    # ピック（先が鉤）
    pick = ic.path([(6.6, 25.4), (25.2, 6.8), (26.4, 6.6), (27.2, 4.4)], 0.62, 0.45)
    ic.shadow(pick, 0.4, 0.6, 0.45)
    ic.fill(pick, "#c9d0d5", bevel=0.6, spec=0.9, shine=30)
    # 布を巻いた握り
    grip = ic.rough(ic.box(8.8, 25.2, 10.0, 5.2, 1.8, -45), 0.25, 0.7, k=1)
    ic.shadow(grip, 0.4, 0.6, 0.45)
    lx, ly = ic.local(8.8, 25.2, -45)
    wraps = 1.0 - 0.25 * (np.sin((lx + ly * 0.8) * 2.4) > 0.55)
    ic.fill(grip, "#8a7656", bevel=1.6, profile="soft", tex=wraps * cloth_tex(ic, 45, 0.12, k=2), spec=0.05)
    ic.line([(4.4, 30.0), (3.2, 31.2)], 0.5, "#6e5d42")
    ic.line([(5.4, 30.4), (5.0, 31.6)], 0.5, "#6e5d42")


@painter("repair_kit")
def p_repair_kit(ic):
    # 袋からはみ出すもの（後ろ）: テープ、銅線の輪、ボルト
    tape = ic.cut(ic.circle(9.6, 11.0, 5.6), ic.circle(9.6, 11.0, 2.4))
    ic.fill(tape, "#aeb3b8", bevel=1.4, spec=0.45, tex=1.0 + 0.06 * np.sin(np.hypot(ic.X - 9.6, ic.Y - 11.0) * 6))
    ic.fill(ic.cut(ic.circle(9.6, 11.0, 2.4), ic.circle(9.6, 11.0, 1.6)), "#8a6a44", bevel=0.4)
    for r, k in ((4.4, 1), (3.6, 2)):
        ic.fill(ic.cut(ic.circle(22.0, 10.4, r), ic.circle(22.0, 10.4, r - 0.8)), "#c8743a", bevel=0.5, spec=0.8,
                shine=30)
    ax = Axis(15.8, 14.0, 17.4, 4.0)
    ic.fill(ic.abox(ax, 0.0, 7.0, 2.2, 0.4), "#9aa0a6", light="cyl", axis=ax, spec=0.7,
            tex=1.0 + 0.25 * np.sign(np.sin(((ic.X - ax.x0) * ax.ux + (ic.Y - ax.y0) * ax.uy) * 6)))
    hx, hy = ax.p(7.6)
    ic.fill(ic.poly([(hx + 2.6 * math.cos(math.radians(a)), hy + 2.6 * math.sin(math.radians(a)))
                     for a in range(0, 360, 60)]), "#b4babf", bevel=0.9, profile="lin", spec=0.8)
    # 工具袋
    pouch = ic.box(16.0, 21.6, 25.0, 15.4, 3.0)
    ic.shadow(pouch, 0.4, 0.7, 0.5)
    ic.fill(pouch, "#6a6b3c", bevel=2.2, profile="soft", tex=cloth_tex(ic, 0, 0.14, k=3), spec=0.06)
    flap = ic.inter(ic.box(16.0, 18.2, 25.0, 8.6, 3.0), ic.Y - 21.0 + 0 * ic.X)
    ic.fill(flap, "#5c5d32", bevel=1.4, profile="soft", tex=cloth_tex(ic, 0, 0.14, k=4), spec=0.06)
    ic.stroke(ic.box(16.0, 21.6, 22.0, 12.4, 2.0), 0.4, "#a8a878", alpha=0.6 * (np.sin(ic.X * 3 + ic.Y * 3) > 0))
    # 縫い付けたレンチの印
    ic.fill(ic.circle(16.0, 24.6, 3.6), "#2c2d1c", bevel=0.8)
    wr = ic.union(ic.seg(13.9, 26.7, 17.4, 23.2, 0.65), ic.cut(ic.circle(17.9, 22.7, 1.4), ic.box(18.6, 22.0, 1.2, 1.2, 0, 45)))
    ic.fill(wr, "#d8d6c4", light="flat")


@painter("binoculars")
def p_binoculars(ic):
    strap = ic.path([(6.8, 8.6), (3.6, 15.0), (4.2, 23.0), (6.4, 30.0)], 0.6)
    ic.fill(strap, "#3a2c22", bevel=0.4, spec=0.2)
    for cx in (10.6, 21.6):
        barrel = ic.box(cx, 17.4, 9.0, 19.0, 3.4)
        ic.shadow(barrel, 0.4, 0.6, 0.45)
        wear = smooth(0.6, 0.72, ic.noise(1.6, 3, k=int(cx)) + smooth(1.4, 0, -barrel) * 0.25)
        col = mix("#26282c", "#9ea3a8", wear)
        ic.fill(barrel, col, light="cyl", axis=Axis(cx, 30, cx, 5), spec=0.6, shine=24,
                tex=ic.grain(0.08, 0.8, k=int(cx) + 1))
        cup = ic.box(cx, 8.6, 8.2, 3.4, 1.4)
        ic.fill(cup, "#141517", light="cyl", axis=Axis(cx, 30, cx, 5), spec=0.2)
    bridge = ic.box(16.1, 14.0, 5.6, 7.0, 1.4)
    ic.fill(bridge, "#1d1f22", bevel=0.8, spec=0.5)
    ic.fill(ic.box(16.1, 9.8, 3.4, 3.0, 0.6), "#3a3d42", bevel=0.6, spec=0.6,
            tex=1.0 - 0.2 * (np.sin(ic.X * 2 * math.pi / 0.9) > 0.3))
    for cx, cracked in ((10.6, False), (21.6, True)):
        ring = ic.ellipse(cx, 25.8, 3.9, 2.6)
        ic.fill(ring, "#3a3d42", bevel=0.6, spec=0.6)
        lens = ic.ellipse(cx, 25.8, 3.0, 1.9)
        ic.fill(lens, ic.lin(cx - 3, 24, cx + 3, 27.5, "#4060a0", "#141a30"), light="flat")
        ic.fill(ic.ellipse(cx - 1.0, 25.2, 1.1, 0.5, -20), "#c8d8ff", light="flat", alpha=0.85)
        if cracked:
            ic.line([(cx - 2.6, 25.0), (cx - 0.4, 26.0), (cx + 0.8, 24.6), (cx + 2.6, 26.6)], 0.4, "#e8eeff")
            ic.line([(cx - 0.4, 26.0), (cx - 0.2, 27.4)], 0.35, "#e8eeff")


@painter("survivor_terminal")
def p_terminal(ic):
    rot = -8
    bump = ic.box(16.0, 16.4, 28.0, 21.6, 3.2, rot)
    ic.shadow(bump, 0.4, 0.6, 0.4)
    ic.fill(bump, "#2b2e33", bevel=1.6, profile="soft", tex=ic.grain(0.06, 1.0, k=1), spec=0.25)
    lx, ly = ic.local(16.0, 16.4, rot)
    corners = ic.inter(bump, -(ic.inter(np.abs(lx) - 10.6, np.abs(ly) - 7.0)))
    ic.fill(ic.inter(corners, ic.union(np.abs(lx) - 10.6, np.abs(ly) - 7.0) * 0 + ic.inter(np.abs(lx) - 10.0, np.abs(ly) - 6.6)),
            "#c96a1b", bevel=1.0, spec=0.3)
    screen = ic.box(16.0, 16.4, 21.4, 15.0, 0.8, rot)
    ic.fill(screen, "#0b2612", light="flat")
    grid = (np.abs(((lx + 20) % 3.6) - 1.8) < 0.22) | (np.abs(((ly + 20) % 3.6) - 1.8) < 0.22)
    ic.fill(ic.inter(screen + 0.3, (~grid) * 1.0 - 0.5), "#16502a", light="flat", alpha=0.0)
    ic.tint((screen < 0) * grid, "#1f6a32", 1.0, "mix")
    road = ic.path([(7.4, 22.0), (12.0, 19.4), (14.0, 22.6), (20.6, 21.0), (25.0, 23.0)], 0.45)
    ic.fill(ic.inter(road, screen), "#2f8a46", light="flat")
    # 心拍の線
    def R(x, y):
        r = math.radians(rot)
        return (16.0 + x * math.cos(r) - y * math.sin(r), 16.4 + x * math.sin(r) + y * math.cos(r))
    pts = [R(-9.6, 0.0), R(-4.4, 0.0), R(-3.0, -4.0), R(-1.4, 3.6), R(0.2, -1.6), R(1.4, 0.0), R(9.6, 0.0)]
    ic.line(pts, 0.75, "#7dff8c", glow=0.5, glow_col="#60ff70", emit=1.0)
    ic.fill(ic.circle(*R(5.2, -3.6), 0.8), "#e8ff70", light="flat", emit=1.0, glow=0.4)
    # ひび
    o = R(7.6, -5.0)
    for a, ln in ((200, 7.0), (240, 5.0), (160, 4.0), (275, 3.4)):
        e = (o[0] + ln * math.cos(math.radians(a)), o[1] + ln * math.sin(math.radians(a)))
        m = ((o[0] + e[0]) / 2 + 0.6, (o[1] + e[1]) / 2 - 0.4)
        ic.fill(ic.inter(ic.path([o, m, e], 0.28), screen), "#e6f5e8", light="flat", alpha=0.85)
    # 角のテープ
    tape = ic.rough(ic.box(5.0, 26.4, 10.0, 4.4, 0.3, -40), 0.3, 0.7, k=2)
    ic.shadow(tape, 0.3, 0.5, 0.4)
    ic.fill(tape, TAPE, bevel=0.7, tex=cloth_tex(ic, -40, 0.12, k=3), spec=0.35)


# ===========================================================================
#  書き出し
# ===========================================================================
def paint_icon(key: str) -> Image.Image:
    if key not in PAINTERS:
        raise KeyError(f"アイコンの描き方が無い: {key}（gen_nr_items.py に @painter を足す）")
    ic = Icon(key)
    PAINTERS[key](ic)
    return ic.finish()


def _slot_bg(size, kind):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    dr = ImageDraw.Draw(img)
    if kind == "slot":       # 統合版の古い UI のスロット（灰色・内側の段）
        dr.rectangle([0, 0, size - 1, size - 1], fill=(139, 139, 139, 255))
        dr.line([(0, 0), (size - 1, 0)], fill=(55, 55, 55, 255), width=2)
        dr.line([(0, 0), (0, size - 1)], fill=(55, 55, 55, 255), width=2)
        dr.line([(0, size - 1), (size - 1, size - 1)], fill=(255, 255, 255, 255), width=2)
        dr.line([(size - 1, 0), (size - 1, size - 1)], fill=(255, 255, 255, 255), width=2)
    else:
        dr.rectangle([0, 0, size - 1, size - 1], fill=(49, 50, 54, 255))
    return img


def contact_sheet(icons, path):
    """[(key, 32px の画像)] → 4 倍（スロットの灰色・暗い背景）と等倍を並べた確認用の絵。"""
    from nr_preview import contact_sheet as sheet
    cells = []
    for key, im in icons:
        big = im.resize((ICON * 4, ICON * 4), Image.NEAREST)
        w = ICON * 4 * 2 + 12 + 44
        cell = Image.new("RGBA", (w, ICON * 4 + 8), (24, 25, 28, 255))
        for i, kind in enumerate(("slot", "dark")):
            bg = _slot_bg(ICON * 4 + 8, kind)
            bg.alpha_composite(big, (4, 4))
            cell.alpha_composite(bg, (i * (ICON * 4 + 10), 0))
        for j, kind in enumerate(("slot", "dark")):
            bg = _slot_bg(ICON + 4, kind)
            bg.alpha_composite(im, (2, 2))
            cell.alpha_composite(bg, (2 * (ICON * 4 + 10) + 2, 4 + j * (ICON + 10)))
        cells.append((key, cell))
    img = sheet(cells, cols=4, title="NIGHT RUNNER items (32px icons, x4 nearest + 1x)")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return img


def _clear_dir(folder):
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="このキーだけ描く（コンタクトシートの確認用。JSON は書かない）")
    ap.add_argument("--sheet", default=SHEET, help="コンタクトシートの書き出し先")
    a = ap.parse_args(argv)
    S = load_spec()
    items = list(S.all_items())
    keys = [it["key"] for it in items]
    missing = [k for k in keys if k not in PAINTERS]
    if missing:
        print(f"[{PRODUCER}] ERROR: アイコンの描き方が無い: {missing}", file=sys.stderr)
        return 1
    only = [k for k in a.only.split(",") if k]
    if only:
        icons = [(k, paint_icon(k)) for k in only]
        contact_sheet(icons, a.sheet)
        print(f"[{PRODUCER}] sheet {a.sheet} ({len(icons)} icons)")
        return 0
    _clear_dir(ITEM_DIR)
    _clear_dir(RECIPE_DIR)
    os.makedirs(TEX_DIR, exist_ok=True)
    tex_frag, lang = {}, {"ja_JP": {}, "en_US": {}}
    icons = []
    n_recipes = 0
    for it in items:
        key = it["key"]
        write_json(os.path.join(ITEM_DIR, f"{key}.json"), item_json(it, S))
        rec = recipe_json(it)
        if rec:
            write_json(os.path.join(RECIPE_DIR, f"{key}.json"), rec)
            n_recipes += 1
        im = paint_icon(key)
        im.save(os.path.join(TEX_DIR, f"{key}.png"), optimize=True)
        icons.append((key, im))
        tex_frag[f"nr_{key}"] = {"textures": TEX_REF + key}
        for code, field in (("ja_JP", "ja"), ("en_US", "en")):
            lang[code][f"item.{it['id']}"] = it[field]
            lang[code][f"item.{it['id']}.name"] = it[field]
    frag("item_texture", PRODUCER, tex_frag)
    frag("lang", PRODUCER, lang)
    contact_sheet(icons, a.sheet)
    print(f"[{PRODUCER}] items {len(items)} / recipes {n_recipes} / icons {len(icons)} ({ICON}px) / "
          f"sheet {os.path.relpath(a.sheet)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
