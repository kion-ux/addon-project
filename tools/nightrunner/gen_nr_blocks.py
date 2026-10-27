# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — カスタムブロック（バリケード・街灯・UV ライト・瓦礫・箱・罠…）の生成器。

`nr_spec.BLOCKS`（30 種）と `nr_spec.block_traps()` + `TRAP_BLOCKS`（罠ブロック 9 種）の全部について書く:

| 書くもの | 場所（このフォルダ・ファイルは全部この生成器のもの） |
|---|---|
| BP ブロック（format 1.21.120、content.md §4 / rendering.md §8・§11 B1〜B6） | `packs/nightrunner_BP/blocks/<key>.json` |
| 作業台のレシピ（spec に `recipe` があるもの。tags + unlock 付き） | `packs/nightrunner_BP/recipes/blocks/<key>.json` |
| 壊したときのルート（spec の `loot` → `LOOT_TABLES`、散らかり系は空） | `packs/nightrunner_BP/loot_tables/nr_blocks/<key>.json` |
| ジオメトリ `geometry.nr.b.<key>`（1.16.0、nr_common.write_geometry） | `packs/nightrunner_RP/models/blocks/nr/<key>.geo.json` |
| テクスチャ（nr_paint で塗る。≤256×256） | `packs/nightrunner_RP/textures/nr/blocks/<key>.png` |
| ブロックの状態・カスタムコンポーネントの表（スクリプト用） | `packs/nightrunner_BP/scripts/data/block_defs.js` |
| カスタムコンポーネントの一覧（スクリプト担当が登録する） | `tools/nightrunner/.cache/block_components.json` |
| 断片 terrain_texture / blocks / lang | `.frag/<種類>/gen_nr_blocks.json` |
| 確認用の画像 | `build_preview/nightrunner/blocks.png`（全ブロック 3/4）・`blocks_states.png`・`blocks_scene.png` |

ブロックの決め方（スクリプト・構造物の生成器との約束）:

* **向き**: `rotatable` のブロックは `minecraft:placement_direction`（`minecraft:cardinal_direction`、
  `y_rotation_offset: 180` = 置いた人の方を向く）+ `minecraft:transformation` の permutation。
  **状態の値 = モデルの前（-Z = north 面）が向く方角**（north 0° / west 90° / south 180° / east -90°）。
  壁に付く物（救急箱・落書きの板・ガス管）はモデルの +Z が壁側。
* **状態**: spec の `states` に加えて、`variants > 1` で状態が無いものに `nr:variant`（0..n-1）、
  罠に `nr:trap_state`（`TRAP_STATE_VALUES`。armed / triggered / spent / idle）、電気トラップに `nr:charges`（6..0）、
  使うほど傷む罠に `nr:wear`（0..3）。状態の配列の**先頭が既定値**（灯り系 `nr:lit` / `nr:powered` は 1 を先頭 =
  置いた時から点いている。spec の値の集合は変えていない）。見た目は `bone_visibility`、明るさは
  `light_emission` の permutation。
* **カスタムコンポーネント**（Custom Components V2: コンポーネントと同じ所に `"nr:xxx": {params}`）:
  `COMPONENT_HOOKS` の 12 個。onTick を使うものには `minecraft:tick`、onEntityFallOn には
  `minecraft:entity_fall_on` を付ける。**全部スクリプト側で `blockComponentRegistry.registerCustomComponent`
  する必要がある**（登録の無い名前があるとブロックが読み込めない）→ `.cache/block_components.json`。
* 踏んで発動する罠（spike_trap）は `onStepOn` が来るように当たり箱の高さを 4px 以上に上げる
  （content.md §4.3 / U17）。当たり箱の無い罠（トラバサミ・有刺鉄線）は `onTick` で中の生き物を調べる。
* 発光: ブロックは画素単位で光れない（rendering.md §8）。発光の素材は「明るい色」で塗り（α=255）、
  光は `light_emission` で出す。穴（α=0）のあるテクスチャは `alpha_test`（spec が opaque でも上げる）。

公開 API（gen_nr_structures・データ JS から）:

    block_states(key, facing=None, **over) -> {状態名: 既定値}   # 例 block_states("uv_lamp", facing="north")
    multiblock_parts(name_or_key, facing=None) -> [(ブロック ID, (dx, dy, dz), 状態), ...]
    state_schema(key) -> {状態名: [値...]}（先頭が既定）
    custom_components(key) -> {コンポーネント名: params}
    all_blocks() -> ブロックの辞書のリスト（罠ブロックは TRAP_BLOCKS を混ぜたもの、"trap" に罠の定義）

使い方: `python3 tools/nightrunner/gen_nr_blocks.py [--only key,key] [--no-preview] [--sheet-only]`
（普通は build_nr.py から）。
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
import time
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from nr_common import (BP, RP, SCRATCH, frag, stable_hash, write_geometry, write_json,  # noqa: E402
                       write_text, js_literal)
import nr_paint as NP  # noqa: E402
import nr_block_models as BM  # noqa: E402

PRODUCER = "gen_nr_blocks"
BLOCK_FORMAT = "1.21.120"
RECIPE_FORMAT = "1.20.10"
BLOCK_DIR = os.path.join(BP, "blocks")
RECIPE_DIR = os.path.join(BP, "recipes", "blocks")
LOOT_REL = "loot_tables/nr_blocks"
LOOT_DIR = os.path.join(BP, *LOOT_REL.split("/"))
GEO_DIR = os.path.join(RP, "models", "blocks", "nr")
TEX_DIR = os.path.join(RP, "textures", "nr", "blocks")
TEX_REF = "textures/nr/blocks/"
CACHE = os.path.join(HERE, ".cache", "block_components.json")
DATA_JS = os.path.join(BP, "scripts", "data", "block_defs.js")

MAX_CUBES = 50
MAX_TEX = 256
FULL_BOX = {"origin": [-8, 0, -8], "size": [16, 16, 16]}

# ===========================================================================
#  spec
# ===========================================================================
_SPEC = None


def load_spec():
    """nr_spec.py（無ければ catalog だけ）。"""
    global _SPEC
    if _SPEC is None:
        if os.path.exists(os.path.join(HERE, "nr_spec.py")):
            import nr_spec
            _SPEC = nr_spec
        else:
            import nr_spec_catalog
            _SPEC = nr_spec_catalog
    return _SPEC


