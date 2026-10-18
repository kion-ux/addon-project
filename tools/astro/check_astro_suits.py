# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツの検査（DESIGN §4.3 / §4.5 / §4.11）。

    python3 tools/astro/check_astro_suits.py            # planets/<key>/suit.py がある全惑星
    python3 tools/astro/check_astro_suits.py earth      # 1 惑星だけ
    python3 tools/astro/check_astro_suits.py earth -v   # 外に出た点の場所も詳しく

調べること（どれか 1 つでも NG なら終了コード 1）:
  モデル  * 肌の被覆: 6 部位の外側レイヤー（帽子 0.5・他 0.25。腕はスリムの腕も）を 0.5 間隔で標本化し、
            同じトップレベル配下のキューブ（extra_*・fx_* の動く部品は除く）に 99% 以上入っていること
          * ボーンの命名: トップレベル 6 つ（同名・同ピボット・キューブ無し・回転無し）、
            部位ボーン `<群>_<名前>`、fx_thrust_/fx_glow_/fx_spin_ は部位ボーンの下、名前の重複なし、
            プレイヤーのボーン名（cape, helmet, waist, rightItem …）を装飾に使っていない
          * キューブ数 250〜650、テクスチャ 1024x1024 以下、炎（flame 系の塗り）は fx_* の下（両面の材質）
  アニメ  * SUIT_ANIMS のボーンが実在、Molang が読める、部位ボーンの scale を書いていない
            （組み上がり・解除が scale を使うため）
  書き出し（pack に生成済みなら）
          * geo / png / アタッチャブル 3 種 / アニメ / コントローラ / レンダーコントローラが揃い JSON が読める
          * UV がテクスチャの内側、テクスチャの大きさが geo と一致
          * アニメが参照するボーンが geo に実在、アタッチャブルが参照するアニメ・コントローラが実在
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import astro_common as AC  # noqa: E402
import astro_suit as AS  # noqa: E402
import gen_astro_suits as G  # noqa: E402
from astro_data import PLANETS  # noqa: E402

MIN_CUBES, MAX_CUBES = 250, 650
FLAME_STYLES = ("flame", "flame_core")


class Report:
    def __init__(self, key):
        self.key = key
        self.errors = []
        self.warnings = []
        self.lines = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def info(self, msg):
        self.lines.append(msg)


def _molang_ok(expr):
    from astro_scene import Molang
    if isinstance(expr, (int, float)):
        return True
    try:
        Molang({})(expr)
        return True
    except Exception:  # noqa: BLE001
        return False


