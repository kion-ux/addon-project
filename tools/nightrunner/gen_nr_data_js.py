# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — `packs/nightrunner_BP/scripts/data/*.js`（spec と演出 ID の登録簿を JS へ）。

手書きのスクリプトは数値・名前・語彙をここから import する（DESIGN.md §12）。書くファイルと export:

| ファイル | export |
|---|---|
| `zombies.js` | `ZOMBIES`（ztype の順の配列。spec の全フィールド + `id` `ztype` + 下の派生）、`ZTYPE`（key→番号）、`ZOMBIE_BY_KEY`、`ZOMBIE_BY_ID`、`ABILITIES`、`ATTACKS`、`LOCOMOTIONS`、`VOICES`、`GORE_KEYS`、`GORE_DEFAULTS`、`ABILITY_STATES`、ほか語彙 |
| `weapons.js` | `WEAPONS`（配列）、`WEAPON_BY_ID`、`PROJECTILES`、`PROJECTILE_BY_ID`、`WEAPON_CLASSES`、`ANIM_SETS`、`SFX_SETS`、`RARITY` |
| `items.js` | `ITEMS`（MATERIAL_ITEMS + ITEMS をこの順で一つに）、`ITEM_BY_ID`、`SHARED_ITEM_IDS`、`ITEM_KINDS`、`RARITY`、`ZOMBIE_SOURCED` |
| `mods.js` | `MODS`、`MOD_BY_KEY` |
| `traps.js` | `TRAPS`、`TRAP_BY_ID`、`TRAP_BLOCKS` |
| `blocks.js` | `BLOCKS`、`BLOCK_BY_ID`、`MULTIBLOCKS` |
| `props.js` | `PROPS`、`PROP_BY_ID`、`PROP_INTERACTIONS` |
| `skills.js` | `SKILLS`、`SKILL_BY_KEY`、`PROGRESSION`、`XP_TO_NEXT`（添字 = レベル） |
| `crafting.js` | `CRAFTING`、`CRAFT_CATEGORIES` |
| `settings.js` | `SETTINGS_DEFAULTS`、`SETTINGS_SCHEMA`、`PARKOUR_TUNING`、`COMBAT_TUNING`、`GORE_TUNING`、`DIFFICULTY`、`GORE_COMBOS`、`STARTER_KIT`、`LOOT_TABLES`、`DTYPE_OUTCOMES`、`ABILITY_STATES`、`CITY` |
| `fx.js` | `PARTICLES`（名前の配列）、`SOUNDS`（ID の配列）、`PLAYER_ANIMS`（{名前: 長さ秒}）、`ZOMBIE_ONESHOTS`（{名前: 長さ秒 or null}）、`ZOMBIE_ANIMATIONS`（{key: zombie_animations(z)}）、`VOICE_EVENTS` |

約束:

* 値は spec の表をそのまま JSON にしたもの（タプルは配列）。**見た目だけの部品（`model` / `wing_model`、モデラー向けの
  `P(...)` のリスト）は出さない**（数十 KB 減る）。それ以外のフィールドは全部残す。
* `ZOMBIES[i]` に足す派生フィールド: `id`（nr:z_<key>）、`ztype`、`ability_keys`、`ability_params`（{能力: 語彙の既定 +
  上書き}）、`ability_states`（{"能力.段階": 1..7}）、`all_attacks`、`initial_armor`、`collision`（[幅, 高さ]）。
* `ITEMS[i]` に足す派生フィールド: `engine_consumes`（true = BP の `minecraft:food` で**エンジンが 1 個減らす**。
  スクリプトは `itemCompleteUse` で効果だけ与え、自分で数を減らさない。false = スクリプトが減らす）と
  `use_seconds`（使う時間。無ければ 0）。決め方は gen_nr_items.engine_consumes()。
* `*_BY_ID` / `*_BY_KEY` は同じオブジェクトを指す索引で、JS の式（`Object.fromEntries(...)`）で作る（重複して書かない）。
* fx.js は登録簿（nr_registry）が正。ただし作る側が登録簿より**増やした** ID（RP のパーティクル・音の断片と
  sound_definitions・アニメーションに実在するもの）も後ろに足す（登録簿の約束「増やしたら data JS にも出る」）。
  アニメの長さは登録簿の値、登録簿に無いものは RP の `animation_length`。
