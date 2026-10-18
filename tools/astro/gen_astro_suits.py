# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツのジオメトリ・テクスチャ・アタッチャブル・アニメ。

    python3 tools/astro/gen_astro_suits.py            # planets/<key>/suit.py がある全惑星
    python3 tools/astro/gen_astro_suits.py earth mars # その惑星のモデル・テクスチャ・アタッチャブルだけ
                                                      # （共有のアニメ／コントローラは毎回「全惑星」から作り直す）
書き出す物（key ごと）:
  packs/astro_RP/models/entity/astro_suit_<key>.geo.json   geometry.astro.suit_<key>
  packs/astro_RP/textures/entity/astro/suit_<key>.png
  packs/astro_RP/attachables/suit_<key>.attachable.json     astro:suit_<key>
  packs/astro_RP/attachables/suit_<key>_off.attachable.json astro:suit_<key>_off（同じモデル、分解）
共有（全惑星ぶん。決定的な順番で毎回作り直す）:
  packs/astro_RP/animations/astro_suits.animation.json
  packs/astro_RP/animation_controllers/astro_suits.animation_controllers.json

アニメ（animation.astro.suit.<key>.<名前>）:
  assemble  部位ボーンの群（接頭辞）と ASSEMBLE_ORDER から自動。群の開始まで scale 0、
            そこから 0→1.15→1.0（0.25 秒）。同じ群の中は高さ順に少しずつずらす。
            visor 群の下の fx_glow_* は visor_flash の時刻に閃光（拡大して戻る）
  release   逆順に縮んで消える（0.8 秒）  gone  全部 scale 0（ループ）
  idle      SUIT_ANIMS["idle"] + fx_glow_*（バイザー以外）のゆっくりした脈動
  thrust    fx_thrust_* を v.astro_air（空中で 1 に近づく）で伸ばす + SUIT_ANIMS["thrust"]
  sprint    SUIT_ANIMS["sprint"]（v.astro_run で強さを付けられる）
  fp_hide   一人称で腕以外を隠す（fpx_* の包みボーンを scale 0）
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import astro_common as AC  # noqa: E402
from astro_common import NS, write_json  # noqa: E402
from astro_data import ASSEMBLE_ORDER, PLANETS, TRANSFORM  # noqa: E402
import astro_suit as AS  # noqa: E402
from astro_paint import AstroPainter, suit_styles  # noqa: E402

ANIM_FILE = os.path.join(AC.ANIM_DIR, "astro_suits.animation.json")
CTRL_FILE = os.path.join(AC.CTRL_DIR, "astro_suits.animation_controllers.json")
CTRL_ON = f"controller.animation.{NS}.suit"
CTRL_OFF = f"controller.animation.{NS}.suit_off"
IDLE_LEN = 12.0              # idle のループ長（秒）。Molang の周波数は 30°/秒の倍数で継ぎ目が出ない
POP = (0.10, 0.25)           # 組み上がりのポップ: 0→1.15 に 0.10 秒、1.0 に戻るまで 0.25 秒
RELEASE_LEN = 0.8
MAX_CUBES = 650

# 一人称で隠す包みボーン（腕以外のトップレベルの直下に生成時に挟む）
FP_WRAP = ("body", "head", "rightLeg", "leftLeg")


def wrap_name(top):
    return f"fpx_{top}"


def is_wrapper(name):
    return name.startswith("fpx_")


# ===========================================================================
#  モデル
# ===========================================================================
def insert_fp_wrappers(s: AS.Suit) -> None:
    """腕以外のトップレベルの直下に fpx_<top> を挟み、部位ボーンをその子にする。
    fp_hide はこの包みだけを縮めるので、組み上がり（部位ボーンの scale）と重ならない。"""
    from mcmodel import Bone
    m = s.m
    if any(is_wrapper(b.name) for b in m.bones):
        return
    wraps = []
    for top in FP_WRAP:
        w = Bone(wrap_name(top), AS.TOP[top], parent=top)
        wraps.append(w)
        for b in m.bones:
            if b.parent == top:
                b.parent = w.name
    n = len(AS.TOP)
    m.bones[n:n] = wraps


def build_suit(key: str, packed=True) -> AS.Suit:
    s = AS.build(key)
    insert_fp_wrappers(s)
    if packed:
        AS.pack(s)
    return s


