# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 写実寄りの素材ペインタ（numpy でベクトル化）。

mcmodel の各キューブが持つ style 名（cube.style）と面ごとのデカール（cube.decals）から、
アトラス（model.tex_w × model.tex_h の RGBA）を塗る。セル塗りではなく「写真っぽい」ピクセル絵を狙う:

  * 多オクターブの値ノイズ（fbm）、ドメインワープ、セル（Worley）ノイズ
  * 大きな模様（染み・血・汚れ・腐敗の斑）は **モデル空間の 3D ノイズ** で塗るので、
    キューブの角や隣のキューブとの継ぎ目をまたいで模様が繋がる
  * 細かい模様（毛穴・繊維・織り目・木目）は面ローカルの 2D ノイズ。uv_scale（texel 密度）に
    応じて細かいオクターブを足し引きする（密度が低い面で砂嵐にならない）
  * 面ごとのライティング（上は明るく下は暗く）、面の縁の環境遮蔽（AO）、
    金属の縁の擦れ、下ほど溜まる汚れ、重力に沿って垂れる血（側面では画像の +v ＝ 下）、
    血・内臓の濡れたハイライト、腐敗の緑→紫→黒のグラデーション、静脈、打撲、縫合

公開 API:
  paint_model(model, stylebook, seed=0, face_light=True, ao=True) -> PIL.Image (RGBA, tex_w x tex_h)
      model.tex_w が 0 なら model.pack() してから塗る。cube.style が stylebook に無ければ KeyError。
      cube.decals = {面: "名前" | {"name": 名前, ...} | [それらのリスト]}。キー "*" はキューブ単位の
      デカールで、各デカールの faces（既定は 6 面）に描く（例 {"*": {"name": "section", "faces": ["down"]}}）
  zombie_styles(tone, decay, eyes, hair_colour=None, blood=0.1, hair_style="matted", dirt=0.4,
                life_tone=None, blood_kind="red") -> 体の stylebook（skin / skin_dark / flesh / cut_flesh /
      bone / teeth / gums / guts / brain / blood / blood_dry / eye / hair / nail）。体の血は既定で少なめ
      （古い乾いた茶色が多い = blood_age 0.6）。血の量は傷・断面・顔の口元が受け持つ
  EYES / eye_info(kind, glow_colour=None) … 目の全種類（nr_spec_zombies.EYES_VOCAB と同じ名前・色）:
      clouded / bloodshot / milky / glowing_yellow|red|green|orange|cyan / glowing_white（闇の中の光点）/
      none（眼窩）。glowing_* は EMISSIVE_ALPHA で光る。"eye" 素材（目玉キューブ）と face デカールの両方
  section_decal(faces, **params) -> {面: {"name": "section", ...}}（断面の上書き。下の section を参照）
  cube_world_matrices(model) -> {id(cube): 4x4}（3D ノイズを引く休みの姿勢のモデル空間）
  seam_ratio(model, img) -> 側面の角での模様の切れ具合（1 に近いほど繋がっている。自己テストが使う）
  skin_tone(skin, life_tone=None) -> SKINS の 1 系統に生前の肌色（SKIN_TONES）を混ぜた dict
  style(mat, **params) / cloth_style / denim_style / knit_style / leather_style / metal_style /
  painted_metal_style / outfit_palette(kind) -> スタイル（stylebook の 1 項目）
  save_png(img, path, quantize=False) -> 書いたバイト数。quantize_rgba(img) -> P モード画像
  text_mask(text, w, h, at, px) -> 3x5 フォントのマスク（UI や看板の生成器も使える）
  SKINS（nr_spec_zombies.SKIN_VOCAB の 17 系統 + 予備）、SKIN_TONES、BLOOD_KINDS（spec の BLOOD_VOCAB）、
  CLOTH（服の色見本）、MATERIALS、MATERIAL_PARAMS（素材ごとのパラメータの説明）、DECALS

デカール（cube.decals の name）: face（params eyes / mouth / decay / gore / region full|upper|jaw /
  eye_v / eye_gap / brow_v / nose_v / mouth_v / nose）、wound（size, wet, angle, at）、bite、bullet_hole
  （下地の素材で 肉 / 金属 / ガラス / 布 を描き分け）、burn（embers で発光）、text（text, colour, px, wear,
  emissive）= number、stripe（colour, count, orient h|v|d, width, hazard, reflective）、badge（kind
  shield|star|circle|patch, colour, text）、grime、stitches、drips、handprint、buttons、pocket、zipper、
  cracks、rust_streaks、veins、glow_spot、logo（架空のロゴ）。位置は at=(u, v)（面の正規化座標）。
  section … キューブ・面ごとの断面の上書き（cut_flesh の素材の「どの面が断面か・骨はどこか」を
  キューブごとに変える）: kind limb|neck|torso|plain、centre、bone_at（neck / torso では背骨。背中側に置く）、
  bone_r、bones=[(u, v, r)]、fat、skin、wet、trachea_at（neck）。皮膚の縁 → 黄色い脂肪の輪 → 赤い筋肉の束
  → 白い骨（髄）、neck は頸椎・脊髄・気管・食道・頸動脈、torso は腰椎・背筋・大動脈・腸の輪切り。

発光（Bedrock の entity_emissive_alpha 系マテリアル）:
  アルファが 255 未満の texel が光る（光り方 = 1 - alpha/255）。
  * EMISSIVE_ALPHA = 16  … 光る texel（≈94% 自己発光。光る目・UV ランプ・燠火・酸の血）
  * EMISSIVE_HALO  = 40  … 光る目・光る点の周りのにじみ（≈84% 自己発光。DESIGN §13 / rendering.md M3 の
    「発光画素は α=3〜40」に収める。弱い光に見せるのは α ではなく暗い色で）
  * それ以外の塗った texel は必ず 255、アトラスの使っていない所は 0（どの面からも参照されない）
  光る texel を持つテクスチャはアルファテスト系マテリアル（entity_alphatest 等）で描かないこと
  （alpha 16 の texel が捨てられて穴になる）。

座標の約束（統合版の実際の対応。DESIGN.md §13・nr_preview.py の _CORNERS と同じ）:
  側面（north/south/east/west）は画像の上が上（+Y）。だから垂れる血は世界の下向き = 画像の +v 方向へ
  流れる（契約の「-V」は世界座標での下向きの意味）。
  ファイル座標で **east は min-X の面（体の右）で u→-Z**、**west は max-X の面で u→+Z**、
  north（min-Z）: u→+X, south（max-Z）: u→-X, up: u→+X / v→-Z, down: u→+X / v→+Z。
  この向きだと側面 4 枚が east→north→west→south の順（mcmodel の矩形の並び）で切れ目なく繋がる。
  （tools/preview.py・hd_scene.py は east を +X に置く旧い並びなので、確認画像は nr_preview で描く）
  3D ノイズを引く位置は「休みの姿勢のモデル空間」: ボーンとキューブの rotation（pivot 回り）を
  掛けてから引くので、回ったキューブや傾いたボーンの境でも模様が繋がる（cube_world_matrices）。
  細かい 2D の模様も、側面は帯の通しの座標で引く（側面の角 3 つで切れない）。

計測（このリポジトリの 4 コア機、python3 tools/nightrunner/nr_paint.py の自己テスト）:
  * 512x512・400 キューブ・18 スタイル・デカール 10 枚: 0.6 秒前後（予算 3 秒）。
    スタイル 1 つあたり約 10ms の固定費があるので、スタイル数が支配的（キューブ数ではない）。
  * PNG: RGBA 約 406 KiB → パレット化 約 145 KiB（約 36%）。アルファ（0 / 16 / 160 / 255）は完全に一致、
    色の平均誤差は約 2.6/255。パレット化はアルファの段ごとに別パレットを作るので、発光マーカーが
    他の texel と混ざることは無い（読み戻して一致しなければ RGBA のまま書く）。
