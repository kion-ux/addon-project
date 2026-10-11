# -*- coding: utf-8 -*-
"""言語ファイル（日本語 / English）。スクリプトが使う翻訳キーもここに全部ある。
validate_aot.py が、スクリプトに書いた aot.* のキーがここに揃っているかを調べる。"""
from __future__ import annotations

import os

import aot_common as C
from aot_common import BP, RP

# (キー, 日本語, English)
L = [
    ("pack.name", "進撃の巨人アドオン", "Attack on Titan Add-on"),
    ("pack.description", "§7立体機動装置・うなじ・無垢の巨人・調査兵団（非公式ファンメイド）",
     "§7ODM gear, nape slashing, pure titans and the Survey Corps (unofficial fan-made)"),

    # ---- アイテム ----
    ("item.aot:odm_blades", "超硬質スチールの刃", "Ultrahard Steel Blades"),
    ("item.aot:thunder_spear", "雷槍", "Thunder Spear"),
    ("item.aot:gas_canister", "ガスボンベ", "Gas Canister"),
    ("item.aot:spare_blades", "替え刃", "Spare Blades"),
    ("item.aot:hardened_steel", "超硬質スチール", "Ultrahard Steel"),
    ("item.aot:survey_journal", "調査兵団の手帳", "Survey Corps Journal"),
    ("item.aot:flare_gun", "信煙弾", "Flare Gun"),
    ("item.aot:odm_gear", "立体機動装置", "ODM Gear"),
    ("item.aot:survey_jacket", "調査兵団の上着とマント", "Survey Corps Jacket & Cloak"),
    ("item.aot:survey_boots", "兵団のブーツ", "Military Boots"),

    # ---- エンティティ ----
    ("entity.aot:titan_small.name", "4m級巨人", "4-Meter Class Titan"),
    ("entity.aot:titan_medium.name", "7m級巨人", "7-Meter Class Titan"),
    ("entity.aot:titan_large.name", "13m級巨人", "13-Meter Class Titan"),
    ("entity.aot:titan_abnormal.name", "奇行種", "Abnormal Titan"),
    ("entity.aot:eren_yeager.name", "エレン・イェーガー", "Eren Yeager"),
    ("entity.aot:mikasa_ackerman.name", "ミカサ・アッカーマン", "Mikasa Ackerman"),
    ("entity.aot:armin_arlert.name", "アルミン・アルレルト", "Armin Arlert"),
    ("entity.aot:levi_ackerman.name", "リヴァイ・アッカーマン", "Levi Ackerman"),
    ("entity.aot:hange_zoe.name", "ハンジ・ゾエ", "Hange Zoë"),
    ("entity.aot:erwin_smith.name", "エルヴィン・スミス", "Erwin Smith"),
    ("entity.aot:jean_kirstein.name", "ジャン・キルシュタイン", "Jean Kirstein"),
    ("entity.aot:sasha_blouse.name", "サシャ・ブラウス", "Sasha Blouse"),
    ("entity.aot:connie_springer.name", "コニー・スプリンガー", "Connie Springer"),
    ("entity.aot:survey_soldier.name", "調査兵", "Survey Corps Soldier"),

    # ---- 画面の表示 ----
    ("aot.title.kill", "討伐！", "TITAN SLAIN!"),
    ("aot.title.kill_count", "討伐数 %s", "Kills: %s"),
    ("aot.title.grabbed", "巨人に掴まれた！", "A titan has you!"),
    ("aot.title.grabbed_hint", "刃で斬れ（スニークで指を斬って脱出）",
     "Slash it! (sneak to cut its fingers and escape)"),
    ("aot.title.escaped", "脱出！", "Escaped!"),
    ("aot.title.no_gas", "ガスが切れた", "Out of gas"),
    ("aot.title.need_gear", "立体機動装置を脚に装備しよう", "Equip the ODM gear (legs slot)"),
    ("aot.title.shallow", "浅い！　勢いが足りない", "Too shallow! Not enough momentum"),
    ("aot.title.ankle", "腱を削いだ — 膝をついた！", "Tendons cut - it's down on its knees!"),
    ("aot.title.eyes", "目を潰した！", "Blinded it!"),
    ("aot.title.no_spare", "替え刃がない！", "No spare blades!"),
    ("aot.msg.gas_full", "ガスは満タンだ", "Your gas is already full"),
    ("aot.msg.gas_refilled", "ガスを補給した", "Gas refilled"),
    ("aot.msg.swapped", "刃を替えた（替え刃 残り %s）", "Blades replaced (%s spares left)"),
    ("aot.msg.rank_up", "昇進した:", "Promoted to"),
    ("aot.msg.flare_seen", "%s が信煙弾を撃った:", "%s fired a flare:"),
    ("aot.msg.rally", "「心臓を捧げよ！」 — 力が湧いてくる",
     "\"Dedicate your hearts!\" - you feel your strength rise"),
    ("aot.msg.kit_taken", "装備はもう支給されている", "Your gear has already been issued"),
    ("aot.msg.kit_given", "調査兵団の装備一式が支給された", "Survey Corps gear issued"),
    ("aot.msg.saved", "設定を保存した", "Settings saved"),
    ("aot.msg.welcome", "心臓を捧げよ！　進撃の巨人アドオンへようこそ",
     "Dedicate your hearts! Welcome to the Attack on Titan add-on"),
    ("aot.msg.welcome_hint", "調査兵団の手帳を右クリックすると、操作説明と装備の支給があります",
     "Use the Survey Corps Journal for the controls and to receive your gear"),
    ("aot.msg.reset", "討伐数と支給の記録を消した", "Kills and gear record reset"),
    ("aot.flare.green", "§a緑（進路）", "§aGreen (heading)"),
    ("aot.flare.red", "§c赤（巨人発見）", "§cRed (titan spotted)"),
    ("aot.flare.black", "§8黒（奇行種）", "§8Black (abnormal)"),
    ("aot.flare.yellow", "§e黄（作戦成功）", "§eYellow (mission complete)"),

    # ---- HUD ----
    ("aot.hud.gas", "ガス", "Gas"),
    ("aot.hud.blade", "刃", "Blade"),
    ("aot.hud.spare", "替え刃×%s", "Spares x%s"),
    ("aot.hud.spear", "雷槍×%s", "Spears x%s"),
    ("aot.hud.kills", "討伐 %s", "Kills %s"),

    # ---- 階級 ----
    ("aot.rank.trainee", "訓練兵", "Trainee"),
    ("aot.rank.recruit", "新兵", "Recruit"),
    ("aot.rank.soldier", "兵士", "Soldier"),
    ("aot.rank.elite", "精鋭", "Elite"),
    ("aot.rank.squad_leader", "班長", "Squad Leader"),
    ("aot.rank.section_commander", "分隊長", "Section Commander"),
    ("aot.rank.captain", "兵士長", "Captain"),

    # ---- 手帳 ----
    ("aot.ui.title", "調査兵団の手帳", "Survey Corps Journal"),
    ("aot.ui.rank", "階級:", "Rank:"),
    ("aot.ui.kills", "討伐数: %s", "Titans slain: %s"),
    ("aot.ui.gas", "ガス: %s%%", "Gas: %s%%"),
    ("aot.ui.spares", "替え刃: %s 組", "Spare blades: %s"),
    ("aot.ui.motto", "心臓を捧げよ。", "Dedicate your hearts."),
    ("aot.ui.btn.controls", "立体機動の操作", "ODM controls"),
    ("aot.ui.btn.titans", "巨人図鑑", "Titan guide"),
    ("aot.ui.btn.corps", "調査兵団", "The Survey Corps"),
    ("aot.ui.btn.kit", "装備の支給を受ける", "Receive your gear"),
    ("aot.ui.btn.settings", "設定", "Settings"),
    ("aot.ui.back", "戻る", "Back"),
    ("aot.ui.ctl.anchor",
     "§l右クリック長押し§r: 視線の先（45m）へアンカーを撃ち込み、押している間ワイヤーを巻き取って飛ぶ。"
     "巨人に刺せば、巨人が動いても刺さったまま。脚に立体機動装置、手に刃が必要。",
     "§lHold use§r: fire the anchors where you look (45m) and reel in while held. "
     "Anchors stick to titans and move with them. Needs the ODM gear on your legs and blades in hand."),
    ("aot.ui.ctl.release", "§l離す§r: ワイヤーを切り離す。勢いはしばらく残るので、弧を描いて飛べる。",
     "§lRelease§r: cut the wires. Your momentum carries you in an arc for a moment."),
    ("aot.ui.ctl.boost", "§l空中でジャンプ§r: ガスを噴いて視線の方向へ加速する（ガス 6）。",
     "§lJump in the air§r: a gas burst in the direction you look (6 gas)."),
    ("aot.ui.ctl.spin", "§l空中でスニーク§r: 回転斬り。周りを斬り、うなじが範囲内なら削ぐ（ガス 5）。",
     "§lSneak in the air§r: spinning slash. Cuts everything around you and the nape if it's in reach (5 gas)."),
    ("aot.ui.ctl.nape",
     "§lうなじ§r: 巨人の首の後ろ。後ろか上から斬れば一撃で倒せる。ただし勢い（速さ、またはワイヤーを"
     "使った直後）が無いと「浅い」。体のほかの場所は斬っても蒸気を上げて再生する。",
     "§lThe nape§r: the back of the neck. Strike it from behind or above to kill in one blow - "
     "but only with momentum (speed, or right after using the wires); otherwise the cut is too shallow. "
     "Everywhere else regenerates in a cloud of steam."),
    ("aot.ui.ctl.pass", "§l巨人に刺して巻き取る§r: うなじの脇を勢いよく抜けると自動で斬る。",
     "§lAnchor into a titan and reel in§r: sweep past its nape at speed and you cut it automatically."),
    ("aot.ui.ctl.ankle", "§l足首を斬る§r: 腱を削ぐと巨人が膝をつき、うなじが下がる。",
     "§lCut the ankles§r: sever the tendons and the titan drops to its knees, bringing the nape down."),
    ("aot.ui.ctl.land", "§l着地§r: 落ちる直前にガスを噴いて衝撃を消す（立体機動装置とガスが必要）。",
     "§lLanding§r: a gas burst just before you hit the ground cancels fall damage (needs gear and gas)."),
    ("aot.ui.ctl.blades", "§l刃§r: 斬るたびに刃こぼれする。限界が来ると替え刃に自動で交換する。",
     "§lBlades§r: they chip with every cut and are swapped for a spare automatically when worn out."),
    ("aot.ui.ctl.gas", "§lガス§r: アンカー・巻き取り・噴射で減る。ガスボンベを使うと満タンになる。",
     "§lGas§r: spent by anchors, reeling and bursts. Drink a gas canister to refill."),
    ("aot.ui.ctl.spear", "§l雷槍§r: 右クリックで撃つ。刺さって 1.2 秒後に爆発。うなじの近くなら一撃。",
     "§lThunder spear§r: use to fire. It sticks and detonates after 1.2s - fatal near the nape."),
    ("aot.ui.ctl.grab", "§l掴まれたら§r: 刃で斬るか、スニークで指を斬って脱出（ガス 10）。2.5 秒で食われる。",
     "§lIf grabbed§r: slash, or sneak to cut the fingers (10 gas). You have 2.5 seconds."),
    ("aot.ui.ctl.flare", "§l信煙弾§r: 右クリックで撃つ。スニーク＋右クリックで色を変える。",
     "§lFlare gun§r: use to fire, sneak + use to change the colour."),
    ("aot.ui.titan.intro",
     "巨人は人だけを狙い、うなじ以外の傷は再生する。素材は落とさず、倒すと蒸気になって消える。",
     "Titans hunt only humans and regenerate any wound but the nape. They drop nothing and "
     "evaporate when slain."),
    ("aot.ui.titan.titan_small", "§l4m級§r — 小型。掴みはしないが噛みつく。足首を狙いやすい。",
     "§l4-meter class§r - small. Bites instead of grabbing. Easy to hamstring."),
    ("aot.ui.titan.titan_medium", "§l7m級§r — 手が届けば掴んで口へ運ぶ。上半身の前に浮くと払われる。",
     "§l7-meter class§r - grabs anything in reach and swats at soldiers in front of its chest."),
    ("aot.ui.titan.titan_large", "§l13m級§r — 大型。歩くたびに地面が揺れる。うなじまで立体機動が要る。",
     "§l13-meter class§r - large. The ground shakes as it walks; you need ODM to reach the nape."),
    ("aot.ui.titan.titan_abnormal", "§l奇行種§r — 予測できない動き。突然跳びかかり、全力で走る。",
     "§lAbnormal§r - unpredictable. Leaps without warning and sprints flat out."),
    ("aot.ui.titan.night", "夜は日光が無いので座り込んで動かない。攻撃すると起きる。",
     "At night, without sunlight, titans sit motionless - until attacked."),
    ("aot.ui.titan.regen", "最後に斬られてから 3 秒で再生が始まる。雷槍の傷はしばらく治らない。",
     "Regeneration starts 3 seconds after the last cut. Thunder spear wounds heal slowly."),
    ("aot.ui.corps.intro", "スポーンエッグで呼べる。巨人を見つけると自分で立体機動の攻撃を仕掛ける。",
     "Summon them with spawn eggs. They launch their own ODM attacks on titans they see."),
    ("aot.ui.corps.levi", "§lリヴァイ§r — 人類最強の兵士。二連撃でほぼ確実にうなじを削ぐ。",
     "§lLevi§r - humanity's strongest soldier. A double strike that almost never misses."),
    ("aot.ui.corps.mikasa", "§lミカサ§r — 赤いマフラー。リヴァイに次ぐ腕前、二連撃。",
     "§lMikasa§r - the red scarf. Second only to Levi, with a double strike."),
    ("aot.ui.corps.eren", "§lエレン§r — 巨人を一匹残らず駆逐すると誓った少年。",
     "§lEren§r - the boy who swore to wipe out every last titan."),
    ("aot.ui.corps.armin", "§lアルミン§r — 戦いは苦手だが、知恵で仲間を救う。",
     "§lArmin§r - not much of a fighter, but his wits save his friends."),
    ("aot.ui.corps.erwin", "§lエルヴィン§r — 団長。近くで巨人と戦うと、周りの仲間を奮い立たせる。",
     "§lErwin§r - the commander. Near a titan fight he rallies everyone around him."),
    ("aot.ui.corps.hange", "§lハンジ§r — 巨人の研究者。眼鏡とゴーグル。",
     "§lHange§r - the titan researcher, with glasses and goggles."),
    ("aot.ui.corps.others", "§lジャン・サシャ・コニー§r と調査兵も一緒に戦う。",
     "§lJean, Sasha and Connie§r and rank-and-file soldiers fight alongside you."),
    ("aot.ui.corps.recruit",
     "パンかベイクドポテトを渡すと仲間になって付いてくる（サシャはベイクドポテトだけ）。"
     "仲間は右クリックで待機させられる。",
     "Give them bread or a baked potato to recruit them (Sasha only takes baked potatoes). "
     "Use a recruit to make them wait."),
    ("aot.ui.set.spawns", "巨人が自然に湧く", "Titans spawn naturally"),
    ("aot.ui.set.grab", "巨人がプレイヤーを掴む", "Titans can grab players"),
    ("aot.ui.set.hud", "画面下にガスと刃を表示", "Show gas and blades on screen"),
]