def paint(s: AS.Suit) -> AstroPainter:
    mod = s.module
    st = suit_styles(s.key, **getattr(mod, "SUIT_STYLES", {}))
    p = AstroPainter(s.m.tex_w, s.m.tex_h, 300 + PLANETS[s.key]["order"] * 17)
    p.paint_model(s.m, st)
    return p


# ===========================================================================
#  アニメ
# ===========================================================================
def _num(v):
    return round(float(v), 3)


def _bones(s: AS.Suit):
    return {b.name: b for b in s.m.bones}


def part_group(s, name):
    """部位ボーンの群。fx_* / 包みは祖先の群。"""
    B = _bones(s)
    n = name
    while n:
        g = AS.group_of(n)
        if g:
            return g
        n = B[n].parent
    return None


def pop_bones(s: AS.Suit):
    """組み上がりで scale を付けるボーン: 部位ボーンのうち、最も近い部位の祖先と群が違う物
    （トップレベル・包みの直下も含む）。戻り値 [(name, group)]。"""
    B = _bones(s)
    out = []
    for b in s.m.bones:
        g = AS.group_of(b.name)
        if not g:
            continue
        p = b.parent
        while p and not AS.group_of(p) and p in B and p not in AS.TOP:
            p = B[p].parent
        pg = AS.group_of(p) if p else None
        if pg != g:
            out.append((b.name, g))
    return out


def group_start(g):
    return 0.0 if g == "inner" else float(ASSEMBLE_ORDER.get(g, 0.0))


def _stagger(s, items):
    """同じ群の中の時間差: 低い所から順に（左右の対は同時）。最大 0.15 秒。"""
    B = _bones(s)
    by_g = {}
    for name, g in items:
        by_g.setdefault(g, []).append(name)
    out = {}
    for g, names in by_g.items():
        ys = sorted({round(B[n].pivot[1] / 2.0) for n in names})
        if g in ("helmet", "visor", "shoulders"):
            ys = ys[::-1]
        step = min(0.05, 0.15 / max(1, len(ys) - 1)) if len(ys) > 1 else 0.0
        for n in names:
            out[n] = ys.index(round(B[n].pivot[1] / 2.0)) * step
    return out


def anim_assemble(s):
    L = float(TRANSFORM["assemble_len"])
    items = pop_bones(s)
    stg = _stagger(s, items)
    bones = {}
    for name, g in items:
        t0 = group_start(g) + stg[name]
        if g == "inner":
            k = {"0.0": [0, 0, 0], _k(t0 + 0.10): [1.04] * 3, _k(t0 + 0.18): [1, 1, 1]}
        else:
            k = {"0.0": [0, 0, 0]}
            if t0 > 0:
                k[_k(t0)] = [0, 0, 0]
            k[_k(t0 + POP[0])] = [1.15] * 3
            k[_k(t0 + POP[1])] = [1, 1, 1]
        bones[name] = {"scale": k}
    # バイザーの閃光
    tv = (TRANSFORM["visor_flash"] - TRANSFORM["suit_equip"]) / 20.0
    tv = max(tv, group_start("visor") + POP[1] * 0.5)
    for b in s.m.bones:
        if b.name.startswith("fx_glow_") and part_group(s, b.name) == "visor":
            bones[b.name] = {"scale": {"0.0": [1, 1, 1], _k(tv): [1, 1, 1],
                                       _k(tv + 0.08): [1.6, 1.6, 1.6],
                                       _k(min(L, tv + 0.22)): [1, 1, 1]}}
    return {"loop": False, "animation_length": L, "bones": bones}


def _k(t):
    return f"{round(t, 3):g}" if t else "0.0"


def anim_release(s):
    items = pop_bones(s)
    order = sorted({g for _n, g in items}, key=lambda g: -group_start(g))
    span = RELEASE_LEN - 0.24
    n = max(1, len(order) - 1)
    bones = {}
    for name, g in items:
        t0 = span * order.index(g) / n
        bones[name] = {"scale": {"0.0": [1, 1, 1], _k(t0): [1, 1, 1],
                                 _k(t0 + 0.07): [1.12] * 3, _k(t0 + 0.22): [0, 0, 0]}}
    return {"loop": "hold_on_last_frame", "animation_length": RELEASE_LEN, "bones": bones}


