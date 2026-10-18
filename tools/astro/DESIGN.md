# アストロ・ナノギア（ASTRO NANOGEAR）設計書

Minecraft 統合版用の宇宙テーマ変身アドオン。惑星ごとの「星核（変身の核）」に宿るメカ・ナノマシンが
全身装甲と専用ナノウェポンを組み上げ、惑星の力と技術を融合した技で戦う。

この文書は全ての生成スクリプト・スクリプト・作業者（人とエージェント）の **契約** です。
名前（ID・ボーン名・アニメ名・パーティクル ID・効果音 ID・グリフ番号・関数名）はここに書いたものだけを使い、
増やすときはここに追記してから使ってください。ゲームの数値は `astro_data.py` が唯一の出所です。

品質の基準は「MOD 級」: 3D モデルは部位ごとに作り込み（1 スーツ 250〜600 キューブ目安）、テクスチャは
パネルライン・面取り・発光ライン・デカールまで描き、全ての技に専用の演出・音・全身モーションを付ける。
**実機で確認できないので、ソフトレンダラのプレビュー・機械的な検査・Node のスタブ実行で確かめる**（後述）。

---

## 0. 作業の約束

* 既存の `packs/kaiju8_*`・`packs/hyperdim_*`・`tools/*.py`・`tools/hyperdim/*` は **変更しない**（import して使うのは可）。
* 新規ファイルは `tools/astro/`・`packs/astro_BP/`・`packs/astro_RP/`・`docs/astro/`・`build_astro.sh`・`README_ASTRO.md` のみ。
* 生成物（packs/astro_*）は生成スクリプトから作る。手で JSON を書かない（スクリプトの .js は手書き）。
* **git commit / push はしない**（まとめ役が行う）。
* 一時ファイル・プレビューは `ASTRO_SCRATCH`（既定 `build_preview/astro/`、.gitignore 済み）へ。
* 対象: Minecraft Bedrock **1.21.30 以降**、`@minecraft/server` **1.13.0**、`@minecraft/server-ui` **1.2.0**（既存 2 アドオンと同じ。ベータ API 不要）。
  これより新しい API は `typeof x === "function"` 等で有無を確かめてから使い、無ければ劣化動作にする。
* Python は 3 + Pillow + numpy のみ。音は ffmpeg（libvorbis）。JS のテストは Node 22。
* 命名空間 `astro`。翻訳キー・コメント・README は日本語（英語の lang も用意）。

---

## 1. ファイル構成と担当

```
tools/astro/
  DESIGN.md              この文書
  astro_data.py          ゲームデータの単一ソース（惑星・技・数値・レシピ・敵）
  astro_common.py        パス・NS・write_json・ジオメトリ補助（hd_common の box/cbox/beam/polyline 等を再輸出）
  astro_paint.py         メカ用テクスチャペインタ（hd_paint.HDPainter を継承し素材を追加）
  astro_suit.py          スーツの骨格（プレイヤーのボーン名・ピボット）・部位ボーン・被覆検査
  astro_hold.py          ナノウェポン／コアの持ち方（hd_space / hd_holds の規則で一人称・三人称を逆算）
  astro_weapon.py        ウェポン・コアのモデル補助とアタッチャブル／アニメの書き出し
  astro_scene.py         スーツを着て武器を持ったプレイヤーを描くレンダラ（hd_scene の規則）
  astro_animlib.py       全身モーションの記法（キーポーズ → playanimation 用 JSON）と共通モーション
  planets/<key>/         惑星ごとのパッケージ（9 個。各惑星の担当者だけが編集）
      __init__.py        空でよい
      suit.py            build_suit(m) / SUIT_STYLES / SUIT_ANIMS（スーツのモデル・塗り・部位アニメ）
      weapon.py          build_weapon(m, root) / build_core(m, root) / WEAPON_STYLES / CORE_STYLES / WEAPON_ANIMS
      body.py            BODY_ANIMS（その惑星の技・コンボの全身モーション）
  planets/_template/     惑星パッケージの雛形と説明（README）
  gen_astro_suits.py     スーツのジオメトリ・テクスチャ・アタッチャブル（on/off）・スーツのアニメ（引数で惑星を絞れる）
  gen_astro_weapons.py   ウェポン・コアのジオメトリ・テクスチャ・アタッチャブル・アニメ・アイコン（引数で絞れる）
  gen_astro_anim.py      プレイヤーの全身モーション（共通＋惑星の body.py）と scripts/anim_meta.js
  gen_astro_particles.py パーティクルのアトラスと定義（PARTICLES.md に一覧と変数）
  gen_astro_sounds.py    効果音の合成と sound_definitions.json
  gen_astro_ui.py        HUD グリフ（font/glyph_*.png）・フォーム用アイコン・惑星紋章・パックアイコン・scripts/glyphs.js
  gen_astro_entities.py  敵・投射物・ホログラム標的・ダメージ表示（BP/RP の entity・モデル・テクスチャ・アニメ）
  gen_astro_packs.py     マニフェスト・アイテム・レシピ・言語・item_texture.json・scripts/data.js
  validate_astro.py      参照整合性（ID・テクスチャ・UV・Molang 括弧・言語キー）
  check_astro_suits.py   スーツの肌の被覆検査・部位ボーン命名・キューブ数・テクスチャ密度
  test_astro.py          スクリプトの挙動テスト（@minecraft/server のスタブで全技を実行）
  preview_astro.py       docs/astro/*.png（スーツの三面図・武器・アイコン・HUD・パーティクル）
  build_astro.py         全部回して検査し dist/ へ
packs/astro_BP/  scripts/*.js（手書き）+ 生成物
packs/astro_RP/  生成物（アニメは astro_suits / astro_weapons / astro_player の 3 ファイルに分ける）
build_astro.sh   README_ASTRO.md   docs/astro/
```

