# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — 全登録データの入口（DESIGN.md §1 の `nr_spec.py`）。

生成器・データ JS・検証は**このモジュールだけを import する**:

    import nr_spec
    nr_spec.ZOMBIES, nr_spec.ZTYPE, nr_spec.WEAPONS, nr_spec.zombie("volatile"), nr_spec.weapon("nr:w_machete") …

* `nr_spec_zombies`（ゾンビ 50 体と語彙）と `nr_spec_catalog`（武器・アイテム・罠・ブロック・小道具・建物・スキル…）の
  `__all__` をそのまま再輸出する。両方にある名前は下の `_CLASH_RESOLUTION` で**明示的に**決める
  （値が違えば import の時点で止める）。
* 演出 ID（パーティクル・効果音・プレイヤーのモーション・ゾンビのアニメ）の正は `nr_registry`。
  spec が参照する ID が全部登録簿にあることを `check()` が確かめる。
* このモジュールが足すもの: 検索 `zombie(key)` / `weapon(key)` / `item(key)` / `block(key)` / `prop(key)` /
  `structure(key)` / `projectile(key)` / `trap(key)` / `vehicle(key)`（鍵でもフル ID でもよい）、`ztype(key)`、
  `all_item_ids()`（手に持てる nr: の ID）、`all_entity_ids()`（nr: のエンティティ ID）、`ALL_PROJECTILES`、
  `SITE_STRUCTURES` / `site_structures(site)`（ゾンビの出現場所 → 建物モジュール）、
  ゾンビ側も含めた `lang_entries()` / `required_sounds()` / `required_particles()` /
  `required_player_animations()` / `required_zombie_animations()`、合わせた自己検査 `check()`。

`python3 tools/nightrunner/nr_spec.py` で全部の自己検査（ゾンビ・カタログ・登録簿・両者の突き合わせ・
原作の固有名の不使用・ゴアの結果の網羅）を走らせ、数を出す。
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import nr_registry  # noqa: E402  演出 ID の登録簿（正）
import nr_spec_catalog as _C  # noqa: E402
import nr_spec_zombies as _Z  # noqa: E402
from nr_spec_catalog import *  # noqa: E402,F401,F403
from nr_spec_zombies import *  # noqa: E402,F401,F403

# ---------------------------------------------------------------------------
#  名前の衝突の解決（両方の __all__ にある名前）。値は "zombies" / "catalog" のどちらを使うか。
#  同じ意味のはずの表は値が等しいことも確かめる（食い違ったら import で止める）
# ---------------------------------------------------------------------------
_CLASH_RESOLUTION = {
    "DTYPES": "zombies",      # ダメージ種別（DESIGN.md §4）。両方とも同じ 7 つ
}


def _resolve_clashes():
    clashes = set(_Z.__all__) & set(_C.__all__)
    unknown = sorted(clashes - set(_CLASH_RESOLUTION))
    if unknown:
        raise ImportError(f"nr_spec: names exported by both spec modules need a resolution: {unknown}")
    for name in sorted(clashes):
        zv, cv = getattr(_Z, name), getattr(_C, name)
        if zv != cv:
            raise ImportError(f"nr_spec: {name} differs between nr_spec_zombies and nr_spec_catalog")
        globals()[name] = zv if _CLASH_RESOLUTION[name] == "zombies" else cv


_resolve_clashes()

# このモジュールが上書きする名前（カタログ版より広い。鍵でもフル ID でも引ける・ゾンビ側も含む）
OVERRIDDEN = ("weapon", "lang_entries", "required_sounds", "required_particles", "required_player_animations")

# DESIGN.md §6 の区分ごとの数と、エントリの必須の項目
DESIGN_CLASS_COUNTS = {"common": 24, "viral": 8, "special": 11, "night": 4, "boss": 3}
DESIGN_ZOMBIE_FIELDS = (
    "key", "ja", "en", "cls", "height_cm", "heads", "bulk", "limb", "hunch", "arm_len", "decay", "skin",
    "outfit", "mutations", "eyes", "hp", "speed", "damage", "attack", "locomotion", "resist", "gore",
    "abilities", "spawn", "loot", "voice", "bestiary_ja", "bestiary_en", "weakness_ja", "weakness_en",
)