* 1 行 1 export（`export const X = <JSON>;`）。validate_nr / test_nr はこの形を読む。各 export の前の行に
  JSDoc の型（配列は `any[]`、辞書は `Record<string, any>` など）を付け、巨大なリテラルの型推論で
  tsc が遅くなったり、要素ごとの型の食い違いで手書き側が型エラーになったりしないようにする。
* 決定的: 並びは spec の並び（辞書は挿入順）、足した ID は名前順。

使い方: `python3 tools/nightrunner/gen_nr_data_js.py`（普通は build_nr.py から。zombies・entities の後）。
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nr_common import DATA_JS, HERE, RP, load_json, read_frags, write_text  # noqa: E402
import nr_registry as REG  # noqa: E402

PRODUCER = "gen_nr_data_js"
HEADER = "// このファイルは生成物です（tools/nightrunner/gen_nr_data_js.py）。直接編集しないでください。"
# 見た目だけの部品（モデラー向け）。スクリプトは使わないので出さない
VISUAL_ONLY = ("model", "wing_model")
FILES = ("zombies", "weapons", "items", "mods", "traps", "blocks", "props", "skills", "crafting",
         "settings", "fx")


# ---------------------------------------------------------------------------
#  spec の読み込み（nr_spec.py があればそれ、無ければ二つの spec を一つの名前空間に）
# ---------------------------------------------------------------------------
def load_spec():
    if os.path.exists(os.path.join(HERE, "nr_spec.py")):
        import nr_spec
        return nr_spec
    import nr_spec_catalog
    import nr_spec_zombies
    ns = types.SimpleNamespace()
    # 両方にある名前（DTYPES）は同じ値。ゾンビ側を後に入れる
    for mod in (nr_spec_catalog, nr_spec_zombies):
        for name in getattr(mod, "__all__", [n for n in dir(mod) if not n.startswith("_")]):
            setattr(ns, name, getattr(mod, name))
    return ns


# ---------------------------------------------------------------------------
#  JSON 化（タプル → 配列。キーは文字列だけ、数は有限だけ。違えば止める）
# ---------------------------------------------------------------------------
def jsonable(v, path="$"):
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if not isinstance(k, str):
                raise TypeError(f"{path}: 辞書のキー {k!r} が文字列でない（JSON にできない）")
            out[k] = jsonable(x, f"{path}.{k}")
        return out
    if isinstance(v, (list, tuple)):
        return [jsonable(x, f"{path}[{i}]") for i, x in enumerate(v)]
    if isinstance(v, (set, frozenset)):
        return sorted((jsonable(x, path) for x in v), key=lambda x: json.dumps(x, sort_keys=True))
    if v is None or isinstance(v, (bool, str, int)):
        return v
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError(f"{path}: 有限でない数 {v}")
        return 0.0 if v == 0 else v     # -0.0 を 0.0 に
    raise TypeError(f"{path}: {type(v).__name__} は JSON にできない")


def strip_visual(rows):
    """表の各行から見た目だけの部品を外す（元の spec は変えない）。"""
    return [{k: v for k, v in r.items() if k not in VISUAL_ONLY} for r in rows]


# ---------------------------------------------------------------------------
#  書き出し
# ---------------------------------------------------------------------------
class Derived:
    """JSON ではなく JS の式で書く export（索引など）。"""

    def __init__(self, expr: str, jsdoc: str):
        self.expr = expr
        self.jsdoc = jsdoc


def by(table: str, field: str) -> Derived:
    return Derived(f"Object.fromEntries({table}.map((x) => [x.{field}, x]))", "Record<string, any>")


def _jsdoc(v) -> str:
    """値の大まかな型（手書き側で型エラーが出ないよう、中身は緩く）。"""
    if isinstance(v, list):
        if v and all(isinstance(x, str) for x in v):
            return "string[]"
        if v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            return "number[]"
        return "any[]"
    if isinstance(v, dict):
        vals = list(v.values())
        if vals and all(isinstance(x, str) for x in vals):
            return "Record<string, string>"
        if vals and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in vals):
            return "Record<string, number>"
        if vals and all(x is None or (isinstance(x, (int, float)) and not isinstance(x, bool)) for x in vals):
            return "Record<string, ?number>"
        return "Record<string, any>"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, (int, float)):
        return "number"
    if isinstance(v, str):
        return "string"
    return "any"