"""
from __future__ import annotations

import math
import os
import statistics
import sys
import time
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

# ---------------------------------------------------------------------------
#  定数
# ---------------------------------------------------------------------------
EMISSIVE_ALPHA = 16
EMISSIVE_HALO = 40

FACES = ("up", "down", "east", "north", "west", "south")
SIDES = ("east", "north", "west", "south")
_FCODE = {f: i for i, f in enumerate(FACES)}
# 焼き込む面の明るさ。Bedrock も法線で陰を付けるので控えめ
FACE_LIGHT = {"up": 1.07, "down": 0.80, "north": 1.0, "south": 0.95,
              "east": 0.97, "west": 0.93}

f32 = np.float32


def _rgb(v, default=(128, 128, 128)) -> np.ndarray:
    """'#rrggbb' / (r, g, b) / None → float32 (3,)。"""
    if v is None:
        v = default
    if isinstance(v, np.ndarray):
        return v.astype(f32)
    if isinstance(v, str):
        s = v.lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        return np.array([int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)], dtype=f32)
    return np.array([float(v[0]), float(v[1]), float(v[2])], dtype=f32)


def _hex(c) -> str:
    c = _rgb(c)
    return "#%02x%02x%02x" % tuple(int(max(0, min(255, round(float(x))))) for x in c)


def _seed(*parts) -> int:
    return zlib.crc32(":".join(str(p) for p in parts).encode("utf-8")) & 0x7FFFFFFF


def _ss(e0, e1, x):
    """smoothstep（e0 > e1 も可）。"""
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    """a, b: (N,3) か (3,)、t: (N,) → (N,3)。"""
    t = np.asarray(t, dtype=f32)
    return a + (b - a) * t[..., None]


def _ramp(t, stops):
    """t (N,) を色の段階 [(t0, col0), (t1, col1), ...] で塗る。"""
    xs = [float(s[0]) for s in stops]
    cols = np.array([_rgb(s[1]) for s in stops], dtype=f32)
    out = np.empty(t.shape + (3,), dtype=f32)
    for ch in range(3):
        out[..., ch] = np.interp(t, xs, cols[:, ch])
    return out


def _thr(cover: float, std: float = 0.18) -> float:
    """fbm（平均 0.5・標準偏差 ≈0.18）が cover の割合だけ超えるしきい値。"""
    cover = min(0.999, max(0.001, float(cover)))
    return 0.5 + std * statistics.NormalDist().inv_cdf(1.0 - cover)


# ---------------------------------------------------------------------------
#  ノイズ（uint32 ハッシュ。プロセス・機械をまたいで同じ値）
# ---------------------------------------------------------------------------
_P1 = np.uint32(0x8DA6B343)
_P2 = np.uint32(0xD8163841)
_P3 = np.uint32(0xCB1AB31F)
_K1 = np.uint32(0x7FEB352D)
_K2 = np.uint32(0x846CA68B)
_INV24 = f32(1.0 / 16777216.0)


def _fin(h):
    h = h ^ (h >> np.uint32(16))
    h = h * _K1
    h = h ^ (h >> np.uint32(15))
    h = h * _K2
    h = h ^ (h >> np.uint32(16))
    return h


def _u01(h):
    return (h >> np.uint32(8)).astype(f32) * _INV24


def hash2i(ix, iy, seed):
    return _fin((ix * _P1) ^ (iy * _P2) ^ np.uint32(seed & 0xFFFFFFFF))


def hash3i(ix, iy, iz, seed):
    return _fin((ix * _P1) ^ (iy * _P2) ^ (iz * _P3) ^ np.uint32(seed & 0xFFFFFFFF))


def texel_rand(ax, ay, seed):
    """アトラスの texel ごとの乱数 0..1。"""
    return _u01(hash2i(ax.astype(np.uint32), ay.astype(np.uint32), seed))


def vnoise2(x, y, seed):
    """2D 値ノイズ 0..1（双線形 + smoothstep）。格子点の値は uint32 ハッシュ。"""
    xf = np.floor(x)
    yf = np.floor(y)
    tx = (x - xf).astype(f32)
    ty = (y - yf).astype(f32)
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    ix = xf.astype(np.int64).astype(np.uint32)
    iy = yf.astype(np.int64).astype(np.uint32)
    sd = np.uint32(seed & 0xFFFFFFFF)
    hx0 = ix * _P1
    hx1 = (ix + np.uint32(1)) * _P1
    hy0 = (iy * _P2) ^ sd
    hy1 = ((iy + np.uint32(1)) * _P2) ^ sd
    a = _u01(_fin(hx0 ^ hy0))
    b = _u01(_fin(hx1 ^ hy0))
    c = _u01(_fin(hx0 ^ hy1))
    d = _u01(_fin(hx1 ^ hy1))
    ab = a + (b - a) * tx
    cd = c + (d - c) * tx
    return ab + (cd - ab) * ty


def vnoise3(x, y, z, seed):
    """3D 値ノイズ 0..1（三重線形 + smoothstep）。"""
    xf = np.floor(x)
    yf = np.floor(y)
    zf = np.floor(z)
    tx = (x - xf).astype(f32)
    ty = (y - yf).astype(f32)
    tz = (z - zf).astype(f32)
    tx = tx * tx * (3 - 2 * tx)
    ty = ty * ty * (3 - 2 * ty)
    tz = tz * tz * (3 - 2 * tz)
    ix = xf.astype(np.int64).astype(np.uint32)
    iy = yf.astype(np.int64).astype(np.uint32)
    iz = zf.astype(np.int64).astype(np.uint32)
    sd = np.uint32(seed & 0xFFFFFFFF)
    one = np.uint32(1)
    hx = (ix * _P1, (ix + one) * _P1)
    hy = (iy * _P2, (iy + one) * _P2)
    hz = ((iz * _P3) ^ sd, ((iz + one) * _P3) ^ sd)
    v = {}
    for i in (0, 1):
        for j in (0, 1):
            hij = hx[i] ^ hy[j]
            for k in (0, 1):
                v[i, j, k] = _u01(_fin(hij ^ hz[k]))
    x00 = v[0, 0, 0] + (v[1, 0, 0] - v[0, 0, 0]) * tx
    x10 = v[0, 1, 0] + (v[1, 1, 0] - v[0, 1, 0]) * tx
    x01 = v[0, 0, 1] + (v[1, 0, 1] - v[0, 0, 1]) * tx
    x11 = v[0, 1, 1] + (v[1, 1, 1] - v[0, 1, 1]) * tx
    y0 = x00 + (x10 - x00) * ty
    y1 = x01 + (x11 - x01) * ty
    return y0 + (y1 - y0) * tz


# fbm の出力を「平均 0.5・標準偏差 ≈0.18」にそろえる係数（自己テストで実測して決めた）
_FBM_K2 = 1.29
_FBM_K3 = 1.49


def _oct_weight(tpc):
    """1 周期あたりの texel 数 → そのオクターブの重み（細かすぎるオクターブは消す）。"""
    return np.clip((tpc - 0.9) / 1.4, 0.0, 1.0)


def fbm2(x, y, seed, octaves=4, lac=2.0, gain=0.5, tpc=None):
    """2D fbm。tpc = 基本オクターブ 1 周期の texel 数（配列可）。"""
    acc = np.zeros(np.shape(x), dtype=f32)
    amp = 1.0
    norm = 0.0
    for i in range(octaves):
        norm += amp
        if tpc is not None:
            w = _oct_weight(tpc)
            if np.max(w) <= 0.0:
                break
            acc += (vnoise2(x, y, seed + i * 1013) - 0.5) * (amp * w)
            tpc = tpc / lac
        else:
            acc += (vnoise2(x, y, seed + i * 1013) - 0.5) * amp
        amp *= gain
        x = x * lac + 17.31
        y = y * lac + 9.73
    for j in range(i + 1, octaves):
        norm += amp
        amp *= gain
    return 0.5 + acc * f32(_FBM_K2 / norm)


def fbm3(x, y, z, seed, octaves=3, lac=2.0, gain=0.5, tpc=None):
    acc = np.zeros(np.shape(x), dtype=f32)
    amp = 1.0
    norm = 0.0
    i = 0
    for i in range(octaves):
        norm += amp
        if tpc is not None:
            w = _oct_weight(tpc)
            if np.max(w) <= 0.0:
                break
            acc += (vnoise3(x, y, z, seed + i * 1013) - 0.5) * (amp * w)
            tpc = tpc / lac
        else:
            acc += (vnoise3(x, y, z, seed + i * 1013) - 0.5) * amp
        amp *= gain
        x = x * lac + 17.31
        y = y * lac + 9.73
        z = z * lac + 4.19
    for j in range(i + 1, octaves):
        norm += amp
        amp *= gain
    return 0.5 + acc * f32(_FBM_K3 / norm)


def worley2(x, y, seed, jitter=0.85):
    """セルノイズ。戻り値 (F1, F2, セルの乱数 0..1, 特徴点へのベクトル dx, dy)（セル単位）。"""
    xf = np.floor(x)
    yf = np.floor(y)
    fx = (x - xf).astype(f32)
    fy = (y - yf).astype(f32)
    ix = xf.astype(np.int64).astype(np.uint32)
    iy = yf.astype(np.int64).astype(np.uint32)
    big = f32(1e9)
    F1 = np.full(fx.shape, big, dtype=f32)
    F2 = np.full(fx.shape, big, dtype=f32)
    cid = np.zeros(fx.shape, dtype=f32)
    vx = np.zeros(fx.shape, dtype=f32)
    vy = np.zeros(fx.shape, dtype=f32)
    j = f32(jitter)
    for oy in (-1, 0, 1):
        cy = iy + np.uint32(oy & 0xFFFFFFFF)
        hy = cy * _P2
        for ox in (-1, 0, 1):
            cx = ix + np.uint32(ox & 0xFFFFFFFF)
            h = _fin((cx * _P1) ^ hy ^ np.uint32(seed & 0xFFFFFFFF))
            h2 = _fin(h ^ np.uint32(0x9E3779B9))
            h3 = _fin(h2 ^ np.uint32(0x85EBCA6B))
            px = f32(ox + 0.5) + j * (_u01(h2) - f32(0.5))
            py = f32(oy + 0.5) + j * (_u01(h3) - f32(0.5))
            dx = px - fx
            dy = py - fy
            d = dx * dx + dy * dy
            closer = d < F1
            F2 = np.where(closer, F1, np.minimum(F2, d))
            F1 = np.where(closer, d, F1)
            cid = np.where(closer, _u01(h), cid)
            vx = np.where(closer, dx, vx)
            vy = np.where(closer, dy, vy)
    return np.sqrt(F1), np.sqrt(F2), cid, vx, vy


def _scratch_field(x, y, density, seed, length=0.9):
    """セルごとに 1 本の線分。戻り値: 一番近い線分までの距離（セル単位）。"""
    xf = np.floor(x)
    yf = np.floor(y)
    fx = (x - xf).astype(f32)
    fy = (y - yf).astype(f32)
    ix = xf.astype(np.int64).astype(np.uint32)
    iy = yf.astype(np.int64).astype(np.uint32)
    best = np.full(fx.shape, 1e9, dtype=f32)
    for oy in (-1, 0, 1):
        cy = iy + np.uint32(oy & 0xFFFFFFFF)
        for ox in (-1, 0, 1):
            cx = ix + np.uint32(ox & 0xFFFFFFFF)
            h = _fin((cx * _P1) ^ (cy * _P2) ^ np.uint32(seed & 0xFFFFFFFF))
            on = _u01(h) < density
            h2 = _fin(h ^ np.uint32(0x68E31DA4))
            h3 = _fin(h2 ^ np.uint32(0xB5297A4D))
            h4 = _fin(h3 ^ np.uint32(0x1B56C4E9))
            px = ox + _u01(h2)
            py = oy + _u01(h3)
            ang = _u01(h4) * f32(math.pi)
            ca = np.cos(ang)
            sa = np.sin(ang)
            hl = f32(length * 0.5) * (0.4 + _u01(h ^ np.uint32(0x2545F491)))
            dx = fx - px
            dy = fy - py
            t = np.clip(dx * ca + dy * sa, -hl, hl)
            qx = dx - t * ca
            qy = dy - t * sa
            d = np.sqrt(qx * qx + qy * qy)
            best = np.where(on, np.minimum(best, d), best)
    return best


# ---------------------------------------------------------------------------
#  肌の系統・服の色見本
# ---------------------------------------------------------------------------
SKINS: Dict[str, dict] = {
    # nr_spec_zombies.SKIN_VOCAB の実装（色は spec と同じ値）。
    # base 地 / shadow 陰 / highlight 照り / vein 血管 / mottle 斑 / wet 濡れ 0..1 /
    # tone_mix 生前の肌色（SKIN_TONES）を混ぜる割合 / emissive_vein 血管（ひび）が光る。
    # 以下は nr_paint だけが使う追加の描き分け:
    # cracks 0..1 ひび割れの網（中に vein 色）、exposed 皮が剥けて肉が見える割合（decay の既定を上書き）、
    # spores 0..1 白い胞子の粉、iridescent 角度で青く照る、veins 血管の濃さ（既定は decay から）
    "pale": dict(base=(196, 192, 178), shadow=(138, 132, 128), highlight=(226, 222, 212),
                 vein=(112, 120, 150), mottle=(160, 150, 160), wet=0.2, tone_mix=0.35),
    "grey_green": dict(base=(140, 150, 124), shadow=(88, 98, 80), highlight=(176, 184, 160),
                       vein=(70, 84, 70), mottle=(112, 104, 88), wet=0.25, tone_mix=0.3),
    "necrotic_purple": dict(base=(132, 104, 124), shadow=(78, 56, 76), highlight=(168, 140, 158),
                            vein=(60, 30, 60), mottle=(96, 120, 80), wet=0.35, tone_mix=0.2, veins=0.9),
    "jaundiced": dict(base=(198, 176, 110), shadow=(140, 118, 70), highlight=(224, 206, 148),
                      vein=(120, 90, 60), mottle=(150, 120, 90), wet=0.25, tone_mix=0.3, cracks=0.25),
    "charred": dict(base=(40, 34, 30), shadow=(16, 12, 10), highlight=(88, 76, 66),
                    vein=(120, 40, 20), mottle=(150, 140, 130), wet=0.0, tone_mix=0.0, cracks=0.9,
                    veins=0.0, spores=0.35),
    "drowned_blue": dict(base=(150, 170, 178), shadow=(92, 110, 124), highlight=(196, 210, 214),
                         vein=(70, 80, 120), mottle=(120, 140, 110), wet=0.7, tone_mix=0.2),
    "bloated_pink": dict(base=(206, 156, 148), shadow=(150, 98, 96), highlight=(232, 196, 186),
                         vein=(110, 90, 140), mottle=(160, 170, 110), wet=0.5, tone_mix=0.3, veins=0.85),
    "ashen": dict(base=(164, 160, 154), shadow=(104, 100, 98), highlight=(200, 198, 192),
                  vein=(90, 90, 100), mottle=(130, 120, 110), wet=0.1, tone_mix=0.3),
    "flushed": dict(base=(196, 150, 132), shadow=(140, 92, 84), highlight=(228, 190, 170),
                    vein=(90, 30, 50), mottle=(180, 110, 110), wet=0.45, tone_mix=0.5, veins=0.9),
    "leathery_brown": dict(base=(120, 92, 66), shadow=(70, 50, 36), highlight=(160, 130, 98),
                           vein=(60, 40, 30), mottle=(90, 96, 60), wet=0.05, tone_mix=0.25, cracks=0.45),
    "bruised": dict(base=(150, 120, 128), shadow=(90, 64, 80), highlight=(186, 160, 160),
                    vein=(70, 40, 70), mottle=(150, 150, 80), wet=0.3, tone_mix=0.3, bruises=0.9),
    "nocturnal_grey": dict(base=(92, 96, 104), shadow=(44, 46, 54), highlight=(140, 146, 152),
                           vein=(40, 30, 40), mottle=(120, 60, 60), wet=0.55, tone_mix=0.0, exposed=0.08),
    "shadow_black": dict(base=(34, 34, 40), shadow=(12, 12, 16), highlight=(70, 74, 90),
                         vein=(20, 20, 30), mottle=(60, 40, 50), wet=0.6, tone_mix=0.0, iridescent=True),
    "cinder": dict(base=(46, 36, 32), shadow=(18, 12, 10), highlight=(96, 80, 70),
                   vein=(255, 120, 30), mottle=(140, 130, 120), wet=0.0, tone_mix=0.0,
                   emissive_vein=True, cracks=0.85, veins=0.0, spores=0.3),
    "fungal_ochre": dict(base=(170, 146, 100), shadow=(110, 90, 56), highlight=(210, 190, 140),
                         vein=(90, 70, 40), mottle=(200, 200, 170), wet=0.3, tone_mix=0.15, spores=0.7),
    "raw_flesh": dict(base=(150, 58, 52), shadow=(90, 24, 24), highlight=(196, 110, 98),
                      vein=(70, 20, 30), mottle=(220, 200, 160), wet=0.8, tone_mix=0.0, exposed=0.72),
    "lab_white": dict(base=(222, 224, 226), shadow=(160, 166, 176), highlight=(246, 248, 250),
                      vein=(90, 140, 220), mottle=(200, 190, 200), wet=0.3, tone_mix=0.2, veins=1.0),
    # 以下は nr_paint 独自（見本・小道具用）
    "tan":    dict(base=(176, 136, 104), shadow=(110, 76, 58), highlight=(202, 164, 128),
                   vein=(84, 92, 136), mottle=(150, 110, 110), wet=0.2, tone_mix=0.0),
    "brown":  dict(base=(132, 94, 70), shadow=(78, 52, 40), highlight=(162, 122, 94),
                   vein=(70, 60, 90), mottle=(110, 80, 80), wet=0.2, tone_mix=0.0),
    "dark":   dict(base=(92, 66, 52), shadow=(52, 36, 30), highlight=(122, 92, 74),
                   vein=(50, 40, 60), mottle=(80, 56, 56), wet=0.2, tone_mix=0.0),
    "olive":  dict(base=(166, 140, 106), shadow=(102, 82, 62), highlight=(192, 168, 130),
                   vein=(84, 92, 110), mottle=(140, 110, 100), wet=0.2, tone_mix=0.0),
    "livid":  dict(base=(150, 128, 142), shadow=(86, 66, 84), highlight=(182, 160, 170),
                   vein=(70, 50, 90), mottle=(120, 90, 110), wet=0.25, tone_mix=0.0),
    "burnt":  dict(base=(96, 70, 56), shadow=(44, 32, 28), highlight=(132, 98, 78),
                   vein=(110, 40, 24), mottle=(120, 110, 100), wet=0.0, tone_mix=0.0, cracks=0.5),
    "frozen": dict(base=(170, 182, 190), shadow=(100, 112, 128), highlight=(200, 212, 218),
                   vein=(70, 90, 140), mottle=(150, 160, 180), wet=0.3, tone_mix=0.0),
}

# 生前の肌色（nr_spec_zombies.SKIN_TONES と同じ。0 とても明るい … 4 濃い褐色）
SKIN_TONES = ((232, 200, 176), (214, 176, 146), (190, 146, 112), (150, 104, 74), (100, 68, 48))
_SKIN_EXTRA = ("vein", "mottle", "wet", "emissive_vein", "cracks", "exposed", "spores", "iridescent",
               "veins", "bruises", "decay_tint")


def skin_tone(skin, life_tone: Optional[int] = None) -> dict:
    """SKINS のキー（か dict）と生前の肌色の番号 0..4 から、肌の tone 一式を作る。
    戻り値 dict(base, shadow, highlight, vein, mottle, wet, ...)（色は int の 3 つ組）。"""
    e = dict(SKINS[skin]) if isinstance(skin, str) else dict(skin)
    mixk = float(e.get("tone_mix", 0.0))
    if life_tone is not None and mixk > 0:
        lt = _rgb(SKIN_TONES[int(max(0, min(4, life_tone)))])
        b = _rgb(e["base"])
        e["base"] = b + (lt - b) * f32(mixk)
        e["shadow"] = _rgb(e.get("shadow", b * 0.62)) + (lt * 0.6 - _rgb(e.get("shadow", b * 0.62))) * f32(mixk)
        e["highlight"] = _rgb(e.get("highlight", b * 1.14)) + \
            (np.minimum(255, lt * 1.12) - _rgb(e.get("highlight", b * 1.14))) * f32(mixk)
    for k in ("base", "shadow", "highlight", "vein", "mottle"):
        if k in e:
            e[k] = tuple(int(round(float(x))) for x in _rgb(e[k]))
    return e


CLOTH: Dict[str, str] = {
    # 服の色見本（cloth_style などの base / alt にそのまま渡せる）
    "white_shirt": "#d6d8d4", "blue_shirt": "#9fb4cc", "grey_suit": "#4a4c52",
    "black_suit": "#25262b", "navy": "#26304a", "police": "#1f2a40", "khaki": "#9a8a66",
    "olive_drab": "#5b5e3c", "nurse_teal": "#5f9aa4", "scrubs_green": "#5d8a72",
    "hoodie_grey": "#77787a", "red_flannel": "#8e2a26", "denim": "#3d5578",
    "faded_denim": "#6a83a6", "hi_vis_yellow": "#cfe83a", "hi_vis_orange": "#f2721c",
    "prison_orange": "#d8642a", "chef_white": "#dedbd2", "brown_leather": "#4a3122",
    "black_leather": "#26221f", "construction_tan": "#b0915c", "firefighter": "#3a3428",
    "hazmat_yellow": "#d7c23a", "riot_black": "#202226", "camo_green": "#556042",
    "beanie_red": "#7c2224", "pink": "#c98c9a", "mustard": "#b08a2c",
}


def _tone(p) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = p.get("tone")
    if isinstance(t, str):
        t = SKINS[t]
    if t is None:
        b = _rgb(p.get("base", SKINS["pale"]["base"]))
        return b, b * 0.62, np.minimum(255, b * 1.14 + 6)
    b = _rgb(t.get("base", (180, 170, 155)))
    return b, _rgb(t.get("shadow", b * 0.62)), _rgb(t.get("highlight", np.minimum(255, b * 1.14 + 6)))


# ---------------------------------------------------------------------------
#  画素の集合（同じ style の全キューブ・全面をまとめてベクトル化）
# ---------------------------------------------------------------------------
class Field:
    """ある style で塗る texel 全部を 1 次元配列にしたもの。

    ax, ay   アトラス上の texel 座標
    lx, ly   面ローカルの texel 中心座標（0.5 始まり）、fw, fh 面の texel 寸法
    fa, fb   面の正規化座標 0..1（fb=0 が画像の上。側面では上が +Y）
    s        texel 密度（1 モデル単位あたりの texel 数）
    X, Y, Z  モデル空間の位置（単位）。3D ノイズはこれで引くので継ぎ目で模様が繋がる
    U, V     面ローカルの単位座標（面ごとにずらしてある）。細かい 2D 模様用
    Ua, Va   キューブの長軸に沿った座標（Va が長軸方向）。繊維・木目・筋用
    endon    面が長軸に垂直（断面方向）なら True
    face     面の番号（FACES の並び）、side 側面か、fid 面の通し番号
    ed       面の縁までの距離（texel）、edu 同（単位）
    yrel     キューブ内の高さ 0..1（上が 1）、Ym モデル全体の高さ 0..1
    cid      キューブ番号、crnd キューブごとの乱数 0..1
    """

    def __init__(self):
        self.glow = None     # 素材が「光る」と決めた texel（bool）
        self.wetm = None     # 素材が「濡れている」と決めた量（0..1）
        self.hard = False

    def nb(self, vals, dx=0, dy=-1):
        """同じ面の中の隣の texel の値（dy=-1 は画像で 1 つ上 = 側面なら上側）。面の外なら自分の値。"""
        vals = np.asarray(vals)
        buf = np.zeros((self.H, self.W), vals.dtype)
        buf[self.ay, self.ax] = vals
        lx2 = self.lxi + dx
        ly2 = self.lyi + dy
        ok = (lx2 >= 0) & (lx2 < self.fwi) & (ly2 >= 0) & (ly2 < self.fhi)
        ny = np.clip(self.ay + dy, 0, self.H - 1)
        nx = np.clip(self.ax + dx, 0, self.W - 1)
        return np.where(ok, buf[ny, nx], vals)

    def emboss(self, height, k=1.0):
        """高さの場から「上から光が来た」陰影係数（1 ± k）。"""
        up = self.nb(height.astype(f32), 0, -1)
        lf = self.nb(height.astype(f32), -1, 0)
        return 1.0 + np.clip((height - up) * 0.8 + (height - lf) * 0.3, -1, 1) * f32(k)


def _face_frame(face, o, sz):
    """面の (原点, a 方向, b 方向)。P = O + A*fa + B*fb（ファイル座標。nr_preview の _CORNERS と同じ）。

    統合版の実際の対応（DESIGN.md §13）: east は min-X の面で左上が (x0, y1, z1)、u は -Z へ。
    west は max-X の面で左上が (x1, y1, z0)、u は +Z へ。だから側面の帯は east → north → west →
    south → east の順で切れ目なく一周する（mcmodel の矩形の並びと同じ）。"""
    ox, oy, oz = o
    sx, sy, sz_ = sz
    if face == "north":
        return (ox, oy + sy, oz), (sx, 0, 0), (0, -sy, 0)
    if face == "south":
        return (ox + sx, oy + sy, oz + sz_), (-sx, 0, 0), (0, -sy, 0)
    if face == "east":
        return (ox, oy + sy, oz + sz_), (0, 0, -sz_), (0, -sy, 0)
    if face == "west":
        return (ox + sx, oy + sy, oz), (0, 0, sz_), (0, -sy, 0)
    if face == "up":
        return (ox, oy + sy, oz + sz_), (sx, 0, 0), (0, 0, -sz_)
    return (ox, oy, oz), (sx, 0, 0), (0, 0, sz_)


def _rotm(rot) -> np.ndarray:
    """統合版の rotation [rx, ry, rz]（度）→ 回転行列 R = Rz(-rz)·Ry(ry)·Rx(-rx)（nr_preview・nr_rig と同じ）。"""
    ax, ay, az = (math.radians(float(v)) for v in rot)
    cx, sx_ = math.cos(-ax), math.sin(-ax)
    cy, sy_ = math.cos(ay), math.sin(ay)
    cz, sz_ = math.cos(-az), math.sin(-az)
    Rx = np.array([[1, 0, 0], [0, cx, -sx_], [0, sx_, cx]])
    Ry = np.array([[cy, 0, sy_], [0, 1, 0], [-sy_, 0, cy]])
    Rz = np.array([[cz, -sz_, 0], [sz_, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _pivot_mat(pivot, rot) -> np.ndarray:
    M = np.eye(4)
    if rot is not None and any(abs(float(v)) > 1e-9 for v in rot):
        p = np.asarray(pivot, float)
        R = _rotm(rot)
        M[:3, :3] = R
        M[:3, 3] = p - R @ p
    return M


def cube_world_matrices(model) -> Dict[int, np.ndarray]:
    """{id(cube): 4x4}。休みの姿勢（ジオメトリに書いたボーンとキューブの rotation だけ）での
    キューブの局所座標 → モデル空間。3D ノイズをこの空間で引くので、回ったキューブ（指・腱・腸）や
    猫背で傾いた胸と腹の境でも模様が繋がる。"""
    bones = {b.name: b for b in getattr(model, "bones", [])}
    world: Dict[str, np.ndarray] = {}

    def bw(name, depth=0):
        if name in world:
            return world[name]
        b = bones[name]
        M = _pivot_mat(b.pivot or (0, 0, 0), b.rotation)
        par = getattr(b, "parent", None)
        if par and par in bones and depth < 64:
            M = bw(par, depth + 1) @ M
        world[name] = M
        return M

    out: Dict[int, np.ndarray] = {}
    for b in getattr(model, "bones", []):
        Wb = bw(b.name)
        for c in b.cubes:
            if c.rotation and any(c.rotation):
                piv = c.pivot or [c.origin[i] + c.size[i] / 2 for i in range(3)]
                out[id(c)] = Wb @ _pivot_mat(piv, c.rotation)
            else:
                out[id(c)] = Wb
    return out


# 面の u/v がキューブのどの軸か、法線がどの軸か（0=X,1=Y,2=Z）
_FACE_AXES = {"north": (0, 1, 2), "south": (0, 1, 2), "east": (2, 1, 0), "west": (2, 1, 0),
              "up": (0, 2, 1), "down": (0, 2, 1)}
# 側面が箱を一周する順（u の向きに繋がる。mcmodel の矩形も左からこの順に並ぶ）
_SIDE_RING = ("east", "north", "west", "south")


def _build_field(entries, ybounds, seed, H=0, W=0, mats=None) -> Field:
    """entries: [(cube_index, cube, face, rect)]。H, W はアトラスの寸法（隣接参照用）。
    mats: {id(cube): 4x4}（cube_world_matrices）。あればキューブの局所座標をモデル空間へ移す。"""
    nf = len(entries)
    x0 = np.empty(nf, np.int64)
    y0 = np.empty(nf, np.int64)
    w = np.empty(nf, np.int64)
    h = np.empty(nf, np.int64)
    sc = np.empty(nf, f32)
    fc = np.empty(nf, np.int8)
    ci = np.empty(nf, np.int32)
    O = np.empty((nf, 3), f32)
    A = np.empty((nf, 3), f32)
    B = np.empty((nf, 3), f32)
    off = np.empty((nf, 2), f32)
    along = np.empty(nf, np.int8)    # 0: 長軸が v 方向, 1: u 方向, 2: 面に垂直
    for i, (k, cube, face, rect) in enumerate(entries):
        x0[i], y0[i], w[i], h[i] = rect
        s = float(cube._scale or 1)
        sc[i] = s
        fc[i] = _FCODE[face]
        ci[i] = k
        o, a, b = _face_frame(face, cube.origin, cube.size)
        M = mats.get(id(cube)) if mats else None
        if M is not None:
            Rm = M[:3, :3]
            o = Rm @ np.asarray(o, float) + M[:3, 3]
            a = Rm @ np.asarray(a, float)
            b = Rm @ np.asarray(b, float)
        O[i] = o
        A[i] = a
        B[i] = b
        if face in SIDES:
            # 側面は帯（east → north → west → south）の通しの座標にする: 細かい 2D の模様も
            # 側面の角 3 つでは切れずに回り込む（ずらしはキューブごと）
            hh = _seed(seed, k, "side")
            pu = 0.0
            for f_ in _SIDE_RING[:_SIDE_RING.index(face)]:
                r_ = cube.rects.get(f_)
                pu += (r_[2] if r_ is not None and r_[2] > 0 else
                       max(1, int(round(cube.size[_FACE_AXES[f_][0]] * float(cube._scale or 1)))))
            off[i] = ((hh & 0xFFFF) / 65535.0 * 97.0 + pu / float(cube._scale or 1),
                      ((hh >> 16) & 0x7FFF) / 32767.0 * 89.0)
        else:
            hh = _seed(seed, k, face)
            off[i] = ((hh & 0xFFFF) / 65535.0 * 97.0, ((hh >> 16) & 0x7FFF) / 32767.0 * 89.0)
        size = list(cube.size)
        # 同じ長さなら縦（Y）を長軸とみなす
        la = max(range(3), key=lambda ax_: (size[ax_] + (0.01 if ax_ == 1 else 0.0)))
        ua, va, na = _FACE_AXES[face]
        along[i] = 0 if la == va else (1 if la == ua else 2)
    counts = (w * h).astype(np.int64)
    total = int(counts.sum())
    idx = np.repeat(np.arange(nf), counts)
    start = np.cumsum(counts) - counts
    kk = np.arange(total, dtype=np.int64) - start[idx]
    Wf = w[idx]
    Hf = h[idx]
    lxi = kk % Wf
    lyi = kk // Wf
    F = Field()
    F.n = total
    F.H = int(H or (y0 + h).max())
    F.W = int(W or (x0 + w).max())
    F.fid = idx.astype(np.int32)
    F.lxi = lxi
    F.lyi = lyi
    F.fwi = Wf
    F.fhi = Hf
    F.ax = (x0[idx] + lxi).astype(np.int64)
    F.ay = (y0[idx] + lyi).astype(np.int64)
    F.lx = lxi.astype(f32) + f32(0.5)
    F.ly = lyi.astype(f32) + f32(0.5)
    F.fw = Wf.astype(f32)
    F.fh = Hf.astype(f32)
    F.fa = F.lx / F.fw
    F.fb = F.ly / F.fh
    F.s = sc[idx]
    F.face = fc[idx]
    F.side = F.face >= 2
    F.cid = ci[idx]
    F.crnd = _u01(_fin(F.cid.astype(np.uint32) * _P1 ^ np.uint32(seed & 0xFFFFFFFF)))
    P = O[idx] + A[idx] * F.fa[:, None] + B[idx] * F.fb[:, None]
    F.X = P[:, 0].copy()
    F.Y = P[:, 1].copy()
    F.Z = P[:, 2].copy()
    F.U = F.lx / F.s + off[idx, 0]
    F.V = F.ly / F.s + off[idx, 1]
    al = along[idx]
    F.along = al
    F.Ua = np.where(al == 1, F.V, F.U)
    F.Va = np.where(al == 1, F.U, F.V)
    F.endon = al == 2
    d_l = F.lx
    d_r = F.fw - F.lx
    d_t = F.ly
    d_b = F.fh - F.ly
    F.ed = np.minimum(np.minimum(d_l, d_r), np.minimum(d_t, d_b))
    F.edh = np.minimum(d_l, d_r)
    F.edt = d_t
    F.edu = F.ed / F.s
    F.yrel = np.where(F.side, 1.0 - F.fb, np.where(F.face == 0, 1.0, 0.0)).astype(f32)
    y_lo, y_hi = ybounds
    F.Ym = np.clip((F.Y - y_lo) / max(1e-3, y_hi - y_lo), 0, 1).astype(f32)
    return F


def _streak(F, fv, sd, width=1.0, along=None):
    """1 texel 幅の筋（髪・ブラシ目・錆だれ・木目の細部）。along=None なら長軸方向（Va）。
    列ごとに独立した乱数を、筋の方向にはゆっくり変化させる。0..1。"""
    if along is None:
        along_u = F.along == 1
    else:
        along_u = np.full(F.n, along == "u")
    col_k = np.where(along_u, F.lyi, F.lxi).astype(f32)
    run = np.where(along_u, F.U, F.V)
    k = np.floor(col_k / f32(width)) + F.fid.astype(f32) * f32(131.0)
    a = vnoise2(k, run * f32(fv), sd)
    b = vnoise2(k + 0.5, run * f32(fv * 2.3) + 7.1, sd + 1)
    return (a * 0.7 + b * 0.3).astype(f32)


def _drip_mask(F, src, amt, sd):
    """側面で、src（血の染み）の下端から下へ垂れる筋。アトラス上で列ごとに「上にある直近の染み」
    からの距離を測る（同じ面の中だけ）。戻り値 (覆い 0/1, 先端の照り bool)。"""
    z = np.zeros(F.n, f32)
    if not F.side.any():
        return z, z.astype(bool)
    m = np.asarray(src, bool) & F.side
    buf = np.full((F.H, F.W), -1, np.int64)
    buf[F.ay[m], F.ax[m]] = F.ay[m]
    last = np.maximum.accumulate(buf, axis=0)[F.ay, F.ax]
    top = F.ay - F.lyi
    valid = F.side & (last >= top) & ~m
    d = (F.ay - last).astype(f32)
    h = hash2i(F.ax.astype(np.uint32), (top * 31 + F.fid).astype(np.uint32), sd)
    act = _u01(h) < f32(0.16 + 0.4 * amt)
    h2 = _fin(h ^ np.uint32(0x51ED270B))
    L = np.maximum(f32(1.5), (0.4 + 4.6 * _u01(h2) ** 1.8) * F.s * f32(0.35 + 0.65 * amt))
    body = valid & act & (d <= L)
    tip = body & (d > L - 1.0)
    side_tip = (F.nb(tip, 1, 0) | F.nb(tip, -1, 0)) & (F.s >= 3) & F.side & ~tip
    cov = body | side_tip
    glint = F.nb(tip, 0, 1) & body & (_u01(_fin(h2 ^ np.uint32(0x2C1B3C6D))) < 0.7)
    return cov.astype(f32), glint


def _iso(F, fu, sd, octaves=3, warp=0.0, width=1.0, U=None, V=None, levels=(0.5,)):
    """fbm2 の等値線を「幅 width texel の線」にする（勾配で割るので線の太さが一定で途切れない）。
    静脈・脳溝・ひび割れ用。戻り値 (線 0..1, 線までの距離 texel, ノイズ値)。"""
    U = F.U if U is None else U
    V = F.V if V is None else V
    dd = f32(0.02)
    n0 = _n2(F, fu, fu, sd, octaves, U=U, V=V, warp=warp)
    nx = _n2(F, fu, fu, sd, octaves, U=U + dd, V=V, warp=warp)
    ny = _n2(F, fu, fu, sd, octaves, U=U, V=V + dd, warp=warp)
    g = np.sqrt(((nx - n0) / dd) ** 2 + ((ny - n0) / dd) ** 2) + f32(1e-3)
    dist = np.full(F.n, 1e9, f32)
    for lv in levels:
        dist = np.minimum(dist, np.abs(n0 - f32(lv)) / g * F.s)
    line = np.clip(f32(width) / 2 + 0.5 - dist, 0, 1)
    return line, dist, n0


def _n3(F, freq, sd, octaves=3, warp=0.0, sy=1.0):
    x, y, z = F.X * f32(freq), F.Y * f32(freq * sy), F.Z * f32(freq)
    if warp:
        wx = fbm3(x + 31.7, y, z, sd + 71, 2) - 0.5
        wy = fbm3(x, y + 11.3, z, sd + 72, 2) - 0.5
        x = x + wx * f32(warp)
        y = y + wy * f32(warp)
    return fbm3(x, y, z, sd, octaves, tpc=F.s / f32(freq))


def _n2(F, fu, fv, sd, octaves=3, U=None, V=None, warp=0.0):
    U = F.U if U is None else U
    V = F.V if V is None else V
    x, y = U * f32(fu), V * f32(fv)
    if warp:
        wx = fbm2(x + 5.2, y + 1.3, sd + 51, 2) - 0.5
        wy = fbm2(x + 1.7, y + 9.2, sd + 52, 2) - 0.5
        x = x + wx * f32(warp)
        y = y + wy * f32(warp)
    return fbm2(x, y, sd, octaves, tpc=F.s / f32(max(fu, fv)))


def _grain(F, sd):
    return texel_rand(F.ax, F.ay, sd)


def _P(p, key, default):
    v = p.get(key, default)
    return default if v is None else v


# ---------------------------------------------------------------------------
#  素材（material）。戻り値は (N,3) float32 の色。F.glow / F.wetm を書いてよい
# ---------------------------------------------------------------------------
_BLOOD = _rgb((112, 6, 10))
_BLOOD_DK = _rgb((58, 2, 6))
_BLOOD_HI = _rgb((168, 22, 22))
_GLINT = _rgb((238, 196, 188))

# 血の種類（nr_spec_zombies.BLOOD_VOCAB と同じ色）。style の blood_kind で選ぶ
BLOOD_KINDS = {
    "red":   dict(spray=(176, 18, 20), pool=(96, 8, 10), clot=(70, 10, 10), emissive=False),
    "dark":  dict(spray=(104, 26, 20), pool=(58, 14, 12), clot=(40, 12, 10), emissive=False),
    "black": dict(spray=(30, 12, 18), pool=(16, 6, 10), clot=(10, 4, 6), emissive=False),
    "bile":  dict(spray=(150, 160, 40), pool=(96, 104, 26), clot=(70, 74, 20), emissive=False),
    "acid":  dict(spray=(130, 240, 50), pool=(70, 160, 30), clot=(50, 110, 20), emissive=True),
    "ash":   dict(spray=(110, 104, 98), pool=(70, 66, 62), clot=(40, 36, 32), emissive=False),
    "water": dict(spray=(180, 120, 120), pool=(120, 80, 84), clot=(90, 50, 54), emissive=False),
    "ember": dict(spray=(255, 130, 40), pool=(30, 16, 10), clot=(60, 20, 10), emissive=True),
}


def _blood_cols(kind):
    """(明るい飛沫, 溜まり, 濃い塊) の 3 色と、光るかどうか。"""
    b = BLOOD_KINDS.get(kind or "red", BLOOD_KINDS["red"])
    pool = _rgb(b["pool"])
    if kind in (None, "red"):
        return _BLOOD_HI, _BLOOD, _BLOOD_DK, False
    return _rgb(b["spray"]) * 0.95, pool, _rgb(b["clot"]) * 0.85, bool(b["emissive"])


def _flesh_colour(F, sd, base=(124, 22, 24), wet=0.7, fat=0.02):
    """露出した筋肉。深い赤のむら、長軸に沿った控えめな筋線維、束の境目の暗い溝、白っぽい腱膜。"""
    base = _rgb(base)
    dark = base * f32(0.42)
    light = np.minimum(255, base * f32(1.22) + f32(14))
    ua, va = F.Ua, F.Va
    fib = _streak(F, 0.7, sd + 1)
    warp = _n2(F, 0.5, 0.15, sd + 2, 2, U=ua, V=va) - 0.5
    bq = ua * f32(0.7) + warp * f32(1.0)
    bd = np.abs(bq - np.round(bq)) / f32(0.7) * F.s            # 溝からの距離（texel）
    groove = 1.0 - _ss(0.3, 1.2, bd)
    big = _n3(F, 0.3, sd + 3, 3)
    mid = _n2(F, 0.9, 0.55, sd + 9, 2, U=ua, V=va)
    t = 0.5 + (big - 0.5) * 0.9 + (mid - 0.5) * 0.4 + (fib - 0.5) * 0.2 + (_grain(F, sd + 4) - 0.5) * 0.1 \
        - groove * 0.25
    col = _ramp(t, [(0.0, dark * 0.55), (0.3, dark), (0.55, base), (0.85, light), (1.1, light)])
    # 束の丸み（溝の近くが暗く、束の中ほどが明るい）
    col = col * (0.9 + 0.12 * _ss(0.5, 2.5, bd))[:, None]
    if F.endon.any():
        F1, F2, cid, _, _ = worley2(F.U * f32(1.4), F.V * f32(1.4), sd + 5)
        edge = 1.0 - _ss(0.0, 0.16, F2 - F1)
        tc = 0.55 + (cid - 0.5) * 0.35 + (_grain(F, sd + 6) - 0.5) * 0.15 - edge * 0.3
        cc = _ramp(tc, [(0.0, dark), (0.55, base), (1.0, light)])
        cc = _mix(cc, _rgb((190, 146, 138)), edge * 0.3)
        col = np.where(F.endon[:, None], cc, col)
    sheen = _ss(0.66, 0.82, _n2(F, 0.35, 0.1, sd + 7, 3, U=ua, V=va)) * (1 - groove)
    col = _mix(col, _rgb((196, 150, 144)), sheen * 0.4)
    if fat > 0:
        fz = _ss(_thr(fat) - 0.01, _thr(fat) + 0.03, _n3(F, 1.1, sd + 8, 2))
        col = _mix(col, _rgb((180, 150, 92)), fz * 0.75)
    if wet > 0:
        F.wetm = np.maximum(F.wetm if F.wetm is not None else 0, f32(wet))
    return col


def _sx(p, key, default):
    """肌の追加パラメータ: style に直接あればそれ、無ければ tone（SKINS の項目）の値。"""
    if p.get(key) is not None:
        return p[key]
    t = p.get("tone")
    if isinstance(t, str):
        t = SKINS.get(t, {})
    if isinstance(t, dict) and t.get(key) is not None:
        return t[key]
    return default


def m_skin(F, p, sd):
    base, shd, hil = _tone(p)
    decay = float(_P(p, "decay", 1))
    dk = min(1.0, decay / 4.0)
    di = int(min(4, max(0, round(decay))))
    # 死後の退色: 彩度を落として少し暗く、灰緑へ寄せる。陰は冷たい紫灰に。
    # decay_tint: SKINS の系統（色そのものが腐敗を表す）は控えめにする（zombie_styles が 0.35 を渡す）
    tint_k = float(_sx(p, "decay_tint", 1.0))
    g = float(base.mean())
    sat_loss = (0.2 + 0.3 * dk) * tint_k
    dim = f32(1.0 - (0.03 + 0.07 * dk) * tint_k)
    base = (base + (f32(g) - base) * f32(sat_loss)) * dim
    hil = (hil + (f32(hil.mean()) - hil) * f32(sat_loss)) * dim
    green = _rgb((136, 146, 112)) * f32(g / 140.0) * dim
    base = base + (green - base) * f32(min(0.45, 0.14 * decay) * tint_k)
    shd = shd + (_rgb((66, 60, 78)) * f32(g / 150.0) - shd) * f32((0.3 + 0.2 * dk) * (0.5 + 0.5 * tint_k))
    # 明暗: 大（3D）・中（3D）・細（2D）・texel の粒（粒は控えめ。強いと花崗岩に見える）
    big = _n3(F, 0.14, sd + 1, 2)
    mid = _n3(F, 0.55, sd + 2, 3, warp=0.5)
    fine = _n2(F, 1.5, 1.5, sd + 3, 2)
    gr = _grain(F, sd + 4)
    t = 0.5 + (big - 0.5) * 0.5 + (mid - 0.5) * 0.5 + (fine - 0.5) * 0.32 + (gr - 0.5) * 0.12
    col = _ramp(t, [(-0.1, shd * 0.85), (0.08, shd), (0.5, base), (0.92, hil), (1.1, hil)])
    # 色むら（境目の無い柔らかい変化）: 冷たい青灰・黄ばみ・下に溜まる赤紫の死斑・腐敗の緑
    cold = _ss(0.45, 0.85, _n3(F, 0.33, sd + 5, 2, warp=0.8))
    col = col * (1.0 + cold[:, None] * np.array([-0.05, -0.01, 0.03], f32))
    warm = _ss(0.45, 0.85, _n3(F, 0.28, sd + 6, 2))
    col = col * (1.0 + warm[:, None] * np.array([0.05, 0.02, -0.07], f32))
    liv = np.clip(_ss(0.4, 0.8, _n3(F, 0.24, sd + 7, 3, warp=1.0)) * (0.35 + 0.65 * (1 - F.Ym)), 0, 1)
    liv = liv * f32(0.3 + 0.4 * dk)
    mot = _sx(p, "mottle", None)
    if mot is None:
        col = col * (1.0 - liv[:, None] * np.array([0.06, 0.18, 0.15], f32))
    else:
        col = _mix(col, col * 0.45 + _rgb(mot) * 0.55 * f32(g / 150.0) ** 0.3, liv * 0.8)
    grn = _ss(0.45, 0.82, _n3(F, 0.3, sd + 8, 3, warp=1.0)) * f32(0.1 + 0.45 * dk)
    col = col * (1.0 + grn[:, None] * np.array([-0.12, -0.03, -0.15], f32))
    hgt = np.zeros(F.n, f32)
    # 静脈（枝分かれする 1 texel の暗い線）。腐敗が進むと緑黒い「大理石模様」に
    veins = float(_sx(p, "veins", 0.5 + 0.12 * decay))
    if veins > 0:
        line, dist, vn = _iso(F, 0.4, sd + 9, 3, warp=1.4, width=1.0)
        line2, _, _ = _iso(F, 0.95, sd + 10, 2, warp=1.0, width=0.8)
        near = _ss(5.0, 1.5, dist)                       # 太い静脈の近くにだけ細い枝
        halo = _ss(3.0, 0.5, dist)
        vis = _ss(0.36, 0.6, _n3(F, 0.18, sd + 11, 2))
        vm = np.clip(line + line2 * near * 0.7, 0, 1) * vis * f32(min(1.0, veins * 1.5))
        vc = _sx(p, "vein", None)
        if vc is None:
            vcol = _rgb((84, 92, 136)) * f32(1 - dk) + _rgb((40, 52, 38)) * f32(dk)
            if decay >= 2:
                vcol = vcol * 0.7 + _rgb((66, 32, 52)) * 0.3
        else:
            vcol = _rgb(vc) * f32(1 - 0.35 * dk) + _rgb((40, 52, 38)) * f32(0.35 * dk)
        if decay >= 0.5:
            col = _mix(col, col * np.array([0.86, 0.88, 0.82], f32), halo * vis * f32(min(1.0, decay / 2.0) * 0.6))
        col = _mix(col, col * 0.35 + vcol * 0.65, vm * 0.75)
        hgt += line * vis * 0.25            # 浮き出た静脈
    # 打撲（紫の芯→ほんのり黄緑の縁。境目はぼかす）
    bru = float(_sx(p, "bruises", 0.08 + 0.05 * decay))
    if bru > 0:
        b = _n3(F, 0.2, sd + 12, 3, warp=1.2)
        th = _thr(bru * 0.35)
        e = (b - th) / 0.1
        rim = _ss(-1.2, 0.0, e) * (1 - _ss(0.0, 0.8, e))
        core = _ss(-0.2, 1.4, e)
        col = col * (1.0 + rim[:, None] * np.array([0.02, 0.01, -0.08], f32))
        col = _mix(col, col * np.array([0.62, 0.48, 0.62], f32), core * 0.75)
    # 腐敗の斑（黄緑→紫→黒。縁はぼかす）
    rot = float(_P(p, "rot", [0.0, 0.05, 0.12, 0.18, 0.28][di]))
    if rot > 0:
        r = _n3(F, 0.3, sd + 13, 3, warp=1.2)
        th = _thr(rot)
        e = (r - th) / 0.1
        m = _ss(-1.2, 0.6, e)
        col = col * (1.0 - m[:, None] * np.array([0.22, 0.18, 0.32], f32))          # 濁ったオリーブへ
        spot = _n2(F, 0.9, 0.9, sd + 23, 2)
        deep = _ss(0.4, 1.8, e) * _ss(0.42, 0.62, spot)
        col = _mix(col, col * np.array([0.42, 0.33, 0.4], f32), deep * 0.85)        # 紫黒い斑
        black = _ss(1.6, 2.6, e) * _ss(0.5, 0.7, spot)
        col = _mix(col, _rgb((22, 17, 16)), black * 0.8)
        F.wetm = np.maximum(F.wetm if F.wetm is not None else 0, deep * 0.35)
    # 爛れ・かさぶた・膿疱（ゆがんだ Worley。種類も大きさもばらばら）
    # 既定の量は控えめ（多いと全身に血が飛んだ「そばかす」に見える）
    les = float(_P(p, "lesions", [0.0, 0.04, 0.1, 0.16, 0.24][di]))
    if les > 0:
        wu = (_n2(F, 0.9, 0.9, sd + 14, 2) - 0.5) * 1.1
        wv = (_n2(F, 0.9, 0.9, sd + 15, 2) - 0.5) * 1.1
        cf = 0.55
        F1, F2, cid, vx, vy = worley2((F.U + wu) * f32(cf), (F.V + wv) * f32(cf), sd + 16)
        act = cid < f32(les)
        hb = _fin((cid * 16777216).astype(np.uint32) ^ np.uint32(sd & 0xFFFF))
        rr = np.maximum(0.09 + 0.24 * _u01(hb) ** 1.5, f32(0.7 * cf) / F.s)
        # 小さな面（鼻先・指・耳）を 1 つの爛れが覆い尽くして「赤い四角」にならないように
        rr = np.minimum(rr, np.maximum(f32(0.3 * cf) * np.minimum(F.fw, F.fh) / F.s, f32(0.7 * cf) / F.s))
        kind = _u01(_fin(hb ^ np.uint32(0x632BE5AB)))
        d = F1 / rr
        halo = act * _ss(2.2, 0.9, d)
        col = col * (1.0 - halo[:, None] * np.array([-0.02, 0.13, 0.11], f32))
        inside = act & (d < 1.0)
        scab = inside & (kind < 0.45)
        sore = inside & (kind >= 0.45) & (kind < 0.85)
        pus = inside & (kind >= 0.85)
        gr2 = _grain(F, sd + 17)
        sc = _ramp(gr2 * 0.5 + d * 0.5, [(0.0, (34, 16, 12)), (0.5, (62, 30, 20)), (1.0, (96, 50, 34))])
        so = _ramp(d + (gr2 - 0.5) * 0.25, [(0.0, (38, 8, 8)), (0.45, (72, 22, 18)), (0.85, (108, 44, 34)),
                                            (1.0, (128, 66, 54))])
        pu = _ramp(d + (gr2 - 0.5) * 0.2, [(0.0, (214, 198, 140)), (0.45, (186, 160, 96)), (0.75, (140, 54, 44)),
                                           (1.0, (124, 52, 46))])
        col = np.where(scab[:, None], sc, col)
        col = np.where(sore[:, None], so, col)
        col = np.where(pus[:, None], pu, col)
        hgt += scab * (1 - d) * 0.6 + pus * (1 - d) * 0.8 - sore * (1 - d) * 0.9
        F.wetm = np.maximum(F.wetm if F.wetm is not None else 0, (sore | pus) * 0.9)
    # 皮膚が剥がれて肉が見える所（decay 2 以上）
    expo = float(_sx(p, "exposed", [0.0, 0.0, 0.02, 0.05, 0.13][di]))
    if expo > 0:
        # 大きめの斑を少しだけ（細かい斑が全身に散ると血しぶきに見える）
        f = _n3(F, 0.2, sd + 18, 3, warp=1.2)
        th = _thr(expo)
        e = (f - th) / (0.08 / np.sqrt(F.s))
        peel = _ss(-2.0, -1.3, e) * (1 - _ss(-1.3, -0.8, e))      # めくれた皮の縁（少し明るい）
        crust = _ss(-1.0, -0.4, e) * (1 - _ss(0.2, 0.8, e))       # 乾いた黒い縁
        inside = _ss(0.0, 0.6, e)
        col = col * (1.0 + peel[:, None] * np.array([0.07, 0.06, 0.02], f32))
        col = _mix(col, _rgb((50, 18, 14)), crust * 0.85)
        fl = _flesh_colour(F, sd + 19, base=(116, 20, 22), wet=0.0, fat=0.03)
        # 腐って黒ずんだ肉（傷口の新しい赤と区別する）
        fl = _mix(fl, fl * np.array([0.62, 0.85, 0.75], f32) + _rgb((24, 14, 8)), np.full(F.n, 0.7, f32))
        if expo > 0.4:
            # 皮の無い体: 長軸に沿った黄色い脂肪の筋と白い腱
            tend = _ss(0.72, 0.86, _streak(F, 0.3, sd + 24))
            fl = _mix(fl, _rgb(_sx(p, "mottle", (220, 200, 160))) * 0.85, tend * 0.6)
        deep = _ss(0.8, 3.0, e)
        col = _mix(col, fl * (1.0 - deep * 0.35)[:, None], inside)
        hgt += peel * 0.3 - inside * 1.0 - crust * 0.3
        F.wetm = np.maximum(F.wetm if F.wetm is not None else 0, inside * 0.85)
    # 壊死（黒褐色の革のような皮膚、ひび）
    nec = float(_P(p, "necrosis", [0.0, 0.0, 0.0, 0.05, 0.22][di]))
    if nec > 0:
        f = _n3(F, 0.26, sd + 20, 3, warp=1.2)
        th = _thr(nec)
        m = _ss(th - 0.03, th + 0.05, f)
        crack, _, _ = _iso(F, 0.8, sd + 21, 2, warp=0.8, width=1.0)
        nc = _ramp(_n2(F, 0.8, 0.8, sd + 22, 2) + (gr - 0.5) * 0.15,
                   [(0.2, (24, 20, 16)), (0.5, (48, 38, 28)), (0.8, (62, 60, 40))])
        nc = nc * (1.0 - crack[:, None] * f32(0.5))
        col = _mix(col, nc, m * 0.95)
        hgt -= crack * m * 0.4
    # ひび割れ（炭化・乾燥）。割れ目の奥に vein 色（生肉・残り火）
    cracks = float(_sx(p, "cracks", 0.0))
    if cracks > 0:
        wu = (_n2(F, 0.7, 0.7, sd + 30, 2) - 0.5) * 0.9
        F1, F2, cid, vx, vy = worley2((F.U + wu) * f32(0.8), (F.V - wu) * f32(0.8), sd + 31)
        width = (0.08 + 0.08 * cracks) * 4.0 / np.maximum(F.s, 2.0)
        cr = 1.0 - _ss(0.0, width, F2 - F1)
        present = _ss(_thr(min(0.95, cracks)) - 0.04, _thr(min(0.95, cracks)) + 0.04, _n3(F, 0.35, sd + 32, 2))
        crm = cr * present
        dome = np.sqrt(np.clip(1 - (F1 / 0.9) ** 2, 0, 1))
        col = col * (1.0 + (dome - 0.6) * 0.3 * present + np.clip(vy, -1, 1) * 0.08 * present)[:, None]
        vc = _rgb(_sx(p, "vein", (110, 30, 24)))
        if _sx(p, "emissive_vein", False):
            hot = crm > 0.5
            ec = _ramp(crm + (gr - 0.5) * 0.4, [(0.4, vc * 0.6), (0.8, vc), (1.1, np.minimum(255, vc * 0.6 + 120))])
            col = np.where(hot[:, None], ec, col * (1.0 - crm[:, None] * 0.5))
            F.glow = hot if F.glow is None else (F.glow | hot)
        else:
            inner = _ramp(crm + (gr - 0.5) * 0.3, [(0.3, vc * 0.5), (0.9, vc), (1.1, vc * 1.2)])
            col = _mix(col, inner, crm)
        hgt -= crm * 0.6
    # 胞子・灰の粉
    spores = float(_sx(p, "spores", 0.0))
    if spores > 0:
        th = _thr(spores * 0.5)
        sm = _ss(th - 0.03, th + 0.06, _n3(F, 0.45, sd + 33, 3, warp=1.2))
        dust = sm * (gr > 0.55 - 0.35 * sm)
        col = _mix(col, _rgb(_sx(p, "mottle", (200, 200, 170))) * (0.86 + 0.2 * gr)[:, None], dust * 0.8)
    # 角度で青く照る（闇の捕食者）
    if _sx(p, "iridescent", False):
        hue = _n3(F, 0.35, sd + 34, 2)
        tint = _mix(np.broadcast_to(_rgb((50, 90, 170)), (F.n, 3)), np.broadcast_to(_rgb((120, 60, 150)), (F.n, 3)),
                    _ss(0.35, 0.65, hue))
        lum = _ss(0.45, 0.85, t + (fine - 0.5) * 0.5)
        col = col + tint * (lum * 0.45 + (F.face == 0) * 0.12)[:, None]
    wet = float(_sx(p, "wet", 0.0))
    if wet > 0:
        F.wetm = np.maximum(F.wetm if F.wetm is not None else 0, f32(wet * 0.7))
    col = col * F.emboss(hgt, 0.3)[:, None]
    return col


def m_flesh(F, p, sd):
    base = _P(p, "base", (128, 24, 26))
    col = _flesh_colour(F, sd, base=base, wet=float(_P(p, "wet", 0.7)), fat=float(_P(p, "fat", 0.0)))
    return col


def m_cut_flesh(F, p, sd):
    """切断面。断面の面（既定 up/down）は 皮膚の縁→黄色い脂肪の輪→赤い筋肉→（骨の断面）。
    それ以外の面は、裂けた肉と皮膚の縁から垂れる血。"""
    sect = p.get("section", ("up", "down"))
    sect_codes = np.array([_FCODE[f] for f in sect], dtype=np.int8)
    is_sec = np.isin(F.face, sect_codes)
    base, shd, hil = _tone(p if p.get("tone") else {"tone": "pale"})
    # 正規化座標（角の丸い四角）
    cx, cy = p.get("centre", (0.5, 0.5))
    x = (F.fa - f32(cx)) / f32(0.5)
    y = (F.fb - f32(cy)) / f32(0.5)
    ragged = (_n2(F, 1.3, 1.3, sd + 1, 2) - 0.5) * f32(0.16)
    r = (np.abs(x) ** 3 + np.abs(y) ** 3) ** (1 / 3) * (1.0 + ragged)
    # 筋肉（束の断面）
    F1, F2, cid, _, _ = worley2(F.U * f32(1.5), F.V * f32(1.5), sd + 2)
    memb = 1.0 - _ss(0.02, 0.14, F2 - F1)
    mt = 0.5 + (cid - 0.5) * 0.45 + (_grain(F, sd + 3) - 0.5) * 0.25 - memb * 0.3
    mus = _ramp(mt, [(0.0, (58, 6, 8)), (0.45, (112, 14, 16)), (0.8, (156, 34, 32)), (1.1, (186, 70, 60))])
    mus = _mix(mus, _rgb((200, 140, 130)), memb * 0.35)
    col = mus
    # 脂肪（ぶつぶつした黄色）
    fF1, fF2, fc, _, _ = worley2(F.U * f32(2.4), F.V * f32(2.4), sd + 4)
    ft = 0.55 + (fc - 0.5) * 0.4 - (1.0 - _ss(0.0, 0.2, fF2 - fF1)) * 0.3
    fat = _ramp(ft, [(0.0, (150, 112, 54)), (0.5, (214, 182, 98)), (1.0, (238, 214, 140))])
    fat_in = float(_P(p, "fat", 0.76))
    m_fat = _ss(fat_in - 0.04, fat_in + 0.02, r)
    col = _mix(col, fat, m_fat)
    # 皮膚の縁
    m_skin_ = _ss(0.88, 0.93, r)
    sk = _ramp(_grain(F, sd + 5), [(0.0, shd), (0.6, base), (1.0, hil)])
    col = _mix(col, sk, m_skin_)
    col = col * (1.0 - _ss(0.96, 1.05, r)[:, None] * f32(0.35))
    # 骨の断面
    if _P(p, "bone", True):
        bx, by = p.get("bone_at", (0.0, 0.0))
        br = float(_P(p, "bone_r", 0.26))
        rb = np.sqrt((x - f32(bx)) ** 2 + (y - f32(by)) ** 2) / f32(br)
        cort = _ramp(_grain(F, sd + 6), [(0.0, (196, 184, 156)), (1.0, (238, 230, 210))])
        marrow = _ramp(_grain(F, sd + 7), [(0.0, (96, 30, 22)), (0.5, (140, 60, 40)), (1.0, (176, 104, 70))])
        bone = _mix(cort, marrow, _ss(0.62, 0.48, rb))
        mb = _ss(1.08, 0.94, rb)
        col = _mix(col, col * 0.5, _ss(1.35, 1.0, rb) * (1 - mb))      # 骨の周りの暗い溝
        col = _mix(col, bone, mb)
    # 断面以外の面: 裂けた肉 + 皮の縁 + 垂れる血
    side_col = _flesh_colour(F, sd + 8, base=(130, 22, 24), wet=0.0, fat=0.05)
    rag = _n2(F, 1.6, 0.4, sd + 9, 2)
    skin_band = _ss(0.45, 0.55, F.fb + (rag - 0.5) * 0.5)   # 下ほど皮膚が残る
    side_col = _mix(side_col, _mix(sk, _BLOOD, f32(0.25)), skin_band * 0.85)
    col = np.where(is_sec[:, None], col, side_col)
    # 全体を血で濡らす
    wet = _ss(0.45, 0.8, _n3(F, 0.8, sd + 10, 2)) * f32(0.55)
    col = _mix(col, col * np.array([0.7, 0.25, 0.25], f32), wet * (1 - m_skin_ * 0.5))
    F.wetm = np.full(F.n, 0.85, f32)
    return col


def m_bone(F, p, sd):
    base = _rgb(_P(p, "base", (222, 210, 180)))
    age = float(_P(p, "age", 0.4))
    t = 0.55 + (_n3(F, 0.5, sd + 1, 3) - 0.5) * 0.8 + (_grain(F, sd + 2) - 0.5) * 0.2
    stri = _n2(F, 2.2, 0.25, sd + 3, 2, U=F.Ua, V=F.Va)
    t = t + (stri - 0.5) * 0.35
    col = _ramp(t, [(0.0, base * np.array([0.52, 0.47, 0.38], f32)), (0.45, base * 0.86),
                    (0.8, base), (1.1, np.minimum(255, base * 1.08))])
    # 黄ばみ・茶色い染み
    st = _ss(0.55, 0.85, _n3(F, 0.4, sd + 4, 3, warp=1.0)) * f32(0.4 + age)
    col = col * (1.0 - st[:, None] * np.array([0.18, 0.26, 0.42], f32))
    # 小さな穴（骨の多孔質）
    F1, _, cid, _, _ = worley2(F.U * f32(2.6), F.V * f32(2.6), sd + 5)
    pit = (cid < 0.35) * _ss(0.22, 0.08, F1)
    col = col * (1.0 - pit[:, None] * f32(0.35))
    # ひび
    cr = 1.0 - _ss(0.0, 0.022, np.abs(_n2(F, 0.6, 0.6, sd + 6, 3, warp=1.0) - 0.5))
    col = col * (1.0 - (cr * _ss(0.5, 0.7, _n3(F, 0.3, sd + 7, 2)))[:, None] * f32(0.5))
    F.hard = True
    return col


def m_teeth(F, p, sd):
    base = _rgb(_P(p, "base", (206, 192, 146)))
    decay = float(_P(p, "decay", 2))
    # 歯 1 本の幅（単位）。密度が低くても 2 texel は取る
    tw = np.maximum(f32(_P(p, "tooth_w", 0.55)), f32(2.0) / F.s)
    q = F.U / tw
    k = np.floor(q)
    fr = q - k
    th = _u01(hash2i(k.astype(np.int64).astype(np.uint32), F.cid.astype(np.uint32), sd))
    gap = (fr < (f32(1.0) / (tw * F.s)))                     # 歯と歯の間（1 texel）
    shade = 0.55 + 0.45 * np.sin(fr * f32(math.pi)) ** 0.5     # 歯の丸み
    t = shade * (0.85 + th * 0.3) + (_grain(F, sd + 1) - 0.5) * 0.15
    col = _ramp(t, [(0.2, base * 0.45), (0.7, base * 0.85), (1.0, base), (1.2, np.minimum(255, base * 1.1))])
    # 歯茎側の茶色い歯石・腐敗
    gum_side = F.fb if _P(p, "row", "upper") == "upper" else 1.0 - F.fb
    stain = _ss(0.5, 0.0, gum_side) * f32(0.4 + 0.15 * decay) + _ss(0.6, 0.85, th) * 0.4
    col = col * (1.0 - stain[:, None] * np.array([0.32, 0.42, 0.62], f32))
    col = np.where(gap[:, None], col * 0.28, col)
    # 抜けた歯
    miss = (th < f32(0.06 + 0.04 * decay)) & F.side
    col = np.where(miss[:, None], _rgb((26, 8, 8)) + col * 0.05, col)
    F.hard = True
    return col


def m_gums(F, p, sd):
    base = _rgb(_P(p, "base", (150, 58, 66)))
    t = 0.5 + (_n2(F, 1.2, 1.2, sd + 1, 3) - 0.5) * 0.9 + (_grain(F, sd + 2) - 0.5) * 0.2
    col = _ramp(t, [(0.0, base * 0.45), (0.5, base), (1.0, np.minimum(255, base * 1.3 + 10))])
    rot = _ss(0.6, 0.8, _n3(F, 0.7, sd + 3, 2))
    col = _mix(col, _rgb((58, 22, 28)), rot * 0.7)
    F.wetm = np.full(F.n, 0.8, f32)
    return col


def m_guts(F, p, sd):
    """腸。蛇行するチューブ（円筒の陰影）、谷の暗がり、紫の血管、濡れた照り。"""
    base = _rgb(_P(p, "base", (190, 116, 112)))
    warp = _n2(F, 0.45, 0.45, sd + 1, 2) - 0.5
    q = F.Va * f32(0.85) + warp * f32(1.6) + (_n2(F, 0.25, 0.25, sd + 2, 2) - 0.5) * 1.2
    tq = q - np.floor(q)
    cyl = np.sin(tq * f32(math.pi))                   # 0 = 谷, 1 = チューブの頂
    seg = _n2(F, 0.9, 0.9, sd + 3, 2)                 # 節のくびれ
    t = 0.18 + cyl * 0.75 + (seg - 0.5) * 0.3 + (_grain(F, sd + 4) - 0.5) * 0.12
    col = _ramp(t, [(0.0, (46, 12, 16)), (0.25, base * np.array([0.55, 0.42, 0.45], f32)),
                    (0.65, base), (0.95, np.minimum(255, base * 1.18 + 12))])
    # 腐った部分（灰緑）
    rot = _ss(0.6, 0.85, _n3(F, 0.5, sd + 5, 2)) * f32(_P(p, "rot", 0.5))
    col = _mix(col, col * np.array([0.72, 0.8, 0.62], f32), rot)
    # 血管
    vn = _n2(F, 1.1, 1.1, sd + 6, 2, warp=1.2)
    vm = (1.0 - _ss(0.0, 0.03, np.abs(vn - 0.5))) * _ss(0.3, 0.6, cyl)
    col = _mix(col, _rgb((110, 50, 92)), vm * 0.6)
    # 照り（チューブの頂の上側）
    hl = _ss(0.86, 0.97, np.sin((tq - f32(0.12)) * f32(math.pi))) * _ss(0.4, 0.7, _grain(F, sd + 7) + 0.3)
    col = _mix(col, _GLINT, hl * 0.55)
    F.wetm = np.full(F.n, 0.9, f32)
    return col


def m_brain(F, p, sd):
    """脳。曲がりくねった溝（脳溝 = 等値線）と、溝から離れるほど盛り上がる回、細い血管、濡れ。"""
    base = _rgb(_P(p, "base", (196, 154, 148)))
    sul, dist, n = _iso(F, 0.5, sd + 1, 1, warp=1.8, width=1.0, levels=(0.4, 0.6))
    gyr = _ss(0.0, 2.0, dist)
    t = 0.2 + gyr * 0.65 + (_grain(F, sd + 2) - 0.5) * 0.08 + (_n3(F, 0.4, sd + 3, 2) - 0.5) * 0.3
    col = _ramp(t, [(0.0, (96, 40, 46)), (0.35, base * 0.72), (0.75, base), (1.0, np.minimum(255, base * 1.08))])
    col = _mix(col, _rgb((64, 14, 20)), sul * 0.85)
    vm, _, _ = _iso(F, 0.5, sd + 4, 2, warp=1.0, width=0.8)
    vm = vm * _ss(0.42, 0.62, _n3(F, 0.3, sd + 5, 2))
    col = _mix(col, _rgb((150, 30, 36)), vm * 0.6)
    col = col * F.emboss(gyr, 0.22)[:, None]
    F.wetm = np.full(F.n, 0.6, f32)
    return col


def m_blood(F, p, sd):
    """新しい血（濡れて艶がある）。厚い所は黒っぽく、薄い所は明るい赤。側面は縦に流れる。"""
    kind = p.get("blood_kind", "red")
    base = _rgb(_P(p, "base", (104, 6, 10) if kind == "red" else _blood_cols(kind)[1] * 1.08))
    th = _n3(F, 0.45, sd + 1, 3, warp=1.0)
    if F.side.any():
        run = _streak(F, 0.25, sd + 2, along="v")
        th = np.where(F.side, th * 0.65 + run * 0.35, th)
    t = th + (_grain(F, sd + 3) - 0.5) * 0.06
    col = _ramp(t, [(0.15, (156, 22, 22)), (0.4, base * 1.12), (0.6, base * 0.8), (0.85, base * 0.5),
                    (1.0, base * 0.4)])
    col = col * F.emboss(th * 4.0, 0.18)[:, None]
    F.wetm = np.full(F.n, 1.0, f32)
    if _blood_cols(kind)[3]:
        F.glow = np.ones(F.n, bool)
    return col


def m_blood_dry(F, p, sd):
    kind = p.get("blood_kind", "red")
    base = _rgb(_P(p, "base", (74, 24, 18) if kind == "red" else _blood_cols(kind)[2] * 1.1))
    t = 0.5 + (_n3(F, 0.6, sd + 1, 3) - 0.5) * 0.9 + (_grain(F, sd + 2) - 0.5) * 0.2
    col = _ramp(t, [(0.0, base * 0.5), (0.5, base), (1.0, base * 1.45)])
    F1, F2, _, _, _ = worley2(F.U * f32(1.4), F.V * f32(1.4), sd + 3)
    crack = 1.0 - _ss(0.0, 0.09, F2 - F1)
    col = col * (1.0 - crack[:, None] * f32(0.45))
    flake = _ss(0.66, 0.74, _n2(F, 1.4, 1.4, sd + 4, 2))
    col = _mix(col, _rgb((122, 58, 40)), flake * 0.6)
    return col


def m_gore_wet(F, p, sd):
    """混ざった臓物。ゆがんだ塊ごとに 肉 / 腸 / 血の塊（まれに脂肪・骨片）、丸みの陰、谷に溜まる血。"""
    wu = (_n2(F, 0.6, 0.6, sd + 9, 2) - 0.5) * 1.2
    wv = (_n2(F, 0.6, 0.6, sd + 10, 2) - 0.5) * 1.2
    F1, F2, cid, vx, vy = worley2((F.U + wu) * f32(0.6), (F.V + wv) * f32(0.6), sd + 1)
    flesh = _flesh_colour(F, sd + 2, base=(116, 20, 22), wet=0.0, fat=0.0)
    gut = m_guts(F, dict(base=(168, 96, 96)), sd + 3)
    fat = _ramp(_grain(F, sd + 4) * 0.5 + _n2(F, 2.0, 2.0, sd + 5, 2) * 0.5,
                [(0.0, (120, 84, 44)), (0.6, (166, 134, 78)), (1.0, (190, 164, 108))])
    bone = _ramp(_grain(F, sd + 6), [(0.0, (150, 134, 108)), (1.0, (196, 184, 156))])
    clot = _ramp(_grain(F, sd + 7) * 0.4 + _n2(F, 1.4, 1.4, sd + 8, 2) * 0.6, [(0.0, (24, 2, 4)), (1.0, (76, 6, 10))])
    col = np.where((cid < 0.45)[:, None], flesh, np.where((cid < 0.68)[:, None], gut,
                   np.where((cid < 0.92)[:, None], clot, np.where((cid < 0.97)[:, None], fat, bone))))
    dome = np.sqrt(np.clip(1 - (F1 / 0.85) ** 2, 0, 1))
    col = col * (0.55 + 0.5 * dome)[:, None] * (1.0 + np.clip(vy, -1, 1)[:, None] * f32(0.1))
    valley = 1.0 - _ss(0.0, 0.2, F2 - F1)
    col = _mix(col, _rgb((40, 2, 6)), valley * 0.85)
    F.wetm = np.full(F.n, 1.0, f32)
    return col


# 目の種類（nr_spec_zombies.EYES_VOCAB と同じ名前・同じ色。自己テストで突き合わせる）。
# sclera 白目 / iris 虹彩 / pupil 瞳（None は無し）/ glow 発光色（None は光らない）
EYES: Dict[str, dict] = {
    "clouded": dict(sclera=(200, 196, 184), iris=(150, 160, 170), pupil=(110, 120, 130), glow=None),
    "bloodshot": dict(sclera=(220, 140, 130), iris=(90, 60, 40), pupil=(10, 8, 8), glow=None),
    "milky": dict(sclera=(226, 226, 220), iris=(226, 226, 220), pupil=None, glow=None),
    "glowing_yellow": dict(sclera=(60, 50, 20), iris=(255, 220, 80), pupil=(255, 250, 200),
                           glow=(255, 220, 80)),
    "glowing_red": dict(sclera=(60, 10, 10), iris=(255, 50, 30), pupil=(255, 200, 180),
                        glow=(255, 50, 30)),
    "glowing_green": dict(sclera=(40, 60, 20), iris=(150, 255, 60), pupil=(230, 255, 200),
                          glow=(150, 255, 60)),
    "glowing_orange": dict(sclera=(60, 30, 10), iris=(255, 140, 40), pupil=(255, 230, 180),
                           glow=(255, 140, 40)),
    "glowing_cyan": dict(sclera=(20, 50, 50), iris=(110, 240, 255), pupil=(220, 255, 255),
                         glow=(110, 240, 255)),
    "glowing_white": dict(sclera=(10, 10, 14), iris=(240, 240, 255), pupil=(255, 255, 255),
                          glow=(240, 240, 255)),
    "none": dict(sclera=(40, 10, 10), iris=None, pupil=None, glow=None),
}
_EYE_KINDS = tuple(EYES)
# 光点だけの目（白目は闇、中心の 1 texel だけ光る）
_PINPOINT_EYES = ("glowing_white",)


def eye_info(kind: str, glow_colour=None) -> dict:
    """目の種類 → {sclera, iris, pupil, glow}（float32 の色か None）。glow_colour で発光色を差し替え。
    EYES に無い "glowing_*" は glow_colour（無ければ黄色）で光る目として扱う。それ以外の未知の名前は
    ValueError（spec の綴り間違いを黙って通さない）。"""
    if kind in EYES:
        info = dict(EYES[kind])
    elif str(kind).startswith("glowing_"):
        info = dict(EYES["glowing_yellow"])
        if glow_colour is None:
            glow_colour = info["glow"]
    else:
        raise ValueError(f"未知の目 '{kind}'（{', '.join(EYES)}）")
    if glow_colour is not None and info["glow"] is not None:
        gc = tuple(int(v) for v in _rgb(glow_colour))
        info["glow"] = gc
        info["iris"] = gc
    return {k: (None if v is None else _rgb(v)) for k, v in info.items()}


def m_eye(F, p, sd):
    """目玉（小さなキューブ用）。front 面（既定 north）に虹彩と瞳。EYES の全種類:
    clouded 灰青の濁った瞳 / bloodshot 赤い白目と開いた黒い瞳 / milky 瞳まで白濁 / none 眼窩の闇 /
    glowing_* 全体が光る（中心ほど白い）/ glowing_white 闇の中心の 1 点だけ光る。"""
    kind = _P(p, "kind", "clouded")
    info = eye_info(kind, p.get("glow_colour"))
    front = _FCODE[_P(p, "front", "north")]
    x = (F.fa - 0.5) * 2
    y = (F.fb - 0.5) * 2
    r = np.sqrt(x * x + y * y)
    gr = _grain(F, sd + 1)
    is_front = F.face == front
    if kind == "none":
        col = _ramp(r + (gr - 0.5) * 0.3, [(0.0, (8, 2, 2)), (0.6, (34, 6, 6)), (1.2, (96, 18, 16))])
        F.wetm = np.full(F.n, 0.8, f32)
        return col
    if info["glow"] is not None:
        gc = info["glow"]
        if kind in _PINPOINT_EYES:
            # 闇の玉。前の面の中心の 1〜2 texel だけが光る
            col = info["sclera"] * (0.7 + 0.5 * gr)[:, None] + f32(6)
            rpx = r * np.minimum(F.fw, F.fh) * 0.5
            pt = is_front & (rpx < np.maximum(0.75, np.minimum(F.fw, F.fh) * 0.12))
            col = np.where(pt[:, None], np.broadcast_to(info["pupil"], (F.n, 3)), col)
            F.glow = pt
            F.wetm = np.full(F.n, 0.6, f32)
            return col
        core = _ramp(np.where(is_front, r, 1.0 + 0.3 * r),
                     [(0.0, info["pupil"]), (0.35, np.minimum(255, gc * 1.0 + 30)), (0.85, gc),
                      (1.5, gc * 0.62)])
        col = core * (0.84 + 0.16 * gr)[:, None]
        F.glow = np.ones(F.n, bool)
        return col
    scl0 = info["sclera"]
    t = gr * 0.5 + _n2(F, 3.0, 3.0, sd + 2, 2) * 0.5
    scl = _ramp(t, [(0.2, scl0 * 0.66), (0.6, scl0 * 0.86), (0.9, scl0 * 0.95)])
    if kind == "clouded":
        scl = scl * np.array([0.96, 0.94, 0.86], f32)          # 死んだ白目の黄ばみ
    vn, _, _ = _iso(F, 1.2, sd + 3, 2, warp=1.0, width=0.8)
    vn = vn * (np.minimum(F.fw, F.fh) >= 4)          # 小さな目玉に血管の線を引くと傷に見える
    scl = _mix(scl, _rgb((150, 24, 24)), vn * (0.7 if kind == "bloodshot" else 0.3))
    ir = {"bloodshot": 0.46, "milky": 0.62}.get(kind, 0.58)
    iris_c = info["iris"]
    iris = _mix(iris_c * 0.78, iris_c, _ss(ir, 0.0, r))
    if info["pupil"] is not None:
        pr = 0.30 if kind == "bloodshot" else 0.2           # 充血型は瞳が開ききっている
        iris = _mix(iris, info["pupil"], _ss(pr, pr * 0.55, r))
    if kind in ("clouded", "milky"):
        iris = _mix(iris, _rgb((228, 232, 232)), _ss(0.45, 0.0, r) * (0.35 if kind == "clouded" else 0.6))
    col = np.where((is_front & (r < ir))[:, None], iris, scl)
    col = col * (1.0 - _ss(0.7, 1.2, r)[:, None] * 0.35)
    F.wetm = np.full(F.n, 0.9, f32)
    return col


def m_hair(F, p, sd):
    base = _rgb(_P(p, "base", (54, 44, 36)))
    style_ = _P(p, "style", "matted")
    # 毛束: 側面は下向きの 1 texel の筋、上面は前後方向の筋
    strand = _streak(F, 0.5 if style_ != "long" else 0.25, sd + 1, along="v")
    clump = _n2(F, 0.7, 0.3, sd + 2, 2)
    gr = _grain(F, sd + 3)
    t = 0.5 + (strand - 0.5) * 1.1 + (clump - 0.5) * 0.8 + (gr - 0.5) * 0.15
    hi = np.minimum(255, base * 1.6 + 20)
    col = _ramp(t, [(0.0, base * 0.3), (0.3, base * 0.62), (0.58, base), (0.88, hi), (1.1, hi)])
    # 艶の帯（異方性ハイライト。側面の上の方）
    band = _ss(0.6, 0.85, _n2(F, 0.3, 1.0, sd + 4, 2)) * F.side * _ss(0.3, 0.8, F.yrel)
    col = _mix(col, hi, band * (strand > 0.5) * 0.35)
    if style_ in ("short", "buzz"):
        col = _ramp(gr * 0.7 + clump * 0.3, [(0.0, base * 0.45), (0.6, base), (1.0, hi)])
    if style_ in ("balding", "patchy"):
        sk = _rgb(_P(p, "skin", (170, 160, 146)))
        bald = _ss(0.48, 0.56, _n3(F, 0.3, sd + 5, 2) + (F.face == 0) * 0.18)
        skc = sk * (0.82 + 0.18 * gr)[:, None]
        col = _mix(col, skc, bald)
    if style_ == "matted":
        mat_ = _ss(0.5, 0.72, clump) * 0.55
        col = _mix(col, col * np.array([0.58, 0.36, 0.3], f32), mat_)
    # 毛先がばらつく下端（側面の一番下の数 texel は列ごとに長さが違う）
    tipk = _u01(hash2i(F.ax.astype(np.uint32), F.fid.astype(np.uint32), sd + 6))
    tip = F.side & (F.fh - F.ly < tipk * np.minimum(F.s, 4) * 0.6)
    col = np.where(tip[:, None], col * 0.5, col)
    return col


def m_nail(F, p, sd):
    base = _rgb(_P(p, "base", (186, 172, 140)))
    t = 0.5 + (_n2(F, 3.0, 0.4, sd + 1, 2) - 0.5) * 0.8 + (_grain(F, sd + 2) - 0.5) * 0.2
    col = _ramp(t, [(0.0, base * 0.55), (0.5, base), (1.0, np.minimum(255, base * 1.15))])
    dirt = _ss(0.6, 0.95, F.fb) * F.side
    col = _mix(col, _rgb((52, 40, 30)), dirt * 0.8)
    F.hard = True
    return col


# ---- 布もの -----------------------------------------------------------------
def _fold_shading(F, sd, depth=1.0):
    """布のしわ: 横向き（側面）に走る折り目。谷は暗く、谷の上側の山は明るい。"""
    f = _n2(F, 0.32, 1.25, sd, 3, warp=0.8)
    crease = 1.0 - _ss(0.0, 0.07, np.abs(f - 0.5))
    ridge = _ss(0.55, 0.75, f) * (1 - _ss(0.75, 0.95, f))
    broad = _n3(F, 0.22, sd + 1, 2)
    return 1.0 + (broad - 0.5) * 0.22 * depth - crease * 0.22 * depth + ridge * 0.08 * depth


def _pattern_colour(F, p, base, alt, sd):
    pattern = _P(p, "pattern", "plain")
    n = F.n
    col = np.broadcast_to(base, (n, 3)).astype(f32).copy()
    U, V = F.U, F.V
    period = float(_P(p, "period", 1.2))
    if pattern == "stripes":
        q = U / f32(period)
        m = _ss(0.46, 0.54, np.abs(q - np.floor(q) - 0.5) * 2)
        col = _mix(col, alt, m)
    elif pattern == "pinstripe":
        q = U / f32(period * 0.8)
        d = np.abs(q - np.round(q)) * f32(period * 0.8) * F.s
        col = _mix(col, alt, _ss(0.8, 0.3, d) * 0.85)
    elif pattern == "plaid":
        qu = U / f32(period * 1.6)
        qv = V / f32(period * 1.6)
        bu = (np.abs(qu - np.floor(qu) - 0.5) < 0.18).astype(f32)
        bv = (np.abs(qv - np.floor(qv) - 0.5) < 0.18).astype(f32)
        col = _mix(col, alt, bu * 0.55 + bv * 0.55 - bu * bv * 0.2)
        accent = _rgb(_P(p, "accent", np.minimum(255, base * 0.4 + 140)))
        du = np.abs(qu - np.floor(qu) - 0.05) * f32(period * 1.6) * F.s
        dv = np.abs(qv - np.floor(qv) - 0.05) * f32(period * 1.6) * F.s
        col = _mix(col, accent, np.maximum(_ss(0.9, 0.4, du), _ss(0.9, 0.4, dv)) * 0.6)
        # 綾織りの斜め目
        tw = ((F.lx.astype(np.int64) + F.ly.astype(np.int64)) % 2).astype(f32)
        col = col * (0.96 + 0.06 * tw)[:, None]
    elif pattern == "camo":
        a2 = _rgb(_P(p, "alt2", alt * 0.55))
        a3 = _rgb(_P(p, "alt3", np.minimum(255, base * 1.25)))
        c1 = _n3(F, 0.32, sd + 31, 3, warp=1.6)
        c2 = _n3(F, 0.38, sd + 32, 3, warp=1.6)
        c3 = _n3(F, 0.45, sd + 33, 2, warp=1.6)
        col = np.where((c1 > 0.56)[:, None], alt, col)
        col = np.where((c2 > 0.6)[:, None], a2, col)
        col = np.where((c3 > 0.66)[:, None], a3, col)
    elif pattern == "print":
        F1, _, cid, _, _ = worley2(U * f32(1.1), V * f32(1.1), sd + 34)
        dot = (cid < 0.6) * _ss(0.28, 0.18, F1)
        col = _mix(col, alt, dot)
    elif pattern == "check":
        qu = np.floor(U / f32(period * 0.5))
        qv = np.floor(V / f32(period * 0.5))
        m = ((qu + qv) % 2).astype(f32)
        col = _mix(col, alt, m * 0.6)
    elif pattern == "hstripes":
        q = V / f32(period)
        m = _ss(0.46, 0.54, np.abs(q - np.floor(q) - 0.5) * 2)
        col = _mix(col, alt, m)
    return col


def _torn(F, p, col, sd):
    torn = float(_P(p, "torn", 0.0))
    if torn <= 0:
        return col
    under = p.get("under")
    hole_c = _rgb(under) if under is not None else _rgb((30, 24, 22))
    f = _n3(F, 0.5, sd + 41, 3, warp=1.5)
    th = _thr(torn * 0.3)
    # 下の縁のぎざぎざ（裾が裂けている）
    col_k = np.floor(F.lx / np.maximum(1.0, F.s * 0.35))
    rag = _u01(hash2i(col_k.astype(np.uint32), F.cid.astype(np.uint32), sd + 42))
    hem = F.side & (F.fb > 1.0 - rag ** 2 * f32(torn) * 0.4)
    e = (f - th) / 0.04
    fray = _ss(-1.2, -0.2, e) * (1 - _ss(-0.2, 0.2, e))
    col = col * (1.0 - fray[:, None] * f32(0.35))
    hole = (e > 0) | hem
    hc = hole_c * (0.75 + 0.3 * _grain(F, sd + 43))[:, None]
    if under is not None:
        hc = hc * (0.8 + 0.2 * (1 - _ss(0, 2, e)))[:, None]
    return np.where(hole[:, None], hc, col)


def m_cloth(F, p, sd):
    base = _rgb(_P(p, "base", (106, 110, 118)))
    alt = _rgb(_P(p, "alt", base * 0.55))
    col = _pattern_colour(F, p, base, alt, sd)
    # 織り目（平織り）: 1 texel の市松をわずかに
    chk = ((F.lx.astype(np.int64) + F.ly.astype(np.int64)) % 2).astype(f32)
    dens = np.clip((F.s - 1.5) / 3.0, 0.3, 1.0)
    col = col * (1.0 + (chk - 0.5) * 0.05 * dens)[:, None]
    gr = _grain(F, sd + 1)
    col = col * (0.95 + gr * 0.1)[:, None]
    col = col * _fold_shading(F, sd + 2, float(_P(p, "folds", 1.0)))[:, None]
    # 擦り切れ・色あせ（縁と面の中央の出っ張り）
    wear = float(_P(p, "wear", 0.3))
    if wear > 0:
        fade = _ss(0.55, 0.8, _n3(F, 0.4, sd + 3, 2)) * f32(wear)
        g = col.mean(axis=1, keepdims=True)
        col = _mix(col, g * 1.1 + 12, fade * 0.35)
        pill = (gr > 0.93) * f32(wear)
        col = col * (1.0 + pill[:, None] * f32(0.18))
    # 縫い目（面の縁の内側 1 texel を少し暗く）
    if _P(p, "seams", True):
        seam = (np.abs(F.edh - 1.5) < 0.5) & F.side & (F.fw >= 8) & (F.s >= 3)
        col = np.where(seam[:, None], col * 0.82, col)
    return _torn(F, p, col, sd)


def m_denim(F, p, sd):
    base = _rgb(_P(p, "base", (60, 84, 122)))
    # 綾織り（斜めの畝）と白い横糸
    tw = ((F.lx.astype(np.int64) + F.ly.astype(np.int64) * 1) % 3).astype(f32)
    col = np.broadcast_to(base, (F.n, 3)) * (0.93 + 0.07 * tw)[:, None]
    gr = _grain(F, sd + 1)
    weft = _ss(0.7, 0.95, gr) * 0.25
    col = _mix(col, _rgb((186, 196, 210)), weft)
    # 色落ち（面の中央が明るい・膝などの出っ張り）
    wear = float(_P(p, "wear", 0.5))
    bell = np.sin(F.fa * f32(math.pi)) ** 2
    fade = (bell * 0.5 + _n3(F, 0.35, sd + 2, 3) * 0.6 - 0.25) * f32(wear)
    col = _mix(col, np.minimum(255, base * 1.65 + 30), np.clip(fade, 0, 1) * 0.55)
    # ひげ（横向きの明るい擦れ）
    wh = (1.0 - _ss(0.0, 0.08, np.abs(_n2(F, 0.25, 1.6, sd + 3, 2) - 0.5))) * f32(wear) * 0.5
    col = _mix(col, np.minimum(255, base * 1.8 + 30), wh * F.side)
    col = col * _fold_shading(F, sd + 4, 0.8)[:, None]
    # ステッチ（オレンジ色の点線）
    if _P(p, "seams", True):
        st = F.side & (np.abs(F.edh - 1.5) < 0.5) & (F.fw >= 10) & (F.s >= 3) & ((F.lyi % 2) == 0)
        col = np.where(st[:, None], _rgb((176, 128, 64)), col)
    return _torn(F, p, col, sd)


def m_knit(F, p, sd):
    base = _rgb(_P(p, "base", (120, 40, 40)))
    alt = _rgb(_P(p, "alt", base * 0.7))
    col = _pattern_colour(F, dict(p, pattern=_P(p, "pattern", "plain")) if p.get("pattern") != "stripes"
                          else dict(p, pattern="hstripes"), base, alt, sd)
    # 編み目（V 字）: 2x2 texel の目
    lx = F.lx.astype(np.int64)
    ly = F.ly.astype(np.int64)
    v = np.where(((lx % 2) == 0), (ly % 2 == 0), (ly % 2 == 1)).astype(f32)
    row = (ly % 2 == 1).astype(f32)
    col = col * (0.9 + 0.14 * v - 0.04 * row)[:, None]
    gr = _grain(F, sd + 1)
    col = col * (0.94 + 0.12 * gr)[:, None]
    col = col * _fold_shading(F, sd + 2, 0.6)[:, None]
    fuzz = (gr > 0.9).astype(f32) * f32(_P(p, "wear", 0.4))
    col = _mix(col, col * 1.25 + 8, fuzz * 0.6)
    return _torn(F, p, col, sd)


def m_leather(F, p, sd):
    base = _rgb(_P(p, "base", (66, 44, 32)))
    F1, F2, cid, _, _ = worley2(F.U * f32(3.2), F.V * f32(3.2), sd + 1)
    grainv = 1.0 - _ss(0.0, 0.2, F2 - F1)
    t = 0.5 + (_n3(F, 0.5, sd + 2, 3) - 0.5) * 0.7 + (cid - 0.5) * 0.15 - grainv * 0.18
    col = _ramp(t, [(0.0, base * 0.5), (0.5, base), (1.0, np.minimum(255, base * 1.45 + 6))])
    # しわ
    cr = 1.0 - _ss(0.0, 0.05, np.abs(_n2(F, 0.5, 1.5, sd + 3, 2, warp=0.8) - 0.5))
    col = col * (1.0 - cr[:, None] * f32(0.25))
    # 擦れ（縁が明るく白っぽい）
    wear = float(_P(p, "wear", 0.4))
    e = _ss(2.2, 0.5, F.ed) * _ss(0.35, 0.65, _n2(F, 1.5, 1.5, sd + 4, 2)) * f32(wear)
    col = _mix(col, np.minimum(255, base * 1.9 + 30), e * 0.6)
    scuff = _ss(0.68, 0.78, _n3(F, 0.7, sd + 5, 2)) * f32(wear)
    col = _mix(col, col * 1.35 + 10, scuff * 0.5)
    # 艶（上面と側面の上側）
    sh = _ss(0.6, 1.0, F.yrel) * 0.06
    col = col * (1.0 + sh[:, None])
    F.hard = True
    return col


def m_rubber(F, p, sd):
    base = _rgb(_P(p, "base", (40, 40, 42)))
    t = 0.5 + (_n3(F, 0.6, sd + 1, 2) - 0.5) * 0.4 + (_grain(F, sd + 2) - 0.5) * 0.12
    col = _ramp(t, [(0.0, base * 0.7), (0.5, base), (1.0, base * 1.3 + 4)])
    scuff = _ss(0.66, 0.76, _n2(F, 0.9, 0.5, sd + 3, 2)) * f32(_P(p, "wear", 0.4))
    col = _mix(col, _rgb((96, 94, 90)), scuff * 0.45)
    F.hard = True
    return col


def m_kevlar(F, p, sd):
    base = _rgb(_P(p, "base", (74, 78, 58)))
    # 籠目（2x2 texel のブロックが交互）
    lx = F.lx.astype(np.int64) // 2
    ly = F.ly.astype(np.int64) // 2
    bk = ((lx + ly) % 2).astype(f32)
    sub = np.where(bk > 0, (F.lx.astype(np.int64) % 2), (F.ly.astype(np.int64) % 2)).astype(f32)
    col = np.broadcast_to(base, (F.n, 3)) * (0.92 + 0.06 * bk + 0.05 * sub)[:, None]
    col = col * (0.95 + 0.1 * _grain(F, sd + 1))[:, None]
    col = col * _fold_shading(F, sd + 2, 0.5)[:, None]
    if _P(p, "pattern", "plain") == "molle":
        per = 1.6
        q = F.V / f32(per)
        band = (q - np.floor(q)) < 0.42
        tack_q = F.U / f32(1.0)
        tack = band & ((tack_q - np.floor(tack_q)) < (f32(1.0) / (F.s * 1.0)) * 1.0)
        top = band & ((q - np.floor(q)) < (f32(1.0) / (F.s * per)))
        col = np.where(band[:, None], col * 0.86, col)
        col = np.where(top[:, None], col * 1.18, col)
        col = np.where(tack[:, None], col * 0.6, col)
    elif _P(p, "pattern", "plain") == "camo":
        col = _pattern_colour(F, p, base, _rgb(_P(p, "alt", base * 0.6)), sd) * \
            (col / np.maximum(1, np.broadcast_to(base, (F.n, 3))))
    F.hard = False
    return col


def m_hi_vis(F, p, sd):
    base = _rgb(_P(p, "base", (206, 232, 44)))
    col = np.broadcast_to(base, (F.n, 3)) * (0.95 + 0.08 * _grain(F, sd + 1))[:, None]
    chk = ((F.lx.astype(np.int64) + F.ly.astype(np.int64)) % 2).astype(f32)
    col = col * (0.98 + 0.03 * chk)[:, None]
    col = col * _fold_shading(F, sd + 2, 0.8)[:, None]
    # 反射テープ（側面の決まった高さに横帯）
    bands = p.get("bands", (0.35, 0.7))
    bh = float(_P(p, "band_h", 0.11))
    refl = np.zeros(F.n, bool)
    for b in bands:
        refl |= F.side & (np.abs(F.fb - f32(b)) < f32(bh / 2))
    rc = _ramp(_grain(F, sd + 3) * 0.6 + _n2(F, 2.0, 2.0, sd + 4, 2) * 0.4,
               [(0.0, (140, 142, 140)), (0.5, (190, 192, 190)), (1.0, (232, 234, 230))])
    col = np.where(refl[:, None], rc, col)
    edge_band = np.zeros(F.n, bool)
    for b in bands:
        edge_band |= F.side & (np.abs(np.abs(F.fb - f32(b)) - f32(bh / 2)) < f32(0.6) / F.fh)
    col = np.where(edge_band[:, None], col * 0.82, col)
    return _torn(F, p, col, sd)


# ---- 硬いもの ---------------------------------------------------------------
def m_metal(F, p, sd):
    base = _rgb(_P(p, "base", (140, 143, 148)))
    brushed = _streak(F, 0.08, sd + 1)
    t = 0.5 + (_n3(F, 0.25, sd + 2, 3) - 0.5) * 0.6 + (brushed - 0.5) * 0.22 + (_grain(F, sd + 3) - 0.5) * 0.06
    col = _ramp(t, [(0.0, base * 0.55), (0.5, base), (1.0, np.minimum(255, base * 1.22 + 8))])
    # 打痕（ゆるいへこみの陰影）
    dent = _n3(F, 0.5, sd + 5, 2)
    col = col * F.emboss(_ss(0.6, 0.8, dent), 0.12)[:, None]
    # 引っかき傷（細い線。濃さも長さもばらばら）
    dens = float(_P(p, "scratches", 0.5))
    d = _scratch_field(F.U * f32(0.7), F.V * f32(0.7), dens, sd + 4) / f32(0.7) * F.s
    k = _ss(0.75, 0.2, d) * (0.25 + 0.35 * _n2(F, 0.8, 0.8, sd + 6, 2))
    col = _mix(col, np.minimum(255, base * 1.4 + 26), k)
    F.hard = True
    return col


def m_rust(F, p, sd):
    amount = float(_P(p, "amount", 1.0))
    base = _rgb(_P(p, "base", (128, 64, 32)))
    t = 0.5 + (_n3(F, 0.45, sd + 1, 3, warp=1.0) - 0.5) * 1.0 + (_grain(F, sd + 2) - 0.5) * 0.25
    col = _ramp(t, [(0.0, (46, 24, 16)), (0.3, base * 0.66), (0.55, base), (0.8, (172, 92, 42)),
                    (1.05, (196, 126, 66))])
    # 孔食（暗い点）
    F1, _, cid, _, _ = worley2(F.U * f32(1.8), F.V * f32(1.8), sd + 3)
    pit = (cid < 0.5) * _ss(0.3, 0.1, F1)
    col = col * (1.0 - pit[:, None] * f32(0.45))
    # 剥がれかけの層（明るい縁）
    fl = _n2(F, 0.9, 0.9, sd + 4, 2)
    col = _mix(col, _rgb((186, 112, 58)), _ss(0.62, 0.66, fl) * (1 - _ss(0.7, 0.74, fl)) * 0.7)
    # 縦の錆だれ
    st = _n2(F, 2.2, 0.16, sd + 5, 3)
    col = col * (1.0 + ((st - 0.5) * 0.45 * F.side)[:, None])
    if amount < 1.0:
        metal = m_metal(F, dict(p, base=_P(p, "metal", (120, 122, 126))), sd + 6)
        cov = _ss(_thr(amount) - 0.03, _thr(amount) + 0.03, _n3(F, 0.5, sd + 7, 3, warp=1.2))
        col = _mix(metal, col, cov)
    F.hard = True
    return col


def m_painted_metal(F, p, sd):
    base = _rgb(_P(p, "base", (150, 40, 34)))
    t = 0.5 + (_n3(F, 0.3, sd + 1, 3) - 0.5) * 0.35 + (_grain(F, sd + 2) - 0.5) * 0.08
    col = _ramp(t, [(0.0, base * 0.72), (0.5, base), (1.0, np.minimum(255, base * 1.18 + 6))])
    wear = float(_P(p, "wear", 0.4))
    rusty = float(_P(p, "rust", 0.5))
    # 塗装の剥げ: 縁ほど剥げやすい
    chip_f = _n2(F, 1.4, 1.4, sd + 3, 3) + _ss(3.0, 0.5, F.ed) * 0.25 - 0.15
    th = _thr(wear * 0.35)
    chip = chip_f > th
    rim = (chip_f > th - 0.03) & ~chip
    bare = m_metal(F, dict(base=(150, 150, 150), scratches=0.2), sd + 4)
    rustc = _ramp(_n3(F, 0.8, sd + 5, 2), [(0.2, (70, 34, 20)), (0.6, (130, 64, 30)), (0.9, (170, 92, 44))])
    under = _mix(bare, rustc, np.clip(f32(rusty) * 1.2 * _n3(F, 0.6, sd + 6, 2) * 1.6, 0, 1))
    col = np.where(rim[:, None], col * 0.7, col)
    col = np.where(chip[:, None], under, col)
    # 錆だれ（側面で下へ）
    if rusty > 0:
        st = _ss(0.55, 0.85, _n2(F, 2.0, 0.14, sd + 7, 3)) * F.side * f32(rusty) * _ss(0.2, 0.8, F.fb)
        col = _mix(col, col * np.array([0.72, 0.5, 0.36], f32), st * 0.7)
    # 縁の明るい擦れ
    F.hard = True
    return col


def m_chrome(F, p, sd):
    w = (_n2(F, 0.5, 0.5, sd + 1, 2) - 0.5) * 0.12
    v = F.fb + w
    side_c = _ramp(v, [(0.0, (232, 238, 246)), (0.38, (176, 192, 210)), (0.47, (60, 62, 70)),
                       (0.52, (28, 28, 32)), (0.6, (96, 86, 76)), (1.0, (150, 140, 124))])
    up_c = _ramp(F.fb + w, [(0.0, (210, 222, 236)), (1.0, (246, 248, 252))])
    dn_c = _ramp(F.fb + w, [(0.0, (60, 54, 48)), (1.0, (96, 88, 80))])
    col = np.where(F.side[:, None], side_c, np.where((F.face == 0)[:, None], up_c, dn_c))
    d = _scratch_field(F.U * f32(0.8), F.V * f32(0.8), 0.4, sd + 2) / f32(0.8) * F.s
    col = _mix(col, _rgb((250, 252, 255)), _ss(0.8, 0.3, d) * 0.4)
    tint = _rgb(_P(p, "base", (200, 205, 212))) / f32(205)
    F.hard = True
    return col * tint


def m_plastic(F, p, sd):
    base = _rgb(_P(p, "base", (60, 64, 70)))
    t = 0.5 + (_n3(F, 0.35, sd + 1, 2) - 0.5) * 0.3 + (_grain(F, sd + 2) - 0.5) * 0.06
    col = _ramp(t, [(0.0, base * 0.8), (0.5, base), (1.0, np.minimum(255, base * 1.15 + 6))])
    scuff = _ss(0.68, 0.8, _n2(F, 1.2, 0.6, sd + 3, 2)) * f32(_P(p, "wear", 0.3))
    col = _mix(col, np.minimum(255, base * 1.35 + 30), scuff * 0.4)
    F.hard = True
    return col


def m_wood(F, p, sd):
    base = _rgb(_P(p, "base", (126, 88, 56)))
    ua, va = F.Ua, F.Va
    # 年輪の筋: 長軸方向に流れ、ゆるく波打つ。節の周りで大きく曲がる
    F1k, _, cidk, vxk, vyk = worley2(ua * f32(0.3), va * f32(0.1), sd + 4)
    knot = (cidk < 0.14) * _ss(0.42, 0.12, F1k)
    bend = (cidk < 0.14) * _ss(0.9, 0.2, F1k) * vxk * f32(2.5)
    warp = _n2(F, 0.3, 0.05, sd + 1, 3, U=ua, V=va) - 0.5
    q = ua * f32(_P(p, "grain", 1.3)) + warp * f32(4.0) + bend
    ring = np.abs(np.sin(q * f32(math.pi)))           # 0 = 晩材の濃い線
    late = 1.0 - _ss(0.0, 0.35, ring)
    fine = _streak(F, 0.15, sd + 2)
    t = 0.55 + (ring - 0.5) * 0.25 + (fine - 0.5) * 0.3 + (_n3(F, 0.2, sd + 3, 2) - 0.5) * 0.4 - late * 0.3
    dark = base * np.array([0.58, 0.55, 0.52], f32)
    col = _ramp(t, [(0.0, dark * 0.75), (0.35, dark), (0.65, base), (1.0, np.minimum(255, base * 1.22))])
    col = _mix(col, dark * 0.55, knot)
    # 木口（断面方向の面）は年輪
    if F.endon.any():
        rr = np.sqrt((F.fa - 0.37) ** 2 + (F.fb - 0.6) ** 2) * np.maximum(F.fw, F.fh) / F.s
        er = np.sin((rr * f32(3.2) + (fine - 0.5) * 0.4) * f32(2 * math.pi)) * 0.5 + 0.5
        ec = _ramp(er * 0.6 + _grain(F, sd + 5) * 0.4, [(0.0, dark), (1.0, base * 1.1)])
        col = np.where(F.endon[:, None], ec, col)
    # 板の継ぎ目
    planks = float(_P(p, "planks", 0))
    if planks > 0:
        qq = ua / f32(planks)
        d = np.abs(qq - np.round(qq)) * f32(planks) * F.s
        col = _mix(col, _rgb((24, 16, 10)), _ss(0.9, 0.4, d) * (~F.endon))
        col = col * (1.0 + (_ss(1.6, 0.9, d) * (~F.endon) * 0.08))[:, None]
    # 風化（灰色に抜ける）
    wear = float(_P(p, "wear", 0.2))
    gcol = col.mean(axis=1, keepdims=True) * np.array([1.0, 0.98, 0.94], f32) + 24
    col = _mix(col, gcol, np.clip(_n3(F, 0.3, sd + 6, 2) * f32(wear) * 1.3, 0, 1))
    F.hard = True
    return col


def m_concrete(F, p, sd):
    base = _rgb(_P(p, "base", (148, 146, 140)))
    t = 0.5 + (_n3(F, 0.2, sd + 1, 3) - 0.5) * 0.5 + (_n2(F, 0.9, 0.9, sd + 2, 2) - 0.5) * 0.4 + \
        (_grain(F, sd + 3) - 0.5) * 0.12
    col = _ramp(t, [(0.0, base * 0.7), (0.5, base), (1.0, np.minimum(255, base * 1.12))])
    gr = _grain(F, sd + 4)
    col = np.where((gr > 0.96)[:, None], col * 0.8, col)
    col = np.where((gr < 0.03)[:, None], np.minimum(255, col * 1.1), col)
    # 雨だれ
    st = _streak(F, 0.25, sd + 5, along="v")
    col = col * (1.0 - (_ss(0.55, 0.85, st) * F.side * 0.14)[:, None])
    # ひび
    cr = 1.0 - _ss(0.0, 0.16 / F.s, np.abs(_n2(F, 0.35, 0.35, sd + 6, 3, warp=1.4) - 0.5))
    cr = cr * _ss(0.45, 0.6, _n3(F, 0.2, sd + 7, 2)) * f32(_P(p, "cracks", 0.6))
    col = col * (1.0 - cr[:, None] * f32(0.5))
    F.hard = True
    return col


def m_asphalt(F, p, sd):
    base = _rgb(_P(p, "base", (58, 58, 60)))
    t = 0.5 + (_n3(F, 0.25, sd + 1, 3) - 0.5) * 0.5 + (_grain(F, sd + 6) - 0.5) * 0.2
    col = _ramp(t, [(0.0, base * 0.72), (0.5, base), (1.0, base * 1.2)])
    gr = _grain(F, sd + 2)
    stone = _ramp(_grain(F, sd + 3), [(0.0, (84, 82, 78)), (1.0, (118, 114, 108))])
    col = np.where((gr > 0.9)[:, None], col * 0.4 + stone * 0.6, col)
    col = np.where((gr < 0.06)[:, None], col * 0.75, col)
    oil = _ss(0.66, 0.76, _n3(F, 0.4, sd + 4, 2, warp=1.0))
    col = _mix(col, _rgb((28, 28, 32)), oil * 0.55)
    cr = 1.0 - _ss(0.0, 0.16 / F.s, np.abs(_n2(F, 0.3, 0.3, sd + 5, 3, warp=1.5) - 0.5))
    col = col * (1.0 - cr[:, None] * f32(0.45) * f32(_P(p, "cracks", 0.6)))
    F.hard = True
    return col


def m_glass(F, p, sd):
    base = _rgb(_P(p, "base", (54, 70, 76)))
    refl = np.sin((F.fa * 1.6 - F.fb) * f32(math.pi) * 1.4) * 0.5 + 0.5
    t = 0.35 + refl * 0.35 + (_n3(F, 0.3, sd + 1, 2) - 0.5) * 0.3
    col = _ramp(t, [(0.0, base * 0.6), (0.5, base), (0.9, np.minimum(255, base * 1.7 + 30)),
                    (1.1, (200, 214, 220))])
    # 汚れの膜（下と縁に溜まる）
    film = np.clip(_ss(0.4, 1.0, F.fb) * F.side * 0.5 + _ss(2.5, 0.5, F.ed) * 0.4, 0, 1) * \
        _n3(F, 0.6, sd + 2, 2) * 1.4
    col = _mix(col, _rgb((112, 104, 90)), np.clip(film, 0, 0.7))
    crack = float(_P(p, "crack", 0.0))
    if crack > 0:
        cx, cy = 0.35 + 0.3 * ((_seed(sd) & 255) / 255.0), 0.4
        dx = F.fa - f32(cx)
        dy = F.fb - f32(cy)
        ang = np.arctan2(dy, dx)
        rad = np.sqrt(dx * dx + dy * dy)
        spokes = np.abs(np.sin(ang * f32(5.0) + (_n2(F, 0.6, 0.6, sd + 3, 2) - 0.5) * 2.0))
        sp = _ss(0.12, 0.0, spokes) * _ss(crack * 0.9, crack * 0.2, rad)
        rings = np.abs(np.sin(rad * f32(26.0))) < 0.12
        col = _mix(col, _rgb((226, 232, 236)), np.clip(sp + rings * _ss(crack * 0.5, 0.0, rad) * 0.6, 0, 1) * 0.8)
    F.hard = True
    return col


def m_tire(F, p, sd):
    base = _rgb(_P(p, "base", (30, 30, 32)))
    axis = _P(p, "axis", None)
    t = 0.5 + (_n3(F, 0.5, sd + 1, 2) - 0.5) * 0.3 + (_grain(F, sd + 2) - 0.5) * 0.1
    col = _ramp(t, [(0.0, base * 0.7), (0.5, base), (1.0, base * 1.35 + 4)])
    # 側壁 = 軸に垂直な面。axis を指定しなければ「一番薄い寸法」の向き
    side_wall = F.endon if axis is None else np.isin(F.face, {"x": [2, 4], "y": [0, 1], "z": [3, 5]}[axis])
    x = (F.fa - 0.5) * 2
    y = (F.fb - 0.5) * 2
    r = np.sqrt(x * x + y * y)
    hub = _ramp(_grain(F, sd + 3) * 0.3 + (1 - r) * 0.7, [(0.0, (70, 72, 76)), (0.5, (130, 132, 136)), (1.0, (176, 178, 182))])
    hub = np.where((np.abs(r - 0.28) < 0.05)[:, None], hub * 0.4, hub)
    letters = (np.abs(r - 0.78) < 0.05) & (np.sin(np.arctan2(y, x) * 18) > 0.2)
    sw = np.where((r < 0.5)[:, None], hub, np.where(letters[:, None], col * 1.8 + 10, col))
    sw = np.where((r > 1.0)[:, None], col * 0.8, sw)
    # トレッド
    q = F.Va * f32(1.4)
    k = np.floor(q)
    fr = q - k
    zig = (np.abs(F.fa - 0.5 + (k % 2 - 0.5) * 0.12) < 0.07)
    groove = (fr < 0.28) | zig
    tread = np.where(groove[:, None], col * 0.45, col * 1.08)
    col = np.where(side_wall[:, None], sw, tread)
    F.hard = True
    return col


def m_fungus(F, p, sd):
    """寄生菌（冬虫夏草風）。ゆがんだこぶの塊、繊維状の菌糸、黒い胞子の点、ぬめり。"""
    base = _rgb(_P(p, "base", (190, 152, 98)))
    tip = _rgb(_P(p, "alt", (226, 206, 158)))
    wu = (_n2(F, 0.7, 0.7, sd + 6, 2) - 0.5) * 1.2
    wv = (_n2(F, 0.7, 0.7, sd + 7, 2) - 0.5) * 1.2
    F1, F2, cid, vx, vy = worley2((F.U + wu) * f32(0.75), (F.V + wv) * f32(0.75), sd + 1)
    dome = np.sqrt(np.clip(1 - (F1 / 0.8) ** 2, 0, 1))
    hyph = _streak(F, 0.4, sd + 3)
    t = 0.3 + dome * 0.45 + np.clip(vy, -1, 1) * 0.15 * dome + (cid - 0.5) * 0.15 + (hyph - 0.5) * 0.25
    col = _ramp(t, [(0.0, base * 0.32), (0.35, base * 0.62), (0.7, base), (1.0, tip)])
    valley = 1.0 - _ss(0.0, 0.16, F2 - F1)
    col = _mix(col, base * np.array([0.3, 0.24, 0.2], f32), valley * 0.75)
    gr = _grain(F, sd + 4)
    spore = (gr > 0.93) & (dome < 0.7)
    col = np.where(spore[:, None], col * 0.4, col)
    gs = _P(p, "glow_spots", 0)
    if _P(p, "emissive", False) or gs:
        gc = _rgb(_P(p, "glow_colour", (170, 255, 120)))
        spots = (cid < f32(gs or 0.3)) & (F1 < np.maximum(f32(0.16), f32(0.6) / (F.s / 0.75)))
        col = np.where(spots[:, None], _mix(np.broadcast_to(gc, col.shape), np.full((F.n, 3), 255, f32),
                                            _ss(0.2, 0.0, F1)), col)
        F.glow = spots
    F.wetm = dome * 0.45
    return col


def m_tumor(F, p, sd):
    base = _rgb(_P(p, "base", (190, 140, 120)))
    F1, F2, cid, vx, vy = worley2(F.U * f32(0.8), F.V * f32(0.8), sd + 1)
    dome = np.sqrt(np.clip(1 - (F1 / 0.75) ** 2, 0, 1))
    lit = dome * 0.55 + np.clip(vy, -1, 1) * 0.3 * dome
    cc = _ramp(cid, [(0.0, (196, 176, 110)), (0.35, base), (0.7, (150, 96, 116)), (1.0, (172, 76, 70))])
    col = cc * (0.4 + lit + (_grain(F, sd + 2) - 0.5) * 0.1)[:, None]
    edge = 1.0 - _ss(0.0, 0.14, F2 - F1)
    col = _mix(col, _rgb((70, 30, 40)), edge * 0.8)
    vn = 1.0 - _ss(0.0, 0.03, np.abs(_n2(F, 0.9, 0.9, sd + 3, 2, warp=1.2) - 0.5))
    col = _mix(col, _rgb((100, 40, 80)), vn * 0.55)
    pus = (cid > 0.75) & (F1 < 0.16)
    col = np.where(pus[:, None], _rgb((236, 222, 150)), col)
    hl = _ss(0.8, 0.95, dome) * (vy > 0.05)
    col = _mix(col, _GLINT, hl * 0.4)
    F.wetm = dome * 0.6
    return col


def m_char(F, p, sd):
    """炭化。ひび割れた黒い鱗、灰、（燠火なら）ひびの一部だけが光る。"""
    base = _rgb(_P(p, "base", (30, 26, 24)))
    wu = (_n2(F, 0.8, 0.8, sd + 5, 2) - 0.5) * 0.8
    F1, F2, cid, vx, vy = worley2((F.U + wu) * f32(1.1), (F.V + wu) * f32(1.1), sd + 1)
    crack = 1.0 - _ss(0.0, 0.08 * 4.0 / np.maximum(F.s, 2), F2 - F1)
    dome = np.sqrt(np.clip(1 - (F1 / 0.85) ** 2, 0, 1))
    t = 0.35 + dome * 0.3 + np.clip(vy, -1, 1) * 0.12 + (cid - 0.5) * 0.2 + (_grain(F, sd + 2) - 0.5) * 0.12
    col = _ramp(t, [(0.0, base * 0.5), (0.5, base), (0.85, (62, 58, 54)), (1.1, (104, 98, 92))])
    ash = (_grain(F, sd + 3) > 0.97) | ((_n2(F, 1.4, 1.4, sd + 6, 2) > 0.74) & (dome > 0.5))
    col = np.where(ash[:, None], _mix(col, _rgb((150, 146, 140)), np.full(F.n, 0.7, f32)), col)
    col = col * (1.0 - crack[:, None] * f32(0.6))
    embers = _P(p, "embers", _P(p, "emissive", False))
    if embers:
        zone = _n3(F, 0.4, sd + 4, 2) > _thr(float(embers) * 0.35 if not isinstance(embers, bool) else 0.3)
        hot = (crack > 0.6) & zone
        ec = _ramp(crack + (_grain(F, sd + 7) - 0.5) * 0.4, [(0.5, (170, 40, 8)), (0.85, (255, 110, 24)),
                                                             (1.2, (255, 200, 90))])
        col = np.where(hot[:, None], ec, col)
        F.glow = hot
    F.hard = True
    return col


def m_glow(F, p, sd):
    base = _rgb(_P(p, "base", (120, 200, 255)))
    t = 0.85 + (_n3(F, 0.6, sd + 1, 2) - 0.5) * 0.25 + (_grain(F, sd + 2) - 0.5) * 0.06
    core = _ss(0.5, 0.0, np.minimum(np.abs(F.fa - 0.5), np.abs(F.fb - 0.5)))
    col = base * t[:, None]
    col = _mix(col, np.minimum(255, base * 0.4 + 160), core * 0.35)
    F.glow = np.ones(F.n, bool)
    return col


def m_paper(F, p, sd):
    base = _rgb(_P(p, "base", (224, 218, 198)))
    t = 0.5 + (_n3(F, 0.5, sd + 1, 2) - 0.5) * 0.3 + (_grain(F, sd + 2) - 0.5) * 0.12
    col = _ramp(t, [(0.0, base * 0.82), (0.5, base), (1.0, np.minimum(255, base * 1.05))])
    F1, F2, _, _, _ = worley2(F.U * f32(0.7), F.V * f32(0.7), sd + 3)
    cre = 1.0 - _ss(0.0, 0.06, F2 - F1)
    col = col * (1.0 - cre[:, None] * 0.12)
    if _P(p, "lines", True):
        q = F.V / f32(0.7)
        ln = (np.abs(q - np.round(q)) * f32(0.7) * F.s) < 0.5
        col = np.where(ln[:, None], col * np.array([0.82, 0.86, 0.96], f32), col)
    stain = _ss(0.66, 0.72, _n3(F, 0.5, sd + 4, 2)) * (1 - _ss(0.72, 0.78, _n3(F, 0.5, sd + 4, 2)) * 0.6)
    col = _mix(col, col * np.array([0.82, 0.7, 0.5], f32), stain * 0.7)
    return col


def m_sign(F, p, sd):
    base = _rgb(_P(p, "base", (36, 96, 60)))
    border = p.get("border", (226, 226, 220))
    col = m_painted_metal(F, dict(p, base=base, wear=_P(p, "wear", 0.3), rust=_P(p, "rust", 0.4)), sd)
    if border is not None:
        b = (np.abs(F.ed - 1.5) < 0.5) & ~np.isin(F.face, [0, 1])
        bc = m_painted_metal(F, dict(p, base=border, wear=_P(p, "wear", 0.3), rust=0.2), sd + 9)
        col = np.where(b[:, None], bc, col)
    F.hard = True
    return col


# 素材ごとの固有パラメータ（共通の base / alt / dirt / blood / blood_kind / wear / wet / burn / emissive /
# seed はどの素材にも効く）。他の生成器が読むための一覧で、値は「意味（既定）」。
MATERIAL_PARAMS = {
    "skin": "tone=SKINS のキー|dict(base,shadow,highlight) / decay 0..4 (1) / veins 濃さ / bruises / "
            "lesions / rot / exposed / necrosis（各 0..1、既定は decay から）/ vein, mottle 色 / cracks / "
            "spores / iridescent / emissive_vein / decay_tint",
    "flesh": "base (128,24,26) / fat 0..1 (0) / wet (0.7)",
    "cut_flesh": "tone（皮膚の縁）/ section 断面の面 ('up','down') / fat 脂肪の内側の半径 (0.76) / "
                 "bone True / bone_r (0.26) / bone_at (0,0) / centre (0.5,0.5)。キューブごとに変えるときは "
                 "section デカール（section_decal）で面を描き直す",
    "bone": "age 0..1 (0.4)", "teeth": "decay / tooth_w 単位 (0.55) / row 'upper'|'lower'",
    "gums": "-", "guts": "rot 0..1 (0.5)", "brain": "-", "blood": "blood_kind", "blood_dry": "blood_kind",
    "gore_wet": "-", "eye": "kind（EYES のキー: clouded|bloodshot|milky|glowing_yellow|glowing_red|"
                            "glowing_green|glowing_orange|glowing_cyan|glowing_white|none）/ front 'north' / "
                            "glow_colour",
    "hair": "style matted|long|short|buzz|balding|patchy / skin（balding の地肌）",
    "nail": "-", "cloth": "pattern plain|stripes|hstripes|pinstripe|plaid|camo|print|check / period 単位 / "
                          "alt, alt2, alt3, accent / folds / seams / torn 0..1 / under 破れ目の下の色",
    "denim": "torn / under / seams", "knit": "pattern / alt / torn", "leather": "-", "rubber": "-",
    "kevlar": "pattern plain|molle|camo", "hi_vis": "bands (0.35,0.7) / band_h (0.11) / torn",
    "metal": "scratches 0..1 (0.5)", "rust": "amount 0..1 (1) / metal 下地の色",
    "painted_metal": "rust 0..1 (0.5)", "chrome": "-", "plastic": "-",
    "wood": "grain (1.3) / planks 板幅 単位 (0)", "concrete": "cracks (0.6)", "asphalt": "cracks (0.6)",
    "glass": "crack 0..1 (0)", "tire": "axis 'x'|'y'|'z'（既定は一番薄い向き）",
    "fungus": "glow_spots 0..1 / glow_colour", "tumor": "-", "char": "embers True|0..1",
    "glow": "-（全部光る）", "paper": "lines True", "sign": "border 色|None",
}

# 素材名 → (関数, 血の付き方: 'soak' 染み込む / 'gloss' 表面で艶 / 'none')
MATERIALS = {
    "skin": (m_skin, "gloss"), "flesh": (m_flesh, "gloss"), "cut_flesh": (m_cut_flesh, "gloss"),
    "bone": (m_bone, "gloss"), "teeth": (m_teeth, "gloss"), "gums": (m_gums, "gloss"),
    "guts": (m_guts, "gloss"), "brain": (m_brain, "gloss"), "blood": (m_blood, "none"),
    "blood_dry": (m_blood_dry, "none"), "gore_wet": (m_gore_wet, "gloss"), "eye": (m_eye, "gloss"),
    "hair": (m_hair, "soak"), "nail": (m_nail, "gloss"),
    "cloth": (m_cloth, "soak"), "denim": (m_denim, "soak"), "knit": (m_knit, "soak"),
    "leather": (m_leather, "gloss"), "rubber": (m_rubber, "gloss"), "kevlar": (m_kevlar, "soak"),
    "hi_vis": (m_hi_vis, "soak"), "metal": (m_metal, "gloss"), "rust": (m_rust, "gloss"),
    "painted_metal": (m_painted_metal, "gloss"), "chrome": (m_chrome, "gloss"),
    "plastic": (m_plastic, "gloss"), "wood": (m_wood, "soak"), "concrete": (m_concrete, "soak"),
    "asphalt": (m_asphalt, "soak"), "glass": (m_glass, "gloss"), "tire": (m_tire, "gloss"),
    "fungus": (m_fungus, "gloss"), "tumor": (m_tumor, "gloss"), "char": (m_char, "gloss"),
    "glow": (m_glow, "none"), "paper": (m_paper, "soak"), "sign": (m_sign, "gloss"),
}
# 有機物（縁の陰を丸く・強めに）
_ORGANIC = {"skin", "flesh", "cut_flesh", "gums", "guts", "brain", "blood", "blood_dry",
            "gore_wet", "eye", "hair", "fungus", "tumor", "cloth", "denim", "knit", "kevlar", "hi_vis"}


# ---------------------------------------------------------------------------
#  どの素材にも掛かる上塗り: 汚れ・擦れ・焦げ・血・濡れ
# ---------------------------------------------------------------------------
def _ov_wear_edges(F, col, wear, sd):
    """硬いものの縁の擦れ（明るい）と、縁の欠け。"""
    e = _ss(1.0 + 0.25 * F.s, 0.5, F.ed)
    br = _ss(0.4, 0.62, _n2(F, 1.8, 1.8, sd, 2))
    m = e * br * f32(wear)
    hi = np.minimum(255, col * 1.35 + 22)
    return _mix(col, hi, m * 0.7)


def _ov_dirt(F, col, amt, sd, hard):
    low = (1.0 - F.Ym) ** 2 * 0.55 + np.where(F.side, (1.0 - F.yrel) ** 3, 0.0) * 0.45
    edge = _ss(1.0 + 0.5 * F.s, 0.5, F.ed) * 0.35
    patch = _n3(F, 0.42, sd + 1, 3, warp=1.2)
    g = np.clip(f32(amt) * (0.25 + low + edge) * (patch * 1.9 - 0.45), 0, 1)
    dirt = _ramp(_n3(F, 0.9, sd + 2, 2), [(0.2, (52, 44, 36)), (0.6, (78, 68, 54)), (0.9, (96, 88, 74))])
    col = _mix(col, col * 0.45 + dirt * 0.55, g * 0.8)
    # 細かい点々（泥はね）
    gr = _grain(F, sd + 3)
    speck = (gr > 1.0 - 0.08 * amt) & (g > 0.25)
    col = np.where(speck[:, None], col * 0.82, col)
    # 雨だれの筋（硬いもの・側面）
    if hard:
        st = _ss(0.55, 0.8, _n2(F, 2.4, 0.13, sd + 4, 3)) * F.side * f32(amt) * 0.4
        col = col * (1.0 - st[:, None])
    return col


def _ov_burn(F, col, amt, sd):
    f = _n3(F, 0.35, sd, 3, warp=1.4)
    th = _thr(min(0.95, amt * 0.8))
    e = (f - th) / 0.08
    scorch = _ss(-1.5, 0.0, e)
    charm = _ss(0.0, 0.6, e)
    col = _mix(col, col * np.array([0.55, 0.42, 0.32], f32), scorch * 0.8)
    F1, F2, _, _, _ = worley2(F.U * f32(1.6), F.V * f32(1.6), sd + 1)
    crack = 1.0 - _ss(0.0, 0.1, F2 - F1)
    ch = _ramp(_grain(F, sd + 2) * 0.5 + (1 - crack) * 0.5, [(0.0, (8, 6, 6)), (0.5, (28, 24, 22)), (1.0, (62, 56, 52))])
    return _mix(col, ch, charm)


def _ov_blood(F, col, amt, mode, sd, kind="red", age=0.0):
    """血の上塗り。amt 0..1（量）、age 0..1（0 = 新しく赤い、1 = 古く乾いた茶色が多い）。
    量が少ないときは飛沫の点を減らす（少量の血が全身に散った「そばかす」に見えないように）。"""
    if amt <= 0:
        return col
    b_hi, b_mid, b_dk, b_glow = _blood_cols(kind)
    tint = np.clip(b_mid / 255.0 * 1.6 + 0.1, 0, 1).astype(f32)
    # 大きな染み（3D。キューブの角・隣のキューブへ繋がる）
    st = _n3(F, 0.3, sd + 1, 3, warp=1.6, sy=0.55)
    th = _thr(min(0.85, 0.03 + amt * 0.3))
    e = (st - th) / 0.06
    stain = _ss(-0.2, 0.4, e)
    thick = _ss(0.2, 2.5, e)
    # 薄く塗り広げた縁（半透明、かすれ）
    smear = _ss(-1.8, -0.2, e) * _ss(0.45, 0.7, _n2(F, 1.1, 0.5, sd + 11, 2)) * 0.55
    # 飛沫: 「飛んだ方向」の帯の中にだけ点が集まる
    zone = _ss(-0.05, 0.08, _n3(F, 0.2, sd + 2, 2, warp=1.0) - f32(_thr(0.06 + 0.46 * amt)))
    dens = min(1.0, 0.2 + 1.6 * amt)
    cf = 1.4
    F1, _, cid, _, _ = worley2(F.U * f32(cf), F.V * f32(cf), sd + 3)
    hr = _u01(_fin((cid * 16777216).astype(np.uint32) ^ np.uint32((sd + 4) & 0xFFFF)))
    rmin = f32((0.85 if mode == "soak" else 0.55) * cf) / F.s
    rr = np.maximum(0.08 + 0.3 * hr ** 2, rmin)
    dots = ((cid < (0.45 if mode == "soak" else 0.6) * zone * dens + 0.015 * amt * amt)
            & (F1 < rr)).astype(f32)
    cov = np.maximum(stain, dots)
    dr, dgl = _drip_mask(F, stain > 0.5, amt, sd + 5)
    cov = np.maximum(cov, dr)
    thick = np.maximum(np.maximum(thick, dr * 0.75), dots * 0.5)
    if mode == "soak":
        # 布・紙・木: 染み込んで暗くなる。縁は繊維に沿ってにじみ、乾いた跡の濃い輪。織り目は残る
        wick = _ss(-2.2, 0.6, e + (_grain(F, sd + 10) - 0.5) * 0.9)
        cov = np.maximum(np.maximum(wick * 0.95, dots), dr)
        tide = _ss(-0.6, -0.1, e) * (1 - _ss(-0.1, 0.4, e))
        soak = col * np.clip(b_mid / 255.0 * 1.1 + 0.05, 0, 1).astype(f32) + b_mid * 0.35
        old = _mix(soak, col * np.array([0.36, 0.2, 0.15], f32) + _rgb((26, 8, 4)),
                   _ss(0.45, 0.75, _n3(F, 0.6, sd + 6, 2)))
        out = _mix(col, old, cov * 0.92)
        out = _mix(out, b_dk * 0.7, tide * 0.5)
        if b_glow:
            F.glow = (cov > 0.6) if F.glow is None else (F.glow | (cov > 0.6))
        return out
    # 表面に乗る血: 厚い所ほど黒く、薄い所は下地が透ける
    fresh = _ramp(thick + (_grain(F, sd + 7) - 0.5) * 0.15,
                  [(0.0, b_hi), (0.4, b_mid), (1.0, b_dk)])
    thin = col * tint + b_mid * 0.3
    bc = _mix(thin, fresh, _ss(0.0, 0.5, thick))
    ag = float(min(1.0, max(0.0, age)))
    dry = np.clip(_ss(0.55 - 0.45 * ag, 0.8 - 0.4 * ag, _n3(F, 0.5, sd + 8, 2)), 0, 1)
    if ag > 0:
        # 古い血: 乾いて黒ずんだ赤茶色（明るい赤は傷口の新しい血だけに残す）
        dried = np.minimum(bc * np.array([0.5, 0.62, 0.55], f32) + _rgb((26, 12, 6)), 255)
        bc = _mix(bc, dried, dry * (0.7 + 0.25 * ag))
        thin = _mix(thin, col * np.array([0.62, 0.5, 0.45], f32) + _rgb((22, 8, 4)), np.full(F.n, 0.6 * ag, f32))
    else:
        bc = _mix(bc, bc * np.array([0.62, 0.8, 0.75], f32) + _rgb((8, 5, 2)), dry * 0.65)
    out = _mix(col, thin * 0.85 + col * 0.15, smear * (1 - cov))
    out = _mix(out, bc, cov)
    # 照り: 厚い血の上の縁、点々、垂れの先端
    covm = cov > 0.5
    g = _grain(F, sd + 9)
    topedge = covm & ~F.nb(covm, 0, -1) & (thick > 0.25) & (g > 0.4)
    sp = covm & (g > 0.975) & (thick > 0.3)
    gl = (topedge | sp | dgl) & (dry < 0.4)
    out = np.where(gl[:, None], _mix(out, _GLINT, np.full(F.n, 0.5, f32)), out)
    if b_glow:
        F.glow = (cov > 0.6) if F.glow is None else (F.glow | (cov > 0.6))
    return out


def _ov_wet(F, col, wetm, sd):
    """濡れ: 少し暗く・彩度を上げ、照りの点（上向きの面と側面の上側に多い）。"""
    if wetm is None:
        return col
    wetm = np.broadcast_to(np.asarray(wetm, f32), (F.n,))
    g = col.mean(axis=1, keepdims=True)
    col = _mix(col, (col - g) * 1.15 + g * 0.86, wetm * 0.5)
    gr = _grain(F, sd + 1)
    hi = _n2(F, 1.1, 1.1, sd + 2, 2)
    up = np.where(F.face == 0, 1.0, np.where(F.side, 0.3 + 0.7 * F.yrel, 0.0))
    spec = (hi > 0.82) & (F.nb(hi, 0, -1) < hi) & (gr > 0.5 - 0.35 * up) & (wetm > 0.35)
    tint = np.minimum(255, col * 0.4 + _GLINT * 0.7)
    return np.where(spec[:, None], _mix(col, tint, wetm * 0.6), col)


def _shade_field(F, organic, face_light, ao, hard):
    sh = np.ones(F.n, f32)
    if face_light:
        lut = np.array([FACE_LIGHT[f] for f in FACES], f32)
        sh *= lut[F.face]
        sh *= np.where(F.side, 0.93 + 0.12 * F.yrel, 1.0)
    if ao:
        band = np.clip(0.45 * F.s, 1.0, 3.0)
        small = np.clip(np.minimum(F.fw, F.fh) / 6.0, 0.25, 1.0)
        a = np.clip(1.0 - (F.ed - 0.5) / band, 0, 1)
        k = (0.24 if organic else 0.13) * small
        sh *= 1.0 - k * a * a
        if hard:
            # 硬いものは上の縁が光を拾う
            top = F.side & (F.edt < 1.0) & (F.fh >= 4)
            sh = np.where(top, sh * 1.1, sh)
    return sh


# ---------------------------------------------------------------------------
#  デカール（面ごと。正規化座標で描くので面の大きさに追従する）
# ---------------------------------------------------------------------------
class _Face:
    def __init__(self, painter, cube, face, rect, style, seed):
        x0, y0, w, h = rect
        self.w, self.h = w, h
        self.x0, self.y0 = x0, y0
        self.rgb = painter.rgb[y0:y0 + h, x0:x0 + w]
        self.alpha = painter.alpha[y0:y0 + h, x0:x0 + w]
        self.glow = painter.glow[y0:y0 + h, x0:x0 + w]
        self.s = float(cube._scale or 1)
        self.face = face
        self.side = face in SIDES
        self.style = style
        self.mat = style.get("mat", "skin")
        self.seed = seed
        bh, bm, bd, bg = _blood_cols(style.get("blood_kind", "red"))
        self.bcol = bm if style.get("blood_kind", "red") != "red" else _BLOOD
        jj, ii = np.mgrid[0:h, 0:w].astype(f32)
        self.px = ii + 0.5          # texel 中心（texel 単位）
        self.py = jj + 0.5
        self.u = self.px / w
        self.v = self.py / h
        self.ax = (ii + x0).astype(np.int64)
        self.ay = (jj + y0).astype(np.int64)

    # 形（0..1 のマスク。縁は 1 texel で滑らかに）
    def ellipse(self, cu, cv, ru, rv, soft=1.0):
        dx = (self.px - cu * self.w) / max(0.5, ru * self.w)
        dy = (self.py - cv * self.h) / max(0.5, rv * self.h)
        d = np.sqrt(dx * dx + dy * dy)
        rpx = max(0.5, min(ru * self.w, rv * self.h))
        return np.clip((1.0 - d) * rpx / soft + 0.5, 0, 1)

    def blob(self, cu, cv, ru, rv):
        """ぼかした楕円（陰影の造形用）。中心 1 → 外へ 0。"""
        dx = (self.px - cu * self.w) / max(0.5, ru * self.w)
        dy = (self.py - cv * self.h) / max(0.5, rv * self.h)
        return np.exp(-(dx * dx + dy * dy) * 2.2)

    def seg(self, u0, v0, u1, v1, width_px=1.0):
        ax, ay = u0 * self.w, v0 * self.h
        bx, by = u1 * self.w, v1 * self.h
        dx, dy = bx - ax, by - ay
        L2 = max(1e-6, dx * dx + dy * dy)
        t = np.clip(((self.px - ax) * dx + (self.py - ay) * dy) / L2, 0, 1)
        qx = self.px - (ax + t * dx)
        qy = self.py - (ay + t * dy)
        d = np.sqrt(qx * qx + qy * qy)
        return np.clip(width_px / 2.0 - d + 0.5, 0, 1)

    def noise(self, freq, sd, octaves=3):
        return fbm2(self.px / self.s * freq, self.py / self.s * freq, sd, octaves,
                    tpc=np.full(self.px.shape, self.s / freq, f32))

    def grain(self, sd):
        return texel_rand(self.ax, self.ay, sd)

    def paint(self, mask, col, a=1.0):
        m = np.clip(np.asarray(mask, f32) * a, 0, 1)
        col = np.asarray(col, f32)
        self.rgb[...] = self.rgb + (col - self.rgb) * m[..., None]

    def mul(self, mask, factor):
        """mask の所を factor 倍。factor はスカラー・(3,) の色ごと・(h, w) の texel ごと・(h, w, 3)。"""
        m = np.clip(np.asarray(mask, f32), 0, 1)[..., None]
        f = np.asarray(factor, f32)
        if f.ndim == 2:
            f = f[..., None]
        self.rgb[...] = self.rgb * (1.0 + (f - 1.0) * m)

    def emit(self, mask, col, alpha=EMISSIVE_ALPHA, thr=0.5):
        m = np.asarray(mask) > thr
        self.rgb[m] = np.asarray(col, f32) if np.ndim(col) == 1 else np.asarray(col, f32)[m]
        self.alpha[m] = np.minimum(self.alpha[m], alpha)
        self.glow[m] = True

    def drips_from(self, src, amount=1.0, sd=0, col=None):
        """マスク src の下側から血を垂らす（側面のみ。画像の +v が下）。"""
        if not self.side:
            return
        col = self.bcol if col is None else _rgb(col)
        h, w = src.shape
        rng = np.random.default_rng(sd & 0xFFFFFFFF)
        out = np.zeros_like(src)
        for x in range(w):
            ys = np.nonzero(src[:, x] > 0.5)[0]
            if len(ys) == 0 or rng.random() > 0.35 + 0.4 * amount:
                continue
            y0 = ys.max()
            L = int(round((0.5 + rng.random() ** 1.6 * 4.0) * self.s * amount))
            y1 = min(h - 1, y0 + max(1, L))
            out[y0:y1 + 1, x] = 1.0
            if y1 + 1 < h and rng.random() < 0.6 and L > 2:
                out[y1, max(0, x - 1):x + 2] = np.maximum(out[y1, max(0, x - 1):x + 2], 0.7)
        self.paint(out, col * 0.9)
        # 玉の照り
        gl = (out > 0.5) & (np.roll(out, -1, axis=0) < 0.5) & (self.grain(sd + 1) > 0.5)
        self.paint(gl, _GLINT, 0.4)


# 3x5 の極小フォント（看板・番号・バッジ用）
_FONT = {
    "A": (".#.", "#.#", "###", "#.#", "#.#"), "B": ("##.", "#.#", "##.", "#.#", "##."),
    "C": (".##", "#..", "#..", "#..", ".##"), "D": ("##.", "#.#", "#.#", "#.#", "##."),
    "E": ("###", "#..", "##.", "#..", "###"), "F": ("###", "#..", "##.", "#..", "#.."),
    "G": (".##", "#..", "#.#", "#.#", ".##"), "H": ("#.#", "#.#", "###", "#.#", "#.#"),
    "I": ("###", ".#.", ".#.", ".#.", "###"), "J": ("..#", "..#", "..#", "#.#", ".#."),
    "K": ("#.#", "#.#", "##.", "#.#", "#.#"), "L": ("#..", "#..", "#..", "#..", "###"),
    "M": ("#.#", "###", "###", "#.#", "#.#"), "N": ("##.", "#.#", "#.#", "#.#", "#.#"),
    "O": (".#.", "#.#", "#.#", "#.#", ".#."), "P": ("##.", "#.#", "##.", "#..", "#.."),
    "Q": (".#.", "#.#", "#.#", "##.", ".##"), "R": ("##.", "#.#", "##.", "#.#", "#.#"),
    "S": (".##", "#..", ".#.", "..#", "##."), "T": ("###", ".#.", ".#.", ".#.", ".#."),
    "U": ("#.#", "#.#", "#.#", "#.#", "###"), "V": ("#.#", "#.#", "#.#", "#.#", ".#."),
    "W": ("#.#", "#.#", "###", "###", "#.#"), "X": ("#.#", "#.#", ".#.", "#.#", "#.#"),
    "Y": ("#.#", "#.#", ".#.", ".#.", ".#."), "Z": ("###", "..#", ".#.", "#..", "###"),
    "0": ("###", "#.#", "#.#", "#.#", "###"), "1": (".#.", "##.", ".#.", ".#.", "###"),
    "2": ("##.", "..#", ".#.", "#..", "###"), "3": ("##.", "..#", ".#.", "..#", "##."),
    "4": ("#.#", "#.#", "###", "..#", "..#"), "5": ("###", "#..", "##.", "..#", "##."),
    "6": (".##", "#..", "###", "#.#", "###"), "7": ("###", "..#", ".#.", ".#.", ".#."),
    "8": ("###", "#.#", "###", "#.#", "###"), "9": ("###", "#.#", "###", "..#", "##."),
    "-": ("...", "...", "###", "...", "..."), ".": ("...", "...", "...", "...", ".#."),
    "/": ("..#", "..#", ".#.", "#..", "#.."), ":": ("...", ".#.", "...", ".#.", "..."),
    "!": (".#.", ".#.", ".#.", "...", ".#."), "?": ("##.", "..#", ".#.", "...", ".#."),
    "+": ("...", ".#.", "###", ".#.", "..."), "#": ("#.#", "###", "#.#", "###", "#.#"),
    "'": (".#.", ".#.", "...", "...", "..."), "&": (".#.", "#.#", ".#.", "#.#", ".##"),
    "*": ("#.#", ".#.", "#.#", "...", "..."), " ": ("...", "...", "...", "...", "..."),
    "%": ("#.#", "..#", ".#.", "#..", "#.#"), "(": (".#.", "#..", "#..", "#..", ".#."),
    ")": (".#.", "..#", "..#", "..#", ".#."), "=": ("...", "###", "...", "###", "..."),
}


def text_mask(text: str, w: int, h: int, at=(0.5, 0.5), px: Optional[int] = None,
              spacing: int = 1) -> np.ndarray:
    """3x5 フォントで text を描いたマスク (h, w)。px = 1 ドットの texel 数（既定は収まる最大）。
    収まらない時は字間を詰め、それでも収まらなければ収まる文字数まで切る（はみ出して欠けた字は描かない）。"""
    text = str(text).upper()
    if px is None:
        px = max(1, min((w - 1) // max(1, (4 * len(text) - 1)), (h - 1) // 5))
    if (3 * len(text) + spacing * (len(text) - 1)) * px > w:
        spacing = 0
    while len(text) > 1 and 3 * len(text) * px > w:
        text = text[:-1]
    n = max(1, len(text))
    tw = (3 * n + spacing * (n - 1)) * px
    th = 5 * px
    x0 = int(round(at[0] * w - tw / 2))
    y0 = int(round(at[1] * h - th / 2))
    x0 = min(max(0, x0), max(0, w - tw))
    y0 = min(max(0, y0), max(0, h - th))
    m = np.zeros((h, w), f32)
    for i, ch in enumerate(text):
        g = _FONT.get(ch, _FONT["?"])
        cx = x0 + i * (3 + spacing) * px
        for r, row in enumerate(g):
            for c, bit in enumerate(row):
                if bit == "#":
                    ys, xs = y0 + r * px, cx + c * px
                    ya, yb = max(0, ys), min(h, ys + px)
                    xa, xb = max(0, xs), min(w, xs + px)
                    if ya < yb and xa < xb:
                        m[ya:yb, xa:xb] = 1.0
    return m


def d_text(fc: _Face, d):
    col = _rgb(d.get("colour", d.get("color", (232, 230, 220))))
    m = text_mask(d.get("text", "NR"), fc.w, fc.h, d.get("at", (0.5, 0.5)), d.get("px"))
    wear = float(d.get("wear", 0.2))
    if wear > 0:
        # 文字は読めることが優先。軽い擦れは texel の欠けだけ、強い擦れで面ごと剥げる
        m = m * (fc.grain(fc.seed + 3) > wear * 0.35)
        if wear > 0.45:
            m = m * (fc.noise(0.8, fc.seed + 4, 2) > 0.25 + 0.5 * (wear - 0.45))
    if d.get("shadow"):
        sh = np.roll(np.roll(m, 1, axis=0), 1, axis=1)
        fc.mul(sh * (1 - m), 0.55)
    if d.get("emissive"):
        fc.emit(m, col)
    else:
        fc.paint(m, col * (0.92 + 0.12 * fc.grain(fc.seed + 5))[..., None])


def d_stripe(fc: _Face, d):
    col = _rgb(d.get("colour", d.get("color", (220, 200, 40))))
    count = int(d.get("count", 1))
    orient = d.get("orient", "h")
    wd = float(d.get("width", 0.14))
    off = float(d.get("offset", 0.5))
    m = np.zeros((fc.h, fc.w), f32)
    for i in range(count):
        c = off if count == 1 else (0.5 + (i - (count - 1) / 2.0) * (wd * 2.0 + float(d.get("gap", 0.08))) +
                                    (off - 0.5))
        if orient == "v":
            q = fc.u
        elif orient == "d":
            q = (fc.u + fc.v) * 0.5
        else:
            q = fc.v
        m = np.maximum(m, np.clip((wd / 2 - np.abs(q - c)) * (fc.h if orient == "h" else fc.w) + 0.5, 0, 1))
    if d.get("hazard"):
        # 黄黒の斜め縞
        k = np.floor((fc.px + fc.py) / max(2.0, fc.s * 1.0))
        col_arr = np.where((k % 2 == 0)[..., None], col, _rgb((24, 22, 20)))
    else:
        col_arr = np.broadcast_to(col, (fc.h, fc.w, 3))
    wear = float(d.get("wear", 0.15))
    chip = fc.noise(1.4, fc.seed + 7, 3) > 0.86 - wear * 0.3
    shade_ = (0.9 + 0.15 * fc.grain(fc.seed + 8))[..., None]
    if d.get("reflective"):
        col_arr = col_arr * (0.85 + 0.3 * fc.grain(fc.seed + 9))[..., None]
    fc.paint(m * (~chip), col_arr * shade_)


def d_badge(fc: _Face, d):
    col = _rgb(d.get("colour", d.get("color", (206, 168, 70))))
    cu, cv = d.get("at", (0.5, 0.5))
    sz = float(d.get("size", 0.32))
    kind = d.get("kind", "shield")
    x = (fc.px - cu * fc.w) / max(1.0, sz * min(fc.w, fc.h) * 0.5)
    y = (fc.py - cv * fc.h) / max(1.0, sz * min(fc.w, fc.h) * 0.5)
    if kind == "circle":
        m = (x * x + y * y) <= 1.0
    elif kind == "star":
        ang = np.arctan2(y, x)
        r = np.sqrt(x * x + y * y)
        m = r <= 0.55 + 0.45 * np.abs(np.cos(ang * 2.5))
    elif kind == "patch":
        m = (np.abs(x) <= 1.0) & (np.abs(y) <= 0.7)
    else:   # 盾
        m = (np.abs(x) <= 0.85 * (1.0 - np.clip(y - 0.1, 0, 1) ** 1.3)) & (y >= -0.9) & (y <= 1.0)
    m = m.astype(f32)
    inner = m * (np.roll(m, 1, 0) * np.roll(m, -1, 0) * np.roll(m, 1, 1) * np.roll(m, -1, 1))
    rim = m - inner
    shine = _ss(0.8, -0.6, x + y)
    body = _mix(col * 0.75, np.minimum(255, col * 1.25 + 20), shine.reshape(-1)).reshape(fc.h, fc.w, 3)
    fc.paint(m, body)
    fc.paint(rim, col * 0.45)
    cen = (x * x + y * y) < 0.12
    fc.paint(cen, np.minimum(255, col * 1.4 + 30))
    if d.get("text"):
        tm = text_mask(d["text"], fc.w, fc.h, (cu, cv + sz * 0.3), 1)
        fc.paint(tm * m, col * 0.35)


def d_grime(fc: _Face, d):
    amt = float(d.get("amount", 0.6))
    n = fc.noise(0.5, fc.seed + 1, 3)
    low = fc.v ** 2 if fc.side else np.full_like(fc.v, 0.4)
    g = np.clip((n * 1.6 - 0.45 + low * 0.8) * amt, 0, 1)
    fc.paint(g, _rgb((58, 50, 40)), 0.6)
    st = _ss(0.55, 0.8, fbm2(fc.px / fc.s * 2.0, fc.py / fc.s * 0.15, fc.seed + 2, 3)) * amt
    if fc.side:
        fc.mul(st, 0.72)
    sp = fc.grain(fc.seed + 3) > 1 - 0.15 * amt
    fc.mul(sp, 0.6)


def d_wound(fc: _Face, d):
    """裂傷: ぎざぎざの縁、乾いた縁取り、腫れた周囲、奥は暗い肉、照り、下へ垂れる血。"""
    cu, cv = d.get("at", (0.5, 0.45))
    size = float(d.get("size", 0.5))
    ang = math.radians(float(d.get("angle", -25)))
    wet = float(d.get("wet", 0.8))
    ca, sa = math.cos(ang), math.sin(ang)
    x = (fc.px - cu * fc.w)
    y = (fc.py - cv * fc.h)
    L = size * max(fc.w, fc.h) * 0.5
    Wd = max(1.2, L * float(d.get("width", 0.22)))
    xr = (x * ca + y * sa) / L
    yr = (-x * sa + y * ca) / Wd
    rag = (fc.noise(1.6, fc.seed + 1, 2) - 0.5) * 0.9
    prof = np.sqrt(np.clip(1 - xr * xr, 0, 1))          # 両端が細い
    d_ = np.abs(yr + rag * 0.4) - prof
    swell = _ss(1.8, 0.3, d_ + 0.0) * (prof > 0.0)
    fc.mul(swell * 0.6, np.array([1.05, 0.78, 0.76], f32))
    crust = _ss(0.6, 0.0, d_) * (d_ > -0.25)
    fc.paint(crust, _rgb((62, 20, 16)), 0.85)
    inside = _ss(-0.05, -0.35, d_)
    depth = np.clip(-d_ / np.maximum(prof, 1e-3), 0, 1)
    fib = np.sin((xr * 9.0 + rag * 3.0) * math.pi) * 0.5 + 0.5
    meat = _ramp((depth * 0.7 + fib * 0.3).reshape(-1),
                 [(0.0, (150, 30, 30)), (0.5, (96, 10, 14)), (1.0, (30, 2, 4))]).reshape(fc.h, fc.w, 3)
    fc.paint(inside, meat)
    gl = inside * (fc.grain(fc.seed + 2) > 0.8) * (depth < 0.6) * wet
    fc.paint(gl, _GLINT, 0.6)
    if wet > 0:
        fc.drips_from(inside, wet, fc.seed + 3)


def d_bite(fc: _Face, d):
    """噛み傷: 上下の弧に並ぶ歯の穴、噛みちぎられた肉の穴、腫れと打撲、垂れる血。"""
    cu, cv = d.get("at", (0.5, 0.5))
    size = float(d.get("size", 0.46))
    rx = size * 0.5
    ry = size * 0.36 * fc.w / fc.h
    fc.mul(fc.blob(cu, cv, rx * 1.7, ry * 1.9), np.array([0.7, 0.55, 0.68], f32))
    fc.mul(fc.blob(cu, cv, rx * 1.15, ry * 1.25), np.array([1.06, 0.84, 0.82], f32))
    rag = fc.noise(1.8, fc.seed + 1, 2)
    hole = fc.ellipse(cu, cv, rx * 0.62, ry * 0.55) * (rag > 0.3)
    rim = np.clip(fc.ellipse(cu, cv, rx * 0.78, ry * 0.7) - hole, 0, 1)
    fc.paint(rim, _rgb((70, 22, 18)), 0.85)
    depth = fc.blob(cu, cv + 0.02, rx * 0.4, ry * 0.4)
    meat = _ramp((depth * 0.7 + fc.grain(fc.seed + 2) * 0.3).reshape(-1),
                 [(0.0, (150, 30, 30)), (0.5, (96, 12, 14)), (1.0, (34, 2, 4))]).reshape(fc.h, fc.w, 3)
    fc.paint(hole, meat)
    fc.paint(hole * (fc.grain(fc.seed + 3) > 0.86), _GLINT, 0.5)
    # 歯の穴
    n = max(4, int(rx * fc.w / 1.6))
    for lo, hi in ((200.0, 340.0), (20.0, 160.0)):
        for i in range(n):
            a = math.radians(lo + (hi - lo) * (i + 0.5) / n)
            u = cu + math.cos(a) * rx
            v = cv + math.sin(a) * ry
            fc.paint(fc.ellipse(u, v, 0.75 / fc.w, 0.75 / fc.h, soft=0.5), _rgb((52, 6, 8)))
    fc.drips_from(hole, 0.8, fc.seed + 4)


def d_bullet_hole(fc: _Face, d):
    cu, cv = d.get("at", (0.5, 0.5))
    r = float(d.get("size", 0.08))
    hard = fc.mat in ("metal", "painted_metal", "chrome", "sign", "plastic", "rust", "glass",
                      "concrete", "asphalt", "tire", "rubber")
    rp = max(0.6, r * min(fc.w, fc.h))
    ru, rv = rp / fc.w, rp / fc.h
    hole = fc.ellipse(cu, cv, ru, rv)
    ring = fc.ellipse(cu, cv, ru * 2.0, rv * 2.0) * (1 - hole)
    if fc.mat == "glass":
        x = fc.px - cu * fc.w
        y = fc.py - cv * fc.h
        ang = np.arctan2(y, x)
        rad = np.sqrt(x * x + y * y)
        sp = (np.abs(np.sin(ang * 4.0 + 0.7)) < 0.12) & (rad < rp * 6)
        fc.paint(sp, _rgb((226, 232, 236)), 0.7)
        fc.paint(ring, _rgb((220, 226, 230)), 0.8)
        fc.paint(hole, _rgb((16, 18, 20)))
    elif hard:
        fc.paint(ring, _rgb((196, 194, 188)), 0.8)        # めくれた地金
        fc.paint(fc.ellipse(cu, cv, ru * 3.0, rv * 3.0) * (1 - ring - hole), _rgb((40, 36, 32)), 0.35)
        fc.paint(hole, _rgb((10, 10, 10)))
        if fc.side:
            fc.drips_from(hole, 0.5, fc.seed + 1, col=(96, 56, 30))
    elif fc.mat in ("cloth", "denim", "knit", "kevlar", "hi_vis", "paper"):
        fc.paint(ring, _rgb((36, 20, 16)), 0.6)
        fc.paint(fc.ellipse(cu, cv, ru * 3.0, rv * 3.0), _rgb((70, 8, 10)), 0.5)
        fc.paint(hole, _rgb((22, 6, 6)))
    else:
        fc.paint(fc.ellipse(cu, cv, ru * 2.8, rv * 2.8), _rgb((110, 30, 40)), 0.45)
        fc.paint(ring, _rgb((90, 10, 12)), 0.9)
        fc.paint(hole, _rgb((18, 2, 4)))
        fc.drips_from(hole, 0.9, fc.seed + 2)


def d_burn(fc: _Face, d):
    cu, cv = d.get("at", (0.5, 0.5))
    size = float(d.get("size", 0.45))
    n = fc.noise(1.0, fc.seed + 1, 3)
    x = (fc.px - cu * fc.w) / (size * fc.w * 0.5)
    y = (fc.py - cv * fc.h) / (size * fc.h * 0.5)
    r = np.sqrt(x * x + y * y) + (n - 0.5) * 0.7
    scorch = _ss(1.4, 0.8, r)
    blister = _ss(1.0, 0.75, r) * (1 - _ss(0.75, 0.5, r))
    charm = _ss(0.75, 0.5, r)
    if fc.mat in ("skin", "flesh"):
        fc.mul(scorch, np.array([0.9, 0.62, 0.55], f32))
        fc.paint(blister, _rgb((178, 70, 60)), 0.7)
        pus = blister * (fc.grain(fc.seed + 2) > 0.8)
        fc.paint(pus, _rgb((220, 200, 150)), 0.8)
    else:
        fc.mul(scorch, np.array([0.55, 0.45, 0.38], f32))
    cr = fc.grain(fc.seed + 3)
    ch = _ramp(cr.reshape(-1), [(0.0, (8, 6, 6)), (0.7, (30, 26, 24)), (1.0, (80, 74, 70))]).reshape(fc.h, fc.w, 3)
    fc.paint(charm, ch)
    if d.get("embers"):
        em = charm * (fc.noise(2.0, fc.seed + 4, 2) > 0.62)
        fc.emit(em, _rgb((255, 120, 30)))


def d_stitches(fc: _Face, d):
    u0, v0 = d.get("start", (0.2, 0.3))
    u1, v1 = d.get("end", (0.8, 0.7))
    line = fc.seg(u0, v0, u1, v1, 1.0)
    fc.mul(fc.seg(u0, v0, u1, v1, 3.0), np.array([0.82, 0.66, 0.64], f32))
    fc.paint(line, _rgb((70, 18, 18)))
    n = max(2, int(math.hypot((u1 - u0) * fc.w, (v1 - v0) * fc.h) / max(2.0, fc.s * 0.7)))
    nx, ny = -(v1 - v0) * fc.h, (u1 - u0) * fc.w
    ln = math.hypot(nx, ny) or 1.0
    nx, ny = nx / ln * 1.5 / fc.w, ny / ln * 1.5 / fc.h
    for i in range(n):
        t = (i + 0.5) / n
        cu, cv = u0 + (u1 - u0) * t, v0 + (v1 - v0) * t
        fc.paint(fc.seg(cu - nx, cv - ny, cu + nx, cv + ny, 1.0), _rgb((20, 16, 14)))


def d_drips(fc: _Face, d):
    src = np.zeros((fc.h, fc.w), f32)
    src[0:max(1, int(fc.h * float(d.get("start", 0.08)))), :] = 1.0
    fc.paint(src * (fc.noise(1.0, fc.seed + 1, 2) > 0.4), fc.bcol, 0.85)
    fc.drips_from(src, float(d.get("amount", 0.9)), fc.seed + 2)


def d_handprint(fc: _Face, d):
    cu, cv = d.get("at", (0.5, 0.55))
    sz = float(d.get("size", 0.5))
    m = fc.ellipse(cu, cv + sz * 0.12, sz * 0.22, sz * 0.2)
    for i, (du, ln) in enumerate(((-0.17, 0.30), (-0.06, 0.36), (0.05, 0.34), (0.15, 0.28))):
        m = np.maximum(m, fc.seg(cu + du * sz, cv - 0.02 * sz, cu + du * sz * 1.3, cv - ln * sz,
                                 max(1.0, sz * fc.w * 0.07)))
    m = np.maximum(m, fc.seg(cu - 0.2 * sz, cv + 0.12 * sz, cu - 0.38 * sz, cv - 0.02 * sz,
                             max(1.0, sz * fc.w * 0.07)))
    m = m * (fc.noise(2.0, fc.seed + 1, 2) > 0.3)
    fc.paint(m, fc.bcol * 0.9, 0.9)
    fc.drips_from(m, 0.7, fc.seed + 2)


def d_buttons(fc: _Face, d):
    col = _rgb(d.get("colour", (216, 212, 200)))
    cu = float(d.get("u", 0.5))
    fc.mul(fc.seg(cu, 0.0, cu, 1.0, 1.0), 0.8)
    n = int(d.get("count", 4))
    for i in range(n):
        v = (i + 0.6) / (n + 0.2)
        fc.paint(fc.ellipse(cu + 1.0 / fc.w, v, 0.6 / fc.w, 0.6 / fc.h), col)


def d_pocket(fc: _Face, d):
    u0, v0, u1, v1 = d.get("box", (0.15, 0.2, 0.45, 0.45))
    for a, b, c, e in ((u0, v0, u1, v0), (u0, v0, u0, v1), (u1, v0, u1, v1), (u0, v1, u1, v1)):
        fc.mul(fc.seg(a, b, c, e, 1.0), 0.75)
    fc.mul(fc.seg(u0, v0 + 1.5 / fc.h, u1, v0 + 1.5 / fc.h, 1.0), 1.12)


def d_zipper(fc: _Face, d):
    cu = float(d.get("u", 0.5))
    m = fc.seg(cu, 0.0, cu, 1.0, 1.0)
    teeth = m * ((fc.py.astype(np.int64) % 2) == 0)
    fc.paint(m, _rgb((40, 40, 42)))
    fc.paint(teeth, _rgb((150, 150, 146)))


def d_cracks(fc: _Face, d):
    n = fbm2(fc.px / fc.s * 0.5, fc.py / fc.s * 0.5, fc.seed + 1, 3)
    m = (1 - _ss(0.0, 0.02, np.abs(n - 0.5))) * float(d.get("amount", 1.0))
    fc.mul(m, 0.4)


def d_rust_streaks(fc: _Face, d):
    st = _ss(0.5, 0.8, fbm2(fc.px / fc.s * 2.2, fc.py / fc.s * 0.15, fc.seed + 1, 3))
    st = st * _ss(0.0, 0.6, fc.v) * float(d.get("amount", 0.8))
    fc.mul(st, np.array([0.72, 0.5, 0.34], f32))


def d_veins(fc: _Face, d):
    n = fbm2(fc.px / fc.s * 0.6, fc.py / fc.s * 0.6, fc.seed + 1, 3)
    m = (1 - _ss(0.0, 0.03, np.abs(n - 0.5))) * float(d.get("amount", 0.8))
    col = _rgb(d.get("colour", (40, 46, 36)))
    if d.get("emissive"):
        fc.emit(m, col)
    else:
        fc.paint(m, col, 0.7)


def d_glow_spot(fc: _Face, d):
    cu, cv = d.get("at", (0.5, 0.5))
    r = float(d.get("size", 0.2))
    col = _rgb(d.get("colour", (255, 200, 80)))
    fc.emit(fc.ellipse(cu, cv, r, r), col)
    halo = fc.ellipse(cu, cv, r * 1.6, r * 1.6) * (1 - fc.ellipse(cu, cv, r, r))
    m = halo > 0.5
    # にじみはほぼ全発光（α=EMISSIVE_HALO）なので色を暗くして「弱い光」にする
    fc.rgb[m] = fc.rgb[m] * 0.35 + col * 0.3
    fc.alpha[m] = np.minimum(fc.alpha[m], EMISSIVE_HALO)
    fc.glow[m] = True


def _sec_disc(fc: _Face, cx, cy, rx, ry=None, soft=1.0):
    """texel 座標の楕円のマスク（縁 1 texel で滑らか）と正規化距離。"""
    ry = rx if ry is None else ry
    dx = (fc.px - cx) / max(0.5, rx)
    dy = (fc.py - cy) / max(0.5, ry)
    dd = np.sqrt(dx * dx + dy * dy)
    return np.clip((1.0 - dd) * max(0.5, min(rx, ry)) / soft + 0.5, 0, 1), dd


def _sec_bone(fc: _Face, cx, cy, R, sd, marrow=True, spongy=False):
    """断面の骨: 白い皮質の輪と、赤い髄（spongy なら海綿状の黄色い骨）、周りの暗い溝。texel 単位。"""
    R = max(0.8, R)
    m, dd = _sec_disc(fc, cx, cy, R)
    groove = np.clip(1.0 - np.abs(dd - 1.0 - 0.6 / R) * R / 0.9, 0, 1) * (dd > 0.95)
    fc.mul(groove, 0.5)
    gr = fc.grain(sd)
    cort = _ramp(gr.reshape(-1), [(0.0, (196, 184, 158)), (1.0, (240, 232, 212))]).reshape(fc.h, fc.w, 3)
    fc.paint(m, cort)
    if spongy:
        sp = _ramp(fc.grain(sd + 1).reshape(-1), [(0.0, (150, 70, 52)), (0.45, (206, 168, 120)),
                                                   (1.0, (230, 206, 160))]).reshape(fc.h, fc.w, 3)
        fc.paint(np.clip((0.78 - dd) * R + 0.5, 0, 1), sp)
    elif marrow and R >= 1.3:
        mar = _ramp(fc.grain(sd + 2).reshape(-1), [(0.0, (92, 22, 18)), (0.5, (138, 46, 32)),
                                                    (1.0, (186, 120, 70))]).reshape(fc.h, fc.w, 3)
        fc.paint(np.clip((0.55 - dd) * R + 0.5, 0, 1), mar)


def d_section(fc: _Face, d):
    """切断面の断面（キューブ・面ごとの上書き。cut_flesh の素材が塗った面を描き直す）。

    外から 皮膚の縁 → 黄色い脂肪の輪 → 赤い筋肉の束（白い筋膜の線）→ 骨。濡れた照りと溜まった血。
    params（座標は面の正規化座標 u →右, v →下。半径は面の短い方の半分を 1 とした割合）:
      kind     "limb"（既定。骨 1 本）/ "neck"（頸椎・気管・食道・頸動脈）/ "torso"（腰椎と背筋・大動脈・
               ぎっしり詰まった腸の輪切り）/ "plain"（骨なし）
      centre   断面の中心 (0.5, 0.5)
      bone_at  骨（neck / torso では背骨）の位置。None で骨なし。既定は limb = centre、
               neck / torso = 中心から v の小さい側へ（呼ぶ側が「背中の向き」に合わせて渡すこと）
      bone_r   骨の半径（limb 0.26 / neck 0.24 / torso 0.17）。bones=[(u, v, r), ...] で骨を足せる
      fat      脂肪の輪の内側の半径（limb 0.74 / neck 0.84 / torso 0.8）。skin 皮膚の縁の内側 (0.9)
      wet      濡れ (0.8)
    """
    kind = d.get("kind", "limb")
    w, h = fc.w, fc.h
    sd = fc.seed
    cu, cv = d.get("centre", (0.5, 0.5))
    half = min(w, h) * 0.5
    x = (fc.px / w - cu) / 0.5
    y = (fc.py / h - cv) / 0.5
    rag = (fc.noise(1.3, sd + 1, 2) - 0.5) * 0.16
    pe = 2.6
    r = (np.abs(x) ** pe + np.abs(y) ** pe) ** (1 / pe) * (1.0 + rag)
    dflt = {"limb": (0.74, 0.26), "neck": (0.84, 0.24), "torso": (0.8, 0.17), "plain": (0.74, 0.0)}
    fat_in, br0 = dflt.get(kind, dflt["limb"])
    fat_in = float(d.get("fat", fat_in))
    skin_in = float(d.get("skin", 0.9))
    if "bone_at" in d:
        bone_at = d["bone_at"]
    elif kind in ("neck", "torso"):
        bone_at = (cu, cv - (0.27 if kind == "neck" else 0.32))
    elif kind == "plain":
        bone_at = None
    else:
        bone_at = (cu, cv)
    br = float(d.get("bone_r", br0)) * half
    # --- 筋肉（束の断面: Worley のセルごとに色が少し違い、境に白い筋膜）
    F1, F2, cid, _, _ = worley2(fc.px / fc.s * 1.4 + 3.1, fc.py / fc.s * 1.4 + 1.7, sd + 2)
    memb = 1.0 - _ss(0.02, 0.13, F2 - F1)
    mt = 0.5 + (cid - 0.5) * 0.5 + (fc.grain(sd + 3) - 0.5) * 0.25 - memb * 0.3
    mus = _ramp(mt.reshape(-1), [(0.0, (60, 6, 8)), (0.45, (116, 14, 16)), (0.8, (160, 34, 32)),
                                 (1.1, (190, 72, 62))]).reshape(h, w, 3)
    mus = mus + (_rgb((206, 150, 140)) - mus) * (memb * 0.4)[..., None]
    fc.paint(np.ones((h, w), f32), mus)
    # --- 脂肪の輪（ぶつぶつした黄色）。内側の縁は筋肉へ不規則に食い込む
    G1, G2, gc, _, _ = worley2(fc.px / fc.s * 2.6, fc.py / fc.s * 2.6, sd + 4)
    ft = 0.55 + (gc - 0.5) * 0.4 - (1.0 - _ss(0.0, 0.2, G2 - G1)) * 0.3
    fat = _ramp(ft.reshape(-1), [(0.0, (150, 112, 54)), (0.5, (214, 182, 98)),
                                 (1.0, (240, 216, 142))]).reshape(h, w, 3)
    wob = (fc.noise(2.2, sd + 5, 2) - 0.5) * 0.08
    fc.paint(_ss(fat_in - 0.03, fat_in + 0.02, r + wob), fat)
    # --- 皮膚の縁（体の肌の色）と、切り口の外周の暗さ
    base, shd, hil = _tone(fc.style if fc.style.get("tone") is not None else {"tone": "pale"})
    sk = _ramp(fc.grain(sd + 6).reshape(-1), [(0.0, shd), (0.6, base), (1.0, hil)]).reshape(h, w, 3)
    fc.paint(_ss(skin_in - 0.02, skin_in + 0.03, r), sk)
    fc.mul(_ss(0.95, 1.06, r), 0.62)
    # --- 種類ごとの中身
    inner = r < fat_in - 0.02
    if kind in ("neck", "torso") and bone_at is not None:
        sx, sy = bone_at[0] * w, bone_at[1] * h
        bx, by = sx - cu * w, sy - cv * h
        n_ = math.hypot(bx, by)
        bx, by = (bx / n_, by / n_) if n_ > 1e-6 else (0.0, -1.0)
        qx, qy = -by, bx
        along = (fc.px - sx) * bx + (fc.py - sy) * by          # 背中へ +
        across = (fc.px - sx) * qx + (fc.py - sy) * qy
        R = max(1.2, br)
        if kind == "torso":
            # 背骨の両脇の太い背筋（暗い赤の塊）と、腹腔の腸の輪切り・大動脈
            for sg in (-1, 1):
                em, _ = _sec_disc(fc, sx + qx * sg * 1.9 * R + bx * 0.7 * R, sy + qy * sg * 1.9 * R + by * 0.7 * R,
                                  1.25 * R, 1.25 * R)
                fc.mul(em * inner, np.array([0.78, 0.6, 0.62], f32))
            # 腹腔: 脂肪の輪の内側で、背骨と背筋より前。腸の輪切り（管の壁・中身）がぎっしり詰まり、
            # 隙間に血が溜まる。腸 1 本は面の短い方の半分の 0.3 ほど（小さいと砂嵐に見える）
            cav = inner & (along < -1.5 * R) & (r < fat_in - 0.05)
            cell = max(3.2, 0.3 * half)
            H1, H2, hc, _, _ = worley2(fc.px / cell + 0.37, fc.py / cell + 0.71, sd + 7, jitter=0.55)
            tube = _ss(0.47, 0.40, H1)
            wall = _ss(0.47, 0.42, H1) * (1 - _ss(0.36, 0.30, H1))
            gcol = _ramp((hc * 0.6 + fc.grain(sd + 8) * 0.4).reshape(-1),
                         [(0.0, (158, 88, 84)), (0.5, (200, 132, 122)), (1.0, (222, 168, 146))]).reshape(h, w, 3)
            fc.paint(cav * 0.95, _rgb((48, 4, 8)))                  # 腸の間に溜まった血
            fc.paint(cav * tube, gcol)
            fc.paint(cav * wall, _rgb((112, 44, 52)), 0.85)
            lum = cav * _ss(0.2, 0.1, H1) * (hc > 0.35)
            fc.paint(lum, _rgb((92, 62, 30)), 0.9)                 # 中身（黄褐色）
            fc.paint(cav * tube * (fc.grain(sd + 13) > 0.9), _GLINT, 0.5)
            am, _ = _sec_disc(fc, sx - bx * 2.1 * R, sy - by * 2.1 * R, 0.6 * R)
            fc.paint(am, _rgb((210, 170, 160)))                    # 大動脈の壁
            am2, _ = _sec_disc(fc, sx - bx * 2.1 * R, sy - by * 2.1 * R, 0.38 * R)
            fc.paint(am2, _rgb((70, 4, 8)))
        else:
            # 首: 前に気管（白い軟骨の輪と暗い穴）、その後ろに潰れた食道、両脇に頸動脈
            ta = d.get("trachea_at")
            if ta is None:
                tx, ty = cu * w - bx * 0.6 * half, cv * h - by * 0.6 * half
            else:
                tx, ty = ta[0] * w, ta[1] * h
            tr = max(1.2, 0.2 * half)
            tm, _ = _sec_disc(fc, tx, ty, tr)
            fc.paint(tm, _rgb((222, 204, 196)))
            lm, _ = _sec_disc(fc, tx, ty, max(0.55, tr * 0.55))
            fc.paint(lm, _rgb((26, 6, 8)))
            ex_, ey_ = (tx + sx) / 2 + bx * 0.1 * half, (ty + sy) / 2 + by * 0.1 * half
            om, _ = _sec_disc(fc, ex_, ey_, max(1.0, 0.24 * half), max(0.7, 0.1 * half))
            fc.paint(om, _rgb((150, 58, 62)))
            fc.paint(om * (np.abs((fc.px - ex_) * bx + (fc.py - ey_) * by) < 0.5), _rgb((60, 12, 16)))
            for sg in (-1, 1):
                vx_ = tx + qx * sg * 0.42 * half + bx * 0.12 * half
                vy_ = ty + qy * sg * 0.42 * half + by * 0.12 * half
                cm, _ = _sec_disc(fc, vx_, vy_, max(0.7, 0.1 * half))
                fc.paint(cm, _rgb((96, 6, 10)))
                jm, _ = _sec_disc(fc, vx_ + qx * sg * 0.16 * half, vy_ + qy * sg * 0.16 * half, max(0.6, 0.09 * half))
                fc.paint(jm * (1 - cm), _rgb((54, 14, 34)))
        # 椎骨: 椎体（海綿骨）・椎弓と脊柱管（中に白っぽい脊髄）・後ろへ突き出す棘突起・（腰椎は）横突起
        _sec_bone(fc, sx - bx * 0.35 * R, sy - by * 0.35 * R, 1.05 * R, sd + 9, spongy=True)
        arch, _ = _sec_disc(fc, sx + bx * 0.75 * R, sy + by * 0.75 * R, 0.78 * R)
        fc.paint(arch, _rgb((226, 216, 192)))
        sp_len = 2.4 * R if kind == "torso" else 1.9 * R
        spn = (along > 0.9 * R) & (along < sp_len) & (np.abs(across) < np.maximum(0.5, 0.34 * R - 0.08 * (along - R)))
        fc.paint(spn * inner, _rgb((222, 210, 184)))
        if kind == "torso":
            tp = (np.abs(along - 0.55 * R) < max(0.5, 0.24 * R)) & (np.abs(across) > 0.8 * R) & (np.abs(across) < 2.1 * R)
            fc.paint(tp * inner, _rgb((214, 202, 176)))
        canal, _ = _sec_disc(fc, sx + bx * 0.8 * R, sy + by * 0.8 * R, max(0.6, 0.42 * R))
        fc.paint(canal, _rgb((40, 8, 10)))
        cord, _ = _sec_disc(fc, sx + bx * 0.8 * R, sy + by * 0.8 * R, max(0.45, 0.26 * R))
        fc.paint(cord * (R >= 1.8), _rgb((216, 190, 170)))
    elif bone_at is not None and br > 0:
        _sec_bone(fc, bone_at[0] * w, bone_at[1] * h, br, sd + 9)
    for b_ in d.get("bones", ()) or ():
        _sec_bone(fc, b_[0] * w, b_[1] * h, float(b_[2]) * half, sd + 10)
    # --- 濡れ: 切り口に溜まった血（低い所が暗い）と照り
    wet = float(d.get("wet", 0.8))
    if wet > 0:
        pool = _ss(0.55, 0.75, fc.noise(0.9, sd + 11, 2)) * (r < skin_in) * wet
        fc.mul(pool, np.array([0.62, 0.3, 0.3], f32))
        gl = (fc.grain(sd + 12) > 0.94 - 0.04 * wet) & (r < fat_in)
        fc.paint(gl, _GLINT, 0.45 * wet)


def section_decal(faces=("down",), **params) -> Dict[str, dict]:
    """断面デカールを面ごとに置く辞書（cube.decals にそのまま入れる / update する）。
    例: Cube(..., "cut_flesh", decals=section_decal(("up",), kind="neck", bone_at=(0.5, 0.24)))"""
    return {f: dict(params, name="section") for f in faces}


def d_logo(fc: _Face, d):
    """架空のロゴ（実在の企業ロゴは使わない）: 円と横棒と短い文字。"""
    col = _rgb(d.get("colour", (230, 226, 214)))
    cu, cv = d.get("at", (0.5, 0.5))
    sz = float(d.get("size", 0.5))
    ring = fc.ellipse(cu - sz * 0.32, cv, sz * 0.16, sz * 0.16 * fc.w / fc.h)
    ring = ring * (1 - fc.ellipse(cu - sz * 0.32, cv, sz * 0.09, sz * 0.09 * fc.w / fc.h))
    fc.paint(ring, col)
    if d.get("text"):
        fc.paint(text_mask(d["text"], fc.w, fc.h, (cu + sz * 0.15, cv), d.get("px")), col)


# ---- ゾンビの顔 ---------------------------------------------------------------
def d_face(fc: _Face, d):
    """写実寄りのゾンビの顔。線で描かず、光と影で彫る（下地の肌の質感を残す）。

    params: eyes = clouded|bloodshot|glowing_yellow|glowing_red|glowing_green|none
            mouth = snarl|gaping|torn|stitched|jawless|closed
            decay 0..4, gore 0..1, nose = True/False（既定は decay < 3.5）
            region = full（頭の正面 1 枚）| upper（生え際〜上唇の顔板。顎は別ボーン）| jaw（下顎の正面）
            位置（正規化。v は上端 0 → 下端 1）: eye_v, eye_gap（= eye_dx。目は u = 0.5 ± eye_gap）,
            brow_v, nose_v（鼻の穴の高さ）, mouth_v（口の線）, calm（肌のざらつきを均す量）
    """
    eyes = d.get("eyes", "clouded")
    mouth = d.get("mouth", "snarl")
    decay = float(d.get("decay", 2))
    gore = float(d.get("gore", 0.5))
    region = d.get("region", "full")
    sd = fc.seed
    w, h = fc.w, fc.h
    nose = bool(d.get("nose", decay < 3.5))
    # 顔の中は肌のざらつきを 3x3 で均す（造形が読めるように）
    r = fc.rgb
    pad = np.pad(r, ((1, 1), (1, 1), (0, 0)), mode="edge")
    avg = sum(pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9.0
    calm = float(d.get("calm", 0.55))
    fc.rgb[...] = r * (1 - calm) + avg * calm
    if region == "jaw":
        _face_jaw(fc, d, mouth, decay, gore)
        return
    upper = region == "upper"
    ev = float(d.get("eye_v", 0.52 if upper else 0.46))
    eu = float(d.get("eye_gap", d.get("eye_dx", 0.25 if upper else 0.2)))
    mv = float(d.get("mouth_v", 0.97 if upper else 0.78))
    nv = float(d.get("nose_v", ev + (mv - ev) * 0.68))
    bv = float(d.get("brow_v", ev - 0.09 * (1.0 if not upper else 1.4)))
    sock = 0.5 + 0.12 * decay
    eh_n = max(0.06, (nv - ev) * 0.35)        # 目の周りの造形の縦の大きさ
    # --- 造形（掛け算の陰影） ---
    fc.mul(fc.blob(0.5, bv, 0.42, 0.06), 1.12)                                   # 眉骨
    fc.mul(fc.blob(0.5, (bv + ev) / 2, 0.42, 0.03), 0.9)
    for s_ in (-1, 1):
        cu = 0.5 + s_ * eu
        # 落ちくぼんだ眼窩: 外側は柔らかく、目の周りは紫黒く
        fc.mul(fc.blob(cu, ev + 0.015, 0.17, eh_n * 1.6), np.array([0.6, 0.5, 0.56], f32) ** (sock / 0.7))
        fc.mul(fc.blob(cu, ev + 0.01, 0.1, eh_n), np.array([0.62, 0.5, 0.56], f32) ** (sock / 0.7))
        fc.mul(fc.blob(cu + s_ * 0.06, (ev + nv) / 2 + 0.02, 0.12, eh_n), 1.12)       # 頬骨
        fc.mul(fc.blob(cu + s_ * 0.04, (nv + mv) / 2 + 0.02, 0.10, (mv - nv) * 0.5 + 0.03),
               0.80 - 0.04 * decay)                                                # こけた頬
    if nose:
        fc.mul(fc.blob(0.5, (ev + nv) / 2, 0.05, (nv - ev) * 0.6), 1.14)           # 鼻筋
        fc.mul(fc.blob(0.44, (ev + nv) / 2 + 0.03, 0.03, (nv - ev) * 0.45), 0.86)
        fc.mul(fc.blob(0.5, nv + 0.035, 0.10, 0.03), 0.70)                         # 鼻の下の影
        for s_ in (-1, 1):
            fc.paint(fc.ellipse(0.5 + s_ * 0.045, nv, 0.6 / w + 0.01, 0.5 / h + 0.008),
                     _rgb((40, 14, 14)), 0.9)                                      # 鼻の穴
    else:
        # 鼻が腐り落ちた穴（逆ハート型の空洞と骨の縁）
        cy = nv - 0.04
        ry = max(0.06, (nv - ev) * 0.35)
        cav = np.maximum(fc.ellipse(0.47, cy, 0.045, ry), fc.ellipse(0.53, cy, 0.045, ry))
        fc.paint(fc.ellipse(0.5, cy - 0.01, 0.11, ry * 1.35), _rgb((96, 30, 26)), 0.6)
        fc.paint(cav, _rgb((20, 4, 4)))
        fc.paint(fc.seg(0.5, cy - ry, 0.5, cy + ry, 1.0) * cav, _rgb((180, 168, 140)), 0.7)
    if not upper:
        fc.mul(fc.blob(0.5, mv + 0.13, 0.16, 0.05), 1.08)                         # 顎先
        fc.mul(fc.blob(0.5, min(0.99, mv + 0.22), 0.5, 0.05), 0.82)                # 顎の下の影
    # --- 目 ---
    for s_ in (-1, 1):
        _eye(fc, 0.5 + s_ * eu, ev, eyes, decay, gore, s_, d.get("glow_colour"))
    # --- 口 ---
    if upper:
        _mouth_upper(fc, mv, mouth, decay, gore)
    else:
        _mouth(fc, mv, mouth, decay, gore)
    # --- 血・汚れ ---
    if gore > 0:
        g = fc.noise(1.2, sd + 41, 2)
        # 口の周りと顎に血（縁はノイズでぎざぎざ）。下唇から垂れる
        smear = fc.blob(0.5, mv + (0.0 if upper else 0.06), 0.15 + 0.05 * gore, 0.06 + 0.04 * gore) * \
            (0.6 + 0.9 * gore)
        m = np.clip(smear * 1.5 - (1.0 - g) * 0.9, 0, 1)
        fc.paint(m, fc.bcol * (0.75 + 0.3 * fc.grain(sd + 44))[..., None], 0.9)
        fc.drips_from((m > 0.5).astype(f32), gore, sd + 42)
        if nose and gore > 0.3:
            for s_ in (-1, 1):
                fc.paint(fc.seg(0.5 + s_ * 0.045, nv + 0.01, 0.5 + s_ * 0.05, mv - 0.03, 1.0),
                         fc.bcol * 0.8, 0.8 * gore)
    # 血の涙（gore が強いとき。目が無い種類は眼窩から必ず流す。bleed=False で無し）
    if gore > 0.4 or (eyes == "none" and d.get("bleed", True)):
        tg = max(gore, 0.6) if eyes == "none" else gore
        for s_ in (-1, 1):
            tear = np.zeros((h, w), f32)
            x = int((0.5 + s_ * (eu - 0.03)) * w)
            y0 = int((ev + 0.04) * h)
            y1 = int(min(h - 1, (ev + 0.04 + 0.12 * tg + 0.08 * fc.grain(sd + 43 + s_)[0, 0]) * h))
            tear[y0:y1, x:x + 1] = 1.0
            fc.paint(tear, fc.bcol * 0.8, 0.75 * tg)


def _mouth_upper(fc: _Face, mv, kind, decay, gore):
    """顔板（生え際〜上唇）の下端の口: 上唇、めくれた唇の下の歯茎、裂けた頬。歯は別キューブ。"""
    w, h = fc.w, fc.h
    mw = 0.2 + 0.02 * decay
    lip = fc.ellipse(0.5, mv - 0.02, mw, max(0.6 / h, 0.03))
    fc.mul(fc.blob(0.5, mv - 0.07, mw * 1.1, 0.04), 0.82)                      # 上唇の上の溝の影
    if kind in ("snarl", "gaping", "torn", "jawless"):
        # 唇がめくれて歯茎が見える
        gum = fc.ellipse(0.5, mv + 0.005, mw * 0.95, max(0.8 / h, 0.035))
        fc.paint(gum, _rgb((112, 40, 46)) * (0.85 + 0.25 * fc.grain(fc.seed + 81))[..., None])
        fc.paint(fc.ellipse(0.5, mv - 0.035, mw, max(0.6 / h, 0.02)), _rgb((70, 24, 26)), 0.85)
        bottom = (fc.py > h - 1.0) & (np.abs(fc.u - 0.5) < mw * 0.9)
        fc.paint(bottom, _rgb((22, 4, 6)))                                     # 口の奥の暗がり
    elif kind == "stitched":
        fc.paint(lip, _rgb((60, 20, 22)), 0.8)
        n = max(3, int(mw * 2 * w / 2.5))
        for i in range(n):
            u = 0.5 - mw + (i + 0.5) * 2 * mw / n
            fc.paint(fc.seg(u - 0.6 / w, mv - 2.0 / h, u + 0.6 / w, 1.0, 1.0), _rgb((22, 18, 16)))
    else:
        fc.paint(lip, _rgb((76, 30, 30)), 0.75)
    if kind == "torn":
        tear = fc.ellipse(0.5 + mw * 1.1, mv - 0.03, mw * 0.5, 0.06) * (fc.noise(1.6, fc.seed + 82, 2) > 0.3)
        fc.paint(tear, _rgb((110, 18, 20)))
        fc.paint(tear * (fc.py > mv * h - 1.0), _rgb((196, 180, 132)) * 0.85)
    if kind == "jawless":
        rag = (fc.noise(1.8, fc.seed + 83, 2) > 0.45) & (fc.v > mv - 0.08) & (np.abs(fc.u - 0.5) < mw * 1.3)
        fc.paint(rag, _rgb((120, 20, 22)))


def _face_jaw(fc: _Face, d, mouth, decay, gore):
    """下顎の正面（顎先）: 下唇、唇の下の影、顎先の照り、口から垂れる血。"""
    w, h = fc.w, fc.h
    mv = float(d.get("mouth_v", -0.03))
    mw = 0.36 + 0.03 * decay                     # 顎の板は幅が狭いので口は相対的に広い
    lip_v = max(0.5 / h, mv + 0.12)
    if mouth in ("snarl", "gaping", "torn"):
        fc.paint(fc.ellipse(0.5, lip_v - 0.06, mw, max(0.7 / h, 0.08)), _rgb((104, 36, 42)), 0.9)   # 下の歯茎
        fc.paint(fc.ellipse(0.5, lip_v + 0.04, mw, max(0.6 / h, 0.06)), _rgb((66, 22, 24)), 0.85)  # めくれた下唇
    elif mouth == "stitched":
        n = max(3, int(mw * 2 * w / 2.5))
        for i in range(n):
            u = 0.5 - mw + (i + 0.5) * 2 * mw / n
            fc.paint(fc.seg(u - 0.6 / w, 0.0, u + 0.6 / w, lip_v + 2.0 / h, 1.0), _rgb((22, 18, 16)))
    else:
        fc.paint(fc.ellipse(0.5, lip_v, mw, max(0.6 / h, 0.06)), _rgb((80, 32, 32)), 0.7)
    fc.mul(fc.blob(0.5, lip_v + 0.2, mw * 1.2, 0.12), 0.8)                     # 唇の下の影
    fc.mul(fc.blob(0.5, 0.72, 0.3, 0.14), 1.1)                                 # 顎先
    fc.mul(fc.blob(0.5, 1.0, 0.6, 0.1), 0.82)
    if gore > 0:
        top = np.zeros((h, w), f32)
        top[0:max(1, int(h * 0.18)), :] = (np.abs(fc.u[0:max(1, int(h * 0.18)), :] - 0.5) < mw).astype(f32)
        g = fc.noise(1.2, fc.seed + 91, 2)
        m = np.clip(fc.blob(0.5, lip_v, mw * 1.1, 0.25) * (0.6 + 0.9 * gore) * 1.5 - (1 - g) * 0.9, 0, 1)
        fc.paint(m, fc.bcol * (0.75 + 0.3 * fc.grain(fc.seed + 92))[..., None], 0.9)
        fc.drips_from(np.maximum(top * (g > 0.45), (m > 0.5).astype(f32)), gore, fc.seed + 93)


def _eye(fc: _Face, cu, ev, kind, decay, gore, side, glow_colour=None):
    """顔の目 1 つ（EYES の全種類）。cu, ev は目の中心（面の正規化座標）、side は -1 = u の小さい側。"""
    info = eye_info(kind, glow_colour)
    w, h = fc.w, fc.h
    glowing = info["glow"] is not None
    ew = max(1.6, w * (0.064 if glowing else 0.075))   # 目の半幅（texel）
    eh = max(0.7, h * 0.03)
    ru, rv = ew / w, eh / h
    open_ = fc.ellipse(cu, ev, ru, rv, soft=0.6)
    lid = fc.ellipse(cu, ev - 0.6 / h, ru * 1.15, rv * 1.6) * (1 - open_)
    fc.paint(lid, _rgb((70, 34, 34)), 0.55)                 # 赤黒い瞼
    if kind == "none":
        # 目が無い: 暗い眼窩の穴（奥ほど黒い）と、縁の乾いた血
        fc.paint(fc.ellipse(cu, ev, ru * 1.05, rv * 1.7), _rgb((14, 2, 2)))
        fc.paint(fc.ellipse(cu, ev - 0.5 / h, ru * 0.6, rv * 0.6), _rgb((60, 8, 8)), 0.5)
        fc.paint(np.clip(fc.ellipse(cu, ev, ru * 1.25, rv * 2.1) - fc.ellipse(cu, ev, ru * 1.05, rv * 1.7), 0, 1),
                 _rgb((58, 14, 12)), 0.6)
        return
    dx = (fc.px - cu * w) / max(0.5, ru * w)
    dy = (fc.py - ev * h) / max(0.5, rv * h)
    rr = np.sqrt(dx * dx + dy * dy)
    if glowing:
        gc = info["glow"]
        eye_m = np.maximum(open_, fc.ellipse(cu, ev, ru, rv * 1.2))
        if kind in _PINPOINT_EYES:
            # 闇の中の光点: 白目は真っ暗、中心の 1 texel（大きな顔なら十字に 5 texel）だけ光る
            fc.paint(eye_m, info["sclera"] + f32(4))
            pt = (np.abs(fc.px - cu * w) < 0.75) & (np.abs(fc.py - ev * h) < 0.75)
            if ew >= 3.0:
                pt = pt | ((np.abs(fc.px - cu * w) < 1.6) & (np.abs(fc.py - ev * h) < 0.6))
            fc.emit(pt, info["pupil"], thr=0.5)
            return
        # にじみ（目の外側 1 texel）: 暗い発光色。発光は α=EMISSIVE_HALO（DESIGN §13 の 3〜40）
        halo = fc.ellipse(cu, ev, ru + 1.2 / w, rv + 1.2 / h)
        m = (halo > 0.5) & (eye_m <= 0.4)
        fc.rgb[m] = fc.rgb[m] * 0.35 + gc * 0.3
        fc.alpha[m] = np.minimum(fc.alpha[m], EMISSIVE_HALO)
        fc.glow[m] = True
        core = _ramp(rr.reshape(-1), [(0.0, info["pupil"]), (0.35, np.minimum(255, gc * 1.0 + 30)),
                                      (0.8, gc), (1.3, gc * 0.7)]).reshape(h, w, 3)
        fc.emit(eye_m, core, thr=0.4)
        return
    scl = info["sclera"] * np.array([0.84, 0.8, 0.7] if kind == "clouded" else [0.86, 0.84, 0.82], f32)
    gr = fc.grain(fc.seed + 61 + side)
    fc.paint(open_, scl * (0.86 + 0.18 * gr)[..., None])
    if kind == "bloodshot":
        # 白目の毛細血管（1 texel の赤い点）
        fc.paint(open_ * (fc.grain(fc.seed + 64 + side) > 0.7), _rgb((150, 30, 28)), 0.7)
    # 虹彩（少し上・内側を見る）。milky は虹彩も白く、灰青のにごりだけ
    iu = cu - side * 0.15 * ru
    ir = fc.ellipse(iu, ev, max(0.55, ew * 0.48) / w, max(0.6, eh * 1.0) / h) * open_
    if kind == "milky":
        fc.paint(ir, _rgb((196, 204, 210)), 0.5)
    else:
        fc.paint(ir, info["iris"])
    pupil = info["pupil"]
    if pupil is not None:
        pw = max(0.5, ew * (0.3 if kind == "bloodshot" else 0.18))
        fc.paint(fc.ellipse(iu, ev, pw / w, 0.5 / h) * open_, pupil, 0.85 if kind == "clouded" else 1.0)
    if kind == "clouded":
        fc.paint(fc.ellipse(iu, ev, max(0.5, ew * 0.25) / w, 0.5 / h) * open_, _rgb((228, 232, 230)), 0.35)
    # 上瞼の影と照り
    top = open_ * (fc.py < ev * h - eh * 0.2)
    fc.mul(top, 0.72)
    gl = fc.ellipse(cu + side * ru * 0.4, ev - rv * 0.3, 0.5 / w, 0.5 / h) * open_
    fc.paint(gl, _rgb((250, 246, 236)), 0.8)
    # 下瞼の赤み
    fc.paint(fc.ellipse(cu, ev + rv * 1.6, ru * 0.9, 0.6 / h) * (1 - open_), _rgb((120, 40, 40)), 0.4)


def _mouth(fc: _Face, mv, kind, decay, gore):
    w, h = fc.w, fc.h
    mw = 0.2 + 0.02 * decay          # 口の半幅
    sd = fc.seed
    tooth = _rgb((206, 190, 140))
    if kind == "closed":
        fc.paint(fc.seg(0.5 - mw * 0.8, mv, 0.5 + mw * 0.8, mv, 1.0), _rgb((64, 22, 22)))
        fc.mul(fc.blob(0.5, mv + 0.04, mw * 0.9, 0.025), 1.1)
        return
    if kind == "stitched":
        fc.mul(fc.blob(0.5, mv, mw * 1.1, 0.05), np.array([0.72, 0.55, 0.55], f32))
        fc.paint(fc.seg(0.5 - mw, mv, 0.5 + mw, mv, 1.0), _rgb((60, 14, 16)))
        n = max(3, int(mw * 2 * w / 2.5))
        for i in range(n):
            u = 0.5 - mw + (i + 0.5) * 2 * mw / n
            fc.paint(fc.seg(u - 0.7 / w, mv - 1.5 / h, u + 0.7 / w, mv + 1.5 / h, 1.0), _rgb((22, 18, 16)))
        return
    if kind == "gaping":
        top, bot = mv - 0.06, mv + 0.12
    elif kind == "jawless":
        top, bot = mv - 0.04, 1.02
    else:   # snarl / torn
        top, bot = mv - 0.035, mv + 0.05
    hole = fc.ellipse(0.5, (top + bot) / 2, mw, (bot - top) / 2 + 0.5 / h)
    if kind == "jawless":
        hole = np.maximum(hole, ((fc.v > mv) & (np.abs(fc.u - 0.5) < mw * (1.1 - 0.3 * (fc.v - mv)))).astype(f32))
    inner = _ramp(fc.grain(sd + 71).reshape(-1), [(0.0, (16, 3, 4)), (0.7, (40, 8, 9)), (1.0, (70, 14, 14))]).reshape(h, w, 3)
    fc.paint(fc.ellipse(0.5, (top + bot) / 2, mw * 1.12, (bot - top) / 2 + 1.5 / h), _rgb((84, 26, 26)), 0.7)  # 唇の縁
    fc.paint(hole, inner)
    # 歯（1 texel の隙間で区切る）。腐敗で欠ける
    tw = max(1.0, w * 0.04)

    def row(vrow, rows=1.0):
        band = (np.abs(fc.py - vrow * h) < max(0.6, rows * h * 0.022)) & (hole > 0.5)
        k = np.floor(fc.px / (tw + 1))
        gap = (fc.px - k * (tw + 1)) < 1.0
        missing = texel_rand(k.astype(np.int64), np.full_like(k, int(vrow * 100)).astype(np.int64), sd + 72) < 0.1 + 0.06 * decay
        tcol = tooth * (0.8 + 0.25 * fc.grain(sd + 73))[..., None]
        stain = (fc.grain(sd + 74) > 0.7)
        tcol = np.where(stain[..., None], tcol * np.array([0.7, 0.6, 0.45], f32), tcol)
        m = band & ~gap & ~missing
        fc.paint(m, tcol)

    row(top + 0.02, 1.2)
    if kind in ("gaping", "snarl", "torn"):
        row(bot - 0.02, 1.0)
    if kind == "gaping":
        fc.paint(fc.ellipse(0.5, bot - 0.035, mw * 0.55, 0.03) * hole, _rgb((110, 40, 44)), 0.8)  # 舌
    if kind == "torn":
        # 片頬が裂けて奥歯が見える
        tear = fc.ellipse(0.5 + mw * 1.1, mv, mw * 0.55, 0.045) * (fc.noise(1.6, sd + 75, 2) > 0.3)
        fc.paint(tear, _rgb((110, 18, 20)))
        fc.paint(tear * (np.abs(fc.py - mv * h) < 1.0), tooth * 0.85)
    if kind == "jawless":
        tongue = fc.ellipse(0.5, mv + 0.16, mw * 0.4, 0.12) * (fc.v > mv + 0.04)
        fc.paint(tongue, _rgb((128, 44, 50)))
        fc.mul(tongue * (np.abs(fc.u - 0.5) < 0.5 / w + 0.01), 0.7)
        rag = fc.noise(1.8, sd + 76, 2)
        flesh_m = (hole > 0.5) & (rag > 0.55) & (fc.v > mv + 0.04)
        fc.paint(flesh_m, _rgb((126, 22, 24)))


DECALS = {
    "face": d_face, "wound": d_wound, "bite": d_bite, "bullet_hole": d_bullet_hole, "burn": d_burn,
    "text": d_text, "number": d_text, "stripe": d_stripe, "badge": d_badge, "grime": d_grime,
    "stitches": d_stitches, "drips": d_drips, "handprint": d_handprint, "buttons": d_buttons,
    "pocket": d_pocket, "zipper": d_zipper, "cracks": d_cracks, "rust_streaks": d_rust_streaks,
    "veins": d_veins, "glow_spot": d_glow_spot, "logo": d_logo, "section": d_section,
}


# ---------------------------------------------------------------------------
#  本体
# ---------------------------------------------------------------------------
class _Atlas:
    def __init__(self, w, h):
        self.rgb = np.zeros((h, w, 3), f32)
        self.alpha = np.zeros((h, w), np.uint8)
        self.glow = np.zeros((h, w), bool)
        self.shade = np.ones((h, w), f32)


def _decal_list(v) -> List[dict]:
    if v is None:
        return []
    if isinstance(v, (str, dict)):
        v = [v]
    out = []
    for d in v:
        out.append({"name": d} if isinstance(d, str) else dict(d))
    return out


def paint_model(model, stylebook: Dict[str, dict], seed: int = 0, face_light: bool = True,
                ao: bool = True) -> Image.Image:
    """model（mcmodel.Model）を stylebook で塗った RGBA 画像を返す。"""
    if not model.tex_w:
        model.pack()
    W, H = model.tex_w, model.tex_h
    at = _Atlas(W, H)
    cubes = model.all_cubes()
    if not cubes:
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mats = cube_world_matrices(model)
    ys = []
    for c in cubes:
        M = mats.get(id(c))
        o, s = np.asarray(c.origin, float), np.asarray(c.size, float)
        if M is None:
            ys += [o[1], o[1] + s[1]]
            continue
        cor = np.array([[o[0] + s[0] * i, o[1] + s[1] * j, o[2] + s[2] * k]
                        for i in (0, 1) for j in (0, 1) for k in (0, 1)])
        ys += list((cor @ M[:3, :3].T + M[:3, 3])[:, 1])
    ybounds = (min(ys), max(ys))
    groups: Dict[str, list] = {}
    for k, cube in enumerate(cubes):
        if cube.style not in stylebook:
            raise KeyError(f"{model.identifier}: stylebook に style '{cube.style}' がない")
        for face in FACES:
            rect = cube.rects.get(face)
            if rect is None or rect[2] <= 0 or rect[3] <= 0:
                continue
            groups.setdefault(cube.style, []).append((k, cube, face, rect))
    for name in sorted(groups):
        p = stylebook[name]
        mat = p.get("mat", "skin")
        if mat not in MATERIALS:
            raise ValueError(f"style '{name}': 未知の素材 '{mat}'（{sorted(MATERIALS)}）")
        fn, bmode = MATERIALS[mat]
        sd = _seed(seed, name, mat, p.get("seed", 0))
        F = _build_field(groups[name], ybounds, sd, H, W, mats)
        col = fn(F, p, sd)
        hard = F.hard
        wear = float(p.get("wear", 0.0))
        if hard and wear > 0:
            col = _ov_wear_edges(F, col, wear, sd + 101)
        dirt = float(p.get("dirt", 0.0))
        if dirt > 0:
            col = _ov_dirt(F, col, dirt, sd + 102, hard)
        burn = float(p.get("burn", 0.0))
        if burn > 0:
            col = _ov_burn(F, col, burn, sd + 103)
        blood = float(p.get("blood", 0.0))
        if blood > 0 and bmode != "none":
            col = _ov_blood(F, col, blood, bmode, sd + 104, p.get("blood_kind", "red"),
                            float(p.get("blood_age", 0.0)))
        wetp = float(p.get("wet", 0.0))
        wetm = F.wetm
        if wetp > 0:
            wetm = np.maximum(wetm if wetm is not None else 0, f32(wetp))
        if wetm is not None:
            col = _ov_wet(F, col, wetm, sd + 105)
        glow = F.glow
        if p.get("emissive") and mat not in ("fungus", "char"):
            glow = np.ones(F.n, bool)
        sh = _shade_field(F, mat in _ORGANIC, face_light, ao, hard)
        at.rgb[F.ay, F.ax] = np.clip(col, 0, 255)
        at.shade[F.ay, F.ax] = sh
        at.alpha[F.ay, F.ax] = 255
        if glow is not None:
            gm = np.broadcast_to(np.asarray(glow, bool), (F.n,))
            at.glow[F.ay[gm], F.ax[gm]] = True
            at.alpha[F.ay[gm], F.ax[gm]] = EMISSIVE_ALPHA
    # デカール
    for k, cube in enumerate(cubes):
        if not cube.decals:
            continue
        p = stylebook[cube.style]
        items = []
        for face, dv in cube.decals.items():
            if face == "*":
                # キューブ単位のデカール: d["faces"]（既定は 6 面全部）の各面に描く
                for j, d in enumerate(_decal_list(dv)):
                    for f_ in d.get("faces") or FACES:
                        items.append((f_, 100 + j, d))
                continue
            items += [(face, j, d) for j, d in enumerate(_decal_list(dv))]
        for face, j, d in items:
            rect = cube.rects.get(face)
            if rect is None or rect[2] <= 0 or rect[3] <= 0:
                continue
            fn = DECALS.get(d.get("name"))
            if fn is None:
                raise ValueError(f"未知のデカール '{d.get('name')}'（{sorted(DECALS)}）")
            fc = _Face(at, cube, face, rect, p, _seed(seed, k, face, j, d.get("seed", 0)))
            fn(fc, d)
    # 陰影を掛けて量子化（光る texel には掛けない）
    sh = np.where(at.glow, 1.0, at.shade)
    rgb = at.rgb * sh[..., None]
    # 4x4 のベイヤー配列で ±0.5 の誤差拡散代わり（グラデーションの段を消す）
    bayer = (np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], f32) + 0.5) / 16 - 0.5
    rgb = rgb + np.tile(bayer, (H // 4 + 1, W // 4 + 1))[:H, :W, None]
    out = np.zeros((H, W, 4), np.uint8)
    out[..., :3] = np.clip(np.round(rgb), 0, 255).astype(np.uint8)
    out[..., 3] = at.alpha
    out[at.alpha == 0, :3] = 0
    return Image.fromarray(out, "RGBA")


# ---------------------------------------------------------------------------
#  スタイル作成の補助
# ---------------------------------------------------------------------------
def style(mat: str, **params) -> dict:
    if mat not in MATERIALS:
        raise ValueError(f"未知の素材 '{mat}'")
    d = {"mat": mat}
    d.update(params)
    return d


def cloth_style(base, pattern="plain", dirt=0.35, blood=0.2, torn=0.0, alt=None, wear=0.3, **kw) -> dict:
    return style("cloth", base=base, pattern=pattern, dirt=dirt, blood=blood, torn=torn,
                 alt=alt, wear=wear, **kw)


def denim_style(base=CLOTH["denim"], dirt=0.4, blood=0.2, torn=0.0, wear=0.5, **kw) -> dict:
    return style("denim", base=base, dirt=dirt, blood=blood, torn=torn, wear=wear, **kw)


def knit_style(base, pattern="plain", dirt=0.3, blood=0.2, torn=0.0, alt=None, **kw) -> dict:
    return style("knit", base=base, pattern=pattern, alt=alt, dirt=dirt, blood=blood, torn=torn, **kw)


def leather_style(base=CLOTH["black_leather"], dirt=0.25, blood=0.2, wear=0.5, **kw) -> dict:
    return style("leather", base=base, dirt=dirt, blood=blood, wear=wear, **kw)


def metal_style(base="#8c8f94", dirt=0.3, blood=0.0, wear=0.5, **kw) -> dict:
    return style("metal", base=base, dirt=dirt, blood=blood, wear=wear, **kw)


def painted_metal_style(base, dirt=0.35, wear=0.4, rust=0.5, blood=0.0, **kw) -> dict:
    return style("painted_metal", base=base, dirt=dirt, wear=wear, rust=rust, blood=blood, **kw)


def outfit_palette(kind: str) -> Dict[str, dict]:
    """職業ごとの服のスタイル一式（top / bottom / shoes / extra）。"""
    P = {
        "office": dict(top=cloth_style(CLOTH["white_shirt"], dirt=0.45, blood=0.45),
                       bottom=cloth_style(CLOTH["grey_suit"], "pinstripe", alt="#6a6c72"),
                       shoes=leather_style(CLOTH["black_leather"]),
                       extra=cloth_style("#5a1e22", "stripes", alt="#24262c", dirt=0.2)),
        "police": dict(top=cloth_style(CLOTH["police"], dirt=0.35, blood=0.35),
                       bottom=cloth_style(CLOTH["police"], dirt=0.4),
                       shoes=leather_style(CLOTH["black_leather"]),
                       extra=style("kevlar", base="#26282c", pattern="molle", dirt=0.3, blood=0.2)),
        "medic": dict(top=cloth_style(CLOTH["scrubs_green"], dirt=0.3, blood=0.6),
                      bottom=cloth_style(CLOTH["scrubs_green"], dirt=0.35, blood=0.3),
                      shoes=style("rubber", base="#d8d8d4", dirt=0.5),
                      extra=cloth_style("#e8e6e0", dirt=0.3, blood=0.7)),
        "worker": dict(top=style("hi_vis", base=CLOTH["hi_vis_orange"], dirt=0.55, blood=0.3),
                       bottom=denim_style(dirt=0.6),
                       shoes=leather_style(CLOTH["brown_leather"], dirt=0.6),
                       extra=painted_metal_style("#d8b020", wear=0.5, rust=0.1)),
        "soldier": dict(top=cloth_style(CLOTH["olive_drab"], "camo", alt="#3e4230", alt2="#26281e",
                                        alt3="#7a704e", dirt=0.45, blood=0.35),
                        bottom=cloth_style(CLOTH["olive_drab"], "camo", alt="#3e4230", alt2="#26281e",
                                           alt3="#7a704e", dirt=0.55),
                        shoes=leather_style("#2a241e", dirt=0.6),
                        extra=style("kevlar", base="#4e5238", pattern="molle", dirt=0.4)),
        "casual": dict(top=cloth_style(CLOTH["red_flannel"], "plaid", alt="#2a1612", dirt=0.4, blood=0.4),
                       bottom=denim_style(),
                       shoes=style("rubber", base="#e0ddd6", dirt=0.6),
                       extra=knit_style(CLOTH["beanie_red"])),
        "prisoner": dict(top=cloth_style(CLOTH["prison_orange"], dirt=0.5, blood=0.4),
                         bottom=cloth_style(CLOTH["prison_orange"], dirt=0.55),
                         shoes=style("rubber", base="#d8d6d0", dirt=0.6),
                         extra=style("metal", base="#9a9ca0", wear=0.6)),
        "hazmat": dict(top=style("rubber", base=CLOTH["hazmat_yellow"], dirt=0.5, blood=0.4),
                       bottom=style("rubber", base=CLOTH["hazmat_yellow"], dirt=0.6, blood=0.2),
                       shoes=style("rubber", base="#2a2a2c", dirt=0.6),
                       extra=style("glass", base="#3c4c50")),
    }
    return P[kind]


def zombie_styles(tone, decay=2, eyes="clouded", hair_colour=None, blood=0.1, hair_style="matted",
                  dirt=0.4, life_tone: Optional[int] = None, blood_kind: str = "red") -> Dict[str, dict]:
    """ゾンビの体の stylebook（skin / skin_dark / flesh / cut_flesh / bone / teeth / gums / guts /
    brain / blood / blood_dry / eye / hair / nail）。

    tone: SKINS のキー（nr_spec_zombies の skin）か dict(base, shadow, highlight[, vein, mottle, wet, ...])
    life_tone: 生前の肌色 0..4（spec の tone。SKINS[skin]["tone_mix"] の割合で混ぜる）
    blood_kind: BLOOD_KINDS のキー（spec の gore の blood。red / dark / black / bile / acid / ash / water / ember）
    """
    t = skin_tone(tone, life_tone)
    if isinstance(tone, str) and "decay_tint" not in t:
        t["decay_tint"] = 0.35
    colours = {k: t[k] for k in ("base", "shadow", "highlight") if k in t}
    extras = {k: t[k] for k in _SKIN_EXTRA if k in t}
    decay = float(decay)
    dark = {k: tuple(int(x * 0.8) for x in v) for k, v in colours.items()}
    hair = hair_colour or "#3a3029"
    bk = dict(blood_kind=blood_kind)
    return {
        "skin": style("skin", tone=colours, decay=decay, blood=blood, dirt=dirt, blood_age=0.6, **bk,
                      **extras),
        "skin_dark": style("skin", tone=dark, decay=min(4.0, decay + 1), blood=min(1.0, blood * 1.5),
                           blood_age=0.6,
                           dirt=min(1.0, dirt + 0.2), **bk, **extras),
        "flesh": style("flesh", blood=0.0, wet=0.7, **bk),
        "cut_flesh": style("cut_flesh", tone=colours, bone=True, **bk),
        "bone": style("bone", blood=0.35, dirt=0.2, age=0.3 + 0.1 * decay, **bk),
        "teeth": style("teeth", decay=decay, blood=0.3, **bk),
        "gums": style("gums", blood=0.3, **bk),
        "guts": style("guts", blood=0.4, rot=0.2 + 0.15 * decay, **bk),
        "brain": style("brain", blood=0.3, **bk),
        "blood": style("blood", **bk),
        "blood_dry": style("blood_dry", **bk),
        "eye": style("eye", kind=eyes),
        "hair": style("hair", base=hair, style=hair_style, blood=blood * 0.6, dirt=dirt,
                      skin=colours["base"], **bk),
        "nail": style("nail", dirt=0.5, blood=0.2, blood_age=0.5, **bk),
    }


# ---------------------------------------------------------------------------
#  PNG の書き出し
# ---------------------------------------------------------------------------
def quantize_rgba(img: Image.Image, colors: int = 256) -> Image.Image:
    """アルファ値ごとに別々にパレットを作る量子化（アルファは 1 段も変えない）。

    発光マーカー（EMISSIVE_ALPHA / EMISSIVE_HALO）と 255 と 0 の texel がパレットの別の項目に
    なるので、パレット化しても entity_emissive_alpha の光り方が変わらない。
    """
    a = np.array(img.convert("RGBA"))
    A = a[..., 3]
    rgb = a[..., :3]
    levels = sorted(set(np.unique(A).tolist()))
    counts = {lv: int((A == lv).sum()) for lv in levels}
    budget = colors - (1 if 0 in levels else 0)
    vis = [lv for lv in levels if lv != 0]
    if len(vis) > budget:
        raise ValueError("アルファの段階が多すぎてパレット化できない")
    # アルファ段ごとの色数（画素数に比例、最低 1）
    total = sum(counts[lv] for lv in vis) or 1
    alloc = {lv: max(1, int(budget * counts[lv] / total)) for lv in vis}
    while sum(alloc.values()) > budget:
        big = max(alloc, key=lambda k: alloc[k])
        alloc[big] -= 1
    pal: List[int] = []
    trns: List[int] = []
    index = np.zeros(A.shape, np.uint8)
    nxt = 0
    if 0 in levels:
        pal += [0, 0, 0]
        trns.append(0)
        nxt = 1
    for lv in vis:
        m = A == lv
        px = rgb[m]
        k = min(alloc[lv], len(np.unique(px.view(np.dtype((np.void, 3))))))
        strip = Image.fromarray(px.reshape(1, -1, 3), "RGB")
        q = strip.quantize(colors=max(1, k), method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        sub = q.getpalette()[:3 * max(1, k)]
        idx = np.array(q).reshape(-1)
        used = int(idx.max()) + 1
        pal += sub[:3 * used]
        trns += [lv] * used
        index[m] = (idx + nxt).astype(np.uint8)
        nxt += used
    out = Image.fromarray(index, "P")
    pal += [0, 0, 0] * (256 - len(pal) // 3)
    out.putpalette(pal[:768])
    out.info["transparency"] = bytes(trns)
    return out


def save_png(img: Image.Image, path: str, quantize: bool = False) -> int:
    """PNG を書く。quantize=True ならアルファ段ごとのパレット化（アルファは完全に保つ）。
    パレット化した結果を読み戻してアルファが元と一致しなければ RGBA のまま書く。戻り値はバイト数。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if quantize:
        q = quantize_rgba(img)
        back = np.array(q.convert("RGBA"))[..., 3]
        if np.array_equal(back, np.array(img.convert("RGBA"))[..., 3]):
            q.save(path, optimize=True, transparency=q.info["transparency"])
            return os.path.getsize(path)
    img.save(path, optimize=True)
    return os.path.getsize(path)


