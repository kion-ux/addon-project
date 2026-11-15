# 影渡り — 技術の取り決め（モジュール契約）

ゲームの中身は [DESIGN.md](DESIGN.md)。数値は `src/config.js` の `CONFIG`。
ここは **モジュール同士の約束** であり、別々に書かれたモジュールがそのまま組み合わさるための正本。

## 全体

- 素の ES Modules。ビルド不要。`three@0.170.0` を import map で読む（`three` と `three/addons/`）
- 画像・音声ファイルは使わない。テクスチャはキャンバスで描き、音は WebAudio で合成する
- 外部への通信は three の読み込み（jsDelivr）と Google Fonts だけ
- 文言は日本語。コードのコメントも日本語
- 単位はメートル・秒・ラジアン。**Y が上、北が -Z**。街は x, z ともに -210..210
- 向き: `yaw = 0` で北 (-Z) を向く。前 = `(-sin yaw, 0, -cos yaw)`、右 = `(cos yaw, 0, -sin yaw)`。
  モデルはローカル -Z を前に作り、`obj.rotation.y = yaw` で向ける。`src/core/math.js` に関数あり
- 地面（通り）は y = 0。海と運河の水面は y = -1.2（`CONFIG.world.seaLevel`）

## ファイルと担当

```
index.html              画面の枠・import map・読み込み画面（#view, #hud-layer, #touch-layer, #menu-layer）
src/main.js             起動・ゲームループ・状態遷移・デバッグ窓口（契約の正本）
src/config.js           調整値
src/core/events.js      イベントバス          src/core/math.js   数学の小道具
src/core/save.js        保存                  src/core/input.js  Input
src/core/audio.js       AudioSystem
src/world/collision.js  CollisionWorld        src/world/city.js  City（+ textures.js など補助は自由）
src/world/sky.js        Sky
src/actors/rig.js       createHumanoid / Humanoid（人型の骨組みと手続きアニメ）
src/actors/player.js    Player                src/actors/npcs.js NpcManager（+ nav.js）
src/combat/combat.js    Combat
src/game/missions.js    Missions
src/view/camera.js      CameraRig             src/view/hud.js    Hud
src/view/fx.js          Fx
src/stubs/<名前>.js      各モジュールの仮実装（本物が読めない時の代役。消さない）
tests/                  Playwright による自動テスト
```

各モジュールは自分の DOM と CSS を自分で作る（`<style>` を `document.head` に足す）。
`index.html` には空の層しかない。HUD は `#hud-layer`、タッチ操作は `#touch-layer`、
メニュー・タイトル・地図は `#menu-layer` に差し込む。

## 起動と毎フレーム（main.js）

1. `MODULES` の順に import。失敗したら `src/stubs/` の代役を使い `game.fallbacks` に記録
2. 全モジュールを `new X(game)` → 同じ順に `await x.init()`
   - **constructor では他モジュールに触らない**。`init()` では自分より前のモジュールだけ使ってよい
   - 順番: collision → city → sky → audio → input → fx → player → npcs → combat → missions → camRig → hud
3. 毎フレーム（`realDt` は実時間、`dt = realDt × timeScale`）:

```
timeScale = fx.computeTimeScale(realDt)     ヒットストップ・スローモーション
input.update(realDt)
if state が 'playing' か 'dead':
    player.update(dt) → combat.update(dt) → npcs.update(dt) → missions.update(dt)
city.update(realDt)
sky.update(playing ? dt : 0)
fx.update(playing ? dt : realDt)
camRig.update(realDt)
audio.update(realDt)
hud.update(realDt)
renderer.render(scene, camera)
```

各 update は main が try/catch で包み、例外は `game.errors` に入る（ゲームは止まらない）。

### game（全モジュールが受け取る共有の入れ物）

