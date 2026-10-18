# ナノウェポン・星核・全身モーションの作り方（planets/<key>/weapon.py・body.py）

このフォルダの `weapon.py` と `body.py` を `tools/astro/planets/<key>/` にコピーして書き始めてください
（`__init__.py` は空でよい。`<key>` は `astro_data.PLANETS` のキー）。
**お手本は `planets/earth/weapon.py`（蒼星剣 ガイア・セイバー／地球核 アース・コア）と `planets/earth/body.py`**。
自分の惑星のフォルダ以外（`astro_weapon.py` `astro_hold.py` `astro_animlib.py` などの共通部分）は編集しないでください。
足りない機能があればまとめ役に伝えてください。

---

## 1. 作業の流れ

```sh
python3 tools/astro/astro_weapon.py preview <key>          # 作って塗って描く → build_preview/astro/weapon_<key>.png
python3 tools/astro/astro_weapon.py preview <key> --swing   # 振り（三人称・一人称のコマ）も → weapon_<key>_swing.png
python3 tools/astro/gen_astro_weapons.py <key>             # pack へ書き出す（preview も中でこれを回す）
python3 tools/astro/gen_astro_anim.py                      # 全身モーションと anim_meta.js（全惑星分）
python3 tools/astro/gen_astro_anim.py --check              # 武器が体に入るコマの一覧（CLIP の行が出なければ OK）
python3 tools/astro/gen_astro_anim.py --preview <key>.combo1 [--view q34|left|back|"200,-14"] [--frames 8]
python3 tools/astro/gen_astro_anim.py --describe <key>.combo1   # キーごとに腕と刃先が実際にどちらを向いたか
python3 tools/astro/astro_hold.py [<kind> ...]             # 持ち方の確認（代役の形で、三人称 3 方向 + 一人称）
```

* `weapon_<key>.png` は上から: ウェポン 4 方向 / コア 4 方向 / 手に持った姿（三人称 2・コア・一人称 2）/ アイコン（64px の 4 倍と等倍）。
  **必ず絵を見て直す**（実機で確かめられないので、絵と検査が頼り）。
* `gen_astro_weapons.py` と `gen_astro_anim.py` は、共有ファイル（`animations/astro_weapons.animation.json`・
  `astro_player.animation.json`・コントローラ・`anim_meta.js`）を **planets/ にある全惑星から毎回作り直す**。
  自分の惑星だけを指定して回してよい（他の惑星は壊れない。塗りは変わった物だけ塗り直す）。
* 出力に `ERROR` が無いこと。`WARN`（キューブ数が予算外・form_ の外のキューブなど）も直す。

## 2. weapon.py に書くもの

| 名前 | 必須 | 内容 |
|---|---|---|
| `build_weapon(m, root)` | ○ | ナノウェポン。`root`（ボーン名 `origin`、握り = 原点）の下に部品ボーンを作ってキューブを置く |
| `build_core(m, root)` | ○ | 星核（手に持つコア）。`root` = 球の中心 |
| `WEAPON_STYLES` / `CORE_STYLES` | ○ | 塗り。辞書か `def WEAPON_STYLES(key): return weapon_styles(key, ...)`（§6） |
| `WEAPON_ANIMS` / `CORE_ANIMS` | | 回る部品・振り・形成の伸び方（§7） |
| `KIND` | | 持ち方の種類。省略で `astro_data.PLANETS[key]["weapon"]["kind"]` |
| `HOLD` / `CORE_HOLD` | | 持ち方の上書き `{"scale": 0.9, "anchor": (0,0,1), "tp": {...}, "fp": {...}}`（普通は書かない） |
| `ICON` | | アイコンの撮り方 `{"weapon": (yaw, pitch, 画面の回転), "core": (...)}` |
| `ICON_HIDE` | | アイコンで隠すボーン名のタプル |
| `UV_SCALE` / `CORE_UV_SCALE` | | テクスチャ密度の基準（既定 4 / 6。1024² / 512² に収まる最大まで自動で上げる） |

## 3. 武器空間と持ち方