スクリプト（`packs/astro_BP/scripts/`）:

| ファイル | 内容 |
|---|---|
| `data.js` | **生成**（gen_astro_packs）。PLANETS / COMMON / TRANSFORM / MOVE_LABEL 等 |
| `glyphs.js` | **生成**（gen_astro_ui）。HUD グリフの文字 |
| `anim_meta.js` | **生成**（gen_astro_anim）。全身モーションの長さ |
| `main.js` | イベントとループの配線、`/scriptevent astro:*` |
| `util.js` | API の版差の吸収・ベクトル（hyperdim の util.js を土台に） |
| `state.js` | プレイヤーごとの状態（変身中の惑星・星力・超新星ゲージ・同調率・設定）と保存 |
| `fx.js` | パーティクル・音・画面揺れ・フラッシュ・カットイン・全身モーション |
| `combat.js` | 標的判定・範囲検索・ダメージ（ダメージバンク）・ダメージ表示・ゲージ加算 |
| `engine.js` | 技の選択と実行、再使用、ctx、共通の動き（突進・ホバー・急降下・ワープ・投射物・設置範囲） |
| `transform.js` | 変身／解除の演出と時間割、防具の退避、コア⇔ウェポン・スーツの差し替え、保険の掃除 |
| `mobility.js` | スラスター機動（二段ジャンプ・ホバー・ブーストダッシュ・回避・ジャスト回避・着地）、解除の長押し判定 |
| `combo.js` | 通常攻撃の三段コンボと三段目の追撃 |
| `passives.js` | 惑星ごとの常時効果（effects の掛け直しと special の処理の呼び出し） |
| `hud.js` | アクションバーの HUD（グリフ） |
| `ui.js` | 星核ターミナル（状態・惑星図鑑・設定・解除・操作説明） |
| `enemies.js` | 侵略者（ドローン・センチネル・ボス ネメシス）の攻撃パターン、ホログラム標的 |
| `planets/<key>.js` | 惑星ごとの技（9 ファイル） |

---

## 2. ゲームの仕様

### 2.1 入手と進行
1. 初回参加で **星核ターミナル** が配られる（右クリックで UI）。
2. 鉄・レッドストーン・アメジストで **ナノマシン・セル** → セル＋ガラス＋ダイヤで **コア・フレーム**。
3. フレーム＋セル＋惑星ごとの素材で **惑星コア**（8 種）。
4. 夜の地上に **ヴォイド・ドローン**・**ヴォイド・センチネル** が現れ、セルを落とす。
5. **ヴォイド・シグナル** を夜に使うとボス **虚星王 ネメシス** が降臨。倒すと **太陽の欠片** → **ソル・コア**（第 9 形態）。
6. 形態ごとに **同調率**（Lv1〜5）が上がり、与ダメージ・最大星力・再使用短縮が伸びる。

### 2.2 操作
| 入力 | 効果 |
|---|---|
| 惑星コアを持って右クリック | **変身**（約 3 秒の演出。星力 30 以上が必要。オーバーヒート中は不可） |
| 攻撃 | 三段コンボ（1.3 秒あくと 1 段目へ）。三段目は惑星ごとの追撃 |
| 右クリック | **惑星技** |
| ダッシュ中に右クリック | **機動技** |
| 空中で右クリック | **空中技** |
| スニーク＋右クリック | 超新星ゲージ 100%: **必殺技**（カットイン・時間停止）／未満: **ナノ・バリア**（0.7 秒ほぼ無敵、3 秒に 1 回） |
| 空中でジャンプ | スラスター **二段ジャンプ**（形態ごとに回数） |
| 空中でジャンプ長押し | **ホバー**（ゆっくり上昇／滞空。星力を消費） |
| 空中でスニーク | **ブースト・ダッシュ** |
| 地上でスニークを素早く 2 回 | **回避ステップ**（直後は無敵。そこで攻撃を受けると **ジャスト回避**） |
| スニークしたまま 2 秒静止 | **変身解除**（HUD に進み具合） |
| ダッシュ | 加速と足元の噴射 |

変身中は「ナノウェポン」（コアが変わったもの）を持っていなくても装甲と機動は有効。技はナノウェポンを持っている時だけ。

### 2.3 数値（astro_data.COMMON）
* **星力**: 変身中は毎秒 0.35 減る、技ごとに cost、ホバー毎秒 4。0 で強制解除＋オーバーヒート 20 秒（再変身不可・弱体化）。変身していない時は毎秒 3 戻る。敵を倒すと +5。
* **超新星ゲージ**: 通常攻撃 +3、技の命中 +2、被ダメージ ×0.8、ジャスト回避 +15。100 で必殺技。必殺技の最中は溜まらない。
* **同調率**: 形態ごと。命中 +2 XP、撃破 +12 XP。閾値 0/200/600/1400/3000。Lv ごとに与ダメージ +6%・最大星力 +10・再使用 -5%。
* **防御**: スーツ（頭スロット）の防御点 = PLANETS[key].defense。変身中は元の防具を外して保管する（2.4）。