| 項目 | 内容 |
|---|---|
| `THREE` | three の名前空間 |
| `cfg` | `CONFIG` |
| `events` | イベントバス `on(name, fn) → off`, `once`, `emit(name, payload)` |
| `rng` | シード付き乱数 `rng()`, `rng.range(a,b)`, `rng.int(a,b)`, `rng.pick(arr)`, `rng.chance(p)`, `rng.fork(salt)` |
| `clock` | `{ time, realTime, dt, realDt, timeScale, frame }` |
| `settings` | `{ quality:'low'|'medium'|'high', sensitivity, invertY, viewMode:'third'|'first', sfxVolume, musicVolume, showFps, autoParkour, vibration }` |
| `quality()` | 今の品質の設定 `CONFIG.render.quality[settings.quality]` |
| `state` | `'boot' | 'title' | 'playing' | 'paused' | 'map' | 'dead'` |
| `renderer`, `scene`, `camera`, `canvas` | three の描画一式。`camera` は `scene` に追加済み |
| `isTouch`, `isTest`, `isDebug` | 端末・起動モード |
| `stats` | `{ fps, frameMs, drawCalls, triangles, pixelRatio }` |
| モジュール | `collision, city, sky, audio, input, fx, player, npcs, combat, missions, camRig, hud` |

関数:

| 関数 | 内容 |
|---|---|
| `setState(s)` | 状態を変えて `state:changed {from,to}` を出す |
| `startNewGame()` | 新しく始める（npcs.reset → missions.loadState(null) → player.spawnAt → 'playing'） |
| `continueGame(data?)` | 保存から続ける |
| `hasSave()` | 保存があるか |
| `respawn()` | 倒れた後の再開（missions.respawnPoint → npcs.calmDown → player.respawn） |
| `pause()`, `resume()`, `openMap()`, `toTitle()` | 状態の切り替え（'map' から戻るのも `resume()`） |
| `saveNow()` | すぐ保存 |
| `applySettings(partial)` | 設定を変える（品質・視点などを反映して `settings:changed`） |
| `vibrate(ms)`, `toggleFullscreen()`, `requestWakeLock()` | 端末の機能（使えなくても落ちない） |

### デバッグ窓口 `window.__game.debug`

`step(n, dt=1/60)` で n フレーム進める（テストでは自走ループが止まっている）/ `render()` / `snapshot()` /
`inject(partialInput)` / `clearInject()` / `teleport(x,y,z,yaw)`。URL 引数: `?test=1`（自走なし・保存なし・
タイトルを飛ばす）, `?seed=N`, `?quality=low|medium|high`, `?skipTitle=1`, `?view=first`, `?live=1`（test でも自走）, `?debug=1`。

## イベント

| 名前 | 中身 | 出す側 |
|---|---|---|
| `state:changed` | `{from, to}` | main |
| `game:started` | `{fresh}` | main |
| `settings:changed` | `{prev, settings}` | main |
| `resize` | `{width, height}` | main |
| `player:jump` | `{sprint}` | player |
| `player:land` | `{fall, hard, roll, soft, water}` | player（fall = 落ちた高さ m） |
| `player:parkour` | `{move}` move = `'vault'|'climbStart'|'climbLeap'|'mantle'|'hang'|'wallRun'|'wallJump'|'gapJump'|'roll'|'dive'|'zipline'|'balance'` | player |
| `player:waterEnter` | `{speed}` | player |
| `player:damaged` | `{amount, hp, source, dir}` | player |
| `player:died` | `{cause}` | player |
| `player:respawn` | `{}` | main |
| `player:hidden` | `{hidden}` | player |
| `player:sense` | `{active}` | player |
| `combat:swing` | `{index}` | combat |
| `combat:hit` | `{target, damage, blocked, kind, point}` | combat |
| `combat:counter` | `{npc}` | combat |
| `combat:assassinate` | `{npc, air}` | combat |
| `combat:dodge` | `{}` | combat |
| `combat:knife` | `{target}` | combat |
| `npc:stateChanged` | `{npc, from, to}` | npcs |
| `npc:alerted` | `{npc}` | npcs（平常/怪しみ → 戦闘になった時） |
| `npc:attackStart` | `{npc}` | npcs（振りかぶり開始 = カウンター受付の予告） |
| `npc:killed` | `{npc, method}` | npcs（method = damage の kind） |
| `target:fleeing` | `{npc}` | npcs |
| `tower:synced` | `{tower}` | missions |
| `contract:started` / `contract:completed` | `{contract}` | missions |
| `collectible:picked` | `{item, count, total}` | missions |
| `chest:opened` | `{chest, money}` | missions |
| `money:changed` | `{money, delta}` | missions |
| `upgrade:bought` | `{kind, level}` | missions |
| `race:started` / `race:checkpoint` / `race:finished` | `{race, index, time, medal}` | missions |
| `ui:toast` | `{text, kind}` | 誰でも（hud が表示） |
| `ui:banner` | `{title, sub}` | 誰でも（hud が大きく表示） |
| `view:changed` | `{mode}` | camRig |

