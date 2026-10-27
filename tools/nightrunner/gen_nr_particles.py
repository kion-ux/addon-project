# -*- coding: utf-8 -*-
"""NIGHT RUNNER — パーティクル（nr:<名前>）とスプライトアトラスの生成。

    python3 tools/nightrunner/gen_nr_particles.py            # 生成 + 静的検査 + 確認画像
    python3 tools/nightrunner/gen_nr_particles.py --check    # 生成物を書かずに検査だけ（アトラスは描く）

書くもの:
  packs/nightrunner_RP/particles/<名前>.json          （identifier nr:<名前>。nr_registry.PARTICLES の全部 + 補助）
  packs/nightrunner_RP/textures/nr/particle/nr_gore.png （血・肉片・骨・脳・腸・血痕・血だまり）
  packs/nightrunner_RP/textures/nr/particle/nr_fx.png   （煙・炎・火花・放電・輪・線・閃光ほか）
  build_preview/nightrunner/particles_atlas.png         （確認用のコンタクトシート）

約束（DESIGN.md §9・§11・§12、nr_registry の冒頭）:
* スクリプトは MolangVariableMap.setFloat("variable.<名前>", 値)、こちらは `(v.<名前> ?? 既定値)` で読む。
  読む変数は nr_registry.PARTICLES に書かれたもの（size life count … gore）。既定値は「/particle で出しても
  それらしく見える」値。gore はゴアレベル 0..1（数・大きさ・寿命を絞る）。
* 個数はすべて math.clamp で上限を付ける（1 エミッタあたり MAX_PER_EMITTER まで）。
* 血・肉片は固有色で描き、色の変化（乾く・薄れる）は tint で掛ける。煙・火花・輪などは白で描いて tint で色を付ける。
* 平らな血痕・血だまりは facing_camera_mode `emitter_transform_xz`（地面）/ `_yz`（±X の壁）/ `_xy`（±Z の壁）。
  material は particles_blend（DisableCulling なので裏からも見える・縁が柔らかい）。
* 子エフェクト（イベントの particle_effect）は親の変数を読めない（公式: pre_effect_expression は新しい
  エミッタで走り、親の Molang の値は見えない）。子に渡す値は pre_effect_expression で定数として置く。

使った部品・欄はすべて公式の JSON スキーマ（build_preview/nr_research/.../json_schemas/client/particles/1.21.10）
と突き合わせる（check_schema）。スキーマに無い欄は生成を止める。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from typing import Dict, List, Tuple
from urllib.parse import unquote

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import nr_common as C  # noqa: E402
import nr_registry as REG  # noqa: E402

PRODUCER = "gen_nr_particles"
f32 = np.float32
SS = 4                      # スーパーサンプリングの倍率
ATLAS_W = 1024
TEX_REL = "textures/nr/particle"
TEX_DIR = os.path.join(C.RP, *TEX_REL.split("/"))
PART_DIR = os.path.join(C.RP, "particles")
SHEET = os.path.join(C.SCRATCH, "particles_atlas.png")
SCHEMA_DIRS = [
    os.path.join(C.ROOT, "build_preview", "nr_research", "fx_ui", "bs", "metadata", "json_schemas"),
    os.path.join(C.ROOT, "build_preview", "nr_research", "content", "bs_1.21.120.4", "metadata", "json_schemas"),
]
SCHEMA_VER = "1.21.10"
FORMAT_VERSION = "1.10.0"   # バニラの shriek・MS の例と同じ（1.21.120 のエンジンで読める）
MAX_PER_EMITTER = 96        # 1 エミッタが同時に持つ粒の上限（DESIGN §11 の 1 tick 300 の予算の内側）

# 血の色（nr_paint の _BLOOD / BLOOD_KINDS["red"] と同じ系統。0..255）
BLOOD_HI = (168, 22, 22)
BLOOD_MID = (112, 6, 10)
BLOOD_DK = (58, 2, 6)
GLINT = (238, 206, 198)


# ===========================================================================
#  ノイズ・形（numpy。すべて決定的）
# ===========================================================================
def _h32(a):
    a = a.astype(np.uint32)
    a ^= a >> np.uint32(16)
    a *= np.uint32(0x7FEB352D)
    a ^= a >> np.uint32(15)
    a *= np.uint32(0x846CA68B)
    a ^= a >> np.uint32(16)
    return a


def _lat(ix, iy, seed):
    ux = ix.astype(np.int64).astype(np.uint32)
    uy = iy.astype(np.int64).astype(np.uint32)
    h = _h32(ux * np.uint32(0x9E3779B1) ^ _h32(uy + np.uint32(seed & 0xFFFFFFFF)))
    return h.astype(np.float64) / 4294967296.0


def vnoise(x, y, seed):
    """2D 値ノイズ 0..1。"""
    xf = np.floor(x)
    yf = np.floor(y)
    tx = x - xf
    ty = y - yf
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    a = _lat(xf, yf, seed)
    b = _lat(xf + 1, yf, seed)
    c = _lat(xf, yf + 1, seed)
    d = _lat(xf + 1, yf + 1, seed)
    return ((a + (b - a) * tx) * (1 - ty) + (c + (d - c) * tx) * ty).astype(f32)


def fbm(x, y, seed, octaves=4, gain=0.5):
    acc = np.zeros(np.shape(x), f32)
    amp, norm = 1.0, 0.0
    for i in range(octaves):
        acc += (vnoise(x, y, seed + 977 * i) - 0.5) * amp
        norm += amp
        amp *= gain
        x = x * 2.03 + 13.7
        y = y * 2.03 + 7.1
    return 0.5 + acc / norm * 1.6


def coords(w, h):
    """出力の画素単位の座標（中心が 0、y は下向き）を SS 倍の細かさで。"""
    ys, xs = np.mgrid[0:h * SS, 0:w * SS].astype(f32)
    return (xs + 0.5) / SS - w / 2.0, (ys + 0.5) / SS - h / 2.0


def harm(ang, rng, kmin=2, kmax=9, amp=0.12, decay=1.0):
    """角度の関数（不規則な輪郭の半径のゆらぎ）。"""
    out = np.zeros_like(ang)
    for k in range(kmin, kmax + 1):
        a = amp * rng.uniform(0.25, 1.0) * (kmin / k) ** decay
        out += a * np.cos(k * ang + rng.uniform(0, 2 * math.pi))
    return out


def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_capsule(X, Y, x0, y0, x1, y1, r0, r1):
    dx, dy = x1 - x0, y1 - y0
    ll = dx * dx + dy * dy + 1e-9
    t = np.clip(((X - x0) * dx + (Y - y0) * dy) / ll, 0.0, 1.0)
    qx, qy = x0 + t * dx, y0 + t * dy
    return np.hypot(X - qx, Y - qy) - (r0 + (r1 - r0) * t)


def sd_poly(X, Y, pts):
    """凸でなくてもよい多角形の符号付き距離（内側が負）。"""
    d = np.full(X.shape, 1e9, f32)
    s = np.ones(X.shape, f32)
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        wx, wy = X - x0, Y - y0
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey + 1e-9), 0, 1)
        bx, by = wx - ex * t, wy - ey * t
        d = np.minimum(d, bx * bx + by * by)
        c1 = Y >= y0
        c2 = Y < y1
        c3 = ex * wy > ey * wx
        flip = (c1 & c2 & c3) | (~c1 & ~c2 & ~c3)
        s = np.where(flip, -s, s)
    return s * np.sqrt(d)


def cover(d):
    """符号付き距離（出力の画素単位）→ 被覆率。縮小で滑らかな縁になる。"""
    return np.clip(0.5 - d * SS, 0.0, 1.0).astype(f32)


def lerp(a, b, t):
    a = np.asarray(a, f32)
    b = np.asarray(b, f32)
    t = np.asarray(t, f32)
    if t.ndim >= 1 and (a.ndim == 1 or b.ndim == 1 or t.ndim == max(a.ndim, b.ndim) - 1):
        t = t[..., None]     # 色（…,3）を場（…）で混ぜる
    return a + (b - a) * t


_L = np.array([-0.45, -0.62, 0.64], f32)
_L /= np.linalg.norm(_L)
_H = _L + np.array([0, 0, 1], f32)
_H /= np.linalg.norm(_H)


def normals(hgt, bump=1.0):
    gy, gx = np.gradient(hgt.astype(f32))
    nx, ny = -gx * SS * bump, -gy * SS * bump
    inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1.0)
    return nx * inv, ny * inv, inv


def shade(n, base, amb=0.55, spec=0.8, shin=48.0, glint=GLINT):
    nx, ny, nz = n
    diff = np.clip(nx * _L[0] + ny * _L[1] + nz * _L[2], 0, 1)
    sp = np.clip(nx * _H[0] + ny * _H[1] + nz * _H[2], 0, 1) ** shin
    return base * (amb + (1 - amb) * diff)[..., None] + (spec * sp)[..., None] * np.asarray(glint, f32)


def liquid(d, prof=3.0, thin=(150, 14, 18), thick=(62, 3, 7), a_thin=0.82, a_thick=0.97,
           gloss=1.0, ring=0.22, shin=46.0, bump=1.0, dome=False):
    """液体の膜の陰影。d は符号付き距離（画素）。縁は薄く明るく、内側は厚く暗い。縁のメニスカスに艶。"""
    inside = np.maximum(-d, 0.0)
    th = 1.0 - np.exp(-inside / prof)
    if dome:
        th = np.sqrt(np.clip(inside / prof, 0, 1))
    hgt = th * prof * 0.9
    n = normals(hgt, bump)
    base = lerp(thin, thick, th ** 0.7)
    band = np.exp(-((inside - prof * 0.55) / (prof * 0.38)) ** 2)
    base = base * (1.0 - ring * band)[..., None]
    col = shade(n, base, amb=0.62, spec=0.95 * gloss, shin=shin)
    a = cover(d) * (a_thin + (a_thick - a_thin) * th)
    return col / 255.0, a


def finish(col, a):
    """SS の (色 0..1, α) → 出力の RGBA uint8（前乗算で縮小して縁を汚さない）。"""
    col = np.clip(col, 0, 1).astype(f32)
    a = np.clip(a, 0, 1).astype(f32)
    H, W = a.shape[0] // SS, a.shape[1] // SS
    pm = (col * a[..., None]).reshape(H, SS, W, SS, 3).mean(axis=(1, 3))
    aa = a.reshape(H, SS, W, SS).mean(axis=(1, 3))
    rgb = np.where(aa[..., None] > 1e-4, pm / np.maximum(aa[..., None], 1e-4), 0.0)
    out = np.dstack([np.clip(rgb, 0, 1), aa])
    out = (out * 255.0 + 0.5).astype(np.uint8)
    out[out[..., 3] == 0] = 0
    return out


def rng_for(*parts):
    return np.random.default_rng(C.stable_hash(":".join(str(p) for p in parts)))


# ===========================================================================
#  血のスプライト
# ===========================================================================
def splat_sdf(X, Y, rng, R0, fingers=6, sats=10, elong=1.0, ang=0.0, rough=0.9, seed=0, lim=60.0):
    """飛び散った血の形（中心の塊 + 指 + 衛星の滴）。lim は中心からの最大距離（画素）。"""
    ca, sa = math.cos(ang), math.sin(ang)
    U = X * ca + Y * sa
    V = -X * sa + Y * ca
    Ue = U / elong
    rho = np.hypot(Ue, V)
    th = np.arctan2(V, Ue)
    d = (rho - R0 * (1.0 + harm(th, rng, 2, 10, 0.16))) * min(1.0, elong)
    for _ in range(fingers):
        a = rng.uniform(-math.pi, math.pi)
        if elong > 1.0:
            a = rng.normal(0.0, 0.55) + (math.pi if rng.random() < 0.15 else 0.0)
        L = R0 * rng.uniform(1.2, 1.95) * (elong if abs(math.cos(a)) > 0.7 else 1.0)
        L = min(L, lim - 4)
        w0 = R0 * rng.uniform(0.12, 0.22)
        w1 = w0 * rng.uniform(0.3, 0.55)
        ex, ey = math.cos(a) * L, math.sin(a) * L
        x0, y0 = math.cos(a) * R0 * 0.4, math.sin(a) * R0 * 0.4
        cap = sd_capsule(U, V, x0, y0, ex, ey, w0, w1)
        bulb = sd_circle(U, V, ex + math.cos(a) * w1, ey + math.sin(a) * w1, w1 * rng.uniform(1.4, 2.1))
        d = smin(d, smin(cap, bulb, w1 * 0.8), R0 * 0.18)
    for _ in range(sats):
        a = rng.uniform(-math.pi, math.pi)
        if elong > 1.0 and rng.random() < 0.7:
            a = rng.normal(0.0, 0.45)
        dist = R0 * rng.uniform(1.25, 2.4) * (elong ** 0.6 if abs(math.cos(a)) > 0.6 else 1.0)
        r = R0 * rng.uniform(0.035, 0.13) * (2.6 - dist / R0) / 1.4
        r = max(r, 0.7)
        dist = min(dist, lim - r * 3 - 2)
        cx, cy = math.cos(a) * dist, math.sin(a) * dist
        if rng.random() < 0.45:   # 外向きに伸びた滴（勢いの向き）
            tail = r * rng.uniform(1.5, 3.2)
            sat = sd_capsule(U, V, cx - math.cos(a) * tail, cy - math.sin(a) * tail, cx, cy, r * 0.35, r)
        else:
            sat = sd_circle(U, V, cx, cy, r)
        d = np.minimum(d, sat)
    d = d + (fbm(X * 0.22, Y * 0.22, seed, 4) - 0.5) * rough * 2.0
    return d


def paint_splat(w, h, idx, kind):
    """地面の血痕（idx で形を変える）。kind: round / dir / cluster。"""
    rng = rng_for("splat", kind, idx)
    X, Y = coords(w, h)
    lim = w / 2.0 - 3
    if kind == "round":
        d = splat_sdf(X, Y, rng, w * rng.uniform(0.17, 0.22), int(rng.integers(5, 9)),
                      int(rng.integers(8, 16)), 1.0, 0.0, 1.0, idx * 7 + 1, lim)
    elif kind == "dir":
        d = splat_sdf(X + w * 0.12, Y, rng, w * rng.uniform(0.13, 0.17), int(rng.integers(4, 8)),
                      int(rng.integers(12, 20)), rng.uniform(1.5, 2.1), rng.uniform(-0.2, 0.2), 1.0,
                      idx * 7 + 2, lim)
    else:   # 小さな塊の集まり（散弾・噴霧が当たった跡）
        d = np.full(X.shape, 1e9, f32)
        for k in range(int(rng.integers(5, 9))):
            a = rng.uniform(-math.pi, math.pi)
            r = rng.uniform(0, w * 0.26)
            R0 = w * rng.uniform(0.045, 0.1)
            cx, cy = math.cos(a) * r, math.sin(a) * r
            sub = splat_sdf(X - cx, Y - cy, rng, R0, int(rng.integers(2, 5)), int(rng.integers(3, 7)),
                            1.0, 0.0, 0.6, idx * 31 + k, lim - math.hypot(cx, cy))
            d = smin(d, sub, 1.5)
    col, a = liquid(d, prof=w * 0.035, ring=0.28)
    # 薄い所にわずかな色むら（乾き始め）
    m = fbm(X * 0.06, Y * 0.06, 900 + idx, 3)
    col = col * (0.88 + 0.24 * m)[..., None]
    return finish(col, a)


def paint_wall(w, h, var, frame, frames=4):
    """壁の血痕。上に飛沫、下へ垂れる筋（frame が進むほど長い）。画像の上 = 世界の上。"""
    rng = rng_for("wall", var)
    X, Y = coords(w, h)
    cy = -h * 0.2
    R0 = w * rng.uniform(0.13, 0.16)
    d = splat_sdf(X, Y - cy, rng, R0, int(rng.integers(5, 8)), int(rng.integers(10, 16)),
                  1.0, 0.0, 0.9, 400 + var, h * 0.36)
    prog = [0.22, 0.5, 0.78, 1.0][frame] if frames == 4 else (frame + 1) / frames
    drng = rng_for("wall_drips", var)
    nd = int(drng.integers(4, 7))
    for _j in range(nd):
        x = drng.uniform(-R0 * 1.15, R0 * 1.15)
        y0 = cy + math.sqrt(max(R0 * R0 * 1.1 - x * x, 0.0)) * 0.8
        Lmax = h / 2.0 - 6 - y0
        L = Lmax * drng.uniform(0.35, 1.0)
        spd = drng.uniform(0.7, 1.15)
        p = min(1.0, prog * spd)
        wd = drng.uniform(1.5, 3.1)
        y1 = y0 + L * p
        wig = drng.uniform(-2.0, 2.0)
        xm = x + wig * 0.5
        seg1 = sd_capsule(X, Y, x, y0 - 2, xm, (y0 + y1) / 2, wd * 1.25, wd)
        seg2 = sd_capsule(X, Y, xm, (y0 + y1) / 2, x + wig, y1, wd, wd * 0.85)
        bulb = sd_circle(X, Y, x + wig, y1 + wd * 0.4, wd * drng.uniform(1.35, 1.7))
        dd = smin(smin(seg1, seg2, 1.0), bulb, 1.4)
        d = smin(d, dd, 2.0)
    d = d + (fbm(X * 0.25, Y * 0.25, 700 + var, 3) - 0.5) * 1.2
    col, a = liquid(d, prof=w * 0.03, ring=0.25)
    return finish(col, a)


def paint_pool(w, h, idx):
    """血だまり。中心が黒っぽく、縁に艶。"""
    rng = rng_for("pool", idx)
    X, Y = coords(w, h)
    R0 = w * 0.34
    rho = np.hypot(X, Y * rng.uniform(1.0, 1.2))
    th = np.arctan2(Y, X)
    d = rho - R0 * (1.0 + harm(th, rng, 2, 6, 0.1, 1.2))
    for _ in range(int(rng.integers(3, 6))):
        a = rng.uniform(-math.pi, math.pi)
        r = R0 * rng.uniform(0.25, 0.45)
        dist = R0 * rng.uniform(0.7, 0.95)
        d = smin(d, sd_circle(X, Y, math.cos(a) * dist, math.sin(a) * dist, r), R0 * 0.2)
    for _ in range(int(rng.integers(3, 7))):
        a = rng.uniform(-math.pi, math.pi)
        dist = R0 * rng.uniform(1.15, 1.35)
        d = np.minimum(d, sd_circle(X, Y, math.cos(a) * dist, math.sin(a) * dist, rng.uniform(1.0, 3.0)))
    d = d + (fbm(X * 0.08, Y * 0.08, 50 + idx, 3) - 0.5) * 3.0
    col, a = liquid(d, prof=w * 0.032, thin=(128, 10, 14), thick=(30, 1, 4), a_thin=0.86, a_thick=0.99,
                    gloss=1.35, ring=0.1, shin=95.0, bump=0.75)
    # 厚い所の濃い赤のむら（固まりかけ）
    clot = fbm(X * 0.11, Y * 0.11, 90 + idx, 3)
    col = col * (1.0 + 0.35 * np.clip(clot - 0.55, 0, 1))[..., None]
    # 空の映り込み（奥が少し明るい）と、濃い中心のむら
    refl = np.clip(0.5 - Y / h, 0, 1) * np.clip(-d / (w * 0.08), 0, 1)
    col = col + (refl * 0.05)[..., None] * np.array([0.9, 0.85, 0.95], f32)
    m = fbm(X * 0.05, Y * 0.05, 80 + idx, 3)
    col = col * (0.9 + 0.2 * m)[..., None]
    return finish(col, a)


def paint_drop(w, h, idx):
    """艶のある丸い血の滴（いくつかは二つ・三つがくっついた形）。"""
    rng = rng_for("drop", idx)
    X, Y = coords(w, h)
    R = min(w, h) * rng.uniform(0.24, 0.33)
    th = np.arctan2(Y, X)
    d = np.hypot(X, Y) - R * (1 + harm(th, rng, 2, 5, 0.05))
    if idx % 4 == 2:
        a = rng.uniform(-math.pi, math.pi)
        d = smin(d, sd_circle(X, Y, math.cos(a) * R * 1.05, math.sin(a) * R * 1.05, R * 0.55), R * 0.35)
    if idx % 4 == 3:
        for _ in range(2):
            a = rng.uniform(-math.pi, math.pi)
            d = np.minimum(d, sd_circle(X, Y, math.cos(a) * R * 1.45, math.sin(a) * R * 1.45, R * 0.28))
    col, a = liquid(d, prof=R * 0.9, thin=(170, 20, 22), thick=(70, 3, 8), a_thin=0.9, a_thick=1.0,
                    gloss=1.2, ring=0.0, shin=60.0, dome=True)
    return finish(col, a)


def paint_streak(w, h, idx):
    """速さの向きに伸びた滴（横長。lookat_direction で u が進む向き）。"""
    rng = rng_for("streak", idx)
    X, Y = coords(w, h)
    r = h * rng.uniform(0.26, 0.34)
    L = w * rng.uniform(0.3, 0.4)
    d = sd_capsule(X, Y, -L, 0, L * 0.6, 0, r * 0.35, r)
    d = smin(d, sd_circle(X, Y, L * 0.65, 0, r * 1.05), r * 0.5)
    col, a = liquid(d, prof=r * 0.9, thin=(175, 22, 24), thick=(75, 4, 8), a_thin=0.85, a_thick=1.0,
                    gloss=1.2, ring=0.0, shin=55.0, dome=True)
    return finish(col, a)


def paint_jet(w, h, idx):
    """噴き出す血の太い筋（噴水・噴射の芯）。うねる液柱 + 千切れかけの滴。"""
    rng = rng_for("jet", idx)
    X, Y = coords(w, h)
    t = (X + w / 2) / w
    yc = (np.sin(t * rng.uniform(5, 9) + rng.uniform(0, 6)) * h * 0.06).astype(f32)
    r = h * (0.16 + 0.1 * np.sin(t * rng.uniform(8, 14) + rng.uniform(0, 6))) * np.clip(1.2 - t * 0.5, 0, 1)
    d = np.abs(Y - yc) - r
    d = np.maximum(d, np.abs(X) - w * 0.42)
    for _ in range(3):
        cx = rng.uniform(w * 0.1, w * 0.45)
        d = np.minimum(d, sd_circle(X, Y, cx, rng.uniform(-h * 0.2, h * 0.2), h * rng.uniform(0.07, 0.13)))
    d = d + (fbm(X * 0.3, Y * 0.3, 60 + idx, 3) - 0.5) * 1.2
    col, a = liquid(d, prof=h * 0.18, thin=(185, 26, 26), thick=(95, 6, 10), a_thin=0.85, a_thick=0.98,
                    gloss=1.1, ring=0.0, shin=40.0, dome=True)
    return finish(col, a)


def paint_mist(w, h, idx):
    """血の霧（柔らかいかたまり）。"""
    X, Y = coords(w, h)
    sd = 300 + idx * 13
    wx = fbm(X * 0.06, Y * 0.06, sd + 1, 3) - 0.5
    wy = fbm(X * 0.06, Y * 0.06, sd + 2, 3) - 0.5
    n = fbm((X + wx * 14) * 0.09, (Y + wy * 14) * 0.09, sd, 5)
    r = np.hypot(X, Y) / (w * 0.46)
    fall = np.clip(1 - r * r, 0, 1) ** 1.6
    a = np.clip((n - 0.32) * 1.9, 0, 1) * fall * 0.85
    col = lerp((120, 8, 12), (196, 40, 40), np.clip(n * 1.2 - 0.2, 0, 1)) / 255.0
    return finish(col, a)


def paint_dot(w, h, idx):
    """小さな血の点（血の跡・足元）。"""
    rng = rng_for("dot", idx)
    X, Y = coords(w, h)
    R = w * rng.uniform(0.16, 0.26)
    d = splat_sdf(X, Y, rng, R, int(rng.integers(0, 3)), int(rng.integers(1, 4)), 1.0, 0.0, 0.4,
                  1200 + idx, w / 2 - 1.5)
    col, a = liquid(d, prof=R * 0.5, ring=0.15, gloss=1.1)
    return finish(col, a)


def paint_footprint(w, h, idx):
    """血を踏んだ靴の跡（上がつま先）。idx 1 は左右反転。"""
    X, Y = coords(w, h)
    Xs = -X if idx % 2 else X
    fore = (np.hypot((Xs - 1.5) / (w * 0.17), (Y + h * 0.15) / (h * 0.24)) - 1) * w * 0.17
    heel = (np.hypot((Xs + 0.5) / (w * 0.14), (Y - h * 0.27) / (h * 0.13)) - 1) * w * 0.14
    arch = sd_capsule(Xs, Y, 1.0, -h * 0.05, 0.0, h * 0.2, w * 0.1, w * 0.1)
    d = smin(np.minimum(fore, heel), arch, 2.0)
    chev = np.sin(np.abs(Xs) * 0.9 + Y * 1.35) > 0.3          # 前: 山形の溝（血が付かない）
    bars = np.sin(Y * 1.6) > 0.45                                # かかと: 横の溝
    tread = np.where(Y > h * 0.12, bars, chev)
    patch = fbm(X * 0.12, Y * 0.12, 1300 + idx, 4)
    keep = (~tread) & (patch > 0.38)
    d = np.where(keep, d, np.maximum(d, 0.6))
    edge = np.abs(d) < 1.0
    d = np.where(edge & (patch > 0.3), d - 0.6, d)
    col, a = liquid(d, prof=1.6, thin=(140, 14, 18), thick=(80, 5, 9), a_thin=0.75, a_thick=0.9, ring=0.0,
                    gloss=0.6)
    return finish(col, a * 0.92)


# ===========================================================================
#  肉片・骨・脳・腸
# ===========================================================================
def _lump(X, Y, rng, R, amp=0.2, seed=0, rough=1.0):
    th = np.arctan2(Y, X)
    d = np.hypot(X, Y * rng.uniform(1.0, 1.4)) - R * (1 + harm(th, rng, 2, 7, amp))
    return d + (fbm(X * 0.4, Y * 0.4, seed, 3) - 0.5) * rough * 2.2


def paint_chunk(w, h, idx, pale=False):
    """肉片（赤い筋肉・脂肪・皮付き）。pale は薄い色の組織（緑などに染める用）。"""
    rng = rng_for("chunk", idx, pale)
    X, Y = coords(w, h)
    R = min(w, h) * rng.uniform(0.27, 0.36)
    d = _lump(X, Y, rng, R, 0.22, 2000 + idx)
    inside = np.maximum(-d, 0)
    bumps = fbm(X * 0.35, Y * 0.35, 2100 + idx, 4)
    hgt = np.sqrt(np.clip(inside / (R * 0.8), 0, 1)) * R * 0.5 + bumps * 2.2
    n = normals(hgt, 0.9)
    ang = rng.uniform(0, math.pi)
    stri = np.sin((X * math.cos(ang) + Y * math.sin(ang)) * 1.6 + bumps * 6.0)
    if pale:
        base = lerp((150, 140, 128), (225, 215, 200), bumps)
        base = base * (0.9 + 0.08 * stri)[..., None]
    else:
        base = lerp((92, 14, 18), (176, 42, 44), np.clip(bumps * 1.2 - 0.1, 0, 1))
        base = base * (0.86 + 0.12 * stri)[..., None]
        if idx % 3 == 1:   # 脂肪
            _f1, _f2, cid, _vx, _vy = _worley(X * 0.18, Y * 0.18, 2200 + idx)
            fat = (_f1 < 0.33) & (cid > 0.55)
            base = np.where(fat[..., None], lerp((200, 170, 130), (232, 208, 170), bumps), base)
        if idx % 4 == 3:   # 皮が付いている（灰緑の皮・破れた縁）
            cut = (X * math.cos(ang + 1.2) + Y * math.sin(ang + 1.2)) + (fbm(X * 0.3, Y * 0.3, 2300 + idx, 3) - 0.5) * 6
            skin = cut > R * 0.15
            sk = lerp((88, 100, 80), (128, 138, 108), fbm(X * 0.5, Y * 0.5, 2400 + idx, 3))
            base = np.where(skin[..., None], sk, base)
            rim = np.abs(cut - R * 0.15) < 1.2
            base = np.where(rim[..., None], np.asarray((70, 8, 10), f32), base)
    # 血の被膜（縁が濃い赤）
    edge = np.exp(-inside / 2.2)
    if not pale:
        base = lerp(base, (70, 4, 8), edge * 0.6)
    col = shade(n, base, amb=0.5, spec=0.65, shin=36.0)
    return finish(col / 255.0, cover(d))


def _worley(x, y, seed):
    xf = np.floor(x)
    yf = np.floor(y)
    F1 = np.full(x.shape, 9.0, f32)
    F2 = np.full(x.shape, 9.0, f32)
    cid = np.zeros(x.shape, f32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            cx, cy = xf + ox, yf + oy
            px = cx + 0.15 + 0.7 * _lat(cx, cy, seed)
            py = cy + 0.15 + 0.7 * _lat(cx, cy, seed + 1)
            dd = np.hypot(px - x, py - y).astype(f32)
            c = _lat(cx, cy, seed + 2).astype(f32)
            closer = dd < F1
            F2 = np.where(closer, F1, np.minimum(F2, dd))
            cid = np.where(closer, c, cid)
            F1 = np.where(closer, dd, F1)
    return F1, F2, cid, None, None


def paint_bone(w, h, idx):
    """骨片（とがった破片・肋骨のかけら・歯）。折れた端に骨髄。"""
    rng = rng_for("bone", idx)
    X, Y = coords(w, h)
    ang = rng.uniform(0, math.pi)
    ca, sa = math.cos(ang), math.sin(ang)
    U = X * ca + Y * sa
    V = -X * sa + Y * ca
    L = min(w, h) * 0.4
    kind = idx % 3
    if kind == 0:       # とがった破片（多角形）
        pts = [(-L, rng.uniform(-2, 0)), (-L * 0.4, -rng.uniform(2.5, 4)), (L * 0.3, -rng.uniform(2, 3.5)),
               (L, rng.uniform(-1, 1)), (L * 0.2, rng.uniform(2.5, 4)), (-L * 0.5, rng.uniform(2, 3.5))]
        d = sd_poly(U, V, pts)
    elif kind == 1:     # 肋骨（曲がった棒）
        cur = rng.uniform(0.012, 0.03)
        Vb = V + cur * U * U - 2
        d = np.maximum(np.abs(Vb) - 2.6, np.abs(U) - L)
    else:               # 歯・小片
        d = sd_capsule(U, V, -L * 0.45, 0, L * 0.35, 0, 3.6, 2.4)
        d = smin(d, sd_circle(U, V, L * 0.4, 0, 3.0), 1.5)
    jag = (fbm(U * 0.9, V * 0.9, 2500 + idx, 2) - 0.5) * 1.6
    d = d + jag * (U > L * 0.5)
    inside = np.maximum(-d, 0)
    hgt = np.sqrt(np.clip(inside / 3.0, 0, 1)) * 2.5
    n = normals(hgt, 1.0)
    base = lerp((196, 184, 156), (236, 228, 206), fbm(U * 0.4, V * 0.4, 2600 + idx, 3))
    end = np.clip((U - L * 0.55) / (L * 0.3), 0, 1)
    pores = fbm(U * 1.2, V * 1.2, 2700 + idx, 2)
    marrow = lerp((150, 60, 50), (96, 22, 20), pores)
    base = lerp(base, marrow, end * 0.85)
    crack = np.abs(fbm(U * 0.25, V * 0.6, 2800 + idx, 3) - 0.5) < 0.02
    base = np.where(crack[..., None], base * 0.7, base)
    smear = fbm(X * 0.2, Y * 0.2, 2900 + idx, 3) > 0.62
    base = np.where(smear[..., None], lerp(base, (120, 10, 14), 0.75), base)
    col = shade(n, base, amb=0.55, spec=0.35, shin=20.0)
    return finish(col / 255.0, cover(d))


def paint_brain(w, h, idx):
    """脳の欠片（桃灰色、しわ、濡れた艶、血）。"""
    rng = rng_for("brain", idx)
    X, Y = coords(w, h)
    R = min(w, h) * rng.uniform(0.27, 0.35)
    d = _lump(X, Y, rng, R, 0.16, 3000 + idx, 0.8)
    wx = fbm(X * 0.12, Y * 0.12, 3150 + idx, 2) - 0.5
    ridge = np.abs(fbm((X + wx * 8) * 0.2, (Y - wx * 8) * 0.2, 3100 + idx, 3) - 0.5)
    sulci = np.exp(-(ridge / 0.045) ** 2)          # しわの溝（曲がりくねった線）
    gyri = 1.0 - sulci
    inside = np.maximum(-d, 0)
    hgt = np.sqrt(np.clip(inside / (R * 0.7), 0, 1)) * R * 0.4 + gyri * 1.6
    n = normals(hgt, 1.0)
    base = lerp((150, 98, 104), (218, 172, 172), gyri)
    base = lerp(base, (110, 16, 20), np.exp(-inside / 2.0) * 0.7)
    blood = fbm(X * 0.2, Y * 0.2, 3200 + idx, 3) > 0.64
    base = np.where(blood[..., None], lerp(base, (130, 14, 18), 0.7), base)
    col = shade(n, base, amb=0.55, spec=0.8, shin=42.0)
    return finish(col / 255.0, cover(d))


def paint_gut(w, h, idx):
    """腸の切れ端（横長の管。節のくびれ、上面の艶、千切れた赤い端）。"""
    rng = rng_for("gut", idx)
    X, Y = coords(w, h)
    t = (X + w / 2) / w
    amp = h * rng.uniform(0.12, 0.22)
    yc = amp * np.sin(t * rng.uniform(4, 7) + rng.uniform(0, 6))
    r = h * rng.uniform(0.15, 0.2) * (1 + 0.15 * np.cos(X * 0.9))
    d = np.abs(Y - yc) - r
    d = np.maximum(d, np.abs(X) - w * 0.44 + (fbm(Y * 0.5, X * 0.1, 3300 + idx, 2) - 0.5) * 4)
    inside = np.maximum(-d, 0)
    hgt = np.sqrt(np.clip(inside / r, 0, 1)) * r
    n = normals(hgt, 1.0)
    rings = 0.5 + 0.5 * np.cos(X * 0.9)
    base = lerp((150, 76, 74), (210, 132, 124), rings * 0.6 + 0.4 * fbm(X * 0.3, Y * 0.3, 3400 + idx, 3))
    ends = np.clip((np.abs(X) - w * 0.36) / (w * 0.08), 0, 1)
    base = lerp(base, (110, 12, 16), ends)
    col = shade(n, base, amb=0.5, spec=0.9, shin=50.0)
    return finish(col / 255.0, cover(d))


# ===========================================================================
#  煙・炎・光・線（白で描いて tint で色を付けるもの／固有色のもの）
# ===========================================================================
def paint_smoke(w, h, idx):
    X, Y = coords(w, h)
    sd = 5000 + idx * 17
    wx = fbm(X * 0.05, Y * 0.05, sd + 1, 3) - 0.5
    wy = fbm(X * 0.05, Y * 0.05, sd + 2, 3) - 0.5
    n = fbm((X + wx * 18) * 0.07, (Y + wy * 18) * 0.07, sd, 5)
    r = np.hypot(X, Y) / (w * 0.47)
    fall = np.clip(1 - r * r, 0, 1) ** 1.3
    a = np.clip((n - 0.25) * 1.7, 0, 1) * fall
    lit = np.clip(0.75 - (X + Y) / (w * 1.2) + (n - 0.5) * 0.8, 0.35, 1.0)
    col = np.dstack([lit, lit, lit]) * 0.96
    return finish(col, a * 0.92)


def _fire_ramp(t):
    stops = [(0.0, (0.25, 0.02, 0.0)), (0.3, (0.75, 0.12, 0.02)), (0.55, (1.0, 0.45, 0.05)),
             (0.8, (1.0, 0.8, 0.3)), (1.0, (1.0, 0.98, 0.85))]
    t = np.clip(t, 0, 1)
    out = np.zeros(t.shape + (3,), f32)
    for (t0, c0), (t1, c1) in zip(stops[:-1], stops[1:]):
        m = (t >= t0) & (t <= t1)
        k = ((t - t0) / (t1 - t0))[..., None]
        out = np.where(m[..., None], np.asarray(c0, f32) + (np.asarray(c1, f32) - np.asarray(c0, f32)) * k, out)
    return out


def paint_flame(w, h, frame, frames, var):
    """炎のコマ（下が丸く太く、上へ細く尖る。コマが進むと上からちぎれて消える）。固有色（加算向き）。"""
    X, Y = coords(w, h)
    p = frame / max(1, frames - 1)
    yr = (Y + h * 0.46) / (h * 0.92)
    yn = np.clip(yr, 0, 1)                                   # 0 = 上（先端）、1 = 下（根元）
    grow = 0.6 + 0.4 * math.sin(min(1.0, p * 1.6) * math.pi / 2)
    sd = 6000 + var * 101
    n = fbm(X * 0.1, (Y + p * 40) * 0.085, sd, 5)
    n2 = fbm(X * 0.2, (Y + p * 70) * 0.17, sd + 7, 3)
    prof = yn ** 1.2 * np.sqrt(np.clip((1.0 - yn) / 0.22, 0, 1))
    width = w * 0.33 * grow * prof
    xw = X + (n - 0.5) * w * 0.32 * (1 - yn) ** 1.2
    shape = 1 - (np.abs(xw) / np.maximum(width, 0.4)) ** 1.5
    inten = np.clip(shape * 1.5, 0, 1) ** 0.8 * (0.6 + 0.6 * n2) * (0.5 + 0.5 * yn)
    inten = inten * np.clip(1 - (1 - yn) * p * 1.3 * (1.3 - n), 0, 1) * (1 - p * 0.35)
    inten = np.clip(inten, 0, 1) * ((yr >= 0) & (yr <= 1))
    col = _fire_ramp(inten * 1.1)
    a = np.clip(inten * 1.6, 0, 1)
    return finish(col, a)


def paint_fireball(w, h, frame, frames, var):
    """爆発の火の玉（固有色・particles_blend）。後半は黒煙に変わり、ところどころ火が残る。"""
    X, Y = coords(w, h)
    p = frame / max(1, frames - 1)
    sd = 7000 + var * 37
    wx = fbm(X * 0.04, Y * 0.04, sd + 1, 3) - 0.5
    wy = fbm(X * 0.04, Y * 0.04, sd + 2, 3) - 0.5
    n = fbm((X + wx * 30) * 0.05 + p * 0.7, (Y + wy * 30) * 0.05 - p * 0.5, sd, 5)
    R = w * (0.24 + 0.2 * math.sqrt(p))
    r = np.hypot(X, Y + p * h * 0.06)
    body = np.clip(1 - (r - R * (0.75 + 0.5 * n)) / (w * 0.06), 0, 1)
    body *= np.clip(1 - r / (w * 0.49), 0, 1) ** 0.5
    heat = np.clip((1 - r / (R * 1.1)) * 1.3 + (n - 0.5) * 1.2, 0, 1) * (1 - p) ** 1.3
    fire = _fire_ramp(heat * 1.2)
    smoke = lerp((26, 22, 20), (90, 82, 76), np.clip(n * 1.3 - 0.2, 0, 1)) / 255.0
    k = np.clip(heat * 2.2, 0, 1)
    col = smoke * (1 - k[..., None]) + fire * k[..., None]
    a = np.clip(body * (0.95 - 0.25 * p), 0, 1)
    return finish(col, a)


def paint_glow(w, h, idx):
    X, Y = coords(w, h)
    r = np.hypot(X, Y) / (w * 0.48)
    if idx == 0:
        a = np.clip(1 - r, 0, 1) ** 2.2
    else:
        a = np.clip(np.exp(-(r / 0.18) ** 2) + 0.55 * np.clip(1 - r, 0, 1) ** 3, 0, 1)
    col = np.ones(X.shape + (3,), f32)
    return finish(col, a)


def paint_spark(w, h, idx):
    X, Y = coords(w, h)
    if w == h:
        r = np.hypot(X, Y) / (w * 0.45)
        a = np.clip(np.exp(-(r / 0.25) ** 2) * 1.2 + 0.5 * np.clip(1 - r, 0, 1) ** 2, 0, 1)
    else:   # 横長の筋（lookat_direction で速さの向き）
        ax = np.abs(X) / (w * 0.47)
        ay = np.abs(Y) / (h * 0.42)
        a = np.clip(1 - ax, 0, 1) ** 0.7 * np.exp(-(ay / 0.45) ** 2) * 1.3
        a = np.clip(a, 0, 1)
    col = np.ones(X.shape + (3,), f32)
    hot = np.clip(a * 1.6 - 0.6, 0, 1)
    col = col * (0.85 + 0.15 * hot)[..., None]
    return finish(col, a)


def _polyline_dist(X, Y, pts):
    d = np.full(X.shape, 1e9, f32)
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        d = np.minimum(d, sd_capsule(X, Y, x0, y0, x1, y1, 0, 0))
    return d


def _bolt(rng, x0, y0, x1, y1, depth, rough):
    pts = [(x0, y0), (x1, y1)]
    for _ in range(depth):
        out = [pts[0]]
        for (ax, ay), (bx, by) in zip(pts[:-1], pts[1:]):
            mx, my = (ax + bx) / 2, (ay + by) / 2
            L = math.hypot(bx - ax, by - ay)
            nx, ny = -(by - ay) / (L + 1e-9), (bx - ax) / (L + 1e-9)
            off = rng.normal(0, rough) * L
            out += [(mx + nx * off, my + ny * off), (bx, by)]
        pts = out
    return pts


def paint_arc(w, h, idx):
    """放電の稲妻（白。芯 + にじみ + 枝）。"""
    rng = rng_for("arc", idx)
    X, Y = coords(w, h)
    a = rng.uniform(0, math.pi)
    L = w * 0.42
    x0, y0 = -math.cos(a) * L, -math.sin(a) * L
    pts = _bolt(rng, x0, y0, -x0, -y0, 5, 0.22)
    d = _polyline_dist(X, Y, pts)
    for _ in range(int(rng.integers(1, 4))):
        k = int(rng.integers(4, len(pts) - 4))
        bx, by = pts[k]
        ba = a + rng.uniform(-1.4, 1.4)
        bl = w * rng.uniform(0.12, 0.25)
        bp = _bolt(rng, bx, by, bx + math.cos(ba) * bl, by + math.sin(ba) * bl, 3, 0.25)
        d = np.minimum(d, _polyline_dist(X, Y, bp) + 0.3)
    core = np.exp(-(d / 0.7) ** 2)
    glow = np.exp(-(d / 3.2) ** 2) * 0.55
    alpha = np.clip(core + glow, 0, 1)
    edge = np.clip(1 - np.maximum(np.abs(X), np.abs(Y)) / (w * 0.48), 0, 1) ** 0.3
    col = np.ones(X.shape + (3,), f32) * (0.75 + 0.25 * core)[..., None]
    return finish(col, alpha * edge)


def paint_ring(w, h, idx):
    X, Y = coords(w, h)
    r = np.hypot(X, Y)
    R = w * 0.42
    if idx == 0:    # 細い輪
        a = np.exp(-((r - R) / 2.2) ** 2) + 0.35 * np.exp(-((r - R) / 7.0) ** 2)
    else:           # 太い衝撃波（外側が明るく、内へ薄れる）
        n = fbm(X * 0.06, Y * 0.06, 8000, 3)
        inner = np.clip((r - R * 0.45) / (R * 0.55), 0, 1) ** 2.2
        a = np.where(r <= R, inner, np.exp(-((r - R) / 2.5) ** 2)) * (0.7 + 0.5 * n)
    col = np.ones(X.shape + (3,), f32)
    return finish(col, np.clip(a, 0, 1))


def paint_flash(w, h, idx):
    """銃口の閃光（星形。固有色: 白い芯 → 黄 → 橙）。"""
    rng = rng_for("flash", idx)
    X, Y = coords(w, h)
    r = np.hypot(X, Y) / (w * 0.47)
    th = np.arctan2(Y, X)
    k = int(rng.integers(5, 9))
    spikes = np.zeros_like(r)
    for _i in range(k):
        a0 = rng.uniform(0, 2 * math.pi)
        ln = rng.uniform(0.55, 1.0)
        dth = np.abs(np.angle(np.exp(1j * (th - a0))))
        spikes = np.maximum(spikes, np.exp(-(dth / (0.12 + 0.1 * (1 - r))) ** 2) * np.clip(1 - r / ln, 0, 1))
    core = np.exp(-(r / 0.22) ** 2)
    n = fbm(X * 0.15, Y * 0.15, 8100 + idx, 3)
    inten = np.clip(core * 1.3 + spikes * (0.6 + 0.6 * n), 0, 1)
    col = _fire_ramp(0.55 + inten * 0.5)
    return finish(col, np.clip(inten * 1.2, 0, 1))


def paint_plume(w, h, idx):
    """横から見た銃口の炎（左が銃口、右へ広がる）。"""
    X, Y = coords(w, h)
    t = np.clip((X + w * 0.45) / (w * 0.9), 0, 1)
    wid = h * (0.12 + 0.35 * t ** 0.7) * np.clip((1 - t) * 3, 0, 1)
    n = fbm(X * 0.15, Y * 0.3, 8200 + idx, 3)
    inten = np.clip(1 - np.abs(Y) / np.maximum(wid, 0.3), 0, 1) * (0.6 + 0.6 * n) * (1.1 - t * 0.6)
    col = _fire_ramp(0.5 + inten * 0.55)
    return finish(col, np.clip(inten * 1.3, 0, 1))


def paint_line(w, h, idx):
    """横長の線（0: 速さの線、1: 曳光弾の筋）。"""
    X, Y = coords(w, h)
    t = (X + w / 2) / w
    if idx == 0:
        prof = np.sin(np.clip(t, 0, 1) * math.pi) ** 0.8
        a = np.exp(-(Y / (h * 0.18)) ** 2) * prof
    else:
        prof = np.clip(t * 1.4, 0, 1) ** 1.5 * np.clip((1 - t) * 12, 0, 1)
        a = (np.exp(-(Y / (h * 0.12)) ** 2) + 0.4 * np.exp(-(Y / (h * 0.35)) ** 2)) * prof
    col = np.ones(X.shape + (3,), f32)
    return finish(col, np.clip(a, 0, 1))


def paint_swing(w, h, idx):
    """近接武器の振りの軌跡（弧のにじみ。白）。"""
    X, Y = coords(w, h)
    R = w * 0.7
    cy = R * 0.62
    r = np.hypot(X, Y - cy)
    band = np.exp(-((r - R) / (h * 0.16)) ** 2)
    t = np.clip((X + w * 0.46) / (w * 0.92), 0, 1)
    a = band * t ** 1.5 * np.clip((1 - t) * 8, 0, 1) * (1.0 if idx == 0 else 0.7)
    a *= np.clip(1 - np.maximum(np.abs(X) / (w * 0.49), np.abs(Y) / (h * 0.49)), 0, 1) ** 0.2
    col = np.ones(X.shape + (3,), f32)
    return finish(col, np.clip(a * 1.2, 0, 1))


def paint_ash(w, h, idx):
    """灰のかけら（暗い灰色。半分は縁が赤く光る燠）。"""
    rng = rng_for("ash", idx)
    X, Y = coords(w, h)
    k = int(rng.integers(5, 8))
    R = w * rng.uniform(0.22, 0.36)
    pts = [(math.cos(2 * math.pi * i / k + rng.uniform(-0.3, 0.3)) * R * rng.uniform(0.6, 1.0),
            math.sin(2 * math.pi * i / k + rng.uniform(-0.3, 0.3)) * R * rng.uniform(0.4, 0.9)) for i in range(k)]
    d = sd_poly(X, Y, pts)
    base = lerp((40, 38, 36), (98, 94, 90), fbm(X * 0.5, Y * 0.5, 9000 + idx, 2))
    if idx % 2:
        glow = np.exp(-np.maximum(-d, 0) / 1.0)
        base = lerp(base, (255, 130, 40), glow * 0.9)
    return finish(base / 255.0, cover(d))


def paint_ember(w, h, idx):
    X, Y = coords(w, h)
    r = np.hypot(X, Y) / (w * 0.45)
    a = np.clip(np.exp(-(r / 0.45) ** 2) * 1.3, 0, 1)
    col = _fire_ramp(0.55 + 0.45 * np.exp(-(r / 0.3) ** 2))
    return finish(col, a)


def paint_debris(w, h, idx):
    """瓦礫・木っ端（固有色。上面が明るい）。"""
    rng = rng_for("debris", idx)
    X, Y = coords(w, h)
    kind = idx % 4
    if kind == 3:   # 木っ端（細長い）
        ang = rng.uniform(0, math.pi)
        d = sd_capsule(X, Y, -math.cos(ang) * w * 0.38, -math.sin(ang) * w * 0.38,
                       math.cos(ang) * w * 0.38, math.sin(ang) * w * 0.38, 1.6, 0.8)
        base = np.asarray((122, 88, 52), f32)
    else:
        k = int(rng.integers(4, 7))
        R = w * rng.uniform(0.28, 0.4)
        pts = [(math.cos(2 * math.pi * i / k + rng.uniform(-0.4, 0.4)) * R * rng.uniform(0.6, 1.0),
                math.sin(2 * math.pi * i / k + rng.uniform(-0.4, 0.4)) * R * rng.uniform(0.6, 1.0)) for i in range(k)]
        d = sd_poly(X, Y, pts)
        base = np.asarray([(128, 126, 120), (70, 68, 66), (140, 70, 52)][kind], f32)
    inside = np.maximum(-d, 0)
    shade_k = np.clip(0.75 + 0.5 * (-(X + Y) / w) + (fbm(X * 0.8, Y * 0.8, 9100 + idx, 2) - 0.5) * 0.4, 0.4, 1.2)
    col = base[None, None, :] * shade_k[..., None] * (0.8 + 0.2 * np.clip(inside, 0, 1))[..., None]
    return finish(col / 255.0, cover(d))


def paint_bubble(w, h, idx):
    X, Y = coords(w, h)
    R = w * (0.3 + 0.04 * idx)
    r = np.hypot(X, Y)
    ring = np.exp(-((r - R) / 0.9) ** 2)
    film = np.clip(1 - r / R, 0, 1) * 0.18
    hl = np.exp(-(np.hypot(X + R * 0.4, Y + R * 0.4) / 1.2) ** 2)
    a = np.clip(ring + film + hl, 0, 1)
    col = np.ones(X.shape + (3,), f32) * (0.8 + 0.2 * hl)[..., None]
    return finish(col, a)


def paint_wdrop(w, h, idx):
    """白い艶の滴（酸・毒・水を tint で染める）。"""
    rng = rng_for("wdrop", idx)
    X, Y = coords(w, h)
    R = w * rng.uniform(0.26, 0.34)
    d = np.hypot(X, Y * (1.0 + 0.25 * (idx % 2))) - R * (1 + harm(np.arctan2(Y, X), rng, 2, 4, 0.05))
    col, a = liquid(d, prof=R, thin=(235, 235, 235), thick=(150, 150, 150), a_thin=0.85, a_thick=1.0,
                    gloss=0.9, ring=0.0, dome=True)
    return finish(col, a)


def paint_star(w, h, idx):
    X, Y = coords(w, h)
    ax, ay = np.abs(X) / (w * 0.48), np.abs(Y) / (h * 0.48)
    ang = (math.pi / 4) * (idx % 2)
    U = (X * math.cos(ang) + Y * math.sin(ang)) / (w * 0.48)
    V = (-X * math.sin(ang) + Y * math.cos(ang)) / (w * 0.48)
    cross = np.exp(-np.abs(V) / 0.05) * np.clip(1 - np.abs(U), 0, 1) ** 2 + \
        np.exp(-np.abs(U) / 0.05) * np.clip(1 - np.abs(V), 0, 1) ** 2
    if idx >= 2:   # 8 本
        cross = cross + 0.5 * (np.exp(-np.abs(U - V) / 0.07) + np.exp(-np.abs(U + V) / 0.07)) * \
            np.clip(1 - np.hypot(U, V) * 1.4, 0, 1) ** 2
    core = np.exp(-(np.hypot(ax, ay) / 0.16) ** 2)
    a = np.clip(cross + core, 0, 1)
    col = np.ones(X.shape + (3,), f32)
    return finish(col, a)


def paint_eyes(w, h, idx):
    """暗闇に光る二つの目（白い芯 + 赤橙のにじみ。固有色）。"""
    X, Y = coords(w, h)
    a = np.zeros(X.shape, f32)
    core = np.zeros(X.shape, f32)
    for sx in (-1, 1):
        ex = sx * w * 0.22
        e = np.hypot((X - ex) / 1.0, (Y - (idx * 0.5)) / 0.55)
        core = np.maximum(core, np.exp(-(e / 2.2) ** 2))
        a = np.maximum(a, np.exp(-(e / 5.5) ** 2))
    col = lerp((255, 60, 20), (255, 240, 200), core) / 255.0
    return finish(col, np.clip(a * 0.9 + core, 0, 1))


def paint_fly(w, h, frame):
    X, Y = coords(w, h)
    body = cover(np.hypot(X / 1.6, Y / 1.0) - 1.1)
    wy = -1.3 if frame == 0 else 0.4
    wings = np.maximum(cover(np.hypot((X - 1.4) / 1.4, (Y - wy) / 0.8) - 1),
                       cover(np.hypot((X + 1.4) / 1.4, (Y - wy) / 0.8) - 1)) * 0.55
    a = np.maximum(body, wings)
    col = lerp((150, 160, 170), (18, 18, 20), body / np.maximum(a, 1e-3)) / 255.0
    return finish(col, a)


def paint_paper(w, h, idx):
    rng = rng_for("paper", idx)
    X, Y = coords(w, h)
    pts = [(rng.uniform(-3.5, -1.5), rng.uniform(-3.5, -1.0)), (rng.uniform(1.0, 3.5), rng.uniform(-3.5, -1.5)),
           (rng.uniform(1.5, 3.5), rng.uniform(1.0, 3.5)), (rng.uniform(-3.5, -1.0), rng.uniform(1.5, 3.5))]
    d = sd_poly(X, Y, pts)
    base = np.asarray([(205, 30, 32), (230, 210, 120), (200, 26, 28), (240, 236, 226)][idx % 4], f32)
    col = base[None, None, :] * (0.85 + 0.15 * np.clip(-(X + Y) / 6, -1, 1))[..., None]
    return finish(col / 255.0, cover(d))


def paint_casing(w, h, idx):
    """真鍮の薬莢（横向き）。"""
    X, Y = coords(w, h)
    L, r = w * 0.36, h * 0.17
    d = np.maximum(np.abs(X) - L, np.abs(Y) - r)
    d = np.where(X > L - 1.2, np.maximum(d, np.abs(Y) - r * 0.85), d)
    cyl = np.clip(1 - (Y / r) ** 2, 0, 1)
    base = lerp((110, 78, 24), (232, 196, 96), cyl ** 0.6)
    hl = np.exp(-((Y + r * 0.35) / (r * 0.18)) ** 2)
    base = base + hl[..., None] * np.asarray((60, 55, 40), f32)
    mouth = X < -L + 1.0
    base = np.where(mouth[..., None], np.asarray((60, 42, 16), f32), base)
    return finish(base / 255.0, cover(d))


def paint_chevron(w, h, idx):
    X, Y = coords(w, h)
    a = np.zeros(X.shape, f32)
    for k, yy in enumerate((-h * 0.16, h * 0.08)):
        d = np.abs(Y - yy - np.abs(X) * -0.75 + h * 0.1) - h * 0.06
        d = np.maximum(d, np.abs(X) - w * 0.32)
        a = np.maximum(a, cover(d) * (1.0 - 0.25 * k))
    glow = np.exp(-(np.hypot(X, Y) / (w * 0.32)) ** 2) * 0.35
    col = np.ones(X.shape + (3,), f32)
    return finish(col, np.clip(a + glow, 0, 1))


def paint_diamond(w, h, idx):
    X, Y = coords(w, h)
    m = np.abs(X) + np.abs(Y)
    R = w * 0.36
    a = np.exp(-((m - R) / 1.6) ** 2) + np.exp(-(np.hypot(X, Y) / 3.0) ** 2) + 0.3 * np.exp(-((m - R) / 6) ** 2)
    col = np.ones(X.shape + (3,), f32)
    return finish(col, np.clip(a, 0, 1))


def paint_rope(w, h, idx):
    X, Y = coords(w, h)
    d = np.hypot(X, Y) - w * 0.32
    tw = 0.5 + 0.5 * np.sin((X + Y) * 2.4)
    base = lerp((96, 70, 40), (170, 136, 88), tw)
    return finish(base / 255.0, cover(d))


def paint_spore(w, h, idx):
    X, Y = coords(w, h)
    r = np.hypot(X, Y) / (w * 0.45)
    a = np.clip(np.exp(-(r / 0.35) ** 2) * 0.9 + 0.5 * np.exp(-((r - 0.55) / 0.12) ** 2), 0, 1)
    col = np.ones(X.shape + (3,), f32) * (0.85 + 0.15 * np.exp(-(r / 0.2) ** 2))[..., None]
    return finish(col, a * (0.7 + 0.08 * idx))


# ===========================================================================
#  アトラス（棚詰め。セット = 同じ大きさのコマを横に並べた帯）
# ===========================================================================
class SpriteSet:
    def __init__(self, name, fw, fh, frames, desc=""):
        self.name, self.fw, self.fh, self.frames, self.desc = name, fw, fh, frames, desc
        self.x = self.y = 0

    @property
    def n(self):
        return len(self.frames)

    @property
    def w(self):
        return self.fw * self.n


class Atlas:
    def __init__(self, key, sets, width=ATLAS_W):
        self.key = key
        self.tex = f"{TEX_REL}/{key}"
        self.sets: Dict[str, SpriteSet] = {s.name: s for s in sets}
        order = sorted(sets, key=lambda s: (-s.fh, -s.w, s.name))
        x = y = row_h = 0
        for s in order:
            if s.w > width:
                raise SystemExit(f"[particles] {key}: {s.name} の帯 {s.w}px がアトラス幅 {width} を超える")
            if x + s.w > width:
                x, y, row_h = 0, y + row_h, 0
            s.x, s.y = x, y
            x += s.w
            row_h = max(row_h, s.fh)
        used_h = y + row_h
        self.width = width
        self.height = 1 << max(4, (used_h - 1).bit_length())
        self.used_h = used_h
        img = np.zeros((self.height, width, 4), np.uint8)
        for s in sets:
            for i, fr in enumerate(s.frames):
                if fr.shape[:2] != (s.fh, s.fw):
                    raise SystemExit(f"[particles] {key}: {s.name}[{i}] の大きさ {fr.shape[:2]} != {(s.fh, s.fw)}")
                img[s.y:s.y + s.fh, s.x + i * s.fw:s.x + (i + 1) * s.fw] = fr
        self.img = img

    def cell(self, name, i=0):
        s = self.sets[name]
        return s.x + i * s.fw, s.y, s.fw, s.fh

    def write(self):
        os.makedirs(TEX_DIR, exist_ok=True)
        Image.fromarray(self.img, "RGBA").save(os.path.join(TEX_DIR, self.key + ".png"), optimize=True)


def build_gore_atlas() -> Atlas:
    sets = [
        SpriteSet("splat", 128, 128, [paint_splat(128, 128, i, "round" if i < 5 else "cluster") for i in range(8)],
                  "地面の血痕（丸い 5 + 小さな塊 3）"),
        SpriteSet("splat_dir", 128, 128, [paint_splat(128, 128, i, "dir") for i in range(8)],
                  "勢いの向きに伸びた血痕（+u 向き）"),
        SpriteSet("wall", 128, 128, [paint_wall(128, 128, v, f) for v in range(2) for f in range(4)],
                  "壁の血痕 2 種 × 垂れる 4 コマ"),
        SpriteSet("wall2", 128, 128, [paint_wall(128, 128, v, f) for v in range(2, 4) for f in range(4)],
                  "壁の血痕（別の 2 種）× 4 コマ"),
        SpriteSet("pool", 128, 128, [paint_pool(128, 128, i) for i in range(4)], "血だまり"),
        SpriteSet("mist", 64, 64, [paint_mist(64, 64, i) for i in range(4)], "血の霧"),
        SpriteSet("foot", 64, 64, [paint_footprint(64, 64, i) for i in range(2)], "血の足跡（右・左）"),
        SpriteSet("jet", 64, 32, [paint_jet(64, 32, i) for i in range(4)], "噴き出す血の芯（横長）"),
        SpriteSet("gut", 64, 32, [paint_gut(64, 32, i) for i in range(4)], "腸の切れ端（横長）"),
        SpriteSet("drop", 32, 32, [paint_drop(32, 32, i) for i in range(8)], "艶のある血の滴"),
        SpriteSet("chunk", 32, 32, [paint_chunk(32, 32, i) for i in range(8)], "肉片"),
        SpriteSet("pale", 32, 32, [paint_chunk(32, 32, i, pale=True) for i in range(4)], "薄い組織（tint 用）"),
        SpriteSet("bone", 32, 32, [paint_bone(32, 32, i) for i in range(6)], "骨片"),
        SpriteSet("brain", 32, 32, [paint_brain(32, 32, i) for i in range(4)], "脳の欠片"),
        SpriteSet("streak", 64, 16, [paint_streak(64, 16, i) for i in range(4)], "伸びた滴（横長）"),
        SpriteSet("dot", 16, 16, [paint_dot(16, 16, i) for i in range(8)], "小さな血の点"),
        SpriteSet("wdrop", 16, 16, [paint_wdrop(16, 16, i) for i in range(4)], "白い滴（毒・胆汁を tint で染める）"),
    ]
    return Atlas("nr_gore", sets)


def build_fx_atlas() -> Atlas:
    sets = [
        SpriteSet("fireball", 128, 128, [paint_fireball(128, 128, f, 8, 0) for f in range(8)], "爆発の火の玉 8 コマ"),
        SpriteSet("ring", 128, 128, [paint_ring(128, 128, i) for i in range(2)], "輪（細い・衝撃波）"),
        SpriteSet("flame", 64, 64, [paint_flame(64, 64, f, 8, 0) for f in range(8)], "炎 8 コマ"),
        SpriteSet("flame2", 64, 64, [paint_flame(64, 64, f, 8, 1) for f in range(8)], "炎（別の形）8 コマ"),
        SpriteSet("smoke", 64, 64, [paint_smoke(64, 64, i) for i in range(8)], "煙（白。tint で色）"),
        SpriteSet("arc", 64, 64, [paint_arc(64, 64, i) for i in range(8)], "放電"),
        SpriteSet("flash", 64, 64, [paint_flash(64, 64, i) for i in range(4)], "銃口の閃光"),
        SpriteSet("glow", 64, 64, [paint_glow(64, 64, i) for i in range(2)], "柔らかい光"),
        SpriteSet("mark", 64, 64, [paint_chevron(64, 64, 0), paint_diamond(64, 64, 0)], "印（山形・菱形）"),
        SpriteSet("plume", 64, 32, [paint_plume(64, 32, i) for i in range(2)], "銃口の炎（横）"),
        SpriteSet("swing", 64, 32, [paint_swing(64, 32, i) for i in range(2)], "振りの軌跡"),
        SpriteSet("star", 32, 32, [paint_star(32, 32, i) for i in range(4)], "きらめき"),
        SpriteSet("eyes", 32, 16, [paint_eyes(32, 16, i) for i in range(2)], "光る目"),
        SpriteSet("spark_s", 32, 8, [paint_spark(32, 8, i) for i in range(2)], "火花の筋（横長）"),
        SpriteSet("line", 64, 8, [paint_line(64, 8, i) for i in range(2)], "速さの線・曳光"),
        SpriteSet("spark", 16, 16, [paint_spark(16, 16, i) for i in range(2)], "火花の点"),
        SpriteSet("ash", 16, 16, [paint_ash(16, 16, i) for i in range(8)], "灰・燠"),
        SpriteSet("debris", 16, 16, [paint_debris(16, 16, i) for i in range(8)], "瓦礫・木っ端"),
        SpriteSet("bubble", 16, 16, [paint_bubble(16, 16, i) for i in range(4)], "泡"),
        SpriteSet("wdrop", 16, 16, [paint_wdrop(16, 16, i) for i in range(4)], "白い滴（tint 用）"),
        SpriteSet("casing", 16, 16, [paint_casing(16, 16, i) for i in range(2)], "薬莢"),
        SpriteSet("spore", 16, 16, [paint_spore(16, 16, i) for i in range(4)], "胞子"),
        SpriteSet("ember", 8, 8, [paint_ember(8, 8, i) for i in range(2)], "火の粉"),
        SpriteSet("fly", 8, 8, [paint_fly(8, 8, f) for f in range(2)], "蝿 2 コマ"),
        SpriteSet("paper", 8, 8, [paint_paper(8, 8, i) for i in range(4)], "紙片"),
        SpriteSet("rope", 8, 8, [paint_rope(8, 8, 0)], "ロープ"),
    ]
    return Atlas("nr_fx", sets)


# ===========================================================================
#  確認画像（コンタクトシート）
# ===========================================================================
def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _ground(w, h, seed, base=(92, 90, 86), var=26):
    X, Y = np.mgrid[0:h, 0:w].astype(f32)
    n = fbm(X * 0.05, Y * 0.05, seed, 4) * 0.7 + fbm(X * 0.4, Y * 0.4, seed + 9, 2) * 0.3
    g = np.asarray(base, f32)[None, None, :] + (n[..., None] - 0.5) * var * 2
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


def contact_sheet(atlases: List[Atlas], path=SHEET):
    gore, fx = atlases
    pad = 16
    W = gore.width + fx.width + pad * 3
    scene_h = 300
    H = max(gore.used_h, fx.used_h) + scene_h + pad * 4 + 40
    sheet = Image.new("RGBA", (W, H), (24, 26, 30, 255))
    dr = ImageDraw.Draw(sheet)
    fnt = _font(13)
    # 血のアトラスは路面の上に、fx は暗い背景の上に
    bg = _ground(gore.width, gore.used_h, 11)
    sheet.alpha_composite(bg, (pad, pad + 20))
    sheet.alpha_composite(Image.fromarray(gore.img[:gore.used_h]), (pad, pad + 20))
    bg2 = Image.new("RGBA", (fx.width, fx.used_h), (40, 44, 52, 255))
    sheet.alpha_composite(bg2, (gore.width + pad * 2, pad + 20))
    sheet.alpha_composite(Image.fromarray(fx.img[:fx.used_h]), (gore.width + pad * 2, pad + 20))
    dr.text((pad, 4), f"nr_gore {gore.width}x{gore.height}", fill=(230, 230, 230), font=fnt)
    dr.text((gore.width + pad * 2, 4), f"nr_fx {fx.width}x{fx.height}", fill=(230, 230, 230), font=fnt)
    for at, ox in ((gore, pad), (fx, gore.width + pad * 2)):
        for s in at.sets.values():
            dr.rectangle([ox + s.x, pad + 20 + s.y, ox + s.x + s.w - 1, pad + 20 + s.y + s.fh - 1],
                         outline=(255, 255, 0, 90))
            dr.text((ox + s.x + 2, pad + 20 + s.y + 1), s.name, fill=(255, 255, 120), font=_font(10))
    # 場面: 路面と壁に血痕・血だまり・肉片を 2 倍で置く
    sy = pad * 2 + 20 + max(gore.used_h, fx.used_h)
    scene = _ground(W - pad * 2, scene_h, 21, base=(70, 70, 68), var=18)
    wall = _ground(360, scene_h, 31, base=(150, 146, 136), var=14)
    scene.alpha_composite(wall, (W - pad * 2 - 360, 0))

    def put(name, i, x, y, scale=2.0, atlas=gore):
        cx, cy, cw, ch = atlas.cell(name, i)
        im = Image.fromarray(atlas.img[cy:cy + ch, cx:cx + cw]).resize((int(cw * scale), int(ch * scale)),
                                                                          Image.NEAREST)
        scene.alpha_composite(im, (int(x), int(y)))

    put("pool", 0, 10, 20, 2.2)
    put("splat", 1, 250, 10, 2.0)
    put("splat_dir", 2, 470, 30, 1.8)
    put("splat", 6, 690, 40, 1.6)
    for i, (n, k) in enumerate((("chunk", 0), ("chunk", 3), ("bone", 0), ("brain", 1), ("gut", 2), ("drop", 2))):
        put(n, k, 80 + i * 70, 220, 2.0)
    put("foot", 0, 920, 30, 2.0)
    put("foot", 1, 990, 110, 2.0)
    for f in range(4):
        put("wall", f, W - pad * 2 - 360 + 10 + f * 86, 40, 0.9 * 1.5)
    sheet.alpha_composite(scene, (pad, sy))
    dr.text((pad, sy - 14), "scene: ground / wall (x2, nearest)", fill=(230, 230, 230), font=fnt)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.convert("RGB").save(path, optimize=True)
    return path


def main_sprites_only():
    gore = build_gore_atlas()
    fx = build_fx_atlas()
    gore.write()
    fx.write()
    p = contact_sheet([gore, fx])
    print(f"[particles] atlas nr_gore {gore.width}x{gore.height} (used {gore.used_h}), "
          f"nr_fx {fx.width}x{fx.height} (used {fx.used_h}) → {p}")
    return gore, fx


# ===========================================================================
#  Molang（生成した式の字句・構文・関数・変数の検査と、範囲の評価・簡易の物理の計算）
# ===========================================================================
class MolangError(Exception):
    pass


_TOK = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)f?|([A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)*)"
                  r"|(\?\?|&&|\|\||==|!=|<=|>=|[-+*/<>!?:(),;=]))")
# 公式の math.* と引数の数（validate_nr の表と同じもののうち使う可能性のあるもの）
MATH_FUNCS = {"abs": 1, "acos": 1, "asin": 1, "atan": 1, "atan2": 2, "ceil": 1, "clamp": 3, "cos": 1,
              "exp": 1, "floor": 1, "hermite_blend": 1, "lerp": 3, "ln": 1, "max": 2, "min": 2, "mod": 2,
              "pow": 2, "random": 2, "random_integer": 2, "round": 1, "sin": 1, "sqrt": 1, "trunc": 1,
              "sign": 1}
BUILTIN_VARS = {"particle_age", "particle_lifetime", "particle_random_1", "particle_random_2",
                "particle_random_3", "particle_random_4", "emitter_age", "emitter_lifetime",
                "emitter_random_1", "emitter_random_2", "emitter_random_3", "emitter_random_4", "entity_scale"}
INTERNAL_VARS = {"drop"}   # イベントの pre_effect_expression から子へ渡す内部の変数（滴の着地から出た血痕）
_BIN_PREC = {"??": 1, "||": 3, "&&": 4, "==": 5, "!=": 5, "<": 6, "<=": 6, ">": 6, ">=": 6,
             "+": 7, "-": 7, "*": 8, "/": 8}


def _tokens(s):
    out, pos, s = [], 0, s.strip()
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m or m.end() == pos:
            raise MolangError(f"読めない文字 {s[pos:pos + 12]!r}")
        if m.group(1) is not None:
            out.append(("num", float(m.group(1))))
        elif m.group(2) is not None:
            out.append(("id", m.group(2).lower()))
        else:
            out.append(("op", m.group(3)))
        pos = m.end()
    return out


class _Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ("end", None)

    def take(self, kind=None, val=None):
        tk = self.peek()
        if (kind and tk[0] != kind) or (val is not None and tk[1] != val):
            raise MolangError(f"{val or kind} が要るところに {tk[1]!r}")
        self.i += 1
        return tk

    def program(self):
        stmts = []
        while self.peek()[0] != "end":
            if self.peek() == ("id", "return"):
                self.take()
                stmts.append(("return", self.expr(0)))
            elif self.peek()[0] == "id" and self.peek(1) == ("op", "="):
                name = self.take()[1]
                self.take("op", "=")
                stmts.append(("assign", _norm_var(name), self.expr(0)))
            else:
                stmts.append(("expr", self.expr(0)))
            if self.peek() == ("op", ";"):
                self.take()
            elif self.peek()[0] != "end":
                raise MolangError(f"式の後ろに余計なもの {self.peek()[1]!r}（; が要る?）")
        return stmts

    def expr(self, minp):
        left = self.unary()
        while True:
            tk = self.peek()
            if tk[0] != "op":
                break
            op = tk[1]
            if op == "?" and minp <= 2:
                self.take()
                a = self.expr(2)
                if self.peek() == ("op", ":"):
                    self.take()
                    b = self.expr(2)
                else:
                    b = ("num", 0.0)
                left = ("tern", left, a, b)
                continue
            p = _BIN_PREC.get(op)
            if p is None or p < minp:
                break
            self.take()
            right = self.expr(p + (0 if op == "??" else 1))
            left = ("bin", op, left, right)
        return left

    def unary(self):
        tk = self.peek()
        if tk == ("op", "-") or tk == ("op", "!"):
            self.take()
            return ("un", tk[1], self.unary())
        if tk == ("op", "("):
            self.take()
            e = self.expr(0)
            self.take("op", ")")
            return e
        if tk[0] == "num":
            self.take()
            return ("num", tk[1])
        if tk[0] == "id":
            self.take()
            name = tk[1]
            if name.startswith("math."):
                fn = name[5:]
                if fn == "pi":
                    return ("num", math.pi)
                if fn not in MATH_FUNCS:
                    raise MolangError(f"知らない関数 math.{fn}")
                self.take("op", "(")
                args = []
                if self.peek() != ("op", ")"):
                    args.append(self.expr(0))
                    while self.peek() == ("op", ","):
                        self.take()
                        args.append(self.expr(0))
                self.take("op", ")")
                if len(args) != MATH_FUNCS[fn]:
                    raise MolangError(f"math.{fn} の引数が {len(args)} 個（{MATH_FUNCS[fn]} 個）")
                return ("call", fn, args)
            if name in ("true", "false"):
                return ("num", 1.0 if name == "true" else 0.0)
            if not (name.startswith("v.") or name.startswith("variable.")):
                raise MolangError(f"v. / math. 以外の名前 {name}（パーティクルでは使わない）")
            return ("var", _norm_var(name))
        raise MolangError(f"式が要るところに {tk[1]!r}")


def _norm_var(name):
    if name.startswith("variable."):
        name = "v." + name[9:]
    if not name.startswith("v."):
        raise MolangError(f"代入先 {name} は v.<名前> で")
    return name


_PARSED: Dict[str, list] = {}


def molang_parse(s):
    if isinstance(s, (int, float)):
        return [("expr", ("num", float(s)))]
    if s not in _PARSED:
        p = _Parser(_tokens(s))
        _PARSED[s] = p.program()
        if not _PARSED[s]:
            raise MolangError("空の式")
    return _PARSED[s]


def molang_vars(s):
    """式が読む変数・書く変数の集合（'v.' を除いた名前）。"""
    reads, writes = set(), set()

    def walk(nd):
        k = nd[0]
        if k == "var":
            reads.add(nd[1][2:])
        elif k in ("un",):
            walk(nd[2])
        elif k == "bin":
            walk(nd[2])
            walk(nd[3])
        elif k == "tern":
            walk(nd[1])
            walk(nd[2])
            walk(nd[3])
        elif k == "call":
            for a in nd[2]:
                walk(a)
    for st in molang_parse(s):
        if st[0] == "assign":
            writes.add(st[1][2:])
            walk(st[2])
        else:
            walk(st[1])
    return reads, writes


def _num(x):
    return 0.0 if x is None else float(x)


def _eval(nd, env, rng):
    k = nd[0]
    if k == "num":
        return nd[1]
    if k == "var":
        return env.get(nd[1])
    if k == "un":
        a = _num(_eval(nd[2], env, rng))
        return -a if nd[1] == "-" else (0.0 if a else 1.0)
    if k == "tern":
        return _eval(nd[2], env, rng) if _num(_eval(nd[1], env, rng)) else _eval(nd[3], env, rng)
    if k == "bin":
        op = nd[1]
        if op == "??":
            a = _eval(nd[2], env, rng)
            return a if a is not None else _eval(nd[3], env, rng)
        a = _num(_eval(nd[2], env, rng))
        if op == "&&":
            return 1.0 if (a and _num(_eval(nd[3], env, rng))) else 0.0
        if op == "||":
            return 1.0 if (a or _num(_eval(nd[3], env, rng))) else 0.0
        b = _num(_eval(nd[3], env, rng))
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b if b else 0.0
        return 1.0 if {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "==": a == b, "!=": a != b}[op] else 0.0
    if k == "call":
        fn, args = nd[1], [_num(_eval(a, env, rng)) for a in nd[2]]
        d2r = math.pi / 180.0
        if fn == "random":
            return rng.uniform(min(args), max(args)) if args[0] != args[1] else args[0]
        if fn == "random_integer":
            return float(rng.integers(int(min(args)), int(max(args)) + 1))
        if fn == "clamp":
            return min(max(args[0], args[1]), args[2])
        if fn == "sin":
            return math.sin(args[0] * d2r)
        if fn == "cos":
            return math.cos(args[0] * d2r)
        if fn == "atan2":
            return math.atan2(args[0], args[1]) / d2r
        if fn == "mod":
            return math.fmod(args[0], args[1]) if args[1] else 0.0
        if fn == "pow":
            try:
                return float(abs(args[0]) ** args[1]) * (1 if args[0] >= 0 else -1)
            except OverflowError:
                return 1e30
        if fn == "lerp":
            return args[0] + (args[1] - args[0]) * args[2]
        if fn == "hermite_blend":
            t = args[0]
            return 3 * t * t - 2 * t * t * t
        if fn == "exp":
            return math.exp(min(args[0], 80))
        if fn == "ln":
            return math.log(args[0]) if args[0] > 0 else -1e30
        if fn == "sqrt":
            return math.sqrt(max(args[0], 0))
        if fn == "sign":
            return math.copysign(1.0, args[0]) if args[0] else 0.0
        return float({"abs": abs, "floor": math.floor, "ceil": math.ceil, "round": lambda x: math.floor(x + 0.5),
                      "trunc": math.trunc, "min": min, "max": max, "acos": lambda x: math.degrees(math.acos(x)),
                      "asin": lambda x: math.degrees(math.asin(x)),
                      "atan": lambda x: math.degrees(math.atan(x))}[fn](*args))
    raise MolangError(f"評価できない {k}")


def molang_eval(s, env, rng=None):
    """式（文の列）を評価する。env は {'v.名前': 値}（書き込みもここへ）。"""
    rng = rng or np.random.default_rng(1)
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    val = 0.0
    for st in molang_parse(s):
        if st[0] == "assign":
            env[st[1]] = _num(_eval(st[2], env, rng))
        elif st[0] == "return":
            return _num(_eval(st[1], env, rng))
        else:
            val = _eval(st[1], env, rng)
    return _num(val)


# ===========================================================================
#  部品の組み立て（欄の形はバニラ／公式スキーマのとおり）
# ===========================================================================
def n(x):
    """数を Molang／JSON 用に短く。文字列はそのまま。"""
    if isinstance(x, str):
        return x
    x = float(x)
    if x.is_integer():
        return str(int(x))
    return ("%.5f" % x).rstrip("0").rstrip(".")


def jnum(x):
    """JSON に数として入れる値（整数は int）。"""
    if isinstance(x, str):
        return x
    x = float(x)
    return int(x) if x.is_integer() else round(x, 5)


AGE = "v.particle_age"
T = "(v.particle_age / v.particle_lifetime)"
R1, R2, R3, R4 = (f"v.particle_random_{i}" for i in range(1, 5))
EAGE = "v.emitter_age"


def V(name, d):
    return f"(v.{name} ?? {n(d)})"


def VC(name, d, lo, hi):
    return f"math.clamp((v.{name} ?? {n(d)}), {n(lo)}, {n(hi)})"


def FR(r, k):
    """もう一つの乱数 0..1（particle_random を k 倍した小数部）。"""
    return f"math.mod({r} * {n(k)}, 1.0)"


def RND(a, b):
    return f"math.random({n(a)}, {n(b)})"


def sel(r, cases):
    """r の値で場合分け: cases = [(上限, 値), ..., (None, 値)]。"""
    out = n(cases[-1][1])
    for edge, ex in reversed(cases[:-1]):
        out = f"({r} < {n(edge)} ? {n(ex)} : {out})"
    return out


def fade(k):
    return f"math.clamp((1.0 - {T}) * {n(k)}, 0.0, 1.0)"


def fade_io(a, b):
    return f"math.clamp(math.min({T} * {n(a)}, (1.0 - {T}) * {n(b)}), 0.0, 1.0)"


def C_once(active=None):
    return {"minecraft:emitter_lifetime_once": {} if active is None else {"active_time": jnum(active)}}


def C_loop(active, sleep=None):
    d = {"active_time": jnum(active)}
    if sleep is not None:
        d["sleep_time"] = jnum(sleep)
    return {"minecraft:emitter_lifetime_looping": d}


def C_instant(num):
    return {"minecraft:emitter_rate_instant": {"num_particles": jnum(num)}}


def C_steady(rate, maxp):
    return {"minecraft:emitter_rate_steady": {"spawn_rate": jnum(rate), "max_particles": jnum(maxp)}}


def C_init(create=None, update=None):
    d = {}
    if create:
        d["creation_expression"] = create
    if update:
        d["per_update_expression"] = update
    return {"minecraft:emitter_initialization": d}


def _v3(v):
    return [jnum(x) for x in v]


def C_point(offset=None, direction=None):
    d = {}
    if offset is not None:
        d["offset"] = _v3(offset)
    if direction is not None:
        d["direction"] = direction if isinstance(direction, str) else _v3(direction)
    return {"minecraft:emitter_shape_point": d}


def C_sphere(radius, direction="outwards", offset=None, surface=False):
    d = {"radius": jnum(radius), "direction": direction if isinstance(direction, str) else _v3(direction)}
    if offset is not None:
        d["offset"] = _v3(offset)
    if surface:
        d["surface_only"] = True
    return {"minecraft:emitter_shape_sphere": d}


def C_disc(radius, direction="outwards", offset=None, surface=False):
    d = {"radius": jnum(radius), "plane_normal": "y",
         "direction": direction if isinstance(direction, str) else _v3(direction)}
    if offset is not None:
        d["offset"] = _v3(offset)
    if surface:
        d["surface_only"] = True
    return {"minecraft:emitter_shape_disc": d}


def C_box(half, direction, offset=None, surface=False):
    d = {"half_dimensions": _v3(half), "direction": direction if isinstance(direction, str) else _v3(direction)}
    if offset is not None:
        d["offset"] = _v3(offset)
    if surface:
        d["surface_only"] = True
    return {"minecraft:emitter_shape_box": d}


def C_life(max_life):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": jnum(max_life)}}


def C_speed(expr):
    return {"minecraft:particle_initial_speed": jnum(expr)}


def C_spin(rot, rate=None):
    d = {"rotation": jnum(rot)}
    if rate is not None:
        d["rotation_rate"] = jnum(rate)
    return {"minecraft:particle_initial_spin": d}


def C_dyn(acc=None, drag=None, rdrag=None, racc=None):
    d = {}
    if acc is not None:
        d["linear_acceleration"] = _v3(acc)
    if drag is not None:
        d["linear_drag_coefficient"] = jnum(drag)
    if racc is not None:
        d["rotation_acceleration"] = jnum(racc)
    if rdrag is not None:
        d["rotation_drag_coefficient"] = jnum(rdrag)
    return {"minecraft:particle_motion_dynamic": d}


def C_param(rel=None, rot=None):
    d = {}
    if rel is not None:
        d["relative_position"] = _v3(rel)
    if rot is not None:
        d["rotation"] = jnum(rot)
    return {"minecraft:particle_motion_parametric": d}


def C_coll(radius, rest=None, drag=None, expire=None, events=None, enabled=None):
    d = {"collision_radius": jnum(radius)}
    if enabled is not None:
        d["enabled"] = jnum(enabled)
    if drag is not None:
        d["collision_drag"] = jnum(drag)
    if rest is not None:
        d["coefficient_of_restitution"] = jnum(rest)
    if expire is not None:
        d["expire_on_contact"] = bool(expire)
    if events:
        d["events"] = events
    return {"minecraft:particle_motion_collision": d}


def UV(at, u, v, w, h):
    return {"texture_width": at.width, "texture_height": at.height, "uv": [jnum(u), jnum(v)],
            "uv_size": [jnum(w), jnum(h)]}


def UVF(at, sets, r, fps=10, stretch=True, loop=False):
    """フリップブック（同じ大きさの帯のどれかを r で選ぶ）。コマは横に並ぶ。"""
    ss = [at.sets[s] for s in sets]
    fw, fh, nf = ss[0].fw, ss[0].fh, ss[0].n
    assert all((s.fw, s.fh, s.n) == (fw, fh, nf) for s in ss)
    if len(ss) == 1:
        bu, bv = ss[0].x, ss[0].y
    else:
        k = len(ss)
        idx = f"math.min(math.floor({r} * {k}), {k - 1})"
        bu = sel(idx, [(i + 0.5, s.x) for i, s in enumerate(ss[:-1])] + [(None, ss[-1].x)])
        bv = sel(idx, [(i + 0.5, s.y) for i, s in enumerate(ss[:-1])] + [(None, ss[-1].y)])
    return {"texture_width": at.width, "texture_height": at.height,
            "flipbook": {"base_UV": [jnum(bu), jnum(bv)], "size_UV": [fw, fh], "step_UV": [fw, 0],
                         "frames_per_second": fps, "max_frame": nf, "stretch_to_lifetime": stretch, "loop": loop}}


def pick(at, name, r, start=0, count=None):
    """帯 name のコマ start..start+count-1 から r で選んだ u（式）。"""
    s = at.sets[name]
    cnt = count or (s.n - start)
    if cnt <= 1:
        return s.x + start * s.fw
    return f"({s.x + start * s.fw} + math.min(math.floor({r} * {cnt}), {cnt - 1}) * {s.fw})"


def C_bb(size, mode, uv, direction=None):
    d = {"size": [jnum(size[0]), jnum(size[1])], "facing_camera_mode": mode}
    if direction is not None:
        if direction[0] == "velocity":
            d["direction"] = {"mode": "derive_from_velocity", "min_speed_threshold": direction[1]}
        else:
            d["direction"] = {"mode": "custom", "custom_direction": _v3(direction[1])}
    d["uv"] = uv
    return {"minecraft:particle_appearance_billboard": d}


def C_tint(r, g, b, a):
    return {"minecraft:particle_appearance_tinting": {"color": [jnum(r), jnum(g), jnum(b), jnum(a)]}}


LIGHT = {"minecraft:particle_appearance_lighting": {}}


def C_events(creation=None, timeline=None, expiration=None):
    d = {}
    if creation:
        d["creation_event"] = creation
    if timeline:
        d["timeline"] = timeline
    if expiration:
        d["expiration_event"] = expiration
    return {"minecraft:emitter_lifetime_events": d}


def ev_effect(effect, kind="emitter", pre=None):
    d = {"effect": effect, "type": kind}
    if pre:
        d["pre_effect_expression"] = pre
    return {"particle_effect": d}


def ev_decals(options, life=40, nothing=0.0):
    """滴の着地 → 地面の血痕（v.drop = 1 で落ち着く）。options = [(重み, 大きさ)]、nothing は出さない重み。"""
    opts = []
    if nothing:
        opts.append({"weight": jnum(nothing)})
    for w, s in options:
        e = ev_effect("nr:blood_splat_ground", "emitter", f"v.size = {n(s)}; v.life = {n(life)}; v.drop = 1;")
        opts.append({"weight": jnum(w), **e})
    return {"randomize": opts}


# 作ったパーティクル: 名前 -> {"doc": ..., "material": ..., "atlas": ...}
EFFECTS: Dict[str, dict] = {}
GORE: Atlas = None   # type: ignore[assignment]
FX: Atlas = None     # type: ignore[assignment]
MAT_ALPHA, MAT_BLEND, MAT_ADD = "particles_alpha", "particles_blend", "particles_add"


def effect(name, at, material, comps, events=None, note=""):
    if name in EFFECTS:
        raise SystemExit(f"[particles] 二重定義 {name}")
    pe = {"description": {"identifier": f"nr:{name}",
                          "basic_render_parameters": {"material": material, "texture": at.tex}},
          "components": comps}
    if events:
        pe["events"] = events
    EFFECTS[name] = {"doc": {"format_version": FORMAT_VERSION, "particle_effect": pe},
                     "atlas": at, "material": material, "note": note}


# ===========================================================================
#  粒の「種類」（一つのエミッタの中で particle_random で見た目を変える）
#  (横の大きさ, 縦の大きさ, u, v, uv 幅, uv 高さ) の式の組
# ===========================================================================
def k_drop(w, r=R4):
    """液体の滴: 最初の 0.16 秒は速さの向きに伸びた筋、その後は丸い滴（lookat_direction 用）。"""
    early = f"{AGE} < 0.16"
    st, dr = GORE.sets["streak"], GORE.sets["drop"]
    return (f"({early} ? ({w}) * 3.2 : ({w}) * 1.15)", f"({w})",
            f"({early} ? {pick(GORE, 'streak', r)} : {pick(GORE, 'drop', r)})",
            f"({early} ? {st.y} : {dr.y})", f"({early} ? {st.fw} : {dr.fw})", f"({early} ? {st.fh} : {dr.fh})")


def k_sprite(at, name, w, r=R4, aspect=None):
    s = at.sets[name]
    asp = aspect if aspect is not None else s.fw / s.fh
    return (f"({w}) * {n(asp)}" if asp != 1 else f"({w})", f"({w})", pick(at, name, r), s.y, s.fw, s.fh)


def mixk(r, cases):
    """cases = [(上限, 種類), ..., (None, 種類)] → 6 つの式。"""
    return tuple(sel(r, [(e, k[i]) for e, k in cases]) for i in range(6))


def bb_k(k, mode, at, direction=None):
    sx, sy, u, v, uw, vh = k
    return C_bb([sx, sy], mode, UV(at, u, v, uw, vh), direction)


def decal_tint(LF):
    dry = f"math.clamp({AGE} / ({LF} * 0.5 + 0.01), 0.0, 1.0)"
    return C_tint(f"1.0 - 0.32 * {dry}", f"1.0 - 0.4 * {dry}", f"1.0 - 0.38 * {dry}", fade(9))


GRAV = -17
G_ = VC("gore", 1, 0, 1)


# ===========================================================================
#  血
# ===========================================================================
def e_blood_spray():
    S = VC("size", 1, 0.2, 4)
    SPR = VC("spread", 0.25, 0, 2)
    J = f"(0.16 + {SPR})"
    k = k_drop(f"(0.045 + 0.045 * {R3}) * {S}")
    effect("blood_spray", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 12, 0, 500)} * (0.35 + 0.65 * {G_})), 1, 48)"),
        **C_point(offset=[f"math.random(-0.2, 0.2) * {SPR}"] * 3,
                  direction=[f"{V('dx', 0)} + math.random(-1, 1) * {J}",
                             f"{V('dy', 1)} + 0.12 + math.random(-1, 1) * {J}",
                             f"{V('dz', 0)} + math.random(-1, 1) * {J}"]),
        **C_speed(f"(3.0 + 4.5 * {R1}) * {VC('speed', 1, 0.05, 4)}"),
        **C_life(f"0.9 + 0.8 * {R2}"),
        **C_dyn(acc=[0, GRAV, 0], drag=0.55),
        **C_coll(0.04, expire=True, events=[{"event": "land", "min_speed": 2}]),
        **bb_k(k, "lookat_direction", GORE, ("velocity", 0.05)),
        **C_tint(f"1.0 - 0.25 * {T}", f"1.0 - 0.3 * {T}", f"1.0 - 0.3 * {T}", fade(6)),
        **LIGHT,
    }, {"land": ev_decals([(3, 0.2), (1.5, 0.32), (0.6, 0.45)], 40, 5)},
        "向き付きの滴。着地で血痕（v.drop で床へ落ち着く）")


def e_blood_burst():
    S = VC("size", 1, 0.2, 4)
    k = mixk(R1, [(0.82, k_drop(f"(0.04 + 0.05 * {R3}) * {S}")),
                  (None, k_sprite(GORE, "jet", f"(0.09 + 0.06 * {R3}) * {S}"))])
    effect("blood_burst", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 14, 0, 500)} * (0.35 + 0.65 * {G_})), 1, 56)"),
        **C_sphere(f"0.12 * {S}", [RND(-1, 1), RND(-0.25, 1.2), RND(-1, 1)]),
        **C_speed(f"(2.5 + 5.0 * {R2}) * {VC('speed', 0.8, 0.05, 4)}"),
        **C_life(sel(R1, [(0.82, f"0.8 + 0.7 * {R3}"), (None, f"0.35 + 0.2 * {R3}")])),
        **C_dyn(acc=[0, GRAV, 0], drag=sel(R1, [(0.82, 0.6), (None, 1.6)])),
        **C_coll(0.04, expire=True, events=[{"event": "land", "min_speed": 2}]),
        **bb_k(k, "lookat_direction", GORE, ("velocity", 0.05)),
        **C_tint(f"1.0 - 0.25 * {T}", f"1.0 - 0.3 * {T}", f"1.0 - 0.3 * {T}", fade(5)),
        **LIGHT,
    }, {"land": ev_decals([(3, 0.22), (1.2, 0.36)], 40, 6)}, "全方向に弾ける滴と液の塊")


def e_blood_mist():
    S = VC("size", 1, 0.2, 4)
    LF = VC("life", 0.9, 0.2, 4)
    effect("blood_mist", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(4 + 10 * {G_}), 1, 16)"),
        **C_sphere(f"0.25 * {S}", "outwards"),
        **C_speed(f"(0.4 + 1.0 * {R2}) * {S}"),
        **C_life(f"{LF} * (0.7 + 0.6 * {R3})"),
        **C_dyn(acc=[0, -0.5, 0], drag=2.2),
        **C_spin(RND(0, 360), RND(-40, 40)),
        **C_bb([f"(0.3 + 0.3 * {R4}) * {S} * (1.0 + 1.5 * math.pow({T}, 0.6))"] * 2, "lookat_xyz",
               UV(GORE, pick(GORE, "mist", FR(R1, 5.3)), GORE.sets["mist"].y, 64, 64)),
        **C_tint(1, 1, 1, f"(0.35 + 0.5 * {G_}) * math.pow(1.0 - {T}, 1.4)"),
        **LIGHT,
    }, note="細かい血の霧（広がって薄れる）")


def e_blood_drip():
    S = VC("size", 1, 0.2, 4)
    CNT = VC("count", 3, 1, 8)
    w = f"(0.03 + 0.02 * {R3}) * {S}"
    st = GORE.sets["streak"]
    effect("blood_drip", GORE, MAT_BLEND, {
        # スクリプトは必ず v.count を渡す → v.count 滴を 0.7 秒で。アニメの状態（腹の傷など。変数なし）からは
        # 状態の間 2.2 滴/秒（最長 30 秒で止まる。取り残しを作らない）
        **C_lifeexpr(f"{EAGE} > ({CONT_COUNT} ? 30 : 0.7)"),
        **C_steady(f"({CONT_COUNT} ? 2.2 : {CNT} / 0.7)", CNT),
        **C_box([0.06, 0.02, 0.06], [0, -1, 0]),
        **C_speed(f"0.3 + 0.5 * {R2}"),
        **C_life(2.2),
        **C_dyn(acc=[0, -16, 0], drag=0.3),
        **C_coll(0.02, expire=True, events=[{"event": "land", "min_speed": 2}]),
        **C_bb([f"{w} * (1.5 + 2.0 * math.clamp({AGE} * 3.0, 0.0, 1.0))", w], "lookat_direction",
               UV(GORE, pick(GORE, "streak", R4), st.y, st.fw, st.fh), ("velocity", 0.05)),
        **C_tint(1, 1, 1, fade(8)),
        **LIGHT,
    }, {"land": ev_decals([(2, 0.12), (1, 0.18)], 30, 2)}, "ぽたぽた落ちて床で小さな血痕")


def e_blood_fountain():
    S = VC("size", 1, 0.2, 3)
    LF = VC("life", 0.6, 0.05, 5)
    J = 0.1
    k = mixk(R1, [(0.3, k_sprite(GORE, "jet", f"(0.11 + 0.05 * {R3}) * {S}")),
                  (None, k_drop(f"(0.045 + 0.04 * {R3}) * {S}"))])
    effect("blood_fountain", GORE, MAT_BLEND, {
        **C_once(LF),
        **C_steady(f"(24 + 46 * {G_}) * math.sqrt({S})", 48),
        **C_point(direction=[f"{V('dx', 0)} + math.random(-{J}, {J})", f"{V('dy', 1)} + math.random(-{J}, {J})",
                             f"{V('dz', 0)} + math.random(-{J}, {J})"]),
        **C_speed(f"(3.2 + 2.2 * {R2}) * (0.72 + 0.28 * math.sin({EAGE} * 900)) * (0.6 + 0.4 * {S})"),
        **C_life(sel(R1, [(0.3, f"0.45 + 0.2 * {R3}"), (None, f"1.0 + 0.6 * {R3}")])),
        **C_dyn(acc=[0, -16, 0], drag=0.45),
        **C_coll(0.04, expire=True, events=[{"event": "land", "min_speed": 2}]),
        **bb_k(k, "lookat_direction", GORE, ("velocity", 0.05)),
        **C_tint(1, f"1.0 - 0.2 * {T}", f"1.0 - 0.2 * {T}", fade(6)),
        **LIGHT,
    }, {"land": ev_decals([(2, 0.22), (1, 0.35)], 40, 4)}, "断面から拍動して噴く（v.life 秒）")


def _splat_uv():
    a, b = GORE.sets["splat"], GORE.sets["splat_dir"]
    u = f"({R2} < 0.62 ? {pick(GORE, 'splat', R3)} : {pick(GORE, 'splat_dir', R3)})"
    v = f"({R2} < 0.62 ? {a.y} : {b.y})"
    return UV(GORE, u, v, a.fw, a.fh)


def e_blood_splat_ground():
    SZ = VC("size", 1, 0.05, 6)
    LF = VC("life", 40, 0.5, 300)
    DROP = V("drop", 0)
    grow = f"(0.5 + 0.5 * math.clamp({AGE} / 0.1, 0.0, 1.0))"
    effect("blood_splat_ground", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(offset=[0, f"{R4} * 0.006", 0]),
        **C_life(LF),
        **C_spin(RND(0, 360), 0),
        # v.drop = 1（滴の着地から）のときだけ重力と当たり判定で床へ落ち着く（壁に当たった滴も床へ）
        **C_dyn(acc=[0, f"-14 * {DROP}", 0], drag=f"0.5 * {DROP}"),
        **C_coll(0.01, rest=0, drag=40, enabled=f"{DROP} > 0"),
        **C_bb([f"{SZ} * (0.85 + 0.3 * {R1}) * {grow}"] * 2, "emitter_transform_xz", _splat_uv()),
        **decal_tint(LF),
        **LIGHT,
    }, note="地面の血痕（平ら）。乾くと暗くなり、最後に薄れて消える")


def _wall_uv():
    sets = [s for nm, s in sorted(GORE.sets.items()) if nm.startswith("wall")]
    variants = [(s, j) for s in sets for j in range(s.n // 4)]
    nv = len(variants)
    fw, fh = sets[0].fw, sets[0].fh
    kidx = f"math.min(math.floor({R1} * {nv}), {nv - 1})"
    t = f"({AGE} * (0.75 + 0.5 * {R3}))"
    frame = f"({t} < 0.3 ? 0 : ({t} < 0.85 ? 1 : ({t} < 1.7 ? 2 : 3)))"
    u0 = sel(kidx, [(i + 0.5, s.x + j * 4 * s.fw) for i, (s, j) in enumerate(variants[:-1])] +
             [(None, variants[-1][0].x + variants[-1][1] * 4 * fw)])
    v0 = sel(kidx, [(i + 0.5, s.y) for i, (s, _j) in enumerate(variants[:-1])] + [(None, variants[-1][0].y)])
    return UV(GORE, f"{u0} + {frame} * {fw}", v0, fw, fh)


def _wall(name, axis_var, mode, axis):
    SZ = VC("size", 1, 0.05, 5)
    LF = VC("life", 40, 0.5, 300)
    side = f"({V(axis_var, 1)} >= 0 ? 1 : -1)"
    off = [0, 0, 0]
    off[axis] = f"{side} * {R4} * 0.006"
    effect(name, GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(offset=off),
        **C_life(LF),
        **C_spin(f"({R2} - 0.5) * 16", 0),
        **C_bb([f"{SZ} * (0.9 + 0.25 * {FR(R2, 7.1)})"] * 2, mode, _wall_uv()),
        **decal_tint(LF),
        **LIGHT,
    }, note=f"壁の血痕（{mode}。下へ垂れる 4 コマ。v.{axis_var} の符号の側へ少し浮かす）")


def e_blood_splat_wall_x():
    _wall("blood_splat_wall_x", "dx", "emitter_transform_yz", 0)   # ±X を向いた壁 = YZ 面


def e_blood_splat_wall_z():
    _wall("blood_splat_wall_z", "dz", "emitter_transform_xy", 2)   # ±Z を向いた壁 = XY 面


def e_blood_pool():
    SZ = VC("size", 1.2, 0.1, 6)
    LF = VC("life", 60, 0.5, 300)
    grow_t = f"math.min({LF} * 0.35, 6.0)"
    g = f"(0.25 + 0.75 * (1.0 - math.pow(1.0 - math.clamp({AGE} / {grow_t}, 0.0, 1.0), 2.2)))"
    p = GORE.sets["pool"]
    effect("blood_pool", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(offset=[0, f"0.001 + {R3} * 0.003", 0]),
        **C_life(LF),
        **C_spin(RND(0, 360), 0),
        **C_bb([f"{SZ} * (0.9 + 0.2 * {R1}) * {g}"] * 2, "emitter_transform_xz",
               UV(GORE, pick(GORE, "pool", R2), p.y, p.fw, p.fh)),
        **decal_tint(LF),
        **LIGHT,
    }, note="広がっていく血だまり（最初の 35%（最大 6 秒）で広がる）")


def e_blood_trail():
    SZ = VC("size", 1, 0.1, 3)
    d = GORE.sets["dot"]
    effect("blood_trail", GORE, MAT_BLEND, {
        **C_once(),
        # gib の動きのアニメ（0.12 秒ごと）からも出るので、半分だけ・短命
        **C_instant(f"(v.emitter_random_1 < 0.55 ? 1 : 0)"),
        **C_point(offset=[RND(-0.05, 0.05), 0, RND(-0.05, 0.05)]),
        **C_life(f"10 + 6 * {R3}"),
        **C_spin(RND(0, 360), 0),
        **C_dyn(acc=[0, -14, 0], drag=0.5),
        **C_coll(0.01, rest=0, drag=40),
        **C_bb([f"{SZ} * (0.1 + 0.09 * {R1}) * (0.6 + 0.4 * math.clamp({AGE} / 0.08, 0.0, 1.0))"] * 2,
               "emitter_transform_xz", UV(GORE, pick(GORE, "dot", R2), d.y, d.fw, d.fh)),
        **C_tint(1, 1, 1, fade(6)),
        **LIGHT,
    }, note="小さな血の点（床へ落ちて残る）")


def e_bleed_stump():
    st = GORE.sets["streak"]
    w = f"(0.025 + 0.02 * {R3})"
    effect("bleed_stump", GORE, MAT_BLEND, {
        # ロケータに付いている間（状態の間。最長 45 秒で止血）。誤ってスクリプトから出しても 1.5 秒で終わる
        **C_lifeexpr(f"{EAGE} > ({ATT} ? 45 : 1.5)"),
        **C_steady(f"2.5 + 2.0 * v.emitter_random_1", 10),
        **C_point(offset=[RND(-0.04, 0.04), RND(-0.03, 0.0), RND(-0.04, 0.04)], direction=[0, -1, 0]),
        **C_speed(f"0.1 + 0.3 * {R2}"),
        **C_life(1.6),
        **C_dyn(acc=[0, -15, 0], drag=0.3),
        **C_coll(0.02, expire=True, events=[{"event": "land", "min_speed": 2}]),
        **C_bb([f"{w} * (1.4 + 2.0 * math.clamp({AGE} * 3.0, 0.0, 1.0))", w], "lookat_direction",
               UV(GORE, pick(GORE, "streak", R4), st.y, st.fw, st.fh), ("velocity", 0.05)),
        **C_tint(1, 1, 1, fade(8)),
        **LIGHT,
    }, {"land": ev_decals([(1, 0.12), (0.6, 0.18)], 12, 6.4)}, "断面からの持続的な滴り（ロケータに付く。ループ）")


def e_bloody_footprint():
    SZ = VC("size", 1, 0.2, 3)
    LF = VC("life", 30, 0.5, 300)
    f = GORE.sets["foot"]
    effect("bloody_footprint", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(offset=[0, f"0.002 + {R3} * 0.003", 0]),
        **C_life(LF),
        # 任意: v.dx / v.dz（歩く向き）があればつま先をそちらへ（無ければ向きは乱数）。向きの符号は実機未確認
        **C_spin(f"math.atan2(-{V('dx', 'math.random(-1, 1)')}, -{V('dz', 'math.random(-1, 1)')}) + "
                 f"math.random(-6, 6)", 0),
        **C_bb([f"{SZ} * 0.34", f"{SZ} * 0.34"], "emitter_transform_xz",
               UV(GORE, pick(GORE, "foot", R1), f.y, f.fw, f.fh)),
        **decal_tint(LF),
        **LIGHT,
    }, note="血を踏んだ足跡（平ら）")


# ===========================================================================
#  肉片・骨・脳・腸・複合
# ===========================================================================
def _solid_motion(rest, cdrag, radius, events=None):
    return {**C_dyn(acc=[0, -18, 0], drag=0.25, rdrag=1.2),
            **C_coll(radius, rest=rest, drag=cdrag, events=events)}


def e_gore_chunks():
    S = VC("size", 1, 0.2, 4)
    SPR = VC("spread", 0.15, 0, 2)
    c = GORE.sets["chunk"]
    effect("gore_chunks", GORE, MAT_ALPHA, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 6, 1, 24)}), 1, 24)"),
        **C_sphere(f"0.02 + {SPR}", [RND(-1, 1), RND(0.2, 1.3), RND(-1, 1)]),
        **C_speed(f"(2.0 + 3.5 * {R1}) * {VC('speed', 0.8, 0.05, 3)}"),
        **C_life(f"3.5 + 2.0 * {R2}"),
        **C_spin(RND(0, 360), f"({R3} - 0.5) * 900"),
        **_solid_motion(0.35, 6, 0.06, [{"event": "land", "min_speed": 2.5}]),
        **C_bb([f"(0.07 + 0.1 * {R4}) * {S}"] * 2, "lookat_xyz",
               UV(GORE, pick(GORE, "chunk", FR(R2, 7.3)), c.y, c.fw, c.fh)),
        **C_tint(1, 1, 1, fade(5)),
        **LIGHT,
    }, {"land": ev_decals([(1, 0.25), (0.5, 0.35)], 40, 2)}, "回転して飛び、跳ねて転がる肉片")


def e_bone_shards():
    b = GORE.sets["bone"]
    effect("bone_shards", GORE, MAT_ALPHA, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 5, 1, 16)}), 1, 16)"),
        **C_sphere(0.08, [RND(-1, 1), RND(0.1, 1.2), RND(-1, 1)]),
        **C_speed(f"(3.0 + 4.0 * {R1}) * {VC('speed', 0.8, 0.05, 3)}"),
        **C_life(f"3.0 + 1.5 * {R2}"),
        **C_spin(RND(0, 360), f"({R3} - 0.5) * 1400"),
        **_solid_motion(0.45, 4, 0.04),
        **C_bb([f"0.06 + 0.06 * {R4}"] * 2, "lookat_xyz", UV(GORE, pick(GORE, "bone", FR(R2, 5.7)), b.y, b.fw, b.fh)),
        **C_tint(1, 1, 1, fade(5)),
        **LIGHT,
    }, note="白い骨片（よく跳ねる）")


def e_brain_matter():
    b = GORE.sets["brain"]
    effect("brain_matter", GORE, MAT_ALPHA, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 4, 1, 14)}), 1, 14)"),
        **C_sphere(0.1, [RND(-1, 1), RND(0.2, 1.2), RND(-1, 1)]),
        **C_speed(f"(1.5 + 3.0 * {R1}) * {VC('speed', 0.8, 0.05, 3)}"),
        **C_life(f"3.5 + 1.5 * {R2}"),
        **C_spin(RND(0, 360), f"({R3} - 0.5) * 500"),
        **_solid_motion(0.1, 9, 0.05, [{"event": "land", "min_speed": 2}]),
        **C_bb([f"0.07 + 0.06 * {R4}"] * 2, "lookat_xyz", UV(GORE, pick(GORE, "brain", FR(R2, 3.9)), b.y, b.fw, b.fh)),
        **C_tint(1, 1, 1, fade(5)),
        **LIGHT,
    }, {"land": ev_decals([(1, 0.2)], 40, 2)}, "脳の欠片（べちゃっと止まる）")


def e_gut_strands():
    g = GORE.sets["gut"]
    effect("gut_strands", GORE, MAT_ALPHA, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 4, 1, 12)}), 1, 12)"),
        **C_sphere(0.1, [RND(-1, 1), RND(0.0, 1.0), RND(-1, 1)]),
        **C_speed(f"(1.2 + 2.0 * {R1}) * {VC('speed', 0.8, 0.05, 3)}"),
        **C_life(f"4.0 + 1.5 * {R2}"),
        **C_dyn(acc=[0, -14, 0], drag=0.8),
        **C_coll(0.05, rest=0.05, drag=10, events=[{"event": "land", "min_speed": 2}]),
        **C_bb([f"(0.18 + 0.12 * {R4})", f"(0.09 + 0.06 * {R4})"], "lookat_direction",
               UV(GORE, pick(GORE, "gut", FR(R2, 4.3)), g.y, g.fw, g.fh), ("velocity", 0.2)),
        **C_tint(1, 1, 1, fade(5)),
        **LIGHT,
    }, {"land": ev_decals([(1, 0.25)], 40, 1)}, "糸を引く腸の切れ端（速さの向きに伸びる）")


def _gore_mix(S, droplets, chunks, bones, brains, guts):
    """液 + 固形の混ぜ物の種類（R1 の境目）。各引数はその種類の割合。"""
    cases, acc = [], 0.0
    for frac, k in ((droplets, k_drop(f"(0.045 + 0.05 * {R3}) * {S}")),
                    (chunks, k_sprite(GORE, "chunk", f"(0.09 + 0.09 * {R3}) * {S}")),
                    (bones, k_sprite(GORE, "bone", f"(0.07 + 0.06 * {R3}) * {S}")),
                    (brains, k_sprite(GORE, "brain", f"(0.08 + 0.07 * {R3}) * {S}")),
                    (guts, k_sprite(GORE, "gut", f"(0.09 + 0.05 * {R3}) * {S}"))):
        if frac <= 0:
            continue
        acc += frac
        cases.append((round(acc, 4), k))
    jets = 1.0 - acc
    if jets > 1e-6:
        cases.append((None, k_sprite(GORE, "jet", f"(0.12 + 0.06 * {R3}) * {S}")))
    else:
        cases[-1] = (None, cases[-1][1])
    return mixk(R1, cases), droplets, round(acc, 4)


def _gore_composite(name, n_expr, S, mix, speeds, lifes, dir_bias, spread_r, note):
    k, dfrac, sfrac = mix
    has_jet = sfrac < 0.9999
    life = [(dfrac, f"{lifes[0]} + 0.6 * {R4}")] + ([(sfrac, f"{lifes[1]} + 1.5 * {R4}"), (None, f"0.45 + 0.25 * {R4}")]
                                                   if has_jet else [(None, f"{lifes[1]} + 1.5 * {R4}")])
    rot = [(dfrac, 0)] + ([(sfrac, RND(0, 360)), (None, 0)] if has_jet else [(None, RND(0, 360))])
    rate = [(dfrac, 0)] + ([(sfrac, f"({R3} - 0.5) * 900"), (None, 0)] if has_jet else
                           [(None, f"({R3} - 0.5) * 900")])
    effect(name, GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(n_expr),
        **C_sphere(f"{spread_r} * {S}", [f"{V('dx', 0)} * {dir_bias} + math.random(-1, 1)",
                                         f"{V('dy', 0.3)} * {dir_bias} + math.random(-0.4, 1.2)",
                                         f"{V('dz', 0)} * {dir_bias} + math.random(-1, 1)"] if dir_bias else
                   [RND(-1, 1), RND(-0.3, 1.3), RND(-1, 1)]),
        **C_speed(f"({speeds[0]} + {speeds[1]} * {R2}) * (0.8 + 0.2 * {S})"),
        **C_life(sel(R1, life)),
        **C_spin(sel(R1, rot), sel(R1, rate)),
        **C_dyn(acc=[0, GRAV, 0], drag=sel(R1, [(dfrac, 0.5), (None, 0.3)]), rdrag=1.0),
        **C_coll(0.04, rest=0.25, drag=5, events=[{"event": "land", "min_speed": 2}]),
        **bb_k(k, "lookat_direction", GORE, ("velocity", 0.05)),
        **C_tint(1, f"1.0 - 0.2 * {T}", f"1.0 - 0.2 * {T}", fade(5)),
        **LIGHT,
    }, {"land": ev_decals([(3, 0.24), (1.5, 0.4), (0.5, 0.6)], 45, 4)}, note)


def e_head_explode():
    S = VC("size", 1, 0.3, 3)
    _gore_composite("head_explode", f"math.clamp(math.round(64 * {G_}), 0, 64)", S,
                    _gore_mix(S, 0.5, 0.18, 0.12, 0.12, 0.0), (3.0, 5.0), (1.0, 3.0), 1.3, 0.12,
                    "頭が弾ける（滴・肉片・骨・脳・液の塊）。打たれた向きに偏る")


def e_sever_burst():
    S = VC("size", 1, 0.3, 3)
    _gore_composite("sever_burst", f"math.clamp(math.round(10 + 26 * {G_}), 0, 40)", S,
                    _gore_mix(S, 0.75, 0.1, 0.0, 0.0, 0.0), (2.0, 4.0), (0.8, 2.5), 1.6, 0.06,
                    "切断の瞬間の断面からの飛沫")


def e_body_explode():
    S = VC("size", 1, 0.3, 3)
    _gore_composite("body_explode", f"math.clamp(math.round(20 + 52 * {G_}), 0, 72)", S,
                    _gore_mix(S, 0.4, 0.24, 0.1, 0.06, 0.1), (3.0, 7.0), (1.2, 3.5), 0.0, 0.4,
                    "全身が弾け飛ぶ（全方向）")


def e_hit_flesh():
    k = mixk(R1, [(0.85, k_drop(f"0.035 + 0.035 * {R3}")),
                  (None, k_sprite(GORE, "mist", f"0.18 + 0.12 * {R3}"))])
    J = 0.55
    effect("hit_flesh", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(8),
        **C_point(direction=[f"{V('dx', 0)} + math.random(-{J}, {J})", f"{V('dy', 0.3)} + math.random(-{J}, {J})",
                             f"{V('dz', 0)} + math.random(-{J}, {J})"]),
        **C_speed(f"1.5 + 2.5 * {R2}"),
        **C_life(sel(R1, [(0.85, f"0.5 + 0.3 * {R4}"), (None, 0.35)])),
        **C_dyn(acc=[0, sel(R1, [(0.85, -14), (None, -1)]), 0], drag=sel(R1, [(0.85, 0.8), (None, 4)])),
        **C_coll(0.03, expire=True),
        **bb_k(k, "lookat_direction", GORE, ("velocity", 0.05)),
        **C_tint(1, 1, 1, sel(R1, [(0.85, fade(5)), (None, f"0.6 * (1.0 - {T})")])),
        **LIGHT,
    }, note="肉に当たった小さな飛沫")


# エンティティ（ロケータ）に付いて出ているか（公式: v.entity_scale は付いているときだけ実体の大きさ）。
# 付いているとき（アニメコントローラの状態の particle_effects）は状態の間ずっと、
# スクリプトの spawnParticle で出たときは短い時間で終わる（ループの取り残しを作らない）。
ATT = "((v.entity_scale ?? 0) > 0)"
# スクリプトは必ず渡し、アニメの状態からは渡されない変数で「状態に付いた連続の出し方」を見分ける
CONT_COUNT = "((v.count ?? -1) < 0)"
CONT_SIZE = "((v.size ?? -1) < 0)"


def C_lifeexpr(expire):
    return {"minecraft:emitter_lifetime_expression": {"activation_expression": 1, "expiration_expression": expire}}


def k_fx(name, w, r=R4, aspect=None):
    return k_sprite(FX, name, w, r, aspect)


def flame_uv(r=R1):
    return UVF(FX, ["flame", "flame2"], r, fps=12, stretch=True, loop=False)


SMOKE_U = lambda r: pick(FX, "smoke", r)  # noqa: E731


def smoke_bb(size_expr, r):
    s = FX.sets["smoke"]
    return C_bb([size_expr, size_expr], "lookat_xyz", UV(FX, SMOKE_U(r), s.y, s.fw, s.fh))


def e_hit_spark():
    J = 0.6
    k = mixk(R1, [(0.1, k_fx("glow", "0.35", R4)),
                  (None, (f"0.1 + 0.12 * {R3}", "0.03", pick(FX, "spark_s", R4), FX.sets["spark_s"].y, 32, 8))])
    effect("hit_spark", FX, MAT_ADD, {
        **C_once(),
        **C_instant(12),
        **C_point(direction=[f"{V('dx', 0)} + math.random(-{J}, {J})", f"{V('dy', 0.3)} + math.random(-{J}, {J})",
                             f"{V('dz', 0)} + math.random(-{J}, {J})"]),
        **C_speed(sel(R1, [(0.1, 0), (None, f"4.0 + 5.0 * {R2}")])),
        **C_life(sel(R1, [(0.1, 0.07), (None, f"0.18 + 0.22 * {R3}")])),
        **C_dyn(acc=[0, -14, 0], drag=1.5),
        **C_coll(0.02, rest=0.5, drag=2),
        **bb_k(k, "lookat_direction", FX, ("velocity", 0.05)),
        **C_tint(1, f"1.0 - 0.45 * {T}", f"0.75 - 0.65 * {T}", fade(2.5)),
    }, note="装甲・金属に当たった火花（跳ねる）")


def e_burn_flesh():
    S = VC("size", 1, 0.2, 4)
    effect("burn_flesh", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(6 + 4 * {S}), 3, 14)"),
        **C_sphere(f"0.25 * {S}", [RND(-0.3, 0.3), 1, RND(-0.3, 0.3)]),
        **C_speed(f"0.4 + 0.6 * {R2}"),
        **C_life(f"1.2 + 0.8 * {R3}"),
        **C_dyn(acc=[f"({R4} - 0.5) * 0.6", 0.9, f"({FR(R4, 3.3)} - 0.5) * 0.6"], drag=1.4),
        **C_spin(RND(0, 360), RND(-30, 30)),
        **smoke_bb(f"(0.22 + 0.15 * {R4}) * {S} * (1.0 + 1.8 * {T})", FR(R1, 7.0)),
        **C_tint(f"0.42 + 0.14 * {T}", f"0.37 + 0.16 * {T}", f"0.33 + 0.18 * {T}", f"0.55 * {fade_io(6, 1.3)}"),
        **LIGHT,
        **C_events(creation=["embers"]),
    }, {"embers": ev_effect("nr:ember_trail")}, "焼ける肉の煙（茶灰）+ 火の粉（子: ember_trail）")


def e_char_flakes():
    S = VC("size", 1, 0.2, 4)
    a = FX.sets["ash"]
    effect("char_flakes", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 8, 1, 32)}), 1, 32)"),
        **C_sphere(f"0.25 * {S}", [RND(-1, 1), RND(0.2, 1.0), RND(-1, 1)]),
        **C_speed(f"0.4 + 1.1 * {R2}"),
        **C_life(f"2.0 + 1.5 * {R3}"),
        **C_dyn(acc=[f"({R4} - 0.5) * 0.8", -1.4, f"({FR(R4, 5.1)} - 0.5) * 0.8"], drag=1.8),
        **C_coll(0.02, rest=0, drag=10),
        **C_spin(RND(0, 360), f"({R1} - 0.5) * 240"),
        **C_bb([f"(0.05 + 0.05 * {R4}) * {S}"] * 2, "lookat_xyz", UV(FX, pick(FX, "ash", FR(R2, 3.7)), a.y, 16, 16)),
        **C_tint(1, 1, 1, fade(3)),
        **LIGHT,
    }, note="炭化した体が崩れる灰（燠が混じる）")


def e_fire_burst():
    S = VC("size", 1, 0.2, 4)
    effect("fire_burst", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(10 + 6 * {S}), 6, 28)"),
        **C_sphere(f"0.3 * {S}", "outwards"),
        **C_speed(f"(1.0 + 1.5 * {R2}) * math.sqrt({S})"),
        **C_life(f"0.45 + 0.35 * {R3}"),
        **C_dyn(acc=[0, 2.5, 0], drag=2),
        **C_spin(f"({R4} - 0.5) * 30", 0),
        **C_bb([f"(0.35 + 0.3 * {R4}) * {S} * (0.7 + 0.6 * math.sin({T} * 180))"] * 2, "lookat_xyz", flame_uv()),
        **C_tint(1, 1, 1, fade(4)),
    }, note="着火の炎（ぼっと広がる）")


def e_ground_fire():
    r = VC("radius", 1.5, 0.3, 4)
    LF = VC("life", 6, 0.5, 60)
    timeline = {}
    t = 0.0
    while t <= 60.0 + 1e-6:
        timeline[n(round(t, 2))] = ["smoke", "embers"] if int(round(t / 1.5)) % 2 == 0 else ["smoke"]
        t += 1.5
    effect("ground_fire", FX, MAT_ADD, {
        **C_once(LF),
        **C_steady(f"math.clamp(6 + 14 * {r} * {r}, 6, 60)", f"math.clamp(12 + 18 * {r}, 12, 80)"),
        **C_disc(r, [0, 1, 0]),
        **C_speed(f"0.3 + 0.5 * {R2}"),
        **C_life(f"0.6 + 0.5 * {R3}"),
        **C_dyn(acc=[0, 2.2, 0], drag=1.5),
        **C_spin(f"({R4} - 0.5) * 24", 0),
        **C_bb([f"(0.5 + 0.4 * {R4}) * (0.8 + 0.4 * math.sin({T} * 180))"] * 2, "lookat_xyz", flame_uv()),
        **C_tint(1, 1, 1, fade_io(6, 3)),
        # 煙と火の粉は 1.5 秒ごとに中心から（エミッタが生きている間だけ = v.life 秒）
        **C_events(timeline=timeline),
    }, {"smoke": ev_effect("nr:smoke_dark", "emitter", "v.size = 0.9; v.life = 2.5;"),
        "embers": ev_effect("nr:ember_trail")}, "地面で燃え続ける炎（半径 v.radius、v.life 秒）")


def e_explosion():
    S = VC("size", 1, 0.3, 4)
    fb = FX.sets["fireball"]
    fire = (f"(1.1 + 1.0 * {R4}) * {S} * (0.6 + 0.6 * math.sqrt({T}))", None,
            f"{fb.x} + math.min(math.floor({T} * {fb.n}), {fb.n - 1}) * {fb.fw}", fb.y, fb.fw, fb.fh)
    fire = (fire[0], fire[0]) + fire[2:]
    k = mixk(R1, [(0.32, fire), (0.75, k_fx("debris", f"(0.06 + 0.07 * {R4}) * math.sqrt({S})", FR(R3, 7.7))),
                  (None, k_fx("spark", f"0.08 + 0.06 * {R4}", FR(R3, 5.5)))])
    q = f"math.sqrt({S})"
    effect("explosion", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(30 * {q}) + 12, 16, 64)"),
        **C_sphere(f"0.5 * {S}", "outwards"),
        **C_speed(sel(R1, [(0.32, f"(0.8 + 2.0 * {R2}) * {q}"), (0.75, f"(5.0 + 9.0 * {R2}) * {q}"),
                           (None, f"(7.0 + 8.0 * {R2}) * {q}")])),
        **C_life(sel(R1, [(0.32, f"0.75 + 0.4 * {R3}"), (0.75, f"1.4 + 1.2 * {R3}"), (None, f"0.35 + 0.4 * {R3}")])),
        **C_dyn(acc=[0, sel(R1, [(0.32, 1.2), (None, -18)]), 0], drag=sel(R1, [(0.32, 3.0), (0.75, 0.35), (None, 1.2)])),
        **C_coll(0.05, rest=0.3, drag=4),
        **C_spin(RND(0, 360), sel(R1, [(0.32, RND(-40, 40)), (0.75, f"({R3} - 0.5) * 800"), (None, 0)])),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(1, sel(R1, [(0.75, 1), (None, 0.75)]), sel(R1, [(0.75, 1), (None, 0.4)]), fade(3)),
    }, note="爆発（火の玉のコマ・瓦礫・火花）")


def e_smoke_dark():
    S = VC("size", 1, 0.2, 4)
    LF = VC("life", 2, 0.2, 10)
    c = f"(0.12 + 0.12 * {T})"
    effect("smoke_dark", FX, MAT_BLEND, {
        **C_once(f"{LF} * 0.5"),
        **C_steady(f"8 + 6 * {S}", 32),
        **C_sphere(f"0.3 * {S}", [RND(-0.3, 0.3), 1, RND(-0.3, 0.3)]),
        **C_speed(f"0.4 + 0.6 * {R2}"),
        **C_life(f"(1.4 + 1.0 * {R3}) * math.sqrt(math.clamp({LF} / 2.0, 0.5, 2.5))"),
        **C_dyn(acc=[f"({R4} - 0.5) * 0.6", 0.9, f"({FR(R4, 3.1)} - 0.5) * 0.6"], drag=1.2),
        **C_spin(RND(0, 360), RND(-25, 25)),
        **smoke_bb(f"(0.4 + 0.3 * {R4}) * {S} * (1.0 + 1.6 * {T})", FR(R1, 6.1)),
        **C_tint(c, f"{c} * 0.95", f"{c} * 0.92", f"0.8 * {fade_io(5, 1.2)}"),
        **LIGHT,
    }, note="黒煙（v.life の半分の間出し続ける）")


def e_shock_arcs():
    S = VC("size", 1, 0.3, 3)
    a = FX.sets["arc"]
    effect("shock_arcs", FX, MAT_ADD, {
        # スクリプトは必ず v.size を渡す → 0.45 秒。アニメの状態（感電。変数なし）からは状態の間（最長 8 秒）
        **C_lifeexpr(f"{EAGE} > ({CONT_SIZE} ? 8.0 : 0.45)"),
        **C_steady(f"10 + 8 * {S}", 10),
        **C_sphere(f"0.55 * {S}", "outwards", surface=True),
        **C_speed(0),
        **C_life(f"0.08 + 0.14 * {R2}"),
        **C_spin(RND(0, 360), 0),
        **C_bb([f"(0.5 + 0.4 * {R3}) * {S}"] * 2, "lookat_xyz",
               UV(FX, f"{a.x} + math.mod(math.floor({R4} * 8 + {AGE} * 30), 8) * {a.fw}", a.y, a.fw, a.fh)),
        **C_tint(0.6, 0.82, 1.0, f"(0.65 + 0.35 * math.sin({AGE} * 2400 + {R1} * 360)) * {fade(2)}"),
    }, note="体のまわりの放電（ちらつく。状態に付けば状態の間、スクリプトなら 0.45 秒）")


def e_shock_spark():
    effect("shock_spark", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"math.clamp(math.round({VC('count', 8, 1, 24)}), 1, 24)"),
        **C_sphere(0.15, [RND(-1, 1), RND(-0.2, 1.2), RND(-1, 1)]),
        **C_speed(f"3.0 + 5.0 * {R2}"),
        **C_life(f"0.2 + 0.3 * {R3}"),
        **C_dyn(acc=[0, -12, 0], drag=1.2),
        **C_coll(0.02, rest=0.5, drag=2),
        **C_bb([f"0.1 + 0.1 * {R4}", "0.028"], "lookat_direction",
               UV(FX, pick(FX, "spark_s", R1), FX.sets["spark_s"].y, 32, 8), ("velocity", 0.05)),
        **C_tint(0.7, 0.86, 1.0, fade(2.5)),
    }, note="感電の火花の弾け")


def e_toxic_gas():
    r = VC("radius", 1.5, 0.2, 5)
    LF = VC("life", 3, 0.3, 30)
    effect("toxic_gas", FX, MAT_BLEND, {
        **C_once(LF),
        **C_steady(f"math.clamp(4 + 8 * {r} * {r}, 4, 30)", f"math.clamp(10 + 14 * {r}, 10, 64)"),
        **C_disc(r, [RND(-0.3, 0.3), RND(0.2, 0.6), RND(-0.3, 0.3)], offset=[0, 0.3, 0]),
        **C_speed(f"0.2 + 0.3 * {R2}"),
        **C_life(f"2.0 + 1.2 * {R3}"),
        **C_dyn(acc=[f"({R4} - 0.5) * 0.3", 0.05, f"({FR(R4, 2.9)} - 0.5) * 0.3"], drag=1.0),
        **C_spin(RND(0, 360), RND(-20, 20)),
        **smoke_bb(f"(0.5 + 0.4 * {R4}) * (0.6 + 0.4 * math.sqrt({r})) * (1.0 + 1.1 * {T})", FR(R1, 4.7)),
        **C_tint(0.42, 0.8, 0.22, f"0.55 * {fade_io(4, 1.6)}"),
        **LIGHT,
    }, note="緑の毒ガスの雲（半径 v.radius、v.life 秒）")


def e_toxic_burst():
    S = VC("size", 1, 0.2, 4)
    wd, pl = GORE.sets["wdrop"], GORE.sets["pale"]
    k = mixk(R1, [(0.6, (f"(0.05 + 0.05 * {R3}) * {S}", f"(0.05 + 0.05 * {R3}) * {S}", pick(GORE, "wdrop", R4), wd.y, 16, 16)),
                  (None, (f"(0.08 + 0.09 * {R3}) * {S}", f"(0.08 + 0.09 * {R3}) * {S}", pick(GORE, "pale", R4), pl.y, 32, 32))])
    effect("toxic_burst", GORE, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(20 + 16 * {S}), 8, 56)"),
        **C_sphere(f"0.3 * {S}", [RND(-1, 1), RND(-0.1, 1.2), RND(-1, 1)]),
        **C_speed(f"(2.5 + 5.0 * {R2}) * math.sqrt({S})"),
        **C_life(sel(R1, [(0.6, f"0.9 + 0.6 * {R4}"), (None, f"2.5 + 1.5 * {R4}")])),
        **C_spin(sel(R1, [(0.6, 0), (None, RND(0, 360))]), sel(R1, [(0.6, 0), (None, f"({R3} - 0.5) * 700")])),
        **C_dyn(acc=[0, GRAV, 0], drag=0.45, rdrag=1.0),
        **C_coll(0.04, rest=0.2, drag=6),
        **bb_k(k, "lookat_xyz", GORE),
        **C_tint(sel(R1, [(0.6, 0.55), (None, 0.62)]), sel(R1, [(0.6, 0.85), (None, 0.78)]),
                 sel(R1, [(0.6, 0.18), (None, 0.3)]), fade(4)),
        **LIGHT,
        **C_events(creation=["gas"]),
    }, {"gas": ev_effect("nr:toxic_gas", "emitter", "v.radius = 0.9; v.life = 1.8;")},
        "膨れた感染者が破裂する（緑の滴・肉片 + 子: toxic_gas）")


def e_acid_spit_trail():
    k = mixk(R1, [(0.7, k_fx("wdrop", f"0.05 + 0.04 * {R3}", R4)), (None, k_fx("glow", "0.22", R4))])
    effect("acid_spit_trail", FX, MAT_ADD, {
        **C_once(),
        **C_instant(3),
        **C_sphere(0.05, [RND(-0.3, 0.3), RND(-0.3, 0.3), RND(-0.3, 0.3)]),
        **C_speed(f"0.3 + 0.4 * {R2}"),
        **C_life(f"0.3 + 0.25 * {R3}"),
        **C_dyn(acc=[0, -4, 0], drag=1.5),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(0.55, 1.0, 0.25, sel(R1, [(0.7, fade(2)), (None, f"0.35 * (1.0 - {T})")])),
    }, note="酸の唾の軌跡（光る緑の滴）")


def e_acid_splash():
    r = VC("radius", 1.0, 0.2, 4)
    LF = VC("life", 2.5, 0.3, 30)
    gl, bu = FX.sets["glow"], FX.sets["bubble"]
    puddle = (f"(0.5 + 0.4 * {R4}) * math.sqrt({r})", None, gl.x, gl.y, gl.fw, gl.fh)
    puddle = (puddle[0], puddle[0]) + puddle[2:]
    bubble = (f"(0.05 + 0.1 * {R4}) * math.clamp({T} * 1.3, 0.0, 1.0)", None, pick(FX, "bubble", R3), bu.y, 16, 16)
    bubble = (bubble[0], bubble[0]) + bubble[2:]
    k = mixk(R1, [(0.3, puddle), (None, bubble)])
    effect("acid_splash", FX, MAT_ADD, {
        **C_once(LF),
        **C_steady(f"({EAGE} < 0.1 ? 120 : 6 + 10 * {r} * {r})", f"math.clamp(14 + 20 * {r}, 14, 72)"),
        **C_disc(r, [0, 1, 0], offset=[0, 0.02, 0]),
        **C_speed(0),
        **C_life(sel(R1, [(0.3, f"math.max(v.emitter_lifetime - {EAGE}, 0.3)"), (None, f"0.4 + 0.5 * {R2}")])),
        **C_spin(RND(0, 360), 0),
        **bb_k(k, "emitter_transform_xz", FX),
        **C_tint(sel(R1, [(0.3, 0.45), (None, 0.7)]), 1.0, sel(R1, [(0.3, 0.2), (None, 0.4)]),
                 sel(R1, [(0.3, f"0.45 * {fade_io(8, 4)}"), (None, f"0.9 * {fade(1.5)}")])),
    }, note="酸の飛び散り（地面に光る水たまりと泡。平ら）")


def e_fungal_spores():
    r = VC("radius", 1.5, 0.2, 5)
    effect("fungal_spores", FX, MAT_BLEND, {
        **C_once(4),
        **C_steady(f"math.clamp(5 + 6 * {r}, 5, 30)", 48),
        **C_sphere(r, "outwards", offset=[0, 0.5, 0]),
        **C_speed(f"0.05 + 0.15 * {R2}"),
        **C_life(f"3.0 + 2.0 * {R3}"),
        **C_dyn(acc=[f"math.sin({AGE} * 90 + {R1} * 360) * 0.3", 0.05, f"math.cos({AGE} * 90 + {R1} * 360) * 0.3"],
                drag=0.6),
        **C_bb([f"0.04 + 0.04 * {R4}"] * 2, "lookat_xyz", UV(FX, pick(FX, "spore", R4), FX.sets["spore"].y, 16, 16)),
        **C_tint(0.8, 0.85, 0.45, fade_io(4, 3)),
        **LIGHT,
    }, note="菌の胞子が漂う（4 秒）")


def e_uv_glow():
    r = VC("radius", 1.0, 0.2, 5)
    k = mixk(R1, [(0.55, k_fx("glow", f"(0.6 + 0.6 * {R3}) * math.sqrt({r})", R4)),
                  (None, k_fx("spore", f"0.04 + 0.04 * {R3}", R4))])
    effect("uv_glow", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(4 + 3 * {r}), 4, 16)"),
        **C_sphere(r, "outwards"),
        **C_speed(sel(R1, [(0.55, 0.05), (None, f"0.1 + 0.2 * {R2}")])),
        **C_life(f"0.6 + 0.6 * {R2}"),
        **C_dyn(acc=[0, 0.1, 0], drag=1.0),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(0.55, 0.32, 1.0, sel(R1, [(0.55, f"0.22 * {fade_io(3, 2)}"), (None, f"0.8 * {fade_io(4, 2)}")])),
    }, note="UV の青紫の光の靄（と漂う粒）")


def e_uv_burn():
    S = VC("size", 1, 0.2, 4)
    k = mixk(R1, [(0.7, k_fx("smoke", f"(0.2 + 0.15 * {R3}) * {S} * (1.0 + 1.5 * {T})", R4)),
                  (None, k_fx("spark", f"0.06 + 0.05 * {R3}", R4))])
    effect("uv_burn", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(8 + 4 * {S}), 4, 18)"),
        **C_sphere(f"0.3 * {S}", [RND(-0.4, 0.4), 1, RND(-0.4, 0.4)]),
        **C_speed(sel(R1, [(0.7, f"0.6 + 0.6 * {R2}"), (None, f"1.0 + 1.5 * {R2}")])),
        **C_life(sel(R1, [(0.7, f"0.9 + 0.6 * {R2}"), (None, f"0.25 + 0.2 * {R2}")])),
        **C_dyn(acc=[0, 1.4, 0], drag=1.3),
        **C_spin(RND(0, 360), RND(-40, 40)),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(sel(R1, [(0.7, 0.46), (None, 0.85)]), sel(R1, [(0.7, 0.4), (None, 0.65)]), sel(R1, [(0.7, 0.56), (None, 1.0)]),
                 sel(R1, [(0.7, f"0.6 * {fade_io(6, 1.3)}"), (None, fade(2))])),
    }, note="UV で焼かれる（紫がかった煙とはぜる粒）")


def e_uv_cone():
    g = FX.sets["glow"]
    dist = f"(0.4 + 5.5 * {R1})"
    J = f"{dist} * 0.18"
    effect("uv_cone", FX, MAT_ADD, {
        **C_once(),
        **C_instant(12),
        **C_point(offset=[f"{V('dx', 0)} * {dist} + math.random(-1, 1) * {J}",
                          f"{V('dy', 0)} * {dist} + math.random(-1, 1) * {J}",
                          f"{V('dz', 1)} * {dist} + math.random(-1, 1) * {J}"]),
        **C_life(0.2),
        **C_bb([f"0.15 + 0.5 * {dist}"] * 2, "lookat_xyz", UV(FX, g.x, g.y, g.fw, g.fh)),
        **C_tint(0.5, 0.35, 1.0, f"(0.16 - 0.018 * {dist}) * {fade_io(6, 3)}"),
    }, note="UV ライトの円錐（向き v.dx/dy/dz に沿って広がる光）")


def e_scream_wave():
    r = VC("radius", 3, 0.5, 12)
    rg = FX.sets["ring"]
    effect("scream_wave", FX, MAT_BLEND, {
        **C_once(0.5),
        **C_steady(6, 3),
        **C_point(),
        **C_life(0.7),
        **C_bb([f"0.3 + 2.0 * {r} * (1.0 - math.pow(1.0 - {T}, 2.5))"] * 2, "lookat_xyz",
               UV(FX, rg.x, rg.y, rg.fw, rg.fh)),
        **C_tint(0.88, 0.8, 0.7, f"0.55 * (1.0 - {T})"),
    }, note="叫びの波紋（広がる輪 3 つ）")


def e_shockwave_ground():
    r = VC("radius", 3, 0.5, 10)
    rg = FX.sets["ring"]
    effect("shockwave_ground", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(offset=[0, 0.05, 0]),
        **C_life(0.45),
        **C_bb([f"0.4 + 2.0 * {r} * (1.0 - math.pow(1.0 - {T}, 2.2))"] * 2, "emitter_transform_xz",
               UV(FX, rg.x + rg.fw, rg.y, rg.fw, rg.fh)),
        **C_tint(0.86, 0.8, 0.7, f"0.75 * (1.0 - {T})"),
        **LIGHT,
        **C_events(creation=["dust", "chips"]),
    }, {"dust": ev_effect("nr:dust_land", "emitter", "v.size = 1.8;"),
        "chips": ev_effect("nr:impact_dust")}, "地面を叩く衝撃の輪（平ら）+ 土煙と瓦礫（子）")


def e_revenant_aura():
    S = VC("size", 1, 0.3, 3)
    ss = FX.sets["spark_s"]
    effect("revenant_aura", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(10 * {S}), 4, 24)"),
        **C_sphere(f"0.6 * {S}", [RND(-0.3, 0.3), 1, RND(-0.3, 0.3)]),
        **C_speed(f"0.5 + 0.7 * {R2}"),
        **C_life(f"0.8 + 0.6 * {R3}"),
        **C_dyn(acc=[f"math.cos({AGE} * 540 + {R1} * 360) * 2.0", 0.8, f"math.sin({AGE} * 540 + {R1} * 360) * 2.0"],
                drag=0.8),
        **C_bb([f"0.16 + 0.1 * {R4}", "0.035"], "lookat_direction", UV(FX, pick(FX, "spark_s", R4), ss.y, 32, 8),
               ("velocity", 0.05)),
        **C_tint(0.3, 1.0, 0.85, fade_io(5, 2)),
        **C_events(creation=["murk"]),
    }, {"murk": ev_effect("nr:smoke_dark", "emitter", "v.size = 0.6; v.life = 1.4;")},
        "青緑の光の筋が渦を巻いて昇る + 黒い靄（子: smoke_dark）")


def e_night_eyes():
    e = FX.sets["eyes"]
    effect("night_eyes", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.55),
        **C_bb(["0.36", "0.18"], "lookat_xyz", UV(FX, pick(FX, "eyes", R1), e.y, e.fw, e.fh)),
        **C_tint(1, 0.85, 0.8, fade_io(10, 3)),
    }, note="夜の捕食者の光る目の残光")


def _dust(name, comps_extra, n_expr, note, life="0.6 + 0.5 * v.particle_random_3", size="(0.25 + 0.2 * v.particle_random_4)",
          grow=1.6, alpha=0.55, events=None):
    effect(name, FX, MAT_BLEND, {
        **C_once(),
        **C_instant(n_expr),
        **comps_extra,
        **C_life(life),
        **C_spin(RND(0, 360), RND(-30, 30)),
        **smoke_bb(f"{size} * (1.0 + {grow} * math.pow({T}, 0.7))", FR(R1, 5.9)),
        **C_tint(0.62, 0.57, 0.5, f"{alpha} * math.pow(1.0 - {T}, 1.2)"),
        **LIGHT,
    }, events, note)


def e_dust_land():
    S = VC("size", 1, 0.2, 4)
    _dust("dust_land", {**C_disc(f"0.25 * {S}", "outwards"),
                        **C_speed(f"(1.2 + 1.4 * {R2}) * math.sqrt({S})"),
                        **C_dyn(acc=[0, 0.4, 0], drag=3.5)},
          f"math.clamp(math.round(8 + 6 * {S}), 4, 24)", "着地・落下物の土煙（地面に沿って広がる）",
          size=f"(0.25 + 0.2 * {R4}) * math.sqrt({S})")


def e_dust_slide():
    _dust("dust_slide", {**C_disc(0.25, [f"-{V('dx', 0)} * 0.8 + math.random(-0.4, 0.4)", RND(0.2, 0.5),
                                         f"-{V('dz', 1)} * 0.8 + math.random(-0.4, 0.4)"]),
                         **C_speed(f"1.0 + 1.2 * {R2}"),
                         **C_dyn(acc=[0, 0.3, 0], drag=3.0)},
          6, "スライディングの土煙（進む向き v.dx/dz の後ろへ）", life=f"0.5 + 0.4 * {R3}", size=f"(0.2 + 0.15 * {R4})")


def e_wall_scrape():
    k = mixk(R1, [(0.5, k_fx("smoke", f"(0.12 + 0.1 * {R3}) * (1.0 + 1.5 * {T})", R4)),
                  (None, k_fx("debris", f"0.04 + 0.04 * {R3}", R4))])
    effect("wall_scrape", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(6),
        **C_sphere(0.1, [RND(-1, 1), RND(-0.2, 0.6), RND(-1, 1)]),
        **C_speed(f"0.8 + 1.5 * {R2}"),
        **C_life(sel(R1, [(0.5, f"0.5 + 0.3 * {R3}"), (None, f"0.8 + 0.4 * {R3}")])),
        **C_dyn(acc=[0, sel(R1, [(0.5, 0.2), (None, -14)]), 0], drag=sel(R1, [(0.5, 3), (None, 0.5)])),
        **C_spin(RND(0, 360), RND(-200, 200)),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(0.66, 0.62, 0.56, sel(R1, [(0.5, f"0.45 * (1.0 - {T})"), (None, fade(4))])),
        **LIGHT,
    }, note="壁走り・壁登りの削れ（埃と小石）")


def e_speed_lines():
    ln = FX.sets["line"]
    effect("speed_lines", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(6),
        **C_sphere(1.4, [f"-{V('dx', 0)}", f"-{V('dy', 0)}", f"-{V('dz', 1)}"],
                   offset=[f"{V('dx', 0)} * 2.2", f"{V('dy', 0)} * 2.2", f"{V('dz', 1)} * 2.2"], surface=True),
        **C_speed(f"14 + 6 * {R2}"),
        **C_life(0.18),
        **C_bb([f"0.9 + 0.7 * {R3}", "0.03"], "lookat_direction", UV(FX, ln.x, ln.y, ln.fw, ln.fh), ("velocity", 0.05)),
        **C_tint(1, 1, 1, f"0.35 * {fade_io(5, 3)}"),
    }, note="全力疾走のスピード線（前方の殻から後ろへ流れる）")


def e_grapple_line():
    rp = FX.sets["rope"]
    effect("grapple_line", FX, MAT_ALPHA, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.12),
        **C_bb(["0.07", "0.07"], "lookat_xyz", UV(FX, rp.x, rp.y, rp.fw, rp.fh)),
        **LIGHT,
    }, note="フックのロープの点（スクリプトが線上に並べる。0.12 秒）")


def e_kick_impact():
    rg = FX.sets["ring"]
    ring = (f"0.2 + 1.0 * math.pow({T}, 0.5)", None, rg.x, rg.y, rg.fw, rg.fh)
    ring = (ring[0], ring[0]) + ring[2:]
    k = mixk(R1, [(0.12, ring), (0.7, k_fx("smoke", f"(0.2 + 0.12 * {R3}) * (1.0 + 1.3 * {T})", R4)),
                  (None, k_fx("debris", f"0.04 + 0.04 * {R3}", R4))])
    J = 0.45
    effect("kick_impact", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(12),
        **C_point(direction=[f"{V('dx', 0)} + math.random(-{J}, {J})", f"{V('dy', 0)} + math.random(-0.1, 0.5)",
                             f"{V('dz', 1)} + math.random(-{J}, {J})"]),
        **C_speed(sel(R1, [(0.12, 0), (0.7, f"2.0 + 2.0 * {R2}"), (None, f"2.5 + 2.5 * {R2}")])),
        **C_life(sel(R1, [(0.12, 0.25), (None, f"0.4 + 0.3 * {R3}")])),
        **C_dyn(acc=[0, sel(R1, [(0.7, 0.2), (None, -14)]), 0], drag=sel(R1, [(0.12, 0), (0.7, 4), (None, 0.6)])),
        **C_spin(RND(0, 360), sel(R1, [(0.7, 0), (None, RND(-300, 300))])),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(sel(R1, [(0.12, 1), (None, 0.66)]), sel(R1, [(0.12, 1), (None, 0.62)]), sel(R1, [(0.12, 1), (None, 0.56)]),
                 sel(R1, [(0.12, f"0.6 * (1.0 - {T})"), (0.7, f"0.5 * (1.0 - {T})"), (None, fade(4))])),
        **LIGHT,
    }, note="ドロップキックの衝撃（輪・埃・小石を打った向きへ）")


def e_muzzle_flash():
    S = VC("size", 1, 0.3, 3)
    f = FX.sets["flash"]
    effect("muzzle_flash", FX, MAT_ADD, {
        **C_once(),
        **C_instant(3),
        # 銃身の向きに沿って 3 つ（正面からは星、横からは伸びた炎に見える）
        **C_point(offset=[f"{V('dx', 0)} * (0.04 + 0.16 * {R1})", f"{V('dy', 0)} * (0.04 + 0.16 * {R1})",
                          f"{V('dz', 1)} * (0.04 + 0.16 * {R1})"]),
        **C_life(f"0.05 + 0.03 * {R2}"),
        **C_spin(RND(0, 360), 0),
        **C_bb([f"(0.38 - 0.22 * {R1}) * {S} * (1.0 - 0.3 * {T})"] * 2, "lookat_xyz",
               UV(FX, pick(FX, "flash", R3), f.y, f.fw, f.fh)),
        **C_tint(1, 0.92, 0.75, fade(3)),
    }, note="銃口の閃光（ごく短い）")


def e_bullet_tracer():
    ln = FX.sets["line"]
    effect("bullet_tracer", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(direction=[V("dx", 0), V("dy", 0), V("dz", 1)]),
        # v.speed は倍率（1 = 90 ブロック/秒）
        **C_speed(f"90 * {VC('speed', 1, 0.1, 4)}"),
        **C_life(0.15),
        **C_bb(["1.6", "0.06"], "lookat_direction", UV(FX, ln.x + ln.fw, ln.y, ln.fw, ln.fh), ("velocity", 0.05)),
        **C_tint(1, 0.85, 0.5, fade(3)),
    }, note="弾道の光の筋（v.speed は倍率。1 = 90 ブロック/秒）")


def e_impact_dust():
    k = mixk(R1, [(0.55, k_fx("smoke", f"(0.14 + 0.1 * {R3}) * (1.0 + 1.4 * {T})", R4)),
                  (None, k_fx("debris", f"0.035 + 0.04 * {R3}", R4))])
    effect("impact_dust", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(8),
        **C_sphere(0.08, [RND(-1, 1), RND(0.1, 1.2), RND(-1, 1)]),
        **C_speed(sel(R1, [(0.55, f"0.8 + 1.0 * {R2}"), (None, f"2.0 + 2.5 * {R2}")])),
        **C_life(sel(R1, [(0.55, f"0.5 + 0.4 * {R3}"), (None, f"0.7 + 0.5 * {R3}")])),
        **C_dyn(acc=[0, sel(R1, [(0.55, 0.3), (None, -15)]), 0], drag=sel(R1, [(0.55, 3), (None, 0.5)])),
        **C_coll(0.02, rest=0.3, drag=4),
        **C_spin(RND(0, 360), sel(R1, [(0.55, 0), (None, RND(-400, 400))])),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(0.64, 0.6, 0.54, sel(R1, [(0.55, f"0.5 * (1.0 - {T})"), (None, fade(4))])),
        **LIGHT,
    }, note="弾がブロックに当たった土埃と破片")


def e_swing_trail():
    sw = FX.sets["swing"]
    effect("swing_trail", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.14),
        **C_bb(["1.4", "0.7"], "lookat_direction", UV(FX, sw.x, sw.y, sw.fw, sw.fh),
               ("custom", [V("dx", 1), V("dy", 0), V("dz", 0)])),
        **C_tint(VC("cr", 1, 0, 1), VC("cg", 1, 0, 1), VC("cb", 1, 0, 1), f"0.85 * {fade(1.2)}"),
    }, note="近接武器の振りの軌跡（属性色 v.cr/cg/cb、向き v.dx/dy/dz）")


def e_shell_casing():
    c = FX.sets["casing"]
    effect("shell_casing", FX, MAT_ALPHA, {
        **C_once(),
        **C_instant(1),
        **C_point(direction=[f"{V('dx', 1)} + math.random(-0.2, 0.2)", f"{V('dy', 0)} + 0.9 + math.random(0, 0.3)",
                             f"{V('dz', 0)} + math.random(-0.2, 0.2)"]),
        **C_speed(f"2.5 + 1.0 * {R2}"),
        **C_life(2.5),
        **C_spin(RND(0, 360), f"({R3} < 0.5 ? -1 : 1) * (700 + 400 * {R4})"),
        **C_dyn(acc=[0, -18, 0], drag=0.2, rdrag=0.8),
        **C_coll(0.02, rest=0.45, drag=3),
        **C_bb(["0.08", "0.08"], "lookat_xyz", UV(FX, pick(FX, "casing", R1), c.y, c.fw, c.fh)),
        **C_tint(1, 1, 1, fade(5)),
        **LIGHT,
    }, note="排莢（真鍮の薬莢が跳ねて転がる）")


def e_arrow_trail():
    sp = FX.sets["spore"]
    effect("arrow_trail", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.25),
        **C_bb([f"0.05 + 0.03 * {T}"] * 2, "lookat_xyz", UV(FX, sp.x, sp.y, 16, 16)),
        **C_tint(1, 1, 1, f"0.35 * (1.0 - {T})"),
    }, note="矢・ボルトの細い風切りの尾")


def e_fuse_spark():
    ss = FX.sets["spark_s"]
    effect("fuse_spark", FX, MAT_ADD, {
        **C_once(),
        **C_instant(4),
        **C_point(direction=[RND(-1, 1), RND(0.2, 1.2), RND(-1, 1)]),
        **C_speed(f"1.0 + 1.5 * {R2}"),
        **C_life(f"0.15 + 0.15 * {R3}"),
        **C_dyn(acc=[0, -6, 0], drag=1.0),
        **C_bb([f"0.06 + 0.04 * {R4}", "0.02"], "lookat_direction", UV(FX, pick(FX, "spark_s", R4), ss.y, 32, 8),
               ("velocity", 0.05)),
        **C_tint(1, 0.8, 0.4, fade(2)),
    }, note="導火線の火花")


def e_firecracker_pop():
    pa, gl = FX.sets["paper"], FX.sets["glow"]
    flash = ("0.6", "0.6", gl.x + gl.fw, gl.y, gl.fw, gl.fh)
    paper = (f"0.04 + 0.03 * {R3}", f"0.04 + 0.03 * {R3}", pick(FX, "paper", R4), pa.y, pa.fw, pa.fh)
    k = mixk(R1, [(0.08, flash), (None, paper)])
    effect("firecracker_pop", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(14),
        **C_sphere(0.05, [RND(-1, 1), RND(-0.2, 1.2), RND(-1, 1)]),
        **C_speed(sel(R1, [(0.08, 0), (None, f"2.0 + 2.0 * {R2}")])),
        **C_life(sel(R1, [(0.08, 0.06), (None, f"1.0 + 0.6 * {R3}")])),
        **C_dyn(acc=[0, -8, 0], drag=2.5),
        **C_spin(RND(0, 360), RND(-500, 500)),
        **bb_k(k, "lookat_xyz", FX),
        **C_tint(1, sel(R1, [(0.08, 0.9), (None, 1)]), sel(R1, [(0.08, 0.6), (None, 1)]), fade(4)),
    }, note="爆竹のはじける閃光と赤い紙片")


def e_flame():
    S = VC("size", 1, 0.2, 4)
    effect("flame", FX, MAT_ADD, {
        **C_once(),
        **C_instant(3),
        **C_sphere(f"0.06 * {S}", [RND(-0.2, 0.2), 1, RND(-0.2, 0.2)]),
        **C_speed(f"0.2 + 0.3 * {R2}"),
        **C_life(f"0.35 + 0.25 * {R3}"),
        **C_dyn(acc=[0, 1.8, 0], drag=1.5),
        **C_spin(f"({R4} - 0.5) * 20", 0),
        **C_bb([f"(0.18 + 0.12 * {R4}) * {S}"] * 2, "lookat_xyz", flame_uv()),
        **C_tint(1, 1, 1, fade(4)),
    }, note="小さな炎（燃える布・ドラム缶・火炎の改造）")


def e_ember_trail():
    e = FX.sets["ember"]
    effect("ember_trail", FX, MAT_ADD, {
        **C_once(),
        **C_instant(4),
        **C_sphere(0.08, [RND(-0.5, 0.5), RND(0.3, 1.0), RND(-0.5, 0.5)]),
        **C_speed(f"0.3 + 0.7 * {R2}"),
        **C_life(f"0.4 + 0.5 * {R3}"),
        **C_dyn(acc=[f"({R4} - 0.5) * 1.2", 1.5, f"({FR(R4, 3.7)} - 0.5) * 1.2"], drag=1.0),
        **C_bb([f"0.03 + 0.02 * {R4}"] * 2, "lookat_xyz", UV(FX, pick(FX, "ember", R1), e.y, 8, 8)),
        **C_tint(1, f"0.75 + 0.25 * math.sin({AGE} * 1500 + {R1} * 360)", 0.6, fade(2)),
    }, note="火の粉の尾（ちらつきながら昇る）")


def e_toxic_drip():
    w = FX.sets["wdrop"]
    effect("toxic_drip", FX, MAT_BLEND, {
        **C_once(),
        **C_instant(f"(v.emitter_random_1 < 0.5 ? 1 : 2)"),
        **C_box([0.05, 0.02, 0.05], [0, -1, 0]),
        **C_speed(0.2),
        **C_life(0.8),
        **C_dyn(acc=[0, -14, 0], drag=0.3),
        **C_coll(0.02, expire=True),
        **C_bb([f"0.04 + 0.02 * {R4}"] * 2, "lookat_xyz", UV(FX, pick(FX, "wdrop", R1), w.y, 16, 16)),
        **C_tint(0.45, 0.9, 0.2, fade(5)),
        **LIGHT,
    }, note="毒の改造の緑の滴り")


def e_uv_trail():
    g = FX.sets["glow"]
    effect("uv_trail", FX, MAT_ADD, {
        **C_once(),
        **C_instant(3),
        **C_sphere(0.06, "outwards"),
        **C_speed(0.15),
        **C_life(f"0.3 + 0.2 * {R2}"),
        **C_bb([f"(0.08 + 0.06 * {R3}) * (1.0 - 0.6 * {T})"] * 2, "lookat_xyz", UV(FX, g.x + g.fw, g.y, g.fw, g.fh)),
        **C_tint(0.6, 0.35, 1.0, f"0.8 * (1.0 - {T})"),
    }, note="UV の改造の紫の光の尾")


def e_impact_ring():
    rg = FX.sets["ring"]
    effect("impact_ring", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.22),
        **C_bb([f"0.15 + 0.85 * math.pow({T}, 0.5)"] * 2, "direction_z", UV(FX, rg.x, rg.y, rg.fw, rg.fh),
               ("custom", [V("dx", 0), V("dy", 0), V("dz", 1)])),
        **C_tint(1, 1, 1, f"0.9 * (1.0 - {T})"),
    }, note="衝撃の改造の命中の白い輪（面が打った向き v.dx/dy/dz を向く）")


def e_dust_trail():
    _dust("dust_trail", {**C_sphere(0.05, "outwards"), **C_speed(f"0.2 + 0.3 * {R2}"), **C_dyn(acc=[0, 0.2, 0], drag=2.0)},
          2, "砂ぼこりの尾", life=f"0.5 + 0.3 * {R3}", size=f"(0.15 + 0.1 * {R4})", grow=1.3, alpha=0.4)


def e_loot_glint():
    s = FX.sets["star"]
    effect("loot_glint", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"(v.emitter_random_1 < 0.5 ? 1 : 2)"),
        **C_sphere(0.3, "outwards"),
        **C_speed(0),
        **C_life(0.6),
        **C_spin(RND(0, 360), RND(-90, 90)),
        **C_bb([f"(0.18 + 0.12 * {R2}) * math.sin({T} * 180)"] * 2, "lookat_xyz", UV(FX, pick(FX, "star", R3), s.y, 32, 32)),
        **C_tint(1, 0.95, 0.75, 0.9),
    }, note="落ちている物資のきらめき")


def e_safezone_ring():
    r = VC("radius", 6, 1, 32)
    g = FX.sets["glow"]
    effect("safezone_ring", FX, MAT_ADD, {
        **C_once(),
        **C_instant(f"math.clamp(math.round(6 * {r}), 8, 64)"),
        **C_disc(r, [0, 1, 0], offset=[0, 0.1, 0], surface=True),
        **C_speed(f"0.2 + 0.3 * {R2}"),
        **C_life(f"1.0 + 0.6 * {R3}"),
        **C_bb([f"0.15 + 0.1 * {R4}"] * 2, "lookat_xyz", UV(FX, g.x + g.fw, g.y, g.fw, g.fh)),
        **C_tint(0.6, 0.35, 1.0, fade_io(4, 2)),
    }, note="UV の安全地帯の境界（半径 v.radius の輪に昇る光の粒）")


def e_chase_marker():
    m = FX.sets["mark"]
    effect("chase_marker", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.55),
        **C_bb([f"0.45 + 0.1 * math.sin({AGE} * 720)"] * 2, "lookat_xyz", UV(FX, m.x, m.y, m.fw, m.fh)),
        **C_tint(1, 0.15, 0.1, f"0.85 * {fade_io(8, 3)}"),
    }, note="追ってくる夜の捕食者の頭上の赤い脈動")


def e_sense_ping():
    m = FX.sets["mark"]
    effect("sense_ping", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.6),
        **C_bb([f"0.35 + 0.15 * {T}"] * 2, "lookat_xyz", UV(FX, m.x + m.fw, m.y, m.fw, m.fh)),
        **C_tint(VC("cr", 1, 0, 1), VC("cg", 0.85, 0, 1), VC("cb", 0.3, 0, 1), fade_io(8, 2)),
    }, note="感知で見えた感染者の印（色 v.cr/cg/cb）")


def e_trap_spark():
    sp = FX.sets["spark"]
    effect("trap_spark", FX, MAT_ADD, {
        **C_once(),
        **C_instant(5),
        **C_sphere(0.1, [RND(-1, 1), RND(0, 1.2), RND(-1, 1)]),
        **C_speed(f"0.8 + 1.5 * {R2}"),
        **C_life(f"0.15 + 0.15 * {R3}"),
        **C_dyn(acc=[0, -8, 0], drag=1.0),
        **C_bb([f"0.05 + 0.03 * {R4}"] * 2, "lookat_xyz", UV(FX, pick(FX, "spark", R1), sp.y, 16, 16)),
        **C_tint(1, 0.85, 0.4, fade(2)),
    }, note="罠の作動・待機中の小さな火花")


def e_flame_jet():
    LF = VC("life", 1.5, 0.1, 10)
    J = 0.12
    effect("flame_jet", FX, MAT_ADD, {
        **C_once(LF),
        **C_steady(40, 48),
        **C_point(direction=[f"{V('dx', 0)} + math.random(-{J}, {J})", f"{V('dy', 1)} + math.random(-{J}, {J})",
                             f"{V('dz', 0)} + math.random(-{J}, {J})"]),
        **C_speed(f"5.0 + 3.0 * {R2}"),
        **C_life(f"0.45 + 0.25 * {R3}"),
        **C_dyn(acc=[0, 2.5, 0], drag=1.8),
        **C_coll(0.1, rest=0, drag=6),
        **C_spin(f"({R4} - 0.5) * 30", 0),
        **C_bb([f"0.2 + 0.7 * math.pow({T}, 0.6)"] * 2, "lookat_xyz", flame_uv()),
        **C_tint(1, 1, 1, fade(3)),
    }, note="一方向へ噴き出す炎（v.life 秒）")


def e_flies():
    fl = FX.sets["fly"]
    w = f"(220 + 200 * {R2})"
    effect("flies", FX, MAT_ALPHA, {
        **C_once(),
        **C_instant(6),
        **C_point(),
        **C_life(4),
        **C_param(rel=[f"math.cos({AGE} * {w} + {R1} * 360) * (0.3 + 0.3 * {R3})",
                       f"0.25 + math.sin({AGE} * {w} * 1.7 + {R4} * 360) * 0.15",
                       f"math.sin({AGE} * {w} + {R1} * 360) * (0.3 + 0.3 * {R3})"]),
        **C_bb(["0.05", "0.05"], "lookat_xyz",
               {"texture_width": FX.width, "texture_height": FX.height,
                "flipbook": {"base_UV": [fl.x, fl.y], "size_UV": [fl.fw, fl.fh], "step_UV": [fl.fw, 0],
                             "frames_per_second": 20, "max_frame": fl.n, "stretch_to_lifetime": False, "loop": True}}),
        **LIGHT,
    }, note="遺骸にたかる蝿（4 秒飛び回る）")


def e_alarm_flash():
    g = FX.sets["glow"]
    effect("alarm_flash", FX, MAT_ADD, {
        **C_once(),
        **C_instant(1),
        **C_point(),
        **C_life(0.5),
        **C_bb(["0.9", "0.9"], "lookat_xyz", UV(FX, g.x, g.y, g.fw, g.fh)),
        **C_tint(1, 0.55, 0.1, f"(math.mod(math.floor({AGE} * 8), 2) < 0.5 ? 0.9 : 0.15)"),
    }, note="車のアラームの点滅")


def e_heal_sparkle():
    s = FX.sets["star"]
    effect("heal_sparkle", FX, MAT_ADD, {
        **C_once(),
        **C_instant(8),
        **C_sphere(0.5, [RND(-0.2, 0.2), 1, RND(-0.2, 0.2)], offset=[0, 0.6, 0]),
        **C_speed(f"0.4 + 0.5 * {R2}"),
        **C_life(f"0.7 + 0.4 * {R3}"),
        **C_dyn(drag=1.0),
        **C_spin(RND(0, 360), RND(-120, 120)),
        **C_bb([f"0.08 + 0.07 * {R4}"] * 2, "lookat_xyz", UV(FX, pick(FX, "star", R1), s.y, 32, 32)),
        **C_tint(0.55, 1.0, 0.6, f"(0.6 + 0.4 * math.sin({AGE} * 1400 + {R1} * 360)) * {fade_io(5, 2)}"),
    }, note="回復のきらめき")


BUILDERS = [v for k, v in sorted(globals().items()) if k.startswith("e_") and callable(v)]


# ===========================================================================
#  検査（公式スキーマ・Molang・uv・上限・変数・イベント・簡易物理）
# ===========================================================================
class Report:
    def __init__(self):
        self.errors: List[str] = []
        self.warns: List[str] = []
        self.notes: List[str] = []

    def err(self, s):
        self.errors.append(s)

    def warn(self, s):
        self.warns.append(s)


class SchemaChecker:
    """公式の JSON スキーマ（draft-07 の一部: $ref/oneOf/type/properties/required/items/enum/min/max）で検査。
    strict: スキーマの properties に無い欄は誤り（= 使った欄はすべて公式スキーマにあることを保証する）。"""

    def __init__(self, root):
        self.root = root
        self.cache: Dict[str, dict] = {}

    def load(self, path):
        if path not in self.cache:
            with open(path, encoding="utf-8") as fh:
                self.cache[path] = json.load(fh)
        return self.cache[path]

    def resolve(self, sch, cur):
        while isinstance(sch, dict) and "$ref" in sch:
            path = os.path.normpath(os.path.join(os.path.dirname(cur), unquote(sch["$ref"])))
            cur, sch = path, self.load(path)
        return sch, cur

    def check(self, inst, sch, cur, ptr, errs):
        sch, cur = self.resolve(sch, cur)
        if "oneOf" in sch:
            first = None
            for alt in sch["oneOf"]:
                e: List[str] = []
                self.check(inst, alt, cur, ptr, e)
                if not e:
                    return
                first = first or e
            errs.append(f"{ptr}: どの形（oneOf）にも合わない — {first[0] if first else ''}")
            return
        if "enum" in sch and inst not in sch["enum"]:
            errs.append(f"{ptr}: {inst!r} は {sch['enum']} のどれでもない")
            return
        t = sch.get("type")
        if t == "object":
            if not isinstance(inst, dict):
                errs.append(f"{ptr}: オブジェクトでない")
                return
            props = sch.get("properties")
            addl = sch.get("additionalProperties")
            for k, v in inst.items():
                if props is not None and k in props:
                    self.check(v, props[k], cur, f"{ptr}/{k}", errs)
                elif isinstance(addl, dict):
                    self.check(v, addl, cur, f"{ptr}/{k}", errs)
                elif props is not None:
                    errs.append(f"{ptr}: 公式スキーマに無い欄 {k!r}")
            for k in sch.get("required", []):
                if k not in inst:
                    errs.append(f"{ptr}: 必須の欄 {k!r} が無い")
        elif t == "array":
            if not isinstance(inst, list):
                errs.append(f"{ptr}: 配列でない")
                return
            if "minItems" in sch and len(inst) < sch["minItems"]:
                errs.append(f"{ptr}: 要素が {len(inst)} 個（{sch['minItems']} 個以上）")
            if "maxItems" in sch and len(inst) > sch["maxItems"]:
                errs.append(f"{ptr}: 要素が {len(inst)} 個（{sch['maxItems']} 個まで）")
            if isinstance(sch.get("items"), dict):
                for i, v in enumerate(inst):
                    self.check(v, sch["items"], cur, f"{ptr}[{i}]", errs)
        elif t in ("number", "integer"):
            if isinstance(inst, bool) or not isinstance(inst, (int, float)) or (t == "integer" and not isinstance(inst, int)):
                errs.append(f"{ptr}: {t} でない（{inst!r}）")
                return
            if "minimum" in sch and inst < sch["minimum"]:
                errs.append(f"{ptr}: {inst} < 最小 {sch['minimum']}")
            if "maximum" in sch and inst > sch["maximum"]:
                errs.append(f"{ptr}: {inst} > 最大 {sch['maximum']}")
        elif t == "string":
            if not isinstance(inst, str):
                errs.append(f"{ptr}: 文字列でない（{inst!r}）")
            elif "maxLength" in sch and len(inst) > sch["maxLength"]:
                errs.append(f"{ptr}: 長すぎる")
        elif t == "boolean":
            if not isinstance(inst, bool):
                errs.append(f"{ptr}: 真偽値でない")


def find_schema():
    for base in SCHEMA_DIRS:
        p = os.path.join(base, "client", "particles", SCHEMA_VER, "Particle Effect Data.json")
        if os.path.exists(p):
            return p
    return None


_NON_MOLANG = {"facing_camera_mode", "mode", "event", "effect", "type", "creation_event", "expiration_event",
               "event_name", "log"}


def molang_strings(obj, path=""):
    """部品・イベントの中の Molang の文字列 [(パス, 文字列)]。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _NON_MOLANG or (k == "timeline" and isinstance(v, dict)):
                continue
            yield from molang_strings(v, f"{path}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from molang_strings(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        key = path.rsplit("/", 1)[-1]
        if key.startswith("plane_normal") and obj in ("x", "y", "z"):
            return
        if key.startswith("direction") and obj in ("inwards", "outwards"):
            return
        yield path, obj


def event_names_used(comps):
    out = []
    coll = comps.get("minecraft:particle_motion_collision", {})
    ev = coll.get("events")
    for e in ([ev] if isinstance(ev, dict) else (ev or [])):
        out.append(("collision", e.get("event")))
    for cname in ("minecraft:emitter_lifetime_events", "minecraft:particle_lifetime_events"):
        c = comps.get(cname, {})
        for key in ("creation_event", "expiration_event"):
            v = c.get(key)
            for nm in ([v] if isinstance(v, str) else (v or [])):
                out.append((f"{cname}.{key}", nm))
        for t, v in (c.get("timeline") or {}).items():
            for nm in ([v] if isinstance(v, str) else v):
                out.append((f"{cname}.timeline[{t}]", nm))
    return out


def event_effects(node):
    """イベントの木の中の particle_effect [(effect, type, pre)]。"""
    out = []
    if isinstance(node, dict):
        pe = node.get("particle_effect")
        if isinstance(pe, dict):
            out.append((pe.get("effect"), pe.get("type"), pe.get("pre_effect_expression")))
        for k in ("sequence", "randomize"):
            for sub in node.get(k, []) or []:
                out += event_effects(sub)
    return out


_SAMPLE_R = (0.0, 0.13, 0.37, 0.5, 0.63, 0.87, 0.9999)


def _envs_for_bounds():
    """上限の検査に使う変数の組（未設定・0・巨大・負・一つだけ巨大）。"""
    names = REG.PARTICLE_VARS + tuple(INTERNAL_VARS)
    base = [{}, {f"v.{k}": 0.0 for k in names}, {f"v.{k}": 1e6 for k in names}, {f"v.{k}": -1e6 for k in names}]
    for k in names:
        base.append({f"v.{k}": 1e6})
        base.append({f"v.{k}": -1e6})
    out = []
    for b in base:
        for er in (0.0, 0.9999):
            e = dict(b)
            for i in range(1, 5):
                e[f"v.emitter_random_{i}"] = er
            e["v.emitter_age"] = 0.0
            e["v.emitter_lifetime"] = 1.0
            out.append(e)
    return out


def _cells(at):
    cells = set()
    for s in at.sets.values():
        for i in range(s.n):
            cells.add((s.x + i * s.fw, s.y, s.fw, s.fh))
    return cells


def check_effects(rep: Report):
    names = set(EFFECTS)
    # 登録簿の全部があるか
    for pid in REG.all_particle_ids():
        nm = pid.split(":", 1)[1]
        if nm not in names:
            rep.err(f"登録簿の {pid} を作っていない")
    extra = sorted(names - {p.split(':', 1)[1] for p in REG.all_particle_ids()})
    if extra:
        rep.notes.append(f"登録簿に無い補助 {len(extra)}: {', '.join(extra)}")
    schema_path = find_schema()
    sc = SchemaChecker(os.path.dirname(schema_path)) if schema_path else None
    if not sc:
        rep.warn("公式の粒子スキーマが見つからない（build_preview/nr_research）。スキーマ検査を飛ばした")
    envs = _envs_for_bounds()
    rng = np.random.default_rng(7)
    pre_sets: Dict[str, set] = {}   # 子エフェクト -> イベントが置く変数
    graph: Dict[str, set] = {}
    for name, ent in sorted(EFFECTS.items()):
        pe = ent["doc"]["particle_effect"]
        for ev in (pe.get("events") or {}).values():
            for eff, _typ, pre in event_effects(ev):
                child = (eff or "").split(":", 1)[-1]
                graph.setdefault(name, set()).add(child)
                if pre:
                    try:
                        pre_sets.setdefault(child, set()).update(molang_vars(pre)[1])
                    except MolangError:
                        pass
    for name, ent in sorted(EFFECTS.items()):
        doc, at = ent["doc"], ent["atlas"]
        pe = doc["particle_effect"]
        comps = pe["components"]
        where = f"nr:{name}: "
        if sc:
            errs: List[str] = []
            sc.check(pe, {"$ref": os.path.basename(schema_path)}, schema_path, "particle_effect", errs)
            for e in errs:
                rep.err(where + "スキーマ: " + e)
        # Molang（字句・構文・関数・変数）
        reads, writes = set(), set()
        strs = list(molang_strings(comps, "/components")) + list(molang_strings(pe.get("events") or {}, "/events"))
        parsed_ok = True
        for path, s in strs:
            try:
                r, w = molang_vars(s)
            except MolangError as exc:
                rep.err(f"{where}{path}: Molang の誤り {exc} — {s[:100]}")
                parsed_ok = False
                continue
            if path.endswith("pre_effect_expression"):
                continue     # 子エフェクトの変数（検査は子の側）
            reads |= r
            writes |= w
        allowed = BUILTIN_VARS | set(REG.PARTICLE_VARS) | INTERNAL_VARS | writes
        unknown = sorted(reads - allowed)
        if unknown:
            rep.err(f"{where}知らない変数 {unknown}")
        listed = set(REG.PARTICLES.get(name, ("", ""))[1].split())
        used_params = reads & set(REG.PARTICLE_VARS)
        miss = sorted(listed - used_params)
        if miss:
            rep.err(f"{where}登録簿の変数 {miss} を読んでいない")
        more = sorted(used_params - listed)
        if more:
            rep.warn(f"{where}登録簿に無い変数も読む {more}（任意。既定値あり）")
        for child_var in sorted(pre_sets.get(name, set()) - reads):
            rep.warn(f"{where}イベントが置く v.{child_var} を読んでいない")
        # イベント
        evs = pe.get("events") or {}
        for where2, nm in event_names_used(comps):
            if nm not in evs:
                rep.err(f"{where}{where2} のイベント {nm} が events に無い")
        for evn, ev in evs.items():
            for eff, typ, _pre in event_effects(ev):
                if not eff or not eff.startswith("nr:") or eff.split(":", 1)[1] not in names:
                    rep.err(f"{where}イベント {evn} の effect {eff} が無い")
                if typ in ("particle", "particle_with_velocity"):
                    ce = EFFECTS.get((eff or "").split(":", 1)[-1])
                    if ce and "minecraft:emitter_rate_manual" not in ce["doc"]["particle_effect"]["components"]:
                        rep.err(f"{where}イベント {evn}: type {typ} の先 {eff} は emitter_rate_manual が要る")
        if not parsed_ok:
            continue
        # 上限（同時の粒の数・寿命・出す時間）
        rate = comps.get("minecraft:emitter_rate_instant") or comps.get("minecraft:emitter_rate_steady") or \
            comps.get("minecraft:emitter_rate_manual")
        key = "num_particles" if "minecraft:emitter_rate_instant" in comps else "max_particles"
        if not rate or key not in rate:
            rep.err(f"{where}emitter_rate の {key} が無い（上限が決まらない）")
        else:
            worst = max(molang_eval(rate[key], dict(e), rng) for e in envs)
            ent["max_particles"] = worst
            if worst > MAX_PER_EMITTER or worst < 0:
                rep.err(f"{where}{key} の最大 {worst:.0f}（上限 {MAX_PER_EMITTER}）")
        life = comps.get("minecraft:particle_lifetime_expression", {}).get("max_lifetime")
        if life is None:
            rep.err(f"{where}particle_lifetime_expression.max_lifetime が無い")
        else:
            worst = 0.0
            for e in envs[:12]:
                for r in _SAMPLE_R:
                    ee = dict(e)
                    for i in range(1, 5):
                        ee[f"v.particle_random_{i}"] = r
                    worst = max(worst, molang_eval(life, ee, rng))
            ent["max_life"] = worst
            if worst > 300.5:
                rep.err(f"{where}粒の寿命の最大 {worst:.0f} 秒（300 まで）")
        lo = comps.get("minecraft:emitter_lifetime_once")
        if lo and "active_time" in lo:
            worst = max(molang_eval(lo["active_time"], dict(e), rng) for e in envs)
            if worst > 120:
                rep.err(f"{where}active_time の最大 {worst:.0f} 秒")
        if not any(k in comps for k in ("minecraft:emitter_lifetime_once", "minecraft:emitter_lifetime_looping",
                                        "minecraft:emitter_lifetime_expression")):
            rep.err(f"{where}emitter_lifetime_* が無い")
        # uv（コマがアトラスのどれかのセルにぴったり入るか）と大きさ
        bb = comps.get("minecraft:particle_appearance_billboard")
        if not bb:
            rep.err(f"{where}billboard が無い")
            continue
        uv = bb.get("uv", {})
        if (uv.get("texture_width"), uv.get("texture_height")) != (at.width, at.height):
            rep.err(f"{where}uv の texture_width/height {uv.get('texture_width')}x{uv.get('texture_height')} "
                    f"がアトラス {at.width}x{at.height} と違う")
        cells = _cells(at)
        bad = set()
        maxsz = 0.0
        lifetime_guess = ent.get("max_life", 1.0) or 1.0
        for r1 in _SAMPLE_R:
            for r2 in (0.0, 0.5, 0.9999):
                for r3 in (0.0, 0.62, 0.9999):
                    for r4 in (0.0, 0.3, 0.9999):
                        for age in (0.0, 0.05, 0.12, 0.2, 0.5, 1.0, 2.0, 30.0):
                            env = {"v.particle_random_1": r1, "v.particle_random_2": r2, "v.particle_random_3": r3,
                                   "v.particle_random_4": r4, "v.particle_age": min(age, lifetime_guess),
                                   "v.particle_lifetime": lifetime_guess, "v.emitter_age": 0.0,
                                   "v.emitter_lifetime": 1.0}
                            for i in range(1, 5):
                                env[f"v.emitter_random_{i}"] = r2
                            if "flipbook" in uv:
                                fb = uv["flipbook"]
                                bu = molang_eval(fb["base_UV"][0], dict(env), rng)
                                bv = molang_eval(fb["base_UV"][1], dict(env), rng)
                                mf = int(round(molang_eval(fb["max_frame"], dict(env), rng)))
                                for fr in range(mf):
                                    rect = (bu + fb["step_UV"][0] * fr, bv + fb["step_UV"][1] * fr,
                                            fb["size_UV"][0], fb["size_UV"][1])
                                    if tuple(round(x, 3) for x in rect) not in cells:
                                        bad.add(rect)
                            else:
                                rect = tuple(molang_eval(x, dict(env), rng) for x in (uv["uv"] + uv["uv_size"]))
                                if tuple(round(x, 3) for x in rect) not in cells:
                                    bad.add(rect)
                            for sexpr in bb["size"]:
                                sz = molang_eval(sexpr, dict(env), rng)
                                if not math.isfinite(sz) or sz < 0:
                                    rep.err(f"{where}大きさが {sz}（{sexpr[:60]}）")
                                maxsz = max(maxsz, sz)
        if bad:
            rep.err(f"{where}uv がアトラスのセルに合わない {sorted(bad)[:3]}")
        ent["max_size"] = maxsz
        if maxsz > 12:
            rep.warn(f"{where}粒の大きさの最大 {maxsz:.1f} ブロック")
        if bb.get("facing_camera_mode", "").startswith("emitter_transform") and ent["material"] != MAT_BLEND and \
                ent["material"] != MAT_ADD:
            rep.warn(f"{where}平らな粒が particles_alpha（裏から見えない恐れ）")
        coll = comps.get("minecraft:particle_motion_collision")
        if coll and coll.get("collision_radius", 0) > 0.5:
            rep.err(f"{where}collision_radius > 0.5")
        for e in ((coll or {}).get("events") or []):
            if e.get("min_speed", 2) < 2:
                rep.warn(f"{where}collision の min_speed {e.get('min_speed')}（公式: 最小 2）")
    # 子エフェクトの連鎖に輪が無いか
    def dfs(nm, stack):
        if nm in stack:
            rep.err(f"イベントの連鎖が輪になる: {' → '.join(stack + [nm])}")
            return
        for c in graph.get(nm, ()):
            dfs(c, stack + [nm])
    for nm in graph:
        dfs(nm, [])


# ===========================================================================
#  簡易の物理（滴がどこまで飛ぶか・着地の速さで血痕のイベントが出るか）
# ===========================================================================
def _norm3(v):
    L = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / L for x in v]


