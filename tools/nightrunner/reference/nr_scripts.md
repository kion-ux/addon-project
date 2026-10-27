# NIGHT RUNNER — 手書きスクリプトの共通 API（`core/` と `gore/`）

`packs/nightrunner_BP/scripts/` の **土台**（`core/` と `gore/`）が他のフォルダ（`zombies/` `player/` `combat/`
`world/` `ui/`）に公開する関数・定数・出来事の一覧。**ここに書いた名前と引数は約束**（変えるときはこの文書も直す）。
契約の元は `tools/nightrunner/DESIGN.md` §3（プロパティ）・§4（体力・部位・ゴア）・§5（gib）・§12（データ・BP イベント・
`applyHit`）・§13（描画）。API の根拠は `reference/script_api.md`（@minecraft/server 2.3.0 / server-ui 2.0.0、安定版だけ）。

* import はファイルからの相対パス（例 `combat/melee.js` から `import { applyHit } from "../gore/gore.js";`）。
* **ゾンビへのダメージは必ず `applyHit`**（`gore/gore.js`）。`entity.applyDamage` を直接ゾンビに使わない
  （バニラの赤い点滅だけが欲しい時は `hurtVanilla`）。死なせるのも `applyHit` か `kill`（`gore/death.js`）。
* ゾンビのプロパティ（`nr:head` `nr:state` …）は `setPart` / `setState` / `setArmor`（`gore/gore.js`）で書く
  （`setProperty` は次の tick まで `getProperty` に出ない。同じ tick の読み直しは `partState` / `stateOf` が正しい）。
* パーティクルは `particle()`（`core/fx.js`）だけ。1 tick 300 の予算（`core/budget.js`）と ID の検査を通る。
  演出の ID は `tools/nightrunner/nr_registry.py`（`scripts/data/fx.js`）に載っているものだけ。
* モジュールの最上位では subscribe・`onBlockComponent` / `onItemComponent`・`setMeleeResolver` などの登録だけをする。
  `world` を触る初期化は `world.afterEvents.worldLoad` か `system.run` の中。before イベントの中ではワールドを書き換えない
  （`applyHit`・`set()`・演出も before の中から呼ばず `system.run` へ）。
* 型は JSDoc（`check_nr_types.py` が tsc で検査。0 件が条件）。`Vector3` などは `import("@minecraft/server")` の型。

---

## 1. 起動の順と各フォルダの入口

`main.js` は import するだけ（処理を書かない）。順は `core/util → bus → settings → budget → fx → hp → components`、
`gore/hitloc → blood → gibs → death → gore`、その後に各フォルダの `index.js`（`zombies → player → combat → world → ui`）。
各フォルダの持ち主は**自分の `index.js` だけ**を編集し、そこから自分のモジュールを import する（`main.js` は触らない）。

| 段階 | 起きること |
|---|---|
| import（early execution） | 各モジュールの最上位: subscribe、`onBlockComponent` / `onItemComponent`、`setMeleeResolver` など |
| `system.beforeEvents.startup` | `core/components.js` が BP の全カスタムコンポーネントを登録（下の §9） |
| `world.afterEvents.worldLoad` | `core/settings.js` が設定を読む（それまで `get()` は既定値）→ `EV.SETTINGS {key: "*"}` |
| 毎 tick | gib の物理（1 tick）、死体（1 tick）、噴水（3 tick ごと）、毒の雲（10 tick ごと）、状態のタイマー |

---

## 2. `core/util.js` — ベクトル・乱数・エンティティの小物

| 関数・定数 | 説明 |
|---|---|
| `DEG`、`UP`、`DOWN` | 度→ラジアン、`{0,1,0}`、`{0,-1,0}` |
| `v3(x?, y?, z?)` `add(a, b)` `sub(a, b)` `scale(a, s)` `addScaled(a, b, s)` | ベクトル（`a + b·s`） |
| `dot(a, b)` `len(a)` `lenXZ(a)` `dist(a, b)` `distXZ(a, b)` | 内積・長さ・距離 |
| `norm(a, fallback?)` `flat(a, fallback?)` `lerpV(a, b, t)` `lerp(a, b, t)` | 正規化（長さ 0 なら fallback、既定 +Z）・水平だけ |
| `clamp(v, lo, hi)` `clamp01(v)` `finiteVec(v)` | 丸め・有限の `{x,y,z}` か |
| `yawForward(yaw)` `yawRight(yaw)` `yawOfDir(d)` `yawOf(e)` | yaw（度。0 = 南 +Z、90 = 西 −X）と向き |
| `toLocal(origin, yaw, p) → [r,u,f]` `toWorld(origin, yaw, ruf)` | ゾンビの局所座標（r = 右、u = 上、f = 前）とワールドの変換 |
| `dirToLocal(yaw, d) → [r,u,f]` `dirToWorld(yaw, ruf)` | 向きの変換 |
| `rand(lo, hi)` `randInt(lo, hi)`（両端含む） `chance(p)` `pick(arr)` `jitterDir(d, s)` `rangeVal(v, def)` | 乱数（`rangeVal([lo,hi])` は範囲の乱数、数はそのまま） |
| `valid(e)` | 有効なエンティティか（例外は false）。**何 tick もまたいで持つ Entity は使う前に必ず** |
| `now()` | `system.currentTick` |
| `isZombieId(typeId)` `isZombie(e)` `isPlayer(e)` `zkey(typeId)` | `nr:z_*` か・プレイヤーか・`nr:z_office_worker → office_worker` |
| `getProp(e, name, def)` `setProp(e, name, value)` `trigger(e, event)` | 例外を握る薄い包み（失敗は警告 1 回で false） |
| `dpNum(e, key, def)` | 数の動的プロパティ |
| `despawn(e)` | `remove()`、駄目なら BP イベント `nr:despawn` |
| `warnOnce(key, ...msg)` `safe(label, fn)` `later(ticks, fn)` | 警告 1 回・例外を握って呼ぶ・n tick 後（`system.runTimeout`） |

