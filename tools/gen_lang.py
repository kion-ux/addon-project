# -*- coding: utf-8 -*-
"""Writes ja_JP / en_US language files for both packs."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BP = os.path.join(ROOT, "packs", "kaiju8_BP")
RP = os.path.join(ROOT, "packs", "kaiju8_RP")

ITEMS = {
    "kaiju_core": ("怪獣核", "Kaiju Core"),
    "kaiju_shell": ("怪獣外殻", "Kaiju Carapace"),
    "kaiju_alloy": ("怪獣合金", "Kaiju Alloy"),
    "kaiju_remains": ("怪獣残骸", "Kaiju Remains"),
    "combat_blade": ("討伐隊制式刀", "Defense Force Blade"),
    "df_rifle": ("討伐隊制式銃", "Defense Force Rifle"),
    "weapon_no2": ("識別怪獣兵器2号", "Numbers Weapon No.2"),
    "weapon_no4": ("識別怪獣兵器4号 双刃刀", "Numbers Weapon No.4 - Twin Blades"),
    "battle_axe": ("大型戦斧", "Heavy Battle Axe"),
    "combat_suit_helmet": ("討伐隊戦闘服 ヘルメット", "Combat Suit Helmet"),
    "combat_suit_chestplate": ("討伐隊戦闘服 上衣", "Combat Suit Jacket"),
    "combat_suit_leggings": ("討伐隊戦闘服 脚部", "Combat Suit Leggings"),
    "combat_suit_boots": ("討伐隊戦闘服 ブーツ", "Combat Suit Boots"),
    "parasite_kaiju": ("小型怪獣", "Small Kaiju"),
    "no8_power": ("怪獣8号の力", "Power of Kaiju No.8"),
    "kaiju_detector": ("怪獣探知機", "Kaiju Detector"),
    "no8_form": ("怪獣8号の体", "Kaiju No.8 Body"),
}

ENTITIES = {
    "yoju": ("余獣", "Yoju"),
    "honju": ("本獣", "Honju"),
    "kaiju_no8": ("怪獣8号", "Kaiju No.8"),
    "kaiju_no9": ("怪獣9号", "Kaiju No.9"),
    "kaiju_no10": ("怪獣10号", "Kaiju No.10"),
    "defense_force_officer": ("日本防衛隊 隊員", "Defense Force Officer"),
    "kafka_hibino": ("日比野カフカ", "Kafka Hibino"),
    "reno_ichikawa": ("市川レノ", "Reno Ichikawa"),
    "mina_ashiro": ("亜白ミナ", "Mina Ashiro"),
    "soshiro_hoshina": ("保科宗四郎", "Soshiro Hoshina"),
    "kikoru_shinomiya": ("四ノ宮キコル", "Kikoru Shinomiya"),
    "parasite_kaiju": ("小型怪獣", "Small Kaiju"),
    "rifle_beam": ("砲撃", "Cannon Round"),
    "kaiju_acid": ("怪獣の酸", "Kaiju Acid"),
    "df_bullet": ("弾丸", "Bullet"),
}

EGGS = ["yoju", "honju", "kaiju_no8", "kaiju_no9", "kaiju_no10",
        "defense_force_officer", "kafka_hibino", "reno_ichikawa",
        "mina_ashiro", "soshiro_hoshina", "kikoru_shinomiya", "parasite_kaiju"]

UI = {
    "kaiju8.rank.cadet": ("訓練生", "Cadet"),
    "kaiju8.rank.member": ("一般隊員", "Officer"),
    "kaiju8.rank.senior": ("上級隊員", "Senior Officer"),
    "kaiju8.rank.vice_captain": ("副隊長", "Vice-Captain"),
    "kaiju8.rank.captain": ("隊長", "Captain"),
    "kaiju8.rank.director": ("長官", "Director General"),

    "kaiju8.msg.welcome": ("§b[日本防衛隊]§r 本日付で第3部隊への配属を命ずる。",
                           "§b[Defense Force]§r You are hereby assigned to the Third Division."),
    "kaiju8.msg.welcome_hint": ("§7怪獣探知機をスニーク使用で討伐隊端末が開く。",
                                "§7Sneak-use the Kaiju Detector to open your Defense Force terminal."),
    "kaiju8.msg.power_gained": ("§c体の奥で何かが弾けた…… 怪獣8号の力を得た！",
                                "§cSomething burst open inside you - you have the power of Kaiju No.8!"),
    "kaiju8.msg.already_power": ("§7既にその力は体に宿っている。",
                                 "§7That power already lives in you."),
    "kaiju8.msg.no_power": ("§7何も起こらない。まだ「力」がない。",
                            "§7Nothing happens. You do not have the power yet."),
    "kaiju8.msg.too_tired": ("§7体が変身に耐えられない。少し休め。",
                             "§7Your body cannot take the transformation yet."),
    "kaiju8.msg.exhausted": ("§c怪獣化が解けた。全身が軋む……",
                             "§cThe transformation broke. Your whole body is screaming."),
    "kaiju8.msg.strain": ("§c解放戦力が高すぎる。身体が悲鳴を上げている！",
                          "§cThe release rate is too high - your body cannot hold it!"),
    "kaiju8.msg.subjugated": ("§a討伐完了:§r %s", "§aSubjugated:§r %s"),
    "kaiju8.msg.identified_down": ("§6§l識別怪獣 %s の討伐を確認！",
                                   "§6§lIdentified kaiju %s has been confirmed down!"),
    "kaiju8.msg.alert": ("§c§l[怪獣災害]§r %s の出現を確認。討伐対象 %s 体。",
                         "§c§l[Kaiju Disaster]§r %s sighted. %s hostiles inbound."),
    "kaiju8.msg.alerts_on": ("§a怪獣災害警報: 有効", "§aKaiju disaster alerts: ON"),
    "kaiju8.msg.alerts_off": ("§7怪獣災害警報: 無効", "§7Kaiju disaster alerts: OFF"),
    "kaiju8.msg.scan_clear": ("§a周囲に怪獣反応なし。", "§aNo kaiju detected nearby."),
    "kaiju8.msg.scan_header": ("§e怪獣反応 %s 件:", "§e%s kaiju detected:"),
    "kaiju8.msg.release_set": ("§b解放戦力を %s%% に設定した。",
                               "§bCombat power release set to %s%%."),
    "kaiju8.msg.release_capped": ("§7戦闘服がなければ %s%% までしか耐えられない。",
                                  "§7Without the full combat suit your body caps out at %s%%."),
    "kaiju8.msg.fire_no2": ("§b砲撃", "§bCannon fired"),
    "kaiju8.msg.slash": ("§b高速斬撃", "§bHigh-speed slash"),
    "kaiju8.msg.smash": ("§6叩きつけ", "§6Ground smash"),
    "kaiju8.msg.reset": ("§7記録を初期化した。", "§7Your record has been reset."),

    "kaiju8.title.awaken": ("§c怪獣8号", "§cKAIJU NO.8"),
    "kaiju8.title.awaken_sub": ("§f人間のまま、怪獣になった。",
                                "§fStill human - and now a kaiju."),
    "kaiju8.title.transform": ("§c解放", "§cRELEASE"),
    "kaiju8.title.transform_sub": ("§f怪獣8号 —— 変身", "§fKaiju No.8 - transformed"),
    "kaiju8.title.alert": ("§c§l怪獣災害発生", "§c§lKAIJU DISASTER"),
    "kaiju8.title.alert_sub": ("§f至急、討伐に向かえ", "§fProceed to subjugation immediately"),
    "kaiju8.title.promoted": ("§b昇進", "§bPROMOTED"),

    "kaiju8.hud.form": ("§c怪獣化", "§cKAIJU FORM"),

    "kaiju8.ui.terminal": ("討伐隊端末", "Defense Force Terminal"),
    "kaiju8.ui.body": ("討伐数: §e%s§r    解放戦力: §b%s%%§r",
                       "Subjugations: §e%s§r    Release rate: §b%s%%§r"),
    "kaiju8.ui.set_release": ("解放戦力の設定", "Set combat power release"),
    "kaiju8.ui.release_label": ("解放戦力 (%)", "Release rate (%)"),
    "kaiju8.ui.record": ("討伐記録", "Service record"),
    "kaiju8.ui.scan": ("怪獣スキャン", "Scan for kaiju"),
    "kaiju8.ui.alerts_on": ("怪獣災害警報: 有効", "Disaster alerts: ON"),
    "kaiju8.ui.alerts_off": ("怪獣災害警報: 無効", "Disaster alerts: OFF"),
    "kaiju8.ui.record_kills": ("討伐数: §e%s", "Subjugations: §e%s"),
    "kaiju8.ui.record_rank": ("階級:", "Rank:"),
    "kaiju8.ui.record_release": ("解放戦力: §b%s%%", "Release rate: §b%s%%"),
    "kaiju8.ui.record_suit": ("戦闘服 一式着用: %s", "Full combat suit: %s"),
    "kaiju8.ui.record_no8": ("怪獣化エネルギー: %s", "Kaiju energy: %s"),
    "kaiju8.ui.close": ("閉じる", "Close"),
}

PACK = {
    "BP": {
        "pack.name": ("§c怪獣8号§r アドオン [動作]", "§cKaiju No.8§r Add-on [Behavior]"),
        "pack.description": ("日本防衛隊の装備・怪獣災害・怪獣8号への変身。",
                             "Defense Force gear, kaiju disasters and the Kaiju No.8 transformation."),
    },
    "RP": {
        "pack.name": ("§c怪獣8号§r アドオン [表示]", "§cKaiju No.8§r Add-on [Resource]"),
        "pack.description": ("怪獣・討伐隊のモデルとテクスチャ。",
                             "Models and textures for the kaiju and the Defense Force."),
    },
}


def write_lang(folder, pack_key, include_content):
    os.makedirs(folder, exist_ok=True)
    for idx, code in ((0, "ja_JP"), (1, "en_US")):
        out = []
        for key, vals in PACK[pack_key].items():
            out.append(f"{key}={vals[idx]}")
        if include_content:
            out.append("")
            for name, vals in ITEMS.items():
                out.append(f"item.kaiju8:{name}={vals[idx]}")
                out.append(f"item.kaiju8:{name}.name={vals[idx]}")
            out.append("")
            for name, vals in ENTITIES.items():
                out.append(f"entity.kaiju8:{name}.name={vals[idx]}")
            out.append("")
            for name in EGGS:
                label = (f"{ENTITIES[name][0]}のスポーンエッグ" if idx == 0
                         else f"Spawn {ENTITIES[name][1]}")
                out.append(f"item.spawn_egg.entity.kaiju8:{name}.name={label}")
            out.append("")
            for key, vals in UI.items():
                out.append(f"{key}={vals[idx]}")
        with open(os.path.join(folder, code + ".lang"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"  {os.path.relpath(folder, ROOT)}/{code}.lang")
    with open(os.path.join(folder, "languages.json"), "w", encoding="utf-8") as fh:
        json.dump(["en_US", "ja_JP"], fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    print("language files:")
    write_lang(os.path.join(RP, "texts"), "RP", True)
    write_lang(os.path.join(BP, "texts"), "BP", False)