* **武器空間**: 16 単位 = 1 ブロック。**握りの中心 = 原点、刃先（穂先・鎚頭・銃口）= -Z、刃の幅 = ±Y、刃の平の法線 = ±X**。
  片刃（サーベル・斧）は **-Y が刃**。コアは **球の中心 = 原点、+Y = 上**。
* **回転**はキューブもボーンも統合版の値そのまま（`R = Rz(-rz)·Ry(ry)·Rx(-rx)`）。
  rx 正 = 上端が -Z へ倒れる / ry 正 = 正面（-Z）が -X を向く / rz 正 = 上端が -X へ倒れる。
* **持ち方**は `astro_hold.py` が種類（kind）ごとに決める。三人称はバニラの持ち姿勢（右腕 -18°）のまま、
  握りの点がメカの篭手の拳に来るよう逆算する（篭手は素の拳より約 1 単位大きいので、握りを少し外・下へずらしてある）。
  一人称はカメラ空間で画面の右下に置く（照準を隠さない）。
* **篭手に隠れる所**: 握りの前後 `±2.6 / scale`（下の表）。**鍔はそれより -Z、柄頭はそれより +Z** に置く。
  柄頭の飾りを大きくすると、腰や前腕に刺さる（`--check` と `astro_hold.py` の絵で確かめる）。

| kind | 形 | scale（手に持った縮尺） | 全長の目安（武器空間） | 篭手に隠れる握り | 手首の角度* | 振り（三人称/一人称） |
|---|---|---|---|---|---|---|
| saber | サーベル（片刃・細身。刃は -Y） | 0.9 | 28 | ±2.9 | 48° | rx 38/70 |
| sword | 騎士剣（両刃・幅広） | 0.9 | 32 | ±2.9 | 46° | rx 34/66 |
| greatsword | 片手持ちの大剣 | 0.86 | 46 | ±3.0 | 66° | rx 26/52 |
| scepter | 王笏（長柄。頭が -Z） | 0.9 | 34 | ±2.9 | 110° | rx 22/40 |
| axe | 戦斧（柄の先に斧頭。刃は -Y） | 0.9 | 30 | ±2.9 | 96° | rx 40/64 |
| hammer | 鎚（柄の先に鎚頭） | 0.9 | 28 | ±2.9 | 96° | rx 40/60 |
| ring | 環刃（YZ 平面の大きな輪。握りは輪の内側の柄、輪の中心は -Z 側） | 0.8 | 22 | ±3.2 | 78° | rx 30/54 |
| crossbow | 弩（銃口 -Z、弓は ±X、握りは銃床の下 = 原点） | 0.85 | 22 | ±3.1 | 55° | 反動 rx -14/-18・z +1.5/+2.5 |
| trident | 三叉槍（穂先 -Z、握りは柄の中ほど） | 0.88 | 48 | ±3.0 | 118° | 突き z -4/-6 |
| core | 星核（中心 = 原点。拳の前に浮かせる） | 1.0 | 直径 5〜7 | — | — | — |

\* 手首の角度 = 前腕（肩→拳）と刃先の向きの角度。アタッチャブルは腕に固定なので、この角度は全てのモーションで変わらない
（剣は腕の延長に近く、斧・槍は腕と直角に近い）。全身モーションの `wield()` はこの角度を守って腕を解く（§9）。

## 4. ボーン

```
hold        手に bind（q.item_slot_to_bone_name(c.item_slot)）。持ち方（tp / fp）— 自動
 └ origin   握り = 原点（コアは球の中心）。振り・待機の揺れ — 自動。build_weapon の root
    ├ form_0_grip     形成の部品（番号の順に、持ち替えた瞬間 0 → 1.15 → 1.0 でポップ。同じ番号は同時）
    ├ form_1_guard      pivot は「生えてくる根元」（刃なら鍔の位置）。全体で約 0.6 秒
    ├ form_2_blade      WEAPON_ANIMS["form_axes"] = {"form_2_blade": "z"} で z 方向に「伸びる」
    │  └ fx_spin_xxx    回る部品（WEAPON_ANIMS で回す。書かなければ既定: ウェポンは Z 軸 120°/秒、コアは Y 軸 90°/秒）
    └ fx_glow_xxx       脈動する発光（既定で 1.0〜1.06 倍に脈打つ）
```

