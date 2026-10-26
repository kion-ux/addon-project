# NIGHT RUNNER: 感染都市 — 設計の約束事（実装者向け）

Minecraft **統合版 (Bedrock)** 用の、パルクール × ゾンビ × 部位破壊ゴアのアドオン。
ダイイングライト 2 の「昼は屋上を走り、夜は追われる」遊びを、オリジナルの名前・デザインで作る。
**このファイルは全生成スクリプト・全スクリプトが守る契約**。ID・ボーン名・プロパティ名・
ファイルの持ち主をここで固定する。変えるときはこのファイルを先に直すこと。

---

## 0. 基本

| 項目 | 値 |
|---|---|
| 名前 | `NIGHT RUNNER: 感染都市` / `NIGHT RUNNER: Infected City` |
| 名前空間 | `nr`（ID は `nr:...`、ファイル名・テクスチャのキーは `nr_...`） |
| 版 | `1.0.0`（manifest は `[1, 0, 0]`） |
| min_engine_version | `[1, 21, 120]` |
| Script API | `@minecraft/server` **2.3.0**、`@minecraft/server-ui` **2.0.0**（安定版のみ。ベータ API 禁止） |
| BP / RP | `packs/nightrunner_BP` / `packs/nightrunner_RP` |
| 生成スクリプト | `tools/nightrunner/`（Python 3、Pillow・numpy・ffmpeg が使える） |
| ビルド | `./build_nightrunner.sh` → `tools/nightrunner/build_nr.py` → `dist/NightRunner_v1.0.0.mcaddon` ほか |
| 言語 | 日本語 (`ja_JP`) / English (`en_US`)。コメント・README は日本語 |
| ゴアレベル | 設定 0〜100、**既定 100** |

### 生成方針

* `packs/nightrunner_*` の **JSON・PNG・OGG はすべて Python から生成**する（手で置かない）。
  例外は **`packs/nightrunner_BP/scripts/` の手書き JS**（`scripts/data/` だけは生成）。
* 生成は決定的に（乱数は `random.Random(固定 seed)`、ハッシュは `zlib.crc32`。組み込み `hash()` 禁止）。
  同じ入力から同じバイト列が出ること。
* 2.x の Script API の注意: スクリプトはワールド読み込み前に走る（early execution）。
  `world` を触る初期化は `world.afterEvents.worldLoad` か `system.run` の中で。
  カスタムコンポーネントの登録は `system.beforeEvents.startup`。`isValid` はプロパティ。
  `applyKnockback({x, z}, vertical)`。before イベント内で世界を書き換えない（`system.run` へ逃がす）。
* 型検査: `tools/nightrunner/typings/` に公式の d.ts（server 2.3.0 / server-ui 2.0.0 / common）を置き、
  `check_nr_types.py` が `tsc --checkJs --noEmit` で全 JS を検査する（ビルドに含む）。

---

## 1. ファイルの持ち主（並行作業で衝突しないために）

一つのファイルを書くのは一つの生成器だけ。共有の登録ファイル（`item_texture.json`、`terrain_texture.json`、
`sound_definitions.json`、`blocks.json`、`flipbook_textures.json`、言語ファイル）は、各生成器が
**断片**を `tools/nightrunner/.frag/<登録名>/<生成器名>.json` に書き、`gen_nr_packs.py` が最後にまとめる
（`.frag/` は gitignore）。断片は「最終ファイルの該当する辞書」をそのまま入れる:

| 登録名 | 断片の中身 | まとめ先 |
|---|---|---|
| `item_texture` | `{ "nr_xxx": {"textures": "textures/nr/items/xxx"} }` | RP `textures/item_texture.json` |
| `terrain_texture` | `{ "nr_xxx": {"textures": "textures/nr/blocks/xxx"} }` | RP `textures/terrain_texture.json` |
| `sound_definitions` | `{ "nr.xxx": {"category": ..., "sounds": [...]}}` | RP `sounds/sound_definitions.json` |
| `blocks` | `{ "nr:xxx": {"sound": "stone"} }` | RP `blocks.json` |
| `flipbook` | `[ {...}, ... ]` | RP `textures/flipbook_textures.json` |
| `lang` | `{ "ja_JP": {"key": "値"}, "en_US": {...} }` | BP/RP `texts/*.lang` |
| `sounds_json` | `{ "entity_sounds": {...}, "individual_event_sounds": {...} }` | RP `sounds.json` |