# ---------------------------------------------------------------------------
#  自己テスト・見本帳
# ---------------------------------------------------------------------------
def _swatch_styles():
    Z = zombie_styles("pale", 2, "clouded")
    S = []

    def add(label, st):
        S.append((label, st))

    for d in range(5):
        add(f"skin pale d{d}", style("skin", tone="pale", decay=d, blood=0.0, dirt=0.2))
    add("skin tan d2 blood.6", style("skin", tone="tan", decay=2, blood=0.6, dirt=0.3))
    add("skin dark d3", style("skin", tone="dark", decay=3, blood=0.3, dirt=0.3))
    add("skin livid d1 bruise", style("skin", tone="livid", decay=1, bruises=0.9, blood=0.0))
    add("skin jaundiced d4", style("skin", tone="jaundiced", decay=4, blood=0.4))
    add("skin burnt d2 burn.6", style("skin", tone="burnt", decay=2, burn=0.6))
    add("flesh", Z["flesh"])
    add("cut_flesh", Z["cut_flesh"])
    add("bone", Z["bone"])
    add("teeth", Z["teeth"])
    add("gums", Z["gums"])
    add("guts", Z["guts"])
    add("brain", Z["brain"])
    add("blood", Z["blood"])
    add("blood_dry", Z["blood_dry"])
    add("gore_wet", style("gore_wet"))
    for k in ("clouded", "bloodshot", "glowing_yellow", "glowing_red", "none"):
        add("eye " + k, style("eye", kind=k))
    add("hair matted", Z["hair"])
    add("hair long blonde", style("hair", base="#9c8456", style="long", blood=0.2))
    add("hair balding", style("hair", base="#4a4038", style="balding", skin=(170, 160, 146)))
    add("nail", Z["nail"])
    add("cloth plain shirt", cloth_style(CLOTH["white_shirt"], dirt=0.4, blood=0.5))
    add("cloth stripes", cloth_style("#9fb4cc", "stripes", alt="#e0e4e8", blood=0.3))
    add("cloth plaid", cloth_style(CLOTH["red_flannel"], "plaid", alt="#22140f", blood=0.3))
    add("cloth camo", outfit_palette("soldier")["top"])
    add("cloth pinstripe", cloth_style(CLOTH["black_suit"], "pinstripe", alt="#7a7c84", blood=0.3))
    add("cloth print torn", cloth_style("#c98c9a", "print", alt="#f0e0c0", torn=0.7, under=(150, 40, 36)))
    add("denim", denim_style(blood=0.3))
    add("knit", knit_style(CLOTH["beanie_red"], dirt=0.3))
    add("leather", leather_style(CLOTH["brown_leather"], blood=0.3))
    add("rubber", style("rubber", dirt=0.5))
    add("kevlar molle", style("kevlar", pattern="molle", dirt=0.3, blood=0.2))
    add("hi_vis", style("hi_vis", base=CLOTH["hi_vis_yellow"], dirt=0.5, blood=0.3))
    add("metal", metal_style(wear=0.6, dirt=0.3))
    add("rust", style("rust", dirt=0.2))
    add("rust half", style("rust", amount=0.5))
    add("painted_metal", painted_metal_style("#9a2420", wear=0.6, rust=0.6))
    add("chrome", style("chrome"))
    add("plastic", style("plastic", base="#2c4a7a", wear=0.4, dirt=0.3))
    add("wood planks", style("wood", planks=1.5, wear=0.3, dirt=0.2))
    add("concrete", style("concrete", dirt=0.4))
    add("asphalt", style("asphalt"))
    add("glass cracked", style("glass", crack=0.8))
    add("tire", style("tire", dirt=0.5))
    add("fungus glow", style("fungus", glow_spots=0.3))
    add("tumor", style("tumor"))
    add("char embers", style("char", embers=True))
    add("glow uv", style("glow", base="#7a5cff"))
    add("paper", style("paper", blood=0.3))
    add("sign", style("sign", base="#1e5a8c", dirt=0.4))
    add("painted metal bloody", painted_metal_style("#d8d4cc", wear=0.3, rust=0.2, blood=0.7))
    return S


