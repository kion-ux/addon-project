# 描画リファレンス — NIGHT RUNNER の RP が「起動せずに」正しく描かれるための根拠集

Minecraft を起動して確かめられないので、**Mojang の公式サンプルの実ファイル・公式ドキュメント・
Mojang のバリデータのソース**を証拠として読み、そこから生成器の規則を決める。
DESIGN.md §3 の「要確認事項」（part_visibility は子に伝わるか）の答えもここに書く。

## 凡例

| 記号 | 意味 |
|---|---|
| ✅ | **確認済み**: バニラの実ファイル（`Mojang/bedrock-samples`）か公式ドキュメント／公式メタデータに書いてある |
| 🟡 | **準拠**: コミュニティ資料（bedrock.dev wiki）・旧版バニラ（RenderDragon 以前）のシェーダ／マテリアル・Mojang のツールのソース。強い状況証拠 |
| ❓ | **UNVERIFIED**: 証拠を見つけられなかった。推奨値を書いてあるので、それに従い、実機で確かめるまで「安全側」に倒す |

## 証拠の置き場所（すべて gitignore 済みの `build_preview/nr_research/`）

| 略記 | 中身 | 出どころ |
|---|---|---|
| `BS/` | `bedrock-samples/`（バニラ RP/BP・公式ドキュメント JSON・Molang クエリ表・Script API メタデータ） | https://github.com/Mojang/bedrock-samples （`main` = **1.26.50.4**、commit `46ba6ea`） |
| `BS/metadata/doc_modules/*.json` | 公式ドキュメント本体（animations / molang / schemas …）。読みやすく平文にしたものが `docs_txt/*.txt` | 同上 |
| `MAT/entity.material` | 旧版バニラの `materials/entity.material`（v1.16.201） | https://github.com/ZtechNetwork/MCBVanillaResourcePack/blob/8fdcc0ad0465ae4c466441ef0d5a616f0f1cc33d/materials/entity.material |
| `SHADER/entity.fragment` | 旧版バニラ GLSL `entity.fragment` の写し（第三者リポジトリに残っていたもの） | https://github.com/lonelyang/SlimeChunkDisplay/blob/HEAD/shaders/glsl/entity.fragment |
| `MS/` | Microsoft Learn の原稿（`MicrosoftDocs/minecraft-creator`、commit `4432fb6`, 2026-10-20） | https://github.com/MicrosoftDocs/minecraft-creator |
| `WIKI/` | bedrock.dev wiki の原稿（commit `657b405`, 2026-10-24） | https://github.com/Bedrock-OSS/bedrock-wiki （公開版 https://wiki.bedrock.dev ） |
| `MCTOOLS/TextureImageInfoGenerator.ts` | Mojang 製 Minecraft Creator Tools のテクスチャ検証（予算の数値） | https://github.com/Mojang/minecraft-creator-tools/blob/main/app/src/info/projectGenerators/textureImageInfo/TextureImageInfoGenerator.ts |

> 注: RenderDragon（1.18.30 以降の全機種）では `.material` ファイルも GLSL もパックから差し替えられない。
> `MAT/` と `SHADER/` は「マテリアル名が何をするか」を知るための旧版の証拠で、名前と挙動は今も同じだと
> 公式ドキュメント（`MS/creator/Documents/material-files.md`, 2025-11-25）が同じ一覧で説明している。

---

## 0. 要点（先に結論）

1. **part_visibility は子へ伝わらない（ボーンごと）**。親を隠しても、子に `true` が当たっていれば子は描かれる。
   → DESIGN.md §3 の「ボーンを隠すと子も隠れる」は**誤り**。すべてのボーンに「自分と全祖先の条件の AND」を
   書くことが**必須**（`nr_rig.visibility_rules()` は既にそうしている）。ただし**隠したボーンの変換（回転・移動）は子へ伝わる**。
2. `q.property('nr:x')` は render controller・animation controller・client entity の scripts で使える（バニラに実例）。
   enum は `== 'cut_upper'` の文字列比較、int/bool は数値。
3. 光る目は `entity_emissive_alpha`。**アルファ 255 = 普通に照らされる、0<α<255 = (1−α/255) だけ発光、
   RGBA=(0,0,0,0) だけが透明（捨てられる）**。α=0 でも RGB≠0 なら「不透明で全発光」になる。
4. `entity_alphatest_one_sided` という名前は**存在しない**（どこにも無い）。片面にしたいなら `entity_emissive_alpha_one_sided`。
5. `playAnimation` は client entity に載っていないアニメも再生できる。**controller 名ごとに 1 本**、別名なら重なる、
   既存の controller 名を渡すとそれを**上書き**する。状態の保存はされない（後から来た人には見えない）。
   → ゾンビの常時の見た目（切断・這う・死体）は**プロパティ＋自前のコントローラ**で、playAnimation は一発ものだけ。
6. geometry は **`format_version: "1.16.0"`** に統一（`binding` は 1.16.0 から。1.12.0 にも per-face UV と locators はある）。
7. テクスチャ: 非 2 冪 OK・パレット PNG（tRNS・中間アルファ含む）OK（バニラに多数）。**1 枚 ≤1024×1024 を推奨**
   （Mojang の検証が >4 MiB で警告）。**アドオン全体の展開後テクスチャ ≤150 MiB**（Mojang の検証の tier0 予算、超えるとエラー）。
   DESIGN §11 の上限いっぱいに作ると超えるので、武器・小道具を小さめに。
8. ブロック: 形は 30×30×30 px まで、当たり判定は 1 箱・高さ 16 まで（配列・24 は 1.26.0 から）、
   `minecraft:multi_block` は 1.26.20 からなので**使えない**（min_engine 1.21.120）。

---

## 1. render controller の `part_visibility`

### 1.1 隠した親の子は描かれるか → **描かれる（伝わらない）** ✅

バニラの 3 例。いずれも `{"*": false}` で**祖先を含む全ボーン**を消し、その後で**子だけ** `true` にしている。
子が見えるのはゲーム内で誰もが見ている挙動（一人称の素手の腕、クリーキングの光る目、銅ゴーレムの頭の花）。

**(a) プレイヤーの一人称の腕** — `BS/resource_pack/render_controllers/player.render_controllers.json`

```json
"controller.render.player.first_person": {
  "geometry": "Geometry.default",
  "part_visibility": [
    { "*": false },
    { "rightArm": "query.get_equipped_item_name(0, 1) == '' || query.get_equipped_item_name(0, 1) == 'filled_map'" },
    { "rightSleeve": "query.get_equipped_item_name(0, 1) == '' || query.get_equipped_item_name(0, 1) == 'filled_map'" },
    ...
```

`Geometry.default` = `geometry.humanoid.custom`（`BS/resource_pack/entity/player.entity.json`）。その骨格
（`BS/resource_pack/models/entity/humanoid.custom.geo.json`）では **`rightArm` の親は `body` → `waist` → `root`**。
`body` は `"*": false` で消えているのに、素手の一人称では右腕が見える。

**(b) クリーキングの目** — `BS/resource_pack/render_controllers/creaking.render_controllers.json`

```json
"controller.render.creaking_eyes": {
  "geometry": "Geometry.default",
  "materials": [ { "*": "Array.materials[query.is_invisible ? 0 : 1]" } ],
  "textures": [ "Texture.eyes" ],
  "ignore_lighting": true,
  "part_visibility": [
    { "*": false },
    { "head": "variable.has_emissive_eyes" }
  ]
}
```

`geometry.creaking`（`creaking.geo.json`）で **`head` の親は `upperBody` → `root`**。

**(c) 銅ゴーレムの花** — `BS/resource_pack/render_controllers/copper_golem.render_controllers.json`

```json
"controller.render.copper_golem_flower": {
  "geometry": "Geometry.flower",
  "part_visibility": [
    { "*": "false" },
    { "flower": "query.property('minecraft:has_flower')" }
  ]
}
```

`geometry.copper_golem.flower`（`copper_golem.geo.json`）で **`flower` の親は `head` → `body` → `root`**。

**結論**: `part_visibility` はボーン 1 本ずつの「自分のキューブを描くか」のスイッチで、**子孫には伝わらない**。

### 1.2 隠したボーンの「動き」は子へ伝わる ✅（状況証拠）

* (c) の花は頭の上に乗って頭と一緒に動く（`head`・`body` は隠れているがアニメーションは効いている）。
* 一人称で何か持っていると `rightArm` は隠れる（(a) の条件）が、手の物は腕の振り（`first_person_attack_controller`）と
  一緒に動く。物は `rightItem`（`rightArm` の子）に付いている。

→ **断面ボーンを消える部位の子に置いても、親の変換は効く**。ただし表示は自分の条件だけで決まる。
ロケータ（`loc_*`）も、付いているボーンが隠れていても追従する（変換は計算される）。

### 1.3 推奨: 全ボーンに「自分 AND 全祖先」の式を生成する（必須）✅

`tools/nightrunner/nr_rig.py` の `visibility_rules()` が既にこれを実装している。実際の出力（骨格だけ、抜粋）:

```json
"part_visibility": [
  { "*": true },
  { "pelvis": "q.property('nr:torso') != 'halved'" },
  { "leg_r": "q.property('nr:leg_r') != 'cut_upper' && q.property('nr:torso') != 'halved'" },
  { "shin_r": "q.property('nr:leg_r') != 'cut_lower' && q.property('nr:leg_r') != 'cut_upper' && q.property('nr:torso') != 'halved'" },
  { "foot_r": "q.property('nr:leg_r') != 'cut_lower' && q.property('nr:leg_r') != 'cut_upper' && q.property('nr:torso') != 'halved'" },
  { "stump_leg_r_upper": "q.property('nr:leg_r') == 'cut_upper' && q.property('nr:torso') != 'halved'" },
  { "guts": "(q.property('nr:torso') == 'gutted' || q.property('nr:torso') == 'halved')" },
  { "head": "q.property('nr:head') != 'severed' && q.property('nr:head') != 'crushed'" },
  { "jaw": "(q.property('nr:head') == 'intact' || q.property('nr:head') == 'wounded' || q.property('nr:head') == 'cracked')" },
  { "forearm_r": "q.property('nr:arm_r') != 'cut_lower' && q.property('nr:arm_r') != 'cut_upper'" },
  { "hand_r": "q.property('nr:arm_r') != 'cut_lower' && q.property('nr:arm_r') != 'cut_upper'" },
  { "stump_arm_r_upper": "q.property('nr:arm_r') == 'cut_upper'" }
]
```

形の決まり:

* **配列**で、要素は**キー 1 つのオブジェクト**、**`{"*": true}` を先頭**に置く。
  公式: *"The arrays for Materials and Part visibility are applied in the order specified. Materials and Part visibility
  specified later in the file will override previous materials or parts."*（`BS/metadata/doc_modules/animations.json` →
  Render Controllers > Examples > Note）✅
  バニラの witch / npc は 1 オブジェクトに複数キーを書いているが（`{"*": false, "head": true, ...}`）、
  JSON のキー順に依存するので**使わない**。
* 値は `true`/`false`/数値/Molang 文字列のどれでもよい（バニラに `true`、`"false"`、`0` がある）✅。
* キーは `*` を含むワイルドカード可（`"leg*"`, `"chest*"`, `"*Saddle*"`、大文字小文字を区別）✅。
  NR のボーン名は `*` 以外のワイルドカードを使わないこと（`arm_r` と `arm_r_wound` が `arm_r*` で巻き込まれる）。
* **ジオメトリに無いボーン名を書いても無害** ✅: `controller.render.player.third_person` は `helmet`, `leftLegging`,
  `belt`, `leftSock` などを列挙しているが、`geometry.humanoid.custom` にそれらは無い。
  → 50 種で共通の render controller に、種類ごとの服のボーンを全部並べてよい。
* 服・装備・変異の子ボーン（`hat`, `armor_chest`…）も**祖先の条件を引き継いだ式**を必ず持たせる
  （「常に表示」でも祖先が消えるなら式が要る）。`nr_rig.visibility_rules(model)` に**モデルを渡して**生成する。
* 祖先 AND の式は、`"*": true` に任せられるボーン（どの祖先も条件を持たない）だけ省略できる。

### 1.4 Molang でのプロパティの比較 ✅

| 型 | 書き方 | 根拠 |
|---|---|---|
| enum | `q.property('nr:arm_r') == 'cut_upper'`、`!= 'intact'` | `BS/resource_pack/entity/armadillo.entity.json`: `"variable.is_rolled_up = query.property('minecraft:armadillo_state') != 'unrolled';"` |
| int | `q.property('nr:blood') >= 2`、`q.property('nr:part') == 3` | int は float として返る（「All numerical values are floats」`docs_txt/molang.txt`） |
| bool | `q.property('x')`（0/1）。算術にも使える | `bee.v2.render_controllers.json`: `"array.skins[query.property('minecraft:has_nectar') + query.is_angry * 2]"` |

* 文字列は**単引用符**、比較は `==` と `!=` だけ、**大文字小文字を区別**（「All things in Molang are case-INsensitive,
  with the exception of strings」）。enum 値はすべて小文字にする ✅（`docs_txt/molang.txt` Strings / Case Sensitivity）。
* 演算子の優先順位は min_engine_version で変わる（1.18.20 で `&&` が `||` より先に）。1.21.120 では新しい規則だが、
  **`||` の塊は必ず括弧で囲む**（`nr_rig._expr` はそうしている）✅（`docs_txt/molang.txt` Versioned Changes）。
* プロパティが無いエンティティで `q.property` を呼ぶと**コンテンツエラー＋0**（`MS/creator/Documents/IntroductionToEntityProperties.md`:
  *"will send a content error message and return 0 if no property with that name is found"*）✅
  → `controller.render.nr.zombie` を使う全エンティティは、式に出てくる全プロパティを定義すること。
* RP から読むプロパティは **`"client_sync": true`** が必須（同ドキュメント: *"sent to clients, where it will be available
  to the content in the Resource Pack"*）✅。
* 上限 ✅（同ドキュメント Limitations）: **1 エンティティ 32 プロパティ**、enum は**最大 16 値**、各値 1〜32 文字・
  先頭は英字・以降は英数字と `_`。int は ±100 万の範囲で使う。範囲外の set は黙って丸められる。
  NR のゾンビは 13 個・最大 7 値なので余裕がある。

### 1.5 `q.property` が使える場所 ✅

| 場所 | 使えるか | バニラの実例 |
|---|---|---|
| render controller（part_visibility / arrays の添字 / materials / color 系） | ✅ | `copper_golem.render_controllers.json`（part_visibility）、`bee.v2.render_controllers.json`（添字） |
| animation controller の transitions | ✅ | `bee.animation_controllers.json`: `{ "dripping": "query.property('minecraft:has_nectar')" }` |
| client entity の `scripts.pre_animation` / `animate` の条件 | ✅ | `chicken.entity.json`, `armadillo.entity.json`, `copper_golem.entity.json`（`{ "walk_controller": "query.property('minecraft:chest_interaction') == 'none'" }`） |
| アニメーションのボーンの式の中 | 🟡 | バニラに直書きの例は無い（クエリ表では `query.property` の query_sets は `default` = どこでも）。**バニラ流儀に合わせ、`pre_animation` で `v.*` に落としてからアニメで使う** |

---

## 2. render controller の配列・複数の render controller・種類ごとのジオメトリ

### 2.1 配列と添字 ✅

```json
"arrays": {
  "geometries": { "Array.geos": [ "Geometry.default", "Geometry.warm", "Geometry.cold" ] },
  "textures":   { "Array.textures": [ "Texture.default", "Texture.warm", "Texture.cold" ] }
},
"geometry": "query.is_baby ? Geometry.baby : Array.geos[v.index]",
"textures": [ "query.is_baby ? Array.baby_textures[v.index] : Array.textures[v.index]" ]
```
（`BS/resource_pack/render_controllers/chicken.v3.render_controllers.json`。`v.index` は client entity の
`pre_animation` で enum から作っている: `"v.index = (t.variant == 'temperate') ? 0 : ((t.variant == 'warm') ? 1 : 2);"`）

* **大きさの上限は無い**: 公式 *"you can have as many arrays as you like, each with as many elements as you like"* ✅
  （`docs_txt/molang.txt` Render Controllers > Array Expressions）。バニラ最大は `controller.render.npc` の 60 要素。
* **添字は折り返す**: 公式 *"index = max(0, expression_result) % array_size"*、小数は切り捨て ✅。
  → `nr:ztype` が 63（汎用）なのに配列が 50 要素だと `63 % 50 = 13` 番の種類が出る。**範囲外は三項演算子で先に分ける**:
  `"geometry": "(q.property('nr:part') > 10 || q.property('nr:ztype') >= 50) ? Geometry.generic : Array.geos[q.property('nr:ztype')]"`
* enum は添字にできないので、`pre_animation` で数値に直す（chicken / copper_golem の流儀）。
* 配列の要素は同じ型だけ（texture 配列に material を混ぜない）✅。

### 2.2 1 つの client entity に複数の render controller ✅

* 例: 銅ゴーレム 3 本（花・体・目）、ウォーデン 6 本、クリーキング 2 本。`render_controllers` に列挙した順に描く。
* **条件付きで丸ごと on/off** できる ✅: `player.entity.json`
  `{ "controller.render.player.first_person": "variable.is_first_person && !query.is_spectator" }`
* 各 render controller は**ジオメトリを丸ごともう一度描く**（ドローコールが増える）。
* **同じジオメトリを重ね描きする「上塗りパス」は避ける**: 深度が等しい面は既定の深度テスト（Less）で落ちる／ちらつく。
  バニラの重ね描き用マテリアル（`villager_v2`, `villager_v2_masked`, `zombie_villager_v2*`）は
  `"depthFunc": "LessEqual"` を足してある（`MAT/entity.material`）。目・発光層のバニラ専用マテリアル
  （`creaking_eyes`, `copper_golem_eyes`, `warden_bioluminescent_layer`）は中身が非公開 ❓。
  → NR では「光る目」は 1 パスの `entity_emissive_alpha` で済ませる（§3）。
* **別ジオメトリで同じボーン名**を持たせれば、アニメーションは両方に効く（銅ゴーレムの `Geometry.flower` は
  `root/body/head/flower` を持ち、体のアニメに付いてくる）✅。重ね描きが要るなら「少し膨らませた別ジオメトリ」で。

### 2.3 種類ごとのジオメトリの選び方（推奨）

* **ゾンビ**: BP に 50 の識別子（`nr:z_<key>`）があるので、**client entity を 50 個**（各々 `geometry.default` /
  `textures.default` / `materials.default` が自分の種類）にして、render controller は共有する。配列は要らない。