| 生成器 | 書くもの |
|---|---|
| `nr_common.py` | 定数・パス・`write_json`・`frag()`（断片を書く）・ID 補助 |
| `nr_spec.py`（`nr_spec_zombies.py` / `nr_spec_catalog.py` を再輸出） | 全登録データ（ゾンビ 50 体・武器・アイテム・罠・ブロック・小道具・建物・スキル）。**名前（日英）はここ** |
| `nr_paint.py` | 写実寄りの素材ペインタ（腐肉・筋肉・骨・内臓・血・布・金属・ゴム…） |
| `nr_rig.py` / `nr_kit.py` | ゾンビの共通骨格・ゴア用ボーン・断面（stump）・ちぎれた部位（gib）の抽出 / 服・装備・変異の部品集 |
| `gen_nr_zombies.py`（+ `zoo_*.py`） | ゾンビ 50 体のジオメトリ・テクスチャ・gib ジオメトリ |
| `gen_nr_zombie_anim.py` | ゾンビのアニメーション・アニメーションコントローラ |
| `gen_nr_player_anim.py` | プレイヤーのパルクール・武器モーション（`playAnimation` で再生） |
| `gen_nr_weapons.py` | 武器のモデル・テクスチャ・アイコン・アタッチャブル・アイテム JSON・レシピ |
| `gen_nr_props.py` | 小道具エンティティ（車・バス・コンテナ…）のモデル・テクスチャ |
| `gen_nr_blocks.py` | カスタムブロック（バリケード・街灯・UV ライト・罠・瓦礫…）のモデル・テクスチャ・BP JSON |
| `gen_nr_structures.py` | `.mcstructure` の書き出し（建物モジュール）と `scripts/data/structures.js` |
| `gen_nr_particles.py` | スプライトアトラスとパーティクル |
| `gen_nr_sounds.py` | 効果音の合成（numpy + ffmpeg）と sound_definitions の断片 |
| `gen_nr_ui.py` | 独自グリフのフォント（HUD 用）、フォームのアイコン、パックアイコン |
| `gen_nr_entities.py` | BP: ゾンビ 50・gib・飛び道具・小道具のエンティティ、スポーンルール、ルートテーブル / RP: クライアントエンティティ、レンダーコントローラ |
| `gen_nr_items.py` | 武器以外のアイテム（回復・投擲物・素材・道具）とレシピ |
| `gen_nr_data_js.py` | `scripts/data/*.js`（spec とリグ寸法を JS へ） |
| `gen_nr_packs.py` | manifest、断片のまとめ、言語ファイル。**最後に走る** |
| `build_nr.py` | 上を順に実行 → `test_nr.py` → `check_nr_types.py` → `validate_nr.py` → dist |

---

## 2. ID の付け方

| 種類 | 形 | 例 |
|---|---|---|
| ゾンビ | `nr:z_<key>` | `nr:z_office_worker`、`nr:z_volatile` |
| ちぎれた部位 | `nr:gib` | （プロパティで種類と部位を選ぶ） |
| 飛び道具 | `nr:proj_<key>` | `nr:proj_bolt`、`nr:proj_molotov`、`nr:proj_spit` |
| 小道具（車など） | `nr:prop_<key>` | `nr:prop_sedan_wreck` |
| 武器 | `nr:w_<key>` | `nr:w_machete` |
| その他アイテム | `nr:<key>` | `nr:medkit`、`nr:uv_flashlight` |
| ブロック | `nr:<key>` | `nr:barricade`、`nr:uv_lamp`、`nr:spike_trap` |
| パーティクル | `nr:<name>` | `nr:blood_spray` |
| 効果音 | `nr.<分類>.<名前>` | `nr.gore.sever`、`nr.z.groan`、`nr.pk.vault` |
| ジオメトリ | `geometry.nr.<分類>.<key>` | `geometry.nr.z.office_worker`、`geometry.nr.gib.office_worker`、`geometry.nr.w.machete` |
| アニメーション | `animation.nr.<分類>.<名前>` | `animation.nr.z.walk_shamble`、`animation.nr.p.vault` |
| アニメコントローラ | `controller.animation.nr.<分類>.<名前>` | `controller.animation.nr.z.locomotion` |
| レンダーコントローラ | `controller.render.nr.<名前>` | `controller.render.nr.zombie`、`controller.render.nr.gib` |
| テクスチャ | `textures/nr/<分類>/<key>` | `textures/nr/zombies/office_worker`、`textures/nr/items/machete` |
| 言語キー | 標準の形 | `entity.nr:z_office_worker.name`、`item.nr:w_machete`、`tile.nr:barricade.name` |
| 動的プロパティ | `nr:<名前>` | エンティティ `nr:hp`、ワールド `nr:settings` |
| scriptevent | `nr:<名前>` | `nr:kit`、`nr:city`、`nr:spawn`、`nr:settings`、`nr:gore` |

ゾンビの**種類番号 `ztype`** は `nr_spec.ZOMBIES` の並び順（0〜49）。gib・データ JS・レンダーコントローラの配列は全部この順。

---

## 3. ゾンビの骨格（全 50 体共通・名前を変えない）

