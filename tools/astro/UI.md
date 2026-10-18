# アストロ・ナノギア — HUD グリフと UI 素材

`tools/astro/gen_astro_ui.py` が書き出す（この文書も自動生成。直すときは生成スクリプトの `write_ui_md` を直す）。
見本: `docs/astro/hud.png`（HUD・カットイン・ターミナルの見本）、`build_preview/astro/glyphs_EA.png` / `glyphs_EB.png`（全セルを 4 倍・2 倍にして番号を付けたもの。桃色の線 = 送り幅、緑の印 = 文字の高さ 4〜11 行）。

## 1. 統合版のグリフの規則（このアドオンで守っていること）

* `U+XXRC` → `RP/font/glyph_XX.png` の R 行 C 列（16×16 マス）。**EA = HUD（256×256、16 px セル）**、**EB = 大きな絵（512×512、32 px セル）**。E0/E1（バニラ）・E2/E3（他パックと衝突しやすい）・2E–9F と F9–FF（日本語・繁体字ロケールのページ）は使わない。
* 送り幅 = セルの不透明な列の範囲（空の列は詰められる）＋約 1 GUI px の隙間。負の字間は無い。幅を決めたいグリフは両端の列にかすかな画素（アルファ 20）を置いてある（下の表の「幅」）。
* 16 px セルはほぼ 16 GUI px（ASCII の約 2 倍の高さの箱）で描かれる。絵は文字の高さ（4〜11 行）に置き、技アイコンと紋章でも 3〜12 行に収めた（2 行のアクションバーで上下の行に被らない）。
* 512 のページ（EB）は 16 px と同じ大きさで細かく描かれる（たぶん）か、2 倍の大きさ（不確か）。どちらでも崩れないように EB はタイトル・サブタイトル専用にしている（HUD の行には入れない）。
* **§ の色はグリフを染めない** → 惑星ごとに色違いのグリフを用意した。§ の色はグリフの後ろの文字にだけ効く。
* **グリフの並びの前に `§r`** を置く（太字・斜体が残っていると崩れる）。**`§l`（太字）をグリフの隣に置かない**（太字はグリフをずらして二重に描く）。
* アクションバーは表示が数秒で消えるので **40 tick 以内ごとに送り直す**（HUD は 4 tick ごとなので問題ない）。各行は中央揃え。行の間は約 10 GUI px。空白は 4 GUI px。
* グリフはアクションバー・タイトル／サブタイトル・チャット・アイテム名／説明・server-ui のフォーム・エンティティの nameTag で描かれる。

## 2. `glyphs.js` の形

```js
import { G, bar, energyBar, novaBar, progressBar, xpBar, pips, moveIcon, textWidth, WIDTH } from "./glyphs.js";
```

```
G.emblem:    {<key>: 文字}                       （惑星 9 つ: mercury, venus, earth, mars, jupiter, saturn, uranus, neptune, sol）
G.emblemBig: {<key>: 文字}
G.energy:    {<key>: {full, half, empty, capL, capR}, low: {full, half, empty, capL, capR}}
G.energyLow: {full, half, empty, capL, capR}
G.nova:      {full, empty, flow, capL, capR}
G.move:      {<key>: {<kind>: {ready, wait}}}   kind = skill, dash, air, ult
G.icon:      {energy, nova, revert, overheat, barrier, sync, check, lock, warn, pipOn, pipOff, sep, arrow}
G.iconBig:   {energy, nova, revert, overheat, barrier, sync, check, lock, warn}
G.sync:      {full, empty, half, capL, capR}
G.progress:  {full, empty, half, capL, capR}
G.xp:        {full, empty, capL, capR}
G.banner:    {wingL, wingR, divider, lineL, lineR}
```

* `G.energy[key].capL/capR` は全惑星で同じ金属の端。`G.energy.low` = `G.energyLow`（星力 20% 未満の赤いセルと赤い LED の端）。
* `G.sync` = `G.progress`（同じグリフ）= 変身・解除の進み具合（CORE SYNC n%）の白いバー（half あり）。`G.xp` = 同調率の XP の細い紫のバー。
* `G.icon.sep` は斜めの区切り（│ の代わり）、`G.icon.arrow` はメニュー用の小さな ▶。
* `G.banner.wingL/wingR`（翼）・`divider`（中央にひし形の線）・`lineL/lineR`（文字を挟む線）と `G.emblemBig`・`G.iconBig` は EB（タイトル用）。

