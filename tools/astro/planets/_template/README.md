# 惑星スーツの作り方（v1.1: 7 頭身・細かい部品）

このフォルダは雛形です。`tools/astro/planets/<key>/` に `__init__.py`（空）と、ここの `suit.py` をコピーして
書き始めてください（`<key>`: mercury venus earth mars jupiter saturn uranus neptune sol）。
**お手本は `planets/earth/suit.py`（蒼星機装 ガイア、約 1060 キューブ）** です。迷ったらそれを読んでください。

自分の惑星のフォルダ以外（`astro_suit.py` などの共通部分・他の惑星）は編集しないでください。
足りない機能があればまとめ役に伝えてください。

---

## 0. v1.0 から変わったこと（必読）

| | v1.0 | v1.1 |
|---|---|---|
| 体型 | プレイヤーの肌（4 頭身の箱）を覆う | **7 頭身の全身像**（背丈 32、頭 4.6、長い脚、逆三角形の胴） |
| 肌 | `s.inner_suit()` で全部覆い、被覆検査 | 変身中はスクリプトが **透明化** するので覆わない。被覆検査は無い |
| 土台 | inner_suit の黒い殻 | **`s.frame7()`** の暗い機械の骨格（関節・ピストン・指まで） |
| 寸法 | `ARM_X` `LEG_X` `HAND_Y` | **`A.*`**（解剖の目安。`from astro_suit import A`） |
| 細かさ | 250〜650 キューブ | **600〜1400**（目安 850〜1150）、うち **35% 以上が 3 辺とも 1.0 以下** |
| 検査 | 被覆・命名・数 | **プロポーション**（背丈・頭の高さと幅・胸/腰・見えている脚）・細かさ・命名・アニメ |

骨格（トップレベル 6 ボーンの名前とピボット）は **変わらない**。プレイヤーの動き（歩き・振り・全身モーション）は
そのままスーツに伝わる。だから「腕の付け根の球（肩関節）」や「腿の上端」はピボットより **上** にあり、
腕・脚が回るとピボットを中心に振れる（§11）。

## 1. 作業の流れ

```sh
python3 tools/astro/preview_astro.py suit <key>     # 組み立てて塗って描く → build_preview/astro/suit_<key>.png
python3 tools/astro/check_astro_suits.py <key>      # 7 頭身・細かさ・命名・アニメの検査（NG なら終了コード 1）
python3 tools/astro/gen_astro_suits.py <key>        # pack へ書き出す（geo / png / アタッチャブル 3 種 / 共有アニメ）
```

* プレビューは pack を書き換えないので、何度でも回して **必ず PNG を開いて見る**。並べ図（プレイヤーの肌は描かない）:
  正面（7 頭身の目盛り = 1 頭身ごとの横線、水色の線 = バニラのプレイヤーの箱）/ 背面 / 左側面 / 斜め前 / 斜め後ろ /
  **内部フレームだけ** / 組み上がり 0.45・0.95・1.35・1.8 秒 / 空中 / 疾走 / ナノウェポン / 見下ろし / 解除 /
  **近接（上半身・脚・背中）** / 一人称。見出しの 2 行目に計測値（背丈 H、頭の高さ（H/7 に近いこと）と幅、
  胸/腰、見えている脚の長さ（×H）、細かい部品の割合）が出る。
* 正面の目盛りで、頭がちょうど一番上の 1 マス（1 頭身）に収まり、股（腿の付け根）が 4 マス目の下あたりに来るのが目安。
* `gen_astro_suits.py` は共有のアニメ／コントローラを「planets/ にある全惑星」から毎回作り直すので、
  自分の惑星だけを指定して回してよい。最後に `check_astro_suits.py <key>` が `[OK]` で、警告も無いこと。
* 1 回のプレビューは 40 秒ほど（CPU を他の人と分け合っているので、むやみに並列で回さない）。

## 2. suit.py に書くもの

