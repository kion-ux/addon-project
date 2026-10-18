# 惑星スーツの作り方（planets/<key>/suit.py）

このフォルダは雛形です。`tools/astro/planets/<key>/` を作り、`__init__.py`（空）と、ここの `suit.py` を
コピーして書き始めてください（`<key>` は `astro_data.PLANETS` のキー: mercury venus earth mars jupiter
saturn uranus neptune sol）。**お手本は `planets/earth/suit.py`（蒼星機装 ガイア）** です。迷ったらそれを読んでください。

自分の惑星のフォルダ以外（`astro_suit.py` などの共通部分・他の惑星）は編集しないでください。
足りない機能があればまとめ役に伝えてください。

---

## 1. 作業の流れ

```sh
python3 tools/astro/preview_astro.py suit <key>     # 組み立てて塗って描く → build_preview/astro/suit_<key>.png
python3 tools/astro/check_astro_suits.py <key>      # 被覆・命名・キューブ数・アニメの検査（NG なら終了コード 1）
python3 tools/astro/gen_astro_suits.py <key>        # pack へ書き出す（geo / png / アタッチャブル 3 種 / 共有アニメ）
```

* プレビューは pack を書き換えないので、何度でも回して **必ず絵を見て** 直す（正面・背面・側面・斜め・見下ろし・
  組み上がり 0.3/0.8/1.2/1.8 秒・空中・疾走・解除・一人称）。
* `gen_astro_suits.py` は共有のアニメ／コントローラを「planets/ にある全惑星」から毎回作り直すので、
  自分の惑星だけを指定して回してよい（他の惑星のファイルは壊れない）。
* 最後に `check_astro_suits.py <key>` が `[OK]` になること。

## 2. suit.py に書くもの

| 名前 | 必須 | 内容 |
|---|---|---|
| `build_suit(s)` | ○ | `s: astro_suit.Suit` に部位ボーンとキューブを足す |
| `SUIT_STYLES` | | 塗りの上書き・追加 `{"スタイル名": {キー: 値}}`（§5） |
| `SUIT_ANIMS` | | 部位アニメ `{"idle"/"thrust"/"sprint": {ボーン: {rotation/position: [...]}}}`（§6） |
| `MIRROR` | | 既定 True。False にすると `_r` の自動鏡映をしない（左右非対称のスーツ） |
| `MIRROR_STYLES` | | 鏡映した左側で塗りを替える `{"glow_hot": "glow_cold"}`（水星の左右の色分けなど） |
| `COVER_ALLOW` | | 被覆検査の除外 `[("rightArm", "east")]` や `[("body", (x0,y0,z0), (x1,y1,z1))]` |
| `UV_SCALE` | | テクスチャ密度の基準（既定 4。1024x1024 に収まる最大まで自動で上げる） |

## 3. 座標・回転・骨格

* 16 単位 = 1 ブロック。プレイヤーは **-Z が正面、右手が -X**、+Y が上。足の裏が y=0、頭の上が y=32。
* 肌の箱（この外側レイヤー = 帽子 +0.5・他 +0.25 より外を覆う）:

| 部位 | 箱 (原点)+(大きさ) | ピボット |
|---|---|---|
| head | (-4,24,-4)+(8,8,8) | (0,24,0) |
| body | (-4,12,-2)+(8,12,4) | (0,24,0) |
| rightArm | (-8,12,-2)+(4,12,4)（スリムは幅 3・y 11.5〜） | (-5,22,0) |
| rightLeg | (-3.9,0,-2)+(4,12,4) | (-1.9,12,0) |

  左腕・左脚は X を反転。`astro_suit` の定数: `ARM_X = -6`（右腕の中心）・`LEG_X = -1.9`（右脚の中心）・`HAND_Y = 13.2`。
* **回転**（キューブ・ボーンの `rotation [rx, ry, rz]`、統合版の値そのまま。`R = Rz(-rz)·Ry(ry)·Rx(-rx)`）:

| 値 | 見え方 |
|---|---|
| rx > 0 | 上端が前（-Z）へ倒れる。**rx < 0 は面が前上を向く**（つま先・斜めの胸板・額の斜面） |
| ry > 0 | 正面（-Z）を向いていた面が右（-X）を向く ＝ +X の端が前へ出る（右胸板を V 字にする向き） |
| rz > 0 | 上端が +X へ、下端が -X へ ＝ **右側の部品なら下端が外へ開く**（草摺・肩の垂れ）。横板の外（-X）の端を下げたい時は rz < 0 |

  右側だけ作れば、左は `(rx, -ry, -rz)` に自動で直る。

## 4. 部位ボーンと命名（いちばん大事）