* **gib**: 1 つの `nr:gib` に 50＋汎用のジオメトリ・テクスチャを配列で持ち、`nr:ztype` と `nr:part` で選ぶ（§2.1 の折り返し対策必須）。
* 共有 render controller の part_visibility は全種類のボーンの和集合になる。1 本の式は毎フレーム評価される。
  和集合が大きく（目安 150 行超）なりそうなら、**種類ごとの render controller**（`controller.render.nr.z.<key>`）を同じ関数で
  生成するほうが軽く、名前の衝突検査（`merge_visibility`）も要らない ❓（コストは未計測。上限の記載は無い）。

---

## 3. マテリアル

### 3.1 何があるか（エンティティ用）✅🟡

継承と中身は `MAT/entity.material`（旧版）。名前と説明は `MS/creator/Documents/material-files.md`（2025-11）。

| 名前 | 存在 | 継承 / 中身（旧版） | カリング | アルファの扱い |
|---|---|---|---|---|
| `entity` | ✅ | `entity_static` + `USE_OVERLAY` | **裏面を捨てる** | 無視（透明部分は RGB がそのまま出る） |
| `entity_nocull` | ✅ | `entity` + `DisableCulling` | 両面 | 無視 |
| `entity_alphatest` | ✅ | `entity_nocull` + `ALPHA_TEST` | **両面** | **α<0.5 を捨てる** |
| `entity_alphablend` | ✅ | `entity` + `Blending` | 裏面を捨てる | 半透明（ブレンド） |
| `entity_emissive` | ✅ | `entity` + `USE_EMISSIVE` | 裏面を捨てる | α で発光量（捨てない。公式は「.tga 前提」） |
| `entity_emissive_alpha` | ✅ | `entity_nocull` + `ALPHA_TEST` + `USE_EMISSIVE` | **両面** | §3.2 |
| `entity_emissive_alpha_one_sided` | ✅ | `entity` + `ALPHA_TEST` + `USE_EMISSIVE` | **裏面を捨てる** | §3.2（エンダードラゴンが使用） |
| `entity_alphatest_glint` | ✅ | `entity_alphatest` + `GLINT` | 両面 | エンチャントの光（アタッチャブル用） |
| `entity_change_color` / `entity_alphatest_change_color` | ✅ | `USE_COLOR_MASK`（羊・狼の色） | 両面 | — |
| `entity_multitexture` / `_color_mask` / `_alpha_test` / `_alpha_test_color_mask` / `_multiplicative_blend` / `_masked` | ✅ | 2〜3 枚のテクスチャを重ねる（馬・ラマ・熱帯魚・村人 v2） | 種類による | — |
| `entity_beam` / `entity_beam_additive` / `entity_dissolve_layer0/1` | ✅ | 特殊（ドラゴン） | — | 使わない |
| **`entity_alphatest_one_sided`** | **無い** | `MAT/`・現行バニラの全 client entity・公式一覧のどこにも無い | — | **使わない**（存在しない名前は描かれない／エラー ❓） |

* マテリアルはパックから**新しく定義できない**（RenderDragon）。公式も *"Sticking to the built-in Vanilla materials is safest!"* ✅。
* バニラの別名（`zombie` = `entity_alphatest`, `spider` = `entity_emissive_alpha` …）も使えるが、意味が変わり得るので**素の名前を使う**。
* `entity`（不透明）は透明部分を捨てないので、穴のあるテクスチャには使わない。

### 3.2 `entity_emissive_alpha` のアルファの意味 🟡✅

旧版シェーダ（`SHADER/entity.fragment`）:

```glsl
#ifdef USE_EMISSIVE
  #define NEEDS_DISCARD(C) (C.a + C.r + C.g + C.b == 0.0)   // RGBA がすべて 0 のときだけ捨てる
#else
  #define NEEDS_DISCARD(C) (C.a < 0.5)                      // 普通の alphatest
#endif
...
#ifdef USE_EMISSIVE
  color *= mix(vec4(1.0), light, color.a);   // α=1: 普通に照らす / α=0: 光の影響なし（全発光）
#else
  color *= light;
#endif
```

バニラの発光テクスチャ（`BS/resource_pack/textures/entity/...`、TGA）を数えて同じ規則を確かめた ✅:

| テクスチャ（マテリアル） | α=255 | 中間 α | α=0 の画素の RGB | 読み取れること |
|---|---|---|---|---|
| `spider/cave_spider.tga`（`spider` = emissive_alpha） | 体 2028 | **目 20 画素が α=3**（赤） | — | 目だけほぼ全発光 |
| `enderman/enderman.tga`（`enderman`） | 1052 | **目 6 画素が α=3**（紫） | 990 画素すべて (0,0,0) | 穴は RGBA=0、目は α=3 |
| `slime/magmacube_v2.tga`（`magma_cube`） | 0 | 1376 画素が α=29/126 | すべて (0,0,0) | 全身が半分〜ほぼ全発光 |
| `blaze.tga`（`blaze_head`） | 0 | 464 画素 α=90 | **1584 画素が RGB≠0** | α=0 でも色があれば**不透明の全発光** |

まとめ（NR の規則）:

* **α=255** → 普通に照らされる。**体のほとんどはこれ**。
* **0<α<255** → 発光の強さ ≈ 1−α/255。光る目・UV 管・燃える芯は **α=3〜40**（バニラは 3）。
* **RGBA=(0,0,0,0)** → 透明（捨てる）。**穴は必ずこの値**。
* **α=0 で RGB≠0** → 透明にならず**全発光の不透明**になる。ペインタが透明部分に色を残すと「光るゴミ」になる。
* 縁のアンチエイリアス（α=128 など）も**発光扱い**になる。発光させない画素の α は 255 か 0 に二値化する。
* 重ね描きなしの 1 パスで済む・赤い被ダメージ点滅も効く（`USE_OVERLAY` を `entity` から継承）。

### 3.3 用途ごとの推奨

| 用途 | マテリアル | 理由・注意 |
|---|---|---|
| 普通のゾンビ（`eyes` が `clouded`/`bloodshot`/`none`） | `entity_alphatest` | 両面（断面の内側・布のひらひらが見える）、α<0.5 を捨てる |
| 光る目のゾンビ（`glowing_*`）・ボス・夜の捕食者 | `entity_emissive_alpha` | 目の画素だけ α=3〜20。体は α=255、穴は (0,0,0,0)。違いは「α<0.5 を捨てる（alphatest）」か「RGBA=0 だけ捨てる（emissive_alpha）」だけなので、M2/M3 を守ったテクスチャなら全種類 emissive_alpha にしても見た目は同じ |
| gib（ちぎれた部位） | `entity_emissive_alpha`（全種類で 1 つ） | `nr:gib` は 1 つの client entity なので種類ごとにマテリアルを変えにくい（変えるなら `materials` の配列を `nr:ztype` で引く）。テクスチャが M2/M3（§11）を守っていれば、光らない種類では `entity_alphatest` と同じ見た目になり、光る目の種類の頭 gib は目も光る |
| 汎用の肉片 `geometry.nr.gib.generic` | `entity_alphatest` | — |
| 車などの小道具の車体 | `entity_alphatest`（穴なしで大きく閉じた形なら `entity_emissive_alpha_one_sided` で片面化） | 片面にすると描く面が半分 |
| 車の窓ガラス（割れていない） | `entity_alphablend`（ガラス用 render controller を**最後**に置く、または per-bone で `{ "glass*": "Material.glass" }`） | 半透明の前後関係は保証されない ❓。ガラス同士が重なる構図を避ける |
| 割れた窓・汚れたガラス | `entity_alphatest`（穴を抜く） | 半透明より壊れにくい |
| ヘッドライト・回転灯・UV ランプの発光部 | `entity_emissive_alpha`（per-bone 指定可） | 夜に光って見える。周りは照らさない（照らすのはブロックの `light_emission` だけ） |
| 武器（アタッチャブル） | `entity_emissive_alpha` + `enchanted: entity_alphatest_glint` | HyperDim と同じ。刃の光る縁だけ α<255 |

per-bone のマテリアル割り当ては公式に例がある ✅（`animations.json` Note: `{ "*": "Material.default" }, { "TailA": "Material.horse_hair" }, { "*Saddle*": "Material.horse_saddle" }`、
`chicken.render_controllers.json`: `{ "leg*": "Material.legs" }`）。後の行が前の行を上書きする。

### 3.4 被ダメージの赤・燃焼色・上塗り色 ✅

公式（`animations.json` Render Controllers > Examples）とバニラ:

```json
"is_hurt_color":  { "r": 0.0, "g": 0.0, "b": 1.0, "a": 0.5 }          // クリーパー例（青く点滅）
"on_fire_color":  { "r": 0.0, "g": 0.0, "b": 0.0, "a": 0.0 }          // 火の玉例（燃えても色を変えない）
"overlay_color":  { "r": "variable.is_invulnerable ? 1.0 : this", ... "a": "variable.is_invulnerable ? query.overlay_alpha : this" }
```

* 書かなければバニラ既定（被ダメージで赤く点滅）。`a: 0` で無効（`cape.render_controllers.json` の `is_hurt_color` が全 0）。
* 値は Molang 可・`this` = 既定値のまま（`ender_dragon`: `"a": "query.death_ticks > 1.0 ? variable.death_alpha : this"`）。
* 上塗りはシェーダで `color.rgb = mix(color, overlayColor, overlayColor.a)`（`SHADER/`）。`USE_OVERLAY` の無い
  `entity_static` 系では効かないが、§3.1 の推奨マテリアルは全部効く。