def render_module(name: str, exports: dict, note: str = "") -> str:
    lines = [HEADER]
    if note:
        lines += ["// " + ln for ln in note.splitlines()]
    for k, v in exports.items():
        if isinstance(v, Derived):
            lines.append(f"/** @type {{{v.jsdoc}}} */")
            lines.append(f"export const {k} = {v.expr};")
            continue
        val = jsonable(v, f"{name}.{k}")
        text = json.dumps(val, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if "\n" in text or " " in text or " " in text:
            raise ValueError(f"{name}.{k}: 1 行に収まらない文字がある")
        lines.append(f"/** @type {{{_jsdoc(val)}}} */")
        lines.append(f"export const {k} = {text};")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
#  作る側が実際に作ったもの（登録簿より増えた分を fx.js に足すため）
# ---------------------------------------------------------------------------
def _json_files(folder):
    if not os.path.isdir(folder):
        return []
    return sorted(glob.glob(os.path.join(folder, "**", "*.json"), recursive=True))


def _safe_load(path):
    try:
        return load_json(path)
    except (OSError, ValueError):
        return None


def produced_particles() -> set:
    out = set()
    for p in _json_files(os.path.join(RP, "particles")):
        doc = _safe_load(p)
        eff = (doc or {}).get("particle_effect") if isinstance(doc, dict) else None
        ident = ((eff or {}).get("description") or {}).get("identifier") if isinstance(eff, dict) else None
        if isinstance(ident, str) and ident.startswith("nr:"):
            out.add(ident[3:])
    return out


def produced_sounds() -> set:
    out = set()
    for _producer, doc in read_frags("sound_definitions"):
        if isinstance(doc, dict):
            doc = doc.get("sound_definitions", doc)
            out.update(k for k in doc if isinstance(k, str) and k.startswith("nr."))
    doc = _safe_load(os.path.join(RP, "sounds", "sound_definitions.json"))
    if isinstance(doc, dict):
        defs = doc.get("sound_definitions", doc)
        if isinstance(defs, dict):
            out.update(k for k in defs if isinstance(k, str) and k.startswith("nr."))
    return out


def produced_animations() -> dict:
    """RP の animation.nr.* → 長さ（秒。書いてなければ None）。"""
    out = {}
    for p in _json_files(os.path.join(RP, "animations")):
        doc = _safe_load(p)
        anims = (doc or {}).get("animations") if isinstance(doc, dict) else None
        if not isinstance(anims, dict):
            continue
        for k, a in anims.items():
            if isinstance(k, str) and k.startswith("animation.nr."):
                ln = a.get("animation_length") if isinstance(a, dict) else None
                out[k] = float(ln) if isinstance(ln, (int, float)) and not isinstance(ln, bool) else None
    return out


# ---------------------------------------------------------------------------
#  表を組む
# ---------------------------------------------------------------------------
def zombie_rows(S) -> list:
    rows = []
    for i, z in enumerate(S.ZOMBIES):
        d = dict(z)
        d["id"] = S.zombie_id(z)
        d["ztype"] = i
        keys = S.ability_keys(z)
        d["ability_keys"] = keys
        d["ability_params"] = {k: S.ability_params(z, k) for k in keys}
        d["ability_states"] = S.ability_states(z)
        d["all_attacks"] = S.all_attacks(z)
        d["initial_armor"] = S.initial_armor(z)
        d["collision"] = list(S.zombie_collision(z))
        rows.append(d)
    return rows


def item_rows(S) -> list:
    import gen_nr_items as GI      # BP アイテムの書き方（エンジンが減らすか）と同じ規則を使う
    rows = []
    for it in strip_visual(S.all_items()):
        it["engine_consumes"] = GI.engine_consumes(it)
        it["use_seconds"] = GI.use_seconds(it)
        rows.append(it)
    return rows


def fx_tables(S) -> dict:
    # パーティクル（名前。ID は nr:<名前>）
    particles = list(REG.PARTICLES)
    extra = sorted(produced_particles() - set(particles))
    particles += extra
    # 効果音
    sounds = list(dict.fromkeys(REG.all_sound_ids(S)))
    sounds += sorted(produced_sounds() - set(sounds))
    # アニメーション
    have = produced_animations()
    player = {n: float(v[1]) for n, v in REG.PLAYER_ANIMS.items()}
    for full in sorted(have):
        if full.startswith("animation.nr.p."):
            n = full[len("animation.nr.p."):]
            if n not in player:
                player[n] = have[full]
    oneshots = {n: have.get(f"animation.nr.z.{n}") for n in REG.all_zombie_oneshots(S)}
    zanims = {z["key"]: S.zombie_animations(z) for z in S.ZOMBIES}
    return dict(PARTICLES=particles, SOUNDS=sounds, PLAYER_ANIMS=player, ZOMBIE_ONESHOTS=oneshots,
                ZOMBIE_ANIMATIONS=zanims, VOICE_EVENTS=list(REG.ZOMBIE_VOICE_EVENTS),
                PLAYER_MOTIONS=S.PLAYER_MOTIONS), len(extra)


def build(S) -> dict:
    """{ファイル名: (exports, 注記)}。"""
    mods = {}
    zrows = zombie_rows(S)
    ability_states = {z["key"]: z["ability_states"] for z in zrows}
    mods["zombies"] = (dict(
        ZOMBIES=zrows,
        ZTYPE=dict(S.ZTYPE),
        ZOMBIE_BY_KEY=by("ZOMBIES", "key"),
        ZOMBIE_BY_ID=by("ZOMBIES", "id"),
        ABILITIES=S.ABILITY_VOCAB,
        ATTACKS=S.ATTACK_VOCAB,
        LOCOMOTIONS=S.LOCOMOTION_VOCAB,
        VOICES=S.VOICE_VOCAB,
        GORE_KEYS=S.GORE_KEYS,
        GORE_DEFAULTS=S.GORE_DEFAULTS,
        ABILITY_STATES=ability_states,
        ABILITY_TRIGGERS=S.ABILITY_TRIGGERS,
        ATTACK_EFFECTS=S.ATTACK_EFFECTS,
        BLOOD_KINDS=S.BLOOD_VOCAB,
        WEAK_ZONES=S.WEAK_ZONES,
        EXPLODE_KINDS=S.EXPLODE_KINDS,
        CORPSE_KINDS=S.CORPSE_KINDS,
        CLASS_ORDER=S.CLASS_ORDER,
        CLASS_INFO=S.CLASS_INFO,
        HIT_PARTS=S.HIT_PARTS,
        ARMOR_BONES=S.ARMOR_BONES,
        PROPERTY_ENUMS=S.PROPERTY_ENUMS,
        RESIST_DEFAULT=S.RESIST_DEFAULT,
        SPAWN_SITES={k: {"ja": v[0], "fallback": v[1]} for k, v in S.SPAWN_SITES.items()},
    ), "ZOMBIES は ztype の順（ZOMBIES[ZTYPE[key]]）。派生: id ztype ability_keys ability_params "
       "ability_states all_attacks initial_armor collision")
    mods["weapons"] = (dict(
        WEAPONS=strip_visual(S.WEAPONS),
        WEAPON_BY_ID=by("WEAPONS", "id"),
        PROJECTILES=strip_visual(S.PROJECTILES),
        PROJECTILE_BY_ID=by("PROJECTILES", "id"),
        WEAPON_CLASSES={k: {"kind": v[0], "hands": v[1], "anim_set": v[2], "mods": list(v[3])}
                        for k, v in S.WEAPON_CLASSES.items()},
        WEAPON_KINDS=S.WEAPON_KINDS,
        ANIM_SETS=S.ANIM_SETS,
        SFX_SETS=S.SFX_SETS,
        RARITY=S.RARITY,
    ), "")
    mods["items"] = (dict(
        ITEMS=item_rows(S),
        ITEM_BY_ID=by("ITEMS", "id"),
        SHARED_ITEM_IDS=S.SHARED_ITEM_IDS,
        ITEM_KINDS=S.ITEM_KINDS,
        RARITY=S.RARITY,
        ZOMBIE_SOURCED=S.ZOMBIE_SOURCED,
    ), "ITEMS = MATERIAL_ITEMS（共有）+ ITEMS（その他）。engine_consumes = true のものは BP の minecraft:food で\n"
       "エンジンが 1 個減らす（スクリプトは itemCompleteUse で効果だけ）。false はスクリプトが減らす")
    mods["mods"] = (dict(MODS=S.MODS, MOD_BY_KEY=by("MODS", "key")), "")
    mods["traps"] = (dict(TRAPS=strip_visual(S.TRAPS),
                          TRAP_BY_ID=Derived("Object.fromEntries(TRAPS.filter((x) => x.id).map((x) => [x.id, x]))",
                                             "Record<string, any>"),
                          TRAP_BY_KEY=by("TRAPS", "key"),
                          TRAP_BLOCKS=S.TRAP_BLOCKS),
                     "TRAP_BY_ID は ID のある罠だけ（prop_interaction の罠は id が null。TRAP_BY_KEY なら全部）")
    mods["blocks"] = (dict(BLOCKS=strip_visual(S.BLOCKS), BLOCK_BY_ID=by("BLOCKS", "id"),
                           MULTIBLOCKS=S.MULTIBLOCKS, BLOCK_SOUNDS=S.BLOCK_SOUNDS), "")
    mods["props"] = (dict(PROPS=strip_visual(S.PROPS), PROP_BY_ID=by("PROPS", "id"),
                          PROP_INTERACTIONS=S.PROP_INTERACTIONS), "")
    max_level = int(S.PROGRESSION["max_level"])
    mods["skills"] = (dict(SKILLS=S.SKILLS, SKILL_BY_KEY=by("SKILLS", "key"), PROGRESSION=S.PROGRESSION,
                           XP_TO_NEXT=[0] + [S.xp_to_next(lv) for lv in range(1, max_level + 1)]),
                      "XP_TO_NEXT[レベル] = そのレベルから次へ上がるのに要る経験値（[0] は使わない）")
    mods["crafting"] = (dict(CRAFTING=S.CRAFTING, CRAFT_CATEGORIES=S.CRAFT_CATEGORIES), "")
    mods["settings"] = (dict(
        SETTINGS_DEFAULTS=S.SETTINGS_DEFAULTS,
        SETTINGS_SCHEMA=S.SETTINGS_SCHEMA,
        PARKOUR_TUNING=S.PARKOUR_TUNING,
        COMBAT_TUNING=S.COMBAT_TUNING,
        GORE_TUNING=S.GORE_TUNING,
        DIFFICULTY=S.DIFFICULTY,
        GORE_COMBOS=S.GORE_COMBOS,
        STARTER_KIT=S.STARTER_KIT,
        LOOT_TABLES=S.LOOT_TABLES,
        DTYPE_OUTCOMES=S.DTYPE_OUTCOMES,
        ABILITY_STATES=ability_states,
        CITY=S.CITY,
    ), "ABILITY_STATES[key] = {\"能力.段階\": nr:ability の値}（zombies.js と同じ）")
    fx, n_extra = fx_tables(S)
    mods["fx"] = (fx, "PARTICLES は名前（ID は nr:<名前>）。登録簿（nr_registry）の ID の後に、作る側が増やした ID を名前順に足す\n"
                      "PLAYER_ANIMS / ZOMBIE_ONESHOTS は {名前: 長さ秒}（animation.nr.p.<名前> / animation.nr.z.<名前>）。"
                      "ZOMBIE_ONESHOTS の長さは RP に無ければ null")
    return mods, n_extra


def main(argv=None) -> int:
    S = load_spec()
    mods, n_extra = build(S)
    os.makedirs(DATA_JS, exist_ok=True)
    total = 0
    for name in FILES:
        exports, note = mods[name]
        text = render_module(name, exports, note)
        write_text(os.path.join(DATA_JS, f"{name}.js"), text)
        total += len(text.encode("utf-8"))
    # 自分の名前の付いていない古い生成物は残す（zombie_shapes.js / structures.js / glyphs.js は他の生成器のもの）
    print(f"[{PRODUCER}] scripts/data/ {len(FILES)} files, {total / 1024:.1f} KiB"
          f" (zombies {len(S.ZOMBIES)} / weapons {len(S.WEAPONS)} / items {len(S.all_items())}"
          f" / fx extra particles {n_extra})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
