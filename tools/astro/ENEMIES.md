# アストロ・ナノギア 侵略者（ENEMIES.md）

宇宙からの侵略者 3 種（ヴォイド・ドローン／ヴォイド・センチネル／虚星王ネメシス）と、練習台のホログラム標的、
ドローンのボルト、ダメージ数字の名札。

| 担当ファイル | 内容 |
|---|---|
| `tools/astro/gen_astro_entities.py` | モデル・テクスチャ・BP/RP のエンティティ・アニメ・コントローラ・描画・ドロップ・スポーン（全部生成） |
| `packs/astro_BP/scripts/invaders.js` | 攻撃パターン・予告・ボスの召喚と撃破演出・ホログラム標的の DPS 表示（手書き） |
| `tools/astro/ENEMIES.md` | この文書 |

```
python3 tools/astro/gen_astro_entities.py             生成 + 自前の検査（ボーン・UV・コントローラ・Molang・参照）
python3 tools/astro/gen_astro_entities.py --preview   + build_preview/astro/enemy_<id>.png（4〜7 方向・攻撃の姿勢）
python3 tools/astro/gen_astro_entities.py --test      + invaders.js の Node スモークテスト（下記）
python3 tools/astro/gen_astro_entities.py --only=drone,boss …  絞り込み（名前の一部で可）
```
数値の出所: 体力は `astro_data.ENEMIES`、それ以外の数値は `invaders.js` 冒頭の `CFG`。

---

## 1. 一覧

| ID | 名前 | HP | 当たり判定 (幅×高) | 出現 | ドロップ | モデル |
|---|---|---|---|---|---|---|
| `astro:void_drone` | ヴォイド・ドローン | 20 | 0.85×0.95 | 夜の地上（重み 12・1〜2 体・地表の密度上限 4）／ネメシスの召喚 | ナノマシン・セル 1〜2（＋幸運） / XP 6 | 139 キューブ・512² |
| `astro:void_sentinel` | ヴォイド・センチネル | 44 | 1.3×2.6 | 夜の地上（重み 5・1 体・上限 2） | セル 2〜3（＋幸運）、35% で鉄インゴット 1〜2 / XP 10 | 202 キューブ・1024² |
| `astro:nemesis` | 虚星王 ネメシス | 480 | 2.4×3.8 | ヴォイド・シグナル（夜の地上）／`/scriptevent astro:boss` | 太陽の欠片 ×2、セル 6〜10、ダイヤ 1〜3 / XP 120 | 278 キューブ・1024² |
| `astro:hologram_target` | ホログラム標的 | 200（毎回満タン） | 0.8×2.2 | スポーンエッグ／`/scriptevent astro:target` | なし | 120 キューブ・512² |
| `astro:void_bolt` | （ドローンの弾） | — | 0.3 | ドローンが撃つ | — | 4 キューブ |
| `astro:dmg_text` | （ダメージ数字） | — | — | combat.js が出す（2 秒で消える） | — | 空 |

スポーン条件（両方）: `spawns_on_surface`・明るさ 0〜7（天候補正あり）・難易度 easy〜hard・
バイオームタグ `overworld`（`mushroom_island` を除く）・個体数の枠は `monster`。
デスポーン: ドローンとセンチネルは距離（48〜96 m）で消える。ネメシスとホログラム標的は `persistent`。

家族（type_family）: 侵略者は `astro_invader` + `astro_drone` / `astro_sentinel` / `astro_boss` + `monster` `mob`。
標的は `astro_target` `mob`（monster ではないのでゴーレムは襲わない）。ボルトは `astro_bolt`、数字は `astro_text`。

共通: 侵略者どうし（ボルトの撃ち手を含む）は傷つけ合わない（damage_sensor の `other`/`damager` が `astro_invader`）。
ドローン・ボスは落下・壁衝突のダメージ無し、ボスは窒息・溶岩・炎も無効・ノックバック無効・ボスバー（空が暗くなる）。
センチネルの落下ダメージは 40%。