# 飛び道具（プレイヤー側 + ゾンビ側）
ALL_PROJECTILES = list(_C.PROJECTILES) + list(_Z.ZOMBIE_PROJECTILES)

# ゾンビの出現場所（SPAWN_SITES）→ 建物モジュール（STRUCTURES の鍵）。代わりの場所（fallback）は spec が持つ
SITE_STRUCTURES = {
    "street": ("street_block_segment",),
    "apartment": ("apartment_low", "apartment_tall"),
    "shop": ("corner_shop",),
    "gas_station": ("gas_station",),
    "hospital": ("clinic",),
    "police": ("police_station",),
    "church": ("church_tower",),
    "warehouse": ("warehouse", "collapsed_building"),
    "parking": ("parking_garage",),
    "rooftop": ("rooftop_parkour_set", "billboard_roof"),
}
# 建物だけに置く種類（spawn.where = structure）が要る印（MARKER_KINDS）
STRUCTURE_MARKER_FOR_CLASS = {"boss": "z_boss", "night": "z_night_nest", "special": "z_special",
                              "viral": "z_viral", "common": "z_interior"}

# 表示名に使わない原作の固有名（ゲームの鍵・ID は対象外。表示する文字列だけを調べる）
ORIGINALITY_BANNED = (
    (r"\bvolatiles?\b", re.I), (r"\bvirals?\b", re.I), (r"\bhowlers?\b", re.I), (r"\bdemolishers?\b", re.I),
    (r"\bgoons?\b", re.I), (r"\bbanshees?\b", re.I), (r"\brevenants?\b", re.I), (r"\bbiters?\b", re.I),
    (r"\bharran\b", re.I), (r"\bvilledor\b", re.I), (r"\bGRE\b", 0), (r"\bnight hunters?\b", re.I),
    (r"\binhibitors?\b", re.I), (r"\bantizin\b", re.I), (r"\bsurvivor sense\b", re.I),
    (r"ボラタイル", 0), (r"ヴァイラル|バイラル", 0), (r"ハウラー", 0), (r"デモリッシャー", 0), (r"グーン", 0),
    (r"バンシー", 0), (r"レヴナント|リヴナント|レブナント", 0), (r"バイター", 0), (r"ハラン", 0),
    (r"ヴィレドール|ビレドール", 0), (r"ナイトハンター", 0), (r"インヒビター", 0), (r"サバイバーセンス", 0),
)


# ---------------------------------------------------------------------------
#  検索（鍵でもフル ID でもよい）
# ---------------------------------------------------------------------------
def _find(rows, key, prefixes, what):
    for r in rows:
        if r["key"] == key or r.get("id") == key:
            return r
    for pre in prefixes:
        if key.startswith(pre):
            k = key[len(pre):]
            for r in rows:
                if r["key"] == k:
                    return r
    raise KeyError(f"unknown {what}: {key!r}")


def zombie(key):
    """ゾンビ（"volatile" / "nr:z_volatile"）。"""
    return _find(_Z.ZOMBIES, key, ("nr:z_",), "zombie")


def ztype(key) -> int:
    """種類番号（ZOMBIES の並び順 0..49）。"""
    return _Z.ZTYPE[zombie(key)["key"]]


def weapon(key):
    """武器（"machete" / "nr:w_machete"）。"""
    return _find(_C.WEAPONS, key, ("nr:w_",), "weapon")


def item(key):
    """武器・ブロック以外のアイテム（共有 23 種 + その他）。"bandage" / "nr:bandage"。"""
    return _find(_C.all_items(), key, ("nr:",), "item")


def block(key):
    """カスタムブロック（罠ブロックも）。"barricade" / "nr:barricade"。"""
    return _find(list(_C.BLOCKS) + _C.block_traps(), key, ("nr:",), "block")


def prop(key):
    """小道具エンティティ。"sedan_wreck" / "nr:prop_sedan_wreck"。"""
    return _find(_C.PROPS, key, ("nr:prop_",), "prop")