* **キューブは必ず部位ボーンへ**。トップレベル（body / head / rightArm / leftArm / rightLeg / leftLeg）に直接置かない。
* 部位ボーンは `s.part(群, 名前, 親, pivot=None)` で作る → 名前は `<群>_<名前>`。群は組み上がりの順番
  （`astro_data.ASSEMBLE_ORDER`、秒）:

| 群 | 開始 | 例 |
|---|---|---|
| inner | 0.00（一瞬で） | `s.inner_suit()` が作る黒いボディスーツ |
| boots | 0.00 | 足首から |
| legs | 0.20 | 膝・腿 |
| waist | 0.40 | ベルト・草摺 |
| torso | 0.55 | 胸・腹・襟・星核 |
| back | 0.75 | 背板・バックパック・スラスター |
| arms | 0.85 | 上腕・肘・篭手・拳 |
| shoulders | 1.00 | 肩当て |
| helmet | 1.20 | 兜 |
| extra | 1.30 | 環・衛星・マント・光輪（動く飾り） |
| visor | 1.50 | バイザー（+ 閃光） |

* **pivot は「生えてくる根元」**（組み上がりは pivot を中心に 0→1.15→1.0 とポップする）。省略すると群と親から既定値
  （ブーツは足首、脚は膝、腕は前腕、肩当ては肩の付け根、兜は頭の中心…）。同じ群の中は低い所から順に少しずつずれて出る。
* 親は トップレベル名・別の部位ボーン名・Bone のどれでもよい。同じ群の子は親と一緒に出る（群が違う子は自分の時刻に出る）。
* **右側だけ作り、名前の末尾を `_r` にする**（例 `s.part("arms", "gauntlet_r", "rightArm")`）。
  `build()` が最後に `_l` を作る（X 反転・回転 (rx,-ry,-rz)・デカールの east/west 入れ替え）。
  鏡映する部分木の中のボーンは **全部** `_r` で終わること（`fx_thrust_r` など）。片側だけの部品は `_r` を付けない。
* 胸・兜など中央の部品の左右対称は `mirror_x(bone, cube, cube...)`（同じボーンの中で X 反転を足す）。
  脚の中心で対称にするなら `mirror_x(bone, cube, about=LEG_X)`。
* 動かす部品はさらに子ボーン `s.fx(種類, 名前, 親)` → `fx_<種類>_<名前>`:
  * `fx_thrust_*` スラスターの炎。**局所 -Y（下）へ伸ばして作る**（斜めのノズルはボーンの rotation で傾ける）。
    生成器が空中で伸ばし（長さ ×1）、地上で縮める（×0.22 の種火）。炎は全長で作っておく。
  * `fx_glow_*` 発光の脈動（生成器が待機中ゆっくり 3.5% 脈打たせる）。visor 群の下の `fx_glow_*` は変身時に閃光。
  * `fx_spin_*` 回転体（動きは SUIT_ANIMS で書く）。
  * **材質**: スーツの既定は片面（`entity_emissive_alpha_one_sided`。一人称で兜の内側が画面を覆わないため）。
    `fx_*` ボーンだけ両面。炎・輪・薄い板は fx_* に入れる（検査が警告する）。
* **プレイヤーのボーン名を付けない**: cape hat jacket waist root rightItem leftItem helmet bodyArmor belt
  leftSleeve rightSleeve leftPants rightPants rightSock leftSock rightBoot leftBoot leftLegging rightLegging
  leftArmArmor rightArmArmor（大文字小文字を区別しない）。付けるとそのボーンに付いて動いてしまう。`helmet_crest` のように
  群の接頭辞が付いていれば問題ない。

## 5. 形を作る道具（`from astro_common import ...`）

| 関数 | 使い方 |
|---|---|
| `cbox(bone, 中心, 大きさ, スタイル, rotation=…, pivot=…)` | 基本の箱 |
| `rbox(bone, 中心, 大きさ, スタイル, rot=(rx,ry,rz))` | 傾けた箱（中心まわり）。`plate(..., tilt=)` は同じ物 |
| `bevel(bone, 中心, 大きさ, スタイル, cut, axis, rot=)` | 45° 面取りの箱（6 個）。肩当て・兜・胸郭に。戻り値の [0][1] が本体 |
| `chamfer(...)` | 段々の面取り（2 個） |
| `octa(bone, 中心, 幅, 長さ, スタイル, axis)` | 八角柱（2 個）。ノズル・関節の円盤・宝玉の台 |
| `beam(bone, p0, p1, 幅, 高さ, スタイル, roll=)` / `polyline(bone, 点列, 幅, 高さ, スタイル)` | 2 点を結ぶ角柱 / 折れ線（角・アンテナ・翼の骨） |
| `taper(bone, p0, p1, 根元の幅, 先の幅, 段数, スタイル)` | 先細り（炎・トゲ・角）。45° の段も重ねて丸く見せる |
| `ring(bone, 中心, 半径, 個数, (接線長 or 0, 厚み, 幅), スタイル, axis)` | 輪（環・光の輪・ノズルの縁） |
| `stick(bone, 板, 面, a, b, (a 方向, b 方向, 厚み), スタイル, sink=)` | 傾いた板の面に、同じ傾きで小物を貼る（縁取り・ボルト・重ね板） |
| `line_on(bone, 板, 面, (a0,b0), (a1,b1), 幅, 厚み, スタイル)` | 傾いた板の面の上を走る線（発光ライン・金の縁） |
| `surface(板, 面, a, b)` | 面の上の点と法線（自分で配置したい時） |
| `fill_tri_yz(...)` | YZ 平面の三角形を埋める（hyperdim と同じ） |

