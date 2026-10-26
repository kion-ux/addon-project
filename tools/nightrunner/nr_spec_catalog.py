# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — カタログ（ゾンビ以外の全登録データ）。

`nr_spec.py` がこのモジュールと `nr_spec_zombies.py` を再輸出する。**名前（日英）・数値・見た目の説明はここが正**。
約束事は `tools/nightrunner/DESIGN.md`（ID の形・ゴアの状態・ファイルの持ち主）。

このファイルはデータだけ（生成器の副作用なし）。中身:

| 表 | 使う生成器 |
|---|---|
| `SURFACES` | 見た目の説明で使う素材（塗りの系統と基準色）。`nr_paint` の塗り分けの手がかり |
| `MATERIAL_ITEMS` | **共有アイテム 23 種**（素材・戦利品・回復・弾）。ゾンビのルートもここの ID だけを使う |
| `ITEMS` | 共有以外のアイテム（ブースター・食べ物・道具・修理キット） |
| `WEAPONS` / `PROJECTILES` / `MODS` | 武器 38 種・飛び道具エンティティ・武器の改造 |
| `TRAPS` / `BLOCKS` / `PROPS` | 罠・カスタムブロック・小道具エンティティ（車など） |
| `LOOT_TABLES` | 箱・車のトランク・建物のルート |
| `STRUCTURES` / `CITY` / `MARKER_KINDS` | 街の建物モジュールと街区の組み立て |
| `SKILLS` / `PROGRESSION` | パルクールと戦闘のスキルツリー、経験値 |
| `PARKOUR_TUNING` / `COMBAT_TUNING` / `GORE_TUNING` | 動き・戦闘・ゴアの数値 |
| `SETTINGS_DEFAULTS` / `SETTINGS_SCHEMA` / `DIFFICULTY` | 設定（ゴアレベル 0〜100、既定 100）と難易度 |
| `CRAFTING` | 生存者の端末（独自 UI）で作るレシピ |
| `ANIM_SETS` / `PLAYER_MOTIONS` | プレイヤーの武器モーションとパルクールのモーション名 |

座標の約束（見た目の説明 `model` の部品 `P(...)`）:

* 大きさは**人の体に合わせる**: 身長 180cm = 32 単位（`tools/rig.py` と同じ）→ **1 単位 ≒ 5.6cm**、
  1 m ≒ 17.8 単位。武器は手に持って読めるよう実寸の 1.1〜1.2 倍に誇張済みの数字を書いている。
* **武器空間**: 原点 = 利き手の拳の中心（握り）、**-Z = 刃先・銃口の向く前**、+Y = 上。
  刃物の切れる側（刃）は **-Y**、峰は +Y。斧・ハンマーの頭は -Y 側へ張り出す。
  両手武器の二つ目の握りは `grips` の z（左手）。
* **ブロック空間**: 原点 = ブロックの底面中央、x・z は -8〜8、y は 0〜16（ピクセル）。
  モデル全体が **30×30×30 px 以内**、かつ 1 px 以上が自分のマス内（wiki.bedrock.dev の block-components#geometry）。
  当たり箱は 1 個、`origin + size` が `[8, 16, 8]` 以内（高さ 24 は format 1.21.130 以降なので使わない）。
* **小道具空間**: 原点 = 地面の中央、**-Z = 車の前**、+Y = 上。大きさは人の体と同じ縮尺（1 m ≒ 17.8 単位）。
  当たりはバリアブロック（`barrier`: 足元からの矩形 `[x0, z0, x1, z1, 高さ]`、ブロック単位、原点のマスが 0）。

部品 `P(name, size, at, mat, note, rot=None, rep=None)`:
`size` = (x, y, z) の大きさ、`at` = 中心の座標、`mat` = `SURFACES` のキー、`note` = 作り込みの指示（日本語）、
`rot` = 中心まわりの回転（度、Bedrock の XYZ）、`rep` = 同じ部品を置く**追加の**中心座標（ボルト・釘・車輪など）。
回転は目安。生成器は形が読めるように調整してよい（大きさ・素材・部品の有無は守る）。

レシピ `shaped(...)` / `shapeless(...)` は作業台（`crafting_table`）用。生存者の端末と作業台ブロック
`nr:crafting_bench` で作るものは `CRAFTING`。ID は全部フル ID（`nr:...` / `minecraft:...`）で書く。

`python3 tools/nightrunner/nr_spec_catalog.py` で自己検査（キーの重複・参照切れ・レシピ・寸法の上限）。
"""
from __future__ import annotations

import re

# ===========================================================================
#  部品・レシピの補助
# ===========================================================================


def P(name, size, at, mat, note="", rot=None, rep=None):
    """見た目の部品（モデラー向け）。単位・座標は上の docstring。"""
    d = {"name": name, "size": tuple(float(v) for v in size),
         "at": tuple(float(v) for v in at), "mat": mat, "note": note}
    if rot is not None:
        d["rot"] = tuple(float(v) for v in rot)
    if rep:
        d["rep"] = [tuple(float(v) for v in r) for r in rep]
    return d


def shaped(pattern, keys, count=1):
    """作業台の形のあるレシピ。pattern は 1〜3 行・同じ幅、keys は {文字: フル ID}。"""
    return {"type": "shaped", "pattern": list(pattern), "keys": dict(keys), "count": count}


def shapeless(ingredients, count=1):
    """作業台の形のないレシピ。ingredients は [(フル ID, 個数), ...]（合計 9 個まで）。"""
    return {"type": "shapeless", "ingredients": [(i, n) for i, n in ingredients], "count": count}


def nid(key: str) -> str:
    return "nr:" + key


# ===========================================================================
#  素材（見た目の説明で使う塗りの系統）。rgb は基準色。nr_paint はこれに汚れ・錆・血を重ねる
# ===========================================================================
SURFACES = {
    # 金属
    "steel_clean":   dict(ja="研いだ鋼", rgb=(196, 202, 206), note="刃の研ぎ跡。細い横線の筋、強いハイライト"),
    "steel_worn":    dict(ja="使い込んだ鋼", rgb=(148, 152, 154), note="細かい擦り傷・指紋の曇り・点錆"),
    "steel_rusty":   dict(ja="錆びた鋼", rgb=(126, 82, 54), note="橙〜焦げ茶の錆の斑、剥がれた塗装の縁"),
    "steel_dark":    dict(ja="黒染めの鋼", rgb=(56, 58, 62), note="パーカライジングの梨地、角だけ擦れて銀"),
    "steel_painted": dict(ja="塗装鋼板", rgb=(120, 124, 120), note="車体・標識。塗装の欠け・下地の錆"),
    "iron_cast":     dict(ja="鋳鉄", rgb=(72, 72, 74), note="ざらついた鋳肌、角に赤錆"),
    "chrome":        dict(ja="クロムめっき", rgb=(214, 218, 224), note="鏡面。くすみと点錆、映り込みの帯"),
    "aluminium":     dict(ja="アルミ", rgb=(178, 182, 186), note="ヘアライン、白い酸化"),
    "brass":         dict(ja="真鍮", rgb=(178, 142, 66), note="薬莢・金具。緑青のくすみ"),
    "copper_wire":   dict(ja="銅線", rgb=(186, 106, 60), note="巻いた銅線・むき出しの導線"),
    "rebar":         dict(ja="鉄筋", rgb=(96, 72, 58), note="節（リブ）の斜線、赤錆とコンクリの粉"),
    "chainlink":     dict(ja="金網", rgb=(150, 156, 156), note="菱形の網目（透過テクスチャ）"),
    # 木
    "wood_old":      dict(ja="古い木", rgb=(124, 94, 64), note="木目・割れ・黒ずんだ手垢"),
    "wood_dark":     dict(ja="濃い木", rgb=(80, 58, 42), note="銃床・柄。油の艶、打痕"),
    "wood_raw":      dict(ja="白木", rgb=(178, 142, 98), note="新しい切り口、ささくれ"),
    "plywood":       dict(ja="合板", rgb=(188, 158, 112), note="積層の縞が木口に見える、水染み"),
    "wood_painted":  dict(ja="塗装木材", rgb=(150, 42, 34), note="剥げた赤ペンキ（消防斧の柄など）"),
    # 樹脂・ゴム・布
    "rubber_black":  dict(ja="黒ゴム", rgb=(30, 30, 32), note="タイヤ・グリップ。溝と擦り減り"),
    "plastic_black": dict(ja="黒樹脂", rgb=(42, 42, 46), note="グリップの格子模様、成形の継ぎ目"),
    "plastic_orange": dict(ja="橙の樹脂", rgb=(232, 112, 32), note="コーン・柵。色褪せと泥"),
    "plastic_yellow": dict(ja="黄の樹脂", rgb=(232, 192, 44), note="警告色。黒い縞と組み合わせる"),
    "plastic_white": dict(ja="白の樹脂", rgb=(222, 222, 214), note="黄ばみ・ひび"),
    "plastic_red":   dict(ja="赤の樹脂", rgb=(176, 32, 30), note="燃料缶・テールランプの外枠"),
    "plastic_blue":  dict(ja="青の樹脂", rgb=(40, 84, 160), note="ブルーシート・ゴミ箱"),
    "tape_grey":     dict(ja="ダクトテープ", rgb=(152, 152, 148), note="布目、端のめくれ、重ね巻きの段差"),
    "tape_black":    dict(ja="黒いビニールテープ", rgb=(26, 26, 28), note="艶、巻きの段差"),
    "cloth_rag":     dict(ja="汚れた布", rgb=(142, 126, 102), note="ほつれ・染み・焦げ"),
    "cloth_red":     dict(ja="赤い布", rgb=(140, 30, 28), note="目印の布切れ"),
    "leather_brown": dict(ja="茶革", rgb=(102, 66, 40), note="ひび割れ、縫い目"),
    "paracord":      dict(ja="パラコード", rgb=(92, 98, 62), note="編み目の斜線"),
    "rope":          dict(ja="麻縄", rgb=(162, 138, 96), note="撚りの斜線、毛羽"),
    "burlap":        dict(ja="麻袋", rgb=(170, 150, 108), note="粗い織り目、縫い目、湿った下側"),
    "trash_bag":     dict(ja="ゴミ袋", rgb=(24, 24, 30), note="艶のある皺、破れ目から中身"),
    "tarp_blue":     dict(ja="ブルーシート", rgb=(36, 82, 148), note="折り目・ハトメ"),
    "cardboard":     dict(ja="段ボール", rgb=(172, 132, 82), note="波板の断面、湿った染み"),
    # 石・道路
    "concrete":      dict(ja="コンクリート", rgb=(152, 152, 146), note="気泡の点、型枠の跡、ひび"),
    "concrete_dark": dict(ja="汚れたコンクリ", rgb=(96, 96, 92), note="煤・苔・雨垂れの縦筋"),
    "asphalt":       dict(ja="アスファルト", rgb=(52, 52, 56), note="砂利の粒、白線の剥げ"),
    "brick_red":     dict(ja="赤レンガ", rgb=(142, 66, 50), note="目地、欠け"),
    # ガラス・灯り（emissive_* は発光マテリアル）
    "glass_clear":   dict(ja="ガラス", rgb=(176, 206, 216), note="半透明。汚れと雨染み"),
    "glass_broken":  dict(ja="割れたガラス", rgb=(150, 182, 192), note="放射状のひび・抜けた穴（透過）"),
    "glass_tinted":  dict(ja="色付きガラス", rgb=(52, 62, 70), note="車の後部窓"),
    "emissive_white": dict(ja="白い光", rgb=(255, 246, 220), note="ヘッドライト・街灯（発光）"),
    "emissive_amber": dict(ja="橙の光", rgb=(255, 170, 60), note="ウインカー・炎（発光）"),
    "emissive_red":  dict(ja="赤い光", rgb=(255, 40, 30), note="テールランプ・警告灯（発光）"),
    "emissive_blue": dict(ja="青い光", rgb=(60, 120, 255), note="パトライト（発光）"),
    "emissive_uv":   dict(ja="UV の光", rgb=(160, 80, 255), note="紫外線ランプ・UV キノコ（発光）"),
    "emissive_green": dict(ja="緑の画面", rgb=(90, 255, 150), note="端末の画面（発光）"),
    # 車の塗装
    "paint_white":   dict(ja="白い塗装", rgb=(214, 214, 206), note="救急車・バン。黄ばみ・泥はね"),
    "paint_black":   dict(ja="黒い塗装", rgb=(28, 30, 34), note="パトカーの黒。艶の残り"),
    "paint_red":     dict(ja="赤い塗装", rgb=(150, 30, 28), note="セダンの赤。色褪せ・錆"),
    "paint_blue":    dict(ja="青い塗装", rgb=(44, 72, 118), note="セダン・バス"),
    "paint_yellow":  dict(ja="黄色い塗装", rgb=(226, 176, 36), note="タクシー・バスの帯"),
    "paint_olive":   dict(ja="オリーブドラブ", rgb=(84, 90, 58), note="軍用車。白いステンシル文字"),
    "paint_green":   dict(ja="緑の塗装", rgb=(52, 104, 62), note="ゴミ収集車・大型ゴミ箱"),
    "paint_orange":  dict(ja="橙の塗装", rgb=(196, 92, 34), note="コンテナ。波板の陰影"),
    "paint_burnt":   dict(ja="焼けた塗装", rgb=(44, 38, 36), note="炭化・白い灰・虹色の焼け"),
    "decal_stripe":  dict(ja="反射帯", rgb=(230, 220, 60), note="救急車・パトカーのチェッカー帯"),
    # 体・ゴア（nr_paint の cut_flesh / bone / gore_wet と同じ系統）
    "blood_wet":     dict(ja="濡れた血", rgb=(112, 6, 8), note="艶、垂れ、縁が黒い"),
    "blood_dry":     dict(ja="乾いた血", rgb=(72, 14, 10), note="茶黒の固まり、擦れ"),
    "gore_meat":     dict(ja="肉片", rgb=(152, 40, 40), note="筋の繊維、脂肪の黄"),
    "bone":          dict(ja="骨", rgb=(228, 216, 190), note="割れた断面、骨髄の赤"),
    "mutated":       dict(ja="変異組織", rgb=(120, 150, 70), note="脈打つ瘤、黄緑の膿、菌糸"),
    "fungus_uv":     dict(ja="UV キノコ", rgb=(150, 96, 230), note="傘の裏のひだが発光"),
    "fuel":          dict(ja="燃料・油", rgb=(40, 34, 26), note="虹色の油膜"),
    "paper":         dict(ja="紙", rgb=(214, 206, 180), note="印刷・皺・染み"),
}

# ===========================================================================
#  ゴアの状態（DESIGN.md §3 の enum と同じ。変えるときは DESIGN.md から）
# ===========================================================================
HEAD_STATES = ("intact", "wounded", "jawless", "cracked", "severed", "crushed")
LIMB_STATES = ("intact", "wounded", "broken", "cut_lower", "cut_upper")
TORSO_STATES = ("intact", "slashed", "gutted", "halved")
GORE_PARTS = {"head": HEAD_STATES, "arm": LIMB_STATES, "leg": LIMB_STATES, "torso": TORSO_STATES}

DTYPES = ("slash", "blunt", "pierce", "blast", "fire", "shock", "toxic")
# 効果の種別（DTYPES ＋ UV）。UV はゾンビの resist.uv で効きが決まる（昼の感染者 0、夜の捕食者に大）
EFFECT_DTYPES = DTYPES + ("uv",)
WEIGHTS = ("light", "medium", "heavy")

# ダメージ種別ごとに起こりうる結果（DESIGN.md §4 の表）。武器の sever_bias・罠の gore はこの中から選ぶ。
# pierce の切断は「散弾・大口径の至近距離」だけ（spec では gore_power >= 0.85 の武器に限る）
DTYPE_OUTCOMES = {
    "slash":  {"head": ("wounded", "jawless", "severed"), "arm": ("wounded", "cut_lower", "cut_upper"),
               "leg": ("wounded", "cut_lower", "cut_upper"), "torso": ("slashed", "gutted", "halved")},
    "blunt":  {"head": ("wounded", "cracked", "crushed"), "arm": ("wounded", "broken"),
               "leg": ("wounded", "broken"), "torso": ()},
    "pierce": {"head": ("wounded", "cracked", "crushed"), "arm": ("wounded", "cut_lower"),
               "leg": ("wounded", "cut_lower"), "torso": ("slashed",)},
    "blast":  {"head": ("crushed",), "arm": ("cut_upper",), "leg": ("cut_upper",), "torso": ("halved", "gutted")},
    "fire":   {"head": (), "arm": (), "leg": (), "torso": ()},
    "shock":  {"head": (), "arm": (), "leg": (), "torso": ()},
    "toxic":  {"head": (), "arm": (), "leg": (), "torso": ()},
    "uv":     {"head": (), "arm": (), "leg": (), "torso": ()},
}

# ===========================================================================
#  レア度（説明文の色・能力の倍率・改造の枠）
# ===========================================================================
RARITY = {
    "common":    dict(ja="ありふれた", en="Common", color="§f", rgb=(214, 214, 214), stat_mult=1.00, mod_slots=1),
    "uncommon":  dict(ja="良質な", en="Uncommon", color="§a", rgb=(96, 220, 96), stat_mult=1.08, mod_slots=1),
    "rare":      dict(ja="希少な", en="Rare", color="§9", rgb=(80, 140, 255), stat_mult=1.16, mod_slots=2),
    "epic":      dict(ja="傑作", en="Epic", color="§5", rgb=(176, 90, 230), stat_mult=1.25, mod_slots=2),
    "legendary": dict(ja="伝説の", en="Legendary", color="§6", rgb=(255, 170, 40), stat_mult=1.35, mod_slots=3),
}

# ===========================================================================
#  プレイヤーのモーション（animation.nr.p.<名前>。gen_nr_player_anim がこの名前で全部作る）
#  近接の各振り: (名前, 振りかぶり tick, 当たる tick, 終わり tick, 軌道)
#  軌道: r2l 右から左 / l2r 左から右 / down 振り下ろし / up 振り上げ / thrust 突き / spin 回転
# ===========================================================================
ANIM_SETS = {
    "slash_1h": dict(ja="片手の刃", swings=[("slash_1h_a", 3, 5, 10, "r2l"), ("slash_1h_b", 3, 5, 10, "l2r"),
                                          ("slash_1h_c", 4, 6, 12, "down")],
                     heavy=("slash_1h_heavy", 10, 13, 22, "r2l"), idle="hold_1h", sprint="sprint_1h"),
    "slash_2h": dict(ja="両手の刃", swings=[("slash_2h_a", 6, 9, 17, "r2l"), ("slash_2h_b", 6, 9, 17, "l2r"),
                                          ("slash_2h_c", 8, 11, 20, "down")],
                     heavy=("slash_2h_heavy", 14, 18, 30, "spin"), idle="hold_2h", sprint="sprint_2h"),
    "blunt_1h": dict(ja="片手の打撃", swings=[("blunt_1h_a", 4, 6, 12, "r2l"), ("blunt_1h_b", 4, 6, 12, "l2r"),
                                            ("blunt_1h_c", 5, 8, 14, "down")],
                     heavy=("blunt_1h_heavy", 11, 14, 24, "down"), idle="hold_1h", sprint="sprint_1h"),
    "blunt_2h": dict(ja="両手の打撃", swings=[("blunt_2h_a", 8, 11, 20, "r2l"), ("blunt_2h_b", 9, 12, 22, "down")],
                     heavy=("blunt_2h_heavy", 16, 20, 34, "down"), idle="hold_2h", sprint="sprint_2h"),
    "stab":     dict(ja="突き", swings=[("stab_a", 3, 5, 11, "thrust"), ("stab_b", 3, 5, 11, "thrust"),
                                       ("stab_c", 5, 7, 14, "r2l")],
                     heavy=("stab_heavy", 10, 13, 24, "thrust"), idle="hold_spear", sprint="sprint_2h"),
    "bow":      dict(ja="弓", draw="bow_draw", hold="bow_hold", release="bow_release", idle="hold_bow"),
    "crossbow": dict(ja="クロスボウ", aim="crossbow_aim", fire="crossbow_fire", reload="crossbow_reload",
                     idle="hold_rifle"),
    "pistol":   dict(ja="拳銃", aim="pistol_aim", fire="pistol_fire", reload="pistol_reload", idle="hold_pistol"),
    "rifle":    dict(ja="長物の銃", aim="rifle_aim", fire="rifle_fire", reload="rifle_reload",
                     cycle="rifle_bolt", idle="hold_rifle"),
    "shotgun":  dict(ja="散弾銃", aim="shotgun_aim", fire="shotgun_fire", reload="shotgun_reload",
                     cycle="shotgun_pump", idle="hold_rifle"),
    "throw":    dict(ja="投擲", wind="throw_wind", release="throw_release", idle="hold_1h"),
}

# パルクール・素手の動き（parkour.js が playAnimation で呼ぶ）
PLAYER_MOTIONS = {
    "climb": "壁登り（両手を交互に上へ）", "ledge_hang": "縁にぶら下がる", "ledge_pullup": "縁からよじ登る",
    "vault_low": "低い障害物を片手で飛び越える", "vault_high": "2 段の障害物を両手で押して越える（スピードヴォルト）",
    "wallrun_r": "右の壁を走る", "wallrun_l": "左の壁を走る", "walljump": "壁を蹴って跳ぶ",
    "slide": "スライディング", "slide_tackle": "スライディングで足を払う", "roll": "受け身の前転",
    "land_hard": "着地の衝撃で膝をつく", "dropkick": "空中のドロップキック", "kick": "前蹴り",
    "stomp": "倒れた敵を踏み潰す", "grapple_fire": "鉤縄を撃つ", "grapple_pull": "鉤縄で引かれて飛ぶ",
    "glide": "パラグライダーで滑空", "glide_open": "パラグライダーを開く", "parry": "受け流し",
    "dodge_l": "左へ回避", "dodge_r": "右へ回避", "use_heal": "包帯・救急キットを使う",
    "use_inject": "注射（ブースター・免疫・抑制剤）", "uv_raise": "UV ライトを掲げる", "grabbed": "掴まれて振りほどく",
    "lockpick": "鍵開け", "ground_pound": "空中から叩きつける",
}

# 効果音の分類（キーは nr.<分類>.<名前>）と、このカタログが要る名前は required_sounds() で集める
SFX_SETS = {
    "blade_light":  dict(swing="nr.w.swing_light", hit="nr.gore.slice", heavy="nr.w.swing_heavy", wall="nr.w.hit_metal"),
    "blade_heavy":  dict(swing="nr.w.swing_heavy", hit="nr.gore.chop", heavy="nr.w.swing_heavy", wall="nr.w.hit_metal"),
    "blunt_light":  dict(swing="nr.w.swing_light", hit="nr.gore.thud", heavy="nr.w.swing_heavy", wall="nr.w.hit_wood"),
    "blunt_heavy":  dict(swing="nr.w.swing_heavy", hit="nr.gore.smash", heavy="nr.w.swing_heavy", wall="nr.w.hit_metal"),
    "pierce":       dict(swing="nr.w.swing_light", hit="nr.gore.stab", heavy="nr.w.swing_heavy", wall="nr.w.hit_wood"),
    "bow":          dict(draw="nr.w.bow_draw", fire="nr.w.bow_release", hit="nr.gore.stab"),
    "crossbow":     dict(draw="nr.w.crossbow_reload", fire="nr.w.crossbow_fire", hit="nr.gore.stab"),
    "pistol":       dict(fire="nr.gun.pistol", reload="nr.gun.reload_mag", empty="nr.gun.empty", hit="nr.gore.bullet"),
    "revolver":     dict(fire="nr.gun.revolver", reload="nr.gun.reload_revolver", empty="nr.gun.empty",
                         hit="nr.gore.bullet"),
    "shotgun":      dict(fire="nr.gun.shotgun", reload="nr.gun.reload_shell", cycle="nr.gun.pump",
                         empty="nr.gun.empty", hit="nr.gore.bullet"),
    "rifle":        dict(fire="nr.gun.rifle", reload="nr.gun.reload_mag", cycle="nr.gun.bolt",
                         empty="nr.gun.empty", hit="nr.gore.bullet"),
    "smg":          dict(fire="nr.gun.smg", reload="nr.gun.reload_mag", empty="nr.gun.empty", hit="nr.gore.bullet"),
    "throw":        dict(throw="nr.w.throw", hit="nr.w.hit_metal"),
}


# ===========================================================================
#  アイテムの共通の形
# ===========================================================================
def _item(key, ja, en, kind, stack=64, rarity="common", icon="", desc_ja="", desc_en="",
          use=None, recipe=None, **extra):
    d = dict(key=key, id=nid(key), ja=ja, en=en, kind=kind, stack=stack, rarity=rarity, icon=icon,
             desc_ja=desc_ja, desc_en=desc_en, use=use, recipe=recipe)
    d.update(extra)
    return d


# ===========================================================================
#  共有アイテム（素材・戦利品・回復・弾・紙幣）— 両方の spec がこの 23 個の ID だけを使う
# ===========================================================================
SHARED_ITEM_IDS = (
    "nr:scrap", "nr:rags", "nr:alcohol", "nr:chemicals", "nr:blades", "nr:duct_tape", "nr:battery",
    "nr:gunpowder_pouch", "nr:mutated_tissue", "nr:infected_trophy", "nr:volatile_trophy", "nr:apex_trophy",
    "nr:inhibitor", "nr:uv_shroom", "nr:bandage", "nr:medkit", "nr:immunity_booster", "nr:ammo_pistol",
    "nr:ammo_shotgun", "nr:ammo_rifle", "nr:bolt", "nr:survivor_arrow", "nr:money",
)

MATERIAL_ITEMS = [
    _item("scrap", "金属くず", "Scrap Metal", "material", 64,
          icon="曲がった鋼板の切れ端 2 枚と六角ボルト 1 本が重なった山。縁は赤錆、片方に剥げた青い塗装",
          desc_ja="武器・弾・罠の基本の材料。車や機械を叩けば出てくる。",
          desc_en="Basic material for weapons, ammo and traps. Smash cars and machines to find it."),
    _item("rags", "布切れ", "Rags", "material", 64,
          icon="結んだ灰色と生成りの布の束。ほつれた端、茶色い染み",
          desc_ja="包帯・火炎瓶・パラグライダーに使う。",
          desc_en="Used for bandages, molotovs and paragliders."),
    _item("alcohol", "アルコール", "Alcohol", "material", 32,
          icon="茶色のガラス瓶。手書きの白いラベル「消毒用」、コルク栓、瓶の肩に光の筋",
          desc_ja="消毒と燃料に。火炎瓶・救急キット・火炎の改造の材料。",
          desc_en="For disinfecting and burning. Used in molotovs, medkits and fire mods."),
    _item("chemicals", "化学薬品", "Chemicals", "material", 32,
          icon="白い樹脂のポリ容器。黄色い危険表示の菱形ラベル、青いキャップ、垂れた緑の液",
          desc_ja="薬・毒の改造・爆薬の材料。病院や倉庫で見つかる。",
          desc_en="For medicine, toxic mods and explosives. Found in clinics and warehouses."),
    _item("blades", "刃の破片", "Blade Fragments", "material", 64,
          icon="折れたカッターの刃・鋸の歯・包丁の先が 3 枚、扇形に重なる。刃先に光",
          desc_ja="刃物・投げナイフ・出血の改造の材料。",
          desc_en="For blades, throwing knives and bleed mods."),
    _item("duct_tape", "ダクトテープ", "Duct Tape", "material", 32,
          icon="銀灰色のダクトテープのロール。端がめくれて垂れている、芯は茶色の紙",
          desc_ja="何でも直す。武器の補修と改造の留め具。",
          desc_en="Fixes everything. Holds weapon repairs and mods together."),
    _item("battery", "電池", "Battery", "material", 32,
          icon="単一電池 2 本をテープで束ね、赤と黒の導線が出ている。片方は錆びた端子",
          desc_ja="感電の改造・UV ライト・電気トラップの電源。",
          desc_en="Powers shock mods, UV lights and electric traps."),
    _item("gunpowder_pouch", "火薬袋", "Gunpowder Pouch", "material", 32,
          icon="口を紐で縛った麻の小袋。黒い粉がこぼれ、赤い「火気厳禁」の判",
          desc_ja="弾と爆発物の材料。",
          desc_en="For ammo and explosives."),
    _item("mutated_tissue", "変異組織", "Mutated Tissue", "material", 32, rarity="uncommon",
          icon="脈打つ黄緑の瘤が付いた肉片。表面に菌糸の白い筋、ぬめる艶",
          desc_ja="特殊感染者から取れる。ブースターと毒の改造の材料。",
          desc_en="Harvested from special infected. Used in boosters and toxic mods."),
    _item("infected_trophy", "感染者の戦利品", "Infected Trophy", "trophy", 16, rarity="uncommon",
          icon="歯の並んだ下顎の骨に、名札のプラスチック片を針金で留めたもの",
          desc_ja="手強い感染者の証。強い改造と武器の材料。",
          desc_en="Proof of a tough kill. Needed for strong mods and weapons."),
    _item("volatile_trophy", "ボラタイルの戦利品", "Volatile Trophy", "trophy", 16, rarity="rare",
          icon="裂けた顎と長い牙、紫に光る神経の束が付いた夜の捕食者の頭骨の欠片",
          desc_ja="夜の捕食者の牙。UV の装備と上位の改造に使う。",
          desc_en="A night predator's fang. Used for UV gear and top-tier mods."),
    _item("apex_trophy", "頂点の戦利品", "Apex Trophy", "trophy", 16, rarity="legendary",
          icon="巨大な脊椎の一節に赤黒い結晶状の変異が生え、内側から橙に脈打つ",
          desc_ja="ボスを倒した者だけが持つ。伝説の武器と抑制剤の材料。",
          desc_en="Only boss-slayers carry one. For legendary weapons and inhibitors."),
    _item("inhibitor", "抑制剤", "Inhibitor", "consumable", 16, rarity="epic",
          icon="青く光る液の入ったガラスの注射器。銀の留め具、黒い目盛り、針に保護キャップ",
          desc_ja="打つと感染を押し戻し、最大体力か最大スタミナが永久に上がる（端末で選ぶ）。",
          desc_en="Pushes the infection back. Permanently raises max health or max stamina (choose in the terminal).",
          use=dict(type="inhibitor", use_ticks=30, max_health_add=2, max_health_cap=20,
                   max_stamina_add=10, max_stamina_cap=100, anim="use_inject", sound="nr.ui.inject")),
    _item("uv_shroom", "UV キノコ", "UV Shroom", "consumable", 32, rarity="uncommon",
          icon="傘の裏が紫に光るひょろ長いキノコ 2 本、根元に湿った土",
          desc_ja="食べると免疫が少し戻る。免疫ブースターと UV 装備の材料。",
          desc_en="Eat to regain some immunity. Ingredient for immunity boosters and UV gear.",
          use=dict(type="immunity", use_ticks=16, immunity_s=45, food=1, anim="use_heal", sound="nr.ui.eat")),
    _item("bandage", "包帯", "Bandage", "consumable", 16,
          icon="巻いた白い包帯と、端を留める安全ピン。うっすら血の染み",
          desc_ja="体力を少し回復し、出血を止める。",
          desc_en="Restores a little health and stops bleeding.",
          use=dict(type="heal", use_ticks=20, heal=6, over_ticks=30, cure=["bleed"], anim="use_heal",
                   sound="nr.ui.bandage"),
          recipe=shapeless([("nr:rags", 2), ("nr:alcohol", 1)], count=2)),
    _item("medkit", "救急キット", "Medkit", "consumable", 8, rarity="uncommon",
          icon="白い十字の付いた赤い樹脂の救急箱。留め金が片方外れ、包帯がはみ出す",
          desc_ja="体力を大きく回復し、しばらく再生する。",
          desc_en="Restores a lot of health and regenerates for a while.",
          use=dict(type="heal", use_ticks=40, heal=16, over_ticks=20, regen_ticks=200, regen_amp=0,
                   cure=["bleed", "poison"], anim="use_heal", sound="nr.ui.medkit"),
          recipe=shaped(["RAR", "CBC"], {"R": "nr:rags", "A": "nr:alcohol", "C": "nr:chemicals",
                                          "B": "nr:bandage"})),
    _item("immunity_booster", "免疫ブースター", "Immunity Booster", "consumable", 8, rarity="uncommon",
          icon="紫の液のアンプル。白いラベルに UV の記号、銀のキャップ",
          desc_ja="打つと免疫の残り時間が大きく戻り、しばらく減らない。",
          desc_en="Restores a large amount of immunity and pauses its drain for a while.",
          use=dict(type="immunity", use_ticks=24, immunity_s=180, pause_s=30, anim="use_inject",
                   sound="nr.ui.inject")),
    _item("ammo_pistol", "拳銃弾", "Pistol Ammo", "ammo", 64,
          icon="真鍮の薬莢の拳銃弾 5 発を斜めに並べる。1 発は弾頭が鉛色",
          desc_ja="拳銃・リボルバー・手製サブマシンガンの弾。",
          desc_en="Ammo for pistols, revolvers and the scrap SMG."),
    _item("ammo_shotgun", "散弾", "Shotgun Shells", "ammo", 32,
          icon="赤い樹脂の散弾実包 3 本、真鍮の底。1 本は口が開いて粒が見える",
          desc_ja="散弾銃の弾。",
          desc_en="Shells for shotguns."),
    _item("ammo_rifle", "ライフル弾", "Rifle Ammo", "ammo", 32,
          icon="細長い真鍮のライフル弾 3 発、銅の尖った弾頭",
          desc_ja="狩猟用ライフルの弾。",
          desc_en="Ammo for the hunting rifle."),
    _item("bolt", "ボルト", "Crossbow Bolt", "ammo", 32,
          icon="短く太い金属の矢。三枚の樹脂の羽根、研いだ鉄筋の先",
          desc_ja="クロスボウの矢。拾い直せる。",
          desc_en="Crossbow ammo. Can be recovered."),
    _item("survivor_arrow", "生存者の矢", "Survivor Arrow", "ammo", 64,
          icon="竹の矢柄に切った樹脂板の羽根、刃の破片を巻き付けた矢じり",
          desc_ja="生存者の弓の矢。拾い直せる。",
          desc_en="Arrows for the survivor bow. Can be recovered.",
          recipe=shaped(["B", "S", "F"], {"B": "nr:blades", "S": "minecraft:stick", "F": "minecraft:feather"},
                        count=6)),
    _item("money", "古い紙幣", "Old Banknotes", "currency", 64,
          icon="輪ゴムで留めた皺だらけの紙幣の束。角が焦げている",
          desc_ja="崩壊前のお金。今は端末の取引と作業台の部品代に使う。",
          desc_en="Pre-fall money. Now used for terminal trades and bench parts."),
]

# ===========================================================================
#  共有以外のアイテム（ブースター・食べ物・道具）
# ===========================================================================
ITEMS = [
    # --- 回復・ブースター -----------------------------------------------------------
    _item("energy_drink", "エナジードリンク", "Energy Drink", "consumable", 16,
          icon="凹んだ黒いアルミ缶に黄緑の稲妻のロゴ、プルタブが開いている",
          desc_ja="スタミナを全快し、30 秒間スタミナの回復が速くなる。",
          desc_en="Fully restores stamina and speeds up stamina recovery for 30 seconds.",
          use=dict(type="stamina", use_ticks=20, stamina=100, regen_mult=1.5, duration_s=30, anim="use_heal",
                   sound="nr.ui.drink")),
    _item("canned_food", "缶詰", "Canned Food", "consumable", 16,
          icon="ラベルが半分剥げた缶詰、ふたが開いて豆が見える。缶切りの跡",
          desc_ja="空腹を満たし、体力を少し戻す。",
          desc_en="Fills hunger and restores a little health.",
          use=dict(type="food", use_ticks=32, food=6, saturation=0.6, heal=2, anim="use_heal",
                   sound="nr.ui.eat")),
    _item("chocolate_bar", "チョコバー", "Chocolate Bar", "consumable", 16,
          icon="赤い包み紙が破れて一口かじられたチョコバー",
          desc_ja="空腹を少し満たし、スタミナを 20 戻す。",
          desc_en="Fills a bit of hunger and restores 20 stamina.",
          use=dict(type="food", use_ticks=16, food=3, saturation=0.3, stamina=20, anim="use_heal",
                   sound="nr.ui.eat")),
    _item("painkillers", "鎮痛剤", "Painkillers", "consumable", 16,
          icon="橙色の薬瓶と白い錠剤 2 粒、ラベルに手書きの×",
          desc_ja="30 秒間、受けるダメージを 20% 減らす。",
          desc_en="Reduces damage taken by 20% for 30 seconds.",
          use=dict(type="buff", use_ticks=16, damage_taken_mult=0.8, duration_s=30, anim="use_heal",
                   sound="nr.ui.pills")),
    _item("fortify_booster", "強化ブースター", "Fortifying Booster", "consumable", 8, rarity="uncommon",
          icon="灰色の液の注射器、黒いゴムの栓に白い盾の印",
          desc_ja="45 秒間、受けるダメージを 30% 減らす。",
          desc_en="Reduces damage taken by 30% for 45 seconds.",
          use=dict(type="buff", use_ticks=24, damage_taken_mult=0.7, duration_s=45, anim="use_inject",
                   sound="nr.ui.inject")),
    _item("champion_booster", "闘士ブースター", "Champion Booster", "consumable", 8, rarity="uncommon",
          icon="赤い液の注射器、黒いゴムの栓に白い拳の印",
          desc_ja="45 秒間、近接ダメージ +30%、部位破壊の確率 +15%。",
          desc_en="+30% melee damage and +15% dismember chance for 45 seconds.",
          use=dict(type="buff", use_ticks=24, melee_damage_mult=1.3, gore_power_add=0.15, duration_s=45,
                   anim="use_inject", sound="nr.ui.inject")),
    _item("hunter_booster", "狩人ブースター", "Hunter Booster", "consumable", 8, rarity="rare",
          icon="緑に光る液の注射器、黒いゴムの栓に白い目の印",
          desc_ja="30 秒間、暗視と、24 ブロック内の感染者が壁越しに光って見える。",
          desc_en="Night vision and infected within 24 blocks glow through walls for 30 seconds.",
          use=dict(type="buff", use_ticks=24, night_vision=True, reveal_radius=24, duration_s=30,
                   anim="use_inject", sound="nr.ui.inject")),
    # --- 道具 ---------------------------------------------------------------------
    _item("grappling_hook", "グラップリングフック", "Grappling Hook", "tool", 1, rarity="rare",
          icon="黒い握りのピストル型の発射器に、三本爪の鉤と巻いた細いワイヤー",
          desc_ja="使うと狙った所へ鉤を撃ち、体ごと引き寄せられる。",
          desc_en="Fire a hook at a surface and get pulled toward it.",
          use=dict(type="grapple", cooldown_ticks=30, range=26, anim="grapple_fire", sound="nr.pk.grapple_fire"),
          model=[P("grip", (1.4, 4.2, 2.2), (0, -1.6, 0.6), "plastic_black", "滑り止めの格子、親指の当たる窪み", rot=(14, 0, 0)),
                 P("body", (1.8, 2.2, 7.0), (0, 0.8, -1.8), "steel_dark", "巻き取り機の箱。側面にねじ 4 本と傷"),
                 P("spool", (2.6, 2.6, 1.4), (0, 0.8, 0.6), "aluminium", "ワイヤーの巻き胴（側面に巻いたワイヤーの縞）"),
                 P("barrel", (1.0, 1.0, 3.0), (0, 1.2, -6.6), "steel_worn", "発射筒"),
                 P("hook_shaft", (0.6, 0.6, 2.2), (0, 1.2, -9.0), "steel_worn", "鉤の軸"),
                 P("hook_claw", (0.4, 1.8, 0.4), (0, 2.0, -10.0), "steel_clean", "三本爪（120 度ずつ回す）",
                   rot=(-35, 0, 0), rep=[(0.8, 0.6, -10.0), (-0.8, 0.6, -10.0)]),
                 P("trigger", (0.4, 0.9, 0.5), (0, -0.4, -0.5), "steel_dark", "引き金"),
                 P("tape", (1.9, 2.3, 0.8), (0, 0.8, -4.2), "tape_grey", "割れを留めたテープ")]),
    _item("paraglider", "パラグライダー", "Paraglider", "tool", 1, rarity="rare",
          icon="継ぎ当てだらけの布の翼を畳んだ背負い袋、黄色い紐と金具",
          desc_ja="空中で使うと翼を開いてゆっくり滑空する。もう一度使うと畳む。",
          desc_en="Use in mid-air to open the wing and glide. Use again to fold it.",
          use=dict(type="glide", min_height=3, anim="glide_open", sound="nr.pk.glide_open"),
          wing_model=[P("canopy_center", (14.0, 1.0, 6.0), (0, 30.0, 0), "tarp_blue", "中央のセル。縫い目と継ぎ当て（布切れ）"),
                      P("canopy_side", (10.0, 1.0, 5.4), (11.0, 27.5, 0.2), "cloth_rag", "左右の翼、外側へ下がる",
                        rot=(0, 0, -18), rep=[(-11.0, 27.5, 0.2)]),
                      P("lines", (0.2, 12.0, 0.2), (5.0, 21.0, 0), "rope", "吊り紐（左右 3 本ずつ）",
                        rot=(0, 0, 14), rep=[(-5.0, 21.0, 0), (7.5, 21.0, 1.5), (-7.5, 21.0, 1.5)]),
                      P("harness_bar", (8.0, 0.6, 0.6), (0, 15.0, 0), "steel_worn", "握りの横棒、黄色いテープ")]),
    _item("uv_flashlight", "UV フラッシュライト", "UV Flashlight", "tool", 1, rarity="rare",
          icon="太い黒い懐中電灯、レンズが紫に光り、側面にテープで留めた電池",
          desc_ja="使うと UV の光を前へ照らす。夜の感染者を怯ませ、焼く。電池が減ると点滅する。",
          desc_en="Shine UV light ahead. Stuns and burns night infected. Flickers when the battery runs low.",
          use=dict(type="uv_light", battery_s=12, recharge_per_s=1.0, cone_range=10, cone_deg=25,
                   stun_ticks=40, uv_dps=3, slow=0.6, anim="uv_raise", sound="nr.ui.uv_on"),
          model=[P("body", (2.0, 2.0, 7.0), (0, 0, -1.0), "aluminium", "黒いアルマイトの胴、滑り止めの刻み"),
                 P("head", (2.8, 2.8, 2.2), (0, 0, -5.4), "plastic_black", "広がったライトの頭"),
                 P("lens", (2.4, 2.4, 0.3), (0, 0, -6.6), "emissive_uv", "紫に光るレンズ、内側に LED の点 7 個"),
                 P("tailcap", (2.2, 2.2, 1.0), (0, 0, 3.0), "steel_dark", "スイッチの尾栓"),
                 P("battery_pack", (1.4, 1.2, 3.0), (0, -1.6, -0.6), "plastic_yellow", "テープで留めた予備電池",),
                 P("tape", (2.2, 2.2, 0.8), (0, -0.3, -0.6), "tape_grey", "電池を留めるテープ")]),
    _item("lockpick", "ロックピック", "Lockpick", "tool", 16,
          icon="曲げた細い金属片 2 本（テンションとピック）を布で巻いた握り",
          desc_ja="鍵の掛かった隠し箱を開ける。失敗すると折れる。",
          desc_en="Opens locked stashes. Breaks if you fail.",
          use=dict(type="lockpick", break_chance=0.25, tries=3, use_ticks=40, anim="lockpick",
                   sound="nr.ui.lockpick"),
          recipe=shaped(["B", "S"], {"B": "nr:blades", "S": "nr:scrap"}, count=2)),
    _item("repair_kit", "修理キット", "Repair Kit", "tool", 8, rarity="uncommon",
          icon="ダクトテープ・ボルト・針金を詰めた小さな工具袋",
          desc_ja="持っている武器の耐久を 35% 戻す（最大値は少し減る）。",
          desc_en="Restores 35% durability to the held weapon (max durability drops a little).",
          use=dict(type="repair", use_ticks=30, restore=0.35, max_loss=0.05, anim="use_heal",
                   sound="nr.ui.repair"),
          recipe=shaped(["SSS", " T "], {"S": "nr:scrap", "T": "nr:duct_tape"})),
    _item("binoculars", "双眼鏡", "Binoculars", "tool", 1, rarity="uncommon",
          icon="塗装の剥げた黒い双眼鏡、首紐が垂れている、片方のレンズにひび",
          desc_ja="覗くと遠くを拡大し、視線の先の感染者に 30 秒の目印を付ける。",
          desc_en="Zoom in and tag the infected you look at for 30 seconds.",
          use=dict(type="zoom", fov=30, mark_s=30, mark_range=96, anim="uv_raise", sound="nr.ui.zoom")),
    _item("survivor_terminal", "生存者の端末", "Survivor Terminal", "tool", 1, rarity="rare",
          icon="ひびの入った頑丈なタブレット、緑の画面に地図と心拍の線、角にテープ",
          desc_ja="使うと端末が開く: 設定（ゴアレベル）・図鑑・クラフト・スキル・操作説明。",
          desc_en="Opens the terminal: settings (gore level), bestiary, crafting, skills and controls.",
          use=dict(type="terminal", anim="uv_raise", sound="nr.ui.open"),
          recipe=shaped(["SGS", "SRS", "SBS"], {"S": "nr:scrap", "G": "minecraft:glass_pane",
                                                 "R": "minecraft:redstone", "B": "nr:battery"})),
]

ITEM_KINDS = ("material", "trophy", "consumable", "ammo", "currency", "tool")


# ===========================================================================
#  武器（ID nr:w_<key>）
#  cls（形の区分）→ kind / hands / anim_set / 既定の改造 は下の表から決める
# ===========================================================================
WEAPON_CLASSES = {
    #  cls               kind         hands  anim_set     改造（既定）
    "one_hand_blade": ("melee",     1, "slash_1h", ("fire", "shock", "bleed", "toxic", "uv")),
    "two_hand_blade": ("melee",     2, "slash_2h", ("fire", "shock", "bleed", "toxic", "uv")),
    "one_hand_blunt": ("melee",     1, "blunt_1h", ("fire", "shock", "toxic", "uv", "impact")),
    "two_hand_blunt": ("melee",     2, "blunt_2h", ("fire", "shock", "toxic", "uv", "impact")),
    "spear":          ("melee",     2, "stab",     ("fire", "shock", "bleed", "toxic", "uv")),
    "bow":            ("bow",       2, "bow",      ("fire", "shock", "toxic", "uv")),
    "crossbow":       ("crossbow",  2, "crossbow", ("fire", "shock", "toxic", "uv", "impact")),
    "pistol":         ("gun",       1, "pistol",   ()),
    "revolver":       ("gun",       1, "pistol",   ()),
    "shotgun":        ("gun",       2, "shotgun",  ()),
    "rifle":          ("gun",       2, "rifle",    ()),
    "smg":            ("gun",       2, "rifle",    ()),
    "throwable":      ("throwable", 1, "throw",    ()),
}
WEAPON_KINDS = ("melee", "bow", "crossbow", "gun", "throwable")

_DEFAULT_SFX = {
    ("one_hand_blade", "light"): "blade_light", ("one_hand_blade", "medium"): "blade_light",
    ("one_hand_blade", "heavy"): "blade_heavy", ("two_hand_blade", "heavy"): "blade_heavy",
    ("two_hand_blade", "medium"): "blade_heavy", ("one_hand_blunt", "light"): "blunt_light",
    ("one_hand_blunt", "medium"): "blunt_light", ("one_hand_blunt", "heavy"): "blunt_heavy",
    ("two_hand_blunt", "heavy"): "blunt_heavy", ("two_hand_blunt", "medium"): "blunt_heavy",
    ("spear", "light"): "pierce", ("spear", "medium"): "pierce", ("spear", "heavy"): "pierce",
}


def W(key, ja, en, cls, dtype, weight, *, damage, attack_speed, stamina_cost, durability, reach,
      crit_mult, knockback, gore_power, sever_bias, rarity, recipe, model, palette,
      alt_dtype=None, ammo=None, mag=0, reload_ticks=0, spread=0.0, pellets=1, range=None,
      projectile=None, charge_ticks=0, noise=0, stack=1, mods_allowed=None, grips=(0.0,),
      desc_ja="", desc_en="", special=None, sfx=None, fx=None, unlock_level=0):
    """武器 1 つ。単位: damage は体力（ハート半分 = 1）、attack_speed は 1 秒の振り（銃は 1 秒の発射）数、
    reach / range はブロック、reload_ticks / charge_ticks は tick、spread は度、noise は音が届く半径（ブロック）。
    ammo は共有アイテムのフル ID、projectile は飛び道具エンティティのフル ID（nr:proj_<key>）、銃は None
    （スクリプトのレイ）。sever_bias は強い一撃で選ぶ部位の結果、gore_power は切断・破壊の起きやすさ 0〜1。
    unlock_level は端末の作業台レシピが解禁される戦闘のレベル。"""
    kind, hands, anim_set, mods = WEAPON_CLASSES[cls]
    if sfx is None:
        sfx = _DEFAULT_SFX.get((cls, weight), {"bow": "bow", "crossbow": "crossbow", "pistol": "pistol",
                                               "revolver": "revolver", "shotgun": "shotgun", "rifle": "rifle",
                                               "smg": "smg", "throwable": "throw"}.get(cls, "blade_light"))
    return dict(
        key=key, id="nr:w_" + key, ja=ja, en=en, cls=cls, kind=kind, dtype=dtype, alt_dtype=alt_dtype,
        weight=weight, hands=hands, damage=damage, attack_speed=attack_speed, stamina_cost=stamina_cost,
        durability=durability, reach=reach, crit_mult=crit_mult, knockback=knockback, gore_power=gore_power,
        sever_bias=dict(sever_bias), ammo=ammo, mag=mag, reload_ticks=reload_ticks, spread=spread,
        pellets=pellets, range=range if range is not None else reach, projectile=projectile,
        charge_ticks=charge_ticks, noise=noise, stack=stack,
        mods_allowed=list(mods if mods_allowed is None else mods_allowed), rarity=rarity, recipe=recipe,
        model=model, palette=list(palette), anim_set=anim_set, grips=list(grips), sfx=sfx, fx=fx or {},
        special=special or {}, desc_ja=desc_ja, desc_en=desc_en, unlock_level=unlock_level,
        geometry="geometry.nr.w." + key, texture="textures/nr/items/" + key,
    )


_STICK = "minecraft:stick"
_IRON = "minecraft:iron_ingot"
_PLANK = "minecraft:oak_planks"

WEAPONS = [
    # =====================================================================================
    #  片手の刃（slash_1h）
    # =====================================================================================
    W("machete", "マチェーテ", "Machete", "one_hand_blade", "slash", "medium",
      damage=8, attack_speed=1.5, stamina_cost=9, durability=260, reach=3.0, crit_mult=1.8, knockback=0.35,
      gore_power=0.75, sever_bias=dict(head="severed", arm="cut_lower", leg="cut_lower", torso="slashed"),
      rarity="common",
      recipe=shaped([" B", " B", "ST"], {"B": "nr:blades", "S": _STICK, "T": "nr:duct_tape"}),
      palette=["#94989a", "#c4cace", "#2a2a2e", "#5c623e", "#481008"],
      desc_ja="藪を払う鉈。首も腕も一振りで落ちる、扱いやすい万能の刃。",
      desc_en="A brush-clearing blade. Takes heads and arms in one swing — the all-rounder.",
      model=[
          P("handle", (1.3, 1.7, 5.2), (0, 0, 0.4), "plastic_black", "2 枚の樹脂の貼り合わせ。滑り止めの格子、中央の継ぎ目"),
          P("rivet", (1.4, 0.4, 0.4), (0, 0, -1.4), "brass", "柄の鋲（真鍮）", rep=[(0, 0, 0.6), (0, 0, 2.2)]),
          P("pommel", (1.5, 1.9, 0.6), (0, 0, 3.2), "steel_dark", "紐穴のある尻金"),
          P("lanyard", (0.3, 0.3, 2.4), (0, -0.9, 4.3), "paracord", "尻金から垂れる紐の輪", rot=(35, 0, 0)),
          P("bolster", (1.6, 2.1, 0.5), (0, 0, -2.4), "steel_dark", "口金"),
          P("blade_base", (0.35, 2.2, 5.0), (0, -0.1, -5.2), "steel_worn", "根元は幅 2.2、峰に点錆"),
          P("blade_belly", (0.35, 2.6, 4.2), (0, -0.3, -9.8), "steel_worn", "先へ向かって膨らむ（マチェーテの腹）"),
          P("blade_tip", (0.35, 1.8, 1.8), (0, 0.0, -12.6), "steel_worn", "斜めに落とした切っ先", rot=(22, 0, 0)),
          P("edge", (0.2, 0.5, 10.6), (0, -1.45, -8.0), "steel_clean", "研いだ刃。3 か所の刃こぼれ（欠けの凹み）"),
          P("spine_rust", (0.4, 0.3, 9.0), (0, 1.0, -7.8), "steel_rusty", "峰の錆の帯"),
          P("blood", (0.42, 1.4, 4.6), (0, -0.5, -10.0), "blood_dry", "刃先半分に乾いた血、刃の溝に黒い固まり"),
          P("tape_fix", (1.45, 1.85, 1.2), (0, 0, -1.5), "tape_grey", "柄の割れを留めた補修テープ"),
      ]),
    W("cleaver", "肉切り包丁", "Butcher's Cleaver", "one_hand_blade", "slash", "medium",
      damage=9, attack_speed=1.35, stamina_cost=10, durability=240, reach=2.7, crit_mult=1.7, knockback=0.45,
      gore_power=0.85, sever_bias=dict(head="jawless", arm="cut_upper", leg="cut_lower", torso="gutted"),
      rarity="common",
      recipe=shaped(["SB", "SB", " W"], {"S": "nr:scrap", "B": "nr:blades", "W": _STICK}),
      palette=["#9a9c9c", "#d0d4d6", "#5a3c28", "#721010", "#2a2a2c"],
      desc_ja="肉屋の重い包丁。骨ごと叩き切るので腕が肩から落ちやすい。",
      desc_en="A heavy butcher's cleaver. Chops through bone — arms come off at the shoulder.",
      model=[
          P("handle", (1.3, 1.6, 4.8), (0, 0, 0.4), "wood_dark", "黒ずんだ木の柄、3 本の鋲"),
          P("rivet", (1.4, 0.4, 0.4), (0, 0, -1.0), "steel_worn", "鋲", rep=[(0, 0, 0.6), (0, 0, 2.2)]),
          P("tang", (0.4, 1.2, 1.0), (0, 0.2, -2.3), "steel_worn", "柄と刃のつなぎ"),
          P("blade", (0.45, 4.0, 7.2), (0, -1.1, -6.4), "steel_worn", "長方形の厚い刃（幅 4）。曇った表面に打痕"),
          P("hang_hole", (0.5, 0.8, 0.8), (0, 0.4, -9.2), "steel_dark", "吊るし穴（貫通に見せる黒）"),
          P("edge", (0.24, 0.5, 7.2), (0, -3.25, -6.4), "steel_clean", "まっすぐな刃、大きな欠け 1 か所"),
          P("blood", (0.5, 2.6, 5.0), (0, -1.8, -6.8), "blood_wet", "刃の下半分を濡らす血、指で拭った跡"),
          P("rust", (0.5, 0.6, 3.0), (0, 0.6, -5.0), "steel_rusty", "峰の錆"),
      ]),
    W("kukri", "ククリナイフ", "Kukri", "one_hand_blade", "slash", "light",
      damage=7, attack_speed=1.8, stamina_cost=7, durability=220, reach=2.8, crit_mult=1.9, knockback=0.25,
      gore_power=0.7, sever_bias=dict(head="severed", arm="cut_lower", leg="cut_lower", torso="slashed"),
      rarity="uncommon",
      recipe=shaped([" B", "BS", "L "], {"B": "nr:blades", "S": "nr:scrap", "L": "minecraft:leather"}),
      palette=["#8e9294", "#c8ccd0", "#5e3c24", "#2c2c2e", "#60100c"],
      desc_ja="前へ折れ曲がった山刀。速く振れて、手首の返しで首を刎ねる。",
      desc_en="A forward-bent knife. Quick swings; a flick of the wrist takes the head.",
      model=[
          P("handle", (1.4, 1.7, 4.6), (0, 0, 0.3), "wood_dark", "膨らんだ木の柄、真鍮の輪 2 本"),
          P("brass_ring", (1.6, 1.9, 0.4), (0, 0, -1.6), "brass", "輪", rep=[(0, 0, 2.2)]),
          P("pommel_cap", (1.5, 1.8, 0.6), (0, 0, 2.9), "brass", "尻の金具"),
          P("blade_1", (0.4, 1.8, 3.4), (0, 0.3, -3.8), "steel_worn", "根元。上へ少し反る", rot=(-8, 0, 0)),
          P("blade_2", (0.4, 2.4, 3.2), (0, 0.4, -6.8), "steel_worn", "腹。いちばん幅が広い"),
          P("blade_3", (0.4, 2.0, 2.8), (0, -0.6, -9.4), "steel_worn", "先は下へ折れる（ククリの屈曲）", rot=(24, 0, 0)),
          P("edge", (0.22, 0.4, 7.4), (0, -1.0, -6.6), "steel_clean", "内側の反った刃"),
          P("cho", (0.42, 0.6, 0.5), (0, -0.7, -2.4), "steel_dark", "刃元の小さな切り欠き（チョー）"),
          P("blood", (0.45, 1.4, 3.0), (0, -0.4, -8.4), "blood_dry", "先の方に乾いた血"),
      ]),
    W("combat_knife", "コンバットナイフ", "Combat Knife", "one_hand_blade", "slash", "light",
      damage=5, attack_speed=2.4, stamina_cost=5, durability=300, reach=2.4, crit_mult=2.4, knockback=0.15,
      gore_power=0.45, sever_bias=dict(head="jawless", arm="wounded", leg="wounded", torso="gutted"),
      rarity="common", alt_dtype="pierce",
      recipe=shaped(["B", "S", "T"], {"B": "nr:blades", "S": "nr:scrap", "T": "nr:duct_tape"}),
      special=dict(backstab_mult=2.5, heavy_is_stab=True),
      palette=["#3a3c40", "#c6cacc", "#2a2a2c", "#5c623e", "#701010"],
      desc_ja="軽くて速い。背後から突けば一撃で黙らせる。重攻撃は突き刺し。",
      desc_en="Light and fast. A stab from behind silences them. Heavy attack is a thrust.",
      model=[
          P("handle", (1.2, 1.5, 4.4), (0, 0, 0.3), "rubber_black", "輪の刻みが 6 本並ぶゴムの柄"),
          P("guard", (0.6, 2.6, 0.5), (0, -0.2, -2.1), "steel_dark", "十字の鍔（下へ長い）"),
          P("pommel", (1.3, 1.6, 0.7), (0, 0, 2.8), "steel_dark", "ガラス割りの尖った尻"),
          P("blade", (0.3, 1.5, 5.4), (0, 0.0, -5.0), "steel_dark", "黒染めのクリップポイント、峰側に鋸刃"),
          P("serration", (0.32, 0.4, 2.2), (0, 0.8, -3.4), "steel_worn", "峰の鋸刃（ギザギザの段）"),
          P("edge", (0.18, 0.4, 5.2), (0, -0.75, -5.0), "steel_clean", "銀に研ぎ出した刃"),
          P("tip", (0.3, 1.0, 1.2), (0, 0.15, -8.1), "steel_dark", "クリップの切っ先", rot=(-20, 0, 0)),
          P("cord_wrap", (1.3, 1.6, 1.0), (0, 0, -1.2), "paracord", "柄の根元のパラコード巻き"),
      ]),
    W("scrap_katana", "廃材の刀", "Scrap Katana", "one_hand_blade", "slash", "medium",
      damage=10, attack_speed=1.4, stamina_cost=10, durability=280, reach=3.2, crit_mult=2.0, knockback=0.3,
      gore_power=0.9, sever_bias=dict(head="severed", arm="cut_upper", leg="cut_upper", torso="halved"),
      rarity="rare", recipe=None, unlock_level=6,
      palette=["#a8acae", "#dadee2", "#26262a", "#7a1a14", "#8c6a3c"],
      desc_ja="車の板バネを叩いて伸ばした反りのある刃。切れ味は本物に迫る。",
      desc_en="A curved blade hammered out of a car leaf spring. Nearly as sharp as the real thing.",
      model=[
          P("tsuka", (1.3, 1.6, 6.6), (0, 0, 1.2), "cloth_red", "赤い布を菱目に巻いた柄（巻きの菱の陰影）"),
          P("tsuka_tape", (1.35, 1.65, 1.0), (0, 0, 3.6), "tape_black", "柄頭の黒テープ"),
          P("tsuba", (0.6, 3.4, 3.4), (0, 0, -2.4), "steel_rusty", "丸ノコの刃を切った鍔（外周に歯）", rot=(45, 0, 0)),
          P("habaki", (0.6, 1.6, 0.8), (0, 0.1, -3.0), "brass", "はばき（銅線を巻いて作る）"),
          P("blade_1", (0.4, 1.5, 6.0), (0, 0.1, -6.2), "steel_worn", "身幅 1.5、板バネの研ぎ跡"),
          P("blade_2", (0.4, 1.4, 6.0), (0, 0.5, -12.1), "steel_worn", "上へ反る", rot=(-5, 0, 0)),
          P("blade_3", (0.4, 1.2, 4.6), (0, 1.2, -17.2), "steel_worn", "さらに反る", rot=(-9, 0, 0)),
          P("kissaki", (0.4, 1.0, 1.4), (0, 1.75, -20.2), "steel_clean", "切っ先", rot=(-24, 0, 0)),
          P("hamon", (0.42, 0.5, 15.8), (0, -0.4, -11.6), "steel_clean", "波打つ刃文（白い波線）", rot=(-6, 0, 0)),
          P("bolt_holes", (0.44, 0.5, 0.5), (0, 0.3, -5.0), "steel_dark", "板バネの元のボルト穴（埋めた跡）", rep=[(0, 0.6, -9.0)]),
          P("blood", (0.44, 0.9, 5.0), (0, 0.6, -15.0), "blood_wet", "切っ先に向かう血の筋"),
      ]),
    W("hatchet", "消防の手斧", "Fire Hatchet", "one_hand_blade", "slash", "medium",
      damage=9, attack_speed=1.3, stamina_cost=11, durability=320, reach=2.8, crit_mult=1.7, knockback=0.5,
      gore_power=0.8, sever_bias=dict(head="severed", arm="cut_upper", leg="cut_upper", torso="gutted"),
      rarity="common", alt_dtype="blunt",
      recipe=shaped(["SS", "BW", " W"], {"S": "nr:scrap", "B": "nr:blades", "W": _STICK}),
      palette=["#a2281e", "#7a7c7e", "#2a2a2c", "#c8ccd0", "#5a120c"],
      desc_ja="救助隊の片手斧。重い頭で叩き割り、裏のピックで頭蓋に穴を開ける。",
      desc_en="A rescue hatchet. The heavy head chops; the pick on the back punches skulls.",
      model=[
          P("handle", (1.2, 1.5, 11.0), (0, 0, -3.0), "wood_painted", "剥げた赤ペンキの柄、手垢で黒い握り"),
          P("grip_wrap", (1.3, 1.6, 4.0), (0, 0, 0.2), "rubber_black", "ゴムの握り"),
          P("head_core", (1.4, 3.0, 2.4), (0, -0.4, -8.6), "steel_painted", "赤い塗装の頭（欠け多数）"),
          P("blade", (0.6, 3.4, 3.2), (0, -3.2, -8.6), "steel_worn", "-Y へ張り出す刃、扇形に広がる"),
          P("edge", (0.3, 0.4, 3.6), (0, -4.9, -8.6), "steel_clean", "研いだ刃、血で曇る"),
          P("pick", (0.8, 2.6, 0.9), (0, 2.2, -8.6), "steel_worn", "+Y 側のピック（先細り）", rot=(0, 0, 0)),
          P("pick_tip", (0.5, 1.0, 0.6), (0, 3.8, -8.6), "steel_clean", "ピックの先"),
          P("wedge", (1.5, 0.5, 0.6), (0, -0.4, -10.4), "steel_dark", "頭の楔"),
          P("blood", (0.62, 2.4, 3.0), (0, -3.4, -8.6), "blood_wet", "刃に濡れた血、髪の毛が貼り付く"),
      ]),
    W("sickle", "錆びた鎌", "Rusty Sickle", "one_hand_blade", "slash", "light",
      damage=6, attack_speed=2.0, stamina_cost=6, durability=180, reach=2.6, crit_mult=2.1, knockback=0.15,
      gore_power=0.65, sever_bias=dict(head="severed", arm="wounded", leg="cut_lower", torso="gutted"),
      rarity="common",
      recipe=shaped(["BB", " S"], {"B": "nr:blades", "S": _STICK}),
      palette=["#7e5236", "#9a9c9c", "#6e5034", "#4a100c"],
      desc_ja="農具の鎌。引っかけて引けば喉と腹が裂ける。",
      desc_en="A farm sickle. Hook and pull — throats and bellies open.",
      model=[
          P("handle", (1.3, 1.5, 5.4), (0, 0, 0.6), "wood_old", "割れた木の柄、針金の補強"),
          P("wire", (1.4, 1.6, 0.6), (0, 0, -1.6), "steel_worn", "巻いた針金", rep=[(0, 0, 2.6)]),
          P("ferrule", (1.4, 1.6, 0.8), (0, 0, -2.4), "steel_rusty", "口金"),
          P("blade_1", (0.3, 0.9, 3.4), (0, 0.4, -4.4), "steel_rusty", "まっすぐ伸びる根元"),
          P("blade_2", (0.3, 0.9, 3.0), (0, 1.6, -6.9), "steel_rusty", "上へ曲がり始める", rot=(-40, 0, 0)),
          P("blade_3", (0.3, 0.9, 2.8), (0, 3.6, -7.8), "steel_rusty", "ほぼ垂直", rot=(-85, 0, 0)),
          P("blade_4", (0.3, 0.8, 2.4), (0, 5.0, -6.6), "steel_rusty", "手前へ返る先端", rot=(-135, 0, 0)),
          P("edge", (0.32, 0.3, 7.6), (0, 2.2, -6.2), "steel_worn", "内側の刃（鈍い銀の線）", rot=(-60, 0, 0)),
          P("blood", (0.34, 0.9, 2.0), (0, 3.2, -7.8), "blood_dry", "曲がりの内側に血"),
      ]),
    # =====================================================================================
    #  両手の刃（slash_2h）
    # =====================================================================================
    W("fire_axe", "消防斧", "Fire Axe", "two_hand_blade", "slash", "heavy",
      damage=17, attack_speed=0.8, stamina_cost=20, durability=380, reach=3.4, crit_mult=1.8, knockback=1.0,
      gore_power=0.95, sever_bias=dict(head="severed", arm="cut_upper", leg="cut_upper", torso="halved"),
      rarity="uncommon", alt_dtype="blunt", grips=(0.0, -9.0),
      recipe=shaped(["SSB", " W ", " W "], {"S": "nr:scrap", "B": "nr:blades", "W": _STICK}),
      palette=["#b02a1e", "#e0c040", "#7e8082", "#d0d4d6", "#5a120c"],
      desc_ja="ガラスもドアも人も割る赤い斧。横薙ぎで胴を真っ二つにする。",
      desc_en="The red axe that breaks glass, doors and people. A side swing cuts torsos in half.",
      model=[
          P("haft", (1.5, 1.7, 22.0), (0, 0, -6.0), "wood_painted", "赤い塗装の柄、黄色い帯 2 本、白い文字「FIRE」"),
          P("haft_band", (1.6, 1.8, 0.8), (0, 0, -12.0), "plastic_yellow", "黄色の帯", rep=[(0, 0, -3.0)]),
          P("grip", (1.6, 1.8, 4.0), (0, 0, 2.4), "rubber_black", "末端のゴム握り"),
          P("knob", (1.9, 2.1, 0.8), (0, 0, 4.8), "rubber_black", "柄尻の膨らみ"),
          P("head", (1.8, 3.6, 3.0), (0, -0.2, -17.2), "steel_painted", "赤い頭、欠けた塗装から灰色"),
          P("blade", (0.8, 4.6, 4.2), (0, -4.0, -17.2), "steel_worn", "-Y へ広がる扇形の刃"),
          P("edge", (0.4, 0.5, 5.0), (0, -6.4, -17.2), "steel_clean", "研いだ刃、細かい欠け"),
          P("pick", (1.0, 4.0, 1.2), (0, 3.6, -17.2), "steel_painted", "反対側の尖ったピック"),
          P("pick_tip", (0.6, 1.4, 0.7), (0, 6.2, -17.2), "steel_clean", "ピックの先、血が固まる"),
          P("blood", (0.84, 3.6, 4.0), (0, -4.2, -17.2), "blood_wet", "刃全体に血と肉片、柄へ垂れる筋"),
          P("blood_drip", (1.6, 3.0, 0.3), (0, -0.2, -15.0), "blood_wet", "柄を伝う血"),
      ]),
    W("scythe", "戦の大鎌", "War Scythe", "two_hand_blade", "slash", "heavy",
      damage=15, attack_speed=0.85, stamina_cost=19, durability=300, reach=3.9, crit_mult=1.9, knockback=0.6,
      gore_power=1.0, sever_bias=dict(head="severed", arm="cut_lower", leg="cut_lower", torso="halved"),
      rarity="rare", grips=(0.0, -10.0), recipe=None, unlock_level=8,
      palette=["#6e5034", "#8a8c8e", "#c8ccd0", "#3a3a3c", "#5a120c"],
      desc_ja="草刈り鎌の刃を真っすぐ立てた戦鎌。間合いが広く、脚と首を刈り取る。",
      desc_en="A scythe blade fixed straight, like a war scythe. Long reach — reaps legs and heads.",
      model=[
          P("snath", (1.3, 1.4, 26.0), (0, 0, -8.0), "wood_old", "曲がりのある古い柄（2 本継ぎ、継ぎ目に針金）"),
          P("handle_peg", (0.9, 3.0, 1.0), (0, 1.6, -8.0), "wood_dark", "柄の途中の握り（左手）"),
          P("collar", (1.6, 1.8, 2.0), (0, 0, -20.4), "steel_rusty", "刃を留める金輪とボルト 2 本"),
          P("bolt", (2.0, 0.5, 0.5), (0, 0, -20.0), "steel_worn", "留めボルト", rep=[(0, 0, -20.8)]),
          P("blade_1", (0.35, 2.2, 6.0), (0, -1.6, -24.0), "steel_worn", "まっすぐ前へ伸ばし直した刃", rot=(10, 0, 0)),
          P("blade_2", (0.35, 1.8, 6.0), (0, -2.6, -29.6), "steel_worn", "先へ細る"),
          P("blade_3", (0.35, 1.2, 3.0), (0, -2.4, -33.6), "steel_clean", "切っ先、上へ少し反る", rot=(-12, 0, 0)),
          P("edge", (0.2, 0.4, 13.0), (0, -3.2, -27.6), "steel_clean", "長い刃（下側）"),
          P("rag_flag", (0.2, 2.6, 2.0), (0, -1.2, -19.0), "cloth_red", "目印の赤い布がはためく"),
          P("blood", (0.38, 1.6, 8.0), (0, -2.6, -27.0), "blood_dry", "刃に沿った血の帯"),
      ]),
    W("leaf_spring_greatsword", "板バネの大剣", "Leaf-Spring Greatsword", "two_hand_blade", "slash", "heavy",
      damage=18, attack_speed=0.75, stamina_cost=22, durability=420, reach=3.6, crit_mult=1.8, knockback=1.2,
      gore_power=1.0, sever_bias=dict(head="severed", arm="cut_upper", leg="cut_upper", torso="halved"),
      rarity="epic", alt_dtype="blunt", grips=(0.0, -4.5), recipe=None, unlock_level=12,
      palette=["#5c5e60", "#9ea2a4", "#d6dade", "#2a2a2c", "#7a3a1c"],
      desc_ja="トラックの板バネを 3 枚重ねてボルトで締めた大剣。重さで骨ごと断ち割る。",
      desc_en="Three truck leaf springs bolted into a greatsword. Its weight splits bone and all.",
      model=[
          P("grip", (1.5, 1.7, 9.0), (0, 0, -2.2), "leather_brown", "革紐を巻いた長い握り（巻きの段差）"),
          P("pommel", (2.2, 2.2, 1.6), (0, 0, 3.0), "iron_cast", "歯車をはめた柄頭"),
          P("guard", (1.4, 6.0, 1.4), (0, 0, -7.4), "steel_rusty", "鉄筋 2 本を溶接した十字鍔、端が下へ曲がる"),
          P("leaf_1", (0.5, 3.0, 22.0), (0, 0, -19.0), "steel_worn", "いちばん長い板（刃）。研ぎ出した縁"),
          P("leaf_2", (0.5, 2.6, 15.0), (0.5, 0.1, -15.6), "steel_dark", "2 枚目（短い、黒い）"),
          P("leaf_3", (0.5, 2.2, 9.0), (-0.5, 0.2, -12.6), "steel_dark", "3 枚目（いちばん短い、反対側）"),
          P("center_bolt", (2.2, 0.8, 0.8), (0, 0, -11.0), "steel_worn", "板を貫く中心ボルトとナット", rep=[(0, 0, -16.0)]),
          P("clamp", (2.0, 3.4, 0.8), (0, 0, -9.0), "steel_rusty", "U ボルトの締め金", rep=[(0, 0, -20.0)]),
          P("edge", (0.3, 0.5, 20.0), (0, -1.6, -19.8), "steel_clean", "研いだ刃（曲がった跡のうねり）"),
          P("tip", (0.5, 2.0, 2.2), (0, 0.4, -30.6), "steel_worn", "斜めに切った先端", rot=(30, 0, 0)),
          P("blood", (0.55, 2.4, 9.0), (0, -0.6, -25.0), "blood_wet", "先半分を覆う血、肉片がボルトに挟まる"),
      ]),
    W("buzzsaw_glaive", "丸ノコ薙刀", "Buzzsaw Glaive", "two_hand_blade", "slash", "heavy",
      damage=16, attack_speed=0.9, stamina_cost=20, durability=360, reach=4.0, crit_mult=1.7, knockback=0.8,
      gore_power=1.0, sever_bias=dict(head="severed", arm="cut_lower", leg="cut_upper", torso="halved"),
      rarity="legendary", grips=(0.0, -9.0), recipe=None, unlock_level=16,
      special=dict(innate_mod="shock", innate_tier=1),
      palette=["#5a5c5e", "#c4c8cc", "#e0c040", "#26262a", "#70a0ff"],
      desc_ja="鉄パイプの先に電動丸ノコを付け、電池で回す。触れた肉を挽き、感電させる。",
      desc_en="A battery-driven circular saw on a pipe. Grinds whatever it touches and shocks it.",
      model=[
          P("pole", (1.4, 1.4, 24.0), (0, 0, -7.0), "steel_worn", "鉄パイプ、黄と黒の警告テープを螺旋に"),
          P("tape_spiral", (1.5, 1.5, 3.0), (0, 0, -4.0), "plastic_yellow", "警告テープ（黄黒の縞）", rep=[(0, 0, -10.0)]),
          P("grip", (1.6, 1.6, 4.0), (0, 0, 1.6), "tape_black", "黒テープの握り"),
          P("battery_box", (2.4, 2.8, 4.0), (0, -2.0, -12.0), "plastic_yellow", "電動工具の電池パックを針金で留める"),
          P("cable", (0.4, 0.4, 7.0), (0, -1.0, -16.0), "rubber_black", "電池から刃のモーターへの黒い電線"),
          P("motor", (2.6, 2.6, 3.2), (0, 0, -20.4), "plastic_black", "丸ノコのモーター部、通気スリット"),
          P("guard", (1.2, 5.0, 4.0), (1.0, 1.2, -23.8), "steel_painted", "半円の安全カバー（上半分）"),
          P("saw_disc", (0.3, 8.0, 8.0), (0, 0, -24.0), "steel_clean", "直径 8 の円盤（22.5 度ずつ回した 4 枚で円に）",
            rep=[(0, 0, -24.0)]),
          P("teeth", (0.4, 8.8, 0.6), (0, 0, -24.0), "steel_worn", "外周の歯（45 度ずつ 4 本で 8 方向の歯）"),
          P("arbor_nut", (0.9, 1.4, 1.4), (0.5, 0, -24.0), "brass", "軸のナット"),
          P("spark_glow", (0.2, 1.2, 1.2), (-0.4, 0, -21.0), "emissive_blue", "モーターの隙間の青い火花（発光）"),
          P("blood", (0.32, 6.0, 6.0), (0, -1.0, -24.4), "blood_wet", "刃の下半分に血と肉、遠心力で飛び散った跡"),
      ]),
    # =====================================================================================
    #  片手の打撃（blunt_1h）
    # =====================================================================================
    W("pipe_wrench", "パイプレンチ", "Pipe Wrench", "one_hand_blunt", "blunt", "medium",
      damage=8, attack_speed=1.4, stamina_cost=9, durability=400, reach=2.8, crit_mult=1.7, knockback=0.6,
      gore_power=0.55, sever_bias=dict(head="cracked", arm="broken", leg="broken"),
      rarity="common", recipe=None,
      palette=["#b02a1e", "#6e7072", "#3a3a3c", "#a8acae", "#4a100c"],
      desc_ja="配管工の大きなレンチ。重い顎で頭蓋にひびを入れる。",
      desc_en="A plumber's big wrench. The heavy jaw cracks skulls.",
      model=[
          P("handle", (1.2, 1.8, 10.0), (0, 0, -1.6), "steel_painted", "赤い I 字断面の柄、塗装が剥げて灰"),
          P("grip_end", (1.3, 2.0, 2.0), (0, 0, 2.6), "iron_cast", "吊るし穴のある柄尻"),
          P("frame", (1.6, 2.6, 2.6), (0, 0.4, -7.6), "iron_cast", "顎の枠"),
          P("hook_jaw", (1.4, 1.2, 3.6), (0, 2.4, -8.4), "steel_worn", "上の可動顎、内側に歯"),
          P("heel_jaw", (1.4, 1.0, 2.2), (0, -0.6, -9.6), "steel_worn", "下の固定顎、歯の刻み"),
          P("adjust_nut", (1.8, 1.8, 1.2), (0, 1.4, -6.0), "steel_worn", "調整ナット（ローレットの縦溝）"),
          P("blood", (1.5, 2.0, 1.6), (0, 2.0, -9.4), "blood_dry", "顎に乾いた血と髪"),
      ]),
    W("crowbar", "バール", "Crowbar", "one_hand_blunt", "blunt", "medium",
      damage=7, attack_speed=1.5, stamina_cost=8, durability=450, reach=2.9, crit_mult=1.8, knockback=0.5,
      gore_power=0.5, sever_bias=dict(head="cracked", arm="broken", leg="broken"),
      rarity="common", alt_dtype="pierce",
      recipe=shaped(["  I", " I ", "I  "], {"I": _IRON}),
      special=dict(pry_locked=True, pry_durability_cost=20),
      palette=["#a8281e", "#5a5c5e", "#2a2a2c", "#4a100c"],
      desc_ja="釘抜きの付いたバール。鍵の掛かった箱もこじ開けられる（耐久を使う）。",
      desc_en="A crowbar with a nail claw. Can pry open locked stashes (costs durability).",
      model=[
          P("shaft", (0.9, 0.9, 13.0), (0, 0, -2.4), "steel_painted", "六角の棒、赤い塗装が擦れて黒い地金"),
          P("grip_tape", (1.0, 1.0, 4.0), (0, 0, 1.4), "tape_black", "黒テープの握り"),
          P("hook_1", (0.9, 0.9, 2.4), (0, 1.0, -9.6), "steel_painted", "曲がり始め", rot=(-45, 0, 0)),
          P("hook_2", (0.9, 2.4, 0.9), (0, 2.6, -10.2), "steel_painted", "鉤の背"),
          P("hook_3", (0.9, 0.9, 1.8), (0, 3.6, -9.4), "steel_worn", "鉤の先、二股の釘抜き", rot=(30, 0, 0)),
          P("claw_split", (0.95, 0.5, 1.2), (0, 3.4, -8.6), "steel_dark", "釘抜きの割れ目（黒）"),
          P("flat_end", (1.0, 0.5, 1.6), (0, -0.3, 4.2), "steel_worn", "反対側の平たいへら", rot=(-15, 0, 0)),
          P("blood", (1.0, 2.4, 1.0), (0, 2.6, -10.3), "blood_dry", "鉤に固まった血"),
      ]),
    W("nail_bat", "釘バット", "Nail Bat", "one_hand_blunt", "blunt", "medium",
      damage=9, attack_speed=1.3, stamina_cost=10, durability=220, reach=3.0, crit_mult=1.6, knockback=0.7,
      gore_power=0.65, sever_bias=dict(head="crushed", arm="broken", leg="broken"), alt_dtype="slash",
      mods_allowed=["fire", "shock", "bleed", "toxic", "uv", "impact"],
      rarity="common",
      recipe=shaped(["NPN", " P ", " T "], {"N": "nr:scrap", "P": _PLANK, "T": "nr:duct_tape"}),
      palette=["#b08a5c", "#8e9092", "#2a2a2c", "#7a1410", "#4a100c"],
      desc_ja="木のバットに釘を打ち込んだ定番。肉を引き裂き、出血させる。",
      desc_en="A wooden bat studded with nails. Tears flesh and causes bleeding.",
      special=dict(innate_bleed_chance=0.25),
      model=[
          P("handle", (1.2, 1.2, 5.0), (0, 0, 0.6), "tape_grey", "ダクトテープを巻いた握り（巻きの段）"),
          P("knob", (1.8, 1.8, 0.8), (0, 0, 3.4), "wood_raw", "グリップエンドの膨らみ"),
          P("taper", (1.6, 1.6, 4.0), (0, 0, -3.6), "wood_raw", "細い首から太くなる"),
          P("barrel", (2.4, 2.4, 8.0), (0, 0, -9.4), "wood_raw", "太い打撃部。焼き印と割れ、黒い血の染み"),
          P("cap", (2.2, 2.2, 0.6), (0, 0, -13.6), "wood_old", "先端の丸み"),
          P("nail", (3.4, 0.25, 0.25), (0, 0.6, -7.0), "steel_rusty",
            "貫通した釘（両側に 0.5 ずつ出る）。曲がったもの・頭が残ったものを混ぜる",
            rep=[(0, -0.5, -8.4), (0, 0.4, -10.0), (0, -0.8, -11.4), (0, 0.2, -12.6)]),
          P("nail_v", (0.25, 3.4, 0.25), (0.4, 0, -7.6), "steel_rusty", "縦の釘",
            rep=[(-0.5, 0, -9.2), (0.2, 0, -10.8), (-0.3, 0, -12.2)]),
          P("blood", (2.5, 2.5, 4.0), (0, 0, -11.0), "blood_wet", "先半分に血と肉片、釘に布切れが絡む"),
      ]),
    W("police_baton", "警棒", "Police Baton", "one_hand_blunt", "blunt", "light",
      damage=5, attack_speed=2.2, stamina_cost=5, durability=500, reach=2.7, crit_mult=1.6, knockback=0.5,
      gore_power=0.3, sever_bias=dict(head="cracked", arm="broken", leg="broken"),
      rarity="uncommon", recipe=None,
      special=dict(stagger_bonus=0.25),
      palette=["#1c1c20", "#5a5c60", "#c4c8cc", "#2a2a2c"],
      desc_ja="伸縮式の特殊警棒。軽く速く、敵をよろめかせる。パトカーで見つかる。",
      desc_en="An expandable baton. Light and quick; staggers enemies. Found in police cars.",
      model=[
          P("grip", (1.2, 1.2, 5.0), (0, 0, 0.6), "rubber_black", "発泡ゴムの握り、細かい凹凸"),
          P("end_cap", (1.3, 1.3, 0.8), (0, 0, 3.4), "steel_dark", "尻のキャップ"),
          P("tube_1", (1.0, 1.0, 4.0), (0, 0, -3.8), "steel_dark", "1 段目の筒"),
          P("tube_2", (0.8, 0.8, 4.0), (0, 0, -7.6), "steel_dark", "2 段目（細い）"),
          P("tube_3", (0.6, 0.6, 3.6), (0, 0, -11.2), "steel_worn", "3 段目、擦れて銀"),
          P("tip", (0.9, 0.9, 0.9), (0, 0, -13.2), "steel_worn", "先端の重り"),
          P("ring", (1.1, 1.1, 0.3), (0, 0, -5.8), "chrome", "段の継ぎ目の輪", rep=[(0, 0, -9.6)]),
      ]),
    W("claw_hammer", "金槌", "Claw Hammer", "one_hand_blunt", "blunt", "light",
      damage=7, attack_speed=1.8, stamina_cost=7, durability=380, reach=2.6, crit_mult=1.9, knockback=0.4,
      gore_power=0.55, sever_bias=dict(head="cracked", arm="broken", leg="broken"),
      rarity="common",
      recipe=shaped(["II", " S"], {"I": _IRON, "S": _STICK}),
      palette=["#3a3c40", "#a8acae", "#c88a2c", "#2a2a2c", "#4a100c"],
      desc_ja="釘抜き付きの金槌。小さいが頭に当てれば頭蓋が割れる。",
      desc_en="A claw hammer. Small, but a blow to the head cracks the skull.",
      model=[
          P("handle", (1.1, 1.4, 8.4), (0, 0, -0.8), "plastic_yellow", "黄と黒の樹脂の柄"),
          P("grip", (1.2, 1.5, 3.6), (0, 0, 1.4), "rubber_black", "黒ゴムの握り"),
          P("neck", (1.0, 1.0, 1.4), (0, 0, -5.4), "steel_dark", "柄と頭のつなぎ"),
          P("head", (1.3, 1.3, 1.6), (0, 0, -6.6), "steel_dark", "頭の中心"),
          P("face", (1.6, 2.4, 1.6), (0, -1.6, -6.6), "steel_worn", "-Y の打撃面（円柱を 2 枚の箱で）"),
          P("strike", (1.8, 0.4, 1.8), (0, -2.9, -6.6), "steel_clean", "磨かれた打撃面"),
          P("claw", (1.2, 2.6, 0.8), (0, 2.0, -6.2), "steel_dark", "+Y の二股の釘抜き、後ろへ反る", rot=(-25, 0, 0)),
          P("blood", (1.85, 0.8, 1.85), (0, -2.6, -6.6), "blood_wet", "打撃面の血と骨片"),
      ]),
    W("pipe_mace", "鉄パイプのメイス", "Pipe Mace", "one_hand_blunt", "blunt", "medium",
      damage=9, attack_speed=1.25, stamina_cost=11, durability=420, reach=2.9, crit_mult=1.7, knockback=0.8,
      gore_power=0.7, sever_bias=dict(head="crushed", arm="broken", leg="broken"),
      rarity="uncommon",
      recipe=shaped(["SIS", " I ", " T "], {"S": "nr:scrap", "I": _IRON, "T": "nr:duct_tape"}),
      palette=["#6e7072", "#8c5a3a", "#a8acae", "#2a2a2c", "#5a120c"],
      desc_ja="鉄パイプの先にボルトとナットを溶接した棍棒。頭を潰す。",
      desc_en="A steel pipe with bolts and nuts welded on the end. Crushes heads.",
      model=[
          P("pipe", (1.2, 1.2, 12.0), (0, 0, -3.0), "steel_worn", "亜鉛めっきの鉄パイプ、ねじ山の跡"),
          P("grip", (1.4, 1.4, 4.4), (0, 0, 1.4), "cloth_rag", "布を巻いてテープで留めた握り"),
          P("elbow", (1.8, 1.8, 2.2), (0, 0, -9.6), "iron_cast", "パイプ継ぎ手（T 字）"),
          P("head", (2.6, 2.6, 3.4), (0, 0, -11.6), "steel_rusty", "溶接の盛り上がった頭"),
          P("bolt", (0.8, 0.8, 0.8), (1.6, 0, -11.0), "steel_worn", "溶接したボルトの頭",
            rep=[(-1.6, 0, -11.0), (0, 1.6, -12.2), (0, -1.6, -12.2), (1.2, 1.2, -12.8), (-1.2, -1.2, -10.4)]),
          P("gear", (0.6, 3.6, 3.6), (0, 0, -13.4), "iron_cast", "先端に溶接した歯車（外周に歯）"),
          P("blood", (2.7, 2.7, 3.0), (0, -0.4, -12.0), "blood_wet", "頭全体に血と髪の毛"),
      ]),
    # =====================================================================================
    #  両手の打撃（blunt_2h）
    # =====================================================================================
    W("sledgehammer", "大ハンマー", "Sledgehammer", "two_hand_blunt", "blunt", "heavy",
      damage=18, attack_speed=0.7, stamina_cost=22, durability=500, reach=3.3, crit_mult=1.8, knockback=1.4,
      gore_power=0.9, sever_bias=dict(head="crushed", arm="broken", leg="broken"),
      rarity="uncommon", grips=(0.0, -8.0),
      recipe=shaped(["III", "ISI", " S "], {"I": _IRON, "S": _STICK}),
      palette=["#3a3c40", "#7a5a3a", "#e0c040", "#9ea2a4", "#5a120c"],
      desc_ja="解体用の大ハンマー。頭は弾け、体は吹き飛ぶ。",
      desc_en="A demolition sledge. Heads pop and bodies fly.",
      model=[
          P("haft", (1.5, 1.6, 20.0), (0, 0, -5.0), "wood_old", "ヒッコリーの柄、黄色い塗装の帯、割れ"),
          P("grip", (1.6, 1.7, 4.0), (0, 0, 3.0), "rubber_black", "末端のゴム握り"),
          P("band", (1.6, 1.7, 1.0), (0, 0, -8.0), "plastic_yellow", "黄色の帯（左手の位置）"),
          P("head", (3.4, 6.4, 3.4), (0, 0, -16.0), "steel_dark", "八角の頭（縦長）。角は面取り、打痕だらけ"),
          P("face_low", (3.6, 0.6, 3.6), (0, -3.4, -16.0), "steel_clean", "-Y の打撃面、擦れて銀"),
          P("face_high", (3.6, 0.6, 3.6), (0, 3.4, -16.0), "steel_worn", "+Y の打撃面"),
          P("wedge", (1.6, 0.4, 1.6), (0, 0, -18.0), "steel_rusty", "頭を留める楔の頭"),
          P("blood", (3.7, 3.0, 3.7), (0, -2.2, -16.0), "blood_wet", "下の面に血・脳片・髪がこびりつく"),
      ]),
    W("rebar_club", "鉄筋コンクリの棍棒", "Rebar Concrete Club", "two_hand_blunt", "blunt", "heavy",
      damage=16, attack_speed=0.75, stamina_cost=20, durability=280, reach=3.4, crit_mult=1.6, knockback=1.3,
      gore_power=0.85, sever_bias=dict(head="crushed", arm="broken", leg="broken"),
      rarity="common", grips=(0.0, -7.0),
      recipe=shaped(["CC", "RC", "R "], {"C": "minecraft:cobblestone", "R": _IRON}),
      palette=["#98988e", "#5e463a", "#6e6e6a", "#2a2a2c", "#5a120c"],
      desc_ja="崩れた柱から引き抜いた鉄筋と、先に残ったコンクリの塊。原始的で重い。",
      desc_en="Rebar pulled from a collapsed pillar with a chunk of concrete still on it. Primitive and heavy.",
      model=[
          P("rebar", (1.0, 1.0, 18.0), (0, 0, -4.0), "rebar", "節のある鉄筋、少し曲がる"),
          P("rebar_2", (0.8, 0.8, 12.0), (0.9, 0.3, -9.0), "rebar", "並走する 2 本目、先で曲がる", rot=(0, 3, 0)),
          P("grip", (1.5, 1.5, 5.0), (0, 0, 1.8), "tape_grey", "ダクトテープと布の握り"),
          P("wire_tie", (2.0, 1.6, 0.5), (0.4, 0.1, -6.0), "steel_worn", "結束線", rep=[(0.4, 0.1, -10.0)]),
          P("chunk", (5.0, 4.6, 6.0), (0.3, -0.2, -15.6), "concrete", "割れたコンクリの塊。角が欠け、骨材の小石が見える",
            rot=(6, 10, -4)),
          P("chunk_2", (3.2, 3.0, 3.0), (-1.4, 1.4, -17.6), "concrete_dark", "塊に付いた小塊", rot=(-12, 20, 8)),
          P("rebar_end", (0.6, 0.6, 2.4), (1.4, -1.4, -19.2), "rebar", "塊から突き出た鉄筋の端（曲がる）", rot=(20, 30, 0)),
          P("blood", (5.2, 3.0, 4.0), (0.3, -1.2, -16.6), "blood_wet", "塊の下面に血と肉片"),
      ]),
    W("sign_axe", "道路標識の斧", "Stop-Sign Axe", "two_hand_blunt", "blunt", "heavy",
      damage=15, attack_speed=0.8, stamina_cost=19, durability=300, reach=3.6, crit_mult=1.7, knockback=1.1,
      gore_power=0.85, sever_bias=dict(head="severed", arm="cut_upper", leg="broken", torso="gutted"),
      alt_dtype="slash", rarity="rare", grips=(0.0, -9.0), recipe=None, unlock_level=7,
      palette=["#b01c1c", "#e8e8e0", "#8a8c8e", "#2a2a2c", "#5a120c"],
      desc_ja="「止まれ」の標識を半分に切り、縁を研いだ斧。叩いても切っても使える。",
      desc_en="A stop sign cut in half with a ground edge. Bash or chop — both work.",
      model=[
          P("post", (1.4, 1.4, 22.0), (0, 0, -6.0), "steel_painted", "角形の標識柱。等間隔の穴（黒い点の列）"),
          P("post_holes", (1.45, 0.4, 0.4), (0, 0, -2.0), "steel_dark", "柱の穴", rep=[(0, 0, -5.0), (0, 0, -8.0), (0, 0, -11.0)]),
          P("grip", (1.6, 1.6, 4.0), (0, 0, 3.0), "tape_black", "黒テープの握り"),
          P("sign", (0.35, 6.0, 7.4), (0, -3.4, -17.6), "steel_painted",
            "赤い八角形の標識の半分。白い縁取りと白文字の一部「ST」、反射材のつぶつぶ"),
          P("sign_back", (0.1, 6.0, 7.4), (0.2, -3.4, -17.6), "aluminium", "裏面はアルミ地、落書き"),
          P("bracket", (1.8, 2.0, 1.4), (0, -0.4, -15.4), "steel_rusty", "標識を留める金具とボルト",
            rep=[(0, -0.4, -19.8)]),
          P("edge", (0.4, 0.4, 7.2), (0, -6.5, -17.6), "steel_clean", "研いだ下の縁（刃）"),
          P("blood", (0.4, 3.6, 5.0), (0, -4.6, -17.8), "blood_wet", "刃の近くに血、白文字にも飛沫"),
      ]),
    W("piston_hammer", "ピストンハンマー", "Piston Hammer", "two_hand_blunt", "blunt", "heavy",
      damage=19, attack_speed=0.65, stamina_cost=24, durability=520, reach=3.4, crit_mult=1.9, knockback=1.5,
      gore_power=0.95, sever_bias=dict(head="crushed", arm="broken", leg="broken"),
      rarity="epic", grips=(0.0, -8.0), recipe=None, unlock_level=13,
      palette=["#4a4c50", "#a8acae", "#b88a3c", "#2a2a2c", "#5a120c"],
      desc_ja="エンジンのピストンとコンロッドをパイプに付けた戦鎚。地面を叩くと周りが吹き飛ぶ。",
      desc_en="An engine piston and con-rod on a pipe. Slam the ground and everything nearby flies.",
      special=dict(ground_slam_radius=2.5, ground_slam_damage=8),
      model=[
          P("pipe", (1.5, 1.5, 20.0), (0, 0, -5.0), "steel_worn", "太い鉄パイプ、溶接の盛り"),
          P("grip", (1.7, 1.7, 4.0), (0, 0, 3.0), "leather_brown", "革を巻いた握り"),
          P("con_rod", (1.2, 1.6, 5.0), (0, 0, -16.0), "steel_dark", "コンロッド（I 字断面）"),
          P("big_end", (2.6, 2.6, 1.4), (0, 0, -13.6), "steel_dark", "コンロッドの大端とボルト 2 本"),
          P("piston", (4.4, 4.4, 4.6), (0, 0, -20.2), "aluminium", "ピストン（八角に見えるよう 2 枚重ね）、上面に煤"),
          P("piston_rings", (4.6, 4.6, 0.4), (0, 0, -21.4), "steel_dark", "ピストンリングの溝", rep=[(0, 0, -20.6)]),
          P("crown", (4.0, 4.0, 0.6), (0, 0, -22.7), "steel_dark", "燃焼室側の黒い冠面（打撃面）"),
          P("weld", (2.0, 2.0, 1.0), (0, 0, -12.6), "steel_rusty", "パイプとの溶接部"),
          P("blood", (4.7, 4.7, 2.0), (0, 0, -22.0), "blood_wet", "冠面と側面に血と脳片"),
      ]),
    # =====================================================================================
    #  槍（stab）
    # =====================================================================================
    W("rebar_spear", "鉄筋の槍", "Rebar Spear", "spear", "pierce", "medium",
      damage=10, attack_speed=1.2, stamina_cost=10, durability=300, reach=4.2, crit_mult=2.0, knockback=0.6,
      gore_power=0.45, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      rarity="common", grips=(0.0, -8.0),
      recipe=shaped(["  B", " R ", "T  "], {"B": "nr:blades", "R": _IRON, "T": "nr:duct_tape"}),
      special=dict(pin_stagger_ticks=20),
      palette=["#5e463a", "#a8acae", "#9a9890", "#8c2a20", "#5a120c"],
      desc_ja="鉄筋の先をグラインダーで尖らせた槍。間合いの外から目を突く。",
      desc_en="Rebar ground to a point. Stab eyes from outside their reach.",
      model=[
          P("shaft", (1.0, 1.0, 28.0), (0, 0, -8.0), "rebar", "節の斜線のある鉄筋、少したわむ"),
          P("grip", (1.4, 1.4, 4.0), (0, 0, 1.6), "tape_grey", "テープの握り"),
          P("grip2", (1.4, 1.4, 3.0), (0, 0, -8.0), "cloth_rag", "左手の位置の布巻き"),
          P("point_1", (0.9, 0.9, 2.4), (0, 0, -23.2), "steel_worn", "研ぎ始め（銀の削り跡）"),
          P("point_2", (0.6, 0.6, 2.0), (0, 0, -25.4), "steel_clean", "尖らせた先"),
          P("point_3", (0.3, 0.3, 1.2), (0, 0, -27.0), "steel_clean", "切っ先"),
          P("flag", (0.2, 2.6, 2.2), (0, -1.4, -21.0), "cloth_red", "結んだ赤い布切れ"),
          P("blood", (1.0, 1.0, 5.0), (0, 0, -24.0), "blood_wet", "先に血、垂れた筋"),
      ]),
    W("pitchfork", "干し草フォーク", "Hay Fork", "spear", "pierce", "medium",
      damage=9, attack_speed=1.2, stamina_cost=10, durability=260, reach=4.0, crit_mult=1.8, knockback=0.9,
      gore_power=0.5, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      rarity="common", grips=(0.0, -9.0),
      recipe=shaped(["I I", "ISI", " S "], {"I": _IRON, "S": _STICK}),
      special=dict(push_back=1.2, hits_max=2),
      palette=["#7e5a3a", "#8a8c8e", "#6e3a20", "#5a120c"],
      desc_ja="農家の四本フォーク。刺して押し返し、二体まで貫く。",
      desc_en="A four-tine farm fork. Stabs and shoves back; pierces up to two.",
      model=[
          P("handle", (1.1, 1.1, 24.0), (0, 0, -6.0), "wood_old", "古い木の柄、手の形に黒ずむ"),
          P("d_grip", (2.4, 2.4, 0.6), (0, 0, 6.4), "wood_dark", "D 字の握り（上辺）"),
          P("socket", (1.4, 1.4, 2.6), (0, 0, -19.0), "steel_rusty", "柄を受ける金具と鋲"),
          P("yoke", (5.0, 1.0, 1.0), (0, 0, -20.6), "steel_rusty", "爪の付け根の横棒"),
          P("tine", (0.4, 0.4, 6.0), (2.2, 0, -24.0), "steel_worn", "爪（4 本、先が少し上へ反る）",
            rep=[(0.75, 0, -24.0), (-0.75, 0, -24.0), (-2.2, 0, -24.0)]),
          P("tine_tip", (0.3, 0.3, 1.0), (2.2, 0.2, -27.4), "steel_clean", "爪の先",
            rep=[(0.75, 0.2, -27.4), (-0.75, 0.2, -27.4), (-2.2, 0.2, -27.4)]),
          P("blood", (5.2, 0.5, 4.0), (0, 0, -25.0), "blood_dry", "爪の先半分に血、間に布切れ"),
      ]),
    W("kitchen_spear", "包丁の槍", "Kitchen-Knife Spear", "spear", "pierce", "light",
      damage=8, attack_speed=1.5, stamina_cost=8, durability=200, reach=4.0, crit_mult=2.2, knockback=0.4,
      gore_power=0.55, sever_bias=dict(head="cracked", arm="cut_lower", leg="wounded", torso="slashed"),
      alt_dtype="slash", rarity="common", grips=(0.0, -8.0),
      recipe=shaped(["  B", " S ", "S  "], {"B": "nr:blades", "S": _STICK}),
      palette=["#b08a5c", "#c8ccd0", "#8e9092", "#2a2a2c", "#5a120c"],
      desc_ja="モップの柄に包丁を針金とテープで縛り付けた槍。軽くて速い。",
      desc_en="A kitchen knife lashed to a mop handle with wire and tape. Light and fast.",
      model=[
          P("handle", (1.0, 1.0, 24.0), (0, 0, -6.0), "wood_raw", "モップの柄、ねじ山の残る先端"),
          P("grip", (1.2, 1.2, 4.0), (0, 0, 2.0), "plastic_blue", "青い樹脂のキャップと握り"),
          P("knife_handle", (1.1, 1.4, 3.6), (0, 0.6, -18.4), "plastic_black", "包丁の柄（柄に沿わせる）"),
          P("lashing", (1.6, 2.0, 3.0), (0, 0.3, -18.4), "steel_worn", "巻いた針金"),
          P("tape", (1.7, 2.1, 1.2), (0, 0.3, -16.6), "tape_grey", "テープ", rep=[(0, 0.3, -20.0)]),
          P("blade", (0.3, 1.8, 6.4), (0, 0.4, -23.4), "steel_clean", "三徳包丁の刃、刃元の刻印"),
          P("tip", (0.3, 1.0, 1.4), (0, 0.1, -27.2), "steel_clean", "切っ先", rot=(20, 0, 0)),
          P("blood", (0.32, 1.4, 3.0), (0, 0.2, -25.0), "blood_wet", "先の血"),
      ]),
    # =====================================================================================
    #  弓・クロスボウ
    # =====================================================================================
    W("survivor_bow", "生存者の弓", "Survivor Bow", "bow", "pierce", "medium",
      damage=14, attack_speed=1.0, stamina_cost=4, durability=350, reach=2.4, crit_mult=2.2, knockback=0.5,
      gore_power=0.5, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      ammo="nr:survivor_arrow", mag=1, reload_ticks=0, spread=0.6, range=48, projectile="nr:proj_arrow",
      charge_ticks=20, noise=4, rarity="uncommon",
      recipe=shaped([" SR", "B R", " SR"], {"S": _STICK, "B": "nr:scrap", "R": "minecraft:string"}),
      special=dict(silent=True, headshot_mult=2.5),
      palette=["#2a2a2c", "#5c623e", "#c8c0a8", "#8a8c8e", "#7a1a14"],
      desc_ja="スキー板を切ったリムに滑車を付けた弓。静かで、頭を射抜けば一撃。",
      desc_en="A bow with limbs cut from skis and a pulley. Silent; a headshot is one kill.",
      model=[
          P("riser", (1.2, 8.0, 1.6), (0, 0, 0), "steel_dark", "金属の握り（ハンドル）、肉抜きの穴 2 つ"),
          P("grip", (1.4, 3.0, 1.9), (0, -0.4, 0.2), "paracord", "パラコードを巻いた握り"),
          P("arrow_rest", (0.6, 0.4, 1.0), (-0.7, 1.4, -0.4), "steel_worn", "矢の置き台"),
          P("limb_upper", (1.0, 9.0, 0.6), (0, 8.4, 1.0), "plastic_black", "上のリム（スキー板、黄色のロゴの欠片）",
            rot=(-12, 0, 0)),
          P("limb_lower", (1.0, 9.0, 0.6), (0, -8.4, 1.0), "plastic_black", "下のリム", rot=(12, 0, 0)),
          P("limb_logo", (1.05, 2.0, 0.65), (0, 9.4, 1.2), "plastic_yellow", "スキー板のロゴの名残", rot=(-12, 0, 0)),
          P("cam", (0.8, 1.8, 1.8), (0, 12.6, 2.0), "aluminium", "上の滑車", rep=[(0, -12.6, 2.0)]),
          P("string", (0.15, 25.0, 0.15), (0, 0, 3.2), "rope", "弦（引くと +Z へ伸びる。アニメで動かす）"),
          P("stabilizer", (0.8, 0.8, 4.0), (0, -2.6, -2.2), "steel_dark", "前へ出た安定棒、先に布の重り"),
          P("sight", (0.4, 1.2, 0.6), (0.8, 2.4, -0.2), "emissive_green", "蛍光の照準ピン（発光）"),
      ]),
    W("crossbow", "改造クロスボウ", "Scrap Crossbow", "crossbow", "pierce", "heavy",
      damage=20, attack_speed=0.6, stamina_cost=6, durability=300, reach=2.4, crit_mult=2.0, knockback=0.9,
      gore_power=0.65, sever_bias=dict(head="crushed", arm="wounded", leg="wounded", torso="slashed"),
      ammo="nr:bolt", mag=1, reload_ticks=30, spread=0.3, range=64, projectile="nr:proj_bolt",
      noise=6, rarity="rare", recipe=None, unlock_level=5,
      special=dict(silent=True, pin_to_wall=True),
      palette=["#3a3c40", "#7a5a3a", "#a8acae", "#e0c040", "#2a2a2c"],
      desc_ja="車の板バネをリムにした重いクロスボウ。ボルトは頭を貫き、死体を壁に縫い留める。",
      desc_en="A heavy crossbow with leaf-spring limbs. Bolts go through heads and pin bodies to walls.",
      model=[
          P("stock", (1.6, 2.2, 14.0), (0, 0, 2.6), "wood_dark", "銃床（ライフルの廃材）、頬当てに布"),
          P("pistol_grip", (1.4, 3.6, 1.8), (0, -2.2, 0.4), "wood_dark", "握り", rot=(16, 0, 0)),
          P("rail", (1.2, 1.0, 14.0), (0, 1.4, -8.0), "aluminium", "矢を乗せる溝付きのレール"),
          P("prod", (16.0, 1.0, 1.6), (0, 1.2, -14.0), "steel_dark", "板バネのリム（左右に張る、少し後ろへ反る）"),
          P("prod_clamp", (2.4, 2.4, 2.2), (0, 1.2, -14.0), "steel_rusty", "リムの留め金とボルト"),
          P("string", (15.0, 0.2, 0.2), (0, 1.6, -9.0), "rope", "弦（引いた状態）"),
          P("stirrup", (3.0, 0.4, 2.4), (0, 1.2, -16.6), "steel_worn", "足掛けの輪"),
          P("trigger", (0.4, 1.0, 0.6), (0, -0.8, -1.2), "steel_dark", "引き金と用心金"),
          P("scope", (1.0, 1.0, 4.0), (0, 2.8, -3.0), "steel_dark", "古い光学照準（レンズに反射）"),
          P("loaded_bolt", (0.4, 0.4, 9.0), (0, 2.1, -11.0), "steel_worn", "装填中のボルト（羽根は黄色）"),
      ]),
    # =====================================================================================
    #  銃（ヒットスキャン: projectile=None。スクリプトのレイ）
    # =====================================================================================
    W("pistol", "拳銃", "Service Pistol", "pistol", "pierce", "light",
      damage=8, attack_speed=4.0, stamina_cost=0, durability=600, reach=2.2, crit_mult=2.0, knockback=0.3,
      gore_power=0.4, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      ammo="nr:ammo_pistol", mag=12, reload_ticks=32, spread=1.5, range=40, noise=32,
      rarity="uncommon", recipe=None, unlock_level=4,
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", shell="nr:shell_casing", impact="nr:impact_dust"),
      palette=["#26282c", "#5a5c60", "#2a2a2c", "#b08a3c"],
      desc_ja="警官の拳銃。音で群れを呼ぶので最後の手段に。",
      desc_en="A police sidearm. The noise draws hordes — a last resort.",
      model=[
          P("slide", (1.3, 1.6, 7.6), (0, 1.6, -2.4), "steel_dark", "スライド。後端と前端にセレーション（縦溝）"),
          P("ejection_port", (0.2, 0.7, 1.6), (0.65, 1.9, -2.0), "brass", "排莢口から見える真鍮"),
          P("frame", (1.2, 1.0, 6.4), (0, 0.4, -2.6), "plastic_black", "樹脂のフレーム、前にレール"),
          P("barrel_tip", (0.7, 0.7, 0.4), (0, 1.7, -6.3), "steel_worn", "銃口"),
          P("grip", (1.3, 4.2, 2.2), (0, -1.6, 0.4), "plastic_black", "握り（細かい梨地）", rot=(14, 0, 0)),
          P("mag_base", (1.3, 0.6, 2.2), (0, -3.8, 1.0), "steel_dark", "弾倉の底", rot=(14, 0, 0)),
          P("trigger_guard", (0.5, 0.4, 2.0), (0, -0.6, -1.6), "plastic_black", "用心金"),
          P("trigger", (0.3, 0.9, 0.4), (0, -0.2, -1.0), "steel_dark", "引き金"),
          P("sights", (0.4, 0.4, 0.5), (0, 2.6, -5.8), "emissive_white", "白い点の照星", rep=[(0, 2.6, 0.9)]),
          P("tape", (1.4, 1.2, 0.8), (0, -0.4, 0.4), "tape_grey", "握りに巻いたテープ（汗止め）", rot=(14, 0, 0)),
      ]),
    W("revolver", "リボルバー", ".44 Revolver", "revolver", "pierce", "medium",
      damage=15, attack_speed=1.6, stamina_cost=0, durability=500, reach=2.2, crit_mult=2.2, knockback=0.7,
      gore_power=0.7, sever_bias=dict(head="crushed", arm="wounded", leg="wounded", torso="slashed"),
      ammo="nr:ammo_pistol", mag=6, reload_ticks=50, spread=1.0, range=48, noise=40,
      rarity="rare", recipe=None, unlock_level=9,
      special=dict(ammo_per_shot=2, overpenetrate=1),
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", impact="nr:impact_dust"),
      palette=["#c4c8cc", "#5e3c24", "#2a2a2c", "#b08a3c"],
      desc_ja="大口径の回転式拳銃。1 発で頭が弾ける（拳銃弾を 2 発使う）。",
      desc_en="A big-bore revolver. One shot pops a head (uses 2 pistol rounds).",
      model=[
          P("barrel", (1.0, 1.2, 6.6), (0, 1.6, -5.6), "chrome", "長い銃身、上にベンチレーテッドリブ"),
          P("ejector_rod", (0.5, 0.5, 4.0), (0, 0.8, -4.6), "chrome", "銃身下の排莢桿の覆い"),
          P("cylinder", (2.2, 2.2, 2.6), (0, 1.2, -1.2), "chrome", "回転弾倉、6 本の縦溝（フルート）"),
          P("frame", (1.2, 2.6, 4.2), (0, 1.0, 0.2), "chrome", "フレーム、曇りと擦れ"),
          P("hammer", (0.5, 1.0, 0.8), (0, 2.6, 1.8), "steel_dark", "撃鉄（ギザ付き）", rot=(-30, 0, 0)),
          P("grip", (1.4, 4.0, 2.0), (0, -1.6, 1.6), "wood_dark", "木の握り、市松の滑り止め", rot=(18, 0, 0)),
          P("trigger_guard", (0.4, 0.4, 2.0), (0, -0.4, -0.6), "chrome", "用心金"),
          P("front_sight", (0.3, 0.6, 0.6), (0, 2.5, -8.6), "steel_dark", "照星"),
      ]),
    W("pump_shotgun", "ポンプ式散弾銃", "Pump Shotgun", "shotgun", "pierce", "heavy",
      damage=4, attack_speed=1.0, stamina_cost=0, durability=450, reach=2.4, crit_mult=1.5, knockback=1.2,
      gore_power=0.95, sever_bias=dict(head="crushed", arm="cut_lower", leg="cut_lower", torso="slashed"),
      ammo="nr:ammo_shotgun", mag=6, reload_ticks=12, spread=7.0, pellets=8, range=18, noise=48,
      rarity="rare", recipe=None, unlock_level=10,
      special=dict(reload_per_shell=True, close_range_blocks=4, close_gore_bonus=0.3),
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", shell="nr:shell_casing", impact="nr:impact_dust"),
      palette=["#26282c", "#2a2a2c", "#5a5c60", "#b01c1c"],
      desc_ja="至近距離で手足を吹き飛ばす。1 発ずつ込める。",
      desc_en="Blows limbs off at close range. Loads one shell at a time.",
      model=[
          P("barrel", (1.0, 1.0, 18.0), (0, 1.4, -11.0), "steel_dark", "銃身、先端に照星"),
          P("mag_tube", (0.9, 0.9, 13.0), (0, 0.2, -9.0), "steel_dark", "銃身下のチューブ弾倉"),
          P("pump", (1.6, 1.6, 5.0), (0, 0.3, -10.0), "plastic_black", "前のポンプ（横溝 6 本）"),
          P("receiver", (1.6, 2.8, 6.4), (0, 1.0, -0.8), "steel_dark", "機関部、排莢口"),
          P("shell_side", (0.3, 0.5, 1.2), (0.85, 1.0, -0.6), "plastic_red", "排莢口に見える赤い実包"),
          P("trigger_guard", (0.5, 1.0, 2.2), (0, -0.6, -0.6), "steel_dark", "用心金と引き金"),
          P("grip", (1.4, 3.0, 2.0), (0, -1.4, 2.8), "plastic_black", "ピストルグリップ風の握り", rot=(20, 0, 0)),
          P("stock", (1.6, 2.6, 8.0), (0, -0.4, 7.6), "plastic_black", "銃床、肩当てのゴム"),
          P("shell_holder", (1.7, 1.4, 3.0), (0, 0.0, 6.4), "leather_brown", "銃床の弾差し（赤い実包 4 発）"),
          P("sling", (0.3, 0.3, 10.0), (-0.9, -1.0, 0.0), "paracord", "スリング（垂れ下がる）"),
      ]),
    W("double_barrel", "二連散弾銃", "Double-Barrel Shotgun", "shotgun", "pierce", "heavy",
      damage=4.5, attack_speed=2.0, stamina_cost=0, durability=380, reach=2.4, crit_mult=1.5, knockback=1.4,
      gore_power=1.0, sever_bias=dict(head="crushed", arm="cut_lower", leg="cut_lower", torso="slashed"),
      ammo="nr:ammo_shotgun", mag=2, reload_ticks=40, spread=9.0, pellets=10, range=14, noise=52,
      rarity="rare", recipe=None, unlock_level=8,
      special=dict(both_barrels_on_heavy=True, close_range_blocks=3, close_gore_bonus=0.4),
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", impact="nr:impact_dust"),
      palette=["#3a3c40", "#7a5a3a", "#b88a3c", "#2a2a2c"],
      desc_ja="中折れの二連銃。重攻撃で 2 発同時に撃ち、群れごと吹き飛ばす。",
      desc_en="A break-action double. Heavy attack fires both barrels and clears a crowd.",
      model=[
          P("barrel_l", (0.9, 0.9, 16.0), (-0.48, 1.3, -9.0), "steel_dark", "左銃身"),
          P("barrel_r", (0.9, 0.9, 16.0), (0.48, 1.3, -9.0), "steel_dark", "右銃身"),
          P("rib", (0.4, 0.3, 16.0), (0, 1.85, -9.0), "steel_worn", "銃身の間の帯"),
          P("forend", (1.6, 1.2, 5.0), (0, 0.4, -6.0), "wood_dark", "先台（木）"),
          P("action", (1.6, 2.2, 3.6), (0, 1.0, 0.4), "steel_worn", "機関部、唐草の彫刻（すり減る）"),
          P("hammers", (0.4, 0.9, 0.7), (0.4, 2.2, 1.8), "steel_dark", "撃鉄 2 つ", rep=[(-0.4, 2.2, 1.8)]),
          P("trigger", (0.3, 0.8, 0.4), (0, -0.2, 0.4), "steel_dark", "引き金 2 本", rep=[(0, -0.2, 1.0)]),
          P("stock", (1.6, 3.0, 10.0), (0, -0.6, 7.0), "wood_dark", "木の銃床、ひびをテープで補修"),
          P("stock_tape", (1.7, 3.1, 1.0), (0, -0.6, 4.6), "tape_grey", "ひびの補修テープ"),
          P("butt_plate", (1.7, 3.2, 0.5), (0, -0.8, 12.2), "rubber_black", "床尾板"),
      ]),
    W("hunting_rifle", "狩猟用ライフル", "Hunting Rifle", "rifle", "pierce", "heavy",
      damage=26, attack_speed=0.9, stamina_cost=0, durability=400, reach=2.4, crit_mult=2.5, knockback=1.0,
      gore_power=0.85, sever_bias=dict(head="crushed", arm="cut_lower", leg="cut_lower", torso="slashed"),
      ammo="nr:ammo_rifle", mag=5, reload_ticks=60, spread=0.2, range=96, noise=64,
      rarity="epic", recipe=None, unlock_level=14,
      special=dict(scope_fov=30, overpenetrate=2),
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", shell="nr:shell_casing", impact="nr:impact_dust"),
      palette=["#26282c", "#7a5a3a", "#b88a3c", "#2a2a2c"],
      desc_ja="ボルトアクションの狩猟銃。遠くの頭を確実に吹き飛ばすが、街中に響く。",
      desc_en="A bolt-action hunting rifle. Takes heads at long range — and the whole city hears it.",
      model=[
          P("barrel", (0.8, 0.8, 18.0), (0, 1.5, -13.0), "steel_dark", "細長い銃身、先にマズルブレーキ"),
          P("muzzle_brake", (1.1, 1.1, 1.6), (0, 1.5, -22.6), "steel_dark", "横穴のあるブレーキ"),
          P("receiver", (1.3, 1.6, 6.0), (0, 1.5, -1.6), "steel_dark", "機関部"),
          P("bolt_handle", (1.8, 0.5, 0.5), (1.0, 1.4, 0.6), "steel_worn", "ボルトの取っ手（右へ）"),
          P("bolt_knob", (0.8, 0.8, 0.8), (1.9, 1.1, 0.6), "steel_worn", "取っ手の玉"),
          P("scope", (1.2, 1.2, 9.0), (0, 3.2, -1.6), "steel_dark", "スコープの胴"),
          P("scope_bell", (1.6, 1.6, 2.0), (0, 3.2, -6.6), "steel_dark", "対物側の広がり、レンズの反射"),
          P("scope_mount", (0.8, 1.0, 0.8), (0, 2.2, -4.0), "steel_worn", "マウント", rep=[(0, 2.2, 0.6)]),
          P("stock", (1.6, 2.6, 22.0), (0, 0.3, -2.0), "wood_dark", "前から後ろまで続く木の銃床、頬当ての盛り上がり"),
          P("grip", (1.4, 2.8, 1.8), (0, -1.4, 2.0), "wood_dark", "握りの首、市松の刻み", rot=(22, 0, 0)),
          P("mag", (1.0, 1.2, 2.0), (0, -0.4, -1.2), "steel_dark", "箱形弾倉の底"),
          P("sling", (0.3, 0.3, 14.0), (-0.9, -1.4, -2.0), "leather_brown", "革のスリング"),
      ]),
    W("scrap_smg", "手製サブマシンガン", "Scrap SMG", "smg", "pierce", "medium",
      damage=5, attack_speed=10.0, stamina_cost=0, durability=500, reach=2.2, crit_mult=1.6, knockback=0.2,
      gore_power=0.55, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      ammo="nr:ammo_pistol", mag=30, reload_ticks=45, spread=4.0, range=32, noise=48,
      rarity="epic", recipe=None, unlock_level=15,
      special=dict(full_auto=True, hold_to_fire=True),
      fx=dict(muzzle="nr:muzzle_flash", tracer="nr:tracer", shell="nr:shell_casing", impact="nr:impact_dust"),
      palette=["#5a5c60", "#2a2a2c", "#9a9c9e", "#c8a040", "#5c623e"],
      desc_ja="水道管と溶接で作った連射銃。長押しで撃ち続ける。弾をばらまき、腕をちぎる。",
      desc_en="A full-auto gun welded from water pipe. Hold to fire. Sprays lead and tears off arms.",
      model=[
          P("receiver", (1.6, 1.6, 9.0), (0, 1.2, -2.0), "steel_worn", "水道管の機関部、溶接のビード"),
          P("barrel_shroud", (1.4, 1.4, 6.0), (0, 1.2, -9.4), "steel_dark", "穴をあけた放熱筒（円い穴の列）"),
          P("barrel_tip", (0.7, 0.7, 1.0), (0, 1.2, -12.8), "steel_dark", "銃口"),
          P("mag", (0.8, 5.6, 1.6), (-1.4, 1.2, -4.0), "steel_dark", "左へ突き出した横差しの長い弾倉", rot=(0, 0, 90)),
          P("grip", (1.3, 3.6, 1.8), (0, -1.0, 0.4), "tape_black", "テープを巻いた握り", rot=(12, 0, 0)),
          P("trigger_guard", (0.4, 0.4, 2.0), (0, -0.2, -1.2), "steel_worn", "針金の用心金"),
          P("fore_grip", (1.0, 3.0, 1.2), (0, -0.8, -7.4), "wood_raw", "前の縦握り（木の端材）"),
          P("stock_wire", (0.4, 0.4, 8.0), (0, 0.8, 6.0), "steel_worn", "折り曲げた鉄筋のストック（2 本）",
            rep=[(0, -0.8, 6.0)]),
          P("butt", (0.6, 2.6, 0.6), (0, 0, 10.0), "steel_worn", "ストックの肩当て"),
          P("cocking", (0.8, 0.4, 0.8), (0.9, 1.6, -0.8), "brass", "コッキングハンドル（ボルトの頭）"),
      ]),
    # =====================================================================================
    #  投擲（stack 個で持ち、投げると減る）
    # =====================================================================================
    W("throwing_knives", "投げナイフ", "Throwing Knives", "throwable", "pierce", "light",
      damage=9, attack_speed=2.0, stamina_cost=4, durability=0, reach=2.4, crit_mult=2.4, knockback=0.2,
      gore_power=0.35, sever_bias=dict(head="cracked", arm="wounded", leg="wounded", torso="slashed"),
      range=24, projectile="nr:proj_throwing_knife", charge_ticks=6, stack=16, noise=2, rarity="common",
      recipe=None, special=dict(retrievable=True, silent=True),
      palette=["#3a3c40", "#c8ccd0", "#2a2a2c"],
      desc_ja="重心を先に寄せた投げナイフ。音を立てず、拾って使い回せる。",
      desc_en="Front-weighted throwing knives. Silent and reusable.",
      model=[
          P("blade", (0.3, 1.2, 4.4), (0, 0, -3.2), "steel_dark", "黒染めの両刃（ダイヤ形）"),
          P("edge", (0.32, 1.4, 3.0), (0, 0, -3.6), "steel_clean", "銀の研ぎ出し"),
          P("handle", (0.4, 1.0, 3.2), (0, 0, 0.6), "steel_dark", "肉抜き穴 2 つの柄"),
          P("cord", (0.6, 1.2, 2.0), (0, 0, 0.8), "paracord", "パラコードの柄巻き"),
          P("ring", (0.4, 1.0, 0.8), (0, 0, 2.6), "steel_worn", "柄尻の輪"),
      ]),
    W("throwing_stars", "刃の手裏剣", "Blade Stars", "throwable", "slash", "light",
      damage=6, attack_speed=3.0, stamina_cost=3, durability=0, reach=2.4, crit_mult=2.0, knockback=0.1,
      gore_power=0.4, sever_bias=dict(head="jawless", arm="cut_lower", leg="wounded", torso="slashed"),
      range=22, projectile="nr:proj_throwing_star", charge_ticks=0, stack=16, noise=2, rarity="common",
      recipe=None, special=dict(retrievable=True, silent=True, innate_bleed_chance=0.35),
      palette=["#9a9c9e", "#c8ccd0", "#7a5236", "#5a120c"],
      desc_ja="丸ノコの刃を四つ角に切った手裏剣。連投でき、出血させる。",
      desc_en="Saw blades cut into four-point stars. Throw rapidly; causes bleeding.",
      model=[
          P("core", (1.4, 0.25, 1.4), (0, 0, 0), "steel_worn", "中心の円盤、軸穴（黒い円）"),
          P("point_a", (0.8, 0.22, 4.4), (0, 0, 0), "steel_clean", "斜めに伸びる 2 本の刃先（菱形に研ぐ）", rot=(0, 45, 0)),
          P("point_b", (0.8, 0.22, 4.4), (0, 0, 0), "steel_clean", "もう一組の刃先（直交）", rot=(0, -45, 0)),
          P("teeth", (3.0, 0.24, 0.5), (0, 0, 0), "steel_rusty", "元の丸ノコの歯の名残", rot=(0, 0, 0)),
          P("blood", (1.2, 0.26, 1.6), (0.6, 0, 0.6), "blood_dry", "刃先の血"),
      ]),
    W("molotov", "火炎瓶", "Molotov", "throwable", "fire", "light",
      damage=3, attack_speed=1.0, stamina_cost=5, durability=0, reach=2.4, crit_mult=1.0, knockback=0.0,
      gore_power=0.0, sever_bias={}, range=20, projectile="nr:proj_molotov", charge_ticks=8, stack=8, noise=10,
      rarity="common", recipe=None,
      special=dict(fire_radius=3.5, burn_ticks=120, burn_dps=3, puddle_ticks=160, sets_burn=2),
      fx=dict(trail="nr:flame", impact="nr:fire_burst"),
      palette=["#6a4a1c", "#c8b890", "#ff9a30", "#3a3a3c"],
      desc_ja="アルコールと布の火炎瓶。割れた所に火の海。焼けた体は炭になり、もろく崩れる。",
      desc_en="Alcohol and a rag. A sea of fire where it breaks. Burnt bodies char and crumble.",
      model=[
          P("bottle", (1.8, 3.4, 1.8), (0, 0, 0), "glass_tinted", "茶色い酒瓶、液面が見える（半透明）"),
          P("shoulder", (1.4, 0.8, 1.4), (0, 2.0, 0), "glass_tinted", "瓶の肩"),
          P("neck", (0.8, 1.6, 0.8), (0, 3.0, 0), "glass_tinted", "瓶の首"),
          P("label", (1.85, 1.6, 1.85), (0, -0.2, 0), "paper", "破れた酒のラベル"),
          P("rag", (0.9, 2.2, 0.9), (0, 4.4, 0), "cloth_rag", "口に詰めた布、先が垂れる", rot=(0, 0, 15)),
          P("flame", (1.2, 1.6, 1.2), (0.3, 5.8, 0), "emissive_amber", "布の先の炎（発光、アニメで揺らす）"),
          P("tape", (1.85, 0.6, 1.85), (0, 1.2, 0), "tape_grey", "布を留めるテープ"),
      ]),
    W("pipe_bomb", "パイプ爆弾", "Pipe Bomb", "throwable", "blast", "medium",
      damage=40, attack_speed=1.0, stamina_cost=5, durability=0, reach=2.4, crit_mult=1.0, knockback=2.5,
      gore_power=1.0, sever_bias=dict(head="crushed", arm="cut_upper", leg="cut_upper", torso="halved"),
      range=18, projectile="nr:proj_pipe_bomb", charge_ticks=8, stack=8, noise=64, rarity="uncommon",
      recipe=None, special=dict(fuse_ticks=50, blast_radius=5.0, falloff=0.6, gib_burst=True,
                                beeps_lure=True),
      fx=dict(trail="nr:fuse_spark", impact="nr:explosion"),
      palette=["#6e7072", "#e0c040", "#2a2a2c", "#b01c1c"],
      desc_ja="釘を巻いた鉄パイプの爆弾。導火線が燃える間、音で敵を引き寄せてから吹き飛ばす。",
      desc_en="A nail-wrapped pipe bomb. The hissing fuse draws them in — then everything flies apart.",
      model=[
          P("pipe", (1.6, 1.6, 4.4), (0, 0, 0), "steel_worn", "亜鉛めっきのパイプ"),
          P("cap", (2.0, 2.0, 0.8), (0, 0, -2.4), "iron_cast", "両端のねじ込み蓋", rep=[(0, 0, 2.4)]),
          P("nails", (1.9, 1.9, 3.0), (0, 0, 0), "steel_rusty", "テープで巻き付けた釘の層（斜めに並ぶ頭）"),
          P("tape", (2.0, 2.0, 0.8), (0, 0, -1.0), "tape_black", "黒テープ", rep=[(0, 0, 1.0)]),
          P("fuse", (0.3, 0.3, 2.0), (0, 0.4, 3.6), "plastic_yellow", "黄色い導火線（先が火花）", rot=(30, 0, 0)),
          P("spark", (0.6, 0.6, 0.6), (0, 0.9, 4.5), "emissive_amber", "火花（発光）"),
          P("warning", (2.05, 0.8, 1.6), (0, 0.6, 0), "plastic_red", "赤い「危険」のステッカー"),
      ]),
    W("firecracker", "爆竹", "Firecracker Lure", "throwable", "blast", "light",
      damage=0, attack_speed=1.0, stamina_cost=3, durability=0, reach=2.4, crit_mult=1.0, knockback=0.0,
      gore_power=0.0, sever_bias={}, range=22, projectile="nr:proj_firecracker", charge_ticks=4, stack=16,
      noise=28, rarity="common", recipe=None,
      special=dict(lure_radius=28, lure_ticks=120, lure_pull=1.0),
      fx=dict(impact="nr:firecracker_pop"),
      palette=["#c01c1c", "#e0c040", "#2a2a2c"],
      desc_ja="鳴り続ける爆竹の束。6 秒間、周りの感染者を引き寄せる。",
      desc_en="A bundle of crackling firecrackers. Draws nearby infected for 6 seconds.",
      model=[
          P("bundle", (2.2, 3.0, 1.4), (0, 0, 0), "plastic_red", "赤い紙筒を束ねる（縦の筋で 8 本に見せる）"),
          P("band", (2.3, 0.6, 1.5), (0, 0.4, 0), "plastic_yellow", "金色の帯（漢字風の模様）"),
          P("fuse", (0.25, 2.4, 0.25), (0, 2.6, 0), "paper", "より合わせた導火線", rot=(0, 0, 20)),
          P("spark", (0.5, 0.5, 0.5), (0.4, 3.8, 0), "emissive_amber", "火花"),
      ]),
    W("uv_flare", "UV 発煙筒", "UV Flare", "throwable", "uv", "light",
      damage=0, attack_speed=1.0, stamina_cost=3, durability=0, reach=2.4, crit_mult=1.0, knockback=0.0,
      gore_power=0.0, sever_bias={}, range=22, projectile="nr:proj_uv_flare", charge_ticks=4, stack=8, noise=6,
      rarity="uncommon", recipe=None,
      special=dict(uv_radius=7, uv_ticks=240, uv_dps=2, night_stun_ticks=40, light_level=12, immunity_regen=1.0),
      fx=dict(trail="nr:uv_glow", impact="nr:uv_glow"),
      palette=["#7a3ac8", "#e0d8ff", "#2a2a2c"],
      desc_ja="紫外線を出す発煙筒。12 秒間、夜の感染者を寄せ付けない安全圏を作る。",
      desc_en="A UV-emitting flare. Makes a 12-second safe zone night infected won't enter.",
      model=[
          P("tube", (1.0, 4.4, 1.0), (0, 0, 0), "plastic_white", "白い筒に紫の帯と注意書き"),
          P("band", (1.05, 0.8, 1.05), (0, 0.6, 0), "fungus_uv", "紫の帯", rep=[(0, -1.0, 0)]),
          P("cap", (1.2, 0.8, 1.2), (0, -2.6, 0), "plastic_black", "黒い尻蓋"),
          P("head", (0.9, 0.8, 0.9), (0, 2.6, 0), "emissive_uv", "燃える先端（強い紫の光）"),
      ]),
]


# ===========================================================================
#  飛び道具エンティティ（ID nr:proj_<key>）— プレイヤー側のものだけ。
#  ゾンビが吐く・投げるもの（proj_spit など）は nr_spec_zombies が持つ。
#  speed はブロック/tick、gravity はブロック/tick²。on_hit: stick（刺さって残る）/ shatter（割れる）/
#  bounce（跳ねて止まる）
# ===========================================================================
def _proj(key, ja, en, *, speed, gravity, on_hit, lifetime_ticks, pickup=None, pickup_chance=0.0,
          spin=None, trail=None, hitbox=(0.25, 0.25), restitution=0.0, model=()):
    return dict(key=key, id="nr:proj_" + key, ja=ja, en=en, speed=speed, gravity=gravity, on_hit=on_hit,
                lifetime_ticks=lifetime_ticks, pickup=pickup, pickup_chance=pickup_chance, spin=spin,
                trail=trail, hitbox=hitbox, restitution=restitution, model=list(model),
                geometry="geometry.nr.proj." + key)


PROJECTILES = [
    _proj("arrow", "生存者の矢", "Survivor Arrow", speed=3.0, gravity=0.05, on_hit="stick",
          lifetime_ticks=1200, pickup="nr:survivor_arrow", pickup_chance=0.75, trail="nr:arrow_trail",
          model=[P("shaft", (0.3, 0.3, 10.0), (0, 0, 0), "wood_raw", "竹の矢柄、節"),
                 P("head", (0.2, 0.9, 1.6), (0, 0, -5.6), "steel_clean", "刃の破片を研いだ矢じり、針金で巻く"),
                 P("vane", (0.1, 0.8, 2.0), (0, 0.5, 4.0), "plastic_yellow", "切った樹脂の羽根（3 枚、120 度）",
                   rep=[(0.45, -0.25, 4.0), (-0.45, -0.25, 4.0)])]),
    _proj("bolt", "ボルト", "Crossbow Bolt", speed=4.0, gravity=0.03, on_hit="stick", lifetime_ticks=1200,
          pickup="nr:bolt", pickup_chance=0.8, trail="nr:arrow_trail",
          model=[P("shaft", (0.4, 0.4, 7.0), (0, 0, 0), "rebar", "短い鉄筋の矢柄"),
                 P("head", (0.6, 0.6, 1.4), (0, 0, -4.0), "steel_clean", "四角錐に研いだ先"),
                 P("vane", (0.1, 0.9, 1.6), (0, 0.55, 2.8), "plastic_yellow", "黄色い羽根 3 枚",
                   rep=[(0.48, -0.28, 2.8), (-0.48, -0.28, 2.8)])]),
    _proj("throwing_knife", "投げナイフ", "Throwing Knife", speed=2.0, gravity=0.06, on_hit="stick",
          lifetime_ticks=1200, pickup="nr:w_throwing_knives", pickup_chance=0.9, spin="x_fast",
          model=[P("blade", (0.3, 1.2, 4.4), (0, 0, -1.6), "steel_dark", "黒染めの刃"),
                 P("handle", (0.4, 1.0, 3.2), (0, 0, 2.2), "paracord", "コード巻きの柄")]),
    _proj("throwing_star", "刃の手裏剣", "Blade Star", speed=2.4, gravity=0.04, on_hit="stick",
          lifetime_ticks=1200, pickup="nr:w_throwing_stars", pickup_chance=0.85, spin="y_fast",
          model=[P("core", (1.4, 0.25, 1.4), (0, 0, 0), "steel_worn", "中心の円盤"),
                 P("point_a", (0.8, 0.22, 4.4), (0, 0, 0), "steel_clean", "刃先", rot=(0, 45, 0)),
                 P("point_b", (0.8, 0.22, 4.4), (0, 0, 0), "steel_clean", "刃先", rot=(0, -45, 0))]),
    _proj("molotov", "火炎瓶", "Molotov", speed=1.2, gravity=0.08, on_hit="shatter", lifetime_ticks=200,
          spin="x_slow", trail="nr:flame",
          model=[P("bottle", (1.8, 3.4, 1.8), (0, 0, 0), "glass_tinted", "茶色い瓶"),
                 P("rag", (0.9, 2.0, 0.9), (0, 2.6, 0), "cloth_rag", "燃える布"),
                 P("flame", (1.2, 1.6, 1.2), (0, 4.0, 0), "emissive_amber", "炎")]),
    _proj("pipe_bomb", "パイプ爆弾", "Pipe Bomb", speed=1.0, gravity=0.08, on_hit="bounce", lifetime_ticks=50,
          spin="x_slow", trail="nr:fuse_spark", restitution=0.3,
          model=[P("pipe", (1.6, 1.6, 4.4), (0, 0, 0), "steel_worn", "パイプ"),
                 P("cap", (2.0, 2.0, 0.8), (0, 0, -2.4), "iron_cast", "蓋", rep=[(0, 0, 2.4)]),
                 P("spark", (0.6, 0.6, 0.6), (0, 0.9, 3.4), "emissive_amber", "導火線の火花（点滅）")]),
    _proj("firecracker", "爆竹", "Firecracker", speed=1.1, gravity=0.08, on_hit="bounce", lifetime_ticks=120,
          spin="x_slow", trail="nr:fuse_spark", restitution=0.25,
          model=[P("bundle", (2.2, 3.0, 1.4), (0, 0, 0), "plastic_red", "赤い束"),
                 P("spark", (0.5, 0.5, 0.5), (0, 2.0, 0), "emissive_amber", "火花")]),
    _proj("uv_flare", "UV 発煙筒", "UV Flare", speed=1.1, gravity=0.08, on_hit="bounce", lifetime_ticks=240,
          spin="x_slow", trail="nr:uv_glow", restitution=0.2,
          model=[P("tube", (1.0, 4.4, 1.0), (0, 0, 0), "plastic_white", "白い筒"),
                 P("head", (0.9, 0.8, 0.9), (0, 2.6, 0), "emissive_uv", "紫の光")]),
]

# ===========================================================================
#  武器の改造（ItemStack の動的プロパティ nr:mods に {key: 段階} で保存、説明文に出す）
#  端末の「改造」画面で、手に持った武器へ材料を払って付ける。段階 1〜3。
#  chance は 1 撃ごとの発動確率、ticks は効果の長さ。vs は相手の区分への倍率（cls は nr_spec_zombies の cls）
# ===========================================================================
MODS = [
    dict(key="fire", ja="火炎", en="Fire", dtype="fire", applies_to=("melee", "bow", "crossbow"),
         tiers=[dict(level=1, chance=0.30, dps=2.0, ticks=60, sets_burn=1,
                     cost=[("nr:alcohol", 2), ("nr:rags", 2), ("nr:scrap", 2)]),
                dict(level=2, chance=0.45, dps=3.0, ticks=80, sets_burn=2,
                     cost=[("nr:alcohol", 3), ("nr:chemicals", 1), ("nr:infected_trophy", 1)]),
                dict(level=3, chance=0.60, dps=4.0, ticks=100, sets_burn=3, spread_radius=2.0,
                     cost=[("nr:alcohol", 4), ("nr:chemicals", 2), ("nr:volatile_trophy", 1)])],
         vs=dict(common=1.0, viral=1.0, special=0.9, night=0.8, boss=0.7),
         visual=dict(glow_rgb=(255, 120, 30), particle="nr:flame", particle_rgb=(255, 150, 50),
                     trail="nr:ember_trail", tint_rgb=(255, 90, 20)),
         sound="nr.w.mod_fire", lore_ja="当たると燃え上がる。燃えた感染者は炭になって崩れる。",
         lore_en="Sets targets ablaze. Burnt infected char and crumble."),
    dict(key="shock", ja="感電", en="Shock", dtype="shock", applies_to=("melee", "bow", "crossbow"),
         tiers=[dict(level=1, chance=0.25, damage=3, stun_ticks=30, chain=1, chain_radius=3.0,
                     cost=[("nr:battery", 2), ("nr:scrap", 2), ("nr:duct_tape", 1)]),
                dict(level=2, chance=0.35, damage=4, stun_ticks=40, chain=2, chain_radius=3.5,
                     cost=[("nr:battery", 3), ("nr:scrap", 3), ("nr:infected_trophy", 1)]),
                dict(level=3, chance=0.50, damage=6, stun_ticks=50, chain=3, chain_radius=4.0,
                     cost=[("nr:battery", 4), ("nr:chemicals", 1), ("nr:volatile_trophy", 1)])],
         vs=dict(common=1.0, viral=1.1, special=1.0, night=1.0, boss=0.6),
         visual=dict(glow_rgb=(110, 190, 255), particle="nr:spark_shock", particle_rgb=(150, 210, 255),
                     trail="nr:shock_arc", tint_rgb=(90, 160, 255)),
         sound="nr.w.mod_shock", lore_ja="電撃で痺れさせ、近くの敵へ連鎖する。",
         lore_en="Stuns with electricity and chains to nearby enemies."),
    dict(key="bleed", ja="出血", en="Bleed", dtype="slash", applies_to=("melee",),
         tiers=[dict(level=1, chance=0.40, dps=1.5, ticks=100, gore_power_add=0.05,
                     cost=[("nr:blades", 3), ("nr:scrap", 1), ("nr:duct_tape", 1)]),
                dict(level=2, chance=0.55, dps=2.0, ticks=100, gore_power_add=0.10,
                     cost=[("nr:blades", 4), ("nr:infected_trophy", 1)]),
                dict(level=3, chance=0.70, dps=3.0, ticks=120, gore_power_add=0.15,
                     cost=[("nr:blades", 6), ("nr:volatile_trophy", 1)])],
         vs=dict(common=1.0, viral=1.0, special=1.0, night=0.9, boss=0.8),
         visual=dict(glow_rgb=(200, 20, 20), particle="nr:bleed_drip", particle_rgb=(140, 0, 0),
                     trail="nr:blood_trail", tint_rgb=(160, 10, 10)),
         sound="nr.w.mod_bleed", lore_ja="傷口から血が噴き続ける。部位も落ちやすくなる。",
         lore_en="Wounds keep spurting. Limbs come off more easily."),
    dict(key="toxic", ja="毒", en="Toxic", dtype="toxic", applies_to=("melee", "bow", "crossbow"),
         tiers=[dict(level=1, chance=0.30, dps=1.5, ticks=100, cloud_radius=1.5, slow=0.2,
                     cost=[("nr:chemicals", 2), ("nr:mutated_tissue", 1)]),
                dict(level=2, chance=0.40, dps=2.5, ticks=100, cloud_radius=2.0, slow=0.3,
                     cost=[("nr:chemicals", 3), ("nr:mutated_tissue", 2), ("nr:infected_trophy", 1)]),
                dict(level=3, chance=0.50, dps=3.5, ticks=120, cloud_radius=2.5, slow=0.4,
                     cost=[("nr:chemicals", 4), ("nr:mutated_tissue", 3), ("nr:volatile_trophy", 1)])],
         vs=dict(common=1.0, viral=1.0, special=0.8, night=1.0, boss=0.7),
         visual=dict(glow_rgb=(120, 230, 60), particle="nr:toxic_gas", particle_rgb=(130, 220, 70),
                     trail="nr:toxic_drip", tint_rgb=(90, 200, 40)),
         sound="nr.w.mod_toxic", lore_ja="毒の霧をまとい、当たった敵と周りを蝕んで鈍らせる。",
         lore_en="Releases a toxic mist that eats at and slows the target and those nearby."),
    dict(key="uv", ja="UV", en="UV", dtype="uv", applies_to=("melee", "bow", "crossbow"),
         tiers=[dict(level=1, night_mult=1.25, night_stun_ticks=20, immunity_on_kill_s=5,
                     cost=[("nr:uv_shroom", 3), ("nr:battery", 1), ("nr:scrap", 2)]),
                dict(level=2, night_mult=1.40, night_stun_ticks=30, immunity_on_kill_s=8,
                     cost=[("nr:uv_shroom", 4), ("nr:battery", 2), ("nr:volatile_trophy", 1)]),
                dict(level=3, night_mult=1.60, night_stun_ticks=40, immunity_on_kill_s=12,
                     cost=[("nr:uv_shroom", 6), ("nr:battery", 2), ("nr:apex_trophy", 1)])],
         vs=dict(common=1.0, viral=1.0, special=1.0, night=1.6, boss=1.2),
         visual=dict(glow_rgb=(160, 80, 255), particle="nr:uv_glow", particle_rgb=(170, 110, 255),
                     trail="nr:uv_trail", tint_rgb=(140, 70, 255)),
         sound="nr.w.mod_uv", lore_ja="刃が紫外線を帯びる。夜の捕食者に大きく効き、倒すと免疫が戻る。",
         lore_en="The weapon carries UV light. Devastating to night predators; kills restore immunity."),
    dict(key="impact", ja="衝撃", en="Impact", dtype="blunt", applies_to=("melee", "crossbow"),
         only_dtypes=("blunt", "pierce"),
         tiers=[dict(level=1, knockback_add=0.4, stagger_chance=0.35, bone_break_add=0.15,
                     cost=[("nr:scrap", 4), ("nr:duct_tape", 1), ("nr:gunpowder_pouch", 1)]),
                dict(level=2, knockback_add=0.6, stagger_chance=0.50, bone_break_add=0.25,
                     cost=[("nr:scrap", 6), ("nr:gunpowder_pouch", 2), ("nr:infected_trophy", 1)]),
                dict(level=3, knockback_add=0.8, stagger_chance=0.65, bone_break_add=0.35,
                     cost=[("nr:scrap", 8), ("nr:gunpowder_pouch", 3), ("nr:volatile_trophy", 1)])],
         vs=dict(common=1.0, viral=1.0, special=1.1, night=1.0, boss=0.8),
         visual=dict(glow_rgb=(240, 236, 220), particle="nr:impact_ring", particle_rgb=(230, 225, 210),
                     trail="nr:dust_trail", tint_rgb=(220, 210, 190)),
         sound="nr.w.mod_impact", lore_ja="当たった瞬間に小さな破裂。吹き飛ばし、骨を砕く。",
         lore_en="A small blast on contact. Sends them flying and shatters bone."),
]

# ===========================================================================
#  罠（ブロックは nr:<key>、動く物は小道具 nr:prop_<key>、車のアラームは小道具の仕掛け）
#  trigger.type: step（踏む）/ proximity（近づく）/ hit（叩く・撃つ・爆発・火）/ fire（火が付く）/
#                cut（縄を切る）/ timer / interact
#  gore: 罠が起こしやすい部位の結果 {部位: (結果, G=100 での確率)}
# ===========================================================================
def _trap(key, ja, en, block_or_entity, *, trigger, effect, gore, rearm, recipe, model=(), prop=None,
          props=(), light_emission=0, sfx=None, fx=None, desc_ja="", desc_en="", **extra):
    tid = {"block": "nr:" + key, "prop": "nr:prop_" + (prop or key), "prop_interaction": None}[block_or_entity]
    d = dict(key=key, id=tid, ja=ja, en=en, block_or_entity=block_or_entity, trigger=trigger,
             effect=effect, gore=gore, rearm=rearm, recipe=recipe, model=list(model), prop=prop,
             props=list(props), light_emission=light_emission, sfx=sfx or {}, fx=fx or {},
             desc_ja=desc_ja, desc_en=desc_en)
    d.update(extra)   # 例: sever_on_struggle（トラバサミでもがくと脛がちぎれる）
    return d


TRAPS = [
    _trap("electric_trap", "電気トラップ", "Electric Trap", "block",
          trigger=dict(type="proximity", radius=1.6, who="zombie", needs_charge=True),
          effect=dict(damage=8, dtype="shock", stun_ticks=60, chain=3, chain_radius=3.0, sets_shock=1,
                      sets_burn=1, charges=6),
          gore=dict(head=("cracked", 0.15)),
          rearm=dict(mode="recharge", ticks=200, refill=[("nr:battery", 1)]),
          recipe=shaped(["CBC", "SSS"], {"C": "minecraft:copper_ingot", "B": "nr:battery", "S": "nr:scrap"}),
          light_emission=3, sfx=dict(trigger="nr.trap.zap", idle="nr.trap.hum"),
          fx=dict(trigger="nr:spark_shock", idle="nr:spark_small"),
          desc_ja="踏み板とコイル。感染者が近づくと放電し、周りへ連鎖する。電池 1 個で 6 回。",
          desc_en="A plate and coils. Discharges when infected approach, chaining to others. 6 zaps per battery.",
          model=[P("plate", (14, 1, 14), (0, 0.5, 0), "steel_rusty", "錆びた鉄板、縞鋼板の模様"),
                 P("coil", (3, 4, 3), (-4.5, 3, -4.5), "copper_wire", "銅線を巻いたコイル（4 隅）",
                   rep=[(4.5, 3, -4.5), (-4.5, 3, 4.5), (4.5, 3, 4.5)]),
                 P("battery", (5, 4, 3), (0, 3, 5), "plastic_black", "車のバッテリー、赤と黒の端子"),
                 P("wire", (0.6, 0.6, 9), (0, 1.3, 0), "rubber_black", "コイルをつなぐ電線（十字）",
                   rep=[(0, 1.3, 0)]),
                 P("lamp", (1.2, 1.2, 1.2), (2, 5.4, 5), "emissive_blue", "充電の青いランプ（発光）")]),
    _trap("spike_trap", "スパイクの罠", "Spike Trap", "block",
          trigger=dict(type="step", who="any_mob", players=False),
          effect=dict(damage=10, dtype="pierce", slow=0.7, slow_ticks=60, root_ticks=20, durability=20),
          gore=dict(leg=("broken", 0.6), torso=("slashed", 0.35)),
          rearm=dict(mode="durable", uses=20, repair=[("nr:scrap", 2)]),
          recipe=shaped(["R R", "RRR", "PPP"], {"R": _IRON, "P": _PLANK}),
          sfx=dict(trigger="nr.trap.impale"), fx=dict(trigger="nr:blood_spray"),
          desc_ja="板に尖らせた鉄筋を並べた罠。踏んだ足を串刺しにし、倒れれば腹が裂ける。",
          desc_en="Sharpened rebar on a board. Impales the foot that steps in; a fall rips the belly.",
          model=[P("board", (16, 1.5, 16), (0, 0.75, 0), "plywood", "黒ずんだ合板"),
                 P("spike", (1, 9, 1), (-5, 6, -5), "rebar", "先を研いだ鉄筋（9 本、高さを変えて斜めに）",
                   rot=(8, 0, -6),
                   rep=[(0, 6.5, -5.5), (5, 5.5, -5), (-5.5, 6, 0), (0, 7, 0), (5, 6, 0.5), (-5, 5.5, 5),
                        (0.5, 6, 5.5), (5, 6.5, 5)]),
                 P("blood", (8, 0.2, 7), (1, 1.6, 1), "blood_dry", "板に染みた血"),
                 P("cloth", (2, 3, 0.2), (0, 6, 0), "cloth_rag", "鉄筋に引っかかった布切れ")]),
    _trap("bear_trap", "トラバサミ", "Bear Trap", "block",
          trigger=dict(type="step", who="any_mob", players=True),
          effect=dict(damage=9, dtype="pierce", hold_ticks=120, player_damage=4, player_hold_ticks=40),
          gore=dict(leg=("broken", 0.7)),
          sever_on_struggle=dict(leg="cut_lower", chance=0.35),
          rearm=dict(mode="interact", ticks=20),
          recipe=shaped(["S S", "BIB", "SSS"], {"S": "nr:scrap", "B": "nr:blades", "I": _IRON}),
          sfx=dict(trigger="nr.trap.snap"), fx=dict(trigger="nr:blood_spray"),
          desc_ja="鋼の顎。挟んだ感染者を 6 秒止め、もがくと脛ごとちぎれる。開いて使い直せる。",
          desc_en="Steel jaws. Holds infected for 6 s; if they struggle, the shin tears off. Re-set by hand.",
          model=[P("base", (6, 1, 6), (0, 0.5, 0), "steel_dark", "中央の踏み板"),
                 P("jaw", (12, 1, 1.2), (0, 1.2, -4.6), "steel_rusty", "開いた顎の弧（内側にギザギザの歯）",
                   rep=[(0, 1.2, 4.6)]),
                 P("jaw_side", (1.2, 1, 9), (-6, 1.2, 0), "steel_rusty", "顎の側面", rep=[(6, 1.2, 0)]),
                 P("teeth", (11, 1.6, 0.6), (0, 1.8, -4.0), "steel_worn", "歯の列", rep=[(0, 1.8, 4.0)]),
                 P("spring", (2, 2, 4), (-7, 1.2, 0), "steel_dark", "板バネ", rep=[(7, 1.2, 0)]),
                 P("chain", (0.6, 0.6, 5), (0, 0.4, 7.5), "steel_worn", "地面へ打つ杭への鎖"),
                 P("stake", (1.2, 1.2, 1.2), (0, 0.6, 10.5), "iron_cast", "杭の頭（隣のマスへはみ出す）")]),
    _trap("fuel_canister", "燃料缶", "Explosive Fuel Can", "block",
          trigger=dict(type="hit", by=("melee", "projectile", "bullet", "fire", "explosion")),
          effect=dict(damage=28, dtype="blast", radius=4.0, falloff=0.55, knockback=2.0, fire_radius=3.0,
                      fire_ticks=100, sets_burn=2, fuse_ticks=6),
          gore=dict(head=("crushed", 0.5), arm=("cut_upper", 0.6), leg=("cut_upper", 0.6), torso=("halved", 0.3)),
          rearm=None,
          recipe=shaped(["S S", "SAS", "SAS"], {"S": "nr:scrap", "A": "nr:alcohol"}),
          sfx=dict(trigger="nr.trap.explode"), fx=dict(trigger="nr:explosion", after="nr:flame"),
          desc_ja="赤い携行缶。叩くか撃つと爆発し、周りを燃やす。",
          desc_en="A red jerry can. Hit or shoot it and it explodes into flames.",
          model=[P("body", (6, 12, 10), (0, 6, 0), "plastic_red", "角形の携行缶、側面に X のプレス"),
                 P("press_x", (6.2, 9, 0.6), (0, 6, 0), "plastic_red", "側面の X 字の凸（テクスチャの陰影）"),
                 P("handle", (5, 2, 1), (0, 13, -2.4), "plastic_red", "上の 3 連の取っ手", rep=[(0, 13, 0), (0, 13, 2.4)]),
                 P("spout", (2, 3, 2), (0, 13.5, 3.8), "plastic_black", "注ぎ口とキャップ"),
                 P("label", (6.1, 3, 4), (0, 7, -2), "plastic_yellow", "黄色の「可燃性」ラベルと炎の記号"),
                 P("drip", (2, 0.2, 3), (1, 0.1, 3), "fuel", "床に垂れた油膜")]),
    _trap("propane_tank", "プロパンボンベ", "Propane Tank", "prop", prop="propane_tank",
          trigger=dict(type="hit", by=("projectile", "bullet", "fire", "explosion", "melee")),
          effect=dict(vent_ticks=40, jet_speed=0.9, damage=45, dtype="blast", radius=5.5, falloff=0.5,
                      knockback=3.0, fire_radius=3.5, fire_ticks=80, sets_burn=3),
          gore=dict(head=("crushed", 0.7), arm=("cut_upper", 0.8), leg=("cut_upper", 0.8), torso=("halved", 0.5)),
          rearm=None, recipe=None,
          sfx=dict(vent="nr.trap.hiss", trigger="nr.trap.explode_big"),
          fx=dict(vent="nr:gas_jet", trigger="nr:explosion"),
          desc_ja="撃つと穴から火を噴いて暴れ回り、数秒後に大爆発する。",
          desc_en="Shoot it and it rockets around spitting flame, then blows up big."),
    _trap("gas_pipe", "ガス管", "Gas Pipe", "block",
          trigger=dict(type="hit", by=("melee", "projectile", "bullet", "explosion")),
          effect=dict(jet_length=6, jet_ticks=100, dps=6, dtype="fire", sets_burn=3, ignite=True),
          gore=dict(),
          rearm=dict(mode="interact", ticks=200, refill=[("nr:duct_tape", 1)]),
          recipe=None,
          sfx=dict(trigger="nr.trap.gas_burst", idle="nr.trap.hiss"), fx=dict(trigger="nr:flame_jet"),
          desc_ja="壁のガス管とバルブ。叩くと裂けて 5 秒間、前へ火を噴く。テープで塞げばまた使える。",
          desc_en="A wall gas pipe and valve. Hit it and it bursts, jetting flame for 5 s. Tape it to reuse.",
          model=[P("pipe_v", (3, 16, 3), (0, 8, 6), "steel_painted", "壁沿いの黄色い縦管"),
                 P("pipe_h", (3, 3, 10), (0, 8, 1), "steel_painted", "手前へ曲がる横管"),
                 P("elbow", (4, 4, 4), (0, 8, 6), "iron_cast", "継ぎ手"),
                 P("valve", (4, 4, 4), (0, 8, -4), "brass", "バルブ本体"),
                 P("wheel", (6, 0.8, 6), (0, 11, -4), "plastic_red", "赤いハンドル（十字のスポーク）"),
                 P("label", (3.1, 3, 3.1), (0, 4, 6), "plastic_yellow", "「ガス」の黄色い札"),
                 P("crack", (3.2, 1.2, 3.2), (0, 8, -1), "steel_dark", "裂け目（壊れた状態で表示）")]),
    _trap("car_alarm", "車のアラーム", "Car Alarm", "prop_interaction",
          props=("sedan_wreck", "taxi_wreck", "police_car", "pickup_truck", "ambulance"),
          trigger=dict(type="hit", by=("melee", "projectile", "bullet", "explosion", "player_land"),
                       chance=0.35),
          effect=dict(lure_radius=40, lure_ticks=300, lights_blink=True, spawn_viral=(2, 4)),
          gore=dict(), rearm=None, recipe=None,
          sfx=dict(trigger="nr.trap.car_alarm"), fx=dict(trigger="nr:alarm_flash"),
          desc_ja="車を叩く・撃つ・飛び乗ると 35% で鳴り出し、15 秒間 40 ブロック内の感染者を呼ぶ。走る感染者も来る。",
          desc_en="Hitting, shooting or landing on a car may set it off: draws infected within 40 blocks for 15 s."),
    _trap("tripwire_mine", "ワイヤー地雷", "Tripwire Mine", "block",
          trigger=dict(type="proximity", radius=1.2, who="zombie", arm_ticks=40),
          effect=dict(damage=35, dtype="blast", radius=4.5, falloff=0.55, knockback=2.2),
          gore=dict(leg=("cut_upper", 0.8), arm=("cut_upper", 0.4), torso=("halved", 0.25)),
          rearm=None,
          recipe=shaped(["T", "G", "S"], {"T": "minecraft:tripwire_hook", "G": "nr:gunpowder_pouch",
                                          "S": "nr:scrap"}),
          sfx=dict(arm="nr.trap.click", trigger="nr.trap.explode"), fx=dict(trigger="nr:explosion"),
          desc_ja="釘を詰めた缶と張った針金。脚の高さで炸裂し、脚を吹き飛ばす。置いて 2 秒で作動。",
          desc_en="A nail-packed can and a tight wire. Bursts at leg height and blows legs off. Arms 2 s after placing.",
          model=[P("can", (5, 6, 5), (0, 3, 0), "steel_worn", "ラベルの剥げた缶、テープで巻く"),
                 P("nails", (5.4, 2, 5.4), (0, 4, 0), "steel_rusty", "缶に巻いた釘の層"),
                 P("post", (1, 6, 1), (-7, 3, 0), "wood_raw", "針金を張る杭", rep=[(7, 3, 0)]),
                 P("wire", (14, 0.2, 0.2), (0, 4, 0), "steel_clean", "脚の高さに張った細い針金"),
                 P("led", (0.8, 0.8, 0.8), (0, 6.4, 0), "emissive_red", "点滅する赤い LED（発光）")]),
    _trap("oil_puddle", "油だまり", "Oil Slick", "block",
          trigger=dict(type="fire", by=("fire", "molotov", "spark", "explosion", "shock")),
          effect=dict(burn_ticks=160, dps=3, dtype="fire", radius=1.5, spread=True, slow=0.5, sets_burn=2,
                      slip=True),
          gore=dict(), rearm=None,
          recipe=shapeless([("nr:alcohol", 2), ("nr:chemicals", 1)], count=3),
          sfx=dict(trigger="nr.trap.ignite", idle="nr.trap.fire_loop"), fx=dict(trigger="nr:flame"),
          desc_ja="床に撒いた油。滑って転ばせ、火が付くと 8 秒燃え広がる。",
          desc_en="Oil spilled on the floor. Trips walkers; ignites into an 8-second spreading blaze.",
          model=[P("puddle", (16, 0.4, 16), (0, 0.2, 0), "fuel", "虹色の油膜（縁は不規則、アルファで抜く）"),
                 P("puddle_ext", (6, 0.4, 6), (8, 0.2, 5), "fuel", "隣のマスへはみ出す流れ"),
                 P("can", (3, 2, 5), (-4, 1, -4), "steel_rusty", "倒れた油缶", rot=(0, 30, 90))]),
    _trap("uv_trap", "UV トラップ", "UV Trap", "block",
          trigger=dict(type="proximity", radius=5.0, who="night", night_only=False),
          effect=dict(uv_ticks=100, uv_dps=4, dtype="uv", stun_ticks=60, light_level=15, radius=6.0),
          gore=dict(), rearm=dict(mode="recharge", ticks=400, refill=[("nr:battery", 1)]),
          recipe=shaped(["UGU", "SBS", "S S"], {"U": "nr:uv_shroom", "G": "minecraft:glass_pane",
                                                 "B": "nr:battery", "S": "nr:scrap"}),
          light_emission=4, sfx=dict(trigger="nr.trap.uv_burst"), fx=dict(trigger="nr:uv_glow"),
          desc_ja="人感センサー付きの UV 投光器。夜の捕食者が近づくと 5 秒間焼き、怯ませる。",
          desc_en="A motion-sensing UV floodlight. Burns and stuns night predators for 5 s.",
          model=[P("leg", (1, 14, 1), (-5, 7, -5), "aluminium", "三脚の脚（外へ開く）", rot=(-12, 0, 12),
                   rep=[(5, 7, -5), (0, 7, 6)]),
                 P("head", (10, 7, 4), (0, 17, 0), "plastic_black", "投光器の箱、放熱フィン"),
                 P("lens", (9, 6, 0.4), (0, 17, -2.2), "emissive_uv", "紫の LED パネル（6×9 の粒）"),
                 P("sensor", (2, 2, 2), (0, 21.5, -1), "plastic_white", "人感センサーのドーム"),
                 P("battery", (5, 4, 3), (0, 2, 0), "plastic_yellow", "足元の電池箱、電線が三脚を登る")]),
    _trap("spike_log", "揺れる杭丸太", "Swinging Spike Log", "prop", prop="spike_log",
          trigger=dict(type="cut", by=("melee", "projectile"), target="rope"),
          effect=dict(damage=22, dtype="pierce", knockback=2.6, swing_ticks=30, arc_deg=150, width=3),
          gore=dict(torso=("slashed", 0.7), head=("crushed", 0.5), arm=("broken", 0.5)),
          rearm=dict(mode="interact", ticks=60, refill=[("nr:rags", 3)]),
          recipe=None, sfx=dict(trigger="nr.trap.rope_snap", hit="nr.gore.smash"),
          fx=dict(trigger="nr:dust_burst"),
          desc_ja="鎖で吊った杭だらけの丸太。縄を切ると振り子で通りをなぎ払う。",
          desc_en="A spiked log hung on chains. Cut the rope and it sweeps the street like a pendulum."),
    _trap("barbed_wire", "有刺鉄線", "Barbed Wire", "block",
          trigger=dict(type="step", who="any_mob", players=True),
          effect=dict(damage=1, dtype="slash", slow=0.7, bleed_dps=1.0, bleed_ticks=60, player_damage=1),
          gore=dict(arm=("wounded", 0.4), leg=("wounded", 0.6)),
          rearm=dict(mode="durable", uses=60, repair=[("nr:scrap", 1)]),
          recipe=shaped(["SBS", "BSB", "SBS"], {"S": "nr:scrap", "B": "nr:blades"}, count=4),
          sfx=dict(trigger="nr.trap.wire"), fx=dict(trigger="nr:bleed_drip"),
          desc_ja="巻いた有刺鉄線。通る者を鈍らせ、肉を裂いて出血させる。",
          desc_en="Coiled barbed wire. Slows anything passing through and tears flesh.",
          model=[P("coil", (16, 10, 3), (0, 5, -3), "steel_worn", "螺旋に巻いた鉄線（輪を 5 つ、透過テクスチャ）"),
                 P("coil_2", (16, 9, 3), (0, 4.5, 3), "steel_rusty", "後ろの段の輪"),
                 P("barb", (16, 0.6, 0.6), (0, 8, 0), "steel_clean", "棘の列"),
                 P("post", (1.2, 12, 1.2), (-7.4, 6, 0), "wood_old", "支柱", rep=[(7.4, 6, 0)]),
                 P("rag", (2, 3, 0.2), (3, 6, -3.2), "cloth_rag", "引っかかった布切れと血")]),
]


# ===========================================================================
#  カスタムブロック（ID nr:<key>）— ブロック空間（px、原点は底面中央）
#  collision: False（通り抜け）/ dict(origin=[x,y,z], size=[w,h,d])。origin+size は [-8,0,-8]〜[8,16,8]
#  sound: RP blocks.json の音のキー（バニラにあるもの）
#  render: opaque / alpha_test（金網・ガラスの穴）/ blend（血だまり・油）
#  parkour: climb（壁登りできる）/ vault（乗り越え）/ landing（落下ダメージ無効）/ zipline / updraft（滑空の上昇気流）
# ===========================================================================
BLOCK_SOUNDS = ("stone", "wood", "metal", "cloth", "gravel", "sand", "glass", "chain", "lantern", "iron",
                "anvil", "scaffolding", "ladder", "slime", "bone_block", "bamboo_wood", "copper", "netherite",
                "honey_block", "mud")


def _box(x0, y0, z0, w, h, d):
    return dict(origin=[x0, y0, z0], size=[w, h, d])


def _block(key, ja, en, category, *, model, collision, sound, map_color, light_emission=0, selection=None,
           loot=None, recipe=None, destroy_time=1.5, blast_resistance=3.0, flammable=False, rotatable=True,
           states=None, interact=None, parkour=(), multiblock=None, variants=1, render="opaque",
           hp=None, desc_ja="", desc_en="", extra=None):
    d = dict(key=key, id=nid(key), ja=ja, en=en, category=category, model=list(model), collision=collision,
             selection=selection if selection is not None else (collision or _box(-8, 0, -8, 16, 16, 16)),
             sound=sound, map_color=map_color, light_emission=light_emission, loot=loot, recipe=recipe,
             destroy_time=destroy_time, blast_resistance=blast_resistance, flammable=flammable,
             rotatable=rotatable, states=dict(states or {}), interact=interact, parkour=list(parkour),
             multiblock=multiblock, variants=variants, render=render, hp=hp, desc_ja=desc_ja, desc_en=desc_en,
             geometry="geometry.nr.b." + key, texture="textures/nr/blocks/" + key)
    if extra:
        d.update(extra)
    return d


BLOCKS = [
    # --- バリケード ---------------------------------------------------------------------
    _block("barricade", "板のバリケード", "Plank Barricade", "barricade",
           collision=_box(-8, 0, -2, 16, 16, 4), sound="wood", map_color="#7c5e40", destroy_time=2.0,
           flammable=True, hp=40, parkour=("climb",),
           recipe=shaped(["PSP", "PPP", "PSP"], {"P": _PLANK, "S": "nr:scrap"}, count=2),
           desc_ja="戸口や窓を塞ぐ板。感染者は叩いて壊す（体力 40）。",
           desc_en="Planks nailed over doors and windows. Infected batter it down (40 HP).",
           model=[P("plank_top", (18, 4, 1.4), (0, 13, -0.6), "wood_old", "横板。端が割れて隣へはみ出す", rot=(0, 0, 4)),
                  P("plank_mid", (17, 3.6, 1.4), (0.5, 8, 0.6), "plywood", "斜めに打った板", rot=(0, 0, -9)),
                  P("plank_low", (18, 4, 1.4), (0, 3, -0.6), "wood_old", "下の横板", rot=(0, 0, -3)),
                  P("brace", (3, 16, 1.2), (-6, 8, 1.6), "wood_dark", "裏の縦の添え木", rep=[(6, 8, 1.6)]),
                  P("nail", (0.8, 0.8, 0.6), (-6, 13, -1.4), "steel_rusty", "釘の頭",
                    rep=[(6, 13, -1.4), (-6, 3, -1.4), (6, 3, -1.4), (0, 8, -0.2)]),
                  P("handprint", (5, 6, 0.2), (3, 7, -1.4), "blood_dry", "引っかいた血の手形 3 本の筋"),
                  P("spray", (12, 4, 0.2), (0, 10.5, -1.4), "paint_red", "赤スプレーの殴り書き「入るな」（テクスチャ）")]),
    _block("metal_barricade", "鉄板のバリケード", "Metal Barricade", "barricade",
           collision=_box(-8, 0, -2, 16, 16, 4), sound="metal", map_color="#6e7072", destroy_time=4.0,
           blast_resistance=8.0, hp=120, parkour=("climb",),
           recipe=shaped(["SIS", "SIS", "SIS"], {"S": "nr:scrap", "I": _IRON}, count=2),
           desc_ja="波板と山形鋼の壁。感染者でも壊すのに時間がかかる（体力 120）。",
           desc_en="Corrugated sheet on angle iron. Takes infected a long time to break (120 HP).",
           model=[P("sheet", (16, 16, 1.0), (0, 8, 0), "steel_rusty", "縦の波板（明暗の縞 8 本）、錆の流れ"),
                  P("frame_h", (17, 1.6, 1.6), (0, 2, -1.2), "steel_dark", "山形鋼の横材", rep=[(0, 14, -1.2)]),
                  P("frame_v", (1.6, 16, 1.6), (-7.2, 8, -1.2), "steel_dark", "縦材", rep=[(7.2, 8, -1.2)]),
                  P("bolt", (1, 1, 0.6), (-7.2, 2, -2.2), "steel_worn", "ボルト",
                    rep=[(7.2, 2, -2.2), (-7.2, 14, -2.2), (7.2, 14, -2.2)]),
                  P("uv_mark", (6, 6, 0.2), (3, 9, -0.7), "fungus_uv", "生存者の UV 塗料の印（矢印と円）"),
                  P("dent", (4, 4, 0.4), (-3, 6, -0.6), "steel_dark", "内側から叩かれた凹み")]),
    _block("sandbags", "土嚢", "Sandbags", "barricade",
           collision=_box(-8, 0, -5, 16, 12, 10), sound="sand", map_color="#a8946c", destroy_time=2.5,
           blast_resistance=10.0, parkour=("vault",),
           recipe=shaped(["RRR", "DDD"], {"R": "nr:rags", "D": "minecraft:sand"}, count=2),
           desc_ja="積んだ土嚢。腰の高さで乗り越えられ、爆発にも強い。",
           desc_en="Stacked sandbags. Waist-high for vaulting; stands up to blasts.",
           model=[P("bag_row1", (8.4, 4, 9), (-4, 2, 0), "burlap", "下段の袋（膨らみ・縫い目・結び口）", rep=[(4, 2, 0)]),
                  P("bag_row2", (8.4, 4, 8.5), (0, 6, 0.2), "burlap", "中段（半分ずらす）", rep=[(-8.2, 6, 0.2), (8.2, 6, 0.2)]),
                  P("bag_row3", (8.4, 4, 8), (-4, 10, 0), "burlap", "上段", rep=[(4, 10, 0)]),
                  P("leak", (3, 1, 3), (5, 0.5, -5), "concrete", "破れて漏れた砂"),
                  P("stencil", (5, 2, 0.2), (-4, 2, -4.6), "paint_white", "白いステンシル番号")]),
    # --- 通り ---------------------------------------------------------------------------
    _block("traffic_cone", "カラーコーン", "Traffic Cone", "street",
           collision=_box(-4, 0, -4, 8, 11, 8), sound="bamboo_wood", map_color="#e07020", destroy_time=0.5,
           rotatable=False,
           desc_ja="道路工事の橙のコーン。蹴ると転がる（叩くと倒れた形に変わる）。",
           desc_en="An orange road cone. Knock it and it tips over.",
           states={"nr:fallen": [0, 1]},
           model=[P("base", (11, 1.2, 11), (0, 0.6, 0), "rubber_black", "黒い四角い台、角が欠ける"),
                  P("cone_1", (7, 3, 7), (0, 2.7, 0), "plastic_orange", "下段"),
                  P("band_1", (6, 2, 6), (0, 5.2, 0), "paint_white", "白い反射帯"),
                  P("cone_2", (5, 3, 5), (0, 7.6, 0), "plastic_orange", "中段"),
                  P("band_2", (4, 1.5, 4), (0, 9.8, 0), "paint_white", "反射帯"),
                  P("tip", (3, 1.8, 3), (0, 11.4, 0), "plastic_orange", "先端、泥と擦り傷")]),
    _block("road_barrier", "コンクリート防護柵", "Concrete Road Barrier", "street",
           collision=_box(-8, 0, -5, 16, 12, 10), sound="stone", map_color="#9a9a92", destroy_time=6.0,
           blast_resistance=20.0, parkour=("vault",),
           recipe=shaped(["CCC", "CCC"], {"C": "minecraft:smooth_stone"}, count=2),
           desc_ja="台形断面のコンクリ柵（ジャージー型）。並べて道を塞ぐ。乗り越えられる。",
           desc_en="A Jersey-style concrete barrier. Blocks roads; can be vaulted.",
           model=[P("base", (16, 4, 10), (0, 2, 0), "concrete", "下の幅広部、泥はね"),
                  P("mid", (16, 4, 7), (0, 6, 0), "concrete", "中、斜面"),
                  P("top", (16, 4, 4.4), (0, 10, 0), "concrete", "上の細い部分、欠け"),
                  P("stripe", (16.2, 3, 0.2), (0, 7, -3.6), "decal_stripe", "赤白の斜め縞の反射材"),
                  P("lift_hole", (3, 2, 10.2), (-4, 1, 0), "concrete_dark", "フォーク用の穴（黒）", rep=[(4, 1, 0)]),
                  P("graffiti", (8, 4, 0.2), (2, 9, 2.3), "paint_blue", "裏の落書き")]),
    _block("street_lamp_base", "街灯の土台", "Street Lamp Base", "light",
           collision=_box(-3, 0, -3, 6, 16, 6), sound="metal", map_color="#3a3c40", destroy_time=5.0,
           multiblock=("street_lamp", 0), parkour=("climb",),
           desc_ja="鋳物の街灯の台座。上に柱 3 本と灯具を積む。",
           desc_en="Cast-iron lamp base. Stack three poles and a lamp head on it.",
           model=[P("plinth", (10, 3, 10), (0, 1.5, 0), "iron_cast", "八角の台座、ボルト 4 本"),
                  P("flare", (7, 5, 7), (0, 5.5, 0), "iron_cast", "裾広がりの胴"),
                  P("shaft", (4.5, 8, 4.5), (0, 12, 0), "iron_cast", "柱の根元"),
                  P("panel", (2.6, 3.4, 0.4), (0, 6, -3.6), "steel_dark", "点検口の蓋（外れかけ）"),
                  P("poster", (4, 5, 0.2), (0, 12, -2.4), "paper", "破れた尋ね人のビラ"),
                  P("bolt", (1, 1, 1), (-4, 3.2, -4), "steel_rusty", "台座のボルト",
                    rep=[(4, 3.2, -4), (-4, 3.2, 4), (4, 3.2, 4)])]),
    _block("street_lamp_pole", "街灯の柱", "Street Lamp Pole", "light",
           collision=_box(-2, 0, -2, 4, 16, 4), sound="metal", map_color="#3a3c40", destroy_time=4.0,
           multiblock=("street_lamp", 1), parkour=("climb",), variants=2,
           desc_ja="街灯の柱。よじ登れる。",
           desc_en="A lamp pole. Climbable.",
           model=[P("pole", (3.4, 16, 3.4), (0, 8, 0), "steel_painted", "暗緑の塗装、縦の錆の筋"),
                  P("collar", (4, 1, 4), (0, 15.5, 0), "iron_cast", "継ぎ目の輪"),
                  P("sticker", (3.5, 4, 3.5), (0, 6, 0), "paper", "貼り紙の重なり（variant 1 のみ）")]),
    _block("street_lamp_head", "街灯の灯具", "Street Lamp Head", "light",
           collision=_box(-2, 0, -2, 4, 16, 4), sound="lantern", map_color="#3a3c40", light_emission=14,
           destroy_time=4.0, multiblock=("street_lamp", 2), states={"nr:lit": [0, 1]},
           desc_ja="柱の上の腕と灯具。夜は点き、たまに瞬く（nr:lit）。",
           desc_en="Arm and lamp atop the pole. Lit at night and flickers (nr:lit).",
           model=[P("pole_top", (3.4, 10, 3.4), (0, 5, 0), "steel_painted", "柱の続き"),
                  P("arm", (2, 2, 18), (0, 11, -8), "steel_painted", "道路側（-Z）へ伸びる腕、少し上がる", rot=(-6, 0, 0)),
                  P("arm_brace", (1, 1, 8), (0, 8, -3), "steel_painted", "腕の斜めの支え", rot=(-40, 0, 0)),
                  P("housing", (6, 2.5, 9), (0, 12.5, -18), "steel_painted", "コブラ型の灯具の笠"),
                  P("lens", (5, 0.5, 7), (0, 11.0, -18), "emissive_white", "下向きの光るレンズ（nr:lit=0 で暗く）"),
                  P("bird_nest", (3, 1.5, 3), (0, 14.2, -16), "rope", "笠の上の鳥の巣の枝")]),
    _block("uv_lamp", "UV ライト", "UV Lamp", "light",
           collision=_box(-3, 0, -3, 6, 16, 6), sound="lantern", map_color="#8040e0", light_emission=12,
           destroy_time=3.0, states={"nr:powered": [0, 1]}, interact="toggle_power",
           recipe=shaped(["GUG", "UBU", " S "], {"G": "minecraft:glass_pane", "U": "nr:uv_shroom",
                                                  "B": "nr:battery", "S": "nr:scrap"}),
           extra=dict(safe_radius=10, immunity_regen_per_s=10, repel_night=True),
           desc_ja="紫外線の灯り。半径 10 ブロックは夜の安全地帯（夜の捕食者が入れず、免疫が戻る）。",
           desc_en="A UV light. Within 10 blocks is a night safe zone: night predators stay out, immunity recovers.",
           model=[P("base", (8, 2, 8), (0, 1, 0), "plastic_black", "重りの台"),
                  P("battery", (5, 4, 4), (0, 4, 0), "plastic_yellow", "電池箱、配線"),
                  P("post", (2, 8, 2), (0, 10, 0), "aluminium", "支柱"),
                  P("tube", (2.4, 10, 2.4), (0, 19, 0), "emissive_uv", "縦の UV 蛍光管（強い紫）"),
                  P("cage", (4, 11, 4), (0, 19, 0), "chainlink", "管を囲う金網の籠（透過）"),
                  P("cap", (4.4, 1.2, 4.4), (0, 25, 0), "plastic_black", "上の蓋")]),
    # --- 瓦礫・ゴミ ----------------------------------------------------------------------
    _block("rubble_pile", "瓦礫の山", "Rubble Pile", "debris",
           collision=_box(-8, 0, -8, 16, 8, 16), sound="gravel", map_color="#8a8880", destroy_time=2.0,
           loot="rubble", parkour=("vault",), variants=3, rotatable=True,
           desc_ja="崩れた壁のコンクリ片とレンガと鉄筋。崩すと金属くずが出ることがある。",
           desc_en="Chunks of concrete, brick and rebar from a fallen wall. May give scrap when cleared.",
           model=[P("slab_a", (12, 4, 9), (-2, 2, -2), "concrete", "割れた床スラブ、斜め", rot=(0, 15, 8)),
                  P("slab_b", (9, 3, 8), (3, 5.5, 3), "concrete_dark", "上に乗った塊", rot=(10, -20, -6)),
                  P("brick", (4, 2, 2), (-5, 1, 5), "brick_red", "レンガ（3 個、モルタル付き）",
                    rep=[(5, 1, -6), (-1, 8, 1)]),
                  P("rebar", (0.8, 0.8, 12), (1, 7, -1), "rebar", "突き出た曲がった鉄筋", rot=(-30, 40, 0)),
                  P("dust", (16, 0.4, 16), (0, 0.2, 0), "concrete", "粉塵の広がり")]),
    _block("debris_scatter", "散らばった瓦礫", "Scattered Debris", "debris",
           collision=False, selection=_box(-8, 0, -8, 16, 2, 16), sound="gravel", map_color="#7a7870",
           destroy_time=0.3, variants=4, render="alpha_test",
           desc_ja="床に散ったガラス片・紙・小石。歩くとじゃりっと鳴る。",
           desc_en="Glass shards, paper and grit on the floor. Crunches underfoot.",
           model=[P("grit", (16, 0.2, 16), (0, 0.1, 0), "concrete", "小石と粉（アルファで抜く）"),
                  P("glass", (3, 0.2, 2), (-4, 0.3, 3), "glass_broken", "ガラス片", rep=[(5, 0.3, -2), (1, 0.3, 6)]),
                  P("paper", (4, 0.2, 5), (3, 0.3, 4), "paper", "新聞紙", rot=(0, 25, 0)),
                  P("can", (1.6, 2.4, 1.6), (-6, 1.2, -5), "aluminium", "潰れた空き缶", rot=(0, 0, 90))]),
    _block("trash_bags", "ゴミ袋の山", "Trash Bag Pile", "debris",
           collision=_box(-8, 0, -8, 16, 10, 16), sound="cloth", map_color="#26262c", destroy_time=0.8,
           loot="trash", parkour=("landing", "vault"),
           desc_ja="積まれたゴミ袋。飛び降りても落下ダメージを受けない（着地点）。",
           desc_en="Piled trash bags. Land on them from any height without fall damage.",
           extra=dict(negate_fall=True),
           model=[P("bag_a", (9, 7, 9), (-3, 3.5, -3), "trash_bag", "膨らんだ黒い袋、結び口が上", rot=(0, 20, 6)),
                  P("bag_b", (8, 6, 8), (4, 3, 2), "trash_bag", "破れて中身が出る袋", rot=(0, -15, -8)),
                  P("bag_c", (8, 6, 7), (-1, 8, 1), "trash_bag", "上に載った袋"),
                  P("bag_blue", (6, 5, 6), (-4, 2.5, 5), "plastic_blue", "青い袋"),
                  P("box", (6, 4, 5), (5, 2, -5), "cardboard", "潰れた段ボール"),
                  P("spill", (5, 0.4, 4), (5, 0.2, 6), "cloth_rag", "こぼれた生ゴミと布")]),
    _block("tire_stack", "タイヤの山", "Tire Stack", "debris",
           collision=_box(-7, 0, -7, 14, 12, 14), sound="cloth", map_color="#2a2a2e", destroy_time=1.5,
           parkour=("vault",), flammable=True,
           desc_ja="積み上げた古タイヤ。燃えると黒煙を上げて長く燃える。",
           desc_en="Stacked old tires. Burns long with thick black smoke.",
           model=[P("tire_1", (14, 4, 14), (0, 2, 0), "rubber_black", "下のタイヤ、溝のすり減り、穴（内側は黒）"),
                  P("tire_2", (13, 4, 13), (0.6, 6, -0.4), "rubber_black", "ずれて載る", rot=(0, 12, 0)),
                  P("tire_3", (14, 4, 14), (-0.8, 10, 0.5), "rubber_black", "少し傾く", rot=(4, -8, 2)),
                  P("hole", (7, 12.2, 7), (0, 6, 0), "asphalt", "中心の穴（暗い）"),
                  P("water", (6, 0.2, 6), (0, 11.9, 0), "fuel", "溜まった雨水の油膜")]),
    # --- 箱・ルート ---------------------------------------------------------------------
    _block("wooden_crate", "木箱", "Wooden Crate", "container",
           collision=_box(-7, 0, -7, 14, 14, 14), sound="wood", map_color="#9a7448", destroy_time=1.0,
           loot="crate_wood", flammable=True, parkour=("vault",),
           desc_ja="壊すと中身が出る木箱。",
           desc_en="A wooden crate. Break it to get what's inside.",
           model=[P("box", (14, 14, 14), (0, 7, 0), "wood_raw", "板の継ぎ目、焼き印「FRAGILE」"),
                  P("frame_edge", (15, 1.6, 1.6), (0, 0.8, -6.6), "wood_dark", "外枠の角材（12 本の辺）",
                    rep=[(0, 13.2, -6.6), (0, 0.8, 6.6), (0, 13.2, 6.6)]),
                  P("frame_v", (1.6, 14, 1.6), (-6.6, 7, -6.6), "wood_dark", "縦の角材",
                    rep=[(6.6, 7, -6.6), (-6.6, 7, 6.6), (6.6, 7, 6.6)]),
                  P("diag", (1.4, 1.4, 18), (0, 7, -7.2), "wood_dark", "前面の斜めの補強", rot=(45, 90, 0)),
                  P("stencil", (8, 3, 0.2), (0, 10, -7.1), "paint_black", "黒いステンシル")]),
    _block("survivor_stash", "生存者の隠し箱", "Survivor Stash", "container",
           collision=_box(-7, 0, -5, 14, 9, 10), sound="metal", map_color="#4a5a3a", destroy_time=-1,
           loot="stash_common", interact="open_stash", states={"nr:locked": [0, 1], "nr:open": [0, 1]},
           extra=dict(loot_locked="stash_locked", refill_days=3),
           desc_ja="生存者の金属の箱。使うと中身が手に入る（3 日で補充）。鍵付きはロックピックかバールで。",
           desc_en="A survivor's footlocker. Use to loot (refills every 3 days). Locked ones need a lockpick or crowbar.",
           model=[P("box", (14, 7, 10), (0, 3.5, 0), "paint_olive", "オリーブの軍用トランク、角の金具"),
                  P("lid", (14.4, 2, 10.4), (0, 8, 0), "paint_olive", "蓋（nr:open=1 で後ろへ開く）"),
                  P("corner", (1.6, 1.6, 1.6), (-6.6, 0.8, -4.6), "steel_worn", "角の金具",
                    rep=[(6.6, 0.8, -4.6), (-6.6, 8.2, -4.6), (6.6, 8.2, -4.6)]),
                  P("handle", (4, 1, 1), (-7.6, 5, 0), "steel_dark", "左右の取っ手", rot=(0, 90, 0), rep=[(7.6, 5, 0)]),
                  P("padlock", (2, 2.4, 1), (0, 5.5, -5.6), "brass", "南京錠（nr:locked=1 のみ）"),
                  P("uv_mark", (5, 4, 0.2), (3.5, 4, -5.2), "fungus_uv", "UV 塗料の生存者の印（発光気味）")]),
    _block("med_cabinet", "壁の救急箱", "Wall Medicine Cabinet", "container",
           collision=_box(-5, 2, 4, 10, 12, 4), sound="metal", map_color="#d8d8d0", destroy_time=1.0,
           loot="med_cabinet", interact="open_stash", states={"nr:open": [0, 1]},
           extra=dict(refill_days=2, wall_mounted=True),
           desc_ja="壁掛けの白い救急箱。包帯や薬が残っていることがある。",
           desc_en="A white wall-mounted first aid cabinet. Might still hold bandages and meds.",
           model=[P("box", (10, 12, 4), (0, 8, 6), "plastic_white", "壁に付く白い箱、黄ばみ"),
                  P("door", (10.4, 12.4, 0.6), (0, 8, 3.8), "plastic_white", "扉（nr:open=1 で開く）"),
                  P("cross", (4, 4, 0.2), (0, 9, 3.4), "plastic_red", "赤十字"),
                  P("blood", (3, 5, 0.2), (3, 6, 3.4), "blood_dry", "血の手形"),
                  P("hinge", (0.6, 2, 0.6), (-5.2, 4, 3.8), "steel_worn", "蝶番", rep=[(-5.2, 12, 3.8)])]),
    _block("crafting_bench", "生存者の作業台", "Survivor Workbench", "station",
           collision=_box(-8, 0, -6, 16, 14, 12), sound="wood", map_color="#8a6a44", light_emission=6,
           destroy_time=2.5, interact="open_bench",
           recipe=shaped(["SIS", "PPP", "P P"], {"S": "nr:scrap", "I": _IRON, "P": _PLANK}),
           desc_ja="万力と工具の並ぶ作業台。近く（4 ブロック）で端末の「作業台」レシピ（武器・銃・罠）が作れる。",
           desc_en="A workbench with a vise and tools. Within 4 blocks the terminal's bench recipes unlock.",
           model=[P("top", (16, 2, 12), (0, 13, 0), "wood_old", "傷と焦げ跡と油染みの天板"),
                  P("leg", (2, 12, 2), (-7, 6, -5), "wood_dark", "脚", rep=[(7, 6, -5), (-7, 6, 5), (7, 6, 5)]),
                  P("shelf", (14, 1, 10), (0, 3, 0), "plywood", "下の棚、工具箱と缶"),
                  P("vise", (4, 3, 3), (-5, 15.5, -5), "steel_painted", "青い万力、ハンドル"),
                  P("pegboard", (16, 10, 1), (0, 19, 6), "plywood", "奥の有孔ボード（穴の点）、吊った工具の影"),
                  P("hammer", (1, 5, 1), (-3, 19, 5.2), "wood_old", "掛けた金槌"),
                  P("lamp", (3, 2, 3), (5, 23, 4), "emissive_amber", "クランプ式の作業灯（発光）"),
                  P("toolbox", (6, 3, 4), (4, 1.5, 1), "plastic_red", "下の赤い工具箱")]),
    # --- ゴアの飾り ---------------------------------------------------------------------
    _block("blood_pool", "血だまり", "Blood Pool", "gore",
           collision=False, selection=_box(-8, 0, -8, 16, 1, 16), sound="slime", map_color="#5a0a0a",
           destroy_time=0.2, variants=4, render="blend",
           desc_ja="床に広がった血。縁は黒く乾き、中は艶がある（4 つの形）。",
           desc_en="Blood spread on the floor. Dark dried rim, glossy middle (4 shapes).",
           model=[P("pool", (16, 0.15, 16), (0, 0.08, 0), "blood_wet", "不規則な形（アルファ）、中央に艶"),
                  P("rim", (18, 0.1, 14), (1, 0.05, -1), "blood_dry", "乾いた縁（隣へ少しはみ出す）"),
                  P("splat", (4, 0.12, 4), (9, 0.06, 7), "blood_dry", "飛び散った点")]),
    _block("gore_remains", "遺骸の山", "Gore Remains", "gore",
           collision=_box(-6, 0, -6, 12, 4, 12), sound="bone_block", map_color="#6a2a20", destroy_time=0.6,
           loot="gore_remains", variants=3,
           desc_ja="食い荒らされた遺骸。肋骨・破れた服・散らばった骨。蝿が飛ぶ。",
           desc_en="Picked-over remains: ribs, torn clothes, scattered bones. Flies buzz.",
           extra=dict(ambient_particle="nr:flies"),
           model=[P("ribcage", (6, 4, 7), (0, 2, 0), "bone", "肋骨（曲がった細い骨を 5 本並べる）、肉の残り"),
                  P("spine", (1.4, 1.4, 8), (0, 1, 4), "bone", "背骨の節"),
                  P("skull", (3.4, 3.4, 4), (-5, 1.7, -4), "bone", "頭蓋骨（顎なし）、眼窩の影", rot=(0, 30, 20)),
                  P("femur", (1.2, 1.2, 7), (5, 0.6, -3), "bone", "大腿骨", rot=(0, -40, 0)),
                  P("cloth", (10, 0.6, 8), (1, 0.3, 1), "cloth_rag", "破れたシャツとズボン"),
                  P("meat", (4, 1.4, 3), (-2, 0.7, 4), "gore_meat", "肉片"),
                  P("blood", (16, 0.1, 16), (0, 0.05, 0), "blood_dry", "下の血の染み")]),
    # --- 足場・パルクール ---------------------------------------------------------------
    _block("chainlink_fence", "金網フェンス", "Chain-Link Fence", "parkour",
           collision=_box(-8, 0, -1, 16, 16, 2), sound="chain", map_color="#9a9e9e", destroy_time=3.0,
           parkour=("climb",), render="alpha_test",
           recipe=shaped(["III", "I I"], {"I": "minecraft:iron_bars"}, count=3),
           desc_ja="金網のフェンス。よじ登って越えられる。",
           desc_en="A chain-link fence. Climb it to get over.",
           model=[P("mesh", (16, 15, 0.2), (0, 8, 0), "chainlink", "菱形の網（透過）、所々破れて外側へめくれる"),
                  P("post", (1.4, 16, 1.4), (-7.3, 8, 0), "aluminium", "支柱（隣とつながる）"),
                  P("rail", (16, 1, 1), (0, 15.5, 0), "aluminium", "上の横パイプ"),
                  P("barbs", (16, 1.2, 1.2), (0, 16.8, 0), "steel_rusty", "上に張った有刺鉄線の 1 本"),
                  P("rag", (2, 3, 0.3), (4, 10, -0.4), "cloth_rag", "引っかかった布切れ")]),
    _block("broken_window", "割れた窓枠", "Broken Window Frame", "parkour",
           collision=False, selection=_box(-8, 0, -1, 16, 16, 2), sound="glass", map_color="#8aa0a8",
           destroy_time=0.6, render="alpha_test", parkour=("vault",),
           desc_ja="ガラスの割れた窓枠。中を抜けられる（縁のガラス片に注意）。",
           desc_en="A shattered window frame. You can dive through it.",
           model=[P("frame_top", (16, 2, 2), (0, 15, 0), "wood_painted", "白いペンキの剥げた上枠", rep=[(0, 1, 0)]),
                  P("frame_side", (2, 14, 2), (-7, 8, 0), "wood_painted", "左右の枠", rep=[(7, 8, 0)]),
                  P("mullion", (1, 12, 1), (0, 8, 0), "wood_painted", "中の桟（折れてぶら下がる）", rot=(0, 0, 12)),
                  P("shard", (5, 4, 0.2), (-4, 12, 0), "glass_broken", "上隅に残るガラス片（尖った形）",
                    rep=[(4.5, 3.5, 0), (5, 12.5, 0)]),
                  P("curtain", (5, 10, 0.3), (5, 9, 1.4), "cloth_red", "内側に垂れたちぎれたカーテン")]),
    _block("graffiti_panel", "落書きの壁板", "Graffiti Panel", "decor",
           collision=_box(-8, 0, 6, 16, 16, 2), sound="wood", map_color="#6a5a8a", destroy_time=1.5,
           variants=4, states={"nr:variant": [0, 1, 2, 3]}, flammable=True,
           desc_ja="生存者のスプレー落書きの板（矢印「安全→」、数を数えた線、髑髏の警告、UV の印）。",
           desc_en="Survivor spray-paint boards: 'SAFE →' arrows, tally marks, skull warnings, UV signs.",
           model=[P("board", (16, 16, 1.2), (0, 8, 7.2), "plywood", "合板（variant ごとにテクスチャの落書き）"),
                  P("drip", (14, 10, 0.2), (0, 9, 6.5), "paint_red", "垂れたスプレー（variant 0: 赤い矢印）"),
                  P("nail", (0.8, 0.8, 0.6), (-7, 15, 6.4), "steel_rusty", "留め釘", rep=[(7, 15, 6.4), (-7, 1, 6.4), (7, 1, 6.4)])]),
    _block("scaffold_platform", "工事用足場", "Scaffold Platform", "parkour",
           collision=_box(-8, 13, -8, 16, 3, 16), sound="scaffolding", map_color="#c8a040", destroy_time=1.0,
           parkour=("climb",),
           recipe=shaped(["PPP", "I I", "I I"], {"P": _PLANK, "I": _IRON}, count=2),
           desc_ja="鉄パイプの枠と足場板。上を歩け、枠をよじ登れる。積み重ねて塔にする。",
           desc_en="Steel pipe frame with planks on top. Walk on it, climb the frame, stack it into towers.",
           model=[P("deck", (16, 2, 16), (0, 14.5, 0), "plywood", "上の足場板（板の継ぎ目 4 本、泥の足跡）"),
                  P("pipe_v", (1.4, 16, 1.4), (-7.3, 8, -7.3), "steel_worn", "4 隅の縦パイプ",
                    rep=[(7.3, 8, -7.3), (-7.3, 8, 7.3), (7.3, 8, 7.3)]),
                  P("pipe_x", (1.2, 1.2, 21), (-7.3, 7, 0), "steel_worn", "側面の斜めの筋交い", rot=(43, 0, 0),
                    rep=[(7.3, 7, 0)]),
                  P("clamp", (2, 2, 2), (-7.3, 13, -7.3), "steel_dark", "クランプ",
                    rep=[(7.3, 13, -7.3), (-7.3, 13, 7.3), (7.3, 13, 7.3)]),
                  P("toe_board", (16, 2, 0.6), (0, 16.6, -7.6), "plastic_yellow", "黄色い幅木")]),
    _block("zipline_anchor", "ジップライン・アンカー", "Zipline Anchor", "parkour",
           collision=_box(-3, 0, -3, 6, 16, 6), sound="metal", map_color="#6a6c70", destroy_time=4.0,
           parkour=("zipline",), interact="zipline",
           recipe=shaped(["ISI", " I ", "SIS"], {"I": _IRON, "S": "nr:scrap"}),
           extra=dict(link_range=48, ride_speed=0.75, min_drop=0.0),
           desc_ja="ワイヤーを張る支柱。視線の先 48 ブロック内の別のアンカーへ、使うと滑車で滑る。",
           desc_en="A cable post. Use it to ride a pulley to another anchor within 48 blocks in view.",
           model=[P("post", (3, 14, 3), (0, 7, 0), "steel_painted", "黄色い支柱、錆"),
                  P("base", (8, 1.5, 8), (0, 0.75, 0), "steel_dark", "ボルト留めの台板"),
                  P("head", (5, 3, 5), (0, 15, 0), "steel_dark", "ワイヤーの留め具"),
                  P("pulley", (1.4, 3.6, 3.6), (2.8, 15, 0), "aluminium", "滑車（溝の円）"),
                  P("cable", (0.4, 0.4, 14), (0, 16.4, -7), "steel_clean", "張ったワイヤーの始まり（-Z へ）")]),
    # --- 屋上 ---------------------------------------------------------------------------
    _block("ac_unit", "屋上の室外機", "Rooftop AC Unit", "rooftop",
           collision=_box(-8, 0, -5, 16, 12, 10), sound="metal", map_color="#b0b0a8", destroy_time=3.0,
           loot="ac_unit", parkour=("vault",),
           desc_ja="屋上の室外機。乗り越えられる。壊すと金属くずと電池。",
           desc_en="A rooftop AC unit. Vaultable. Break it for scrap and batteries.",
           model=[P("case", (16, 11, 10), (0, 5.5, 0), "plastic_white", "黄ばんだ白い筐体、側面にスリット"),
                  P("grille", (9, 9, 0.4), (-2.5, 6, -5.2), "steel_dark", "ファンの丸い格子（同心円）"),
                  P("fan", (7, 7, 0.4), (-2.5, 6, -4.8), "plastic_black", "中の羽根 3 枚"),
                  P("pipe", (1, 1, 6), (6, 3, 6), "copper_wire", "銅の冷媒管 2 本（壁へ）", rep=[(6, 5, 6)]),
                  P("feet", (16, 1, 2), (0, 0.5, -3.5), "steel_rusty", "置き台の脚", rep=[(0, 0.5, 3.5)]),
                  P("rust", (5, 3, 0.2), (5, 2, -5.1), "steel_rusty", "錆の流れ")]),
    _block("roof_vent", "屋上の換気フード", "Roof Vent", "rooftop",
           collision=_box(-4, 0, -4, 8, 14, 8), sound="metal", map_color="#9a9c9e", destroy_time=2.0,
           parkour=("updraft",), extra=dict(updraft_height=8, updraft_strength=0.25),
           desc_ja="回るタービンの換気口。上の空気が昇り、パラグライダーで上がれる。",
           desc_en="A spinning turbine vent. Warm air rises — catch it with the paraglider.",
           model=[P("duct", (6, 6, 6), (0, 3, 0), "aluminium", "四角いダクト、リベットの列"),
                  P("neck", (5, 3, 5), (0, 7.5, 0), "aluminium", "首"),
                  P("turbine", (9, 5, 9), (0, 11, 0), "aluminium", "球形のタービン（斜めの羽根の縞、回すなら bone で）"),
                  P("cap", (4, 1, 4), (0, 14, 0), "steel_worn", "上の軸受け")]),
    _block("water_tower_leg", "給水塔の脚", "Water Tower Leg", "rooftop",
           collision=_box(-2, 0, -2, 4, 16, 4), sound="metal", map_color="#6a5a4a", destroy_time=4.0,
           parkour=("climb",), multiblock=("water_tower", 0),
           desc_ja="屋上の給水塔を支える鉄骨の脚。よじ登れる。",
           desc_en="A steel leg holding up a rooftop water tower. Climbable.",
           model=[P("leg", (3, 16, 3), (0, 8, 0), "steel_rusty", "H 形鋼、錆の筋"),
                  P("brace", (1, 1, 22), (0, 8, 3), "steel_rusty", "隣の脚への斜めの筋交い", rot=(45, 0, 0)),
                  P("rung", (6, 0.8, 0.8), (0, 4, -2), "steel_worn", "梯子の横桟", rep=[(0, 8, -2), (0, 12, -2)]),
                  P("plate", (5, 1, 5), (0, 15.5, 0), "steel_dark", "上の継ぎ板")]),
    _block("fire_barrel", "焚き火のドラム缶", "Burning Barrel", "light",
           collision=_box(-6, 0, -6, 12, 14, 12), sound="metal", map_color="#5a3a2a", light_emission=13,
           destroy_time=3.0, parkour=("updraft",), states={"nr:lit": [0, 1]},
           extra=dict(updraft_height=6, updraft_strength=0.2, burn_on_touch=1, ambient_particle="nr:flame"),
           desc_ja="生存者が火を焚くドラム缶。触れると燃える。上は上昇気流。",
           desc_en="A survivor's burn barrel. Touching it burns; warm air rises above.",
           model=[P("drum", (11, 14, 11), (0, 7, 0), "steel_rusty", "黒く焼けたドラム缶、輪の凸 2 本、下に穴"),
                  P("ring", (11.6, 1, 11.6), (0, 4.5, 0), "steel_dark", "補強の輪", rep=[(0, 9.5, 0)]),
                  P("hole", (2, 2, 0.4), (-2, 2, -5.6), "emissive_amber", "下の空気穴から見える火", rep=[(2, 2, -5.6)]),
                  P("fire", (8, 4, 8), (0, 15, 0), "emissive_amber", "上の炎（パーティクルと重ねる）"),
                  P("wood", (2, 2, 10), (0, 13, 0), "wood_dark", "突き出た薪", rot=(20, 40, 0))]),
    _block("road_sign", "道路標識", "Road Sign", "street",
           collision=_box(-1, 0, -1, 2, 16, 2), sound="metal", map_color="#c8c8c0", destroy_time=2.0,
           variants=4, states={"nr:variant": [0, 1, 2, 3]},
           desc_ja="傾いた道路標識（止まれ・一方通行・避難経路・速度制限）。",
           desc_en="A leaning road sign (stop, one-way, evacuation route, speed limit).",
           model=[P("post", (1.4, 20, 1.4), (0, 10, 0), "steel_painted", "角柱の標識柱（穴の列）、少し傾く", rot=(0, 0, 3)),
                  P("plate", (10, 10, 0.4), (0.5, 22, -1), "steel_painted", "標識板（variant でテクスチャ）"),
                  P("bracket", (2, 1, 1.2), (0.4, 19, -0.4), "steel_worn", "留め金", rep=[(0.4, 25, -0.4)]),
                  P("sticker", (3, 2, 0.2), (2, 20, -1.3), "paper", "貼られたステッカー"),
                  P("dent", (3, 3, 0.2), (-1.5, 24, -1.3), "steel_dark", "弾痕の凹み 3 つ")]),
]

# 罠のうちブロックのものの「ブロックとしての性質」（gen_nr_blocks が TRAPS と合わせて使う）
TRAP_BLOCKS = {
    "electric_trap": dict(collision=_box(-8, 0, -8, 16, 2, 16), sound="metal", map_color="#4a6a8a",
                          destroy_time=2.0, render="opaque"),
    "spike_trap":    dict(collision=_box(-8, 0, -8, 16, 2, 16), sound="wood", map_color="#6a5a4a",
                          destroy_time=2.0, render="opaque"),
    "bear_trap":     dict(collision=False, selection=_box(-7, 0, -6, 14, 3, 12), sound="metal",
                          map_color="#5a5a5c", destroy_time=1.5, render="opaque"),
    "fuel_canister": dict(collision=_box(-3, 0, -5, 6, 14, 10), sound="metal", map_color="#b02020",
                          destroy_time=1.0, render="opaque"),
    "gas_pipe":      dict(collision=_box(-2, 0, -6, 4, 16, 14), sound="metal", map_color="#c8a020",
                          destroy_time=4.0, render="opaque"),
    "tripwire_mine": dict(collision=False, selection=_box(-8, 0, -3, 16, 7, 6), sound="metal",
                          map_color="#7a7c7e", destroy_time=0.5, render="alpha_test"),
    "oil_puddle":    dict(collision=False, selection=_box(-8, 0, -8, 16, 1, 16), sound="slime",
                          map_color="#2a241c", destroy_time=0.2, render="blend"),
    "uv_trap":       dict(collision=_box(-5, 0, -5, 10, 16, 10), sound="lantern", map_color="#8040e0",
                          destroy_time=2.0, render="opaque"),
    "barbed_wire":   dict(collision=False, selection=_box(-8, 0, -5, 16, 11, 10), sound="chain",
                          map_color="#8a8c8e", destroy_time=1.5, render="alpha_test"),
}

# いくつかのブロックで組む物（建物・街の生成が積む順。offset はブロック）
MULTIBLOCKS = {
    "street_lamp": [("street_lamp_base", (0, 0, 0)), ("street_lamp_pole", (0, 1, 0)),
                    ("street_lamp_pole", (0, 2, 0)), ("street_lamp_pole", (0, 3, 0)),
                    ("street_lamp_head", (0, 4, 0))],
    "water_tower": [("water_tower_leg", (dx, dy, dz)) for dx in (0, 3) for dz in (0, 3) for dy in range(5)],
}


# ===========================================================================
#  小道具エンティティ（ID nr:prop_<key>）— 小道具空間（単位、原点は地面の中央、-Z が前）
#  size_blocks = (幅 x, 高さ y, 長さ z)。barrier はバリアブロックの矩形 [x0, z0, x1, z1, 高さ]
#  （原点のあるマスを (0,0) とするマス座標、両端を含む）。anchor = 原点をマスのどこに置くか
#  （0 = 整数座標＝マスの角、0.5 = マスの中央）。幅 2 の車は x を角に置くので x0=-1, x1=0
# ===========================================================================
PROP_INTERACTIONS = {
    "car_alarm":     "叩く・撃つ・飛び乗ると鳴る（TRAPS の car_alarm）",
    "loot_trunk":    "後ろで使うとトランクが開き、ルート表 loot から出る（1 回、3 日で補充）",
    "loot_glovebox": "運転席側で使うとグローブボックスから glovebox のルート",
    "loot_cargo":    "荷台・扉を使うと loot から出る",
    "lightbar":      "回転灯が光る（赤青の点滅、夜は周りを照らす）",
    "climb_roof":    "屋根に登れる（パルクールの足場。バリアの高さが屋根の高さ）",
    "fuel_leak":     "漏れた燃料に火が付くと燃え、さらに撃つと爆発（燃料缶と同じ数値）",
    "smoke":         "くすぶる煙を出し続ける",
    "open_doors":    "扉が開閉する（nr:variant で開いた見た目）",
    "breakable_glass": "窓を叩くと割れる音とガラスの粒",
    "vent_jet":      "撃たれると穴から火を噴いて暴れる（TRAPS の propane_tank）",
    "swing":         "縄を切ると振り子で振れる（TRAPS の spike_log）",
}


def _prop(key, ja, en, *, size_blocks, model, barrier, anchor=(0.0, 0.5), interactions=(), loot=None,
          variants=1, cube_budget=500, texture_size=(512, 512), spawn_weight=0, hp=None, trap=None,
          desc_ja="", desc_en="", extra=None):
    d = dict(key=key, id="nr:prop_" + key, ja=ja, en=en, size_blocks=tuple(size_blocks), model=list(model),
             barrier=[list(b) for b in barrier], anchor=tuple(anchor), interactions=list(interactions),
             loot=loot, variants=variants, cube_budget=cube_budget, texture_size=tuple(texture_size),
             spawn_weight=spawn_weight, hp=hp, trap=trap, desc_ja=desc_ja, desc_en=desc_en,
             geometry="geometry.nr.prop." + key, texture="textures/nr/props/" + key)
    if extra:
        d.update(extra)
    return d


def _sedan_parts(paint, glass_front="glass_broken", tires="rubber_black", wear="steel_rusty"):
    """セダン型の車体（セダン・タクシー・パトカーの共通。幅 32・高さ 26・長さ 82 単位）。"""
    return [
        P("body_lower", (32, 9, 80), (0, 8.5, 0), paint, "車体の下半分。4 枚のドアの継ぎ目と凹んだノブ、敷居の錆、泥はね"),
        P("beltline", (31, 3, 44), (0, 14.5, 1), paint, "窓の下の帯、擦り傷の線"),
        P("hood", (30, 2.5, 22), (0, 14.0, -28), paint, "ボンネット。中央の膨らみ、凹み、熱で剥げた塗装", rot=(5, 0, 0)),
        P("front_bumper", (33, 4.5, 3), (0, 6.5, -40.5), "plastic_black", "前のバンパー、片側が外れて垂れる", rot=(0, 0, 4)),
        P("grille", (18, 4, 0.6), (0, 10.5, -40.2), "plastic_black", "横桟のグリル、虫と血の跡"),
        P("headlight", (6, 3, 1), (-11, 11, -40.0), "emissive_white", "左のヘッドライト（点く。nr:variant で消灯）"),
        P("headlight_broken", (6, 3, 1.1), (11, 11, -40.0), glass_front, "右は割れて中が暗い"),
        P("indicator", (3, 1.4, 1), (-14, 9, -40.0), "emissive_amber", "ウインカー", rep=[(14, 9, -40.0)]),
        P("plate_front", (8, 2.6, 0.4), (0, 7, -42.2), "paint_white", "前のナンバー（架空の番号）"),
        P("roof", (27, 1.6, 26), (0, 25.2, 2), paint, "屋根。飛び降りた足の凹み、血の手形"),
        P("a_pillar", (1.6, 10, 1.6), (-13.5, 20.5, -15.5), paint, "前の柱", rot=(-35, 0, 0), rep=[(13.5, 20.5, -15.5)]),
        P("b_pillar", (1.6, 9.4, 2.0), (-13.8, 20.5, 2), paint, "中の柱", rep=[(13.8, 20.5, 2)]),
        P("c_pillar", (1.6, 10, 4.0), (-13.5, 20.5, 17), paint, "後ろの柱", rot=(30, 0, 0), rep=[(13.5, 20.5, 17)]),
        P("windshield", (25, 0.4, 13), (0, 20.4, -15.6), glass_front, "前の窓、蜘蛛の巣のひび、内側に血の飛沫",
          rot=(-55, 0, 0)),
        P("rear_window", (25, 0.4, 11), (0, 20.4, 18), "glass_tinted", "後ろの窓、埃に指で書いた文字", rot=(50, 0, 0)),
        P("side_window_f", (0.4, 7.5, 15), (-13.6, 20, -7), "glass_broken", "前席の窓、割れて縁だけ",
          rep=[(13.6, 20, -7)]),
        P("side_window_r", (0.4, 7.5, 13), (-13.6, 20, 10), "glass_clear", "後席の窓、汚れ", rep=[(13.6, 20, 10)]),
        P("trunk", (30, 2.5, 13), (0, 14, 33.5), paint, "トランクの蓋（loot_trunk で開く）"),
        P("rear_bumper", (33, 4.5, 3), (0, 6.5, 40.5), "plastic_black", "後ろのバンパー、擦れ"),
        P("taillight", (7, 3, 1), (-11.5, 12, 40.2), "emissive_red", "テールランプ（片方ひび）", rep=[(11.5, 12, 40.2)]),
        P("plate_rear", (8, 2.6, 0.4), (0, 9, 41.2), "paint_white", "後ろのナンバー"),
        P("wheel", (4, 12, 12), (-14.5, 6, -25), tires, "タイヤ（溝・側面の文字）。左後ろはパンクで潰れる",
          rep=[(14.5, 6, -25), (-14.5, 5, 25), (14.5, 6, 25)]),
        P("hubcap", (4.4, 7, 7), (-14.7, 6, -25), "chrome", "ホイールキャップ（1 つ欠ける）",
          rep=[(14.7, 6, -25), (14.7, 6, 25)]),
        P("mirror", (1.6, 2.4, 3), (-17, 17, -13), paint, "左のドアミラー"),
        P("mirror_hanging", (1.6, 2.4, 3), (17, 14, -13), paint, "右のミラーは折れて配線で垂れる", rot=(0, 0, -60)),
        P("door_handle", (0.6, 0.8, 2.4), (-16.1, 13.5, -4), "chrome", "ドアノブ",
          rep=[(16.1, 13.5, -4), (-16.1, 13.5, 12), (16.1, 13.5, 12)]),
        P("dashboard", (28, 4, 6), (0, 16, -13), "plastic_black", "ダッシュボード、割れたメーター、垂れた配線"),
        P("steering", (6, 6, 1), (-7, 18, -9), "rubber_black", "ハンドル", rot=(-60, 0, 0)),
        P("seat_front", (11, 9, 8), (-7, 13, -3), "leather_brown", "前席、破れて中綿", rep=[(7, 13, -3)]),
        P("seat_rear", (26, 8, 8), (0, 13, 12), "leather_brown", "後席、置き去りの鞄"),
        P("blood_door", (0.3, 7, 12), (-16.2, 12, -4), "blood_dry", "運転席ドアを引きずった血の手形"),
        P("blood_seat", (10, 0.3, 7), (-7, 17.7, -3), "blood_wet", "前席の血だまり"),
        P("rust_fender", (0.3, 4, 10), (-16.2, 9, -30), wear, "フェンダーの錆", rep=[(16.2, 9, 30)]),
        P("exhaust", (2, 2, 5), (10, 3, 41), "steel_rusty", "マフラー"),
        P("antenna", (0.3, 9, 0.3), (12, 30, 24), "steel_dark", "曲がったアンテナ", rot=(-20, 0, 0)),
        P("leak", (12, 0.2, 10), (4, 0.1, -30), "fuel", "エンジンの下のオイル漏れ（地面の虹色）"),
    ]


def _flip(parts, height):
    """車体を上下逆さに（z 軸まわり 180 度）。ひっくり返った車用。"""
    out = []
    for p in parts:
        q = dict(p)
        x, y, z = p["at"]
        q["at"] = (-x, height - y, z)
        if "rot" in p:
            rx, ry, rz = p["rot"]
            q["rot"] = (-rx, -ry, rz)
        if "rep" in p:
            q["rep"] = [(-a, height - b, c) for a, b, c in p["rep"]]
        out.append(q)
    return out


_SEDAN_BARRIER = [[-1, -2, 0, 2, 1], [-1, -1, 0, 1, 2]]

PROPS = [
    _prop("sedan_wreck", "放置されたセダン", "Abandoned Sedan", size_blocks=(2.0, 1.6, 5.1),
          model=_sedan_parts("paint_red"), barrier=_SEDAN_BARRIER,
          interactions=("car_alarm", "loot_trunk", "loot_glovebox", "climb_roof", "breakable_glass"),
          loot="car_trunk", variants=4, cube_budget=320, texture_size=(512, 512), spawn_weight=30,
          extra=dict(variant_paints=("paint_red", "paint_blue", "paint_white", "steel_painted")),
          desc_ja="乗り捨てられたセダン。トランクとグローブボックスに物資。叩くとアラームが鳴ることがある。",
          desc_en="An abandoned sedan. Supplies in the trunk and glovebox. Hitting it may trip the alarm."),
    _prop("taxi_wreck", "放置されたタクシー", "Abandoned Taxi", size_blocks=(2.0, 1.75, 5.1),
          model=_sedan_parts("paint_yellow") + [
              P("roof_sign", (9, 3, 4), (0, 27.5, 4), "plastic_white", "屋根の行灯「TAXI」（消えている、ひび）"),
              P("checker", (0.4, 2, 70), (-16.2, 12, 0), "decal_stripe", "側面の市松の帯", rep=[(16.2, 12, 0)]),
              P("meter", (4, 2, 3), (4, 17.5, -11), "emissive_red", "料金メーターの赤い数字（発光）"),
              P("partition", (26, 7, 0.4), (0, 19, 4), "glass_clear", "前後席の仕切り板、ひび")],
          barrier=_SEDAN_BARRIER, interactions=("car_alarm", "loot_trunk", "loot_glovebox", "climb_roof"),
          loot="car_trunk", cube_budget=340, spawn_weight=12,
          desc_ja="黄色いタクシー。客を乗せたまま止まったらしい。",
          desc_en="A yellow taxi. It seems to have stopped with a fare still inside."),
    _prop("police_car", "パトカー", "Police Cruiser", size_blocks=(2.1, 1.8, 5.3),
          model=_sedan_parts("paint_black", wear="steel_dark") + [
              P("door_white", (0.4, 9, 30), (-16.3, 10, 3), "paint_white", "前後のドアは白、金色の星の紋章と「POLICE」",
                rep=[(16.3, 10, 3)]),
              P("lightbar", (22, 2.5, 4), (0, 27.2, 0), "plastic_black", "屋根の回転灯の台"),
              P("light_red", (8, 2, 3.6), (-6, 28.6, 0), "emissive_red", "赤のレンズ（点滅）"),
              P("light_blue", (8, 2, 3.6), (6, 28.6, 0), "emissive_blue", "青のレンズ（点滅）"),
              P("push_bar", (26, 8, 3), (0, 9, -43.5), "steel_dark", "前のプッシュバンパー（格子 3 本）"),
              P("spotlight", (1.6, 1.6, 3), (-14.5, 22, -12), "chrome", "A ピラーのスポットライト"),
              P("cage", (26, 7, 0.4), (0, 19, 4), "chainlink", "後席の金網の仕切り"),
              P("shotgun_rack", (1, 1, 10), (0, 18, -5), "steel_dark", "前席間の銃架（空）")],
          barrier=_SEDAN_BARRIER,
          interactions=("car_alarm", "loot_trunk", "loot_glovebox", "lightbar", "climb_roof"),
          loot="police_trunk", cube_budget=380, spawn_weight=8,
          desc_ja="警察車両。トランクに弾薬や警棒が残る。回転灯がまだ点滅している。",
          desc_en="A police cruiser. Ammo and batons may remain in the trunk. The lightbar still flashes."),
    _prop("ambulance", "救急車", "Ambulance", size_blocks=(2.4, 3.0, 6.4),
          model=[
              P("cab", (36, 18, 26), (0, 14, -38), "paint_white", "運転室の下半分、赤い帯"),
              P("cab_hood", (34, 4, 12), (0, 16, -47), "paint_white", "短いボンネット", rot=(8, 0, 0)),
              P("cab_upper", (34, 12, 18), (0, 29, -34), "paint_white", "運転室の上、屋根"),
              P("windshield", (32, 0.4, 13), (0, 28.5, -43.5), "glass_broken", "前の窓、割れ", rot=(-20, 0, 0)),
              P("box", (38, 38, 64), (0, 27, 14), "paint_white", "後ろの箱型の車体。赤とチェッカーの帯、青い生命の星の印"),
              P("stripe", (38.4, 4, 64), (0, 18, 14), "decal_stripe", "反射のチェッカー帯"),
              P("red_band", (38.4, 2.4, 90), (0, 23, 0), "plastic_red", "赤い帯"),
              P("lightbar", (30, 3, 5), (0, 36.5, -34), "plastic_black", "運転室の上の回転灯"),
              P("box_lights", (4, 3, 2), (-16, 44, -17.5), "emissive_red", "箱の前の四隅の赤灯",
                rep=[(16, 44, -17.5), (-16, 44, 45.5), (16, 44, 45.5)]),
              P("rear_doors", (17, 30, 1), (-9.5, 25, 46.6), "paint_white", "後ろの観音扉（左は開く）",
                rot=(0, 70, 0)),
              P("rear_door_r", (17, 30, 1), (8.5, 25, 46.5), "paint_white", "右の扉、窓に血"),
              P("stretcher", (8, 6, 26), (-4, 12, 40), "aluminium", "半分外へ出たストレッチャー、血染めのシーツ"),
              P("sheet", (8.4, 1, 20), (-4, 15.4, 40), "blood_wet", "シーツの血"),
              P("cabinet", (4, 20, 30), (16, 24, 18), "plastic_white", "中の医療棚（loot）"),
              P("wheel", (5, 14, 14), (-17, 7, -34), "rubber_black", "前輪", rep=[(17, 7, -34)]),
              P("wheel_rear", (8, 14, 14), (-16, 7, 28), "rubber_black", "後輪（ダブル）", rep=[(16, 7, 28)]),
              P("step", (30, 2, 4), (0, 6, 48), "steel_worn", "後ろのステップ"),
              P("headlight", (6, 4, 1), (-12, 15, -53.5), "emissive_white", "ヘッドライト", rep=[(12, 15, -53.5)]),
              P("grille", (20, 6, 0.6), (0, 14, -53.5), "plastic_black", "グリル"),
              P("bumper", (38, 5, 3), (0, 7, -54), "plastic_black", "バンパー"),
              P("blood_smear", (0.4, 14, 20), (-19.3, 22, 20), "blood_dry", "側面を引きずった血の帯"),
          ],
          barrier=[[-1, -1, 0, 3, 3], [-1, -3, 0, -2, 2]], anchor=(0.0, 0.5),
          interactions=("car_alarm", "loot_cargo", "lightbar", "climb_roof", "open_doors"),
          loot="ambulance", cube_budget=420, texture_size=(1024, 1024), spawn_weight=5,
          desc_ja="後ろの扉が開いた救急車。医療品が残っている。",
          desc_en="An ambulance with its back doors open. Medical supplies remain."),
    _prop("city_bus", "路線バス", "City Bus", size_blocks=(2.8, 3.6, 13.0),
          model=[
              P("body", (44, 36, 204), (0, 24, 0), "paint_blue", "車体の下半分と柱。下は青、帯は白、広告の板"),
              P("window_band", (44.4, 13, 176), (0, 36, 8), "glass_tinted", "側面の窓の帯（3 枚割れ、内側に手形と血）"),
              P("roof", (42, 3, 200), (0, 43.5, 0), "paint_white", "屋根、汚れの筋"),
              P("roof_ac", (30, 5, 36), (0, 47, 40), "plastic_white", "屋根のエアコン箱（乗れる）"),
              P("hatch", (10, 1, 10), (0, 45.5, -20), "steel_worn", "非常口のハッチ（開いている）"),
              P("windshield", (40, 22, 0.6), (0, 32, -102.2), "glass_broken", "大きな前面ガラス、割れ"),
              P("dest_sign", (30, 5, 1), (0, 41.5, -102.2), "emissive_amber", "行き先表示「回送」（点滅）"),
              P("front_mask", (44, 14, 3), (0, 12, -102), "paint_white", "前面の下、凹み"),
              P("headlight", (6, 3, 1), (-16, 10, -103.8), "emissive_white", "ヘッドライト", rep=[(16, 10, -103.8)]),
              P("door_front", (0.6, 30, 14), (22.4, 21, -88), "glass_clear", "前扉（折れ戸が開く）", rot=(0, 30, 0)),
              P("door_mid", (0.6, 30, 16), (22.4, 21, 10), "glass_clear", "中扉（開いたまま）", rot=(0, -30, 0)),
              P("ad_panel", (0.4, 10, 50), (-22.4, 22, 10), "paper", "側面の広告（色褪せた架空の飲料）"),
              P("wheel_front", (6, 16, 16), (-19, 8, -72), "rubber_black", "前輪", rep=[(19, 8, -72)]),
              P("wheel_rear", (10, 16, 16), (-17, 8, 56), "rubber_black", "後輪（ダブル）", rep=[(17, 8, 56)]),
              P("seats", (14, 8, 140), (-12, 16, 10), "plastic_blue", "中の座席の列（窓から見える）",
                rep=[(12, 16, 10)]),
              P("rail", (0.8, 0.8, 160), (0, 38, 10), "chrome", "吊り革の手すり"),
              P("bike_rack", (30, 8, 4), (0, 10, -106), "steel_dark", "前の自転車ラック（曲がる）"),
              P("blood_smear", (0.4, 10, 40), (22.4, 34, -40), "blood_dry", "窓を引きずった血"),
              P("rust", (0.4, 6, 30), (-22.4, 8, 60), "steel_rusty", "下回りの錆"),
          ],
          barrier=[[-1, -6, 1, 6, 3]], anchor=(0.5, 0.5),
          interactions=("loot_cargo", "climb_roof", "breakable_glass", "open_doors"),
          loot="bus_luggage", cube_budget=650, texture_size=(1024, 1024), spawn_weight=3,
          desc_ja="通りを塞ぐ路線バス。屋根は屋上へ渡る足場。中には荷物が残る。",
          desc_en="A city bus blocking the street. Its roof is a step to the rooftops; luggage remains inside."),
    _prop("box_truck", "箱型トラック", "Box Truck", size_blocks=(2.6, 3.6, 8.0),
          model=[
              P("cab", (38, 22, 30), (0, 17, -48), "paint_white", "運転室、ドアに架空の引越し屋のロゴ"),
              P("cab_roof", (36, 10, 22), (0, 33, -45), "paint_white", "運転室の上"),
              P("windshield", (34, 0.4, 12), (0, 32, -55.5), "glass_broken", "前の窓", rot=(-15, 0, 0)),
              P("hood", (34, 4, 10), (0, 26, -60), "paint_white", "短いボンネット", rot=(6, 0, 0)),
              P("box", (42, 44, 86), (0, 32, 12), "aluminium", "荷箱。縦の継ぎ目とリベット列、落書き"),
              P("rollup", (38, 20, 1), (0, 44, 55.5), "aluminium", "半分上がったシャッター（横の筋）"),
              P("cargo", (30, 16, 20), (0, 18, 40), "cardboard", "中に積まれた段ボール（loot）"),
              P("lift_gate", (38, 2, 12), (0, 6, 62), "steel_worn", "後ろのリフト（下りている）"),
              P("wheel", (6, 16, 16), (-18, 8, -48), "rubber_black", "前輪", rep=[(18, 8, -48)]),
              P("wheel_rear", (10, 16, 16), (-16, 8, 34), "rubber_black", "後輪（ダブル）", rep=[(16, 8, 34)]),
              P("fuel_tank", (6, 6, 16), (-19, 10, -20), "aluminium", "燃料タンク（撃つと漏れる）"),
              P("mirror", (2, 8, 3), (-21, 30, -56), "plastic_black", "大きなミラー", rep=[(21, 30, -56)]),
              P("headlight", (6, 4, 1), (-14, 18, -65.6), "emissive_white", "ヘッドライト", rep=[(14, 18, -65.6)]),
              P("bumper", (40, 5, 3), (0, 8, -66), "steel_dark", "バンパー"),
              P("graffiti", (0.4, 16, 40), (21.2, 34, 12), "paint_red", "側面の落書き「生存者は北へ」"),
          ],
          barrier=[[-1, -2, 1, 3, 3], [-1, -4, 1, -3, 2]], anchor=(0.5, 0.0),
          interactions=("car_alarm", "loot_cargo", "climb_roof", "fuel_leak"),
          loot="cargo", cube_budget=420, texture_size=(1024, 1024), spawn_weight=5,
          desc_ja="シャッターの半分開いた引越しトラック。荷物の中に物資。",
          desc_en="A moving truck with the shutter half up. Supplies among the boxes."),
    _prop("pickup_truck", "ピックアップトラック", "Pickup Truck", size_blocks=(2.2, 2.0, 5.8),
          model=[
              P("body", (34, 10, 92), (0, 11, 0), "paint_green", "車体の下、泥だらけ、錆の穴"),
              P("hood", (32, 4, 26), (0, 18, -32), "paint_green", "長いボンネット", rot=(3, 0, 0)),
              P("cab", (32, 14, 22), (0, 23, -6), "paint_green", "運転室"),
              P("windshield", (30, 0.4, 12), (0, 26, -19), "glass_broken", "前の窓", rot=(-40, 0, 0)),
              P("bed", (32, 8, 36), (0, 18, 26), "paint_green", "荷台の枠（中は空洞、波板の床）"),
              P("tailgate", (32, 8, 1.4), (0, 14, 45), "paint_green", "下りたテールゲート", rot=(80, 0, 0)),
              P("toolbox", (30, 5, 6), (0, 24.5, 11), "aluminium", "荷台の工具箱（縞鋼板）"),
              P("spare", (14, 4, 14), (4, 16, 30), "rubber_black", "荷台のスペアタイヤ"),
              P("rollbar", (30, 10, 2), (0, 32, 10), "steel_dark", "ロールバーと作業灯 2 つ"),
              P("rollbar_lamp", (4, 3, 2), (-8, 37, 10), "emissive_white", "作業灯", rep=[(8, 37, 10)]),
              P("bullbar", (30, 12, 3), (0, 12, -47), "steel_dark", "グリルガード（ブルバー）"),
              P("wheel", (6, 14, 14), (-16, 7, -28), "rubber_black", "大きなオフロードタイヤ",
                rep=[(16, 7, -28), (-16, 7, 28), (16, 7, 28)]),
              P("jerrycan", (5, 9, 8), (-10, 20, 38), "plastic_red", "荷台の携行缶"),
              P("blood", (0.4, 6, 14), (17.2, 16, -6), "blood_dry", "ドアの血"),
          ],
          barrier=[[-1, -3, 0, 2, 1], [-1, -2, 0, 0, 2]], anchor=(0.0, 0.0),
          interactions=("car_alarm", "loot_cargo", "loot_glovebox", "climb_roof"),
          loot="car_trunk", cube_budget=360, spawn_weight=10,
          desc_ja="荷台に工具箱を積んだピックアップ。",
          desc_en="A pickup with a toolbox in the bed."),
    _prop("burnt_car", "焼けた車", "Burnt-Out Car", size_blocks=(2.0, 1.4, 5.0),
          model=[
              P("body_lower", (32, 8, 80), (0, 6.5, 0), "paint_burnt", "焼けて炭化した車体、白い灰と虹色の焼け"),
              P("hood", (30, 2, 22), (0, 11.5, -28), "paint_burnt", "めくれたボンネット", rot=(14, 0, 0)),
              P("roof", (27, 1.4, 26), (0, 22.5, 2), "paint_burnt", "熱で沈んだ屋根"),
              P("pillars", (1.4, 9, 1.4), (-13.5, 17.5, -15), "paint_burnt", "柱",
                rep=[(13.5, 17.5, -15), (-13.5, 17.5, 2), (13.5, 17.5, 2), (-13.5, 17.5, 17), (13.5, 17.5, 17)]),
              P("rim", (3, 10, 10), (-14.5, 4, -25), "steel_dark", "タイヤが燃え落ちたホイール（地面に沈む）",
                rep=[(14.5, 4, -25), (-14.5, 4, 25), (14.5, 4, 25)]),
              P("seat_springs", (11, 6, 8), (-7, 11, -3), "steel_rusty", "焼け残った座席のバネの格子",
                rep=[(7, 11, -3), (0, 11, 12)]),
              P("steering", (6, 6, 1), (-7, 15, -9), "steel_dark", "芯だけのハンドル", rot=(-60, 0, 0)),
              P("ash", (36, 0.3, 86), (0, 0.15, 0), "concrete_dark", "周りの煤と灰"),
              P("skeleton", (8, 6, 10), (-7, 15, -3), "paint_burnt", "運転席の黒焦げの人影（骨格の形）"),
          ],
          barrier=[[-1, -2, 0, 2, 1]], interactions=("smoke", "climb_roof"),
          loot=None, cube_budget=260, spawn_weight=10,
          desc_ja="燃え尽きた車。まだ煙がくすぶる。",
          desc_en="A burnt-out car, still smoldering."),
    _prop("overturned_car", "横転した車", "Overturned Car", size_blocks=(2.0, 1.6, 5.1),
          model=_flip(_sedan_parts("paint_blue"), 26.0) + [
              P("crushed_roof", (27, 4, 26), (0, 2, 2), "paint_blue", "地面に潰れた屋根（窓の高さが半分）"),
              P("underside", (30, 1, 78), (0, 25.5, 0), "steel_rusty", "上を向いた車の底: 排気管・燃料タンク・サスペンション"),
              P("fuel_drip", (16, 0.2, 14), (6, 0.1, 20), "fuel", "漏れたガソリン（fuel_leak）")],
          barrier=[[-1, -2, 0, 2, 2]], interactions=("fuel_leak", "climb_roof", "car_alarm"),
          loot="car_trunk", cube_budget=360, spawn_weight=6,
          desc_ja="ひっくり返った車。漏れた燃料に火が付くと爆発する。",
          desc_en="A car on its roof. If the leaking fuel catches fire, it explodes."),
    _prop("garbage_truck", "ゴミ収集車", "Garbage Truck", size_blocks=(2.8, 3.8, 9.0),
          model=[
              P("cab", (40, 26, 26), (0, 19, -58), "paint_white", "前の運転室（低い乗降口）"),
              P("cab_windshield", (38, 14, 0.6), (0, 26, -71.2), "glass_broken", "大きな前面窓"),
              P("body", (44, 46, 82), (0, 33, 4), "paint_green", "収集箱、縦の補強リブ 6 本、汚れの垂れ"),
              P("rib", (45, 46, 2), (0, 33, -30), "paint_green", "補強のリブ",
                rep=[(0, 33, -16), (0, 33, -2), (0, 33, 12), (0, 33, 26), (0, 33, 40)]),
              P("hopper", (42, 30, 24), (0, 26, 56), "paint_green", "後ろのホッパー、開いた口から黒い汁"),
              P("blade", (36, 4, 18), (0, 40, 56), "steel_rusty", "圧縮の刃（ゴミと布が絡む）", rot=(30, 0, 0)),
              P("bin", (14, 18, 14), (-26, 16, 48), "plastic_blue", "横に吊られたゴミ箱（リフター）"),
              P("lightbar", (26, 3, 4), (0, 34, -58), "emissive_amber", "屋根の黄色い回転灯"),
              P("step", (34, 2, 6), (0, 8, 70), "steel_worn", "後ろの作業員用ステップと手すり"),
              P("wheel", (6, 18, 18), (-20, 9, -50), "rubber_black", "前輪", rep=[(20, 9, -50)]),
              P("wheel_rear", (10, 18, 18), (-18, 9, 20), "rubber_black", "後輪（ダブル 2 軸）",
                rep=[(18, 9, 20), (-18, 9, 38), (18, 9, 38)]),
              P("headlight", (6, 4, 1), (-14, 14, -71.6), "emissive_white", "ヘッドライト", rep=[(14, 14, -71.6)]),
              P("trash_spill", (40, 3, 30), (0, 1.5, 84), "trash_bag", "後ろにこぼれたゴミの山"),
          ],
          barrier=[[-1, -2, 1, 4, 3], [-1, -4, 1, -3, 2]], anchor=(0.5, 0.5),
          interactions=("loot_cargo", "climb_roof", "car_alarm"),
          loot="garbage", cube_budget=480, texture_size=(1024, 1024), spawn_weight=3,
          desc_ja="止まったゴミ収集車。ひどい臭いと、たまに良い物。",
          desc_en="A stalled garbage truck. Awful smell, occasionally good finds."),
    _prop("shipping_container", "輸送コンテナ", "Shipping Container", size_blocks=(2.7, 2.85, 6.7),
          model=[
              P("shell", (43, 45, 106), (0, 22.5, 0), "paint_orange", "波板の側面（縦の凹凸 24 本）、錆の流れ"),
              P("corner", (4, 4, 4), (-20, 2, -52), "steel_dark", "四隅の鋳物の金具（8 個）",
                rep=[(20, 2, -52), (-20, 2, 52), (20, 2, 52), (-20, 43, -52), (20, 43, -52), (-20, 43, 52),
                     (20, 43, 52)]),
              P("door", (20.5, 42, 1), (-10.5, 22.5, 53.4), "paint_orange", "後ろの扉（左）", rep=[(10.5, 22.5, 53.4)]),
              P("lock_rod", (1, 42, 1), (-15, 22.5, 54.2), "steel_worn", "扉の閂（4 本）と取っ手",
                rep=[(-6, 22.5, 54.2), (6, 22.5, 54.2), (15, 22.5, 54.2)]),
              P("logo", (0.4, 10, 50), (21.7, 30, 0), "paint_white", "架空の海運会社のロゴと番号"),
              P("roof_dent", (30, 1, 40), (0, 45.2, 10), "steel_rusty", "屋根の凹みと水たまりの跡"),
              P("vent", (4, 2, 1), (-17, 40, -53.4), "steel_dark", "通気口", rep=[(17, 40, -53.4)]),
          ],
          barrier=[[-1, -3, 1, 3, 3]], anchor=(0.5, 0.5),
          interactions=("open_doors", "loot_cargo", "climb_roof"), loot="cargo",
          cube_budget=200, texture_size=(1024, 1024), spawn_weight=4,
          desc_ja="港から流れてきたコンテナ。扉を開けると物資。屋根は足場。",
          desc_en="A container from the docks. Open the doors for supplies; the roof is a perch."),
    _prop("dumpster", "大型ゴミ箱", "Dumpster", size_blocks=(2.0, 1.4, 1.2),
          model=[
              P("bin", (30, 18, 18), (0, 11, 0), "paint_green", "前が斜めの緑の箱、凹み、落書き"),
              P("lid", (15, 1.4, 19), (-7.6, 20.7, 0), "plastic_black", "黒い蓋（左は閉じる）"),
              P("lid_open", (15, 19, 1.4), (7.6, 30, 9.6), "plastic_black", "右の蓋は開いて後ろへ倒れる"),
              P("rim", (31, 2, 19), (0, 19, 0), "paint_green", "上の縁"),
              P("pocket", (2, 3, 6), (-16, 14, 0), "steel_dark", "側面のフォークポケット", rep=[(16, 14, 0)]),
              P("wheel", (3, 3, 3), (-12, 1.5, -6), "rubber_black", "キャスター", rep=[(12, 1.5, -6), (-12, 1.5, 6), (12, 1.5, 6)]),
              P("trash", (26, 4, 14), (0, 20, 0), "trash_bag", "溢れたゴミ袋"),
              P("arm", (2, 2, 8), (6, 21, -4), "gore_meat", "蓋の隙間から垂れた腕"),
              P("graffiti", (20, 8, 0.4), (0, 11, -9.3), "paint_white", "白いスプレーのタグ"),
          ],
          barrier=[[-1, 0, 0, 0, 1]], anchor=(0.0, 0.5),
          interactions=("loot_cargo", "climb_roof"), loot="dumpster", cube_budget=120, spawn_weight=14,
          desc_ja="路地の大型ゴミ箱。乗って塀を越える台にもなる。",
          desc_en="An alley dumpster. Doubles as a step over walls."),
    _prop("helicopter_crash", "墜落したヘリコプター", "Crashed Helicopter", size_blocks=(3.2, 3.4, 13.0),
          model=[
              P("fuselage", (32, 30, 70), (0, 15, -20), "paint_white", "胴体（右へ 25 度傾き、腹が潰れる）。報道ヘリの青い帯",
                rot=(0, 0, 25)),
              P("cockpit_glass", (28, 20, 18), (-3, 18, -58), "glass_broken", "割れた操縦席の風防（大きな曲面を 3 枚で）",
                rot=(0, 0, 25)),
              P("tail_boom", (10, 10, 70), (4, 18, 46), "paint_white", "尾部、途中で折れて地面へ", rot=(-8, 0, 20)),
              P("tail_fin", (2, 16, 10), (6, 28, 78), "paint_white", "垂直尾翼"),
              P("tail_rotor", (1, 14, 2), (9, 28, 80), "steel_dark", "尾部のローター（曲がる）"),
              P("rotor_hub", (6, 6, 6), (6, 34, -16), "steel_dark", "メインローターの軸"),
              P("blade_1", (4, 1, 60), (10, 34, 12), "steel_dark", "折れたローター（地面に刺さる）", rot=(20, 10, 0)),
              P("blade_2", (4, 1, 50), (-20, 26, -30), "steel_dark", "反対側のローター（下へ折れる）", rot=(-10, 70, 30)),
              P("skid", (2, 2, 60), (-14, 1, -20), "aluminium", "左のスキッド（曲がる）", rep=[(14, 6, -20)]),
              P("door_open", (1, 18, 20), (-20, 14, -22), "paint_white", "外れかけた側扉"),
              P("crate", (10, 8, 10), (-28, 4, -8), "paint_olive", "投げ出された物資箱（loot）"),
              P("fire_glow", (10, 6, 10), (4, 22, -6), "emissive_amber", "エンジン部の残り火（煙のパーティクルと）"),
              P("blood", (14, 0.3, 10), (-6, 9, -54), "blood_dry", "操縦席の血"),
          ],
          barrier=[[-1, -4, 1, 1, 2], [0, 2, 0, 5, 1]], anchor=(0.5, 0.5),
          interactions=("smoke", "loot_cargo", "climb_roof"), loot="helicopter",
          cube_budget=480, texture_size=(1024, 1024), spawn_weight=1,
          desc_ja="墜ちた報道ヘリ。投げ出された箱に貴重な物資。煙で遠くからも見える。",
          desc_en="A crashed news helicopter. Rare supplies in the scattered crates; its smoke is visible from afar."),
    _prop("army_truck", "軍用トラック", "Army Truck", size_blocks=(2.6, 3.4, 8.0),
          model=[
              P("cab", (38, 20, 28), (0, 20, -46), "paint_olive", "角ばった運転室、白いステンシルの番号"),
              P("canvas_cab", (36, 8, 24), (0, 34, -46), "burlap", "運転室の幌屋根"),
              P("hood", (34, 10, 22), (0, 22, -68), "paint_olive", "長いボンネット、通気スリット"),
              P("grill_guard", (36, 14, 3), (0, 16, -80), "steel_dark", "格子のガード、牽引フック"),
              P("bed", (40, 8, 74), (0, 18, 18), "paint_olive", "荷台の枠、木の床"),
              P("canvas", (42, 26, 72), (0, 35, 18), "burlap", "弓形の骨に掛けた幌（骨の盛り上がり 5 本、破れ）"),
              P("canvas_hole", (14, 10, 0.4), (-8, 34, 54.2), "cloth_rag", "後ろの幌がめくれて中が見える"),
              P("crates", (30, 12, 30), (0, 28, 34), "paint_olive", "中の弾薬箱の山（loot）"),
              P("wheel", (8, 18, 18), (-18, 9, -50), "rubber_black", "前輪（太いオフロード）", rep=[(18, 9, -50)]),
              P("wheel_rear", (10, 18, 18), (-17, 9, 20), "rubber_black", "後輪（2 軸）",
                rep=[(17, 9, 20), (-17, 9, 40), (17, 9, 40)]),
              P("spare", (16, 16, 4), (0, 22, -30), "rubber_black", "運転室の後ろのスペアタイヤ"),
              P("jerrycans", (5, 10, 8), (-21, 20, 0), "paint_olive", "側面の燃料缶", rep=[(-21, 20, 10)]),
              P("headlight", (4, 4, 2), (-14, 22, -80), "emissive_white", "丸目のヘッドライト（籠付き）",
                rep=[(14, 22, -80)]),
              P("sandbags", (36, 6, 6), (0, 25, 56), "burlap", "荷台の後ろの土嚢"),
          ],
          barrier=[[-1, -2, 1, 3, 3], [-1, -5, 1, -3, 2]], anchor=(0.5, 0.0),
          interactions=("loot_cargo", "climb_roof"), loot="army_crate",
          cube_budget=460, texture_size=(1024, 1024), spawn_weight=2,
          desc_ja="検問の跡に残る軍のトラック。弾薬と武器が見つかる。",
          desc_en="A military truck left at a checkpoint. Ammo and weapons inside."),
    _prop("propane_tank", "プロパンボンベ", "Propane Tank", size_blocks=(0.8, 1.4, 0.8),
          model=[
              P("body", (12, 18, 12), (0, 11, 0), "plastic_white", "白い円筒（八角に見えるよう 45 度の箱を重ねる）、錆の斑"),
              P("body_45", (12, 18, 12), (0, 11, 0), "plastic_white", "45 度回した 2 枚目", rot=(0, 45, 0)),
              P("foot_ring", (11, 2, 11), (0, 1, 0), "steel_rusty", "下の足輪"),
              P("collar", (10, 5, 10), (0, 22, 0), "steel_painted", "上の保護リング（取っ手の穴 2 つ）"),
              P("valve", (3, 3, 3), (0, 21.5, 0), "brass", "真鍮のバルブ"),
              P("label", (12.2, 5, 4), (0, 12, -4), "plastic_red", "赤い「可燃性ガス」の札"),
          ],
          barrier=[], anchor=(0.5, 0.5), interactions=("vent_jet",), trap="propane_tank",
          cube_budget=40, texture_size=(128, 128), spawn_weight=6, hp=6,
          desc_ja="撃つと暴れて爆発するボンベ（TRAPS の propane_tank）。",
          desc_en="A tank that rockets and explodes when shot (TRAPS: propane_tank)."),
    _prop("spike_log", "揺れる杭丸太", "Swinging Spike Log", size_blocks=(3.0, 4.5, 1.0),
          model=[
              P("beam_anchor", (8, 2, 8), (0, -1, 0), "wood_dark", "原点 = 吊り点（梁の下面に打った板）"),
              P("chain", (1, 50, 1), (-16, -26, 0), "steel_worn", "2 本の鎖（輪の模様）", rep=[(16, -26, 0)]),
              P("rope", (1.4, 8, 1.4), (0, -6, 0), "rope", "止めの縄（切る所）"),
              P("log", (48, 12, 12), (0, -56, 0), "wood_old", "皮の残る丸太（八角に見せる）、両端の木口に年輪"),
              P("spike", (1.4, 1.4, 9), (-18, -56, -9), "rebar", "前へ突き出た鉄筋と尖った杭（12 本）",
                rep=[(-9, -52, -9), (0, -58, -9), (9, -54, -9), (18, -57, -9), (-13, -60, -9), (13, -51, -9),
                     (-4, -61, -9), (5, -49, -9), (-18, -50, -9), (18, -61, -9), (0, -53, -9)]),
              P("blood", (30, 8, 0.4), (0, -56, -6.2), "blood_dry", "前面の血と肉片"),
          ],
          barrier=[], anchor=(0.5, 0.5), interactions=("swing",), trap="spike_log",
          cube_budget=80, texture_size=(256, 256), spawn_weight=0,
          extra=dict(origin_note="原点は吊り点（梁の下面）。モデルは下（-Y）へ垂れる"),
          desc_ja="路地の上に吊られた杭丸太（TRAPS の spike_log）。",
          desc_en="A spiked log hung over an alley (TRAPS: spike_log)."),
]

# ===========================================================================
#  ルート表（(フル ID, 最小, 最大, 確率)。ゾンビの loot と同じ形）
# ===========================================================================
LOOT_TABLES = {
    "trash":        [("nr:rags", 0, 2, 0.6), ("nr:scrap", 0, 1, 0.4), ("nr:duct_tape", 0, 1, 0.12),
                     ("nr:money", 1, 4, 0.2), ("nr:canned_food", 1, 1, 0.1), ("nr:chemicals", 1, 1, 0.08)],
    "rubble":       [("nr:scrap", 0, 2, 0.5), ("minecraft:cobblestone", 1, 2, 0.4), ("minecraft:iron_nugget", 1, 3, 0.2)],
    "crate_wood":   [("nr:scrap", 1, 3, 0.7), ("nr:rags", 1, 2, 0.5), ("nr:alcohol", 1, 1, 0.25),
                     ("nr:duct_tape", 1, 1, 0.25), ("nr:gunpowder_pouch", 1, 1, 0.12), ("nr:canned_food", 1, 1, 0.2),
                     ("nr:w_machete", 1, 1, 0.03), ("nr:w_pipe_wrench", 1, 1, 0.04)],
    "stash_common": [("nr:bandage", 1, 2, 0.6), ("nr:scrap", 2, 4, 0.7), ("nr:rags", 1, 3, 0.6),
                     ("nr:alcohol", 1, 2, 0.4), ("nr:battery", 1, 1, 0.25), ("nr:money", 3, 10, 0.6),
                     ("nr:energy_drink", 1, 1, 0.3), ("nr:survivor_arrow", 4, 8, 0.2),
                     ("nr:w_throwing_knives", 2, 4, 0.15), ("nr:w_firecracker", 1, 2, 0.2),
                     ("nr:lockpick", 1, 2, 0.25)],
    "stash_locked": [("nr:medkit", 1, 1, 0.5), ("nr:immunity_booster", 1, 2, 0.45), ("nr:inhibitor", 1, 1, 0.08),
                     ("nr:battery", 1, 2, 0.5), ("nr:gunpowder_pouch", 1, 2, 0.4), ("nr:money", 8, 24, 0.8),
                     ("nr:ammo_pistol", 6, 12, 0.3), ("nr:repair_kit", 1, 1, 0.3),
                     ("nr:w_kukri", 1, 1, 0.05), ("nr:w_fire_axe", 1, 1, 0.04), ("nr:w_pistol", 1, 1, 0.04),
                     ("nr:w_pipe_bomb", 1, 1, 0.15), ("nr:w_uv_flare", 1, 2, 0.25)],
    "med_cabinet":  [("nr:bandage", 1, 3, 0.8), ("nr:medkit", 1, 1, 0.2), ("nr:alcohol", 1, 1, 0.4),
                     ("nr:chemicals", 1, 1, 0.3), ("nr:painkillers", 1, 1, 0.35), ("nr:immunity_booster", 1, 1, 0.1)],
    "car_trunk":    [("nr:scrap", 1, 3, 0.8), ("nr:rags", 1, 2, 0.4), ("nr:duct_tape", 1, 1, 0.3),
                     ("nr:battery", 1, 1, 0.35), ("nr:alcohol", 1, 1, 0.2), ("nr:money", 2, 8, 0.4),
                     ("nr:w_crowbar", 1, 1, 0.06), ("nr:w_claw_hammer", 1, 1, 0.06), ("nr:w_sign_axe", 1, 1, 0.01),
                     ("nr:repair_kit", 1, 1, 0.1)],
    "glovebox":     [("nr:money", 1, 5, 0.6), ("nr:bandage", 1, 1, 0.3), ("nr:battery", 1, 1, 0.2),
                     ("nr:chocolate_bar", 1, 1, 0.3), ("nr:painkillers", 1, 1, 0.15), ("nr:ammo_pistol", 2, 6, 0.08)],
    "police_trunk": [("nr:ammo_pistol", 6, 14, 0.7), ("nr:ammo_shotgun", 2, 6, 0.35), ("nr:w_police_baton", 1, 1, 0.3),
                     ("nr:w_pistol", 1, 1, 0.12), ("nr:w_pump_shotgun", 1, 1, 0.03), ("nr:bandage", 1, 2, 0.5),
                     ("nr:battery", 1, 2, 0.4), ("nr:binoculars", 1, 1, 0.05)],
    "ambulance":    [("nr:medkit", 1, 2, 0.6), ("nr:bandage", 2, 4, 0.8), ("nr:immunity_booster", 1, 1, 0.3),
                     ("nr:chemicals", 1, 2, 0.5), ("nr:alcohol", 1, 2, 0.5), ("nr:fortify_booster", 1, 1, 0.12),
                     ("nr:painkillers", 1, 2, 0.4)],
    "bus_luggage":  [("nr:rags", 1, 3, 0.7), ("nr:money", 2, 10, 0.6), ("nr:canned_food", 1, 2, 0.4),
                     ("nr:energy_drink", 1, 1, 0.3), ("nr:bandage", 1, 1, 0.3), ("nr:chocolate_bar", 1, 2, 0.3)],
    "cargo":        [("nr:scrap", 2, 5, 0.8), ("nr:duct_tape", 1, 2, 0.5), ("nr:chemicals", 1, 2, 0.35),
                     ("nr:battery", 1, 2, 0.35), ("nr:canned_food", 1, 3, 0.4), ("nr:gunpowder_pouch", 1, 1, 0.15),
                     ("nr:w_sledgehammer", 1, 1, 0.04), ("nr:w_rebar_club", 1, 1, 0.05)],
    "garbage":      [("nr:rags", 1, 4, 0.8), ("nr:scrap", 1, 3, 0.6), ("nr:chemicals", 1, 1, 0.2),
                     ("nr:mutated_tissue", 1, 1, 0.05), ("nr:money", 1, 3, 0.2), ("nr:w_nail_bat", 1, 1, 0.03)],
    "dumpster":     [("nr:rags", 1, 3, 0.7), ("nr:scrap", 0, 2, 0.5), ("nr:duct_tape", 1, 1, 0.15),
                     ("nr:alcohol", 1, 1, 0.12), ("nr:canned_food", 1, 1, 0.15)],
    "army_crate":   [("nr:ammo_rifle", 4, 10, 0.6), ("nr:ammo_pistol", 8, 16, 0.6), ("nr:ammo_shotgun", 4, 8, 0.4),
                     ("nr:gunpowder_pouch", 2, 4, 0.6), ("nr:medkit", 1, 1, 0.4), ("nr:w_pipe_bomb", 1, 2, 0.3),
                     ("nr:w_hunting_rifle", 1, 1, 0.03), ("nr:w_double_barrel", 1, 1, 0.05),
                     ("nr:w_combat_knife", 1, 1, 0.15), ("nr:binoculars", 1, 1, 0.2)],
    "helicopter":   [("nr:inhibitor", 1, 1, 0.35), ("nr:immunity_booster", 1, 2, 0.6), ("nr:medkit", 1, 2, 0.6),
                     ("nr:battery", 2, 3, 0.6), ("nr:w_revolver", 1, 1, 0.08), ("nr:grappling_hook", 1, 1, 0.05),
                     ("nr:uv_flashlight", 1, 1, 0.12), ("nr:money", 10, 30, 0.7)],
    "gore_remains": [("nr:rags", 1, 2, 0.6), ("nr:money", 1, 6, 0.4), ("nr:bandage", 1, 1, 0.15),
                     ("nr:lockpick", 1, 1, 0.1), ("minecraft:bone", 1, 3, 0.7)],
    "ac_unit":      [("nr:scrap", 2, 4, 0.9), ("nr:battery", 1, 1, 0.2), ("minecraft:copper_ingot", 1, 2, 0.4)],
}


# ===========================================================================
#  街の建物モジュール（gen_nr_structures が .mcstructure に書き出す）
#  向き: 正面（道路側・入口）は -Z。footprint = (x, z) ブロック、height = 地面からの高さ。
#  placement: ground（地面に建つ）/ roof（他の建物の屋上に載せる）/ road（道路の区画タイル）
#  palette: 役割 → ブロック ID（バニラか nr:）。markers: (印の種類, 数, 置き場所の説明)。
#  印は MARKER_KINDS のキー、または "prop:<PROPS のキー>" / "block:<BLOCKS・罠ブロックのキー>"。
#  gen_nr_structures は印の位置を scripts/data/structures.js に書き、スクリプトが街を組むときに湧かせる。
# ===========================================================================
MARKER_KINDS = {
    "z_street":       dict(ja="通りの感染者", spawn="cls=common, time=day の群れ（2〜5 体）"),
    "z_interior":     dict(ja="屋内で眠る感染者", spawn="cls=common、昼は寝ていて物音で起きる。夜は外へ出る"),
    "z_viral":        dict(ja="騒ぎに駆けつける俊敏型", spawn="cls=viral、銃声・アラーム・爆発の後に湧く"),
    "z_special":      dict(ja="特殊感染者", spawn="cls=special を spawn.weight で 1 体"),
    "z_night_nest":   dict(ja="夜の捕食者の巣（ダークゾーン）", spawn="cls=night。昼は暗がりで眠り、夜に出てくる"),
    "z_boss":         dict(ja="ボスの居場所", spawn="cls=boss、まれ（街ごとに最大 1）"),
    "prop_car":       dict(ja="車", spawn="sedan_wreck / taxi_wreck / police_car / pickup_truck / burnt_car / overturned_car を spawn_weight で"),
    "prop_big":       dict(ja="大きい車", spawn="city_bus / box_truck / garbage_truck / shipping_container / army_truck / ambulance"),
    "loot_stash":     dict(ja="生存者の隠し箱", spawn="nr:survivor_stash（nr:locked=0）"),
    "loot_locked":    dict(ja="鍵付きの隠し箱", spawn="nr:survivor_stash（nr:locked=1）"),
    "loot_med":       dict(ja="救急箱", spawn="nr:med_cabinet（壁）"),
    "loot_crate":     dict(ja="木箱", spawn="nr:wooden_crate 1〜3 個"),
    "trap_random":    dict(ja="罠（燃料缶・ボンベ・ガス管）", spawn="fuel_canister / propane_tank / gas_pipe のどれか"),
    "uv_safe":        dict(ja="UV の安全地帯", spawn="nr:uv_lamp（nr:powered=1）。安全地帯の中心"),
    "survivor_spawn": dict(ja="生存者の出発点", spawn="プレイヤーの出現・復活の地点（隠れ家の中）"),
    "zipline":        dict(ja="ジップラインの端", spawn="nr:zipline_anchor。近くの別の端と結ぶ"),
    "landing":        dict(ja="着地点", spawn="nr:trash_bags（落下ダメージ無効）"),
    "climb_route":    dict(ja="登りの道筋", spawn="置かない。テストとガイド表示の目印（縁・足場の順）"),
    "roof_link":      dict(ja="屋上の渡り", spawn="隣の建物の屋上へ板（バニラの足場板）か鉄骨を渡す端"),
    "lamp":           dict(ja="街灯", spawn="MULTIBLOCKS.street_lamp"),
    "barricade":      dict(ja="バリケード", spawn="nr:barricade / nr:metal_barricade / nr:sandbags / nr:road_barrier"),
}

STRUCTURES = [
    dict(key="apartment_low", ja="低層アパート", en="Low-Rise Apartment", district="residential",
         placement="ground", footprint=(16, 20), height=18, floors=3, floor_h=5, weight=10,
         palette=dict(walls="minecraft:brick_block", walls_alt="minecraft:white_terracotta",
                      trim="minecraft:smooth_stone", floor="minecraft:spruce_planks",
                      ceiling="minecraft:smooth_stone", window="minecraft:glass_pane",
                      window_broken="nr:broken_window", roof="minecraft:gray_concrete",
                      parapet="minecraft:stone_brick_wall", fire_escape="minecraft:iron_bars",
                      fire_escape_floor="minecraft:iron_trapdoor", ladder="minecraft:ladder",
                      door="minecraft:spruce_door", stairs="minecraft:stone_brick_stairs",
                      decor_wet="minecraft:moss_carpet", web="minecraft:web"),
         features=["東側の外壁に 3 階分の非常階段（鉄格子の踊り場と梯子。1 階は梯子が上がっていてジャンプで掴む）",
                   "各階 2 部屋。散らかった家具（バニラの樽・本棚・羊毛のベッド）、壁の血の手形",
                   "窓の半分は割れた窓枠（nr:broken_window）で、外から飛び込める",
                   "屋上: 給水塔（MULTIBLOCKS.water_tower）・室外機 2・換気フード 1・物干し",
                   "正面の玄関に板のバリケード（半分壊れている）", "裏の路地にゴミ袋の山（着地点）"],
         markers=[("z_interior", 4, "各階の部屋"), ("z_street", 1, "正面の歩道"), ("loot_stash", 1, "3 階の奥の部屋"),
                  ("loot_med", 1, "2 階の浴室"), ("loot_crate", 1, "屋上の物置"), ("landing", 1, "裏の路地"),
                  ("roof_link", 2, "屋上の東西の縁"), ("climb_route", 6, "非常階段→屋上")],
         connects=dict(front="-Z", door=(8, 0), roof_height=16, roof_links=("east", "west"),
                       street="正面は歩道に接し、裏は幅 2 の路地")),
    dict(key="apartment_tall", ja="高層アパート", en="High-Rise Apartment", district="residential",
         placement="ground", footprint=(24, 24), height=42, floors=7, floor_h=5, weight=5,
         palette=dict(walls="minecraft:light_gray_concrete", walls_alt="minecraft:gray_concrete",
                      trim="minecraft:white_concrete", floor="minecraft:polished_andesite",
                      ceiling="minecraft:smooth_stone", window="minecraft:gray_stained_glass_pane",
                      window_broken="nr:broken_window", balcony="minecraft:smooth_stone_slab",
                      railing="minecraft:iron_bars", roof="minecraft:gray_concrete",
                      stairs="minecraft:polished_andesite_stairs", ladder="minecraft:ladder",
                      lobby_floor="minecraft:white_concrete", dark_floor="minecraft:black_concrete",
                      decor_wet="minecraft:moss_carpet", web="minecraft:web"),
         features=["正面に段違いのバルコニー（隣のバルコニーへ 2〜3 ブロックの跳躍で登れるパルクールの道）",
                   "1〜2 階は窓を塞いだ真っ暗な「ダークゾーン」（夜の捕食者の巣、昼に忍び込むと物資）",
                   "中央の階段室（踊り場に死体・血だまり）。エレベーター穴（落ちると下まで）",
                   "屋上: ジップラインの端・アンテナ（避雷針）・ペントハウスの小屋・室外機の列",
                   "外壁の縦樋と看板の縁が登れる手掛かり"],
         markers=[("z_night_nest", 2, "1〜2 階の暗がり"), ("z_interior", 6, "3〜7 階の廊下と部屋"),
                  ("z_special", 1, "ロビー"), ("loot_locked", 1, "最上階のペントハウス"),
                  ("loot_stash", 2, "4 階と 6 階"), ("loot_med", 2, "各階の廊下"), ("zipline", 1, "屋上の角"),
                  ("climb_route", 10, "バルコニー伝い→屋上"), ("roof_link", 1, "屋上の東の縁")],
         connects=dict(front="-Z", door=(12, 0), roof_height=37, roof_links=("east",),
                       street="ロビーは歩道に面したガラス戸（割れている）")),
    dict(key="corner_shop", ja="角の商店", en="Corner Shop", district="commercial",
         placement="ground", footprint=(14, 14), height=11, floors=2, floor_h=5, weight=10,
         palette=dict(walls="minecraft:cyan_terracotta", trim="minecraft:white_concrete",
                      floor="minecraft:white_terracotta", ceiling="minecraft:smooth_stone",
                      shopfront="nr:broken_window", shutter="minecraft:iron_trapdoor",
                      awning="minecraft:red_carpet", shelf="minecraft:barrel", counter="minecraft:spruce_planks",
                      window="minecraft:glass_pane", roof="minecraft:gray_concrete", ladder="minecraft:ladder"),
         features=["角の 2 面がショーウィンドウ（割れている）、半分下りたシャッター",
                   "赤い日除け（乗れる。歩道から日除け→ 2 階の窓→屋上へ登れる）",
                   "店内: 倒れた棚・散らばった缶（debris_scatter）・レジの台、奥の倉庫",
                   "2 階は店主の住まい（散らかった部屋、閉じこもった跡）",
                   "屋上に看板の枠"],
         markers=[("z_interior", 2, "倉庫と 2 階"), ("loot_crate", 2, "倉庫"), ("loot_stash", 1, "2 階の寝室"),
                  ("prop:dumpster", 1, "横の路地"), ("climb_route", 4, "日除け→ 2 階→屋上"),
                  ("roof_link", 1, "屋上の北の縁")],
         connects=dict(front="-Z", door=(2, 0), roof_height=10, roof_links=("north",),
                       street="交差点の角に置く（-Z と -X の 2 面が道路）")),
    dict(key="gas_station", ja="ガソリンスタンド", en="Gas Station", district="commercial",
         placement="ground", footprint=(32, 24), height=10, floors=1, floor_h=6, weight=4,
         palette=dict(ground="minecraft:light_gray_concrete", canopy="minecraft:white_concrete",
                      canopy_trim="minecraft:red_concrete", pillar="minecraft:smooth_stone",
                      kiosk_walls="minecraft:white_concrete", kiosk_window="minecraft:glass_pane",
                      pump="minecraft:red_concrete", sign_pole="minecraft:iron_bars",
                      sign_face="minecraft:yellow_concrete", roof="minecraft:gray_concrete",
                      lamp="minecraft:sea_lantern"),
         features=["給油所の屋根（高さ 6、柱 4 本。車の屋根から飛び乗れる）、屋根裏に照明（sea_lantern）",
                   "給油機 4 台（撃つと燃料缶と同じ爆発: block:fuel_canister を足元に）",
                   "売店（割れた入口、倒れた棚、レジ、冷蔵庫の列）",
                   "背の高い価格の看板（柱を登れる、上からジップライン）",
                   "プロパンの檻（撃つと連鎖して吹き飛ぶ）"],
         markers=[("prop_car", 3, "給油機の横"), ("block:fuel_canister", 4, "給油機の足元"),
                  ("prop:propane_tank", 3, "売店の横の檻"), ("z_street", 2, "敷地"), ("z_interior", 1, "売店の奥"),
                  ("loot_crate", 2, "売店"), ("loot_med", 1, "売店のトイレ"), ("zipline", 1, "看板の上")],
         connects=dict(front="-Z", door=(24, 18), roof_height=6, roof_links=(),
                       street="正面の 2 か所の出入口が道路へ（縁石を切り下げる）")),
    dict(key="clinic", ja="診療所", en="Clinic", district="civic",
         placement="ground", footprint=(28, 22), height=16, floors=3, floor_h=5, weight=3,
         palette=dict(walls="minecraft:white_concrete", trim="minecraft:light_gray_concrete",
                      floor="minecraft:white_terracotta", ceiling="minecraft:smooth_stone",
                      window="minecraft:white_stained_glass_pane", window_broken="nr:broken_window",
                      cross_sign="minecraft:red_concrete", bed="minecraft:white_wool",
                      curtain="minecraft:light_gray_stained_glass_pane", roof="minecraft:light_gray_concrete",
                      stairs="minecraft:stone_brick_stairs", lamp="minecraft:sea_lantern",
                      blood_floor="nr:blood_pool"),
         features=["正面の赤十字の看板（壁に赤いコンクリで十字）、救急搬入口のスロープと庇",
                   "1 階: 待合室（倒れた椅子・血の引きずり跡）、受付、処置室",
                   "2 階: 病室（ベッド・カーテンの仕切り・点滴台＝鉄格子）、隔離室（板で封鎖、中に感染者）",
                   "3 階: 薬品庫（鍵付き）、屋上へのハッチ", "屋上にヘリポートの H と室外機"],
         markers=[("z_interior", 6, "病室と廊下"), ("z_special", 1, "隔離室"), ("loot_med", 4, "処置室と病室"),
                  ("loot_locked", 1, "3 階の薬品庫"), ("prop:ambulance", 1, "搬入口"),
                  ("block:blood_pool", 4, "床"), ("climb_route", 5, "庇→ 2 階の窓→屋上"), ("roof_link", 1, "屋上の西")],
         connects=dict(front="-Z", door=(14, 0), roof_height=15, roof_links=("west",),
                       street="正面玄関と、横の救急搬入口（車が入れる幅 6）")),
    dict(key="police_station", ja="警察署", en="Police Station", district="civic",
         placement="ground", footprint=(26, 24), height=13, floors=2, floor_h=5, weight=2,
         palette=dict(walls="minecraft:stone_bricks", walls_alt="minecraft:blue_concrete",
                      trim="minecraft:white_concrete", floor="minecraft:polished_andesite",
                      ceiling="minecraft:smooth_stone", window="minecraft:glass_pane",
                      bars="minecraft:iron_bars", door="minecraft:iron_door", roof="minecraft:gray_concrete",
                      stairs="minecraft:stone_brick_stairs", sandbags="nr:sandbags",
                      barricade="nr:metal_barricade", lamp="minecraft:redstone_lamp"),
         features=["正面に土嚢と鉄板のバリケードの陣地（最後の抵抗の跡、薬莢と血）",
                   "1 階: 受付、留置場（鉄格子の房に閉じ込められた感染者）、武器庫（鍵付き）",
                   "2 階: 事務所、ロッカー室、屋上への階段", "裏の駐車場にパトカー 2 台",
                   "屋上: 無線のアンテナ（避雷針の列）と投光器"],
         markers=[("z_interior", 4, "事務所と廊下"), ("z_special", 1, "留置場（重装の感染者）"),
                  ("loot_locked", 2, "武器庫"), ("loot_stash", 1, "ロッカー室"), ("loot_med", 1, "受付"),
                  ("prop:police_car", 2, "裏の駐車場"), ("barricade", 4, "正面の陣地"), ("roof_link", 1, "屋上の東")],
         connects=dict(front="-Z", door=(13, 2), roof_height=12, roof_links=("east",),
                       street="正面の階段と陣地が歩道まで張り出す")),
    dict(key="church_tower", ja="教会の塔", en="Church Tower", district="civic",
         placement="ground", footprint=(16, 26), height=48, floors=2, floor_h=8, weight=1,
         palette=dict(walls="minecraft:stone_bricks", walls_alt="minecraft:cracked_stone_bricks",
                      moss="minecraft:mossy_stone_bricks", trim="minecraft:smooth_quartz",
                      pillar="minecraft:quartz_pillar", floor="minecraft:dark_oak_planks",
                      pews="minecraft:spruce_planks", stained_a="minecraft:red_stained_glass_pane",
                      stained_b="minecraft:blue_stained_glass_pane", stained_c="minecraft:yellow_stained_glass_pane",
                      roof="minecraft:deepslate_tiles", bell="minecraft:bell", ladder="minecraft:ladder",
                      spire="minecraft:polished_blackstone", candle_light="minecraft:lantern"),
         features=["身廊（高さ 16、ステンドグラスの窓、並んだ長椅子、祭壇の前に避難者の寝床の跡）",
                   "正面の塔（6×6、高さ 48）。外壁の飛び出た石の縁と窓の庇を伝って頂上まで登れる",
                   "塔の中は梯子と踊り場、途中の鐘楼に鐘（鳴らすと街中の感染者が集まる）",
                   "頂上は街を見渡す見晴らし（ジップラインの起点、マップの目印）"],
         markers=[("z_interior", 5, "身廊"), ("z_night_nest", 1, "地下の納骨堂（入口は祭壇の裏）"),
                  ("loot_stash", 1, "鐘楼"), ("loot_locked", 1, "納骨堂"), ("zipline", 2, "塔の頂上"),
                  ("climb_route", 14, "塔の外壁→鐘楼→頂上")],
         connects=dict(front="-Z", door=(8, 0), roof_height=16, roof_links=(),
                       street="正面に石段と小さな広場（墓地の柵）")),
    dict(key="warehouse", ja="倉庫", en="Warehouse", district="industrial",
         placement="ground", footprint=(40, 28), height=14, floors=1, floor_h=12, weight=4,
         palette=dict(walls="minecraft:light_gray_concrete", walls_alt="minecraft:iron_block",
                      frame="minecraft:gray_concrete", floor="minecraft:smooth_stone",
                      roof="minecraft:gray_concrete", skylight="minecraft:glass", door="minecraft:iron_trapdoor",
                      rack="nr:scaffold_platform", crate="nr:wooden_crate", catwalk="minecraft:iron_bars",
                      catwalk_floor="minecraft:spruce_slab", lamp="minecraft:redstone_lamp",
                      ladder="minecraft:ladder"),
         features=["大きな搬入口（シャッター 3 つ、1 つは開いている）とプラットフォーム",
                   "中に背の高い棚（足場ブロックで 3 段、上を渡って移動できる）と木箱の山",
                   "壁沿いのキャットウォーク（高さ 8）と事務所の中二階",
                   "屋根の天窓（割れて中に飛び降りられる。下に着地用のゴミ袋）",
                   "暗い奥は夜の捕食者の巣"],
         markers=[("z_night_nest", 2, "奥の暗がり"), ("z_interior", 5, "棚の間"), ("z_special", 1, "搬入口"),
                  ("loot_crate", 6, "棚"), ("loot_locked", 1, "中二階の事務所"), ("prop_big", 1, "搬入口の前"),
                  ("landing", 1, "天窓の下"), ("trap_random", 2, "棚の間"), ("climb_route", 6, "棚→キャットウォーク→天窓")],
         connects=dict(front="-Z", door=(20, 0), roof_height=14, roof_links=("east", "west"),
                       street="搬入口の前は車が入れる広い舗装")),
    dict(key="parking_garage", ja="立体駐車場", en="Parking Garage", district="commercial",
         placement="ground", footprint=(32, 40), height=17, floors=4, floor_h=4, weight=2,
         palette=dict(floor="minecraft:gray_concrete", pillar="minecraft:light_gray_concrete",
                      low_wall="minecraft:smooth_stone", ramp="minecraft:smooth_stone_slab",
                      line_paint="minecraft:white_concrete", stair_core="minecraft:polished_andesite",
                      stairs="minecraft:polished_andesite_stairs", railing="minecraft:iron_bars",
                      lamp="minecraft:sea_lantern", barrier="nr:road_barrier"),
         features=["4 層の開放型の駐車場（外周は腰の高さの壁＝乗り越えて外へ飛び出せる）",
                   "片側のスロープで層をつなぐ。各層に車が 3〜5 台（アラーム付きが混じる）",
                   "階段室の塔（角）。最上階は屋根なしで、まれにヘリの残骸",
                   "外壁の柱を伝って登れる（パルクールの練習場）"],
         markers=[("prop_car", 14, "各層の駐車枠"), ("prop:helicopter_crash", 1, "最上階（30% で出す）"),
                  ("z_street", 4, "各層"), ("z_viral", 2, "最上階"), ("loot_stash", 1, "階段室"),
                  ("climb_route", 8, "外の柱→各層→最上階"), ("roof_link", 1, "最上階の東")],
         connects=dict(front="-Z", door=(4, 0), roof_height=16, roof_links=("east",),
                       street="正面に車の出入口 2 つ（バーが折れている）")),
    dict(key="rooftop_parkour_set", ja="屋上パルクールの足場", en="Rooftop Parkour Kit", district="any",
         placement="roof", footprint=(24, 24), height=12, floors=0, floor_h=0, weight=8,
         palette=dict(plank_bridge="minecraft:spruce_slab", beam="minecraft:iron_bars",
                      shack_walls="minecraft:spruce_planks", shack_roof="nr:metal_barricade",
                      scaffold="nr:scaffold_platform", ac="nr:ac_unit", vent="nr:roof_vent",
                      leg="nr:water_tower_leg", tank="minecraft:spruce_planks", fence="nr:chainlink_fence",
                      landing="nr:trash_bags"),
         features=["屋上に載せる部品の組: 板の渡り（隣の屋上まで 3〜6 ブロック）、鉄骨の梁、足場の塔",
                   "生存者の小屋（中にクラフト台と隠し箱、外に UV ライト）",
                   "給水塔（脚を登って、上からジップライン）、換気フード（パラグライダーの上昇気流）",
                   "金網フェンスの囲い（登って越える）、室外機の列（乗り越え）"],
         markers=[("roof_link", 4, "四方の縁"), ("zipline", 1, "給水塔の上"), ("loot_stash", 1, "小屋"),
                  ("uv_safe", 1, "小屋の前"), ("z_street", 1, "屋上（昼の迷い感染者）"),
                  ("climb_route", 8, "足場→給水塔")],
         connects=dict(front="-Z", door=None, roof_height=0, roof_links=("north", "south", "east", "west"),
                       street="建物の屋上の高さに置く（スクリプトが下の建物の roof_height に合わせる）")),
    dict(key="uv_safehouse", ja="UV の隠れ家", en="UV Safehouse", district="any",
         placement="ground", footprint=(12, 12), height=8, floors=1, floor_h=5, weight=2,
         palette=dict(walls="minecraft:spruce_planks", walls_alt="nr:metal_barricade",
                      floor="minecraft:spruce_planks", roof="minecraft:spruce_slab",
                      window="minecraft:iron_bars", door="minecraft:iron_door", lamp="nr:uv_lamp",
                      bench="nr:crafting_bench", stash="nr:survivor_stash", bed="minecraft:white_wool",
                      sandbags="nr:sandbags", rug="minecraft:gray_carpet", candle_light="minecraft:lantern"),
         features=["鉄板と板で補強した小屋。四隅と入口に UV ライト（半径 10 が夜の安全地帯）",
                   "中: 寝床（休むと夜を飛ばせる＝バニラのベッドは置かず、スクリプトの「休む」）、作業台、隠し箱",
                   "屋根に登る梯子と、屋上の見張り台（ジップラインの端）",
                   "入口の前に土嚢と有刺鉄線"],
         markers=[("survivor_spawn", 1, "中央"), ("uv_safe", 5, "四隅と入口"), ("loot_stash", 1, "奥"),
                  ("zipline", 1, "屋根"), ("block:barbed_wire", 3, "入口の前")],
         connects=dict(front="-Z", door=(6, 0), roof_height=6, roof_links=(),
                       street="どこにでも置ける。街を組むとき、出発点として最初に 1 つ")),
    dict(key="collapsed_building", ja="崩れたビル", en="Collapsed Building", district="any",
         placement="ground", footprint=(20, 20), height=24, floors=4, floor_h=5, weight=3,
         palette=dict(walls="minecraft:light_gray_concrete", walls_alt="minecraft:cracked_stone_bricks",
                      floor="minecraft:smooth_stone", rubble="nr:rubble_pile", debris="nr:debris_scatter",
                      rebar="minecraft:iron_bars", slab="minecraft:smooth_stone_slab",
                      stairs="minecraft:stone_brick_stairs", dust="minecraft:gravel",
                      moss="minecraft:moss_block", vine="minecraft:vine", web="minecraft:web"),
         features=["半分崩れた 4 階建て。崩れた側は床が斜めに垂れ下がり、瓦礫の斜面になって 3 階まで登れる",
                   "むき出しの鉄筋（鉄格子）と宙に浮いた床の切れ端（跳び移るパルクール）",
                   "残った側の部屋は暗く、夜の捕食者がいる", "瓦礫の下に押し潰された車"],
         markers=[("z_night_nest", 1, "残った側の 1 階"), ("z_interior", 3, "残った部屋"),
                  ("loot_crate", 2, "瓦礫の間"), ("loot_stash", 1, "4 階の端"), ("prop:burnt_car", 1, "瓦礫の下"),
                  ("climb_route", 10, "瓦礫の斜面→床の切れ端→ 4 階")],
         connects=dict(front="-Z", door=(10, 0), roof_height=20, roof_links=("east",),
                       street="正面の歩道まで瓦礫が崩れ出す")),
    dict(key="billboard_roof", ja="屋上の看板", en="Rooftop Billboard", district="commercial",
         placement="roof", footprint=(12, 6), height=14, floors=0, floor_h=0, weight=4,
         palette=dict(frame="minecraft:iron_bars", face="minecraft:white_concrete",
                      face_print="minecraft:orange_concrete", catwalk="minecraft:iron_trapdoor",
                      ladder="minecraft:ladder", lamp="minecraft:redstone_lamp"),
         features=["鉄骨の脚に載った大きな看板（色褪せた架空の広告、破れた紙）",
                   "看板の前のキャットウォークと照明（夜は点く）", "裏の梯子で上へ。看板の上はこの区画で最も高い足場の一つ"],
         markers=[("zipline", 1, "看板の上"), ("climb_route", 4, "梯子→キャットウォーク→上"), ("loot_crate", 1, "キャットウォーク")],
         connects=dict(front="-Z", door=None, roof_height=0, roof_links=(),
                       street="建物の屋上の道路側に置く")),
    dict(key="street_block_segment", ja="通りの区画", en="Street Segment", district="any",
         placement="road", footprint=(48, 14), height=2, floors=0, floor_h=0, weight=10,
         palette=dict(asphalt="minecraft:black_concrete", asphalt_worn="minecraft:gray_concrete",
                      lane="minecraft:white_concrete", center="minecraft:yellow_concrete",
                      curb="minecraft:smooth_stone_slab", sidewalk="minecraft:polished_andesite",
                      sidewalk_crack="minecraft:andesite", manhole="minecraft:iron_trapdoor",
                      grate="minecraft:iron_bars", planter="minecraft:coarse_dirt", grass="minecraft:grass_block",
                      crosswalk="minecraft:white_concrete"),
         features=["幅 8 の車道（2 車線、中央の黄線、白い破線、ひび割れと穴）＋両側に幅 3 の歩道と縁石",
                   "端に横断歩道（区画の継ぎ目）、マンホール、雨水の格子",
                   "歩道の植え込み（枯れ木の跡）、12 ブロックごとに街灯",
                   "乗り捨てられた車の列（斜めに止まる、ドアが開いている）、道を塞ぐバリケード"],
         markers=[("prop_car", 3, "車道"), ("prop_big", 1, "車道（20%）"), ("lamp", 4, "歩道"),
                  ("z_street", 3, "車道と歩道"), ("barricade", 2, "車道（15%）"), ("block:traffic_cone", 3, "車道"),
                  ("block:blood_pool", 2, "歩道"), ("block:road_sign", 1, "交差点側の歩道"),
                  ("trap_random", 1, "歩道（20%）"), ("prop:dumpster", 1, "路地の口")],
         connects=dict(front="-Z", door=None, roof_height=0, roof_links=(),
                       street="長さ 48 の道路タイル。端で隣の区画・交差点につながる")),
]

# 街区の組み立て（scripts の city 生成が使う数値）
CITY = dict(
    grid_pitch=64,            # 街区の間隔（道路の中心から中心まで）
    road_width=8, sidewalk=3, alley=2, curb_height=1,
    lot=50,                   # 道路と歩道を除いた区画の内側（これに建物 1 つか、小さいもの 2〜4）
    sub_lots=((24, 24), (16, 16)),
    lamp_spacing=12, car_per_segment=(2, 4), big_vehicle_chance=0.2, barricade_chance=0.15,
    blood_decal_chance=0.3, roof_link_chance=0.55, zipline_chance=0.25, rooftop_kit_chance=0.35,
    safehouse_every_blocks=9,   # 3×3 街区に 1 つ
    z_day_per_block=(6, 10), z_night_per_block=(3, 6), viral_on_noise=(2, 4),
    max_city_blocks=(5, 5), build_ticks_per_block=4, seed_default=1337,
    district_weights=dict(residential=0.4, commercial=0.3, civic=0.1, industrial=0.2),
    ground_y_offset=0,
)


# ===========================================================================
#  スキル（端末の「スキル」画面）。パルクールの点はパルクールの経験値、戦闘の点は戦闘の経験値で貯まる。
#  requires は同じ木でなくてもよい。effect の数値は parkour.js / combat.js がそのまま読む。
#  input は操作（統合版の入力: ジャンプ・スニーク・攻撃・使用・ダッシュ）
# ===========================================================================
def _skill(key, ja, en, tree, tier, cost, requires, effect, desc_ja, desc_en, input=None, icon=""):
    return dict(key=key, ja=ja, en=en, tree=tree, tier=tier, cost=cost, requires=list(requires),
                effect=dict(effect), desc_ja=desc_ja, desc_en=desc_en, input=input, icon=icon)


SKILLS = [
    # --- パルクール --------------------------------------------------------------------
    _skill("second_wind", "健脚", "Second Wind", "parkour", 1, 1, [],
           dict(stamina_regen_mult=1.25, stamina_max_add=10),
           "スタミナの回復 +25%、最大スタミナ +10。", "+25% stamina regen, +10 max stamina.",
           icon="走る脚と上向きの矢印"),
    _skill("speed_vault", "スピードヴォルト", "Speed Vault", "parkour", 2, 1, ["second_wind"],
           dict(vault_max_height=2.1, vault_speed_keep=1.0, vault_stamina_mult=0.5),
           "2 段の障害物も速度を落とさず飛び越える。", "Vault two-block obstacles without losing speed.",
           input="ダッシュ中に障害物へジャンプ", icon="箱を両手で越える人影"),
    _skill("wall_run", "壁走り", "Wall Run", "parkour", 3, 2, ["speed_vault"],
           dict(wallrun_ticks=24, wallrun_rise=1.2),
           "ダッシュジャンプで壁に沿って 1.2 秒走る。", "Dash-jump along a wall to run on it for 1.2 s.",
           input="壁に沿ってダッシュ中にジャンプ（長押し）", icon="壁を横に走る人影"),
    _skill("wall_jump", "壁蹴り", "Wall Jump", "parkour", 4, 2, ["wall_run"],
           dict(walljump_h=0.9, walljump_v=0.55, chain_max=3),
           "壁走り中にジャンプで反対側へ跳ぶ（3 回まで連続）。", "Jump off during a wall run (chain up to 3).",
           input="壁走り中にジャンプ", icon="壁を蹴る脚"),
    _skill("climb_sprint", "素早い登攀", "Quick Climber", "parkour", 2, 1, ["second_wind"],
           dict(climb_speed_mult=1.35, climb_stamina_mult=0.7),
           "壁登りの速さ +35%、消費 -30%。", "+35% climb speed, -30% climb stamina.",
           icon="壁を登る手"),
    _skill("safe_roll", "受け身", "Safe Roll", "parkour", 2, 1, ["second_wind"],
           dict(roll_fall_mult=0.15, roll_window_ticks=8),
           "着地直前のスニークで前転し、落下ダメージを 85% 減らす。", "Sneak right before landing to roll: -85% fall damage.",
           input="着地の直前にスニーク", icon="前転する人影"),
    _skill("cat_landing", "猫の着地", "Cat Landing", "parkour", 3, 1, ["safe_roll"],
           dict(safe_fall_add=4),
           "落下ダメージを受けない高さ +4 ブロック。", "+4 blocks of fall height without damage.",
           icon="着地する猫"),
    _skill("slide_tackle", "滑り込み払い", "Slide Tackle", "parkour", 3, 1, ["safe_roll"],
           dict(slide_knockdown=True, slide_damage=3, slide_ticks_add=6),
           "スライディングで感染者の足を払って倒す。", "Sliding knocks infected off their feet.",
           input="ダッシュ中にスニーク", icon="滑り込む脚"),
    _skill("dropkick", "ドロップキック", "Dropkick", "parkour", 4, 2, ["slide_tackle"],
           dict(dropkick_force=2.2, dropkick_damage=6, dropkick_stagger_ticks=30, stamina=20),
           "空中から両足で蹴り飛ばす。屋上から落とせば一撃。", "Kick with both feet from mid-air. Off a roof, it's a kill.",
           input="空中でスニーク＋攻撃", icon="両足で蹴る人影"),
    _skill("grapple_master", "鉤縄の達人", "Grapple Master", "parkour", 4, 2, ["wall_run"],
           dict(grapple_range_add=8, grapple_cooldown_mult=0.6, grapple_pull_enemy=True),
           "グラップリングフックの射程 +8、待ち時間 -40%。敵に撃つと引き寄せる。",
           "+8 grapple range, -40% cooldown. Fire at an enemy to yank it in.", icon="鉤縄"),
    _skill("glider_ace", "滑空の名手", "Glider Ace", "parkour", 4, 1, ["cat_landing"],
           dict(glide_sink_mult=0.7, updraft_mult=1.5),
           "パラグライダーの沈みが 30% 遅く、上昇気流で 1.5 倍上がる。",
           "Paraglider sinks 30% slower; updrafts lift 1.5x.", icon="パラグライダー"),
    _skill("ghost_runner", "追跡逃れ", "Ghost Runner", "parkour", 5, 2, ["grapple_master", "wall_jump"],
           dict(chase_decay_mult=1.4, chase_detect_mult=0.8),
           "夜の追跡が 40% 早く収まり、見つかりにくくなる。",
           "Night chases end 40% faster and you are harder to spot.", icon="影の中の走る人影"),
    # --- 戦闘 --------------------------------------------------------------------------
    _skill("power_attack", "強撃", "Power Attack", "combat", 1, 1, [],
           dict(heavy_damage_mult=1.6, heavy_gore_add=0.25, heavy_charge_ticks=10),
           "スニークしながら攻撃で溜めの強撃（ダメージ +60%、部位破壊 +25%）。",
           "Attack while sneaking for a charged power attack (+60% damage, +25% dismember).",
           input="スニーク＋攻撃", icon="振りかぶる刃"),
    _skill("front_kick", "前蹴り", "Front Kick", "combat", 1, 1, [],
           dict(kick_force=1.2, kick_damage=2, kick_stagger_ticks=24, stamina=8),
           "素手の使用で前蹴り。押し返してよろめかせる。", "Use with an empty hand to kick: shoves and staggers.",
           input="素手で使用（右クリック／長押し）", icon="蹴る脚"),
    _skill("parry", "受け流し", "Parry", "combat", 2, 1, ["front_kick"],
           dict(parry_window_ticks=6, parry_stagger_ticks=40, block_damage_mult=0.4),
           "攻撃を受ける瞬間にスニークで受け流し、相手を大きくよろめかせる。",
           "Sneak just as a hit lands to parry and heavily stagger the attacker.",
           input="被弾の直前にスニーク", icon="交差する刃"),
    _skill("dodge", "回避", "Dodge", "combat", 3, 1, ["parry"],
           dict(dodge_distance=2.2, dodge_iframes=6, stamina=12),
           "横移動中にスニークを素早く 2 回で横へ跳ぶ（無敵 6 tick）。",
           "Double-tap sneak while strafing to sidestep (6 invulnerable ticks).",
           input="横移動中にスニーク 2 回", icon="横へ跳ぶ人影"),
    _skill("vault_kick", "跳び蹴り", "Vault Kick", "combat", 3, 1, ["front_kick", "speed_vault"],
           dict(vault_over_staggered=True, vault_kick_damage=5, vault_kick_force=1.6),
           "よろめいた敵を跳び箱のように越えて背中を蹴り飛ばす。",
           "Vault over a staggered enemy and kick it in the back.",
           input="よろめいた敵へジャンプ", icon="敵を越える人影"),
    _skill("skull_crusher", "頭蓋砕き", "Skull Crusher", "combat", 2, 1, ["power_attack"],
           dict(blunt_head_crush_add=0.35, blunt_stagger_mult=1.2),
           "打撃武器の頭への一撃で頭が弾ける確率 +35%。", "+35% chance for blunt head hits to crush the skull.",
           icon="割れた頭蓋"),
    _skill("dismember_mastery", "解体の極意", "Dismember Mastery", "combat", 2, 2, ["power_attack"],
           dict(slash_gore_add=0.2, limb_hp_mult=0.75),
           "刃物の部位破壊 +20%、手足の部位体力 -25%（腕も脚も落ちやすい）。",
           "+20% slash dismemberment; limbs have 25% less part HP.", icon="切れた腕"),
    _skill("headhunter", "首狩り", "Headhunter", "combat", 3, 2, ["dismember_mastery"],
           dict(stagger_decap_add=0.3, headshot_mult_add=0.25),
           "よろめいた敵の首を刎ねる確率 +30%、頭への一撃 +25%。",
           "+30% decapitation on staggered enemies; +25% head damage.", icon="飛ぶ首"),
    _skill("bleed_mastery", "流血の達人", "Bloodletter", "combat", 3, 1, ["dismember_mastery"],
           dict(bleed_mod_mult=1.5, bleed_chance_add=0.1),
           "出血の改造の効果 1.5 倍、発動 +10%。", "Bleed mods are 1.5x stronger, +10% proc chance.",
           icon="滴る血"),
    _skill("stomp", "踏みつけ", "Stomp", "combat", 2, 1, ["power_attack"],
           dict(stomp_kill_crawler=True, stomp_head_crush=True, stomp_damage=20),
           "這う・倒れた感染者の頭を踏み潰して止めを刺す。", "Stomp the heads of crawling or downed infected to finish them.",
           input="倒れた敵の上でスニーク＋攻撃", icon="踏み下ろす靴"),
    _skill("finisher", "処刑", "Executioner", "combat", 4, 2, ["stomp", "headhunter"],
           dict(finisher_on_stun=True, finisher_heal=2, finisher_stamina=15),
           "感電・よろめきの敵に処刑技（首を刎ねる・頭を割る）。体力とスタミナが少し戻る。",
           "Execute stunned or staggered enemies (decapitate or split the skull); restores some health and stamina.",
           input="よろめいた敵に強撃", icon="処刑の刃"),
    _skill("ground_pound", "地面叩き", "Ground Pound", "combat", 4, 2, ["skull_crusher", "dropkick"],
           dict(ground_pound_radius=3.0, ground_pound_damage=10, ground_pound_force=1.4),
           "両手打撃武器を空中から叩きつけ、周りを吹き飛ばす。",
           "Slam a two-handed blunt weapon from mid-air to blast everything around.",
           input="空中で両手打撃の強撃", icon="地面の衝撃の輪"),
    _skill("marksman", "射手", "Marksman", "combat", 1, 1, [],
           dict(draw_speed_mult=1.3, ranged_headshot_add=0.25, reload_mult=0.85),
           "弓を引く速さ +30%、飛び道具の頭撃ち +25%、装填 -15%。",
           "+30% draw speed, +25% ranged headshot damage, -15% reload time.", icon="弓と照準"),
    _skill("lethal_throw", "投擲の名手", "Lethal Throw", "combat", 2, 1, ["marksman"],
           dict(throw_damage_mult=1.4, throw_range_mult=1.25, throwable_stack_add=4),
           "投擲のダメージ +40%、飛距離 +25%、持てる数 +4。",
           "+40% throw damage, +25% range, carry 4 more throwables.", icon="飛ぶナイフ"),
]

# 経験値（パルクールと戦闘の 2 本立て。武器の unlock_level は戦闘のレベル）
PROGRESSION = dict(
    max_level=24, points_per_level=1, xp_curve=dict(base=100, exp=1.4),   # 次のレベルまで round(base * level^exp)
    combat_xp=dict(common=8, viral=20, special=50, night=120, boss=600, dismember=2, decapitate=4,
                   finisher=3, headshot=2, trap_kill=3, night_mult=2.0),
    parkour_xp=dict(vault=2, climb_per_block=0.5, wallrun=4, walljump=3, slide=1, roll=3, dropkick=4,
                    grapple=2, glide_per_s=0.2, zipline=2, landing_pile=5, roof_gap=3, chase_escape_per_level=25),
)


def xp_to_next(level: int) -> int:
    c = PROGRESSION["xp_curve"]
    return int(round(c["base"] * level ** c["exp"]))


# ===========================================================================
#  パルクールの数値（ブロック・tick。プレイヤーは applyImpulse が効かないので applyKnockback と効果で動かす）
# ===========================================================================
PARKOUR_TUNING = dict(
    stamina=dict(max=100, regen_per_tick=0.8, regen_delay_ticks=20, exhausted_below=10,
                 exhausted_slow_amp=1, sprint_per_tick=0.0, jump=2, climb_per_tick=0.5, vault=4,
                 wallrun=10, walljump=6, slide=6, roll=0, kick=8, dropkick=20, grapple=10, dodge=12),
    climb=dict(speed=0.18, max_height=0, stamina_needed=5, ledge_reach=1.2, pullup_ticks=12,
               hang_max_ticks=200, wall_check_dist=0.7, hold_jump_ticks=4),
    vault=dict(low_max_height=1.25, high_max_height=1.6, vault_ticks=8, speed_keep=0.85,
               min_speed=0.12, forward_impulse=0.55, up_impulse=0.45),
    wallrun=dict(duration_ticks=24, min_speed=0.18, rise=1.2, gravity_scale=0.25, wall_check_dist=0.8,
                 forward_impulse=0.42, walljump_h=0.9, walljump_v=0.55, cooldown_ticks=10),
    slide=dict(trigger_speed=0.24, duration_ticks=18, speed_boost=1.35, friction=0.92, cooldown_ticks=10,
               hitbox_note="スニークの姿勢（高さ 1.5）で滑る。1 ブロックの隙間は抜けられない"),
    roll=dict(window_ticks=6, min_fall=4, fall_dmg_mult=0.4, roll_ticks=10, forward_impulse=0.4),
    fall=dict(safe_height=6, death_note="安全な高さを超えた分だけバニラの落下ダメージ（ゴミ袋の上は 0）"),
    kick=dict(force=1.2, up=0.25, damage=2, reach=2.2, cooldown_ticks=12),
    dropkick=dict(force=2.2, up=0.45, damage=6, reach=2.6, stagger_ticks=30, cooldown_ticks=30, min_air_ticks=4),
    grapple=dict(range=26, pull_speed=1.6, max_pull_ticks=30, cooldown_ticks=30, swing=False,
                 hook_speed=3.0, min_dist=3),
    glider=dict(min_height=3, sink_per_tick=0.06, forward_speed=0.42, turn_rate=6.0,
                updraft_lift=0.25, slow_falling_amp=0, fold_on_sneak=True),
    zipline=dict(ride_speed=0.75, max_length=48, detach_on_sneak=True),
    jump_boost=dict(amp=1, note="パルクール中のジャンプ力（effect jump_boost）"),
    immunity=dict(max_s=300, drain_per_s=1.0, dark_light_level=5, uv_regen_per_s=10, warn_s=(60, 30, 10),
                  damage_at_zero=2, damage_interval_ticks=20, heartbeat_below_s=30),
    chase=dict(levels=4, detect_radius=(16, 24, 32, 40), decay_s=(20, 30, 40, 60), uv_escape_radius=10,
               spawn_per_level=(1, 2, 3, 5), volatile_speed_mult=(1.0, 1.1, 1.2, 1.35)),
)

# ===========================================================================
#  戦闘の数値（combat.js）
# ===========================================================================
COMBAT_TUNING = dict(
    hitzone_mult=dict(head=2.0, torso=1.0, arm=0.7, leg=0.8),
    part_hp_frac=dict(head=0.45, arm=0.35, leg=0.40, torso=0.90),   # 部位体力（最大体力に対する割合）
    crit_base_chance=0.05, backstab_mult=1.5, stagger_threshold=0.25, stagger_ticks=24,
    heavy=dict(charge_ticks=10, damage_mult=1.6, stamina_mult=1.8, gore_add=0.2),
    durability=dict(per_hit=1, per_miss=0, per_wall=2, broken_damage_mult=0.25, warn_frac=0.2),
    exhausted=dict(attack_speed_mult=0.6, damage_mult=0.7),
    combo_window_ticks=12,
    armor=dict(slash_mult=0.3, pierce_mult=0.4, blunt_mult=0.7, blast_mult=0.8, break_hits=(3, 6)),
    noise=dict(melee=4, gun_default=32, explosion=64, car_alarm=40, shout=12),
    friendly_fire_mult=0.5,
)

# ゴアレベル G（0〜100）で何が変わるか（gore.js）。min_g: その結果が起き始める G
GORE_TUNING = dict(
    sever_mult_exp=0.8,           # 切断の確率 × (G/100)^0.8
    blood_mult="G/100",           # 血のパーティクル・血痕の量
    min_g=dict(wounded=0, jawless=20, cracked=20, broken=0, cut_lower=30, cut_upper=30, severed=30,
               crushed=40, slashed=10, gutted=40, halved=60),
    fountain_ticks=dict(base=40, at_100=100),       # 断面からの血の噴水（G=100 で 5 秒）
    gib_count=dict(sever=1, crushed_head=(3, 8), halved=(2, 5), explode=(6, 14), chunk_scale="G/100"),
    decal_lifetime_s=dict(base=30, at_100=120),
    screen_blood_range=3.0, screen_blood_min_g=50,
    guts_min_g=40, overkill_burst_min_g=70,
)

# HUD に出すゴアのコンボ（独自グリフの文字列は gen_nr_ui、言葉はここ）
GORE_COMBOS = {
    "headshot":    dict(ja="ヘッドショット", en="HEADSHOT", xp=2),
    "dismember":   dict(ja="部位切断", en="DISMEMBER", xp=2),
    "decapitated": dict(ja="斬首", en="DECAPITATED", xp=4),
    "skull_crush": dict(ja="頭蓋粉砕", en="SKULL CRUSH", xp=3),
    "bisected":    dict(ja="一刀両断", en="BISECTED", xp=5),
    "gutted":      dict(ja="腹裂き", en="GUTTED", xp=2),
    "finisher":    dict(ja="処刑", en="EXECUTED", xp=3),
    "environment": dict(ja="罠で仕留めた", en="ENVIRONMENTAL", xp=3),
    "multi_kill":  dict(ja="まとめて仕留めた", en="MULTI KILL", xp=4),
    "overkill":    dict(ja="木っ端微塵", en="OVERKILL", xp=3),
}

# ===========================================================================
#  設定（ワールドの動的プロパティ nr:settings に JSON で保存。端末の「設定」画面）
# ===========================================================================
SETTINGS_SCHEMA = [
    dict(key="gore_level", ja="ゴアレベル", en="Gore Level", type="slider", min=0, max=100, step=5, default=100,
         note_ja="0 = 切断・血なし／100 = 最大（既定）", note_en="0 = no dismemberment or blood / 100 = maximum (default)"),
    dict(key="gib_lifetime_s", ja="肉片が消えるまで（秒）", en="Gib Lifetime (s)", type="slider", min=10, max=300,
         step=10, default=60),
    dict(key="corpse_lifetime_s", ja="死体が消えるまで（秒）", en="Corpse Lifetime (s)", type="slider", min=10,
         max=600, step=10, default=90),
    dict(key="max_gibs", ja="肉片の上限", en="Max Gibs", type="slider", min=0, max=128, step=4, default=48),
    dict(key="max_corpses", ja="死体の上限", en="Max Corpses", type="slider", min=0, max=64, step=2, default=24),
    dict(key="blood_decal_mult", ja="血痕の量", en="Blood Decals", type="slider", min=0.0, max=2.0, step=0.1,
         default=1.0),
    dict(key="screen_blood", ja="画面の返り血", en="Screen Blood", type="toggle", default=True),
    dict(key="particle_budget", ja="1 tick のパーティクル上限", en="Particle Budget / tick", type="slider",
         min=50, max=300, step=10, default=300),
    dict(key="natural_spawn", ja="自然に湧く", en="Natural Spawning", type="toggle", default=True),
    dict(key="horde_density", ja="群れの濃さ", en="Horde Density", type="slider", min=0.25, max=3.0, step=0.25,
         default=1.0),
    dict(key="chase_enabled", ja="夜の追跡", en="Night Chases", type="toggle", default=True),
    dict(key="immunity_enabled", ja="免疫（暗闇で感染）", en="Immunity Timer", type="toggle", default=True),
    dict(key="friendly_fire", ja="味方への攻撃", en="Friendly Fire", type="toggle", default=False),
    dict(key="difficulty", ja="難易度", en="Difficulty", type="dropdown",
         options=("easy", "normal", "hard", "nightmare"), default="normal"),
    dict(key="difficulty_scaling", ja="人数で強くする", en="Scale With Players", type="toggle", default=True),
    dict(key="hud_enabled", ja="HUD を出す", en="Show HUD", type="toggle", default=True),
    dict(key="damage_numbers", ja="ダメージの数字", en="Damage Numbers", type="toggle", default=False),
    dict(key="parkour_assist", ja="パルクールの補助", en="Parkour Assist", type="toggle", default=True,
         note_ja="縁つかみ・乗り越えの判定を甘くする", note_en="More forgiving ledge grabs and vaults"),
]
SETTINGS_DEFAULTS = {s["key"]: s["default"] for s in SETTINGS_SCHEMA}

DIFFICULTY = {
    "easy":      dict(ja="やさしい", en="Easy", zombie_hp_mult=0.75, zombie_damage_mult=0.6, night_mult=0.8,
                      horde_mult=0.75, immunity_drain_mult=0.6, durability_mult=1.5, player_scale_per_extra=0.10),
    "normal":    dict(ja="ふつう", en="Normal", zombie_hp_mult=1.0, zombie_damage_mult=1.0, night_mult=1.0,
                      horde_mult=1.0, immunity_drain_mult=1.0, durability_mult=1.0, player_scale_per_extra=0.15),
    "hard":      dict(ja="むずかしい", en="Hard", zombie_hp_mult=1.3, zombie_damage_mult=1.4, night_mult=1.3,
                      horde_mult=1.3, immunity_drain_mult=1.25, durability_mult=0.8, player_scale_per_extra=0.2),
    "nightmare": dict(ja="悪夢", en="Nightmare", zombie_hp_mult=1.6, zombie_damage_mult=1.8, night_mult=1.6,
                      horde_mult=1.6, immunity_drain_mult=1.5, durability_mult=0.6, player_scale_per_extra=0.25),
}

# ===========================================================================
#  端末のクラフト（独自 UI）。station: terminal（どこでも）/ bench（nr:crafting_bench の 4 ブロック内）
#  unlock: None / {"skill": key} / {"level": 戦闘のレベル}
# ===========================================================================
def _craft(key, category, output, count, inputs, station="terminal", unlock=None, ticks=20):
    return dict(key=key, category=category, output=output, count=count, inputs=[(i, n) for i, n in inputs],
                station=station, unlock=unlock, craft_ticks=ticks)


CRAFT_CATEGORIES = {
    "medical": dict(ja="医療", en="Medical"), "ammo": dict(ja="弾", en="Ammo"),
    "throwable": dict(ja="投擲", en="Throwables"), "booster": dict(ja="ブースター", en="Boosters"),
    "tool": dict(ja="道具", en="Tools"), "trap": dict(ja="罠", en="Traps"), "weapon": dict(ja="武器", en="Weapons"),
    "gun": dict(ja="銃", en="Firearms"), "special": dict(ja="特別", en="Special"),
}

CRAFTING = [
    # 医療
    _craft("bandage", "medical", "nr:bandage", 2, [("nr:rags", 2), ("nr:alcohol", 1)]),
    _craft("medkit", "medical", "nr:medkit", 1, [("nr:bandage", 2), ("nr:alcohol", 1), ("nr:chemicals", 1)],
           ticks=40),
    _craft("immunity_booster", "medical", "nr:immunity_booster", 1,
           [("nr:uv_shroom", 2), ("nr:chemicals", 1), ("minecraft:glass_bottle", 1)], ticks=40),
    _craft("painkillers", "medical", "nr:painkillers", 2, [("nr:chemicals", 1), ("minecraft:sugar", 1)]),
    # ブースター
    _craft("fortify_booster", "booster", "nr:fortify_booster", 1,
           [("nr:mutated_tissue", 1), ("nr:chemicals", 1), ("nr:alcohol", 1)], unlock={"level": 3}),
    _craft("champion_booster", "booster", "nr:champion_booster", 1,
           [("nr:infected_trophy", 1), ("nr:alcohol", 1), ("nr:chemicals", 1)], unlock={"level": 5}),
    _craft("hunter_booster", "booster", "nr:hunter_booster", 1,
           [("nr:volatile_trophy", 1), ("nr:uv_shroom", 2), ("nr:chemicals", 1)], unlock={"level": 8}),
    _craft("inhibitor", "special", "nr:inhibitor", 1,
           [("nr:apex_trophy", 1), ("nr:volatile_trophy", 2), ("nr:mutated_tissue", 4)], ticks=80),
    # 弾
    _craft("ammo_pistol", "ammo", "nr:ammo_pistol", 12, [("nr:scrap", 2), ("nr:gunpowder_pouch", 1)],
           station="bench", unlock={"level": 4}),
    _craft("ammo_shotgun", "ammo", "nr:ammo_shotgun", 6, [("nr:scrap", 2), ("nr:gunpowder_pouch", 1),
                                                         ("minecraft:paper", 1)], station="bench", unlock={"level": 8}),
    _craft("ammo_rifle", "ammo", "nr:ammo_rifle", 5, [("nr:scrap", 3), ("nr:gunpowder_pouch", 1)],
           station="bench", unlock={"level": 14}),
    _craft("bolt", "ammo", "nr:bolt", 4, [("nr:scrap", 2), ("minecraft:stick", 1), ("nr:duct_tape", 1)]),
    _craft("survivor_arrow", "ammo", "nr:survivor_arrow", 6,
           [("nr:blades", 1), ("minecraft:stick", 2), ("minecraft:feather", 1)]),
    # 投擲
    _craft("molotov", "throwable", "nr:w_molotov", 1,
           [("nr:alcohol", 1), ("nr:rags", 1), ("minecraft:glass_bottle", 1)]),
    _craft("pipe_bomb", "throwable", "nr:w_pipe_bomb", 1,
           [("nr:scrap", 2), ("nr:gunpowder_pouch", 1), ("nr:duct_tape", 1)], unlock={"level": 3}),
    _craft("firecracker", "throwable", "nr:w_firecracker", 2, [("nr:gunpowder_pouch", 1), ("minecraft:paper", 2)]),
    _craft("uv_flare", "throwable", "nr:w_uv_flare", 1, [("nr:uv_shroom", 1), ("nr:chemicals", 1), ("nr:scrap", 1)],
           unlock={"level": 2}),
    _craft("throwing_knives", "throwable", "nr:w_throwing_knives", 4, [("nr:blades", 2), ("nr:scrap", 1)]),
    _craft("throwing_stars", "throwable", "nr:w_throwing_stars", 4, [("nr:blades", 3)],
           unlock={"skill": "lethal_throw"}),
    # 道具
    _craft("lockpick", "tool", "nr:lockpick", 2, [("nr:blades", 1), ("nr:scrap", 1)]),
    _craft("repair_kit", "tool", "nr:repair_kit", 1, [("nr:scrap", 3), ("nr:duct_tape", 1)]),
    _craft("uv_flashlight", "tool", "nr:uv_flashlight", 1,
           [("nr:battery", 2), ("nr:uv_shroom", 3), ("nr:scrap", 3), ("minecraft:glass_pane", 1)],
           station="bench", unlock={"level": 4}, ticks=60),
    _craft("grappling_hook", "tool", "nr:grappling_hook", 1,
           [("nr:scrap", 6), ("nr:volatile_trophy", 1), ("minecraft:string", 4), ("nr:battery", 1)],
           station="bench", unlock={"skill": "wall_run"}, ticks=80),
    _craft("paraglider", "tool", "nr:paraglider", 1,
           [("nr:rags", 10), ("nr:scrap", 6), ("nr:duct_tape", 3), ("minecraft:string", 4)],
           station="bench", unlock={"skill": "cat_landing"}, ticks=80),
    _craft("binoculars", "tool", "nr:binoculars", 1, [("minecraft:glass_pane", 2), ("nr:scrap", 2)],
           station="bench"),
    # 罠
    _craft("electric_trap", "trap", "nr:electric_trap", 1,
           [("nr:battery", 2), ("minecraft:copper_ingot", 2), ("nr:scrap", 3)], station="bench", unlock={"level": 4}),
    _craft("bear_trap", "trap", "nr:bear_trap", 1, [("nr:scrap", 4), ("nr:blades", 2)], station="bench"),
    _craft("tripwire_mine", "trap", "nr:tripwire_mine", 1,
           [("nr:gunpowder_pouch", 1), ("nr:scrap", 2), ("minecraft:tripwire_hook", 1)], unlock={"level": 6}),
    _craft("uv_trap", "trap", "nr:uv_trap", 1, [("nr:uv_shroom", 3), ("nr:battery", 2), ("nr:scrap", 3)],
           station="bench", unlock={"level": 7}),
    _craft("uv_lamp", "trap", "nr:uv_lamp", 1, [("nr:uv_shroom", 2), ("nr:battery", 1), ("nr:scrap", 2)],
           station="bench"),
    _craft("fuel_canister", "trap", "nr:fuel_canister", 1, [("nr:alcohol", 2), ("nr:scrap", 3)]),
    # 武器（作業台。レシピの無い強い武器はここだけ）
    _craft("scrap_katana", "weapon", "nr:w_scrap_katana", 1,
           [("nr:blades", 6), ("nr:scrap", 4), ("nr:rags", 2), ("nr:infected_trophy", 2), ("nr:money", 20)],
           station="bench", unlock={"level": 6}, ticks=100),
    _craft("scythe", "weapon", "nr:w_scythe", 1,
           [("nr:blades", 5), ("nr:scrap", 3), ("minecraft:stick", 2), ("nr:infected_trophy", 2)],
           station="bench", unlock={"level": 8}, ticks=100),
    _craft("sign_axe", "weapon", "nr:w_sign_axe", 1,
           [("nr:scrap", 8), ("nr:blades", 2), ("nr:duct_tape", 2), ("nr:infected_trophy", 1)],
           station="bench", unlock={"level": 7}, ticks=100),
    _craft("leaf_spring_greatsword", "weapon", "nr:w_leaf_spring_greatsword", 1,
           [("nr:scrap", 12), ("nr:blades", 4), ("minecraft:leather", 2), ("nr:volatile_trophy", 1),
            ("nr:money", 40)], station="bench", unlock={"level": 12}, ticks=140),
    _craft("piston_hammer", "weapon", "nr:w_piston_hammer", 1,
           [("nr:scrap", 14), ("minecraft:iron_ingot", 4), ("nr:volatile_trophy", 1), ("nr:money", 40)],
           station="bench", unlock={"level": 13}, ticks=140),
    _craft("buzzsaw_glaive", "weapon", "nr:w_buzzsaw_glaive", 1,
           [("nr:scrap", 10), ("nr:blades", 6), ("nr:battery", 4), ("nr:apex_trophy", 1), ("nr:money", 80)],
           station="bench", unlock={"level": 16}, ticks=200),
    _craft("crossbow", "weapon", "nr:w_crossbow", 1,
           [("nr:scrap", 6), ("minecraft:string", 3), ("minecraft:oak_planks", 2), ("nr:infected_trophy", 1)],
           station="bench", unlock={"level": 5}, ticks=100),
    # 銃（作業台、紙幣で部品を買い足す）
    _craft("pistol", "gun", "nr:w_pistol", 1, [("nr:scrap", 8), ("nr:money", 30), ("nr:duct_tape", 1)],
           station="bench", unlock={"level": 4}, ticks=120),
    _craft("revolver", "gun", "nr:w_revolver", 1, [("nr:scrap", 10), ("nr:money", 60), ("nr:infected_trophy", 1)],
           station="bench", unlock={"level": 9}, ticks=140),
    _craft("pump_shotgun", "gun", "nr:w_pump_shotgun", 1,
           [("nr:scrap", 12), ("nr:money", 80), ("nr:volatile_trophy", 1)], station="bench", unlock={"level": 10},
           ticks=160),
    _craft("double_barrel", "gun", "nr:w_double_barrel", 1,
           [("nr:scrap", 10), ("nr:money", 60), ("minecraft:oak_planks", 2)], station="bench", unlock={"level": 8},
           ticks=140),
    _craft("hunting_rifle", "gun", "nr:w_hunting_rifle", 1,
           [("nr:scrap", 14), ("nr:money", 120), ("nr:volatile_trophy", 2), ("minecraft:glass_pane", 1)],
           station="bench", unlock={"level": 14}, ticks=200),
    _craft("scrap_smg", "gun", "nr:w_scrap_smg", 1,
           [("nr:scrap", 16), ("nr:money", 100), ("nr:volatile_trophy", 1), ("nr:duct_tape", 3)],
           station="bench", unlock={"level": 15}, ticks=200),
]

# 自然に生える UV キノコ（暗い屋内・瓦礫の陰に置く。素手で壊すと nr:uv_shroom）
BLOCKS.append(_block(
    "uv_shroom_patch", "UV キノコの群生", "UV Shroom Patch", "nature",
    collision=False, selection=_box(-6, 0, -6, 12, 8, 12), sound="slime", map_color="#9a60e6",
    light_emission=5, destroy_time=0.1, loot="uv_shroom_patch", render="alpha_test", rotatable=False,
    desc_ja="暗がりに生える紫に光るキノコ。壊すと UV キノコが取れる。",
    desc_en="Purple glowing mushrooms in dark places. Break for UV shrooms.",
    model=[P("stem_a", (1, 6, 1), (-2, 3, -1), "plastic_white", "細い柄（半透明の白）"),
           P("cap_a", (4, 1.4, 4), (-2, 6.6, -1), "fungus_uv", "傘、裏のひだが発光"),
           P("stem_b", (1, 4, 1), (2.5, 2, 2), "plastic_white", "短い柄"),
           P("cap_b", (3, 1.2, 3), (2.5, 4.4, 2), "fungus_uv", "傘"),
           P("stem_c", (0.8, 3, 0.8), (0, 1.5, 3.5), "plastic_white", "小さい柄"),
           P("cap_c", (2, 1, 2), (0, 3.2, 3.5), "fungus_uv", "小さい傘"),
           P("glow", (8, 0.2, 8), (0, 0.1, 0), "emissive_uv", "根元の光る菌糸（アルファ）"),
           P("moss", (12, 0.4, 12), (0, 0.2, 0), "mutated", "湿った苔と菌糸")]))
LOOT_TABLES["uv_shroom_patch"] = [("nr:uv_shroom", 1, 3, 1.0)]
# 刃の破片・UV キノコ・火薬袋の出どころを足す
LOOT_TABLES["crate_wood"].append(("nr:blades", 1, 2, 0.35))
LOOT_TABLES["car_trunk"].append(("nr:blades", 1, 2, 0.25))
LOOT_TABLES["cargo"].append(("nr:blades", 1, 3, 0.3))
LOOT_TABLES["stash_common"].append(("nr:uv_shroom", 1, 2, 0.2))
for _s in STRUCTURES:
    if _s["key"] in ("apartment_tall", "collapsed_building", "warehouse", "church_tower"):
        _s["markers"].append(("block:uv_shroom_patch", 3, "暗がりの隅"))
CRAFTING.append(_craft("gunpowder_pouch", "ammo", "nr:gunpowder_pouch", 1,
                       [("minecraft:gunpowder", 2), ("nr:rags", 1)]))

# ゾンビから取れる（nr_spec_zombies の loot が出す）共有アイテム
ZOMBIE_SOURCED = ("nr:mutated_tissue", "nr:infected_trophy", "nr:volatile_trophy", "nr:apex_trophy")

# 初めてワールドに入ったときに渡す物（scriptevent nr:kit でも）
STARTER_KIT = [("nr:survivor_terminal", 1), ("nr:w_pipe_wrench", 1), ("nr:bandage", 3), ("nr:w_uv_flare", 2),
               ("nr:w_throwing_knives", 4)]


# ===========================================================================
#  引き出しの補助（生成器・データ JS 用）
# ===========================================================================
def all_items():
    """インベントリに入るアイテムのうち、武器・ブロック以外（共有 + その他）。"""
    return MATERIAL_ITEMS + ITEMS


def block_traps():
    return [t for t in TRAPS if t["block_or_entity"] == "block"]


def registry():
    """フル ID → (表の名前, エントリ)。アイテム・武器・ブロック・罠ブロック・小道具・飛び道具。"""
    reg = {}
    for name, rows in (("MATERIAL_ITEMS", MATERIAL_ITEMS), ("ITEMS", ITEMS), ("WEAPONS", WEAPONS),
                       ("BLOCKS", BLOCKS), ("TRAPS", block_traps()), ("PROPS", PROPS),
                       ("PROJECTILES", PROJECTILES)):
        for r in rows:
            if r["id"] in reg:
                raise ValueError(f"duplicate id {r['id']} ({reg[r['id']][0]} / {name})")
            reg[r["id"]] = (name, r)
    return reg


def inventory_ids():
    """手に持てる（レシピの材料・出来上がりになれる）nr: の ID。"""
    return ({r["id"] for r in all_items()} | {w["id"] for w in WEAPONS} | {b["id"] for b in BLOCKS}
            | {t["id"] for t in block_traps()})


def by_key(rows, key):
    for r in rows:
        if r["key"] == key:
            return r
    raise KeyError(key)


def weapon(key):
    return by_key(WEAPONS, key)


def required_sounds():
    """このカタログが参照する効果音のキー（gen_nr_sounds は全部作る）。"""
    out = set()
    for it in all_items():
        if it.get("use") and it["use"].get("sound"):
            out.add(it["use"]["sound"])
    for w in WEAPONS:
        out.update(SFX_SETS[w["sfx"]].values())
    for m in MODS:
        out.add(m["sound"])
    for t in TRAPS:
        out.update(t["sfx"].values())
    return sorted(out)


def required_particles():
    """このカタログが参照するパーティクルの ID（gen_nr_particles は全部作る）。"""
    out = set()
    for w in WEAPONS:
        out.update(w["fx"].values())
    for m in MODS:
        out.add(m["visual"]["particle"])
        out.add(m["visual"]["trail"])
    for t in TRAPS:
        out.update(t["fx"].values())
    for p in PROJECTILES:
        if p["trail"]:
            out.add(p["trail"])
    for b in BLOCKS:
        if b.get("ambient_particle"):
            out.add(b["ambient_particle"])
    return sorted(out)


def required_player_animations():
    """animation.nr.p.<名前> の一覧（gen_nr_player_anim は全部作る）。"""
    names = set(PLAYER_MOTIONS)
    for s in ANIM_SETS.values():
        for k, v in s.items():
            if k == "ja":
                continue
            if k == "swings":
                names.update(sw[0] for sw in v)
            elif k == "heavy":
                names.add(v[0])
            else:
                names.add(v)
    for it in all_items():
        if it.get("use") and it["use"].get("anim"):
            names.add(it["use"]["anim"])
    return sorted("animation.nr.p." + n for n in names)


def lang_entries():
    """名前の言語キー（DESIGN.md §2 の形）。{"ja_JP": {...}, "en_US": {...}}。"""
    ja, en = {}, {}
    for it in all_items() + WEAPONS:
        ja["item." + it["id"]] = it["ja"]
        en["item." + it["id"]] = it["en"]
    for b in BLOCKS + block_traps():
        ja[f"tile.{b['id']}.name"] = b["ja"]
        en[f"tile.{b['id']}.name"] = b["en"]
    for p in PROPS + PROJECTILES:
        ja[f"entity.{p['id']}.name"] = p["ja"]
        en[f"entity.{p['id']}.name"] = p["en"]
    return {"ja_JP": ja, "en_US": en}


def vanilla_refs():
    """このカタログが使うバニラの ID（validate_nr が公式の一覧と照らせるように）。"""
    items, blocks = set(), set()

    def from_recipe(r):
        if not r:
            return
        refs = r["keys"].values() if r["type"] == "shaped" else [i for i, _ in r["ingredients"]]
        items.update(x for x in refs if x.startswith("minecraft:"))
    for x in all_items() + WEAPONS + BLOCKS + TRAPS:
        from_recipe(x.get("recipe"))
    for c in CRAFTING:
        items.update(i for i, _ in c["inputs"] if i.startswith("minecraft:"))
    for rows in LOOT_TABLES.values():
        items.update(r[0] for r in rows if r[0].startswith("minecraft:"))
    for m in MODS:
        for t in m["tiers"]:
            items.update(i for i, _ in t["cost"] if i.startswith("minecraft:"))
    for st in STRUCTURES:
        blocks.update(v for v in st["palette"].values() if v.startswith("minecraft:"))
    return {"items": sorted(items), "blocks": sorted(blocks)}


# nr_spec.py の `from nr_spec_catalog import *` で出す名前（P・shaped などの補助は出さない）
__all__ = [
    "SURFACES", "HEAD_STATES", "LIMB_STATES", "TORSO_STATES", "GORE_PARTS", "DTYPES", "EFFECT_DTYPES", "WEIGHTS",
    "DTYPE_OUTCOMES",
    "RARITY", "ANIM_SETS", "PLAYER_MOTIONS", "SFX_SETS", "SHARED_ITEM_IDS", "MATERIAL_ITEMS", "ITEMS",
    "ITEM_KINDS", "WEAPON_CLASSES", "WEAPON_KINDS", "WEAPONS", "PROJECTILES", "MODS", "TRAPS", "BLOCK_SOUNDS",
    "BLOCKS", "TRAP_BLOCKS", "MULTIBLOCKS", "PROP_INTERACTIONS", "PROPS", "LOOT_TABLES", "MARKER_KINDS",
    "STRUCTURES", "CITY", "SKILLS", "PROGRESSION", "xp_to_next", "PARKOUR_TUNING", "COMBAT_TUNING", "GORE_TUNING",
    "GORE_COMBOS", "SETTINGS_SCHEMA", "SETTINGS_DEFAULTS", "DIFFICULTY", "CRAFT_CATEGORIES", "CRAFTING",
    "ZOMBIE_SOURCED", "STARTER_KIT", "all_items", "block_traps", "registry", "inventory_ids", "by_key", "weapon",
    "required_sounds", "required_particles", "required_player_animations", "lang_entries", "vanilla_refs",
]


# ===========================================================================
#  自己検査
# ===========================================================================
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")
_SOUND_RE = re.compile(r"^nr\.[a-z0-9_]+\.[a-z0-9_]+$")
_PARTICLE_RE = re.compile(r"^nr:[a-z0-9_]+$")


def _vanilla_lists():
    """build_preview/nr_research/catalog/ に落とした公式メタデータがあれば読む（無ければ None）。"""
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    folder = os.path.join(os.path.dirname(os.path.dirname(here)), "build_preview", "nr_research", "catalog")
    out = {}
    for name in ("vanilla_items", "vanilla_blocks"):
        path = os.path.join(folder, name + ".txt")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                out[name] = {ln.strip() for ln in fh if ln.strip()}
    path = os.path.join(folder, "blocks.json")
    if os.path.isfile(path):
        import json
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        out["block_sounds"] = {v.get("sound") for v in doc.values() if isinstance(v, dict) and v.get("sound")}
    return out


def _bbox(parts):
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for p in parts:
        for c in [p["at"]] + p.get("rep", []):
            for i in range(3):
                lo[i] = min(lo[i], c[i] - p["size"][i] / 2)
                hi[i] = max(hi[i], c[i] + p["size"][i] / 2)
    return lo, hi


def self_check():
    err = []
    E = err.append
    van = _vanilla_lists()
    try:
        registry()             # ID の重複（表をまたいでも）はここで分かる
    except ValueError as ex:
        E(str(ex))
    inv = inventory_ids()

    def check_item_id(ref, where, kind="item"):
        if not isinstance(ref, str):
            E(f"{where}: bad id {ref!r}")
        elif ref.startswith("nr:"):
            if ref not in inv:
                E(f"{where}: unknown nr item {ref}")
        elif ref.startswith("minecraft:"):
            lst = van.get("vanilla_items" if kind == "item" else "vanilla_blocks")
            if lst is not None and ref not in lst:
                E(f"{where}: {ref} is not a vanilla {kind} (bedrock-samples metadata)")
        else:
            E(f"{where}: id must start with nr: or minecraft: ({ref})")

    def check_parts(parts, where):
        if not parts:
            E(f"{where}: model is empty")
        names = set()
        for p in parts:
            if p["mat"] not in SURFACES:
                E(f"{where}.{p['name']}: unknown surface {p['mat']}")
            if p["name"] in names:
                E(f"{where}: duplicate part name {p['name']}")
            names.add(p["name"])
            if any(v <= 0 for v in p["size"]):
                E(f"{where}.{p['name']}: non-positive size {p['size']}")

    def check_recipe(r, out_id, where):
        if r is None:
            return
        if not 1 <= r["count"] <= 64:
            E(f"{where}: count {r['count']}")
        if r["type"] == "shaped":
            pat = r["pattern"]
            if not 1 <= len(pat) <= 3 or len({len(row) for row in pat}) != 1 or len(pat[0]) > 3:
                E(f"{where}: pattern must be 1-3 rows of equal width <= 3: {pat}")
            used = {ch for row in pat for ch in row if ch != " "}
            if used != set(r["keys"]):
                E(f"{where}: pattern letters {sorted(used)} != keys {sorted(r['keys'])}")
            for ch, ref in r["keys"].items():
                check_item_id(ref, f"{where}.key[{ch}]")
        elif r["type"] == "shapeless":
            if sum(n for _, n in r["ingredients"]) > 9:
                E(f"{where}: shapeless uses more than 9 items")
            for ref, _ in r["ingredients"]:
                check_item_id(ref, f"{where}.ingredient")
        else:
            E(f"{where}: unknown recipe type {r['type']}")
        if out_id not in inv:
            E(f"{where}: recipe output {out_id} is not an inventory id")

    # --- キーの形と重複 ---------------------------------------------------------------
    for name, rows in (("MATERIAL_ITEMS", MATERIAL_ITEMS), ("ITEMS", ITEMS), ("WEAPONS", WEAPONS),
                       ("PROJECTILES", PROJECTILES), ("MODS", MODS), ("TRAPS", TRAPS), ("BLOCKS", BLOCKS),
                       ("PROPS", PROPS), ("STRUCTURES", STRUCTURES), ("SKILLS", SKILLS), ("CRAFTING", CRAFTING),
                       ("SETTINGS_SCHEMA", SETTINGS_SCHEMA)):
        seen = set()
        for r in rows:
            k = r["key"]
            if not _KEY_RE.match(k):
                E(f"{name}: key {k!r} is not snake_case ASCII")
            if k in seen:
                E(f"{name}: duplicate key {k}")
            seen.add(k)
    for name, d in (("SURFACES", SURFACES), ("LOOT_TABLES", LOOT_TABLES), ("MARKER_KINDS", MARKER_KINDS),
                    ("PLAYER_MOTIONS", PLAYER_MOTIONS), ("ANIM_SETS", ANIM_SETS), ("GORE_COMBOS", GORE_COMBOS),
                    ("PROP_INTERACTIONS", PROP_INTERACTIONS), ("MULTIBLOCKS", MULTIBLOCKS)):
        for k in d:
            if not _KEY_RE.match(k):
                E(f"{name}: key {k!r} is not snake_case ASCII")
    # 小道具の罠と小道具の ID がぶつからない／ブロックと罠ブロックの ID がぶつからない（registry が検査）

    # --- 共有アイテム -----------------------------------------------------------------
    if tuple(m["id"] for m in MATERIAL_ITEMS) != SHARED_ITEM_IDS:
        E("MATERIAL_ITEMS ids must equal SHARED_ITEM_IDS (same order)")
    for it in all_items():
        w = f"item {it['key']}"
        if it["kind"] not in ITEM_KINDS:
            E(f"{w}: kind {it['kind']}")
        if not 1 <= it["stack"] <= 64:
            E(f"{w}: stack {it['stack']}")
        if it["rarity"] not in RARITY:
            E(f"{w}: rarity {it['rarity']}")
        if not (it["ja"] and it["en"] and it["icon"] and it["desc_ja"] and it["desc_en"]):
            E(f"{w}: missing name/icon/description")
        if it["kind"] in ("consumable", "tool") and not it["use"]:
            E(f"{w}: {it['kind']} needs a use")
        if it.get("use") and it["use"].get("sound") and not _SOUND_RE.match(it["use"]["sound"]):
            E(f"{w}: bad sound key {it['use']['sound']}")
        check_recipe(it["recipe"], it["id"], w)
        for mk in ("model", "wing_model"):
            if it.get(mk):
                check_parts(it[mk], f"{w}.{mk}")

    # --- 飛び道具・改造 -----------------------------------------------------------------
    proj_ids = {p["id"] for p in PROJECTILES}
    for p in PROJECTILES:
        if p["pickup"]:
            check_item_id(p["pickup"], f"projectile {p['key']}.pickup")
        if p["on_hit"] not in ("stick", "shatter", "bounce"):
            E(f"projectile {p['key']}: on_hit {p['on_hit']}")
        check_parts(p["model"], f"projectile {p['key']}")
    mod_keys = {m["key"] for m in MODS}
    for m in MODS:
        if m["dtype"] not in EFFECT_DTYPES:
            E(f"mod {m['key']}: dtype {m['dtype']}")
        if [t["level"] for t in m["tiers"]] != [1, 2, 3]:
            E(f"mod {m['key']}: tiers must be 1,2,3")
        for t in m["tiers"]:
            for ref, n in t["cost"]:
                check_item_id(ref, f"mod {m['key']}.tier{t['level']}.cost")
        for k in ("particle", "trail"):
            if not _PARTICLE_RE.match(m["visual"][k]):
                E(f"mod {m['key']}: bad particle {m['visual'][k]}")
        if not _SOUND_RE.match(m["sound"]):
            E(f"mod {m['key']}: bad sound {m['sound']}")

    # --- 武器 ------------------------------------------------------------------------
    crafted = {c["output"] for c in CRAFTING}
    looted = {e[0] for rows in LOOT_TABLES.values() for e in rows}
    starter = {i for i, _ in STARTER_KIT}
    for w in WEAPONS:
        n = f"weapon {w['key']}"
        if w["cls"] not in WEAPON_CLASSES:
            E(f"{n}: cls {w['cls']}")
            continue
        if w["kind"] not in WEAPON_KINDS:
            E(f"{n}: kind {w['kind']}")
        if w["dtype"] not in EFFECT_DTYPES or (w["alt_dtype"] is not None and w["alt_dtype"] not in DTYPES):
            E(f"{n}: dtype {w['dtype']} / {w['alt_dtype']}")
        if w["weight"] not in WEIGHTS:
            E(f"{n}: weight {w['weight']}")
        if w["hands"] not in (1, 2):
            E(f"{n}: hands {w['hands']}")
        if w["anim_set"] not in ANIM_SETS:
            E(f"{n}: anim_set {w['anim_set']}")
        if w["rarity"] not in RARITY:
            E(f"{n}: rarity {w['rarity']}")
        if w["sfx"] not in SFX_SETS:
            E(f"{n}: sfx {w['sfx']}")
        if not 0.0 <= w["gore_power"] <= 1.0:
            E(f"{n}: gore_power {w['gore_power']}")
        for f in ("damage", "attack_speed", "reach", "crit_mult", "range"):
            if not w[f] >= 0:
                E(f"{n}: {f} {w[f]}")
        if w["kind"] != "throwable" and w["durability"] <= 0:
            E(f"{n}: durability must be > 0")
        if w["kind"] == "melee" and w["stamina_cost"] <= 0:
            E(f"{n}: melee stamina_cost must be > 0")
        if not (w["ja"] and w["en"] and w["desc_ja"] and w["desc_en"]):
            E(f"{n}: missing names/descriptions")
        # 部位の結果
        allowed = {}
        for dt in (w["dtype"], w["alt_dtype"]):
            if dt:
                for part, outs in DTYPE_OUTCOMES[dt].items():
                    allowed.setdefault(part, set()).update(outs)
        for part, out in w["sever_bias"].items():
            if part not in GORE_PARTS:
                E(f"{n}: sever_bias part {part}")
            elif out not in GORE_PARTS[part] or out == "intact":
                E(f"{n}: sever_bias {part}={out} is not a gore state")
            elif out not in allowed.get(part, ()):
                E(f"{n}: sever_bias {part}={out} impossible for dtype {w['dtype']}/{w['alt_dtype']}")
            elif (w["dtype"] == "pierce" and w["alt_dtype"] is None and out.startswith("cut")
                  and w["gore_power"] < 0.85):
                E(f"{n}: pierce cuts need gore_power >= 0.85")
        if w["dtype"] in ("slash", "blunt", "pierce", "blast") and w["gore_power"] > 0 and not w["sever_bias"]:
            E(f"{n}: needs sever_bias")
        # 弾・飛び道具
        if w["kind"] in ("gun", "bow", "crossbow"):
            if not w["ammo"]:
                E(f"{n}: ranged weapon needs ammo")
            elif w["ammo"] not in SHARED_ITEM_IDS:
                E(f"{n}: ammo {w['ammo']} must be a shared item")
            if w["mag"] <= 0:
                E(f"{n}: mag must be > 0")
        elif w["ammo"] is not None:
            E(f"{n}: only guns/bows use ammo")
        if w["kind"] == "gun" and w["projectile"] is not None:
            E(f"{n}: guns are hitscan (projectile=None)")
        if w["kind"] in ("bow", "crossbow", "throwable") and w["projectile"] not in proj_ids:
            E(f"{n}: projectile {w['projectile']} not in PROJECTILES")
        if w["kind"] == "melee" and w["projectile"] is not None:
            E(f"{n}: melee weapons have no projectile")
        if w["kind"] == "throwable" and w["stack"] < 2:
            E(f"{n}: throwables stack")
        if w["kind"] != "throwable" and w["stack"] != 1:
            E(f"{n}: weapons stack 1")
        if w["pellets"] < 1:
            E(f"{n}: pellets")
        # 改造
        for mk in w["mods_allowed"]:
            if mk not in mod_keys:
                E(f"{n}: unknown mod {mk}")
                continue
            m = by_key(MODS, mk)
            if w["kind"] not in m["applies_to"]:
                E(f"{n}: mod {mk} does not apply to {w['kind']}")
            if m.get("only_dtypes") and w["dtype"] not in m["only_dtypes"]:
                E(f"{n}: mod {mk} only for {m['only_dtypes']}")
        if RARITY[w["rarity"]]["mod_slots"] < 1 and w["mods_allowed"]:
            E(f"{n}: no mod slots")
        for k, v in w["fx"].items():
            if not _PARTICLE_RE.match(v):
                E(f"{n}: fx {k}={v}")
        im = w["special"].get("innate_mod")
        if im and im not in mod_keys:
            E(f"{n}: innate_mod {im}")
        check_recipe(w["recipe"], w["id"], n)
        check_parts(w["model"], n)
        if sum(1 + len(p.get("rep", [])) for p in w["model"]) > 180:
            E(f"{n}: more than 180 cubes")
        for c in w["palette"]:
            if not _HEX_RE.match(c):
                E(f"{n}: palette {c}")
        if not (w["recipe"] or w["id"] in crafted or w["id"] in looted or w["id"] in starter):
            E(f"{n}: cannot be obtained (no recipe, terminal craft or loot)")
    melee = [w for w in WEAPONS if w["kind"] == "melee"]
    if len(WEAPONS) < 34 or len(melee) < 22:
        E(f"need >= 34 weapons and >= 22 melee (have {len(WEAPONS)} / {len(melee)})")

    # --- 罠 --------------------------------------------------------------------------
    prop_keys = {p["key"] for p in PROPS}
    for t in TRAPS:
        n = f"trap {t['key']}"
        kind = t["block_or_entity"]
        if kind == "block":
            if t["key"] not in TRAP_BLOCKS:
                E(f"{n}: block trap needs TRAP_BLOCKS entry")
            check_parts(t["model"], n)
        elif kind == "prop":
            if t["prop"] not in prop_keys:
                E(f"{n}: prop {t['prop']} not in PROPS")
            elif by_key(PROPS, t["prop"])["trap"] != t["key"]:
                E(f"{n}: PROPS.{t['prop']}.trap must point back")
        elif kind == "prop_interaction":
            for pk in t["props"]:
                if pk not in prop_keys:
                    E(f"{n}: prop {pk} not in PROPS")
                elif t["key"] not in by_key(PROPS, pk)["interactions"]:
                    E(f"{n}: PROPS.{pk} lacks interaction {t['key']}")
        else:
            E(f"{n}: block_or_entity {kind}")
        for part, (out, ch) in t["gore"].items():
            if part not in GORE_PARTS or out not in GORE_PARTS[part] or not 0 < ch <= 1:
                E(f"{n}: gore {part}={out} {ch}")
        if t["effect"].get("dtype") and t["effect"]["dtype"] not in EFFECT_DTYPES:
            E(f"{n}: effect dtype")
        if t["rearm"]:
            for ref, _ in t["rearm"].get("refill", []) + t["rearm"].get("repair", []):
                check_item_id(ref, f"{n}.rearm")
        if t["recipe"]:
            check_recipe(t["recipe"], t["id"], n)
        for v in t["sfx"].values():
            if not _SOUND_RE.match(v):
                E(f"{n}: sfx {v}")
        for v in t["fx"].values():
            if not _PARTICLE_RE.match(v):
                E(f"{n}: fx {v}")
    for k in TRAP_BLOCKS:
        if k not in {t["key"] for t in block_traps()}:
            E(f"TRAP_BLOCKS.{k}: not a block trap")

    # --- ブロック（罠ブロックも） ------------------------------------------------------
    sounds_ok = set(BLOCK_SOUNDS)
    if "block_sounds" in van:
        for s in BLOCK_SOUNDS:
            if s not in van["block_sounds"]:
                E(f"BLOCK_SOUNDS: {s} is not used by vanilla blocks.json")

    def check_box(box, where, max_y=16):
        if box is False:
            return
        o, s = box["origin"], box["size"]
        if any(v <= 0 for v in s):
            E(f"{where}: size {s}")
        if not (-8 <= o[0] <= 8 and 0 <= o[1] <= 16 and -8 <= o[2] <= 8):
            E(f"{where}: origin {o} out of [-8,0,-8]..[8,16,8]")
        if not (o[0] + s[0] <= 8 and o[1] + s[1] <= max_y and o[2] + s[2] <= 8):
            E(f"{where}: origin+size {[o[i] + s[i] for i in range(3)]} exceeds [8,{max_y},8]")

    block_like = [(b["key"], b, b["model"]) for b in BLOCKS] + \
                 [(t["key"], dict(TRAP_BLOCKS.get(t["key"], {}), light_emission=t["light_emission"]), t["model"])
                  for t in block_traps()]
    for key, b, model in block_like:
        n = f"block {key}"
        check_parts(model, n)
        lo, hi = _bbox(model)
        size = [hi[i] - lo[i] for i in range(3)]
        if any(v > 30.0001 for v in size):
            E(f"{n}: model {['%.1f' % v for v in size]} exceeds 30x30x30 px")
        if any(abs(v) > 30 for v in lo + hi):
            E(f"{n}: model reaches beyond 30 px from origin")
        if not (lo[0] < 8 and hi[0] > -8 and lo[1] < 16 and hi[1] > 0 and lo[2] < 8 and hi[2] > -8):
            E(f"{n}: model must overlap its own block cell")
        if "collision" in b:
            check_box(b["collision"], f"{n}.collision")
        if b.get("selection"):
            check_box(b["selection"], f"{n}.selection")
        if not 0 <= b.get("light_emission", 0) <= 15:
            E(f"{n}: light_emission")
        if b.get("sound") not in sounds_ok:
            E(f"{n}: sound {b.get('sound')} not in BLOCK_SOUNDS")
        if not _HEX_RE.match(b.get("map_color", "")):
            E(f"{n}: map_color {b.get('map_color')}")
        if b.get("render") not in ("opaque", "alpha_test", "blend"):
            E(f"{n}: render {b.get('render')}")
        if b.get("loot") and b["loot"] not in LOOT_TABLES:
            E(f"{n}: loot {b['loot']}")
        if b.get("loot_locked") and b["loot_locked"] not in LOOT_TABLES:
            E(f"{n}: loot_locked {b['loot_locked']}")
        for tag in b.get("parkour", []):
            if tag not in ("climb", "vault", "landing", "zipline", "updraft"):
                E(f"{n}: parkour tag {tag}")
        if b.get("recipe"):
            check_recipe(b["recipe"], nid(key), n)
        if b.get("ambient_particle") and not _PARTICLE_RE.match(b["ambient_particle"]):
            E(f"{n}: ambient_particle")
    block_keys = {b["key"] for b in BLOCKS} | {t["key"] for t in block_traps()}
    for mb, rows in MULTIBLOCKS.items():
        for bk, _ in rows:
            if bk not in block_keys:
                E(f"MULTIBLOCKS.{mb}: unknown block {bk}")
    for b in BLOCKS:
        if b["multiblock"] and b["multiblock"][0] not in MULTIBLOCKS:
            E(f"block {b['key']}: multiblock {b['multiblock']}")

    # --- 小道具 ----------------------------------------------------------------------
    for p in PROPS:
        n = f"prop {p['key']}"
        check_parts(p["model"], n)
        for it in p["interactions"]:
            if it not in PROP_INTERACTIONS and it not in {t["key"] for t in TRAPS}:
                E(f"{n}: interaction {it}")
        if p["loot"] and p["loot"] not in LOOT_TABLES:
            E(f"{n}: loot {p['loot']}")
        if any(i.startswith("loot") for i in p["interactions"]) and not p["loot"]:
            E(f"{n}: loot interaction without loot table")
        if p["cube_budget"] > 700 or max(p["texture_size"]) > 1024:
            E(f"{n}: over the prop limits (700 cubes / 1024 px)")
        if sum(1 + len(q.get("rep", [])) for q in p["model"]) > p["cube_budget"]:
            E(f"{n}: described parts exceed cube_budget")
        w, h, length = p["size_blocks"]
        for r in p["barrier"]:
            x0, z0, x1, z1, bh = r
            if x0 > x1 or z0 > z1 or bh < 1 or bh > int(h) + 1:
                E(f"{n}: barrier {r}")
            if (x1 - x0 + 1) > w + 1.01 or (z1 - z0 + 1) > length + 1.01:
                E(f"{n}: barrier {r} larger than the prop")
        if p["trap"] and p["trap"] not in {t["key"] for t in TRAPS}:
            E(f"{n}: trap {p['trap']}")
        if "climb_roof" in p["interactions"] and not p["barrier"]:
            E(f"{n}: climb_roof needs a barrier")
    if not 12 <= len(PROPS) <= 16:
        E(f"PROPS: want 12-16, have {len(PROPS)}")

    # --- ルート表 ---------------------------------------------------------------------
    for name, rows in LOOT_TABLES.items():
        for ref, lo_, hi_, ch in rows:
            check_item_id(ref, f"loot {name}")
            if not (0 <= lo_ <= hi_ and 0 < ch <= 1):
                E(f"loot {name}: bad row {(ref, lo_, hi_, ch)}")

    # --- 建物 ------------------------------------------------------------------------
    if len(STRUCTURES) != 14:
        E(f"STRUCTURES: want 14, have {len(STRUCTURES)}")
    for s in STRUCTURES:
        n = f"structure {s['key']}"
        fx, fz = s["footprint"]
        if fx > 48 or fz > 48 or s["height"] > 64:
            E(f"{n}: footprint {s['footprint']} / height {s['height']} over 48x48x64")
        if s["floors"] * s["floor_h"] > s["height"]:
            E(f"{n}: floors * floor_h > height")
        if s["placement"] not in ("ground", "roof", "road"):
            E(f"{n}: placement")
        for role, ref in s["palette"].items():
            if ref.startswith("nr:"):
                if ref[3:] not in block_keys:
                    E(f"{n}.palette.{role}: unknown nr block {ref}")
            else:
                check_item_id(ref, f"{n}.palette.{role}", kind="block")
        for mk, cnt, _where in s["markers"]:
            if mk.startswith("prop:"):
                if mk[5:] not in prop_keys:
                    E(f"{n}: marker {mk}")
            elif mk.startswith("block:"):
                if mk[6:] not in block_keys:
                    E(f"{n}: marker {mk}")
            elif mk not in MARKER_KINDS:
                E(f"{n}: marker {mk}")
            if cnt < 1:
                E(f"{n}: marker count {cnt}")
        door = s["connects"]["door"]
        if door is not None and not (0 <= door[0] <= fx and 0 <= door[1] <= fz):
            E(f"{n}: door {door} outside footprint")

    # --- スキル ----------------------------------------------------------------------
    skill_keys = {k["key"] for k in SKILLS}
    for k in SKILLS:
        if k["tree"] not in ("parkour", "combat"):
            E(f"skill {k['key']}: tree")
        if k["cost"] < 1:
            E(f"skill {k['key']}: cost")
        for r in k["requires"]:
            if r not in skill_keys:
                E(f"skill {k['key']}: requires {r}")
    state = {}

    def visit(key, stack=()):
        if state.get(key) == 2:
            return
        if key in stack:
            E(f"skill cycle: {' -> '.join(stack + (key,))}")
            return
        for r in by_key(SKILLS, key)["requires"]:
            if r in skill_keys:
                visit(r, stack + (key,))
        state[key] = 2
    for k in skill_keys:
        visit(k)
    for tree in ("parkour", "combat"):
        if sum(1 for k in SKILLS if k["tree"] == tree) < 10:
            E(f"skills: tree {tree} needs >= 10")

    # --- 端末のクラフト ----------------------------------------------------------------
    for c in CRAFTING:
        n = f"craft {c['key']}"
        check_item_id(c["output"], f"{n}.output")
        for ref, k in c["inputs"]:
            check_item_id(ref, f"{n}.input")
            if k < 1:
                E(f"{n}: input count")
        if c["station"] not in ("terminal", "bench"):
            E(f"{n}: station")
        if c["category"] not in CRAFT_CATEGORIES:
            E(f"{n}: category")
        u = c["unlock"]
        if u is not None:
            if "skill" in u and u["skill"] not in skill_keys:
                E(f"{n}: unlock skill {u['skill']}")
            if "level" in u and not 1 <= u["level"] <= PROGRESSION["max_level"]:
                E(f"{n}: unlock level")
        if not 1 <= c["count"] <= 64:
            E(f"{n}: count")

    # --- 設定 ------------------------------------------------------------------------
    need = ("gore_level", "gib_lifetime_s", "corpse_lifetime_s", "max_gibs", "max_corpses", "blood_decal_mult",
            "screen_blood", "particle_budget", "natural_spawn", "horde_density", "chase_enabled",
            "immunity_enabled", "friendly_fire", "difficulty", "difficulty_scaling")
    for k in need:
        if k not in SETTINGS_DEFAULTS:
            E(f"SETTINGS_DEFAULTS: missing {k}")
    if SETTINGS_DEFAULTS.get("gore_level") != 100:
        E("gore_level default must be 100")
    for s in SETTINGS_SCHEMA:
        if s["type"] == "slider" and not s["min"] <= s["default"] <= s["max"]:
            E(f"setting {s['key']}: default out of range")
        if s["type"] == "dropdown" and s["default"] not in s["options"]:
            E(f"setting {s['key']}: default not an option")
    if SETTINGS_DEFAULTS["difficulty"] not in DIFFICULTY:
        E("difficulty default")

    # --- 作業台レシピの衝突（同じ並びで別の物ができない） -----------------------------
    seen_r = {}
    for rid, r in ([(x["id"], x["recipe"]) for x in all_items() + WEAPONS + BLOCKS + block_traps()]):
        if not r:
            continue
        if r["type"] == "shaped":
            sig = ("shaped", tuple(tuple(r["keys"].get(ch, "") for ch in row) for row in r["pattern"]))
        else:
            sig = ("shapeless", tuple(sorted((i, n) for i, n in r["ingredients"])))
        if sig in seen_r and seen_r[sig] != rid:
            E(f"recipe collision: {seen_r[sig]} and {rid} use the same grid")
        seen_r[sig] = rid

    # --- 何かから手に入るか（ゾンビのルートで出るものは除く） ---------------------------
    sources = crafted | looted | starter
    for it in all_items():
        if it["id"] in ZOMBIE_SOURCED:
            continue
        if not (it["recipe"] or it["id"] in sources):
            E(f"item {it['key']}: cannot be obtained")
    for t in block_traps():
        if not (t["recipe"] or t["id"] in crafted) and t["key"] != "gas_pipe":
            E(f"trap {t['key']}: cannot be crafted")

    # --- 参照する音・パーティクル・アニメの名前の形 ------------------------------------
    for s in required_sounds():
        if not _SOUND_RE.match(s):
            E(f"sound key {s}")
    for p in required_particles():
        if not _PARTICLE_RE.match(p):
            E(f"particle id {p}")
    for it in all_items():
        a = it.get("use", {}) and it["use"].get("anim")
        if a and a not in PLAYER_MOTIONS:
            E(f"item {it['key']}: anim {a} not in PLAYER_MOTIONS")
    return err


def summary():
    melee = sum(1 for w in WEAPONS if w["kind"] == "melee")
    return (f"materials {len(MATERIAL_ITEMS)}, items {len(ITEMS)}, weapons {len(WEAPONS)} (melee {melee}), "
            f"projectiles {len(PROJECTILES)}, mods {len(MODS)}, traps {len(TRAPS)}, blocks {len(BLOCKS)} "
            f"(+{len(block_traps())} trap blocks), props {len(PROPS)}, structures {len(STRUCTURES)}, "
            f"skills {len(SKILLS)}, terminal recipes {len(CRAFTING)}, loot tables {len(LOOT_TABLES)}, "
            f"sounds {len(required_sounds())}, particles {len(required_particles())}, "
            f"player anims {len(required_player_animations())}")


if __name__ == "__main__":
    import sys
    problems = self_check()
    van = _vanilla_lists()
    print("nr_spec_catalog:", summary())
    if not van:
        print("  (vanilla id lists not found under build_preview/nr_research/catalog — minecraft: ids "
              "checked by prefix only)")
    for p in problems:
        print("  NG", p)
    if problems:
        print(f"{len(problems)} problem(s)")
        sys.exit(1)
    print("OK")
