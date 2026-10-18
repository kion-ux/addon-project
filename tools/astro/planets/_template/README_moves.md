# 惑星の技の書き方（planets/&lt;key&gt;.js 担当者向け）

アストロ・ナノギアの 9 形態は、それぞれ `packs/astro_BP/scripts/planets/<key>.js` の 1 ファイルに
**惑星技・機動技・空中技・必殺・三段目の追撃・変身の締め・パッシブ** を書く。
変身・解除・HUD・機動・コンボ・ゲージ・保存はエンジン側（engine.js ほか）が全部やるので、
担当者は「技の中身（演出と当たり）」だけを書けばよい。

* 見本（リファレンス実装）: `planets/earth.js`（地球 ガイア）
* 雛形: `planets/_template.js`（コメント付き。コピーして使う）
* 今の他の 8 形態は `engine.genericMoves(key)`（惑星の色で描く汎用の技）で仮に動いている（`TODO` の印）
* 数値・名前・説明の出所: `tools/astro/astro_data.py`（→ `scripts/data.js` の `PLANETS[key]`）
* 名前の約束: `tools/astro/DESIGN.md`（パーティクル §4.7・全身モーション §4.6・効果音 §4.9）、
  パーティクルの変数と見た目: `tools/astro/PARTICLES.md`、HUD のグリフ: `tools/astro/UI.md`

---

## 1. 手順

1. `planets/_template.js` を `planets/<key>.js` に上書きコピーし、`const KEY = "template"` を惑星キーに変える。
2. `PLANETS[KEY].moves`（data.js）の名前・説明・`cd`（再使用 tick）・`cost`（星力）を読んで、説明どおりの技を書く。
3. 全身モーションは `planets/<key>/body.py`（アニメ担当）が `animation.astro.p.<key>.<名前>` を作る。
   スクリプトからは `body(p, "<key>.<名前>")`。まだ無い名前は **何もしない**（エラーにならない）ので先に書いてよい。
4. `python3 tools/astro/test_astro.py --planet <key>` で確かめる（3 章）。
5. 他のファイル（engine.js など）は触らない。足りない関数があればまとめ役に頼む。

```js
import { register, ultOpen, projectile } from "../engine.js";
import { P, sound, body } from "../fx.js";
import { hit } from "../combat.js";

register("mars", {
  skill(ctx) { /* … */ return 20; },   // 返り値 = 技の最中（tick）。その間は他の技が出ない
  dash(ctx) { /* … */ return 14; },
  air(ctx) { /* … */ return 26; },
  ult(ctx) { ultOpen(ctx, 70, 14); /* … */ return 60; },
  combo3(ctx, target) { /* … */ return 10; },
  burst(ctx) { /* … */ return 12; },
  passive: { tick(p, st) {}, onHit(p, target, dmg, ctx) {}, onHurt(p, attacker, dmg) {}, onKill(p, victim) {}, dmgMul(p) { return 1; } },
  meta: { noDamage: [] },              // ダメージを与えない技（例 ["dash"]）を書くとテストがダメージを求めない
});
```

どの技がいつ出るか（engine.chooseKind）:

| 入力 | kind |
|---|---|
| スニーク＋右クリック（超新星ゲージ 100%） | `ult`（ゲージ未満なら ナノ・バリア。バリアはエンジンが出す） |
| 空中で右クリック | `air` |
| ダッシュ中に右クリック | `dash` |
| 右クリック | `skill` |
| 通常攻撃の 3 段目 | `combo3(ctx, target)`（再使用・星力なし。ダメージ本体はバニラの攻撃） |
| 変身の 50 tick 目（TRANSFORM.planet_burst） | `burst(ctx)`（まだ硬直中。ダメージは与えない） |

再使用時間（`cd × 同調率の短縮`）・星力の消費・必殺のゲージ 0・「技の最中」ロックはエンジンがやる。

---

## 2. ctx（技の文脈）