### 2.4 変身の時間割（astro_data.TRANSFORM、tick）
```
 0  コアが手から浮かび、リングが展開（core_rise）。動けなくなる（freeze 64 tick, 無敵）
    演出カメラ ON（設定で切れる）: 正面斜め → 周回 → 顔のアップ → 戻す
 8  ナノマシンの奔流がコアから噴き出し、螺旋を描いて全身へ（swarm_start）
14  頭スロットにスーツを置く → 組み上がりアニメ開始（suit_equip、1.8 秒）
    ブーツ→脚→腰→胴→背→腕→肩→兜→バイザー の順に部位がポップして現れる（ASSEMBLE_ORDER）
    パーティクルは各部位の位置へ同じ時刻に流れ込む
40  手のコアがナノウェポンに変わる（weapon_form。ウェポン側も刃が伸びる形成アニメ）
46  バイザー点灯（visor_flash）
50  惑星の力が弾ける（planet_burst = planets/<key>.js の burst）。カットイン（紋章＋形態名）
60  カメラを戻す（camera_clear）。操作が戻る
```
タイトル: `CORE SYNC 0%→25→50→75→100%` を進捗グリフ付きで出し、最後に紋章＋形態名。

**防具の退避**: 変身時に頭・胴・脚・足の防具をインベントリへ移し（入らなければ変身を断る）、
種類 ID を動的プロパティに記録。解除時に同じ種類をインベントリから探して着せ直す（kaiju8 の方式）。

**差し替え**: スーツは頭スロットに `lockMode = slot`・`keepOnDeath = true` で置く。suit_equip で `astro:suit_<key>_on`
（組み上がり）を置き、`assemble_len` 秒後に `astro:suit_<key>`（装着中）へ差し替える。
ナノウェポン `astro:weapon_<key>` は手のコアと同じスロットに `lockMode = inventory`・`keepOnDeath = true` で置く。
解除時は逆に戻す。保険として 1 秒ごとに「変身していないのにスーツ／ウェポンを持っている」「別形態のウェポン」を
コアへ戻す掃除をし、地面に落ちたウェポン・スーツ（item エンティティ）も見つけ次第コアに直す。

**解除の演出**: 頭スロットを `astro:suit_<key>_off`（同じモデルで分解アニメ）に差し替え、0.9 秒後に外す。
ナノマシンがコアへ還るパーティクルと効果音。ウェポンはその場でコアに戻す。

**死亡**: 変身中に死んだら、リスポーン時に解除（スーツとウェポンを消してコアを戻し、防具を着せ直す）。
退出中の変身状態は再参加時に復元する（スーツが頭にあれば変身中とみなす）。

### 2.5 HUD（アクションバー、4 tick ごと）
```
[紋章] 形態名  Lv3  │ ⚡[星力バー 16 セル] 72  │ ✦[超新星バー 10 セル] 100%
[技アイコン] 1.2s  [技アイコン] ✔  [技アイコン] ✔  [必殺アイコン] READY
```
* 星力バーは惑星色、20% 未満で赤く点滅。超新星バーは満タンで金と白が流れる。
* 解除の長押し中・溜め中・バリア中・オーバーヒート中は 2 行目を状態表示に差し替える。
* グリフの番号と見た目は gen_astro_ui.py が決め、`glyphs.js` に `G.energy[key].full` のように書き出す（§4.8）。

### 2.6 星核ターミナル（server-ui）
* トップ: 状態（変身中の形態・星力・ゲージ・オーバーヒート）、ボタン: 惑星図鑑 / 変身解除（変身中のみ） /
  設定 / 操作説明 / 記録。
* 惑星図鑑: 9 形態のボタン（紋章アイコン `textures/ui/astro/emblem_<key>`）→ 形態ページ（解説・パッシブ・
  4 技の名前と説明と再使用・同調率 Lv と XP・所持していればコアの場所）。
* 設定（ModalForm）: 変身カメラ演出 ON/OFF、HUD 表示 ON/OFF、演出の量（多い/標準/少ない → パーティクル予算倍率）、
  ダメージ数字 ON/OFF。プレイヤーごとに動的プロパティへ保存。
* `UserBusy` は 1 秒おきに数回再試行（kaiju8 ui.js の show()）。

### 2.7 敵
| ID | 名前 | 仕様 |
|---|---|---|
| `astro:void_drone` | ヴォイド・ドローン | 浮遊。HP20。夜の地上にスポーン。距離を取って紫のレーザー（`astro:void_bolt` 投射物）。セル 1〜2 |
| `astro:void_sentinel` | ヴォイド・センチネル | 二足歩行の機兵。HP44。近接＋地面の衝撃波（スクリプト）。セル 2〜3 |
| `astro:nemesis` | 虚星王 ネメシス | ボス。HP480。ボスバー。浮遊する黒い星の機械。レーザー薙ぎ払い・ドローン召喚・隕石雨・ブラックホール吸引・突進。太陽の欠片 2・セル 8 |
| `astro:hologram_target` | ホログラム標的 | 倒れない練習台。直近 5 秒の合計と DPS を頭上に表示 |
| `astro:void_bolt` | （投射物） | ドローンのレーザー |
| `astro:dmg_text` | （表示） | ダメージの数字（nameTag） |

