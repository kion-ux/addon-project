# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 説明書を spec.py から起こす。

技や形態の表を手で書くと、必ず実装とずれる。企画書 §18「配布内容と実装済み
一覧が一致すること」を満たすため、数字が出る表はすべて生成する。
散文の部分だけがこのファイルに直書きされている。
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import spec                                             # noqa: E402

OUT = os.path.join(ROOT, "docs", "GRAND_LINE_AWAKENING.md")


def forms_table() -> str:
    rows = ["| 形態 | 解放条件 | 維持コスト | 技数 | 作り分け |",
            "|---|---|---|---|---|"]
    for f in spec.FORMS:
        unlock = "最初から" if f.unlock_hits == 0 else f"命中 {f.unlock_hits} 回"
        upkeep = "なし" if f.upkeep == 0 else f"{f.upkeep}/秒"
        rows.append(f"| **{f.ja}** | {unlock} | {upkeep} | "
                    f"{len(spec.techs_of(f.key))} | {f.note} |")
    return "\n".join(rows)


def tech_table() -> str:
    rows = ["| # | 形態 | 技 | 判定 | 溜め / 有効 / 後隙 | 威力 | 気力 | 再使用 |",
            "|---|---|---|---|---|---|---|---|"]
    shape_ja = {
        "line": "直線（通過した軌道）", "cone": "前方の円錐", "arc": "曲がる軌道",
        "slam": "叩きつけ（着弾地点の周囲）",
        "sphere": "全方位", "zone": "足元の区域", "self": "自己強化",
        "dash": "自分が飛ぶ", "projectile": "飛翔体", "delayed": "遅延して打ち上げ",
    }
    for i, t in enumerate(spec.TECHS, 1):
        form = spec.FORM_BY_KEY[t.form]
        power = "—" if t.damage == 0 else (
            f"{t.damage:g}" if t.hits == 1 else f"{t.damage:g} x{t.hits}")
        rows.append(
            f"| {i} | {form.ja} | **{t.ja}** | {shape_ja[t.shape]} | "
            f"{t.windup}/{t.active}/{t.recover}t | {power} | {t.cost:g} | "
            f"{t.cooldown/20:.1f}秒 |")
    return "\n".join(rows)


def showpiece_table() -> str:
    rows = ["| 時間 | 身体・表情 | VFX・音 |", "|---|---|---|"]
    for step in spec.SHOWPIECE:
        a = step["t"] / 20.0
        b = step["until"] / 20.0
        fx = "、".join(sorted({s["fx"].split(":")[1] for s in step["stages"]}))
        note = "（声は入れない）" if step.get("no_voice") else ""
        rows.append(f"| {a:.2f}〜{b:.2f}秒 | {step['ja']} | {fx}{note} |")
    return "\n".join(rows)


def quality_table() -> str:
    rows = ["| 項目 | 軽量 | 標準 | 高品質 |", "|---|---|---|---|"]
    q = spec.QUALITY
    order = spec.QUALITY_ORDER
    rows.append("| 描く層 | " + " | ".join(
        "・".join(spec.LAYER_JA[n] for n in q[k]["layers"]) for k in order) + " |")
    rows.append("| 粒子の密度 | " + " | ".join(
        f"{int(q[k]['density'] * 100)}%" for k in order) + " |")
    rows.append("| 演出補助エンティティ | " + " | ".join(
        str(q[k]["helpers"]) for k in order) + " |")
    rows.append("| 大技のフル演出・同時数 | " + " | ".join(
        str(q[k]["showpiece"]) for k in order) + " |")
    rows.append("| 本体キューブの設計予算 | " + " | ".join(
        f"{q[k]['cubes'][0]}〜{q[k]['cubes'][1]}" for k in order) + " |")
    return "\n".join(rows)


def qa_table() -> str:
    #  自動検査で潰せるもの / 実機でしか見られないもの を正直に分ける
    automated = {
        "QA-01": "tools/validate.py（参照欠落・UUID・依存・アイコン）",
        "QA-03": "tools/gla/test_logic.py（100回操作で個数不変）",
        "QA-04": "tools/gla/test_logic.py（20往復で残留なし）",
        "QA-07": "tools/gla/test_logic.py（単発1回／連打は定義回数／壁越し・自分に当たらない）",
        "QA-09": "tools/gla/test_logic.py（消費だけ無効・クールダウンは有効）",
        "QA-10": "tools/gla/test_logic.py（全24技でブロック書き換え0）",
    }
    rows = ["| ID | 試験 | 合格条件 | 現状 |", "|---|---|---|---|"]
    for code, name, cond in spec.QA_CHECKS:
        state = automated.get(code)
        mark = f"自動: {state}" if state else "**実機未検証**"
        rows.append(f"| {code} | {name} | {cond} | {mark} |")
    return "\n".join(rows)


