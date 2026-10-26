# コンテンツ JSON の検証済み書式 — 1.21.120

NIGHT RUNNER の **BP / RP の JSON を書く生成器**（`gen_nr_entities.py`・`gen_nr_items.py`・`gen_nr_weapons.py`・
`gen_nr_blocks.py`・`gen_nr_structures.py`・`gen_nr_packs.py` ほか）のための書式表。対象は
**min_engine_version `[1, 21, 120]`**。スクリプト側の型は `reference/script_api.md`、見た目（ジオメトリ・
レンダーコントローラ・マテリアル）は `reference/rendering.md` を見ること。この文書は「JSON に何を書けば
1.21.120 で通るか」だけを扱う。

* **根拠は実物の引用**。下の記号で出典を示す（全部ローカルに写しがある。§0）。
* 版の違うことを書いた資料（1.26 系の wiki・2025 年 11 月以降の MS Learn）は、**1.21.120 の実物
  （bedrock-samples `v1.21.120.4` の vanilla ファイル・JSON スキーマ・ドキュメント）と食い違うときは実物を優先**した。
* 実機でしか確かめられないことは **UNVERIFIED** と書き、推奨のやり方を添えた（§10 に一覧）。
* `<!-- check:… -->` の付いたコードブロック（` ```jsonc ` = コメント付き JSON）は §11 の検査器で
  「コンポーネント名が 1.21.120 のスキーマに実在するか」「上限を守っているか」などを機械的に検査済み。
  `//` コメントは説明用。**生成器が書く本物の JSON にはコメントを入れない**（`write_json` は素の JSON）。

---

## 0. 出典と版

| 記号 | 中身 | 版 | ローカルの写し（`build_preview/nr_research/content/` 下。gitignore） |
|---|---|---|---|
| 〔BS:…〕 | Mojang/bedrock-samples の vanilla パック（`behavior_pack/…`・`resource_pack/…`） | タグ **`v1.21.120.4`**（2025-10-28） | `bs_1.21.120.4/` |
| 〔DOC:名前〕 | 同じタグの `documentation/<名前>.html`（Entities・Blocks・Features・Fogs・Recipes・Entity Events…） | 同上 | `bs_1.21.120.4/documentation/`、テキスト化 `doc_txt/` |
| 〔SCH:…〕 | 同じタグの `metadata/json_schemas/…`（エンジンが出した JSON スキーマ） | 同上 | `bs_1.21.120.4/metadata/json_schemas/` |
| 〔VD:…〕 / 〔CMD〕 | 同じタグの `metadata/vanilladata_modules/…` / `metadata/command_modules/mojang-commands.json` | 同上 | 同上 |
| 〔MS:…〕 | MicrosoftDocs/minecraft-creator（MS Learn の原稿）`creator/…` | コミット `a2748504`（**2025-11-04**、1.21.120 公開の 1 週間後） | `mcc/creator/` |
| 〔WIKI:…〕 | Bedrock-OSS/bedrock-wiki `docs/…` | `657b4050`（2026-10-24。**1.26 系まで書いてある**ので版の注記に注意） | `wiki/docs/` |
| 〔MCS:…〕 | microsoft/minecraft-samples（**実物の `.mcstructure` 29 個**・地物の見本） | `5e04b6f7`（2026-08-24） | `mcsamples/` |
| 〔DTS:Lnnn〕 | `tools/nightrunner/typings/server/index.d.ts`（`@minecraft/server` 2.3.0 の公式 d.ts）の行 | 2.3.0 | リポジトリ内 |

取り直し方（どれも認証なしで取れる）:

```text
git clone --filter=blob:none --no-checkout --depth 1 --branch v1.21.120.4 https://github.com/Mojang/bedrock-samples bs_1.21.120.4
git clone --filter=blob:none --no-checkout https://github.com/MicrosoftDocs/minecraft-creator mcc   # その後 a2748504 を sparse checkout
単体なら https://raw.githubusercontent.com/Mojang/bedrock-samples/v1.21.120.4/behavior_pack/entities/zombie.json
```

### 0.1 `format_version` の選び方（1.21.120 向け）