def anim_gone(s):
    return {"loop": True, "bones": {n: {"scale": 0} for n, _g in pop_bones(s)}}


def _planet_anim(s, name):
    a = (getattr(s.module, "SUIT_ANIMS", {}) or {}).get(name, {})
    if "bones" in a:
        return dict(a["bones"]), {k: v for k, v in a.items() if k != "bones"}
    return dict(a), {}


def _merge_tracks(base, extra):
    for bone, tr in extra.items():
        cur = base.setdefault(bone, {})
        for ch, v in tr.items():
            cur[ch] = v
    return base


def anim_idle(s):
    bones = {}
    k = 0
    for b in s.m.bones:
        if b.name.startswith("fx_glow_") and part_group(s, b.name) != "visor":
            ph = (k * 67) % 360
            bones[b.name] = {"scale": f"1.0 + math.sin(q.anim_time * 180.0 + {ph}) * 0.035"}
            k += 1
    pb, opts = _planet_anim(s, "idle")
    _merge_tracks(bones, pb)
    out = {"loop": True, "animation_length": opts.get("animation_length", IDLE_LEN),
           "bones": bones}
    return out


def anim_thrust(s):
    bones = {}
    k = 0
    for b in s.m.bones:
        if b.name.startswith("fx_thrust_"):
            ph = (k * 97) % 360
            ln = (f"0.22 + v.astro_air * (0.78 + math.sin(q.anim_time * 1440.0 + {ph}) * 0.12)"
                  f" + math.sin(q.anim_time * 1080.0 + {ph}) * 0.04")
            wd = "0.75 + v.astro_air * 0.25"
            bones[b.name] = {"scale": [wd, ln, wd]}
            k += 1
    pb, opts = _planet_anim(s, "thrust")
    _merge_tracks(bones, pb)
    return {"loop": True, "animation_length": opts.get("animation_length", IDLE_LEN),
            "bones": bones}


def anim_sprint(s):
    pb, opts = _planet_anim(s, "sprint")
    return {"loop": True, "animation_length": opts.get("animation_length", IDLE_LEN),
            "bones": pb}


def anim_fp_hide(s):
    return {"loop": True, "bones": {wrap_name(t): {"scale": 0} for t in FP_WRAP}}


def suit_animations(s) -> dict:
    base = f"animation.{NS}.suit.{s.key}"
    A = {
        f"{base}.assemble": anim_assemble(s),
        f"{base}.release": anim_release(s),
        f"{base}.gone": anim_gone(s),
        f"{base}.idle": anim_idle(s),
        f"{base}.thrust": anim_thrust(s),
        f"{base}.sprint": anim_sprint(s),
        f"{base}.fp_hide": anim_fp_hide(s),
    }
    # 惑星が追加で書いたアニメ（SUIT_ANIMS の idle/thrust/sprint 以外）もそのまま書き出す
    for name, a in (getattr(s.module, "SUIT_ANIMS", {}) or {}).items():
        if name in ("idle", "thrust", "sprint"):
            continue
        body = dict(a) if "bones" in a else {"loop": True, "bones": dict(a)}
        A[f"{base}.{name}"] = body
    return A


def controllers() -> dict:
    return {
        CTRL_ON: {
            "initial_state": "assemble",
            "states": {
                "assemble": {"animations": ["assemble"],
                             "transitions": [{"ready": "q.all_animations_finished"}]},
                "ready": {"animations": []},
            },
        },
        CTRL_OFF: {
            "initial_state": "release",
            "states": {
                "release": {"animations": ["release"],
                            "transitions": [{"gone": "q.all_animations_finished"}]},
                "gone": {"animations": ["gone"]},
            },
        },
    }


