# -*- coding: utf-8 -*-
"""アストロ・ナノギア — ゲームデータの単一ソース。

惑星（変身形態）の名前・配色・技・コスト・再使用時間・パッシブ・機動・防御・レシピをここに書き、
* Python の生成スクリプト（モデル・テクスチャ・パーティクル・言語・アイテム・レシピ）
* スクリプト（packs/astro_BP/scripts/data.js に書き出す）
の両方が参照する。値を変えるときはここだけ直してビルドし直す。

色は 0..255 の RGB。スクリプトへは 0..1 に直して渡す。
時間は tick（20 tick = 1 秒）。
"""
from __future__ import annotations

NS = "astro"
ADDON_JA = "アストロ・ナノギア"
ADDON_EN = "Astro Nanogear"
VERSION = (1, 0, 0)

# ---------------------------------------------------------------------------
#  全形態共通の数値
# ---------------------------------------------------------------------------
COMMON = {
    "energy_max": 100,          # 星力（Lv ごとに +energy_per_level）
    "energy_per_level": 10,
    "energy_to_transform": 30,  # 変身に必要な星力
    "energy_drain": 0.35,       # 変身中に毎秒減る量
    "energy_regen": 3.0,        # 変身していない時に毎秒戻る量
    "energy_on_kill": 5,
    "hover_cost": 4.0,          # ホバー中に毎秒減る量
    "overheat_ticks": 400,      # 星力切れで強制解除された後、再変身できるまで
    "nova_max": 100,            # 超新星ゲージ（必殺技）
    "nova_on_hit": 3,
    "nova_on_skill_hit": 2,
    "nova_per_damage_taken": 0.8,
    "nova_on_just_dodge": 15,
    "revert_hold_ticks": 40,    # スニークしたまま静止して変身解除するまで
    "barrier_ticks": 14,        # ナノ・バリア（スニーク＋右クリック、ゲージ未満）
    "barrier_cd": 60,
    "sync_xp": [0, 200, 600, 1400, 3000],   # 同調率 Lv1..5 に必要な累計 XP
    "sync_damage_per_level": 0.06,          # Lv ごとの与ダメージ増加
    "sync_cd_per_level": 0.05,              # Lv ごとの再使用短縮
    "xp_on_hit": 2,
    "xp_on_kill": 12,
    "combo_reset_ticks": 26,
}

# 変身の時間割（tick）。スクリプトの演出と、スーツのアタッチャブルの組み上がり
# アニメーション（scripts → 頭スロットにスーツを置いた瞬間が 0 秒）の両方がこれに合わせる。
TRANSFORM = {
    "freeze": 64,          # 動けない時間（全体）
    "core_rise": 0,        # コアが手から浮かぶ
    "swarm_start": 8,      # ナノマシンが噴き出す
    "suit_equip": 14,      # 頭スロットにスーツを置く = 組み上がりアニメ 0 秒
    "assemble_len": 1.8,   # 組み上がりアニメの長さ（秒）
    "weapon_form": 40,     # 手のコアがナノウェポンに変わる
    "visor_flash": 46,     # バイザー点灯
    "planet_burst": 50,    # 惑星の力が弾ける（形態ごとの演出）
    "camera_clear": 60,    # 演出カメラを戻す
}
# 組み上がりの順番（アタッチャブルの部位ボーン → 開始秒）。部位ボーンの命名は DESIGN.md 参照
ASSEMBLE_ORDER = {
    "boots": 0.00, "legs": 0.20, "waist": 0.40, "torso": 0.55, "back": 0.75,
    "arms": 0.85, "shoulders": 1.00, "helmet": 1.20, "visor": 1.50, "extra": 1.30,
}

MOVE_KINDS = ("skill", "dash", "air", "ult")
MOVE_LABEL_JA = {"skill": "惑星技", "dash": "機動技", "air": "空中技", "ult": "必殺"}
MOVE_INPUT_JA = {
    "skill": "右クリック",
    "dash": "ダッシュ中に右クリック",
    "air": "空中で右クリック",
    "ult": "スニーク＋右クリック（超新星ゲージ 100%）",
}