単位は Bedrock のモデル単位（16 = 1 ブロック）。基準身長 180cm ≒ 32 単位（`tools/rig.py` と同じ）。
種類ごとに身長・体格・猫背・腕の長さは変えてよいが、**ボーン名と親子関係は下の通り**。

```
root                               足元 (0,0,0)。歩き・倒れ・這いの全身の移動と回転
└ waist                            腰 (0, hip_y, 0)
  ├ pelvis                         骨盤の箱・腰回りの服。ここに脚が付く
  │ ├ leg_r                        右股関節。太腿
  │ │ ├ shin_r                     膝。脛
  │ │ │ └ foot_r                   足首。足
  │ │ └ stump_leg_r_lower          膝の断面（leg_r = cut_lower で表示）
  │ ├ stump_leg_r_upper            股関節の断面（leg_r = cut_upper で表示）
  │ ├ leg_l / shin_l / foot_l / stump_leg_l_lower
  │ └ stump_leg_l_upper
  └ torso                          腹（背骨の下半分）
    ├ torso_wound                  腹の切り傷（torso = slashed 以上で表示）
    ├ guts                         垂れた腸（torso = gutted / halved で表示）
    ├ stump_torso                  胴の断面と背骨・腸（torso = halved で表示。下半身は pelvis ごと消える）
    └ chest                        胸
      ├ neck                       首
      │ ├ head                     頭（髪・帽子・マスクはこの子）
      │ │ ├ jaw                    下顎（head = jawless で消える）
      │ │ ├ head_wound             顔の裂傷（head = wounded / jawless / cracked で表示）
      │ │ └ skull_open             割れた頭蓋と脳（head = cracked で表示）
      │ └ stump_neck               首の断面（head = severed / crushed で表示）
      ├ arm_r                      右肩。上腕
      │ ├ forearm_r                肘。前腕
      │ │ └ hand_r                 手首。手
      │ ├ arm_r_wound              腕の傷（arm_r = wounded / broken で表示）
      │ └ stump_arm_r_lower        肘の断面（arm_r = cut_lower で表示）
      ├ stump_arm_r_upper          肩の断面（arm_r = cut_upper で表示）
      ├ arm_l / forearm_l / hand_l / arm_l_wound / stump_arm_l_lower
      └ stump_arm_l_upper
```

* 服・装備・変異の部品は**それが付く体の部位のボーンの子**にする（腕が落ちたら袖も一緒に落ちる）。
  部品用の子ボーンを足すのは自由（例 `head` の子に `hat`、`chest` の子に `armor_chest`）。
  ただし上の名前は消さない・親を変えない。装甲のある種類は `armor_head`、`armor_chest`、`armor_arm_r`…
  （`nr:armor` で表示を切る）。
* **`part_visibility` は子へ伝わらない**（`reference/rendering.md` §1。親を隠しても子は描かれる。変換は伝わる）。
  だから**すべてのボーンに「自分と全祖先の条件の AND」の式を生成する**（`nr_rig.visibility_rules()`）。
  断面ボーンは「消える部位の親」に付ける（例: 肩の断面は `chest` の子、肘の断面は `arm_r` の子）。
* 追加の子ボーン（spec が使う）: `gear_tank` `gear_flashlight` `gear_shield` `held_tool` `held_debris` `throat_sac`
  `acid_sac_<場所>` `extra_head_<n>` `armor_<部位>`。`nr:armor` は装甲の段階に加えて、壊れて外れる装備
  （spec の `gore.breakables = {bone: 最低段階}`）の表示にも使う。初期値は spec の `initial_armor(z)`。
* `nr:ability` の値 1..7 は種類ごとに spec の `ability_states(z)` が割り当てる（能力の順 → 段階の順）。
  アニメは `animation.nr.z.ab_<ability>_<phase>`（`zombie_animations(z)` が列挙）。0 は「能力なし」。
* 断面（stump）は、赤い筋肉・白い骨の断面・黄色い脂肪の輪・滴る血の小キューブで作り、
  `nr_paint` の `cut_flesh` / `bone` / `gore_wet` で塗る。
* 光る目などは `entity_emissive_alpha` 系のマテリアル（`reference/rendering.md` に従う）。

### ゾンビのエンティティプロパティ（BP の `description.properties`。全部 `client_sync: true`）