## 2. 行動

すべての危険な攻撃は **0.5 秒以上前に予告** する（地面の赤い警告 `astro:warning`、赤い点線 `astro:line_n`、
溜めの光 `astro:converge`/`glow`、溜めの音）。ブロックは一切壊さない（爆発はパーティクルと自前のダメージだけ）。

### ヴォイド・ドローン「ヴォイド・ドローン」
* 紫黒の装甲球。正面にマゼンタの単眼、X 字の 4 枚のヒレ（羽ばたく）、下の噴射炎、眼の下の双連装の砲口。
* **位置取り**（スクリプト）: 22 m 以内の最寄りのプレイヤーを狙い、その周り **6.5〜9.5 m・高さ +3 m** の輪の上を
  ゆっくり回る（applyImpulse の速度制御、最大 0.3 m/tick）。近づかれると下がる。地面の 1.6 m より下には降りない。
  交戦中は BP のイベント `astro:engage` で徘徊（random_hover）を止め、見失うと `astro:disengage` で戻す。
  眼の向きはバニラの look_at_target と、アニメの `q.target_x/y_rotation`。
* **ボルト**: 約 3 秒（60 ± 14 tick）ごと。**0.6 秒の溜め**（眼が膨らんで点滅・ヒレが開く・赤い照準線が胸へ伸びる・
  溜めの音）→ 発射（`astro.drone_laser`、反動のアニメ）。`astro:void_bolt` を `minecraft:projectile` の
  `shoot()` で秒速 18 m 撃つ（4 ダメージ）。`shoot` が無い版では同じ弾をスクリプトで飛ばして当てる（同じダメージ）。
  軌跡はマゼンタの光の点、着弾で火花。射線から横へ動けば避けられる。
* 約 0.9 秒ごとにうなり（`astro.drone_hum`、14 m 以内に人がいる時）。撃破で小爆発。

### ヴォイド・センチネル「ヴォイド・センチネル」
* 全高 2.6 ブロックの逆関節（鳥脚）の二足機兵。猫背の胴・巨大な肩と角・横一文字の単眼スリット・胸の虚空炉・前腕の刃。
* 近接はバニラ（`melee_attack`、6 ダメージ、刃を振るアニメ = `v.attack_time`）。歩行は歩いた距離で位相を取る歩行サイクル、
  足音（`astro.sentinel_step`）と土煙。
* **地を走る衝撃波**: 5 m 以内（高低差 3 m 以内）にプレイヤーがいて接地していると約 6 秒（120 ± 24 tick）ごと。
  **0.8 秒の振りかぶり**（両腕を頭上へ・足が止まる・足元に半径 6.5 m の警告・溜めの音）→ 叩きつけ
  （`astro.sentinel_slam`・画面の揺れ）→ 輪が 0.6 m/tick で半径 6.5 m まで広がる。輪が通る時に **地面にいる** と
  6 ダメージ＋外へ吹き飛ばし。**跳べば避けられる**（足が地面より 0.9 m 上）。

### 虚星王 ネメシス「虚星王 ネメシス」
* 浮遊する黒い星の機械（約 4 ブロック）。割れ目から菫の光が漏れる装甲殻の球、正面の特異点の単眼（菫の虹彩・黒い瞳・
  回る降着円盤・V 字の瞼）、背後に扇状の 9 本の黒い棘の光冠、傾いて回る二重の光輪、巡る 6 枚の装甲片、
  下に垂れる 5 本の触手、眼の左右の大顎。
* **位置取り**: 48 m 以内の最寄りのプレイヤーから **9 m・高さ +2.2 m**（地面から 1.4 m 以上）に浮かび、常にそちらを向く。
  技の最中は動きが鈍る（近づいて殴る隙）。突進の後 1.2 秒は特に遅い。
* **技の順番**: 5 つの技をシャッフルした袋から順に使う（同じ技は続かない。使えない技は後回し）。
  間隔は第一形態 2.3〜3.3 秒、第二形態 1.3〜1.9 秒。

