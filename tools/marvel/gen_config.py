# -*- coding: utf-8 -*-
"""contract.py から scripts/config.js を書き出す。

識別子を Python と JavaScript の二箇所で手書きすると必ずずれるので、
**JS 側の定数はすべてここで生成する**。手で編集しないこと。
"""
from __future__ import annotations

import json

import _path  # noqa: F401

import contract as K  # noqa: E402

HEADER = """// ===========================================================================
//  自動生成ファイル — 手で編集しないこと。
//  tools/marvel/contract.py を直して `python3 tools/marvel/gen_config.py`。
// ===========================================================================
"""


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def main() -> None:
    K.ensure_dirs()

    techniques = {}
    for name, spec in K.TECHNIQUES.items():
        techniques[name] = {
            "item": K.tech_item(name),
            "ja": spec["ja"],
            "en": spec["en"],
            "pose": spec["pose"],
            "clip": spec["clip"],
            "cost": spec["cost"],
            "cd": spec["cd"],
            "stage": spec["stage"],
            "colour": spec["colour"],
            "hold": K.POSE_HOLD[spec["pose"]],
            "form": K.form_item(K.MAGNETO, name),
            "ultimate": bool(spec.get("ultimate")),
        }

    ally = {}
    for character, techs in K.ALLY_TECHNIQUES.items():
        ally[character] = [{
            "key": t["key"], "ja": t["ja"], "en": t["en"], "cost": t["cost"],
            "cd": t["cd"], "colour": t["colour"],
            "form": K.form_item(character, t["key"]),
        } for t in techs]

    heroes = {}
    for key in K.PLAYABLE:
        c = K.CHARACTERS[key]
        heroes[key] = {
            "ja": c["ja"], "en": c["en"], "form": K.form_item(key),
            "health": c["health"], "damage": c["damage"],
            "lead": key == K.MAGNETO,
        }

    parts = {name: K.part(name) for name in K.PARTICLES}

    body = [
        HEADER,
        f"export const NS = {js(K.NS)};",
        "",
        "/** 動的プロパティ名 */",
        f"export const PROP = {js(K.DYNAMIC_PROPS)};",
        "",
        "/** タグ */",
        f"export const TAG = {js(K.TAGS)};",
        "",
        "/** タイプファミリ */",
        f"export const FAMILY = {js(K.FAMILIES)};",
        "",
        "/** 磁力ゲージ */",
        f"export const MAG_MAX = {K.MAG_MAX};",
        f"export const MAG_REGEN = {K.MAG_REGEN};",
        f"export const MAG_REGEN_STAGE3 = {K.MAG_REGEN_STAGE3};",
        f"export const MAG_DRAIN = {K.MAG_DRAIN};",
        "",
        "/** 段階の解禁条件 [撃破数, 段階] */",
        f"export const STAGE_THRESHOLDS = {js(K.STAGE_THRESHOLDS)};",
        "",
        "/** 磁力が効くブロックと、その磁化強度 */",
        f"export const MAGNETIC_BLOCKS = {js(K.MAGNETIC_BLOCKS)};",
        "",
        "/** 装備の素材名 -> 圧壊倍率 */",
        f"export const MAGNETIC_ITEMS = {js(K.MAGNETIC_ITEMS)};",
        f"export const IMMUNE_ITEMS = {js(K.IMMUNE_ITEMS)};",
        "",
        "/** アイテム */",
        f"export const ITEM = {js({k: K.eid(k) for k in K.ITEMS})};",
        "",
        "/** 技 */",
        f"export const TECH = {js(techniques)};",
        f"export const TECH_ORDER = {js(K.TECH_ORDER)};",
        "",
        "/** アイテム ID -> 技キー */",
        f"export const TECH_BY_ITEM = "
        f"{js({K.tech_item(n): n for n in K.TECHNIQUES})};",
        "",
        "/** ブラザーフッドの技 */",
        f"export const ALLY_TECH = {js(ally)};",
        "",
        "/** 変身できるキャラ */",
        f"export const HERO = {js(heroes)};",
        f"export const HERO_ORDER = {js(K.PLAYABLE)};",
        "",
        "/** すべての変身体アイテム（掃除用） */",
        f"export const FORM_ITEMS = "
        f"{js(sorted({K.form_item(c, t) for c, t, _g, _n in K.form_variants()}))};",
        "",
        "/** エンティティ */",
        f"export const ENTITY = {js({k: K.eid(k) for k in K.ENTITY_KEYS})};",
        "",
        "/** パーティクル */",
        f"export const FX = {js(parts)};",
        "",
        "/** サウンド（バニラのイベント名） */",
        f"export const SOUND = {js(K.SOUNDS)};",
        "",
    ]
    path = f"{K.SCRIPT_DIR}/config.js"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body))
    print(f"  scripts/config.js  ({len(K.TECHNIQUES)} techniques, "
          f"{len(K.PARTICLES)} particles)")


if __name__ == "__main__":
    main()