| プロパティ | 型 | 値 | 既定 |
|---|---|---|---|
| `nr:head` | enum | `intact` `wounded` `jawless` `cracked` `severed` `crushed` | `intact` |
| `nr:arm_r` / `nr:arm_l` | enum | `intact` `wounded` `broken` `cut_lower` `cut_upper` | `intact` |
| `nr:leg_r` / `nr:leg_l` | enum | `intact` `wounded` `broken` `cut_lower` `cut_upper` | `intact` |
| `nr:torso` | enum | `intact` `slashed` `gutted` `halved` | `intact` |
| `nr:blood` | int 0..3 | 体の血の量（傷の数で上がる） | 0 |
| `nr:burn` | int 0..3 | 焼け具合（3 で炭化） | 0 |
| `nr:shock` | int 0..1 | 感電中 | 0 |
| `nr:armor` | int 0..3 | 残っている装甲の段階（装甲持ちのみ意味がある） | 3 |
| `nr:state` | enum | `normal` `crawl` `climb` `stagger` `down` `special` `dead` | `normal` |
| `nr:pose` | int 0..7 | 死に方・倒れ方の変化 | 0 |
| `nr:ability` | int 0..7 | 特殊能力の段階（溜め・発動など。種類ごとに意味を決める） | 0 |
| `nr:variant` | int 0..3 | 見た目の変化（生成器が使うなら） | 0 |

render controller `controller.render.nr.zombie`（全種類共通）の `part_visibility` は上の表から
**生成**する（手書きしない）。例: `forearm_r` は `arm_r` が `cut_lower` / `cut_upper` のとき非表示、
`arm_r` は `cut_upper` のとき非表示、`pelvis` は `torso == 'halved'` のとき非表示。

---

## 4. 体力とダメージ（ゾンビは「本当の体力」をスクリプトが持つ）

* ゾンビの `minecraft:health` は**大きなプール**（`value: 1000, max: 1000`）。本当の体力は動的プロパティ
  `nr:hp`（初回に spec の `hp` で初期化）。
* `world.afterEvents.entityHurt` で受けたダメージを、部位・武器・耐性で補正して `nr:hp` から引き、
  直後に `minecraft:health` を最大へ戻す（バニラでは死なない）。`nr:hp <= 0` で**死亡処理**
  （`nr:on_death` イベント → `nr:dead` コンポーネントグループ: AI・移動・攻撃を外し、物理と押せる体だけ残す。
  `nr:state = dead`、`nr:pose` に死に方。死体は設定の秒数で消す）。
* プール以上の一撃（/kill、巨大爆発など）でバニラの死が来たら `entityDie` で**全身が弾け飛ぶ**ゴアにする。
* ルート・経験値はバニラの死を通らないので、スクリプトが spec の `loot` で落とす。
* スクリプトが自分で入れるダメージ（技・罠・爆発）は `applyDamage` の前に「予約」を記録し、
  `entityHurt` 側で二重に数えない。

### 当たった部位の判定

`scripts/data/zombies.js`（生成）に、種類ごとの**部位の当たり箱**（ゾンビの足元を原点、向きはゾンビの
yaw、単位ブロック）を書き出す: `head`、`torso`（胸＋腹）、`arm_r/l`（上腕＋前腕の 2 箱）、
`leg_r/l`（太腿＋脛の 2 箱）。`nr:state` が `crawl` / `down` / `dead` のときは寝た姿勢の箱を使う。
近接はプレイヤーの目から視線方向のレイ、飛び道具は着弾点、で一番近い箱を選ぶ。
外れたら「狙いの高さ」で決める。

### ゴアの結果（ダメージ種別 × 部位）

ダメージ種別 `dtype`: `slash`（刃）/ `blunt`（打撃）/ `pierce`（刺突・矢・弾）/ `blast`（爆発）/
`fire` / `shock` / `toxic`。武器の重さ `weight`: `light` / `medium` / `heavy`。

| 部位 | slash | blunt | pierce（銃の大口径・散弾は強） | blast |
|---|---|---|---|---|
| 頭 | 弱: `wounded`→`jawless`、強: `severed`（首が飛ぶ・噴水） | 中: `cracked`、強: `crushed`（頭が弾ける） | `wounded`、強: `cracked`/`crushed` | 近いほど `crushed` |
| 腕 | 肘から先に当たれば `cut_lower`、上なら `cut_upper` | `broken`（ぶら下がる） | `wounded` | `cut_upper` |
| 脚 | `cut_lower` / `cut_upper`（→ 這う） | `broken`（片脚を引きずる、両方で倒れて這う） | `wounded` | `cut_upper` |
| 胴 | `slashed`→`gutted`、重い横薙ぎで `halved` | 肋骨が折れて吹き飛ぶ（`down`） | `wounded` 相当（`slashed`） | `halved` |

* ゴアレベル `G`（0〜100）: 切断の起きやすさ・血の量・gib の数・血だまりの寿命を比例させる。
  `G = 0` は切断なし・血ほぼなし。**`G = 100` が既定で最大**（初撃でも強い一撃なら落ちる、内臓がこぼれる、
  gib が跳ねる、血の噴水が数秒続く、近くで仕留めると画面に血）。