`stick` / `line_on` の (a, b) は面の 0..1 の座標: north/south は (x, y)、east/west は (z, y)、up/down は (x, z)。
**重ねて奥行きを出す**: 下の板（青）→ 少しずらした上の板（白）→ 縁の金 → 発光線、の順に重ねると一気にそれらしくなる。

## 6. 塗り（SUIT_STYLES）

`astro_paint.suit_styles(key)` が `astro_data.PLANETS[key]["colors"]` から一式を作る。使えるスタイル名:

| 名前 | kind | 用途 |
|---|---|---|
| `plate` / `plate_b` | armor | 主装甲 / 一段暗い奥の板（パネル線なし） |
| `plate2` / `plate2_b` | armor | 副装甲（白など）/ その奥の板 |
| `accent` | armor | 差し色の装甲 |
| `plain` / `plain2` | armor | パネル線も照りも無い板 |
| `inner` | inner | 黒いインナー（六角メッシュ・ごく稀に光る継ぎ目） |
| `frame` / `dark` | frame | 関節・フレームの暗い金属（溝あり / 無地） |
| `chrome` / `gold` / `silver` | chrome / trim | 鏡面 / 金具（縁取り） |
| `visor` | visor | バイザー（発光・照り返し・走査線） |
| `glow` / `glow_soft` / `glow_accent` | glowline | 発光ライン（全発光 / 半発光 / 差し色） |
| `vent` / `thruster` / `flame` | vent / thruster / flame | 排気口 / ノズル（下面に同心円）/ 炎 |
| `core` / `planet` | core / planet | 惑星の星核（発光）/ 同じ模様の差し色（非発光） |
| `gem` / `gem_accent` / `crystal` / `ice` / `energy` | | 宝玉・結晶・氷・プラズマ |
| `cloth` | cloth | マント（ひだ・下端の雲の縁取り `cloud`・上端の縁 `hem`） |
| `hazard` / `serial` / `emblem` | decal | 警告ストライプ / 型番 / 惑星の紋章を板に描いた物 |
| `luna` | planet | 月（クレーター） |

上書き・追加の例:
```python
SUIT_STYLES = {
    "plate": {"panel": 0},                                   # パネル線を消す
    "plate2": {"stripe": {"dir": "h", "period": 8, "width": 3, "color": (176, 112, 70)}},  # 縞（木星）
    "flame": {"glow": (255, 140, 40), "deep": (160, 40, 10)},  # 炎の色
    "hot": {"kind": "glowline", "glow": (255, 150, 60), "light": (255, 240, 200)},  # 新しいスタイル
    "rim": {"kind": "trim", "base": (220, 226, 240)},          # 銀の縁取り
}
```
主なキー: `base light dark line`（色）、`panel`（0 でパネル線なし）、`bolts`、`sheen`、`stripe`、`trim`（下辺の帯の色）、
`emit`（発光の強さ: アルファ。**低いほど強く光る**、12 ≈ 全発光、150 ≈ 半発光、255 = 光らない）、
`bevel` / `outline`（False で面取り・輪郭を消す）。core / planet は `planet="mars"` 等で模様を選べる。

**デカール**（1 つの面にだけ描く）: キューブに `decals={"west": {"decal": "serial", "text": "AR-04"}}`。
種類: `hazard`（c1, c2, band=full/top/bottom）、`serial`（text, ink, x, y）、`emblem`（color, size）、
`stripe`（color, dir, pos, width, emit）、`chevron`、`lights`（count, color）、`bolt`。

## 7. 部位アニメ（SUIT_ANIMS）