関数:

| 関数 | 中身 |
|---|---|
| `bar(set, frac, cells, caps = true)` | `capL + セル×cells + capR`。`set.half` があれば半セル単位。0 < frac なら最低半セル、frac < 1 なら最後のセルは空ける |
| `energyBar(key, frac, cells = 16, tick)` | 星力。frac < 0.2 で `G.energyLow`（赤）と惑星色が 8 tick ごとに点滅 |
| `novaBar(frac, cells = 10, tick)` | 超新星。100% で白熱のセル 3 つが流れる（4 tick で 1 セル） |
| `progressBar(frac, cells = 20)` / `xpBar(frac, cells = 10)` | 進捗（G.progress = G.sync）・同調率の XP（G.xp） |
| `pips(n, max = 5)` | 同調率 Lv の粒 ◆◆◆◇◇ |
| `moveIcon(key, kind, ready)` | 技アイコン（ready = 明るい枠、false = 灰色に惑星色の芯） |
| `textWidth(str)` | GUI px の幅の目安（グリフは表の幅＋1、ASCII 約 6、日本語 9、空白 4） |

## 3. HUD の組み方（アクションバー 2 行）

```js
const pl = PLANETS[key];                       // data.js
const t = system.currentTick;
const line1 = `§r${G.emblem[key]} ${pl.tc}${pl.form_ja} §fLv${lv} ${G.icon.sep} ` +
  `${G.icon.energy}${energyBar(key, st.energy / maxE, 16, t)} §f${Math.floor(st.energy)} ${G.icon.sep} ` +
  `${G.icon.nova}${novaBar(st.nova / 100, 10, t)} ${st.nova >= 100 ? "§e" : "§7"}${Math.floor(st.nova)}%`;

// 技: アイコン + 再使用の残り秒 / ✔ / READY（間は空白 2 つ）
const cell = (kind) => {
  const left = cdLeft(kind);                   // tick
  const ok = left <= 0 && (kind !== "ult" || st.nova >= 100);
  const tail = left > 0 ? `§7${(left / 20).toFixed(1)}s` : kind === "ult" ? (ok ? "§6READY" : `§7${Math.floor(st.nova)}%`) : `${G.icon.check}`;
  return `${moveIcon(key, kind, ok)} ${tail}`;
};
const line2 = `§r${cell("skill")}  ${cell("dash")}  ${cell("air")}  ${cell("ult")}`;
p.onScreenDisplay.setActionBar(`${line1}\n${line2}`);
```

2 行目の差し替え（優先順に 1 つ）:

| 状態 | 2 行目 |
|---|---|
| 解除の長押し中 | `` `§r${G.icon.revert} §cREVERT ${progressBar(hold / 40)} §f${pct}%` `` |
| オーバーヒート中 | `` `§r${G.icon.overheat} §cOVERHEAT §f${sec}s ${G.icon.lock}` ``（変身していない時は 1 行目の代わりに） |
| ナノ・バリア中 | `` `§r${G.icon.barrier} §bNANO BARRIER ${bar(G.progress, left / 14, 10)}` `` |
| 溜め中 | `` `§r${G.icon.energy} §eCHARGE ${progressBar(c)} §f${pct}%` `` |
| 星力 20% 未満 | 1 行目の数字の後に `` ` ${G.icon.warn}` `` |

同調率の表示（ターミナルやチャット）: `` `${G.icon.sync} §dSYNC Lv${lv} ${pips(lv)} ${xpBar(xpFrac)}` ``。

幅の目安（見本の行を実測）: 1 行目 ≈ 330 GUI px、2 行目 ≈ 165 GUI px（地球・16 + 10 セル）。GUI の幅は 1080p・GUI 倍率 3 で約 640 px、スマホでは 400〜480 px 程度なので1 行目は 16 + 10 セルで収まる。狭い端末向けに設定で 12 + 8 セルへ減らせるようにしておくとよい。

## 4. タイトル・カットイン（EB）