def all_blocks() -> List[dict]:
    """BLOCKS + 罠ブロック（TRAPS の block を TRAP_BLOCKS の性質と合わせて BLOCKS と同じ形に）。"""
    S = load_spec()
    out = []
    for b in S.BLOCKS:
        e = dict(b)
        e["trap"] = None
        out.append(e)
    for t in S.block_traps():
        tb = dict(S.TRAP_BLOCKS.get(t["key"], {}))
        col = tb.get("collision", False)
        sel = tb.get("selection") or (col if col else dict(FULL_BOX))
        e = dict(key=t["key"], id=t["id"], ja=t["ja"], en=t["en"], category="trap", model=list(t["model"]),
                 collision=col, selection=sel, sound=tb.get("sound", "metal"),
                 map_color=tb.get("map_color", "#808080"), light_emission=int(t.get("light_emission", 0)),
                 loot=None, recipe=t.get("recipe"), destroy_time=tb.get("destroy_time", 1.5),
                 blast_resistance=tb.get("blast_resistance", 3.0), flammable=False,
                 rotatable=tb.get("rotatable", True), states={}, interact=None, parkour=[], multiblock=None,
                 variants=1, render=tb.get("render", "opaque"), hp=None, desc_ja=t.get("desc_ja", ""),
                 desc_en=t.get("desc_en", ""), geometry="geometry.nr.b." + t["key"],
                 texture=TEX_REF + t["key"], trap=t)
        out.append(e)
    return out


def entry(key: str) -> dict:
    k = key[3:] if key.startswith("nr:") else key
    for e in all_blocks():
        if e["key"] == k:
            return e
    raise KeyError(f"ブロック {key} は spec に無い")


# ===========================================================================
#  状態（DESIGN の名前空間 nr:）
# ===========================================================================
TRAP_STATE = "nr:trap_state"
CHARGES = "nr:charges"
WEAR = "nr:wear"
VARIANT = "nr:variant"
CARDINAL = "minecraft:cardinal_direction"
CARDINAL_VALUES = ["south", "west", "north", "east"]     # エンジンの並び（先頭 south が既定）

# 罠の状態の語彙: armed 仕掛けてある / triggered 作動中（挟んでいる・燃えている・噴いている）/
# spent 使い切った（電池切れ・裂けたまま・閉じて空・焦げ跡）/ idle 作動待ち（置いた直後のワイヤー地雷）
TRAP_STATE_VALUES = {
    "electric_trap": ["armed", "triggered", "spent"],
    "spike_trap": ["armed", "triggered"],
    "bear_trap": ["armed", "triggered", "spent"],
    "fuel_canister": ["armed", "triggered"],
    "gas_pipe": ["armed", "triggered", "spent"],
    "tripwire_mine": ["armed", "idle", "triggered"],
    "oil_puddle": ["armed", "triggered", "spent"],
    "uv_trap": ["armed", "triggered", "spent"],
    "barbed_wire": ["armed", "triggered"],
}
WEAR_TRAPS = ("spike_trap", "barbed_wire")      # rearm.mode == durable（使うほど傷む）
# 罠の状態ごとの明るさ（無い状態は spec の light_emission）
TRAP_LIGHT = {
    "electric_trap": {"armed": 3, "triggered": 10, "spent": 0},
    "fuel_canister": {"triggered": 9},
    "gas_pipe": {"triggered": 13},
    "oil_puddle": {"triggered": 15, "spent": 0},
    "uv_trap": {"armed": 4, "triggered": 15, "spent": 0},
    "tripwire_mine": {"armed": 1, "idle": 0, "triggered": 6},
}
# 先頭を 1 にする（置いた時から点いている）灯りの状態
DEFAULT_ON = ("nr:lit", "nr:powered")


def state_schema(e) -> Dict[str, list]:
    """ブロックの状態 {名前: [値...]}（先頭が既定）。traits の状態は入れない（block_states が足す）。"""
    if isinstance(e, str):
        e = entry(e)
    st: Dict[str, list] = {}
    for k, vals in (e.get("states") or {}).items():
        vals = list(vals)
        if k in DEFAULT_ON and 1 in vals:
            vals = [1] + [v for v in vals if v != 1]
        st[k] = vals
    if int(e.get("variants", 1)) > 1 and VARIANT not in st:
        st[VARIANT] = list(range(int(e["variants"])))
    t = e.get("trap")
    if t:
        st[TRAP_STATE] = list(TRAP_STATE_VALUES.get(e["key"], ["armed", "triggered"]))
        charges = int((t.get("effect") or {}).get("charges", 0))
        if charges:
            st[CHARGES] = list(range(charges, -1, -1))
        if e["key"] in WEAR_TRAPS or (t.get("rearm") or {}).get("mode") == "durable":
            st[WEAR] = [0, 1, 2, 3]
    return st


def block_states(key: str, facing: Optional[str] = None, **over) -> dict:
    """構造物に置くときの状態の辞書（全部の状態。向きのあるブロックは minecraft:cardinal_direction も）。

    facing = モデルの前が向く方角（north / south / west / east）。None ならエンジンの既定（south）。
    over は状態名の "nr:" を "nr_" に変えたキーワードでも、dict(**{"nr:lit": 0}) でもよい。
    """
    e = entry(key)
    out = {k: v[0] for k, v in state_schema(e).items()}
    if e.get("rotatable", True):
        f = facing or CARDINAL_VALUES[0]
        if f not in CARDINAL_VALUES:
            raise ValueError(f"facing {f} は {CARDINAL_VALUES} のどれか")
        out[CARDINAL] = f
    for k, v in over.items():
        name = k if ":" in k else k.replace("_", ":", 1)
        if name not in out:
            raise KeyError(f"{key}: 状態 {name} は無い（{sorted(out)}）")
        if name != CARDINAL and v not in state_schema(e)[name]:
            raise ValueError(f"{key}: {name}={v!r} は {state_schema(e)[name]} に無い")
        out[name] = v
    return out