### 2.8 コマンド（チート ON）
```
/scriptevent astro:kit      全コアとターミナル・素材
/scriptevent astro:energy   星力満タン   /scriptevent astro:nova  超新星ゲージ満タン
/scriptevent astro:sync     今の形態の同調率を Lv5
/scriptevent astro:target   ホログラム標的   /scriptevent astro:boss  ネメシス
/scriptevent astro:revert   強制解除        /scriptevent astro:transform <key>  コア無しで変身（確認用）
```

---

## 3. 惑星（形態）

名前・配色・技名・数値・パッシブ・モチーフは `astro_data.PLANETS` を見ること。ここには造形と演出の方針だけを書く。

| 形態 | 造形の芯 | ナノウェポン（kind） | 変身の締め（burst） |
|---|---|---|---|
| 水星 クイックシルバー | 細身の銀の流線形。ヘルメスの翼の兜・翼のブーツ。左右で灼熱（橙）と極寒（シアン）の発光 | サーベル（saber）。液体金属の刃・鍔の冷却フィン | 液体金属の飛沫が全身を流れ落ちて固まり、残像が八方へ |
| 金星 モーニングスター | 金とクリーム。花弁のように重なる腰装甲・星の冠・肩の雲ポッド | 星頭の王笏（scepter）。八芒星の頭と回る雲の輪 | 黄色い雲が渦を巻いて晴れ、頭上に明星が灯る |
| 地球 ガイア | 青と白の騎士。緑の大陸線・白い雲のマント・月の子機 | 騎士剣（sword）。鍔に地球儀の核 | 海と森の色の輪が足元から広がり、オーロラの幕が立つ |
| 火星 アレス | 重装。真紅と錆色・鶏冠の兜・大肩当て・背を回る二つの衛星 | 杭打ち機付きの戦斧（axe） | 赤い砂嵐が吹き飛び、溶岩の割れ目が足元に走る |
| 木星 ゼウス | 巨体。クリームと褐色の縞・胸の大赤斑コア（回転）・肩のテスラコイル・王冠 | 雷霆鎚（hammer）。テスラコイルの鎚頭 | 落雷が三度、胸の嵐が渦巻く |
| 土星 クロノス | 淡金とアイボリー・腰を斜めに回る大環・胸の六角形・文字盤 | 環刃（ring）。歯の回る円環 | 大環が広がって地平線のように一閃、時計の陣 |
| 天王星 ウラノス | 淡い青緑の鋭い装甲・肩の氷晶・背で 98° 傾いて縦に回る環・ダイヤの鶏冠 | 弩（crossbow）。傾いた環の付いた弩 | 横倒しの環が回って氷晶が散り、地面が凍る |
| 海王星 トリトン | 紺碧と藍・白い波頭のヒレ・三叉の冠・水色の発光線 | 三叉槍（trident） | 渦潮が足元から巻き上がり、波頭が砕ける |
| 太陽 ソル | 白金と金・頭の後ろで回るコロナの光輪・紅炎のヒレ・胸の核融合炉 | 紅炎剣（greatsword。片手で持つ大剣） | 収縮した光が一気に膨らみ、コロナの輪が三重に広がる |

全形態に共通する意匠: 胸か腰の **星核**（その惑星の球体が光る）、関節の黒いインナー（六角メッシュ）、
細い発光ライン、パネルライン、警告ストライプや型番の小さなデカール、背中のスラスター（空中で炎が伸びる）。

---

## 4. 技術の契約

### 4.1 データ（astro_data.py → data.js）
`gen_astro_packs.py` が `scripts/data.js` を書き出す:
```js
export const NS = "astro";
export const COMMON = {...};          // astro_data.COMMON そのまま
export const TRANSFORM = {...};
export const MOVE_KINDS = ["skill","dash","air","ult"];
export const MOVE_LABEL = {skill:"惑星技", ...};
export const PLANETS = {
  mercury: { key, order, ja, en, form_ja, form_en, core_ja, suit_ja, tc,
             color:[r,g,b] /*glow 0..1*/, light, deep, plate, accent,
             weapon:{key, ja, en, kind}, damage, defense, mobility:{...}, passive:{effects, special, ja},
             combo3:{ja, desc}, moves:{skill:{ja,en,cd,cost,desc}, ...},
             core:"astro:core_mercury", suit:"astro:suit_mercury", suitOff:"astro:suit_mercury_off",
             weaponId:"astro:weapon_mercury" }, ...
};
export const CORE_TO_PLANET = {"astro:core_mercury":"mercury", ...};
export const WEAPON_TO_PLANET = {...};  export const SUIT_TO_PLANET = {...};
export const ENEMIES = {...};
```

### 4.2 アイテム ID
| ID | 用途 | 備考 |
|---|---|---|
| `astro:core_<key>` | 惑星コア（9） | stack 1、use_modifiers 0.2 秒、手に持つと 3D のコア |
| `astro:weapon_<key>` | ナノウェポン（9） | hand_equipped、damage、耐久なし、クリエイティブ一覧に出さない |
| `astro:suit_<key>_on` | 組み上がり中のスーツ（9） | wearable slot.armor.head、protection = defense、一覧に出さない |
| `astro:suit_<key>` | スーツ（9） | wearable slot.armor.head、protection = defense、一覧に出さない |
| `astro:suit_<key>_off` | 分解中のスーツ（9） | 同上、protection 0 |
| `astro:nano_cell` `astro:core_frame` `astro:solar_fragment` `astro:terminal` `astro:void_signal` | 素材・道具 | |
| `astro:hologram_target_spawn_egg` 等 | スポーンエッグ | entity の spawn_egg で自動 |