| メンバー | 中身 |
|---|---|
| `p` | プレイヤー |
| `key` / `planet` | 惑星キー / `PLANETS[key]`（名前・色・技・数値） |
| `kind` | `"skill"` `"dash"` `"air"` `"ult"` `"combo3"` `"burst"` |
| `dim` | 技を始めた次元（パーティクル・音はここへ） |
| `c` `light` `deep` `accent` `plate` `plate2` | 発光色・芯の色・影の色・差し色・主装甲・副装甲（[r,g,b] 0..1） |
| `hot` | 白寄りの発光色（`white(c, 0.45)`） |
| `tc` | テキスト色コード（`§a` など） |
| `f` `r` `v` | 開始時の水平前方・右・視線 |
| `start` | 開始時の足元 |
| `level` | 同調率 Lv（1..5） |
| `at(t, fn)` | t tick 後に fn。**死亡・退出・解除・次元移動で止まる**。`t <= 0` なら今すぐ |
| `every(t0, n, step, fn(i))` | t0 から step tick おきに n 回 |
| `once(e, max = 1, tag = "")` | この技で同じ相手に当てる回数の制限（tag ごとに別に数える）。当ててよければ true |
| `alive()` | 技を続けてよいか（自分で長い処理を回す時に） |
| `loc()` `chest()` `head()` | 今の足元・胸（+1.0）・頭（+1.62） |
| `front(d = 1.6, y = 1.0)` | **開始時の向き**で前方 d m・高さ y の点（今の位置から） |
| `local(fwd, right = 0, up = 0)` | 今の足元から開始時の向きで前・右・上へずらした点 |
| `liveDir()` / `liveView()` | **今の**水平前方 / 視線（溜めの後に振り向きを追う時） |
| `dmg(base)` | 同調率・惑星・パッシブの補正を掛けた値（**hit() は自動で掛けるので表示・計算用**） |
| `hit(e, base, o)` | `combat.hit(ctx, e, base, o)` の短縮 |
| `foes(radius, at = chest())` | 周りの攻撃してよい相手（**範囲技用**。PvP のプレイヤーと範囲の中の生き物に当たる） |
| `hostiles(radius, at = chest())` | 周りの**敵対的な相手だけ**（標的・落下点・軌道の中心を**選ぶ**時はこれ） |
| `cone(range, deg, from?, dir?)` | 扇形（既定: 胸から今の視線） |
| `nearest(radius, deg = 180, los = true)` | 一番近い**敵対的な相手**（deg で視線の扇に、los で頭から見通せる相手に絞る） |
| `aimed(maxD = 16)` | 視線の先の相手（意図して狙った相手。敵対的でなくてもよい。ブロックの向こうは無し） |
| `pick(radius, deg = 40)` | `aimed` → `nearest` の順に一人選ぶ（単体を狙う技の標準） |
| `aim(maxD = 20)` | 狙っている地点（見ている敵の足元 → 見ているブロックの上 → 前方の地面） |
| `ground(loc)` | loc の真下の地面に合わせた点 |
| `extra` | 呼び出し側の追加情報（combo3 なら `{ target }`） |

---

## 3. 関数の早見表

### engine.js（動き・飛び道具・範囲）

