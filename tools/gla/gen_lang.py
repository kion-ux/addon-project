# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — ja_JP / en_US の言語ファイル (企画書 §12 / §18)。

画面に出る文字の出所をこの1枚に集める。守っているのは3つ:

* 技名・形態名・アイテム名・区画名・品質名を手で書かない。すべて spec.py
  から引く（企画書 §09「技を1つ足すときに触るのは spec.py だけ」）。
  ここで名前を打ち直すと、spec を直しても画面の文字だけ古いまま残る。
* 日本語と英語で **同じキー集合** を出す。片方に無いキーはその言語で生の id
  （gla.msg.xxx）が画面に出てしまうので、main() で突き合わせて落とす。
* スマホの1行に収まる長さで書く（企画書 §12 スマホの読みやすさ）。常時表示は
  形態名・技・気力・再使用待ちの4つだけで、説明はメニュー側へ逃がす。

表示名は「短縮名（画面用）」と「正式名称」を分けてある。メッセージの頭に付ける
のは短縮名の §6[GLA]§r で、正式名称と非公式である旨は gla.name.full と
pack.description の2か所だけが持つ（企画書 §18 非公式であることの明示）。

出力: packs/gla_RP/texts/ と packs/gla_BP/texts/ の
      ja_JP.lang / en_US.lang / languages.json。