アイコン: `textures/items/astro/<name>.png`（64x64、モデルからレンダリング。素材はペイント）。
item_texture.json のキーは `astro_<name>`。

### 4.3 モデルの規約

**座標**: 16 単位 = 1 ブロック。プレイヤーは -Z が正面、右手が -X。回転の規則は `tools/hyperdim/hd_space.py`
（`R = Rz(-rz)·Ry(ry)·Rx(-rx)`）。プレビューは `hd_scene` と同じく X を鏡映して描く。

**スーツの骨格**（`astro_suit.py`）: トップレベルのボーンはプレイヤーと同名・同ピボット
```
body (0,24,0)   head (0,24,0)   rightArm (-5,22,0)   leftArm (5,22,0)
rightLeg (-1.9,12,0)   leftLeg (1.9,12,0)
```
肌の箱: head (-4,24,-4)+(8,8,8) / body (-4,12,-2)+(8,12,4) / rightArm (-8,12,-2)+(4,12,4) /
leftArm (4,12,-2)+(4,12,4) / rightLeg (-3.9,0,-2)+(4,12,4) / leftLeg (-0.1,0,-2)+(4,12,4)。
外側のレイヤー（帽子 0.5・上着/袖/ズボン 0.25）より外を覆うこと。

**部位ボーン**: キューブは必ず部位ボーンに入れる（トップレベルのボーンに直接置かない）。部位ボーンの名前は
`<群>_<名前>` で、群は組み上がりの順番（astro_data.ASSEMBLE_ORDER）:
`inner`（インナー。最初に一瞬で）/ `boots` / `legs` / `waist` / `torso` / `back` / `arms` / `shoulders` /
`helmet` / `visor` / `extra`（環・衛星・マントなど）。
部位ボーンの pivot は「生えてくる根元」（ブーツなら足首、肩当てなら肩の付け根）に置く。組み上がりは pivot を
中心に scale 0 → 1.15 → 1.0（0.25 秒）でポップする。
アニメで動かす部位（回る環・衛星・スラスターの炎・マント・バイザーの光）はさらに子ボーンに分ける。
スラスターの炎ボーンは `fx_thrust_*`（空中で伸び、地上で縮む）、発光の脈動は `fx_glow_*`、
回転体は `fx_spin_*`（動きは planets/<key>/suit.py の SUIT_ANIMS で書く）。

**被覆の検査**（check_astro_suits.py）: 6 部位それぞれ、肌の外側レイヤーの表面（帽子 0.5、他 0.25 膨らませた箱）を
0.5 単位間隔で標本化し、各点が同じトップレベルボーン配下のいずれかのキューブ（回転・inflate 込み）の内側に
あることを確かめる。1% を超えて外に出ていたらビルドを止める（関節の内側など見えない所は許容リストで除外可）。

**ナノウェポン**（`planets/<key>/weapon.py` の build_weapon）: hyperdim と同じ武器空間（握り = 原点、刃先 = -Z、+Y = 上）。
ボーン `hold`（`binding: q.item_slot_to_bone_name(c.item_slot)`）→ `root` → 部品。形成アニメ用に
部品ボーンへ `form_<順番>_<名前>`（例 `form_0_grip`, `form_1_guard`, `form_2_blade`）と付けると、
gen_astro_anim が持ち替えた瞬間に刃が伸びるアニメを作る。回る部品は `fx_spin_*`。
持ち方は kind ごとに astro_hold.py が決める（三人称・一人称）。kind: saber / scepter / sword / axe / hammer /
ring / crossbow / trident / greatsword。

**コア**（build_core）: 手のひらサイズ（直径 5〜7 単位）。中心にその惑星の球（模様を描く）、機械の枠、
`fx_spin_*` のリング。持ち方は `core` 種（拳の少し上に浮かせて持つ）。

**テクスチャ密度**: スーツは uv_scale 4 を目安に 1024x1024 に収まる最大（hyperdim の build_model と同じ探索）。
ウェポン・コアも同様。材質は astro_paint の kind を使う（4.4）。

### 4.4 ペインタ（astro_paint.py）
`HDPainter` を継承し、セル塗りのアニメ調メカの素材を足す。スタイルは `{"kind": ..., 色...}` の辞書で、
キューブの `style` 名 → スタイル。`astro_paint.suit_styles(planet_key, **over)` が惑星の配色から一式を作る。

追加する kind（最低限）:
| kind | 見た目 |
|---|---|
| `armor` | 主装甲。面のグラデーション、上辺と左辺の照り、下辺と右辺の影、パネルライン、小さなボルト |
| `armor2` | 副装甲（色違い）。帯や縞の模様を `stripe` で指定可（木星の縞など） |
| `inner` | 黒いインナー。六角メッシュと細い発光の継ぎ目 |
| `frame` | 関節・フレームの暗い金属。溝と細かい部品 |
| `chrome` | 鏡面（帯状の映り込みのグラデーション） |
| `visor` | バイザーのガラス（発光、上が明るいグラデーション、斜めの照り返し） |
| `glowline` | 発光ライン（全発光、芯が白） |
| `vent` | 排気口のスリット（奥が発光） |
| `thruster` | ノズルの内側（同心円の発光） |
| `core` | 星核（その惑星の模様: mercury 銀の液面 / venus 黄色い雲の渦 / earth 大陸と雲 / mars 赤い砂と極冠 / jupiter 縞と大赤斑 / saturn 縞 / uranus 淡い青緑 / neptune 紺と暗斑 / sol 粒状斑とプラズマ）。全発光寄り |
| `planet` | `core` と同じ模様を装甲の差し色として（発光なし） |
| `decal` | 警告ストライプ・型番・紋章などを面に重ねる（デカール機構は mctexture に倣う） |
| `flame` | スラスターの炎（全発光、先が透明に近い） |
| `cloth` | マント（hd_paint の cloth を流用、雲の縁取り） |
| `crystal` / `ice` | 氷晶・ダイヤ（hd_paint の crystal を流用） |
発光は entity_emissive_alpha の規約（アルファが低いほど自己発光）。