---

## 3. `core/bus.js` — モジュール間の通知

`on(name, fn) → 解除関数`、`off(name, fn)`、`once(name, fn)`、`emit(name, data)`（同期。購読者の例外は警告だけ）、
`listeners(name)`。名前は定数 `EV` を使う。**中身（data）の形**:

| `EV.*` | いつ | data |
|---|---|---|
| `HIT` `"hit"` | `applyHit` の最後（取り消し・弾き・死体も） | `HitResult`（§10.3） |
| `SEVER` `"sever"` | 腕・脚・頭・下半身がちぎれた | `{zombie, part, state, from, attacker, hit, gib, corpse}` |
| `DECAP` `"decap"` | 首が飛んだ（`nr:head = severed`） | `{zombie, attacker, hit, corpse}` |
| `CRUSH` `"crush"` | 頭が弾けた（`crushed`） | `{zombie, attacker, hit, corpse}` |
| `HEADSHOT` `"headshot"` | 頭に飛び道具・ヒットスキャン、または首が飛ぶ・頭が弾ける近接 | `{zombie, attacker, hit, kill, part: "head"}` |
| `GUTTED` / `HALVED` | 腹が裂けた / 胴が真っ二つ | `{zombie, attacker, hit, corpse}` |
| `KILL` `"kill"` | 死んだ（体力 0・即死部位・弱点・オーバーキル） | `{zombie, key, attacker, hit, cause, pos, overkill, explode?, decap, crushed, headshot, environment, byPlayer, corpse, pose}`（オーバーキルは `{zombie, key, attacker, hit, cause: "overkill", pos, overkill: true, corpse: false, byPlayer, headshot: false}`） |
| `ARMOR_BREAK` | `nr:armor` が 1 段下がった | `{zombie, armor（新しい段階）, part, attacker, breakable（装甲でなく壊れる部品）, hit}` |
| `WEAKSPOT` | spec の `gore.weak_spots` に当たった | `{zombie, part, zone, ability?, once, first, attacker, hit, corpse}`（能力の発動は `zombies/abilities.js`） |
| `STAGGER` / `KNOCKDOWN` | よろめいた / 倒れた | `{zombie, ticks}` |
| `CRAWL` | 這う状態になった（`nr:to_crawl`） | `{zombie, attacker, hit}` |
| `REGROW` | spec の `gore.regrow` で部位が生え戻った | `{zombie, part}` |
| `CORPSE` | 死体ができた / 消えた | `{zombie, created, kind: "normal" \| "ash" \| "melt"}` |
| `GIB` | gib が出た | `{gib, part（nr:part の番号）, zombie?, ztype}` |
| `SETTINGS` | 設定が変わった | `{key, value}`（まとめて変わった・読み込んだ時は `key: "*"`） |

---

## 4. `core/settings.js` — 設定（ワールドの動的プロパティ `nr:settings` に JSON 1 本）

| 関数 | 説明 |
|---|---|
| `get(key)` / `num(key, def)` | 値（worldLoad 前は既定値）/ 数として |
| `set(key, value) → boolean` | 型と範囲（`SETTINGS_SCHEMA` の min..max・options）で検査して丸め、保存して `EV.SETTINGS`。受け付けたら true |
| `setMany(obj) → 数` / `reset()` / `all()` / `isReady()` | まとめて・既定へ・写し・読み込み済みか |
| `onChange(fn)` | `EV.SETTINGS` の購読（解除関数を返す） |
| `gore() → 0..1` | ゴアレベル `G = gore_level / 100`（**既定 1 = 最大**） |
| `difficulty()` | `DIFFICULTY[settings.difficulty]` の倍率表（`zombie_hp_mult` など） |
| `tuning(name, fallback)` | `data/settings.js`・`data/zombies.js` の表を名前で（`GORE_TUNING`、`LOOT_TABLES` …） |
| `DEFAULTS` | 既定値（`SETTINGS_DEFAULTS`） |

ゴアに効く設定: `gore_level`（0..100）、`gib_lifetime_s`（10..300）、`max_gibs`（0..128）、`corpse_lifetime_s`（10..600）、
`max_corpses`（0..64）、`blood_decal_mult`（0..2）、`screen_blood`（bool）、`particle_budget`（50..300）。

---

## 5. `core/budget.js` — 1 tick のパーティクル予算（DESIGN §11: ≤ 300）

`PRIO = {LOW: 0, NORMAL: 1, HIGH: 2, CRITICAL: 3}`。その tick に使える割合は LOW 55% / NORMAL 80% / HIGH 95% / CRITICAL 100%
（上限 = 設定 `particle_budget`、最大 300）。飾り（LOW）が手応え（HIGH）を食い潰さない。

| 関数 | 説明 |
|---|---|
| `take(n = 1, prio = NORMAL, all = true) → 取れた数` | `all` なら全部取れる時だけ |
| `left(prio)` / `can(n, prio)` | 残り / 取れるか（取らない） |
| `pressure(prio) → 0..1` | 混み具合（1 = 空いている）。演出の数を減らすのに掛ける |
| `stats()` | `{tick, used, cap, denied, deniedTotal}` |

`particle()` が自動で 1 点ずつ取るので、普通は直接呼ばない（自前で `spawnParticle` しない）。

---

## 6. `core/fx.js` — 演出の薄い包み