* 部位ごとに「部位体力」（最大体力に対する割合）を持ち、累積で閾値を超えるか、強い一撃の確率判定で状態が進む。
* 状態の効果: 腕が無い → 掴み・殴り不可（両腕無しは噛みつきのみ）、片脚 `broken` → 鈍足、
  脚が無い・両脚 `broken` → `crawl`（這う。当たり箱が低くなる）、胴 `halved` → 上半身だけで這う、
  頭 `severed`/`crushed` → 即死、`cracked` → 大ダメージ、`jawless` → 噛みつき不可。

---

## 5. ちぎれた部位 `nr:gib` と「物理」

* プロパティ: `nr:ztype` int 0..63（63 = 汎用の肉片）、`nr:part` int 0..15、`nr:spin` int 0..7、
  `nr:rest` int 0..3、`nr:bleed` int 0..1、`nr:side` int 0..1。
* `nr:part`: 0 頭 / 1 下顎 / 2 右腕まるごと / 3 左腕まるごと / 4 右前腕＋手 / 5 左前腕＋手 /
  6 右脚まるごと / 7 左脚まるごと / 8 右脛＋足 / 9 左脛＋足 / 10 下半身（骨盤＋両脚） /
  11 腸 / 12 脳・頭蓋の欠片 / 13 肉片 / 14 骨・肋骨 / 15 目玉・臓器。
* ジオメトリ: 種類ごとに `geometry.nr.gib.<key>`（ボーン `p_head` `p_jaw` `p_arm_r` `p_arm_l`
  `p_forearm_r` `p_forearm_l` `p_leg_r` `p_leg_l` `p_shin_r` `p_shin_l` `p_lower`）を、
  **ゾンビ本体のモデルから部分木を抜き出して自動生成**する（同じ UV・同じテクスチャ。切り口に断面キューブを足す）。
  各ボーンは部位の重心が原点に来るように置く。汎用の `geometry.nr.gib.generic`（`p_guts` `p_brain`
  `p_chunk` `p_bone` `p_eye`）は共通の内臓テクスチャ。
* `controller.render.nr.gib`: ジオメトリとテクスチャを `nr:ztype`（と `nr:part > 10` なら汎用）の配列で選び、
  `part_visibility` で `nr:part` の 1 本だけ表示。
* 「物理」: `minecraft:physics` と小さな当たり箱で、ブロックに当たって転がる・落ちる。
  スクリプトが `applyImpulse` で打たれた向きに飛ばし、着地のたびに反発係数で跳ね返し、摩擦で止める。
  空中ではクライアントのアニメーションが `nr:spin` の軸と速さで回し、止まると `nr:rest` の寝姿に落ち着く。
  動いている間は血の尾を引き、止まった所に血だまり。プレイヤーが殴ると蹴り飛ばせる。
  数（既定 48）と寿命（既定 60 秒）に上限。
* 死体（`nr:state = dead` のゾンビ）も打たれた向きに吹き飛び（屋上から落ちる）、死体でもさらに切断できる。
  高所から落ちたゾンビは着地の衝撃で脚が折れる・潰れる。

---

## 6. ゾンビの種類（`nr_spec_zombies.py`）

50 体。区分ごとの数: **一般感染者 24 / 俊敏型 8 / 特殊感染者 11 / 夜の捕食者 4 / ボス 3**。
ダイイングライト 2 の敵（バイター・ヴァイラル・ハウラー・スピッター・グーン・デモリッシャー・
バンシー・ボラタイル・リヴナント・チャージャー・スーサイダー 等）に**着想を得たオリジナル**で、名前は変える。
子どもの感染者は作らない。

各エントリの形（`dict`）:

```python
dict(
  key="office_worker",            # ID: nr:z_office_worker
  ja="感染したサラリーマン", en="Infected Office Worker",
  cls="common",                   # common / viral / special / night / boss
  height_cm=176, heads=7.2, bulk=1.0, limb=1.0, hunch=14, arm_len=1.05,  # 骨格（rig へ）
  decay=2,                        # 腐敗の段階 0..4（肌色・露出・欠損）
  skin="pale",                    # 肌の系統（nr_paint の SKINS のキー）
  outfit=[...],                   # 服・装備の部品（nr_kit の関数名と引数）
  mutations=[...],                # 変異（腫瘍・骨の棘・菌糸・露出した肋骨…）
  eyes="clouded",                 # EYES_VOCAB の 10 種（clouded / bloodshot / milky / glowing_* 6 色 / none）
  hp=24, speed=0.22, damage=4, attack="swipe",   # 体力・速さ・攻撃力・攻撃の型
  locomotion="shamble",           # shamble / limp / stagger / run / sprint / crawl / brute / stalk / leap
  resist=dict(slash=1.0, blunt=1.0, pierce=1.0, blast=1.0, fire=1.0, shock=1.0, toxic=1.0, uv=0.0),
  gore=dict(armored=[], no_sever=[], explode=False, ...),       # 例外（装甲の部位、切れない部位、死ぬと爆発）
  abilities=[...],                # scripts/zombies/abilities.js のキー
  spawn=dict(time="day"/"night"/"any", weight=10, group=(2, 5), where="city"/"overworld"/"structure"),
  loot=[("nr:scrap", 0, 2, 0.6), ...],
  voice="groan_male",             # 効果音のキー（nr.z.<voice>.<idle|alert|attack|hurt|death>）
  bestiary_ja="…", bestiary_en="…", weakness_ja="…", weakness_en="…",
)
```