* `W.form(m, parent, 番号, "名前", pivot)` / `W.spin(m, parent, "名前", pivot, rotation=静止の傾き)` /
  `W.glow(...)` / `W.part(...)`（ただのボーン）で作る。**キューブは必ず form_ ボーン（かその子）に**
  （origin の直下に置くと形成アニメで消えない → WARN）。
* **プレイヤーと同じ名前のボーンを作らない**（root waist body head rightArm rightItem leftItem cape hat …）。
  アタッチャブルでもプレイヤーのそのボーンに付いて動いてしまう。`W.part` は例外を出す。
* `fx_*` ボーンは両面描画（薄い板・輪・炎はここへ）、その他は片面（閉じた箱の裏は描かない）。
* 回るボーンに静止の傾き（`rotation=(28, 0, 0)`）を付けると、アニメの回転はその上に足され、傾いたまま首を振る（ジャイロ）。

## 5. ジオメトリの補助（`import astro_weapon as W`）

| 関数 | 内容 |
|---|---|
| `W.cbox(bone, 中心, 大きさ, style, rotation=None, uv_scale=None)` | 中心と大きさの箱（回転は中心まわり） |
| `W.box(bone, 原点, 大きさ, style)` / `W.rbox(bone, 中心, 大きさ, style, rot=(..))` | 原点の箱 / 回転付きの箱 |
| `W.beam(bone, p0, p1, w, h, style, roll=0, extend=0)` | p0→p1 の角柱（幅 w は X、高さ h は Y 寄り） |
| `W.polyline(bone, 点列, 幅(列可), 高さ(列可), style)` | 点列に沿った角柱（先細り） |
| `W.octa(bone, 中心, 太さ, 長さ, style, axis="z")` | 八角柱（柄・柄頭・ノズル） |
| `W.chamfer(...)` / `W.bevel(bone, 中心, 大きさ, style, cut, axis, edge_style)` | 角を落とした箱（2 個 / 本当の 45°、6 個） |
| `W.ring(bone, 中心, 半径, 数, (接線長 0=自動, 厚み, 幅), style, axis, styles=[交互])` | 輪（axis="x" 側面 / "y" 水平 / "z" 正面） |
| `W.sphere(bone, 中心, 半径, style)` | 球（7 個）。惑星の球は style を `globe_style` に |
| `W.blade_point(bone, 底辺 z, 半幅, 頂点 z, 厚み, style, layer=0.8)` | YZ 平面の切先（三角形を角柱で埋める） |
| `W.fill_tri_yz(...)` `W.arc_points(...)` `W.lerp` `W.tri_fan(...)` | astro_common と同じ |

`uv_scale` は 1 単位あたりのテクセル（細かい部品ほど大きく。柄巻・宝玉・球は 8〜16、刃は 5〜6）。全体は自動で最大まで上がる。
**キューブ数の予算: ウェポン 80〜200、コア 30〜80**（地球: 131 / 67）。

## 6. 塗り

`astro_paint.weapon_styles(key, **上書き)` / `core_styles(key, **上書き)` が惑星の配色から一式を作る。
名前（style）: `blade` `blade_tint` `blade_flat`（段で作る切先・斧刃）`edge` `edge_hot`（発光の刃）`metal` `metal_tint`
`gold` `silver` `wrap`（柄巻）`gem` `energy` `void` `rune` `crystal` `dark` `plate` `plate_b` `plate2` `frame` `chrome`
`glow` `glow_soft` `glow_accent` `vent` `thruster` `core` `planet` `luna` …（一覧は astro_paint.py の冒頭）。

* **球に惑星の模様を貼る**: `globe=W.globe_style("<惑星名>", emit=36)`（`W.sphere` の 7 個の箱に継ぎ目なく。
  emit はアルファ: 低いほど光る、255 で光らない。`globe_style("luna", emit=255, halo=None)` で月）。