| 関数 | 説明 |
|---|---|
| `particle(dim, id, loc, vars?, prio = NORMAL, cost = 1) → bool` | `id` は `"nr:blood_spray"` か `"blood_spray"`。`vars = {名前: 数}` は Molang の `variable.<名前>`（パーティクル側 `v.<名前>`）。登録簿に無い ID・予算切れ・有限でない位置は出さない |
| `particles(dim, id, points, vars?, prio?) → 出せた数` | 同じものを複数の点に |
| `molang(vars) → MolangVariableMap` | `{名前: 数}` から |
| `sound(dim, id, loc, {volume?, pitch?}?) → bool` | 位置の音。1 tick 40 個まで、同じ音・1.5 ブロック以内の重複はまとめる |
| `playerSound(p, id, opts?)` | その人だけに聞こえる |
| `zombieAnim(z, name, opts?) → bool` | 一発アニメ `animation.nr.z.<name>`。**必ず** `controller: "nr.z.os"`、`stopExpression: "q.any_animation_finished"`、`nextState: "none"`、`blendOutTime: 0.15`（`ONESHOT`。DESIGN §13 / rendering.md P1・P2）。登録簿の一発もの（`react_head` `react_torso` `react_arm_r/l` `react_leg_r/l` `react_heavy` `knockdown` `getup` `grab` `bite` `shoved` `climb_up` `stunned` `burn_flail` `uv_recoil` `alert` `sever_recoil` `kicked`）と `ab_*` `atk_*` `walk_*` `run_*` |
| `playerAnim(p, name, opts?)` | プレイヤーのモーション `animation.nr.p.<name>`（層の既定 `nr.p.act`） |
| `fade(p, {red, green, blue}, fadeIn, hold, fadeOut)` | 画面を色で覆う（秒） |
| `shake(p, intensity 0..4, seconds, type?)` | `/camerashake`（Camera API の揺れはベータなので） |
| `ONESHOT`、`PRIO` | 上の既定値・優先度（`budget.js` の再輸出） |

ゾンビの**常時の見た目**（切断・這う・死体・燃焼・感電）は playAnimation ではなく、プロパティ駆動の RP のコントローラ。

---

## 7. `core/hp.js` — ゾンビの「本当の体力」（DESIGN §4）

`minecraft:health` は大きなプール（1000）。本当の体力は動的プロパティ `nr:hp`（最大 `nr:hp_max`）。初回は
spec の `hp × difficulty().zombie_hp_mult`（設定 `difficulty_scaling` なら × 人数）。

| 関数・定数 | 説明 |
|---|---|
| `HP_KEY = "nr:hp"`、`HP_MAX_KEY = "nr:hp_max"` | 動的プロパティの名前 |
| `zombieSpec(k)` | spec（`data/zombies.js` の ZOMBIES の行 + `ztype`）。`k` は鍵・ID・エンティティ |
| `ztypeOf(k)` / `zombieKeys()` | 種類番号（不明は 63）/ 全部の鍵 |
| `baseHp(key)` | 基本体力 × 難易度 × 人数 |
| `initHp(z, hp?)` | 無ければ入れる（`hp` を渡すと上書き。ボスの段階など） |
| `hpOf(z)` `maxHpOf(z)` `hpFraction(z)` | 今の体力・最大・割合 |
| `setHp(z, v)` `addHp(z, d)` `setMaxHp(z, max)` | 書く（0..最大）・足す・最大を変える（割合を保つ）。**ダメージは `applyHit` で**（これは回復・能力用） |
| `resetPool(z)` | プールを満タンへ（`entityHurt` の後に gore.js が呼ぶ） |
| `reserve(z, cause?)` / `consumeReservation(z, cause)` | スクリプトの `applyDamage` を `entityHurt` で二重に数えない予約（3 tick 有効） |
| `hurtVanilla(z, amount = 1, attacker?, cause = override) → bool` | バニラの被弾（赤い点滅・のけぞり）だけ。予約して `applyDamage`、本当の体力は減らない |
| `forget(id)` | 予約を捨てる |

---

## 8. `entityHurt` の流れ（gore.js が購読。他のモジュールは購読しなくてよい）

1. `world.afterEvents.entityHurt`（`entityTypes` = 全ゾンビ）: プールが 0 以下 → **オーバーキル**（`death.overkill`、全身が弾ける）。
2. `resetPool` → 予約済み（`hurtVanilla` など）なら読み飛ばす → 死体なら無視（死体は BP の `damage_sensor` で来ない）。
3. `hurtToHit(z, damage, src)` で hit を作り `applyHit`。原因ごと:
   * `entityAttack` / `ramAttack` / `maceSmash`: プレイヤーなら **`setMeleeResolver` の関数**（無ければ / undefined を返したら
     `defaultMeleeHit` = 手の武器 `WEAPON_BY_ID` の dtype・weight・gore_power、ItemStack の動的プロパティ `nr:mods`（JSON）、
     バニラの道具は剣 = 斬・斧 = 重い斬・素手 = 軽い打撃）。プレイヤー以外は中くらいの打撃。
   * `projectile`: 着弾点（`projectileHitEntity` の位置と向き）と **`setProjectileResolver` の関数**（既定は飛び道具の ID → 撃った武器）。
   * 爆発 → blast、火・溶岩 → fire、雷 → shock、`fall` → 脚（10 以上なら胴も）への重い打撃、接触・鍾乳石 → trap の刺突、
     金床・落下ブロック → 頭への打撃、魔法・ウィザー → toxic、その他はゴアなしのダメージだけ。
4. `entityDie`（プールを超えた・`/kill`）→ オーバーキル。
5. 死体を殴る（`entityHitEntity`）・撃つ（`projectileHitEntity`）→ `applyHit(..., {corpse: true})`（死体の切断・吹き飛び）。
6. `entitySpawn` / `entityLoad` → `initZombie`（`nr:hp`、`nr:armor = initial_armor`、spec の `pre_damage`）。

