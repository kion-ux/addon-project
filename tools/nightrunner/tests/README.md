# NIGHT RUNNER の挙動テスト（`tools/nightrunner/tests/`）

このフォルダの `*.mjs` は `tools/nightrunner/test_nr.py` が **Minecraft 無しで**走らせるテスト。
`@minecraft/server` 2.3.0 / `@minecraft/server-ui` 2.0.0 を「動く偽物」（`tools/nightrunner/test_fakes/`）に
差し替え、偽のワールド・プレイヤー・ゾンビ・tick の進行の中で、手書きのアドオン
（`packs/nightrunner_BP/scripts/main.js` から読み込まれる全部）を実際に動かす。

* **`main.js` がまだ無い間は、ここのテストは走らない**（偽物の自己テストだけが走って 0 で終わる）。
  だから「アドオンができたら通るはず」のテストを先に置いてもよいが、`--strict`（ビルドの最終段）では
  `main.js` が無いこと自体が失敗になる。
* テストの道具（`nr-test`）の全部は `test_nr.py` の先頭の説明と `test_fakes/harness.js` のコメントにある。
  ここには「足し方」と「偽物の約束」だけを書く。

---

## 1. 走らせ方

```text
python3 tools/nightrunner/test_nr.py                          # 自己テスト + 組み込み smoke + ここの *.mjs 全部
python3 tools/nightrunner/test_nr.py -k gore                   # テスト名かファイル名に gore を含むものだけ
python3 tools/nightrunner/test_nr.py --file tests/gore.mjs     # このファイルだけ（組み込み smoke は走らない）
python3 tools/nightrunner/test_nr.py --file tests/gore.mjs -v  # テストごとの結果とアドオンの console.* も出す
python3 tools/nightrunner/test_nr.py --keep                    # 作業フォルダ（build_preview/nightrunner/nr_test_*）を残す
python3 tools/nightrunner/test_nr.py --json build_preview/nightrunner/test_nr.json   # 結果・使った演出・未使用の一覧
```

終了コード: 0 = 全部通った、1 = 失敗あり、2 = 道具が動かない（node が無い・d.ts が読めない）。

---

## 2. ファイルの置き方

| 置くもの | 扱い |
|---|---|
| `tests/<名前>.mjs` | テスト。**ファイルごとに node のプロセスが一つ**（アドオンはファイルごとに一度だけ起動） |
| `tests/<名前>.js` / `.json` | 補助（テストから `./<名前>.js` で import する部品・表）。一緒に作業フォルダへ写る |
| `tests/<フォルダ>/...` | 下のフォルダもそのまま写る（`--file tests/gore/heads.mjs` も可） |

作業フォルダでは `tests/` と `scripts/`（BP の `scripts/` の写し）が並ぶので、アドオンの中身は
`../scripts/...` で直接 import できる（`main.js` が読み込んだものと**同じモジュール**になる）。
`scripts/data/*.js`（生成物）は `DATA` からも読める（`DATA.zombies.ZOMBIES`、`DATA.shapes.SHAPES` など）。

名前は内容が分かるように: `gore_heads.mjs`、`parkour_vault.mjs`、`traps.mjs`、`terminal_forms.mjs` …。

---

## 3. 最小の例

```js
import { test, tick, spawnPlayer, spawnZombie, hit, expect, prop, used } from "nr-test";

test("重い刃で首を斬ると首が飛び、血が噴く", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:w_machete");     // 位置・手に持つアイテム
  const z = spawnZombie("office_worker", { x: 0, y: 64, z: 2 });     // spec の鍵か nr:z_* の ID
  await hit(p, z, { part: "head", damage: 30 });                     // 頭を狙って殴る
  await tick(5);                                                     // tick を進める（必ず await）
  expect(prop(z, "head")).toBeOneOf(["severed", "crushed"]);
  expect(used().particles["nr:blood_fountain"]).toBeGreaterThan(0);
});
```

よく使う形:

```js
import { test, tick, spawnPlayer, answerForm, lastForm, use, expect, expectViolation, mc } from "nr-test";

test("端末: 設定でゴアレベルを 40 にする", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:survivor_terminal");
  answerForm(0);                          // ActionForm: 0 番のボタン
  answerForm((f) => {                     // ModalForm: 関数なら開いたフォーム（f.inputs）を見て答えられる
    const v = f.inputs.map((c) => (c.type === "slider" ? c.defaultValue ?? c.min : c.type === "toggle" ? !!c.defaultValue
      : c.type === "dropdown" ? c.defaultValueIndex ?? 0 : c.defaultValue ?? ""));
    v[f.inputs.findIndex((c) => c.label.includes("ゴア"))] = 40;
    return v;                             // 入力の値の配列（入力の数と順は f.inputs のとおり。"defaults" で既定値のまま）
  });
  await use(p);                           // before で取り消して system.run で開く → 次の tick に開く
  await tick(3);                          // フォームの答えは開いた次の tick に返る
  expect(lastForm().type).toBe("modal");
});

test("わざと違反を起こして、偽物が見つけることを確かめる", async () => {
  const z = mc.world.getDimension("overworld").spawnEntity("nr:z_office_worker", { x: 0, y: 64, z: 2 });
  await expectViolation(() => z.setProperty("nr:head", "gone"), "property");   // 記録から消えるので失敗にならない
});
```

---

## 4. テストが失敗になるもの

* テストの例外・`expect` の失敗
* **契約違反**（アドオンが try/catch で握りつぶしても残る）: RP/BP に無い ID（パーティクル・効果音・アニメ・
  エンティティ・アイテム・ブロック・構造物とそのパレット・BP イベント・プロパティ）、enum に無い値・範囲外の int、
  NaN / Infinity の座標や Molang 値、オプションの辞書の綴り違い（`stopExpresion` など。実機は黙って無視する）、
  before イベントの中の書き換え・subscribe・フォームの show、worldLoad 前の `world`、プレイヤーへの `applyImpulse`、
  1.x の形の API、server-ui 1.x の形、入力の間の label / header / divider、`animation.nr.*` の playAnimation に
  controller（`nr.` で始まる）・stopExpression・nextState が無い、1 tick のパーティクル 300 個超、
  ゲームに無いグローバル（`setTimeout` など）… 全部の一覧は `test_nr.py` の先頭
* アドオンの購読者・`system.run*`・`runJob`・カスタムコンポーネントの中の捕まらない例外、捕まらない Promise の reject
* アドオンの `console.error`
* tick を進めずに止まった `await`（フォームの答え・`waitTicks`・`runTimeout` は `tick()` しないと来ない）

`console.warn` と「偽物の限界」（下の §6）は数えて出すだけで、失敗にはしない。

---

## 5. 偽物の約束（実機と違うかもしれない所はここに合わせて書く）

**時間**

* 何も勝手には進まない。**`tick(n)` だけが時間を進める**。1 tick の順: 前の tick に書いたプロパティを反映 →
  プレイヤーの入力 → 物理 → 効果・火・死体の片付け → ブロックの onStepOn / onStepOff / onTick → after イベント →
  `system.run` / `runTimeout` / `runInterval` / `waitTicks` / フォームの答え → `runJob`（1 tick に最大 256 歩）→ after イベント → 消すもの。
* `system.run` は**いつも次の tick**（実機はイベントの中なら同じ tick の終わりのこともある。どちらでも動くように書く）。
* 道具（`hit`・`use`・`press` など）は、その場で after イベントまで流してから戻る。
* `setProperty` の値は**次の tick まで `getProperty` に出ない**（d.ts server:L7592 のとおり）。`triggerEvent` の
  set_property も同じ。テストの `prop()` は書いた最新の値を返す。状態の真実はアドオン側の表に持つこと（script_api.md §17）。
* テストの始めの時刻は 1000（朝）。`setTime(t)` で変える。13000〜22999 が夜。
* `Math.random` は決まった種の乱数（同じテストは毎回同じ結果）。

**ワールド**

* 地面は平ら: `y < 64` が石（63 は草）、`y >= 64` が空気。立つ高さは 64。`setGround(y)` / `setGround(null)`（奈落）。
* 光: 空が開いていれば昼 15・夜 4、屋根の下は 0、光るブロック（BP の `minecraft:light_emission` とバニラの松明など）から
  1 ブロックごとに 1 減る。`setLight(n)` か `setLight((loc) => n)` で固定できる。
