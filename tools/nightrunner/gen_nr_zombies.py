# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビ 50 体の見た目（DESIGN.md §1 の `gen_nr_zombies`）。

約束事は DESIGN.md §2（ID）・§3（ボーン・プロパティ）・§5（gib）・§11（上限）・§12（当たり箱）・§13（描画）、
根拠は reference/rendering.md §1〜§3・§6 と §11 のチェックリスト（G1〜G7・R1〜R8・M1〜M6）。

■ 書くもの（このファイルが持ち主。下のフォルダの中は全部この生成器のもの）

| 書くもの | 場所 |
|---|---|
| ゾンビのジオメトリ `geometry.nr.z.<key>`（1.16.0。nr_common.geometry_doc を字下げ無しで。write_geo） | RP `models/entity/nr/zombies/<key>.geo.json` |
| ゾンビのテクスチャ（nr_paint で塗る。アルファが完全に保てる時だけパレット化） | RP `textures/nr/zombies/<key>.png` |
| ちぎれた部位 `geometry.nr.gib.<key>`（nr_rig.extract_gibs。本体と同じテクスチャ） | RP `models/entity/nr/gibs/<key>.geo.json` |
| 汎用の肉片 `geometry.nr.gib.generic` とそのテクスチャ | RP `models/entity/nr/gibs/generic.geo.json`、`textures/nr/gibs/generic.png` |
| レンダーコントローラ `controller.render.nr.zombie`（＋合わせられない種類の `controller.render.nr.z.<key>`）・`controller.render.nr.gib` | RP `render_controllers/nr_zombie.render_controllers.json` |
| 部位の当たり箱とロケータ `SHAPES[key] = {height, width, stand, lie, prone, locators}`（DESIGN §12） | BP `scripts/data/zombie_shapes.js` |
| gen_nr_entities 用の一覧（zombie_assets の中身を全部） | `tools/nightrunner/.cache/zombie_assets.json` |
| 種類ごとのキャッシュ（内容のハッシュが同じなら作り直さない） | `tools/nightrunner/.cache/zombies/<key>.json` |
| 確認画像（NR_PREVIEW=1 か --sheet） | `build_preview/nightrunner/zombies/sheet_<n>.png`（前・後ろ 8 体）、`gore_<n>.png`（ゴア 4 状態 × 6 体） |

■ 1 体の作り方（ztype = nr_spec.ZOMBIES の並び）
1. `nr_kit.build_zombie(z)` → (model, stylebook, info)。アトラスは kit が詰め済み（512²、ボス 1024²）。
2. `nr_paint.paint_model(model, book, seed=crc32("nr.z.<key>"))`。α=0 の画素は RGB も 0 にする（M2）。
   0<α<255 の画素（光る目・光る血・燠火…）が 1 つでもあれば `entity_emissive_alpha`、無ければ `entity_alphatest`
   （光る画素を alphatest で描くと穴になる。rendering.md §3.2）。α の段は {0, 255} と 3〜40 だけ（M3、自己検査）。
3. visible_bounds は G5: 立ち姿の高さ H（ブロック）から幅 2H+1・高さ H+1.5・offset [0, H/2+0.25, 0]
   （寝た姿勢・這う姿勢を含む。0.25 刻みで切り上げ）。gib は部位の外接球の半径 R から幅 2R+1.5。
4. 当たり箱は `nr_kit.hitboxes(model)`（nr_rig.hitboxes から触手・刺さった棒などの nr_nohit を除く）。
   DESIGN §12 の r/u/f（r = -x、u = y、f = -z、ブロック）。hitloc.js が読む形 {height, width, stand, lie, prone,
   locators}（stand / lie / prone は {部位: [{c, h}, ...]}、部位 = head torso arm_r arm_l leg_r leg_l）。

■ レンダーコントローラ（rendering.md §1.3・§2・R1〜R8）
* `controller.render.nr.zombie`: Geometry.default / Material.default / Texture.default。part_visibility は
  `nr_kit.visibility_rules(model, z)`（nr_rig の §3 の規則と armor_* に、spec の gore.breakables（nr:armor >= 段階）と
  変異・特注の明滅・能力の段階の項を足し、**全ボーンについて自分と全祖先の条件を AND** したもの）を 50 体ぶん合わせる。
  合わせ方は gen_nr_entities の VisMerge と同じ（同じ名前のボーンの式が種類で違えば — 片方が「規則なし = いつも表示」
  も違いに数える — その種類だけ専用の `controller.render.nr.z.<key>`）。最後に `nr_rig.merge_visibility` でも検査する。
  焼け（nr:burn 1..3 で黒く寄せる）と感電（nr:shock で青白く明滅）は overlay_color（R8）、被ダメージは is_hurt_color。
* **大きさの判断**: 50 体の和集合は 98 行・式の合計 ≈ 8.4 KB、ファイル 18 KB（2026-10 の計測。実行のたびに表に出す）。
  1 体のジオメトリは 36〜48 ボーン（規則を持つのは 31〜43）。rendering.md §2.3 の目安（150 行）より小さく、名前の衝突も 0
  なので **1 本の共有コントローラ**にした（区分ごとに分けても 1 本の行は 98 → 33〜65 に減るだけ。ジオメトリに
  無いボーンの行の式をエンジンが評価するかは未計測 ❓）。行数が 150 を超えたら警告を出すので、その時は
  plan_render_controllers を区分ごとに回す（client entity の RC の ID は zombie_assets の render_controller で渡る）。
* `controller.render.nr.gib`: `nr:ztype`（0..49 = 種類、50 以上 = 汎用）と `nr:part`（0..10 = 種類の部位、11..15 =
  汎用の肉片）で選ぶ。配列の添字は折り返す（max(0, i) % 長さ）ので、範囲外は三項演算子で先に分ける（R5）:
  `(q.property('nr:part') > 10 || q.property('nr:ztype') >= 50) ? Geometry.generic : Array.geos[q.property('nr:ztype')]`。
  名前は gen_nr_entities の `nr:gib` の client entity と合わせる（Geometry/Texture.z_<key>・.generic、
  Material.default / .generic）。part_visibility は p_* の 1 本だけ（`nr_rig.gib_visibility_rules()`）。
  gib のジオメトリは部位ごとに 1 本のボーンへ焼き込んであるので、子へ伝わらない問題は無い。
* client entity は gen_nr_entities が書く。透明化（shadow_cloak）の種類の `controller.render.nr.zombie_cloak` と
  飛び道具の RC も gen_nr_entities（このファイルの RC は `owned_render_controllers()` で教える）。