* `overlay_color` には `query.life_time` も使える（`experience_orb.render_controllers.json` が点滅に使用）✅。

NR での使い方（推奨）:

* **焼け（`nr:burn`）**: テクスチャを増やさず `overlay_color` で黒く寄せる:
  `"r": "q.property('nr:burn') > 0 ? 0.06 : this", ..., "a": "q.property('nr:burn') > 0 ? q.property('nr:burn') * 0.22 : this"`
* **感電（`nr:shock`）**: `"a": "q.property('nr:shock') ? (math.sin(q.life_time * 2400.0) > 0.0 ? 0.55 : 0.1) : this"`（色は青白）
* `overlay_color` と被ダメージ点滅が同時のときどちらが勝つか ❓。`this` に戻す形にしておく。
* **体の血（`nr:blood`）**: 種類ごとに上塗りテクスチャを持つとメモリが 50 枚×段階ぶん増える（§6.5 の予算を超える）。
  **体表の薄い「血のりキューブ」**（`inflate` で 0.02〜0.05 外へ出す、gore_wet で塗る）を部位のボーンの子に置き、
  `q.property('nr:blood') >= n` で出す。z ファイティングを避けるため元の面と**同じ平面に置かない**。

### 3.5 Vibrant Visuals（PBR）について 🟡

バニラの発光モブは `*.texture_set.json` と `_mers.tga`（G = 発光）も持つ（例 `enderman.texture_set.json`、
目の画素の MERS = `[0, 32, *, 3]`）。テクスチャセットを付けない場合の Vibrant Visuals での発光の見え方は ❓。
NR v1.0 は付けない（クラシック描画が基準）。

---

## 4. client entity

### 4.1 形（推奨テンプレート）✅

`format_version` はバニラの大半と同じ **`"1.10.0"`**（現行のゾンビ・プレイヤーは `1.26.0` だが、min_engine 1.21.120 では使わない）。

```json
{
  "format_version": "1.10.0",
  "minecraft:client_entity": {
    "description": {
      "identifier": "nr:z_office_worker",
      "materials": { "default": "entity_alphatest" },
      "textures":  { "default": "textures/nr/zombies/office_worker" },
      "geometry":  { "default": "geometry.nr.z.office_worker" },
      "animations": {
        "look": "animation.nr.z.look",
        "loco": "controller.animation.nr.z.locomotion",
        "gore": "controller.animation.nr.z.gore_fx"
      },
      "particle_effects": { "neck_spurt": "nr:blood_fountain", "drip": "nr:blood_drip" },
      "sound_effects":    { "squelch": "nr.gore.drip" },
      "scripts": {
        "initialize":    [ "v.nr_phase = math.random(0.0, 1.0);" ],
        "pre_animation": [
          "v.nr_dead  = q.property('nr:state') == 'dead';",
          "v.nr_crawl = q.property('nr:state') == 'crawl' || q.property('nr:torso') == 'halved';",
          "v.nr_tcos  = math.cos(q.modified_distance_moved * 38.17 + v.nr_phase * 360.0) * q.modified_move_speed * 57.3;"
        ],
        "animate": [ "loco", { "look": "!v.nr_dead" }, "gore" ]
      },
      "render_controllers": [ "controller.render.nr.zombie" ],
      "spawn_egg": { "base_color": "#4b5a3a", "overlay_color": "#7a1010" }
    }
  }
}
```

| フィールド | 意味（根拠） |
|---|---|
| `materials` / `textures` / `geometry` | 短い名前 → 実体。render controller は `Material.x` / `Texture.x` / `Geometry.x` で参照 ✅（公式 ClientEntityDocumentationIntroduction.md） |
| `animations` | 短い名前 → アニメーション**または**アニメコントローラの完全名（バニラのゾンビは両方をここに書く）✅ |
| `animation_controllers` | 旧形式（1.8）。1.10 からは `animations` に入れて `scripts.animate` で再生 ✅（Upgrade from v1.8 to v1.10） |
| `scripts.initialize` | 生成時に 1 回（バニラのゾンビ: `"v.tp_melee_spear_base_arm_rotation_x = -30.0;"`）✅ |
| `scripts.pre_animation` | 毎フレーム、アニメの前（`t.` 一時変数・`v.` 実体変数）✅ |
| `scripts.animate` | 再生する根のアニメ／コントローラ。`{名前: 式}` で重み付き・条件付き ✅ |
| `scripts.variables` | `{"variable.x": "public"}` で他から `c.owning_entity->v.x` で読める（プレイヤーの `attack_time`）✅ |
| `scripts.scale` | 全体の倍率 ✅ |
| `scripts.should_update_effects_offscreen` | 画面外でもエフェクトを更新（バニラのゾンビ `"1.0"`）✅ |
| `render_controllers` | 文字列か `{名前: 条件}` ✅ |
| `spawn_egg` | `{texture, texture_index}` か `{base_color, overlay_color}` ✅ |
| `enable_attachables` | 装備・手持ちを描く。NR のゾンビの骨格には `rightItem` 等が無いので**書かない**（false） ✅ |
| `hide_armor` | 防具を描かない（`enable_attachables` より優先）✅ |
| `held_item_ignores_lighting` | 手持ちを全発光 ✅ |
| `locators`（description 直下） | リードの位置など（`"lead": { "head": [0, 14, -6] }`）✅ |

### 4.2 モブのアニメで使うクエリ ✅

`BS/metadata/molang_modules/mojang-molang-queries.json` で実在と説明を確認（全部 query_sets = default）。

| クエリ | 内容 | 使いどころ |
|---|---|---|
| `q.modified_move_speed` | 歩きアニメ用の速さ（子ども・燃焼で補正） | 歩き・走りの重み |
| `q.modified_distance_moved` | 水平移動距離（m、ロード以降） | 歩き周期の位相（バニラ: `math.cos(q.modified_distance_moved * 38.17)`） |
| `q.ground_speed` / `q.vertical_speed` | m/s（上が正） | 走り/全力疾走の切替、落下・跳躍の姿勢 |
| `q.is_on_ground` / `q.is_moving` | 0/1 | 着地・停止 |
| `q.is_wall_climbing` | 壁を登っている | 登りの姿勢（`minecraft:can_climb` 系） |
| `q.has_target` / `q.target_x_rotation` / `q.target_y_rotation` | ターゲット・狙う角度 | 首の向き（バニラ `animation.common.look_at_target` は `relative_to: {rotation: entity}` で `q.target_x_rotation - this`） |
| `q.is_delayed_attacking` | `behavior.delayed_attack` で攻撃中 | 溜め攻撃の型 |
| `v.attack_time` | **エンジンが設定**する振りの進み（攻撃していないとき負、振りで 0→1） | 腕の振り。バニラのゾンビ・ホグリン・ヤギ・クリーキングが代入せずに読む（`controller.animation.humanoid.attack`: `"attacking": "variable.attack_time >= 0.0"`） |
| `q.hurt_time` / `q.hurt_direction` | 被ダメージの残り時間・向き | 打たれた瞬間ののけぞり（スクリプト不要。ウォーデンの心臓も `query.hurt_time > 0`） |
| `q.life_time` / `q.anim_time` / `q.delta_time` / `q.frame_alpha` | 時間 | 揺れ・点滅・補間 |
| `q.is_alive` | 生死 | **NR では使わない**（本当の死はスクリプト。`q.property('nr:state') == 'dead'` を見る） |
| `q.distance_from_camera` / `q.lod_index(a, b, …)` | カメラからの距離 / 段階 | 遠いとき細部のボーンを part_visibility で消す（軽量化） |
| `q.all_animations_finished` / `q.any_animation_finished` / `q.state_time` | コントローラの中だけ | 一発ものの終わり |

### 4.3 アニメーション・コントローラの機能 ✅

アニメーション（`BS/metadata/doc_modules/schemas.json` の animation スキーマ、`animations.json`）:

| キー | 意味 |
|---|---|
| `"loop": true / false / "hold_on_last_frame"` | *"should this animation stop, loop, or stay on the last frame when finished"*。最後の姿勢を保つなら `"hold_on_last_frame"`（バニラ: `animation.creaking.twitch`, `animation.breeze.slide`） |
| `"override_previous_animation": true` | *"reset bones in this animation to the default pose before applying this animation"*（バニラ: `animation.player.sleeping`）。**既定は加算**（*"animations are ADDITIVE unless otherwise specified"*） |
| `"blend_weight"` / `"animation_length"` / `"start_delay"` / `"loop_delay"` / `"anim_time_update"` | 重み・長さ・開始遅延・ループ間隔・時間の進め方（既定 `query.anim_time + query.delta_time`） |
| `"relative_to": {"rotation": "entity"}` | 親でなく体の向き基準の回転（首振り） |
| キーフレームの `"lerp_mode": "catmullrom"`、`"pre"`/`"post"` | 補間・不連続 |
| チャンネル式の `this` | ここまでに積まれた値（`"30.0 - this"` で絶対値にする） |
| `particle_effects` / `sound_effects`（時刻キー） | `{ "effect": 短い名前, "locator": ロケータ名, "pre_effect_script": Molang, "bind_to_actor": false }` |
| ボーン名の照合 | **大文字小文字を区別しない**（バニラの `animation.humanoid.move` は `leftarm` と書き、骨格は `leftArm`）。無いボーンは無視（*"missing bones are ignored"*） |