---

## 9. `core/components.js` — カスタムコンポーネント（Custom Components V2）

BP のブロック・アイテムの JSON が使う `nr:*` の名前は `scripts/data/components.js`（`gen_nr_data_js` が BP を走査して書く:
`BLOCK_COMPONENTS` `ITEM_COMPONENTS` `BLOCK_COMPONENT_USERS` `ITEM_COMPONENT_USERS` `UNTICKED_BLOCKS`）。
`system.beforeEvents.startup` で**全部**登録する（JSON が使うのに登録が無いと実機ではそのブロック／アイテムが読み込みエラー）。
振る舞いは各モジュールが**モジュールの最上位（import の時）**に足す:

```js
import { onBlockComponent, onItemComponent } from "../core/components.js";
import { applyHit } from "../gore/gore.js";
import { isZombie } from "../core/util.js";
onBlockComponent("nr:trap", {
  onStepOn(e, params, name) {            // e = BlockComponentStepOnEvent、params = JSON の値（unknown → JSDoc で型を付ける）
    const p = /** @type {{damage?: number}} */ (params);
    const z = e.entity;
    if (z && isZombie(z)) applyHit(z, { source: "trap", dtype: "pierce", weight: "light", damage: p.damage ?? 4, part: "leg_r" });
  },
  onTick(e, params) { /* JSON に minecraft:tick が要る */ },
});
onItemComponent("nr:weapon", { onBeforeDurabilityDamage(e) { e.durabilityDamage = 0; } });
```

| 関数・定数 | 説明 |
|---|---|
| `onBlockComponent(name, handlers) → 外す関数` | ブロックのフック: `beforeOnPlayerPlace` `onEntityFallOn` `onPlace` `onPlayerBreak` `onPlayerInteract` `onRandomTick` `onStepOff` `onStepOn` `onTick`（2.3.0 の d.ts。`onBreak` はベータ専用で無い） |
| `onItemComponent(name, handlers) → 外す関数` | アイテムのフック: `onBeforeDurabilityDamage` `onCompleteUse` `onConsume` `onHitEntity` `onMineBlock` `onUse` `onUseOn` |
| `dispatch(kind, name, hook, ev, params) → 呼んだ数` | 配る中身（テスト・デバッグから直接呼べる） |
| `hasHandler(kind, name, hook)` / `componentStatus()` | ハンドラがあるか / `{started, block: {名前: [登録したフック]}, item}` |
| `BLOCK_HOOKS` / `ITEM_HOOKS` | フックの名前 |

* ハンドラの引数は `(event, params, name)`。`params` は JSON に書いた値の辞書（`CustomComponentParameters.params`）。
* 登録するフックは **startup の時点でハンドラがあるものだけ**（無いフックは登録しない = 何も起きない）。`onPlayerInteract`
  を登録するとブロックが「触れる」ブロックになり手のブロックをその面に置けなくなる、`onTick` は `minecraft:tick` の無い
  ブロックで実機がコンテンツエラー、などの副作用を避けるため。startup の後に足したハンドラは、そのフックが登録済みの時だけ届く（警告）。
* `onTick` を足した名前を `minecraft:tick` の無いブロックが使っていると startup で警告（`UNTICKED_BLOCKS`。JSON 側を直す）。
* 同じ（名前, フック）に複数のハンドラ: 足した順に全部。1 つの例外は他を止めず `console.error`（テストでは失敗になる）。
* `beforeOnPlayerPlace` は before イベント（読み取り専用。`e.cancel = true` で置くのを止める。書き換えは `system.run` へ）。
* 2026-10 時点の BP の名前: ブロック `nr:ambient_fx` `nr:craft_bench` `nr:fire_barrel` `nr:knockable` `nr:landing`
  `nr:multiblock` `nr:random_variant` `nr:stash` `nr:street_lamp` `nr:trap` `nr:uv_lamp` `nr:zipline`、アイテム `nr:weapon`。

---

## 10. `gore/gore.js` — ゴアの結果の決定と適用（DESIGN §4 / §12）

### 10.1 `applyHit(zombie, hit) → HitResult | undefined`

ゾンビ（死体も）に一撃を入れる**唯一の入口**。体力・部位・装甲・ゴア・死亡・演出・通知が一度に決まる。ゾンビでなければ
undefined。before イベントの中から呼ばない。連鎖（爆発 → 周りの applyHit → …）は深さ 4 まで。

`hit`（DESIGN §12 の形 + 追加。全部省略可）:

| フィールド | 説明 |
|---|---|
| `attacker` | 攻撃者（プレイヤーなら経験値・画面の返り血・背後の判定） |
| `part` `sub` | 部位 `head` `torso` `arm_r` `arm_l` `leg_r` `leg_l`、箱 0 = 上（胸・上腕・太腿）/ 1 = 下（腹・前腕・脛） |
| `point` | 当たった点（ワールド）。無ければ攻撃者の目からのレイ → 狙いの高さ（§11） |
| `dir` | 打たれた向き（攻撃者 → ゾンビ）。無ければ攻撃者・点から |
| `dtype` | `slash` `blunt` `pierce` `blast` `fire` `shock` `toxic` `uv`（それ以外は blunt） |
| `weight` | `light` `medium` `heavy` |
| `damage` | 体力の点（耐性・部位の倍率の前）。無ければ武器の `damage` |
| `power` | 0..2（1 = 普通）。吹き飛び・血・gib の勢い（既定は weight から） |
| `source` | `melee` `projectile` `hitscan` `blast` `trap` `fire` `shock` `toxic` `fall` |
| `weapon` | `WEAPON_BY_ID` の値か武器の ID（`gore_power` `crit_mult` `knockback` `sever_bias` を読む） |
| `mods` | `{改造の鍵: 段階}`（`bleed` → gore_power 加算、`impact` → 骨折・よろめき・押し返し） |
| `corpse` | 死体への一撃（体力は減らない・切断と吹き飛びだけ） |
| `crit` | 会心（undefined なら近接は `COMBAT_TUNING.crit_base_chance` で振る。false で無し） |
| `heavy` | 溜め攻撃（`COMBAT_TUNING.heavy` の倍率・ゴア加算） |
| `gorePower` | 切断・破壊の起きやすさ 0..1.3（無ければ武器の `gore_power`、無ければ dtype と weight から） |
| `outcome` | 結果の指定（罠・とどめ）: `"severed"`（当たった部位）か `{部位か系統: 結果 \| [結果, 確率]}` |
| `parts` | 複数の部位に同時に効く（落下・爆発。体力は一度だけ減る）。部位も点も無い blast は全身 |
| `knockdown` | 倒す（`nr:state down`）。`stunTicks` 感電の長さ。`burn` `nr:burn` をこの段階まで |
| `noGore` `noKnockback` `noAnim` `noVanilla` | 部位を進めない・押し返さない・一発アニメ無し・バニラの被弾（赤い点滅）無し |

