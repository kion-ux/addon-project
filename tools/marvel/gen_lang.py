# -*- coding: utf-8 -*-
"""言語ファイル。日本語を主、英語を副として両方揃える。"""
from __future__ import annotations

import os

import _path  # noqa: F401

import contract as K  # noqa: E402
import gen_bp  # noqa: E402

PACK_JA = "マーベル・ミュータント / 磁界の帝王"
PACK_EN = "Marvel Mutants / Master of Magnetism"
PACK_DESC_JA = "マグニートーとブラザーフッド。金属を支配し、センチネルを迎え撃て。"
PACK_DESC_EN = ("Magneto and the Brotherhood. Command every metal on earth "
                "and tear the Sentinels apart.")

UI_JA = {
    "hud.mag": "磁力",
    "hud.stage": "段階",
    "hud.tech": "選択中",
    "hud.cooldown": "再充填",
    "hud.flying": "磁気飛行",
    "hud.barrier": "障壁展開中",
    "hud.sight": "磁力視",
    "msg.welcome": "§d[X遺伝子]§r 血の中で、何かが目を覚ましている。",
    "msg.welcome_hint": "§7X遺伝子を作って飲めば、ミュータントとして覚醒する。",
    "msg.welcome_tech": "§7ヘルメットを持って使用で変身、スニーク＋使用で設定。",
    "msg.awakened": "§d覚醒した。§r世界の金属が、お前に語りかけてくる。",
    "msg.already_mutant": "§7既に覚醒している。",
    "msg.no_power": "§7まだ力が無い。X遺伝子を飲め。",
    "msg.transform": "§5変身：§r磁界の帝王",
    "msg.revert": "§7変身を解いた。",
    "msg.too_tired": "§c磁力が足りない。",
    "msg.exhausted": "§c磁力を使い果たした。",
    "msg.no_mag": "§c磁力が足りない。",
    "msg.cooldown": "§7まだ再充填中だ。",
    "msg.locked": "§7この技はまだ扱えない。",
    "msg.stage_up": "§6段階が上がった。",
    "msg.tech_set": "§d技を選択：",
    "msg.hero_set": "§d姿を選択：",
    "msg.ally_summoned": "§dブラザーフッドが応じた。",
    "msg.no_target": "§7そこには何も無い。",
    "msg.immune": "§cアダマンチウムには磁力が効かない。",
    "msg.reset": "§7全て初期化した。",
    "msg.scan": "§b走査完了：",
    "title.awaken": "§dＸ　Ｇ Ｅ Ｎ Ｅ",
    "title.awaken_sub": "お前は、もう人間ではない",
    "title.transform": "§5磁 界 の 帝 王",
    "title.transform_sub": "MASTER OF MAGNETISM",
    "title.ultimate": "§c磁 界 の 棺",
    "title.ultimate_sub": "SPHERE OF RUIN",
    "ui.terminal": "セレブロ端末",
    "ui.terminal_body": "何を視る？",
    "ui.pick_tech": "技を選ぶ",
    "ui.pick_hero": "姿を選ぶ",
    "ui.status": "状態",
    "ui.scan_metal": "金属を走査",
    "ui.scan_mutant": "ミュータントを走査",
    "ui.summon": "ブラザーフッドを招集",
    "ui.close": "閉じる",
    "ui.give_tech": "技アイテムを受け取る",
    "class.stage1": "エリック",
    "class.stage2": "マグニートー",
    "class.stage3": "磁界の帝王",
}