| 名前 | 必須 | 内容 |
|---|---|---|
| `build_suit(s)` | ○ | `s: astro_suit.Suit`。最初に `s.frame7(...)`、その上に部位ボーンとキューブを足す |
| `SUIT_STYLES` | | 塗りの上書き・追加 `{"スタイル名": {キー: 値}}`（§8） |
| `SUIT_ANIMS` | | 部位アニメ `{"idle"/"thrust"/"sprint"/他: {ボーン: {rotation/position: [...]}}}`（§9） |
| `MIRROR` | | 既定 True。False で `_r` の自動鏡映をしない（左右非対称のスーツ。frame7 の骨格だけは常に左右対称） |
| `MIRROR_STYLES` | | 鏡映した左側で塗りを替える `{"glow_hot": "glow_cold"}`（水星の左右の色分けなど） |
| `ORNAMENTS` | | 計測から外す飾りのボーン名のリスト（`s.part(..., ornament=True)` と同じ） |
| `UV_SCALE` | | テクスチャ密度の基準（既定 4。1024x1024 に収まる最大まで自動で上げ下げ。earth は x7 になった） |

## 3. 7 頭身の寸法（`astro_suit.A`）

座標: 16 単位 = 1 ブロック、**-Z が正面、右手が -X**、+Y が上、足の裏が y=0。点のタプルは **右側の値**
（右側だけ作れば左は自動で鏡映）。表は DESIGN §4.3b と同じ。

| 部位 | ボーン | 定数（右側） |
|---|---|---|
| 背丈・1 頭身 | | `A.H = 32`、`A.UNIT = 4.571` |
| 頭（兜） | head | `A.HEAD_TOP 32.0` `A.HEAD_BOT 27.4` `A.HEAD_Y 29.7` `A.HEAD_Z -0.25` `A.HEAD_W 4.6`（検査 ≤ 5.4）`A.HEAD_D 5.0` `A.EYE_Y 29.5` `A.FACE_Z -2.75` `A.CHIN_Y 27.4` |
| 首 | head | `A.NECK_BOT 25.6` `A.NECK_TOP 27.8` `A.NECK_W 2.4` `A.NECK_Z 0.15` |
| 肩の線 | body | `A.SHOULDER_Y 26.0` `A.DELTOID_X -7.5`（肩当ての外の目安 -7.0〜-8.0） |
| 胸 | body | `A.CHEST_TOP 26.2` `A.CHEST_BOT 20.5` `A.CHEST_Y 23.4` `A.CHEST_W 9.8` `A.CHEST_D 5.2` `A.CHEST_FRONT -2.6` `A.CHEST_BACK 2.6` |
| 腰（くびれ） | body | `A.WAIST_TOP 20.5` `A.WAIST_BOT 16.8` `A.WAIST_Y 18.6` `A.WAIST_W 6.0` `A.WAIST_D 3.9` `A.WAIST_Z 0.15` |
| 骨盤 | body | `A.PELVIS_TOP 17.0` `A.PELVIS_BOT 13.6` `A.PELVIS_Y 15.3` `A.PELVIS_W 7.4` `A.PELVIS_D 4.4` `A.CROTCH_Y 13.6` |
| 背中 | body | `A.BACKPACK (0, 22.2, 3.4)`（バックパック・スラスターの付け根） |
| 股関節 | rightLeg | `A.HIP (-2.2, 14.6, 0)` `A.HIP_Y`（ピボット y12 より上。骨盤・草摺で隠す） |
| 脚の軸 | rightLeg | `A.LEG_X -2.15`（腿・膝・脛・足の中心の X） |
| 腿 | rightLeg | `A.THIGH_TOP 15.0` `A.THIGH_BOT 9.0` `A.THIGH_W 3.3` |
| 膝 | rightLeg | `A.KNEE (-2.15, 8.5, -0.05)` `A.KNEE_Y` `A.KNEE_TOP 9.4` `A.KNEE_BOT 7.6` |
| 脛 | rightLeg | `A.SHIN_TOP 7.8` `A.SHIN_BOT 1.8` `A.SHIN_W 2.9` `A.CALF_Y 5.8` |
| 足首・足 | rightLeg | `A.ANKLE (-2.15, 2.1, 0.3)` `A.FOOT_TOP 1.8` `A.TOE_Z -4.0` `A.HEEL_Z 1.6` `A.FOOT_W 2.7` |
| 肩関節 | rightArm | `A.SHOULDER (-6.4, 24.4, 0)`（ピボット (-5,22) より上。肩当てで隠す） |
| 二の腕 | rightArm | `A.UPPER_ARM_TOP 24.0` `A.UPPER_ARM_BOT 19.0` `A.UPPER_ARM_W 2.6` `A.UPPER_ARM_X -6.3` |
| 肘 | rightArm | `A.ELBOW (-6.2, 18.5, 0.1)` `A.ELBOW_Y` `A.ELBOW_TOP 19.2` `A.ELBOW_BOT 17.8` |
| 前腕（籠手） | rightArm | `A.FOREARM_TOP 18.2` `A.FOREARM_BOT 14.6` `A.FOREARM_W 2.9` `A.FOREARM_X -6.1` |
| 手首・拳 | rightArm | `A.WRIST (-6.05, 14.75, 0)` `A.FIST (-6, 13, 0)` `A.FIST_TOP 14.6` `A.FIST_BOT 11.4` `A.FIST_W 2.6` `A.FIST_D 2.8` |
| 武器の握り | rightArm | `A.GRIP (-6, 13.2, 0)`（武器の柄は Z 方向にここを通る。拳はこれを包む） |

