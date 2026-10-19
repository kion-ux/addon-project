# -*- coding: utf-8 -*-
"""アストロ・ナノギア — スーツのジオメトリ・テクスチャ・アタッチャブル・アニメ。

    python3 tools/astro/gen_astro_suits.py            # planets/<key>/suit.py がある全惑星
    python3 tools/astro/gen_astro_suits.py earth mars # その惑星のモデル・テクスチャ・アタッチャブルだけ
                                                      # （共有のアニメ／コントローラは毎回「全惑星」から作り直す）
書き出す物（key ごと）:
  packs/astro_RP/models/entity/astro_suit_<key>.geo.json   geometry.astro.suit_<key>
  packs/astro_RP/textures/entity/astro/suit_<key>.png
  packs/astro_RP/attachables/suit_<key>_on.attachable.json  astro:suit_<key>_on（組み上がり → ready）
  packs/astro_RP/attachables/suit_<key>.attachable.json     astro:suit_<key>（装着中。組み上がりを繰り返さない）
  packs/astro_RP/attachables/suit_<key>_off.attachable.json astro:suit_<key>_off（分解 → gone）
共有（全惑星ぶん。決定的な順番で毎回作り直す）:
  packs/astro_RP/animations/astro_suits.animation.json
  packs/astro_RP/animation_controllers/astro_suits.animation_controllers.json
  packs/astro_RP/render_controllers/astro_suits.render_controllers.json  controller.render.astro.suit
    （既定 entity_emissive_alpha_one_sided、fx_* ボーンだけ両面の entity_emissive_alpha）

アニメ（animation.astro.suit.<key>.<名前>）:
  assemble  部位ボーンの群（接頭辞）と ASSEMBLE_ORDER から自動。群の開始まで scale 0、
            そこから 0→1.15→1.0（0.25 秒）。同じ群の中は高さ順に少しずつずらす。
            visor 群の下の fx_glow_* は visor_flash の時刻に閃光（拡大して戻る）
  release   逆順に縮んで消える（0.8 秒）  gone  全部 scale 0（ループ）
  idle      SUIT_ANIMS["idle"] + fx_glow_*（バイザー以外）のゆっくりした脈動
  thrust    fx_thrust_* を v.astro_air（空中で 1 に近づく）で伸ばす + SUIT_ANIMS["thrust"]
  sprint    SUIT_ANIMS["sprint"]（v.astro_run で強さを付けられる）
  fp_hide   一人称で head・body・rightLeg・leftLeg を scale 0（腕だけ残る）
  hide_all  6 つのトップレベルを scale 0（頭スロット以外に置かれた時だけ。v1.1: 変身中はスクリプトが
            装着者を透明化するので q.is_invisible では隠さない。DESIGN §4.3b）
ループするアニメ（idle / thrust / sprint / 惑星の追加）は継ぎ目なく繰り返すこと:
  q.anim_time に掛ける周波数 × ループ長が 360° の整数倍（loop_errors() が調べる。check_astro_suits も使う）
"""
from __future__ import annotations

import os
import re
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
RC_FILE = os.path.join(AC.RP, "render_controllers", "astro_suits.render_controllers.json")
RC_NAME = f"controller.render.{NS}.suit"
IDLE_LEN = 12.0              # idle のループ長（秒）。Molang の周波数は 30°/秒の倍数で継ぎ目が出ない
POP = (0.10, 0.25)           # 組み上がりのポップ: 0→1.15 に 0.10 秒、1.0 に戻るまで 0.25 秒
RELEASE_LEN = 0.8
MAX_CUBES = 1400             # これを超えたら警告（検査は check_astro_suits。生成は止めない）

FP_HIDE = ("head", "body", "rightLeg", "leftLeg")     # 一人称で隠すトップレベル


# ===========================================================================
#  モデル
# ===========================================================================
def build_suit(key: str, packed=True, module=None) -> AS.Suit:
    s = AS.build(key, module=module)
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
    return {"loop": "hold_on_last_frame", "animation_length": L, "bones": bones}


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