## モジュール

### CollisionWorld — `src/world/collision.js`

すべて軸に沿った箱（box）と、片側へ傾いた屋根（wedge）。空間ハッシュ（一マス 8m 前後）で引く。

```
Collider = { id, type:'box'|'wedge', min:{x,y,z}, max:{x,y,z}, axis:'x'|'z', rise:1|-1,
             kind:'ground'|'building'|'roof'|'wall'|'prop'|'beam'|'tower'|'ship'|'stall'|'awning'|'hay'|'pier'|'stairs',
             climbable:bool, soft:bool, data:any }
```

- `addBox(min, max, opts={kind, climbable, soft, data}) → Collider`
- `addWedge(min, max, axis, rise, opts) → Collider` — 屋根の片面。上面は軸に沿った斜面で、低い側が `min.y`
  （厚み 0）、高い側が `max.y`。`rise=1` なら軸の + 側が高い
- `addWater(min, max) → Water` — 水の領域。水面は `max.y`
- `topAt(collider, x, z) → number` — その点での上面の高さ
- `queryAABB(minX, minY, minZ, maxX, maxY, maxZ, out=[]) → Collider[]`
- `groundAt(x, z, fromY, radius=0) → {y, collider} | null` — `fromY + 0.05` 以下で一番高い上面。
  `radius > 0` なら足元の円が少しでも乗っている面を数える（端に立てる）
- `moveCapsule(pos, radius, height, delta, opts={stepHeight}) → result` — 縦の円柱として押し戻し。
  `pos`（Vector3, 足元）を書き換え、`{onGround, groundY, ground, hitWall, wallNormal:{x,z}, wallCollider, hitCeiling, stepped}` を返す。
  `stepHeight` 以下の段差は登る。速い移動はすり抜けないよう内部で分割する
- `raycast(origin, dir, maxDist, opts={ignoreSoft:true, kinds?}) → {distance, point, normal, collider} | null`（dir は正規化済み）
- `lineOfSight(a, b) → bool` — 柔らかい物（日除け・干し草）は視線を遮らない
- `wallProbe(pos, yaw, distance, heightOffset) → {collider, normal:{x,z}, point, topY, climbable} | null` — 水平の光線で前の壁を探す。
  `topY` は当たった物のその点の上面の高さ
- `waterAt(x, z) → number | null` — 水面の高さ
- `pointInside(x, y, z) → Collider | null`
- `colliders` 配列、`waters` 配列

### City — `src/world/city.js`

`init()` で街を作る（`game.rng.fork(1)` を使い、同じ seed なら同じ街）。メッシュを `scene` に、当たり判定を
`collision` に入れ、以下のデータを持つ。静的な形は材質ごと・区画（`CONFIG.world.chunk`）ごとにまとめて描画回数を抑える。