| 関数 | 説明 |
|---|---|
| `register(key, impl)` | 登録（ファイルの最後で 1 回） |
| `lunge(ctx, dir, power, up = 0.12)` | 突進（power 1.0〜1.8 = 1 tick の水平速度の目安）。着地まで落下ダメージ無効 |
| `hover(ctx, ticks, lift = 0.35)` | 宙で止まる（低速落下）。空中技の溜めに |
| `plunge(ctx, onLand(loc), maxT = 34, speed = 2.6)` | 真下へ叩きつけ、着地の瞬間に onLand（着地しなければ maxT で） |
| `warp(ctx, loc, facing?)` | 瞬間移動。ブロックの中には入らない（上・手前を探す。無理なら false） |
| `behind(target, d = 1.4)` / `safeAhead(dim, from, dir, maxD)` / `standable(dim, loc)` | 背後の位置 / 壁の手前 / 立てるか |
| `dashHits(ctx, ticks, radius, base, o)` | 突進中、毎 tick 前方の敵に 1 回ずつ当てる |
| `ultOpen(ctx, ticks = 80, radius = 12)` | **必殺の開幕（必ず最初に）**: カットイン・フラッシュ・無敵・時間停止・紋章の陣 |
| `projectile(ctx, from, dir, o)` | スクリプト弾（下の表） |
| `zone(ctx, loc, o)` | 設置範囲（下の表） |
| `meteor(ctx, target, o)` | 予告の陣 → 落下 → 爆発（返り値 = 着弾の tick）。`delay` `fall` `height` `radius` `damage` `color` `size` `particle` `onImpact` |
| `chain(ctx, first, o)` | 連鎖する雷（`max` `range` `damage` `falloff` `delay` `from` `color` `sound` `onHit(e, i)`） |
| `aimPoint(p, maxD)` / `genericMoves(key)` | ctx.aim の中身 / 汎用の技一式（仮の間） |

`projectile(ctx, from, dir, o)` の o:

| キー | 既定 | 意味 |
|---|---|---|
| `speed` | 1.2 | 1 tick に進む m（0.85 ≒ 17 m/s） |
| `range` / `life` | 30 / 100 | 射程 m / 最長 tick |
| `radius` | 0.6 | 当たりの半径 |
| `pierce` | 0 | 貫通できる数（`Infinity` で全部） |
| `gravity` | 0 | 毎 tick の落下 |
| `blocks` | true | false でブロックを抜ける |
| `homing` / `turn` | — / 0.35 | 追尾の相手（`true` で前方の一番近い相手）/ 曲がる強さ |
| `returns` / `returnAt` / `rehit` | — | ブーメラン（射程の端か returnAt tick で折り返す。戻りは同じ相手にもう一度当たる） |
| `hitEvery` | — | 貫通弾が同じ相手に何 tick おきに当たり直すか（多段） |
| `damage` / `hitOpts` | — | 当たった相手に自動で `hit(ctx, e, damage, hitOpts)` |
| `trail(dim, pos, prev, age, shot)` | — | 毎 tick の見た目（`shot.pos` を書き換えれば地形に沿わせられる） |
| `onHit(e, pos, shot)` / `onEnd(pos, reason, shot)` | — | 当たった / 終わった（reason: block / entity / range / life / owner / returned / stopped） |

`zone(ctx, loc, o)` の o: `radius`(3) `ticks`(60) `every`(10) `delay` `damage` `hit` `effects:[[id, ticks, amp]]` `pull` `lift`
`height`(2.5) `follow`（付いて動く相手）`color` `particle` `visual(dim, center, age, z)` `visualEvery`(2) `onPulse(enemies, z)` `onEnd(z)`。
返り値の `z.stop()` で消せる。`z.center` `z.radius` は書き換えてよい（広がる嵐など）。

### fx.js（演出）

| 関数 | 説明 |
|---|---|
| `P(dim, id, loc, o)` | パーティクル 1 つ（id は `"glow"` など astro: を除く）。o: `color size life rot count speed spread dir var height spin rate grav len` |
| `line(dim, id, a, b, step, o)` / `ring(dim, id, c, r, n, o, y)` | 線・水平の輪。id が glow/trail/star/nano/hex/dot なら `line_n`/`ring_n` の 1 回で描く |
| `arc(dim, center, fwd, r, a0, a1, tilt, color, o)` | 3D の斬撃の弧（返り値は弧の点） |
| `burst(dim, loc, color, power)` / `shock(dim, ground, color, radius, o)` | 当たりの瞬間 / 地を走る衝撃波（半径 m で渡す） |
| `beam(dim, a, b, color, o)` / `swarm(dim, from, to, color, o)` | 光線（両端の光つき）/ ナノマシンの奔流 |
| `emblem(dim, loc, key, o)` / `slash(dim, loc, color, rot, size, kind, life)` / `afterimage(dim, feet, color, life)` | 紋章の陣 / 斬撃 / 残像（足元を渡す） |
| `sound(dim, "astro.<名前>", loc, pitch, volume)` | 効果音 |
| `shake(dim, loc, radius, intensity, sec)` / `flash(dim, loc, radius, color, hold, out)` | 画面揺れ / フラッシュ（合計 0.5 秒以上に自動でそろう） |
| `body(p, name, controller = "astro.act")` / `bodyStop(p, controller)` | 全身モーション（`"<key>.<名前>"` か共通の名前。共通の名前は形態の版があればそちら） |
| `white(c, t)` `mix(a, b, t)` `shade(c, k)` | 色の計算 |
| `status(p, text, ticks)` / `announce(p, text, ticks)` | HUD の 2 行目を差し替え（溜め中など）/ アクションバーを一時的に乗っ取る |
| `glyph(path, fallback)` | glyphs.js の G をたどる（`glyph(["emblem", key], "♁")`） |
| `fxScale()` / `budgetLeft()` | 演出の量の倍率（0.5/1/1.5）/ この tick の残り予算 |