```js
// 変身の進捗（TRANSFORM の各段で）
p.onScreenDisplay.setTitle(`§fCORE SYNC §b${pct}%`, { subtitle: `§r${progressBar(pct / 100, 20)}`,
  fadeInDuration: 0, stayDuration: 12, fadeOutDuration: 4 });
// 締め（planet_burst）: 翼＋大きな紋章、サブタイトルに形態名
p.onScreenDisplay.setTitle(`§r${G.banner.wingL}${G.emblemBig[key]}${G.banner.wingR}`, {
  subtitle: `§r${G.banner.lineL} ${pl.tc}${pl.form_ja} §7| ${pl.tc}${pl.form_en} §r${G.banner.lineR}`,
  fadeInDuration: 2, stayDuration: 30, fadeOutDuration: 10 });
// 必殺技のカットイン
p.onScreenDisplay.setTitle(`§r${G.iconBig.nova}`, { subtitle: `§r${G.banner.divider} §6${pl.moves.ult.ja} §r${G.banner.divider}`,
  fadeInDuration: 0, stayDuration: 24, fadeOutDuration: 6 });
// 警告（オーバーヒート）
p.onScreenDisplay.setTitle(`§r${G.iconBig.overheat}`, { subtitle: "§cOVERHEAT", stayDuration: 30 });
```

## 5. フォーム（server-ui）の素材

| パス | 大きさ | 用途 |
|---|---|---|
| `textures/ui/astro/emblem_<key>` | 128×128 | 惑星図鑑のボタン（機械の輪の枠に惑星。背景は透明） |
| `textures/ui/astro/{status,codex,revert,settings,guide,records,back}` | 64×64 | トップのボタン（状態・惑星図鑑・解除・設定・操作説明・記録・戻る） |
| `textures/items/astro/{nano_cell,core_frame,solar_fragment,terminal,void_signal}` | 64×64 | 素材・道具のアイコン |
| `textures/items/astro/suit_<key>` | 64×64 | スーツのアイコン（スーツのモデルがあれば兜と胸を描き、無ければ紋章付きの兜の絵） |

ボタン: `form.button(`${pl.tc}${pl.form_ja}\n§8${pl.ja}`, `textures/ui/astro/emblem_${key}`)`。ボタンの文字にもグリフを使える（例: `` `${G.emblem[key]} ${pl.form_ja}` ``、`` `${G.icon.lock} §8???` `` = 未入手）。

## 6. グリフの一覧

### glyph_EA（HUD、16 px セル）

