# Script API 早見表 — `@minecraft/server` 2.3.0 / `@minecraft/server-ui` 2.0.0

NIGHT RUNNER の手書き JS（`packs/nightrunner_BP/scripts/`）を書く人のための表。
**型の根拠は同梱した公式 d.ts だけ**（npm の公式 tarball を無改変で置いたもの）:

| 記号 | ファイル | 版 |
|---|---|---|
| `server:L1234` | `tools/nightrunner/typings/server/index.d.ts` の 1234 行目 | `@minecraft/server` 2.3.0（manifest の `"version": "2.3.0"`） |
| `ui:L123` | `tools/nightrunner/typings/server-ui/index.d.ts` | `@minecraft/server-ui` 2.0.0 |
| `common:L12` | `tools/nightrunner/typings/common/index.d.ts` | `@minecraft/common` 1.2.0（2.3.0 の peerDependency `^1.2.0`。2.3.0 公開時点の最新） |

* 署名は d.ts からの**そのままの引用**（複数行のものは 1 行に詰めただけ）。行番号は宣言の先頭行。
* 印: **〔E〕** = 早期実行（early execution）中でも呼べる / **〔RO✗〕** = 読み取り専用モード（before イベントの中）では呼べない・書けない /
  **〔T〕** = 例外を投げうる。d.ts の `@remarks` の定型文（"This function can be called in early-execution mode." /
  "This function can't be called in read-only mode." / `@throws`）から機械的に拾った。
* **この文書の ` ```js ` の例はすべて `tsc --checkJs` で検査済み**（§19 の手順で再検査できる）。` ```ts ` は d.ts の引用。
* 実機でしか分からないことは **（要実機確認）** と書いた。§18 にまとめてある。
* **d.ts の中の `@example` は古いものが混じっている**（`entity.applyKnockback(0, 0, 0, 1)` server:L7359 / L6203 / L19289、`world.playSound(...)` server:L13752 / L17604、
  `world.beforeEvents.chatSend` server:L17318、`modalForm.toggle("…", true)` / `slider(…, 0, 50, 5, 30)` ui:L471〜L481 / L619〜L629 は全部 2.3.0 / 2.0.0 では型エラー）。
  例は写さず、署名を見ること。

---

## 0. 型検査（`check_nr_types.py`）

```text
python3 tools/nightrunner/check_nr_types.py            # BP の scripts/**/*.js を検査（無ければ OK で終わる）
python3 tools/nightrunner/check_nr_types.py PATH ...   # 別のフォルダ／ファイル（試験用）
python3 tools/nightrunner/check_nr_types.py --raw      # tsc の出力を全部
NR_SKIP_TYPES=1 ...                                    # Node / npm が無い環境だけ（飛ばす）
```

* TypeScript 5.6.3 を `tools/nightrunner/.node/` に自動で入れる（gitignore 済み）。設定は `tsconfig.nr.json`
  （`checkJs` / `strict: false` / `noImplicitAny: false` / `lib: ["ES2022"]` だけ。DOM・Node は無い）。
* `lib` に DOM が無いので `setTimeout` / `setInterval` / `fetch` / `require` / `process` は「Cannot find name」になる（ゲームにも無い）。
  ゲームにある非標準のグローバルは `console`（`log` / `info` / `warn` / `error`）だけ（`typings/nr_env.d.ts`）。
* JS でも型は付く: `subscribe((ev) => …)` の `ev` は文脈から型が付く。引数の型は JSDoc で付ける。

```js
/** @param {Player} p @param {Entity} z */
function sample(p, z) {
  // 戻り値が和型のものは絞ってから使う（strict でなくても和型のメソッド呼びはエラー）
  const head = String(z.getProperty("nr:head") ?? "intact");
  const hp = /** @type {number} */ (z.getDynamicProperty("nr:hp") ?? 0);
  return head.toUpperCase() + (hp - 1) + p.name;
}
```

* よく出るエラーと意味: `TS2339`（その名前は型に無い＝ベータ専用・1.x の名前・綴り違い）、`TS2554`（引数の数）、
  `TS2349`（`isValid()` のようにプロパティを呼んだ）、`TS2353`（オプション辞書に無いキー）、`TS2724`（import できない名前）、
  `TS2304`（`setTimeout` などゲームに無いグローバル）。
* 型を黙らせる `// @ts-ignore` は使わない（使うなら理由をコメントに）。

---

## 1. 実行の段階と権限（early execution / startup / worldLoad / before イベント）

2.x のスクリプトは**ワールドの読み込みより前に走る**（early execution）。その間に呼べるのは 〔E〕 のものだけ。

| 段階 | 何が起きるか | 呼べるもの |
|---|---|---|
| モジュールの最上位（import 時） | early execution | `world.afterEvents.*.subscribe` / `world.beforeEvents.*.subscribe` / `system.afterEvents.*` / `system.beforeEvents.*` / `system.run*` / `system.clearRun` / `system.runJob` / `system.waitTicks` / `system.currentTick`（全部 〔E〕）。**`world.getDimension`・`world.getDynamicProperty`・`world.getPlayers`・`new ItemStack`・`BlockPermutation.resolve` は 〔E〕 が無い＝呼ぶと例外** |
| `system.beforeEvents.startup` | early execution のまま | 上に加えて `blockComponentRegistry` / `itemComponentRegistry` / `customCommandRegistry` の登録（〔E〕） |
| `world.afterEvents.worldLoad` | 最初の tick の終わり | 全部。**`world` を触る初期化はここか、`system.run` の中** |
| before イベントの中 | 読み取り専用モード | 読むこと・`ev.cancel = true`。〔RO✗〕 のもの（ほぼ全部の「書く」API）は例外。書き換えは `system.run(() => …)` へ逃がす |
| after イベント・`system.run*` の中 | 通常 | 全部 |

```ts
readonly afterEvents: WorldAfterEvents;                 // server:L17304 〔E〕
readonly beforeEvents: WorldBeforeEvents;               // server:L17341 〔E〕 "Event callbacks are executed in read-only mode."
readonly worldLoad: WorldLoadAfterEventSignal;          // server:L18195
subscribe(callback: (arg0: WorldLoadAfterEvent) => void): (arg0: WorldLoadAfterEvent) => void;   // server:L18301 〔E〕〔RO✗〕
readonly startup: StartupBeforeEventSignal;             // server:L16958（SystemBeforeEvents）
readonly shutdown: ShutdownBeforeEventSignal;           // server:L16952
```

```js
world.afterEvents.worldLoad.subscribe(() => {
  if (world.getDynamicProperty("nr:settings") === undefined) world.setDynamicProperty("nr:settings", "{}");
});
```

注意:
* `subscribe` 自体が 〔RO✗〕。**before イベントの中で別のイベントを subscribe しない**。
* `WorldLoadAfterEvent` には中身が無い（server:L18288）。プレイヤーは `world.getAllPlayers()` で取る。
* 2.3.0 安定版の **before イベントはこれだけ**（server:L18205〜）: `effectAdd` `entityRemove` `explosion` `itemUse`
  `playerBreakBlock` `playerGameModeChange` `playerInteractWithBlock` `playerInteractWithEntity` `playerLeave` `weatherChange`。
  **`entityHurt` の before は無い**（ダメージの取り消しはできない → DESIGN §4 の「大きな体力プール＋戻す」方式）。
* `world.getDynamicProperty` / `setDynamicProperty` に 〔RO✗〕 の印は無いが、before の中で状態を書くのは避け `system.run` へ。
* カスタムコマンドのコールバックも **before 相当（書けない）**（公式ドキュメント `custom-commands.md`）。`system.run` で包む。
* 「1 tick に詰め込みすぎると watchdog がスクリプトを止める」。重い処理は `system.runJob`（§13）。

---

## 2. 起動時の登録 `system.beforeEvents.startup`

```ts
subscribe(callback: (arg0: StartupEvent) => void): (arg0: StartupEvent) => void;   // server:L16297
readonly blockComponentRegistry: BlockComponentRegistry;   // server:L16315
readonly customCommandRegistry: CustomCommandRegistry;     // server:L16321
readonly itemComponentRegistry: ItemComponentRegistry;     // server:L16327
registerCustomComponent(name: string, customComponent: BlockCustomComponent): void;     // server:L3620 〔E〕〔T〕
registerCustomComponent(name: string, itemCustomComponent: ItemCustomComponent): void;  // server:L11634 〔E〕〔T〕
readonly params: unknown;                                  // server:L5858（CustomComponentParameters）
```

ブロックのイベント（`BlockCustomComponent` server:L18349〜、全部 `(event, params: CustomComponentParameters) => void`）:
`beforeOnPlayerPlace`(L18356, `e.cancel` / `e.player`) `onEntityFallOn`(L18363, `e.entity?` `e.fallDistance`) `onPlace`(L18370)
`onPlayerBreak`(L18371) `onPlayerInteract`(L18379, `e.player?` `e.face` `e.faceLocation?`) `onRandomTick`(L18385)
`onStepOff`(L18392) `onStepOn`(L18399, `e.entity?`) `onTick`(L18405)。全イベント共通で `e.block` `e.dimension`（`BlockEvent` server:L3674）。
**`onBreak` はベータ専用**（2.4.0-beta にしか無い）。

アイテムのイベント（`ItemCustomComponent` server:L19687〜）: `onBeforeDurabilityDamage`(L19695, `e.durabilityDamage` を書き換え可)
`onCompleteUse`(L19705) `onConsume`(L19712) `onHitEntity`(L19719, `e.attackingEntity` `e.hitEntity` `e.hadEffect` `e.itemStack?`)
`onMineBlock`(L19726) `onUse`(L19733, `e.source: Player` `e.itemStack?`) `onUseOn`(L19740)。

```js
system.beforeEvents.startup.subscribe((ev) => {
  ev.blockComponentRegistry.registerCustomComponent("nr:spike_trap", {
    onStepOn(e, p) {
      const params = /** @type {{damage?: number}} */ (p.params); // params は unknown。JSDoc で型を付ける
      e.entity?.applyDamage(params.damage ?? 4, { cause: EntityDamageCause.contact });
    },
    onTick(e) { e.dimension.spawnParticle("nr:spark", e.block.center()); },
  });
  ev.itemComponentRegistry.registerCustomComponent("nr:weapon", {
    onHitEntity(e, p) { const w = /** @type {{dtype: string}} */ (p.params); console.warn(w.dtype, e.hitEntity.typeId); },
    onBeforeDurabilityDamage(e) { e.durabilityDamage = 0; }, // 耐久はスクリプト側で管理するなら 0 に
  });
});
```

### 1.21.120 のブロック・アイテム JSON での書き方（Custom Components V2）

**`format_version` は 1.21.90 以上**（NIGHT RUNNER は `"1.21.120"`）にし、カスタムコンポーネントは
**普通のコンポーネントと同じ所に、名前空間付きのキーで並べる**。値の辞書がそのまま `params` になる。

```json
{
  "format_version": "1.21.120",
  "minecraft:block": {
    "description": { "identifier": "nr:spike_trap" },
    "components": {
      "minecraft:tick": { "interval_range": [10, 10], "looping": true },
      "nr:spike_trap": { "damage": 6 }
    }
  }
}
```

```json
{
  "format_version": "1.21.120",
  "minecraft:item": {
    "description": { "identifier": "nr:w_machete" },
    "components": {
      "minecraft:max_stack_size": 1,
      "nr:weapon": { "dtype": "slash", "weight": "medium" }
    }
  }
}
```

* 根拠: 公式 `creator/Documents/scripting/custom-components.md`（"in version 1, custom components were added by listing them in a
  `minecraft:custom_components` array; in version 2, they're registered the way any native Minecraft component is"）、
  `components-tutorial.md`（`"format_version": "1.21.90"` のアイテムに `"starter:add_night_vision_on_consume": {}`）。
  控えは `build_preview/nr_research/ms_docs/`。