アニメーションコントローラ:

```json
"controller.animation.nr.z.locomotion": {
  "initial_state": "walk",
  "states": {
    "walk":  { "animations": [ { "walk": "q.modified_move_speed" } ],
               "transitions": [ { "crawl": "v.nr_crawl" }, { "dead": "v.nr_dead" } ],
               "blend_transition": 0.25 },
    "crawl": { "animations": [ "crawl" ], "transitions": [ { "dead": "v.nr_dead" } ], "blend_transition": 0.3 },
    "dead":  { "animations": [ "death_pose" ],          // death_pose は "loop": "hold_on_last_frame"
               "transitions": [ { "walk": "!v.nr_dead" } ] }
  }
}
```

* `blend_transition`（秒）で状態の切替をクロスフェード、`blend_via_shortest_path: true` で回転の近道 ✅（エヴォーカー）。
* 遷移は**上から順**、**1 フレームに 1 回**だけ ✅（*"Only one transition will be processed per frame"*）。
* 状態の `particle_effects`（その状態の間ずっと出る）✅: ブレイズ `"flaming": { "particle_effects": [ { "effect": "charged_flames" } ] }`、
  エヴォーカー `{ "effect": "spell", "locator": "left_hand" }`。短い名前は client entity の `particle_effects` に書く。
  → **断面からの滴り・首の噴水**は「部位の状態ごとのコントローラ」の状態エフェクトにすれば、スクリプトのパーティクル予算を使わない。
* 状態の `variables` に `remap_curve`（入力を折れ線で写す）✅。
* `on_entry` / `on_exit`: BP のコントローラではコマンド。RP では Molang 式（変数の設定）に使う 🟡（WIKI animation-controllers-intro）。

---

## 5. スクリプトからの `Entity.playAnimation`（プレイヤー以外のモブにも効く）

API（`BS/metadata/script_modules/@minecraft/server-bindings_2.3.0.json`）✅:
`playAnimation(animationName: string, options?: PlayAnimationOptions): void`、
`PlayAnimationOptions = { blendOutTime?, controller?, nextState?, players?: Player[], stopExpression? }`、
`call_privilege: default`（**before イベントの中では呼べない** → `system.run` へ）、`InvalidEntityError` を投げる。
公式の説明は薄い（`MS/creator/ScriptAPI/minecraft/server/PlayAnimationOptions.md`: *"controller: Specifies a controller to use
that has been defined on the entity."* / *"players: A list of players the animation will be visible to."*）。
意味の詳細は `/playanimation` と同じで、コミュニティ資料（`WIKI/docs/commands/playanimation.md`、日本のコマンド勢の検証）による。

| 問い | 答え | 根拠 |
|---|---|---|
| client entity の `animations` に載っている必要は？ | **無い**。RP に読み込まれていれば、どのエンティティにもどのアニメも再生できる | 🟡 WIKI の例（ピグリンやエンダードラゴンのアニメをプレイヤー・アレイに再生）。公式も *"refers to an animation name or an animation JSON file in a resource pack"*。HyperDim も player.entity.json を上書きせず `animation.hd.p.*` を再生している |
| 自分のコントローラと重なるか？ | **新しい controller 名なら新しいコントローラとして追加され、重なる（加算）**。**既存の controller 名**（例 `controller.animation.allay.dancing`）を渡すと**それを上書き**する | 🟡 WIKI: *"If an existing animation controller is accessed, it will be overwritten."* / *"If a non-existent animation controller is specified, it will be registered as a new one"* |
| 1 つの controller で同時に何本？ | **1 本**。同じ名前に次を流すと前のを置き換える。同時に重ねたいなら名前を分ける | 🟡 WIKI: *"Each animation controller can play only one animation at a time."* |
| 止め方 | 同じ controller に**何もしないアニメ**を流す（HyperDim の `animation.hd.p.none`）か、`stopExpression` が真になって `nextState` へ移る（存在しない状態名なら止まる） | 🟡 WIKI Removing Stacked Animations |
| controller を省略したら？ | 既定の 1 本（名前は `__runtime_controller` と言われる）を共有する | ❓ → **必ず名前を渡す** |
| stopExpression / nextState の既定 | ❓（`q.any_animation_finished` / `default` と言われる） | → **必ず書く** |
| 保存されるか | **されない**。クライアント側のその場限り。後から近づいた人・入り直した人には見えない。コントローラは消せず、ワールドを出るか遠ざかるとリセット | 🟡 WIKI Storage and Removal |
| 自分のコントローラとの評価順 | ❓（後に足されると言われるが根拠なし）。`override_previous_animation` の効き方が順番で変わる |
| `stopExpression` の副作用 | 式の中で `v.x = 1;` が実行される（パロットの例）。毎フレーム評価 | 🟡 |

NR の規則:

* **ゾンビの常時の見た目（切断・這う・ぶら下がる腕・死体の姿勢・感電の震え）は、プロパティを見る自前のコントローラで出す**
  （同期され、後から来た人にも正しく見える）。playAnimation は**一発もの**（`ZOMBIE_ONESHOTS`）だけ。
* 一発ものは `{controller: "nr.z.os", blendOutTime: 0.15, stopExpression: "q.any_animation_finished", nextState: "none"}` を基本にする。
  **controller 名は `nr.` で始め、client entity のコントローラの完全名と絶対に重ねない**。
* 一発ものは**加算（差分）で書き、最初と最後のキーを 0（休みの姿勢）にする**。そうすれば「終わった後に最後の姿勢が残るか」
  「評価順」がどちらでも見た目が壊れない。
* 打たれた瞬間ののけぞりは、スクリプトを待たずに `q.hurt_time` で自前のコントローラから出せる（§4.2）。
  部位ごとのリアクション（`react_head` 等）だけ playAnimation で上乗せ。

---

## 6. ジオメトリ

### 6.1 format_version ✅

公式スキーマ（`BS/metadata/doc_modules/schemas.json`、平文 `docs_txt/schemas.txt`）の版ごとの差:

| 版 | 追加・変更 |
|---|---|
| 1.12.0 | per-face UV（`uv: {north: {uv, uv_size, material_instance}, ...}`）、`locators`（配列形・`{offset, rotation, ignore_inherited_scale}` 形）、`texture_width/height`、`visible_bounds_*` は**既にある**。キューブの pivot に *"Note that in 1.12 this is flipped upside-down, but is fixed in 1.14."* の注記 |
| 1.16.0 | **`binding`**（*"Useful for items. A molang expression specifying the bone name of the parent skeletal hierarchy..."*） |
| 1.21.0 | `item_display_transforms`（ブロックを手持ち・GUI で表示するときの変換） |

* バニラの使い分け: `binding` を持つ 10 本はすべて 1.16.0（盾・トライデント・クロスボウ・望遠鏡・槍）。
  1.12.0 にも per-face UV（`fishing_hook.geo.json`）と locators（`baby_strider.geo.json`）がある ✅。
* 公式のアタッチャブルの例（`MS/creator/Documents/attachables.md` の wrench）も 1.16.0、WIKI も *"upgrade the model file format version to "1.16.0""* 🟡。
* **NR は全ジオメトリを `"1.16.0"` で書く**（`mcmodel.Model.write` は 1.12.0 固定なので、NR の書き出しで上書きするか版を引数にする）。
* 1.12 の pivot の注記は「pivot を省略したときの既定（箱の中心）」の扱いと読める ❓。**回転するキューブには必ず pivot を明示**する
  （`mcmodel.Cube.to_json` は明示している）。そうすれば版の差は出ない。

### 6.2 per-face UV ✅

* 面を**省略するとその面は描かれない**（スキーマ: *"Omitting a face will cause that face to not get drawn."*）。
  断面の裏・体に埋まった面・接している面を省いて描画を減らせる（ただし `entity_alphatest` は両面なので、
  開いた箱の内側が見える向きなら残す）。
* `uv_size` の**負の値で反転**（バニラ `fishing_hook.geo.json`: `"uv_size": [ 16, -16 ]`、`[ -3, 3 ]`）。
* UV の単位は `description.texture_width/height`。実際の PNG と同じ寸法にする（倍数でも通ると言われるが ❓）。
* `material_instance` は面ごとの名前（ブロック用。エンティティでは使わない）。

### 6.3 locators ✅

* ボーンの `locators: { "名前": [x, y, z] }`（モデル空間）。または `{ "offset": [...], "rotation": [...], "ignore_inherited_scale": true }`。
* アニメ・コントローラの `particle_effects` / `sound_effects` の `locator` に名前で使う（エヴォーカー `left_hand`、イルカ、ラヴェジャー `stun`）。
* 付いたボーンが part_visibility で隠れていても位置は追従する（§1.2）。
* NR の `LOCATOR_BONES`（`nr_rig.py`）は「部位が落ちても残る側」に付けてあるので、断面の噴水はそのロケータから出せる。

### 6.4 visible_bounds（視錐台カリング用の箱）✅

* 単位は**ブロック**（スキーマの文面は model units だが、バニラの値はブロック）: 人型 `1 × 2, offset [0, 1, 0]`、
  ウォーデン（約 2.9 ブロック）`4 × 5.5, offset [0, 2.25, 0]`、ドラゴン `14 × 13`、ガスト `7 × 10`。