`A.left(p)` / `mx(p)` で点の X を反転できる。

## 4. 回転

キューブ・ボーンの `rotation [rx, ry, rz]` は統合版の値そのまま（`R = Rz(-rz)·Ry(ry)·Rx(-rx)`）:

| 値 | 見え方 |
|---|---|
| rx > 0 | 上端が前（-Z）へ倒れる。**rx < 0 は面が前上を向く**（つま先・斜めの胸板・額の斜面） |
| ry > 0 | 正面（-Z）を向いていた面が右（-X）を向く ＝ +X の端が前へ出る（右胸板を V 字にする向き） |
| rz > 0 | 上端が +X へ、下端が -X へ ＝ **右側の部品なら下端が外へ開く**（草摺・肩の垂れ）。下端を内へ絞るなら rz < 0 |

右側だけ作れば、左は `(rx, -ry, -rz)` に自動で直る。

## 5. 部位ボーンと命名（いちばん大事）

* **キューブは必ず部位ボーンへ**。トップレベル（body / head / rightArm / leftArm / rightLeg / leftLeg）に直接置かない。
* `s.part(群, 名前, 親, pivot=None, rotation=None, ornament=False)` → 名前は `<群>_<名前>`。群 = 組み上がりの順番（秒）:

| 群 | 開始 | 例（既定の pivot） |
|---|---|---|
| inner | 0.00（一瞬） | `s.frame7()` が作る骨格（`inner_*`。自分では作らない） |
| boots | 0.00 | サバトン（`A.ANKLE`） |
| legs | 0.20 | 腿・膝・脛の装甲（`A.KNEE`） |
| waist | 0.40 | ベルト・前垂れ・草摺・後ろ垂れ（(0, 17, 0)） |
| torso | 0.55 | 胸・腹・襟・星核（(0, 22.4, 0)） |
| back | 0.75 | バックパック・スラスター・翼（(0, 22.2, 2.6)） |
| arms | 0.85 | 二の腕・肘・篭手・手の甲（`A.ELBOW`） |
| shoulders | 1.00 | 肩当て（`A.SHOULDER`） |
| helmet | 1.20 | 兜・角（(0, 27.8, 0)） |
| extra | 1.30 | マント・環・衛星・光輪（動く飾り） |
| visor | 1.50 | バイザー（+ 閃光）（(0, 29.5, -2.75)） |

* **pivot は「生えてくる根元」**（組み上がりは pivot を中心に 0→1.15→1.0 とポップする）。
* **右側だけ作り、名前の末尾を `_r`** にする（`s.part("arms", "gauntlet_r", "rightArm")`）。`build()` が最後に `_l` を作る。
  鏡映する部分木の中のボーンは **全部** `_r` で終わること（`fx_thrust_r` など）。片側だけの部品は `_r` を付けない。
* 胸・兜など中央の部品の左右対称は `mirror_x(bone, cube, [cubes], {dict}...)`（同じボーンの中で X 反転を足す。
  リストや layered_plate の辞書もそのまま渡せる）。脚の中心で対称にするなら `mirror_x(bone, cube, about=A.LEG_X)`。