■ gen_nr_entities への API（キャッシュの JSON を読むだけ。重い import はしない）
* `zombie_assets(key)` → {geometry, gib_geometry, texture, gib_texture, material, atlas, visible_bounds,
  visibility, bones, render_controller, cubes, gib_cubes, emissive, ztype, cls}
* `gib_generic_assets()` → {geometry, texture}
* `render_controller_of(key)` / `owned_render_controllers()`（このファイルが書いた RC の ID。二重定義を避けるため
  gen_nr_entities はこれを書かない）
* まだ一度も走っていなければ FileNotFoundError（gen_nr_entities は命名規則で続ける）。

■ 速さ: 内容のハッシュ（spec の 1 体の項目 + 作るのに使うモジュールのソース + この生成器の組み立て関数のソース）が
  キャッシュと同じで、書いたファイルも消えたり変わったりしていなければ、その種類は作り直さない。
  作り直す種類はプロセスを並べて（-j、既定 CPU 数）組み立て・塗り。全部作り直しても 4 コアで 30 秒ほど。

使い方:
    python3 tools/nightrunner/gen_nr_zombies.py                # 全部（キャッシュが合う種類は飛ばす）
    python3 tools/nightrunner/gen_nr_zombies.py --force        # 全部作り直す
    python3 tools/nightrunner/gen_nr_zombies.py --only volatile,bride   # その種類だけ作り直す（RC・当たり箱は全種類で書く）
    python3 tools/nightrunner/gen_nr_zombies.py --sheet        # + 確認画像（NR_PREVIEW=1 でも）
    python3 tools/nightrunner/gen_nr_zombies.py --check        # 書いたファイルの自己検査だけ
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import math
import multiprocessing as mp
import os
import sys
import time
import traceback
import zlib
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
for _p in (TOOLS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nr_common as C  # noqa: E402
from nr_common import RP, SCRATCH, load_json, write_json  # noqa: E402
import nr_rig as R  # noqa: E402
import nr_spec as S  # noqa: E402

PRODUCER = "gen_nr_zombies"
ASSET_VERSION = 1            # キャッシュの形を変えたら上げる

# ---- 出力の置き場所（全部この生成器のもの） ----
GEO_DIR = os.path.join(RP, "models", "entity", "nr", "zombies")
GIB_DIR = os.path.join(RP, "models", "entity", "nr", "gibs")
TEX_DIR = os.path.join(RP, "textures", "nr", "zombies")
GIB_TEX_DIR = os.path.join(RP, "textures", "nr", "gibs")
RC_PATH = os.path.join(RP, "render_controllers", "nr_zombie.render_controllers.json")
SHAPES_JS = "zombie_shapes"                      # scripts/data/zombie_shapes.js
CACHE_ROOT = os.path.join(HERE, ".cache")
CACHE_DIR = os.path.join(CACHE_ROOT, "zombies")
ASSETS_JSON = os.path.join(CACHE_ROOT, "zombie_assets.json")
SHEET_DIR = os.path.join(SCRATCH, "zombies")

# ---- ID ----
RC_ZOMBIE = "controller.render.nr.zombie"
RC_GIB = "controller.render.nr.gib"
RC_FORMAT = "1.10.0"
GIB_GENERIC_KEY = "generic"
GIB_GENERIC_GEO = "geometry.nr.gib.generic"
GIB_GENERIC_TEX = "textures/nr/gibs/generic"
MAT_ALPHATEST = "entity_alphatest"
MAT_EMISSIVE = "entity_emissive_alpha"
EMISSIVE_ALPHA_RANGE = (3, 40)                   # M3: 光る画素の α
RC_ROWS_WARN = 150                               # rendering.md §2.3 の目安

# 作るのに使うモジュール（中身が変わったら全種類を作り直す）
CODE_FILES = ("nr_kit.py", "nr_kit_mut.py", "nr_kit_outfit.py", "nr_rig.py", "nr_paint.py", "nr_common.py",
              "nr_spec.py", "nr_spec_zombies.py", os.path.join("..", "mcmodel.py"), os.path.join("..", "rig.py"))


def warn(msg: str) -> None:
    print(f"[{PRODUCER}] WARNING: {msg}", flush=True)


def ztype_of(key: str) -> int:
    for i, z in enumerate(S.ZOMBIES):
        if z["key"] == key:
            return i
    raise KeyError(key)


def paint_seed(key: str) -> int:
    return zlib.crc32(f"nr.z.{key}".encode("utf-8"))


def _rel(path: str) -> str:
    return os.path.relpath(path, C.ROOT)


def _sha(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        h.update(fh.read())
    return h.hexdigest()


def _paths(key: str) -> Dict[str, str]:
    return {"geo": os.path.join(GEO_DIR, f"{key}.geo.json"),
            "gib": os.path.join(GIB_DIR, f"{key}.geo.json"),
            "tex": os.path.join(TEX_DIR, f"{key}.png")}


# ===========================================================================
#  1. 1 体を作る（プロセスの中で走る）
# ===========================================================================
def _alpha_clean(arr):
    """RGBA の配列 → (直した配列, {α: 画素数}, RGB を 0 に直した画素数)。α=0 の画素は RGB も 0（M2）。"""
    import numpy as np
    a = arr[..., 3]
    zero = a == 0
    fixed = int((arr[zero][:, :3] != 0).any(axis=1).sum()) if zero.any() else 0
    arr[zero] = 0
    vals, counts = np.unique(a, return_counts=True)
    return arr, {int(v): int(c) for v, c in zip(vals, counts)}, fixed


def _body_bounds(height: float) -> dict:
    """G5: 寝た姿勢も入る visible_bounds（ブロック）。"""
    H = max(0.5, float(height))
    w = math.ceil((2.0 * H + 1.0) * 4.0) / 4.0
    h = math.ceil((H + 1.5) * 4.0) / 4.0
    return {"width": w, "height": h, "offset": [0, round(H / 2.0 + 0.25, 3), 0]}


def _gib_bounds(gib) -> dict:
    """gib: 原点（部位の重心）からいちばん遠い角の距離 R（ブロック）で、空中で回っても寝ても入る箱。"""
    import numpy as np
    r = 0.0
    for c in gib.all_cubes():
        P = (R.cube_matrix(c) @ R.cube_corners(c).T).T[:, :3]
        r = max(r, float(np.linalg.norm(P, axis=1).max()))
    rb = r / 16.0
    w = max(2.5, math.ceil((2.0 * rb + 1.5) * 4.0) / 4.0)
    return {"width": w, "height": w, "offset": [0, round(rb / 2.0, 3), 0]}


def _set_bounds(model, vb: dict) -> None:
    model.visible_bounds = (vb["width"], vb["height"])
    model.vb_offset = tuple(vb["offset"])


def write_geo(path: str, *models) -> None:
    """nr_common.write_geometry と同じ中身（nr_common.geometry_doc = 1.16.0）を字下げ無しで書く。
    字下げ付きだと 1 体 ≈ 650 KB × 100 ファイルでパックの上限 80 MB（DESIGN §11）を超える（詰めると約 1/5）。"""
    doc = C.geometry_doc(*models)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")


def _build_one(job: Tuple[str, str]) -> dict:
    """(key, ハッシュ) → キャッシュの記録。ファイルを書く。失敗は {"key", "error"} で返す（他の種類は続ける）。"""
    key, zhash = job
    try:
        import numpy as np
        from PIL import Image
        import nr_kit as K
        import nr_paint as P
        t0 = time.perf_counter()
        z = S.ZOMBIE_BY_KEY[key]
        model, book, info = K.build_zombie(z)
        t_build = time.perf_counter() - t0
        img = P.paint_model(model, book, seed=paint_seed(key))
        arr, levels, fixed = _alpha_clean(np.asarray(img.convert("RGBA"), np.uint8).copy())
        t_paint = time.perf_counter() - t0 - t_build
        emissive_px = sum(c for lv, c in levels.items() if 0 < lv < 255)
        material = MAT_EMISSIVE if emissive_px else MAT_ALPHATEST
        shapes = K.hitboxes(model)
        vb = _body_bounds(shapes["height"])
        _set_bounds(model, vb)
        gib = R.extract_gibs(model, key)
        gvb = _gib_bounds(gib)
        _set_bounds(gib, gvb)
        paths = _paths(key)
        write_geo(paths["geo"], model)
        write_geo(paths["gib"], gib)
        nbytes = P.save_png(Image.fromarray(arr, "RGBA"), paths["tex"], quantize=True)
        with Image.open(paths["tex"]) as im:
            png_mode = im.mode
        gib_info = {p: {k: v for k, v in d.items() if k in ("half", "src", "cubes")}
                    for p, d in getattr(gib, "gib_info", {}).items()}
        return {
            "version": ASSET_VERSION, "hash": zhash, "key": key, "ztype": ztype_of(key), "cls": z["cls"],
            "cubes": info["cubes"], "cap": info["cap"], "atlas": [model.tex_w, model.tex_h],
            "texel": info["texel"], "detail": info["detail"], "scale": info["scale"],
            "kit_warnings": list(info["warnings"]), "kit_emissive": bool(info["emissive"]),
            "material": material, "emissive_px": emissive_px, "alpha_levels": levels, "alpha_fixed": fixed,
            "png_bytes": nbytes, "png_mode": png_mode,
            "visibility": [[b, e] for b, e in info["visibility"]],
            "bones": [[b.name, b.parent] for b in model.bones],
            "shapes": {k: shapes[k] for k in ("height", "width", "depth", "stand", "lie", "prone", "locators")},
            "visible_bounds": vb,
            "gib": {"cubes": len(gib.all_cubes()), "visible_bounds": gvb, "info": gib_info},
            "sha": {k: _sha(p) for k, p in paths.items()},
            "seconds": {"build": round(t_build, 3), "paint": round(t_paint, 3),
                        "total": round(time.perf_counter() - t0, 3)},
        }
    except Exception as exc:  # noqa: BLE001  1 体の失敗で全部を止めない（最後に失敗で終わる）
        return {"key": key, "error": f"{type(exc).__name__}: {exc}", "trace": traceback.format_exc()}


# 組み立ての中身（このソースもハッシュに入れる。確認画像・RC の書き方を変えても作り直さない）
_BUILD_FUNCS = (_alpha_clean, _body_bounds, _gib_bounds, _set_bounds, write_geo, _build_one, paint_seed)


def code_hash() -> str:
    h = hashlib.sha256()
    h.update(f"v{ASSET_VERSION}".encode())
    for rel in CODE_FILES:
        p = os.path.normpath(os.path.join(HERE, rel))
        h.update(rel.encode())
        h.update(open(p, "rb").read() if os.path.exists(p) else b"<missing>")
    for fn in _BUILD_FUNCS:
        h.update(inspect.getsource(fn).encode("utf-8"))
    return h.hexdigest()


def zombie_hash(z: dict, code: str) -> str:
    h = hashlib.sha256()
    h.update(code.encode())
    h.update(json.dumps(z, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))
    return h.hexdigest()[:32]


def _cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def load_cached(key: str, zhash: Optional[str] = None) -> Optional[dict]:
    """キャッシュの記録。zhash を渡すと、ハッシュが同じで書いたファイルも元のままの時だけ返す。"""
    p = _cache_path(key)
    if not os.path.exists(p):
        return None
    try:
        rec = load_json(p)
    except Exception:  # noqa: BLE001  壊れたキャッシュは作り直す
        return None
    if rec.get("version") != ASSET_VERSION or "error" in rec:
        return None
    if zhash is not None:
        if rec.get("hash") != zhash:
            return None
        for k, path in _paths(key).items():
            if _sha(path) != (rec.get("sha") or {}).get(k):
                return None
    return rec


def build_all(force_keys: Sequence[str] = (), force: bool = False, jobs: int = 0) -> Tuple[List[dict], List[dict]]:
    """全種類の記録（ztype の順）と失敗の一覧。キャッシュが合う種類は作り直さない。"""
    code = code_hash()
    recs: Dict[str, dict] = {}
    todo: List[Tuple[str, str]] = []
    for z in S.ZOMBIES:
        h = zombie_hash(z, code)
        rec = None if (force or z["key"] in force_keys) else load_cached(z["key"], h)
        if rec is not None:
            rec["cached"] = True
            rec["ztype"] = ztype_of(z["key"])         # 並びが変わっても見た目は同じなので作り直さない
            recs[z["key"]] = rec
        else:
            todo.append((z["key"], h))
    fails: List[dict] = []
    if todo:
        # 重い（ボス・特殊）種類から投げると並びの最後で待たない
        weight = {"boss": 0, "special": 1, "night": 1}
        todo.sort(key=lambda kh: (weight.get(S.ZOMBIE_BY_KEY[kh[0]]["cls"], 2), ztype_of(kh[0])))
        n = max(1, min(jobs or os.cpu_count() or 1, len(todo)))
        os.makedirs(CACHE_DIR, exist_ok=True)
        results = []
        if n == 1:
            results = [_build_one(j) for j in todo]
        else:
            with ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("fork")) as ex:
                futs = [ex.submit(_build_one, j) for j in todo]
                for f in as_completed(futs):
                    results.append(f.result())
        for rec in results:
            if "error" in rec:
                fails.append(rec)
                old = load_cached(rec["key"])
                if old is not None and all(os.path.exists(p) for p in _paths(rec["key"]).values()):
                    warn(f"{rec['key']}: 作り直しに失敗したので前の版（キャッシュ）を使う")
                    old["cached"] = True
                    old["stale"] = True
                    recs[rec["key"]] = old
                continue
            write_json(_cache_path(rec["key"]), rec)
            rec["cached"] = False
            recs[rec["key"]] = rec
    ordered = [recs[z["key"]] for z in S.ZOMBIES if z["key"] in recs]
    return ordered, fails


# ===========================================================================
#  2. 汎用の肉片
# ===========================================================================
def write_generic_gibs() -> dict:
    import numpy as np
    from PIL import Image
    import nr_paint as P
    m = R.build_generic_gibs(paint=True)
    if m.texture is None:
        raise RuntimeError("nr_rig.build_generic_gibs が塗れなかった（nr_paint が import できない）")
    arr, levels, _fixed = _alpha_clean(np.asarray(m.texture.convert("RGBA"), np.uint8).copy())
    path_geo = os.path.join(GIB_DIR, f"{GIB_GENERIC_KEY}.geo.json")
    path_tex = os.path.join(RP, GIB_GENERIC_TEX + ".png")
    write_geo(path_geo, m)
    nbytes = P.save_png(Image.fromarray(arr, "RGBA"), path_tex, quantize=True)
    emissive = sum(c for lv, c in levels.items() if 0 < lv < 255)
    return {"geometry": GIB_GENERIC_GEO, "texture": GIB_GENERIC_TEX, "atlas": [m.tex_w, m.tex_h],
            "cubes": len(m.all_cubes()), "png_bytes": nbytes, "emissive_px": emissive,
            "material": MAT_EMISSIVE if emissive else MAT_ALPHATEST, "alpha_levels": levels}


# ===========================================================================
#  3. レンダーコントローラ
# ===========================================================================
def _rules_and_bones(rec: dict) -> Tuple[List[Tuple[str, str]], List[str]]:
    return [(b, e) for b, e in rec["visibility"]], [n for n, _p in rec["bones"]]


def plan_render_controllers(recs: Sequence[dict]):
    """(共有の規則, {key: RC の ID}, {専用 RC: 規則})。gen_nr_entities の VisMerge と同じ合わせ方:
    同じ名前のボーンの式が違えば（規則なし = いつも表示、も 1 つの式に数える）、その種類は専用の RC。"""
    expr: Dict[str, Optional[str]] = {}
    order: List[str] = []
    rc_of: Dict[str, str] = {}
    own: Dict[str, List[Tuple[str, str]]] = {}
    for rec in recs:
        rules, bones = _rules_and_bones(rec)
        r = dict(rules)
        mine = [(b, r.get(b)) for b in bones] + [(b, e) for b, e in rules if b not in set(bones)]
        clash = sorted({b for b, e in mine if b in expr and expr[b] != e})
        if clash:
            rid = f"controller.render.nr.z.{rec['key']}"
            own[rid] = rules
            rc_of[rec["key"]] = rid
            warn(f"{rec['key']}: ボーン {', '.join(clash[:4])} の表示の式が他の種類と違うので専用の {rid}")
            continue
        for b, e in mine:
            if b not in expr:
                expr[b] = e
                order.append(b)
        rc_of[rec["key"]] = RC_ZOMBIE
    shared = [(b, expr[b]) for b in order if expr[b] is not None]
    # 規則だけの合わせ方（nr_rig.merge_visibility）でも衝突しないこと
    R.merge_visibility(*[_rules_and_bones(rec)[0] for rec in recs if rc_of[rec["key"]] == RC_ZOMBIE])
    return shared, rc_of, own


def overlay_color() -> dict:
    """焼け（nr:burn 1..3 で黒く寄せる）・感電（nr:shock で青白く明滅）。それ以外は this（既定のまま）。R8。"""
    shock = "q.property('nr:shock') > 0"
    burn = "q.property('nr:burn') > 0"
    return {
        "r": f"{shock} ? 0.62 : ({burn} ? 0.06 : this)",
        "g": f"{shock} ? 0.82 : ({burn} ? 0.05 : this)",
        "b": f"{shock} ? 1.0 : ({burn} ? 0.04 : this)",
        "a": f"{shock} ? (math.sin(q.life_time * 2400.0) > 0.0 ? 0.55 : 0.12) : "
             f"({burn} ? q.property('nr:burn') * 0.22 : this)",
    }


def hurt_color() -> dict:
    """被ダメージの点滅（暗い血の赤）。"""
    return {"r": 0.72, "g": 0.04, "b": 0.03, "a": 0.55}


def zombie_rc(rules: Sequence[Tuple[str, str]]) -> dict:
    return {
        "geometry": "Geometry.default",
        "materials": [{"*": "Material.default"}],
        "textures": ["Texture.default"],
        "part_visibility": R.part_visibility(rules),
        "overlay_color": overlay_color(),
        "is_hurt_color": hurt_color(),
    }


def gib_rc(keys: Sequence[str]) -> dict:
    """R5: 範囲外（nr:ztype >= 種類の数・汎用の部位）は三項演算子で先に分けてから配列を引く。"""
    last_type_part = len(R.GIB_TYPE_PARTS) - 1
    generic = f"(q.property('nr:part') > {last_type_part} || q.property('nr:ztype') >= {len(keys)})"
    idx = "q.property('nr:ztype')"
    return {
        "arrays": {
            "geometries": {"Array.geos": [f"Geometry.z_{k}" for k in keys]},
            "textures": {"Array.skins": [f"Texture.z_{k}" for k in keys]},
        },
        "geometry": f"{generic} ? Geometry.generic : Array.geos[{idx}]",
        "materials": [{"*": f"{generic} ? Material.generic : Material.default"}],
        "textures": [f"{generic} ? Texture.generic : Array.skins[{idx}]"],
        "part_visibility": R.part_visibility(R.gib_visibility_rules()),
    }


def write_render_controllers(recs: Sequence[dict]) -> dict:
    shared, rc_of, own = plan_render_controllers(recs)
    rcs = {RC_ZOMBIE: zombie_rc(shared)}
    for rid, rules in own.items():
        rcs[rid] = zombie_rc(rules)
    rcs[RC_GIB] = gib_rc([z["key"] for z in S.ZOMBIES])
    write_json(RC_PATH, {"format_version": RC_FORMAT, "render_controllers": rcs})
    pv = rcs[RC_ZOMBIE]["part_visibility"]
    stats = {"shared_rows": len(shared), "own": len(own),
             "shared_chars": sum(len(k) + len(str(v)) for d in pv for k, v in d.items()),
             "file_kb": round(os.path.getsize(RC_PATH) / 1024, 1)}
    if len(shared) > RC_ROWS_WARN:
        warn(f"{RC_ZOMBIE} の part_visibility が {len(shared)} 行（目安 {RC_ROWS_WARN}）: 区分ごとの RC を考える")
    return {"rc_of": rc_of, "ids": sorted(rcs), "stats": stats}


# ===========================================================================
#  4. 当たり箱（scripts/data/zombie_shapes.js）と gen_nr_entities 用の一覧
# ===========================================================================
SHAPE_FIELDS = ("height", "width", "stand", "lie", "prone", "locators")


def write_shapes(recs: Sequence[dict]) -> int:
    shapes = {rec["key"]: {k: rec["shapes"][k] for k in SHAPE_FIELDS} for rec in recs}
    C.write_data_js(SHAPES_JS, {"SHAPES": shapes}, header=(
        "gen_nr_zombies: 部位の当たり箱とロケータ（DESIGN §12）。SHAPES[key] = {height, width, stand, lie, prone, locators}。\n"
        "箱は {c: [r, u, f], h: [hr, hu, hf]}（中心と半分の大きさ、ブロック）。r = ゾンビの右、u = 上、f = 前。\n"
        "stand = 立ち、lie = 仰向け（頭が -f）、prone = うつ伏せの這い（頭が +f）。部位 = head torso arm_r arm_l leg_r leg_l\n"
        "（2 箱の部位は [上, 下]）。locators は立ち姿勢の [r, u, f]。"))
    return len(shapes)


def asset_entry(rec: dict, rc_id: str) -> dict:
    key = rec["key"]
    return {
        "key": key, "ztype": rec["ztype"], "cls": rec["cls"],
        "geometry": f"geometry.nr.z.{key}", "gib_geometry": f"geometry.nr.gib.{key}",
        "texture": f"textures/nr/zombies/{key}", "gib_texture": f"textures/nr/zombies/{key}",
        "material": rec["material"], "atlas": list(rec["atlas"]), "visible_bounds": rec["visible_bounds"],
        "visibility": [list(x) for x in rec["visibility"]], "bones": [n for n, _p in rec["bones"]],
        "render_controller": rc_id, "cubes": rec["cubes"], "gib_cubes": rec["gib"]["cubes"],
        "emissive": rec["emissive_px"] > 0,
    }


def write_assets_json(recs: Sequence[dict], rc: dict, generic: dict) -> None:
    doc = {
        "version": ASSET_VERSION,
        "zombies": {rec["key"]: asset_entry(rec, rc["rc_of"][rec["key"]]) for rec in recs},
        "generic": {"geometry": generic["geometry"], "texture": generic["texture"], "material": generic["material"]},
        "render_controllers": {"file": os.path.relpath(RC_PATH, RP), "ids": rc["ids"], "stats": rc["stats"]},
    }
    write_json(ASSETS_JSON, doc)
    global _ASSETS
    _ASSETS = None


# ---- API（gen_nr_entities から。JSON を読むだけ） ----
_ASSETS: Optional[dict] = None


def _assets_doc() -> dict:
    global _ASSETS
    if _ASSETS is None:
        if not os.path.exists(ASSETS_JSON):
            raise FileNotFoundError(f"{_rel(ASSETS_JSON)} が無い（先に gen_nr_zombies.py を走らせる）")
        _ASSETS = load_json(ASSETS_JSON)
    return _ASSETS


def zombie_assets(key: str) -> dict:
    """{geometry, gib_geometry, texture, gib_texture, material, atlas, visible_bounds, visibility, bones,
    render_controller, cubes, gib_cubes, emissive, ztype, cls}（DESIGN §1・§2 の名前）。"""
    zs = _assets_doc().get("zombies") or {}
    if key not in zs:
        raise KeyError(f"{key} の記録が無い（gen_nr_zombies.py を走らせ直す）")
    return copy.deepcopy(zs[key])


def all_zombie_assets() -> Dict[str, dict]:
    return copy.deepcopy(_assets_doc().get("zombies") or {})


def gib_generic_assets() -> dict:
    g = _assets_doc().get("generic") or {}
    return {"geometry": g.get("geometry", GIB_GENERIC_GEO), "texture": g.get("texture", GIB_GENERIC_TEX)}


def render_controller_of(key: str) -> str:
    return zombie_assets(key).get("render_controller") or RC_ZOMBIE


def owned_render_controllers() -> List[str]:
    """このファイルが書いたレンダーコントローラの ID（書いたファイルから読む。無ければ空）。"""
    if not os.path.exists(RC_PATH):
        return []
    return sorted((load_json(RC_PATH).get("render_controllers") or {}).keys())


# ===========================================================================
#  5. 自己検査（書いたファイルを読み直す。参照切れ一般は validate_nr）
# ===========================================================================
def _molang_bool(expr, props: dict, life: float = 0.2) -> bool:
    import nr_preview as V
    return bool(V.molang(expr, properties=props, life_time=life))


def state_props(z: dict, state: Optional[dict] = None) -> dict:
    props = R.default_state()
    props["nr:armor"] = S.initial_armor(z)
    props.update(state or {})
    return props


def hidden_bones(rec: dict, state: Optional[dict] = None, life: float = 0.2) -> List[str]:
    """その状態で part_visibility が隠すボーン（Molang を評価する。確認画像と検査用）。"""
    props = state_props(S.ZOMBIE_BY_KEY[rec["key"]], state)
    rules = dict((b, e) for b, e in rec["visibility"])
    return [n for n, _p in rec["bones"] if n in rules and not _molang_bool(rules[n], props, life)]


def _ancestors(par: Dict[str, Optional[str]], name: str) -> List[str]:
    out, cur = [], par.get(name)
    while cur and cur not in out:
        out.append(cur)
        cur = par.get(cur)
    return out


# 自己検査で part_visibility を評価する状態（ゴアの確認画像の 4 つ + 能力・装甲の段階を混ぜた 2 つ）
CHECK_STATES = (
    {"nr:head": "severed", "nr:arm_r": "cut_upper"},
    {"nr:torso": "halved", "nr:arm_l": "cut_lower"},
    {"nr:head": "cracked", "nr:torso": "gutted", "nr:leg_r": "cut_lower", "nr:armor": 0},
    {"nr:head": "jawless", "nr:arm_r": "wounded", "nr:arm_l": "broken", "nr:leg_l": "cut_upper",
     "nr:torso": "slashed", "nr:armor": 1},
    {"nr:head": "crushed", "nr:arm_l": "cut_upper", "nr:leg_r": "cut_upper", "nr:armor": 0, "nr:ability": 1},
    {"nr:ability": 2, "nr:armor": 2, "nr:arm_r": "cut_lower", "nr:leg_l": "cut_lower"},
)


def self_check(recs: Sequence[dict]) -> List[str]:
    import numpy as np
    from PIL import Image
    errs: List[str] = []
    E = errs.append
    keys = [z["key"] for z in S.ZOMBIES]
    have = {rec["key"] for rec in recs}
    for k in keys:
        if k not in have:
            E(f"{k}: 記録が無い（作れなかった）")
    rc_doc = load_json(RC_PATH)["render_controllers"] if os.path.exists(RC_PATH) else {}
    if RC_ZOMBIE not in rc_doc or RC_GIB not in rc_doc:
        E(f"{_rel(RC_PATH)} に {RC_ZOMBIE} / {RC_GIB} が無い")
    assets = _assets_doc().get("zombies", {}) if os.path.exists(ASSETS_JSON) else {}
    for rec in recs:
        key = rec["key"]
        z = S.ZOMBIE_BY_KEY[key]
        p = _paths(key)
        try:
            geo = load_json(p["geo"])
            gib = load_json(p["gib"])
        except Exception as exc:  # noqa: BLE001
            E(f"{key}: ジオメトリが読めない（{exc}）")
            continue
        for doc, ident in ((geo, f"geometry.nr.z.{key}"), (gib, f"geometry.nr.gib.{key}")):
            if doc.get("format_version") != C.GEOMETRY_FORMAT:
                E(f"{ident}: format_version {doc.get('format_version')}（G1）")
            g = doc["minecraft:geometry"][0]
            if g["description"]["identifier"] != ident:
                E(f"{ident}: identifier が {g['description']['identifier']}")
        g = geo["minecraft:geometry"][0]
        d = g["description"]
        tw, th = d["texture_width"], d["texture_height"]
        with Image.open(p["tex"]) as im:
            size = im.size
            arr = np.asarray(im.convert("RGBA"))
        if size != (tw, th):
            E(f"{key}: テクスチャ {size} とジオメトリ {tw}x{th} が違う（G3）")
        gd = gib["minecraft:geometry"][0]["description"]
        if (gd["texture_width"], gd["texture_height"]) != (tw, th):
            E(f"{key}: gib のテクスチャ寸法が本体と違う")
        side = 1024 if z["cls"] == "boss" else 512
        if max(tw, th) > side:
            E(f"{key}: テクスチャ {tw}x{th}（上限 {side}。DESIGN §11）")
        bones = {b["name"]: b for b in g["bones"]}
        for name, parent in R.SKELETON:
            if name not in bones:
                E(f"{key}: §3 のボーン {name} が無い")
            elif (bones[name].get("parent") or None) != parent:
                E(f"{key}: {name} の親が {bones[name].get('parent')}（§3 では {parent}）")
        for name in bones:
            if name != name.lower() or not all(ch.isalnum() or ch == "_" for ch in name):
                E(f"{key}: ボーン名 {name}（G6）")
        cubes = sum(len(b.get("cubes") or []) for b in g["bones"])
        bad_uv = 0
        for b in list(g["bones"]) + list(gib["minecraft:geometry"][0]["bones"]):
            for c in b.get("cubes") or []:
                if c.get("rotation") and any(c["rotation"]) and "pivot" not in c:
                    E(f"{key}: {b['name']} の回転するキューブに pivot が無い（G2）")
                for face, f in (c.get("uv") or {}).items():
                    u, v = f["uv"]
                    w, h = f["uv_size"]
                    if min(u, u + w) < -1e-3 or min(v, v + h) < -1e-3 or max(u, u + w) > tw + 1e-3 \
                            or max(v, v + h) > th + 1e-3:
                        bad_uv += 1
        if bad_uv:
            E(f"{key}: テクスチャの外に出る UV {bad_uv} 面（G3）")
        cap = {"boss": 1100, "special": 650, "night": 650}.get(z["cls"], 450)
        if cubes > cap:
            E(f"{key}: キューブ {cubes}（上限 {cap}。DESIGN §11）")
        locs = set()
        for b in g["bones"]:
            locs |= set(b.get("locators") or {})
        miss = [n for n in R.REQUIRED_LOCATORS if n not in locs]
        if miss:
            E(f"{key}: ロケータが無い: {', '.join(miss)}")
        gib_bones = {b["name"] for b in gib["minecraft:geometry"][0]["bones"]}
        if not set(R.GIB_TYPE_PARTS) <= gib_bones:
            E(f"{key}: gib のボーンが足りない（{sorted(set(R.GIB_TYPE_PARTS) - gib_bones)}）")
        # テクスチャのアルファ（M2・M3）
        a = arr[..., 3]
        if (arr[a == 0][:, :3] != 0).any():
            E(f"{key}: α=0 なのに RGB が 0 でない画素がある（M2: 光るゴミになる）")
        mid = np.unique(a[(a > 0) & (a < 255)])
        bad = [int(v) for v in mid if not (EMISSIVE_ALPHA_RANGE[0] <= v <= EMISSIVE_ALPHA_RANGE[1])]
        if bad:
            E(f"{key}: 発光でない中間の α {bad[:6]}（M3）")
        want = MAT_EMISSIVE if mid.size else MAT_ALPHATEST
        if rec["material"] != want:
            E(f"{key}: マテリアル {rec['material']} だがテクスチャからは {want}")
        # 当たり箱
        sh = rec["shapes"]
        for pose in ("stand", "lie", "prone"):
            for part in R.HIT_PARTS:
                n = len(sh[pose].get(part) or [])
                if not 1 <= n <= 2:
                    E(f"{key}: 当たり箱 {pose}.{part} が {n} 箱")
        # 表示の規則: 既定の状態で §3 の体は見え、ゴア用ボーンは隠れる。RC は全ボーンの式を持つ
        hid = set(hidden_bones(rec))
        for name in R.BONE_NAMES:
            if (name in R.GORE_BONES) != (name in hid):
                E(f"{key}: 既定の状態で {name} が{'見える' if name in R.GORE_BONES else '隠れる'}")
        # part_visibility は子へ伝わらない（rendering.md §1.1）: どの状態でも「隠れた祖先の下で見えるボーン」が無いこと
        par = {n: p for n, p in rec["bones"]}
        for st in CHECK_STATES:
            hid = set(hidden_bones(rec, st))
            leak = next(((n, a) for n in par if n not in hid for a in _ancestors(par, n) if a in hid), None)
            if leak:
                E(f"{key}: {st} で {leak[1]} が隠れているのに子孫の {leak[0]} が見える（祖先の条件の AND が無い）")
                break
        rid = (assets.get(key) or {}).get("render_controller", RC_ZOMBIE)
        pv = {next(iter(dd)): dd[next(iter(dd))] for dd in (rc_doc.get(rid) or {}).get("part_visibility", [])}
        if pv.get("*") is not True:
            E(f"{rid}: part_visibility の先頭が {{'*': true}} でない（R1）")
        for b, e in rec["visibility"]:
            if pv.get(b) != e:
                E(f"{key}: {rid} のボーン {b} の式が種類の規則と違う")
                break
        for n, _par in rec["bones"]:
            if n not in dict((b, e) for b, e in rec["visibility"]) and n in pv:
                E(f"{key}: いつも表示のボーン {n} に {rid} が条件を付けている")
                break
    gib_rc_ = rc_doc.get(RC_GIB) or {}
    if len(((gib_rc_.get("arrays") or {}).get("geometries") or {}).get("Array.geos") or []) != len(keys):
        E(f"{RC_GIB}: 配列の長さが種類の数と違う")
    gib_vis = {next(iter(dd)) for dd in gib_rc_.get("part_visibility", [])} - {"*"}
    if gib_vis != set(R.GIB_PARTS):
        E(f"{RC_GIB}: part_visibility が DESIGN §5 の p_* と違う")
    for path in (os.path.join(GIB_DIR, f"{GIB_GENERIC_KEY}.geo.json"), os.path.join(RP, GIB_GENERIC_TEX + ".png")):
        if not os.path.exists(path):
            E(f"汎用の肉片が無い: {_rel(path)}")
    js = os.path.join(C.DATA_JS, f"{SHAPES_JS}.js")
    if not os.path.exists(js):
        E(f"{_rel(js)} が無い")
    return errs


# ===========================================================================
#  6. 確認画像（NR_PREVIEW=1 / --sheet）
# ===========================================================================
SHEET_PER = 8
GORE_PER = 6
TILE = (200, 320)
BG = (40, 42, 48)
# (ラベル, 状態, yaw, pitch)
GORE_STATES = (
    ("頭 severed・右腕 cut_upper", {"nr:head": "severed", "nr:arm_r": "cut_upper"}, 30, 10),
    ("胴 halved・左腕 cut_lower", {"nr:torso": "halved", "nr:arm_l": "cut_lower"}, 150, 14),
    ("頭 cracked・腹 gutted・右脚 cut_lower・装甲 0",
     {"nr:head": "cracked", "nr:torso": "gutted", "nr:leg_r": "cut_lower", "nr:armor": 0}, 35, 16),
    ("顎なし・右腕 wounded・左腕 broken・左脚 cut_upper・胴 slashed・装甲 1",
     {"nr:head": "jawless", "nr:arm_r": "wounded", "nr:arm_l": "broken", "nr:leg_l": "cut_upper",
      "nr:torso": "slashed", "nr:armor": 1}, -30, 8),
)


def _camera(V, rec: dict, yaw: float, pitch: float):
    sh = rec["shapes"]
    hu = float(sh["height"]) * 16.0
    wu = max(float(sh["width"]), float(sh.get("depth", sh["width"]))) * 16.0
    scale = min(TILE[1] * 0.9 / (hu * 1.06), TILE[0] * 0.92 / (wu * 1.12))
    return V.Camera(yaw=yaw, pitch=pitch, target=(0, hu * 0.5, 0), scale=scale)


def _preview_one(key: str):
    """(key, 前と後ろを並べた画像, [ゴアの状態の画像])。保存したファイル（ゲームと同じ物）から描く。"""
    import nr_preview as V
    from PIL import Image
    rec = load_cached(key)
    p = _paths(key)
    geo = V.load_geometry(p["geo"])
    tex = V.load_texture(p["tex"], geo)
    hide = hidden_bones(rec)
    shots = [V.render(geo, tex, camera=_camera(V, rec, yaw, 6), size=TILE, hidden=hide, hide_mode="exact",
                      bg=BG, ss=2) for yaw in (25, 205)]
    both = Image.new("RGB", (TILE[0] * 2, TILE[1]), BG)
    for i, s in enumerate(shots):
        both.paste(s.convert("RGB"), (i * TILE[0], 0))
    gore = []
    for _lab, st, yaw, pitch in GORE_STATES:
        hide = hidden_bones(rec, st)
        gore.append(V.render(geo, tex, camera=_camera(V, rec, yaw, pitch), size=TILE, hidden=hide,
                             hide_mode="exact", bg=BG, ss=2).convert("RGB"))
    return key, both, gore


def write_sheets(recs: Sequence[dict], jobs: int = 0) -> List[str]:
    import nr_preview as V
    os.makedirs(SHEET_DIR, exist_ok=True)
    for f in os.listdir(SHEET_DIR):
        if (f.startswith("sheet_") or f.startswith("gore_")) and f.endswith(".png"):
            os.remove(os.path.join(SHEET_DIR, f))
    keys = [rec["key"] for rec in recs]
    out: Dict[str, tuple] = {}
    n = max(1, min(jobs or os.cpu_count() or 1, len(keys)))
    if n == 1:
        for k in keys:
            out[k] = _preview_one(k)
    else:
        with ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("fork")) as ex:
            for k, both, gore in ex.map(_preview_one, keys):
                out[k] = (k, both, gore)
    by = {rec["key"]: rec for rec in recs}
    written = []
    for i in range(0, len(keys), SHEET_PER):
        chunk = keys[i:i + SHEET_PER]
        tiles = []
        for k in chunk:
            r = by[k]
            kb = round(os.path.getsize(_paths(k)["tex"]) / 1024)
            mat = "E" if r["material"] == MAT_EMISSIVE else "A"
            tiles.append((f"{r['ztype']} {k} {r['cubes']}c {r['atlas'][0]}px {kb}K {mat}", out[k][1]))
        path = os.path.join(SHEET_DIR, f"sheet_{i // SHEET_PER + 1}.png")
        V.contact_sheet(tiles, cols=4, title=f"NIGHT RUNNER zombies {i}–{i + len(chunk) - 1}（前 / 後ろ。既定の状態）"
                        ).save(path)
        written.append(path)
    for i in range(0, len(keys), GORE_PER):
        chunk = keys[i:i + GORE_PER]
        tiles = []
        for k in chunk:
            for j, im in enumerate(out[k][2]):
                tiles.append((f"{k} #{j + 1}", im))
        path = os.path.join(SHEET_DIR, f"gore_{i // GORE_PER + 1}.png")
        title = " / ".join(f"#{j + 1} {lab}" for j, (lab, *_r) in enumerate(GORE_STATES))
        V.contact_sheet(tiles, cols=8, title=title).save(path)
        written.append(path)
    return written