BODY = """# GRAND LINE AWAKENING — ワンピース統合版アドオン

Minecraft **統合版 (Bedrock Edition)** 用の**非公式ファン制作**アドオンです。
Minecraft・ONE PIECE の公式商品ではなく、権利者とは関係ありません。
公式ロゴ、作品映像、抽出した音声・画像は一切同梱していません。

ルフィの通常形態からギア5（ニカ）までの**変身**と、形態ごとに作り分けた
**24枠の技**、そして変身直後の**浮遊しながらの大爆笑**を中心に作られています。

- 対応バージョン: **Minecraft Bedrock {mev} 以降**
- 使用API: `@minecraft/server {srv}` / `@minecraft/server-ui {ui}`
- 言語: 日本語 / English（ゲームの言語設定に追従）
- namespace: `{ns}`（他パックと衝突しないよう専用のものを使用）

> **この版で確認できていないこと（重要）**
> 実機での描画・音・タッチ操作・負荷は**まだ検証していません**。
> 下の QA 表で「実機未検証」と書いた項目は、そのとおり未検証です。
> 企画書の方針どおり、確認していないものを「動作確認済み」とは書きません。

---

## 導入方法

1. `dist/GrandLineAwakening_v{ver}.mcaddon` をインポートする
2. ワールド設定で **ビヘイビアーパック** と **リソースパック** の両方を有効化する
3. ワールド設定の **「ベータAPI」を ON** にする（スクリプト機能に必要）

---

## 操作

タッチ操作を優先し、覚えることを4つに絞っています（企画書 §09）。

| 操作 | 効果 |
|---|---|
| **悪魔の実（ゴム）** を食べる | 能力を得る（最初の一度だけ） |
| **麦わら帽子** を使う | 変身 / 変身中は解除 |
| **しゃがみ＋麦わら帽子** | 形態を選ぶ |
| **拳の包帯** を使う | 選択中の技を1回発動 |
| **しゃがみ＋拳の包帯** | 次の技へ切替（発動とは排他。切替で技は出ません） |
| **ログポース** を使う | 設定・訓練場・通常状態へ復旧 |
| **しゃがみ＋ログポース** | 技の一覧から直接選ぶ |

画面に出しっぱなしにするのは **形態名・選択中の技・気力・再使用待ち** の4つだけ。
詳しい説明はメニュー側にあります（企画書 §12）。

---

## 形態

同じモデルの色替えでは済ませず、輪郭・立ち方・動き・攻撃の性格を形態ごとに
変えています。ギア3だけは常時形態ではなく、**技中だけ前腕と脛が膨張**します。

{forms}

解放は「技を当てた回数」で進みます。ログポースの設定からは解放できません
（気力無限を入れても解放条件は勝手に緩みません）。

---

## 技 — 24枠

技名と色を隠して録画を見ても「伸ばす技」「連打」「重い一撃」が区別できること、
を設計の検収条件にしています（企画書 §10）。そのため判定の形・溜めの長さ・
命中回数・ノックバックを意図的にばらしてあります。

{techs}

技名は企画書の候補名です。「原作全技収録」ではありません。

---

## 看板演出 — ニカ変身後の浮遊・大笑い

変身の達成感を最も強く見せる場面として、専用に {sp:.1f} 秒を設計しています
（企画書 §08）。

{showpiece}

- 浮遊は**見た目だけ**です。プレイヤーの実座標は動かさないので、落下や壁抜けは
  増えません（見た目の root を約 {lift} ブロック上げています）。
- **声は入れません。** 許諾の確認できない音声を同梱しないという方針のため、
  打音と身体の動きだけで成立させています（企画書 §11）。
- 強い点滅は使いません。
- 設定の「演出短縮」で {short:.1f} 秒の短縮版に切り替えられます。
- 被弾・死亡・再接続・ディメンション移動では演出を打ち切り、通常状態へ戻します。

---

## システム

### 気力

最大 {emax:g}。技のコスト、形態の維持コスト、回復待ちを別々の項目にしています。

- 通常時の回復 {regen:g}/秒、戦闘していない時間が続くと {idle:g}/秒
- **気力無限**（設定）は**消費だけ**を無効にします。クールダウン、被ダメージ、
  解放条件は無効になりません（企画書 §09 / QA-09）

### 品質設定

重いときに見栄えを丸ごと失うのではなく、重要な輪郭と命中表現から残します。
VFX は5層（{layers}）に分けてあり、削るのは外側からです。

{quality}

**接触（3層）はどの設定でも必ず描きます** — 命中が読めなくなるのが一番困るからです。

### ホスト設定

- **地形破壊**: 初期値 OFF
- **PvP**: 初期値 OFF（OFF の間、技は他プレイヤーを対象にしません）

### 全方位で判定する技

企画書 §09 の「単に自分の周囲を毎回全方向攻撃しない」を守るため、自分を中心に
全方位で判定してよい技は `tools/gla/spec.py` の `ALL_AROUND` に列挙した
**白い星銃**（宣言どおりの全方位）と**地面のゴム化**（足元の区域）だけです。
それ以外は前方・軌道・着弾地点のいずれかで判定します。この2つ以外に
`sphere` / `zone` を足すと、spec の自己検査が落ちます。

どちらもログポースの「ホスト設定」から変更します。

---

## 訓練場

ログポースの「訓練場」から、その場に港島を建てます。区画は企画書 §12 のとおり。

| 区画 | 目的 | 置いてあるもの |
|---|---|---|
{zones}

「標的を片付ける」は**標的だけ**を消します。一度置いた地形は消しません。

---

## 開発者向け

### ビルド

```bash
./build.sh          # 2つのアドオンを両方ビルドして dist/ へ
```

必要なもの: Python 3.11+、`Pillow`、Node.js（スクリプトの読み込み確認と挙動テスト用）。

### 単一の定義元

**技・形態・アイテム・エンティティ・演出・QA表は、すべて
`tools/gla/spec.py` の1枚から生成されます**（企画書 §09）。
技を1つ増やすときに触るのはこのファイルだけです。そこから

| 生成物 | 生成元 |
|---|---|
| `packs/gla_RP/models/` `textures/entity/` | `tools/gla/gen_models.py` |
| `packs/gla_RP/animations/` `animation_controllers/` | `tools/gla/gen_anim.py` |
| `packs/gla_RP/particles/` `textures/particle/` | `tools/gla/gen_particles.py` |
| `packs/gla_RP/entity/` `attachables/` `render_controllers/` `textures/items/` | `tools/gla/gen_client.py` |
| `packs/gla_BP/items/` `entities/` `recipes/` `loot_tables/` `manifest.json` | `tools/gla/gen_bp.py` |
| `packs/gla_BP/scripts/data.js` | `tools/gla/gen_data.py` |
| `packs/gla_*/texts/` | `tools/gla/gen_lang.py` |
| この説明書 | `tools/gla/gen_docs.py` |

`packs/` 以下の生成物と `scripts/data.js` は**手で編集しないでください**。

### 手で書いてあるもの

`packs/gla_BP/scripts/` の `main.js` `state.js` `skills.js` `combat.js`
`fx.js` `ui.js` `training.js` `util.js` は手書きです（`data.js` だけが生成物）。

### 層の分け方（企画書 §13）

```
入力        main.js       アイテム使用・技切替・形態選択を1つに正規化
ゲーム状態  state.js      form / phase / 気力 / 解放状態 / 復旧
戦闘処理    combat.js     判定の形・命中履歴(action_id)・ノックバック
技          skills.js     溜め→有効→後隙 の進行と演出の予約
表示        fx.js         5層の並べ方と品質による間引き
UI          ui.js         形態選択・設定・技一覧
訓練場      training.js   港島の建築
```

状態遷移は `normal → transforming → active → attacking → recovering → active`、
解除は `reverting → normal`、異常時は `safe_reset → normal`。

### 基準版の記録

`./build.sh` は `dist/RELEASE_RECORD.md` も書き出します（企画書 §18 基準版の記録）。
配布ファイル名、パックの中身のハッシュ、BP/RP の UUID と版、本体版と
モジュール版が入っています。ハッシュは zip の時刻ではなく**中身**から取るので、
同じ内容なら何度ビルドしても同じ値になります。

実機名・設定・確認日・確認者・合格した QA 項目の欄は**空のまま**です。
実機で確認した人がそこへ記入するまで、確認は行われていないことを意味します。

### 検証コマンド

```bash
python3 tools/validate.py         # 参照欠落・UUID・依存・言語キー（両アドオン）
python3 tools/check_scripts.py    # スクリプトが実際に読み込めるか（両アドオン）
python3 tools/gla/test_logic.py   # 下の QA 表の「自動」項目を実行
```

### 開発用コマンド

製品の進行（解放条件・レシピ）とは分けてあります（企画書 §12）。

| コマンド | 効果 |
|---|---|
| `/scriptevent gla:power` | 能力を得る |
| `/scriptevent gla:unlock` | 全形態を解放する |
| `/scriptevent gla:form gear5` | 指定の形態へ変身する |
| `/scriptevent gla:recover` | 通常状態へ復旧する |
| `/scriptevent gla:reset` | 進行をすべて初期化する |

---

## QA・検収チェックリスト（企画書 §17）

「入る」「見える」「動く」「戻れる」を分けて確認します。
**自動検査で潰せるのは JSON・参照・数値・命中ロジックまでで、
見た目・音・タッチ操作・負荷は実機でしか検収できません。**

{qa}

---

## 企画書との対応

### この版に入っているもの

- 形態専用の立ち姿・移動、表情差分、変身・解除、攻撃ごとの当たり判定
- 技選択 UI、軽量化設定、訓練場、再接続時の復旧
- 配布用 BP/RP と、その検証手順（上の検証コマンド）

### 意図的に入れていないもの

| 項目 | 理由 |
|---|---|
| カメラの寄り・切替演出 | Camera API の対応版を実機で確認するまで入れない（企画書 §11 / §14）。カメラの揺れのみ、設定で OFF にできる形で実装 |
| 地形を実際に壊す処理 | ホストの検証済みルールが決まるまで、許可されても実行しない（QA-10 を壊さないため） |
| 一人称の専用腕 | 三人称の完成後、別検収で追加する工程（企画書 §14） |
| 全キャラクター | 第1弾はルフィのみ。品質基準の完成後に追加（企画書 §03） |
| 自作の効果音 | 許諾の確認できる音だけを同梱する方針のため、現状はバニラの音のみ |
| 左右移動クリップの自動再生 | クリップは生成・宣言済みだが、アタッチャブルが読める組み込みクエリでは「横に動いている」を出し分けられないため、自動では鳴らしていない |

### 技ごとの専用アニメーションについて

24技それぞれの専用クリップは生成してあり、スクリプトから
`player.playAnimation()` で再生を試みます。**この経路が対象版で動くかは
未検証**です。動かなかった場合でもアタッチャブル側の移動・待機・振りと、
層に分けた VFX で技は成立するよう作ってあります。

---

## ライセンスと権利について

- 本アドオンは**非公式のファン制作**です。ONE PIECE および Minecraft の
  権利者とは関係がありません。
- モデル・テクスチャ・パーティクル・アニメーションは**すべてこのリポジトリの
  スクリプトが生成した自作物**です。原作映像からの抽出物は含みません。
- 効果音はバニラ Minecraft の音のみを参照しています。音声ファイルは同梱していません。
- 公開・再配布の際は、非公式である旨の表示を外さないでください。
  Minecraft 側の利用ガイドラインと、ONE PIECE 側の権利・素材利用条件は
  別々に確認が必要です。非営利・自作であることだけを理由に、
  公開許諾済みとは扱えません（企画書 §18）。
"""


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    zones = "\n".join(
        f"| **{z['ja']}** | {z['purpose']} | {z['props']} |"
        for z in spec.TRAINING["zones"])
    text = BODY.format(
        mev=".".join(str(v) for v in spec.MIN_ENGINE),
        srv=spec.SERVER_MODULE, ui=spec.SERVER_UI_MODULE, ns=spec.NS,
        ver=".".join(str(v) for v in spec.VERSION),
        forms=forms_table(), techs=tech_table(), showpiece=showpiece_table(),
        sp=spec.SHOWPIECE_TICKS / 20.0, short=spec.SHOWPIECE_SHORT_TICKS / 20.0,
        lift=spec.SHOWPIECE_LIFT, emax=spec.ENERGY_MAX,
        regen=spec.ENERGY_REGEN, idle=spec.ENERGY_REGEN_IDLE,
        layers="・".join(spec.LAYER_JA[n] for n in (1, 2, 3, 4, 5)),
        quality=quality_table(), zones=zones, qa=qa_table(),
    )
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"docs: {os.path.relpath(OUT, ROOT)} "
          f"({len(text.splitlines())} lines, {len(spec.TECHS)} techniques)")


if __name__ == "__main__":
    main()