* 上書きの例: `edge={"glow": (88, 246, 204), "sat": 0.45}`、`blade={"kind": "chrome", "base": (184, 204, 236)}`。
* 発光は entity_emissive_alpha の規約（アルファ 0 = 抜き、255 = 普通、1〜40 ≒ 全発光）。

## 7. アタッチャブルのアニメ（WEAPON_ANIMS / CORE_ANIMS）

値は統合版のアニメのチャンネル（Molang 可）。使える変数: `q.anim_time`（秒）、`v.astro_sw`（攻撃の振り 0→1）、
`v.astro_fp`（一人称で 1）、`v.astro_usew`（右クリック中 0→1、なめらか）。素の `q.*` は持ち主を評価する。

```python
WEAPON_ANIMS = {
    "idle":  {"fx_spin_moon": {"rotation": [0, 0, "q.anim_time * 140.0"]},   # W.spin_expr("z", 140) と同じ
              "fx_glow_core": W.pulse_expr(180, 0.08)},
    "swing": {"fx_spin_moon": {"rotation": [0, 0, "v.astro_sw * 360.0"]}},   # 振るたびに足される
    "form_axes": {"form_2_blade": "z"},          # 形成で z 方向に伸びる部品（他は一様にポップ）
    "swing_root": {"rx": (34, 66)},              # 手首の返しの角度（三人称, 一人称）。正で刃先が -Y（刃の側）へ
    "idle_length": 6.0,
}
CORE_ANIMS = {"idle": {"fx_spin_ring_a": W.spin_expr("y", 80)}, "use": {...}}   # use = 右クリック中（変身の構え）
```
自動で付くもの: `origin` の呼吸（上下 0.1）・振り（種類ごとの手首の返し）・コアの浮遊（上下 0.35 とゆっくり首振り）・
右クリック中のコアの拡大と輪の加速・形成（form_）。

## 8. アイコン・プレビュー・検査の目安

* アイコンは 64x64・透過・1px の暗い縁（自動）。剣は斜め 45°（`ICON`）。小さい表示で形が分かるか（等倍の絵）を見る。
* 三人称: 握りが拳の中にあるか、刃が脚・地面に刺さっていないか。一人称: 照準（中央の +）を隠さず、右下に収まるか。
* 形成: `form_` の番号が「柄 → 鍔 → 刃」の順か。刃は `form_axes` で伸ばす。
* `validate_astro.py`（まとめ役）がジオメトリ・アニメ・アタッチャブルの相互参照、UV、Molang の括弧を全部調べる。

---

## 9. body.py — 全身モーション（BODY_ANIMS）

```python
from astro_animlib import BACK, DOWN, FWD, LEFT, RIGHT, UP, H, P, aim, anim, dirv, flip, wield

hit = P(rA=wield(blade=dirv(f=1.0, r=-0.1), edge=LEFT), b=(6, -12, 0), lL=(-30, 0, -6), ground=True)
BODY_ANIMS = {
    "combo1": anim(0.5, {0.0: H, 0.07: wind, 0.17: hit, 0.26: follow, 0.5: H}),     # kind="act"（既定）
    "dive":   anim(0.6, {...}, kind="act", loop=False, blend=None),
}
```

* 名前は `animation.astro.p.<key>.<名前>` になる（`.` を含めない）。スクリプトは `body(p, "<key>.<名前>")`。
  **`combo1` `combo2` `combo3` は通常攻撃の三段で自動で再生**される（0.4〜0.7 秒が目安）。
* **共通モーション**（`henshin` `revert` `airjump` `boost` `hover` `step` `land` `barrier` `ult_rise` `cast` `throw`
  `slam` `thrust` `spin` `none`）は astro_animlib.library() にある。武器の向きを `wield()` で書いた共通モーションは、
  各惑星の武器で解き直した版（`<key>.cast` など）が自動で作られ、スクリプトはそちらを優先して使う。
  **同じ名前を BODY_ANIMS に書くと、その惑星ではそちらが使われる**（上書き）。
* キー = `{秒: 姿勢}`。**姿勢は全身の絶対値**。書かなかった部位は自然体（`H`）。前の姿勢を土台に `P(前, rA=...)`。
  最初と最後は `H` にする（なめらかに戻る）。キーの間は統合版と同じ catmullrom で補間される。