* 動かす部品は `s.fx(種類, 名前, 親)` → `fx_<種類>_<名前>`: `fx_thrust_*`（炎。局所 -Y へ全長で作る。空中で伸びる）/
  `fx_glow_*`（脈動。visor 群の下はバイザーの閃光）/ `fx_spin_*`（回転体。動きは SUIT_ANIMS）。
  `fx_*` は両面の材質（炎・輪・薄い板は fx_* に入れる）。それ以外は片面（一人称で兜の内側が画面を覆わないため）。
* **飾り（角・鶏冠・アンテナ・背中の翼）は `ornament=True`**（または名前に crest / horn / antenna / plume / halo /
  ornament を含める）。背丈・頭・胸の計測から外れる（入れたままだと背丈が 35 を超えたり、頭の高さが NG になる）。
* **プレイヤーのボーン名を付けない**: cape hat jacket waist root rightItem leftItem helmet bodyArmor belt
  leftSleeve rightSleeve leftPants rightPants rightSock leftSock rightBoot leftBoot leftLegging rightLegging
  leftArmArmor rightArmArmor（大文字小文字を区別しない）。`helmet_crest` のように群の接頭辞が付いていれば問題ない。

## 6. 内部フレーム `s.frame7()`

最初に呼ぶ。これだけで「装甲を外した 7 頭身のロボ」になる（約 420 キューブ、うち 36% が細かい部品）:
兜の芯（顔の板・目の溝・耳のセンサー）と首（喉の輪・腱・首の後ろのピストン）、胸郭（4 段の肋骨の籠・鎖骨・胸骨・
胸の板・灯り・肩の受け）、背骨（9 個の椎骨と 2 本のケーブル）、細い腰（腹の節・腰椎・脇の油圧シリンダー）、
骨盤（股の箱・股関節の受け・腰の帯）、肩と股の球関節、肘・膝・足首・手首の八角の関節ドラム、節のある二の腕・
前腕・腿・脛（芯 + 支柱 + 輪）、二の腕の裏・膝裏・足首の後ろのピストン、**4 本 × 3 節の指と 2 節の親指の拳**
（`A.GRIP` を包む）、つま先の板が 2 枚の足。

```python
f = s.frame7()                                   # 既定
f = s.frame7(bulk=0.9)                           # 細身（手足と胸の太さ ×0.9。0.8〜1.25）
f = s.frame7(bulk=1.15, skip=("foot",))          # 巨体。足は自分のサバトンで包むので省く
f = s.frame7(style={"suit": "inner", "metal": "frame", "band": "frame_lt", "dark": "dark",
                    "joint": "chrome", "glow": "glow_soft"})  # 塗りの役割（既定値）
f = s.frame7(style="inner_hot", fingers=False)   # 文字列 = ボディスーツの塗り。fingers=False で指を省く
```

* `skip` に渡せる名前: head neck chest spine waist pelvis shoulder upper_arm elbow forearm wrist hand hip thigh knee
  shin ankle foot pistons cables。**装甲で完全に包む所は省く**とキューブとテクスチャの節約になる（earth は "foot"）。
  見える関節（肘・膝・足首のドラム、腰の脇、膝裏・ふくらはぎ）は残すこと — そこが 7 頭身のメカらしさの見せ場。
* 戻り値 `f` は役割名 → Bone の辞書（"head" "neck" "chest" "spine" "waist" "pelvis" "shoulder_r" "upper_arm_r"
  "forearm_r" "hand_r" "thigh_r" "knee_r" "shin_r" "foot_r"）。装甲は普通はトップレベル（"rightArm" など）の下に
  自分の部位ボーンを作って置く。**inner_* のボーンにキューブを足さない**（左右の鏡映がずれる・inner の時刻に出る）。
* 骨格の外形（右側。装甲はこれより 0.05 以上外か、わざと見せる）:

| ボーン | x | y | z |
|---|---|---|---|
| inner_head | ±2.14 | 27.3..31.8 | -2.58..1.95 |
| inner_neck | ±1.61 | 25.1..28.3 | -1.46..1.92 |
| inner_chest | ±4.68（肋骨） | 20.7..26.2 | -2.88..2.15 |
| inner_spine | ±1.2 | 15.5..25.8 | 1.8..2.9 |
| inner_waist | ±3.12（脇のピストン） | 16.45..21.3 | -1.8..2.2 |
| inner_pelvis | ±3.2 | 13.4..17.2 | -2.18..2.2 |
| inner_shoulder_r | -7.62..-5.05 | 23.2..25.6 | ±1.2 |
| inner_upper_arm_r（肘を含む） | -7.93..-4.67 | 16.8..23.6 | -1.58..1.76 |
| inner_forearm_r（手首を含む） | -7.84..-4.36 | 13.6..18.1 | ±1.76 |
| inner_hand_r | -7.49..-4.83 | 11.36..14.62 | -1.93..1.31 |
| inner_thigh_r（股関節の球を含む） | -4.11..-0.19 | 9.1..15.7 | ±1.96 |
| inner_knee_r（膝裏のピストン） | -3.90..-0.40 | 6.2..11.4 | -1.78..1.88 |
| inner_shin_r（足首を含む） | -3.80..-0.50 | 0.9..8.0 | -1.53..1.96 |
| inner_foot_r | -3.45..-0.85 | 0..2.34 | -4.08..1.65 |

## 7. 形を作る道具（`from astro_suit import ...`。astro_common の物も同じ名前で使える）

| 関数 | 使い方 |
|---|---|
| `cbox(bone, 中心, 大きさ, スタイル, rotation=…, pivot=…)` | 基本の箱 |
| `rbox(bone, 中心, 大きさ, スタイル, rot=(rx,ry,rz))` | 傾けた箱（中心まわり）。`plate(..., tilt=)` は同じ物 |
| `bevel(bone, 中心, 大きさ, スタイル, cut, axis, rot=, edge_style=)` | 45° 面取り（6 個）。戻り値の [0][1] が本体（stick の土台に） |
| `chamfer(...)` | 段々の面取り（2 個） |
| `octa(bone, 中心, 幅, 長さ, スタイル, axis)` | 八角柱（2 個）。輪・ノズル・腕輪（長さ 0.24 以上） |
| `beam(bone, p0, p1, 幅, 高さ, スタイル)` / `polyline(bone, 点列, 幅, 高さ, スタイル)` | 2 点を結ぶ角柱 / 折れ線 |
| `taper(bone, p0, p1, 根元の幅, 先の幅, 段数, スタイル)` | 先細り（炎・トゲ・角） |
| `ring(bone, 中心, 半径, 個数, (接線長 or 0, 厚み, 幅), スタイル, axis)` | 輪（環・光の輪・ボルトの輪） |
| `stick(bone, 板, 面, a, b, (a 方向, b 方向, 厚み), スタイル, sink=)` | 傾いた板の面に同じ傾きで小物を貼る |
| `line_on(bone, 板, 面, (a0,b0), (a1,b1), 幅, 厚み, スタイル)` | 傾いた板の面の上を走る線（発光ライン・金の縁） |
| **`rod(bone, p0, p1, 太さ, スタイル, sides=8)`** | 丸棒（八角柱 2 個 / 角柱 1 個） |
| **`ball(bone, 中心, 半径, スタイル, style2)`** | 球関節（4 個） |
| **`piston(bone, p0, p1, r=0.42, style="frame", rod_style="chrome", cap_style="dark", split=0.55)`** | 油圧シリンダー（筒 + ロッド + 締め輪 + 両端の目、約 7 個）。肘・膝・足首・首・腹の脇に |
| **`cable(bone, 点列, w=0.26, style="dark", sag=0, seg=0.8, rib=None, rib_every=2)`** | ケーブル・ホース。2 点なら sag ぶん垂れ、3 点以上は滑らかに通る。rib で蛇腹。1 区間 ≤ 1.0 なので細かい部品に数える |
| **`rivets(bone, 板, 面, n, edge="bottom"\|"top"\|"left"\|"right"\|"border", margin=0.3, size=0.26, style="silver", line=((a0,b0),(a1,b1)))`** | ボルト・リベットの列（1 個 1 キューブ。0.26×0.26×0.16） |
| **`vents(bone, 板, 面, n, box=(a0,b0,a1,b1), axis="h"\|"v", w=0.2, style="vent", rim=None)`** | 排気スリット（rim に塗りを渡すと枠も） |
| **`layered_plate(bone, 中心, 大きさ, 下の塗り, top="plate2", rot=, face="north", inset=0.35, trim="gold", trim_edge="bottom", rivet=None, n_rivets=0)`** | 縁取りのある多層の板。戻り値 `{"base","top","trim","rivets"}` |
| **`joint_drum(bone, 中心, r, 長さ, axis="x", style, cap, hub, glow=None, caps=(-1, 1), bolts=0)`** | 関節ドラム（八角柱 + 蓋 + 軸受け + 灯り）。右側の外側は caps=(-1,) |
| **`finger_chain(bone, 点列, w=0.5, h=None, style, knuckle, tip=None)`** | 指の関節の連なり |
| **`greebles(bone, 板, 面, n, seed, styles, size=(0.22,0.6), h=(0.15,0.24))`** | パネルの小物を散らす |
| **`sensor(bone, 中心, size=0.36, style="glow", bezel="dark", axis="z", facing=-1)`** | 小さなセンサーの灯り（2 個）。axis/facing で向き |
| `mx(p)` / `A.left(p)` | 点の X 反転 |