| 項目 | 内容 |
|---|---|
| `root` | 街のメッシュの親 Group |
| `bounds` | `{minX, maxX, minZ, maxZ}` |
| `seaLevel` | 水面の高さ |
| `districts` | `[{id, name, nameEn, rect:{minX,maxX,minZ,maxZ}, center:{x,z}}]`（DESIGN.md の 5 区画） |
| `buildings` | `[{id, min, max, roofY, roofType:'flat'|'gable'|'dome'|'tower', district}]`（地図描画にも使う） |
| `navGrid` | `{cellSize, originX, originZ, w, h, walk:Uint8Array, height:Float32Array}` 地上の歩ける所（1）と高さ |
| `spawnPoints` | `{player:{x,y,z,yaw}, civilians:[{x,y,z}]}` |
| `patrols` | `[{id, district, points:[{x,y,z}], loop}]` 地上の巡回路 |
| `guardPosts` | `[{x,y,z,yaw,district}]` 立ち番 |
| `archerPosts` | `[{x,y,z,yaw,district}]` 屋根の上 |
| `towers` | `[{id, name, district, base:{x,y,z}, top:{x,y,z}, dive:{x,y,z}, yaw}]` 5 本。`top` は頂上の立ち位置、`dive` は飛び込み先の水 |
| `targets` | `[{id, district, name, title, spot:{x,y,z,yaw}, flee:{x,y,z}, guards:[{x,y,z,yaw,kind}], area:{minX,maxX,minZ,maxZ}}]` 5 人（id は区画 id） |
| `hidingSpots` | `[{x,y,z,radius,kind:'bush'|'hay'}]` |
| `chests` | `[{id,x,y,z,yaw}]` 10 |
| `collectibles` | `[{id,x,y,z}]` 30（多くは屋根の上） |
| `shops` | `[{id, kind:'smith'|'tailor'|'doctor', name, x,y,z,yaw}]` |
| `races` | `[{id, name, start:{x,y,z,yaw}, checkpoints:[{x,y,z}], medals:{gold,silver,bronze}}]` 3 |
| `ziplines` | `[{id, a:{x,y,z}, b:{x,y,z}}]`（a が高い側） |
| `restricted` | `[{minX,maxX,minZ,maxZ}]` 立入禁止 |
| `landmarks` | `[{name, x, z}]` 地図の地名 |

関数: `update(dt)`（水面・旗・灯り）, `isRestricted(x,z)`, `districtAt(x,z)`, `applyQuality(q)`。

### Sky — `src/world/sky.js`

`dayTime`（0..1, 0.25 夜明け・0.5 正午・0.75 日没）, `nightFactor`（0 昼〜1 夜）, `sunDir`（Vector3）,
`sun`（DirectionalLight）, `hemi`。`init()` で空・光・霧（`scene.fog`）。`update(dt)` で時刻を進め、光と霧
（遠さは `game.quality().fogFar`）を合わせ、影のカメラをプレイヤーに追従させる。`setDayTime(t)`, `applyQuality(q)`。

### AudioSystem — `src/core/audio.js`

`unlock()`（タップの中で呼ぶ。何度呼んでもよい）, `play(name, {pos, volume, pitch})`, `setMusic(mode)`
（`'none'|'title'|'explore'|'stealth'|'combat'`）, `update(dt)`（聞き手 = カメラ、環境音）。音量は `game.settings`。
音の名前: `step stepRoof jump land landHard roll climb grab vault whoosh hit clash kill assassinate counter dodge
knifeThrow knifeHit arrow arrowHit splash swim alert suspicious sync coin chest ui uiBack hurt death zipline bell
race checkpoint contract shout`。知らない名前は無視する。

### Input — `src/core/input.js`

`state`（毎フレーム `update()` が作り直す）:

```
{ move:{x, y}, moveMag, sprint, look:{dx, dy},
  buttons:{ jump, attack, dodge, throw, sense, crouch, interact, view, map, pause }  // 各 {down, pressed, released, heldTime}
  device:'touch'|'keyboard'|'gamepad' }
```

