# -*- coding: utf-8 -*-
"""アストロ・ナノギア — ナノウェポン・惑星コアのジオメトリ・テクスチャ・アタッチャブル・アニメ・アイコン。

    python3 tools/astro/gen_astro_weapons.py            weapon.py のある全惑星
    python3 tools/astro/gen_astro_weapons.py earth mars 指定した惑星は必ず塗り直す

惑星ごとの planets/<key>/weapon.py（build_weapon / build_core / WEAPON_STYLES / CORE_STYLES /
WEAPON_ANIMS / CORE_ANIMS / KIND / HOLD / ICON）からモデルを組み、書き出す:
  models/entity/astro_weapon_<key>.geo.json   geometry.astro.weapon_<key>（テクスチャ ≤ 1024x1024）
  models/entity/astro_core_<key>.geo.json     geometry.astro.core_<key>  （テクスチャ ≤ 512x512）
  textures/entity/astro/weapon_<key>.png / core_<key>.png
  attachables/weapon_<key>.attachable.json / core_<key>.attachable.json
  textures/items/astro/weapon_<key>.png / core_<key>.png   （64x64 のアイコン）
共有ファイル（毎回、weapon.py のある全惑星から作り直す。誰がどの惑星で走らせても同じ結果）:
  animations/astro_weapons.animation.json
  animation_controllers/astro_weapons.animation_controllers.json   （形成 → ready）
  render_controllers/astro_weapons.render_controllers.json         （片面 + fx_* だけ両面）

塗り（テクスチャとアイコン）は時間がかかるので、指定されなかった惑星は「モデル・塗り・ペインタが前回と
同じでファイルがある」なら塗り直さない（build_preview/astro/.weapons_cache.json に指紋を残す）。
最後に参照の整合（ボーン・UV・Molang の括弧・アニメの実在）を確かめ、問題があれば 1 で終わる。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import astro_animcheck as AK  # noqa: E402
import astro_common as AC  # noqa: E402
import astro_weapon as W  # noqa: E402

NS = W.NS
ANIM_PATH = os.path.join(AC.RP, "animations", "astro_weapons.animation.json")
CTRL_PATH = os.path.join(AC.RP, "animation_controllers", "astro_weapons.animation_controllers.json")
RC_PATH = os.path.join(AC.RP, "render_controllers", "astro_weapons.render_controllers.json")
CACHE = os.path.join(AC.SCRATCH, ".weapons_cache.json")


def _fingerprint(geo_doc, styles, what):
    h = hashlib.sha256()
    h.update(json.dumps(geo_doc, sort_keys=True).encode())
    h.update(repr(sorted((k, sorted(v.items(), key=str)) for k, v in styles.items())).encode())
    h.update(what.encode())
    for f in ("astro_paint.py", "astro_weapon.py"):
        p = os.path.join(HERE, f)
        if os.path.exists(p):
            h.update(open(p, "rb").read())
    for f in ("hd_paint.py", "hd_preview.py"):
        p = os.path.join(AC.TOOLS, "hyperdim", f)
        h.update(open(p, "rb").read())
    return h.hexdigest()


def _geo_doc(m):
    return {"format_version": "1.12.0", "minecraft:geometry": [m.to_json()]}


def build_planet(key, force, cache, log):
    """1 惑星分のファイル。返り値 (アニメの dict, 警告のリスト)。"""
    mod = W.load_planet(key)
    t0 = time.time()
    wm, cm = W.build_models(key, mod)
    warns = W.validate_model(wm, "weapon", quiet=True) + W.validate_model(cm, "core", quiet=True)
    anims = {}
    for what, m, styles_name, seed in (("weapon", wm, "WEAPON_STYLES", 101), ("core", cm, "CORE_STYLES", 202)):
        geo_path, tex_path, icon_path = W.paths(key, what)
        doc = _geo_doc(m)
        AC.write_json(geo_path, doc)
        styles = W._styles(mod, styles_name, key)
        missing = [s for s in {c.style for c in m.all_cubes()} if s not in styles]
        if missing:
            raise KeyError(f"{key} {what}: styles not defined: {', '.join(sorted(missing))}")
        fp = _fingerprint(doc, styles, what)
        ck = f"{key}.{what}"
        if force or cache.get(ck) != fp or not os.path.exists(tex_path) or not os.path.exists(icon_path):
            W.paint_model(m, styles, tex_path, seed + W.D.PLANETS[key]["order"])
            W.make_icon(geo_path, tex_path, icon_path, W.icon_view(key, what, mod),
                        hide=tuple(getattr(mod, "ICON_HIDE", ()) or ()))
            cache[ck] = fp
            painted = "painted"
        else:
            painted = "cached"
        if what == "weapon":
            A = W.weapon_animations(key, m, mod)
        else:
            A = W.core_animations(key, m, mod)
        anims.update(A)
        AC.write_json(os.path.join(W.ATT_DIR, f"{what}_{key}.attachable.json"), W.attachable(key, what, A))
        log.append(f"  {key:8s} {what:6s} {len(m.bones):3d} bones {len(m.all_cubes()):4d} cubes "
                   f"{m.tex_w}x{m.tex_h} texel x{getattr(m, 'texel_k', 1)}  {painted}")
    log[-1] += f"  ({time.time() - t0:.1f}s)"
    return anims, [f"{key}: {w}" for w in warns]


# ---------------------------------------------------------------------------
#  検査
# ---------------------------------------------------------------------------
def _balanced(s):
    d = 0
    for ch in s:
        d += ch == "("
        d -= ch == ")"
        if d < 0:
            return False
    return d == 0


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _strings(k)
            yield from _strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from _strings(v)


def check(keys) -> list:
    from PIL import Image
    errors = []
    anims = json.load(open(ANIM_PATH, encoding="utf-8"))["animations"]
    ctrls = json.load(open(CTRL_PATH, encoding="utf-8"))["animation_controllers"]
    rcs = json.load(open(RC_PATH, encoding="utf-8"))["render_controllers"]
    for doc in (anims, ctrls):
        for s in _strings(doc):
            if not _balanced(s):
                errors.append(f"unbalanced molang: {s[:80]}")
    # 待機などのループは継ぎ目（animation_length ごとに q.anim_time が 0 に戻る所）で飛ばないこと
    errors += AK.seam_errors(anims)
    # 振り（v.astro_sw = 持ち主の attack_time。1.21.130 より前の統合版では読めず常に 0 — DESIGN.md §4.5）は
    # 0（振り始め・読めない時）と 1（振り終わり）で自然体: 読めない版でも武器は持ち姿勢のまま壊れて見えない
    for name, a in sorted(anims.items()):
        if name.endswith(".swing"):
            errors += AK.rest_errors(a, "v.astro_sw", where=f"{name} ")
    for key in keys:
        for what in ("weapon", "core"):
            geo_path, tex_path, icon_path = W.paths(key, what)
            g = json.load(open(geo_path, encoding="utf-8"))["minecraft:geometry"][0]
            tw, th = g["description"]["texture_width"], g["description"]["texture_height"]
            if Image.open(tex_path).size != (tw, th):
                errors.append(f"{key} {what}: texture size != geometry")
            if Image.open(icon_path).size != (64, 64):
                errors.append(f"{key} {what}: icon is not 64x64")
            bones = {b["name"] for b in g["bones"]}
            for b in g["bones"]:
                if b.get("parent") and b["parent"] not in bones:
                    errors.append(f"{key} {what}: {b['name']} parent missing")
                for c in b.get("cubes", []):
                    for face, f in c["uv"].items():
                        u, v = f["uv"]
                        w, h = f["uv_size"]
                        if u < 0 or v < 0 or u + w > tw or v + h > th:
                            errors.append(f"{key} {what}: {b['name']} {face} uv outside")
            att = json.load(open(os.path.join(W.ATT_DIR, f"{what}_{key}.attachable.json"),
                                 encoding="utf-8"))["minecraft:attachable"]["description"]
            for s in _strings(att["scripts"]):
                if not _balanced(s):
                    errors.append(f"{key} {what}: unbalanced molang in scripts: {s[:60]}")
            for rc in att.get("render_controllers", []):
                name = rc if isinstance(rc, str) else next(iter(rc))
                if name not in rcs and not name.startswith("controller.render.item_"):
                    errors.append(f"{key} {what}: render controller {name} missing")
            for mat in ("default", "fx"):
                if mat not in att.get("materials", {}):
                    errors.append(f"{key} {what}: material {mat} missing")
            amap = att["animations"]
            for short, full in amap.items():
                if full.startswith("controller."):
                    if full not in ctrls:
                        errors.append(f"{key} {what}: controller {full} missing")
                        continue
                    for st in ctrls[full]["states"].values():
                        for e in st.get("animations", []):
                            k = e if isinstance(e, str) else next(iter(e))
                            if k not in amap:
                                errors.append(f"{key} {what}: controller plays unknown {k}")
                    continue
                if full not in anims:
                    errors.append(f"{key} {what}: animation {full} missing")
                    continue
                for bone in anims[full].get("bones", {}):
                    if bone not in bones:
                        errors.append(f"{key} {what}: {full} animates missing bone {bone}")
            for e in att["scripts"]["animate"]:
                k = e if isinstance(e, str) else next(iter(e))
                if k not in amap:
                    errors.append(f"{key} {what}: animate refers to unknown {k}")
    return errors


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    present = W.planet_keys_with_weapon()
    chosen = [a for a in argv if not a.startswith("-")]
    for k in chosen:
        if k not in present:
            print(f"  ERROR: planets/{k}/weapon.py がありません（あるのは {', '.join(present) or 'なし'}）")
            return 1
    try:
        cache = json.load(open(CACHE, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    anims, warns, log = {}, [], []
    for key in present:                    # 共有ファイルは毎回、全惑星から
        A, wn = build_planet(key, key in chosen or "--force" in argv, cache, log)
        anims.update(A)
        warns += wn
    os.makedirs(AC.SCRATCH, exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh, indent=1, sort_keys=True)
    AC.write_json(ANIM_PATH, {"format_version": "1.10.0",
                              "animations": {k: anims[k] for k in sorted(anims)}})
    AC.write_json(CTRL_PATH, {"format_version": "1.10.0", "animation_controllers": W.form_controller()})
    AC.write_json(RC_PATH, {"format_version": "1.10.0", "render_controllers": W.render_controller()})
    print("\n".join(log))
    for w in warns:
        print(f"  WARN {w}")
    errors = check(present)
    for e in errors:
        print(f"  ERROR {e}")
    print(f"  weapons: {len(present)} planets, {len(anims)} animations, {len(errors)} error(s), "
          f"{len(warns)} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