def _decal_swatches():
    sk = style("skin", tone="pale", decay=2, blood=0.15, dirt=0.25)
    D = []
    for eyes, mouth in (("clouded", "snarl"), ("bloodshot", "gaping"), ("glowing_yellow", "torn"),
                        ("glowing_red", "jawless"), ("none", "stitched"), ("clouded", "closed")):
        D.append((f"face {eyes}/{mouth}", sk, {"name": "face", "eyes": eyes, "mouth": mouth,
                                              "decay": 2, "gore": 0.6}))
    D.append(("face d4 gore1", style("skin", tone="grey_green", decay=4, blood=0.3),
              {"name": "face", "eyes": "clouded", "mouth": "gaping", "decay": 4, "gore": 1.0}))
    D.append(("face dark d1", style("skin", tone="brown", decay=1),
              {"name": "face", "eyes": "bloodshot", "mouth": "snarl", "decay": 1, "gore": 0.3}))
    D.append(("wound", sk, {"name": "wound", "size": 0.7}))
    D.append(("bite", sk, {"name": "bite"}))
    D.append(("bullet skin", sk, {"name": "bullet_hole", "size": 0.06}))
    D.append(("bullet metal", painted_metal_style("#3a5a3a"), {"name": "bullet_hole", "size": 0.07}))
    D.append(("bullet glass", style("glass"), {"name": "bullet_hole", "size": 0.06}))
    D.append(("burn skin", sk, {"name": "burn", "size": 0.7}))
    D.append(("burn cloth embers", cloth_style("#5a5e66"), {"name": "burn", "size": 0.7, "embers": True}))
    D.append(("text POLICE", cloth_style(CLOTH["police"]), {"name": "text", "text": "POLICE", "colour": "#e8e4d8"}))
    D.append(("text 24 sign", style("sign", base="#c89a1a", border=(20, 20, 20)),
              [{"name": "text", "text": "24", "colour": "#141414", "wear": 0.1},
               {"name": "bullet_hole", "at": (0.7, 0.3)}]))
    D.append(("stripe hazard", painted_metal_style("#d8b020"), {"name": "stripe", "hazard": True, "width": 0.4}))
    D.append(("stripe x2 refl", cloth_style("#2c2e30"), {"name": "stripe", "count": 2, "colour": "#c8ccc8", "reflective": True}))
    D.append(("badge", cloth_style(CLOTH["police"]), [{"name": "badge", "at": (0.3, 0.35)},
                                                      {"name": "pocket", "box": (0.15, 0.2, 0.45, 0.5)},
                                                      {"name": "buttons", "u": 0.62}]))
    D.append(("grime", painted_metal_style("#d8d4cc"), {"name": "grime", "amount": 0.9}))
    D.append(("stitches", sk, {"name": "stitches"}))
    D.append(("handprint", style("concrete"), {"name": "handprint"}))
    D.append(("drips", style("concrete"), {"name": "drips"}))
    D.append(("glow spot", style("tumor"), {"name": "glow_spot", "colour": "#a0ff60"}))
    return D


