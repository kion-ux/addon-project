# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — spec.py から実行時テーブルを書き出す。

企画書 §09「技の見た目・判定・コストを一つの定義にまとめる」を、Python 側と
JavaScript 側で二重管理しないための橋渡し。scripts/data.js は生成物なので
手で編集しない — 直すのは tools/gla/spec.py。
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import spec                                             # noqa: E402

OUT = os.path.join(ROOT, spec.BP_DIR, "scripts", "data.js")


def js(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def tech_row(t: spec.Tech) -> dict:
    return {
        "id": t.slug,
        "form": t.form,
        "name": t.name_key,
        "shape": t.shape,
        "cost": t.cost,
        "cd": t.cooldown,
        "windup": t.windup,
        "active": t.active,
        "recover": t.recover,
        "reach": t.reach,
        "radius": t.radius,
        "damage": t.damage,
        "hits": t.hits,
        "gap": t.hit_interval,
        "kbH": t.kb_h,
        "kbV": t.kb_v,
        "terrain": t.terrain,
        "fire": t.fire,
        "anim": t.anim_id,
        "launch": list(t.launch),
        "buffs": [list(e) for e in t.self_effects],
        "stages": t.stages,
        "sfx": t.sfx,
    }


def form_row(f: spec.Form) -> dict:
    return {
        "key": f.key,
        "name": f.name_key,
        "item": spec.form_item(f.key),
        "upkeep": f.upkeep,
        "enter": f.enter,
        "unlock": f.unlock_hits,
        "effects": [list(e) for e in f.effects],
        "transient": f.transient,
    }


HEADER = """// =========================================================================
//  GRAND LINE AWAKENING — 実行時テーブル
//  自動生成ファイル。編集しないこと。生成元: tools/gla/spec.py
//  （企画書 §09「技の見た目・判定・コストを一つの定義にまとめる」）
// =========================================================================
"""


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    forms = [form_row(f) for f in spec.FORMS]
    techs = [tech_row(t) for t in spec.TECHS]
    by_form = {f.key: [t.slug for t in spec.techs_of(f.key)] for f in spec.FORMS}
    show = []
    for step in spec.SHOWPIECE:
        show.append({
            "t": step["t"], "until": step["until"], "pose": step["pose"],
            "stages": step["stages"], "sfx": step.get("sfx", []),
            "lift": bool(step.get("lift")), "swap": bool(step.get("swap_form")),
            "quiet": bool(step.get("quiet")),
        })

    parts = [HEADER]
    parts.append(f'export const NS = {js(spec.NS)};\n')
    parts.append(f'export const ENERGY_MAX = {spec.ENERGY_MAX};\n')
    parts.append(f'export const ENERGY_REGEN = {spec.ENERGY_REGEN};\n')
    parts.append(f'export const ENERGY_REGEN_IDLE = {spec.ENERGY_REGEN_IDLE};\n')
    parts.append(f'export const LOW_ENERGY = {spec.LOW_ENERGY};\n')
    parts.append(f'export const PHASES = {js(spec.PHASES)};\n')
    parts.append(f'export const PROP = {js(spec.PROPS)};\n')
    parts.append(f'export const TAG_ACTIVE = {js(spec.TAG_ACTIVE)};\n')
    parts.append(f'export const DEFAULTS = {js(spec.DEFAULTS)};\n')
    parts.append(f'export const QUALITY = {js(spec.QUALITY)};\n')
    parts.append(f'export const QUALITY_ORDER = {js(spec.QUALITY_ORDER)};\n')
    parts.append(f'export const FORMS = {js(forms)};\n')
    parts.append(f'export const FORM_ORDER = {js(spec.FORM_ORDER)};\n')
    parts.append(f'export const TECHS = {js(techs)};\n')
    parts.append(f'export const TECHS_BY_FORM = {js(by_form)};\n')
    parts.append(f'export const SHOWPIECE = {js(show)};\n')
    parts.append(f'export const SHOWPIECE_TICKS = {spec.SHOWPIECE_TICKS};\n')
    parts.append(f'export const SHOWPIECE_SHORT_TICKS = {spec.SHOWPIECE_SHORT_TICKS};\n')
    parts.append(f'export const SHOWPIECE_LIFT = {spec.SHOWPIECE_LIFT};\n')
    parts.append(f'export const TRAINING = {js(spec.TRAINING)};\n')

    parts.append(f'''
export const ITEM = {{
  fruit: {js(spec.FRUIT_ITEM)},
  hat: {js(spec.HAT_ITEM)},
  wrap: {js(spec.WRAP_ITEM)},
  pose: {js(spec.POSE_ITEM)},
}};

export const FORM_ITEMS = {js(spec.FORM_ITEMS)};

export const MOB = {js({m.slug: m.id for m in spec.MOBS})};

/** 形態キー -> 定義 */
export const FORM_BY_KEY = Object.fromEntries(FORMS.map((f) => [f.key, f]));
/** 技ID -> 定義 */
export const TECH_BY_ID = Object.fromEntries(TECHS.map((t) => [t.id, t]));
''')

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print(f"data.js: {len(forms)} forms, {len(techs)} techniques, "
          f"{len(show)} showpiece steps")


if __name__ == "__main__":
    main()