"""
from __future__ import annotations

import json
import os
import sys
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import spec                                             # noqa: E402

NS = spec.NS
BP = os.path.join(ROOT, spec.BP_DIR, "texts")
RP = os.path.join(ROOT, spec.RP_DIR, "texts")

#  添字0が ja_JP、1が en_US。怪獣8号側の tools/gen_lang.py と同じ並び。
Pair = Tuple[str, str]
#  None は .lang の空行（節の区切り）。
Row = Optional[Tuple[str, Pair]]

# ---------------------------------------------------------------------------
#  spec から引く定数 — 文中の数字も手で書かない
# ---------------------------------------------------------------------------
HAT = spec.ITEM_BY_SLUG["straw_hat"]
WRAP = spec.ITEM_BY_SLUG["fist_wrap"]
POSE = spec.ITEM_BY_SLUG["log_pose"]
FRUIT = spec.ITEM_BY_SLUG["devil_fruit"]
LAST_UNLOCK = max(f.unlock_hits for f in spec.FORMS)     # 最後の形態の解放命中数
ENERGY_MAX = int(spec.ENERGY_MAX)
GROUND = spec.TRAINING["size"]

# ---------------------------------------------------------------------------
#  アドオンの名前 — 短縮名と正式名称を分ける (企画書 §12 / §18)
#
#  画面に流れるメッセージには短縮名しか出さない。スマホの1行は短く、毎回
#  「GRAND LINE AWAKENING — 非公式ファン制作」と出ると本文が読めなくなる。
# ---------------------------------------------------------------------------
SHORT = "§6[GLA]§r"

NAME: Dict[str, Pair] = {
    f"{NS}.name.short": ("§6GLA§r", "§6GLA§r"),
    f"{NS}.name.full": (
        "GRAND LINE AWAKENING（非公式ファン制作）",
        "GRAND LINE AWAKENING (unofficial fan work)"),
}

# ---------------------------------------------------------------------------
#  パック名と説明 (企画書 §18)
#
#  説明文は非公式であることを必ず含める。Minecraft・ONE PIECE の公式商品では
#  なく権利者とは無関係、というのはパック一覧で最初に目に入る場所に要る。
#  名前側は一覧で切れないよう短く、[動作] / [表示] だけで役割を分ける。
# ---------------------------------------------------------------------------
UNOFFICIAL_JA = "非公式ファン制作。Minecraft・ONE PIECE の公式商品ではありません。"
UNOFFICIAL_EN = ("Unofficial fan work. Not an official Minecraft or "
                 "ONE PIECE product.")

PACK: Dict[str, Dict[str, Pair]] = {
    "BP": {
        "pack.name": ("§6GRAND LINE AWAKENING§r [動作]",
                      "§6GRAND LINE AWAKENING§r [Behavior]"),
        "pack.description": (
            f"ルフィの変身と24の技、訓練場。{UNOFFICIAL_JA}",
            f"Luffy's forms, 24 techniques and a training ground. "
            f"{UNOFFICIAL_EN}"),
    },
    "RP": {
        "pack.name": ("§6GRAND LINE AWAKENING§r [表示]",
                      "§6GRAND LINE AWAKENING§r [Resource]"),
        "pack.description": (
            f"形態のモデル・技の演出・アイコン。{UNOFFICIAL_JA}",
            f"Form models, technique effects and icons. {UNOFFICIAL_EN}"),
    },
}

# ---------------------------------------------------------------------------
#  常時表示 (企画書 §12)
#
#  通常プレイ中に出すのは 形態名 / 選択中の技 / 気力 / 再使用待ち の4つだけ。
#  ここに5つ目を足したくなったらメニュー側（gla.ui.*）へ回す。
#  値は「見出し」なので最短の語にしてある — 本体は形態名と技名が占める。
# ---------------------------------------------------------------------------
HUD: Dict[str, Pair] = {
    f"{NS}.hud.form": ("形態", "Form"),
    f"{NS}.hud.tech": ("技", "Tech"),
    f"{NS}.hud.energy": ("気力", "Energy"),
    f"{NS}.hud.cooldown": ("再使用", "Cooldown"),
}

# ---------------------------------------------------------------------------
#  メッセージ (企画書 §12)
#
#  チャット欄は1行で読み切れる長さに収める。%s の数はスクリプトの呼び出しと
#  合っていなければならない（下の ARGS で検査する）。
# ---------------------------------------------------------------------------
MSG: Dict[str, Pair] = {
    # -- 参加時 ---------------------------------------------------------
    f"{NS}.msg.welcome": (
        f"{SHORT} ようこそ。まずは{FRUIT.ja}を食べるところから。",
        f"{SHORT} Welcome. Start by eating the {FRUIT.en}."),
    f"{NS}.msg.welcome_hint": (
        f"§7{HAT.ja}で変身、しゃがみ＋{HAT.ja}で形態を選ぶ。",
        f"§7{HAT.en} to transform; sneak + {HAT.en} to pick a form."),
    #  参加のたびに1行だけ出す非公式の注意（企画書 §18）
    f"{NS}.msg.welcome_unofficial": (f"§8{UNOFFICIAL_JA}", f"§8{UNOFFICIAL_EN}"),

    # -- 能力 -----------------------------------------------------------
    f"{NS}.msg.power_gained": (
        f"§c体がゴムになった！ {HAT.ja}で変身できる。",
        f"§cYour body turned to rubber! Transform with the {HAT.en}."),
    f"{NS}.msg.already_power": ("§7その力はもう身についている。",
                                "§7You already have that power."),
    f"{NS}.msg.no_power": (f"§7まだ能力がない。{FRUIT.ja}を食べよう。",
                           f"§7No power yet. Eat the {FRUIT.en}."),

    # -- 変身 -----------------------------------------------------------
    f"{NS}.msg.no_form": ("§7その形態は無い。", "§7No such form."),
    f"{NS}.msg.locked": ("§7その形態はまだ解放されていない。",
                         "§7That form is still locked."),
    f"{NS}.msg.already_form": ("§7すでにその形態だ。",
                               "§7You are already in that form."),
    f"{NS}.msg.too_tired": ("§7気力が足りない。少し休め。",
                            "§7Not enough energy. Rest a moment."),
    #  持ち物が満杯だと形態表示体を着せられない（企画書 §14 増殖防止の副作用）
    f"{NS}.msg.no_room": ("§7持ち物がいっぱいで変身できない。1枠空けてくれ。",
                          "§7No room to transform. Free one inventory slot."),
    f"{NS}.msg.exhausted": ("§c気力が尽きた。変身が解けた。",
                            "§cOut of energy. The form dropped."),
    f"{NS}.msg.recovered": ("§a通常状態へ戻した。", "§aRestored to normal."),

    # -- 技 -------------------------------------------------------------
    f"{NS}.msg.not_transformed": ("§7変身していないと使えない。",
                                  "§7You need to be transformed first."),
    #  後ろに技名（gla.tech.*）を継ぐので、ここは見出しだけ
    f"{NS}.msg.tech_selected": ("§7技:", "§7Technique:"),
    f"{NS}.msg.cooldown": ("§7あと %s 秒。", "§7%s s to go."),
    f"{NS}.msg.no_energy": ("§7気力が足りない。", "§7Not enough energy."),
    f"{NS}.msg.low_energy": ("§e気力が残りわずか。切れると変身が解ける。",
                             "§eEnergy is low. The form drops when it runs out."),

    # -- 解放 -----------------------------------------------------------
    #  スクリプトは空文字を1つ渡すが、%s は置かない（%s が余ると生で出る）
    f"{NS}.msg.unlocked": ("§a§l新しい形態を解放した！", "§a§lA new form is unlocked!"),
    #  後ろに形態名（gla.form.*）を継ぐ
    f"{NS}.msg.unlocked_form": ("§7解放:", "§7Unlocked:"),

    # -- 設定 -----------------------------------------------------------
    f"{NS}.msg.saved": ("§a設定を保存した。", "§aSettings saved."),
    f"{NS}.msg.infinite_on": ("§b気力無限: ON（消費だけ無効）",
                              "§bInfinite energy: ON (cost only)"),
    f"{NS}.msg.infinite_off": ("§7気力無限: OFF", "§7Infinite energy: OFF"),

    # -- 訓練場 ---------------------------------------------------------
    f"{NS}.msg.training_start": ("§7訓練場を建設中… %s ブロック",
                                 "§7Building the training ground: %s blocks"),
    #  建設中は常時表示を占有するので、割合だけの最短表記にする
    f"{NS}.msg.training_progress": ("§7訓練場 %s%%", "§7Training ground %s%%"),
    f"{NS}.msg.training_done": ("§a訓練場ができた。", "§aTraining ground is ready."),
    f"{NS}.msg.training_busy": ("§7まだ建設中だ。", "§7Still building."),
    f"{NS}.msg.training_cleared": ("§7標的を %s 体片付けた。",
                                   "§7Cleared %s targets."),

    # -- 開発用 (企画書 §12 製品の進行とは分ける) -------------------------
    f"{NS}.msg.dev_unlocked": ("§d[開発] 全形態を解放した。",
                               "§d[Dev] All forms unlocked."),
    f"{NS}.msg.dev_reset": ("§d[開発] 進行を初期化した。",
                            "§d[Dev] Progress reset."),
}

# ---------------------------------------------------------------------------
#  タイトル表示
#
#  画面中央を占有するので、能力を得た一度きりに絞ってある。変身のたびに
#  出すと常時表示（形態名・技・気力・再使用待ち）が隠れる（企画書 §12）。
# ---------------------------------------------------------------------------
TITLE: Dict[str, Pair] = {
    f"{NS}.title.awaken": ("§6覚醒", "§6AWAKENING"),
    f"{NS}.title.awaken_sub": ("§f全身がゴムになった", "§fYour whole body is rubber"),
}

# ---------------------------------------------------------------------------
#  メニュー (企画書 §09 操作 / §12 UIの方向性)
#
#  ボタン文言は指で押す前提で短く、迷う語を残さない。説明は本文側へ置く。
# ---------------------------------------------------------------------------
UI: Dict[str, Pair] = {
    # -- 形態選択（しゃがみ＋麦わら帽子）----------------------------------
    f"{NS}.ui.forms": ("形態を選ぶ", "Choose a form"),
    f"{NS}.ui.forms_body": ("§7命中 §e%s§r 回　気力 §b%s§r",
                            "§7Hits §e%s§r   Energy §b%s§r"),
    #  形態名の直後に続けるので、行を増やさず括弧で添える
    #  行頭の半角空白は読み込み側で落ちうるので、色コードを先に置いて空ける
    f"{NS}.ui.locked_at": ("　§8(命中 %s 回で解放)", "§8 (unlocks at %s hits)"),
    f"{NS}.ui.revert": ("変身を解除", "Revert"),
    f"{NS}.ui.techlist": ("技の一覧", "Techniques"),

    # -- ログポース -------------------------------------------------------
    f"{NS}.ui.settings": ("ログポース", "Log Pose"),
    f"{NS}.ui.settings_body": ("§7画面と遊び方の設定。ホスト設定はワールド全体に効く。",
                               "§7Display and play settings. Host settings apply "
                               "to the whole world."),
    f"{NS}.ui.display": ("画面・演出", "Display"),
    f"{NS}.ui.play": ("遊び方", "Gameplay"),
    f"{NS}.ui.training": ("訓練場", "Training ground"),
    f"{NS}.ui.host": ("ホスト設定", "Host settings"),
    f"{NS}.ui.recover": ("通常状態へ復旧", "Restore to normal"),
    f"{NS}.ui.help": ("操作の説明", "How to play"),
    f"{NS}.ui.close": ("閉じる", "Close"),

    # -- 画面・演出 -------------------------------------------------------
    f"{NS}.ui.quality": ("演出の品質", "Effect quality"),
    f"{NS}.ui.shortfx": ("変身演出を短縮する", "Shorten the transformation"),
    f"{NS}.ui.camerafx": ("カメラを揺らす", "Camera shake"),

    # -- 遊び方 -----------------------------------------------------------
    #  「消費だけ無効」は誤解されやすいので、項目名の側に書いておく（QA-09）
    f"{NS}.ui.infinite": ("気力無限（消費だけ無効）",
                          "Infinite energy (cost only)"),

    # -- 訓練場 -----------------------------------------------------------
    f"{NS}.ui.training_body": (
        f"§7その場に {GROUND} 四方の港島を建てる。地形は消さない。",
        f"§7Builds a {GROUND}x{GROUND} harbour island where you stand. "
        f"Terrain is never removed."),
    f"{NS}.ui.training_build": ("訓練場を建てる", "Build the training ground"),
    f"{NS}.ui.training_clear": ("標的を片付ける", "Clear the targets"),

    # -- ホスト設定 (企画書 §09 初期値は両方 OFF) --------------------------
    f"{NS}.ui.terrain": ("地形破壊を許可", "Allow terrain damage"),
    f"{NS}.ui.pvp": ("PvP を許可", "Allow PvP"),
}

# ---------------------------------------------------------------------------
#  操作の説明 (企画書 §09 — 覚えることは4つ)
#
#  道具の名前と役割は spec.Item が持っているので、ここでは並べ方だけ決める。
#  spec 側の説明文を直せばこの画面も追従する。
# ---------------------------------------------------------------------------


def _op(item: spec.Item) -> Pair:
    return (f"§e{item.ja}§r {item.ja_desc}", f"§e{item.en}§r {item.en_desc}")


HELP: Dict[str, Pair] = {
    f"{NS}.help.hat": _op(HAT),
    f"{NS}.help.wrap": _op(WRAP),
    f"{NS}.help.pose": _op(POSE),
    f"{NS}.help.unlock": (
        f"§7技を当てた回数で形態が解放される（最後は {LAST_UNLOCK} 回）。",
        f"§7Forms unlock from landed hits ({LAST_UNLOCK} for the last one)."),
    f"{NS}.help.energy": (
        f"§7気力は最大 {ENERGY_MAX}。技と維持で減り、休むと戻る。",
        f"§7Energy caps at {ENERGY_MAX}. Techniques and upkeep drain it; "
        f"resting refills it."),
}

# ---------------------------------------------------------------------------
#  引数の数 — スクリプトの呼び出しと %s を突き合わせる
#
#  validate.py は %s の数を見ない。数が合わないと実機で引数が消えるか生の %s
#  が出るだけで、静かに壊れる（QA-15 文字が切れない）。ここに書いた以外の
#  キーは %s を持たないこと、も併せて検査する。
# ---------------------------------------------------------------------------
ARGS: Dict[str, int] = {
    f"{NS}.msg.cooldown": 1,            # skills.js  残り秒
    f"{NS}.msg.training_start": 1,      # training.js 総ブロック数
    f"{NS}.msg.training_progress": 1,   # training.js 進捗 %
    f"{NS}.msg.training_cleared": 1,    # training.js 片付けた標的数
    f"{NS}.ui.forms_body": 2,           # ui.js       命中数・気力
    f"{NS}.ui.locked_at": 1,            # ui.js       解放に要る命中数
}


# ---------------------------------------------------------------------------
#  spec から引く節
# ---------------------------------------------------------------------------
def _items() -> List[Row]:
    """アイテム名と一行説明。

    表示名は `item.gla:<slug>`（BP の minecraft:display_name がこの形で
    参照している）。`.name` はスポーンエッグ等が使うバニラ側の綴りで、
    怪獣8号パックと同じく両方出しておく。`.desc` は spec.Item の説明文。
    """
    rows: List[Row] = []
    for it in spec.ITEMS:
        rows.append((f"item.{NS}:{it.slug}", (it.ja, it.en)))
        rows.append((f"item.{NS}:{it.slug}.name", (it.ja, it.en)))
        rows.append((f"item.{NS}:{it.slug}.desc", (it.ja_desc, it.en_desc)))
    return rows


def _mobs() -> List[Row]:
    return [(f"entity.{NS}:{m.slug}.name", (m.ja, m.en)) for m in spec.MOBS]


def _eggs() -> List[Row]:
    """スポーンエッグ。spec.Mob.summonable が False の内部表示体には出ない。"""
    return [(f"item.spawn_egg.entity.{NS}:{m.slug}.name",
             (f"{m.ja}のスポーンエッグ", f"Spawn {m.en}"))
            for m in spec.MOBS if m.summonable]


def _forms() -> List[Row]:
    return [(f.name_key, (f.ja, f.en)) for f in spec.FORMS]


def _techs() -> List[Row]:
    return [(t.name_key, (t.ja, t.en)) for t in spec.TECHS]


def _quality() -> List[Row]:
    return [(f"{NS}.quality.{k}", (spec.QUALITY[k]["ja"], spec.QUALITY[k]["en"]))
            for k in spec.QUALITY_ORDER]


def _zones() -> List[Row]:
    return [(f"{NS}.zone.{z['key']}", (z["ja"], z["en"]))
            for z in spec.TRAINING["zones"]]


def _table(table: Dict[str, Pair]) -> List[Row]:
    return [(key, pair) for key, pair in table.items()]


def rows_for(pack_key: str, include_content: bool) -> List[Row]:
    """1つのパックに出す行。None は節の区切り（空行）。

    BP には pack.* しか置かない。翻訳を実際に引くのは RP 側だけで、BP の
    texts はパック一覧に出す名前と説明にしか使われないため。
    """
    rows: List[Row] = _table(PACK[pack_key])
    if not include_content:
        return rows
    for section in (_table(NAME), _items(), _mobs(), _eggs(), _forms(),
                    _techs(), _table(HUD), _table(MSG), _table(TITLE),
                    _table(UI), _table(HELP), _quality(), _zones()):
        rows.append(None)
        rows += section
    return rows


# ---------------------------------------------------------------------------
#  書き出し
# ---------------------------------------------------------------------------
def write_lang(folder: str, pack_key: str, include_content: bool) -> int:
    """ja_JP.lang / en_US.lang / languages.json をこの順で書く。

    保存側はフォルダを掘らないので、ここで作る。
    """
    os.makedirs(folder, exist_ok=True)
    rows = rows_for(pack_key, include_content)
    for idx, code in ((0, "ja_JP"), (1, "en_US")):
        out: List[str] = []
        for row in rows:
            if row is None:
                out.append("")
                continue
            key, pair = row
            out.append(f"{key}={pair[idx]}")
        with open(os.path.join(folder, code + ".lang"), "w",
                  encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        print(f"  {os.path.relpath(folder, ROOT)}/{code}.lang")
    with open(os.path.join(folder, "languages.json"), "w",
              encoding="utf-8") as fh:
        json.dump(["en_US", "ja_JP"], fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return sum(1 for r in rows if r)


def read_keys(path: str) -> List[str]:
    """書いた .lang を読み直してキーだけ取り出す（重複もそのまま拾う）。"""
    keys: List[str] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line or "=" not in line:
                continue
            keys.append(line.split("=", 1)[0])
    return keys


def check_placeholders() -> None:
    """%s の数を ARGS と突き合わせる。%% 以外の裸の % も許さない。"""
    for table in (NAME, HUD, MSG, TITLE, UI, HELP):
        for key, pair in table.items():
            want = ARGS.get(key, 0)
            for lang, value in zip(("ja_JP", "en_US"), pair):
                got = value.count("%s")
                if got != want:
                    raise SystemExit(
                        f"{key} ({lang}): %s が {got} 個。呼び出しは {want} 個")
                rest = value.replace("%s", "").replace("%%", "")
                if "%" in rest:
                    raise SystemExit(
                        f"{key} ({lang}): 単独の % は %% と書く")


def main() -> None:
    print("language files:")
    write_lang(RP, "RP", True)
    write_lang(BP, "BP", False)
    check_placeholders()

    #  同じキーが両言語に揃っているかは、書いた物を読み直して確かめる。
    #  片方に無いキーはその言語で生の id が画面に出る（QA-15）。
    total = 0
    for folder in (RP, BP):
        ja = read_keys(os.path.join(folder, "ja_JP.lang"))
        en = read_keys(os.path.join(folder, "en_US.lang"))
        name = os.path.relpath(folder, ROOT)
        assert len(ja) == len(set(ja)), f"{name}: キーが重複している"
        assert set(ja) == set(en), (
            f"{name}: 言語でキーが違う "
            f"ja のみ={sorted(set(ja) - set(en))} en のみ={sorted(set(en) - set(ja))}")
        print(f"  {name}: {len(ja)} keys")
        total += len(ja)
    print(f"lang ok: {total} keys x2 languages "
          f"({len(spec.FORMS)} forms / {len(spec.TECHS)} techniques / "
          f"{len(spec.ITEMS)} items / {len(spec.MOBS)} entities)")


if __name__ == "__main__":
    main()