def multiblock_parts(name_or_key: str, facing: Optional[str] = None) -> List[Tuple[str, Tuple[int, int, int], dict]]:
    """MULTIBLOCKS の 1 組を積む順に [(ブロック ID, (dx, dy, dz), 状態), ...]。

    name_or_key は MULTIBLOCKS の名前（"street_lamp"）か、その部品のブロックの鍵（"street_lamp_pole"）。
    オフセットはブロック単位で、向きは回さない（facing は各部品の向きの状態に入れるだけ）。
    """
    S = load_spec()
    name = name_or_key[3:] if name_or_key.startswith("nr:") else name_or_key
    if name not in S.MULTIBLOCKS:
        e = entry(name)
        if not e.get("multiblock"):
            raise KeyError(f"{name_or_key} は MULTIBLOCKS の名前でも部品でもない")
        name = e["multiblock"][0]
    out = []
    for bk, off in S.MULTIBLOCKS[name]:
        out.append(("nr:" + bk, tuple(int(v) for v in off), block_states(bk, facing=facing)))
    return out


# ===========================================================================
#  カスタムコンポーネント（スクリプトが登録する。名前・フック・params の形はここが正）
# ===========================================================================
COMPONENT_HOOKS = {
    "nr:trap": dict(hooks=["onTick", "onStepOn", "onPlayerInteract", "onPlace"], tick=[5, 5],
                    doc="罠ブロック全部。params.key で scripts/data/traps.js の TRAP_BY_KEY を引く。"
                        "onTick: 近接・踏み・充電・作動待ち（idle→armed）・作動の終わり（triggered→armed/spent）を見る。"
                        "onStepOn: 踏む罠（当たり箱 ≥4px のもの）。onPlayerInteract: 再装填（rearm.refill を払う）・"
                        "トラバサミを開く。onPlace: arm_ticks のある罠を idle にしてから数える。"),
    "nr:uv_lamp": dict(hooks=["onTick", "onPlayerInteract"], tick=[20, 20],
                       doc="UV ライト。powered==1 の間 radius 内を夜の安全地帯に（夜の捕食者を押し戻す・免疫を戻す）。"
                           "使うと nr:powered を切り替える。"),
    "nr:street_lamp": dict(hooks=["onTick"], tick=[60, 200],
                           doc="街灯の灯具。夜は nr:lit=1、昼は 0。夜にときどき瞬く（flicker の確率で 1 tick 消す）。"),
    "nr:fire_barrel": dict(hooks=["onTick", "onStepOn", "onPlayerInteract"], tick=[10, 20],
                           doc="焚き火のドラム缶。lit==1 で炎のパーティクル・上昇気流・乗った/触れた者を燃やす。"
                               "火打ち石・火のついた物で使うと点く、水で消える。"),
    "nr:stash": dict(hooks=["onPlayerInteract"], tick=None,
                     doc="生存者の隠し箱・救急箱。使うと loot（鍵付きは loot_locked）を出し nr:open=1、"
                         "refill_days 日で補充して閉じる。locked==1 はロックピックかバールが要る。"),
    "nr:craft_bench": dict(hooks=["onPlayerInteract"], tick=None,
                           doc="生存者の作業台。使うと端末の作業台レシピ画面。radius 内なら station=bench のレシピが解禁。"),
    "nr:zipline": dict(hooks=["onPlayerInteract"], tick=None,
                       doc="ジップラインの支柱。使うと視線の先 link_range 内の別のアンカーへ滑車で滑る。"),
    "nr:knockable": dict(hooks=["onPlayerInteract"], tick=None,
                         doc="カラーコーン。使う（蹴る）と state を 0/1 で倒す・起こす（entityHitBlock でも倒してよい）。"),
    "nr:multiblock": dict(hooks=["onPlayerBreak"], tick=None,
                          doc="いくつかのブロックで組む物（街灯・給水塔）の部品。壊れたら同じ組の上の部品も壊す。"),
    "nr:landing": dict(hooks=["onEntityFallOn"], tick=None,
                       doc="ゴミ袋の山。ここへ落ちたプレイヤーの落下ダメージを打ち消す（negate_fall）。"),
    "nr:ambient_fx": dict(hooks=["onTick"], tick=[40, 100],
                          doc="周りに演出のパーティクルを出す（遺骸の蝿・UV キノコの胞子）。particle は nr_registry の ID。"),
    "nr:random_variant": dict(hooks=["beforeOnPlayerPlace"], tick=None,
                              doc="置いた時に state（nr:variant）を 0..count-1 から乱数で選ぶ（瓦礫・血だまり・標識…）。"),
}


def custom_components(e) -> Dict[str, dict]:
    """ブロックが持つカスタムコンポーネント {名前: params}。"""
    if isinstance(e, str):
        e = entry(e)
    key = e["key"]
    st = state_schema(e)
    out: Dict[str, dict] = {}
    t = e.get("trap")
    if t:
        trig = t.get("trigger") or {}
        p = {"key": key, "trigger": trig.get("type", "step"), "state": TRAP_STATE}
        if "radius" in trig:
            p["radius"] = trig["radius"]
        if trig.get("who"):
            p["who"] = trig["who"]
        if CHARGES in st:
            p["charges_state"] = CHARGES
            p["charges"] = st[CHARGES][0]
        if WEAR in st:
            p["wear_state"] = WEAR
        rearm = t.get("rearm") or {}
        if rearm.get("mode"):
            p["rearm"] = rearm["mode"]
        if trig.get("arm_ticks"):
            p["arm_ticks"] = trig["arm_ticks"]
        p["poll"] = e.get("collision") is False or trig.get("type") != "step"
        out["nr:trap"] = p
    inter = e.get("interact")
    if inter == "toggle_power" or key == "uv_lamp":
        out["nr:uv_lamp"] = {"state": "nr:powered", "radius": float(e.get("safe_radius", 10)),
                             "immunity_regen_per_s": float(e.get("immunity_regen_per_s", 10)),
                             "repel_night": bool(e.get("repel_night", True))}
    if key == "street_lamp_head":
        out["nr:street_lamp"] = {"state": "nr:lit", "flicker": 0.06}
    if key == "fire_barrel":
        out["nr:fire_barrel"] = {"state": "nr:lit", "burn_on_touch": int(e.get("burn_on_touch", 1)),
                                 "particle": e.get("ambient_particle", "nr:flame"),
                                 "updraft_height": e.get("updraft_height", 6),
                                 "updraft_strength": e.get("updraft_strength", 0.2)}
    if inter == "open_stash":
        p = {"loot": e.get("loot"), "refill_days": int(e.get("refill_days", 3)), "open_state": "nr:open"}
        if e.get("loot_locked"):
            p["loot_locked"] = e["loot_locked"]
        if "nr:locked" in st:
            p["lock_state"] = "nr:locked"
        out["nr:stash"] = p
    if inter == "open_bench":
        out["nr:craft_bench"] = {"radius": 4}
    if inter == "zipline":
        out["nr:zipline"] = {"link_range": int(e.get("link_range", 48)), "ride_speed": float(e.get("ride_speed", 0.75)),
                             "min_drop": float(e.get("min_drop", 0.0))}
    if "nr:fallen" in st:
        out["nr:knockable"] = {"state": "nr:fallen"}
    if e.get("multiblock"):
        out["nr:multiblock"] = {"group": e["multiblock"][0], "part": int(e["multiblock"][1])}
    if e.get("negate_fall") or "landing" in (e.get("parkour") or []):
        out["nr:landing"] = {"negate_fall": True}
    amb = e.get("ambient_particle")
    if key == "uv_shroom_patch":
        amb = amb or "nr:uv_glow"
    if amb and key != "fire_barrel":
        out["nr:ambient_fx"] = {"particle": amb, "chance": 0.6}
    if VARIANT in st:
        out["nr:random_variant"] = {"state": VARIANT, "count": len(st[VARIANT])}
    return out