### 4.5 アタッチャブル（スーツは gen_astro_suits、ウェポン・コアは gen_astro_weapons が書き出す）
調査で確かめた事実（vanilla bedrock-samples 1.26.50 と公開パックから）:
* 名前がプレイヤーのボーンと一致するボーンは、スロットに関係なくそのボーンの最終変換に付いて動く（大文字小文字は区別しない）。
  **装飾ボーンにプレイヤーと同じ名前（cape, hat, jacket, waist, root, rightItem, helmet, bodyArmor, belt, rightSock …）を付けない**。
* アタッチャブル内の素の `q.*` は持ち主（装着者）を評価する（q.is_on_ground, q.is_sneaking, q.is_sprinting, q.is_invisible …）。
  素の `v.*` はアタッチャブル自身の変数。持ち主の攻撃の振りは `c.owning_entity->v.attack_time`。
* 一人称でもアタッチャブルは描かれ、カメラは head ボーンの中。`c.is_first_person` は装着者本人の一人称だけ 1。
* `entity_emissive_alpha` は裏面を描く（カリング無し）ので、閉じた殻の内側が一人称で画面を覆う。
  → スーツは **既定 `entity_emissive_alpha_one_sided`、`fx_*` ボーンだけ `entity_emissive_alpha`** にする
  専用レンダーコントローラ `controller.render.astro.suit`（materials: `[{"*":"Material.default"},{"fx_*":"Material.fx"}]`）。
* 発光: アルファ 0 = 抜き、255 = 普通に陰影、その間は不透明で **アルファが低いほど強く光る**（1〜40 で全発光）。
  `tools/mctexture.py` の EM=254 はほぼ光らないので使わない（hd_paint の EMI=12 / SOFT=150 の規約に従う）。
* アタッチャブルのインスタンス（コントローラの状態）は、アイテムがそのスロットに現れた時と、見る側のクライアントで
  持ち主が読み込まれた時（描画距離に入る・リスポーン・次元移動・再参加）に作り直される。
  → 組み上がりは **専用 ID `astro:suit_<key>_on`** にだけ持たせ、組み上がり後にスクリプトが `astro:suit_<key>` に差し替える。
* 一回きりのアニメは `"loop": "hold_on_last_frame"` と `animation_length` を明示し、`q.all_animations_finished` で遷移。
  インベントリの人形（`q.is_in_ui`）では組み上がりを飛ばす。

**スーツ** 3 種（同じジオメトリ・テクスチャ）:
| ID | コントローラの初期状態 | 用途 |
|---|---|---|
| `astro:suit_<key>_on` | assemble（1.8 秒、部位がポップ）→ ready | 変身の組み上がり中（スクリプトが suit_equip で置き、assemble_len 後に無印へ差し替え） |
| `astro:suit_<key>` | ready | 装着中（後から見えた人にも組み上がりを繰り返さない） |
| `astro:suit_<key>_off` | release（逆順に縮んで消える 0.8 秒）→ gone（全部 scale 0） | 解除の分解（0.9 秒後に外す） |
```
materials default=entity_emissive_alpha_one_sided, fx=entity_emissive_alpha
render_controllers: controller.render.astro.suit
scripts.parent_setup: "v.helmet_layer_visible = 0.0; v.chest_layer_visible = 0.0; v.leg_layer_visible = 0.0; v.boot_layer_visible = 0.0;"
animate: controller, idle, {thrust: !q.is_on_ground（なめらかに）}, {sprint: q.is_sprinting}, {fp_hide: c.is_first_person},
         {hide_all: c.item_slot != 'head' || q.is_invisible}
```
`fp_hide`: 一人称では head・body・rightLeg・leftLeg を scale 0（腕だけ残る）。`hide_all`: 6 つのトップレベルボーンを scale 0。

**ナノウェポン** `astro:weapon_<key>`: tp / fp（持ち方）・idle・swing（`c.owning_entity->v.attack_time`）・
controller（初期 form → ready）。**コア** `astro:core_<key>`: tp / fp・idle（リングの回転・球の脈動）。
ウェポン・コアも閉じた殻は one_sided、`fx_*` は両面の同じ方式でよい。

### 4.6 全身モーション（playanimation）
`astro_animlib.py` の記法でキーポーズを書き、`animation.astro.p.<名前>` として書き出す。
共通（全形態）: `none`, `henshin`（変身 3.0 秒）, `revert`, `airjump`, `boost`, `hover`（ループ）, `step`, `land`,
`barrier`, `ult_rise`, `cast`（片手を掲げる）, `throw`, `slam`, `thrust`, `spin`。
惑星ごと: `<key>.combo1` `<key>.combo2` `<key>.combo3` と、技で使う `<key>.<自由な名前>`
（planets/<key>/body.py の BODY_ANIMS に書く）。
コントローラ名: `astro.act`（技・コンボ）, `astro.move`（機動）, `astro.pose`（変身・ホバー）。
バニラの攻撃の振り・持ち姿勢との足し合わせは hyperdim の gen_hd_anim（ATK_CANCEL, 一人称は腕 25%）に倣う。
`anim_meta.js` に `{ "<名前>": [長さ秒, ブレンド可否] }`。