- `move.y` は前（スティック上）、`move.x` は右。大きさ ≤ 1
- `sprint` = スティックを `CONFIG.input.sprintThreshold` 以上倒す / Shift
- `look.dx` 正 = 右を向く、`look.dy` 正 = 上を向く（ラジアン。感度・上下反転は Input が掛ける）。カメラは `yaw -= dx; pitch += dy`
- `pressed` は「前回の update から押された」。フレームの間の短いタップも取りこぼさない
- `setOverride(partial | null)` — テスト用。`{move:{x,y}, sprint, look:{dx,dy}, buttons:{jump:true}}`。
  `true` は押しっぱなし扱いで、`pressed` は変化から計算する
- `setButtonLabel(name, text)`, `setButtonVisible(name, bool)`, `setButtonHighlight(name, false|'on'|'danger')`
- タッチの部品は `#touch-layer` に作り、`game.state === 'playing'` でタッチ端末の時だけ見せる。
  ボタン配置は右下、安全領域（`env(safe-area-inset-*)`）の内側。複数の指を同時に扱う（Pointer Events）
- 最初のタップ・キー入力で `game.audio.unlock()` を呼ぶ

### 人型 — `src/actors/rig.js`

```
createHumanoid(THREE, opts) → Humanoid
opts = { kind:'player'|'guard'|'spear'|'brute'|'archer'|'target'|'civilian', seed, scale=1, palette? }
```

- 一体 = **SkinnedMesh 1 個**（描画 1 回）。箱・円柱・球を組み合わせ、各頂点を一つの骨に 100% で結ぶ。
  色は頂点カラー。材質は一体ごとの `MeshLambertMaterial({vertexColors:true})`（シェーダは共有される）
- `root`（Group、足元が原点、-Z が前）, `mesh`, `bones`（hips, spine, chest, neck, head, upperArmL/R, forearmL/R,
  handL/R, thighL/R, shinL/R, footL/R, weapon）, `height`
- `play(clip, {fade=0.15, speed=1, duration, loop, restart})` — `duration` を渡すと一回再生がその秒数で終わる
- `update(dt, {speed, lean})` — `speed` は地面を進む速さ（歩き・走りの周期に使う）
- `clip`, `clipTime`, `clipDone`（一回再生が終わったか）
- `setTint(color|null, strength=1)`（気配察知・標的の強調）, `setVisible(bool)`, `setHeadVisible(bool)`, `setWeaponVisible(bool)`
- `getBoneWorldPosition(name, out)`, `getWeaponTip(out)`, `getWeaponBase(out)`, `dispose()`
- `CLIPS`（名前の配列）。最低限: `idle walk run sprint crouchIdle crouchWalk jump fall land roll climbIdle climbUp
  climbSide hang shimmy mantle vault wallRun swim dive balance zipline slash1 slash2 slash3 block blockHit dodge
  counter assassinate airAssassinate assassinated throw hurt stagger death windup strike spearWindup spearStrike
  heavyWindup heavyStrike bowAim bowShoot cower flee lookAround sync`

### Player — `src/actors/player.js`

| 項目 | 内容 |
|---|---|
| `position` | Vector3（足元） |
| `velocity` | Vector3 |
| `yaw` | 向き |
| `state` | `'ground'|'air'|'climb'|'hang'|'wallRun'|'vault'|'mantle'|'roll'|'swim'|'dive'|'zipline'|'balance'|'action'|'stagger'|'dead'` |
| `onGround`, `crouching`, `sprinting`, `inWater`, `isOnRoof`, `isHidden`, `senseActive` | 状態 |
| `hp`, `maxHp`, `knives`, `knivesMax`, `alive` | 数値（missions が最大値を書き換える） |
| `visibility` | 0..1 見つかりやすさの倍率（しゃがみ・隠れ・夜で下がる。隠れ中は 0） |
| `radius`, `height` | 当たりの大きさ |
| `rig` | Humanoid |
| `action` | 実行中の行動 `{name, t, duration, ...}` か null |
| `invulnerable` | 無敵時間中か |
| `fallStartY` | 落ち始めの高さ（空中暗殺の判定に使う） |