def vehicle(key):
    """乗れる乗り物（カタログの VEHICLES）。"survivor_buggy" / "nr:veh_survivor_buggy"。"""
    return _find(_C.VEHICLES, key, ("nr:veh_",), "vehicle")


def structure(key):
    """建物モジュール。"""
    return _find(_C.STRUCTURES, key, (), "structure")


def projectile(key):
    """飛び道具（プレイヤー側とゾンビ側）。"bolt" / "nr:proj_spit"。"""
    return _find(ALL_PROJECTILES, key, ("nr:proj_",), "projectile")


def trap(key):
    """罠（ブロック・小道具・小道具の仕掛け）。"""
    return _find(_C.TRAPS, key, ("nr:", "nr:prop_"), "trap")


def site_structures(site):
    """出現場所 → 置ける建物モジュールの鍵（SPAWN_SITES の fallback をたどる）。"""
    seen = []
    while site is not None and site not in SITE_STRUCTURES:
        if site in seen or site not in _Z.SPAWN_SITES:
            return ()
        seen.append(site)
        site = _Z.SPAWN_SITES[site][1]
    return SITE_STRUCTURES.get(site, ())


# ---------------------------------------------------------------------------
#  ID の一覧
# ---------------------------------------------------------------------------
def all_item_ids():
    """手に持てる nr: の ID（共有・その他のアイテム・武器・ブロック・罠ブロック）。並べ替え済み。"""
    return sorted(_C.inventory_ids())


def all_entity_ids():
    """nr: のエンティティ ID（ゾンビ 50・gib・飛び道具・小道具・乗り物）。並べ替え済み。"""
    ids = [_Z.zombie_id(z) for z in _Z.ZOMBIES] + ["nr:gib"]
    ids += [p["id"] for p in ALL_PROJECTILES] + [p["id"] for p in _C.PROPS]
    ids += [v["id"] for v in _C.VEHICLES]
    return sorted(ids)


def lang_entries():
    """名前の言語キー（カタログ + ゾンビ 50 体 + ゾンビの飛び道具）。{"ja_JP": {...}, "en_US": {...}}。"""
    le = _C.lang_entries()
    for z in _Z.ZOMBIES:
        ident = _Z.zombie_id(z)
        le["ja_JP"][f"entity.{ident}.name"] = z["ja"]
        le["en_US"][f"entity.{ident}.name"] = z["en"]
    for p in _Z.ZOMBIE_PROJECTILES:
        le["ja_JP"][f"entity.{p['id']}.name"] = p["ja"]
        le["en_US"][f"entity.{p['id']}.name"] = p["en"]
    for v in _C.VEHICLES:                     # 乗り物（スポーンエッグの名前は gen_nr_vehicles の断片）
        le["ja_JP"][f"entity.{v['id']}.name"] = v["ja"]
        le["en_US"][f"entity.{v['id']}.name"] = v["en"]
    return le


def required_sounds():
    """spec が参照する効果音（カタログ + 使われているゾンビの声と能力の音）。"""
    out = set(_C.required_sounds())
    for z in _Z.ZOMBIES:
        out.update(_Z.zombie_sounds(z))
        out.update(nr_registry.derived_ability_sounds(_Z.ability_keys(z)))
    return sorted(out)


def required_particles():
    """spec が参照するパーティクル（カタログ + ゾンビの飛び道具の尾と着弾）。"""
    out = set(_C.required_particles())
    for p in _Z.ZOMBIE_PROJECTILES:
        out.update(x for x in (p["trail"], p["impact"]) if x)
    return sorted(out)


def required_player_animations():
    """animation.nr.p.<名前>（カタログの ANIM_SETS・PLAYER_MOTIONS・アイテムの use.anim）。"""
    return _C.required_player_animations()


def required_zombie_animations():
    """animation.nr.z.<名前>（共通の一発もの + 全種類の walk_/run_/atk_/ab_*）。"""
    return nr_registry.all_zombie_anim_ids(sys.modules[__name__])


def anim_set_names(set_key):
    """ANIM_SETS の 1 組が使うモーションの名前（swings / heavy / idle / sprint / aim …）。"""
    out = []
    for k, v in _C.ANIM_SETS[set_key].items():
        if k == "ja":
            continue
        if k == "swings":
            out += [sw[0] for sw in v]
        elif k == "heavy":
            out.append(v[0])
        else:
            out.append(v)
    return out