# ---------------------------------------------------------------------------
#  惑星（変身形態）
#
#  tc       テキスト色コード（HUD・名前）
#  colors   plate=主装甲 / plate2=副装甲 / frame=下地（インナー・関節） /
#           glow=発光（パーティクル・HUD の基本色） / light=発光の芯 / deep=発光の影 /
#           accent=差し色
#  weapon   kind はアタッチャブルの持ち方の種類（DESIGN.md「ナノウェポン」）
#  mobility air_jumps=空中ジャンプ回数 / air_dash=空中ダッシュ回数 /
#           hover=ホバーの上昇力（0..1） / sprint=疾走時の speed 効果 Lv（-1 で無し）
#  passive  effects=変身中に掛け続ける効果 [id, Lv] / special=スクリプトの固有パッシブ
#  defense  スーツ（頭スロット）の防御点
#  damage   ナノウェポンの攻撃力
# ---------------------------------------------------------------------------
PLANETS = {
    "mercury": {
        "order": 1, "symbol": "☿",
        "ja": "水星", "en": "MERCURY",
        "form_ja": "クイックシルバー", "form_en": "QUICKSILVER",
        "core_ja": "水星核 マーキュリー・コア", "core_en": "Mercury Core",
        "suit_ja": "水銀機装 クイックシルバー", "suit_en": "Quicksilver Frame",
        "tc": "§b",
        "colors": {
            "plate": (206, 216, 226), "plate2": (150, 162, 176), "frame": (36, 42, 54),
            "glow": (120, 240, 255), "light": (222, 252, 255), "deep": (18, 70, 104),
            "accent": (255, 150, 60),
        },
        "motif": "液体金属のナノマシン。ヘルメスの翼の兜と翼のブーツ。昼側の灼熱（橙）と夜側の極寒（シアン）を左右で塗り分ける",
        "weapon": {"key": "hermes_edge", "ja": "水銀刃 ヘルメス・エッジ", "en": "Hermes Edge",
                   "kind": "saber"},
        "damage": 7, "defense": 12,
        "mobility": {"air_jumps": 2, "air_dash": 3, "hover": 0.4, "sprint": 2},
        "passive": {"effects": [["speed", 1]], "special": "afterimage",
                    "ja": "スピード II。疾走中は液体金属の残像が残り、残像に触れた敵を斬る"},
        "combo3": {"ja": "水銀の飛沫", "desc": "三段目で液体金属の刃が伸び、前方 4m を薙ぐ"},
        "moves": {
            "skill": {"ja": "水銀閃", "en": "QUICKSILVER FLASH", "cd": 70, "cost": 9,
                      "desc": "前方 7m を一瞬で駆け抜け、通り道の敵を斬る。残った水銀が遅れて弾ける"},
            "dash": {"ja": "ヘルメスの翼", "en": "WINGS OF HERMES", "cd": 90, "cost": 10,
                     "desc": "近くの敵の周りを三度跳び回り、そのたびに斬りつける"},
            "air": {"ja": "マーキュリー・レイン", "en": "MERCURY RAIN", "cd": 100, "cost": 10,
                    "desc": "宙で止まり、液体金属の針を前下方へ雨のように降らせる"},
            "ult": {"ja": "近日点突破 ペリヘリオン・ドライブ", "en": "PERIHELION DRIVE", "cd": 300,
                    "desc": "時を止め、光速で敵の周りを八度斬り抜ける。最後に昼側の灼熱と夜側の極寒が同時に炸裂する"},
        },
        "recipe": {"A": "minecraft:quartz", "B": "minecraft:feather"},
    },
    "venus": {
        "order": 2, "symbol": "♀",
        "ja": "金星", "en": "VENUS",
        "form_ja": "モーニングスター", "form_en": "MORNING STAR",
        "core_ja": "金星核 ヴィーナス・コア", "core_en": "Venus Core",
        "suit_ja": "明星機装 モーニングスター", "suit_en": "Morning Star Frame",
        "tc": "§e",
        "colors": {
            "plate": (240, 196, 92), "plate2": (255, 238, 204), "frame": (62, 42, 24),
            "glow": (226, 255, 96), "light": (255, 255, 214), "deep": (122, 84, 12),
            "accent": (255, 128, 168),
        },
        "motif": "明けの明星の女神。金とクリームの花弁のような腰の装甲、星の冠、肩から硫酸雲を噴く雲ポッド",
        "weapon": {"key": "lucifer_scepter", "ja": "明星杖 ルシファー・セプター", "en": "Lucifer Scepter",
                   "kind": "scepter"},
        "damage": 7, "defense": 14,
        "mobility": {"air_jumps": 1, "air_dash": 1, "hover": 0.7, "sprint": 0},
        "passive": {"effects": [["fire_resistance", 0]], "special": "acid_thorns",
                    "ja": "炎無効。殴ってきた相手を硫酸の毒で蝕む"},
        "combo3": {"ja": "星屑の花", "desc": "三段目で星の花が咲き、周りの敵を灼く"},
        "moves": {
            "skill": {"ja": "硫酸雲 アシッド・ヴェール", "en": "ACID VEIL", "cd": 110, "cost": 11,
                      "desc": "硫酸雲の弾を放つ。着弾点に 4 秒残る黄色い雲が、中の敵を毒と鈍化で蝕む"},
            "dash": {"ja": "逆行旋 レトログレード", "en": "RETROGRADE", "cd": 90, "cost": 9,
                     "desc": "金星の逆回転のように回りながら突進し、触れた敵を背後へ投げ飛ばす"},
            "air": {"ja": "温室熱波 グリーンハウス", "en": "GREENHOUSE", "cd": 100, "cost": 10,
                    "desc": "急降下し、着地点に 465℃ の熱の天蓋を広げる"},
            "ult": {"ja": "明けの明星 モーニングスター", "en": "MORNING STAR", "cd": 300,
                    "desc": "天に巨大な明星を灯し、星光の柱を降らせる。最後に硫酸の雨が降り注ぐ"},
        },
        "recipe": {"A": "minecraft:blaze_powder", "B": "minecraft:glowstone_dust"},
    },
    "earth": {
        "order": 3, "symbol": "♁",
        "ja": "地球", "en": "EARTH",
        "form_ja": "ガイア", "form_en": "GAIA",
        "core_ja": "地球核 アース・コア", "core_en": "Earth Core",
        "suit_ja": "蒼星機装 ガイア", "suit_en": "Gaia Frame",
        "tc": "§a",
        "colors": {
            "plate": (46, 110, 216), "plate2": (236, 242, 248), "frame": (24, 34, 52),
            "glow": (84, 255, 146), "light": (214, 255, 228), "deep": (10, 72, 44),
            "accent": (204, 112, 255),
        },
        "motif": "青と白の騎士型。緑に光る大陸の線、雲のような白いマント、肩の周りを回る月の子機（ルナ・ビット）",
        "weapon": {"key": "gaia_saber", "ja": "蒼星剣 ガイア・セイバー", "en": "Gaia Saber",
                   "kind": "sword"},
        "damage": 8, "defense": 16,
        "mobility": {"air_jumps": 1, "air_dash": 2, "hover": 0.6, "sprint": 1},
        "passive": {"effects": [["regeneration", 0]], "special": "luna_bit",
                    "ja": "再生。月の子機ルナ・ビットが近くの敵を自動で撃つ"},
        "combo3": {"ja": "オーロラ斬", "desc": "三段目でオーロラの斬撃が前方へ広がる"},
        "moves": {
            "skill": {"ja": "潮汐斬 タイダル・エッジ", "en": "TIDAL EDGE", "cd": 90, "cost": 10,
                      "desc": "月の引力で満ちる三日月の波を飛ばす。12m 進み、触れた敵を押し流す"},
            "dash": {"ja": "磁気圏突撃 マグネトスフィア", "en": "MAGNETOSPHERE", "cd": 100, "cost": 10,
                     "desc": "磁気圏の盾をまとって突進する。突進中はほぼ無敵で、触れた敵を弾き飛ばす"},
            "air": {"ja": "月墜 ルナ・フォール", "en": "LUNA FALL", "cd": 110, "cost": 11,
                    "desc": "ルナ・ビットを巨大化させて狙った地点へ落とす"},
            "ult": {"ja": "ガイア・レゾナンス", "en": "GAIA RESONANCE", "cd": 300,
                    "desc": "剣を大地に突き立て、地殻の柱を三重の輪で突き上げる。オーロラの幕が味方を癒やす"},
        },
        "recipe": {"A": "minecraft:emerald", "B": "minecraft:lapis_lazuli"},
    },
    "mars": {
        "order": 4, "symbol": "♂",
        "ja": "火星", "en": "MARS",
        "form_ja": "アレス", "form_en": "ARES",
        "core_ja": "火星核 マーズ・コア", "core_en": "Mars Core",
        "suit_ja": "軍神機装 アレス", "suit_en": "Ares Frame",
        "tc": "§c",
        "colors": {
            "plate": (196, 58, 34), "plate2": (140, 48, 28), "frame": (40, 34, 34),
            "glow": (255, 122, 42), "light": (255, 214, 156), "deep": (112, 20, 8),
            "accent": (217, 137, 58),
        },
        "motif": "重装の軍神。真紅と錆色の厚い装甲、スパルタ風の鶏冠の兜、大きな肩当て、背中を回る二つの衛星（フォボスとダイモス）",
        "weapon": {"key": "ares_breaker", "ja": "軍神斧 アレス・ブレイカー", "en": "Ares Breaker",
                   "kind": "axe"},
        "damage": 10, "defense": 18,
        "mobility": {"air_jumps": 1, "air_dash": 1, "hover": 0.3, "sprint": 0},
        "passive": {"effects": [["strength", 0], ["fire_resistance", 0]], "special": "war_cry",
                    "ja": "攻撃力アップ・炎無効。敵を倒すと雄叫びで周りの敵がすくむ"},
        "combo3": {"ja": "杭打ち", "desc": "三段目で斧の杭打ち機が火を噴き、地面ごと吹き飛ばす"},
        "moves": {
            "skill": {"ja": "赤砂嵐 ダストストーム", "en": "DUST STORM", "cd": 110, "cost": 11,
                      "desc": "赤い砂嵐をまとう。3 秒間、周り 4m の敵を削り、視界を奪う"},
            "dash": {"ja": "軍神突撃 ウォーパス", "en": "WARPATH", "cd": 90, "cost": 9,
                     "desc": "肩から突っ込み、前の敵をまとめて押し込んで打ち上げる"},
            "air": {"ja": "オリンポス・インパクト", "en": "OLYMPUS IMPACT", "cd": 110, "cost": 11,
                    "desc": "真下へ落ち、着地点の周りに溶岩の噴火口を六つ開く"},
            "ult": {"ja": "恐怖と戦慄 フォボス＆ダイモス", "en": "PHOBOS & DEIMOS", "cd": 300,
                    "desc": "二つの衛星を巨大な隕石にして続けざまに落とす。生き残った敵は恐怖ですくむ"},
        },
        "recipe": {"A": "minecraft:magma", "B": "minecraft:redstone_block"},
    },
    "jupiter": {
        "order": 5, "symbol": "♃",
        "ja": "木星", "en": "JUPITER",
        "form_ja": "ゼウス", "form_en": "ZEUS",
        "core_ja": "木星核 ジュピター・コア", "core_en": "Jupiter Core",
        "suit_ja": "雷帝機装 ゼウス", "suit_en": "Zeus Frame",
        "tc": "§6",
        "colors": {
            "plate": (234, 216, 184), "plate2": (201, 142, 90), "frame": (52, 38, 32),
            "glow": (140, 236, 255), "light": (232, 250, 255), "deep": (40, 90, 160),
            "accent": (217, 71, 43),
        },
        "motif": "巨大なガス惑星の王。クリームと褐色の縞の重装甲、胸で渦巻く大赤斑のコア、肩のテスラコイル、王冠の兜",
        "weapon": {"key": "keraunos", "ja": "雷霆鎚 ケラウノス", "en": "Keraunos",
                   "kind": "hammer"},
        "damage": 11, "defense": 20,
        "mobility": {"air_jumps": 1, "air_dash": 1, "hover": 0.5, "sprint": 0},
        "passive": {"effects": [["resistance", 0]], "special": "static",
                    "ja": "耐性。攻撃が当たるたびに静電気が溜まり、5 回目で近くの敵へ連鎖放電"},
        "combo3": {"ja": "雷槌", "desc": "三段目で鎚から落雷し、周りの敵を感電させる"},
        "moves": {
            "skill": {"ja": "雷霆 ケラウノス", "en": "KERAUNOS", "cd": 100, "cost": 11,
                      "desc": "前方の敵に雷を落とし、最大 5 体まで連鎖させる"},
            "dash": {"ja": "重力スイングバイ", "en": "GRAVITY SWING-BY", "cd": 100, "cost": 10,
                     "desc": "前方に重力の井戸を作って敵を一点に集め、その中を突き抜ける"},
            "air": {"ja": "大赤斑 グレートレッドスポット", "en": "GREAT RED SPOT", "cd": 120, "cost": 12,
                    "desc": "巨大な嵐の渦をまとって降り、周りの敵を吸い込んで雷で打つ"},
            "ult": {"ja": "ガリレオの審判", "en": "GALILEAN JUDGEMENT", "cd": 300,
                    "desc": "イオ（噴火）・エウロパ（氷）・ガニメデ（重力）・カリスト（衝突）の四衛星を落とし、最後に極大の雷霆"},
        },
        "recipe": {"A": "minecraft:lightning_rod", "B": "minecraft:copper_block"},
    },
    "saturn": {
        "order": 6, "symbol": "♄",
        "ja": "土星", "en": "SATURN",
        "form_ja": "クロノス", "form_en": "KRONOS",
        "core_ja": "土星核 サターン・コア", "core_en": "Saturn Core",
        "suit_ja": "環帝機装 クロノス", "suit_en": "Kronos Frame",
        "tc": "§h",
        "colors": {
            "plate": (227, 201, 138), "plate2": (247, 238, 216), "frame": (56, 46, 36),
            "glow": (190, 230, 255), "light": (240, 250, 255), "deep": (60, 92, 142),
            "accent": (142, 124, 255),
        },
        "motif": "環を従える時の王。淡い金とアイボリーの装甲、腰を斜めに回る大きな環、胸の六角形（北極の六角渦）、時計の文字盤の意匠",
        "weapon": {"key": "kronos_ring", "ja": "環刃 クロノス・リング", "en": "Kronos Ring",
                   "kind": "ring"},
        "damage": 8, "defense": 15,
        "mobility": {"air_jumps": 1, "air_dash": 2, "hover": 0.9, "sprint": 1},
        "passive": {"effects": [["slow_falling", 0]], "special": "ring_orbit",
                    "ja": "低速落下（水に浮くほど軽い）。環の欠片が体の周りを回り、触れた敵を削る"},
        "combo3": {"ja": "環断", "desc": "三段目で環刃が水平に広がり、周りを一周薙ぐ"},
        "moves": {
            "skill": {"ja": "リング・ソー", "en": "RING SAW", "cd": 80, "cost": 9,
                      "desc": "環刃を投げる。12m 先で折り返して戻り、行きと帰りで敵を刻む"},
            "dash": {"ja": "環転 リング・スライド", "en": "RING SLIDE", "cd": 90, "cost": 9,
                     "desc": "環に乗って地面を滑走し、通り道の敵を切り裂く"},
            "air": {"ja": "六角極渦 ヘキサゴン", "en": "HEXAGON", "cd": 110, "cost": 11,
                    "desc": "狙った地点に六角形の嵐を落とす。中の敵は 4 秒間鈍り、刻まれ続ける"},
            "ult": {"ja": "クロノス・ホライズン", "en": "KRONOS HORIZON", "cd": 300,
                    "desc": "時を止める時計の陣を広げ、止まった敵を巨大な環の一閃で両断する"},
        },
        "recipe": {"A": "minecraft:clock", "B": "minecraft:gold_ingot"},
    },
    "uranus": {
        "order": 7, "symbol": "⛢",
        "ja": "天王星", "en": "URANUS",
        "form_ja": "ウラノス", "form_en": "OURANOS",
        "core_ja": "天王星核 ウラヌス・コア", "core_en": "Uranus Core",
        "suit_ja": "傾天機装 ウラノス", "suit_en": "Ouranos Frame",
        "tc": "§3",
        "colors": {
            "plate": (142, 230, 232), "plate2": (47, 159, 168), "frame": (29, 58, 85),
            "glow": (170, 255, 255), "light": (240, 255, 255), "deep": (20, 90, 112),
            "accent": (255, 255, 255),
        },
        "motif": "横倒しの氷の巨星。淡い青緑の鋭い装甲、肩の氷晶、背中で 98° 傾いて縦に回る環、ダイヤモンドの鶏冠",
        "weapon": {"key": "tilt_bowgun", "ja": "傾天弩 ティルト・ボウガン", "en": "Tilt Bowgun",
                   "kind": "crossbow"},
        "damage": 6, "defense": 13,
        "mobility": {"air_jumps": 2, "air_dash": 2, "hover": 0.6, "sprint": 1},
        "passive": {"effects": [], "special": "frost_aura",
                    "ja": "殴ってきた相手を凍えさせる。近くの敵の足が鈍る"},
        "combo3": {"ja": "氷晶散弾", "desc": "三段目で至近距離へ氷晶の散弾を撃つ"},
        "moves": {
            "skill": {"ja": "絶対零度矢 アブソリュート・アロー", "en": "ABSOLUTE ARROW", "cd": 60, "cost": 8,
                      "desc": "敵を貫く冷気の矢。当たった敵は凍りつき、着弾点に氷の棘が立つ"},
            "dash": {"ja": "98° ロール", "en": "98° ROLL", "cd": 70, "cost": 8,
                     "desc": "横倒しに転がって避け、氷の分身を残す。次の惑星技は三本同時に撃つ"},
            "air": {"ja": "ダイヤモンド・レイン", "en": "DIAMOND RAIN", "cd": 110, "cost": 11,
                    "desc": "前方の広い範囲にダイヤモンドの雨を降らせる"},
            "ult": {"ja": "アクシアル・ティルト", "en": "AXIAL TILT", "cd": 300,
                    "desc": "重力の向きを 98° 傾けて敵を横へ放り出し、氷に閉じ込めてから粉々に砕く"},
        },
        "recipe": {"A": "minecraft:packed_ice", "B": "minecraft:diamond"},
    },
    "neptune": {
        "order": 8, "symbol": "♆",
        "ja": "海王星", "en": "NEPTUNE",
        "form_ja": "トリトン", "form_en": "TRITON",
        "core_ja": "海王星核 ネプチューン・コア", "core_en": "Neptune Core",
        "suit_ja": "深淵機装 トリトン", "suit_en": "Triton Frame",
        "tc": "§9",
        "colors": {
            "plate": (31, 79, 209), "plate2": (24, 32, 107), "frame": (12, 16, 40),
            "glow": (79, 227, 255), "light": (212, 250, 255), "deep": (10, 30, 92),
            "accent": (234, 244, 255),
        },
        "motif": "深海の騎士。紺碧と藍の装甲に白い波頭のヒレ、腕と脛のヒレ、三叉の冠、生物発光のような水色の線",
        "weapon": {"key": "triton_trident", "ja": "深淵三叉槍 トリトン", "en": "Triton Trident",
                   "kind": "trident"},
        "damage": 9, "defense": 15,
        "mobility": {"air_jumps": 1, "air_dash": 2, "hover": 0.5, "sprint": 1},
        "passive": {"effects": [["water_breathing", 0], ["conduit_power", 0]], "special": "tide",
                    "ja": "水中呼吸・コンジットパワー。水中か雨の中では与ダメージが上がる"},
        "combo3": {"ja": "波濤突き", "desc": "三段目の突きで水の槍が 5m 先まで伸びる"},
        "moves": {
            "skill": {"ja": "超音速の風 スーパーソニック", "en": "SUPERSONIC", "cd": 80, "cost": 9,
                      "desc": "秒速 600m の風の刃を突き出す。前方 14m を貫く"},
            "dash": {"ja": "大暗斑 ダークスポット", "en": "DARK SPOT", "cd": 100, "cost": 10,
                     "desc": "暗い渦に飛び込んで 8m 先へ抜ける。残った渦が敵を引き込む"},
            "air": {"ja": "トリトンの逆行", "en": "RETROGRADE TRITON", "cd": 110, "cost": 11,
                    "desc": "槍を逆行する衛星に変えて真下へ投げ、着弾点に窒素の間欠泉を噴かせる"},
            "ult": {"ja": "アビサル・テンペスト", "en": "ABYSSAL TEMPEST", "cd": 300,
                    "desc": "巨大な渦潮と超音速の嵐で敵を巻き上げ、最後に大津波で押し潰す"},
        },
        "recipe": {"A": "minecraft:prismarine_shard", "B": "minecraft:nautilus_shell"},
    },
    "sol": {
        "order": 9, "symbol": "☉",
        "ja": "太陽", "en": "SOL",
        "form_ja": "ソル・オーバードライブ", "form_en": "SOL OVERDRIVE",
        "core_ja": "恒星核 ソル・コア", "core_en": "Sol Core",
        "suit_ja": "恒星機装 ソル・オーバードライブ", "suit_en": "Sol Overdrive Frame",
        "tc": "§6",
        "colors": {
            "plate": (255, 244, 196), "plate2": (255, 194, 61), "frame": (92, 30, 10),
            "glow": (255, 172, 40), "light": (255, 250, 222), "deep": (164, 32, 15),
            "accent": (255, 90, 30),
        },
        "motif": "恒星そのもの。白金と金の装甲、頭の後ろで回る棘のあるコロナの光輪、炎のようなプロミネンスのヒレ、胸で脈打つ核融合炉",
        "weapon": {"key": "prominence_blade", "ja": "紅炎剣 プロミネンス・ブレイド", "en": "Prominence Blade",
                   "kind": "greatsword"},
        "damage": 12, "defense": 20,
        "mobility": {"air_jumps": 2, "air_dash": 2, "hover": 1.0, "sprint": 1},
        "passive": {"effects": [["fire_resistance", 0], ["regeneration", 0], ["night_vision", 0]],
                    "special": "corona",
                    "ja": "炎無効・再生・暗視。近くの敵を焦がすコロナをまとう"},
        "combo3": {"ja": "紅炎の弧", "desc": "三段目で紅炎の弧が前方を焼き払う"},
        "moves": {
            "skill": {"ja": "ソーラー・フレア", "en": "SOLAR FLARE", "cd": 90, "cost": 12,
                      "desc": "前方の扇形を太陽フレアで焼き、目を眩ませる"},
            "dash": {"ja": "コロナ・ドライブ", "en": "CORONA DRIVE", "cd": 90, "cost": 10,
                     "desc": "コロナをまとって突進し、炎の軌跡を残す"},
            "air": {"ja": "プロミネンス・アーチ", "en": "PROMINENCE ARCH", "cd": 110, "cost": 12,
                    "desc": "紅炎のアーチを三本、前方へ叩きつける"},
            "ult": {"ja": "スーパーノヴァ", "en": "SUPERNOVA", "cd": 300,
                    "desc": "自らを恒星の核に変えて収縮し、超新星爆発で全てを吹き飛ばす"},
        },
        "recipe": {"A": "astro:solar_fragment", "B": "minecraft:gold_block"},
    },
}