`stick` / `line_on` / `rivets` / `vents` の (a, b) は面の 0..1 の座標: north/south は (x, y)、east/west は (z, y)、
up/down は (x, z)。**面の向き**: north = 前（-Z）、south = 後ろ、west = -X（右側の部品の外側）、east = +X。

例（earth から）:
```python
# 縁取りのある腿の板: 白の下板 → 青の上板（inset 0.3）→ 金の下縁 → 上板の上辺にリベット 3 個 → 緑の線
fr = layered_plate(t, (A.LEG_X, 11.75, -1.82), (2.85, 4.3, 0.55), "plate2", top="plate",
                   rot=(-3, 0, 0), inset=0.3, trim="gold", rivet="rivet", n_rivets=3, rivet_edge="top")
line_on(t, fr["top"], "north", (0.74, 0.1), (0.74, 0.6), 0.18, 0.16, "glow")
# 膝の外の油圧シリンダー（腿から脛へ）
piston(k, (A.LEG_X - 1.62, 10.9, 0.55), (A.LEG_X - 1.5, 6.3, 0.45), r=0.27)
# バックパックから腰の脇へ垂れる蛇腹のホース（中央の部品なので mirror_x）
hs = cable(bk, [(-1.6, 19.9, 3.6), (-2.9, 17.6, 2.4)], 0.3, "dark", sag=0.35, rib="frame_lt")
mirror_x(bk, hs)
# 肩当ての上板の縁にリベット 6 個、外の垂れ板の上辺に 5 個
rivets(p, top, "up", 6, edge="border", margin=0.25, size=0.24)
rivets(p, l1, "west", 5, edge="top", margin=0.24, size=0.22)
# ふくらはぎの排気口 3 本 / バックパックの枠付きスリット 4 本
vents(g, calf, "south", 3, box=(0.2, 0.2, 0.8, 0.8))
vents(bk, pk[0], "south", 4, box=(0.25, 0.3, 0.75, 0.7), rim="frame")
```

## 8. 塗り（SUIT_STYLES）

`astro_paint.suit_styles(key)` が `astro_data.PLANETS[key]["colors"]` から一式を作る。使えるスタイル名:

| 名前 | kind | 用途 |
|---|---|---|
| `plate` / `plate_b` | armor | 主装甲 / 一段暗い奥の板（パネル線なし） |
| `plate2` / `plate2_b` | armor | 副装甲（白など）/ その奥の板 |
| `accent` / `plain` / `plain2` | armor | 差し色 / パネル線も照りも無い板 |
| `inner` | inner | 黒いボディスーツ（六角メッシュ）。frame7 の筋肉の芯 |
| `frame` / `dark` | frame | 関節・フレームの暗い金属（溝あり / 無地） |
| `frame_lt` / `steel` | frame / chrome | **v1.1**: 少し明るい溝の金属（frame7 の輪・肋骨）/ 落ち着いた鏡面 |
| `chrome` / `gold` / `silver` / `rivet` | chrome / trim | 鏡面 / 金具（縁取り）/ **リベット**（小さくても読める銀） |
| `visor` | visor | バイザー（発光・照り返し・走査線） |
| `glow` / `glow_soft` / `glow_accent` | glowline | 発光ライン（全発光 / 半発光 / 差し色） |
| `vent` / `thruster` / `flame` | vent / thruster / flame | 排気口 / ノズル / 炎 |
| `core` / `planet` / `luna` | core / planet | 惑星の星核（発光）/ 同じ模様の差し色 / 月 |
| `gem` / `gem_accent` / `crystal` / `ice` / `energy` | | 宝玉・結晶・氷・プラズマ |
| `cloth` | cloth | マント（ひだ・雲の縁取り `cloud`・上端の縁 `hem`） |
| `hazard` / `serial` / `emblem` | decal | 警告ストライプ / 型番 / 惑星の紋章 |