# ===========================================================================
#  7. 書き出し
# ===========================================================================
def clean_stale(keys: Sequence[str]) -> int:
    """今の spec に無い種類の古いファイルを消す（このフォルダは全部この生成器のもの）。"""
    want = set(keys)
    n = 0
    for d, suffix, extra in ((GEO_DIR, ".geo.json", ()), (GIB_DIR, ".geo.json", (GIB_GENERIC_KEY,)),
                             (TEX_DIR, ".png", ()), (CACHE_DIR, ".json", ())):
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(suffix) and f[:-len(suffix)] not in want and f[:-len(suffix)] not in extra:
                os.remove(os.path.join(d, f))
                n += 1
    return n


def print_table(recs: Sequence[dict], rc: dict, generic: dict) -> None:
    print(f"{'#':>2} {'key':18s} {'cls':8s} {'cubes':>9s} {'gib':>4s} {'atlas':>9s} {'texel':>5s} {'KB':>5s} "
          f"{'png':4s} {'material':9s} {'emis':>5s} {'H':>5s} {'s':>5s}")
    tot_kb = 0.0
    for r in recs:
        kb = os.path.getsize(_paths(r["key"])["tex"]) / 1024
        tot_kb += kb
        mark = "cache" if r.get("cached") else f"{r['seconds']['total']:.1f}"
        print(f"{r['ztype']:2d} {r['key']:18s} {r['cls']:8s} {r['cubes']:4d}/{r['cap']:<4d} {r['gib']['cubes']:4d} "
              f"{r['atlas'][0]:4d}x{r['atlas'][1]:<4d} {r['texel']!s:>5s} {kb:5.0f} {r['png_mode']:4s} "
              f"{'emissive' if r['material'] == MAT_EMISSIVE else 'alphatest':9s} {r['emissive_px']:5d} "
              f"{r['shapes']['height']:5.2f} {mark:>5s}"
              + (f"  kit: {'; '.join(r['kit_warnings'])}" if r.get("kit_warnings") else ""))
    st = rc["stats"]
    print(f"textures: {len(recs)} 枚 {tot_kb / 1024:.1f} MB（+ 汎用 {generic['png_bytes'] / 1024:.0f} KB）。"
          f"{RC_ZOMBIE}: {st['shared_rows']} 行・式 {st['shared_chars'] / 1024:.1f} KB、専用 RC {st['own']} 本、"
          f"{_rel(RC_PATH)} {st['file_kb']} KB")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NIGHT RUNNER のゾンビ 50 体の見た目を書く")
    ap.add_argument("--force", action="store_true", help="キャッシュを無視して全部作り直す")
    ap.add_argument("--only", default="", help="作り直す種類（カンマ区切り）。他はキャッシュ")
    ap.add_argument("-j", "--jobs", type=int, default=0, help="並列のプロセス数（既定 CPU 数）")
    ap.add_argument("--sheet", action="store_true", help="確認画像を描く（NR_PREVIEW=1 でも）")
    ap.add_argument("--check", action="store_true", help="書いたファイルの自己検査だけ")
    a = ap.parse_args(argv)
    t0 = time.time()
    keys = [z["key"] for z in S.ZOMBIES]
    if a.check:
        recs = [r for r in (load_cached(k) for k in keys) if r is not None]
        errs = self_check(recs)
        for e in errs:
            print("ERROR", e)
        print(f"[{PRODUCER}] 自己検査 {len(recs)} 体: {'OK' if not errs else f'{len(errs)} 件'}")
        return 1 if errs else 0
    only = [k for k in a.only.split(",") if k]
    bad = [k for k in only if k not in S.ZOMBIE_BY_KEY]
    if bad:
        print(f"[{PRODUCER}] 知らない種類: {', '.join(bad)}")
        return 2
    recs, fails = build_all(force_keys=only, force=a.force, jobs=a.jobs)
    removed = clean_stale(keys)
    generic = write_generic_gibs()
    rc = write_render_controllers(recs)
    write_shapes(recs)
    write_assets_json(recs, rc, generic)
    print_table(recs, rc, generic)
    built = sum(1 for r in recs if not r.get("cached"))
    print(f"[{PRODUCER}] {len(recs)} 体（作った {built}・キャッシュ {len(recs) - built}・古いファイルを消した {removed}）"
          f" {time.time() - t0:.1f}s")
    for f in fails:
        print(f"ERROR {f['key']}: {f['error']}\n{f['trace']}")
    errs = self_check(recs)
    for e in errs:
        print("ERROR", e)
    if a.sheet or C.PREVIEW:
        t1 = time.time()
        for p in write_sheets(recs, a.jobs):
            print("wrote", _rel(p))
        print(f"[{PRODUCER}] 確認画像 {time.time() - t1:.1f}s")
    return 1 if (fails or errs) else 0


if __name__ == "__main__":
    sys.exit(main())