* 箱は `offset ± (width/2, height/2, width/2)`。アニメで箱の外へ出た部分は、箱が画面外だと**描かれない（消える）**。
* NR の目安（身長 H ブロック）:
  * 立ち・歩き: `width = max(3, 1.6·H)`, `height = H + 1.5`, `offset = [0, H/2 + 0.25, 0]`
  * **死体・這い・倒れ**（寝た体は足元から頭まで H ほど水平に伸びる）を考えると `width ≥ 2·H + 1`。
    ゾンビは状態が変わるので**最初から寝た姿勢を含む大きさ**にする（例 H=2 → 5 × 3.5、H=4 のボス → 9 × 5.5）。
  * gib は小さくてよいが、回転して飛ぶので `1.5 × 1.5` 程度。
  * 武器（アタッチャブル）は HyperDim と同じく大きめ（`6 × 6`）。

### 6.5 テクスチャの寸法・形式・予算

| 問い | 答え | 根拠 |
|---|---|---|
| 2 の冪でなくてよいか | **よい** | ✅ バニラ `entity/sniffer/sniffer.png` 192×192、`frog/*` 48×48、`fishhook.png` 24×3 |
| 1024×1024 は | **可**。ただし 1 枚 >4 MiB（1024² 超）で Mojang の検証が警告、>2048² でも警告 | 🟡 `MCTOOLS`: `HighestResolutionMipMemoryBudget = 4 * 1024 * 1024`、`individualMemoryBudget = 2048 * 2048 * 4`。バニラのエンティティは最大 256×256 |
| アドオン全体 | 展開後（w×h×4）の合計 **≤150 MiB**（tier0）。超えると検証が**エラー**（サブパックで段階を分けない場合） | 🟡 `MCTOOLS`: `3 /*add-on*/: { 0: 150, 1: 150, 2: 225, 3: 300, 4: 600, 5: 800 }`（MB） |
| アトラスに入るもの（ブロック・アイテムのアイコン） | 1 枚 **≤256×256**、アトラス全体 4096² で警告・8192² 相当でエラー | 🟡 `MCTOOLS`: `individualMemoryBudget = 256 * 256 * 4`（atlas） |
| パレット PNG（mode P + tRNS） | **可**。中間アルファの tRNS も可。8/4/2 bit も可 | ✅ バニラに 186 枚の P 形式（うち tRNS 付き 131 枚、例 `entity/hoglin/hoglin.png`、`entity/breeze/breeze_eyes.png`）。中間アルファ付き: `entity/wind_charge.png`（α 0/127）、`entity/sulfur_cube/sulfur_cube_outer_small.png`（7 段階） |
| 拡大縮小の補間 | エンティティは最近傍（`entity_static` の `"textureFilter": "Point"`） | 🟡 `MAT/` |

**予算の見積り（DESIGN §11 の上限いっぱいの場合）**: ゾンビ 47×512²（47 MiB）＋ボス 3×1024²（12 MiB）＋
武器 38×512²（38 MiB）＋小道具 16×1024²（64 MiB）＝ **161 MiB > 150 MiB**。
→ 武器は 256×512 前後（平均 0.5 MiB）、小道具は 512×512 を基本に 1024² は 4 枚まで、で ≈110 MiB。
`validate_nr.py` で Σ(w·h·4) を計算して 150 MiB を超えたら止める。パレット化は**ファイルサイズ**（パック容量 80 MB）には効くが、
展開後のメモリには効かない。

---

## 7. アタッチャブル（手持ちの武器）— HyperDim の作り方と、NR で再利用するもの

### 7.1 HyperDim の構成（`tools/hyperdim/`）

| 部品 | 中身 |
|---|---|
| `hd_space.py` | 回転の規則 `R = Rz(-rz)·Ry(+ry)·Rx(-rx)`、手に bind したボーンのずれ `OFF_R = (-6,-9,-1)` / `OFF_L = (6,-9,-1)`、拳の中心 `HAND_R = (-6,13.2,0)`、`GRIP_POS = (0,22.2,1)`、バニラの持ち姿勢 `HOLDING_RX = -18`、一人称の腕 `FP_ARM_ROT = (95,-45,115)` / `FP_ARM_POS = (13.5,-10,12)`、目 `(0,26,0)`。`rot()` / `euler()` / `bone_local()` / `beam_angles()`。根拠はバニラの盾・トライデント・望遠鏡・一人称の腕（`tools/hyperdim/reference/README.md`） |
| `hd_holds.py` | 武器空間（握り = 原点、刃 = -Z、刃の幅 = ±Y）。`frame()` / `frame_x()` / `frame_axes()` で「世界でどちらに向けるか」→ `item_rotation()` / `item_position()` で腕の姿勢から逆算。`solve_arm_to()`（拳を点へ）、`two_hand_place()`（両手持ちを両拳が柄に届き体に刺さらない所で探索）、`fp_place()`（一人称をカメラ空間で直接決める。`FP_ITEM_OFF = (0,0,-1)` を戻す）。`design()` が武器ごとの `{arm_r, arm_l, tp, fp, left_tp, use}` |
| `gen_hd_weapons.py` | ジオメトリ: `hold`（`binding: "q.item_slot_to_bone_name(c.item_slot)"`）→ 子 `root`（武器本体）。左手用は `hold_l`（`binding: "c.item_slot == 'main_hand' ? 'leftitem' : 'rightitem'"`）。テクスチャ・アイコン（自前レンダラで 32×32） |
| `gen_hd_anim.py` | アタッチャブル JSON（下）、武器のアニメ（`tp`/`fp`/`tp_use`/`fp_use` の持ち方、`idle`、`swing`、`use`）、プレイヤーの全身モーション（`animation.hd.p.*`）と `anim_meta.js` |
| `hd_pose.py` / `check_hd_clip.py` | 武器が体にめり込まない腕の角度をキーごとに解く・書き出し後に検査（0.6px 超 / 両手で 2px 以上離れたらビルド停止） |

アタッチャブル JSON（`gen_hd_anim.attachable()` の出力）:

```json
{
  "format_version": "1.10.0",
  "minecraft:attachable": { "description": {
    "identifier": "hd:greatsword",                       // アイテムと同じ ID
    "materials": { "default": "entity_emissive_alpha", "enchanted": "entity_alphatest_glint" },
    "textures":  { "default": "textures/entity/hd/greatsword", "enchanted": "textures/misc/enchanted_item_glint" },
    "geometry":  { "default": "geometry.hd.greatsword" },
    "animations": { "tp": "...tp", "fp": "...fp", "idle": "...", "swing": "...", "use": "..." },
    "scripts": {
      "pre_animation": [
        "v.hd_sw = math.clamp(c.owning_entity->v.attack_time, 0.0, 1.0);",
        "v.hd_use = q.is_using_item ? 1.0 : 0.0;",
        "v.hd_usew = (v.hd_usew ?? 0.0) + (v.hd_use - (v.hd_usew ?? 0.0)) * math.min(1.0, q.delta_time * 14.0);",
        "v.hd_fp = c.is_first_person ? 1.0 : 0.0;"
      ],
      "animate": [ { "tp": "1.0 - v.hd_fp" }, { "fp": "v.hd_fp" }, "idle", { "swing": "v.hd_sw > 0.0" }, { "use": "v.hd_usew > 0.01" } ]
    },
    "render_controllers": [ "controller.render.item_default" ]
  } }
}
```

裏付け ✅:
* `controller.render.item_default`（`BS/resource_pack/render_controllers/item_default.render_controllers.json`）は
  `"materials": [ { "*": "variable.is_enchanted ? material.enchanted : material.default" } ]`, `"textures": [ "texture.default", "texture.enchanted" ]`
  → `enchanted` のマテリアルとテクスチャを**必ず両方**定義する。
* `c.is_first_person` はバニラのトライデント・弓・クロスボウが使う（`trident.animation_controllers.json`: `"first_person": "c.is_first_person"`）。
* `c.owning_entity->v.attack_time` は、プレイヤーの client entity が `"variable.attack_time": "public"` にしているから読める
  （現行 `BS/resource_pack/entity/player.entity.json` の `scripts.variables` で確認）。
* `q.item_slot_to_bone_name(c.item_slot)`: `main_hand` → `rightitem`、`off_hand` → `leftitem` 🟡（WIKI）。

### 7.2 NR の武器生成器（`gen_nr_weapons.py`）が再利用するもの・作り直すもの

**そのまま使う（import する）**:
* `hd_space.py` の規則と定数（**全部**）。`hd_holds.py` の `frame` / `frame_x` / `frame_axes` / `item_rotation` /
  `item_position` / `solve_arm_to` / `world_point` / `fp_place` / `two_hand_place`。
  （`tools/hyperdim` を `sys.path` に足して import。コピーすると規則の修正が片方に漏れる）
* `check_hd_clip.py` の考え方（めり込み検査）、`hd_pose.py` の解き方。
* アタッチャブル JSON の形・`pre_animation`（振り = `c.owning_entity->v.attack_time`、構え = `q.is_using_item`、一人称 = `c.is_first_person`）。
* プレイヤー全身モーションの「バニラの打ち消し項」（`gen_hd_anim.HOLD_CANCEL` の `18.0 + 0.375 * v.tcos0`、`ATK_CANCEL`）と、
  一人称では体・脚・root を 0、腕を 25% にする規則（`chan_expr`）。