# ===========================================================================
#  アタッチャブル
# ===========================================================================
# 注意（実機で未確認の前提）: 頭スロットのアタッチャブルの中の q.is_on_ground / q.is_sprinting /
# q.delta_time は「持ち主（プレイヤー）」を指す前提で書いている（kaiju8 の no8_form と hyperdim の武器が
# 同じ前提で q.is_on_ground・q.is_using_item を直接使っている）。c.is_first_person は hyperdim の武器と同じ。
PRE = [
    "v.astro_fp = c.is_first_person ? 1.0 : 0.0;",
    "v.astro_air = (v.astro_air ?? 0.0) + ((q.is_on_ground ? 0.0 : 1.0) - (v.astro_air ?? 0.0))"
    " * math.min(1.0, q.delta_time * 6.0);",
    "v.astro_run = (v.astro_run ?? 0.0) + ((q.is_sprinting ? 1.0 : 0.0) - (v.astro_run ?? 0.0))"
    " * math.min(1.0, q.delta_time * 6.0);",
]
PARENT_SETUP = ("v.helmet_layer_visible = 0.0; v.chest_layer_visible = 0.0; "
                "v.leg_layer_visible = 0.0; v.boot_layer_visible = 0.0;")


def attachable(key, off=False, extra_anims=()):
    base = f"animation.{NS}.suit.{key}"
    ident = f"{NS}:suit_{key}" + ("_off" if off else "")
    anims = {"idle": f"{base}.idle", "thrust": f"{base}.thrust", "sprint": f"{base}.sprint",
             "fp_hide": f"{base}.fp_hide"}
    if off:
        anims.update({"release": f"{base}.release", "gone": f"{base}.gone",
                      "controller": CTRL_OFF})
        animate = ["controller", "idle", "thrust", {"fp_hide": "v.astro_fp > 0.5"}]
    else:
        anims.update({"assemble": f"{base}.assemble", "controller": CTRL_ON})
        for n in extra_anims:
            anims[n] = f"{base}.{n}"
        animate = ["controller", "idle", "thrust", {"sprint": "v.astro_run > 0.01"},
                   {"fp_hide": "v.astro_fp > 0.5"}]
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": ident,
                "materials": {"default": "entity_emissive_alpha",
                              "enchanted": "entity_alphatest_glint"},
                "textures": {"default": f"textures/entity/astro/suit_{key}",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": f"geometry.{NS}.suit_{key}"},
                "animations": anims,
                "scripts": {"parent_setup": PARENT_SETUP, "pre_animation": list(PRE),
                            "animate": animate},
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


# ===========================================================================
def write_suit(s: AS.Suit, quiet=False):
    key = s.key
    geo = os.path.join(AC.GEO_DIR, f"astro_suit_{key}.geo.json")
    tex = os.path.join(AC.TEX_DIR, f"suit_{key}.png")
    os.makedirs(AC.GEO_DIR, exist_ok=True)
    os.makedirs(AC.TEX_DIR, exist_ok=True)
    s.m.write(geo)
    p = paint(s)
    p.save(tex)
    extra = [n for n in (getattr(s.module, "SUIT_ANIMS", {}) or {})
             if n not in ("idle", "thrust", "sprint")]
    write_json(os.path.join(AC.ATT_DIR, f"suit_{key}.attachable.json"),
               attachable(key, extra_anims=extra))
    write_json(os.path.join(AC.ATT_DIR, f"suit_{key}_off.attachable.json"),
               attachable(key, off=True))
    n = len(s.m.all_cubes())
    if not quiet:
        print(f"  suit {key:8s} {len(s.m.bones):3d} bones {n:4d} cubes "
              f"{s.m.tex_w}x{s.m.tex_h} texel x{s.m.uv_scale:g}")
    if n > MAX_CUBES:
        print(f"  WARNING: {key}: {n} cubes > {MAX_CUBES}")
    return geo, tex


def write_shared(keys=None):
    """全惑星（または keys）のスーツから共有のアニメとコントローラを作り直す。"""
    A = {}
    for key in AS.available(keys):
        s = build_suit(key, packed=False)
        A.update(suit_animations(s))
    write_json(ANIM_FILE, {"format_version": "1.8.0", "animations": A})
    write_json(CTRL_FILE, {"format_version": "1.10.0", "animation_controllers": controllers()})
    return A


def main(argv):
    keys = [a for a in argv if not a.startswith("-")]
    avail = AS.available()
    bad = [k for k in keys if k not in avail]
    if bad:
        raise SystemExit(f"no planets/<key>/suit.py for: {bad} (available: {avail})")
    for key in (keys or avail):
        s = build_suit(key)
        write_suit(s)
    A = write_shared()
    print(f"  suit animations: {len(A)} ({len(avail)} planets)")


if __name__ == "__main__":
    main(sys.argv[1:])