- `update(dt)` — 入力（move, sprint, jump, crouch, sense）を読み、移動・パルクール・アニメ
- `spawnAt({x,y,z,yaw})`, `teleport(vec3, yaw)`, `respawn(point)`
- `damage(amount, {source, dir, kind}) → 実際に受けた量`（無敵・死亡中は 0）
- `heal(n)`
- `canAct() → bool` — 戦いの行動を始めてよいか（地上・空中・塀の上。登攀・泳ぎ・転がり・行動中は false）
- `startAction(def) → bool` — combat が呼ぶ。def = `{name(clip), duration, lockMove=true, faceYaw, lunge:{x,z,distance},
  iFrames:[t0,t1], gravity=true, onEnd, cancelableAfter}`。実行中 `state='action'`、終わったら元の状態へ
- `cancelAction()`
- `headPosition(out)` — 目の位置（一人称カメラ用）
- `saveState() → {hp, knives}`, `loadState(d)`

### NpcManager — `src/actors/npcs.js`（+ `nav.js`）

| 項目 | 内容 |
|---|---|
| `list` | 全 NPC |
| `alertLevel` | 0 平常 / 1 捜索・怪しみ / 2 戦闘 |

関数: `update(dt)`, `reset()`（衛兵・市民を最初の配置に戻す。標的は missions が出す）, `calmDown()`,
`spawnGuard({kind, x,y,z, yaw, patrol, district}) → Npc`, `spawnTarget({id, name, title, x,y,z,yaw, flee}) → Npc`,
`removeNpc(npc)`, `nearest(pos, maxDist, filter) → Npc|null`, `queryRadius(pos, r, out=[])`,
`noise(pos, radius, kind)`（物音）, `combatants() → Npc[]`, `applyQuality(q)`。

Npc:

```
id, kind:'guard'|'spear'|'brute'|'archer'|'target'|'civilian', isTarget, targetId, name, title,
position(Vector3), yaw, velocity, radius, height, hp, maxHp, alive,
state:'idle'|'patrol'|'suspicious'|'search'|'combat'|'flee'|'stunned'|'dead',
awareness(0..1), seesPlayer, rig(Humanoid), district,
attack:{ phase:'none'|'windup'|'strike'|'recover', t, counterable }
canBeAssassinated(player) → bool
damage(amount, {source, kind:'slash'|'finisher'|'counter'|'knife'|'assassinate'|'air'|'arrow', dir}) → {killed, blocked, damage}
kill(info), stagger(seconds), headPosition(out)
```

- 衛兵の攻撃は `windup`（この間 `npc:attackStart` 済み。最後の `CONFIG.combat.counterWindow` 秒は `counterable=true`）
  → `strike` の瞬間に `game.combat.npcStrike(npc)` を呼ぶ → `recover`
- 弓兵は `game.combat.spawnProjectile({kind:'arrow', ...})` で矢を射る
- 同時に斬りかかるのは `CONFIG.combat.maxAttackers` 人まで

### Combat — `src/combat/combat.js`

| 項目 | 内容 |
|---|---|
| `damageMul` | 刃の強化倍率（missions が書く） |
| `assassinationCandidate` | 今「斬」で暗殺できる相手（hud がボタンの字を変える） |
| `counterCandidate` | 今「避」でカウンターできる相手 |
| `lockTarget` | 剣の自動の踏み込み先 |
| `projectiles` | 飛んでいるナイフ・矢 |

`update(dt)` — 入力の attack / dodge / throw を読み、`player.startAction` で行動を始め、当たりを解決する。
`npcStrike(npc) → 'hit'|'dodged'|'countered'|'miss'`, `spawnProjectile({kind:'knife'|'arrow'|'rock', owner, from, vel, damage})`。