**作り直す（NR 固有）**:
* 武器の持ち方の表（片手刃・両手刃・片手打撃・両手打撃・槍・弓・クロスボウ・拳銃・ライフル・散弾銃・短機関銃・投擲物）。
  銃は「肩付け」の両手持ち（左手は先台）を `two_hand_place` で、照準時の一人称は `fp_place` で。
* 反動・装填・ポンプなどのモーション（`PLAYER_ANIMS` の名前で）。
* **ジオメトリの版を 1.16.0 に**（HyperDim の `hd_*.geo.json` は 1.12.0 に `binding` を書いている ❓ → §10 のリスク）。
* 改造（fire/shock/bleed/toxic/uv）の見た目: 発光の縁は `entity_emissive_alpha` の α、色違いはテクスチャの配列＋
  render controller（`item_default` ではなく自前の `controller.render.nr.weapon`）で。アイテムの改造は動的プロパティ
  （ItemStack）なので **RP からは読めない** ❓ → 改造ごとに別 ID にしないなら、見た目は変えずに lore と粒子で示す。
* アイコン: アイテムのアトラス用に ≤256²（HyperDim は 32×32）。

---

## 8. カスタムブロックの描画

min_engine 1.21.120 なので、**ブロック JSON の format_version は 1.21.120 以下**、それより新しい版でしか使えない機能は使わない。

| 項目 | 規則 | 根拠 |
|---|---|---|
| `minecraft:geometry` | `"geometry.nr.b.<key>"` か `{identifier, bone_visibility, culling, uv_lock}`。**`minecraft:material_instances` と必ず両方書く**（1.21.80 から） | ✅ `MS/.../minecraftBlock_geometry.md` |
| `bone_visibility` | `{ "bone": false }` / Molang（`"q.block_state('nr:stage') == 3"`）。**ワイルドカード不可**、既定は全部表示（1.20.10 から Molang） | ✅ 同上、🟡 WIKI block-components |
| `uv_lock` | 1.21.100 から | ✅ |
| `n_way_visual_rotation` / `culling_shape` | 1.26.30 から → **使わない** | ✅ |
| `material_instances` | `"*"`・面名（`up` 等）・ジオメトリの面に付けた名前。最大 64。`render_method`: `opaque`（既定）/ `double_sided` / `blend` / `alpha_test` / `alpha_test_single_sided` / `blend_to_opaque` / `alpha_test_to_opaque` / `alpha_test_single_sided_to_opaque`。**1 ブロックの全インスタンスで render_method を揃える** | ✅ `minecraftBlock_material_instances.md`、🟡 WIKI（揃える規則） |
| `ambient_occlusion` / `face_dimming` | 発光ブロックは既定で AO 0・面の陰りなし | 🟡 WIKI |
| 形の大きさ | **30×30×30 px 以内**、各軸で 1px 以上が自分のマス（16³）に入る、座標は原点（マスの底面中央）から各方向 30px 以内 | 🟡 WIKI block-components（公式の数値は見つからない） |
| キューブ数 | **≤50** を目安（超えると Mojang の検証が警告） | ✅ `MS/.../MCToolsValReference/geometry.md` GEOMETRY501 |
| `minecraft:collision_box` | `true` / `false` / `{origin, size}`。origin は `[-8,0,-8]`〜`[8,16,8]`、origin+size も同じ範囲（**高さ 16 まで、1 箱**）。配列（最大 16 箱）と高さ 24 は **1.26.0 から** → 使わない | ✅ `minecraftBlock_collision_box.md`、🟡 WIKI |
| `minecraft:selection_box` | 同じく `[-8,0,-8]`〜`[8,16,8]` の 1 箱 | ✅ |
| `minecraft:light_emission` | 整数 0〜15（たいまつ 14、グロウストーン 15）。8 以上で敵が湧かない | ✅ `minecraftBlock_light_emission.md` |
| テクスチャ | `terrain_texture.json`（アトラス）経由。1 枚 ≤256²（推奨 2 冪の正方形 16〜128） | 🟡 `MCTOOLS` |
| 手持ち・GUI の見た目 | geometry 1.21.0 の `item_display_transforms` | ✅ スキーマ |

**複数マスの物（街灯・給水塔・大きなバリケード）**:
* `minecraft:multi_block` 特性は **1.26.20 から**（2〜4 パーツ）→ **使わない** 🟡（WIKI multi-blocks）。
* 方法 A（`nr_spec_catalog.MULTIBLOCKS` の流儀）: **別々のブロックを積む**（`street_lamp_base` / `_pole` / `_head`）。
  各ブロックの形は自分のマス＋はみ出し 30px 以内。壊れたときの連鎖はスクリプトで。
* 方法 B: 1 ブロックの形を 30px まで伸ばし（約 1.9 マス）、はみ出した部分の当たりは見えないブロック
  （`minecraft:collision_box` だけ持つ `nr:collider`、`material_instances` は透明テクスチャ＋`alpha_test`）か**バリアブロック**で塞ぐ。
* 方法 C（小道具）: 車・バスのように 2 マスを超えるものは**エンティティ**（`nr:prop_*`）にして当たりはバリア（DESIGN §8 の通り）。
* 光る部分（UV 管・電球）: ブロックは画素単位で発光できない（`light_emission` はブロック全体を明るくし周りを照らす）。
  電球だけ光らせたいなら、そのマスを別ブロックにするか、小道具エンティティの `entity_emissive_alpha` で。

---

## 9. プレイヤーのパルクールモーション（playAnimation）— 三人称と一人称

### 9.1 三人称

* プレイヤーの client entity（`player.entity.json`）を**上書きしない**（他のアドオン・スキンと衝突する）。HyperDim と同じく
  `player.playAnimation("animation.nr.p.<名前>", { controller: "nr.p.<層>", blendOutTime, stopExpression })` で重ねる。
* 層（controller 名）を分ける: 例 `nr.p.move`（パルクールの全身: vault / slide / wallrun / climb）、`nr.p.act`（攻撃・投擲）、
  `nr.p.hold`（武器ごとの持ち姿勢のループ）。同じ層に流すと前のが置き換わる（§5）。
* バニラのプレイヤーは三人称で `humanoid_base_pose`, `move.arms`, `move.legs`, `holding`（持つと右腕 -18°）, `bob`, 攻撃の振り…
  を毎フレーム加算している（`player.animation_controllers.json` の `controller.animation.player.root` → `third_person`）✅。
  NR のモーションは**加算**として、
  * 腕は HyperDim の打ち消し項（`HOLD_CANCEL`, `ATK_CANCEL`）を足して「設計どおりの絶対姿勢」にする（実績のある方法）、
  * 体全体を寝かせる・回す動き（slide, roll, wallrun の傾き）は `root` / `waist` / `body` に書く、
  * `override_previous_animation: true` は、バニラより後に評価されるときだけ期待どおり効く ❓（§5 の評価順）→ 使うなら実機で確かめる。
* ループするもの（`climb_loop`, `ledge_hang`, `wallrun_l/r`, `glide`, `grapple_pull`, `grabbed_struggle`）は
  `stopExpression` に**クライアントだけで判定できる終わりの条件**を入れる（例 glide: `"q.is_on_ground"`、wallrun: `"q.is_on_ground || q.state_time > 1.5"`）。
  スクリプトからの停止は同じ controller に空のアニメ（`animation.nr.p.none`）を流す。
* 一回転で終わるもの（roll, 宙返り）はブレンドすると逆回転して見えるので `blendOutTime: 0`（HyperDim の `NO_BLEND`）。

### 9.2 一人称

* 一人称も**同じ骨格にアニメが掛かる**。バニラは一人称で `first_person_base_pose` が `body` を視線に合わせて回し
  （`"body": { "rotation": [ "query.target_x_rotation", "query.target_y_rotation", 0.0 ] }`、`player_firstperson.animation.json`）✅、
  腕はその子なので画面に付いてくる。**`root` / `waist` / `body` / 脚を動かすと腕と武器が画面からずれる** →
  全チャンネルを `v.is_first_person ? 0.0 : (...)` で包む（`v.is_first_person` はエンジンの変数。バニラの
  `player.entity.json` が render controller の切替に使っている）✅。腕は 25% 程度に弱める（HyperDim の `FPK`）。
* 一人称で描かれる腕は**右腕だけ、それも素手（または地図）のとき**（`controller.render.player.first_person` の part_visibility）✅。
  武器を持っていると腕は描かれず、`rightItem` に付いた武器だけが見える（腕の回転は武器の位置として効く）。
  左腕は地図・クロスボウ装填など以外は描かれない → 「両手で縁をつかむ」は一人称では見えない。
* **カメラはボーンのアニメで動かない**（目の位置はエンティティの当たり判定から決まる）。一人称の「体感」は
  Script API の `Camera`（2.3.0 安定版に `setFov({fov, easeOptions})`, `fade(...)`, `setCamera(...)`, `clear()`）✅ と
  `/camerashake` で出す: スライディングで FOV を広げる、着地で揺らす、重い着地で一瞬暗く。
* 三人称の視点（F5）では `v.is_first_person = 0` なので三人称のモーションが見える。

---

## 10. わかっていること・いないこと（リスク）