* **`"minecraft:custom_components": [...]` は使わない**（公式の参照ページに "This type is now deprecated"）。
* JSON に書いたのにスクリプトで登録していない名前があると、そのブロック／アイテムは読み込みでエラーになる（要実機確認: コンテンツログ）。
  逆に登録だけして JSON で使わないのは問題ない。
* permutation 側に同じコンポーネントを書くと、その permutation では base の値を**上書き**する（params ごと）。
* **`onTick` を使うブロックには JSON の `minecraft:tick`（`interval_range: [最小, 最大]` tick、`looping`）が必須**。無いとコンテンツエラー
  （公式 `minecraftBlock_tick.md`: "Custom components listening to the onTick event that are added to a block that does not have the
  minecraft:tick component will cause a content error."）。`onRandomTick` はワールドの random tick で呼ばれる（追加の部品が要るかは要実機確認）。

### カスタムコマンド（安定版にある。`/scriptevent` の代わりにも使える）

```ts
registerCommand(customCommand: CustomCommand, callback: (origin: CustomCommandOrigin, ...args: any[]) => CustomCommandResult | undefined): void;  // server:L5824 〔E〕〔RO✗〕〔T〕
// CustomCommand: { name: string; description: string; permissionLevel: CommandPermissionLevel; cheatsRequired?: boolean;
//                  mandatoryParameters?: CustomCommandParameter[]; optionalParameters?: CustomCommandParameter[] }   server:L18735
```

```js
system.beforeEvents.startup.subscribe((ev) => {
  ev.customCommandRegistry.registerCommand(
    { name: "nr:gore", description: "gore level", permissionLevel: CommandPermissionLevel.GameDirectors,
      cheatsRequired: false, mandatoryParameters: [{ name: "level", type: CustomCommandParamType.Integer }] },
    (origin, level) => {
      system.run(() => world.setDynamicProperty("nr:gore", level)); // コールバックは書けない文脈
      return { status: CustomCommandStatus.Success, message: `gore=${level}` };
    });
});
```

* 名前は名前空間必須。`cheatsRequired` の既定は **true**（チート無しのワールドで使わせたいなら `false`）。
* DESIGN.md の約束は `/scriptevent nr:*`（§2 の ID 表）。コマンドは補助として使ってよいが、両方から同じ処理を呼ぶこと。

---

## 3. world のイベント（after）— 2.3.0 安定版の一覧

`WorldAfterEvents`（server:L17806〜）: `blockExplode` `buttonPush` `dataDrivenEntityTrigger` `effectAdd` `entityDie`
`entityHealthChanged` `entityHitBlock` `entityHitEntity` `entityHurt` `entityLoad` `entityRemove` `entitySpawn` `explosion`
`gameRuleChange` `itemCompleteUse` `itemReleaseUse` `itemStartUse` `itemStartUseOn` `itemStopUse` `itemStopUseOn` `itemUse`
`leverAction` `pistonActivate` `playerBreakBlock` `playerButtonInput` `playerDimensionChange` `playerEmote` `playerGameModeChange`
`playerHotbarSelectedSlotChange` `playerInputModeChange` `playerInputPermissionCategoryChange` `playerInteractWithBlock`
`playerInteractWithEntity` `playerInventoryItemChange` `playerJoin` `playerLeave` `playerPlaceBlock` `playerSpawn`
`pressurePlatePop` `pressurePlatePush` `projectileHitBlock` `projectileHitEntity` `targetBlockHit` `tripWireTrip`
`weatherChange` `worldLoad`。**`chatSend` / `playerSwingStart` / `messageReceive` は無い（ベータ）**。

フィルタ付きで subscribe できるもの（`EntityEventOptions` server:L19016: `entities?: Entity[]`, `entityTypes?: string[]`）:
`entityHurt`(L8989) `entityHitEntity`(L8921) `entityHitBlock`(L8868) `entityDie`(L8545) `entityRemove`(L10022)
`entityHealthChanged`(L8774) `effectAdd`(L6806)。別の型のフィルタ: `dataDrivenEntityTrigger`（`EntityDataDrivenTriggerEventOptions` L5908）、
`playerButtonInput`（`InputEventOptions` L14198）、`playerHotbarSelectedSlotChange`（`HotbarEventOptions` L14511）、
`scriptEventReceive`（`ScriptEventMessageFilterOptions` L16189）。
**`projectileHit*` / `entitySpawn` / `entityLoad` / `itemUse` 系はフィルタ無し**（コールバックの最初で `typeId` を見て早く抜ける）。

### 3.1 `entityHurt` — 本当の体力・部位・ゴアの入口

```ts
readonly entityHurt: EntityHurtAfterEventSignal;          // server:L17886
subscribe(callback: (arg0: EntityHurtAfterEvent) => void, options?: EntityEventOptions): (arg0: EntityHurtAfterEvent) => void;  // server:L8987
readonly damage: number;                                   // server:L8956
readonly damageSource: EntityDamageSource;                 // server:L8963
readonly hurtEntity: Entity;                               // server:L8969
// EntityDamageSource（server:L18944）: cause: EntityDamageCause; damagingEntity?: Entity; damagingProjectile?: Entity;
```

```js
world.afterEvents.entityHurt.subscribe((ev) => {
  const z = ev.hurtEntity;
  if (!z.isValid) return;
  const by = ev.damageSource.damagingEntity;
  if (ev.damageSource.cause === EntityDamageCause.entityAttack && by instanceof Player) {
    z.getComponent("minecraft:health")?.resetToMaxValue(); // プールを戻す（DESIGN §4）
  }
}, { entityTypes: ZOMBIE_TYPES });
```

* 当たった**場所の情報は無い**。近接はプレイヤーの目からのレイ（§4.6 / §6.2）、飛び道具は `projectileHitEntity` の `location`。
* `damage` は軽減後の値と思われる（要実機確認）。プールを戻すのは同じ tick の after の中でよい。
* ダメージが `damage_sensor` で無効にされた時（死体 `nr:dead`）は **`entityHurt` は来ない**（要実機確認）→ 死体の切断は `entityHitEntity` で拾う。
* 自分で `applyDamage` したものもここに来る（DESIGN §4「予約」で二重に数えない）。

### 3.2 `entityHitEntity` / `entityHitBlock` — 近接の「当たった」

```ts
readonly entityHitEntity: EntityHitEntityAfterEventSignal;   // server:L17878
subscribe(callback: (arg0: EntityHitEntityAfterEvent) => void, options?: EntityEventOptions): (arg0: EntityHitEntityAfterEvent) => void;  // server:L8919
readonly damagingEntity: Entity;   // server:L8894
readonly hitEntity: Entity;        // server:L8900
readonly entityHitBlock: EntityHitBlockAfterEventSignal;     // server:L17869
readonly blockFace: Direction;     // server:L8829
readonly damagingEntity: Entity;   // server:L8835
readonly hitBlock: Block;          // server:L8841
readonly hitBlockPermutation: BlockPermutation;   // server:L8847
```

```js
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const hits = ev.damagingEntity.getEntitiesFromViewDirection({ maxDistance: 4, families: ["nr_zombie"] });
  if (hits[0]?.entity.id === ev.hitEntity.id) console.log("視線の先", hits[0].distance);
}, { entityTypes: ["minecraft:player"] });
```

* `options.entityTypes` は**攻撃した側**で絞る（要実機確認: hit と hurt で「対象」がどちらか）。安全のため中でも `typeId` を見る。
* 振っただけ（空振り）では来ない。**空振りを取るイベントは安定版に無い**（`playerSwingStart` はベータ）。
* `entityHurt` との順序は保証されない。ゴアの決定は `entityHurt` に一本化し、ここは死体・gib を叩いた時用。

### 3.3 `projectileHitEntity` / `projectileHitBlock`

```ts
readonly projectileHitEntity: ProjectileHitEntityAfterEventSignal;   // server:L18164
subscribe(callback: (arg0: ProjectileHitEntityAfterEvent) => void): (arg0: ProjectileHitEntityAfterEvent) => void;  // server:L15546
readonly dimension: Dimension;   // server:L15494
readonly hitVector: Vector3;     // server:L15500 "Direction vector of the projectile as it hit an entity."
readonly location: Vector3;      // server:L15506 "Location where the projectile hit occurred."
readonly projectile: Entity;     // server:L15512
readonly source?: Entity;        // server:L15518
getEntityHit(): EntityHitInformation;   // server:L15527 〔RO✗〕 → { entity?: Entity }  server:L19159
readonly projectileHitBlock: ProjectileHitBlockAfterEventSignal;     // server:L18156
getBlockHit(): BlockHitInformation;     // server:L15450 〔RO✗〕 → { block: Block; face: Direction; faceLocation: Vector3 }  server:L18505
```

```js
world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const target = ev.getEntityHit().entity;
  if (target?.isValid && ev.projectile.typeId.startsWith("nr:proj_")) console.log(ev.location, ev.hitVector);
});
world.afterEvents.projectileHitBlock.subscribe((ev) => {
  const hit = ev.getBlockHit();
  console.log(hit.block.typeId, hit.face, hit.faceLocation, ev.location);
});
```

* `location` は着弾点（部位判定に使う）。`hitVector` は弾の向き（正規化されているかは要実機確認 → 自分で正規化）。
* `getEntityHit().entity` は `undefined` のことがある（消えた直後など）。
* 弾を自分で飛ばす時は `minecraft:projectile` コンポーネント（§9.5）。

### 3.4 `entityDie`

```ts
readonly entityDie: EntityDieAfterEventSignal;   // server:L17852
subscribe(callback: (arg0: EntityDieAfterEvent) => void, options?: EntityEventOptions): (arg0: EntityDieAfterEvent) => void;  // server:L8543
readonly damageSource: EntityDamageSource;   // server:L8511
readonly deadEntity: Entity;                 // server:L8517
```

```js
world.afterEvents.entityDie.subscribe((ev) => {
  if (ev.deadEntity.isValid) console.log("全身が弾ける", ev.deadEntity.location, ev.damageSource.cause);
}, { entityTypes: ZOMBIE_TYPES });
```

* NIGHT RUNNER ではバニラの死は「プール以上の一撃」の時だけ（DESIGN §4）。`deadEntity` はこの時点でまだ読めることが多いが
  **必ず `isValid` を見る**。位置が要るなら `entityHurt` で覚えておくのが確実。

### 3.5 `entitySpawn` / `entityLoad` / `entityRemove`

```ts
readonly entitySpawn: EntitySpawnAfterEventSignal;   // server:L17911
subscribe(callback: (arg0: EntitySpawnAfterEvent) => void): (arg0: EntitySpawnAfterEvent) => void;   // server:L10402
readonly cause: EntityInitializationCause;   // server:L10347  Born | Event | Loaded | Spawned | Transformed（server:L1340）
entity: Entity;                              // server:L10355
readonly entityLoad: EntityLoadAfterEventSignal;     // server:L17894
entity: Entity;                              // server:L9348
readonly entityRemove: EntityRemoveAfterEventSignal; // server:L17903
readonly removedEntityId: string;            // server:L9986
readonly typeId: string;                     // server:L9993
```

```js
world.afterEvents.entitySpawn.subscribe((ev) => {
  if (ev.cause === EntityInitializationCause.Spawned && ev.entity.typeId.startsWith("nr:z_")) ev.entity.setDynamicProperty("nr:hp", 24);
});
world.afterEvents.entityLoad.subscribe((ev) => { if (ev.entity.typeId === "nr:gib") ev.entity.remove(); });
```

* `entityRemove` の後はその Entity は無効。`removedEntityId` で自分の表（gib の数・死体の数）から消す。
* チャンクの読み込みで戻ってきたものは `entityLoad`。**`nr:hp` が無ければ初期化**を両方で行う。

### 3.6 アイテムの使用 `itemUse` / `itemStartUse` / `itemStopUse` / `itemReleaseUse` / `itemCompleteUse`