def _iter_values(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _iter_values(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _iter_values(x)
    else:
        yield v


def check_model(key, verbose=False) -> Report:
    r = Report(key)
    try:
        s = G.build_suit(key)
    except Exception as e:  # noqa: BLE001
        r.err(f"build failed: {type(e).__name__}: {e}")
        return r
    m = s.m
    n = len(m.all_cubes())
    r.info(f"{len(m.bones)} bones / {n} cubes / {m.tex_w}x{m.tex_h} (texel x{m.uv_scale:g})")
    for e in AS.naming_errors(s):
        r.err(e)
    if n < MIN_CUBES:
        r.err(f"only {n} cubes (< {MIN_CUBES}: not detailed enough)")
    if n > MAX_CUBES:
        r.err(f"{n} cubes (> {MAX_CUBES}: too heavy)")
    if m.tex_w > 1024 or m.tex_h > 1024:
        r.err(f"texture {m.tex_w}x{m.tex_h} > 1024")
    # 被覆
    cov = AS.coverage(s)
    ok, rep = AS.coverage_report(cov)
    r.info("coverage:\n" + rep)
    if not ok:
        r.err("skin coverage below 99% (see above). Add/extend cubes, or allowlist hidden areas "
              "with COVER_ALLOW in suit.py")
    if verbose:
        for top, c in cov.items():
            if c["uncovered"]:
                r.info(f"  {top}: {c['points'][:12].round(2).tolist()}")
    # 炎は fx_* の下（one_sided の既定材質では裏が抜けて見えるため）
    geo = AS.geo_of(s)
    for b in m.bones:
        chain = [b.name] + AS.ancestors(geo, b.name)
        if any(c.style in FLAME_STYLES for c in b.cubes) and \
                not any(x.startswith("fx_") for x in chain):
            r.warn(f"bone '{b.name}' has flame cubes outside an fx_* bone "
                   "(fx_* bones use the double-sided material)")
    # SUIT_ANIMS
    names = {b.name for b in m.bones}
    owned_scale = {nm for nm, _g in G.pop_bones(s)} | \
        {b.name for b in m.bones if b.name.startswith("fx_thrust_")} | \
        {b.name for b in m.bones if b.name.startswith("fx_glow_")
         and G.part_group(s, b.name) == "visor"}
    for anim, body in (getattr(s.module, "SUIT_ANIMS", {}) or {}).items():
        bones = body.get("bones", body) if isinstance(body, dict) else {}
        for bone, tr in bones.items():
            if bone not in names and not (bone.endswith("_l") and bone[:-2] + "_r" in names):
                r.err(f"SUIT_ANIMS['{anim}'] refers to missing bone '{bone}'")
            if bone in AS.TOP:
                r.err(f"SUIT_ANIMS['{anim}'] animates top-level bone '{bone}' (it follows the player)")
            if "scale" in tr and bone in owned_scale:
                r.err(f"SUIT_ANIMS['{anim}'] writes scale of '{bone}', which the generated "
                      "assemble/release/thrust animations own; scale a child fx_ bone instead")
            for v in _iter_values(tr):
                if isinstance(v, str) and not _molang_ok(v):
                    r.err(f"SUIT_ANIMS['{anim}']['{bone}']: cannot parse Molang {v!r}")
    return r


def _load(path, r):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        r.err(f"missing {os.path.relpath(path, AC.ROOT)} (run gen_astro_suits.py)")
    except json.JSONDecodeError as e:
        r.err(f"bad JSON {os.path.relpath(path, AC.ROOT)}: {e}")
    return None


def check_files(key, r: Report):
    """生成済みのファイルの相互参照。"""
    from PIL import Image
    geo_p = os.path.join(AC.GEO_DIR, f"astro_suit_{key}.geo.json")
    tex_p = os.path.join(AC.TEX_DIR, f"suit_{key}.png")
    if not os.path.exists(geo_p):
        r.warn("not generated yet (gen_astro_suits.py) — file checks skipped")
        return
    doc = _load(geo_p, r)
    if not doc:
        return
    g = doc["minecraft:geometry"][0]
    d = g["description"]
    if d.get("identifier") != f"geometry.{AC.NS}.suit_{key}":
        r.err(f"geometry identifier {d.get('identifier')}")
    tw, th = d["texture_width"], d["texture_height"]
    if os.path.exists(tex_p):
        im = Image.open(tex_p)
        if im.size != (tw, th):
            r.err(f"texture size {im.size} != geo {tw}x{th}")
    else:
        r.err(f"missing texture {os.path.relpath(tex_p, AC.ROOT)}")
    bad_uv = 0
    for b in g["bones"]:
        for c in b.get("cubes", []):
            for f, uv in c["uv"].items():
                u, v = uv["uv"]
                du, dv = uv["uv_size"]
                if u < 0 or v < 0 or u + du > tw or v + dv > th:
                    bad_uv += 1
    if bad_uv:
        r.err(f"{bad_uv} faces have UVs outside the {tw}x{th} texture")
    geo_bones = {b["name"] for b in g["bones"]}
    anims = _load(G.ANIM_FILE, r) or {"animations": {}}
    anims = anims.get("animations", {})
    ctrls = (_load(G.CTRL_FILE, r) or {}).get("animation_controllers", {})
    rcs = (_load(G.RC_FILE, r) or {}).get("render_controllers", {})
    pre = f"animation.{AC.NS}.suit.{key}."
    for name, a in anims.items():
        if not name.startswith(pre):
            continue
        for bone in a.get("bones", {}):
            if bone not in geo_bones:
                r.err(f"{name} animates missing bone '{bone}'")
        if a.get("loop") == "hold_on_last_frame" and not a.get("animation_length"):
            r.err(f"{name}: one-shot animation without animation_length")
    for v in G.VARIANTS:
        p = os.path.join(AC.ATT_DIR, f"suit_{key}{'_' + v if v else ''}.attachable.json")
        att = _load(p, r)
        if not att:
            continue
        desc = att["minecraft:attachable"]["description"]
        if desc["identifier"] != G.ident(key, v):
            r.err(f"{os.path.basename(p)}: identifier {desc['identifier']}")
        if desc["geometry"]["default"] != d["identifier"]:
            r.err(f"{os.path.basename(p)}: geometry {desc['geometry']['default']}")
        if desc["textures"]["default"] != f"textures/entity/astro/suit_{key}":
            r.err(f"{os.path.basename(p)}: texture path")
        for short, full in desc["animations"].items():
            if full.startswith("controller.animation."):
                if full not in ctrls:
                    r.err(f"{os.path.basename(p)}: controller {full} missing")
                else:
                    for st in ctrls[full]["states"].values():
                        for an in st.get("animations", []):
                            nm = an if isinstance(an, str) else list(an)[0]
                            if nm not in desc["animations"]:
                                r.err(f"{os.path.basename(p)}: controller uses '{nm}' "
                                      "not in the attachable's animations")
            elif full not in anims:
                r.err(f"{os.path.basename(p)}: animation {full} missing")
        for entry in desc["scripts"]["animate"]:
            nm = entry if isinstance(entry, str) else list(entry)[0]
            if nm not in desc["animations"]:
                r.err(f"{os.path.basename(p)}: animate '{nm}' is not defined")
        for rc in desc.get("render_controllers", []):
            if rc not in rcs:
                r.err(f"{os.path.basename(p)}: render controller {rc} missing")


def main(argv):
    verbose = "-v" in argv
    keys = [a for a in argv if not a.startswith("-")]
    avail = AS.available()
    for k in keys:
        if k not in PLANETS:
            raise SystemExit(f"unknown planet '{k}'")
        if k not in avail:
            raise SystemExit(f"no tools/astro/planets/{k}/suit.py")
    keys = keys or avail
    if not keys:
        print("no suits to check")
        return 0
    failed = 0
    for key in keys:
        r = check_model(key, verbose)
        if not r.errors or not any(e.startswith("build failed") for e in r.errors):
            check_files(key, r)
        status = "OK" if not r.errors else "NG"
        print(f"[{status}] suit {key}")
        for line in r.lines:
            print("    " + line.replace("\n", "\n    "))
        for w in r.warnings:
            print(f"    warning: {w}")
        for e in r.errors:
            print(f"    ERROR: {e}")
        failed += bool(r.errors)
    print(f"{len(keys) - failed}/{len(keys)} suits passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