### 10.2 決まり方

1. **部位**: `hitloc.locate`（§11）。死体・這い・倒れは寝た姿勢の箱。
2. **ダメージ** = `damage × 耐性 resist[dtype]（uv は resist.uv、既定 0）× 部位の倍率`（頭 = spec の `gore.head_mult`（既定 2.0）、
   胴 1.0、腕 0.7、脚 0.8 = `COMBAT_TUNING.hitzone_mult`）× 弱点 `weak_spots[].mult` × 会心（武器の `crit_mult`、既定 1.5）×
   背後（`backstab_mult`）× 溜め。
3. **`onBeforeHit` の細工**（能力の盾・回避・重い体）: `ctx.damage` を変える・`cancel`（何も起きない）・`deflect`（火花だけ）・
   `noGore` `noStagger` `noKnockback`。
4. **装甲**（spec の `gore.armored` の部位で `nr:armor >= armor_strip[部位]`）: 切れない・火花、ダメージは
   `(armor_mult + ARMOR_T[dtype_mult]) / 2` 倍、装甲の耐久（`armor_hp × armor_break[dtype]` で減る）が尽きると
   `nr:armor` が 1 段下がる（`EV.ARMOR_BREAK`）。装甲の無い種類の「壊れる部品」（`gore.breakables`）は弱点への命中で段階が下がる。
5. **部位の状態**（ゴア）: 部位体力 = 最大体力 × `PART_HP_FRAC`（頭 0.45 / 腕 0.35 / 脚 0.4 / 胴 0.9）。
   強さ = (この一撃 / 部位体力) × (0.4 + gorePower)（死体は × 1.4）。候補は表（DESIGN §4）の weak / mid / strong:
   strong は「部位体力の累積を超えた」か確率 `(強さ − 0.55) / 0.5`、mid は強さ ≥ 0.5 か累積 ≥ 0.6、weak は 0.12 / 0.25。
   * **切断・破壊**（cut_lower / cut_upper / severed / crushed / halved）の確率には `G^sever_mult_exp`（0.8）と spec の `sever_mult`。
   * 結果は spec の `DTYPE_OUTCOMES[dtype][系統]` に載っているもの（＋ どの種別でも wounded / slashed）だけ、
     `GORE_TUNING.min_g` 未満のゴアレベルでは起きない（例 halved は 60、crushed は 40、切断は 30。**G = 0 は切断なし**）。
   * spec の `no_sever`（その部位は切断・破壊されない）、`halve: false`（真っ二つにならない）。状態は重い方へしか進まない。
   * 斬撃の strong は当たった箱で決まる（前腕・脛 = cut_lower、上腕・太腿 = cut_upper）。武器の `sever_bias` で上書き。
   * 打撃の胴は肋骨が折れて倒れる（`knockdown`。骨の gib）。
6. 演出: 命中の血（`hitFx`）・手応えの音、切断は断面の飛沫と噴水・gib（`gibs.spawnGib`）・音、頭が弾ける（脳・骨・目の gib）、
   腸がこぼれる（`guts_min_g` 40 以上）、真っ二つは下半身の gib。`nr:blood`（0..3）は傷の数。
7. 火 → `nr:burn`（3 で炭化・死体は灰）、感電 → `nr:shock = 1`（`stunTicks` 後に 0）、毒 → 部位は変えない、UV → 夜の種類だけ（resist.uv）。
8. **歩けなくなった**（脚が無い・両脚が折れた・胴が真っ二つ）→ BP `nr:to_crawl` + `nr:state = crawl`（spec の
   `crawl_legless: false` の種類は `nr:root_start` + `down`）。片脚だけ折れた → 鈍足（`slowness`）。
9. **体力**: 死体以外は `nr:hp` から引く（頭 `cracked` は + 最大体力 × 0.25）。`hurtVanilla(z, 0.01)` で赤い点滅
   （`entityHurt` から来た一撃・`noVanilla` は除く）。`nr:hp <= 0`・頭 `severed` / `crushed`・死ぬ弱点（`gas_cloud_death` を
   刺す・`detonate`、`detonate` 持ちに火か爆発）→ `death.kill`。
10. 生きていれば: 転倒（`knockdown`、ボスは `hit.knockdown` の時だけ）かよろめき（ダメージ ≥ 最大体力 × `stagger_frac`）、
    押し返し（`applyKnockback`）、一発アニメ（`sever_recoil` / `react_heavy` / `stunned` / `react_<部位>`。4 tick に 1 回）、
    声 `nr.z.<voice>.hurt`（12 tick に 1 回）。