```ts
readonly itemUse: ItemUseAfterEventSignal;              // server:L17992   { itemStack: ItemStack; source: Player }  server:L12967
readonly itemUse: ItemUseBeforeEventSignal;             // server:L18241   + cancel: boolean  server:L13014
readonly itemStartUse: ItemStartUseAfterEventSignal;    // server:L17953   { itemStack: ItemStack; source: Player; useDuration: number }  server:L12678
readonly itemStopUse: ItemStopUseAfterEventSignal;      // server:L17973   { itemStack?: ItemStack; source: Player; useDuration: number }  server:L12804
readonly itemReleaseUse: ItemReleaseUseAfterEventSignal;// server:L17945   { itemStack?: ItemStack; source: Player; useDuration: number }  server:L12099
readonly itemCompleteUse: ItemCompleteUseAfterEventSignal; // server:L17936 { itemStack: ItemStack; source: Player; useDuration: number }  server:L11391
```

```js
world.beforeEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack.typeId !== "nr:w_crossbow") return;
  ev.cancel = true;                                   // before でできるのは取り消しと読むことだけ
  const pl = ev.source;
  system.run(() => pl.playSound("nr.w.dry_fire"));   // 書くのは次へ
});
world.afterEvents.itemReleaseUse.subscribe((ev) => { console.log(ev.itemStack?.typeId, ev.useDuration); });
```

* `useDuration` は**残り**時間（tick）。溜め時間 = アイテムの `use_duration`（tick 換算）− `useDuration`（要実機確認: 単位）。
* `itemStartUse` 以降は**使用時間のあるアイテム**（`minecraft:use_modifiers` の `use_duration`）だけに来る。
* `itemStopUse` / `itemReleaseUse` の `itemStack` は `undefined` のことがある（次元移動など）。
* `source` は `Player` 型。

### 3.7 入力 `playerButtonInput` / `Player.inputInfo`

```ts
readonly playerButtonInput: PlayerButtonInputAfterEventSignal;   // server:L18025
subscribe(callback: (arg0: PlayerButtonInputAfterEvent) => void, options?: InputEventOptions): (arg0: PlayerButtonInputAfterEvent) => void;  // server:L14196
readonly button: InputButton;          // server:L14166
readonly newButtonState: ButtonState;  // server:L14172
readonly player: Player;               // server:L14178
// InputEventOptions（server:L19614）: buttons?: InputButton[]; state?: ButtonState;
// InputButton（server:L1839）: Jump = 'Jump' | Sneak = 'Sneak'      ButtonState（server:L147）: Pressed | Released
readonly inputInfo: InputInfo;         // server:L13548（Player）
getButtonState(button: InputButton): ButtonState;   // server:L11171 〔T〕
getMovementVector(): Vector2;                       // server:L11177 〔T〕
readonly lastInputModeUsed: InputMode;              // server:L11153
```

```js
world.afterEvents.playerButtonInput.subscribe((ev) => {
  if (ev.button === InputButton.Jump && ev.newButtonState === ButtonState.Pressed) ev.player.applyKnockback({ x: 0, z: 0 }, 0.6);
}, { buttons: [InputButton.Jump, InputButton.Sneak] });

/** @param {Player} p */
function heldJump(p) { return p.inputInfo.getButtonState(InputButton.Jump) === ButtonState.Pressed; }
```

* **ボタンは `Jump` と `Sneak` の 2 つだけ**。攻撃・使用・ダッシュのボタンは無い（ダッシュは `isSprinting`、攻撃は `entityHit*`）。
* **タッチ操作の Sneak は押しても 1 tick 以内に離される**（server:L1852 の注記）。「押し続け」は `p.isSneaking` で見る。
* `getMovementVector()` は −1..1 の `{x, y}`。`y` が前後、`x` が左右（**符号は要実機確認**）。
* 押した瞬間はイベント、押している間は毎 tick の `getButtonState`。両方を同じモジュール（`player/parkour.js`）で扱う。

### 3.8 `playerInteractWithEntity` / `playerInteractWithBlock`

```ts
readonly playerInteractWithEntity: PlayerInteractWithEntityAfterEventSignal;  // server:L18085
// after（server:L14843）: beforeItemStack?: ItemStack; itemStack?: ItemStack; player: Player; target: Entity
readonly playerInteractWithEntity: PlayerInteractWithEntityBeforeEventSignal; // server:L18271  + cancel（server:L14916）
readonly playerInteractWithBlock: PlayerInteractWithBlockAfterEventSignal;    // server:L18077
// after（server:L14670）: beforeItemStack?; block: Block; blockFace: Direction; faceLocation: Vector3; isFirstEvent: boolean; itemStack?; player
readonly playerInteractWithBlock: PlayerInteractWithBlockBeforeEventSignal;   // server:L18263  + cancel（server:L14776）
```

```js
world.afterEvents.playerInteractWithBlock.subscribe((ev) => {
  if (ev.isFirstEvent && ev.block.typeId === "nr:uv_lamp") ev.player.sendMessage({ translate: "nr.uv.on" });
});
```

* **長押しで毎 tick 来る**。1 回だけ処理するなら `isFirstEvent`。
* 「使う」＝右クリック／長押しタップ。エンティティの `minecraft:interact` が無くても after は来る（要実機確認）。

### 3.9 `playerSpawn` / `playerJoin` / `playerLeave` / `playerHotbarSelectedSlotChange`

```ts
readonly playerSpawn: PlayerSpawnAfterEventSignal;   // server:L18130   { initialSpawn: boolean; player: Player }  server:L15254
readonly playerJoin: PlayerJoinAfterEventSignal;     // server:L18104   { playerId: string; playerName: string }   server:L15058
readonly playerLeave: PlayerLeaveAfterEventSignal;   // server:L18112（after。playerId / playerName だけ）
readonly playerLeave: PlayerLeaveBeforeEventSignal;  // server:L18279（before）{ player: Player }  server:L15159（退出時の保存はここで読む。system.run の頃には player は無効。setDynamicProperty には RO の印が無い: 要実機確認）
readonly playerHotbarSelectedSlotChange: PlayerHotbarSelectedSlotChangeAfterEventSignal;  // server:L18053
// { itemStack?: ItemStack; newSlotSelected: number; player: Player; previousSlotSelected: number }  server:L14461
```

```js
world.afterEvents.playerSpawn.subscribe((ev) => { if (ev.initialSpawn) ev.player.sendMessage({ translate: "nr.welcome" }); });
```

* `playerJoin` の時点ではプレイヤーの Entity はまだ無い → 初期化は `playerSpawn`（`initialSpawn`）で。死んで復活しても `playerSpawn` が来る。

### 3.10 `system.afterEvents.scriptEventReceive`（`/scriptevent nr:*`）

```ts
readonly scriptEventReceive: ScriptEventCommandMessageAfterEventSignal;   // server:L16935
subscribe(callback: (arg0: ScriptEventCommandMessageAfterEvent) => void, options?: ScriptEventMessageFilterOptions): (arg0: ScriptEventCommandMessageAfterEvent) => void;  // server:L16187
// { id: string; initiator?: Entity; message: string; sourceBlock?: Block; sourceEntity?: Entity; sourceType: ScriptEventSource }  server:L16128〜L16169
// ScriptEventMessageFilterOptions（server:L20180）: namespaces: string[]
sendScriptEvent(id: string, message: string): void;   // server:L16900（System）
```

```js
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const p = ev.sourceEntity;
  if (ev.id === "nr:kit" && p instanceof Player) p.sendMessage(ev.message);
}, { namespaces: ["nr"] });
```

* `sourceType`: `Block` / `Entity` / `NPCDialogue` / `Server`（server:L2400）。チャットから打てば `Entity`（プレイヤー）。
* `world.afterEvents` ではなく **`system.afterEvents`**。

---

## 4. Entity（server:L6982〜）

### 4.1 有効性・基本

```ts
readonly isValid: boolean;        // server:L7094  ← 2.x ではプロパティ。isValid() と呼ぶと TS2349
readonly id: string;              // server:L7005（無効でも読める）
readonly typeId: string;          // server:L7136（無効でも読める）
readonly location: Vector3;       // server:L7113 〔T〕
readonly dimension: Dimension;    // server:L6994 〔T〕
getHeadLocation(): Vector3;       // server:L7587 〔T〕
getViewDirection(): Vector3;      // server:L7669 〔T〕
remove(): void;                   // server:L7807 〔RO✗〕〔T〕 死なない・落とさない
kill(): boolean;                  // server:L7736 〔RO✗〕〔T〕
```

* 何 tick もまたいで持つ Entity は**使う直前に毎回 `isValid`**。無効な Entity のほぼ全メソッドは `InvalidEntityError` を投げる。
* 保存するなら `id` を持ち、`world.getEntity(id)`（server:L17534）で引き直す。

### 4.2 状態フラグ

```ts
readonly isClimbing: boolean;   // server:L7016 〔T〕 梯子など climbable に触れている
readonly isFalling: boolean;    // server:L7026 〔T〕 落下距離 > 0（滑空中は > 1）
readonly isInWater: boolean;    // server:L7035 〔T〕
readonly isOnGround: boolean;   // server:L7047 〔T〕 "This property will always be true when an Entity is first spawned"
readonly isSleeping: boolean;   // server:L7056
isSneaking: boolean;            // server:L7065 〔RO✗〕（書ける。プレイヤーに書いて効くかは要実機確認）
readonly isSprinting: boolean;  // server:L7076 〔T〕
readonly isSwimming: boolean;   // server:L7086 〔T〕
// Player だけ（server:L13510〜）
readonly isEmoting: boolean;    // server:L13561
readonly isFlying: boolean;     // server:L13569
readonly isGliding: boolean;    // server:L13576 エリトラ滑空
readonly isJumping: boolean;    // server:L13584 "This will remain true while the player is holding the jump action."
```

```js
/** @param {Player} p */
function airborne(p) { return !p.isOnGround && !p.isClimbing && !p.isInWater && !p.isFlying && p.getVelocity().y < 0; }
```

* **`isJumping` / `isGliding` / `isFlying` / `isEmoting` は Player だけ**（Entity には無い）。
* `isOnGround` は出現直後に必ず true、重力の無い Entity では当てにならない（d.ts の注記）。gib の着地判定は速度の符号の変化も併用。

### 4.3 エンティティプロパティ（`nr:head` など。client_sync で見た目に効く）

```ts
getProperty(identifier: string): boolean | number | string | undefined;   // server:L7606 〔T〕
setProperty(identifier: string, value: boolean | number | string): void;   // server:L7988 〔RO✗〕〔T〕
resetProperty(identifier: string): boolean | number | string;              // server:L7866 〔RO✗〕〔T〕
triggerEvent(eventName: string): void;                                     // server:L8106 〔RO✗〕〔T〕
setPropertyOverrideForEntity(targetEntity: Entity, identifier: string, value: boolean | number | string): void;  // server:L13937（Player）
```

```js
/** @param {Entity} z */
function sever(z) {
  if (z.getProperty("nr:head") === "intact") z.setProperty("nr:head", "severed");
  z.setProperty("nr:blood", 3);
  z.triggerEvent("nr:on_death");
}
```

* **`setProperty` の値は次の tick まで `getProperty` に出ない**（server:L7592 / L7963 の注記。`resetProperty` も同じ server:L7846）。同じ tick で読み直さない
  → スクリプト側に「今の部位状態」を持ち、プロパティは表示のために書くだけにする。
* enum は文字列、int / float は数。**範囲外・enum に無い文字列・型違いは例外**（`ArgumentOutOfBoundsError` / `InvalidArgumentError`）。
* `triggerEvent` は**定義に無いイベント名で例外**（server:L8076）。名前は DESIGN §12 の表だけ。
* `setPropertyOverrideForEntity` はそのプレイヤーにだけ見える上書き（client_sync のプロパティだけ）。

### 4.4 動き（物理）