```python
SUIT_ANIMS = {
    "idle": {                                   # 常に再生（12 秒でループ）
        "extra_cape_r": {"rotation": ["3.0 + math.sin(q.anim_time * 90.0) * 2.0", 0, 0]},
        "fx_spin_ring": {"rotation": [0, "q.anim_time * 60.0", 0]},
        "extra_moon": {"position": [0, "math.sin(q.anim_time * 120.0) * 0.4", 0]},
    },
    "thrust": {                                 # 常に再生。v.astro_air（空中で 0→1 になめらかに）で強さを付ける
        "extra_cape_r": {"rotation": ["v.astro_air * 34.0", 0, "-v.astro_air * 7.0"]},
    },
    "sprint": {                                 # 疾走中。v.astro_run（0→1）
        "extra_cape_r": {"rotation": ["v.astro_run * 28.0", 0, 0]},
    },
}
```
* 値は数か Molang の文字列。`math.sin/cos` は **度**。`q.anim_time` は 12 秒でループするので、周波数は
  **30°/秒の倍数**（30, 60, 90, 120, 180, 360, 720…）にすると継ぎ目が出ない。
* 使える変数: `q.anim_time`、`v.astro_air`（空中 0..1）、`v.astro_run`（疾走 0..1）、`v.astro_fp`（一人称 1）。
  アタッチャブルの中の素の `q.*`（`q.is_on_ground` `q.is_sneaking` `q.modified_move_speed` …）は装着者を指す。
* 同じボーンの回転・位置は全部のアニメの和になる（idle の揺れ + thrust の跳ね上げ）。
* `_r` のボーンのトラックは左（`_l`）へ自動で鏡映される（rotation は (rx,-ry,-rz)、position は (-x,y,z)）。
  左だけ違う動きにしたい時は `_l` を自分で書く（位相をずらす等）。
* **部位ボーン（`<群>_<名前>`）の scale は書かない**（組み上がり・解除が scale を使う）。大きさを変えたい物は
  `fx_*` の子ボーンにする。トップレベルのボーンも動かさない。
* `idle` / `thrust` / `sprint` 以外の名前を足すと `animation.astro.suit.<key>.<名前>` として書き出され、
  アタッチャブルの animations にも載る（スクリプトや他のアニメから使う時に）。
* 回転体の例: 傾いた軌道は「傾けた部位ボーン（rotation）→ fx_spin の子（rotation を回す）→ その中に衛星」
  （earth の `luna_bit()` を参照）。

## 8. 被覆（肌が見えないこと）

* `s.inner_suit(gap=0.3)` を最初に呼ぶ。6 部位の外側レイヤーより `gap` 外に黒いインナーの殻を張るので、
  これだけで検査は通る（スリムの腕の y 11.25 まで覆う）。装甲はその上に重ねる。
* 被覆の検査は extra_* と fx_*（動く部品）を数えない。トップレベルごとに、**同じトップレベルの下の**
  キューブだけで覆う（腕の装甲で胴を覆うことはできない）。
* 一人称では head / body / 脚が隠れ、**腕（rightArm / leftArm の下）だけが見える**。肩当てや篭手が大きすぎると
  一人称の画面を塞ぐので、プレビューの「一人称」の絵を確かめる。

## 9. 予算と品質の目安

* キューブ 350〜550 を目安（検査は 250〜650 の外を NG）。テクスチャは自動で 1024x1024 に収まる最大の密度。
  小さく細かい部品（宝玉・顔）は `uv_scale=8` などで個別に細かくできる。
* 「箱を積んだ」見た目を避ける: 面取り（bevel）・傾き（rbox）・重ね（stick）・先細り（taper）・縁取り（gold の line_on）。
  胴は上が広く腰が細い逆三角形、兜は額・屋根の斜面と中央の稜で箱の輪郭を崩す。
* 色の配分: 主装甲（plate）と副装甲（plate2）を交互に、発光（glow）は細く要所だけ、金（gold）は縁取りに。

## 10. よくある落とし穴

* 中央の部品を左右対称にしようとして `_r` を付けない部品を X 反転し忘れる → `mirror_x` を使う。
* 同じ平面に色の違う面が重なる（Z ファイト）→ 0.05 以上ずらす。`inner_suit` は左脚の殻を少し厚くして避けている。
* 頭の帽子レイヤーの角（±4.5, 32.5, ±4.5）は必ず内側に入るので、兜の上を大きく面取りすると角が突き抜ける →
  屋根の板は角より上に置く（earth の兜を参照）。
* 衛星・環の軌道が頭や肩当てに当たる → プレビューの「斜め前」「見下ろし」で確かめる。
* `fx_thrust_*` の炎を横向きに作る → 炎は局所 -Y に伸ばし、向きはボーンの rotation で。
* SUIT_ANIMS で `math.sin(q.anim_time * 100)` のような 30 の倍数でない周波数 → 12 秒ごとに跳ぶ。