def _neg(v):
    if isinstance(v, (int, float)):
        return -v
    return f"-({v})"


def _mirror_vec(v, signs):
    if isinstance(v, dict):                     # キーフレーム
        out = {}
        for t, x in v.items():
            if isinstance(x, dict):
                out[t] = {k: _mirror_vec(y, signs) if k in ("pre", "post") else y
                          for k, y in x.items()}
            else:
                out[t] = _mirror_vec(x, signs)
        return out
    if isinstance(v, (list, tuple)):
        return [_neg(x) if sg < 0 else x for x, sg in zip(v, signs)]
    return v


def mirror_tracks(bones: dict) -> dict:
    """`*_r` のボーンのトラックを `*_l` へ写す（rotation は (rx,-ry,-rz)、position は (-x,y,z)）。
    `_l` を自分で書いた物はそのまま。"""
    out = dict(bones)
    for name, tr in bones.items():
        if not name.endswith("_r") or name[:-2] + "_l" in bones:
            continue
        m = {}
        for ch, v in tr.items():
            if ch == "rotation":
                m[ch] = _mirror_vec(v, (1, -1, -1))
            elif ch == "position":
                m[ch] = _mirror_vec(v, (-1, 1, 1))
            else:
                m[ch] = v
        out[name[:-2] + "_l"] = m
    return out


def _planet_anim(s, name):
    a = (getattr(s.module, "SUIT_ANIMS", {}) or {}).get(name, {})
    if "bones" in a:
        bones, opts = dict(a["bones"]), {k: v for k, v in a.items() if k != "bones"}
    else:
        bones, opts = dict(a), {}
    if getattr(s.module, "MIRROR", True):
        bones = mirror_tracks(bones)
    return bones, opts


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
    return {"loop": True, "bones": {t: {"scale": 0} for t in FP_HIDE}}


def anim_hide_all(s):
    return {"loop": True, "bones": {t: {"scale": 0} for t in AS.TOP}}


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
        f"{base}.hide_all": anim_hide_all(s),
    }
    # 惑星が追加で書いたアニメ（SUIT_ANIMS の idle/thrust/sprint 以外）もそのまま書き出す
    for name, a in (getattr(s.module, "SUIT_ANIMS", {}) or {}).items():
        if name in ("idle", "thrust", "sprint"):
            continue
        body = dict(a) if "bones" in a else {"loop": True, "bones": dict(a)}
        A[f"{base}.{name}"] = body
    return A


_ANIM_T = re.compile(r"(?:q|query)\.anim_time\s*\*\s*\(?\s*(-?[\d.]+)|(-?[\d.]+)\s*\*\s*(?:q|query)\.anim_time")


def _strings(v):
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _strings(x)


def loop_errors(name: str, anim: dict) -> list:
    """ループするアニメが継ぎ目なく繰り返すか: q.anim_time に掛かる周波数 f（度/秒）が
    f × animation_length ≡ 0 (mod 360) であること。q.anim_time を掛け算以外で使う式は警告扱いの文を返す。
    戻り値: 問題の説明のリスト（空なら OK）。"""
    if anim.get("loop") is not True:
        return []
    L = float(anim.get("animation_length", IDLE_LEN) or IDLE_LEN)
    out = []
    for bone, tr in (anim.get("bones") or {}).items():
        for expr in _strings(tr):
            for m_ in _ANIM_T.finditer(expr):
                f = float(m_.group(1) or m_.group(2))
                turns = f * L / 360.0
                if abs(turns - round(turns)) > 1e-6:
                    out.append(f"{name}: '{bone}' uses q.anim_time * {f:g} — {f:g}°/s × {L:g} s "
                               f"is {turns:.3f} turns (not whole: jumps at the loop). Use a multiple "
                               f"of {360.0 / L:g}°/s")
            rest = _ANIM_T.sub("", expr)
            if re.search(r"(?:q|query)\.anim_time", rest):
                out.append(f"{name}: '{bone}' uses q.anim_time outside 'q.anim_time * <number>' "
                           f"({expr[:60]!r}); make sure it is periodic over {L:g} s")
    return out