---

## 7. プレイヤー

* **パルクール**（スクリプト `scripts/player/parkour.js`。素手か武器を持っている間ずっと）:
  壁登り（壁に向かってジャンプ長押し）、縁つかまり → よじ登り、走りながらの乗り越え（1〜2 段の障害物）、
  壁走り（壁沿いに空中で走る → 壁蹴り）、スライディング（ダッシュ中にスニーク）、
  受け身ロール（着地直前にスニークで落下ダメージを減らす）、ドロップキック（空中でスニーク＋攻撃）、
  グラップリングフック（アイテム）、パラグライダー（アイテム）。プレイヤーには `applyImpulse` が効かないので
  `applyKnockback` と効果（ジャンプ力・低速落下）で動かす。動きに合わせて `playAnimation("animation.nr.p.<名前>")`。
* **スタミナ**: 走り・パルクール・攻撃で減り、休むと戻る。
* **免疫（夜の感染）**: 暗い所（夜・屋内の暗がり）で減り続け、0 になると体力が削れる。
  UV ライトの近く・`nr:immunity_booster`・`nr:uv_flashlight` で回復。HUD に残り時間。
* **追跡（チェイス）**: 夜にボラタイルなどに見つかると追跡レベル 1〜4。UV で振り切る。
* **HUD**: アクションバー＋タイトルに、独自グリフ（RP `font/glyph_XX.png`）で体力・スタミナ・免疫・
  追跡レベル・武器の耐久・ゴアのコンボ（「HEADSHOT」「DISMEMBER」「DECAPITATED」）。

## 8. 武器・アイテム・罠・街

* 武器（`nr_spec_catalog.WEAPONS`）: 近接（片手刃・両手刃・片手打撃・両手打撃・槍）と飛び道具
  （弓・クロスボウ・投げナイフ・火炎瓶・パイプ爆弾・爆竹・銃）。各武器は `dtype`・`weight`・ダメージ・
  耐久・攻撃速度・スタミナ消費・改造（`fire` / `shock` / `bleed` / `toxic` / `uv`）を持つ。
  改造は ItemStack の動的プロパティに保存し、説明文（lore）に出す。銃はヒットスキャン（スクリプトのレイ）。
* 罠・ブロック: 電気トラップ・スパイク・トラバサミ・爆発する燃料缶・ガス管・車のアラーム（誘い）・
  UV ライト（夜の安全地帯）・バリケード・街灯・瓦礫・ゴミ袋・土嚢など。
* 小道具エンティティ: 車の残骸（セダン・パトカー・救急車・バス・トラック）、コンテナ、ゴミ収集箱、
  焼けた車 ほか。見た目は細かい 3D モデル、当たりはバリアブロックで作る。
* 街: Python が `.mcstructure`（建物モジュール: アパート・商店・ガソリンスタンド・病院・警察署・教会の塔・
  倉庫・立体駐車場・屋上パルクールの足場・UV の隠れ家 など）を書き出し、`/scriptevent nr:city` で
  スクリプトが街区を組み立てる（道路・歩道・建物・車・バリケード・ゾンビの配置）。

## 9. エフェクト・音・UI

* パーティクルは**白で描いて色をスクリプト／Molang から渡す**（HyperDim と同じ）か、血のように固有色のものは固有色で。
  血しぶき（方向付きの噴き出し）、血霧、重力と衝突のある血滴（着地で血痕を作る）、地面と壁の血痕、
  首・肩の断面からの拍動する噴水、頭が弾ける爆発、肉片・骨片・脳片、腸、焼ける煙と火、感電の火花、
  毒ガス、酸の唾、爆発、UV の光、着地の土煙、スピード線、装甲に当たる火花。
* 1 tick に出すパーティクル数・同時に存在する gib と死体の数に上限（設定で変えられる）。
* 効果音は合成（素材音源なし）: 肉を切る・叩き潰す・骨が折れる・ちぎれる・血が噴く・頭が弾ける・
  内臓が落ちる、ゾンビの声（種類ごとの唸り・叫び・遠吠え・金切り声）、足音・パルクール、武器、銃、爆発、
  罠、UV の唸り、UI、夜の追跡の警告音、心音（免疫低下）。