| 部位 | 中身（回転は度、統合版の向き） |
|---|---|
| `rA` `lA` 腕 | Euler `(rx, ry, rz)`（rx 負 = 前へ上がる、rz 正 = 右腕が外へ / 左腕は負で外）か `aim()` か `wield()` |
| `b` 体 | 首の付け根まわり。rx 正 = 前かがみ、ry 正 = 右（-X）を向く |
| `w` 腰 | (0,12,0) まわりに上半身ごと。前傾・踏み込みに |
| `h` 頭 | rx 負 = 見上げる |
| `rL` `lL` 脚 | rx 負 = 前へ出す、rz 正 = 右脚が外へ |
| `root` | 全身の回転（足元まわり）。宙返りは `flip(t0, t1, turns, axis)` で |
| `root_pos` | 全身の位置 (x, y, z)。y 負 = しゃがむ、z 負 = 前へ |
| `ground=True` | 低い方の足の裏が地面に着く高さに root_pos.y を合わせる（構え・膝つき） |

**向き**は体の空間（-Z 前・+Y 上・-X 右）。`dirv(f=前, u=上, r=右)` が分かりやすい。体・腰のひねりは自動で打ち消す
（「体を右へ 40° ひねって、腕は世界の前へ」と書ける）。

* `aim(向き, twist=0)` — 腕（肩→拳）をその向きへ。twist は腕の軸まわりのひねり。
* `wield(blade=刃先の向き, arm=腕の向き)` / `wield(blade=..., edge=刃の向く側)` — 右手の武器の刃先を blade へ。
  手首の角度（§3 の表）は変えられないので、**腕は blade から手首の角度だけ離れた円錐の上で、arm（または edge）に
  一番近い所**になる。だから **arm を blade と同じ向きにしない**（決まらない）。
  * 振りかぶり・振り抜き・構えは `arm=`（腕の置き場所を決める）、**当たる瞬間だけ `edge=`**（刃を進む向きへ）が素直。
  * 腕を高く上げる時は、拳を頭の前に置かず少し右（`r=0.3` 以上）へ。柄頭が顔に刺さらない。
* **体に入らないよう自動で直す**: gen_astro_anim は惑星の武器（生成済みのジオメトリ）で、wield のキーを
  「刃先の向きを保ったまま腕を刃の軸まわりに回す（足りなければ刃先を 36° まで傾ける）」で解き直し、さらに
  0.02 秒ごとに調べて入り込むコマに腕のキーを足す。それでも `--check` に `CLIP` が出たら、
  **間にキーを足して刃の通り道を体の外へ回す**（例: 振りかぶる前に一度横へ出す）。地球の tidal_slash・charge を参照。
* 種類（`anim(..., kind=)`）:
  * `act`（既定）技・コンボ。腕はバニラの持ち姿勢・歩きの腕振り・攻撃の振りを打ち消して、書いた角度そのものになる。
  * `pose` 変身・解除のように長く腕を固める物（攻撃の振りは打ち消さない）。
  * `move` 機動・ホバー。バニラに差分を足すだけ（他のモーションと重なるので腕は控えめに）。
  * 一人称では体・脚・全身は動かず、腕は自然体からの差の 25%（画面が暴れない）。
* `loop=True` でループ。一回転して終わる物（root が 300° 以上回る）は自動でブレンドなし（`anim_meta.js` の 0）。
* 変身の時間割に合わせる時は `astro_animlib.TR`（`TR["weapon_form"]` = 2.0 秒 など、TRANSFORM を秒にした物）。

## 10. スクリプトとの約束

* `anim_meta.js` に `{"<key>.<名前>": [長さ秒, ブレンド可否]}` が入る。技の時間割は `bodyTicks("<key>.<名前>")` で合わせる。
* コントローラは技・コンボが `astro.act`、機動が `astro.move`、変身・ホバーが `astro.pose`（fx.js の body()）。
* ウェポン・コアの ID は `astro:weapon_<key>` / `astro:core_<key>`（アイテムとアタッチャブル。gen_astro_packs と gen_astro_weapons）。