def simulate(name, env0, height, n_samples=300, dt=1 / 60.0, seed=3):
    comps = EFFECTS[name]["doc"]["particle_effect"]["components"]
    rng = np.random.default_rng(seed)
    dyn = comps.get("minecraft:particle_motion_dynamic", {})
    coll = comps.get("minecraft:particle_motion_collision", {})
    min_speed = max(2.0, min([e.get("min_speed", 2) for e in coll.get("events", [])] or [2]))
    shape_key = next((k for k in comps if k.startswith("minecraft:emitter_shape_")), None)
    shape = comps.get(shape_key, {}) if shape_key else {}
    dists, impacts, landed, times = [], [], 0, []
    for _ in range(n_samples):
        env = dict(env0)
        for i in range(1, 5):
            env[f"v.particle_random_{i}"] = float(rng.random())
            env[f"v.emitter_random_{i}"] = 0.5
        env["v.emitter_age"] = float(rng.random()) * 0.3
        env["v.emitter_lifetime"] = 1.0
        off = [molang_eval(x, env, rng) for x in shape.get("offset", [0, 0, 0])]
        d = shape.get("direction", "outwards")
        if isinstance(d, list):
            dirv = _norm3([molang_eval(x, env, rng) for x in d])
        else:
            rv = _norm3(list(rng.normal(size=3)))
            dirv = rv if d == "outwards" else [-x for x in rv]
        spd = molang_eval(comps.get("minecraft:particle_initial_speed", 0), env, rng)
        life = molang_eval(comps["minecraft:particle_lifetime_expression"]["max_lifetime"], env, rng)
        env["v.particle_lifetime"] = life
        p = [off[0], height + off[1], off[2]]
        v = [dirv[i] * spd for i in range(3)]
        t = 0.0
        while t < life:
            env["v.particle_age"] = t
            acc = [molang_eval(x, env, rng) for x in dyn.get("linear_acceleration", [0, 0, 0])]
            drag = molang_eval(dyn.get("linear_drag_coefficient", 0), env, rng)
            for i in range(3):
                v[i] += (acc[i] - drag * v[i]) * dt
                p[i] += v[i] * dt
            t += dt
            if p[1] <= 0.0:
                landed += 1
                impacts.append(math.sqrt(sum(x * x for x in v)))
                dists.append(math.hypot(p[0], p[2]))
                times.append(t)
                break
    if not impacts:
        return {"landed": 0.0}
    imp = np.array(impacts)
    return {"landed": landed / n_samples, "dist_mean": float(np.mean(dists)), "dist_max": float(np.max(dists)),
            "t_mean": float(np.mean(times)), "event_rate": float(np.mean(imp >= min_speed)),
            "impact_mean": float(np.mean(imp))}