```ts
applyImpulse(vector: Vector3): void;                                               // server:L7327 〔RO✗〕〔T〕
applyKnockback(horizontalForce: VectorXZ, verticalStrength: number): void;         // server:L7364 〔RO✗〕〔T〕
clearVelocity(): void;                                                             // server:L7399 〔RO✗〕〔T〕
getVelocity(): Vector3;                                                            // server:L7658 〔T〕
getRotation(): Vector2;                                                            // server:L7618 〔T〕 {x: pitch, y: yaw}
setRotation(rotation: Vector2): void;                                              // server:L8003 〔RO✗〕〔T〕
lookAt(targetLocation: Vector3): void;                                             // server:L7755 〔RO✗〕〔T〕
teleport(location: Vector3, teleportOptions?: TeleportOptions): void;              // server:L8062 〔RO✗〕〔T〕
tryTeleport(location: Vector3, teleportOptions?: TeleportOptions): boolean;        // server:L8129 〔RO✗〕〔T〕
// TeleportOptions（server:L20362）: checkForBlocks?: boolean; dimension?: Dimension; facingLocation?: Vector3; keepVelocity?: boolean; rotation?: Vector2
```

```js
/** @param {Entity} gib @param {Player} p @param {Vector3} dir */
function fling(gib, p, dir) {
  gib.clearVelocity();
  gib.applyImpulse({ x: dir.x * 0.6, y: 0.35, z: dir.z * 0.6 });     // gib・死体・ゾンビ（プレイヤー以外）
  p.applyKnockback({ x: dir.x * 1.2, z: dir.z * 1.2 }, 0.45);       // プレイヤーはこちら（水平は強さ込みのベクトル）
  const yaw = gib.getRotation().y;
  gib.setRotation({ x: 0, y: yaw + 90 });
  gib.teleport(gib.location, { keepVelocity: true, rotation: { x: 0, y: yaw } });
}
```

* **`applyKnockback` は 2 引数**: `({x, z}, vertical)`。水平ベクトルの長さが強さ。1.x の `(dirX, dirZ, h, v)` は TS2554。
  （d.ts 自身の例 server:L7359 は 1.x の形のまま。写さない）
* **プレイヤーに `applyImpulse` は効かない／例外**（DESIGN §7。d.ts の `@throws` には `UnsupportedFunctionalityError` が無いが実機では拒否される: 要実機確認）。
  プレイヤーは `applyKnockback` と効果（jump_boost / slow_falling / levitation）で動かす。`clearVelocity` もプレイヤーには効かない（要実機確認）。
* yaw（`getRotation().y`）は度。0 = 南（+Z）、90 = 西（−X）、180/−180 = 北、−90 = 東。前方 = `(−sin yaw, 0, cos yaw)`。
  向きは `getViewDirection()` を使う方が確実（ピッチ込み）。
* `teleport` はその tick の速度を消す（`keepVelocity: true` で残す）。毎 tick の teleport でゾンビを動かすと AI と喧嘩する。

### 4.5 アニメーション `playAnimation`

```ts
playAnimation(animationName: string, options?: PlayAnimationOptions): void;   // server:L7792 〔RO✗〕〔T〕
// PlayAnimationOptions（server:L19857）: blendOutTime?: number; controller?: string; nextState?: string; players?: Player[]; stopExpression?: string
```

```js
/** @param {Player} p @param {Entity} z */
function anims(p, z) {
  p.playAnimation("animation.nr.p.vault", { blendOutTime: 0.1, stopExpression: "q.any_animation_finished" });
  z.playAnimation("animation.nr.z.ab_scream", { controller: "nr_oneshot", blendOutTime: 0.2 });
}
```

* `/playanimation` と同じ。RP に読み込まれたアニメ ID なら使える（エンティティの `animations` への登録は要らない: 要実機確認）。
* 同じ `controller` 名の再生は前のを置き換える。**上半身と下半身を同時に**流すなら別の `controller` 名を付ける。
* `players` を渡すとその人にだけ見える（一人称の演出など）。
* `stopExpression` を省くと既定は `query.any_animation_finished`（要実機確認）。ループするアニメは止まらないので必ず指定。
* ID は `nr_registry.py`（`scripts/data/fx.js` の `PLAYER_ANIMS` / `ZOMBIE_ONESHOTS`）にあるものだけ。

### 4.6 レイ（視線・弾道）

```ts
getEntitiesFromViewDirection(options?: EntityRaycastOptions): EntityRaycastHit[];          // server:L7574 〔T〕
getBlockFromViewDirection(options?: BlockRaycastOptions): BlockRaycastHit | undefined;     // server:L7452 〔T〕
// EntityRaycastOptions extends EntityFilter（server:L19464）: ignoreBlockCollision?; includeLiquidBlocks?; includePassableBlocks?; maxDistance?
// EntityRaycastHit（server:L19445）: distance: number; entity: Entity
// BlockRaycastOptions extends BlockFilter（server:L18557）: includeLiquidBlocks?; includePassableBlocks?; maxDistance?
// BlockRaycastHit（server:L18530）: block: Block; face: Direction; faceLocation: Vector3（ブロックの北西下の角からの相対）
```

```js
/** @param {Player} p */
function aim(p) {
  const hit = p.getEntitiesFromViewDirection({ maxDistance: 4, families: ["nr_zombie"], excludeTypes: ["nr:gib"] })[0];
  const wall = p.getBlockFromViewDirection({ maxDistance: 1.5, includePassableBlocks: false });
  return { target: hit?.entity, dist: hit?.distance, wall: wall?.block, face: wall?.face };
}
```

* 結果は近い順（要実機確認）。`distance` は**当たり箱の表面まで**の距離。当たり点 = 目 + 方向 × distance（部位判定に使う）。
* `EntityFilter` の全項目（`families` `excludeTypes` `tags` …、§6.1）がレイにも使える。
* ブロックのレイは `ignoreBlockCollision` が無い（`EntityRaycastOptions` 側だけ）。

### 4.7 効果・ダメージ・火

```ts
addEffect(effectType: EffectType | string, duration: number, options?: EntityEffectOptions): Effect | undefined;  // server:L7209 〔RO✗〕〔T〕
// duration は tick（[0, 20000000]）。EntityEffectOptions（server:L18997）: amplifier?: number; showParticles?: boolean
removeEffect(effectType: EffectType | string): boolean;    // server:L7826 〔RO✗〕〔T〕
getEffect(effectType: EffectType | string): Effect | undefined;   // server:L7542 〔T〕
applyDamage(amount: number, options?: EntityApplyDamageByProjectileOptions | EntityApplyDamageOptions): boolean;  // server:L7297 〔RO✗〕〔T〕
// EntityApplyDamageOptions（server:L18925）: cause: EntityDamageCause; damagingEntity?: Entity
// EntityApplyDamageByProjectileOptions（server:L18907）: damagingEntity?: Entity; damagingProjectile: Entity
setOnFire(seconds: number, useEffects?: boolean): boolean;   // server:L7959 〔RO✗〕〔T〕
extinguishFire(useEffects?: boolean): boolean;               // server:L7437 〔RO✗〕〔T〕
```

```js
/** @param {Entity} z @param {Player} p */
function hurt(z, p) {
  z.addEffect("slowness", 3 * TicksPerSecond, { amplifier: 1, showParticles: false });
  z.removeEffect("slowness");
  z.applyDamage(5, { cause: EntityDamageCause.entityAttack, damagingEntity: p });
  z.setOnFire(4, true);
}
```

* 効果 ID は `"slowness"` でも `"minecraft:slowness"` でもよい（`Effect.typeId` は 2.x で常に `minecraft:` 付き）。
* `applyDamage` の戻り値は「ダメージが入ったか」。無敵時間中は false（要実機確認）。

### 4.8 動的プロパティ（エンティティ）

```ts
getDynamicProperty(identifier: string): boolean | number | string | Vector3 | undefined;   // server:L7497 〔T〕
setDynamicProperty(identifier: string, value?: boolean | number | string | Vector3): void;  // server:L7916 〔T〕
setDynamicProperties(values: Record<string, boolean | number | string | Vector3 | undefined>): void;  // server:L7900 〔T〕
getDynamicPropertyIds(): string[];                // server:L7509
getDynamicPropertyTotalByteCount(): number;       // server:L7523
clearDynamicProperties(): void;                   // server:L7374
```

* 値を `undefined` にすると消える。保存はワールドに永続（エンティティと一緒に）。
* 戻りは和型。**`/** @type {number} */ (…)` か `Number(…)` で絞る**（§0）。

### 4.9 その他

```ts
getComponent<T extends string>(componentId: T): EntityComponentReturnType<T> | undefined;   // server:L7470 〔T〕
matches(options: EntityQueryOptions): boolean;          // server:L7776 〔T〕
addTag(tag: string): boolean;  hasTag(tag: string): boolean;   // server:L7251 / L7699
runCommand(commandString: string): CommandResult;        // server:L7885 〔RO✗〕〔T〕（同期。runCommandAsync は 2.x で削除）
```

* `getComponent("minecraft:health")` のように**文字列で渡すと戻りの型が付く**（`EntityComponentTypeMap` server:L2721 付近。`"health"` だけでも可）。
* 2.x では無効な Entity に `getComponent` すると**例外**（1.x は undefined）。

---

## 5. Player（server:L13510〜。Entity を継承）

### 5.1 音・パーティクル（その人だけ）

```ts
playSound(soundId: string, soundOptions?: PlayerSoundOptions): void;    // server:L13763 〔RO✗〕〔T〕
// PlayerSoundOptions（server:L19895）: location?: Vector3; pitch?: number; volume?: number
spawnParticle(effectName: string, location: Vector3, molangVariables?: MolangVariableMap): void;  // server:L13998 〔RO✗〕〔T〕
playMusic(trackId: string, musicOptions?: MusicOptions): void;           // server:L13724
```

```js
/** @param {Player} p */
function ui_click(p) { p.playSound("nr.ui.click", { volume: 0.8, pitch: 1.0 }); }
```

### 5.2 カメラ `Player.camera`

```ts
readonly camera: Camera;                      // server:L13518
fade(fadeCameraOptions?: CameraFadeOptions): void;   // server:L4863 〔RO✗〕〔T〕
// CameraFadeOptions（server:L18583）: fadeColor?: RGB; fadeTime?: CameraFadeTimeOptions
// CameraFadeTimeOptions（server:L18601）: fadeInTime: number; fadeOutTime: number; holdTime: number（すべて秒）
setCamera(cameraPreset: string, setOptions?: CameraFixedBoomOptions | CameraSetFacingOptions | CameraSetLocationOptions | CameraSetPosOptions | CameraSetRotOptions | CameraTargetOptions): void;  // server:L4876 〔RO✗〕〔T〕
// CameraSetRotOptions（server:L18672）: easeOptions?; location?; rotation: Vector2     CameraSetPosOptions（L18666）: easeOptions?; facingLocation: Vector3; location?
// CameraSetLocationOptions（L18661）: easeOptions?; location: Vector3   CameraSetFacingOptions（L18655）: easeOptions?; facingEntity: Entity; location?
// CameraTargetOptions（L18681）: offsetFromTargetCenter?; targetEntity: Entity   CameraFixedBoomOptions（L18626）: entityOffset?; viewOffset?: Vector2
// EaseOptions（server:L18869）: easeTime?: number; easeType?: EasingType（server:L585: Linear / Spring / In|Out|InOut × Sine Quad Cubic Quart Quint Expo Circ Back Elastic Bounce）
setDefaultCamera(cameraPreset: string, easeOptions?: EaseOptions): void;   // server:L4901
setFov(fovCameraOptions?: CameraFovOptions): void;   // server:L4908  CameraFovOptions（L18645）: easeOptions?; fov?: number
clear(): void;                                       // server:L4851 〔RO✗〕〔T〕
readonly isValid: boolean;                           // server:L4839
```

```js
/** @param {Player} p */
function cam(p) {
  p.camera.fade({ fadeTime: { fadeInTime: 0.05, holdTime: 0.1, fadeOutTime: 0.5 }, fadeColor: { red: 0.45, green: 0, blue: 0 } }); // 血の赤
  p.camera.setCamera("minecraft:free", { location: p.getHeadLocation(), rotation: { x: 10, y: 0 }, easeOptions: { easeTime: 0.3, easeType: EasingType.OutCubic } });
  p.camera.setFov({ fov: 80, easeOptions: { easeTime: 0.2 } });
  p.camera.clear();
}
```