SPAWN_EGG = {
    "titan_small": ("4m級巨人のスポーンエッグ", "Spawn 4-Meter Titan"),
    "titan_medium": ("7m級巨人のスポーンエッグ", "Spawn 7-Meter Titan"),
    "titan_large": ("13m級巨人のスポーンエッグ", "Spawn 13-Meter Titan"),
    "titan_abnormal": ("奇行種のスポーンエッグ", "Spawn Abnormal Titan"),
}


def entries():
    out = list(L)
    names = {k: (ja, en) for k, ja, en in L}
    for key, (ja, en) in SPAWN_EGG.items():
        out.append((f"item.spawn_egg.entity.aot:{key}.name", ja, en))
    for key in C.SOLDIERS:
        ja, en = names[f"entity.aot:{key}.name"]
        out.append((f"item.spawn_egg.entity.aot:{key}.name", f"{ja}を呼ぶ", f"Spawn {en}"))
    return out


def main():
    E = entries()
    for pack in (BP, RP):
        d = os.path.join(pack, "texts")
        os.makedirs(d, exist_ok=True)
        for lang, col in (("ja_JP", 1), ("en_US", 2)):
            with open(os.path.join(d, f"{lang}.lang"), "w", encoding="utf-8") as fh:
                for e in E:
                    if pack == BP and not e[0].startswith("pack."):
                        continue
                    fh.write(f"{e[0]}={e[col]}\n")
        C.write_json(os.path.join(d, "languages.json"), ["ja_JP", "en_US"])
    print(f"  lang: {len(E)} keys")


KEYS = {e[0] for e in entries()}

if __name__ == "__main__":
    main()