| 番号 | G のキー | 幅 (GUI px) | 行 |
|---|---|---|---|
| U+EA00 | `G.energy.<key>.capL`（全惑星共通） | 4 | 3–12 |
| U+EA01 | `G.energy.<key>.capR`（全惑星共通） | 4 | 3–12 |
| U+EA02 | `G.nova.full` | 6 | 4–11 |
| U+EA03 | `G.nova.empty` | 6 | 4–11 |
| U+EA04 | `G.nova.flow` | 6 | 4–11 |
| U+EA05 | `G.nova.capL` | 4 | 3–12 |
| U+EA06 | `G.nova.capR` | 4 | 3–12 |
| U+EA07 | `G.progress.full` = `G.sync.full` | 4 | 5–10 |
| U+EA08 | `G.progress.empty` = `G.sync.empty` | 4 | 5–10 |
| U+EA09 | `G.progress.half` = `G.sync.half` | 4 | 5–10 |
| U+EA0A | `G.progress.capL` = `G.sync.capL` | 3 | 4–11 |
| U+EA0B | `G.progress.capR` = `G.sync.capR` | 3 | 4–11 |
| U+EA0C | `G.xp.full` | 3 | 6–9 |
| U+EA0D | `G.xp.empty` | 3 | 6–9 |
| U+EA0E | `G.xp.capL` | 2 | 5–10 |
| U+EA0F | `G.xp.capR` | 2 | 5–10 |
| U+EA10 | `G.emblem.mercury` | 16 | 3–12 |
| U+EA11 | `G.energy.mercury.full` | 5 | 4–11 |
| U+EA12 | `G.energy.mercury.half` | 5 | 4–11 |
| U+EA13 | `G.energy.mercury.empty` | 5 | 4–11 |
| U+EA14 | `G.move.mercury.skill.ready` | 16 | 3–12 |
| U+EA15 | `G.move.mercury.dash.ready` | 16 | 3–12 |
| U+EA16 | `G.move.mercury.air.ready` | 16 | 3–12 |
| U+EA17 | `G.move.mercury.ult.ready` | 16 | 3–12 |
| U+EA18 | `G.move.mercury.skill.wait` | 16 | 3–12 |
| U+EA19 | `G.move.mercury.dash.wait` | 16 | 3–12 |
| U+EA1A | `G.move.mercury.air.wait` | 16 | 3–12 |
| U+EA1B | `G.move.mercury.ult.wait` | 16 | 3–12 |
| U+EA20 | `G.emblem.venus` | 16 | 3–12 |
| U+EA21 | `G.energy.venus.full` | 5 | 4–11 |
| U+EA22 | `G.energy.venus.half` | 5 | 4–11 |
| U+EA23 | `G.energy.venus.empty` | 5 | 4–11 |
| U+EA24 | `G.move.venus.skill.ready` | 16 | 3–12 |
| U+EA25 | `G.move.venus.dash.ready` | 16 | 3–12 |
| U+EA26 | `G.move.venus.air.ready` | 16 | 3–12 |
| U+EA27 | `G.move.venus.ult.ready` | 16 | 3–12 |
| U+EA28 | `G.move.venus.skill.wait` | 16 | 3–12 |
| U+EA29 | `G.move.venus.dash.wait` | 16 | 3–12 |
| U+EA2A | `G.move.venus.air.wait` | 16 | 3–12 |
| U+EA2B | `G.move.venus.ult.wait` | 16 | 3–12 |
| U+EA30 | `G.emblem.earth` | 16 | 3–12 |
| U+EA31 | `G.energy.earth.full` | 5 | 4–11 |
| U+EA32 | `G.energy.earth.half` | 5 | 4–11 |
| U+EA33 | `G.energy.earth.empty` | 5 | 4–11 |
| U+EA34 | `G.move.earth.skill.ready` | 16 | 3–12 |
| U+EA35 | `G.move.earth.dash.ready` | 16 | 3–12 |
| U+EA36 | `G.move.earth.air.ready` | 16 | 3–12 |
| U+EA37 | `G.move.earth.ult.ready` | 16 | 3–12 |
| U+EA38 | `G.move.earth.skill.wait` | 16 | 3–12 |
| U+EA39 | `G.move.earth.dash.wait` | 16 | 3–12 |
| U+EA3A | `G.move.earth.air.wait` | 16 | 3–12 |
| U+EA3B | `G.move.earth.ult.wait` | 16 | 3–12 |
| U+EA40 | `G.emblem.mars` | 16 | 3–12 |
| U+EA41 | `G.energy.mars.full` | 5 | 4–11 |
| U+EA42 | `G.energy.mars.half` | 5 | 4–11 |
| U+EA43 | `G.energy.mars.empty` | 5 | 4–11 |
| U+EA44 | `G.move.mars.skill.ready` | 16 | 3–12 |
| U+EA45 | `G.move.mars.dash.ready` | 16 | 3–12 |
| U+EA46 | `G.move.mars.air.ready` | 16 | 3–12 |
| U+EA47 | `G.move.mars.ult.ready` | 16 | 3–12 |
| U+EA48 | `G.move.mars.skill.wait` | 16 | 3–12 |
| U+EA49 | `G.move.mars.dash.wait` | 16 | 3–12 |
| U+EA4A | `G.move.mars.air.wait` | 16 | 3–12 |
| U+EA4B | `G.move.mars.ult.wait` | 16 | 3–12 |
| U+EA50 | `G.emblem.jupiter` | 16 | 3–12 |
| U+EA51 | `G.energy.jupiter.full` | 5 | 4–11 |
| U+EA52 | `G.energy.jupiter.half` | 5 | 4–11 |
| U+EA53 | `G.energy.jupiter.empty` | 5 | 4–11 |
| U+EA54 | `G.move.jupiter.skill.ready` | 16 | 3–12 |
| U+EA55 | `G.move.jupiter.dash.ready` | 16 | 3–12 |
| U+EA56 | `G.move.jupiter.air.ready` | 16 | 3–12 |
| U+EA57 | `G.move.jupiter.ult.ready` | 16 | 3–12 |
| U+EA58 | `G.move.jupiter.skill.wait` | 16 | 3–12 |
| U+EA59 | `G.move.jupiter.dash.wait` | 16 | 3–12 |
| U+EA5A | `G.move.jupiter.air.wait` | 16 | 3–12 |
| U+EA5B | `G.move.jupiter.ult.wait` | 16 | 3–12 |
| U+EA60 | `G.emblem.saturn` | 16 | 3–12 |
| U+EA61 | `G.energy.saturn.full` | 5 | 4–11 |
| U+EA62 | `G.energy.saturn.half` | 5 | 4–11 |
| U+EA63 | `G.energy.saturn.empty` | 5 | 4–11 |
| U+EA64 | `G.move.saturn.skill.ready` | 16 | 3–12 |
| U+EA65 | `G.move.saturn.dash.ready` | 16 | 3–12 |
| U+EA66 | `G.move.saturn.air.ready` | 16 | 3–12 |
| U+EA67 | `G.move.saturn.ult.ready` | 16 | 3–12 |
| U+EA68 | `G.move.saturn.skill.wait` | 16 | 3–12 |
| U+EA69 | `G.move.saturn.dash.wait` | 16 | 3–12 |
| U+EA6A | `G.move.saturn.air.wait` | 16 | 3–12 |
| U+EA6B | `G.move.saturn.ult.wait` | 16 | 3–12 |
| U+EA70 | `G.emblem.uranus` | 16 | 3–12 |
| U+EA71 | `G.energy.uranus.full` | 5 | 4–11 |
| U+EA72 | `G.energy.uranus.half` | 5 | 4–11 |
| U+EA73 | `G.energy.uranus.empty` | 5 | 4–11 |
| U+EA74 | `G.move.uranus.skill.ready` | 16 | 3–12 |
| U+EA75 | `G.move.uranus.dash.ready` | 16 | 3–12 |
| U+EA76 | `G.move.uranus.air.ready` | 16 | 3–12 |
| U+EA77 | `G.move.uranus.ult.ready` | 16 | 3–12 |
| U+EA78 | `G.move.uranus.skill.wait` | 16 | 3–12 |
| U+EA79 | `G.move.uranus.dash.wait` | 16 | 3–12 |
| U+EA7A | `G.move.uranus.air.wait` | 16 | 3–12 |
| U+EA7B | `G.move.uranus.ult.wait` | 16 | 3–12 |
| U+EA80 | `G.emblem.neptune` | 16 | 3–12 |
| U+EA81 | `G.energy.neptune.full` | 5 | 4–11 |
| U+EA82 | `G.energy.neptune.half` | 5 | 4–11 |
| U+EA83 | `G.energy.neptune.empty` | 5 | 4–11 |
| U+EA84 | `G.move.neptune.skill.ready` | 16 | 3–12 |
| U+EA85 | `G.move.neptune.dash.ready` | 16 | 3–12 |
| U+EA86 | `G.move.neptune.air.ready` | 16 | 3–12 |
| U+EA87 | `G.move.neptune.ult.ready` | 16 | 3–12 |
| U+EA88 | `G.move.neptune.skill.wait` | 16 | 3–12 |
| U+EA89 | `G.move.neptune.dash.wait` | 16 | 3–12 |
| U+EA8A | `G.move.neptune.air.wait` | 16 | 3–12 |
| U+EA8B | `G.move.neptune.ult.wait` | 16 | 3–12 |
| U+EA90 | `G.emblem.sol` | 16 | 3–12 |
| U+EA91 | `G.energy.sol.full` | 5 | 4–11 |
| U+EA92 | `G.energy.sol.half` | 5 | 4–11 |
| U+EA93 | `G.energy.sol.empty` | 5 | 4–11 |
| U+EA94 | `G.move.sol.skill.ready` | 16 | 3–12 |
| U+EA95 | `G.move.sol.dash.ready` | 16 | 3–12 |
| U+EA96 | `G.move.sol.air.ready` | 16 | 3–12 |
| U+EA97 | `G.move.sol.ult.ready` | 16 | 3–12 |
| U+EA98 | `G.move.sol.skill.wait` | 16 | 3–12 |
| U+EA99 | `G.move.sol.dash.wait` | 16 | 3–12 |
| U+EA9A | `G.move.sol.air.wait` | 16 | 3–12 |
| U+EA9B | `G.move.sol.ult.wait` | 16 | 3–12 |
| U+EAA0 | `G.energyLow.full` | 5 | 4–11 |
| U+EAA1 | `G.energyLow.half` | 5 | 4–11 |
| U+EAA2 | `G.energyLow.empty` | 5 | 4–11 |
| U+EAA3 | `G.energyLow.capL` | 4 | 3–12 |
| U+EAA4 | `G.energyLow.capR` | 4 | 3–12 |
| U+EAB0 | `G.icon.energy` | 9 | 4–11 |
| U+EAB1 | `G.icon.nova` | 9 | 4–10 |
| U+EAB2 | `G.icon.revert` | 9 | 4–11 |
| U+EAB3 | `G.icon.overheat` | 9 | 4–11 |
| U+EAB4 | `G.icon.barrier` | 9 | 4–11 |
| U+EAB5 | `G.icon.sync` | 9 | 4–9 |
| U+EAB6 | `G.icon.check` | 9 | 4–10 |
| U+EAB7 | `G.icon.lock` | 9 | 4–11 |
| U+EAB8 | `G.icon.warn` | 9 | 4–11 |
| U+EAB9 | `G.icon.pipOn` | 5 | 5–9 |
| U+EABA | `G.icon.pipOff` | 5 | 5–9 |
| U+EABB | `G.icon.sep` | 3 | 3–12 |
| U+EABC | `G.icon.arrow` | 4 | 5–10 |