* プリセット名はバニラの `minecraft:free` / `minecraft:first_person` / `minecraft:third_person` / `minecraft:third_person_front` /
  `minecraft:fixed_boom` / `minecraft:follow_orbit` など（JSON のカメラプリセットで増やせる）。
* `setCamera` の後は**必ず `clear()`** で戻す（死亡・切断・フォームを開く時も）。`setFov` の元に戻し方は `setFov()`（引数なし）（要実機確認）。
* `playAnimation` / `setCameraWithEase`（カメラの）はベータ。揺れは fade と fov の短い変化で作る。

### 5.3 画面 `Player.onScreenDisplay`

```ts
readonly onScreenDisplay: ScreenDisplay;   // server:L13607
setActionBar(text: (RawMessage | string)[] | RawMessage | string): void;   // server:L15991 〔RO✗〕〔T〕
setTitle(title: (RawMessage | string)[] | RawMessage | string, options?: TitleDisplayOptions): void;   // server:L16081 〔RO✗〕〔T〕
// TitleDisplayOptions（server:L20402）: fadeInDuration: number; fadeOutDuration: number; stayDuration: number; subtitle?（すべて tick。3 つとも必須）
updateSubtitle(subtitle: (RawMessage | string)[] | RawMessage | string): void;   // server:L16121
setHudVisibility(visible: HudVisibility, hudElements?: HudElement[]): void;      // server:L16008 〔RO✗〕〔T〕
hideAllExcept(hudElements?: HudElement[]): void;     // server:L15957
resetHudElementsVisibility(): void;                  // server:L15975
getHiddenHudElements(): HudElement[];                // server:L15948
isForcedHidden(hudElement: HudElement): boolean;     // server:L15966
// HudVisibility（server:L1816）: Hide = 0 | Reset = 1
// HudElement（server:L1796）: PaperDoll 0, Armor 1, ToolTips 2, TouchControls 3, Crosshair 4, Hotbar 5, Health 6, ProgressBar 7, Hunger 8, AirBubbles 9, HorseHealth 10, StatusEffects 11, ItemText 12
```

```js
/** @param {Player} p */
function hud(p) {
  p.onScreenDisplay.setActionBar("§c♥ 20  §e⚡ 80");
  p.onScreenDisplay.setTitle("§4DECAPITATED", { fadeInDuration: 2, stayDuration: 20, fadeOutDuration: 6, subtitle: "+50" });
  p.onScreenDisplay.setHudVisibility(HudVisibility.Hide, [HudElement.Hunger, HudElement.Armor]);
}
```

* アクションバーは数秒で消えるので、出し続けるには書き直す。毎 tick は不要（値が変わった時＋10 tick 前後ごと。`hud.js` でまとめる。間隔は要実機確認）。
* `setTitle` のオプションは **3 つの時間が全部必須**（片方だけは TS エラー）。
* `HudElement` に「独自 HUD」は無い。独自の表示は actionbar / title のテキスト＋独自グリフ（DESIGN §7）。
* `TouchControls` を隠すとタッチ端末で操作できなくなる。隠さない。

### 5.4 入力の許可・ゲームモード・その他

```ts
readonly inputPermissions: PlayerInputPermissions;   // server:L13554
setPermissionCategory(permissionCategory: InputPermissionCategory, isEnabled: boolean): void;   // server:L14663 〔RO✗〕
// InputPermissionCategory（server:L1897）: Camera 1, Movement 2, LateralMovement 4, Sneak 5, Jump 6, Mount 7, Dismount 8, MoveForward 9, MoveBackward 10, MoveLeft 11, MoveRight 12
getGameMode(): GameMode;              // server:L13685
setGameMode(gameMode?: GameMode): void;   // server:L13910 〔RO✗〕
selectedSlotIndex: number;            // server:L13619 〔RO✗〕（書ける）
startItemCooldown(cooldownCategory: string, tickDuration: number): void;   // server:L14013
getItemCooldown(cooldownCategory: string): number;                         // server:L13696
sendMessage(message: (RawMessage | string)[] | RawMessage | string): void; // server:L13899
readonly name: string;                // server:L13599
```

```js
/** @param {Player} p */
function lock(p) {
  p.inputPermissions.setPermissionCategory(InputPermissionCategory.Movement, false); // とどめの演出中など。必ず戻す
  system.runTimeout(() => { if (p.isValid) p.inputPermissions.setPermissionCategory(InputPermissionCategory.Movement, true); }, 20);
  if (p.getGameMode() === GameMode.Creative) p.sendMessage("creative");
}
```

* `isOp()` は 2.x に無い → `commandPermissionLevel`（server:L13531）/ `playerPermissionLevel`（server:L13613）。

---

## 6. Dimension（server:L5927〜）

### 6.1 `getEntities` と検索条件

```ts
getEntities(options?: EntityQueryOptions): Entity[];      // server:L6255 〔T〕
getPlayers(options?: EntityQueryOptions): Player[];       // server:L6316 〔T〕
getEntitiesAtBlockLocation(location: Vector3): Entity[];  // server:L6265
// EntityQueryOptions extends EntityFilter（server:L19342）: closest?; farthest?; location?; maxDistance?; minDistance?; volume?
// EntityFilter（server:L19036）: excludeFamilies?; excludeGameModes?; excludeNames?; excludeTags?; excludeTypes?; families?; gameMode?;
//   maxHorizontalRotation?; maxLevel?; maxVerticalRotation?; minHorizontalRotation?; minLevel?; minVerticalRotation?; name?;
//   propertyOptions?: EntityQueryPropertyOptions[]; scoreOptions?; tags?; type?
// EntityQueryPropertyOptions（server:L19393）: exclude?: boolean; propertyId: string; value?: boolean | string | EqualsComparison | GreaterThanComparison | … | RangeComparison
```

```js
/** @param {Player} p */
function nearby(p) {
  const zs = p.dimension.getEntities({ location: p.location, maxDistance: 16, families: ["nr_zombie"], excludeTypes: ["nr:gib"], closest: 8 });
  const crawlers = p.dimension.getEntities({ type: "nr:z_office_worker", propertyOptions: [{ propertyId: "nr:state", value: { equals: "crawl" } }] });
  const ranged = p.dimension.getEntities({ location: p.location, maxDistance: 30, propertyOptions: [{ propertyId: "nr:blood", value: { lowerBound: 1, upperBound: 3 } }] });
  return [zs, crawlers, ranged];
}
```

* **`maxDistance` / `closest` / `farthest` / `volume` は `location` と一緒に**（無いと無視または例外）。
* `families` は「**全部**に一致」（AND）、`tags` も AND。`type` は 1 つだけ（複数なら `excludeTypes` か結果を絞る）。
* 数値のプロパティは `value: { equals: 3 }` / `{ lowerBound, upperBound }`（`RangeComparison` server:L19935）。素の数は書けない。
* 毎 tick 全ゾンビを探さない。`director.js` が tick ごとに分割して回す（予算は `core/budget.js`）。

### 6.2 レイ `getEntitiesFromRay` / `getBlockFromRay`

```ts
getEntitiesFromRay(location: Vector3, direction: Vector3, options?: EntityRaycastOptions): EntityRaycastHit[];         // server:L6283 〔T〕
getBlockFromRay(location: Vector3, direction: Vector3, options?: BlockRaycastOptions): BlockRaycastHit | undefined;    // server:L6145 〔T〕
getBlockBelow(location: Vector3, options?: BlockRaycastOptions): Block | undefined;   // server:L6131
getBlockAbove(location: Vector3, options?: BlockRaycastOptions): Block | undefined;   // server:L6118
getTopmostBlock(locationXZ: VectorXZ, minHeight?: number): Block | undefined;        // server:L6344
```

```js
/** @param {Player} p */
function hitscan(p) {
  const eye = p.getHeadLocation(), dir = p.getViewDirection();
  // ignoreBlockCollision の既定 false = ブロックでレイが止まる → 壁の向こうの敵は返らない
  const ents = p.dimension.getEntitiesFromRay(eye, dir, { maxDistance: 60, families: ["nr_zombie"] });
  // 壁に当たった点（弾痕・火花用）。faceLocation はブロックの北西下の角からの相対
  const blk = p.dimension.getBlockFromRay(eye, dir, { maxDistance: 60, includeLiquidBlocks: false, includePassableBlocks: false });
  const wall = blk && { x: blk.block.x + blk.faceLocation.x, y: blk.block.y + blk.faceLocation.y, z: blk.block.z + blk.faceLocation.z };
  return { first: ents[0]?.entity, at: ents[0] && { x: eye.x + dir.x * ents[0].distance, y: eye.y + dir.y * ents[0].distance, z: eye.z + dir.z * ents[0].distance }, wall };
}
```

* 銃（ヒットスキャン）はこの 2 本。敵の当たり点 = 始点 + 方向 × `distance`（当たり箱の表面）→ 部位判定へ。
* レイの始点がエンティティの中だと自分に当たる → `excludeTypes: ["minecraft:player"]` か結果から自分を除く。

### 6.3 出す: `spawnEntity` / `spawnItem` / `spawnParticle` / `playSound` / `createExplosion`

```ts
spawnEntity(identifier: EntityType | string, location: Vector3, options?: SpawnEntityOptions): Entity;   // server:L6587 〔RO✗〕〔T〕
// SpawnEntityOptions（server:L20193）: initialPersistence?: boolean; initialRotation?: number（度）; spawnEvent?: string
spawnItem(itemStack: ItemStack, location: Vector3): Entity;                                              // server:L6641 〔RO✗〕〔T〕
spawnParticle(effectName: string, location: Vector3, molangVariables?: MolangVariableMap): void;         // server:L6681 〔RO✗〕〔T〕
playSound(soundId: string, location: Vector3, soundOptions?: WorldSoundOptions): void;                   // server:L6426 〔RO✗〕〔T〕
// WorldSoundOptions（server:L20486）: pitch?: number; volume?: number   ← volume < 0 / pitch < 0.01 は例外
createExplosion(location: Vector3, radius: number, explosionOptions?: ExplosionOptions): boolean;        // server:L6034 〔RO✗〕〔T〕
// ExplosionOptions（server:L19542）: allowUnderwater?; breaksBlocks?; causesFire?; source?: Entity
```

```js
/** @param {Player} p */
function spawnStuff(p) {
  const dim = p.dimension;
  const zed = dim.spawnEntity("nr:z_office_worker", p.location, { initialRotation: 90, spawnEvent: "nr:enrage" });
  dim.spawnItem(new ItemStack("nr:scrap", 2), p.location);
  dim.playSound("nr.gore.sever", p.location, { volume: 1.2, pitch: 0.9 });
  dim.createExplosion(p.location, 3, { breaksBlocks: false, causesFire: false, source: p });
  return zed;
}
```

* **`world.playSound` は 2.x に無い**（TS2339）。全員に聞かせるのは `dimension.playSound`、一人だけは `player.playSound`。
* `spawnEntity` は読み込まれていないチャンクで `LocationInUnloadedChunkError`、世界の外で `LocationOutOfWorldBoundariesError`。
  演出の生成は全部 try/catch で包む（`core/fx.js`）。
* `spawnEvent` に存在しないイベント名を渡すと失敗する（要実機確認: 例外か無視か）。
* `initialPersistence: true` は自然消滅しない（死体・小道具）。数の上限は自分で管理。
* パーティクルは**数で重い**。`core/budget.js` の 1 tick 予算（DESIGN §11: ≤ 300）を必ず通す。

### 6.4 明るさ・ブロック・塗りつぶし