上書き・追加は v1.0 と同じ（`{"plate": {"panel": 0}, "hot": {"kind": "glowline", "glow": (255,150,60)}}`）。
デカールはキューブに `decals={"west": {"decal": "serial", "text": "AR-04"}}`。
**発光ラインは暗い・濃い色の板の上に**（白い板の上の発光は白飛びして読めない。earth は青の板に緑の線）。

## 9. 部位アニメ（SUIT_ANIMS）

```python
SUIT_ANIMS = {
    "idle": {                                   # 常に再生（12 秒でループ）
        "extra_cape_r": {"rotation": ["3.0 + math.sin(q.anim_time * 90.0) * 2.0", 0, 0]},
        "fx_spin_ring": {"rotation": [0, "q.anim_time * 60.0", 0]},
    },
    "thrust": {"extra_cape_r": {"rotation": ["v.astro_air * 26.0", 0, 0]}},   # 空中 0..1
    "sprint": {"extra_cape_r": {"rotation": ["v.astro_run * 24.0", 0, 0]}},   # 疾走 0..1
}
```
* `math.sin/cos` は **度**。ループは 12 秒なので、`q.anim_time` に掛ける周波数は **30°/秒の倍数**（30, 60, 90, 120,
  180, 360, 720, 900…）。**検査が継ぎ目を調べる**（`gen_astro_suits.loop_errors`。100 などは NG）。
  `animation_length` を変えたら周波数 × 長さが 360 の整数倍になるように。
* 変数: `q.anim_time`、`v.astro_air`、`v.astro_run`、`v.astro_fp`。アタッチャブルの中の素の `q.*` は装着者を指す。
* `_r` のトラックは左（`_l`）へ自動で鏡映（rotation は (rx,-ry,-rz)、position は (-x,y,z)）。
* **部位ボーン（`<群>_<名前>`）の scale は書かない**（組み上がり・解除が使う）。トップレベルも動かさない。

## 10. 予算と検査（`check_astro_suits.py`）

| 項目 | 閾値 | earth |
|---|---|---|
| 背丈（飾りを除く足の裏 → 頭頂） | 31〜35 | 32.2 |
| 頭の高さ | 背丈/7 ± 12%（首のくびれの上で断面が頭の大きさに戻る所 → 頭頂） | 4.96（H/6.5） |
| 頭の幅 | ≤ 5.4（耳・頬を含む。角とアンテナは ornament で外す） | 5.29 |
| 胸の幅 / 腰の幅 | ≥ 1.45（body だけ。胸 = y 20.5〜26.7 の最大、腰 = y 17.0〜20.3 の最小） | 9.96 / 5.38 = 1.85 |
| 見えている脚 | ≥ 0.44 × 背丈（正面から見て脚が手前に見えている一番上。extra_* は数えない） | 0.46H |
| キューブ数 | 600〜1400（目安 850〜1150） | 1062 |
| 細かい部品 | 3 辺とも 1.0 以下のキューブが 35% 以上 | 38% |
| 最小の部品 | どの辺も 0.15 以上 | |
| テクスチャ | 1024x1024 に収まる（テクセル x3 未満は警告） | x7 |

その他: 命名、炎は fx_* の下、回転体のめり込み（警告）、SUIT_ANIMS のボーン・Molang・scale、ループの継ぎ目、
生成済みファイルの相互参照、`hide_all` が `c.item_slot != 'head'` だけで判定されていること。