# ===========================================================================
#  BP の JSON
# ===========================================================================
MENU = {"barricade": "construction", "street": "construction", "debris": "construction",
        "parkour": "construction", "decor": "construction", "rooftop": "construction", "gore": "construction",
        "light": "items", "container": "items", "station": "items", "trap": "items", "nature": "nature"}
ROTATION = {"west": [0, 90, 0], "south": [0, 180, 0], "east": [0, -90, 0]}
EMPTY_LOOT = ("blood_pool", "debris_scatter", "oil_puddle")


def _fmt(v) -> str:
    return f"'{v}'" if isinstance(v, str) else str(int(v))


def collision_of(e):
    """当たり箱（踏む罠は onStepOn が来るよう高さ ≥4px に）。"""
    col = e.get("collision")
    if col is False or col is None:
        return False
    col = {"origin": list(col["origin"]), "size": list(col["size"])}
    t = e.get("trap")
    if t and (t.get("trigger") or {}).get("type") == "step" and col["size"][1] < 4:
        col["size"][1] = 4
    return col


def light_rules(e) -> Tuple[int, List[Tuple[str, int]]]:
    """(既定の状態での明るさ, [(条件, 明るさ), ...])。"""
    st = state_schema(e)
    base = int(e.get("light_emission", 0))
    rules: List[Tuple[str, int]] = []
    for s in ("nr:lit", "nr:powered"):
        if s in st:
            rules.append((f"q.block_state('{s}') == 0", 0))
    if e.get("trap"):
        table = TRAP_LIGHT.get(e["key"], {})
        default = st[TRAP_STATE][0]
        base = int(table.get(default, base))
        for v in st[TRAP_STATE]:
            lv = int(table.get(v, int(e.get("light_emission", 0))))
            if v != default and lv != base:
                rules.append((f"q.block_state('{TRAP_STATE}') == '{v}'", lv))
        if e["key"] == "electric_trap":
            rules.append((f"q.block_state('{TRAP_STATE}') == 'armed' && q.block_state('{CHARGES}') == 0", 0))
    return base, rules


def block_json(e, info) -> dict:
    """info = build_one() の戻り（geo の bone_visibility・render_method）。"""
    key = e["key"]
    st = state_schema(e)
    desc = {"identifier": e["id"], "menu_category": {"category": MENU.get(e.get("category"), "construction")}}
    if st:
        desc["states"] = {k: list(v) for k, v in st.items()}
    if e.get("rotatable", True):
        desc["traits"] = {"minecraft:placement_direction": {"enabled_states": [CARDINAL], "y_rotation_offset": 180}}
    geo = {"identifier": e["geometry"]}
    if info["bone_visibility"]:
        geo["bone_visibility"] = dict(info["bone_visibility"])
    comps = {
        "minecraft:geometry": geo if len(geo) > 1 else e["geometry"],
        "minecraft:material_instances": {"*": {"texture": f"nr_{key}", "render_method": info["render"]}},
        "minecraft:collision_box": collision_of(e),
        "minecraft:selection_box": {"origin": list(e["selection"]["origin"]), "size": list(e["selection"]["size"])},
        "minecraft:light_dampening": 0,
        "minecraft:map_color": e["map_color"],
    }
    base, rules = light_rules(e)
    if base:
        comps["minecraft:light_emission"] = base
    dt = float(e.get("destroy_time", 1.5))
    comps["minecraft:destructible_by_mining"] = {"seconds_to_destroy": dt} if dt >= 0 else False
    if dt < 0:
        comps["minecraft:destructible_by_explosion"] = False
    else:
        comps["minecraft:destructible_by_explosion"] = {"explosion_resistance": float(e.get("blast_resistance", 3.0))}
    if e.get("flammable"):
        comps["minecraft:flammable"] = {"catch_chance_modifier": 5, "destroy_chance_modifier": 20}
    if e.get("loot") or key in EMPTY_LOOT:
        comps["minecraft:loot"] = f"{LOOT_REL}/{key}.json"
    cc = custom_components(e)
    ticks = [COMPONENT_HOOKS[c]["tick"] for c in cc if COMPONENT_HOOKS[c]["tick"]]
    if ticks:
        lo = min(t[0] for t in ticks)
        hi = min(t[1] for t in ticks)
        comps["minecraft:tick"] = {"interval_range": [lo, max(lo, hi)], "looping": True}
    if any("onEntityFallOn" in COMPONENT_HOOKS[c]["hooks"] for c in cc):
        comps["minecraft:entity_fall_on"] = {"min_fall_distance": 1}
    for name in sorted(cc):
        comps[name] = cc[name]
    perms = []
    for cond, lv in rules:
        perms.append({"condition": cond, "components": {"minecraft:light_emission": int(lv)}})
    if e.get("rotatable", True):
        for d in ("west", "south", "east"):
            perms.append({"condition": f"q.block_state('{CARDINAL}') == '{d}'",
                          "components": {"minecraft:transformation": {"rotation": list(ROTATION[d])}}})
    body = {"description": desc, "components": comps}
    if perms:
        body["permutations"] = perms
    return {"format_version": BLOCK_FORMAT, "minecraft:block": body}