```ts
getLightLevel(location: Vector3): number;      // server:L6299 〔T〕 "total brightness level of light shining on a certain block position"
getSkyLightLevel(location: Vector3): number;   // server:L6332 〔T〕
getBlock(location: Vector3): Block | undefined;   // server:L6105 〔T〕
setBlockType(location: Vector3, blockType: BlockType | string): void;               // server:L6492 〔RO✗〕〔T〕
setBlockPermutation(location: Vector3, permutation: BlockPermutation): void;        // server:L6469 〔RO✗〕〔T〕
fillBlocks(volume: BlockVolumeBase, block: BlockPermutation | BlockType | string, options?: BlockFillOptions): ListBlockVolume;  // server:L6060 〔RO✗〕〔T〕
// BlockFillOptions（server:L18431）: blockFilter?: BlockFilter; ignoreChunkBoundErrors?: boolean
isChunkLoaded(location: Vector3): boolean;     // server:L6353
```

```js
/** @param {Player} p */
function lightAndFill(p) {
  const light = p.dimension.getLightLevel(p.location);     // 0..15
  const sky = p.dimension.getSkyLightLevel(p.location);    // 0..15
  p.dimension.fillBlocks(new BlockVolume({ x: 0, y: 63, z: 0 }, { x: 15, y: 63, z: 15 }), "minecraft:gray_concrete", { ignoreChunkBoundErrors: true });
  return { light, sky };
}
```

* 明るさの API は**安定版にある**（`Dimension.getLightLevel` / `getSkyLightLevel`、`Block.getLightLevel()` server:L3185 は 〔RO✗〕）。
  ただし `getLightLevel` が夜の空の暗さを反映するか、`getSkyLightLevel` が時刻で変わるかは**要実機確認**。
  免疫（DESIGN §7）の「暗さ」は `world.getTimeOfDay()` と合わせて判定し、UV ランプは自前の距離判定で足す。
* `fillBlocks` の 1 回の体積上限は d.ts に無い（`/fill` と同じ 32768 ブロック程度と思われる: 要実機確認）。大きい街区は分割して `runJob` で。
* 読み込まれていないチャンクは `getBlock` が例外。街の生成は `isChunkLoaded` を見てから。

---

## 7. World（server:L17293〜）

```ts
getTimeOfDay(): number;      // server:L17576 "The time of day, in ticks, between 0 and 24000."
getDay(): number;            // server:L17394
getAbsoluteTime(): number;   // server:L17374
setTimeOfDay(timeOfDay: number | TimeOfDay): void;   // server:L17791 〔RO✗〕
// TimeOfDay（server:L2568）: Day 1000, Noon 6000, Sunset 12000, Night 13000, Midnight 18000, Sunrise 23000
getDimension(dimensionId: string): Dimension;   // server:L17425 "overworld" | "nether" | "the_end"
getAllPlayers(): Player[];                      // server:L17385
getPlayers(options?: EntityQueryOptions): Player[];   // server:L17568
getEntity(id: string): Entity | undefined;      // server:L17534
sendMessage(message: (RawMessage | string)[] | RawMessage | string): void;   // server:L17646
getDynamicProperty(identifier: string): boolean | number | string | Vector3 | undefined;   // server:L17505
setDynamicProperty(identifier: string, value?: boolean | number | string | Vector3): void;  // server:L17778 〔T〕
setDynamicProperties(values: Record<string, boolean | number | string | Vector3 | undefined>): void;   // server:L17696
getDynamicPropertyTotalByteCount(): number;     // server:L17522
readonly structureManager: StructureManager;    // server:L17361
readonly gameRules: GameRules;                  // server:L17347
// 定数: TicksPerDay = 24000（server:L20815）、TicksPerSecond = 20（server:L20821）
```

```js
function isNight() {
  const t = world.getTimeOfDay();
  return t >= TimeOfDay.Night && t < TimeOfDay.Sunrise;
}
```

* 動的プロパティの**上限は d.ts に書かれていない**。文字列 1 本は 32767 文字程度までと言われる（**要実機確認**）。
  `nr:settings` は小さな JSON 1 本にし、大きい表（図鑑の解放状況など）はキーを分ける。書くのは変わった時だけ。
* `World.getDynamicProperty` は**早期実行では呼べない**（〔E〕 が無い）。設定の読み込みは `worldLoad` で。

---

## 8. 構造物 `world.structureManager`

```ts
place(structure: string | Structure, dimension: Dimension, location: Vector3, options?: StructurePlaceOptions): void;   // server:L16604 〔RO✗〕〔T〕
// StructurePlaceOptions（server:L20250）: animationMode?; animationSeconds?; includeBlocks?; includeEntities?; integrity?（0..1）;
//   integritySeed?; mirror?: StructureMirrorAxis; rotation?: StructureRotation; waterlogged?
// StructureRotation（server:L2516）: None | Rotate90 | Rotate180 | Rotate270     StructureMirrorAxis（L2486）: None | X | XZ | Z
// StructureAnimationMode（L2457）: Blocks | Layers | None
get(identifier: string): Structure | undefined;   // server:L16569 〔RO✗〕
createFromWorld(identifier: string, dimension: Dimension, from: Vector3, to: Vector3, options?: StructureCreateOptions): Structure;  // server:L16531
```

```js
/** @param {Dimension} dim */
function build(dim) {
  world.structureManager.place("nr:apartment_a", dim, { x: 0, y: 64, z: 0 }, { rotation: StructureRotation.Rotate90, includeEntities: false, animationMode: StructureAnimationMode.None });
}
```

* BP の `structures/nr/apartment_a.mcstructure` は ID `nr:apartment_a`（フォルダ名が名前空間）。
* **読み込まれていないチャンクへの place は「読み込み待ちに積まれる」**（server:L16579）。置いた直後にその範囲のブロックを読まない。
* 回転は構造物の原点（最小の角）基準で回る（要実機確認）。`scripts/data/structures.js` の `markers` も同じ規則で回すこと。
* `.mcstructure` の中のエンティティは `includeEntities: false` で除ける（ゾンビはスクリプトが置く）。

---

## 9. コンポーネント

### 9.1 体力 `minecraft:health`（`EntityHealthComponent` server:L8814 ← `EntityAttributeComponent` server:L8214）

```ts
readonly currentValue: number;    // server:L8222
readonly defaultValue: number;    // server:L8229
readonly effectiveMax: number;    // server:L8237
readonly effectiveMin: number;    // server:L8245
resetToDefaultValue(): void;      // server:L8255 〔RO✗〕
resetToMaxValue(): void;          // server:L8265 〔RO✗〕
resetToMinValue(): void;          // server:L8275 〔RO✗〕
setCurrentValue(value: number): boolean;   // server:L8290 〔RO✗〕 範囲外は ArgumentOutOfBoundsError
```

```js
/** @param {Entity} z */
function refill(z) { const h = z.getComponent("minecraft:health"); if (h) h.setCurrentValue(h.effectiveMax); }
```

* 移動の速さ `minecraft:movement`（`EntityMovementComponent` server:L9426）も同じ属性型 → `setCurrentValue(0.1)` で変えられる。

### 9.2 装備 `minecraft:equippable`（server:L8578）

```ts
getEquipment(equipmentSlot: EquipmentSlot): ItemStack | undefined;   // server:L8610
getEquipmentSlot(equipmentSlot: EquipmentSlot): ContainerSlot;       // server:L8623
setEquipment(equipmentSlot: EquipmentSlot, itemStack?: ItemStack): boolean;   // server:L8636 〔RO✗〕
// EquipmentSlot（server:L1380）: Chest | Feet | Head | Legs | Mainhand | Offhand（Body はベータ）
```

### 9.3 持ち物 `minecraft:inventory`（server:L9007）と `Container`（server:L5048）

```ts
readonly container: Container;           // server:L9034 〔T〕
getItem(slot: number): ItemStack | undefined;            // server:L5209
setItem(slot: number, itemStack?: ItemStack): void;      // server:L5295 〔RO✗〕
addItem(itemStack: ItemStack): ItemStack | undefined;    // server:L5111 〔RO✗〕 入りきらなかった残りを返す
getSlot(slot: number): ContainerSlot;                    // server:L5222（生きた参照。setLore / setDynamicProperty はあるが getComponent は無い）
readonly size: number;  readonly emptySlotsCount: number;   // server:L5084 / L5065
```

```js
/** @param {Player} p */
function wear(p) {
  const eq = p.getComponent("minecraft:equippable");
  const held = eq?.getEquipment(EquipmentSlot.Mainhand);
  const inv = p.getComponent("minecraft:inventory")?.container;
  const rest = inv?.addItem(new ItemStack("nr:medkit", 1));
  if (rest) p.dimension.spawnItem(rest, p.location);
  return held;
}
```

### 9.4 アイテムの耐久・クールダウン → §10

### 9.5 弾 `minecraft:projectile`（`EntityProjectileComponent` server:L9805）

```ts
owner?: Entity;                 // server:L9919 〔RO✗〕（書ける）
shoot(velocity: Vector3, options?: ProjectileShootOptions): void;   // server:L9955 〔RO✗〕 ProjectileShootOptions（L19921）: uncertainty?: number
// ほか airInertia / gravity / catchFireOnHurt / onFireTime / hitParticle / hitEntitySound / stopOnHit … は書ける
```

```js
/** @param {Player} p */
function throwKnife(p) {
  const dir = p.getViewDirection(), eye = p.getHeadLocation();
  const proj = p.dimension.spawnEntity("nr:proj_knife", { x: eye.x + dir.x * 0.8, y: eye.y + dir.y * 0.8, z: eye.z + dir.z * 0.8 });
  const pc = proj.getComponent("minecraft:projectile");
  if (pc) { pc.owner = p; pc.shoot({ x: dir.x * 2.5, y: dir.y * 2.5, z: dir.z * 2.5 }, { uncertainty: 0 }); }
}
```

* `owner` を入れないと `projectileHit*` の `source` や `entityHurt` の `damagingEntity` が空になる（要実機確認）。
* 出現位置が目の中だと自分に当たる → 上の例のように視線方向に 0.5〜1 ブロック先から出す。

### 9.6 そのほか

`minecraft:type_family`（server:L10587）`hasTypeFamily(f)` / `getTypeFamilies()`、`minecraft:onfire`（server:L9768）
`onFireTicksRemaining`、`minecraft:item`（server:L9228）`itemStack`（落ちているアイテム）、`minecraft:scale`（server:L10281、読むだけ）。

---

## 10. ItemStack（server:L12225〜）

```ts
constructor(itemType: ItemType | string, amount?: number);   // server:L12335 〔T〕（早期実行では作れない）
amount: number;                           // server:L12237 〔RO✗〕 1..255
nameTag?: string;                         // server:L12292 〔RO✗〕
keepOnDeath: boolean;                     // server:L12253
lockMode: ItemLockMode;                   // server:L12272
readonly isStackable: boolean;            // server:L12245
readonly typeId: string;                  // server:L12306
getLore(): string[];                      // server:L12457
setLore(loreList?: (RawMessage | string)[]): void;   // server:L12671 〔RO✗〕 "The maximum lore line count is 20. The maximum lore line length is 50 characters."
getDynamicProperty(identifier: string): boolean | number | string | Vector3 | undefined;   // server:L12427
setDynamicProperty(identifier: string, value?: boolean | number | string | Vector3): void;  // server:L12631 "only works with non-stackable items"
getComponent<T extends string>(componentId: T): ItemComponentReturnType<T> | undefined;    // server:L12409
clone(): ItemStack;                       // server:L12351
// ItemDurabilityComponent（server:L11795）: damage: number（〔RO✗〕書ける）; readonly maxDurability: number
// ItemCooldownComponent（server:L11704）: cooldownCategory; cooldownTicks; getCooldownTicksRemaining(player); startCooldown(player: Player): void
```

```js
/** @param {Player} p */
function wearWeapon(p) {
  const eq = p.getComponent("minecraft:equippable");
  const held = eq?.getEquipment(EquipmentSlot.Mainhand);
  if (!held) return;
  held.setDynamicProperty("nr:mod", "shock");
  held.setLore(["§7改造: §6電撃", "§7耐久 120/200"]);
  const dur = held.getComponent("minecraft:durability");
  if (dur) dur.damage = Math.min(dur.maxDurability, dur.damage + 1);
  held.getComponent("minecraft:cooldown")?.startCooldown(p);
  eq.setEquipment(EquipmentSlot.Mainhand, held);   // ItemStack は写し。書き戻さないと何も変わらない
}
```