_SPEC_SKINS = ("pale", "grey_green", "necrotic_purple", "jaundiced", "charred", "drowned_blue",
               "bloated_pink", "ashen", "flushed", "leathery_brown", "bruised", "nocturnal_grey",
               "shadow_black", "cinder", "fungal_ochre", "raw_flesh", "lab_white")


def _skin_swatches():
    """spec の肌 17 系統（顔のデカール付き）。"""
    eyes = {"nocturnal_grey": "glowing_yellow", "shadow_black": "glowing_red", "cinder": "glowing_red",
            "flushed": "bloodshot", "lab_white": "bloodshot", "raw_flesh": "none"}
    blood = {"charred": "ash", "cinder": "ember", "shadow_black": "black", "nocturnal_grey": "dark",
             "fungal_ochre": "bile", "drowned_blue": "water"}
    out = []
    for i, k in enumerate(_SPEC_SKINS):
        dec = {"necrotic_purple": 3, "charred": 3, "cinder": 3, "raw_flesh": 4, "fungal_ochre": 4,
               "flushed": 1, "lab_white": 1}.get(k, 2)
        Z = zombie_styles(k, dec, eyes.get(k, "clouded"), blood=0.3, life_tone=i % 5,
                          blood_kind=blood.get(k, "red"))
        face = {"name": "face", "eyes": eyes.get(k, "clouded"), "mouth": ("snarl", "gaping", "torn")[i % 3],
                "decay": dec, "gore": 0.4}
        out.append((f"{k} d{dec} t{i % 5}", Z["skin"], face))
    return out