### 4.7 パーティクル（gen_astro_particles）
全て白で描いたスプライトを、スクリプトが渡す色で染める。**色は必ず
`"minecraft:particle_appearance_tinting": {"color": [...]}` の中に書く**（hyperdim の tint() は
components 直下に "color" を置いてしまっていて染まらない。同じ誤りをしない）。

スクリプトから渡す変数（全て任意。`v.x ?? 既定値` で受ける）:
`v.cr v.cg v.cb`（色 0..1）`v.size` `v.life` `v.rot` `v.count` `v.speed` `v.spread`
`v.vx v.vy v.vz`（向き・終点のずれ）`v.var`（スプライトの種類）`v.height` `v.spin` `v.rate` `v.grav` `v.len`

ID（`astro:` を付けて spawnParticle）。★ は流れや形のある特別な動き:
| ID | 内容 |
|---|---|
| `glow` `trail` `dot` `spark` `star` `impact` `flare` | 発光の基本（hyperdim と同等） |
| `ring` `ring_flat` `shock_flat` | 輪（正面向き）／水平の輪／地を走る衝撃波（太い輪が広がる） |
| `circle` `circle_v` `hex_circle` | 技術的な陣（目盛りと文字の円）水平／垂直／六角 |
| `emblem` | 惑星紋章の陣（水平）。`v.var` = 惑星番号 0..8（order-1） |
| `hex` | 六角形のセル（バリア・ホログラム） |
| `scan` | 縦に走る走査線（変身・ホログラム） |
| `pillar` `beam` | 柱（`v.height`）／光線（★ `v.vx,vy,vz` 方向へ `v.len` m 伸びる帯） |
| `slash` `slash_big` `slash_flat` `cross` `thrust` | 斬撃・十字・突きの閃光 |
| `speedline` `wind` `vortex`★ `converge`★ `orbit`★ `aura` | 流れ |
| `nano`★ | ナノマシンの粒（小さな四角とひし形が明滅）。`v.vx,vy,vz` へ `v.life` 秒で飛ぶ |
| `nano_stream`★ | エミッタから (vx,vy,vz) ずれた点へ、螺旋を描いて流れ込む粒の列（変身の奔流） |
| `smoke` `dust` `debris`★ | 煙・土煙・岩の破片（重力で落ちる） |
| `ember` `flame` `plasma` | 火の粉・炎・プラズマの渦 |
| `bolt` `arc` | 稲妻（★ `v.len` で長さ）・放電のちらつき |
| `shard` `ice` `diamond` | 結晶片・氷晶・ダイヤ |
| `droplet` `splash` `bubble` `wave`★ | 液体金属の滴・水しぶき・泡・波頭（進む弧） |
| `cloud`★ | 硫酸雲（ゆっくり膨らんで漂う、blend） |
| `aurora`★ | オーロラの幕（縦に揺らぐ帯） |
| `meteor`★ | 尾を引く火球（向き vx,vy,vz） |
| `black_hole` | 暗い円盤と降着円盤（blend + add の二層） |
| `void` | 紫黒の裂け目・触手（敵用） |
| `warning` | 敵の攻撃予告（地面の赤い円と縞） |
| `afterimage` | 人型の残像（スーツの輪郭） |
| `lens` | 光のにじみ（大きく淡い、必殺技の締め） |
**事実（調査済み）**: format_version は全て "1.10.0"。`lookat_direction` / `direction_x` ではサイズの **[0] が向きに沿う長さ**。
速度の無い粒の向きは `"direction": {"mode": "custom", "custom_direction": [...]}`。光は particles_add（lighting なし）、
暗い煙・虚無は particles_blend。spawnParticle は 1 回ごとに全クライアントへ 1 パケットなので、fx.js の予算は
「回数 × 粒数の重み」で数え、1 tick あたり 100 回前後を上限にする（演出の量の設定で倍率）。輪・線は 1 回で描ける
形状エミッタ（PARTICLES.md の *_n）を使う。

### 4.8 HUD グリフ（gen_astro_ui → glyphs.js）
`font/glyph_<XX>.png`（ページ番号は gen_astro_ui の冒頭で決め、glyphs.js に書く）。§4 の HUD に必要なもの:
惑星紋章（小・大）、星力バーのセル（惑星色 × 満/半/空 + 端）、超新星バー（満/空/流れる光）、
技アイコン（4 種 × 惑星色 × 使える/待ち）、状態アイコン（星力・ゲージ・解除・オーバーヒート・バリア）、
変身の進捗バー、カットイン用の帯。`glyphs.js`:
```js
export const G = { emblem: {mercury:"\uE...", ...}, emblemBig: {...},
  energy: {mercury:{full,half,empty,capL,capR}, ...}, nova: {full,empty,flow,capL,capR},
  move: {mercury:{skill:{ready,wait}, dash:{...}, air:{...}, ult:{...}}, ...},
  icon: {energy, nova, revert, overheat, barrier, sync}, sync: {full,empty,capL,capR}, banner: {...} };
```