* フォーム（`@minecraft/server-ui`）: 生存者の端末（設定・図鑑 50 体・クラフト・スキル・操作説明）。
  **設定にゴアレベル 0〜100 のスライダー（既定 100）**。

## 10. 検証（ビルドに含める）

1. `test_nr.py`: Node で `@minecraft/server` を動くスタブに差し替え、偽プレイヤー・偽ゾンビで
   部位判定・全ゴア結果・gib の生成・死亡処理・全武器の攻撃・パルクールの各動作・罠・街の生成を実行。
   例外ゼロ、参照するパーティクル・音・アニメ・エンティティ・プロパティ値が RP/BP に実在すること。
2. `check_nr_types.py`: 公式 d.ts で全 JS を型検査。
3. `validate_nr.py`: JSON の構文、参照切れ（ジオメトリ・テクスチャ・アニメ・コントローラ・
   レンダーコントローラ・パーティクル・音・言語キー）、UV がテクスチャ内か、Molang の括弧、
   プロパティ値がエンティティ定義の enum にあるか、ボーン名が §3 の通りか、上限（キューブ数・テクスチャ寸法・
   パック容量）。
4. 目視用のプレビュー画像（`HD_PREVIEW` と同じ流儀で `NR_PREVIEW=1`）を `build_preview/` に描く。

## 11. 性能の目安

| もの | 上限 |
|---|---|
| ゾンビ 1 体のキューブ | 一般 ≤ 450、特殊 ≤ 650、ボス ≤ 1100 |
| ゾンビのテクスチャ | 512×512（ボスは 1024×1024 まで）。PNG はパレット化してよい（アルファは保つ） |
| 全テクスチャ（展開後 Σw·h·4） | ≤ 150 MiB（Mojang の検証の予算。`validate_nr.py` が止める） |
| 武器 | ≤ 180 キューブ、≤ 512×512 |
| 小道具 | ≤ 700 キューブ、≤ 1024×1024 |
| パック全体 | ≤ 80 MB |
| 1 tick のパーティクル | ≤ 300（スクリプトの予算で制御） |

---

## 12. スクリプトとデータの契約

### 演出 ID の登録簿

`tools/nightrunner/nr_registry.py` が、パーティクル・効果音・プレイヤーのモーション・ゾンビの一発アニメの
ID を固定する。作る側は全部作る、使う側（手書き JS）は載っている ID だけ使う。ゾンビの声
`nr.z.<voice>.<idle|alert|attack|hurt|death>`、特殊能力の音 `nr.ab.<ability>` は spec の語彙（`VOICE_VOCAB` /
`ABILITY_VOCAB`）から、ゾンビの種類ごとのアニメ（`animation.nr.z.ab_<ability>_<phase>` と `ab_<ability>`、
`atk_<attack>`、`walk_/run_<locomotion>`）は spec の `zombie_animations(z)` から機械的に決まる
（登録簿の `all_sound_ids(spec)` / `all_zombie_anim_names(spec)` / `all_zombie_oneshots(spec)` が並べる）。
spec（武器の音・改造・罠・アイテムのモーション）が参照する演出 ID は全部この登録簿にある（`nr_spec.py` が検査）。

### `scripts/data/*.js`（生成物。手書き JS はここから import する）

| ファイル | 書く生成器 | export |
|---|---|---|
| `zombies.js` | `gen_nr_data_js` | `ZOMBIES`（spec の全フィールド + `id` `ztype`）、`ZTYPE`（key→番号）、`ABILITIES`、`ATTACKS`、`LOCOMOTIONS`、`VOICES`、`GORE_KEYS` |
| `zombie_shapes.js` | `gen_nr_zombies` | `SHAPES[key] = {height, width, stand: {part: [box...]}, lie: {...}, locators: {name: [r,u,f]}}` |
| `weapons.js` / `items.js` / `mods.js` / `traps.js` / `blocks.js` / `props.js` / `skills.js` / `crafting.js` | `gen_nr_data_js` | spec の同名の表（`WEAPONS` は ID→定義の辞書 `WEAPON_BY_ID` も） |
| `settings.js` | `gen_nr_data_js` | `SETTINGS_DEFAULTS`、`PARKOUR_TUNING` |
| `fx.js` | `gen_nr_data_js` | 登録簿の `PARTICLES`（名前の配列）、`SOUNDS`、`PLAYER_ANIMS`、`ZOMBIE_ONESHOTS` |
| `structures.js` | `gen_nr_structures` | `STRUCTURES[key] = {id, size:[x,y,z], markers: [{kind, pos:[x,y,z], dir}], ...}` |
| `glyphs.js` | `gen_nr_ui` | `GLYPH`（名前→1 文字）、`BAR(名前, 割合, 幅)` に使う部品の表 |