PLANET_KEYS = list(PLANETS)

# ---------------------------------------------------------------------------
#  アイテム
# ---------------------------------------------------------------------------
# 素材・道具（惑星ごとのコア・スーツ・ウェポンは PLANETS から作る）
MATERIALS = {
    "nano_cell": {"ja": "ナノマシン・セル", "en": "Nanomachine Cell", "stack": 64, "glint": False},
    "core_frame": {"ja": "コア・フレーム", "en": "Core Frame", "stack": 16, "glint": False},
    "solar_fragment": {"ja": "太陽の欠片 ソーラー・フラグメント", "en": "Solar Fragment", "stack": 16,
                       "glint": True},
    "terminal": {"ja": "星核ターミナル", "en": "Star Core Terminal", "stack": 1, "glint": False},
    "void_signal": {"ja": "ヴォイド・シグナル", "en": "Void Signal", "stack": 16, "glint": True},
}

RECIPES = {
    # 結果キー: (pattern, key -> item, 個数)
    "nano_cell": (["IRI", "RAR", "IRI"],
                  {"I": "minecraft:iron_ingot", "R": "minecraft:redstone",
                   "A": "minecraft:amethyst_shard"}, 2),
    "core_frame": (["CGC", "GDG", "CGC"],
                   {"C": f"{NS}:nano_cell", "G": "minecraft:glass", "D": "minecraft:diamond"}, 1),
    "terminal": (["III", "ICI", "IGI"],
                 {"I": "minecraft:iron_ingot", "C": f"{NS}:nano_cell",
                  "G": "minecraft:glass_pane"}, 1),
    "void_signal": (["NEN", "EXE", "NEN"],
                    {"N": f"{NS}:nano_cell", "E": "minecraft:ender_eye",
                     "X": "minecraft:diamond_block"}, 1),
}
# 惑星コアの共通の形: N=ナノマシン・セル、F=コア・フレーム、A/B=惑星ごとの素材
CORE_PATTERN = ["NAN", "BFB", "NAN"]

# ---------------------------------------------------------------------------
#  敵（宇宙からの侵略者）
# ---------------------------------------------------------------------------
ENEMIES = {
    "void_drone": {"ja": "ヴォイド・ドローン", "en": "Void Drone", "health": 20},
    "void_sentinel": {"ja": "ヴォイド・センチネル", "en": "Void Sentinel", "health": 44},
    "nemesis": {"ja": "虚星王 ネメシス", "en": "Nemesis, the Void Star", "health": 480},
    "hologram_target": {"ja": "ホログラム標的", "en": "Hologram Target", "health": 200},
}


def rgb01(c):
    return [round(c[0] / 255, 3), round(c[1] / 255, 3), round(c[2] / 255, 3)]