* 物理: 重力 0.08/tick、縦の減衰 0.98、横の減衰は空中 0.91・地上 0.546。空中に出したもの・足元が消えたものは落ちる。3 ブロックを超えて
  落ちると落下ダメージ。弾（`minecraft:projectile`）は当たり箱とブロックに当たって `projectileHit*` を出す。
* プレイヤーの移動（`setInput`）: 歩き 0.215、走り 0.28、しゃがみ 0.065 ブロック/tick。`x` = 右、`y` = 前（実機の符号は要確認）。
* 向き: yaw 0 = 南（+Z）、90 = 西（−X）。前 = `(−sin yaw, 0, cos yaw)`、右 = `(−cos yaw, 0, −sin yaw)`。
* ダメージ: 同じ相手への 10 tick 以内の一撃は、前より大きい分だけ通る（実機の無敵時間）。`damage_sensor` の
  `deals_damage: "no"` は `entityHurt` を出さない。体力 0 で `entityDie`、20 tick 後に消える（プレイヤーは復活して `playerSpawn`）。
* 構造物の `Rotate90` は上から見て時計回り、置く位置は回した後の最小の角（**要実機確認**。`scripts/data/structures.js`
  の markers も同じ規則で回す）。`structure_void` は置かない。
* random tick は起きない。onRandomTick を試すときは `randomTick(pos)`。

**テストの間**

* テストごとにワールド（エンティティ・ブロック・時刻・光・フォームの答え）は片付ける。
  **アドオンの中の状態（モジュールの変数・ワールドの動的プロパティ）と `runInterval` は残る**。
* 前のテストで予約された `runTimeout` が次のテストの中で走ることがある。何 tick もまたいで持つ Entity は
  使う直前に `isValid` を見る（片付けられたエンティティを触ると実機と同じく `InvalidEntityError`）。
* テストの順に頼らない（`-k` で一つだけ走らせても通るように）。

**テストのコードの中でも**

* `setTimeout` / `setInterval` / `fetch` は使えない（ゲームに無いので、読んだだけで違反）。待つのは `await tick(n)`。
* テストのコードがした違反も失敗になる。わざと起こすときは `await expectViolation(fn, "種類")`。

---

## 6. 偽物の限界（「[偽物の限界] … は偽の @minecraft/server に無い」と出たら）

d.ts にあるのに偽物が手書きしていない関数を、アドオンが呼んだという意味（アドオンの不具合ではない）。
結果の最後に `偽物の限界: Xxx.yyy ×n` と数が出る。必要なら `test_fakes/server.js` の該当クラスに足し、
`test_fakes/selftest/` に正しい使い方と壊れた使い方の自己テストを足す（`python3 tools/nightrunner/test_nr.py --selftest`）。
偽物のクラスに d.ts に無い公開メンバーを足してはいけない（自己テストが落ちる）。中の状態は `_` で始まる名前か `S`（`globalThis.__nr`）に置く。

---

## 7. 書くときの目安

* 一つのテストで一つのこと。名前は「何をすると何が起きるか」。
* 「演出が出た」は `used()`（このテストの分）で数える: `particles` / `sounds` / `anims` / `events` / `props`（`"nr:head=severed"`）/
  `spawned` / `structures` / `effects` / `molangVars`（`"パーティクル 変数名"`）/ `hurts` / `deaths` / `camera` / `titles` / `actionbars`。
  無い ID は 0 が返る。
* 部位は `PARTS`（`head` `torso` `arm_r` `arm_l` `leg_r` `leg_l`）。`partPoint(z, "arm_r:1")` で 2 つめの箱（前腕）。
  `nr:state` が `crawl` / `down` / `dead` なら寝た姿勢の箱になる。
* 全ゾンビを回すときは `zombieTypes()`（ztype の順）。50 体 × 部位 × 武器のような総当たりは 1 ファイルを数十秒以内に。
* `--json` の `coverage` に、RP/BP にあるのに一度も使われなかった `nr:` のパーティクル・効果音・アニメ・エンティティ・構造物が出る。
  使われない演出を見つける手がかりにする。