**当たり箱の座標**: 箱は `{c: [r, u, f], h: [hr, hu, hf]}`（中心と半分の大きさ、単位ブロック）。軸は
ゾンビの足元を原点に **r = ゾンビ自身の右、u = 上、f = ゾンビが向いている前**。スクリプトは
`getRotation().y`（yaw）から前と右を出して世界座標へ直す。`lie` は仰向けに寝た姿勢（頭が後ろ = -f 側）。

### BP のイベント（全ゾンビ共通。`gen_nr_entities` が作り、スクリプトは `triggerEvent` で呼ぶ）

| イベント | 中身 |
|---|---|
| `nr:on_death` | `nr:dead` を足す（AI・移動・攻撃・ターゲット取りを外し、`minecraft:physics`・押せる体・低い当たり箱だけ残す。`damage_sensor` で全ダメージ無効） |
| `nr:to_crawl` | `nr:crawler` を足す（当たり箱を低く、速さを種類の 35%、乗り越え不可） |
| `nr:root_start` / `nr:root_end` | `nr:rooted`（その場で動かない。叫び・溜め・掴み中） |
| `nr:enrage` / `nr:calm` | `nr:enraged`（速さ ×1.35、追跡範囲を広げる。夜の追跡・ボスの段階） |
| `nr:despawn` | 即座に消える（`minecraft:instant_despawn`） |

`nr:gib`・`nr:proj_*`・`nr:prop_*` にも `nr:despawn` を持たせる。

### 手書きスクリプトの構成（`packs/nightrunner_BP/scripts/`）

```
main.js                 入口。各モジュールを import して登録するだけ
core/   util.js  settings.js（ワールドの動的プロパティ nr:settings）  budget.js（1 tick のパーティクル予算）
        fx.js（パーティクル・音・カメラの薄い包み）  hp.js（本当の体力）  bus.js（モジュール間の通知）
gore/   hitloc.js（部位判定） gore.js（結果の決定と適用） gibs.js（gib の生成と跳ね返り）
        blood.js（血の演出） death.js（死亡・死体・ルート）
zombies/ ai.js（壁登り・飛びかかり・掴み） abilities.js（ABILITY_VOCAB の全実装） director.js（昼夜の出現・群れ）
        chase.js（夜の追跡） noise.js（音で寄ってくる） bosses.js
player/ parkour.js stamina.js immunity.js sense.js hud.js skills.js
combat/ melee.js ranged.js throwables.js mods.js durability.js finishers.js
world/  traps.js uv.js props.js city.js loot.js commands.js（/scriptevent nr:*）
ui/     terminal.js（設定・図鑑・クラフト・スキル・説明） welcome.js
```

モジュール間の呼び出しは、`gore/gore.js` の `applyHit(zombie, hit)`（`hit = {attacker, part?, point?, dir, dtype,
weight, damage, power, source: "melee"|"projectile"|"hitscan"|"blast"|"trap"|"fire"|"shock"|"toxic"|"fall", weapon?, mods?}`）
を中心にする。**ゾンビへのダメージは必ず `applyHit` を通す**（体力・部位・ゴア・死亡・演出が一か所で決まる）。

---

## 13. 描画の規則（`reference/rendering.md` §11 のチェックリストが正）

* **ジオメトリはすべて `format_version: "1.16.0"`**（`binding` は 1.16.0 から。`mcmodel.Model.write` は 1.12.0 固定
  なので、NR の書き出しは `nr_common.write_geometry()` を通す）。回転するキューブには必ず pivot。
* **面の名前と向き（ファイル座標）**: Bedrock は描画のとき X を反転する。ファイル座標では
  **`east` が min-X の面（体の右側。u は -Z へ）、`west` が max-X の面（u は +Z へ）**、up/down/north/south は従来どおり。
  `tools/preview.py` / `hd_scene.py` は east を +X に置いているので、NR の確認画像は `nr_preview.py`（正しい対応）で描く。
  `nr_paint` の 3D ノイズと左右非対称の模様もこの対応で塗る。
* ゾンビの向き: 顔は north（-Z）面、体の右（`arm_r`）は -X。当たり箱の `r/u/f` は `r = -x, u = y, f = -z`（ブロック単位）。
* 発光: `entity_emissive_alpha`。発光画素の α は小さい値（`nr_paint.EMISSIVE_ALPHA`）、それ以外は 255、空きは (0,0,0,0)。
  `entity_alphatest_one_sided` は存在しない。
* `playAnimation` は一発ものだけ（必ず `controller`・`stopExpression`・`nextState` を渡す。加算・最初と最後のキーが 0）。
  ゾンビの常時の見た目（切断・這う・死体・燃焼・感電）はプロパティ駆動の自前コントローラ。