| 項目 | 状態 | 対処 |
|---|---|---|
| DESIGN.md §3「隠すと子も隠れる」 | **誤り**（§1.1 の 3 例） | DESIGN.md を直す（`nr_rig` は既に祖先 AND）。「断面は消える部位の親に付ける」は正しいので残す |
| HyperDim の武器ジオメトリが 1.12.0 で `binding` を使っている | ❓ 1.12.0 で `binding` が読まれる証拠なし（スキーマは 1.16.0 から、バニラ・公式例も 1.16.0） | NR は 1.16.0。HyperDim も 1.16.0 に上げるのが安全（`mcmodel` に版の引数を足す） |
| playAnimation の既定の controller / stopExpression / nextState、自前コントローラとの評価順 | ❓ | すべて明示。一発ものは「最初と最後が 0 の加算」 |
| `overlay_color` と被ダメージ点滅の優先 | ❓ | `this` に戻す式で書く |
| 半透明（`entity_alphablend`）の前後関係 | ❓ | ガラス同士が重なる構図を避け、ガラスの render controller を最後に |
| 1024² 超のテクスチャ | 🟡 警告対象 | 1 枚 ≤1024²、合計 ≤150 MiB |
| ブロックの 30px 規則 | 🟡 WIKI のみ | validator で強制 |
| `entity_alphatest` が両面 | 🟡 旧版の定義（公式の説明文は継承を省略） | 両面前提で作る（片面が要るなら `entity_emissive_alpha_one_sided`） |
| Vibrant Visuals での発光 | ❓ | v1.0 ではテクスチャセットを付けない |

---

## 11. Checklist for generators（`gen_nr_*` が守る規則）

### ジオメトリ（全部）
- [ ] G1. `format_version` は **`"1.16.0"`**。識別子は `geometry.nr.<分類>.<key>`。
- [ ] G2. 回転するキューブには**必ず `pivot`** を書く。
- [ ] G3. `texture_width/height` は実際の PNG の寸法と一致。UV（負の `uv_size` を含む）は全部テクスチャの内側。
- [ ] G4. 見えない面（埋まった面・接した面）は per-face UV から省いてよい（省いた面は描かれない）。両面マテリアルで裏が見える開いた形は省かない。
- [ ] G5. `visible_bounds` はブロック単位。ゾンビは寝た姿勢を含めて `width ≥ 2·H + 1`、`height = H + 1.5`、`offset = [0, H/2 + 0.25, 0]`。
- [ ] G6. ボーン名は小文字・英数字と `_`（アニメの照合は大文字小文字を区別しないので、大文字違いの同名を作らない）。
- [ ] G7. ロケータは「部位が落ちても残る側」のボーンに付ける（`nr_rig.LOCATOR_BONES`）。

### render controller
- [ ] R1. `part_visibility` は `[{"*": true}, {bone: expr}, ...]`（キー 1 つのオブジェクトの配列、`*` が先頭）。
- [ ] R2. **すべてのボーン（服・装備・変異の子ボーンを含む）に「自分と全祖先の条件の AND」**。祖先も自分も条件を持たないボーンだけ省略可。親を隠せば子も隠れる、という前提は**使わない**。
- [ ] R3. enum は `q.property('nr:x') == 'value'`（単引用符・小文字）、int は数値比較。`||` の塊は括弧で囲む。
- [ ] R4. 式に出てくるプロパティは、その render controller を使う全エンティティで定義済み・`client_sync: true`。
- [ ] R5. 配列の添字は `max(0, i) % 長さ` で折り返す。範囲外の値（`nr:ztype` 63 など）は三項演算子で先に分ける。enum は `pre_animation` で数値にしてから添字に。
- [ ] R6. `*` 以外のワイルドカードをボーン名のキーに使わない。
- [ ] R7. 同じジオメトリを重ね描きする上塗りパスを作らない（深度の衝突）。重ねるなら別ジオメトリ（同じボーン名・少し膨らませる）。
- [ ] R8. `is_hurt_color` / `overlay_color` / `on_fire_color` は Molang と `this` で書く。焼け・感電は `overlay_color`。

### マテリアル・テクスチャ
- [ ] M1. 使ってよい名前: `entity_alphatest`, `entity_emissive_alpha`, `entity_emissive_alpha_one_sided`, `entity_alphablend`, `entity_alphatest_glint`（＋必要なら `entity`, `entity_nocull`, `entity_multitexture*`）。**`entity_alphatest_one_sided` は存在しない**。
- [ ] M2. 穴は RGBA **(0,0,0,0)**（RGB も 0）。発光させない画素の α は **255 か 0 の二値**。
- [ ] M3. `entity_emissive_alpha` の発光画素は α=3〜40（強いほど小さく）。光る目以外に中間 α を作らない（validator で α のヒストグラムを検査）。
- [ ] M4. パレット化（P + tRNS）は可。量子化で (0,0,0,0) と発光の α 値を他と混ぜない（tRNS の値を保つ）。
- [ ] M5. エンティティのテクスチャは 1 枚 ≤1024×1024（非 2 冪は可）。ブロック・アイテムのアイコン（アトラス）は ≤256×256。
- [ ] M6. 全テクスチャの Σ(w·h·4) ≤ **150 MiB**（validator が計算して止める）。目安: ゾンビ 512²、ボス 1024²、武器 ≤256×512、小道具 512²（1024² は 4 枚まで）。
- [ ] M7. 車のガラスは `entity_alphablend`（ガラス専用 render controller を最後）か、割れたガラスは `entity_alphatest`。

### client entity・アニメーション
- [ ] A1. client entity は `format_version: "1.10.0"`。アニメもコントローラも `animations` に短い名前で載せ、`scripts.animate` で再生。
- [ ] A2. プロパティは `pre_animation` で `v.nr_*` に落としてからアニメで使う（render controller とコントローラの遷移では `q.property` 直書き可）。
- [ ] A3. ゾンビの常時の状態（切断・這う・死体・感電・燃焼）は**プロパティ駆動の自前コントローラ**で出す。playAnimation に頼らない。
- [ ] A4. 最後の姿勢を保つアニメ（死体の姿勢）は `"loop": "hold_on_last_frame"`。状態の切替は `blend_transition`（回転は `blend_via_shortest_path`）。
- [ ] A5. 被弾ののけぞりの基本は `q.hurt_time` から。振りは `v.attack_time`（エンジンが設定、非攻撃時は負）。
- [ ] A6. 状態ごとの持続エフェクト（断面の滴り・首の噴水）はコントローラの状態の `particle_effects`（`locator` 付き）で。短い名前を client entity の `particle_effects` / `sound_effects` に必ず登録。
- [ ] A7. `q.is_alive` は使わない（NR の死は `nr:state == 'dead'`）。

### playAnimation（スクリプト側への約束）
- [ ] P1. 必ず `controller` を渡す（`nr.` で始まる名前。client entity のコントローラ名と重ねない）。層ごとに名前を分ける。
- [ ] P2. 必ず `stopExpression` と `nextState`（止めるなら存在しない状態名 `"none"`）を渡す。before イベントの中では呼ばず `system.run` で。
- [ ] P3. 一発もののアニメは**加算・最初と最後のキーが 0**。一回転系は `blendOutTime: 0`。
- [ ] P4. ループは `stopExpression` にクライアントで判定できる終わりの条件を入れ、明示停止は同じ controller に `animation.nr.p.none`（長さ 0.05 の空アニメ）を流す。
- [ ] P5. プレイヤーのモーションの全チャンネルを `v.is_first_person ? 0.0 : (...)` で包む（腕だけ一人称で 25%）。腕にはバニラの打ち消し項（`HOLD_CANCEL` / `ATK_CANCEL`）を足す。
- [ ] P6. 一人称の体感は Camera API（`setFov`, `fade`）と `/camerashake` で。

### アタッチャブル（武器）
- [ ] W1. アタッチャブルの `identifier` = アイテムの ID。ジオメトリは 1.16.0、根のボーン `hold` に `binding: "q.item_slot_to_bone_name(c.item_slot)"`、本体は子の `root`（握り = 原点、刃 = -Z）。
- [ ] W2. `controller.render.item_default` を使うなら `materials.enchanted` と `textures.enchanted`（`textures/misc/enchanted_item_glint`）を必ず定義。
- [ ] W3. 持ち方は `hd_space` / `hd_holds` を import して逆算（コピーしない）。めり込み検査（`check_hd_clip` 相当）を通す。
- [ ] W4. 振りは `c.owning_entity->v.attack_time`、一人称は `c.is_first_person`、構えは `q.is_using_item`。

### ブロック
- [ ] B1. format_version ≤ 1.21.120。`minecraft:geometry` と `minecraft:material_instances` を両方書く。
- [ ] B2. 形は 30×30×30 px 以内・各軸で自分のマスと 1px 以上重なる・原点から各方向 30px 以内。キューブ ≤50。
- [ ] B3. `collision_box` / `selection_box` は 1 箱、`[-8,0,-8]`〜`[8,16,8]` の中。配列・高さ 24・`multi_block` 特性は使わない。
- [ ] B4. 1 ブロックの全 material instance で `render_method` を揃える。穴あきは `alpha_test`、ガラスは `blend`。
- [ ] B5. `bone_visibility` のキーは正確なボーン名（ワイルドカード不可）、値は bool か `q.block_state(...)` の式。
- [ ] B6. `light_emission` は整数 0〜15。複数マスの物は別ブロックを積む（`MULTIBLOCKS`）か、大きい物は小道具エンティティ＋バリア。