SIMS = [
    ("blood_spray", {"v.dx": 1.0, "v.dy": 0.0, "v.dz": 0.0, "v.speed": 1.0, "v.count": 12}, 1.3),
    ("blood_spray", {"v.dx": 0.7, "v.dy": 0.7, "v.dz": 0.0, "v.speed": 0.5, "v.count": 8}, 1.3),
    ("blood_burst", {"v.speed": 0.7}, 1.2),
    ("blood_drip", {}, 1.0),
    ("blood_fountain", {"v.dx": 0.0, "v.dy": 1.0, "v.dz": 0.0}, 1.5),
    ("head_explode", {"v.dx": 1.0, "v.dy": 0.0, "v.dz": 0.0}, 1.7),
    ("body_explode", {}, 1.0),
    ("gore_chunks", {"v.speed": 0.2}, 1.0),
    ("gut_strands", {"v.speed": 0.3}, 1.0),
]


def run_sims(rep: Report, verbose=True):
    lines = []
    for name, env, h in SIMS:
        st = simulate(name, env, h)
        if st.get("landed", 0) <= 0:
            rep.warn(f"物理: nr:{name} の粒が寿命の間に床（{h} 下）に届かない")
            continue
        lines.append(f"    {name:15s} h={h:.1f}  着地 {st['landed'] * 100:5.1f}%  距離 平均 {st['dist_mean']:.2f} 最大 "
                     f"{st['dist_max']:.2f}  {st['t_mean']:.2f}s  着地の速さ {st['impact_mean']:.1f}  "
                     f"血痕イベント {st['event_rate'] * 100:.0f}%")
    if verbose and lines:
        print("  [particles] 物理の目安（床へ落ちるまで）:")
        print("\n".join(lines))