### glyph_EB（大きな絵、32 px セル）

| 番号 | G のキー | 幅 (GUI px) | 行 |
|---|---|---|---|
| U+EB00 | `G.emblemBig.mercury` | 11 | 5–26 |
| U+EB01 | `G.emblemBig.venus` | 11 | 5–26 |
| U+EB02 | `G.emblemBig.earth` | 11 | 5–26 |
| U+EB03 | `G.emblemBig.mars` | 11 | 5–26 |
| U+EB04 | `G.emblemBig.jupiter` | 11 | 5–26 |
| U+EB05 | `G.emblemBig.saturn` | 11 | 5–26 |
| U+EB06 | `G.emblemBig.uranus` | 11 | 5–26 |
| U+EB07 | `G.emblemBig.neptune` | 11 | 5–26 |
| U+EB08 | `G.emblemBig.sol` | 11 | 5–26 |
| U+EB10 | `G.banner.wingL` | 16 | 5–26 |
| U+EB11 | `G.banner.wingR` | 16 | 5–26 |
| U+EB12 | `G.banner.divider` | 16 | 10–21 |
| U+EB13 | `G.banner.lineL` | 16 | 13–18 |
| U+EB14 | `G.banner.lineR` | 16 | 13–18 |
| U+EB20 | `G.iconBig.energy` | 7 | 7–23 |
| U+EB21 | `G.iconBig.nova` | 10 | 7–24 |
| U+EB22 | `G.iconBig.revert` | 7 | 8–23 |
| U+EB23 | `G.iconBig.overheat` | 8 | 7–24 |
| U+EB24 | `G.iconBig.barrier` | 11 | 7–24 |
| U+EB25 | `G.iconBig.sync` | 8 | 9–22 |
| U+EB26 | `G.iconBig.check` | 10 | 8–22 |
| U+EB27 | `G.iconBig.lock` | 8 | 8–24 |
| U+EB28 | `G.iconBig.warn` | 10 | 7–23 |

配置: EA の行 0 = バーの部品、行 1〜9 = 惑星（order 順）で 列 0 紋章 / 1〜3 星力 満・半・空 / 4〜7 技（使える: skill, dash, air, ult）/ 8〜B 技（待ち）、行 A = 赤い星力、行 B = 状態アイコン。EB の行 0 = 大きな紋章、行 1 = 飾り、行 2 = 大きなアイコン。空いているセルは将来用。

## 7. 確かめていないこと

* 実機の行間（見本は 10 GUI px で描いた）と、アクションバーの背景の濃さ。グリフに文字の影が付くか。
* EB（512×512）の表示の大きさ（16 px 相当か 32 px 相当か）。
* かすかな画素（アルファ 20）が明るい空の上でうっすら見えるか（見えても 1 画素の暗い点）。