**細かさの稼ぎ方**（earth の内訳の目安: リベット 約 120、指・関節 約 60、センサー 約 30、ケーブルの区間 約 40、
スリット・小板・宝玉 約 100）: 大きな板を減らして、縁（金の帯）・リベットの列・スリット・センサー・小さな重ね板・
指の甲当てを足す。テクスチャ密度はキューブが増えてもほとんど下がらない（小物は 1〜2 px）。

## 11. 作り込みの手順（おすすめ）

1. `s.frame7()` だけでプレビュー → 目盛りと水色の線（バニラの体）で大きさを掴む。
2. シルエットの大物: 兜（`A.HEAD_*` の箱に収める）→ 胸（上が広い。`A.CHEST_W` 9.2〜10.5）→ 肩当て（外は ±8.0〜8.8）→
   腰（くびれは見せる）→ 腿・脛・サバトン → 篭手。ここで正面・側面の絵を見て、7 頭身に見えるか確かめる。
3. 層: 下の板 → 一回り小さい上の板（色違い）→ 金の縁 → 発光線 → リベット・センサー。
4. 関節を見せる: 肘・膝・足首のドラムは隠さない。その横にピストン、膝裏・ふくらはぎ・腰の脇は骨格が見える隙間を残す。
5. 背中（三人称ではいつも見える）: バックパック・スラスター（fx_thrust）・スリット・ボルト・ホース・マント。
6. 惑星の意匠（環・衛星・光輪・翼・炎）は extra_* / fx_spin_* / ornament で。
7. `check_astro_suits.py` → 数字を見て直す → 近接の絵で細部を見る → 組み上がりと一人称を確かめる。

## 12. よくある落とし穴

* **手足のピボットより上の部品は、手足が回ると大きく振れる**: 腕のピボットは (-5, 22, 0)、脚は (±1.9, 12, 0)。
  肩関節の球（y 24.4）・腿の上端（〜15.7）・肩当ては腕／脚と一緒にピボットの周りを回る（前へ 60° 振ると肩の球は
  後ろへ 2 ずれる）。**ピボットより上に出す物は小さくまとめ、肩当て（腕に付く）・骨盤と草摺（胴に付く）の内側に隠す**。
  腿の上端を太くしたり、腕の付け根に大きな板を付けると、歩くだけで胴を突き抜ける。
* 腕を横に 90° 上げる（T ポーズ）と、ピボットより上の肩の球と肩当ては胴の方へ回り込む。これは骨格の制約（避けられない）。
* **腰の装甲で腿の前を覆わない**: 前垂れは細く（幅 2 前後）、草摺は横に。腿の前が股の上まで見えないと
  「見えている脚」が NG。長いスカート（金星の花弁など）は extra_* にして揺らす（計測から外れる）か、前を割る。
* **頭を大きくしない**: 頭の幅 5.4・高さ H/7（≈ 4.6）。耳・頬当ての張り出しも幅に入る。角・鶏冠・アンテナは
  `ornament=True` のボーンへ（入れたままだと背丈と頭の高さが NG）。兜の下端（顎・しころ）は y 27.3 より上に。
* 0.15 未満の辺は作らない（`octa` の長さ 0.22 以下・`bevel` の cut が大きすぎる時にできる。検査が NG にする）。
* **Z ファイト**: 同じ平面に色の違う面が重なるとちらつく → 0.04 以上ずらす（`stick` の sink、`octa` は自動）。
* 中央の部品の左右対称を忘れる → `mirror_x`。`_r` ボーンの中身は鏡映されるので mirror_x しない。
* マント（extra）とスラスターの炎・推進剤タンクの位置関係: マントは thrust/sprint で後ろへ 25〜35° はね上がる。
  バックパックの横の物は x をずらしてマントの軌跡に入れない。
* 一人称では **腕（rightArm / leftArm の下）だけ** が見え、画面の右下に篭手と拳が少し出る（バニラの腕と同じ場所）。
  肩当てや篭手に大きな板を付けすぎると画面を塞ぐので「一人称」の絵を確かめる。
* 衛星・環（fx_spin）の軌道が肩当てに当たる → 検査の警告（6 秒回して調べる）を見て軌道か装甲をずらす。
* 発光ラインを白い板に置くと白飛びする → 青・暗い板に置く。
* `fx_thrust_*` の炎は局所 -Y に伸ばして作り、向きはボーンの rotation で。