* **`getEquipment` / `getItem` が返すのは写し**。変更したら `setEquipment` / `setItem` で書き戻す。
* **動的プロパティは重ならないアイテム（`max_stack_size: 1`）だけ**。重なるアイテムに書くと例外（server:L12625）。武器は全部 1。
* lore は **20 行・1 行 50 文字まで**。それを超えると `ArgumentOutOfBoundsError`。§ の色コードも文字数に入る（要実機確認）。
* 耐久を `damage = maxDurability` にしても**壊れはしない**（要実機確認）→ 壊すのはスクリプトで（`setEquipment(slot, undefined)` + 音）。
* `ItemComponentTypeMap`（server:L2866）の安定版のキー: `book` `compostable` `cooldown` `durability` `dyeable` `enchantable` `food` `inventory`（`potion` はベータ）。

---

## 11. MolangVariableMap（server:L13317〜）— パーティクルに色と向きを渡す

```ts
setFloat(variableName: string, number: number): void;                              // server:L13351 〔T〕
setColorRGB(variableName: string, color: RGB): void;                               // server:L13327 → <name>.r/.g/.b
setColorRGBA(variableName: string, color: RGBA): void;                             // server:L13339 → <name>.r/.g/.b/.a
setVector3(variableName: string, vector: Vector3): void;                           // server:L13378 → <name>.x/.y/.z
setSpeedAndDirection(variableName: string, speed: number, direction: Vector3): void;  // server:L13365 → <name>.speed/.direction_x/_y/_z
// RGB（server:L20119）: red / green / blue（0..1）  RGBA（server:L20147）: + alpha
```

```js
/** @param {Player} p */
function bloodSpray(p) {
  const mv = new MolangVariableMap();
  mv.setColorRGBA("variable.tint", { red: 0.42, green: 0.02, blue: 0.02, alpha: 1 });
  mv.setSpeedAndDirection("variable.spray", 4.0, p.getViewDirection());
  mv.setFloat("variable.size", 1.5);
  p.dimension.spawnParticle("nr:blood_spray", p.getHeadLocation(), mv);
}
```

* 変数名は**パーティクル JSON 側と同じ綴り**で（`variable.tint` なら JSON は `variable.tint.r` など）。
  名前の約束は `nr_registry.py` と `gen_nr_particles.py` に合わせる。
* `NaN` / `Infinity` を渡さない（パーティクルが出ない・例外: 要実機確認）。ベクトルは正規化してから。

---

## 12. Block / BlockPermutation / BlockVolume

```ts
static resolve<T extends string = minecraftvanilladata.MinecraftBlockTypes>(blockName: T, states?: BlockStateArg<T>): BlockPermutation;  // server:L4171 〔T〕
withState<T extends keyof minecraftvanilladata.BlockStateSuperset>(name: T, value: minecraftvanilladata.BlockStateSuperset[T]): BlockPermutation;  // server:L4115
getState<T extends keyof minecraftvanilladata.BlockStateSuperset>(stateName: T): minecraftvanilladata.BlockStateSuperset[T] | undefined;   // server:L4034
getAllStates(): Record<string, boolean | number | string>;   // server:L4011
matches<T extends string = minecraftvanilladata.MinecraftBlockTypes>(blockName: T, states?: BlockStateArg<T>): boolean;   // server:L4100
// Block（server:L2904）: permutation（L2987）, typeId（L3011）, isAir（L2923）, location（L2975）, center()（L3109）, bottomCenter()（L3066）,
//   above(steps?)（L3044）, below(steps?)（L3059）, offset(offset)（L3368）, setPermutation(p)（L3385 〔RO✗〕）, setType(t)（L3403 〔RO✗〕）
constructor(from: Vector3, to: Vector3);   // server:L4626（BlockVolume。両端を含む）
```

```js
/** @param {Block} b */
function lampOn(b) {
  b.setPermutation(b.permutation.withState("nr:on", true));            // 状態名は例（ブロックの states に定義したもの）
  return BlockPermutation.resolve("nr:barricade", { "nr:damage": 0 });  // 同上
}
```

* `@minecraft/vanilla-data` は同梱していない（型は `any` に落ちる）→ 状態名の綴りは型で守られない。自前の状態は `nr:` 付き。
* **`BlockPermutation.resolve` は早期実行で呼べない**（〔E〕 無し）。モジュールの最上位で作り置きしない（`worldLoad` 後に遅延で）。

---

## 13. system（server:L16694〜）

```ts
run(callback: () => void): number;                                   // server:L16795 〔E〕
runTimeout(callback: () => void, tickDelay?: number): number;        // server:L16878 〔E〕
runInterval(callback: () => void, tickInterval?: number): number;    // server:L16823 〔E〕
runJob(generator: Generator<void, void, void>): number;              // server:L16862 〔E〕
clearRun(runId: number): void;                                       // server:L16758 〔E〕
clearJob(jobId: number): void;                                       // server:L16749 〔E〕
waitTicks(ticks: number): Promise<void>;                             // server:L16917 〔E〕〔T〕
readonly currentTick: number;                                        // server:L16721 〔E〕
```

```js
const loop = system.runInterval(() => { /* 毎 tick の処理（予算内で） */ }, 1);
system.runTimeout(() => system.clearRun(loop), 20 * 60);
system.runJob((function* () { for (let i = 0; i < 4096; i++) { /* 1 ブロック置く */ yield; } })());
async function later() { await system.waitTicks(5); }
```

* `run` はイベントの中から呼ぶと**同じ tick の終わり**、それ以外は次の tick（server:L16763〜 の注記。保証はされない）。
* `runJob` は tick ごとに時間の許す限り進める。`yield` を細かく入れる（街の組み立て・大量のブロック）。
* コールバックの中の例外は**そのコールバックだけ止まる**（ログに出る）。`runInterval` の本体は try/catch で包み、1 体の失敗で全体を止めない。
* 2.x では Promise が tick の途中でも解決される（`v2-overview.md`）。`waitTicks(0)` も可。

---

## 14. 列挙と定数

* `EntityDamageCause`（server:L1109）: `anvil` `blockExplosion` `campfire` `charging` `contact` `drowning` `entityAttack`
  `entityExplosion` `fall` `fallingBlock` `fire` `fireTick` `fireworks` `flyIntoWall` `freezing` `lava` `lightning` `maceSmash`
  `magic` `magma` `none` `override` `piston` `projectile` `ramAttack` `selfDestruct` `sonicBoom` `soulCampfire` `stalactite`
  `stalagmite` `starve` `suffocation` `temperature` `thorns` `void` `wither`（値は小文字始まりの文字列）。
  近接 = `entityAttack`、矢・投擲 = `projectile`、爆発 = `entityExplosion` / `blockExplosion`、罠のトゲ = `contact`。
* `GameMode`（server:L1459）: `Adventure` `Creative` `Spectator` `Survival`（2.x は大文字始まり）。
* `Direction`（server:L420）: `Down` `East` `North` `South` `Up` `West`。
* `EquipmentSlot`（server:L1380）、`HudElement`（server:L1796）、`HudVisibility`（server:L1816）、`InputButton`（server:L1839）、
  `ButtonState`（server:L147）、`InputPermissionCategory`（server:L1897）、`TimeOfDay`（server:L2568）、`EasingType`（server:L585）、
  `StructureRotation`（server:L2516）、`EntityInitializationCause`（server:L1340）、`ScriptEventSource`（server:L2400）。
* 定数: `TicksPerSecond = 20`（server:L20821）、`TicksPerDay = 24000`（server:L20815）。

---

## 15. `@minecraft/server-ui` 2.0.0

```ts
// ActionFormData（ui:L106）
body(bodyText: minecraftserver.RawMessage | string): ActionFormData;                     // ui:L112
button(text: minecraftserver.RawMessage | string, iconPath?: string): ActionFormData;   // ui:L119
divider(): ActionFormData;  header(text): ActionFormData;  label(text): ActionFormData;  // ui:L125 / L133 / L141
show(player: minecraftserver.Player): Promise<ActionFormResponse>;                      // ui:L160 〔RO✗〕〔T〕
title(titleText: minecraftserver.RawMessage | string): ActionFormData;                  // ui:L166
readonly selection?: number;                                                            // ui:L237（ActionFormResponse）
// ModalFormData（ui:L495）
dropdown(label: minecraftserver.RawMessage | string, items: (minecraftserver.RawMessage | string)[], dropdownOptions?: ModalFormDataDropdownOptions): ModalFormData;   // ui:L513
slider(label: minecraftserver.RawMessage | string, minimumValue: number, maximumValue: number, sliderOptions?: ModalFormDataSliderOptions): ModalFormData;   // ui:L566
textField(label: minecraftserver.RawMessage | string, placeholderText: minecraftserver.RawMessage | string, textFieldOptions?: ModalFormDataTextFieldOptions): ModalFormData;   // ui:L584
toggle(label: minecraftserver.RawMessage | string, toggleOptions?: ModalFormDataToggleOptions): ModalFormData;   // ui:L604
submitButton(submitButtonText: minecraftserver.RawMessage | string): ModalFormData;    // ui:L572
divider() / header(text) / label(text) / title(text)                                    // ui:L501 / L525 / L533 / L594
show(player: minecraftserver.Player): Promise<ModalFormResponse>;                      // ui:L552 〔RO✗〕〔T〕
readonly formValues?: (boolean | number | string | undefined)[];                       // ui:L652（ModalFormResponse）
// ModalFormDataDropdownOptions（ui:L671）: defaultValueIndex?; tooltip?
// ModalFormDataSliderOptions（ui:L693）: defaultValue?; tooltip?; valueStep?（既定 1）
// ModalFormDataTextFieldOptions（ui:L721）: defaultValue?; tooltip?
// ModalFormDataToggleOptions（ui:L742）: defaultValue?; tooltip?
// MessageFormData（ui:L329）: body（L335）, button1（L342）, button2（L349）, show（L368）, title（L374）
readonly selection?: number;                       // ui:L455（MessageFormResponse。0 = button1、1 = button2）
readonly canceled: boolean;                        // ui:L257（FormResponse）
readonly cancelationReason?: FormCancelationReason;   // ui:L250   FormCancelationReason（ui:L35）: UserBusy | UserClosed
// FormRejectError（ui:L759）: reason: FormRejectReason（ui:L40: MalformedResponse | PlayerQuit | ServerShutdown）
closeAllForms(player: minecraftserver.Player): void;   // ui:L663（UIManager）   export const uiManager: UIManager;  ui:L769
```

```js
/** @param {Player} p */
async function terminal(p) {
  const a = await new ActionFormData().title({ translate: "nr.ui.terminal" }).body("…")
    .button("設定", "textures/nr/ui/settings").button("図鑑", "textures/nr/ui/bestiary").show(p);
  if (a.canceled) {
    if (a.cancelationReason === FormCancelationReason.UserBusy) system.runTimeout(() => terminal(p), 20); // チャット等が開いていた
    return;
  }
  const m = await new ModalFormData().title("設定")
    .slider("ゴアレベル", 0, 100, { defaultValue: 100, valueStep: 5, tooltip: "0 = なし" })
    .toggle("血しぶき", { defaultValue: true })
    .dropdown("難易度", ["Easy", "Normal", "Hard"], { defaultValueIndex: 1 })
    .textField("名前", "Runner", { defaultValue: "" })
    .submitButton("保存").show(p);
  if (!m.canceled && m.formValues) {
    const gore = Number(m.formValues[0]);      // slider → number
    const blood = m.formValues[1] === true;    // toggle → boolean
    const diff = Number(m.formValues[2]);      // dropdown → 選んだ番号
    const name = String(m.formValues[3] ?? ""); // textField → string
    console.log(gore, blood, diff, name);
  }
  const yn = await new MessageFormData().title("確認").body("リセット？").button1("はい").button2("いいえ").show(p);
  if (yn.selection === 0) uiManager.closeAllForms(p);
}
```