11. プレイヤーが近く（`GORE_TUNING.screen_blood_range` 3 ブロック）で仕留めた・切り落とした・頭を潰した → 画面の返り血。
    最後に `EV.HIT`。

### 10.3 `HitResult`

`{zombie, key, part, sub, point, dtype, weight, source, attacker, damage（体力から引いた点。死体・弾きは 0）, hp, maxHp,
killed, corpse, armored, armorBroke, deflected, blocked, crit, backstab, weak（当たった weak_spots の行）,
changes: [{part, from, to}], severed: [部位], decap, crushed, headshot, gutted, halved, staggered, knockdown, crawl, hit}`

### 10.4 そのほかの export

| 関数・定数 | 説明 |
|---|---|
| `setMeleeResolver(fn)` | プレイヤーの近接の hit を作る関数（`combat/melee.js`）。`fn(player, zombie, info: {damage, cause, corpse})` の戻り値: hit（`defaultMeleeHit` の上に重ねる）/ `false`（この被弾は無視。combat が自分で `applyHit` する）/ undefined（既定） |
| `setProjectileResolver(fn)` | 飛び道具の同じもの（`info` に `projectile` `point` `dir`） |
| `defaultMeleeHit(player, zombie, info) → Hit` | 既定の近接の解決（resolver から呼んで上書きしてよい） |
| `onBeforeHit(fn) → 解除関数` | `fn(zombie, ctx: HitCtx)`。`ctx = {zombie, hit, part, group, sub, point, damage, cancel, deflect, noGore, noStagger, noKnockback, corpse}` を書き換える |
| `partState(z, part)` / `partsOf(z)` / `stateOf(z)` / `armorOf(z)` | 今の状態（同じ tick に書いた値を含む） |
| `setPart(z, part, value)` / `setState(z, state)` / `setArmor(z, n)` | 直接書く（enum に無い値は書かない。`setState("crawl")` は `nr:to_crawl` も呼ぶ。死体は生き返らない） |
| `stagger(z, ticks = 24)` / `knockdown(z, ticks = 50)` | よろめき（→ normal）/ 転倒（`knockdown` のアニメ → ticks 後に `getup`） |
| `cancelRegrow(z, part?)` | `gore.regrow` の予定を取り消す |
| `initZombie(z)` | 出現時の初期化（自動。手で出したゾンビにも呼んでよい） |
| `hurtToHit(z, damage, src)` | `entityHurt` → hit（§8） |
| `goreSpec(z)` | spec の `gore`（`GORE_DEFAULTS` で埋めた） |
| `ZOMBIE_IDS` | 全ゾンビの ID（イベントの `entityTypes` に） |
| `debugCounts()` | 控えの大きさ（テスト用） |

---

## 11. `gore/hitloc.js` — 当たった部位

当たり箱は `data/zombie_shapes.js` の `SHAPES[key] = {height, width, stand: {部位: [{c: [r,u,f], h: [hr,hu,hf]}…]}, lie, prone?, locators}`
（gen_nr_zombies。ゾンビの足元が原点、r = 右・u = 上・f = 前、ブロック単位）。**まだ無い間は身長から作る人型の箱**で代わりをする
（動的 `import()` で読むので、無くても main.js は止まらない。読めた後は `hasShapes()` が true）。
姿勢: `nr:state` crawl → prone（うつ伏せ。無ければ lie）、down → lie（仰向け）、dead → `nr:pose` 1・5 なら prone、他は lie。

| 関数・定数 | 説明 |
|---|---|
| `PARTS` | `["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"]` |
| `groupOf(part)` / `sideOf(part)` | `head` `torso` `arm` `leg` / `"r"` `"l"` `""` |
| `locate(z, hit, o?) → PartHit` | applyHit の部位決め: `hit.part`（点があれば箱の上下も）→ `hit.point` → 攻撃者の目からのレイ → 狙いの高さ。必ず返す |
| `rayPart(z, origin, dir, o?)` / `pointPart(z, point, o?)` / `heightPart(z, y, rHint?, o?)` | レイ・点・高さで |
| `partCenter(z, part, sub = 0, o?) → Vector3` | 部位の箱の中心（ワールド） |
| `locatorPos(z, name, o?)` / `locatorDir(z, name, o?)` | ロケータ（`loc_neck` `loc_head` `loc_mouth` `loc_chest` `loc_belly` `loc_waist` `loc_shoulder_r/l` `loc_elbow_r/l` `loc_hand_r/l` `loc_hip_r/l` `loc_knee_r/l`）の位置と外向き |
| `inZone(z, partHit, zone, ranged?)` | 弱点のゾーン（`back` `front` `belly` `nodes` `any` …）か |
| `boxesOf(z, o?)` / `shapeOf(key)` / `poseFor(state, pose)` | 箱・形・姿勢 |
| `shapesReady`（Promise）/ `hasShapes()` | SHAPES の読み込み |

`PartHit = {part, sub, point, local: [r,u,f], pose, how: "ray" | "near" | "point" | "height" | "given", t?}`。
`o = {state?, pose?}` で姿勢を指定できる（無ければエンティティのプロパティ）。

---

## 12. `gore/gibs.js` — ちぎれた部位 `nr:gib` と「物理」（DESIGN §5）