# ===========================================================================
#  書き出し
# ===========================================================================
def build_all():
    global GORE, FX
    GORE = build_gore_atlas()
    FX = build_fx_atlas()
    EFFECTS.clear()
    for b in BUILDERS:
        b()
    return GORE, FX


def write_outputs():
    os.makedirs(PART_DIR, exist_ok=True)
    keep = set()
    for name, ent in sorted(EFFECTS.items()):
        p = os.path.join(PART_DIR, f"{name}.json")
        C.write_json(p, ent["doc"])
        keep.add(os.path.basename(p))
    removed = 0
    for f in sorted(os.listdir(PART_DIR)):
        if f.endswith(".json") and f not in keep:
            try:
                with open(os.path.join(PART_DIR, f), encoding="utf-8") as fh:
                    ident = json.load(fh)["particle_effect"]["description"]["identifier"]
            except Exception:  # noqa: BLE001
                continue
            if ident.startswith("nr:"):
                os.remove(os.path.join(PART_DIR, f))
                removed += 1
    GORE.write()
    FX.write()
    for f in sorted(os.listdir(TEX_DIR)):
        if f.endswith(".png") and f[:-4] not in (GORE.key, FX.key):
            os.remove(os.path.join(TEX_DIR, f))
            removed += 1
    return removed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-sheet", action="store_true", help="確認画像を描かない")
    ap.add_argument("--no-sim", action="store_true", help="簡易の物理の目安を出さない")
    ap.add_argument("-v", "--verbose", action="store_true", help="注意（warn）も全部出す")
    args = ap.parse_args(argv)
    build_all()
    rep = Report()
    check_effects(rep)
    if rep.errors:
        for e in rep.errors[:80]:
            print("  ERROR", e)
        print(f"[particles] 検査で誤り {len(rep.errors)} 件 — 書き出さない")
        return 1
    removed = write_outputs()
    if not args.no_sheet:
        contact_sheet([GORE, FX])
    if not args.no_sim:
        run_sims(rep)
    for w in rep.warns if args.verbose else rep.warns[:12]:
        print("  warn", w)
    if len(rep.warns) > 12 and not args.verbose:
        print(f"  … warn は全部で {len(rep.warns)} 件（-v で全部）")
    for s in rep.notes:
        print("  note", s)
    mats: Dict[str, int] = {}
    for ent in EFFECTS.values():
        mats[ent["material"]] = mats.get(ent["material"], 0) + 1
    worst = max(EFFECTS.items(), key=lambda kv: kv[1].get("max_particles", 0))
    print(f"[particles] {len(EFFECTS)} 個（登録簿 {len(REG.PARTICLES)}）・アトラス "
          f"{GORE.key} {GORE.width}x{GORE.height} / {FX.key} {FX.width}x{FX.height}・材質 "
          + ", ".join(f"{k} {v}" for k, v in sorted(mats.items()))
          + f"・1 エミッタの最大 {worst[1].get('max_particles', 0):.0f}（{worst[0]}）"
          + (f"・古いファイル {removed} を消した" if removed else "")
          + ("" if args.no_sheet else f" → {os.path.relpath(SHEET, C.ROOT)}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