UI_EN = {
    "hud.mag": "Magnetism",
    "hud.stage": "Stage",
    "hud.tech": "Selected",
    "hud.cooldown": "Recharging",
    "hud.flying": "Magnetic Flight",
    "hud.barrier": "Barrier Active",
    "hud.sight": "Magnetic Sight",
    "msg.welcome": "§d[X-Gene]§r Something in your blood is waking up.",
    "msg.welcome_hint": "§7Craft and drink the X-Gene to awaken.",
    "msg.welcome_tech": "§7Use the helmet to transform, sneak+use for options.",
    "msg.awakened": "§dAwakened.§r Every metal on earth is speaking to you.",
    "msg.already_mutant": "§7You have already awakened.",
    "msg.no_power": "§7No power yet. Drink the X-Gene.",
    "msg.transform": "§5Transformed:§r Master of Magnetism",
    "msg.revert": "§7You let the field go.",
    "msg.too_tired": "§cNot enough magnetism.",
    "msg.exhausted": "§cYour field has collapsed.",
    "msg.no_mag": "§cNot enough magnetism.",
    "msg.cooldown": "§7Still recharging.",
    "msg.locked": "§7You cannot wield this yet.",
    "msg.stage_up": "§6You have advanced a stage.",
    "msg.tech_set": "§dTechnique selected: ",
    "msg.hero_set": "§dForm selected: ",
    "msg.ally_summoned": "§dThe Brotherhood answers.",
    "msg.no_target": "§7Nothing there.",
    "msg.immune": "§cAdamantium does not answer to magnetism.",
    "msg.reset": "§7Everything reset.",
    "msg.scan": "§bScan complete: ",
    "title.awaken": "§dX  G E N E",
    "title.awaken_sub": "You are not human any more",
    "title.transform": "§5M A G N E T O",
    "title.transform_sub": "MASTER OF MAGNETISM",
    "title.ultimate": "§cS P H E R E   O F   R U I N",
    "title.ultimate_sub": "SPHERE OF RUIN",
    "ui.terminal": "Cerebro Terminal",
    "ui.terminal_body": "What do you want to see?",
    "ui.pick_tech": "Choose a technique",
    "ui.pick_hero": "Choose a form",
    "ui.status": "Status",
    "ui.scan_metal": "Scan for metal",
    "ui.scan_mutant": "Scan for mutants",
    "ui.summon": "Summon the Brotherhood",
    "ui.close": "Close",
    "ui.give_tech": "Receive technique items",
    "class.stage1": "Erik",
    "class.stage2": "Magneto",
    "class.stage3": "Master of Magnetism",
}


def build(lang: str) -> str:
    ja = lang == "ja_JP"
    lines = [
        f"pack.name={PACK_JA if ja else PACK_EN}",
        f"pack.description={PACK_DESC_JA if ja else PACK_DESC_EN}",
        "",
        "## entities",
    ]
    for key in K.ENTITY_KEYS:
        if key in K.CHARACTERS:
            c = K.CHARACTERS[key]
            name = c["ja"] if ja else c["en"]
        else:
            p = K.PROP_ENTITIES[key]
            name = p["ja"] if ja else p["en"]
        lines.append(f"entity.{K.eid(key)}.name={name}")
        lines.append(f"item.spawn_egg.entity.{K.eid(key)}.name="
                     f"{name}{'のスポーンエッグ' if ja else ' Spawn Egg'}")

    lines += ["", "## items"]
    items = gen_bp.all_items()
    for key, spec in items.items():
        name = spec["ja"] if ja else spec["en"]
        lines.append(f"item.{K.eid(key)}={name}")
        lines.append(f"item.{K.eid(key)}.name={name}")

    lines += ["", "## techniques"]
    for name, spec in K.TECHNIQUES.items():
        label = spec["ja"] if ja else spec["en"]
        lines.append(f"{K.NS}.tech.{name}={label}")
        lines.append(f"{K.NS}.tech.{name}.desc="
                     f"{spec['desc_ja'] if ja else spec['en']}")
    for character, techs in K.ALLY_TECHNIQUES.items():
        for t in techs:
            label = t["ja"] if ja else t["en"]
            lines.append(f"{K.NS}.tech.{t['key']}={label}")
            lines.append(f"{K.NS}.tech.{t['key']}.desc="
                         f"{t['desc_ja'] if ja else t['en']}")

    lines += ["", "## characters"]
    for key, c in K.CHARACTERS.items():
        lines.append(f"{K.NS}.hero.{key}={c['ja'] if ja else c['en']}")
        real = c.get("real_ja" if ja else "real_en")
        if real:
            lines.append(f"{K.NS}.hero.{key}.real={real}")
        if ja and c.get("blurb_ja"):
            lines.append(f"{K.NS}.hero.{key}.blurb={c['blurb_ja']}")
        elif not ja:
            lines.append(f"{K.NS}.hero.{key}.blurb={c['en']}")

    lines += ["", "## ui"]
    table = UI_JA if ja else UI_EN
    for key, value in table.items():
        lines.append(f"{K.NS}.{key}={value}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    K.ensure_dirs()
    print("language files:")
    for pack in (K.RP, K.BP):
        os.makedirs(os.path.join(pack, "texts"), exist_ok=True)
        with open(os.path.join(pack, "texts", "languages.json"), "w",
                  encoding="utf-8") as fh:
            fh.write('[ "ja_JP", "en_US" ]\n')
        for lang in ("ja_JP", "en_US"):
            path = os.path.join(pack, "texts", f"{lang}.lang")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(build(lang))
            print(f"  {os.path.relpath(path, K.ROOT)}")


if __name__ == "__main__":
    main()