### Missions — `src/game/missions.js`

| 項目 | 内容 |
|---|---|
| `money`, `upgrades:{blade, armor, pouch}` | 所持金と強化の段階 |
| `towers` | city.towers + `synced` |
| `contracts` | `[{id, name, title, desc, district, status:'locked'|'available'|'done', npc}]` |
| `collectibles`, `chests`, `races`, `shops` | city のデータ + 進行（`taken`, `opened`, `best`） |
| `objective` | `{text, pos:{x,y,z}|null, kind}` 今の目標（hud が表示） |
| `interactPrompt` | `{label, kind, target}` か null（「調」ボタン） |
| `activeRace` | 競走中なら `{race, index, time}` |
| `stats` | `{kills, assassinations, counters, synced, collectibles, chests, contracts, playTime}` |

関数: `update(dt)`, `loadState(data|null)`（null = 最初から。標的を `npcs.spawnTarget` で出し直す）, `saveState()`,
`respawnPoint() → {x,y,z,yaw}`, `fastTravel(towerId)`, `buyUpgrade(kind) → bool`, `buyItem('knives'|'medicine') → bool`,
`applyUpgrades()`（player.maxHp / knivesMax, combat.damageMul を書く）, `track(id)`, `isRevealed(x, z) → bool`。

### CameraRig — `src/view/camera.js`

`mode`（'third'|'first'）, `yaw`, `pitch`（正 = 上を見る）, `distance`。`update(realDt)` — 入力の look と view ボタン、
状態ごとの振る舞い（title は街の上をゆっくり巡る、playing は追従、dead はゆっくり回る）、壁へのめり込み防止、
疾走の FOV、一人称の揺れと **手元モデル**（腕と剣、行動に合わせて動く）。
`setMode(m)`, `toggleMode()`, `snapBehindPlayer()`, `shake(strength, seconds)`, `punch(fovDelta)`,
`project(vec3, out) → {x, y, visible}`（画面座標 px）。一人称ではプレイヤーの頭を隠す。

### Hud — `src/view/hud.js`

`init()` で HUD・タイトル・一時停止・設定・遊び方・地図・店・死亡・終幕の画面を作る。`update(realDt)`。
`toast(text, kind)`, `banner(title, sub)`, `flash(color)`, `openShop(shop)`, `openMap()`, `closeMap()`。
状態（`state:changed`）に合わせて画面を出し分け、`input.setButton*` で文脈ボタン（暗殺・カウンター・調べる）を更新する。

### Fx — `src/view/fx.js`

`computeTimeScale(realDt) → number`, `hitStop(seconds)`, `slowMo(scale, seconds)`,
`burst(kind, pos, opts)`（`dust sparks blood splash coins sync smoke leaves`）, `startTrail(rig, seconds, color)`,
`ring(pos, color, opts)`, `update(dt)`。気配察知中は画面の色を沈ませる。

## 性能の目安（スマホ）

- 描画 300 回以下、三角形 40 万以下、テクスチャはキャンバスで 512px 程度まで
- 毎フレームの `new THREE.Vector3()` などは避け、使い回す
- NPC の判断は 8 回/秒程度に間引き、遠い NPC のアニメは間引く・遠すぎるものは隠す
- 影は品質 medium 以上で、プレイヤーの周りだけ

## テスト

```
cd games/kagewatari
npm install            # テスト用に three を入れる（ゲーム本体は CDN から読む）
npm test               # tests/*.test.mjs をすべて
node tests/run.mjs parkour   # 名前に parkour を含むものだけ
npm run serve          # http://localhost:8642/ で遊ぶ（three はローカルから配る）
```

テストは Playwright（Chromium）で `?test=1` を開き、`__game.debug` で入力を注入してフレームを進め、状態を確かめる。
スクリーンショットは `tests/out/` に出る（git には入れない）。