| ファイル | 書く値 | 根拠 |
|---|---|---|
| BP エンティティ | `"1.21.120"` | 〔BS:behavior_pack/entities/arrow.json〕が `"1.21.120"`。zombie/husk は `"1.21.90"` |
| アイテム | `"1.21.120"` | 1.21.120 に版付きの変更がある（`menu_category` の扱い）〔WIKI:items/item-format-history.md §1.21.120〕。**1.21.90 以上は `minecraft:custom_components` が使えない**（同 §1.21.90「Removed」） |
| ブロック | `"1.21.120"` | 〔DOC:Blocks〕の例が `"format_version": "1.21.120"`。1.21.90 以上は `minecraft:custom_components` 廃止（〔WIKI:blocks/block-format-history.md §1.21.90〕） |
| スポーンルール | `"1.8.0"` | vanilla 54 本中 51 本が `1.8.0`〔BS:behavior_pack/spawn_rules/〕 |
| レシピ | `"1.20.10"` | 〔BS:behavior_pack/recipes/iron_sword.json〕ほか |
| ルートテーブル | なし | vanilla のルートに `format_version` は無い |
| 地物 / 地物ルール | `"1.13.0"` | 〔DOC:Features〕の例と〔MCS〕の見本 |
| 霧 | `"1.16.100"` | 〔BS:resource_pack/fogs/*.json〕 |
| カメラのプリセット | `"1.21.0"`（`1.19.50` でも可） | 〔MS:Documents/CameraSystem/*.md〕の例 |
| `item_catalog/crafting_item_catalog.json` | `"1.21.60"` | 〔MS:Documents/CraftingItemCatalogDocumentation.md〕 |
| RP `blocks.json` | `"1.21.40"`（文字列）か `[1, 1, 0]` | vanilla は `"format_version" : "1.21.40"`〔BS:resource_pack/blocks.json〕。現行の `[1,1,0]` も旧来の正しい形 |

---

## 1. BP エンティティ

### 1.1 `description`

〔DOC:Entities「Entity Description Properties」〕＋vanilla:

```json
"description": {
  "identifier": "minecraft:zombie",
  "spawn_category": "monster",
  "is_spawnable": true,
  "is_summonable": true
}
```

| キー | 型・既定 | 意味（DOC の文言の要約） |
|---|---|---|
| `identifier` | 文字列 | 名前空間付き ID |
| `is_spawnable` | bool / `false` | **スポーンエッグを作るか**（「Sets whether or not this entity has a spawn egg in the creative ui」） |
| `is_summonable` | bool / `false` | `/summon`（とスクリプトの `spawnEntity`）で出せるか |
| `spawn_category` | 文字列 | 自然スポーンの枠。vanilla の値: `monster`(37) `creature`(34) `water_ambient` `water_creature` `ambient` `axolotls` `misc` `underground_water_creature`〔BS〕 |
| `runtime_identifier` | 文字列 | vanilla のハードコード挙動を借りる（§1.4.11） |
| `properties` | 辞書 | エンティティプロパティ（§1.2） |

`is_experimental: false` は古い形の名残（snowball 1.16.0 など）。書かなくてよい。

### 1.2 `properties`（エンティティプロパティ）

〔MS:Documents/IntroductionToEntityProperties.md〕と〔BS:creaking.json〕〔BS:egg.json〕の実物:

```json
"properties": {
  "minecraft:creaking_state": {
    "type": "enum",
    "values": [ "neutral", "hostile_observed", "hostile_unobserved", "twitching", "crumbling" ],
    "default": "neutral",
    "client_sync": true
  },
  "minecraft:creaking_swaying_ticks": { "type": "int", "default": 0, "range": [ 0, 6 ], "client_sync": true }
}
```

* 型は **`int` / `float` / `enum` / `bool`** の 4 つ。`int`・`float` は `range: [min, max]` が要る。`bool` に range は無い。
  `client_sync: true` で RP（`query.property('nr:x')`）から読める。
* 名前は**名前空間付き**（`minecraft:` 以外）。
* **上限**（同 MS 文書「Limitations of Entity Properties」の原文）:
  * 「Each type of entity is limited to **32 Entity Properties**. Within that, there's no further limit on … how many of them have the `client_sync` property set to true.」
  * 「Each enum is limited to a maximum of **16 entries**. Each entry has a minimum length of 1 and a maximum length of **32 characters**. The first character of an enum entry must be **alphabetical** and the remaining characters can be alphabetical, numeric, or the underscore character.」
  * 超えると content error でプロパティが読み込まれない。
* `default` は値か Molang。Molang の既定値で使えるクエリは `query.had_component_group` だけ（変数は読み書き不可）。
* イベントの `set_property` の Molang は**変数の代入不可・読むのは可**。クエリは `query.property` / `query.has_property` だけ
  （`math.*` は関数でクエリではないので使える）。`int` は Molang が float で計算するので ±100 万以内に保つ。
* 範囲外の値は**黙って丸められる**（警告なし）。enum は文字列で保存されるので、並びを変えても既存の個体は壊れない。
  enum の値を消すと既存個体は既定値に戻る。
* NR のゾンビは 14 個（DESIGN §3 の表）。**全部の enum が 16 個以下・32 文字以下・英字始まり**（`cut_lower` 等も OK）。
  gib は 6 個。余裕は 18 個ある。

フィルタでの読み方〔MS 同文書〕:
`{"test": "enum_property", "subject": "self", "domain": "nr:state", "operator": "!=", "value": "dead"}`。
`int_property` / `float_property` / `bool_property`（value 省略で true）/ `has_property`（`value` にプロパティ名）。

### 1.3 `component_groups` と `events`

〔DOC:Entity Events〕の要点（原文の訳）:

* イベントは `sequence`（配列を**順に全部**）と `randomize`（`weight` で**一つ**選ぶ。weight 省略は 1.0）を組み合わせる。
  各ノードに `filters`・`add`・`remove`・`trigger`・`set_property`・`queue_command` を書ける。
* **ルート直下の `filters`**（`sequence` / `randomize` の外）は **format_version 1.19.20 以上でないと無視される**。
* 「イベントの効果は**すぐ計算されるが、エンティティがサーバーで tick するまで適用されない**。だから `sequence` の
  後ろの要素の filters は、前の要素の変更を見ない」。別のエンティティから送ったイベントは同 tick か次 tick に効く。
* `add`: 「同じ型のコンポーネントは一つしか持てないので、**後から足したグループが上書き**する。**既に付いている
  グループを足し直すと、そのコンポーネントは初期化し直される**（例: `minecraft:timer` は数え直し）」。
* `set_property`: `{"minecraft:has_nectar": false}` の形。`queue_command`: `{"command": "say …"}`（次 tick に実行）。
* vanilla はこのほか `emit_vibration` `play_sound` をイベントに書いている〔BS:creaking.json〕。

**最重要の落とし穴 — グループを外すとコンポーネントは「消える」**。〔MS:Documents/EntityBehaviorIntroduction.md
「Removing Components」〕の原文:「removing a component won't make it go back to the previous state of that component,
and it won't use the same component from another component group or the base components. Instead, the component will be
**removed completely** and reset to its default values.」（例: 基本 `scale: 2` の上にグループで `1.5` を足し、そのグループを
外すと 2 ではなく 1 に戻る）。特に `scale` `collision_box` `variant` `damage_sensor` `environment_sensor` `rideable` が危ない。

→ **生成器の規則**:「切り替える値（移動速度・当たり箱・センサー）は**基本 `components` に置かず、互いに排他なグループに
だけ置く**。切り替えるイベントは『全部外す → 一つ足す』」。vanilla の手本は creaking の `minecraft:mobile` /
`minecraft:immobile`（どちらも `movement` `knockback_resistance` `pushable` を持ち、`become_hostile` で
`add` と `remove` を一つのイベントで入れ替える）〔BS:creaking.json L232–L259, L370–L420〕。
camel の `minecraft:camel_standing` / `minecraft:camel_sitting` は `collision_box` を同じやり方で切り替える〔BS:camel.json〕。
同じ型を持つ二つのグループを**一つのイベントで**入れ替えても壊れないこと（＝remove が add より先に効くこと）は、
vanilla zombie の `minecraft:start_transforming`（どちらのグループも `minecraft:environment_sensor` を持つ）が動いている
ことから分かる〔BS:zombie.json〕。それでも順序を明示したいときは `sequence: [{remove}, {add}]` と分ける（§1.5 はこの形）。

**スクリプトからは**: `entity.triggerEvent("nr:on_death")`（定義に無い名前は例外〔script_api.md §4〕）、
`entity.setProperty("nr:state", "dead")`（値は次 tick まで `getProperty` に出ない）。移動速度は
`entity.getComponent("minecraft:movement").setCurrentValue(v)` でも変えられる（`EntityMovementComponent` 〔DTS:L9426〕 ←
`EntityAttributeComponent.setCurrentValue` 〔DTS:L8290〕）。**最大値（`max`）を超える値が丸められるかは UNVERIFIED** —
スクリプトで上げるなら JSON の `minecraft:movement` に `max` を明示しておく。

### 1.4 DL2 風ゾンビに要るコンポーネント

引数の表は〔DOC:Entities〕（1.21.120 版）。全コンポーネント名が 1.21.120 のエンジンに在ることは
〔SCH:server/entity/1.21.120/ActorDefinitions.json〕の `properties`（全コンポーネントの名前一覧）で確認した。

#### 1.4.1 移動と経路

| コンポーネント | 1.21.120 の引数（既定） | NR での使い方 |
|---|---|---|
| `minecraft:navigation.walk` | `avoid_damage_blocks`(false) `avoid_portals`(false) `avoid_sun`(false) `avoid_water`(false) `blocks_to_avoid`([]) `can_breach`(false) `can_break_doors`(false) `can_jump`(**true**) `can_open_doors`(false) `can_open_iron_doors`(false) `can_pass_doors`(**true**) `can_path_from_air`(false) `can_path_over_lava`(false) `can_path_over_water`(false) `can_sink`(**true**) `can_swim`(false) `can_walk`(**true**) `can_walk_in_lava`(false) `is_amphibious`(false) | 普通のゾンビは vanilla zombie と同じ `is_amphibious/can_pass_doors/can_walk/can_break_doors`。夜の捕食者は昼に `avoid_sun: true`。這う個体は `can_jump: false`（＝乗り越え不可） |
| `minecraft:navigation.climb` | navigation.walk と同じ引数 | 「vertical walls like the vanilla Spiders do」を含む経路を作る。spider は `navigation.climb` ＋ `can_climb` ＋ `movement.basic` ＋ `jump.static`〔BS:spider.json L175–L186〕。壁を登る種類のグループに使える（**壁を実際に登る挙動がカスタムエンティティでも spider と同じかは UNVERIFIED**。DESIGN では壁登りは `zombies/ai.js` がスクリプトで補う） |
| `minecraft:can_climb` | 引数なし | 「Allows this entity to climb up **ladders**」（はしご・つた）。zombie/husk が持つ |
| `minecraft:jump.static` | `jump_power`(0.42) | 1 段の段差を跳ぶ |
| `minecraft:movement` | `value`（`max`） | 速さ。zombie 大人 0.23、子ども 0.35〔BS:zombie.json〕。**DOC の表には無い**が MS Learn に `max`/`value` あり（属性系コンポーネント） |
| `minecraft:movement.basic` | `max_turn`(30.0) | 1 tick に曲がれる最大角度 |
| `minecraft:annotation.break_door` | `break_time`(12.0 秒) `min_difficulty`("hard") | `navigation.*` の `can_break_doors: true` と組で。vanilla zombie は 10% の個体にだけ足す。`behavior.break_door` は vanilla で誰も使っていない |
| `minecraft:annotation.open_door` | 引数なし | `can_open_doors: true` と組（villager_v2）。ゾンビには付けない |
| `minecraft:break_blocks` | `breakable_blocks`（ブロック名の配列） | 歩きながら壊す（ravager の草・作物）。デモリッシャー系に使える |
| `minecraft:follow_range` | `value` `max`（整数） | 追う範囲。nearest_attackable_target の `within_radius` は follow_range が**無いときだけ**使われる |

**`can_path_over_damage_blocks` というキーは 1.21.120 に存在しない**（DOC・MS・スキーマのどれにも無い）。
害のあるブロック（罠）を避けるかは **`avoid_damage_blocks`**。NR のゾンビは罠に突っ込んでほしいので既定の false のまま。

#### 1.4.2 攻撃

| コンポーネント | 引数（既定） | メモ |
|---|---|---|
| `minecraft:attack` | `damage`（数か `[min, max]`。負で回復）`effect_name` `effect_duration`(0.0) | 近接攻撃の威力。melee 系の goal が使う |
| `minecraft:behavior.melee_box_attack` | `attack_once`(false) `attack_types` `can_spread_on_fire`(false) `cooldown_time`(1 秒) **`horizontal_reach`(0.8)** `inner_boundary_time_increase`(0.25) `max_path_time`(0.55) `melee_fov`(90) `min_path_time`(0.2) `on_attack` `on_kill` `outer_boundary_time_increase`(0.5) `path_fail_time_increase`(0.75) `path_inner_boundary`(16) `path_outer_boundary`(32) `priority` `random_stop_interval`(0) `require_complete_path`(false) `speed_multiplier`(1) `track_target`(false) `x_max_rotation`(30) `y_max_head_rotation`(30) | 「reach calculations based on **bounding boxes**」。届く範囲 = 自分の当たり箱を水平に `horizontal_reach` だけ広げた箱。**1.21.120 の vanilla は creeper 以外の近接 31 体が全部これ**（zombie 含む。zombie は 1.20.80 の時点で既にこれ） |
| `minecraft:behavior.melee_attack` | 上と同じ。ただし `horizontal_reach` の代わりに **`reach_multiplier`(2)** | 旧来の「体の大きさ × 倍率」の距離判定。vanilla で残っているのは creeper（`reach_multiplier: 0`）だけ。**NR は `melee_box_attack` を使う** |
| `minecraft:behavior.leap_at_target` | `must_be_on_ground`(true) `set_persistent`(false) `yd`(0.0) | 「Can only be used by **hostile** mobs」。spider: `{"priority": 4, "yd": 0.4, "must_be_on_ground": false}`〔BS:spider.json〕。cat/ocelot は `target_dist: 0.3` も書くが DOC の表には無い（UNVERIFIED） |
| `minecraft:behavior.ranged_attack` | `attack_interval` / `attack_interval_min` / `attack_interval_max` `attack_radius` `attack_radius_min` `burst_interval` `burst_shots`(1) `charge_charged_trigger` `charge_shoot_trigger` `ranged_fov`(90) `set_persistent` `speed_multiplier`(1) `swing`(false) `target_in_sight_time`(1) `x_max_rotation` `y_max_head_rotation` | 「Requires `minecraft:shooter`」。blaze は 3 連射 `burst_shots: 3, burst_interval: 0.3, charge_shoot_trigger: 4.0` |
| `minecraft:shooter` | `def`（撃つエンティティ ID）`aux_val`(-1) `magic`(false) `power`(0 = 飛び道具側の既定) `projectiles`（条件付きリスト）`sound` | skeleton: `{"def": "minecraft:arrow", "sound": "bow"}`、drowned: `{"def": "minecraft:thrown_trident", "sound": "item.trident.throw"}`。スピッター系は `{"def": "nr:proj_spit"}` |

#### 1.4.3 標的

| コンポーネント | 引数（既定） | vanilla zombie の値〔BS:zombie.json〕 |
|---|---|---|
| `minecraft:behavior.nearest_attackable_target` | `attack_interval`(0) `attack_owner` `entity_types`（filters＋`max_dist`＋`must_see`…）`must_reach` `must_see`(false) `must_see_forget_duration`(3.0) `persist_time` `reselect_targets` `scan_interval`(10) `set_persistent` `target_invisible_multiplier`(0.70) `target_search_height`(-1) `target_sneak_visibility_multiplier`(0.80) `within_radius`(0.0) | `priority 2, must_see true, reselect_targets true, within_radius 25, must_see_forget_duration 17`、player/snowgolem/irongolem は `max_dist 35` |
| `minecraft:behavior.hurt_by_target` | `alert_same_type`(false) `entity_types`（filters・`max_dist`(16)…）`hurt_owner` | `priority 1`、`entity_types: [{filters: {test: is_family, subject: other, operator: "!=", value: "breeze"}}]` |
| `minecraft:behavior.random_stroll` | `priority` `speed_multiplier` … | `priority 7, speed_multiplier 1` |
| `minecraft:behavior.look_at_player` | `look_distance` `probability` … | `priority 8, look_distance 6, probability 0.02` |
| `minecraft:behavior.random_look_around` | `priority` | `priority 9` |

#### 1.4.4 体と物理

| コンポーネント | 引数（既定） | メモ |
|---|---|---|
| `minecraft:physics` | `has_collision`(true) `has_gravity`(true) `push_towards_closest_space`(false) | 重力と地形への当たり。player だけ `push_towards_closest_space: true`。**gib・死体に必須**（DESIGN §5） |
| `minecraft:pushable` | `is_pushable`(true) `is_pushable_by_piston`(true) | 押される体。creaking は動けない間 false/false |
| `minecraft:collision_box` | `width`(1.0) `height`(1.0)（負は 0 扱い。値の範囲は ±1e8 と書いてあるだけ） | **幅は X と Z で共通の正方形**。グループで切り替えられる（camel の座り/立ち）。zombie は 0.6×1.9 |
| `minecraft:custom_hit_test` | `hitboxes`: `[{"width", "height", "pivot": [x,y,z]}, …]`（**配列なので複数可**） | 近接・飛び道具の当たり判定だけを当たり箱と別にする。hoglin 大人 `{"width": 2, "height": 1.75, "pivot": [0, 1, 0]}`（当たり箱 1.4）。値から見て **`pivot` は箱の中心**（高さ 1.75 で y=1 → 0.125〜1.875）。**どの箱に当たったかはスクリプトに伝わらない**（`entityHurt` に場所は無い〔script_api.md §3.1〕）→ 部位判定は DESIGN §4 の通りスクリプトでやる。**pivot の x/z を中心から外したときにエンティティの向きで回るかは UNVERIFIED**（NR では pivot の x/z は 0 にする） |
| `minecraft:is_collidable` | 引数なし | 「This component can **only be used on mobs** and enables collisions **exclusively between mobs**. … this type of collision is **unreliable for moving** collidable mobs. It is recommended to use this component only in scenarios where the collidable mob **remains stationary**.」両方に `collision_box` が要る。vanilla は boat・chest_boat・happy_ghast（止まっている間）。**数や大きさの上限は文書に無い（UNVERIFIED）**。NR の車などの当たりは DESIGN §8 の通りバリアブロックで作る |
| `minecraft:knockback_resistance` | `value` `max`（DOC の表に無い。MS Learn と vanilla の値: armor_stand 1.0、hoglin 0.6、ender_dragon 100） | 0〜1。死体は 0 にして吹き飛ばす |
| `minecraft:scale` | `value`(1.0) | 見た目の倍率（zombie の子ども 0.5）。**当たり箱も一緒に縮むかは UNVERIFIED**（子どもの zombie は collision_box を変えずに scale だけ）。NR は scale 1 のまま、種類ごとの身長は geometry と collision_box で表す |
| `minecraft:health` | `value` `max`（MS Learn の既定 100） | NR は**大きなプール** `{value: 1000, max: 1000}`（DESIGN §4） |
| `minecraft:type_family` | `family`（文字列の配列） | zombie: `["zombie", "undead", "monster", "mob"]` |

#### 1.4.5 ダメージの受け方 `minecraft:damage_sensor`

〔DOC:Entities〕: `triggers`（1 個のオブジェクトか配列）。各トリガー:

| キー | 型・既定 | 意味 |
|---|---|---|
| `cause` | 文字列 / `none` | どの原因のダメージか（`all` で全部） |
| `deals_damage` | **`"yes"` / `"no"` / `"no_but_side_effects_apply"`**（既定 yes） | 「`no_but_side_effects_apply`: received damage is not applied to the entity, but the side effects of the attack are. This means that the attacker's weapon loses durability, enchantment side effects are applied, and so on.」。古い `true/false` も vanilla に 13 箇所残っている（20+4+9 箇所が新しい文字列形） |
| `damage_multiplier` | 1.0 | 倍率。`deals_damage` が yes なら「最低 1 までしか減らせない」 |
| `damage_modifier` | 0.0 | 足し引き（0 未満にはならない） |
| `on_damage` | `{filters, event, target}` | 条件とイベント。`event` 無しで filters だけでも可（allay: `{"on_damage": {"filters": …}, "deals_damage": "no"}`） |
| `on_damage_sound_event` | 文字列 | 条件に合った時の音 |

* **JSON の `cause` は snake_case**: vanilla で使われている値 `all` `lava` `fall` `entity_attack` `drowning` `projectile`
  `lightning` `void` `temperature` `none` `magic` `contact`〔BS 全エンティティを集計〕。DOC の別の箇所の列挙:
  `campfire, fire, fire_tick, freezing, lava, lightning, magma, soul_campfire, temperature, entity_attack, entity_explosion,
  fireworks, magic, projectile, ram_attack, sonic_boom, wither, mace_smash`。
  **スクリプトの `EntityDamageCause` は camelCase**（`'entityAttack'` `'fireTick'` `'blockExplosion'` …〔DTS:L1109〕）。
  生成器と JS で書き方が違うので混同しない。
* NR の死体（`nr:dead`）は `{"cause": "all", "deals_damage": "no"}`。このとき `entityHurt` は来ない
  （script_api.md §3.1 の注）→ 死体の切断は `entityHitEntity` / `projectileHitEntity` で拾う。
  **`no_but_side_effects_apply` で `entityHurt` が来るかは UNVERIFIED**（使わない）。

#### 1.4.6 タイマー・環境センサー

* `minecraft:timer`〔DOC〕: `looping`(true) `randomInterval`(true) `random_time_choices`（`time` と排他）
  `time`（数か `[min, max]` 秒）`time_down_event`（`{event, target}`）。
  例: bee `{"looping": false, "time": [20, 50], "randomInterval": true, "time_down_event": {"event": "stop_panicking_after_fire", "target": "self"}}`。
  **グループを足し直すと数え直し**（§1.3）。
* `minecraft:environment_sensor`: `triggers`（`{filters, event}` の 1 個か配列）。昼夜は `is_daytime` フィルタ
  （fox: `{"test": "is_daytime", "value": true}`）。使えるフィルタ名は〔DOC:Entities〕の索引に 100 余り
  （`is_daytime` `is_brightness` `light_level` `in_water` `is_underwater` `on_fire` `has_target` `target_distance`
  `int_property` `enum_property` `is_family` `actor_health` `on_ground` `is_moving` ほか）。

#### 1.4.7 ボスバー `minecraft:boss`

`hud_range`(55) `name` `should_darken_sky`(false)〔DOC〕。vanilla: wither `{"should_darken_sky": true, "hud_range": 55}`、
ender_dragon `{"should_darken_sky": false, "hud_range": 125}`。
**バーの長さは `minecraft:health` の割合**（vanilla の仕組み）。NR は体力を 1000 のプールに戻し続けるので、
**そのままではバーが減らない**。推奨: ボスだけスクリプトが毎ヒット後に
`health.setCurrentValue(Math.max(1, Math.round(1000 * hp / maxHp)))` で本当の体力を映す（バニラの一撃で死ぬ余地が出るが、
その場合は DESIGN §4 の「バニラの死 → 全身が弾け飛ぶ」に落ちる）。`name` を省いたときの表示名と、
`nameTag` を付けたときにバーの名前が変わるかは UNVERIFIED。

#### 1.4.8 消える・燃える

* `minecraft:despawn`〔DOC〕: `despawn_from_chance`(true) `despawn_from_distance`（`{min_distance: 32, max_distance: 128}`）
  `despawn_from_inactivity`(true) `despawn_from_simulation_edge`(true) `filters`（あると標準規則は無視）
  `min_range_inactivity_timer`(30) `min_range_random_chance`(800) `remove_child_entities`(false)。
  vanilla の敵は `{"despawn_from_distance": {}}`。スクリプトで出した個体を残したいときは
  `spawnEntity(…, {initialPersistence: true})`（1.21.120 で追加〔MS:Documents/Update1.21.120.md〕〔DTS:L20201〕）。
* `minecraft:instant_despawn`: `remove_child_entities`(false)。グループに入れて足した瞬間に消える
  （creaking の `minecraft:crumbling`）。DESIGN の `nr:despawn` イベントはこれ。
* `minecraft:burns_in_daylight`: 引数なし（bogged・drowned・phantom）。magma_cube は `false` を書いて打ち消している。
  NR は DL2 に合わせて昼に燃やさない（夜型の昼の挙動はスクリプトと `avoid_sun`）。

#### 1.4.9 見た目の変種

* `minecraft:variant` / `minecraft:mark_variant`: `value`（整数、0 が基本）。RP は `query.variant` / `query.mark_variant`。
  NR はプロパティ `nr:variant` を使う（グループの切り替えより扱いやすく、32 個の枠にも収まる）。

#### 1.4.10 帯域 `minecraft:conditional_bandwidth_optimization`

`default_values` / `conditional_values`（`max_dropped_ticks` `max_optimized_distance` `use_motion_prediction_hints`）。
zombie は `{}`。速く飛ぶもの（snowball）は
`{"default_values": {"max_optimized_distance": 100.0, "max_dropped_ticks": 7, "use_motion_prediction_hints": true}}`。
gib・飛び道具はこれに倣う（「This should be used when actors are travelling very quickly」）。

#### 1.4.11 `runtime_identifier` の注意

〔DOC〕「Sets the name for the Vanilla Minecraft identifier this entity will use to build itself from」。
〔WIKI:entities/runtime-identifier.md〕（実験の記録。**1.21.120 で同じかは UNVERIFIED**）:
* `minecraft:zombie`: 回復薬で傷つき負傷薬で回復、再生・毒が効かない、**Smite が効く**、
  「**ブロックの明るさ 0 でしか湧かない**」。
* `minecraft:snowball`: **当たり箱が消える**、重力無視、プレイヤーの頭から出る、影なし、南向き固定。
* `minecraft:arrow` / `minecraft:thrown_trident`: 矢・トライデントの飛び方とノックバック、拾える。
* 全般に「runtime ID の側の名前になる」。

**NR の推奨: ゾンビ・gib・小道具には付けない**（体力・部位・死はスクリプトが持つので vanilla のハードコードは邪魔）。
飛び道具も付けずに `minecraft:projectile` だけで作り、見た目の不具合が出たときだけ `minecraft:arrow` を試す。

### 1.5 完成形: 最小のゾンビ（`nr:z_office_worker`）

方針（DESIGN §4・§12 の通り）:
* 基本 `components` には**状態で変わらないものだけ**（family・体力プール・物理・押せる体・呼吸・名前・帯域・despawn）。
* `nr:alive`（AI・経路・攻撃・標的）、`nr:body_stand` / `nr:crawler` / `nr:dead`（当たり箱の 3 状態）、
  `nr:mobile` / `nr:mobile_crawl` / `nr:enraged` / `nr:rooted`（**移動速度の 4 状態。互いに排他**）。
* DESIGN のイベント名（`nr:on_death` `nr:to_crawl` `nr:root_start` `nr:root_end` `nr:enrage` `nr:calm` `nr:despawn`）を全部持つ。
* 種類ごとに変わる数値（身長・速さ・攻撃力）は spec から生成器が差し込む。ここは office_worker の値。

<!-- check:entity -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:entity": {
    "description": {
      "identifier": "nr:z_office_worker",
      "spawn_category": "monster",
      "is_spawnable": true,
      "is_summonable": true,
      // DESIGN §3 の表そのまま。14 個（上限 32）。enum は全部 16 個以下・英字始まり・32 文字以下
      "properties": {
        "nr:head":    { "type": "enum", "values": ["intact", "wounded", "jawless", "cracked", "severed", "crushed"], "default": "intact", "client_sync": true },
        "nr:arm_r":   { "type": "enum", "values": ["intact", "wounded", "broken", "cut_lower", "cut_upper"], "default": "intact", "client_sync": true },
        "nr:arm_l":   { "type": "enum", "values": ["intact", "wounded", "broken", "cut_lower", "cut_upper"], "default": "intact", "client_sync": true },
        "nr:leg_r":   { "type": "enum", "values": ["intact", "wounded", "broken", "cut_lower", "cut_upper"], "default": "intact", "client_sync": true },
        "nr:leg_l":   { "type": "enum", "values": ["intact", "wounded", "broken", "cut_lower", "cut_upper"], "default": "intact", "client_sync": true },
        "nr:torso":   { "type": "enum", "values": ["intact", "slashed", "gutted", "halved"], "default": "intact", "client_sync": true },
        "nr:blood":   { "type": "int", "range": [0, 3], "default": 0, "client_sync": true },
        "nr:burn":    { "type": "int", "range": [0, 3], "default": 0, "client_sync": true },
        "nr:shock":   { "type": "int", "range": [0, 1], "default": 0, "client_sync": true },
        "nr:armor":   { "type": "int", "range": [0, 3], "default": 3, "client_sync": true },
        "nr:state":   { "type": "enum", "values": ["normal", "crawl", "climb", "stagger", "down", "special", "dead"], "default": "normal", "client_sync": true },
        "nr:pose":    { "type": "int", "range": [0, 7], "default": 0, "client_sync": true },
        "nr:ability": { "type": "int", "range": [0, 7], "default": 0, "client_sync": true },
        "nr:variant": { "type": "int", "range": [0, 3], "default": 0, "client_sync": true }
      }
    },
    "component_groups": {
      // 生きている間の AI。死ぬと丸ごと外す（移動速度と当たり箱はここに入れない＝§1.3 の落とし穴よけ）
      "nr:alive": {
        "minecraft:movement.basic": {},
        "minecraft:jump.static": {},
        "minecraft:can_climb": {},
        "minecraft:navigation.walk": {
          "can_walk": true,
          "can_pass_doors": true,
          "can_break_doors": true,
          "is_amphibious": true,
          "avoid_damage_blocks": false
        },
        "minecraft:annotation.break_door": { "break_time": 6, "min_difficulty": "normal" },
        "minecraft:attack": { "damage": 4 },
        "minecraft:knockback_resistance": { "value": 0.1 },
        // ゾンビ同士の殴り合いのダメージを消す（死ぬと nr:alive ごと外れる）
        "minecraft:damage_sensor": {
          "triggers": [
            { "on_damage": { "filters": { "test": "is_family", "subject": "other", "value": "nr_zombie" } }, "deals_damage": "no" }
          ]
        },
        "minecraft:behavior.hurt_by_target": {
          "priority": 1,
          "entity_types": [ { "filters": { "test": "is_family", "subject": "other", "operator": "!=", "value": "nr_zombie" } } ]
        },
        "minecraft:behavior.nearest_attackable_target": {
          "priority": 2,
          "must_see": true,
          "reselect_targets": true,
          "within_radius": 32.0,
          "must_see_forget_duration": 17.0,
          "entity_types": [
            {
              "filters": { "any_of": [
                { "test": "is_family", "subject": "other", "value": "player" },
                { "test": "is_family", "subject": "other", "value": "villager" },
                { "test": "is_family", "subject": "other", "value": "wandering_trader" },
                { "test": "is_family", "subject": "other", "value": "irongolem" },
                { "test": "is_family", "subject": "other", "value": "snowgolem" }
              ] },
              "max_dist": 35
            }
          ]
        },
        // 1.21 系の vanilla と同じ箱判定の近接。届く範囲 = 当たり箱 + 水平 0.8
        "minecraft:behavior.melee_box_attack": {
          "priority": 3,
          "speed_multiplier": 1.15,
          "track_target": true,
          "horizontal_reach": 0.8,
          "cooldown_time": 1.0
        },
        "minecraft:behavior.random_stroll": { "priority": 7, "speed_multiplier": 0.8 },
        "minecraft:behavior.look_at_player": { "priority": 8, "look_distance": 8, "probability": 0.02 },
        "minecraft:behavior.random_look_around": { "priority": 9 }
      },
      // 当たり箱の 3 状態（立つ / 這う / 死体）。どれか一つだけを付ける
      "nr:body_stand": {
        "minecraft:collision_box": { "width": 0.6, "height": 1.9 },
        "minecraft:custom_hit_test": { "hitboxes": [ { "width": 0.9, "height": 2.0, "pivot": [0, 1.0, 0] } ] }
      },
      "nr:crawler": {
        "minecraft:collision_box": { "width": 0.8, "height": 0.6 },
        "minecraft:custom_hit_test": { "hitboxes": [ { "width": 1.1, "height": 0.7, "pivot": [0, 0.35, 0] } ] },
        // nr:alive の経路を上書き（這う個体は段差を越えない）。這いは戻らないので外す時は nr:alive と一緒
        "minecraft:navigation.walk": { "can_walk": true, "can_pass_doors": true, "is_amphibious": true, "can_jump": false }
      },
      "nr:dead": {
        "minecraft:collision_box": { "width": 0.9, "height": 0.4 },
        "minecraft:custom_hit_test": { "hitboxes": [ { "width": 1.4, "height": 0.5, "pivot": [0, 0.25, 0] } ] },
        // 死体は vanilla のダメージを受けない（切断は entityHitEntity / projectileHitEntity でスクリプトが拾う）
        "minecraft:damage_sensor": { "triggers": [ { "cause": "all", "deals_damage": "no" } ] }
      },
      // 移動速度の 4 状態（互いに排他。切り替えは「全部外す → 一つ足す」）
      "nr:mobile":       { "minecraft:movement": { "value": 0.23 }, "minecraft:follow_range": { "value": 32, "max": 64 } },
      "nr:mobile_crawl": { "minecraft:movement": { "value": 0.08 }, "minecraft:follow_range": { "value": 32, "max": 64 } },
      "nr:enraged":      { "minecraft:movement": { "value": 0.31 }, "minecraft:follow_range": { "value": 64, "max": 64 } },
      "nr:rooted":       { "minecraft:movement": { "value": 0.0 },  "minecraft:follow_range": { "value": 32, "max": 64 } },
      "nr:despawn": { "minecraft:instant_despawn": {} }
    },
    "components": {
      "minecraft:type_family": { "family": ["nr_zombie", "zombie", "undead", "monster", "mob"] },
      "minecraft:health": { "value": 1000, "max": 1000 },
      "minecraft:physics": {},
      "minecraft:pushable": { "is_pushable": true, "is_pushable_by_piston": true },
      "minecraft:breathable": { "total_supply": 15, "suffocate_time": 0, "breathes_air": true, "breathes_water": true },
      "minecraft:nameable": {},
      "minecraft:is_hidden_when_invisible": {},
      "minecraft:despawn": { "despawn_from_distance": {} },
      "minecraft:conditional_bandwidth_optimization": {}
    },
    "events": {
      "minecraft:entity_spawned": {
        "add": { "component_groups": ["nr:alive", "nr:body_stand", "nr:mobile"] },
        "set_property": { "nr:variant": "math.random_integer(0, 3)" }
      },
      "nr:on_death": {
        "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
        "sequence": [
          { "remove": { "component_groups": ["nr:alive", "nr:body_stand", "nr:crawler", "nr:mobile", "nr:mobile_crawl", "nr:enraged", "nr:rooted"] } },
          { "add": { "component_groups": ["nr:dead"] }, "set_property": { "nr:state": "dead" } }
        ]
      },
      "nr:to_crawl": {
        "filters": { "all_of": [
          { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
          { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "crawl" }
        ] },
        "sequence": [
          { "remove": { "component_groups": ["nr:body_stand", "nr:mobile", "nr:enraged", "nr:rooted"] } },
          { "add": { "component_groups": ["nr:crawler", "nr:mobile_crawl"] }, "set_property": { "nr:state": "crawl" } }
        ]
      },
      "nr:root_start": {
        "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
        "sequence": [
          { "remove": { "component_groups": ["nr:mobile", "nr:mobile_crawl", "nr:enraged"] } },
          { "add": { "component_groups": ["nr:rooted"] } }
        ]
      },
      "nr:root_end": {
        "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
        "sequence": [
          { "remove": { "component_groups": ["nr:rooted", "nr:enraged"] } },
          { "filters": { "test": "enum_property", "domain": "nr:state", "value": "crawl" }, "add": { "component_groups": ["nr:mobile_crawl"] } },
          { "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "crawl" }, "add": { "component_groups": ["nr:mobile"] } }
        ]
      },
      "nr:enrage": {
        "filters": { "all_of": [
          { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
          { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "crawl" }
        ] },
        "sequence": [
          { "remove": { "component_groups": ["nr:mobile", "nr:rooted"] } },
          { "add": { "component_groups": ["nr:enraged"] } }
        ]
      },
      "nr:calm": {
        "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "dead" },
        "sequence": [
          { "remove": { "component_groups": ["nr:enraged", "nr:rooted"] } },
          { "filters": { "test": "enum_property", "domain": "nr:state", "value": "crawl" }, "add": { "component_groups": ["nr:mobile_crawl"] } },
          { "filters": { "test": "enum_property", "domain": "nr:state", "operator": "!=", "value": "crawl" }, "add": { "component_groups": ["nr:mobile"] } }
        ]
      },
      "nr:despawn": { "add": { "component_groups": ["nr:despawn"] } }
    }
  }
}
```

この形の意味:
* **`nr:dead` に残るもの**: 基本の `physics`（重力・地形）・`pushable`（押せる）・`health`（プール）・`type_family` と、
  `nr:dead` 自身の低い `collision_box`・寝た `custom_hit_test`・全ダメージ無効の `damage_sensor`。
  AI・経路・攻撃・移動速度は全部外れている（外れた `minecraft:movement` は既定値に戻る＝MS の「reset to its default values」）。
  死体を吹き飛ばすのはスクリプトの `applyImpulse`（DESIGN §5）。`nr:pose` はスクリプトが `setProperty` で決める。
* `nr:root_end` / `nr:calm` は**怒り状態を解く**（どの速度グループが付いていたかをフィルタで調べる手段が無いため）。
  怒ったまま根付かせたいときは、スクリプトが `nr:root_end` の後に `nr:enrage` を呼び直す。
* 特殊感染者は `nr:alive` に `behavior.ranged_attack` + `shooter`（スピッター）、`behavior.leap_at_target`（ヴァイラル系）、
  `break_blocks`（デモリッシャー系）を足す。壁を登る種類は `navigation.walk` の代わりに `navigation.climb`（§1.4.1）。
* 見た目を決めるのは RP（`reference/rendering.md`）。`nr:state` が `crawl` / `dead` の時の姿勢・`part_visibility` は RP の仕事。

### 1.6 `nr:gib`（物理で転がる肉片）の最小形

<!-- check:entity -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:entity": {
    "description": {
      "identifier": "nr:gib",
      "is_spawnable": false,
      "is_summonable": true,
      "properties": {
        "nr:ztype": { "type": "int", "range": [0, 63], "default": 63, "client_sync": true },
        "nr:part":  { "type": "int", "range": [0, 15], "default": 13, "client_sync": true },
        "nr:spin":  { "type": "int", "range": [0, 7],  "default": 0,  "client_sync": true },
        "nr:rest":  { "type": "int", "range": [0, 3],  "default": 0,  "client_sync": true },
        "nr:bleed": { "type": "int", "range": [0, 1],  "default": 1,  "client_sync": true },
        "nr:side":  { "type": "int", "range": [0, 1],  "default": 0,  "client_sync": true }
      }
    },
    "component_groups": {
      "nr:despawn": { "minecraft:instant_despawn": {} }
    },
    "components": {
      "minecraft:type_family": { "family": ["nr_gib", "inanimate"] },
      // 殴れる（entityHitEntity が来る）ように体力は持たせ、ダメージは全部消す
      "minecraft:health": { "value": 1000, "max": 1000 },
      "minecraft:damage_sensor": { "triggers": [ { "cause": "all", "deals_damage": "no" } ] },
      "minecraft:collision_box": { "width": 0.3, "height": 0.3 },
      // ブロックの中に埋まったら近い空きへ押し出す（vanilla では player だけが使う引数）
      "minecraft:physics": { "has_gravity": true, "has_collision": true, "push_towards_closest_space": true },
      "minecraft:pushable": { "is_pushable": true, "is_pushable_by_piston": true },
      "minecraft:knockback_resistance": { "value": 0.0 },
      "minecraft:despawn": { "despawn_from_distance": {} },
      "minecraft:conditional_bandwidth_optimization": {
        "default_values": { "max_optimized_distance": 60.0, "max_dropped_ticks": 2, "use_motion_prediction_hints": true }
      }
    },
    "events": {
      "nr:despawn": { "add": { "component_groups": ["nr:despawn"] } }
    }
  }
}
```

**UNVERIFIED**: 体力を持つが AI の無いカスタムエンティティに、プレイヤーの近接が当たって `entityHitEntity` が来ること
（vanilla の armor_stand と同じ型なので来るはず）。来なければ gib の蹴り飛ばしはプレイヤーの視線レイで代わりにやる。

---

## 2. 飛び道具

### 2.1 `minecraft:projectile`

〔DOC:Entities〕の表（1.21.120）: `angle_offset`(0) `catch_fire`(false) `crit_particle_on_hurt`(false) `destroy_on_hurt`(false)
`filter`（傷つけないエンティティ）`fire_affected_by_griefing`(false) **`gravity`(0.05)** `hit_nearest_passenger`(false)
`hit_sound` `homing`(false) `ignored_entities`（**[EXPERIMENTAL]**）**`inertia`(0.99)** `is_dangerous`(false) `knockback`(true)
`lightning`(false) `liquid_inertia`(0.6) `multiple_targets`(true) `offset`([0,0,0]) `on_fire_time`(5) **`particle`("iconcrack")**
`potion_effect`(-1) **`power`(1.3)** `reflect_immunity`(0) `reflect_on_hurt`(false) `semi_random_diff_damage`(false)
`shoot_sound` `shoot_target`(true) `should_bounce`(false) `splash_potion`(false) `splash_range`(4)
**`uncertainty_base`(0)** **`uncertainty_multiplier`(0)**（ぶれ = base − 難易度 × multiplier）。

**`on_hit` は DOC の表に載っていない**。vanilla が実際に使っているキー（1.21.120 の実物）:

| `on_hit` のキー | 実例 |
|---|---|
| `impact_damage` | `{"damage": 3, "knockback": true, "filter": "blaze"}`（snowball）、`{"damage": [1, 4], "knockback": true, "semi_random_diff_damage": false, "destroy_on_hit": true}`（arrow）、player の矢は `"max_critical_damage": 10, "min_critical_damage": 9, "power_multiplier": 0.97`、small_fireball は `"catch_fire": true` |
| `remove_on_hit` | `{}`（snowball・llama_spit・egg・small_fireball・splash_potion） |
| `stick_in_ground` | `{"shake_time": 0.35}`（arrow）、`{"shake_time": 0}`（thrown_trident） |
| `arrow_effect` | `{"apply_effect_to_blocking_targets": false}`（arrow） |
| `particle_on_hit` | `{"particle_type": "snowballpoof", "num_particles": 6, "on_entity_hit": true, "on_other_hit": true}` |
| `catch_fire` | `{"fire_affected_by_griefing": true}`（small_fireball） |
| `definition_event` | `{"affect_projectile": true, "event_trigger": {"event": "minecraft:explode", "target": "self"}}`（fireball・wither_skull） |
| `mob_effect` | `{"effect": "wither", "durationeasy": 0, "durationnormal": 200, "durationhard": 800, "amplifier": 1}` |
| `spawn_chance` / `douse_fire` / `thrown_potion_effect` / `wind_burst_on_hit` | egg / splash_potion / wind_charge の専用 |

DOC に無いが vanilla が使っている projectile 直下のキー: `anchor`（snowball・arrow は 1、fireball は 2）、`hit_ground_sound`
（trident）、`stop_on_hurt`（trident）。意味は UNVERIFIED。vanilla の数値をそのまま写して使う。

### 2.2 最小の飛び道具エンティティ（`nr:proj_spit`）

<!-- check:entity -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:entity": {
    "description": {
      "identifier": "nr:proj_spit",
      "is_spawnable": false,
      "is_summonable": true
    },
    "component_groups": {
      "nr:despawn": { "minecraft:instant_despawn": {} }
    },
    "components": {
      "minecraft:collision_box": { "width": 0.25, "height": 0.25 },
      // llama_spit を下敷きに。当たった後の処理（酸だまり・溶け・音）はスクリプトが projectileHit* で行う
      "minecraft:projectile": {
        "on_hit": {
          "impact_damage": { "damage": 2, "knockback": false },
          "remove_on_hit": {}
        },
        "power": 1.2,
        "gravity": 0.04,
        "inertia": 1.0,
        "liquid_inertia": 0.6,
        "uncertainty_base": 6,
        "uncertainty_multiplier": 2,
        "anchor": 1,
        "offset": [0, -0.1, 0],
        "multiple_targets": false
      },
      "minecraft:physics": {},
      "minecraft:pushable": { "is_pushable": false, "is_pushable_by_piston": true },
      "minecraft:conditional_bandwidth_optimization": {
        "default_values": { "max_optimized_distance": 100.0, "max_dropped_ticks": 7, "use_motion_prediction_hints": true }
      }
    },
    "events": {
      "nr:despawn": { "add": { "component_groups": ["nr:despawn"] } }
    }
  }
}
```

* `remove_on_hit` を付けると、`projectileHitEntity` / `projectileHitBlock` が来た時には**弾が既に無効**かもしれない
  （script_api.md §3.3「必ず `isValid` を見る」）。場所は `ev.location`、向きは `ev.hitVector` で取れる。
  **弾の種類（typeId）を無効になった後に読めるかは UNVERIFIED** → 種類ごとの処理が要る弾（火炎瓶・パイプ爆弾）は
  `remove_on_hit` を付けず、スクリプトが処理してから `triggerEvent("nr:despawn")` で消す。
* スクリプトから撃つ: `entity.getComponent("minecraft:projectile").shoot(velocity, {uncertainty?})`〔DTS:L9955〕
  （`EntityProjectileComponent` は stable。`minecraft:projectile` を持つエンティティでだけ取れる）。
* 見た目（RP の client_entity・ジオメトリ）は rendering.md。

### 2.3 投げるアイテム（`minecraft:throwable` + `minecraft:projectile`）

vanilla の wind_charge〔BS:behavior_pack/items/wind_charge.json〕:

```json
"minecraft:projectile": { "projectile_entity": "wind_charge_projectile" },
"minecraft:throwable": { "do_swing_animation": true, "launch_power_scale": 1.5, "max_launch_power": 1.5 },
"minecraft:cooldown": { "category": "wind_charge", "duration": 0.5 }
```

* `minecraft:throwable`〔SCH:server/item/1.21.110/ItemObject.json〕: `do_swing_animation`(false) `launch_power_scale`(1.0)
  `max_draw_duration`(0.0) `max_launch_power`(1.0) `min_draw_duration`(0.0) `scale_power_by_draw_duration`(false)。
* アイテムの `minecraft:projectile`: `projectile_entity`（**必須**。`"nr:proj_molotov"` や `"ns:id<event>"` の形）
  `minimum_critical_power`。MS Learn:「this component sets the entity that is spawned for items that also contain the
  minecraft:throwable component」。
* 溜めて投げる（`scale_power_by_draw_duration: true`）に `minecraft:use_modifiers.use_duration` が要るかは UNVERIFIED。
  NR の投擲物はまず溜め無し（クリックで即投げ）で作る。

<!-- check:item -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:item": {
    "description": {
      "identifier": "nr:molotov",
      "menu_category": { "category": "equipment" }
    },
    "components": {
      "minecraft:icon": "nr_molotov",
      "minecraft:display_name": { "value": "item.nr:molotov" },
      "minecraft:max_stack_size": 16,
      "minecraft:throwable": { "do_swing_animation": true, "launch_power_scale": 1.0, "max_launch_power": 1.1 },
      "minecraft:projectile": { "projectile_entity": "nr:proj_molotov" },
      "minecraft:cooldown": { "category": "nr:throw", "duration": 0.6 }
    }
  }
}
```

---

## 3. アイテム（1.21.120）

### 3.1 `description`

〔SCH:server/item/1.21.110/Description Data.json / Menu Category Data.json〕:
* `identifier`（必須）。
* `menu_category`: `category` = `"construction" | "nature" | "equipment" | "items" | "none"`（既定 none）、
  `group`（256 文字まで、**名前空間必須**。例 `"minecraft:itemGroup.name.sword"`）、`is_hidden_in_commands`(false)。
  1.21.120 から「カテゴリ none のアイテムもコマンドで使える」（版付きの変更〔WIKI:items/item-format-history.md〕）。
* vanilla の古い形 `"category": "Items"`（1.20.50 の apple 等）は書かない。
* **自前の折りたたみグループ**は BP `item_catalog/crafting_item_catalog.json`（1.21.60〜）で作る
  〔MS:Documents/CraftingItemCatalogDocumentation.md〕。グループ名は名前空間付きで、そのまま言語キーになる
  （`nr:itemGroup.weapons=武器` を lang に書く）。既存カテゴリの**末尾**に足される。

<!-- check:item_catalog -->
```jsonc
{
  "format_version": "1.21.60",
  "minecraft:crafting_items_catalog": {
    "categories": [
      {
        "category_name": "equipment",
        "groups": [
          { "group_identifier": { "icon": "nr:w_machete", "name": "nr:itemGroup.weapons" }, "items": ["nr:w_machete", "nr:w_pipe"] }
        ]
      }
    ]
  }
}
```

vanilla のグループ名（抜粋）: `minecraft:itemGroup.name.sword` `.axe` `.arrow` `.helmet` `.chestplate` `.leggings` `.boots`
`.miscFood` `.potion` `.splashPotion` `.mobEgg` `.glass` `.glassPane` `.fence` `.door` `.trapdoor` `.slab` `.stairs` `.walls`
`.concrete` `.stoneBrick`（全 70 余りは同 MS 文書の末尾）。

### 3.2 `components`（1.21.120 にあるもの）

〔SCH:server/item/1.21.110/ItemObject.json〕の `components` に載っている名前が全部（1.21.120 のタグに入っている最新のアイテムスキーマ）:

`allow_off_hand` `block_placer` `bundle_interaction` `can_destroy_in_creative` `compostable` `cooldown` `custom_components`(**廃止**)
`damage` `damage_absorption` `digger` `display_name` `durability` `durability_sensor` `dyeable` `enchantable` `entity_placer`
`fire_resistant` `food` `fuel` `glint` `hand_equipped` `hover_text_color` `icon` `interact_button` `liquid_clipped`
`max_stack_size` `projectile` `rarity` `record` `repairable` `shooter` `should_despawn` `stacked_by_data` `storage_item`
`storage_weight_limit` `storage_weight_modifier` `swing_duration` `tags` `throwable` `use_animation` `use_modifiers` `wearable`
（全部 `minecraft:` 付き）。

| コンポーネント | 1.21.120 の形（スキーマ） | メモ |
|---|---|---|
| `minecraft:icon` | 文字列 か `{"textures": {"default": "<item_texture.json のキー>", …}}` | 古い `{"texture": "x"}` は「Deprecated」〔MS〕。vanilla bundle（1.21.80）は `textures` 形 |
| `minecraft:display_name` | `{"value": "<文字列か言語キー>"}` | 言語キーを入れると翻訳される。NR は `item.nr:<id>` を必ず書く（無くても既定キーは同じ形〔WIKI:items/items-intro.md〕） |
| `minecraft:max_stack_size` | 整数 1〜64 か `{"value": n}` | **動的プロパティを使う武器は 1**（script_api.md §10） |
| `minecraft:hand_equipped` | bool か `{"value": b}` | 「rendered like a tool」（三人称の持ち方） |
| `minecraft:durability` | `{"max_durability": n(≥0, 必須), "damage_chance": {"min", "max"}}`（%、既定 100） | 下の §3.5 |
| `minecraft:damage` | 整数 ≥0 か `{"value": n}` | 「how much **extra** damage the item does on attack」。**1.21.120 では 255 まで**（256〜32767 が通るのは 1.26.0 から〔WIKI:item-format-history §1.26.0〕） |
| `minecraft:enchantable` | `{"slot": …, "value": n}`（どちらも必須） | slot は `none|all|g_armor|armor_head|armor_torso|armor_feet|armor_legs|sword|bow|spear|crossbow|g_tool|hoe|shears|flintsteel|shield|g_digging|axe|pickaxe|shovel|fishing_rod|carrot_stick|elytra|cosmetic_head` |
| `minecraft:repairable` | `{"repair_items": [{"items": [...], "repair_amount": <数か Molang>}]}` | 例 `"repair_amount": "query.max_durability * 0.25"`〔MS〕 |
| `minecraft:use_modifiers` | `use_duration`(秒, 既定 0) `movement_modifier`(0〜1) `emit_vibrations`(true, **1.21.120 で追加**) | 食べ物・投擲・弓の「使う時間」 |
| `minecraft:cooldown` | `{"category": 文字列, "duration": 秒}`（両方必須） | **使う（use）時だけ**。`type: "attack"`（攻撃のクールダウン）は **1.21.130 から**〔WIKI:item-format-history §1.21.130〕で 1.21.120 には無い |
| `minecraft:food` | `can_always_eat`(false) `nutrition`(0) `saturation_modifier`(0.6) `using_converts_to` | `use_modifiers` と `use_animation: "eat"` と組（vanilla apple） |
| `minecraft:use_animation` | `none|eat|drink|block|bow|camera|crossbow|spear|spyglass|brush` | 回復アイテムは `drink`/`eat` |
| `minecraft:wearable` | `{"slot": "slot.armor.head|chest|legs|feet" or "slot.weapon.offhand", "protection": n, "hides_player_location": b}` | 防具。手以外の slot は自動で重ならなくなる |
| `minecraft:tags` | `{"tags": ["minecraft:is_sword", "nr:weapon", …]}` | 自前のタグはスクリプトの `hasTag` で読める |
| `minecraft:shooter` | `ammunition: [{"item", "search_inventory", "use_in_creative", "use_offhand"}]` `charge_on_draw` `max_draw_duration` `scale_power_by_draw_duration` | 弓・クロスボウ型。弾は `minecraft:projectile` を持つアイテム |
| `minecraft:swing_duration` | `{"value": 秒}`（既定 0.3） | **1.21.120 で追加**。「Affects **visuals only** and does not impact attack frequency」 |
| `minecraft:glint` / `rarity` / `hover_text_color` | bool / 文字列 | 改造済み武器の見た目に使える |

**1.21.120 に無いもの**（書くと content error か無視）: `minecraft:weapon`（`on_hurt_entity` ごと廃止。MS「deprecated, no longer in use」）、
`minecraft:kinetic_weapon` / `minecraft:piercing_weapon` / `minecraft:swing_sounds`（1.21.130）、`cooldown.type`（1.21.130）、
`use_modifiers.start_sound`（1.21.130）、`minecraft:custom_components`（1.21.90 以上の版で廃止）。

### 3.3 カスタムコンポーネント（2.x の書き方）

1.21.90 から**平たい書き方**: `components` の中に `"<名前空間>:<名前>": {パラメータ}` を直接書く
（〔WIKI:items/item-format-history.md §1.21.90〕「Removed `minecraft:custom_components` … Custom components should now be applied
in the same way as vanilla components」、〔MS:Documents/scripting/v2-overview.md「Custom Components V2」〕）。

```json
"components": {
  "minecraft:glint": true,
  "nr:weapon": { "key": "machete" }
}
```

* スクリプトは `system.beforeEvents.startup` で `itemComponentRegistry.registerCustomComponent("nr:weapon", {...})`。
  フックの第 2 引数 `CustomComponentParameters` の `params` が JSON のオブジェクト（script_api.md §2）。
* アイテムのフック（2.3.0 stable〔DTS:L19687〕）: `onBeforeDurabilityDamage` `onCompleteUse` `onConsume` `onHitEntity`
  `onMineBlock` `onUse` `onUseOn`。
* 登録していない名前を JSON に書くと読み込み時にエラー（V2 は「registered from scripts before block JSON files are loaded,
  to provide better error messages」）。**JSON と JS の名前の一覧を一致させる**（validate_nr で照合する）。

### 3.4 武器が vanilla のダメージを出すしくみ

* プレイヤーの近接ダメージ = 素手の基本値 1 ＋ `minecraft:damage` の「extra」（＋エンチャント・クリティカル）。
  **合計の式（素手 1 に足すのか）は UNVERIFIED**。NR のゾンビは `entityHurt` の `damage` を使わず spec の値で計算するので
  影響は vanilla の敵とプレイヤーに当てた時だけ。`minecraft:damage` には「同じ系統の vanilla の剣」程度の値を入れる。
* Bedrock の近接には**攻撃のクールダウンが無い**。武器の攻撃速度はスクリプト（`combat/melee.js` が最後に振った tick を
  覚える）で守る。`swing_duration` は見た目だけ。
* 届く距離を変えるアイテムのコンポーネントは 1.21.120 に無い（`piercing_weapon` / `kinetic_weapon` の `reach` は 1.21.130）。
  槍の長い間合いはスクリプトのレイで作る。

### 3.5 耐久をスクリプトで減らす

* `minecraft:durability` を持つアイテムで敵を叩くと**エンジンが耐久を減らす**:
  `ItemCustomComponent.onBeforeDurabilityDamage` は「called when an item containing this component is hitting an entity and
  about to take durability damage」〔DTS:L19691〕、`ItemComponentBeforeDurabilityDamageEvent.durabilityDamage` は書き換え可
  〔DTS:L11490〕。1 回の減り幅は wiki に「Each time an entity is hit using this item, the item's damage increases by **2**」
  〔WIKI:items/item-components.md「Durability」〕（1.21.120 での値は UNVERIFIED）。採掘（`digger`）では減らない（同）。
* **NR の方針**: 武器の JSON に `nr:weapon` を付け、そのフックで `e.durabilityDamage = 0`（エンジンの減りを止める）。
  耐久はスクリプトが一か所（`combat/durability.js`）で `ItemDurabilityComponent.damage` を増やし、`setEquipment` で書き戻す
  （script_api.md §10 の例）。`damage == maxDurability` でも勝手には壊れない（同 §10 の注）ので、壊すのもスクリプト。

### 3.6 武器の完成形

<!-- check:item -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:item": {
    "description": {
      "identifier": "nr:w_machete",
      "menu_category": { "category": "equipment", "group": "minecraft:itemGroup.name.sword" }
    },
    "components": {
      "minecraft:icon": "nr_machete",
      "minecraft:display_name": { "value": "item.nr:w_machete" },
      "minecraft:max_stack_size": 1,
      "minecraft:hand_equipped": true,
      "minecraft:durability": { "max_durability": 220, "damage_chance": { "min": 100, "max": 100 } },
      "minecraft:damage": 6,
      "minecraft:enchantable": { "slot": "sword", "value": 10 },
      "minecraft:repairable": { "repair_items": [ { "items": ["nr:scrap"], "repair_amount": "query.max_durability * 0.25" } ] },
      "minecraft:can_destroy_in_creative": false,
      "minecraft:swing_duration": { "value": 0.35 },
      "minecraft:tags": { "tags": ["minecraft:is_sword", "nr:weapon", "nr:slash"] },
      // カスタムコンポーネント（2.x の平たい書き方）。耐久のフックと武器表の key をスクリプトへ渡す
      "nr:weapon": { "key": "machete" }
    }
  }
}
```

---

## 4. カスタムブロック（1.21.120）

### 4.1 `description`

〔SCH:server/block/1.21.110/Blocks.json / States.json / Traits.json〕:
* `identifier`（必須）、`menu_category`（`category` 必須・`group`・`is_hidden_in_commands`）、`states`、`traits`。
* `states`: `{"nr:lit": [false, true]}`（bool・int・文字列の配列）か `{"nr:stage": {"values": {"min": 0, "max": 3}}}`（範囲）。
  **1 つの状態は 16 値まで**、**1 ブロックの組み合わせは 65,536 まで**（超えると状態が欠けて content error）
  〔WIKI:blocks/block-states.md・block-permutations.md〕。
* `traits`:
  * `minecraft:placement_direction`: `enabled_states`（`"minecraft:cardinal_direction"` / `"minecraft:facing_direction"` の 1〜2 個）、
    `y_rotation_offset`（0/90/180/270/360。既定 0 = プレイヤーが北を向いて置くと north）。
  * `minecraft:placement_position`: `enabled_states`（`"minecraft:block_face"` / `"minecraft:vertical_half"`）。

### 4.2 `permutations`

`[{"condition": "<Molang>", "components": {…}}, …]`。条件は `q.block_state('名前') == 値`。後の要素が上書き。
向きの回転は `minecraft:transformation` を使う（モデルの前が北のとき north 0 / west `[0, 90, 0]` / south `[0, 180, 0]` /
east `[0, -90, 0]`〔WIKI:blocks/block-orientation.md〕）。**`geometry.n_way_visual_rotation` は 1.26.30 から**で 1.21.120 には無い。

### 4.3 `components`

〔DOC:Blocks〕（1.21.120）の表と、〔WIKI:blocks/block-format-history.md〕の版の注記:

| コンポーネント | 形・上限 | メモ |
|---|---|---|
| `minecraft:geometry` | `"geometry.nr.b.xxx"` か `{"identifier", "bone_visibility": {骨: bool か Molang}, "culling", "culling_layer", "uv_lock"}` | RP の `models/blocks/*.geo.json`。**モデルは 30×30×30 px まで**、各軸で少なくとも 1px が 16×16×16 の中、原点から各方向 30px 以内〔WIKI:blocks/block-components.md「Geometry」〕。vanilla の `minecraft:geometry.full_block` / `minecraft:geometry.cross` も可 |
| `minecraft:material_instances` | `{"*": {"texture": "<terrain_texture のキー>", "render_method": …, "ambient_occlusion", "face_dimming", "isotropic", "tint_method"}, "<名前>": {...}, "up": "<名前>"}` | render_method は DOC の `opaque` `double_sided` `blend` `alpha_test` と、1.21.80 で正式になった遠くで不透明に切り替わる `blend_to_opaque` `alpha_test_to_opaque` `alpha_test_single_sided_to_opaque`〔WIKI §1.21.80〕。**全インスタンスで揃える**。`emissive` は 1.21.120 では Upcoming Creator Features（実験）で 1.21.130 で消えた → **使わない** |
| `minecraft:collision_box` | `true` / `false` / `{"origin": [x,y,z], "size": [x,y,z]}`（px） | **origin と origin+size が (-8,0,-8)〜(8,16,8) の中**〔DOC〕。**1 個だけ**（配列で複数・上へ 24px は 1.21.130 の実験） |
| `minecraft:selection_box` | 同上 | 同じ範囲制限 |
| `minecraft:light_emission` | 0〜15（既定 0） | permutation で状態ごとに変えられる |
| `minecraft:light_dampening` | 0〜15（既定 15） | 透ける形のブロックは 0 |
| `minecraft:destructible_by_mining` | bool か `{"seconds_to_destroy": 秒}` | `item_specific_speeds` は実験（使わない） |
| `minecraft:destructible_by_explosion` | bool か `{"explosion_resistance": n}` | |
| `minecraft:loot` | `"loot_tables/blocks/xxx.json"`（256 文字まで） | 省くと自分のアイテムが落ちる |
| `minecraft:transformation` | `rotation`（90° 刻み）`rotation_pivot` `scale` `scale_pivot` `translation` | 変形後も geometry の上限を守る |
| `minecraft:placement_filter` | `{"conditions": [{"allowed_faces": [...6 まで], "block_filter": [...64 まで]}]}`（64 条件まで） | 外れた所には置けない・支えを失うと壊れる |
| `minecraft:map_color` | `"#RRGGBB"` / `[r,g,b]` / `{"color", "tint_method"}` | 省くと地図に出ない |
| `minecraft:friction` | 0.0〜0.9（既定 0.4） | 大きいほど滑らない |
| `minecraft:display_name` | 言語キー（256 文字まで） | 省くと `tile.<id>.name` |
| `minecraft:tick` | `{"interval_range": [最小, 最大]（tick）, "looping": bool}` | カスタムコンポーネントの `onTick` を呼ぶ。「a maximum of **100 queued ticks** can be executed in a given chunk every tick」〔WIKI〕。1.21.10 で正式 |
| `minecraft:entity_fall_on` | `{"min_fall_distance": n}` | `onEntityFallOn` を呼ぶのに要る |
| `minecraft:redstone_conductivity` / `minecraft:redstone_producer`(1.21.120 で正式) / `minecraft:movable` / `minecraft:random_offset` / `minecraft:replaceable` / `minecraft:liquid_detection` / `minecraft:flammable` / `minecraft:crafting_table` / `minecraft:destruction_particles` / `minecraft:breathability` / `minecraft:item_visual` / `minecraft:embedded_visual` / `minecraft:flower_pottable` | DOC の表のとおり | 罠・装置で使う可能性があるもの |

ブロックのカスタムコンポーネントのフック（2.3.0 stable〔DTS:L18349〕）: `beforeOnPlayerPlace` `onEntityFallOn` `onPlace`
`onPlayerBreak` `onPlayerInteract` `onRandomTick` `onStepOff` `onStepOn` `onTick`。
* `onStepOn` / `onStepOff` は「`collision_box` が Y に **3.2px より高い**」ときだけ来る〔WIKI:blocks/block-events.md「Step On」〕
  （UNVERIFIED for 1.21.120）→ 床置きの罠（スパイク・トラバサミ）は当たり箱の高さを 4px 以上にする。
* `onTick` は `minecraft:tick`、`onEntityFallOn` は `minecraft:entity_fall_on` が要る。`onRandomTick` は何も要らない。

**1.21.120 の DOC にまだ載っているが使えないもの**: `events` と `minecraft:on_interact` `on_step_on` `on_placed` … などの
トリガー・`set_block_state` などの応答（Holiday Creator Features。**1.20.80 で削除**〔WIKI:block-format-history §1.20.80〕）、
`minecraft:unit_cube`（1.20.60 で削除）、`minecraft:queued_ticking` / `minecraft:random_ticking`（旧名）。
DOC のブロックの例（`minecraft:destroy_time` `flame_odds`）も古い形なので写さない。
**`minecraft:sound`・`minecraft:tags`（ブロック）・`minecraft:support` は 1.26 系**。ブロックの音は RP `blocks.json` で決める（§4.5）。

### 4.4 完成形（UV ライト `nr:uv_lamp`）

<!-- check:block -->
```jsonc
{
  "format_version": "1.21.120",
  "minecraft:block": {
    "description": {
      "identifier": "nr:uv_lamp",
      "menu_category": { "category": "construction" },
      "states": { "nr:lit": [true, false] },
      "traits": {
        "minecraft:placement_direction": { "enabled_states": ["minecraft:cardinal_direction"], "y_rotation_offset": 180 }
      }
    },
    "components": {
      "minecraft:geometry": "geometry.nr.b.uv_lamp",
      "minecraft:material_instances": { "*": { "texture": "nr_uv_lamp", "render_method": "alpha_test" } },
      "minecraft:collision_box": { "origin": [-3, 0, -3], "size": [6, 16, 6] },
      "minecraft:selection_box": { "origin": [-4, 0, -4], "size": [8, 16, 8] },
      "minecraft:light_dampening": 0,
      "minecraft:light_emission": 14,
      "minecraft:destructible_by_mining": { "seconds_to_destroy": 1.5 },
      "minecraft:destructible_by_explosion": { "explosion_resistance": 6 },
      "minecraft:map_color": "#7d4dff",
      "minecraft:loot": "loot_tables/blocks/nr_uv_lamp.json",
      // 10 tick ごとに周りの夜型ゾンビを焼く（onTick はスクリプト）
      "minecraft:tick": { "interval_range": [10, 10], "looping": true },
      "nr:uv_light": { "radius": 8 }
    },
    "permutations": [
      { "condition": "q.block_state('nr:lit') == false", "components": { "minecraft:light_emission": 0 } },
      { "condition": "q.block_state('minecraft:cardinal_direction') == 'west'",  "components": { "minecraft:transformation": { "rotation": [0, 90, 0] } } },
      { "condition": "q.block_state('minecraft:cardinal_direction') == 'south'", "components": { "minecraft:transformation": { "rotation": [0, 180, 0] } } },
      { "condition": "q.block_state('minecraft:cardinal_direction') == 'east'",  "components": { "minecraft:transformation": { "rotation": [0, -90, 0] } } }
    ]
  }
}
```

### 4.5 RP: `blocks.json`・`terrain_texture.json`・音

* RP `blocks.json`〔BS:resource_pack/blocks.json〕: `{"<ブロック名>": {"sound": "<音の種類>", "textures": …}, "format_version": "1.21.40"}`。
  カスタムブロックは**見た目を `material_instances` で決める**ので、ここには **`"sound"` だけ**書けばよい
  （DESIGN §1 の `blocks` 断片 `{ "nr:xxx": {"sound": "stone"} }`）。
  vanilla で使われている `sound` の値（抜粋）: `stone` `wood` `metal` `iron` `glass` `cloth` `gravel` `sand` `grass` `snow`
  `chain` `lantern` `scaffolding` `ladder` `anvil` `copper` `netherite` `bone_block` `web` `slime` `honey_block` `mud`
  `deepslate` `tuff` `heavy_core` `vault` `itemframe` `lever`（全 120 種）。
* RP `textures/terrain_texture.json`〔BS〕: `{"resource_pack_name", "texture_name": "atlas.terrain", "padding": 8,
  "num_mip_levels": 4, "texture_data": {"nr_uv_lamp": {"textures": "textures/nr/blocks/uv_lamp"}}}`。
  `material_instances.*.texture` は **このキー**（`nr_uv_lamp`）を指す。配列にすると変種（1.21.120 で正式の
  texture variation）になる。
* ブロックの言語キー: `tile.nr:uv_lamp.name=UV ライト`〔MS:Documents/AddCustomDieBlock.md〕。

---

## 5. レシピ・ルート・スポーン・スポーンエッグ

### 5.1 レシピ

vanilla〔BS:behavior_pack/recipes/iron_sword.json / fire_charge.json〕の形:

<!-- check:recipe -->
```jsonc
{
  "format_version": "1.20.10",
  "minecraft:recipe_shaped": {
    "description": { "identifier": "nr:craft_w_machete" },
    "tags": ["crafting_table"],
    "pattern": [
      "S",
      "S",
      "|"
    ],
    "key": {
      "S": { "item": "nr:scrap" },
      "|": { "item": "minecraft:stick" }
    },
    // レシピ本で解放される条件（アイテムを持つ / "context": "PlayerInWater"）
    "unlock": [ { "item": "nr:scrap" } ],
    "result": { "item": "nr:w_machete" }
  }
}
```

<!-- check:recipe -->
```jsonc
{
  "format_version": "1.20.10",
  "minecraft:recipe_shapeless": {
    "description": { "identifier": "nr:craft_medkit" },
    "tags": ["crafting_table"],
    "ingredients": [
      { "item": "nr:bandage" },
      { "item": "nr:alcohol" }
    ],
    "unlock": [ { "item": "nr:bandage" } ],
    "result": { "item": "nr:medkit", "count": 1 }
  }
}
```

* `tags`: `crafting_table`（作業台）。`ingredients` / `key` の各要素は `{"item": id, "data"?, "count"?}` か
  **`{"tag": "minecraft:coals"}`**（vanilla fire_charge が使っている＝タグでの材料指定は動く。wiki の「タグは使えない」は古い）。
* `priority`（整数）・`assume_symmetry`（shaped）も書ける〔DOC:Recipes〕。
* `unlock` はレシピ本での解放条件。**無いとどうなるか（解放されないのか、content log が出るのか）は UNVERIFIED** →
  vanilla と同じく**必ず書く**。DESIGN の主なクラフトはフォーム（端末）なので、JSON レシピは作業台用の補助。
* 独自の作業台にしたいブロックは `minecraft:crafting_table: {"crafting_tags": [...64 まで], "table_name"}` を持たせ、
  レシピの `tags` にそのタグを書く（shaped/shapeless のみ）。

### 5.2 ルートテーブル

vanilla zombie〔BS:behavior_pack/loot_tables/entities/zombie.json〕の形（抜粋）:

<!-- check:loot -->
```jsonc
{
  "pools": [
    {
      "rolls": 1,
      "entries": [
        {
          "type": "item",
          "name": "nr:scrap",
          "weight": 1,
          "functions": [ { "function": "set_count", "count": { "min": 0, "max": 2 } } ]
        }
      ]
    },
    {
      "rolls": 1,
      "conditions": [ { "condition": "random_chance", "chance": 0.15 } ],
      "entries": [
        { "type": "item", "name": "nr:bandage", "weight": 3 },
        { "type": "item", "name": "nr:alcohol", "weight": 1 },
        { "type": "empty", "weight": 4 }
      ]
    }
  ]
}
```

* `rolls` は数か `{"min","max"}`。`entries[].type` は `item` / `loot_table` / `empty`。
* 関数（〔MS:Documents/LootAndTradeTableFunctions.md〕）: `set_count` `set_damage`（耐久 0〜1）`set_data` `set_name` `set_lore`
  `looting_enchant` `enchant_randomly` `enchant_with_levels` `specific_enchants` `random_aux_value` `explosion_decay` ほか。
* 条件（〔MS:Documents/LootTableConditions.md〕）: `random_chance` `random_chance_with_looting` `killed_by_player_or_pets`
  `random_difficulty_chance` `random_regional_difficulty_chance` `has_variant` `has_mark_variant` `match_tool`。
* **スクリプトからルートを振れる（2.3.0 stable）**: `world.getLootTableManager()`〔DTS:L17544〕の
  `generateLootFromEntity(entity, tool?)`〔DTS:L13298〕/ `generateLootFromBlock` / `…BlockPermutation` / `…BlockType` /
  `…EntityType` が `ItemStack[]` を返す（1.21.110 で公開「Loot Generation APIs」〔MS:Documents/Update1.21.110.md〕）。
  → NR は**ゾンビの BP に `minecraft:loot` を書き、スクリプトの死亡処理で `generateLootFromEntity` を呼んで落とす**のが
  一番素直（spec の `loot` は生成器がこのルートテーブルに変換）。`generateLootFromTable`（任意のテーブル）は**ベータ**。
  `killed_by_player_or_pets` などの条件が「殺した者」無しの呼び出しでどう評価されるかは UNVERIFIED → NR のテーブルでは使わない。
  （script_api.md §16.1 の表は「LootTable 系はベータ」とまとめているが、`LootTableManager` と `generateLootFrom{Entity,Block,…}`
  は 2.3.0 の stable d.ts に在る。ベータなのは `generateLootFromTable` と `LootTable` 型。）

### 5.3 スポーンルール

vanilla zombie〔BS:behavior_pack/spawn_rules/zombie.json〕:

```json
{
  "format_version": "1.8.0",
  "minecraft:spawn_rules": {
    "description": { "identifier": "minecraft:zombie", "population_control": "monster" },
    "conditions": [
      {
        "minecraft:spawns_on_surface": {},
        "minecraft:spawns_underground": {},
        "minecraft:brightness_filter": { "min": 0, "max": 7, "adjust_for_weather": true },
        "minecraft:difficulty_filter": { "min": "easy", "max": "hard" },
        "minecraft:weight": { "default": 100 },
        "minecraft:herd": { "min_size": 2, "max_size": 4 },
        "minecraft:permute_type": [ { "weight": 95 }, { "weight": 5, "entity_type": "minecraft:zombie_villager_v2" } ],
        "minecraft:biome_filter": { "test": "has_biome_tag", "operator": "==", "value": "monster" }
      }
    ]
  }
}
```

条件のキー（〔SCH:server/spawn/1.21.50/Spawn Rules.json〕の全部と型）:

| キー | 形 | メモ（〔MS:…/Definitions/NestedTables/*.md〕） |
|---|---|---|
| `minecraft:spawns_on_surface` / `spawns_underground` / `spawns_underwater` / `spawns_lava` | `{}` | 書くとその場所で湧く |
| `minecraft:brightness_filter` | `{"min": 0〜15, "max": 0〜15, "adjust_for_weather": bool}` | **時刻の条件は無い**。夜だけは「暗さ」で表す（雨で昼も暗くなる） |
| `minecraft:difficulty_filter` | `{"min": "peaceful|easy|normal|hard", "max": …}` | |
| `minecraft:weight` | `{"default": 整数≥0, "rarity"?}` | 同じ枠の中での出やすさ |
| `minecraft:herd` | `{"min_size", "max_size", "event"?, "event_skip_count"?, "initial_event"?, "initial_event_count"?}` | 群れ。最初の N 体だけ別イベント（pillager の隊長） |
| `minecraft:density_limit` | `{"surface": n, "underground": n}`（-1 以上） | この種類の上限数 |
| `minecraft:biome_filter` | フィルタ（`has_biome_tag` など） | タグ: `monster` `overworld` `plains` `desert` … |
| `minecraft:delay_filter` | `{"min", "max", "identifier"(必須), "spawn_chance"(既定 100)}` | pillager_patrol の間隔 |
| `minecraft:height_filter` | `{"min", "max"}` | 高さ |
| `minecraft:world_age_filter` | `{"min"}`（`max` もスキーマにある） | ワールドの経過 tick |
| `minecraft:distance_filter` | `{"min", "max"}`（既定 24 / 128） | プレイヤーからの距離 |
| `minecraft:permute_type` | `[{"weight", "entity_type"?, "min_guaranteed"?}]` | 一部を別の ID（`id<event>` 可）で湧かせる |
| `minecraft:mob_event_filter` | `{"event": "minecraft:pillager_patrols_event"}` 等 | |
| `minecraft:player_in_village_filter` | `{"distance", "village_border_tolerance"}` | |
| `minecraft:spawns_on_block_filter` / `spawns_on_block_prevented_filter` / `spawns_above_block_filter` / `disallow_spawns_in_bubble` / `is_persistent` / `spawn_event` | | |

* `population_control` の枠は `animal` `water_animal` `monster` `cat`（ほか未使用の `villager` `pillager`）〔MS:…/DataDrivenSpawning.md〕。
  `monster` は vanilla の敵と上限を共有する。
* **NR の方針**: 街のゾンビは `zombies/director.js` がスクリプトで出す（昼夜・群れ・上限を制御するため）。
  JSON のスポーンルールは「街の外の自然スポーン」（spec の `where: "overworld"`）だけに付ける。
  ID はエンティティと同じ（`nr:z_xxx`）、ファイルは BP `spawn_rules/nr_z_xxx.json`。

<!-- check:spawn_rules -->
```jsonc
{
  "format_version": "1.8.0",
  "minecraft:spawn_rules": {
    "description": { "identifier": "nr:z_office_worker", "population_control": "monster" },
    "conditions": [
      {
        "minecraft:spawns_on_surface": {},
        "minecraft:brightness_filter": { "min": 0, "max": 7, "adjust_for_weather": true },
        "minecraft:difficulty_filter": { "min": "easy", "max": "hard" },
        "minecraft:weight": { "default": 40 },
        "minecraft:herd": { "min_size": 2, "max_size": 5 },
        "minecraft:density_limit": { "surface": 12 },
        "minecraft:distance_filter": { "min": 24, "max": 64 },
        "minecraft:biome_filter": { "all_of": [
          { "test": "has_biome_tag", "operator": "==", "value": "monster" },
          { "test": "has_biome_tag", "operator": "==", "value": "overworld" }
        ] }
      }
    ]
  }
}
```

### 5.4 スポーンエッグ

* BP `description.is_spawnable: true` でクリエイティブにエッグが出る（§1.1）。
* 色・絵は **RP の client_entity** の `description.spawn_egg`〔DOC:Entities「Spawn Egg」〕:
  `{"base_color": "#53443E", "overlay_color": "#2E6854"}` か `{"texture": "<item_texture のキー>", "texture_index": 0}`。
* 名前の言語キー: **`item.spawn_egg.entity.nr:z_office_worker.name=…`**、エンティティ名は `entity.nr:z_office_worker.name=…`
  〔MS:Documents/IntroductionToAddEntity.md L190–L200〕（vanilla は `item.spawn_egg.entity.zombie.name`〔BS:resource_pack/texts/en_US.lang〕）。
* エッグのアイテム ID（`/give` 用）が `nr:z_office_worker_spawn_egg` になるかは UNVERIFIED。テストは `/summon` か
  `dimension.spawnEntity` で行う。

---

## 6. `.mcstructure`（構造物ファイル）

### 6.1 置き場所と ID

〔WIKI:nbt/mcstructure.md〕: `BP/structures/<名前空間>/<パス>.mcstructure` → ID `<名前空間>:<パス>`
（`BP/structures/stuff/towers/diamond.mcstructure` → `stuff:towers/diamond`）。`structures/` 直下は `mystructure:` になる。
NR は `BP/structures/nr/<key>.mcstructure` → `nr:<key>`（script_api.md §8 と同じ）。

### 6.2 NBT の基本（Bedrock の `.mcstructure`）

* **リトルエンディアン・無圧縮**の NBT（Java の `.nbt` はビッグエンディアン＋gzip）。ファイルはヘッダ無しで、
  **ルートの TAG_Compound（名前は空文字列）から直接始まる**（実物 29 個で確認。§6.4）。
* タグ: `0 End` `1 Byte(i8)` `2 Short(i16)` `3 Int(i32)` `4 Long(i64)` `5 Float(f32)` `6 Double(f64)` `7 ByteArray`
  `8 String(u16 長さ + UTF-8)` `9 List(要素の型 1B + i32 個数 + 中身)` `10 Compound(名前付きタグ … End)` `11 IntArray` `12 LongArray`。
  名前付きタグ = 型 1B + 名前（String と同じ形）+ 中身。**空のリストの要素型は `End(0)`**（実物 29 個のうち `entities` が
  空の 24 個は全部 `End`、中身のある 5 個は `Compound(10)`。チェストの空の `Items` も `End`）→ 見本も空は `End` で書く。

### 6.3 ルートの木（型付き）

〔WIKI:nbt/mcstructure.md〕＋実物 29 個〔MCS〕の読み取り結果。**キーの並びも実物の順**:

```text
TAG_Compound ""                                   ルート（名前は空）
├ TAG_Int      format_version = 1
├ TAG_List<Int> size = [sx, sy, sz]
├ TAG_Compound structure
│ ├ TAG_List<List<Int>> block_indices = [ 層0, 層1 ]   2 本ちょうど。どちらも長さ sx*sy*sz
│ ├ TAG_List<Compound>  entities                       エンティティの NBT（ワールド保存と同じ形）。空でよい
│ └ TAG_Compound palette
│   └ TAG_Compound default                             名前付きパレットは default だけが読まれる
│     ├ TAG_List<Compound> block_palette               ブロックの並び（下）
│     └ TAG_Compound block_position_data              { "<層0の通し番号>": { block_entity_data: {...}, tick_queue_data?: [...] } }
└ TAG_List<Int> structure_world_origin = [x, y, z]     保存した時のワールド座標（エンティティの位置の換算にだけ使う）

block_palette の 1 件:
TAG_Compound { TAG_String name = "minecraft:stone_bricks",
               TAG_Compound states = { 状態名: 値 }   ← 文字列状態=TAG_String、整数状態=TAG_Int、真偽状態=TAG_Byte(0/1)
               TAG_Int version = 18168865 }
```

* **`version`（ブロックの互換版）**: 実物で見た値と出現数 — `18168865`(0x01153C21 = **1.21.60.33**) 50、`18163713`(1.21.40.1) 41、
  `18161159`(1.21.30.7) 120、`18095650`(1.20.30.34) 31、`17959425`(1.18.10.1) 53、`17825808`(1.16.0.16) 9。
  4 バイトを上位から読むと版番号になる。wiki は「As of **1.26.30**, this version is set to 18168865」と書いている
  （= 1.21.60 以降ブロック形式の版は上がっていない）→ **NR は `18168865` を書く**。古い値で書くと読み込み時に古い名前・状態から
  変換される（`planks`+`wood_type` のような古い名前の実物もこれで読める）が、新しい名前（`oak_planks` 等）を古い版で書くのは避ける。
* 状態の型は実物で確認（`upside_down_bit`=Byte、`weirdo_direction`=Int、`minecraft:cardinal_direction`=String、
  `open_bit`=Byte、`facing_direction`=Int、`pillar_axis`=String）。**カスタムブロックの状態もそのまま入る**
  （実物に `mike:palm_leave_tip` の `minecraft:cardinal_direction` がある）。
* **1.21.120 の正しいブロック名と状態**は〔VD:mojang-blocks.json〕（1,307 ブロック、`data_items[].properties` と
  `block_properties[]` の値一覧）で引く。例: `minecraft:stone_bricks` `minecraft:oak_planks` `minecraft:gray_concrete`
  `minecraft:smooth_stone_slab`（状態 `minecraft:vertical_half`）`minecraft:oak_stairs`（`upside_down_bit` `weirdo_direction`）
  `minecraft:iron_bars` `minecraft:glass_pane` `minecraft:barrier` `minecraft:structure_void` `minecraft:light_block_15`
  `minecraft:grass_path`（1.21.120 ではまだ `dirt_path` ではない）。**`stonebrick` `planks` `concrete` `log` は 1.21.120 では無い名前**。

### 6.4 並び順の式

* `block_indices` の各層は **x → y → z の入れ子で z が一番速く回る**（wiki: 「proceeds in ZYX order」、2×3×4 の例 `0 0 0`,
  `0 0 1`, `0 0 2`, `0 0 3`, `0 1 0`, …）:

  **`index = (x * sy + y) * sz + z`**（x, y, z は構造物の最小の角からの相対座標）

* 検証: 実物 29 個の `block_position_data` にあるブロックエンティティ 66 個すべてで、`block_entity_data` の
  ワールド座標 − `structure_world_origin` をこの式に入れた値がキーの番号と一致し、層0のそのパレットが
  そのブロック（`minecraft:jigsaw` `minecraft:chest` `minecraft:bed` …）だった（`mcstructure_test/verify_order.py`）。
* 値 `-1` = structure void（置かない＝既存のブロックを残す）。層1（水没などの重ね置き）は普通は全部 `-1`。
  実物 29 個は層1が全部 `-1`、層0に `-1` は無かった。
* 読み込み失敗の条件（wiki が実験で記録）: `block_indices` が 2 本でない、2 本の長さが違う、長さ ≠ sx*sy*sz、
  決まった名前のタグが無いか型違い → content log のエラーで読み込まれない。パレット範囲外の番号は air になる。

### 6.5 Python の見本（検査済み）

依存なし。`blocks` に書かない座標は air、`None` は void。**この関数をそのまま `gen_nr_structures.py` に写してよい**。

```python
import struct

BLOCK_VERSION = 18168865  # 0x01153C21 = 1.21.60.33（v1.21.120 時点の実物と同じ。§6.3）


def _s(b, text):                      # TAG_String の中身（u16 長さ + UTF-8）
    raw = text.encode("utf-8")
    b += struct.pack("<H", len(raw)) + raw


def _tag(b, tag_id, name):            # 名前付きタグの頭（型 1 バイト + 名前）
    b.append(tag_id)
    _s(b, name)


def _int_list(b, name, values):       # TAG_List<TAG_Int>
    _tag(b, 9, name)
    b.append(3)
    b += struct.pack("<i", len(values))
    b += struct.pack("<%di" % len(values), *values)


def _states(b, states):               # TAG_Compound "states"
    _tag(b, 10, "states")
    for k, v in states.items():
        if isinstance(v, bool):
            _tag(b, 1, k); b += struct.pack("<b", int(v))
        elif isinstance(v, int):
            _tag(b, 3, k); b += struct.pack("<i", v)
        else:
            _tag(b, 8, k); _s(b, str(v))
    b.append(0)


def write_mcstructure(path, size, blocks, fill="minecraft:air"):
    sx, sy, sz = size
    palette, keys, layer0 = [], {}, []
    for x in range(sx):                # 並びは x → y → z（z が最も速く回る）
        for y in range(sy):
            for z in range(sz):
                name, states = blocks.get((x, y, z), (fill, {}))
                if name is None:
                    layer0.append(-1)  # structure void（置かない＝既存ブロックを残す）
                    continue
                key = (name, tuple(sorted(states.items())))
                if key not in keys:
                    keys[key] = len(palette)
                    palette.append((name, dict(states)))
                layer0.append(keys[key])
    b = bytearray()
    _tag(b, 10, "")                                   # ルート（名前は空）
    _tag(b, 3, "format_version"); b += struct.pack("<i", 1)
    _int_list(b, "size", [sx, sy, sz])
    _tag(b, 10, "structure")
    _tag(b, 9, "block_indices"); b.append(9); b += struct.pack("<i", 2)
    for layer in (layer0, [-1] * len(layer0)):        # 名前なしの List<Int> を 2 本
        b.append(3); b += struct.pack("<i", len(layer)); b += struct.pack("<%di" % len(layer), *layer)
    _tag(b, 9, "entities"); b.append(0); b += struct.pack("<i", 0)    # 空のリスト（実物は要素型 End=0）
    _tag(b, 10, "palette")
    _tag(b, 10, "default")
    _tag(b, 9, "block_palette"); b.append(10); b += struct.pack("<i", len(palette))
    for name, states in palette:
        _tag(b, 8, "name"); _s(b, name)
        _states(b, states)
        _tag(b, 3, "version"); b += struct.pack("<i", BLOCK_VERSION)
        b.append(0)                                   # パレット 1 件の終わり
    _tag(b, 10, "block_position_data"); b.append(0)   # ブロックエンティティ無し
    b.append(0)                                       # default の終わり
    b.append(0)                                       # palette の終わり
    b.append(0)                                       # structure の終わり
    _int_list(b, "structure_world_origin", [0, 0, 0])
    b.append(0)                                       # ルートの終わり
    with open(path, "wb") as fh:
        fh.write(b)


write_mcstructure("tiny.mcstructure", (3, 2, 2), {
    (0, 0, 0): ("minecraft:stone_bricks", {}),
    (1, 0, 0): ("minecraft:oak_stairs", {"weirdo_direction": 2, "upside_down_bit": False}),
    (2, 0, 1): ("nr:barricade", {"minecraft:cardinal_direction": "east"}),
    (2, 1, 1): (None, {}),
})
```

検査（`build_preview/nr_research/mcstructure_test/test_sketch.py`。読み手は別に書いた `nbt_le.py`）:
1. 書いた 595 バイトを読み、**全バイトを消費**し、書き直すと**バイト一致**。ルートのキーの順と型、`size`、層の長さ 12、
   層1が全部 -1、空の `entities` が `List<End>`、全パレットの `version` = 18168865、`(x*sy+y)*sz+z` で引いたブロックと
   状態の型（Byte/Int/String）が期待どおり。
2. `nbt_le.py` 自体は実物 29 個を**読み→書きでバイト一致**させて確認済み。
3. ブロックエンティティもエンティティも無い実物 9 個を読み、見本の関数で書き直して**同じ配置**になることを確認。

**順序の注意**: 見本はパレットの状態キーを `sorted` で同一視しているが、書く順は最初に出た時の辞書の順。
決定的な出力（DESIGN §0）のため、生成器は `blocks` を決まった順で作ること（`dict` の挿入順を固定）。

### 6.6 置き方と大きさ

* スクリプト（script_api.md §8）: `world.structureManager.place("nr:apartment_a", dim, {x, y, z}, {rotation, mirror,
  includeEntities, includeBlocks, integrity, integritySeed, animationMode, animationSeconds, waterlogged})`。
  **読み込まれていないチャンクへの place は読み込みまで保留される**。メモリ上に作るなら `structureManager.createEmpty(id, size)`
  〔DTS:L16504〕。ワールドから切り出す `createFromWorld` は「Throws if the structure bounds exceed the maximum size」
  〔DTS:L16527 付近〕だが、最大値の数字は d.ts に無い。
* コマンド〔CMD〕: `/structure load <name> <to: x y z> [rotation: 0_degrees|90_degrees|180_degrees|270_degrees]
  [mirror: none|x|z|xz] [animationMode: block_by_block|layer_by_layer] [animationSeconds] [includeEntities] [includeBlocks]
  [waterlogged] [integrity] [seed]`（チート必要、権限 1）。
* 大きさ: 構造物ブロックで**保存**できるのは 64×(高さ)×64 まで（wiki「64×256×64」は旧世界高の記述。1.18 以降の高さの上限は
  UNVERIFIED）。wiki の実験では「`size` がその上限を超えた**ファイルでも読み込める**」。ただし 1.20.50 以降の挙動は未確認 →
  **NR の建物モジュールは 1 個 64×64×64 以内**（高い建物は縦に分けて重ねる）、ブロック数は 1 個 ≤ 100 万を目安。
* 回転は「構造物の原点（最小の角）」まわり（wiki の地物の説明。script の place でも同じかは UNVERIFIED。script_api.md §8 の注）。
  `structures.js` の markers も生成器が同じ規則で回す。

### 6.7 ブロックエンティティ・エンティティを入れる場合（任意）

* 実物のチェスト: `block_position_data["<番号>"].block_entity_data = {Findable: Byte 0, Items: List<Compound>[{Count: Byte,
  Damage: Short, Name: String, Slot: Byte, WasPickedUp: Byte}], id: "Chest", isMovable: Byte 1, x: Int, y: Int, z: Int}`
  （x/y/z は保存時のワールド座標。「Position tags are saved but replaced upon loading」）。
* チェストにルートテーブルを結び付ける NBT（`LootTable` / `LootTableSeed` と思われる）は実物で確認できなかった → UNVERIFIED。
  **NR はチェストを空で置き、スクリプトが place の後に中身を入れる**（`block.getComponent("minecraft:inventory").container`）。
* エンティティは `{identifier, definitions: ["+nr:z_x", "+nr:alive", …], Pos: List<Float>, Rotation, UniqueID: Long, …}` の
  大きな NBT（実物の zombie は 63 キー）。**NR は入れない**（ゾンビ・車はスクリプトが markers に出す。DESIGN §8）。

---

## 7. 地物ルール / `structure_template_feature`（任意。小さな廃墟を自然に置く）

〔DOC:Features〕と〔MCS:chill_oasis_biome〕の実物:

<!-- check:feature -->
```jsonc
{
  "format_version": "1.13.0",
  "minecraft:structure_template_feature": {
    "description": { "identifier": "nr:ruin_small_a" },
    "structure_name": "nr:ruin_small_a",
    "adjustment_radius": 4,
    "facing_direction": "random",
    "constraints": {
      "grounded": {},
      "unburied": {},
      "block_intersection": { "block_allowlist": ["minecraft:air", "minecraft:short_grass", "minecraft:tall_grass"] }
    }
  }
}
```

<!-- check:feature_rules -->
```jsonc
{
  "format_version": "1.13.0",
  "minecraft:feature_rules": {
    "description": { "identifier": "nr:ruin_small_a_rule", "places_feature": "nr:ruin_small_a" },
    "conditions": {
      "placement_pass": "surface_pass",
      "minecraft:biome_filter": [
        { "test": "has_biome_tag", "operator": "==", "value": "overworld" },
        { "test": "has_biome_tag", "operator": "==", "value": "plains" }
      ]
    },
    "distribution": {
      "iterations": 1,
      "scatter_chance": { "numerator": 1, "denominator": 40 },
      "x": { "distribution": "uniform", "extent": [0, 15] },
      "y": "query.heightmap(variable.worldx, variable.worldz)",
      "z": { "distribution": "uniform", "extent": [0, 15] }
    }
  }
}
```

* `structure_template_feature`〔DOC のスキーマ〕: `structure_name`（必須）、`adjustment_radius`（**0〜16**、既定 0。条件を満たす位置を
  この半径で探す）、`facing_direction`（`north|south|east|west|random`、既定 random）、`constraints`（`grounded` / `unburied` /
  `block_intersection.block_allowlist`（旧名 `block_whitelist`））。条件を満たす位置が無ければ置かれない。
  **他のパックの構造物も参照できる**。
* 地物ルール: `description.places_feature`、`conditions.placement_pass`（必須。`surface_pass` など）、`minecraft:biome_filter`、
  `distribution`（`iterations` `scatter_chance` `coordinate_eval_order` と `x/y/z` の分布 `uniform|gaussian|inverse_gaussian|
  triangle|fixed_grid|jittered_grid`）。ファイル名は ID の名前部分と一致させる。
* **制約**: 「Due to constraints in the feature system, **large structures may need to be pre-sliced** into smaller structures」・
  「rotations occur around the structure origin, not the center, so large structures **may be cut off** in random rotation」
  〔WIKI:world-generation/feature-types.md〕。地物が書ける範囲の正確な大きさは UNVERIFIED → **自然配置の廃墟は 16×16 以内**、
  回転で欠けるなら `facing_direction` を固定する。`facing_direction` が south 以外だと**回転しない状態のブロック**（つた等）が
  向きを変えない（同）。
* `scatter_chance` は「an expression or an object with a numerator and denominator」（どちらも 1 以上の整数）
  〔SCH:client_server/world_components/1.21.10/Scatter Chance.json〕。地物の側（scatter_feature）では `10.0` のような数で書く例もある〔MCS〕。
  **街そのものは DESIGN §8 の通りスクリプト（`/scriptevent nr:city`）で組む**。地物は「街の外に転がる小物」専用。
* 試すとき: `/place feature nr:ruin_small_a`・`/place featurerule nr:ruin_small_a_rule`〔CMD〕。

---

## 8. 霧と `/fog`、カメラのプリセット

### 8.1 霧の定義（RP `fogs/*.json`）

〔DOC:Fogs〕のスキーマ＋vanilla〔BS:resource_pack/fogs/default_fog_setting.json〕:

<!-- check:fog -->
```jsonc
{
  "format_version": "1.16.100",
  "minecraft:fog_settings": {
    "description": { "identifier": "nr:night_city" },
    "distance": {
      // 夜の街: 暗い青緑の霧を近くから。render_distance_type "fixed" はブロック単位、"render" は描画距離に対する割合
      "air":     { "fog_start": 6.0,  "fog_end": 56.0, "fog_color": "#0b1418", "render_distance_type": "fixed" },
      "weather": { "fog_start": 4.0,  "fog_end": 40.0, "fog_color": "#0a1013", "render_distance_type": "fixed" },
      "water": {
        "fog_start": 0.0, "fog_end": 18.0, "fog_color": "#0f2a2a", "render_distance_type": "fixed",
        "transition_fog": {
          "init_fog": { "fog_start": 0.0, "fog_end": 0.01, "fog_color": "#0f2a2a", "render_distance_type": "fixed" },
          "min_percent": 0.25, "mid_seconds": 5, "mid_percent": 0.6, "max_seconds": 30
        }
      }
    }
  }
}
```

* `distance` の下に `air` `weather` `water` `lava` `lava_resistance`（どれも任意）。各々 `fog_color` `fog_start` `fog_end`
  （**start ≤ end**）`render_distance_type`（`fixed` = ブロック、`render` = 描画距離に掛ける）`transition_fog`（水に入った時の
  移り変わり）。ほかに `volumetric`（`density` / `media_coefficients` ほか。立体霧の描画向け、任意。NR は使わない）。
* **霧の重なり（active fog stack）**: 下から エンジン既定 → データ既定（`biomes_client.json` の `default`）→ バイオーム →
  **コマンド層**。上から順に探し、その設定値を持つ最初の霧が使われる（無い値は下へ）〔DOC:Fogs〕。
* `/fog`〔CMD〕: **`/fog <対象> push <霧ID> <自分で付ける名前>`**、**`/fog <対象> pop <名前>`**（その名前の一番上を外す）、
  **`/fog <対象> remove <名前>`**（その名前を全部外す）。チート必要、権限 1。「Fog settings in this layer are saved and then
  restored on world load per player」→ **ワールドを開き直しても残る**ので、外し忘れに注意。
  スクリプトからは `player.runCommand("fog @s push nr:night_city nr_night")`（霧の専用 API は 2.3.0 stable に無い）。
  NR は `nr_night` などの名前を固定し、昼に `remove` する。

### 8.2 カメラのプリセット（BP `cameras/presets/*.json`）

〔MS:Documents/CameraSystem/CameraCommandIntroduction.md〕: BP の `cameras/presets/` に置く。

<!-- check:camera -->
```jsonc
{
  "format_version": "1.21.0",
  "minecraft:camera_preset": {
    "identifier": "nr:finisher",
    "inherit_from": "minecraft:free",
    // プレイヤーの状態（暗視・盲目など）を映すか。既定 false
    "player_effects": true,
    "listener": "player"
  }
}
```

* キー: `identifier`（名前空間付き、`minecraft` 以外）、`inherit_from`（`minecraft:free` か別のカスタムプリセット。
  MS は「For now, the other built-in camera perspectives can't be specified here」と書くが follow_orbit を継承する例も同じ文書群にある）、
  `pos_x/y/z` `rot_x`(−90〜90)/`rot_y`、`player_effects`、`listener`（`"player"`）、ターゲット追従系 `rotation_speed`
  `snap_to_target` `horizontal_rotation_limit` `vertical_rotation_limit` `continue_targeting` `tracking_radius`、
  三人称系 `view_offset` `entity_offset` `radius`。
* 1.21.120 の組み込みプリセット〔VD:mojang-camera-presets.json〕: `minecraft:first_person` `minecraft:third_person`
  `minecraft:third_person_front` `minecraft:free` `minecraft:fixed_boom` `minecraft:follow_orbit` `minecraft:control_scheme_camera`。
  `follow_orbit` / `fixed_boom` は MS の文書に「実験（Creator Cameras: New Third Person Presets）」と残っているが、1.21.90 の更新で
  `/controlscheme` と組んで使える旨が書かれ、2.3.0 stable の d.ts に `CameraFixedBoomOptions` がある → **実験無しで使えるかは UNVERIFIED**。
* `/camera`〔CMD〕: `set <preset> [ease <秒> <easing>] [pos …] [rot …] [facing …]`、`clear`、
  `fade [time <in> <hold> <out>] [color <r> <g> <b>]`、`fov_set <値> [秒] [easing]` / `fov_clear`、`attach_to_entity` 等。
  easing は `linear` `spring` `in_quad` … `in_out_elastic`（32 種）。スクリプトは `player.camera.*`（script_api.md §5.2）。
* **NR の方針**: 画面の揺れ・血の赤は `camera.fade` と短い `setFov`。カメラを奪う演出（とどめの一撃）は `minecraft:free`
  を元にしたプリセットで、必ず `clear()` で戻す。カスタムプリセットは無くても作れるので、作るなら `nr:finisher` 1 個だけ。

---

## 9. 生成器のためのチェックリスト

**全般**
- [ ] `format_version` は §0.1 の表どおり。素の JSON（コメント無し）で書く。
- [ ] ID は DESIGN §2。プロパティ・グループ・イベント・カスタムコンポーネントは全部 `nr:` 名前空間。
- [ ] 決定的な出力（並びを固定した dict、`random.Random(seed)`）。

**エンティティ（`gen_nr_entities.py`）**
- [ ] コンポーネント名は〔SCH:server/entity/1.21.120/ActorDefinitions.json〕の `properties` に在るものだけ。
- [ ] プロパティは 32 個以下、enum は 16 値以下・各 1〜32 文字・英字始まり・英数と `_` のみ。`int`/`float` に `range`。default が範囲内。
- [ ] **切り替える値（速さ・当たり箱・センサー・hit test）は基本 `components` に置かない**。排他グループだけに置き、
      イベントは `sequence: [{remove: 全部}, {add: 一つ}]`。基本と同じ名前のコンポーネントをグループに入れない（`nr:dead` も例外にしない）。
- [ ] 全ゾンビ・gib・飛び道具・小道具に `nr:despawn`（`instant_despawn`）。ゾンビに DESIGN §12 の 7 イベント全部。
- [ ] `melee_box_attack` を使う（`melee_attack` を使わない）。`minecraft:attack` を必ず添える。
- [ ] `navigation.*` に `can_path_over_damage_blocks` を書かない（存在しない）。罠を避けさせるなら `avoid_damage_blocks`。
- [ ] `damage_sensor` の `deals_damage` は `"yes"|"no"|"no_but_side_effects_apply"`、`cause` は snake_case。
- [ ] `custom_hit_test.hitboxes` の `pivot` は箱の中心、x/z は 0。`collision_box` の幅は正方形。
- [ ] ボスは `minecraft:boss` を付けるなら体力の写し（§1.4.7）をスクリプト側に依頼する。
- [ ] `runtime_identifier` を付けない。
- [ ] `minecraft:loot` はスクリプトの `generateLootFromEntity` 用。条件 `killed_by_player*` は使わない。

**飛び道具**
- [ ] `minecraft:projectile` の `on_hit` は §2.1 の表のキーだけ。種類ごとの後処理が要る弾は `remove_on_hit` を付けない。
- [ ] `collision_box` 0.25 前後、`conditional_bandwidth_optimization` は snowball と同じ値。

**アイテム（`gen_nr_items.py` / `gen_nr_weapons.py`）**
- [ ] コンポーネント名は §3.2 の一覧だけ。`minecraft:weapon` `custom_components` `kinetic_weapon` `cooldown.type` を書かない。
- [ ] `minecraft:icon` は文字列（`item_texture.json` のキー）か `{"textures": {"default": …}}`。
- [ ] `max_stack_size` 1〜64。動的プロパティ・耐久を持つものは 1。`minecraft:damage` は 0〜255。
- [ ] 武器には `nr:weapon` を付け、スクリプトの `onBeforeDurabilityDamage` で 0 にする（耐久はスクリプトが一元管理）。
- [ ] `display_name.value` は `item.nr:<id>`、lang にも同じキー。
- [ ] `menu_category.group` は名前空間付き（`minecraft:itemGroup.name.*` か `item_catalog` で作った `nr:itemGroup.*`）。

**ブロック（`gen_nr_blocks.py`）**
- [ ] コンポーネント名は §4.3 の表だけ。`events`・`on_*` トリガー・`unit_cube`・`minecraft:sound`・`emissive`・
      配列の `collision_box`・`n_way_visual_rotation` を書かない。
- [ ] `collision_box` / `selection_box` は 1 個、(-8,0,-8)〜(8,16,8) の内。モデルは 30×30×30 px 以内。
- [ ] 状態は 1 つ 16 値以下、組み合わせ 65,536 以下。permutation の条件が参照する状態は `states` か `traits` に在る。
- [ ] `material_instances` の render_method を全インスタンスで揃える。`texture` は `terrain_texture.json` のキー。
- [ ] 踏んで発動する罠は当たり箱の高さ ≥ 4px（`onStepOn` の条件）。`onTick` には `minecraft:tick`。
- [ ] RP `blocks.json` の断片は `{"nr:xxx": {"sound": "<§4.5 の値>"}}`、lang は `tile.nr:xxx.name`。

**レシピ・ルート・スポーン**
- [ ] レシピに `tags` と `unlock` を必ず書く。結果は `{"item", "count"}`。
- [ ] ルートの `entries[].type` は `item|loot_table|empty`、名前は実在の ID。
- [ ] スポーンルールの ID = エンティティ ID、`population_control` は `monster`。条件キーは §5.3 の表だけ。夜は `brightness_filter`。
- [ ] RP client_entity に `spawn_egg`、lang に `entity.<id>.name` と `item.spawn_egg.entity.<id>.name`。

**構造物（`gen_nr_structures.py`）**
- [ ] §6.5 の関数で書く。`version` = 18168865、ブロック名と状態は〔VD:mojang-blocks.json〕に在るもの（カスタムは `nr:`）。
- [ ] 状態の型: bool → Byte、int → Int、文字列 → String。
- [ ] 1 個 64×64×64 以内。`block_indices` は 2 本・同じ長さ・`sx*sy*sz`。エンティティは入れない。
- [ ] 書いた後に自前の読み手で読み戻して数を確かめる（`test_nr.py` に入れる）。

**霧・カメラ**
- [ ] 霧は `fog_start ≤ fog_end`、`render_distance_type` は `fixed|render`。ID は `nr:` 付き。
- [ ] `/fog push` した名前は必ず `remove` する場所がある（ワールドに保存されるため）。
- [ ] カメラは `set` したら必ず `clear`。

---

## 10. UNVERIFIED の一覧（推奨のやり方つき）

| # | 内容 | 推奨 |
|---|---|---|
| U1 | `deals_damage: "no"` の死体・gib に近接が当たった時、`entityHitEntity` が来るか | 来なければプレイヤーの視線レイ（DESIGN §4 の部位判定と同じ）で代わりに判定 |
| U2 | `no_but_side_effects_apply` で `entityHurt` が来るか | 使わない（`yes` か `no`） |
| U3 | `custom_hit_test` の pivot の x/z がエンティティの向きで回るか | x/z = 0 だけ使う |
| U4 | `scale` が当たり箱にも効くか | scale は 1 固定。大きさは geometry と collision_box で |
| U5 | `setCurrentValue` で `minecraft:movement` の `max` を超えた値が丸められるか | 速さの変更はグループで。スクリプトで変えるなら JSON に `max` を書く |
| U6 | ボスバーの名前（`minecraft:boss.name` 省略時・`nameTag` 時） | 実機で確認。HUD（DESIGN §7）に名前を出せば困らない |
| U7 | `navigation.climb` でカスタムエンティティが spider のように壁を登るか | 壁登りはスクリプト（`zombies/ai.js`）を主にする |
| U8 | `leap_at_target.target_dist`（cat が使うが DOC に無い） | 使わない |
| U9 | `minecraft:projectile` の `anchor` `hit_ground_sound` `stop_on_hurt` の意味 | vanilla の値を写すだけ |
| U10 | `remove_on_hit` の弾の typeId を `projectileHit*` で読めるか | 後処理の要る弾は `remove_on_hit` を付けない |
| U11 | 近接ダメージ = 素手 1 + `minecraft:damage` か | NR のゾンビには関係なし（スクリプト計算）。vanilla 相手の値は実機で調整 |
| U12 | 耐久の自動の減り幅（wiki は 2） | フックで 0 にしてスクリプト管理 |
| U13 | 溜め投げに `use_modifiers` が要るか | 溜め無しで作る |
| U14 | レシピの `unlock` が無い時の挙動 | 必ず書く |
| U15 | `generateLootFromEntity` での `killed_by_player*` 条件の評価 | 使わない |
| U16 | スポーンエッグのアイテム ID | `/summon` でテスト |
| U17 | `onStepOn` の「当たり箱 3.2px より高い」条件が 1.21.120 でも同じか | 罠の当たり箱を 4px 以上に |
| U18 | 構造物の保存の高さ上限・巨大ファイルの読み込み | 1 個 64×64×64 以内 |
| U19 | `structureManager.place` の回転の中心 | 生成器とスクリプトで同じ規則を一か所に（structures.js の markers） |
| U20 | チェストのルートテーブル NBT（`LootTable`） | 空で置いてスクリプトが中身を入れる |
| U21 | 地物が書ける範囲の大きさ | 自然配置は 16×16 以内。街はスクリプト |
| U22 | `follow_orbit` / `fixed_boom` が実験無しで使えるか | 使うなら実機確認。NR は `minecraft:free` 基準 |
| U23 | `is_collidable` の上限 | 使わない（バリアブロック） |
| U24 | `runtime_identifier` の効果（wiki の記録） | 付けない |

---

## 11. この文書の検査のしかた

`<!-- check:<種類> -->` の直後のコードブロックを抜き出し、コメントを除いて JSON として読み、種類ごとに検査する
（研究用の道具。`build_preview/` は gitignore なのでリポジトリには入らない）:

```text
python3 -I build_preview/nr_research/content_check/check_content_md.py tools/nightrunner/reference/content.md
python3 -I build_preview/nr_research/mcstructure_test/test_sketch.py build_preview/nr_research/content/mcsamples
```

検査の中身:
* entity: コンポーネント名が〔SCH:server/entity/1.21.120/ActorDefinitions.json〕に在る／プロパティの上限（32・16・1〜32 文字・
  英字始まり・既定値が範囲内）／イベントが参照するグループ・プロパティ・enum 値が在る／**基本とグループで同じコンポーネントが無い**／
  `deals_damage` と `cause` の値／イベントの `sequence` が remove を add より先に書いている。
* item: コンポーネント名が〔SCH:server/item/1.21.110/ItemObject.json〕に在るか名前空間付きのカスタム／`menu_category` の値／
  `max_stack_size` 1〜64／`damage` 0〜255。
* block: コンポーネント名が §4.3 の一覧に在るか名前空間付きのカスタム／当たり箱・選択箱の範囲／光 0〜15／状態 16 値以下・
  組み合わせ 65,536 以下／permutation の条件が参照する状態が在る。
* spawn_rules: 条件キーが〔SCH:server/spawn/1.21.50/Spawn Rules.json〕に在る／明るさ 0〜15。
* recipe・loot・feature・feature_rules・fog・camera・item_catalog: 必須キーと値の範囲（fog は start ≤ end）。