def _eye_swatches():
    """目の全種類（目玉キューブの north 面と、顔デカールの目）。"""
    out = []
    skin = zombie_styles("grey_green", 2, "clouded")["skin"]
    for k in EYES:
        out.append((f"{k} eyeball", style("eye", kind=k), None))
        out.append((f"{k} face", skin, {"name": "face", "eyes": k, "mouth": "closed", "decay": 2,
                                         "gore": 0.0, "eye_v": 0.42, "eye_gap": 0.22}))
    return out


def _build_swatch_model(us=4, cube=8, items=None):
    from mcmodel import Cube, Model
    m = Model("geometry.nr.test.swatches", uv_scale=us, max_atlas=(2048, 2048))
    b = m.bone("root")
    book = {}
    labels = []
    if items is None:
        items = [(lab, st, None) for lab, st in _swatch_styles()] + _decal_swatches()
    for i, (lab, st, dec) in enumerate(items):
        name = f"s{i:03d}"
        book[name] = st
        c = Cube((i % 12 * 10, 0, i // 12 * 10), (cube, cube, cube), style=name)
        if dec is not None:
            c.decals = {"north": dec}
        b.add(c)
        labels.append((lab, c))
    m.pack()
    return m, book, labels


def _iso_tile(atlas: Image.Image, cube, size=132) -> Image.Image:
    """キューブを斜め上から見た絵（up / north / west の 3 面。west が +X の面）を PIL のアフィン変換で作る。"""
    def face(f):
        x, y, w, h = cube.rects[f]
        return atlas.crop((x, y, x + w, y + h)).convert("RGBA")
    tile = Image.new("RGBA", (size, size), (34, 36, 42, 255))
    s = size * 0.42
    cx, cy = size * 0.5, size * 0.52
    # 投影: X 右下、Z 左下、Y 上
    ex = np.array([0.866 * s, 0.5 * s])
    ez = np.array([-0.866 * s, 0.5 * s])
    ey = np.array([0.0, -1.0 * s])
    o = np.array([cx, cy]) - (ex + ez) * 0.5 * 0 - ey * 0.0

    def put(img, P0, Pu, Pv):
        # 画像 (u,v) → 画面: P0 + Pu*u/w + Pv*v/h。逆アフィンを PIL に渡す
        w, h = img.size
        M = np.array([[Pu[0] / w, Pv[0] / h, P0[0]], [Pu[1] / w, Pv[1] / h, P0[1]], [0, 0, 1]])
        inv = np.linalg.inv(M)
        out = img.transform((size, size), Image.AFFINE, tuple(inv[:2].reshape(-1)), Image.NEAREST)
        tile.alpha_composite(out)
    # 立方体の頂点（単位立方体 0..1、原点を中心付近へ）
    def P(x, y, z):
        return o + ex * (x - 0.5) + ez * (z - 0.5) * -1 + ey * (y - 0.5)
    # north 面（Z=0）: u→+X, v→-Y。画面上では手前左に来るよう ez を反転
    put(face("north"), P(0, 1, 0), P(1, 1, 0) - P(0, 1, 0), P(0, 0, 0) - P(0, 1, 0))
    # west 面（X=1。統合版の対応では +X の面は west で u→+Z）
    put(face("west"), P(1, 1, 0), P(1, 1, 1) - P(1, 1, 0), P(1, 0, 0) - P(1, 1, 0))
    # up 面（Y=1）: u→+X, v→-Z
    put(face("up"), P(0, 1, 1), P(1, 1, 1) - P(0, 1, 1), P(0, 1, 0) - P(0, 1, 1))
    return tile


def _swatch_sheet(atlas, labels, path, cols=8, flat_scale=4):
    from PIL import ImageDraw
    tile_w = 132 + 8 * flat_scale + 12
    tile_h = 150
    fw = labels[0][1].rects["north"][2]
    tile_w = 132 + fw * flat_scale + 14
    tile_h = max(150, fw * flat_scale + 22)
    rows = (len(labels) + cols - 1) // cols
    # 光る texel（alpha < 255）も見本では不透明に表示する
    a = np.array(atlas)
    a[..., 3] = np.where(a[..., 3] > 0, 255, 0)
    disp = Image.fromarray(a, "RGBA")
    atlas = disp
    sheet = Image.new("RGB", (cols * tile_w, rows * tile_h), (20, 21, 25))
    dr = ImageDraw.Draw(sheet)
    for i, (lab, cube) in enumerate(labels):
        x = (i % cols) * tile_w
        y = (i // cols) * tile_h
        iso = _iso_tile(disp, cube)
        sheet.paste(iso.convert("RGB"), (x + 2, y + 2))
        fx, fy, fw_, fh_ = cube.rects["north"]
        flat = atlas.crop((fx, fy, fx + fw_, fy + fh_)).resize((fw_ * flat_scale, fh_ * flat_scale), Image.NEAREST)
        sheet.paste(flat.convert("RGB"), (x + 136, y + 2))
        dr.text((x + 4, y + tile_h - 16), lab, fill=(220, 220, 210))
    sheet.save(path)
    return sheet


def _demo_model(kind, seed=7):
    """箱人形のゾンビ（目視用）。kind = 'office' | 'worker'。"""
    from mcmodel import Cube, Model
    if kind == "office":
        Zs = zombie_styles("pale", 2.5, "clouded", hair_colour="#2e2620", blood=0.45)
        Zs.update({"top": cloth_style(CLOTH["white_shirt"], dirt=0.45, blood=0.5, torn=0.35, under=(120, 30, 28)),
                   "bottom": cloth_style(CLOTH["grey_suit"], "pinstripe", alt="#6a6c72", dirt=0.5, blood=0.3, torn=0.3),
                   "tie": cloth_style("#5a1e22", "stripes", alt="#24262c", period=0.6),
                   "shoes": leather_style(CLOTH["black_leather"], dirt=0.5),
                   "hat": style("hair", base="#2e2620", style="matted")})
        face = {"name": "face", "eyes": "clouded", "mouth": "gaping", "decay": 2.5, "gore": 0.8}
    else:
        Zs = zombie_styles("tan", 3.5, "glowing_yellow", hair_colour="#1c1814", blood=0.6, hair_style="short")
        Zs.update({"top": style("hi_vis", base=CLOTH["hi_vis_orange"], dirt=0.6, blood=0.45, torn=0.4, under=(110, 24, 24)),
                   "bottom": denim_style(dirt=0.6, blood=0.35, torn=0.3),
                   "tie": style("kevlar", base="#3a3a36"),
                   "shoes": leather_style(CLOTH["brown_leather"], dirt=0.7),
                   "hat": painted_metal_style("#d8b020", wear=0.6, rust=0.3, dirt=0.4, blood=0.3)})
        face = {"name": "face", "eyes": "glowing_yellow", "mouth": "jawless", "decay": 3.5, "gore": 1.0}
    m = Model("geometry.nr.test.demo_" + kind, uv_scale=4, max_atlas=(512, 512))
    m.bone("root")
    head = m.bone("head", (0, 24, 0), "root")
    head.add(Cube((-4, 24, -4), (8, 8, 8), "skin", decals={"north": face}))
    head.add(Cube((-4.2, 29.5, -4.2), (8.4, 2.8, 8.4), "hat"))
    if kind == "office":
        head.add(Cube((-4.2, 25, 1.5), (8.4, 4.5, 2.7), "hair"))
    body = m.bone("body", (0, 24, 0), "root")
    body.add(Cube((-4, 12, -2), (8, 12, 4), "top", decals={"north": [{"name": "buttons", "u": 0.5},
                                                                     {"name": "wound", "at": (0.3, 0.6), "size": 0.5}],
                                                         "south": {"name": "bite", "at": (0.6, 0.3)}}))
    body.add(Cube((-0.6, 16, -2.3), (1.2, 7, 0.3), "tie"))
    body.add(Cube((-1.5, 13, -2.4), (3, 3, 0.5), "guts"))
    for sx, nm in ((-1, "r"), (1, "l")):
        x0 = 4 if sx > 0 else -8
        arm = m.bone("arm_" + nm, (sx * 5, 22, 0), "body")
        arm.add(Cube((x0, 18, -2), (4, 6, 4), "top"))
        arm.add(Cube((x0, 13, -2), (4, 5, 4), "skin"))
        if nm == "l":
            arm.add(Cube((x0, 10, -2), (4, 3, 4), "skin_dark"))
        leg = m.bone("leg_" + nm, (sx * 2, 12, 0), "root")
        leg.add(Cube((-4 if sx < 0 else 0, 2, -2), (4, 10, 4), "bottom"))
        leg.add(Cube((-4 if sx < 0 else 0, 0, -2.5), (4, 2, 4.5), "shoes"))
    # 右腕は肘の下で切断: 断面と骨
    st = m.bone("stump", (0, 0, 0), "arm_r")
    st.add(Cube((-8, 12.4, -2), (4, 0.6, 4), "cut_flesh"))
    st.add(Cube((-6.6, 11.2, -0.6), (1.2, 1.2, 1.2), "bone"))
    m.pack()
    return m, Zs


def _demo_zombie(out_dir, seed=7):
    """箱人形のゾンビ 2 体を塗って、nr_preview（統合版と同じ面の対応）で描く（目視用）。
    ジオメトリは nr_common.write_geometry（1.16.0）で書く。戻り値は塗りの秒数。"""
    import nr_common
    import nr_preview as V
    tiles = []
    dt = 0.0
    for kind in ("office", "worker"):
        m, Zs = _demo_model(kind, seed)
        t0 = time.time()
        img = paint_model(m, Zs, seed)
        dt += time.time() - t0
        gp = os.path.join(out_dir, f"demo_{kind}.geo.json")
        tp = os.path.join(out_dir, f"demo_{kind}.png")
        nr_common.write_geometry(gp, m)
        img.save(tp)
        for yaw in (-160, 30):
            tiles.append((f"{kind} yaw {yaw}", V.render(m, img, view=(yaw, 6), size=(300, 460))))
        cam = V.Camera(yaw=-22, pitch=4, target=(0, 28, -4), scale=460 * 0.8 / 9.0)
        tiles.append((f"{kind} head", V.render(m, img, camera=cam, size=(300, 460))))
    V.contact_sheet(tiles, cols=6).save(os.path.join(out_dir, "paint_demo_zombie.png"))
    return dt


def _seam_model():
    """継ぎ目の検査用: 大きさの違う箱と、傾いたボーンの上の箱（猫背の胸のように）。"""
    from mcmodel import Cube, Model
    m = Model("geometry.nr.test.seams", uv_scale=4, max_atlas=(512, 512))
    m.bone("root")
    b = m.bone("body", (0, 12, 0), "root")
    b.add(Cube((-4, 12, -2), (8, 8, 4), "skin"))
    b.add(Cube((-6, 2, -3), (5, 10, 6), "skin"))
    b.add(Cube((1, 2, -3), (5, 10, 6), "skin"))
    c = m.bone("chest", (0, 20, 0), "body", [12.0, 0.0, 0.0])
    c.add(Cube((-4.5, 20, -2.5), (9, 7, 5), "skin"))
    c.add(Cube((-1.5, 27, -1.5), (3, 2, 3), "skin", rotation=[0, 0, 20]))
    m.pack()
    return m


def seam_ratio(model, img, styles=("skin",)) -> float:
    """側面の帯の 3 つの角（east|north, north|west, west|south）で、角をまたぐ隣の列の差 ÷ 面の中の
    隣の列の差（全キューブの平均）。模様が角で繋がっていれば 1 に近い（ずれていると 2〜3）。"""
    a = np.asarray(img).astype(np.float32)[..., :3]
    cross, inner = [], []
    for c in model.all_cubes():
        if c.style not in styles:
            continue
        r = c.rects
        for fa, fb in (("east", "north"), ("north", "west"), ("west", "south")):
            ua, va, wa, ha = r[fa]
            ub, vb, wb, hb = r[fb]
            if wa < 3 or wb < 3 or ha < 3 or ha != hb:
                continue
            cross.append(np.abs(a[va:va + ha, ua + wa - 1] - a[vb:vb + hb, ub]).mean())
            inner.append(np.abs(a[va:va + ha, ua + wa - 1] - a[va:va + ha, ua + wa - 2]).mean())
    return float(np.mean(cross) / max(1e-6, np.mean(inner))) if cross else 1.0


def _seam_check(out_dir, seed=3):
    """3D ノイズが箱の角で繋がるか（新しい面の対応）を数値と nr_preview の絵で確かめる。
    比較に、east と west の矩形を入れ替えて塗った（＝旧い向きで塗った）ものも測る。"""
    m = _seam_model()
    st = {"skin": style("skin", tone="grey_green", decay=3, rot=0.45, blood=0.35, blood_age=0.3,
                        dirt=0.2, lesions=0.0)}
    img = paint_model(m, st, seed, face_light=False, ao=False)
    ok = seam_ratio(m, img)
    for c in m.all_cubes():
        c.rects["east"], c.rects["west"] = c.rects["west"], c.rects["east"]
    old = paint_model(m, st, seed, face_light=False, ao=False)
    for c in m.all_cubes():
        c.rects["east"], c.rects["west"] = c.rects["west"], c.rects["east"]
    old_ratio = seam_ratio(m, old)
    try:
        import nr_preview as V
        img2 = paint_model(m, st, seed)
        for c in m.all_cubes():
            c.rects["east"], c.rects["west"] = c.rects["west"], c.rects["east"]
        old2 = paint_model(m, st, seed)
        for c in m.all_cubes():
            c.rects["east"], c.rects["west"] = c.rects["west"], c.rects["east"]
        tiles = []
        for lab, t in (("now (bedrock faces)", img2), ("old east/west", old2)):
            for yaw in (40, -140):
                tiles.append((f"{lab} yaw {yaw}", V.render(m, t, view=(yaw, 18), size=320)))
        V.contact_sheet(tiles, cols=4).save(os.path.join(out_dir, "paint_seams.png"))
    except Exception as e:  # noqa: BLE001  目視用
        print("seam render skipped:", e)
    return ok, old_ratio


def _perf_model(n=400, us=3):
    from mcmodel import Cube, Model
    import random
    rng = random.Random(1234)
    m = Model("geometry.nr.test.perf", uv_scale=us, max_atlas=(512, 512))
    b = m.bone("root")
    names = ["skin", "skin_dark", "flesh", "cut_flesh", "bone", "teeth", "gums", "guts", "brain",
             "blood", "eye", "hair", "nail", "shirt", "pants", "vest", "boots", "metal"]
    for i in range(n):
        sx = rng.choice([1, 1.5, 2, 2, 3, 4])
        sy = rng.choice([1, 2, 3, 4, 6])
        sz = rng.choice([1, 1.5, 2, 3, 4])
        c = Cube((rng.uniform(-8, 8), rng.uniform(0, 30), rng.uniform(-4, 4)), (sx, sy, sz),
                 rng.choice(names))
        if i % 40 == 0:
            c.decals = {"north": {"name": rng.choice(["wound", "bite", "bullet_hole"])}}
        b.add(c)
    m.pack()
    book = zombie_styles("pale", 3, "glowing_yellow", blood=0.6)
    book.update({"shirt": cloth_style("#9fb4cc", "plaid", alt="#334", blood=0.5, torn=0.3),
                 "pants": denim_style(blood=0.3), "vest": style("kevlar", pattern="molle", blood=0.3),
                 "boots": leather_style(dirt=0.6), "metal": metal_style(blood=0.3)})
    return m, book


def _fbm_stats():
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 500, 200000).astype(f32)
    y = rng.uniform(0, 500, 200000).astype(f32)
    z = rng.uniform(0, 500, 200000).astype(f32)
    a = fbm2(x, y, 11, 3)
    b = fbm3(x, y, z, 11, 3)
    return float(a.mean()), float(a.std()), float(b.mean()), float(b.std())


def main():
    from nr_common import SCRATCH
    os.makedirs(SCRATCH, exist_ok=True)
    m2, s2, m3, s3 = _fbm_stats()
    print(f"fbm2 mean {m2:.3f} std {s2:.3f} / fbm3 mean {m3:.3f} std {s3:.3f}")
    # 見本帳
    m, book, labels = _build_swatch_model(us=int(os.environ.get("NR_SWATCH_US", "4")))
    t0 = time.time()
    atlas = paint_model(m, book, seed=1)
    t_sw = time.time() - t0
    atlas.save(os.path.join(SCRATCH, "paint_swatch_atlas.png"))
    _swatch_sheet(atlas, labels, os.path.join(SCRATCH, "paint_swatches.png"))
    print(f"swatches: {len(labels)} cubes, atlas {m.tex_w}x{m.tex_h}, {t_sw:.2f}s")
    # 肌の 17 系統
    m_sk, book_sk, labels_sk = _build_swatch_model(us=4, items=_skin_swatches())
    atlas_sk = paint_model(m_sk, book_sk, seed=2)
    _swatch_sheet(atlas_sk, labels_sk, os.path.join(SCRATCH, "paint_skins.png"), cols=6)
    qk = os.path.join(SCRATCH, "paint_skins_atlas_pal.png")
    nq = save_png(atlas_sk, qk, quantize=True)
    al_src = np.array(atlas_sk)[..., 3]
    al_back = np.array(Image.open(qk).convert("RGBA"))[..., 3]
    print(f"skins atlas alpha levels {sorted(set(np.unique(al_src).tolist()))}, paletted {nq / 1024:.0f} KiB, "
          f"alpha exact={np.array_equal(al_src, al_back)}")
    # 低密度の見本（uv_scale 2）
    m_lo, book_lo, labels_lo = _build_swatch_model(us=2)
    atlas_lo = paint_model(m_lo, book_lo, seed=1)
    _swatch_sheet(atlas_lo, labels_lo, os.path.join(SCRATCH, "paint_swatches_x2.png"), flat_scale=8)
    # 目の種類（spec の EYES_VOCAB と同じか・光る目だけが発光 texel を持つか）
    try:
        import nr_spec_zombies as SZ
        vocab = SZ.EYES_VOCAB
        same = set(vocab) == set(EYES) and all(
            all((EYES[k][f] is None) if vocab[k][f] is None else tuple(EYES[k][f]) == tuple(vocab[k][f])
                for f in ("sclera", "iris", "pupil", "glow")) for k in vocab)
        print("eyes match nr_spec_zombies.EYES_VOCAB:", "OK" if same else "NG")
        assert same, "nr_paint.EYES が spec の EYES_VOCAB と食い違う"
    except ImportError:
        pass
    m_e, book_e, labels_e = _build_swatch_model(us=12, items=_eye_swatches())
    atlas_e = paint_model(m_e, book_e, seed=4)
    _swatch_sheet(atlas_e, labels_e, os.path.join(SCRATCH, "paint_eyes.png"), cols=5)
    ae = np.asarray(atlas_e)[..., 3]
    for lab, c in labels_e:
        u, v, w, h = c.rects["north"]
        glowing = bool((ae[v:v + h, u:u + w] < 255).any() & (ae[v:v + h, u:u + w] > 0).any())
        want = EYES.get(lab.split()[0], {}).get("glow") is not None
        assert glowing == want, f"目 {lab}: 発光 {glowing} != {want}"
    print(f"eyes: {len(EYES)} kinds (eyeball + face) painted, emissive only on glowing_* OK")
    # 継ぎ目（側面の角で 3D の模様が繋がるか）
    ratio, old_ratio = _seam_check(SCRATCH)
    print(f"seams: across-edge / in-face column difference {ratio:.2f} (old east/west order {old_ratio:.2f})"
          f" {'OK' if ratio < 1.4 else 'NG'} -> {os.path.join(SCRATCH, 'paint_seams.png')}")
    assert ratio < 1.4, "箱の角で模様が切れている（面の向きを確かめる）"
    # デモのゾンビ
    try:
        dt = _demo_zombie(SCRATCH)
        print(f"demo zombie painted in {dt:.2f}s -> {os.path.join(SCRATCH, 'paint_demo_zombie.png')}")
    except Exception as e:      # 目視用なので失敗しても本体のテストは続ける
        print("demo zombie skipped:", e)
    # 性能: 512x512 / 約 400 キューブ
    pm, pbook = _perf_model()
    best = 1e9
    for r in range(3):
        t0 = time.time()
        img = paint_model(pm, pbook, seed=r)
        best = min(best, time.time() - t0)
    print(f"timing: {len(pm.all_cubes())} cubes, {pm.tex_w}x{pm.tex_h} atlas painted in {best:.2f}s "
          f"(budget 3.0s) {'OK' if best < 3.0 else 'OVER'}")
    # 決定性
    a1 = np.array(paint_model(pm, pbook, seed=5))
    a2 = np.array(paint_model(pm, pbook, seed=5))
    assert np.array_equal(a1, a2), "同じ入力から違う画像が出た"
    # アルファの約束
    al = a1[..., 3]
    ok_alpha = set(np.unique(al).tolist()) <= {0, EMISSIVE_ALPHA, EMISSIVE_HALO, 255}
    print("alpha values:", sorted(set(np.unique(al).tolist())), "OK" if ok_alpha else "NG")
    # パレット化
    pr = os.path.join(SCRATCH, "paint_perf_rgba.png")
    pq = os.path.join(SCRATCH, "paint_perf_pal.png")
    n_rgba = save_png(img, pr, quantize=False)
    n_pal = save_png(img, pq, quantize=True)
    back = np.array(Image.open(pq).convert("RGBA"))
    same_alpha = np.array_equal(back[..., 3], np.array(img)[..., 3])
    err = np.abs(back[..., :3].astype(int) - np.array(img)[..., :3].astype(int))[np.array(img)[..., 3] > 0]
    print(f"png: RGBA {n_rgba / 1024:.0f} KiB -> paletted {n_pal / 1024:.0f} KiB "
          f"({100 * n_pal / max(1, n_rgba):.0f}%), alpha exact={same_alpha}, "
          f"mean abs colour error {err.mean():.2f}")
    print("wrote", os.path.join(SCRATCH, "paint_swatches.png"))


if __name__ == "__main__":
    main()