### combat.js（当たり）

`hit(src, target, base, o)` — src は ctx（推奨）かプレイヤー。**base は素のダメージ**で、同調率（Lv ごと +6%）・
惑星の補正（ナノウェポンの攻撃力 8 を基準に ±3%/点）・パッシブの `dmgMul` は中で掛かる（`o.raw` で掛けない）。
連続ヒットは無敵時間で消えないように「ダメージバンク」に貯めて後で通す。

| o のキー | 意味 |
|---|---|
| `kb` / `up` / `dir` | 水平ノックバック / 上向き / 向き（既定: 自分 → 相手） |
| `pull` | {x,y,z} へ引き寄せる（kb の代わり） |
| `color` / `power` / `quiet` / `sound` | 当たりの色 / 演出の規模（1 普通・2 大技）/ 演出なし / 当たりの音（既定 astro.hit、power ≥ 1.6 で astro.hit_heavy） |
| `crit` | true か確率（1.5 倍・赤い数字・astro.crit） |
| `nova` / `xp` | ゲージ・同調率 XP の増加（既定 技 2・通常 3 / 2）。**1 つの技で稼げるのは nova 14・xp 12 まで** |

範囲: `enemiesNear(ctx, loc, r)` `enemiesInCone(ctx, origin, dir, range, deg)` `enemiesOnLine(ctx, a, b, width)`
`nearestEnemy(ctx, loc, r, dir?, deg?)`。**自動で狙う技（パッシブ・追尾）と「標的を選ぶ」処理は `nearestHostile(src, loc, r, dir?, deg?, {los})` /
`hostilesNear`（`ctx.hostiles` / `ctx.nearest` / `ctx.pick`）**: 侵略者と monster の家族だけ。中立の mob（ゾンビピグリン・
エンダーマン・クモ・ピグリン）はそのプレイヤーと戦った直後だけ。村人・動物・ゴーレム・プレイヤーは選ばない。
`isTarget` は自分・自分のペット・自分の馬（tamemount）・乗っている相手・乗り手・自分の飛び道具・クリエイティブを除く。
`chain()` の飛び移り先も既定で敵対的な相手だけ（`filter` で変えられる）。
状態: `freeze(e, ticks, strong)` `pull(e, to, strength)` `push(e, from, kb, up)` `launch(e, up, kb, dir)`
`alliesNear(p, loc, r)`（**自分と自分のペット・馬だけ**。他のプレイヤーは含めない — PvP で当てている相手を癒やさない）`heal(e, n)`。
瞬間移動: `warp(ctx, loc, facing, { ground: true })` で足元に地面の無い所（虚空・崖の外）へは跳ばない。

### util.js（計算）

`add sub scale dot len dist hdist up(a, y) norm cross lerp3 yawRotate(dir, deg) yawDeg(dir) rightOf(f) basis(f) dirTo(from, to)
chest(e) rand pick clamp effect(e, id, ticks, amp) groundY(dim, loc) onGround(dim, loc) blocked(dim, loc) valid(e)`。