def recipe_json(e) -> Optional[dict]:
    r = e.get("recipe")
    if not r:
        return None
    if r["type"] == "shaped":
        refs = [r["keys"][ch] for row in r["pattern"] for ch in row if ch != " "]
    else:
        refs = [i for i, _ in r["ingredients"]]
    unlock_ref = next((x for x in refs if x.startswith("nr:")), refs[0])
    body = {"description": {"identifier": f"nr:craft_block_{e['key']}"}, "tags": ["crafting_table"]}
    if r["type"] == "shaped":
        body["pattern"] = list(r["pattern"])
        body["key"] = {ch: {"item": ref} for ch, ref in sorted(r["keys"].items())}
    else:
        body["ingredients"] = [({"item": i, "count": n} if n > 1 else {"item": i}) for i, n in r["ingredients"]]
    body["unlock"] = [{"item": unlock_ref}]
    body["result"] = {"item": e["id"], "count": int(r.get("count", 1))}
    kind = "minecraft:recipe_shaped" if r["type"] == "shaped" else "minecraft:recipe_shapeless"
    return {"format_version": RECIPE_FORMAT, kind: body}


def loot_json(table) -> dict:
    """[(ID, 最小, 最大, 確率)] → ルートテーブル（1 行 = 1 プール、random_chance）。"""
    pools = []
    for ident, lo, hi, chance in table or []:
        ent = {"type": "item", "name": ident, "weight": 1}
        if (lo, hi) != (1, 1):
            ent["functions"] = [{"function": "set_count", "count": {"min": int(lo), "max": int(hi)}}]
        pool = {"rolls": 1, "entries": [ent]}
        if chance < 1.0:
            pool["conditions"] = [{"condition": "random_chance", "chance": round(float(chance), 4)}]
        pools.append(pool)
    return {"pools": pools}


# ===========================================================================
#  モデルとテクスチャ
# ===========================================================================
def _cube_corners(c: dict) -> np.ndarray:
    o = np.array(c["origin"], float)
    s = np.array(c["size"], float)
    inf = float(c.get("inflate", 0) or 0)
    a, b = o - inf, o + s + inf
    pts = np.array([[x, y, z] for x in (a[0], b[0]) for y in (a[1], b[1]) for z in (a[2], b[2])])
    if c.get("rotation"):
        import nr_preview as PV
        R = PV.rot(*[float(v) for v in c["rotation"]])
        piv = np.array(c.get("pivot") or (o + s / 2), float)
        pts = (R @ (pts - piv).T).T + piv
    return pts


def geo_bounds(geo: dict, vis_ok=None) -> Tuple[np.ndarray, np.ndarray]:
    """ジオメトリ全体（ボーンの回転も）の (最小, 最大)。vis_ok(bone) が偽のボーンは除く。"""
    import nr_preview as PV
    g = PV.load_geometry({"format_version": "1.16.0", "minecraft:geometry": [geo]})
    W = PV.bone_matrices(g)
    pts = []
    for bi, bdoc in enumerate(geo["bones"]):
        if vis_ok and not vis_ok(bdoc["name"]):
            continue
        for c in bdoc.get("cubes", []):
            p = _cube_corners(c)
            M = W[g.find(bdoc["name"])]
            pts.append((M[:3, :3] @ p.T).T + M[:3, 3])
    if not pts:
        return np.zeros(3), np.zeros(3)
    P = np.concatenate(pts)
    return P.min(0), P.max(0)


def used_mask(geo: dict, W: int, H: int) -> np.ndarray:
    m = np.zeros((H, W), bool)
    for b in geo["bones"]:
        for c in b.get("cubes", []):
            uv = c.get("uv")
            if not isinstance(uv, dict):
                continue
            for f in uv.values():
                u0, v0 = (int(round(x)) for x in f["uv"])
                du, dv = (int(round(x)) for x in f["uv_size"])
                x0, x1 = sorted((u0, u0 + du))
                y0, y1 = sorted((v0, v0 + dv))
                m[max(0, y0):min(H, y1), max(0, x0):min(W, x1)] = True
    return m


def build_one(e, write=True, log=None) -> dict:
    """1 ブロックを作って（write なら）ジオメトリと PNG を書く。確認用の情報を返す。"""
    key = e["key"]
    seed = stable_hash("nr_block:" + key) & 0xFFFF
    st = state_schema(e)
    bm = BM.build(key, e, seed=seed, states=st)
    if bm.cube_count() > MAX_CUBES:
        raise ValueError(f"{key}: キューブ {bm.cube_count()} 個（≤{MAX_CUBES}）")
    bm.pack()
    img = bm.paint(seed=seed)
    geo = bm.to_json()
    arr = np.array(img)
    a = arr[..., 3]
    render = e.get("render", "opaque")
    W, H = img.size
    if W > MAX_TEX or H > MAX_TEX:
        raise ValueError(f"{key}: テクスチャ {W}x{H}（≤{MAX_TEX}）")
    used = used_mask(geo, W, H)
    if render != "blend":
        # ブロックは画素で光れない: 発光の印（α 16/160）を不透明に戻す
        a = np.where(a > 0, 255, 0).astype(np.uint8)
        if render == "opaque" and bool(((a == 0) & used).any()):
            render = "alpha_test"
    arr[..., 3] = a
    arr[a == 0, :3] = 0
    img = Image.fromarray(arr, "RGBA")
    # 状態の式（vis）が状態の表にある名前・値だけを使っているか
    for bone, cond in bm.vis.items():
        for s, vals in cond.items():
            if s not in st:
                raise ValueError(f"{key}: ボーン {bone} の条件の状態 {s} が無い（{sorted(st)}）")
            for v in vals:
                if v not in st[s]:
                    raise ValueError(f"{key}: ボーン {bone} の条件 {s}={v!r} は {st[s]} に無い")
    bvis = bm.bone_visibility()
    # 形の大きさ（rendering.md §8: 30×30×30 px・原点から 30px 以内・自分のマスと重なる）
    lo, hi = geo_bounds(geo)
    size = hi - lo
    if (size > 30.001).any() or (np.abs(np.concatenate([lo, hi])) > 30.001).any():
        raise ValueError(f"{key}: 形 {np.round(lo, 2).tolist()}〜{np.round(hi, 2).tolist()} が 30px を超える")
    if not (lo[0] < 8 and hi[0] > -8 and lo[1] < 16 and hi[1] > 0 and lo[2] < 8 and hi[2] > -8):
        raise ValueError(f"{key}: 形が自分のマスと重ならない")
    info = {"key": key, "geo": geo, "img": img, "render": render, "bone_visibility": bvis, "vis": dict(bm.vis),
            "cubes": bm.cube_count(), "tex": (W, H), "scale": bm.scale, "notes": list(bm.notes),
            "bounds": (lo.tolist(), hi.tolist())}
    if write:
        write_geometry(os.path.join(GEO_DIR, f"{key}.geo.json"), _GeoDoc(geo, W, H))
        os.makedirs(TEX_DIR, exist_ok=True)
        NP.save_png(img, os.path.join(TEX_DIR, f"{key}.png"), quantize=True)
    return info