| 関数・定数 | 説明 |
|---|---|
| `spawnGib(zombie?, part, dir, power = 1, o?) → Entity \| undefined` | 部位の位置に出し、`nr:ztype` `nr:part` `nr:spin`（1..7）`nr:rest` `nr:bleed` `nr:side` を入れて `applyImpulse` で `dir` へ飛ばす。`part` は `GIB` の名前か番号。`o = {at?, dim?, ztype?, crumble?, kind?, bleed?, spin?}`（ゾンビ無しなら `at` と `dim`）。上限を超えたら古い順に消す。`EV.GIB` |
| `spawnChunks(zombie, n, dir, power?, parts?, o?) → 出した数` | 汎用の肉片をまとめて（数は `n × G`） |
| `kick(gib, dir, power = 1) → bool` | 蹴る・弾く（プレイヤーが殴る・弾が当たると自動） |
| `gibCount()` / `gibList()` / `clearGibs()` | 数・一覧・全部消す |
| `gibPart(part)` | 名前 → 番号 |
| `GIB` | `head 0 jaw 1 arm_r 2 arm_l 3 forearm_r 4 forearm_l 5 leg_r 6 leg_l 7 shin_r 8 shin_l 9 lower 10 guts 11 brain 12 chunk 13 bone 14 eye 15` |
| `GIB_ID = "nr:gib"`、`GENERIC_ZTYPE = 63` | |

物理（スクリプト）: 着地のたびに反発係数 0.38 で跳ね（最大 4 回、`nr.gore.gib_land`、最初の 2 回は地面の血痕）、
転がりに摩擦、止まったら `nr:spin = 0`（RP は `nr:rest` の寝姿）と血だまり 1 つ。動く間は血の尾。断面は 6 秒滴る
（その後 `nr:bleed = 0`）。上限 `max_gibs`（既定 48）・寿命 `gib_lifetime_s`（既定 60 秒、止まった gib は 20 tick ごとに見る）。
炭になる種類（`gore.crumble`）は 2.5〜4 秒で灰になって崩れる。爆風（`detonate`）でも飛ぶ。

---

## 13. `gore/blood.js` — 血の演出

量は全部 `G` と予算で決まる（G = 0 なら出さない）。血の種類 `kind` = spec の `gore.blood`（`red` `dark` `black` `bile` `acid`
`ash` `water` `ember`。ash / ember は血の代わりに灰・火の粉で血だまりを作らない、bile / acid は緑の飛沫を足す）。

| 関数 | 説明 |
|---|---|
| `spray(dim, pos, dir, power?, {kind?, prio?}?)` / `burst(dim, pos, power?, o?)` / `mist(dim, pos, size?, o?)` / `drip(dim, pos, n?, o?)` / `trail(dim, pos, size?, o?)` | しぶき・弾ける・霧・滴り・血の点 |
| `splatGround(dim, pos, size?, o?)` / `splatWall(dim, pos, dir, size?, {kind?, reach?}?)` / `pool(dim, pos, size?, o?)` | 地面の血痕・壁の血痕（±X の面 → `blood_splat_wall_x`、±Z → `_wall_z`、上向き → 地面）・血だまり。地形のレイで貼る場所を探す（1 tick 24 本まで）。寿命は `decalLife()` 秒（G で 30〜120）× 設定 `blood_decal_mult` |
| `fountain(z, loc, ticks?, o?)` / `stopFountains(z)` / `fountainCount()` / `fountainTicks()` | 断面のロケータを追って拍動する噴水（G で 40〜100 tick × spec の `bleed_mult`） |
| `hitFx(z, point, dir, power, {armored?, kind?, bleed?}?)` | 1 回の命中（飛沫・しぶき・後ろの壁・地面）。装甲は火花 |
| `severFx(z, loc, dir, power?, {kind?, fountain?}?)` / `headExplodeFx(z, pos, dir, power?, {kind?, wet?}?)` / `bodyExplodeFx(dim, pos, size?, {kind?, wet?}?)` | 切断・頭が弾ける・全身が弾ける |
| `screenBlood(player, from, intensity?)` | 近くで仕留めた時の画面の返り血（設定 `screen_blood`、G ≥ 50、距離 ≤ 3、16 tick に 1 回） |
| `groundBelow(dim, pos, reach?)` / `kindOf(z)` / `bleedOf(z)` / `makesPools(kind)` / `decalLife()` / `GT` | 補助・`GORE_TUNING` |

---

## 14. `gore/death.js` — 死亡・死体・ルート・特殊な死

| 関数・定数 | 説明 |
|---|---|
| `kill(z, info?) → bool` | 死なせる（applyHit が呼ぶ。罠・能力・コマンドから直接でもよい）: `nr:hp = 0`、BP `nr:on_death`、`nr:state = dead`、`nr:pose`、死の声、spec の `loot`、プレイヤーが関わったら経験値、`gib_extra`、打たれた向きへ吹き飛ぶ、死体の登録（寿命 `corpse_lifetime_s`・上限 `max_corpses`、古い順に消える）、`EV.KILL` `EV.CORPSE`。既に死んでいれば false |
| `overkill(z, info?)` | プールを超えたバニラの死: G ≥ 70（`overkill_burst_min_g`）なら全身が弾ける（部位・肉片の gib、血）、ルート |
| `dropLoot(dim, pos, entries, {scatter?}?) → 山の数` | `[ID, 最小, 最大, 確率]` の並び。文字列（か `{table}`）は `LOOT_TABLES` の名前（例 `"gore_remains"`） |
| `dropXp(dim, pos, xp) → オーブの数` | 4 ずつのオーブ（最大 8） |
| `toxicCloud(dim, pos, {radius, life, poisonS, amp, nauseaS, dmg})` | 毒の雲（プレイヤーに毒・吐き気、ゾンビに toxic のダメージ） |
| `detonate(dim, pos, {radius, dmg, infectedMult?, exclude?, attacker?})` | 爆発（ゾンビは blast の applyHit、gib・死体も飛ぶ、プレイヤーはダメージと押し返しと揺れ） |
| `isCorpse(e)` / `corpseCount()` / `corpseList()` / `clearCorpses()` | 死体 |
| `poseFrom(z, dir, info)` / `POSE` | 死に方: `BACK 0`（仰向け）`FRONT 1` `LEFT 2` `RIGHT 3` `CRUMPLE 4`（首・頭を失って崩れる）`CRAWL 5` `HALF 6`（上半身だけ）`BLOWN 7`（爆発） |
| `setHitHandler(fn)` | 周りへのダメージを流す先（gore.js が applyHit を入れる。他は使わない） |