| 技 | 予告 | 中身 | ダメージ（第一/第二） |
|---|---|---|---|
| 光線の薙ぎ払い（mode 1→2） | 1.0 秒: 眼に光が集まる・縦の技術陣・**標的を横切る地面の赤い点線と 5 つの警告** | 1.2 秒かけて眼からの光線が点線の上を端から端へ走る。第二形態は逆向きの 2 本目が交差 | 7 / 8（1 本につき 1 回） |
| ドローン召喚（mode 3） | 1.2 秒: 周りに虚空の門（裂け目・吸い込む光・輪） | ドローン 2（第二形態 3）機。子機はタグ `astro_minion`・`astro_m_<ボスID>`。**最大 6 機** | — |
| 隕石雨（mode 4） | 各隕石の **1.3 秒前** から着弾点に半径 2.6 m の警告、0.7 秒前から空を落ちる火球、音（着弾 1.15 秒目に合わせる） | 5（第二形態 8）個を 0.25（0.2）秒おき。1 個目は標的の足元、残りは近くのプレイヤーの周り 6 m | 8 / 9 ＋吹き飛ばし |
| 黒孔（mode 5） | 1.0 秒: 吸い込む光・裂け目・地面の警告・重力の音 | 標的と自分の間に重力の井戸。3（3.5）秒間、11 m 以内を中心へ引き寄せ（近いほど強い）、中心 2.2 m では 0.5 秒ごとに 3。最後に **0.6 秒の予告**（半径 4.5 m の警告）の後に弾ける | 弾け 7 / 8 |
| 突進（mode 1→6） | 0.8 秒: 進路の地面に赤い点線・終点に警告・眼が赤く光り後ろへ溜める | 一直線に約 21 m/s で最大 18 m 突っ込む。壁に当たると衝撃で止まる。第二形態は二連 | 10 / 11 ＋強い吹き飛ばし |

* **第二形態**（体力 50% 以下）: 咆哮（mode 7・1.5 秒、タイトル「虚星王 覚醒」）。咆哮の 0.5 秒目に 8 m 以内を押し返す（3）。
  プロパティ `astro:phase` = 2 で光輪・装甲片・触手が 1.8 倍速、全身がマゼンタに脈打つ。火の粉が漂う。
* **撃破**: 子機は虚空へ撤退して消え、残った隕石・黒孔は消える。2.6 秒の連鎖爆発（9 回）→ 大爆発（レンズ・輪・衝撃波・
  黒孔の崩壊・星の粒）→ 80 m 以内にタイトル「虚星王 撃破」。ドロップはルートテーブル（太陽の欠片 2）。
* **降臨（ヴォイド・シグナル）**: `summonNemesis(player)` の決まり
  1. オーバーワールドだけ（ネザー・エンドでは「地上の空にしか届かない」）
  2. 夜だけ（`world.getTimeOfDay()` が 13000〜23000。昼は「夜を待て」）
  3. 頭上 14 ブロックが空いていること（「空の見える場所で使え」）
  4. 160 m 以内にネメシスがいないこと／降臨の最中でないこと
  5. 正面 6〜9 m に高さ 4.5 ブロックの空間があること
  成功するとシグナルを 1 つ消費（クリエイティブでは減らない）し、3.3 秒の降臨演出（`astro.nemesis_spawn`・地面の陣・
  空からの稲妻・吸い込む光・黒孔）→ 出現して咆哮。`{force: true}` は決まりを無視（`/scriptevent astro:boss` 用、消費しない）。

### ホログラム標的「ホログラム標的」
* 六角の投影台（不透明）と、その上に浮かぶシアンの人型ワイヤーフレーム（加算合成）。胸に赤い照準、体を上下する走査の輪、
  殴られると・5 秒ごとに少し乱れる。