class _GeoDoc:
    """write_geometry に渡す包み（to_json 済みの辞書）。"""

    def __init__(self, doc, w, h):
        self.doc, self.tex_w, self.tex_h = doc, w, h

    def to_json(self):
        return self.doc


# ===========================================================================
#  確認用の画像
# ===========================================================================
def vis_ok_fn(vis: Dict[str, Dict[str, list]], states: dict):
    def ok(bone):
        cond = vis.get(bone)
        return cond is None or BM.vis_eval(cond, states)
    return ok


_GROUND = {}


def ground_part(n=3, kind="sidewalk"):
    """地面（確認用。n マス（小数なら半端も）の床、タイルの目地はマスの境に合わせる）。"""
    k = (n, kind)
    if k in _GROUND:
        return _GROUND[k]
    from mcmodel import Cube, Model
    m = Model("geometry.nr.preview_ground", uv_scale=2, max_atlas=(1024, 1024))
    b = m.bone("root")
    half = n * 8
    c = Cube((-half, -2, -half), (2 * half, 2, 2 * half), "g")
    c.decals = {"up": [{"name": "nrb_tiles", "step": 16.0, "off": (half - 8) % 16},
                       {"name": "grime", "amount": 0.5}, {"name": "cracks", "amount": 0.4}]}
    b.add(c)
    m.pack()
    st = {"g": NP.style("concrete", base="#6e6e6a", cracks=0.4, dirt=0.55)}
    img = NP.paint_model(m, st, seed=5)
    _GROUND[k] = (m.to_json(), img)
    return _GROUND[k]


def merge_parts(parts) -> Tuple[dict, Image.Image]:
    """[(geo, img, offset_px(x,y,z), yaw_deg, vis_ok), ...] → 1 つのジオメトリと縦に積んだアトラス。"""
    Wt = max(im.size[0] for _, im, *_ in parts)
    Ht = sum(im.size[1] for _, im, *_ in parts)
    atlas = Image.new("RGBA", (Wt, Ht), (0, 0, 0, 0))
    bones = []
    y0 = 0
    for i, (geo, im, off, yaw, ok) in enumerate(parts):
        atlas.paste(im, (0, y0))
        sx = im.size[0] / float(geo["description"]["texture_width"])
        sy = im.size[1] / float(geo["description"]["texture_height"])
        ox, oy, oz = (float(v) for v in off)
        root = f"p{i}"
        bones.append({"name": root, "pivot": [ox, oy, oz], "rotation": [0, float(yaw), 0]})
        for b in geo["bones"]:
            if ok and not ok(b["name"]):
                continue
            nb = {"name": f"p{i}_{b['name']}", "parent": f"p{i}_{b['parent']}" if b.get("parent") else root,
                  "pivot": [b["pivot"][0] + ox, b["pivot"][1] + oy, b["pivot"][2] + oz]}
            if b.get("rotation"):
                nb["rotation"] = list(b["rotation"])
            cubes = []
            for c in b.get("cubes", []):
                nc = dict(c)
                nc["origin"] = [c["origin"][0] + ox, c["origin"][1] + oy, c["origin"][2] + oz]
                if c.get("pivot"):
                    nc["pivot"] = [c["pivot"][0] + ox, c["pivot"][1] + oy, c["pivot"][2] + oz]
                uv = {}
                for f, r in c["uv"].items():
                    uv[f] = {"uv": [r["uv"][0] * sx, r["uv"][1] * sy + y0], "uv_size": [r["uv_size"][0] * sx,
                                                                                    r["uv_size"][1] * sy]}
                nc["uv"] = uv
                cubes.append(nc)
            if cubes:
                nb["cubes"] = cubes
            bones.append(nb)
        y0 += im.size[1]
    doc = {"format_version": "1.16.0", "minecraft:geometry": [{
        "description": {"identifier": "geometry.nr.preview_scene", "texture_width": Wt, "texture_height": Ht},
        "bones": bones}]}
    return doc, atlas


# 地面の目地（確認用のデカール。nr_block_paint の流儀）
def _d_tiles(fc, d):
    step = float(d.get("step", 16.0)) * fc.s
    off = float(d.get("off", 0.0)) * fc.s
    x = (fc.px - off) % step
    y = (fc.py - off) % step
    joint = (x < 1.0) | (y < 1.0)
    fc.mul(joint, 0.62)
    fc.mul((x >= 1.0) & (x < 2.0) | (y >= 1.0) & (y < 2.0), 1.12)


NP.DECALS["nrb_tiles"] = _d_tiles


def render_block(info, states=None, size=300, yaw=35.0, pitch=26.0, ground=1.5, facing_yaw=0.0):
    import nr_preview as PV
    st = dict(states) if states else {k: v[0] for k, v in state_schema(entry(info["key"])).items()}
    parts = []
    if ground:
        g, gi = ground_part(ground)
        parts.append((g, gi, (0, 0, 0), 0.0, None))
    parts.append((info["geo"], info["img"], (0, 0, 0), facing_yaw, vis_ok_fn(info["vis"], st)))
    doc, atlas = merge_parts(parts)
    cam = PV.Camera(yaw=yaw, pitch=pitch, margin=0.04)
    return PV.render(doc, atlas, camera=cam, size=size, bg=(30, 31, 36), ss=2, alpha_test=1)


def _state_label(st: dict) -> str:
    return " ".join(f"{k.split(':')[1]}={v}" for k, v in st.items() if k != CARDINAL)