`KillInfo = {attacker?, hit?, dir?, power?, cause?, decap?, crushed?, overkill?, parts?, state?, burn?, byPlayer?, noLoot?, noXp?, pose?, at?, dim?, key?}`。

特殊な死（spec の `gore`）: `explode`（`explode_kind` toxic = 毒の雲 / blast = 0.5 秒後に爆発 / acid / spores / water）は体が残らず
「遺骸」の表 `gore_remains` を半分の確率で、`crumble`・`corpse: "ash"`・`nr:burn = 3` は灰になって崩れる、`corpse: "melt"` は溶けて消える。
能力 `toxic_death_puff` / `gas_cloud_death` / `detonate` の「死んだ時」の分はここでやる（`zombies/abilities.js` は重ねて出さない）。
死体は物理で動き続け、高い所から落ちて着地すると衝撃のゴア（脚・腕の打撃 `source: "fall"`）。死体はさらに切断できる。

---

## 15. BP（`gen_nr_entities`）に要るもの — スクリプトが前提にしていること

* ゾンビ: DESIGN §3 のプロパティ全部（`client_sync`）、`minecraft:health {value: 1000, max: 1000}`、`minecraft:physics`、押せる体、
  イベント `nr:on_death`（`nr:dead`: AI・移動・攻撃を外し、`damage_sensor` で全ダメージ無効。**だから死体は entityHurt が来ず、
  gore.js が entityHitEntity / projectileHitEntity で切断する**）、`nr:to_crawl`、`nr:root_start` / `nr:root_end`、`nr:enrage` / `nr:calm`、
  `nr:despawn`。仲間内のダメージ（`nr_zombie` 同士）は `damage_sensor` で止めてよい。
* `nr:gib`: DESIGN §5 のプロパティ、小さな当たり箱と `minecraft:physics`、`damage_sensor` で全ダメージ無効（殴ると
  `entityHitEntity` で蹴られる）、`nr:despawn`。
* テストの仮の BP（gen_nr_entities ができるまで）: `tools/nightrunner` の外の作業場で、本物の BP の写しに上の形の仮エンティティと
  登録簿の仮の ID を足したもので `test_nr.py` を走らせて確かめている（content.md の雛形どおり）。

---

## 16. テスト（`tools/nightrunner/tests/`）

| ファイル | 中身 |
|---|---|
| `gore_hitloc.mjs` | 立ち・寝た姿勢の全部位の箱（レイ・着弾点・高さ） |
| `gore_outcomes.mjs` | dtype × 部位の結果（G 100）、G 0 / 50、累積、這う、装甲の段階、火・感電・毒・UV、spec の例外・生え戻り・pre_damage、壊れる部品、破裂・爆発・灰 |
| `gore_death.mjs` | 死亡・死体・ルート・経験値、死体の寿命と上限、死体の切断、オーバーキル、落下のゴア、溶ける・胞子 |
| `gore_gibs.mjs` | gib の出方・跳ね・止まる・上限・寿命・蹴る・爆風・崩れる・G で数 |
| `gore_blood.mjs` | 壁・地面の血痕、噴水、血の種類、画面の返り血、G 0 |
| `gore_budget.mjs` | 予算の割合・設定・群れの爆発でも 300 以下 |
| `gore_hp.mjs` | 本当の体力とプール、entityHurt の流れ、予約（二重に数えない）、`setMeleeResolver`、難易度・人数、`/kill` |
| `core_components.mjs` | カスタムコンポーネントの登録と配り方 |

`tests/gore_util.js` は補助（`setGore` `defaults` `partsNow` `CUT` と hitloc の再輸出）。

---

## 17. 他の担当へのメモ

* `combat/melee.js`: `setMeleeResolver((p, z, info) => ({dtype, weight, damage, gorePower, power, crit, heavy, mods, part?, point?}))`。
  コンボ・とどめで自分で `applyHit` する時は resolver で `false` を返してバニラの一撃を捨てる。武器の耐久は
  `onItemComponent("nr:weapon", {onBeforeDurabilityDamage})`。
* `combat/ranged.js`: ヒットスキャンは `applyHit(z, {source: "hitscan", point, dir, ...})`（`part` は着弾点から決まる）。
* `world/traps.js`: `onBlockComponent("nr:trap", {...})` で踏んだ・tick を受け、ゾンビには `applyHit(z, {source: "trap", outcome: ...})`。
  ブロックのコールバック（`onStepOn` `onTick` `onPlayerInteract` …）の中ではブロック・エンティティを書き換えてよい
  （公式の custom components の例も `onPlayerInteract` で `setPermutation` する。偽物も読み取り専用にしない）。`beforeOnPlayerPlace` だけは before。
* `zombies/abilities.js`: 盾・回避は `onBeforeHit`、弱点・装甲の破壊は `EV.WEAKSPOT` / `EV.ARMOR_BREAK`、能力の段階は `nr:ability`。
  状態は `setState`（`special` など）で書く。
* `player/hud.js`・スキル: `EV.KILL`（`byPlayer`・`headshot`・`decap`・`overkill`）、`EV.SEVER`、`EV.HEADSHOT` を聞く。
* `gen_nr_zombies` が `data/zombie_shapes.js` を出したら、`gore/hitloc.js` の動的 `import()` は静的な import に替えてよい（人型の代わりも残す）。