def display_strings():
    """表示される文字列 (どこ, 文字列) の一覧（原作の固有名の検査用）。"""
    out = []
    fields = ("ja", "en", "desc_ja", "desc_en", "lore_ja", "lore_en", "note_ja", "note_en",
              "bestiary_ja", "bestiary_en", "weakness_ja", "weakness_en")

    def add_row(where, r):
        for f in fields:
            v = r.get(f)
            if isinstance(v, str):
                out.append((f"{where}.{f}", v))
    for z in _Z.ZOMBIES:
        add_row(f"zombie {z['key']}", z)
        if z["boss"]:
            for f in ("title_ja", "title_en"):
                out.append((f"zombie {z['key']}.boss.{f}", z["boss"][f]))
    for c, info in _Z.CLASS_INFO.items():
        add_row(f"class {c}", info)
    for name, rows in (("item", _C.all_items()), ("weapon", _C.WEAPONS), ("projectile", ALL_PROJECTILES),
                       ("trap", _C.TRAPS), ("block", _C.BLOCKS), ("prop", _C.PROPS), ("vehicle", _C.VEHICLES),
                       ("structure", _C.STRUCTURES), ("skill", _C.SKILLS), ("mod", _C.MODS),
                       ("setting", _C.SETTINGS_SCHEMA)):
        for r in rows:
            add_row(f"{name} {r['key']}", r)
    for name, d in (("craft_category", _C.CRAFT_CATEGORIES), ("gore_combo", _C.GORE_COMBOS),
                    ("rarity", _C.RARITY), ("difficulty", _C.DIFFICULTY)):
        for k, r in d.items():
            add_row(f"{name} {k}", r)
    return out