* 倒れない: 殴られるたびに体力を 200 に戻し、頭上に `ホログラム標的 / 5秒合計 X | DPS Y` を出す（10 tick ごとに古い記録を捨てる）。
  一撃で 200 を超えて倒れた時は 0.5 秒後に同じ場所に出し直す（`/kill` 等の自滅・奈落は除く）。
* 家族に `astro_target`（combat.js の HOSTILE_TYPES と同じ扱いで技の自動照準に入る）。

## 3. 技術の約束（モデル・アニメとスクリプト）

| プロパティ（BP、client_sync） | 値 |
|---|---|
| `astro:mode`（ドローン 0..3） | 0 平常 / 1 溜め / 2 発射 |
| `astro:mode`（センチネル 0..3） | 0 平常 / 1 振りかぶり / 2 叩きつけ |
| `astro:mode`（ネメシス 0..7） | 0 平常 / 1 溜め / 2 光線 / 3 召喚 / 4 隕石 / 5 黒孔 / 6 突進 / 7 咆哮 |
| `astro:phase`（ネメシス 1..2） | 形態 |

* イベント: ドローン `astro:engage` / `astro:disengage`（徘徊の on/off）、ボルト・数字 `astro:despawn`。
* アニメ: `animation.astro.<id>.<名前>`（`astro_entities.animation.json`）。コントローラ `controller.animation.astro.<id>`
  は `v.mode` で状態を切り替え、`!q.is_alive` で死亡アニメへ。センチネルの近接は `v.attack_time > 0`。
* 描画: `controller.render.astro.invader` — 体は `entity_emissive_alpha_one_sided`、`fx_*` ボーン（ヒレ・輪・棘・触手・大顎・
  眼の光）は `entity_emissive_alpha`（両面）。被弾は白っぽいマゼンタのフラッシュ、溜め・咆哮・第二形態は `v.overlay` の脈動。
  `controller.render.astro.hologram` — 投影台は one_sided、`holo*` ボーンは `entity_beam_additive`（加算・自己発光。
  テクスチャのアルファは 255 のまま明るさ = 不透明さ）。
* テクスチャ: `InvaderPainter`（`astro_paint.AstroPainter` の子。虹彩・特異点・ホログラム線・鱗の装甲を追加）。発光は
  entity_emissive_alpha の規約（EMI=12 ほぼ全発光 / SOFT=150 半発光）。
* 重なる箱（八角・面取り）の同じ平面の面は 0.02〜0.04 ずつ引っ込めてある（実機のちらつき防止）。
* 上限: 危険物（光線・隕石・衝撃波・黒孔）同時 18、ボルト 24、子機 6／ボス、演出は 1 tick 70（さらに fx.js の全体予算の内側）。
* スクリプトは `@minecraft/server` 1.13.0 の安定版 API だけ（`applyImpulse`・`setProperty`・`triggerEvent`・`setRotation`・
  `applyKnockback`・`applyDamage`・`getEntities({families,tags})`・`getTimeOfDay`）。版差は try で吸収。
  演出は `import * as FX from "./fx.js"` の `FX.P / FX.sound / FX.shake / FX.announce` があれば使い（全体予算と演出量の設定に乗る）、
  無ければ自前で出す（名前空間 import なので fx.js の export が変わってもモジュールの読み込みは壊れない）。

## 4. 配線（まとめ役へ）

main.js は既に `itemUse(astro:void_signal) → EN.useVoidSignal`、`entityHurt → EN.onEntityHurt`、`entityDie → EN.onEntityDie`、
`entitySpawn(astro:*) → EN.onEntitySpawn`、毎 tick `EN.tickEnemies(t)`、`/scriptevent astro:target|boss → EN.summonTarget|summonBoss`
を呼んでいる。**enemies.js の中身を invaders.js へ委ねるだけ**でよい:

```js
// enemies.js
import {
  INVADER, isInvader, tickInvaders, onInvaderHurt, onInvaderDie, onInvaderSpawn, summonNemesis, summonHologram,
} from "./invaders.js";
export const TYPES = { drone: INVADER.drone, sentinel: INVADER.sentinel, boss: INVADER.boss, target: INVADER.target, bolt: INVADER.bolt };
export function isEnemy(e) { return isInvader(e); }
export function initEnemies() { }
export function tickEnemies(tick) { tickInvaders(tick); }                      // 毎 tick（2 tick ごとでも可）
export function onEntitySpawn(e) { onInvaderSpawn(e); }
export function onEntityHurt(e, damage, source) { return onInvaderHurt(e, damage, source); }  // 常に false（数字は出す）
export function onEntityDie(e, source) { onInvaderDie(e, source); }
export function summonTarget(p) { return summonHologram(p); }
export function summonBoss(p) { return summonNemesis(p, { force: true }); }  // チート用: 昼でも・消費なし
export function useVoidSignal(p) { return summonNemesis(p); }               // 夜の地上だけ・成功で 1 つ消費
```
* ホログラム標的の DPS 表示は invaders.js も持っている。enemies.js の `targetHurt` を残すなら
  `onInvaderHurt(e, damage, source, { hologram: false })` にして二重に書かないこと。
* main.js を通さずに単独で動かすなら `installInvaders()`（tick・itemUse・entityHurt・entityDie・entitySpawn を自分で購読。
  `{ itemUse: false }` 等で個別に外せる）。main.js と両方は使わない。
* 無敵時間などでダメージを止めたい時は `setInvaderDamageFilter((player, amount, source, cause) => false | 数値 | undefined)`。
  （バリア・ジャスト回避は main.js の entityHurt で回復しているので、そのままで効く。）

## 5. 確かめたこと（実機なし）

* **モデル**: `--preview` で正面・斜め・横・背面と攻撃の姿勢（ドローンの溜めと発射、センチネルの歩行・振りかぶり・叩きつけ・
  斬撃、ネメシスの咆哮と突進）を hd_scene と同じ回転規則・X の鏡映で描いて目で確認（`build_preview/astro/enemy_<id>.png`）。
  プレビューはアニメの Molang（三角関数・三項演算子）を小さな評価器で評価して描く。
* **自前の検査**（生成のたび）: JSON・UV がテクスチャ内・テクスチャの大きさ・アニメのボーンが実在・コントローラの状態と遷移
  （初期状態・未知の遷移先・到達できない状態）・Molang の括弧・`q.property` が BP で宣言済み・描画の `v.*` が pre_animation で
  設定済み・`Material.*` がクライアントにある・ルートテーブルのアイテムが実在・イベントのグループが実在・スポーンルールの対象が実在。
* **`--test`**: @minecraft/server を動くスタブ（物理・投射物・クエリ・プロパティ・タグ・時刻）に差し替え、プレイヤー 1 人と
  ドローン・センチネル・ネメシスを 1200 tick 戦わせる（毎 tick 呼び出し＋本物の投射物／2 tick ごと＋スクリプトのボルト）。
  例外が無いこと、3 種すべてからダメージを受けること、ネメシスが mode 1〜7 を全部使い第二形態に入ること、子機が 6 以下、
  撃破で子機が撤退しタイトルが出ること、シグナルの決まり（昼・屋根の下・ネザー・二重召喚・消費・force）、
  ホログラム標的の DPS・回復・リセット・復活、使ったパーティクル・効果音がパックに実在することを確かめる。

## 6. 実機で見てほしいこと（未確認）

* `entity_beam_additive`（ホログラム）と `entity_emissive_alpha_one_sided` の見え方。ホログラムが暗すぎ・明るすぎなら
  `holo_styles()` の `k` を調整。
* ドローンの applyImpulse による位置取りと hover ナビの干渉（交戦中は random_hover を外している）。
* ネメシスの `setRotation` と体の向き（look アニメで `q.target_y_rotation` も足している）。
* `minecraft:projectile` の `shoot()` が無い/効かない場合のスクリプトのボルト（teleport で動かす）の見え方。
* ボスの死亡時のバニラの横倒れ（死亡アニメは沈みながら光輪が広がる）。