_SCALED_T = re.compile(r"v\.\w+\s*\*\s*\(?\s*(?:q|query)\.anim_time|"
                       r"(?:q|query)\.anim_time\s*\*\s*[\d.]+\s*\*\s*v\.\w+")


def loop_warnings(name: str, anim: dict) -> list:
    """ループの継ぎ目の注意（エラーにはしない）: 回転の速さそのものを v.*（v.astro_air など 0..1 で
    なめらかに変わる値）で掛けると、v が半端な間はループの切れ目で角度が跳ぶ。速さは一定にして、
    振れ幅や別の項を v で掛けること。"""
    if anim.get("loop") is not True:
        return []
    out = []
    for bone, tr in (anim.get("bones") or {}).items():
        for expr in _strings(tr):
            if _SCALED_T.search(expr):
                out.append(f"{name}: '{bone}' scales the speed of q.anim_time by a variable "
                           f"({expr[:50]!r}) — it jumps at the loop while the variable is between 0 and 1")
    return out


def controllers() -> dict:
    return {
        CTRL_ON: {
            "initial_state": "assemble",
            "states": {
                "assemble": {"animations": ["assemble"],
                             "transitions": [{"ready": "q.all_animations_finished || q.is_in_ui"}]},
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
# アタッチャブルの中の素の q.*（q.is_on_ground / q.is_sprinting / q.delta_time …）は装着者を評価する
# （DESIGN §4.5 の調査結果。kaiju8 の no8_form・hyperdim の武器も同じ前提）。素の v.* はアタッチャブル自身の変数。
# c.is_first_person は装着者本人の一人称だけ 1。
PRE = [
    "v.astro_fp = c.is_first_person ? 1.0 : 0.0;",
    "v.astro_air = (v.astro_air ?? 0.0) + ((q.is_on_ground ? 0.0 : 1.0) - (v.astro_air ?? 0.0))"
    " * math.min(1.0, q.delta_time * 6.0);",
    "v.astro_run = (v.astro_run ?? 0.0) + ((q.is_sprinting ? 1.0 : 0.0) - (v.astro_run ?? 0.0))"
    " * math.min(1.0, q.delta_time * 6.0);",
    # 累積の位相（秒）。ループの継ぎ目が無く、速さを変えても角度が飛ばない:
    #   v.astro_t    … ただの経過時間
    #   v.astro_spin … 空中で 2.5 倍・疾走で 3 倍まで速く進む時間（回る環・タービン・衛星はこれに角速度を掛ける）
    # q.anim_time * v.astro_run のように「時間 × 変わる重み」にすると、重みが変わる瞬間に角度が大きく飛ぶので使わない。
    "v.astro_t = (v.astro_t ?? 0.0) + q.delta_time;",
    "v.astro_spin = (v.astro_spin ?? 0.0) + q.delta_time * (1.0 + v.astro_air * 1.5 + v.astro_run * 2.0);",
]
PARENT_SETUP = ("v.helmet_layer_visible = 0.0; v.chest_layer_visible = 0.0; "
                "v.leg_layer_visible = 0.0; v.boot_layer_visible = 0.0;")
VARIANTS = ("on", "", "off")          # astro:suit_<key>_on / astro:suit_<key> / astro:suit_<key>_off
HIDE_ALL = "c.item_slot != 'head'"


def ident(key, variant=""):
    return f"{NS}:suit_{key}" + (f"_{variant}" if variant else "")


def attachable(key, variant="", extra_anims=()):
    """variant: "on"（組み上がり → ready）/ ""（装着中）/ "off"（分解 → gone）。"""
    base = f"animation.{NS}.suit.{key}"
    anims = {"idle": f"{base}.idle", "thrust": f"{base}.thrust", "sprint": f"{base}.sprint",
             "fp_hide": f"{base}.fp_hide", "hide_all": f"{base}.hide_all"}
    for n in extra_anims:
        anims[n] = f"{base}.{n}"
    # hide_all は頭スロット以外に置かれた時だけ（v1.1: 変身中は装着者が透明化されるので
    # q.is_invisible を入れるとスーツまで消える。DESIGN §4.3b）
    tail = [{"fp_hide": "v.astro_fp > 0.5"},
            {"hide_all": HIDE_ALL}]
    if variant == "off":
        anims.update({"release": f"{base}.release", "gone": f"{base}.gone",
                      "controller": CTRL_OFF})
        animate = ["controller", "idle", "thrust"] + tail
    elif variant == "on":
        anims.update({"assemble": f"{base}.assemble", "controller": CTRL_ON})
        animate = ["controller", "idle", "thrust", {"sprint": "v.astro_run > 0.01"}] + tail
    else:
        animate = ["idle", "thrust", {"sprint": "v.astro_run > 0.01"}] + tail
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": ident(key, variant),
                "materials": {"default": "entity_emissive_alpha_one_sided",
                              "fx": "entity_emissive_alpha",
                              "enchanted": "entity_alphatest_glint"},
                "textures": {"default": f"textures/entity/astro/suit_{key}",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": f"geometry.{NS}.suit_{key}"},
                "animations": anims,
                "scripts": {"parent_setup": PARENT_SETUP, "pre_animation": list(PRE),
                            "animate": animate},
                "render_controllers": [RC_NAME],
            }
        },
    }


def render_controllers() -> dict:
    return {"format_version": "1.8.0", "render_controllers": {
        RC_NAME: {"geometry": "Geometry.default",
                  "materials": [{"*": "Material.default"}, {"fx_*": "Material.fx"}],
                  "textures": ["Texture.default"]}}}


# ===========================================================================
def dump_geo(model) -> str:
    """ジオメトリを「キューブ 1 個 = 1 行」の JSON に（indent=2 の 1/3 ほどの大きさで、差分も読める）。"""
    import json
    g = model.to_json()
    out = ['{', '  "format_version": "1.16.0",', '  "minecraft:geometry": [', '    {',
           '      "description": ' + json.dumps(g["description"], ensure_ascii=False) + ',',
           '      "bones": [']
    bones = g["bones"]
    for i, b in enumerate(bones):
        head = json.dumps({k: v for k, v in b.items() if k != "cubes"}, ensure_ascii=False)[:-1]
        if b.get("cubes"):
            cubes = ",\n".join("          " + json.dumps(c, separators=(",", ":"))
                               for c in b["cubes"])
            line = head + ', "cubes": [\n' + cubes + '\n        ]}'
        else:
            line = head + '}'
        out.append('        ' + line + (',' if i < len(bones) - 1 else ''))
    out += ['      ]', '    }', '  ]', '}', '']
    return "\n".join(out)


def write_suit(s: AS.Suit, quiet=False):
    key = s.key
    geo = os.path.join(AC.GEO_DIR, f"astro_suit_{key}.geo.json")
    tex = os.path.join(AC.TEX_DIR, f"suit_{key}.png")
    os.makedirs(AC.GEO_DIR, exist_ok=True)
    os.makedirs(AC.TEX_DIR, exist_ok=True)
    with open(geo, "w", encoding="utf-8") as fh:
        fh.write(dump_geo(s.m))
    p = paint(s)
    p.save(tex)
    extra = [n for n in (getattr(s.module, "SUIT_ANIMS", {}) or {})
             if n not in ("idle", "thrust", "sprint")]
    for v in VARIANTS:
        write_json(os.path.join(AC.ATT_DIR, f"suit_{key}{'_' + v if v else ''}.attachable.json"),
                   attachable(key, v, extra_anims=extra))
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
    write_json(RC_FILE, render_controllers())
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