# ---------------------------------------------------------------------------
#  合わせた自己検査
# ---------------------------------------------------------------------------
def _check_cross():
    err = []
    E = err.append
    zs = _Z.ZOMBIES
    # --- DESIGN.md §6: 区分の数と必須の項目 -------------------------------------------
    counts = {c: len(_Z.zombies_of_class(c)) for c in _Z.CLASS_ORDER}
    if counts != DESIGN_CLASS_COUNTS:
        E(f"class counts {counts} != DESIGN.md §6 {DESIGN_CLASS_COUNTS}")
    for c, n in DESIGN_CLASS_COUNTS.items():
        if _Z.CLASS_INFO[c]["count"] != n:
            E(f"CLASS_INFO[{c}].count != {n}")
    missing = [f for f in DESIGN_ZOMBIE_FIELDS if f not in _Z.ZOMBIE_FIELDS]
    if missing:
        E(f"ZOMBIE_FIELDS lacks DESIGN.md §6 fields {missing}")
    if list(_Z.ZTYPE) != [z["key"] for z in zs] or sorted(_Z.ZTYPE.values()) != list(range(len(zs))):
        E("ZTYPE must be the ZOMBIES order 0..49")
    # --- ID の重複 ------------------------------------------------------------------
    ents = all_entity_ids()
    if len(ents) != len(set(ents)):
        E(f"duplicate entity ids {sorted({e for e in ents if ents.count(e) > 1})}")
    items = set(all_item_ids())
    for e in set(ents) & items:
        E(f"{e} is both an entity and an item")
    # --- ゾンビのルート → カタログのアイテム -------------------------------------------
    if tuple(_Z.SHARED_LOOT_ITEMS) != tuple(_C.SHARED_ITEM_IDS):
        E("nr_spec_zombies.SHARED_LOOT_ITEMS != nr_spec_catalog.SHARED_ITEM_IDS")
    van = _C._vanilla_lists().get("vanilla_items")
    dropped = set()
    for z in zs:
        for row in z["loot"]:
            ref = row[0]
            dropped.add(ref)
            if ref.startswith("nr:"):
                if ref not in items:
                    E(f"zombie {z['key']}: loot {ref} is not a catalog item")
            elif ref.startswith("minecraft:"):
                if van is not None and ref not in van:
                    E(f"zombie {z['key']}: loot {ref} is not a vanilla item")
            else:
                E(f"zombie {z['key']}: loot id {ref} must start with nr: or minecraft:")
    for ref in _C.ZOMBIE_SOURCED:
        if ref not in dropped:
            E(f"{ref} is ZOMBIE_SOURCED but no zombie drops it")
    for ref, _n in _C.STARTER_KIT:
        if ref not in items:
            E(f"STARTER_KIT {ref} is not an item")
    # --- 区分の鍵を使う表 -------------------------------------------------------------
    for m in _C.MODS:
        if set(m["vs"]) != set(_Z.CLASS_ORDER):
            E(f"mod {m['key']}: vs keys {sorted(m['vs'])} != classes {list(_Z.CLASS_ORDER)}")
    if not set(_Z.CLASS_ORDER) <= set(_C.PROGRESSION["combat_xp"]):
        E("PROGRESSION.combat_xp needs every zombie class")
    # --- 出現場所 → 建物 ----------------------------------------------------------------
    skeys = {s["key"]: s for s in _C.STRUCTURES}
    for site, keys in SITE_STRUCTURES.items():
        if site not in _Z.SPAWN_SITES:
            E(f"SITE_STRUCTURES: {site} is not a SPAWN_SITES key")
        for k in keys:
            if k not in skeys:
                E(f"SITE_STRUCTURES[{site}]: unknown structure {k}")
    for site, (_desc, fb) in _Z.SPAWN_SITES.items():
        if fb is None and site not in SITE_STRUCTURES:
            E(f"spawn site {site} has no fallback and no structure")
        if not site_structures(site):
            E(f"spawn site {site} does not resolve to a structure")
    for z in zs:
        sp = z["spawn"]
        if sp["where"] != "structure":
            continue
        marker = STRUCTURE_MARKER_FOR_CLASS[z["cls"]]
        ok = any(any(m[0] == marker for m in skeys[k]["markers"])
                 for site in sp["site"] for k in site_structures(site))
        if not ok:
            E(f"zombie {z['key']}: no structure for sites {sp['site']} carries marker {marker}")
    # --- 飛び道具 ---------------------------------------------------------------------
    pids = [p["id"] for p in ALL_PROJECTILES]
    if len(pids) != len(set(pids)):
        E("projectile ids collide between catalog and zombies")
    particles = set(nr_registry.all_particle_ids())
    for p in _Z.ZOMBIE_PROJECTILES:
        for part in p["model"]:
            if part["mat"] not in _C.SURFACES:
                E(f"zombie projectile {p['key']}.{part['name']}: unknown surface {part['mat']}")
        for f in ("trail", "impact"):
            if p[f] and p[f] not in particles:
                E(f"zombie projectile {p['key']}: {f} {p[f]} not in nr_registry.PARTICLES")
    # --- 武器 → 登録簿のモーション・音・パーティクル ----------------------------------------
    anims = set(nr_registry.PLAYER_ANIMS)
    sounds = set(nr_registry.SOUNDS)
    for w in _C.WEAPONS:
        for n in anim_set_names(w["anim_set"]):
            if n not in anims:
                E(f"weapon {w['key']}: anim_set {w['anim_set']} uses {n}, not in nr_registry.PLAYER_ANIMS")
        for sid in _C.SFX_SETS[w["sfx"]].values():
            if sid not in sounds:
                E(f"weapon {w['key']}: sound {sid} not in nr_registry.SOUNDS")
        for pid in w["fx"].values():
            if pid not in particles:
                E(f"weapon {w['key']}: particle {pid} not in nr_registry.PARTICLES")
    for k in _C.PLAYER_MOTIONS:
        if k not in anims:
            E(f"PLAYER_MOTIONS {k} not in nr_registry.PLAYER_ANIMS")
    # --- ゴアの結果の網羅（DESIGN.md §4） ----------------------------------------------
    def dts(w):
        out = {w["dtype"]} | ({w["alt_dtype"]} if w["alt_dtype"] else set())
        im = w["special"].get("innate_mod")
        if im:
            out.add(_C.by_key(_C.MODS, im)["dtype"])
        return out
    need = {
        "slash light": lambda w: w["dtype"] == "slash" and w["weight"] == "light",
        "slash heavy": lambda w: w["dtype"] == "slash" and w["weight"] == "heavy",
        "blunt light": lambda w: w["dtype"] == "blunt" and w["weight"] == "light",
        "blunt heavy": lambda w: w["dtype"] == "blunt" and w["weight"] == "heavy",
        "pierce light": lambda w: w["dtype"] == "pierce" and w["weight"] == "light",
        "pierce heavy": lambda w: w["dtype"] == "pierce" and w["weight"] == "heavy",
        "pierce shotgun": lambda w: w["dtype"] == "pierce" and w["pellets"] > 1,
        "blast": lambda w: "blast" in dts(w) and w["damage"] > 0,
        "fire": lambda w: "fire" in dts(w),
        "shock": lambda w: "shock" in dts(w),
    }
    for label, pred in need.items():
        if not any(pred(w) for w in _C.WEAPONS):
            E(f"no weapon covers gore case '{label}' (DESIGN.md §4)")
    reach = {}
    for w in _C.WEAPONS:
        for part, out in w["sever_bias"].items():
            reach.setdefault(part, set()).add(out)
    for part, states in _C.GORE_PARTS.items():
        for st in states:
            if st in ("intact", "wounded"):
                continue
            if st not in reach.get(part, set()):
                E(f"no weapon's sever_bias reaches {part}={st}")
    # --- 原作の固有名を表示に使わない ----------------------------------------------------
    for where, text in display_strings():
        for pat, flags in ORIGINALITY_BANNED:
            if re.search(pat, text, flags):
                E(f"{where}: display text uses a Dying Light term ({pat}): {text[:60]!r}")
    return err