### 4.9 効果音（gen_astro_sounds、`astro.<名前>`）
合成（素材なし）。各音 2〜3 種の揺らぎ。最低限:
```
core_on core_ring swarm assemble_click armor_lock visor_on transform_burst weapon_form revert power_down
thrust jump boost hover step just_dodge land barrier barrier_hit
swing swing_heavy hit hit_heavy hit_metal crit
laser beam_charge beam_fire explosion explosion_big impact_heavy
liquid zap thunder ice_crack ice_shatter wind gust water_wave splash gravity ring_spin clock_tick time_stop
flare corona supernova cutin ui_open ui_select ui_back alert overheat sync_up
drone_hum drone_laser sentinel_step sentinel_slam nemesis_roar nemesis_charge nemesis_spawn meteor
```

### 4.10 スクリプトの API（惑星の技はこれだけを使って書く）
```js
// planets/<key>.js
import { register, lunge, hover, plunge, warp, behind, safeAhead, ultOpen, projectile, zone, dirTo } from "../engine.js";
import { P, line, ring, arc, burst, shock, beam, swarm, emblem, flash, shake, sound, body, afterimage, white } from "../fx.js";
import { hit, enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy, freeze, pull, launch } from "../combat.js";
register("<key>", {
  skill(ctx) { ...; return 何tick技の最中か; },
  dash(ctx) {...}, air(ctx) {...}, ult(ctx) {...},
  combo3(ctx, target) {...},       // 三段目の追撃（ctx.kind === "combo3"）
  burst(ctx) {...},                // 変身の締め（TRANSFORM.planet_burst）
  passive: { tick(p, st) {}, onHit(p, target, dmg) {}, onHurt(p, attacker, dmg) {}, onKill(p, victim) {} },
});
```
`ctx`: `p` プレイヤー / `key` / `planet`（data.js の PLANETS[key]） / `kind` / `dim` / `c` 発光色 / `light` / `deep` /
`accent` / `hot`（白寄りの発光色） / `f` 水平前方 / `v` 視線 / `start` 開始位置 /
`at(t, fn)` t tick 後に実行（死亡・退出・解除で止まる） / `every(t0, n, step, fn)` / `once(e, max)` /
`loc()` `chest()` `front(d, y)` `liveDir()` / `dmg(base)` 同調率と惑星の補正を掛けたダメージ / `level` 同調率 Lv。
細かい引数は engine.js・fx.js・combat.js の JSDoc を正とする。

### 4.10b スクリプト API の事実（@minecraft/server 1.13.0 で確認済み）
* ある: itemUse / itemStartUse / itemStopUse / itemReleaseUse（使用時間のあるアイテムだけ）/ entityHitEntity / entityHurt /
  entityDie / entitySpawn / playerSpawn / playerLeave / worldInitialize、Entity.playAnimation（players は名前の配列）、
  Dimension.spawnParticle + MolangVariableMap（名前は "variable.xxx"）、applyKnockback(dx, dz, 水平, 垂直)、
  player.camera.setCamera / fade / clear（コマンド `camera` も可）、player.inputPermissions.movementEnabled / cameraEnabled、
  onScreenDisplay.setTitle（options を渡すなら fadeIn/stay/fadeOut の 3 つ全部、tick）/ updateSubtitle / setActionBar /
  setHudVisibility、ItemStack.lockMode / keepOnDeath、isJumping（ジャンプを押している間 true）/ isSneaking / isSprinting。
* ない: Player.inputInfo、playerButtonInput、playerSwingStart、beforeEvents.entityHurt（ダメージの打ち消しは afterEvents で回復）、
  worldLoad、プレイヤーへの applyImpulse / clearVelocity（動かすのは applyKnockback と levitation / slow_falling だけ）。
* カメラと入力ロックは、起動時と playerSpawn で必ず解除する（カメラは /reload やエラーを越えて残る）。
* ホバー: ジャンプ長押し中は levitation（Lv1〜3、6 tick を 2〜4 tick ごとに掛け直し）、離したら slow_falling、スニークで両方外す。

### 4.11 検査
`build_astro.py` は生成 → `test_astro.py` → `check_astro_suits.py` → `validate_astro.py` の順に走らせ、
どれかが失敗したら dist を書かない。
* **test_astro.py**: hyperdim の test_hd.py と同じく @minecraft/server を動くスタブに差し替え、
  9 形態 × {変身, 4 技, 三段コンボ, 機動 5 種, バリア, 解除, 死亡→リスポーン, 星力切れ} と敵 3 種の攻撃を
  実行し、例外が無いこと、技がダメージを与えること、使ったパーティクル・効果音・全身モーション・アイテム ID が
  パックに実在することを確かめる。
* **validate_astro.py**: ジオメトリ・テクスチャ・アニメ・アタッチャブル・パーティクル・効果音・アイコン・
  言語キー・レシピ・マニフェスト・item_texture の相互参照、UV がテクスチャ内、Molang の括弧、
  パーティクルの色が tinting の中にあること、JSON の形式。
* **check_astro_suits.py**: 被覆（4.3）、部位ボーンの命名、キューブ数の下限（スーツ 250）、ボーン名の重複。
* **プレビュー**: preview_astro.py が docs/astro/ に、スーツの正面・背面・斜め（素の状態と組み上がり途中）、
  武器、コア、アイコン一覧、HUD の見本、パーティクルの見本を書き出す。作業者は自分の担当の絵を必ず見て直す。