* **2.0.0 は「オプションの辞書」**: `slider(label, min, max, {defaultValue, valueStep})`、`toggle(label, {defaultValue})`、
  `dropdown(label, items, {defaultValueIndex})`、`textField(label, placeholder, {defaultValue})`。
  1.x の位置引数（`slider(l, 0, 100, 5, 100)` / `toggle(l, true)`）は TS2554 / TS2559。d.ts 内の例（ui:L471〜L481 / L619〜L629）は 1.x の形なので写さない。
* `show` は 〔RO✗〕 → **before イベントの中から開かない**（`system.run` で）。チャットや他の画面が開いていると
  すぐ `canceled` + `UserBusy` で返る → 少し待って開き直す。
* プレイヤーが抜けると Promise が `FormRejectError`（`reason = PlayerQuit`）で reject される → `try/catch`。
* `formValues` は**コントロールを足した順**の配列。`label` / `header` / `divider` が `formValues` の番号を 1 つ使うか
  （`undefined` が入るか）は**要実機確認**（型に `undefined` が含まれるのはそのため）。**入力コントロールの間に label / header / divider を挟まない**
  （置くなら全部の入力の後ろ）—これならどちらでも番号がずれない。ActionFormData の `selection` も同じ理由で、ボタンの間に label 等を挟まない。
* ボタンの絵は RP の**拡張子なしのパス**（`textures/nr/ui/settings`）。

---

## 16. 2.3.0 安定版で**使えない**もの（書きたくなるが型エラー／実機で動かない）

### 16.1 2.4.0-beta（1.21.120）にだけあるもの（`@minecraft/server@2.4.0-beta.1.21.120-stable` と d.ts を比べて抽出）

| 置き場 | ベータ専用（使わない） | 代わり |
|---|---|---|
| `Entity` | `target`、`getAABB()`、`getBlockStandingOn()`、`getAllBlocksStandingOn()` | 追跡先はスクリプトで持つ / 当たり箱は `scripts/data/zombie_shapes.js` / 足元は `dimension.getBlock(loc − {y:0.01})` |
| `Player` | `eatItem`、`getAimAssist`、`getControlScheme` / `setControlScheme`、`postClientMessage`、`stopSound` / `stopAllSounds` | 音は短く作って止めずに済ませる |
| `World` | `broadcastClientMessage`、`getAimAssist`、`getPackSettings` | 設定は `nr:settings`（動的プロパティ）＋フォーム |
| `WorldAfterEvents` | `chatSend`、`messageReceive`、`packSettingChange`、**`playerSwingStart`**、`playerUseNameTag` | 振りは `entityHitEntity` / `entityHitBlock` / アイテムの `onHitEntity`、チャット命令は `/scriptevent` かカスタムコマンド |
| `WorldBeforeEvents` | `chatSend`、`playerPlaceBlock` | after の `playerPlaceBlock` |
| `SystemBeforeEvents` | `watchdogTerminate` | 重い処理を `runJob` に |
| `Camera` | `playAnimation`、`setCameraWithEase` | `setCamera(…, {easeOptions})` |
| `Dimension` | `getWeather`、`stopSound` / `stopAllSounds`、`findClosestBiome`、`getGeneratedStructures` | — |
| `Block` | `isSolid`、`canPlace`、`trySetPermutation`、`getMapColor` | `isAir` / `isLiquid` / 自前のタグ |
| `BlockCustomComponent` | `onBreak` | `onPlayerBreak` |
| 列挙 | `EquipmentSlot.Body`、`ItemComponentTypes.Potion`、`EntityComponentTypes.Npc` | — |
| 型・クラス | `AABB`、`LootTable` 系（`LootTableManager.generateLootFromTable` 等）、`ControlScheme`、`PlayerSwingStartAfterEvent`、`ChatSend*`、`WatchdogTerminate*`、`CompoundBlockVolume`、`*Spline`、`ItemPotionComponent` ほか（計 107 の宣言） | ルートは spec の `loot` からスクリプトで落とす（DESIGN §4） |

`@minecraft/server-ui` は 2.1.0-beta（1.21.120）と 2.0.0 でメンバーの差は無い。

### 16.2 1.x にあって 2.x で消えた・変わったもの

| 1.x の書き方 | 2.3.0 |
|---|---|
| `entity.isValid()` / `block.isValid()` / `container.isValid()` | **プロパティ** `isValid` |
| `entity.applyKnockback(dirX, dirZ, horizontal, vertical)` | `applyKnockback({x, z}, vertical)`（水平は強さ込み） |
| `world.afterEvents.worldInitialize` | `world.afterEvents.worldLoad` |
| `world.beforeEvents.worldInitialize`（カスタムコンポーネント登録） | `system.beforeEvents.startup` |
| `runCommandAsync(...)`（Entity / Dimension） | `runCommand(...)`（同期）か、API で直接 |
| `world.playSound(...)` | `dimension.playSound(...)` / `player.playSound(...)` |
| `player.isOp()` | `player.commandPermissionLevel` |
| JSON の `"minecraft:custom_components": ["nr:x"]` | `"nr:x": { ...params }` をコンポーネントに直接 |
| `ModalFormData.toggle(l, true)` / `slider(l, min, max, step, def)` / `dropdown(l, items, def)` / `textField(l, ph, def)` | 最後をオプションの辞書に（§15） |
| `getComponent` が無効な Entity で `undefined` | **例外**（先に `isValid`） |
| 最上位で `world.getDimension("overworld")` | early execution で例外 → `worldLoad` 以降 |
| `Effect.typeId` が名前空間なし | 常に `minecraft:` 付き |

### 16.3 存在しない（よく推測されるが無い）

`setTimeout` / `setInterval`（→ `system.runTimeout` / `runInterval`）、`InputButton.Sprint` / `Attack` / `Use`、
`Entity.isJumping`（Player だけ）、`world.getEntities(...)`（→ `dimension.getEntities`）、`entity.velocity`（→ `getVelocity()`）、
`entity.setVelocity()`（→ `clearVelocity()` + `applyImpulse()`）、`entity.getHealth()`（→ `getComponent("minecraft:health").currentValue`）、
`player.inventory`（→ `getComponent("minecraft:inventory").container`）、`player.getItemInHand()`（→ equippable の `Mainhand`）、
`dimension.getLight()`（→ `getLightLevel`）、`TextEncoder` / `fetch` / `require`。

---

## 17. NIGHT RUNNER での使い方の約束（実装者向けの要点）

* **初期化**: 最上位では subscribe と `system.beforeEvents.startup` の登録だけ。`world` を触るのは `worldLoad` か `system.run` の中。
* **before イベント**: 取り消し（`cancel`）と読み取りだけ。書くのは `system.run`。フォームを開くのも `system.run`。
* **ダメージ**: `entityHurt`（after、フィルタ `entityTypes`）で受け、`applyHit` に流す（DESIGN §12）。プールは `resetToMaxValue()`。
* **プレイヤーを動かす**: `applyKnockback({x, z}, v)` と効果だけ。`applyImpulse` はゾンビ・gib・死体だけ。
* **プロパティ**: `setProperty` は次の tick に反映。状態の真実はスクリプト側の表に持つ。
* **長く持つ参照**: 使う直前に `isValid`。保存は `id`。
* **演出**: `spawnParticle` / `playSound` / `spawnEntity` は try/catch（未読み込みチャンクで例外）＋ 1 tick 予算。
* **フォーム**: 2.0 のオプション辞書。入力の間に label/header/divider を挟まない。`UserBusy` は少し待って再表示。
* **型検査を通す**: `python3 tools/nightrunner/check_nr_types.py`（ビルドに含まれる）。`@ts-ignore` に頼らない。

---

## 18. 要実機確認の一覧

1. 死体（`damage_sensor` で全ダメージ無効）を叩いた時に `entityHitEntity` が来るか、`entityHurt` が来ないか（§3.1/3.2）。
2. `entityHitEntity` の `entityTypes` フィルタが攻撃側・被弾側のどちらに効くか（§3.2）。
3. `entityHurt.damage` が防具・耐性の軽減後か（§3.1）。
4. `projectileHit*.hitVector` が正規化済みか（§3.3）。
5. `itemReleaseUse.useDuration` の単位と意味（残り tick か）（§3.6）。
6. `getMovementVector()` の `x` の符号（右が + か −か）（§3.7）。
7. プレイヤーへの `applyImpulse` / `clearVelocity` が例外か無視か（§4.4）。
8. `playAnimation` が entity の `animations` に登録していない ID でも再生されるか、`stopExpression` の既定値（§4.5）。
9. `getEntitiesFromViewDirection` / `getEntitiesFromRay` の結果が近い順か（§4.6）。
10. `Dimension.getLightLevel` / `getSkyLightLevel` が夜の暗さ（時刻）を反映するか（§6.4）。
11. `fillBlocks` の体積上限（§6.4）。
12. 動的プロパティの文字列の長さ上限（§7）。
13. 構造物の回転の基準点（§8）。
14. 耐久が尽きたカスタム武器が自動で壊れるか（§10）、lore の 50 文字に § の色コードが入るか。
15. `ModalFormData` の `label` / `header` / `divider` が `formValues` の番号を使うか、`ActionFormData` の `selection` がボタンだけを数えるか（§15）。
16. ブロックの `onRandomTick` に追加のコンポーネントが要るか（§2）。
17. `setFov()` を引数なしで呼んで元に戻るか（§5.2）。

---

## 19. この文書の検査のしかた（例のコードが d.ts と食い違っていないか）

この文書の ` ```js ` を全部抜き出し、各ブロックを `{}` で包んで 1 つのモジュールにし、`check_nr_types.py` にかける。
2026-10 時点の結果: **38 ブロック、型の誤り 0**（わざと 2 か所壊すと 2 件とも検出されることも確認）。
同じ手順で、正しい使い方の見本（全部通る）と、わざと間違えた 14 か所（`applyKnockback(1,2,3,4)`、`isValid()`、
無いメソッド、ベータ専用の import・メソッド・イベント、`world.playSound`、`worldInitialize`、`runCommandAsync`、`setTimeout`、
`InputButton.Sprint`、1.x 形の `slider` / `toggle`、`teleport` のオプション名違い）が**全部検出される**ことも確かめてある。

```text
mkdir -p build_preview/nr_research/typecheck_sample/md_examples
python3 -I build_preview/nr_research/typecheck_sample/extract_md_examples.py "$PWD"
python3 tools/nightrunner/check_nr_types.py build_preview/nr_research/typecheck_sample/md_examples
```

`extract_md_examples.py`（`build_preview/` は gitignore なので、無ければ下をそのまま保存する）:

```text
# script_api.md の ```js を全部抜き出して 1 つのモジュールにする（各ブロックは {} で包む）。
import os, re, sys
ROOT = sys.argv[1]
src = open(os.path.join(ROOT, "tools/nightrunner/reference/script_api.md"), encoding="utf-8").read()
blocks = re.findall(r"```js\n(.*?)```", src, re.S)
head = """import {
  world, system, Player, Entity, Dimension, Block, ItemStack, BlockVolume, BlockPermutation, MolangVariableMap,
  EntityDamageCause, CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, EntityInitializationCause,
  InputButton, ButtonState, TicksPerSecond, EasingType, HudVisibility, HudElement, InputPermissionCategory, GameMode,
  TimeOfDay, StructureRotation, StructureAnimationMode, EquipmentSlot,
} from "@minecraft/server";
import { ActionFormData, ModalFormData, MessageFormData, FormCancelationReason, uiManager } from "@minecraft/server-ui";
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
const ZOMBIE_TYPES = ["nr:z_office_worker", "nr:z_volatile"];
"""
out = head + "".join(f"\n// ---- 例 {i + 1} ----\n{{\n{b}}}\n" for i, b in enumerate(blocks))
dst = os.path.join(ROOT, "build_preview/nr_research/typecheck_sample/md_examples/examples.js")
open(dst, "w", encoding="utf-8").write(out)
print(f"{len(blocks)} blocks -> {dst}")
```