def check():
    """全部の検査。[(区分, メッセージ)] を返す（空なら合格）。"""
    out = []
    out += [("zombies", m) for m in _Z.check_zombies()]
    out += [("catalog", m) for m in _C.self_check()]
    out += [("vehicles", m) for m in _C.vehicle_self_check()]
    out += [("registry", m) for m in nr_registry.check(sys.modules[__name__])]
    out += [("cross", m) for m in _check_cross()]
    return out


def summary():
    me = sys.modules[__name__]
    cls = ", ".join(f"{c}={len(_Z.zombies_of_class(c))}" for c in _Z.CLASS_ORDER)
    lines = [
        f"zombies {len(_Z.ZOMBIES)} ({cls}), zombie projectiles {len(_Z.ZOMBIE_PROJECTILES)}",
        "vocab: outfit=%d mutation=%d skin=%d eyes=%d attack=%d locomotion=%d ability=%d voice=%d blood=%d"
        % (len(_Z.OUTFIT_VOCAB), len(_Z.MUTATION_VOCAB), len(_Z.SKIN_VOCAB), len(_Z.EYES_VOCAB),
           len(_Z.ATTACK_VOCAB), len(_Z.LOCOMOTION_VOCAB), len(_Z.ABILITY_VOCAB), len(_Z.VOICE_VOCAB),
           len(_Z.BLOOD_VOCAB)),
        "eyes: " + ", ".join(_Z.EYES_VOCAB),
        "catalog: " + _C.summary(),
        f"ids: items {len(all_item_ids())}, entities {len(all_entity_ids())}",
        f"registry: particles {len(nr_registry.PARTICLES)}, sounds {len(nr_registry.all_sound_ids(me))} "
        f"(static {len(nr_registry.SOUNDS)}), player anims {len(nr_registry.PLAYER_ANIMS)}, "
        f"zombie anims {len(nr_registry.all_zombie_anim_names(me))} + one-shots {len(nr_registry.ZOMBIE_ONESHOTS)}",
        f"spec requires: sounds {len(required_sounds())}, particles {len(required_particles())}, "
        f"player anims {len(required_player_animations())}, zombie anims {len(required_zombie_animations())}",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    problems = check()
    print(summary())
    for where, msg in problems:
        print(f"  NG [{where}] {msg}")
    if problems:
        print(f"{len(problems)} problem(s)")
        sys.exit(1)
    print("OK: nr_spec（ゾンビ + カタログ + 演出 ID の登録簿）の検査に合格")