### パッシブのフック

| フック | いつ |
|---|---|
| `tick(p, st)` | 5 tick ごと（`passives.PASSIVE_EVERY`）。`st` は作業用（`st.n` 回数・`st.t` tick。変身のたびに空）。間隔は `st.cd` などで自分で数える |
| `onHit(p, target, dmg, ctx)` | 自分の攻撃が当たった（通常攻撃なら ctx は null・dmg はナノウェポンの攻撃力）。中で hit() しても onHit は二重に呼ばれない |
| `onHurt(p, attacker, dmg)` | 攻撃を受けた（バリア・ジャスト回避で防いだ時は呼ばれない） |
| `onKill(p, victim)` | 倒した（星力 +5・XP +12 はエンジンが足す） |
| `dmgMul(p)` | 与ダメージの倍率（海王星の「水中・雨で上がる」など） |

`passive.effects`（data.js）の効果はエンジンが毎秒掛け直すので書かなくてよい。

---

## 4. 演出と時間のこつ

* **3 拍**: 溜め（予兆・吸い込む光・低い音）→ 放つ（白い芯の閃光 + 惑星色 + 飛び散る粒 + 地面の輪 + 2 つ重ねた音 + 揺れ）→ 余韻（煙・火の粉・輪が広がる）。
* 予兆は 6〜10 tick、大技の予告（meteor の `warning`）は 12〜20 tick。必殺は 50〜80 tick。技の返り値は「最後の当たり」の少し後。
* 溜めの後は `ctx.liveDir()` で今の向きに撃つ（溜めの間に振り向ける）。
* 色は惑星の `c`（主）に `hot`（芯）と `accent`（差し色）を少し。地球なら海の青・森の緑・オーロラの紫を自分で定義している。
* 効果音の中の「当たりの瞬間」に合わせる（gen_astro_sounds の実測）:
  `transform_burst` は 0.11 秒後 / `supernova` は 1.6 秒しぼんで **1.66 秒後に爆発**（33 tick 前に鳴らす）/
  `time_stop` の止まる音は 1.25 秒後 / `meteor` の着弾は **1.15 秒後**（23 tick 前）/ `beam_charge`（1.0 秒）の直後に `beam_fire` /
  `hover` は 0.4 秒ごと・`drone_hum` は 0.9 秒ごとに鳴らし直すと途切れない。pitch を上げると短くなる。
* パーティクルの大きさは PARTICLES.md の「目安」を守る。特に:
  `emblem` は直径 ≈ 3.0 × size m、`circle`/`hex_circle`/`warning` は 2.4 × size、`shock_flat` は 3.0 × size、
  `slash` 2.2・`slash_flat` 3.2・`slash_big` 4.0 × size、`lens` は 4 × size（大きくしすぎない）。
  `pillar`・`afterimage`・`scan` は **足元がエミッタ**（地面の高さで出す）。
  `aurora` は 1 回で半径 `spread` の輪に `count` 本の帯が並ぶ（ばらばらに何十個も出さない）。
  `wave` は自分で `dir` へ `speed` m/s で進む。`beam`・`bolt`・`thrust` は `dir` の向きへ `len` m。
  `nano_stream`・`nano`・`line_n` の `dir` は向きではなく **終点までのずれ（m）**。

## 5. 予算のルール

* `spawnParticle` は 1 回ごとに全員へ 1 パケット。fx.js は 1 tick の呼び出しを「1 + count/8」で数え、
  **約 110（設定の「演出の量」で ×0.5〜×1.5）を超えた分は捨てる**。大事な層（当たりの光）を先に、飾りを後に。
* 1 tick に 40 回を超えそうなら `ctx.every` で数 tick に散らす。輪や線は `ring()` / `line()`（1 回で描ける）。
* 毎 tick の `enemiesNear` は同じ場所・同じ半径なら 1 tick の中でまとめて 1 回になる。範囲の中心を毎回少しずつずらさない。
* 演出の量が「少ない」の人がいれば `fxScale()` が 0.5 になる。重い飾りは `if (fxScale() >= 1)` で省ける。
* エンティティを作らない（投射物はスクリプト弾、範囲は zone）。`system.runTimeout` を直接使わない（ctx.at を使う）。