def state_variants(key) -> List[dict]:
    """確認用: 見た目が変わる状態の組み合わせ（各状態を 1 つずつ動かす）。"""
    e = entry(key)
    st = state_schema(e)
    base = {k: v[0] for k, v in st.items()}
    out = []
    for k, vals in st.items():
        if k == CHARGES:
            vals = [vals[0], vals[-1]]
        for v in vals[1:]:
            s = dict(base)
            s[k] = v
            out.append(s)
    return out


def write_previews(infos: Dict[str, dict], keys: Sequence[str]):
    import nr_preview as PV
    os.makedirs(SCRATCH, exist_ok=True)
    tiles = []
    for k in keys:
        info = infos[k]
        im = render_block(info)
        lab = f"{k}  {info['cubes']}c {info['tex'][0]}x{info['tex'][1]}@{info['scale']} {info['render']}"
        tiles.append((lab, im))
    # 複数マスの物（組んだ姿）
    S = load_spec()
    for name, rows in S.MULTIBLOCKS.items():
        if not all(bk in infos for bk, _ in rows):
            continue
        parts = []
        g, gi = ground_part(5 if name == "water_tower" else 3)
        parts.append((g, gi, (0, 0, 0), 0.0, None))
        for bk, (dx, dy, dz) in rows:
            info = infos[bk]
            st = {kk: v[0] for kk, v in state_schema(entry(bk)).items()}
            off = (dx * 16 - (24 if name == "water_tower" else 0), dy * 16, dz * 16 - (24 if name == "water_tower" else 0))
            parts.append((info["geo"], info["img"], off, 0.0, vis_ok_fn(info["vis"], st)))
        doc, atlas = merge_parts(parts)
        im = PV.render(doc, atlas, camera=PV.Camera(yaw=35, pitch=20, margin=0.04), size=300, bg=(30, 31, 36),
                       ss=2)
        tiles.append((f"MULTIBLOCK {name}", im))
    sheet = PV.contact_sheet(tiles, cols=7, title="NIGHT RUNNER blocks (3/4, default state)")
    sheet.save(os.path.join(SCRATCH, "blocks.png"))
    # 状態違い
    st_tiles = []
    for k in keys:
        for s in state_variants(k):
            st_tiles.append((f"{k}: {_state_label(s)}", render_block(infos[k], s, size=220)))
    if st_tiles:
        PV.contact_sheet(st_tiles, cols=8, title="block states").save(os.path.join(SCRATCH, "blocks_states.png"))
    return os.path.join(SCRATCH, "blocks.png")


def write_scene(infos: Dict[str, dict]):
    """通りの一角に並べた確認用の場面（向きも混ぜる）。"""
    import nr_preview as PV
    layout = [
        ("road_barrier", (-3, 0, -2), 0), ("road_barrier", (-2, 0, -2), 0), ("sandbags", (-1, 0, -2), 0),
        ("barricade", (1, 0, -2), 0), ("metal_barricade", (2, 0, -2), 0), ("traffic_cone", (0, 0, -3), 0),
        ("traffic_cone", (-1, 0, -3), 0), ("uv_lamp", (0, 0, 0), 0), ("fire_barrel", (2, 0, 1), 0),
        ("trash_bags", (-3, 0, 1), 0), ("tire_stack", (-2, 0, 2), 0), ("rubble_pile", (3, 0, 2), 0),
        ("blood_pool", (0, 0, 1), 0), ("spike_trap", (-1, 0, -1), 0), ("bear_trap", (1, 0, -1), 0),
        ("electric_trap", (-2, 0, 0), 0), ("fuel_canister", (2, 0, 0), 0), ("wooden_crate", (3, 0, 0), 0),
        ("crafting_bench", (-3, 0, 3), 180), ("survivor_stash", (0, 0, 3), 180), ("gore_remains", (1, 0, 2), 0),
        ("ac_unit", (-1, 0, 3), 180), ("debris_scatter", (-1, 0, 1), 0), ("barbed_wire", (1, 0, -3), 0),
    ]
    S = load_spec()
    parts = []
    g, gi = ground_part(8)
    parts.append((g, gi, (0, 0, 0), 0.0, None))
    for k, (bx, by, bz), yaw in layout:
        if k not in infos:
            continue
        st = {kk: v[0] for kk, v in state_schema(entry(k)).items()}
        parts.append((infos[k]["geo"], infos[k]["img"], (bx * 16, by * 16, bz * 16), yaw,
                      vis_ok_fn(infos[k]["vis"], st)))
    if all(bk in infos for bk, _ in S.MULTIBLOCKS["street_lamp"]):
        for bk, (dx, dy, dz) in S.MULTIBLOCKS["street_lamp"]:
            st = {kk: v[0] for kk, v in state_schema(entry(bk)).items()}
            parts.append((infos[bk]["geo"], infos[bk]["img"], ((dx - 3) * 16, dy * 16, (dz - 3) * 16), 180,
                          vis_ok_fn(infos[bk]["vis"], st)))
    doc, atlas = merge_parts(parts)
    im = PV.render(doc, atlas, camera=PV.Camera(yaw=30, pitch=32, margin=0.03), size=(1400, 1000),
                   bg=(26, 27, 32), ss=2)
    p = os.path.join(SCRATCH, "blocks_scene.png")
    im.save(p)
    return p


# ===========================================================================
#  本体
# ===========================================================================
def write_cache(blocks: List[dict]):
    used: Dict[str, dict] = {}
    for e in blocks:
        for name, params in custom_components(e).items():
            u = used.setdefault(name, {"hooks": COMPONENT_HOOKS[name]["hooks"],
                                       "tick_interval": COMPONENT_HOOKS[name]["tick"],
                                       "doc": COMPONENT_HOOKS[name]["doc"], "blocks": {}})
            u["blocks"][e["id"]] = params
    doc = {
        "_note": "gen_nr_blocks.py が書く。BP のブロックが使うカスタムコンポーネント（Custom Components V2）。"
                 "スクリプトは system.beforeEvents.startup で全部を blockComponentRegistry.registerCustomComponent すること"
                 "（登録の無い名前があるとブロックが読み込めない）。params は JSON のまま。",
        "components": {k: used[k] for k in sorted(used)},
        "states": {e["id"]: {"schema": state_schema(e), "default": block_states(e["key"])} for e in blocks},
        "trap_state": TRAP_STATE, "trap_state_values": TRAP_STATE_VALUES, "cardinal_state": CARDINAL,
    }
    write_json(CACHE, doc)
    return sorted(used)


def write_data_js(blocks: List[dict]):
    defs = {}
    for e in blocks:
        base, rules = light_rules(e)
        defs[e["id"]] = {"key": e["key"], "states": state_schema(e), "defaults": block_states(e["key"]),
                         "rotatable": bool(e.get("rotatable", True)), "components": custom_components(e),
                         "light": base, "trap": bool(e.get("trap")),
                         "collision": collision_of(e) is not False}
    lines = ["// このファイルは生成物です（tools/nightrunner/gen_nr_blocks.py）。直接編集しないでください。",
             "// ブロックの状態（先頭が既定値）・カスタムコンポーネントの params・向きの状態の名前。",
             "/** @type {Record<string, any>} */",
             f"export const BLOCK_DEFS = {js_literal(defs)};",
             f"export const TRAP_STATE = {js_literal(TRAP_STATE)};",
             f"export const CARDINAL_STATE = {js_literal(CARDINAL)};",
             "/** @type {Record<string, string[]>} */",
             f"export const TRAP_STATE_VALUES = {js_literal(TRAP_STATE_VALUES)};",
             "/** @type {Record<string, string[]>} */",
             f"export const BLOCK_COMPONENT_HOOKS = {js_literal({k: v['hooks'] for k, v in COMPONENT_HOOKS.items()})};"]
    write_text(DATA_JS, "\n".join(lines) + "\n")


def _clean_dir(folder, keep_names, ext):
    """自分のフォルダから、今回書かないファイルを消す（消した鍵の残骸を残さない）。"""
    if not os.path.isdir(folder):
        return
    for f in os.listdir(folder):
        if f.endswith(ext) and f[: -len(ext)] not in keep_names:
            os.remove(os.path.join(folder, f))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", default="", help="この鍵だけ（カンマ区切り）。断片・データは全部書き直す")
    ap.add_argument("--no-preview", action="store_true", help="確認用の画像を描かない")
    ap.add_argument("--scene", action="store_true", help="通りの場面の画像も描く")
    ap.add_argument("--sheet-only", action="store_true", help="パックに書かず画像だけ")
    args = ap.parse_args(argv)
    t0 = time.time()
    blocks = all_blocks()
    keys = [e["key"] for e in blocks]
    if len(set(keys)) != len(keys):
        raise SystemExit("ブロックの鍵が重複している")
    only = [k.strip() for k in args.only.split(",") if k.strip()]
    for k in only:
        if k not in keys:
            raise SystemExit(f"--only {k}: そんなブロックは無い")
    write = not args.sheet_only
    infos: Dict[str, dict] = {}
    tex_frag, blocks_frag = {}, {}
    lang = {"ja_JP": {}, "en_US": {}}
    for e in blocks:
        k = e["key"]
        if not only or k in only:
            infos[k] = build_one(e, write=write)
        tex_frag[f"nr_{k}"] = {"textures": TEX_REF + k}
        blocks_frag[e["id"]] = {"sound": e["sound"]}
        lang["ja_JP"][f"tile.{e['id']}.name"] = e["ja"]
        lang["en_US"][f"tile.{e['id']}.name"] = e["en"]
    if write:
        if not only:
            _clean_dir(GEO_DIR, set(keys), ".geo.json")
            _clean_dir(TEX_DIR, set(keys), ".png")
        S = load_spec()
        recipe_keys, loot_keys = set(), set()
        for e in blocks:
            k = e["key"]
            info = infos.get(k)
            if info is None:     # --only の外: 既に書いた JSON の render_method を読み戻す
                p = os.path.join(BLOCK_DIR, f"{k}.json")
                if os.path.exists(p):
                    with open(p, encoding="utf-8") as fh:
                        old = json.load(fh)["minecraft:block"]["components"]
                    geo = old["minecraft:geometry"]
                    info = {"render": old["minecraft:material_instances"]["*"]["render_method"],
                            "bone_visibility": geo.get("bone_visibility", {}) if isinstance(geo, dict) else {}}
                else:
                    info = build_one(e, write=True)
                    infos[k] = info
            write_json(os.path.join(BLOCK_DIR, f"{k}.json"), block_json(e, info))
            r = recipe_json(e)
            if r:
                write_json(os.path.join(RECIPE_DIR, f"{k}.json"), r)
                recipe_keys.add(k)
            if e.get("loot") or k in EMPTY_LOOT:
                write_json(os.path.join(LOOT_DIR, f"{k}.json"), loot_json(S.LOOT_TABLES.get(e.get("loot")) or []))
                loot_keys.add(k)
            if e.get("loot_locked"):
                write_json(os.path.join(LOOT_DIR, f"{k}_locked.json"), loot_json(S.LOOT_TABLES[e["loot_locked"]]))
                loot_keys.add(f"{k}_locked")
        _clean_dir(BLOCK_DIR, set(keys), ".json")
        _clean_dir(RECIPE_DIR, recipe_keys, ".json")
        _clean_dir(LOOT_DIR, loot_keys, ".json")
        frag("terrain_texture", PRODUCER, tex_frag)
        frag("blocks", PRODUCER, blocks_frag)
        frag("lang", PRODUCER, lang)
        comps = write_cache(blocks)
        write_data_js(blocks)
        print(f"[gen_nr_blocks] ブロック {len(blocks)}（作り直し {len(infos)}）・レシピ {len(recipe_keys)}・"
              f"ルート {len(loot_keys)}・カスタムコンポーネント {len(comps)}: {', '.join(comps)}")
    for k, info in infos.items():
        print(f"  {k:18s} {info['cubes']:2d} cubes  tex {info['tex'][0]}x{info['tex'][1]}@{info['scale']}  "
              f"{info['render']:10s} {'generic' if 'generic' in info['notes'] else ''}")
    if not args.no_preview and infos:
        order = [k for k in keys if k in infos]
        p = write_previews(infos, order)
        print(f"[gen_nr_blocks] 確認用: {p}")
        if args.scene or not only:
            print(f"[gen_nr_blocks] 場面: {write_scene(infos)}")
    print(f"[gen_nr_blocks] {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