## 6. 全身モーション

* 技・コンボ: コントローラ `astro.act`（既定）。機動: `astro.move`。変身・ホバー: `astro.pose`。
* 共通の名前（`cast` `throw` `slam` `thrust` `spin` `ult_rise` …）は、その形態の版（`mars.cast`）があればそちらが再生される。
* コンボは `<key>.combo1` `<key>.combo2` `<key>.combo3` があれば自動で再生される（無ければバニラの振り）。
  combo.js は斬撃・当たりの音をモーションの当たりのキー（combo.js の `STRIKE`。body.py の cN_hit の時刻）まで遅らせ、
  `combo3` もその時刻に呼ぶ。`combo3` の中で自分でモーションの当たりまで待つ（`ctx.at(7, …)` など）なら
  `register` に `meta: { combo3Synced: true }` を書く（すぐに呼ばれる）。body.py の当たりの時刻を変えたら STRIKE も直す。
* 連打は 8 tick に 1 回しか数えない（段・ゲージが進まない）。三段目の後は `combo3` の返り値の間、次の段を始めない。
* 長さは `anim_meta.js`（`bodyTicks("mars.slam")` で tick）。技の時間割をモーションに合わせるのに使える。

## 7. テスト

```
python3 tools/astro/test_astro.py --planet mars     # 火星だけ（共通の検査も走る）
python3 tools/astro/test_astro.py                    # 全形態 + 雛形の読み込み
```

1 形態について: 変身の時間割（スーツ・ウェポン・防具の退避・カメラと入力ロックが戻る）、4 技（3 体のゾンビに対して
惑星技・必殺は必ずダメージ。機動技・空中技も `meta.noDamage` に無ければダメージ）、星力の消費と再使用、三段コンボ
（3 段目で combo3）、バリア、二段ジャンプ・ホバー・ブースト・回避・ジャスト回避、スニーク静止の解除、星力切れ、
死亡、再参加 を実際に走らせる。**`[astro]` の警告（技の中の例外）が 1 つでも出たら失敗**。
最後に、使ったパーティクル・効果音・全身モーション・アイテム・エンティティがパックに実在するかを調べる
（まだ生成されていないリソースは SKIPPED）。

失敗の読み方: `mars.skill: no damage dealt` = 惑星技が誰にも当たっていない（向き・半径・高さを確かめる。敵は前方 2〜3m）。
`mars.air: warnings: [astro] mars.air@12: TypeError …` = 空中技の 12 tick 目の処理で例外。

## 8. よくある落とし穴

* `hit()` に `ctx.dmg(…)` を渡すと補正が二重になる（素の値を渡す）。
* `ctx.front()` は**開始時の向き**。突進中に前を追うなら `ctx.local(…)` か `ctx.liveDir()`。
* 多段の当たりで `ctx.once` を忘れると 1 体に何十回も当たる（バンクで全部通る）。段ごとに tag を変える。
* 位置は毎回 `ctx.loc()` で取り直す（`ctx.start` は開始時のまま）。地面に置くものは `ctx.ground()`。
* 自動で敵を探すパッシブ・標的を選ぶ処理は `nearestHostile` / `ctx.hostiles` / `ctx.pick`（村人・動物・中立の mob を撃たない）。
  `ctx.foes(...)[0]` や「一番体力の多い相手」を `foes` から選ぶと、村のゴーレムや牛に大技が落ちる。
* 標的の周りへ跳ぶ技は、標的を見通せるか（`clearLine`）と行き先の足元（`warp(..., { ground: true })`）を確かめる。
* `ult` は必ず `ultOpen` から。`burst` ではダメージを与えない（変身の硬直中）。
* 長い技（60 tick 超）でも返り値は 200 まで。ゾーンや弾は技の後も残ってよい（解除・死亡で消える）。
