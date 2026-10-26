# -*- coding: utf-8 -*-
"""NIGHT RUNNER: 感染都市 — ゾンビ 50 体の登録データ（DESIGN.md §6）。

このファイルはモデラー（nr_kit / gen_nr_zombies）・テクスチャ（nr_paint）・アニメーション
（gen_nr_zombie_anim）・AI スクリプト（scripts/zombies/*.js）・効果音（gen_nr_sounds）・
エンティティ（gen_nr_entities）・図鑑（UI）の**共通の発注書**。

* 下の語彙辞書（OUTFIT_VOCAB / MUTATION_VOCAB / SKIN_VOCAB / EYES_VOCAB / ATTACK_VOCAB /
  LOCOMOTION_VOCAB / ABILITY_VOCAB / VOICE_VOCAB / BLOOD_VOCAB / GORE_KEYS）が**語彙の全て**。
  下流の実装者はここにある鍵を**全部・この意味のまま**実装する。ZOMBIES はこの語彙だけを使う。
* 語彙の各項目は `desc`（何に見えるか・何をするか、一行）と `params`（引数の既定値）を持つ。
  ZOMBIES 側は `(鍵, {引数})` で上書きする。上書きできる引数は `params` にあるもの
  （服は OUTFIT_COMMON_PARAMS も可）だけ。
* ZOMBIES の並び順が種類番号 `ztype`（0〜49）。一般 24 → 俊敏 8 → 特殊 11 → 夜 4 → ボス 3。
* 色はすべて (R, G, B) の 0〜255。長さの単位は、骨格はセンチ・モデルは px（16 = 1 ブロック）、
  距離・範囲はブロック、時間は秒（「tick」と書いたものだけ 1/20 秒）。
* 名前はダイイングライトの敵に着想を得たオリジナル。子どもの感染者はいない（全員 150cm 以上の大人）。

下流が守る取り決め（DESIGN.md §3 のプロパティの使い方）:
* `nr:ability`（0..7）= 今見せている能力の段階。値は種類ごとに `ability_states(z)` が
  能力の並び順に 1.. を割り当てる（例 klaxon: howl_alarm.inflate = 1、howl_alarm.howl = 2）。
  アニメは `animation.nr.z.ab_<能力>_<段階>`、攻撃は `animation.nr.z.atk_<攻撃>`、
  移動は `animation.nr.z.walk_<移動>` / `run_<移動>`（一覧は `zombie_animations(z)`）。
* `nr:armor`（0..3）= 装甲の段階（gore.armored / armor_strip）と、壊れて消える部品
  （gore.breakables: ボンベ・声の袋・懐中電灯・盾・余分な頭）の残り。初期値は `initial_armor(z)`。
* `nr:state` の climb / stagger / down / crawl は能力からも使う（各能力の `state` に書いた）。
* 声の効果音は `nr.z.<voice>.<idle|alert|attack|hurt|death>`（`zombie_sounds(z)`）。

`python3 tools/nightrunner/nr_spec_zombies.py` で自己検査（50 体・区分の数・鍵の重複・語彙の参照・
必須項目・釣り合い）を走らせ、一覧表を出す。
"""
from __future__ import annotations

import copy
import re
import sys

# nr_spec.py が nr_spec_catalog と一緒に `from ... import *` で再輸出する名前（衝突しないようゾンビ専用の名前に）
__all__ = [
    # 表
    "CLASS_ORDER", "CLASS_INFO", "DAMAGE_RANGE", "RIG_BONES", "BODY_BONES", "HIT_PARTS", "ARMOR_BONES",
    "PROPERTY_ENUMS", "DTYPES", "RESIST_KEYS", "RESIST_DEFAULT", "SHARED_LOOT_ITEMS",
    "SPAWN_TIMES", "SPAWN_WHERE", "SPAWN_SITES",
    # 語彙
    "SKIN_VOCAB", "SKIN_TONES", "BLOOD_VOCAB", "EYES_VOCAB", "OUTFIT_LAYERS", "OUTFIT_COMMON_PARAMS",
    "OUTFIT_VOCAB", "MUTATION_VOCAB", "MUTATION_ARMOR", "ATTACK_EFFECTS", "ATTACK_VOCAB",
    "LOCOMOTION_VOCAB", "ABILITY_TRIGGERS", "ABILITY_VOCAB", "VOICE_EVENTS", "VOICE_VOCAB",
    "GORE_KEYS", "GORE_DEFAULTS", "EXPLODE_KINDS", "CORPSE_KINDS", "WEAK_ZONES",
    # ゾンビ
    "ZOMBIE_FIELDS", "ZOMBIE_OPTIONAL_FIELDS", "ZOMBIES", "ZTYPE", "ZOMBIE_BY_KEY",
    "zombie_id", "zombies_of_class", "ability_keys", "ability_params", "ability_states",
    "outfit_params", "mutation_params", "all_attacks", "armor_sources", "part_bones", "initial_armor",
    "zombie_collision", "zombie_animations", "zombie_sounds", "check_zombies", "unused_zombie_vocab",
]

# ---------------------------------------------------------------------------
#  基本の表（DESIGN.md §3〜§6 と同じ値。変えるときは DESIGN.md を先に）
# ---------------------------------------------------------------------------

CLASS_ORDER = ("common", "viral", "special", "night", "boss")

# 区分ごとの数・釣り合いの範囲・性能上限（DESIGN.md §6 / §11）
CLASS_INFO = {
    "common":  dict(ja="一般感染者", en="Common Infected", count=24,
                    hp=(16, 40), speed=(0.14, 0.28), damage=(2, 6),
                    cubes=450, tex=512, xp=(2, 8)),
    "viral":   dict(ja="俊敏型", en="Viral", count=8,
                    hp=(12, 30), speed=(0.30, 0.38), damage=(2, 6),
                    cubes=450, tex=512, xp=(5, 14)),
    "special": dict(ja="特殊感染者", en="Special Infected", count=11,
                    hp=(60, 200), speed=(0.15, 0.32), damage=(3, 12),
                    cubes=650, tex=512, xp=(15, 60)),
    "night":   dict(ja="夜の捕食者", en="Night Hunter", count=4,
                    hp=(120, 260), speed=(0.20, 0.40), damage=(6, 12),
                    cubes=650, tex=512, xp=(50, 120)),
    "boss":    dict(ja="ボス", en="Boss", count=3,
                    hp=(600, 1500), speed=(0.18, 0.38), damage=(10, 14),
                    cubes=1100, tex=1024, xp=(250, 800)),
}
DAMAGE_RANGE = (2, 14)

# ゾンビの骨格のボーン名（DESIGN.md §3。名前と親子を変えない）
RIG_BONES = (
    "root", "waist", "pelvis",
    "leg_r", "shin_r", "foot_r", "stump_leg_r_lower", "stump_leg_r_upper",
    "leg_l", "shin_l", "foot_l", "stump_leg_l_lower", "stump_leg_l_upper",
    "torso", "torso_wound", "guts", "stump_torso", "chest",
    "neck", "head", "jaw", "head_wound", "skull_open", "stump_neck",
    "arm_r", "forearm_r", "hand_r", "arm_r_wound", "stump_arm_r_lower", "stump_arm_r_upper",
    "arm_l", "forearm_l", "hand_l", "arm_l_wound", "stump_arm_l_lower", "stump_arm_l_upper",
)
# 服・変異の `on` 引数に書いてよい（部品を付けてよい）体のボーン
BODY_BONES = ("pelvis", "leg_r", "shin_r", "foot_r", "leg_l", "shin_l", "foot_l",
              "torso", "chest", "neck", "head", "jaw",
              "arm_r", "forearm_r", "hand_r", "arm_l", "forearm_l", "hand_l")

# 部位判定・ゴアの部位（DESIGN.md §4）
HIT_PARTS = ("head", "torso", "arm_r", "arm_l", "leg_r", "leg_l")
# 装甲の部品ボーン（`nr:armor` で表示を切る。DESIGN.md §3）
ARMOR_BONES = {"head": "armor_head", "torso": "armor_chest",
               "arm_r": "armor_arm_r", "arm_l": "armor_arm_l",
               "leg_r": "armor_leg_r", "leg_l": "armor_leg_l"}

# エンティティプロパティの値（DESIGN.md §3。gore の pre_damage の検査に使う）
PROPERTY_ENUMS = {
    "head": ("intact", "wounded", "jawless", "cracked", "severed", "crushed"),
    "arm_r": ("intact", "wounded", "broken", "cut_lower", "cut_upper"),
    "arm_l": ("intact", "wounded", "broken", "cut_lower", "cut_upper"),
    "leg_r": ("intact", "wounded", "broken", "cut_lower", "cut_upper"),
    "leg_l": ("intact", "wounded", "broken", "cut_lower", "cut_upper"),
    "torso": ("intact", "slashed", "gutted", "halved"),
    "state": ("normal", "crawl", "climb", "stagger", "down", "special", "dead"),
}

# ダメージ種別と耐性の鍵（DESIGN.md §4。uv だけは「UV への弱さ」）
DTYPES = ("slash", "blunt", "pierce", "blast", "fire", "shock", "toxic")
RESIST_KEYS = {
    "slash":  "刃物（切断）のダメージ倍率。1.0 = 標準、<1 = 効きにくい、>1 = 弱い",
    "blunt":  "打撃のダメージ倍率",
    "pierce": "刺突・矢・弾のダメージ倍率",
    "blast":  "爆発のダメージ倍率",
    "fire":   "火（炎上・火炎瓶・火の改造）のダメージ倍率。0 = 無効",
    "shock":  "電気（感電改造・電気トラップ）のダメージ倍率",
    "toxic":  "毒（毒の改造・毒ガス）のダメージ倍率。0 = 無効",
    "uv":     "UV への弱さ。0 = UV は効かない。>0 なら UV 光の中で uv × 4 ダメージ/秒と怯み"
              "（ABILITY_VOCAB['uv_weak'] を持つ種類は加えて逃げる）",
}
RESIST_DEFAULT = dict(slash=1.0, blunt=1.0, pierce=1.0, blast=1.0,
                      fire=1.0, shock=1.0, toxic=1.0, uv=0.0)

# 共有の素材・ルートのアイテム（nr_spec_catalog と同じ鍵。名前・アイコンは catalog が決める）
SHARED_LOOT_ITEMS = (
    "nr:scrap", "nr:rags", "nr:alcohol", "nr:chemicals", "nr:blades", "nr:duct_tape",
    "nr:battery", "nr:gunpowder_pouch", "nr:mutated_tissue", "nr:infected_trophy",
    "nr:volatile_trophy", "nr:apex_trophy", "nr:inhibitor", "nr:uv_shroom",
    "nr:bandage", "nr:medkit", "nr:immunity_booster",
    "nr:ammo_pistol", "nr:ammo_shotgun", "nr:ammo_rifle", "nr:bolt", "nr:survivor_arrow",
    "nr:money",
)

# スポーンの場所（`spawn.site`）。§8 の建物モジュールに無い場所は fallback を使う
SPAWN_TIMES = ("day", "night", "any")
SPAWN_WHERE = {
    "city": "/scriptevent nr:city で組んだ街区の中（道路・建物・屋上）",
    "overworld": "街の外も含む通常のオーバーワールド（スポーンルール）",
    "structure": "建物モジュールの決まった位置にだけ置く（自然には湧かない。ボス・巣）",
}
SPAWN_SITES = {
    # 鍵: (説明, 無いときの代わり)
    "street":       ("道路・歩道・路地", None),
    "apartment":    ("アパート", None),
    "shop":         ("商店", None),
    "gas_station":  ("ガソリンスタンド", None),
    "hospital":     ("病院", None),
    "police":       ("警察署", None),
    "church":       ("教会の塔", None),
    "warehouse":    ("倉庫", None),
    "parking":      ("立体駐車場", None),
    "rooftop":      ("屋上パルクールの足場", None),
    "office":       ("オフィス街", "street"),
    "construction": ("工事現場", "warehouse"),
    "waterfront":   ("運河・水辺", "street"),
    "sewer":        ("下水道・地下の暗がり", "warehouse"),
    "plaza":        ("広場・繁華街", "street"),
    "lab":          ("研究所", "hospital"),
    "hive":         ("感染者の巣（暗い屋内に菌糸）", "warehouse"),
    "stadium":      ("競技場", "plaza"),
}

# ---------------------------------------------------------------------------
#  肌（nr_paint の SKINS が実装する）
# ---------------------------------------------------------------------------
# base = 地の色、shadow = 陰・くぼみ、highlight = 骨の出っ張り・脂の照り、vein = 浮いた血管、
# mottle = 斑（死斑・腐敗の染み）、wet = 濡れた照り 0..1、tone_mix = 生前の肌色（SKIN_TONES）を
# 混ぜる割合、emissive_vein = 血管の色を発光させる（cinder のひび割れ）

SKIN_VOCAB = {
    "pale": dict(desc="血の気の失せた青白い死体の肌。薄く青い血管が透け、唇と目の周りが紫",
                 base=(196, 192, 178), shadow=(138, 132, 128), highlight=(226, 222, 212),
                 vein=(112, 120, 150), mottle=(160, 150, 160), wet=0.2, tone_mix=0.35),
    "grey_green": dict(desc="腐敗の進んだ灰緑の肌。関節のしわに黒ずみ、黄土色の染み",
                       base=(140, 150, 124), shadow=(88, 98, 80), highlight=(176, 184, 160),
                       vein=(70, 84, 70), mottle=(112, 104, 88), wet=0.25, tone_mix=0.3),
    "necrotic_purple": dict(desc="壊死した紫の肌。黒紫の血管が網目に走り、緑がかった腐敗の斑",
                            base=(132, 104, 124), shadow=(78, 56, 76), highlight=(168, 140, 158),
                            vein=(60, 30, 60), mottle=(96, 120, 80), wet=0.35, tone_mix=0.2),
    "jaundiced": dict(desc="黄疸の黄ばんだ肌。白目まで黄色く、茶色い斑と乾いたひび",
                      base=(198, 176, 110), shadow=(140, 118, 70), highlight=(224, 206, 148),
                      vein=(120, 90, 60), mottle=(150, 120, 90), wet=0.25, tone_mix=0.3),
    "charred": dict(desc="炭化した黒い肌。割れ目から赤い生肉がのぞき、表面に灰が積もる",
                    base=(40, 34, 30), shadow=(16, 12, 10), highlight=(88, 76, 66),
                    vein=(120, 40, 20), mottle=(150, 140, 130), wet=0.0, tone_mix=0.0),
    "drowned_blue": dict(desc="水を吸ってふやけた青白い肌。指先が白くしわしわ、藻の緑の斑",
                         base=(150, 170, 178), shadow=(92, 110, 124), highlight=(196, 210, 214),
                         vein=(70, 80, 120), mottle=(120, 140, 110), wet=0.7, tone_mix=0.2),
    "bloated_pink": dict(desc="ガスで張った赤桃色の肌。伸びて光り、紫の血管と黄緑の腐敗斑",
                         base=(206, 156, 148), shadow=(150, 98, 96), highlight=(232, 196, 186),
                         vein=(110, 90, 140), mottle=(160, 170, 110), wet=0.5, tone_mix=0.3),
    "ashen": dict(desc="灰のようにくすんだ乾いた肌。頬がこけ、骨の形が浮く",
                  base=(164, 160, 154), shadow=(104, 100, 98), highlight=(200, 198, 192),
                  vein=(90, 90, 100), mottle=(130, 120, 110), wet=0.1, tone_mix=0.3),
    "flushed": dict(desc="感染したばかりの紅潮した肌。汗で光り、首から黒い血管が広がる（俊敏型）",
                    base=(196, 150, 132), shadow=(140, 92, 84), highlight=(228, 190, 170),
                    vein=(90, 30, 50), mottle=(180, 110, 110), wet=0.45, tone_mix=0.5),
    "leathery_brown": dict(desc="長く外にいた干からびた茶色の肌。革のように硬く、深いしわ",
                           base=(120, 92, 66), shadow=(70, 50, 36), highlight=(160, 130, 98),
                           vein=(60, 40, 30), mottle=(90, 96, 60), wet=0.05, tone_mix=0.25),
    "bruised": dict(desc="全身が打ち身のような紫と黄緑のまだら。筋肉の張った巨体向け",
                    base=(150, 120, 128), shadow=(90, 64, 80), highlight=(186, 160, 160),
                    vein=(70, 40, 70), mottle=(150, 150, 80), wet=0.3, tone_mix=0.3),
    "nocturnal_grey": dict(desc="夜の捕食者の濡れた暗灰色の肌。毛がなく、ところどころ皮が剥けて赤い",
                           base=(92, 96, 104), shadow=(44, 46, 54), highlight=(140, 146, 152),
                           vein=(40, 30, 40), mottle=(120, 60, 60), wet=0.55, tone_mix=0.0),
    "shadow_black": dict(desc="煤のように黒い肌。角度で青く虹色に照る（闇に溶ける）",
                         base=(34, 34, 40), shadow=(12, 12, 16), highlight=(70, 74, 90),
                         vein=(20, 20, 30), mottle=(60, 40, 50), wet=0.6, tone_mix=0.0),
    "cinder": dict(desc="焼け焦げた殻の肌。ひび割れの奥が橙に光る残り火",
                   base=(46, 36, 32), shadow=(18, 12, 10), highlight=(96, 80, 70),
                   vein=(255, 120, 30), mottle=(140, 130, 120), wet=0.0, tone_mix=0.0,
                   emissive_vein=True),
    "fungal_ochre": dict(desc="菌糸に侵された黄土色の肌。白い胞子の粉が斑に吹く",
                         base=(170, 146, 100), shadow=(110, 90, 56), highlight=(210, 190, 140),
                         vein=(90, 70, 40), mottle=(200, 200, 170), wet=0.3, tone_mix=0.15),
    "raw_flesh": dict(desc="皮がほとんど無い剥き出しの筋肉。黄色い脂肪の筋と腱が走る",
                      base=(150, 58, 52), shadow=(90, 24, 24), highlight=(196, 110, 98),
                      vein=(70, 20, 30), mottle=(220, 200, 160), wet=0.8, tone_mix=0.0),
    "lab_white": dict(desc="日に当たったことのない真っ白な肌。青い血管がくっきり透ける",
                      base=(222, 224, 226), shadow=(160, 166, 176), highlight=(246, 248, 250),
                      vein=(90, 140, 220), mottle=(200, 190, 200), wet=0.3, tone_mix=0.2),
}

# 生前の肌色（optional の `tone` 0..4）。SKIN_VOCAB[skin]["tone_mix"] の割合で地の色に混ぜる
SKIN_TONES = (
    (232, 200, 176),   # 0 とても明るい
    (214, 176, 146),   # 1 明るい
    (190, 146, 112),   # 2 中間
    (150, 104, 74),    # 3 褐色
    (100, 68, 48),     # 4 濃い褐色
)

# ---------------------------------------------------------------------------
#  血（パーティクル・血痕・断面の色。gore の `blood` が指す）
# ---------------------------------------------------------------------------
BLOOD_VOCAB = {
    "red":   dict(desc="鮮やかな赤い血。噴き出し・滴り・血だまり", spray=(176, 18, 20),
                  pool=(96, 8, 10), clot=(70, 10, 10), emissive=False),
    "dark":  dict(desc="古い感染者のどす黒い赤茶の血。粘って糸を引く", spray=(104, 26, 20),
                  pool=(58, 14, 12), clot=(40, 12, 10), emissive=False),
    "black": dict(desc="夜の捕食者のタールのような黒い血。油膜の照り", spray=(30, 12, 18),
                  pool=(16, 6, 10), clot=(10, 4, 6), emissive=False),
    "bile":  dict(desc="黄緑の胆汁と膿。毒ガス持ちの体液", spray=(150, 160, 40),
                  pool=(96, 104, 26), clot=(70, 74, 20), emissive=False),
    "acid":  dict(desc="発光する緑の酸。地面で泡立つ", spray=(130, 240, 50),
                  pool=(70, 160, 30), clot=(50, 110, 20), emissive=True),
    "ash":   dict(desc="血の代わりに灰と炭の粉。血だまりは作らない", spray=(110, 104, 98),
                  pool=None, clot=(40, 36, 32), emissive=False),
    "water": dict(desc="血の混じった薄桃色の水。大きく飛び散り、すぐ薄まる", spray=(180, 120, 120),
                  pool=(120, 80, 84), clot=(90, 50, 54), emissive=False),
    "ember": dict(desc="火の粉と黒い焦げた体液。橙に光る", spray=(255, 130, 40),
                  pool=(30, 16, 10), clot=(60, 20, 10), emissive=True),
}

# ---------------------------------------------------------------------------
#  目（nr_paint と発光マテリアル。emissive は entity_emissive_alpha 系）
# ---------------------------------------------------------------------------
EYES_VOCAB = {
    "clouded":        dict(desc="白く濁った膜のかかった目。瞳はぼんやり灰青",
                           sclera=(200, 196, 184), iris=(150, 160, 170), pupil=(110, 120, 130),
                           emissive=False, glow=None),
    "bloodshot":      dict(desc="真っ赤に充血した白目と開ききった黒い瞳（俊敏型の目）",
                           sclera=(220, 140, 130), iris=(90, 60, 40), pupil=(10, 8, 8),
                           emissive=False, glow=None),
    "milky":          dict(desc="瞳まで真っ白な白濁の目（古い・水死・焼けた感染者）",
                           sclera=(226, 226, 220), iris=(226, 226, 220), pupil=None,
                           emissive=False, glow=None),
    "glowing_yellow": dict(desc="黄色く光る目（ボラタイル）",
                           sclera=(60, 50, 20), iris=(255, 220, 80), pupil=(255, 250, 200),
                           emissive=True, glow=(255, 220, 80)),
    "glowing_red":    dict(desc="赤く光る目（頂点の捕食者）",
                           sclera=(60, 10, 10), iris=(255, 50, 30), pupil=(255, 200, 180),
                           emissive=True, glow=(255, 50, 30)),
    "glowing_green":  dict(desc="毒々しい黄緑に光る目（酸・毒の感染者）",
                           sclera=(40, 60, 20), iris=(150, 255, 60), pupil=(230, 255, 200),
                           emissive=True, glow=(150, 255, 60)),
    "glowing_orange": dict(desc="残り火のように橙に光る目（爆発・炎の感染者）",
                           sclera=(60, 30, 10), iris=(255, 140, 40), pupil=(255, 230, 180),
                           emissive=True, glow=(255, 140, 40)),
    "glowing_cyan":   dict(desc="胞子の青緑に光る目",
                           sclera=(20, 50, 50), iris=(110, 240, 255), pupil=(220, 255, 255),
                           emissive=True, glow=(110, 240, 255)),
    "glowing_white":  dict(desc="闇の中に針の先ほどの白い光点だけが見える目",
                           sclera=(10, 10, 14), iris=(240, 240, 255), pupil=(255, 255, 255),
                           emissive=True, glow=(240, 240, 255)),
    "none":           dict(desc="目が無い。暗い眼窩から血の涙の跡",
                           sclera=(40, 10, 10), iris=None, pupil=None,
                           emissive=False, glow=None),
}

# ---------------------------------------------------------------------------
#  服・装備（nr_kit が部品として実装する）
# ---------------------------------------------------------------------------
# layer: どう作るか
OUTFIT_LAYERS = {
    "skin":  "肌のテクスチャに直接描く（入れ墨など）。キューブは足さない",
    "cloth": "体のキューブの UV に描き、袖口・裾・襟・ポケットなどを 0.25〜0.5px の薄いキューブで足す",
    "shell": "体より 0.5〜1.5px 大きい外殻のキューブ（厚手の上着・防護服・鎧）",
    "hard":  "硬い独立した部品（ヘルメット・装甲板）。その部位が gore.armored に入っている時だけ "
             "ARMOR_BONES の子ボーンに置き、nr:armor で消す（入っていなければ普通に体の部位の子）",
    "gear":  "独立した小物（ベルト・ボンベ・バッグ・眼鏡）",
    "held":  "手に持つ物（hand_r / hand_l の子）。腕が落ちると一緒に落ちる",
    "hair":  "髪・ひげ。head / jaw の子のキューブ群",
}
# どの服にも渡せる共通の引数
OUTFIT_COMMON_PARAMS = {
    "color":  "主色 (R, G, B)",
    "color2": "副色（柄・縁取り・ロゴ）(R, G, B)",
    "torn":   "破れ 0..3（3 = ぼろぼろで肌が大きく出る、袖・裾が千切れる）",
    "bloody": "血の染み 0..3（3 = ほぼ全面が血で黒ずむ。上から垂れた跡を付ける）",
    "dirty":  "汚れ 0..3（泥・油・煤）",
    "burnt":  "焦げ 0..3（3 = 溶けて肌に張り付いた燃えかす）",
    "wet":    "濡れ（True で色を暗く・照りを強く。水死体）",
}


def _o(desc, bones, layer, armor=(), **params):
    """服・装備の語彙の項目。armor = この部品が装甲になれる部位（gore.armored の根拠）。"""
    return dict(desc=desc, bones=tuple(bones), layer=layer, armor=tuple(armor), params=params)


_ARMS = ("arm_r", "forearm_r", "arm_l", "forearm_l")
_LEGS = ("leg_r", "shin_r", "leg_l", "shin_l")
_UPPER = ("chest", "torso") + _ARMS

OUTFIT_VOCAB = {
    # --- 髪 ---
    "hair": _o("髪。style で形、patchy で抜け毛（頭皮が斑に露出）。long 系は肩まで垂れて揺れる",
               ("head",), "hair",
               style="short", color=(46, 36, 30), patchy=0, length=1.0),
    "beard": _o("ひげ（下顎の子なので顎が飛ぶと一緒に飛ぶ）。stubble / full / goatee / mustache",
                ("jaw",), "hair", style="stubble", color=(46, 36, 30)),
    # --- 頭 ---
    "hard_hat": _o("黄色い作業用ヘルメット。つば・内側の吊りバンド・あごひも。凹み dented 0..3",
                   ("head",), "hard", armor=("head",),
                   color=(240, 196, 20), sticker=True, dented=0),
    "police_cap": _o("制帽。黒いつば・帽章（style=guard なら警備会社の布章）",
                     ("head",), "gear", color=(34, 46, 84), badge=True, style="police"),
    "riot_helmet": _o("機動隊のヘルメット。透明のバイザー（down / up / cracked）と首の垂れ",
                      ("head",), "hard", armor=("head",),
                      color=(20, 22, 26), visor="down", neck_guard=True),
    "helmet_military": _o("戦闘ヘルメット。迷彩カバー・額のゴーグル・垂れたあごひも",
                          ("head",), "hard", armor=("head",),
                          color=(88, 92, 70), cover="camo", goggles=True, chinstrap="dangling"),
    "firefighter_helmet": _o("消防のヘルメット。前章（番号）・後ろの垂れ・上げたシールド",
                             ("head",), "hard", color=(196, 160, 36), shield_text="7",
                             visor="up", neck_flap=True),
    "scooter_helmet": _o("ジェット型のヘルメット。バイザー（up / down / missing）、ひび cracked 0..3",
                         ("head",), "hard", armor=("head",),
                         color=(240, 240, 240), visor="up", strap="dangling", cracked=0),
    "baseball_cap": _o("野球帽。backwards=True で後ろ向き。正面のロゴは color2",
                       ("head",), "gear", color=(180, 30, 30), backwards=False, logo=True),
    "skull_cap": _o("頭にぴったりの布帽子。kind = surgical（手術帽）/ kitchen（厨房の帽子）/ hairnet",
                    ("head",), "cloth", color=(90, 140, 170), kind="surgical"),
    "bridal_veil": _o("花嫁のベール。頭頂のティアラから背中へ垂れる半透明の布（裂け目に血）",
                      ("head",), "cloth", color=(245, 242, 236), length="long", tiara=True),
    "gas_mask": _o("全面のガスマスク。丸い二眼レンズ（intact / cracked / shattered）と吸収缶 filters 1..2",
                   ("head",), "gear", color=(40, 42, 40), filters=2, lens="intact"),
    "surgical_mask": _o("不織布マスク。position = mouth（口元）/ chin（顎に下げる）/ ear（片耳でぶら下がる）",
                        ("head",), "cloth", color=(150, 200, 220), position="mouth"),
    "glasses": _o("眼鏡。kind = clear / sun / thick（老眼鏡の厚いレンズ）/ loupe（手術用拡大鏡）",
                  ("head",), "gear", color=(30, 30, 30), kind="clear", cracked=False),
    "headphones": _o("ヘッドホン（over_ear）かイヤホン（earbuds）。worn=neck で首に掛ける",
                     ("head",), "gear", color=(240, 240, 240), kind="over_ear", worn="head",
                     cord_dangling=False),
    # --- 上半身 ---
    "shirt": _o("襟付きシャツ。cut = dress / blouse / flannel / work、sleeves = long / short / rolled / torn_off、"
                "open = 弾けたボタン数 0..3、pattern = plain / stripe / check",
                _UPPER, "cloth", color=(222, 220, 210), cut="dress", sleeves="long",
                open=0, tucked=True, pattern="plain"),
    "t_shirt": _o("T シャツ。cut = crew / tank（袖なし）/ jersey（番号入りのスポーツシャツ）、print = none / logo / band / number",
                  _UPPER, "cloth", color=(120, 120, 124), cut="crew", print="none", number=""),
    "hoodie": _o("パーカー。hood = down（背中に垂れる）/ up（頭を覆う）、腹のポケットとひも",
                 _UPPER + ("head",), "shell", color=(70, 70, 74), hood="down", zip=False),
    "suit_jacket": _o("背広の上着。襟・二つボタン・胸ポケット。missing_sleeve = none / l / r / both（袖が千切れて無い）",
                      _UPPER, "shell", color=(52, 54, 62), open=True, missing_sleeve="none",
                      pocket_square=False),
    "necktie": _o("ネクタイ。loosened=True で結び目が胸まで下がる。pattern = plain / stripe / dot",
                  ("chest", "torso"), "gear", color=(120, 24, 32), pattern="plain", loosened=True),
    "cardigan": _o("毛糸の前開きカーディガン（ケーブル編みの模様）。buttons_missing 0..4",
                   _UPPER, "shell", color=(120, 90, 70), buttons_missing=0),
    "leather_jacket": _o("革ジャン。studs=True で肩と襟に鋲、patches = 背中のワッペン数、sleeveless で袖なし",
                         _UPPER, "shell", color=(24, 22, 22), studs=False, patches=0, sleeveless=False),
    "rain_jacket": _o("薄手の雨合羽。胸と腕に反射帯、フードは背中に垂れる",
                      _UPPER, "shell", color=(30, 120, 60), reflective=True, hood="down"),
    "hi_vis_vest": _o("蛍光色の安全ベスト。銀の反射帯 2 本（strips の色）",
                      ("chest", "torso"), "cloth", color=(210, 250, 40), strips=(200, 200, 200)),
    "police_uniform": _o("制服のシャツ。肩章・袖の布章・胸の徽章、radio で肩の無線機、belt で装備ベルト"
                         "（ホルスター・手錠・警棒）。style = police / guard",
                         _UPPER + ("pelvis",), "cloth", color=(34, 46, 84), style="police",
                         badge=True, radio=True, belt=True),
    "chef_coat": _o("白いコックコート。ダブルの布ボタン 2 列、rolled_sleeves で袖まくり",
                    _UPPER, "cloth", color=(232, 230, 222), double_breasted=True, rolled_sleeves=False),
    "apron": _o("前掛け。kind = cloth / butcher_leather（厚い革）/ rubber、length = waist / full、stains 0..3",
                ("chest", "torso", "pelvis", "leg_r", "leg_l"), "shell", color=(60, 58, 56),
                kind="cloth", length="waist", stains=1),
    "hospital_gown": _o("背中の開いた入院着（水玉柄）。iv_line で前腕に点滴の針と千切れた管、wrist_tag で手首の識別バンド",
                        _UPPER + ("pelvis", "leg_r", "leg_l", "forearm_l"), "cloth",
                        color=(170, 200, 210), pattern="dots", open_back=True, iv_line=False,
                        wrist_tag=True),
    "scrubs": _o("医療用スクラブの上下。gown で上に手術着を羽織る、stethoscope で首に聴診器",
                 _UPPER + ("pelvis",) + _LEGS, "cloth", color=(120, 180, 200), gown=False,
                 stethoscope=False),
    "coveralls": _o("つなぎの作業着。rolled_top で上半身を脱いで袖を腰で結ぶ、name_patch で胸の名札刺繍",
                    _UPPER + ("pelvis",) + _LEGS, "cloth", color=(40, 70, 120), rolled_top=False,
                    name_patch=True),
    "firefighter_coat": _o("防火服の上着（襟を立て、反射帯 bands が胸・腕・裾に）。pants で同じ生地のズボン",
                           _UPPER + ("pelvis",) + _LEGS, "shell", color=(196, 160, 90),
                           bands=(220, 220, 90), pants=True, collar_up=True),
    "hazmat_suit": _o("全身の化学防護服。頭巾 hood、継ぎ目のテープ taped、バイザーの曇り visor_fog 0..3",
                      _UPPER + ("pelvis", "head") + _LEGS, "shell", color=(236, 200, 40),
                      hood=True, taped=True, visor_fog=1),
    "riot_armor": _o("機動隊の防護衣。胸当て・肩当て・前腕と脛の当て板に白い POLICE の文字",
                     _UPPER + _LEGS, "hard", armor=("torso", "arm_r", "arm_l", "leg_r", "leg_l"),
                     color=(28, 30, 34), coverage="full", text="POLICE"),
    "military_vest": _o("防弾プレートキャリア。弾倉ポーチ pouches 個、肩の無線機、前後の防弾板",
                        ("chest", "torso"), "hard", armor=("torso",),
                        color=(70, 80, 56), pouches=6, radio=True, plates=True),
    "camo_fatigues": _o("迷彩の戦闘服の上下。pattern = woodland / urban / desert",
                        _UPPER + ("pelvis",) + _LEGS, "cloth", color=(110, 112, 104),
                        color2=(60, 62, 58), pattern="woodland"),
    "prison_jumpsuit": _o("橙の囚人服のつなぎ。胸に番号 number、top_tied_waist で上を脱いで袖を腰で結ぶ",
                          _UPPER + ("pelvis",) + _LEGS, "cloth", color=(230, 110, 30),
                          number="0000", top_tied_waist=False),
    "torn_dress": _o("裂けたドレス。style = wedding / evening / sundress、length = knee / floor、train で引きずる裾",
                     ("chest", "torso", "pelvis", "leg_r", "leg_l"), "shell",
                     color=(240, 236, 226), style="wedding", length="floor", train=False),
    "bomb_suit": _o("爆発物処理の防護服。分厚い板入りの上下・高い首の襟・大きなヘルメットと前面のバイザー",
                    _UPPER + ("pelvis", "head") + _LEGS, "hard", armor=HIT_PARTS,
                    color=(40, 60, 50), helmet=True, visor="intact", collar=True),
    "life_vest": _o("橙の救命胴衣。deflated で萎んでしわ、胸に笛",
                    ("chest", "torso"), "shell", color=(240, 110, 30), deflated=False, whistle=True),
    "layered_rags": _o("重ね着したぼろ布。kind = coat（擦り切れたコート）/ robe（僧衣）/ wraps（体に巻いた布）/ loincloth（腰布だけ）",
                       _UPPER + ("pelvis", "leg_r", "leg_l"), "shell", color=(86, 74, 60),
                       color2=(60, 70, 80), kind="coat", layers=2),
    # --- 下半身 ---
    "jeans": _o("ジーンズ。cut = full / shorts、ripped_knees で膝の穴",
                ("pelvis",) + _LEGS, "cloth", color=(50, 60, 85), cut="full", ripped_knees=False),
    "slacks": _o("スラックス（折り目）。short=True で丈が足りずくるぶしが出る",
                 ("pelvis",) + _LEGS, "cloth", color=(48, 50, 58), short=False),
    "work_pants": _o("作業ズボン。cargo で腿のポケット、knee_pads で膝当て",
                     ("pelvis",) + _LEGS, "cloth", color=(70, 62, 48), cargo=True, knee_pads=False),
    "pencil_skirt": _o("タイトスカート（後ろにスリット）。pantyhose で伝線したストッキング",
                       ("pelvis", "leg_r", "leg_l"), "cloth", color=(36, 40, 62), slit=True,
                       pantyhose=True),
    "running_shorts": _o("ランニングパンツ。stripe で脇の線",
                         ("pelvis", "leg_r", "leg_l"), "cloth", color=(30, 30, 34), stripe=True),
    # --- 足 ---
    "sneakers": _o("運動靴。kind = runner / high_top / cleats（スパイク）、color2 は靴底と差し色",
                   ("foot_r", "foot_l"), "gear", color=(230, 230, 230), color2=(60, 60, 60),
                   kind="runner"),
    "boots": _o("ブーツ。kind = work（鉄芯）/ combat（編み上げ）/ rubber（ゴム長）/ fire（消防）/ waders（胸までの胴長）",
                ("foot_r", "foot_l", "shin_r", "shin_l"), "gear", color=(70, 50, 34), kind="work"),
    "dress_shoes": _o("革靴類。kind = oxford / loafer / heels / clog、missing = none / r / l（片方脱げて裸足）",
                      ("foot_r", "foot_l"), "gear", color=(22, 20, 20), kind="oxford", missing="none"),
    # --- 手・腕 ---
    "gloves": _o("手袋。kind = work / rubber / surgical / leather / fingerless / satin、hands = both / r / l",
                 ("hand_r", "hand_l"), "cloth", color=(180, 150, 90), kind="work", hands="both"),
    "wristwatch": _o("腕時計。kind = steel / dress / fitness / gold、cracked で風防のひび",
                     ("forearm_l",), "gear", color=(170, 170, 176), kind="steel", side="l",
                     cracked=False),
    "chain_shackles": _o("手錠・足枷。kind = chain（鎖が垂れて揺れる）/ leather_straps（拘束帯）、broken で千切れた端",
                         ("forearm_r", "forearm_l", "shin_r", "shin_l"), "gear",
                         color=(120, 120, 126), kind="chain", wrists=True, ankles=False,
                         chain_len=4, broken=False),
    "bandage_wrap": _o("巻いた包帯・バンテージ。on = 巻くボーンのリスト",
                       ("forearm_r",), "cloth", color=(220, 214, 196), on=["forearm_r"]),
    "tattoo": _o("入れ墨。on = 描くボーン、motif = tribal / skull / script / koi / barbed",
                 ("arm_r",), "skin", color=(40, 50, 60), on=["arm_r"], motif="tribal"),
    # --- 装備 ---
    "backpack": _o("背負い物。kind = daypack / rucksack（寝袋を括った大型）/ delivery_box（四角い保温配達箱）",
                   ("chest",), "gear", color=(40, 40, 44), kind="daypack", lid_open=False),
    "tool_belt": _o("工具ベルト。tools に下げる道具（hammer / tape / pliers / knife）",
                    ("pelvis",), "gear", color=(110, 80, 50), tools=["hammer", "tape"]),
    "air_tank": _o("背中の空気ボンベと背負い枠。hose で肩越しのホース、mask = hanging（胸に面体）/ none",
                   ("chest",), "gear", color=(190, 190, 196), hose=True, mask="hanging", dented=0),
    "name_badge": _o("名札。style = lanyard（首から下げる）/ clip（胸に留める）/ dogtag（認識票）",
                     ("chest",), "gear", color=(40, 90, 170), style="lanyard"),
    "flashlight": _o("点いた懐中電灯。mount = shoulder / hand。lit で発光と光の円錐（beam の色）",
                     ("chest",), "gear", color=(30, 30, 30), mount="shoulder", lit=True,
                     beam=(255, 240, 200)),
    "riot_shield": _o("透明の大盾（左腕）。表に POLICE、cracked 0..3 で蜘蛛の巣状のひび",
                      ("forearm_l",), "held", color=(180, 200, 210), side="l", text="POLICE",
                      cracked=0, transparent=True),
    "held_tool": _o("手に持った道具。kind = wrench / cleaver / pipe / hammer / scalpel / rebar_sledge"
                    "（鉄筋の先にコンクリ塊）/ fire_axe。持つ腕が broken / cut_* の時は隠す（落とした扱い）",
                    ("hand_r",), "held", color=(150, 150, 156), kind="wrench", hand="r"),
}

# 列挙の引数が取れる値（desc の説明と同じ。自己検査が ZOMBIES の値を照合する）
_OUTFIT_CHOICES = {
    "hair": dict(style=("short", "buzz", "balding", "long", "ponytail", "bun", "bob", "mohawk",
                        "messy", "matted", "shaved")),
    "beard": dict(style=("stubble", "full", "goatee", "mustache")),
    "police_cap": dict(style=("police", "guard")),
    "riot_helmet": dict(visor=("down", "up", "cracked")),
    "helmet_military": dict(cover=("camo", "plain"), chinstrap=("on", "dangling")),
    "firefighter_helmet": dict(visor=("up", "down")),
    "scooter_helmet": dict(visor=("up", "down", "missing"), strap=("on", "dangling")),
    "skull_cap": dict(kind=("surgical", "kitchen", "hairnet")),
    "bridal_veil": dict(length=("short", "long")),
    "gas_mask": dict(lens=("intact", "cracked", "shattered")),
    "surgical_mask": dict(position=("mouth", "chin", "ear")),
    "glasses": dict(kind=("clear", "sun", "thick", "loupe")),
    "headphones": dict(kind=("over_ear", "earbuds"), worn=("head", "neck")),
    "shirt": dict(cut=("dress", "blouse", "flannel", "work"),
                  sleeves=("long", "short", "rolled", "torn_off"),
                  pattern=("plain", "stripe", "check")),
    "t_shirt": dict(cut=("crew", "tank", "jersey"), print=("none", "logo", "band", "number")),
    "hoodie": dict(hood=("down", "up")),
    "suit_jacket": dict(missing_sleeve=("none", "l", "r", "both")),
    "necktie": dict(pattern=("plain", "stripe", "dot")),
    "rain_jacket": dict(hood=("down", "up")),
    "police_uniform": dict(style=("police", "guard")),
    "apron": dict(kind=("cloth", "butcher_leather", "rubber"), length=("waist", "full")),
    "hospital_gown": dict(pattern=("dots", "plain")),
    "riot_armor": dict(coverage=("vest", "full")),
    "camo_fatigues": dict(pattern=("woodland", "urban", "desert")),
    "torn_dress": dict(style=("wedding", "evening", "sundress"), length=("knee", "floor")),
    "bomb_suit": dict(visor=("intact", "cracked", "shattered")),
    "layered_rags": dict(kind=("coat", "robe", "wraps", "loincloth")),
    "jeans": dict(cut=("full", "shorts")),
    "sneakers": dict(kind=("runner", "high_top", "cleats")),
    "boots": dict(kind=("work", "combat", "rubber", "fire", "waders")),
    "dress_shoes": dict(kind=("oxford", "loafer", "heels", "clog"), missing=("none", "r", "l")),
    "gloves": dict(kind=("work", "rubber", "surgical", "leather", "fingerless", "satin"),
                   hands=("both", "r", "l")),
    "wristwatch": dict(kind=("steel", "dress", "fitness", "gold"), side=("l", "r")),
    "chain_shackles": dict(kind=("chain", "leather_straps")),
    "tattoo": dict(motif=("tribal", "skull", "script", "koi", "barbed")),
    "backpack": dict(kind=("daypack", "rucksack", "delivery_box")),
    "tool_belt": dict(tools=("hammer", "tape", "pliers", "knife")),
    "air_tank": dict(mask=("hanging", "none")),
    "name_badge": dict(style=("lanyard", "clip", "dogtag")),
    "flashlight": dict(mount=("shoulder", "hand")),
    "riot_shield": dict(side=("l",)),
    "held_tool": dict(kind=("wrench", "cleaver", "pipe", "hammer", "scalpel", "rebar_sledge", "fire_axe"),
                      hand=("r", "l")),
}
# 専用の子ボーンを持つ部品（壊れて消える物・手に持つ物）。nr_kit はこの名前でボーンを作る。
# 壊れて消える物は gore.breakables に「このボーンは nr:armor >= n の間だけ表示」と書く
_OUTFIT_BONES = {"air_tank": "gear_tank", "flashlight": "gear_flashlight",
                 "riot_shield": "gear_shield", "held_tool": "held_tool"}
for _k, _v in OUTFIT_VOCAB.items():
    _v["choices"] = _OUTFIT_CHOICES.get(_k, {})
    _v["bone"] = _OUTFIT_BONES.get(_k)

# ---------------------------------------------------------------------------
#  腐敗・変異（nr_kit が部品、nr_paint が描き込み）
# ---------------------------------------------------------------------------


def _m(desc, bones, **params):
    return dict(desc=desc, bones=tuple(bones), params=params)


MUTATION_VOCAB = {
    "exposed_ribs": _m("脇腹の皮と肉が裂けて肋骨が count 本のぞく。flesh = 骨に残った肉の量 0..1",
                       ("chest", "torso"), side="l", count=3, flesh=0.3),
    "missing_cheek_teeth": _m("頬が食い破られ、奥歯と歯茎が横から丸見え。size 1..3",
                              ("head", "jaw"), side="l", size=1),
    "bone_spurs": _m("皮膚を突き破って伸びた骨の棘。on のボーンに count 本、長さ length px",
                     ("forearm_r",), on=["forearm_r"], count=2, length=2.0),
    "tumor_cluster": _m("ぶよぶよの腫瘍の房。size 1..3、count 個、色 color",
                        ("torso",), on="torso", size=1, count=3, color=(200, 150, 140)),
    "fungal_growth": _m("皮膚から生えた菌糸の膜とキノコの傘（caps 個）。glow を指定すると傘のひだが発光",
                        ("chest",), on=["chest"], coverage=0.3, color=(200, 190, 150), caps=3,
                        glow=None),
    "bloated_belly": _m("ガスで膨れた腹。size 1..3、veins で浮いた血管、stretch_marks で裂けかけの線",
                        ("torso",), size=2, veins=True, stretch_marks=True),
    "acid_sacs": _m("透けて光る酸の袋。where = neck / cheeks / back / belly、count 個",
                    ("neck", "head"), where="neck", count=2, glow=(150, 255, 60)),
    "elongated_jaw": _m("縦に伸びた顎（length 倍）。split で顎が左右に裂けて開く、teeth = human / needle / tusk",
                        ("head", "jaw"), length=1.3, split=False, teeth="human"),
    "claws": _m("伸びて黒ずんだ爪。length 1..4、hands = both / r / l",
                ("hand_r", "hand_l"), length=1, hands="both", color=(60, 44, 36)),
    "split_face": _m("顔の正中が縦に裂け、中に二列目の歯と赤い肉。depth 1..3、glow で裂け目が発光",
                     ("head",), depth=1, glow=None),
    "exposed_spine": _m("背中の皮が裂けて椎骨が length 個並んで見える。spikes で棘状",
                        ("chest", "torso"), length=6, spikes=False),
    "burn_scars": _m("ケロイド状の火傷痕（テクスチャ）。coverage 0..1",
                     ("head",), on=["head"], coverage=0.3),
    "pustules": _m("膿の詰まった水疱。density 1..3、glow で中が光る（叩くと弾ける見た目）",
                   ("torso",), on=["torso"], density=1, color=(200, 190, 90), glow=None),
    "veins_glowing": _m("皮膚の下で脈打って光る血管。pulse_hz で明滅。only_phase = '能力.段階' を指定すると"
                        "その段階（ability_states の nr:ability の値）の間だけ光る",
                        ("chest",), on=["chest"], color=(120, 255, 200), pulse_hz=1.0,
                        only_phase=None),
    "dark_veins": _m("感染の黒い血管が蜘蛛の巣状に広がる（発光しない）。density 1..3",
                     ("neck",), on=["neck"], color=(60, 20, 40), density=1),
    "eyeless": _m("眼球が無く、眼窩が暗い穴。bleed で頬に血の涙の跡",
                  ("head",), bleed=True),
    "stitches": _m("縫い跡。kind = surgical（細い糸）/ crude（太い糸で雑に）/ staples（ホチキス）",
                   ("torso",), on=["torso"], kind="surgical"),
    "hanging_skin": _m("剥がれて垂れ下がった皮膚の弁（flaps 枚。歩くと揺れる）",
                       ("forearm_l",), on=["forearm_l"], flaps=1),
    "bite_wound": _m("噛み跡（歯形の半月の傷と腫れ）。fresh で鮮血、そうでなければ黒く化膿",
                     ("neck",), on="neck", size=1, fresh=False),
    "missing_nose": _m("鼻が欠け、鼻腔の三角の穴",
                       ("head",)),
    "exposed_skull": _m("頭皮がめくれて頭蓋骨が露出。coverage 0..1",
                        ("head",), coverage=0.3),
    "torn_throat": _m("喉が食い破られ、気管と筋がのぞく。size 1..3",
                      ("neck",), size=1),
    "impaled": _m("体に刺さったままの物。obj = knife / rebar / arrow / glass_shard / pipe、angle 度",
                  ("torso",), obj="knife", on="torso", angle=20),
    "missing_fingers": _m("指が count 本欠けて、骨の先がのぞく",
                          ("hand_l",), hand="l", count=2),
    "throat_sac": _m("喉の下の大きく膨らむ声の袋（叫ぶ時に膨張するアニメ用の子ボーン throat_sac）",
                     ("neck",), size=2, veins=True, glow=None),
    "exposed_lungs": _m("胸の皮が裂けて、叫ぶと膨らむ肺がのぞく",
                        ("chest",), side="both"),
    "bone_plates": _m("骨が板状に盛り上がった天然の装甲（兜・肩当て）。thickness 1..3",
                      ("head",), on=["head"], color=(220, 210, 190), thickness=1),
    "elongated_limbs": _m("異様に長い手足（arms / legs 倍）。extra_joint で前腕にもう一つ関節",
                          ("arm_r", "arm_l"), arms=1.3, legs=1.0, extra_joint=False),
    "fused_bodies": _m("背中と肩から別の感染者の胴（torsos）・頭（heads 個、1..3）・腕（arms）が生える。"
                       "頭は chest の子ボーン extra_head_1..N（gore.breakables で潰れたら消す）",
                       ("chest", "torso"), torsos=2, heads=3, arms=2),
    "bone_blades": _m("前腕の骨が皮を破って伸びた刃。length 1..4",
                      ("forearm_r", "forearm_l"), hands="both", length=2, color=(230, 220, 200)),
    "charred_crust": _m("炭化した殻（テクスチャ＋少し浮いた殻のキューブ）。ember を指定するとひびが光る",
                        ("chest",), coverage=0.8, ember=None),
    "skin_peeled": _m("皮が剥けて赤い筋肉が露出した斑（擦り傷・酸焼け）",
                      ("chest",), on=["chest"], coverage=0.3),
    "waterlogged": _m("水を吸ってふやけ、皮が手袋のように剥がれかけ。algae で藻の斑",
                      ("chest",), coverage=0.8, algae=(70, 110, 60)),
    "explosive_nodes": _m("胸から全身に散った光る結節（count 個。爆発が近いほど速く明滅）",
                          ("chest", "torso"), count=6, glow=(255, 150, 40), pulse_hz=1.5),
    "spore_vents": _m("煙突のような菌の噴出孔（count 個）。胞子 spores の色の粒子を出す",
                      ("chest",), on=["chest"], count=4, spores=(180, 240, 200)),
    "spine_ridge": _m("背骨に沿って並ぶ骨の棘（count 本、長さ length 倍）",
                      ("chest", "torso", "neck"), count=8, length=2.0),
    "muscle_mass": _m("片側だけ異常に肥大した筋肉（factor 倍の太さ）",
                      ("arm_r",), on="arm_r", factor=1.3),
    "metal_fused": _m("肉に食い込んで一体化した金属（plate / rebar / chain）。装甲になる",
                      ("forearm_r",), on=["forearm_r"], kind="plate"),
    "surgical_ports": _m("体に埋め込まれた点滴のポートと千切れた管（tubes 本）",
                         ("chest",), on=["chest"], tubes=4),
    "tendrils": _m("菌糸の触手。where = mouth / back / arms、count 本、長さ length ブロック",
                   ("head",), where="mouth", count=4, length=1.0),
}
_MUTATION_CHOICES = {
    "exposed_ribs": dict(side=("l", "r", "both")),
    "missing_cheek_teeth": dict(side=("l", "r")),
    "acid_sacs": dict(where=("neck", "cheeks", "back", "belly")),
    "elongated_jaw": dict(teeth=("human", "needle", "tusk")),
    "claws": dict(hands=("both", "r", "l")),
    "stitches": dict(kind=("surgical", "crude", "staples")),
    "impaled": dict(obj=("knife", "rebar", "arrow", "glass_shard", "pipe")),
    "missing_fingers": dict(hand=("l", "r")),
    "exposed_lungs": dict(side=("l", "r", "both")),
    "bone_blades": dict(hands=("both", "r", "l")),
    "metal_fused": dict(kind=("plate", "rebar", "chain")),
    "tendrils": dict(where=("mouth", "back", "arms")),
}
# 専用の子ボーン（{where} {n} は引数で埋める）。壊れて消える物は gore.breakables で指す
_MUTATION_BONES = {"throat_sac": "throat_sac", "acid_sacs": "acid_sac_{where}",
                   "fused_bodies": "extra_head_{n}"}
for _k, _v in MUTATION_VOCAB.items():
    _v["choices"] = _MUTATION_CHOICES.get(_k, {})
    _v["bone"] = _MUTATION_BONES.get(_k)

# 変異のうち装甲になるもの（gore.armored の根拠）。on の部位がそのまま装甲の部位
MUTATION_ARMOR = {"bone_plates", "metal_fused"}
_BONE_TO_PART = {"head": "head", "neck": "head", "jaw": "head",
                 "chest": "torso", "torso": "torso", "pelvis": "torso",
                 "arm_r": "arm_r", "forearm_r": "arm_r", "hand_r": "arm_r",
                 "arm_l": "arm_l", "forearm_l": "arm_l", "hand_l": "arm_l",
                 "leg_r": "leg_r", "shin_r": "leg_r", "foot_r": "leg_r",
                 "leg_l": "leg_l", "shin_l": "leg_l", "foot_l": "leg_l"}

# ---------------------------------------------------------------------------
#  攻撃（scripts/zombies/attacks.js とアニメーション animation.nr.z.atk_<鍵>）
# ---------------------------------------------------------------------------
# range = 届く距離（ブロック、体の当たり箱の縁から）、windup / active / recover = tick、
# dmg_mult = spec の damage に掛ける倍率、knockback = (水平, 垂直)、hits = 当たる回数、
# needs = 使う条件（arm = 前腕のある腕が 1 本以上、arms2 = 両腕、arm_r / arm_l = その腕、
# jaw = 顎がある、legs = 這っていない）、fallback = 条件を満たさない時に代わりに使う攻撃、
# effect = ATTACK_EFFECTS の鍵

ATTACK_EFFECTS = {
    "grab":      "掴んで動けなくする（移動速度 0・ジャンプ不可）。hold 秒、攻撃 3 回入力で振りほどける",
    "pin":       "押し倒して上に乗る（pounce_pin の能力で処理）。攻撃 5 回入力で振りほどく",
    "bleed":     "出血。1 ダメージ / 秒を effect_s 秒",
    "poison":    "毒（minecraft:poison 0 段）を effect_s 秒",
    "nausea":    "吐き気（minecraft:nausea）を effect_s 秒",
    "slow":      "鈍足（minecraft:slowness 1 段）を effect_s 秒",
    "stagger_player": "よろめき（鈍足 3 段 + 攻撃不可）を effect_s 秒",
    "knockdown": "倒される（鈍足 255 + 視点が下がるカメラ演出）を effect_s 秒",
    "infect":    "感染。免疫（夜の残り時間）を 10 秒減らす",
    "burn":      "炎上（setOnFire）を effect_s 秒",
}


def _a(desc, range, windup, active, recover, dmg_mult, knockback=(0.3, 0.1), hits=1,
       needs=(), fallback=None, effect=None, effect_s=0.0, **extra):
    d = dict(desc=desc, range=range, windup=windup, active=active, recover=recover,
             dmg_mult=dmg_mult, knockback=knockback, hits=hits, needs=tuple(needs),
             fallback=fallback, effect=effect, effect_s=effect_s)
    d.update(extra)
    return d


ATTACK_VOCAB = {
    "swipe": _a("片腕を横に振り抜く引っかき", 1.6, 8, 3, 10, 1.0, needs=("arm",), fallback="bite"),
    "double_swipe": _a("両腕を交互に二度振り下ろす", 1.7, 10, 8, 14, 0.75, hits=2,
                       needs=("arms2",), fallback="swipe"),
    "grab_bite": _a("両手で肩を掴んで引き寄せ、首に噛みつく", 1.5, 8, 30, 14, 1.4,
                    needs=("arm", "jaw"), fallback="bite", effect="grab", effect_s=1.5,
                    effect2="infect"),
    "bite": _a("首を突き出して噛みつく（腕を失った感染者）", 1.3, 8, 3, 12, 1.2,
               needs=("jaw",), fallback="headbutt", effect="infect"),
    "bite_low": _a("這ったまま足首に噛みつく", 1.4, 10, 3, 14, 1.0, knockback=(0.0, 0.0),
                   needs=("jaw",), fallback="swipe", effect="slow", effect_s=1.0, effect2="infect"),
    "lunge": _a("数歩で一気に間合いを詰めて飛びかかる", 4.0, 6, 6, 16, 1.1, knockback=(0.6, 0.2),
                needs=("legs",), fallback="swipe", dash_speed=0.9),
    "slam": _a("両腕を組んで頭上から叩き下ろす（足元に小さな衝撃）", 2.0, 16, 3, 20, 1.5,
               knockback=(0.8, 0.4), needs=("arms2",), fallback="swipe", aoe=1.2),
    "headbutt": _a("頭を反らしてから額を叩きつける", 1.4, 10, 3, 12, 1.0, knockback=(0.9, 0.2),
                   effect="stagger_player", effect_s=1.0),
    "claw_flurry": _a("爪で四連続の引っかき", 1.8, 6, 16, 14, 0.45, hits=4,
                      needs=("arm",), fallback="bite", effect="bleed", effect_s=3.0),
    "spit": _a("溜めてから放物線で酸の塊（nr:proj_spit）を吐く", 16.0, 16, 2, 16, 1.0,
               knockback=(0.0, 0.0), needs=("jaw",), fallback="swipe", effect="poison",
               effect_s=3.0, min_range=4.0, projectile="nr:proj_spit", proj_speed=1.1),
    "explode": _a("体を震わせて自爆する（威力は能力 detonate の数値）", 3.0, 30, 1, 0, 1.0,
                  knockback=(2.0, 0.6)),
    "scream": _a("正面 60 度へ金切り声の衝撃波", 8.0, 14, 20, 16, 0.3, knockback=(1.6, 0.4),
                 needs=("jaw",), fallback="swipe", effect="slow", effect_s=2.0, cone=60),
    "charge": _a("頭を下げて一直線に突進（壁に当たると能力 rage_charge の気絶）", 20.0, 16, 60, 24, 1.5,
                 knockback=(2.5, 0.6), needs=("legs",), fallback="slam", dash_speed=0.65),
    "throw": _a("瓦礫をもぎ取って放物線で投げる（nr:proj_debris、着弾で半径 1.5 の範囲）", 24.0, 24, 2, 20, 0.8,
                knockback=(1.0, 0.4), needs=("arm",), fallback="slam", min_range=6.0,
                projectile="nr:proj_debris", proj_speed=1.0, aoe=1.5),
    "ground_pound": _a("両拳（か武器）で地面を叩き、輪の衝撃波（中心 1.0 → 縁 0.4 倍）", 4.0, 24, 3, 28, 1.2,
                       knockback=(1.0, 0.5), needs=("arms2",), fallback="stomp", aoe=4.0),
    "pounce": _a("3〜7 ブロック先へ跳びかかり押し倒す（能力 pounce_pin）", 7.0, 10, 12, 16, 1.0,
                 knockback=(0.4, 0.2), needs=("legs",), fallback="lunge", effect="pin",
                 min_range=3.0, leap=(1.2, 0.45)),
    "tool_swing": _a("持った道具を振り下ろす（dtype と効果は held_tool の kind で決まる）", 2.0, 12, 3, 16, 1.3,
                     knockback=(0.6, 0.2), needs=("arm_r",), fallback="swipe"),
    "shield_bash": _a("左腕の盾で殴りつけて押し返す", 1.8, 10, 3, 14, 0.8, knockback=(1.4, 0.3),
                      needs=("arm_l",), fallback="swipe", effect="stagger_player", effect_s=0.8),
    "tackle": _a("肩から体当たりして押し倒す", 3.5, 8, 6, 18, 1.0, knockback=(1.0, 0.3),
                 needs=("legs",), fallback="swipe", effect="knockdown", effect_s=1.0, dash_speed=0.8),
    "grab_throw": _a("掴み上げて 8〜10 ブロック投げ飛ばす", 2.5, 14, 20, 24, 1.2, knockback=(3.0, 0.8),
                     needs=("arm",), fallback="slam", effect="grab", effect_s=1.0),
    "blade_slash": _a("前腕の骨の刃で素早く斬る", 2.6, 6, 4, 10, 1.2, knockback=(0.5, 0.1),
                      needs=("arm",), fallback="bite", effect="bleed", effect_s=4.0),
    "vomit": _a("前方 45 度・3.5 ブロックへ毒の吐瀉物を浴びせ続ける（4 tick ごとに当たる）", 3.5, 16, 24, 20, 0.25,
                knockback=(0.0, 0.0), hits=6, needs=("jaw",), fallback="swipe", effect="poison",
                effect_s=4.0, effect2="nausea", cone=45),
    "stomp": _a("片足で踏み鳴らし、周囲 2 ブロックを揺らす（倒れたプレイヤーへの追い打ち）", 2.0, 14, 3, 18, 1.0,
                knockback=(0.6, 0.6), needs=("legs",), fallback="swipe", aoe=2.0),
    "long_grab": _a("長い腕を伸ばして 3〜6 ブロック先を掴み、引き寄せて噛む（能力 long_grab_drag）", 6.0, 12, 30, 20, 0.6,
                    knockback=(0.0, 0.0), needs=("arm",), fallback="swipe", effect="grab",
                    effect_s=1.5, min_range=3.0),
}

# ---------------------------------------------------------------------------
#  移動（アニメーション animation.nr.z.walk_<鍵> / run_<鍵>）
# ---------------------------------------------------------------------------
# speed（spec）が minecraft:movement の値。歩き回る時は × walk、追う時は × chase。
# step = 段差を自然に越える高さ、jump = 跳べる高さ、gap = 跳び越える隙間（ブロック）、
# climb = 壁を登る素質（実際に登るのは能力 wall_climb を持つ種類）

LOCOMOTION_VOCAB = {
    "shamble": dict(desc="足を引きずる典型的なゾンビ歩き。腕は前か垂れ、頭がぐらぐら揺れる",
                    walk=0.6, chase=1.0, step=0.6, jump=1.0, gap=0, climb=False, footstep="drag"),
    "limp": dict(desc="片脚（nr:variant の偶奇で左右）を引きずり、腰が大きく傾ぐ",
                 walk=0.55, chase=0.9, step=0.6, jump=0.6, gap=0, climb=False, footstep="drag"),
    "stagger": dict(desc="酔ったように不規則によろめき、時々倒れかけて踏みとどまる",
                    walk=0.6, chase=1.0, step=0.6, jump=1.0, gap=0, climb=False, footstep="shuffle"),
    "run": dict(desc="上体を起こしたぎこちない小走り（感染して間もない一般感染者）",
                walk=0.6, chase=1.1, step=1.0, jump=1.0, gap=1, climb=False, footstep="run"),
    "sprint": dict(desc="前傾で腕を振り回す全力疾走。止まる時に滑る",
                   walk=0.55, chase=1.25, step=1.0, jump=1.5, gap=3, climb=True, footstep="run"),
    "crawl": dict(desc="腹ばいで腕だけで体を引きずる（脚の無い・胴が切れた・両脚が折れた時も）",
                  walk=0.5, chase=0.8, step=0.5, jump=0.0, gap=0, climb=False, footstep="crawl"),
    "brute": dict(desc="肩を揺らして地面を踏みしめる重い歩み。足音で地面が揺れる",
                  walk=0.6, chase=1.0, step=1.0, jump=1.0, gap=1, climb=False, footstep="heavy"),
    "stalk": dict(desc="低く身をかがめて忍び寄り、急に速くなる捕食者の歩み",
                  walk=0.5, chase=1.3, step=1.0, jump=2.0, gap=3, climb=True, footstep="soft"),
    "leap": dict(desc="跳ねるように弧を描いて間合いを詰める",
                 walk=0.6, chase=1.2, step=1.0, jump=2.5, gap=4, climb=True, footstep="soft"),
    "waddle": dict(desc="膨れた腹を左右に揺らすよちよち歩き",
                   walk=0.6, chase=0.9, step=0.6, jump=0.5, gap=0, climb=False, footstep="squelch"),
    "lurch": dict(desc="上体を硬直させ、つんのめるように大きく前へ踏み出す",
                  walk=0.6, chase=1.15, step=1.0, jump=1.0, gap=1, climb=False, footstep="shuffle"),
    "scuttle": dict(desc="四つ足で頭を低くした蜘蛛のような這い歩き（壁・天井にも）",
                    walk=0.6, chase=1.25, step=1.0, jump=1.5, gap=2, climb=True, footstep="skitter"),
    "knuckle": dict(desc="長い腕の拳を地面について進むゴリラのような歩き",
                    walk=0.6, chase=1.1, step=1.0, jump=1.0, gap=1, climb=False, footstep="heavy"),
}

# ---------------------------------------------------------------------------
#  特殊能力（scripts/zombies/abilities.js の鍵）
# ---------------------------------------------------------------------------
ABILITY_TRIGGERS = {
    "passive":            "常に有効",
    "on_spawn":           "スポーンした時",
    "on_sight":           "標的が見えた時（視線が通り range 以内）",
    "proximity":          "標的が range 以内に入った時",
    "range_band":         "標的が params の min〜max の距離にいる時",
    "on_hit_taken":       "ダメージを受けた時",
    "on_low_hp":          "体力が params の閾値以下になった時",
    "on_attack_incoming": "range 以内でプレイヤーが攻撃を振った時",
    "weak_spot":          "gore.weak_spots の弱点に当たった時",
    "on_armor_break":     "装甲の段階（nr:armor）が下がった時",
    "on_death":           "死亡処理の時（nr:hp <= 0）",
    "timer":              "params の interval 秒ごと",
    "in_light":           "UV 光（UV ランプ・UV ライト・UV 改造の命中）や明るい光の中",
    "in_dark":            "明るさ params.light_max 以下の場所",
    "on_phase":           "ボスの段階が変わった時",
    "chasing":            "標的を追っている間",
}


def _ab(desc, trigger, cooldown=0.0, range=None, phases=(), anim=False, state="", fx="", **params):
    """能力の語彙の項目。

    trigger  = ABILITY_TRIGGERS の鍵（タプル）
    cooldown = 再使用までの秒、range = 発動を考える距離（ブロック）
    phases   = nr:ability で見せる段階の名前。種類ごとに ability_states(z) が 1..7 の値を
               能力の並び順に割り当てる（0 = 何もしていない）。アニメは
               animation.nr.z.ab_<鍵>_<段階> を nr:ability がその値の間だけ再生する
    anim     = 段階を使わず nr:state で再生する専用アニメ animation.nr.z.ab_<鍵> が要るか
    state    = nr:state / nr:armor / 段階の意味の説明
    fx       = 演出（パーティクル・音）の指示
    params   = 数値（ZOMBIES 側で A(鍵, 引数=...) として上書きできる）"""
    if isinstance(trigger, str):
        trigger = (trigger,)
    return dict(desc=desc, trigger=tuple(trigger), cooldown=cooldown, range=range,
                phases=tuple(phases), anim=bool(anim), state=state, fx=fx, params=params)


ABILITY_VOCAB = {
    # --- 一般感染者 ---
    "shield_block": _ab(
        "左腕の盾で正面 arc 度からの頭・胴・左腕への攻撃を reduction だけ防ぐ（火花）。重い打撃は盾を弾き stagger_s 秒下げさせる。"
        "左腕が broken / 切断か nr:armor = 0 で盾を失う",
        "passive", phases=("lowered",),
        state="lowered = 盾が弾かれて下がっている間。盾（gear_shield）は nr:armor >= 1 かつ左腕が intact / wounded の間だけ表示",
        fx="盾に当たると火花と鈍い金属音", arc=70, reduction=0.9, stagger_s=1.5),
    "armor_shed": _ab(
        "装甲の段階の体力（gore.armor_hp）が尽きるたび nr:armor を 1 下げ、外れた装甲板を gib として飛ばし"
        "（scrap を scrap_chance で落とす）、stagger_s 秒よろめく",
        "on_armor_break", state="よろめきは nr:state stagger（共通のよろめきアニメ）",
        fx="装甲板が飛ぶ・火花・金属の割れる音", stagger_s=1.0, scrap_chance=0.3),
    "tank_burst": _ab(
        "背中のボンベを刺突・射撃・爆発・重い打撃で破ると破裂（一度だけ）。本人は前へ吹き飛んで down_s 秒倒れ、"
        "周り radius の全員に dmg と押し返し",
        "weak_spot", range=2.5,
        state="破裂で nr:armor = 0（gore.breakables の gear_tank が消える）、nr:state down",
        fx="白い噴気と破裂音・金属片", radius=2.5, dmg=4, down_s=2.0),
    "toxic_death_puff": _ab(
        "倒れると防護服の裂け目から溜まった毒ガスが噴き出す（半径 radius・life 秒、中のプレイヤーに poison_s 秒の毒）",
        "on_death", range=2.5, fx="黄緑のガスが噴き出す・空気の抜ける音",
        radius=2.5, life=3.0, poison_s=3.0),
    "tool_wield": _ab(
        "持った道具（outfit の held_tool）で攻撃する: wrench / hammer / pipe / rebar_sledge は blunt、"
        "cleaver / scalpel / fire_axe は slash（scalpel は bleed）。右腕が broken か切断で道具を落とす"
        "（drop_chance で scrap か blades のアイテムになる）",
        "passive", state="held_tool のボーンは持つ腕が broken / cut_* の時に隠す",
        fx="道具が床に落ちる音", drop_chance=0.5),
    "flashlight_beam": _ab(
        "肩の懐中電灯の円錐（cone 度・range）にプレイヤーが dwell 秒入ると、周り alert_radius の感染者が標的を知る（夜のみ）。"
        "胴が slashed 以上になると電灯が割れて消える",
        "passive", range=12.0,
        state="電灯が割れたら nr:armor = 0（gore.breakables の gear_flashlight が消える）",
        fx="光の円錐（パーティクル）、見つけた時に短い唸り", cone=25, dwell=0.5, alert_radius=16),
    "ash_puff": _ab(
        "打撃を受けると chance で、切断では必ず、灰の雲（半径 radius）。中のプレイヤーは blind_s 秒の盲目",
        "on_hit_taken", cooldown=3.0, range=1.5, fx="灰色の粉の雲・乾いた崩れる音",
        chance=0.3, radius=1.5, blind_s=1.5),
    "ankle_grab": _ab(
        "車の下や瓦礫の陰で動かずに待ち、range 以内を通ったプレイヤーの足首を掴む:"
        " hold 秒動けず、bite_dmg の噛みつき。攻撃で振りほどける",
        ("on_spawn", "proximity"), cooldown=6.0, range=1.8, phases=("lurk", "grab"),
        state="lurk = 伏せて動かず声も出さない、grab = 足首を掴んでいる",
        hold=1.2, bite_dmg=2),
    # --- 俊敏型 ---
    "wall_climb": _ab(
        "追跡中に壁で道が塞がれたら、max_height ブロックまでの垂直な壁を climb_speed（ブロック/tick）で登り、"
        "縁で pull_ticks かけてよじ登る",
        "chasing", anim=True, state="nr:state climb の間 ab_wall_climb をループ（縁でよじ登る動きを含む）",
        max_height=8, climb_speed=0.18, pull_ticks=10),
    "pack_flank": _ab(
        "同じ種類が radius 以内に 2 体以上いると、1 体が正面から突っ込み、残り（最大 max_flankers）が左右 flank_angle 度に"
        "回り込んで commit_dist で一斉に襲う",
        "on_sight", cooldown=6.0, range=12.0, radius=12, flank_angle=70, max_flankers=3,
        commit_dist=4),
    "pounce_pin": _ab(
        "min〜max ブロックで跳びかかり（攻撃 pounce）、当たればプレイヤーを押し倒して pin_s 秒動けなくし、"
        "bite_interval 秒ごとに bite_dmg。攻撃 escape_hits 回で振りほどく（振りほどくと相手がよろめく）",
        "range_band", cooldown=10.0, range=7.0, phases=("pin",),
        state="跳びかかりは攻撃 pounce のアニメ。pin = 押さえ込んで噛んでいる",
        fx="押し倒しのカメラ揺れ・噛む音", min=3.0, max=7.0, pin_s=2.5, bite_dmg=2,
        bite_interval=0.5, escape_hits=5),
    "ceiling_ambush": _ab(
        "暗い屋内では天井・壁に張り付いて待ち、真下 detect_radius に来たプレイヤーに落ちてきて"
        "dmg_mult 倍の一撃と slow_s 秒の鈍足",
        "proximity", cooldown=15.0, range=4.0, phases=("hang", "drop"),
        state="hang = 天井に逆さに張り付いて待つ（nr:state climb）、drop = 落下して襲う",
        fx="落ちる前に天井から砂ぼこり・かすれた息", detect_radius=4.0, dmg_mult=1.5, slow_s=1.0),
    "dodge": _ab(
        "range 以内でプレイヤーが攻撃を振ると chance で横へ dist ブロック跳んで避ける（iframes tick の無敵）",
        "on_attack_incoming", cooldown=2.5, range=3.0, phases=("dodge",),
        state="dodge = 横跳び（向きは nr:variant でなく跳んだ向きをスクリプトが体の回転で表す）",
        chance=0.35, dist=1.6, iframes=6),
    "parkour_chase": _ab(
        "プレイヤーが gain ブロック以上高い所にいる時、乗り越え（vault_h まで）・壁登り・gap ブロックの隙間跳びで"
        "屋根から屋根へ追う。屋上では速さ × roof_speed",
        "chasing", phases=("vault",), state="vault = 障害物の乗り越え（登りは wall_climb の nr:state climb）",
        gain=3, vault_h=1.5, gap=3, roof_speed=1.15),
    "frenzy": _ab(
        "体力が hp_below 以下で攻撃を受けると duration 秒の狂乱: 速さ × speed、攻撃力 × damage、攻撃間隔 × interval、"
        "よろめかない。全身の血管が赤く光る",
        ("on_hit_taken", "on_low_hp"), cooldown=20.0, phases=("frenzy",),
        state="frenzy = 狂乱中（veins_glowing の only_phase='frenzy.frenzy' が光る）",
        fx="赤い湯気・荒い息の叫び", hp_below=0.6, duration=6.0, speed=1.4, damage=1.3, interval=0.6),
    "play_dead": _ab(
        "スポーン時は死体のふり（声を出さない）。wake_radius に来るか攻撃されると跳ね起きて "
        "wake_damage_mult 倍の不意打ち。体力が refake_hp 以下になると refakes 回まで倒れたふりをし直す",
        ("on_spawn", "proximity", "on_low_hp"), range=3.0, phases=("feign", "rise"),
        state="feign = 死体のふり（nr:state down と同時）、rise = 跳ね起き", wake_radius=3.0,
        wake_damage_mult=1.5, refake_hp=0.4, refakes=1),
    "flee_bolt": _ab(
        "flee_radius 以内でプレイヤーを見ると、速さ × flee_speed でジグザグに逃げる。escape_s 秒見失われると消える（逃げ切り）",
        "on_sight", range=16.0, flee_radius=16, flee_speed=1.3, escape_s=30),
    "toxic_trail": _ab(
        "逃げている間 interval 秒ごとに足元へ毒のもや（半径 radius・life 秒、中のプレイヤーに poison_s 秒の毒）",
        "chasing", fx="黄緑のもや", interval=1.0, radius=1.2, life=4.0, poison_s=2.0),
    # --- 特殊感染者 ---
    "howl_alarm": _ab(
        "標的を見ると立ち止まり windup 秒喉の袋を膨らませて遠吠え: alert_radius 以内の感染者全員に標的を知らせ、"
        "spawn 体（pool から）を spawn_dist の見えない所に呼ぶ。夜は追跡レベル + chase_add。"
        "溜め中に喉（weak_spot）を撃たれると中断",
        "on_sight", cooldown=20.0, range=24.0, phases=("inflate", "howl"),
        state="inflate = 喉の袋（throat_sac）が膨らむ溜め、howl = 遠吠え",
        fx="音の輪（白い輪のパーティクル）・遠吠え", windup=1.0, alert_radius=32,
        spawn=(2, 4), spawn_dist=(16, 24), pool=["sprinter", "leaper", "brawler"],
        chase_add=1, max_alive_spawned=6),
    "keep_distance": _ab(
        "標的と min〜max の距離を保つ。min より近いと速さ × retreat_speed で後ずさる",
        "chasing", min=6.0, max=14.0, retreat_speed=1.2),
    "sac_rupture": _ab(
        "喉・首の袋に当たると破裂（一度だけ）: その一撃は弱点倍率、kind（bile / acid）の液が radius に飛び散り dmg。"
        "以後 howl_alarm / acid_spit は使えない",
        "weak_spot", range=2.0,
        state="破裂で nr:armor = 0（gore.breakables の throat_sac / acid_sac_* が消える）",
        fx="袋の破裂・液のしぶき", kind="bile", radius=2.0, dmg=2),
    "acid_spit": _ab(
        "min〜max ブロックの標的へ windup 秒（袋が膨らむ）溜めて酸を吐く（攻撃 spit。弾 proj、着弾で dmg と acid_puddle）。"
        "体力 burst_hp 以下では 3 連射",
        "range_band", cooldown=4.0, range=16.0, state="吐く動作は攻撃 spit のアニメ",
        fx="緑の酸の弾と尾", min=4.0, max=16.0, windup=0.8, proj="nr:proj_spit",
        proj_speed=1.1, dmg=4, burst_hp=0.3),
    "acid_puddle": _ab(
        "酸が着弾した所と死体の下に酸だまり（半径 radius・life 秒）。中にいると interval 秒ごとに tick_dmg",
        ("passive", "on_death"), range=1.5, fx="泡立つ緑の水たまり・じゅうじゅう音",
        radius=1.5, life=6.0, tick_dmg=1, interval=0.5),
    "ground_pound": _ab(
        "標的が range 以内で windup 秒振りかぶり、地面を叩いて半径 radius の衝撃波（攻撃 ground_pound）。"
        "ガラス・軽いブロック（nr の瓦礫）を壊す",
        "proximity", cooldown=8.0, range=4.0, state="叩く動作は攻撃 ground_pound のアニメ",
        fx="土煙の輪・瓦礫の破片・カメラ揺れ", windup=1.2, radius=4.0, shake=0.6),
    "heavy_body": _ab(
        "押し返し耐性 knockback_resist。light / medium の武器ではよろめかず、ドロップキックでも倒れない。"
        "heavy の武器・爆発だけがよろめかせる",
        "passive", knockback_resist=0.95),
    "rage_charge": _ab(
        "min〜max ブロック先の標的に、windup 秒吠えてから一直線に突進（攻撃 charge、最長 max_s 秒）。"
        "壁・硬いブロックにぶつかると stun_s 秒気絶（背中が弱点の好機）",
        "range_band", cooldown=10.0, range=20.0,
        state="吠えと突進は攻撃 charge のアニメ。壁で気絶 = nr:state stagger",
        fx="足元の土煙・突進の地響き・壁に当たる衝撃", min=6.0, max=20.0, windup=0.8,
        max_s=3.0, stun_s=3.0),
    "debris_throw": _ab(
        "min〜max ブロック先の標的に、windup 秒で地面から瓦礫をもぎ取り投げる（攻撃 throw、dmg、着弾の範囲 splash）",
        "range_band", cooldown=7.0, range=24.0, phases=("lift",),
        state="lift = 瓦礫をもぎ取って頭上に掲げる（hand_r の子ボーン held_debris をこの段階だけ表示）。投げは攻撃 throw",
        fx="地面が割れる破片・瓦礫の尾の砂", min=6.0, max=24.0, windup=1.2, dmg=8, splash=1.5),
    "gas_cloud_death": _ab(
        "死ぬか、腹（weak_spot）を刺突・斬撃で破られると即座に破裂して死に、半径 radius・life 秒の毒ガス"
        "（毒 poison_amp 段 poison_s 秒＋吐き気 nausea_s 秒、視界がかすむ）",
        ("on_death", "weak_spot"), range=4.0, fx="膨らむ黄緑の濃いガス・破裂の水っぽい爆音",
        radius=4.0, life=8.0, poison_amp=1, poison_s=4.0, nausea_s=4.0),
    "pustule_pop": _ab(
        "攻撃を受けるたび chance で膿疱が弾け、打った相手の方向 radius に毒液（poison_s 秒の毒）",
        "on_hit_taken", range=1.5, fx="黄色い膿のしぶき", chance=0.4, radius=1.5, poison_s=2.0),
    "detonate": _ab(
        "trigger_r 以内に近づくと fuse 秒（結節が速く明滅しビープが速まる）で自爆。死ぬと death_fuse 秒で爆発、"
        "火・爆発・結節（weak_spot）への命中で即爆発。半径 radius、中心で dmg（距離で減る）、感染者には × infected_mult",
        ("proximity", "on_death", "weak_spot"), range=3.0, phases=("fuse",),
        state="fuse = 起爆までの震え（explosive_nodes の明滅が 4 倍速）。爆発の瞬間は攻撃 explode",
        fx="橙の閃光・爆風・肉片の雨・耳鳴り", trigger_r=3.0, fuse=1.5, death_fuse=0.5,
        radius=4.0, dmg=12, infected_mult=2.0),
    "bone_plate": _ab(
        "骨の兜（gore.armored の head）が正面 deflect_arc 度の斬撃・刺突を弾く。打撃で割れると stun_s 秒よろめき、"
        "頭がむき出しになる",
        "passive", state="骨の兜は armor_head ボーン（nr:armor で消える）",
        fx="骨に当たる硬い音・骨の破片", deflect_arc=90, stun_s=2.0),
    "long_leap": _ab(
        "min〜max ブロック先へ crouch 秒しゃがんで大跳躍（屋根にも届く）。着地の周り radius に dmg_mult 倍の一撃",
        "range_band", cooldown=6.0, range=20.0, phases=("crouch", "air"),
        state="crouch = 踏み切りのしゃがみ、air = 空中（手足を広げる）",
        fx="踏み切りの土煙・着地の衝撃", min=8.0, max=20.0, crouch=0.5, radius=2.0, dmg_mult=1.3),
    "keen_scream": _ab(
        "標的が range 以内か、hits_window 秒に 3 回打たれると、正面 cone 度の金切り声（攻撃 scream）で吹き飛ばし、"
        "slow_s 秒の鈍足と画面揺れ",
        ("proximity", "on_hit_taken"), cooldown=12.0, range=6.0, state="叫びは攻撃 scream のアニメ",
        fx="空気の歪み（白い輪）・耳鳴り", cone=60, hits_window=2.0, slow_s=2.0),
    "reanimate": _ab(
        "interval 秒ごとに radius 以内の死体（nr:state dead で、頭が severed / crushed でなく、胴が halved でない）を "
        "max 体まで選び、channel 秒の詠唱（菌糸の触手が伸びる）で体力 revive_hp の割合で蘇らせる（失った部位はそのまま）。"
        "詠唱中に最大体力の interrupt 以上のダメージか火で中断",
        "timer", cooldown=15.0, range=16.0, phases=("chant",),
        state="chant = 両腕を広げて詠唱（tendrils が伸びる）",
        fx="死体へ伸びる青緑の光の筋・胞子・低い詠唱", interval=15.0, radius=16.0, max=2,
        channel=2.0, revive_hp=0.5, interrupt=0.15),
    "spore_cloud": _ab(
        "標的が range 以内か打たれた時、自分の周り半径 radius・life 秒の胞子の雲。中のプレイヤーは nausea_s 秒の吐き気と、"
        "免疫の減りが × immunity_drain",
        ("proximity", "on_hit_taken"), cooldown=14.0, range=10.0, phases=("vent",),
        state="vent = 体を震わせて噴出孔から胞子を噴く", fx="漂う発光胞子・吹き出す音",
        radius=3.5, life=6.0, nausea_s=4.0, immunity_drain=3.0),
    "enrage_unarmored": _ab(
        "装甲が 0（nr:armor = 0）になると吠えて怒り狂い、以後ずっと速さ × speed、攻撃間隔 × interval",
        "on_armor_break", phases=("roar",), state="roar = 激昂の咆哮（一度だけ）。以後の激昂は nr:armor = 0 で分かる",
        fx="吠える・湯気", speed=1.5, interval=0.7),
    "long_grab_drag": _ab(
        "min〜max ブロック先の標的を長い腕で掴み（攻撃 long_grab）、pull ブロック引き寄せて hold 秒押さえ噛む。"
        "掴んでいる腕に最大体力の release 以上のダメージか切断で放す",
        "range_band", cooldown=7.0, range=6.0, phases=("drag",),
        state="腕を伸ばすのは攻撃 long_grab のアニメ、drag = 引き寄せて噛んでいる",
        min=3.0, max=6.0, pull=3.0, hold=1.5, release=0.15),
    # --- 夜の捕食者 ---
    "uv_weak": _ab(
        "UV 光の中では resist.uv × dps のダメージ/秒、stagger_after 秒で怯み、光から flee_s 秒逃げる。"
        "UV の安全地帯（UV ランプの範囲）には入らない",
        "in_light", phases=("burn",), state="burn = 腕で目を覆って身をよじる（nr:state stagger と同時）",
        fx="皮膚から煙・焼ける音", dps=4.0, stagger_after=0.5, flee_s=3.0),
    "chase_call": _ab(
        "夜に標的を見つけると叫んで追跡レベルを + add（最大 4）し、radius 以内の夜の捕食者を呼ぶ",
        "on_sight", cooldown=15.0, range=32.0, phases=("call",), state="call = 天を仰いで叫ぶ",
        fx="遠くまで響く金切り声・HUD の追跡警告", add=1, radius=48),
    "shadow_cloak": _ab(
        "明るさ light_max 以下で懐中電灯・UV に照らされていないと、ほぼ透明になる（光る目だけ見える）。"
        "明るい所では姿が見え、速さ × lit_speed",
        ("in_dark", "passive"), phases=("cloaked",),
        state="cloaked = 透明化中（レンダーコントローラが本体を隠し目だけ描く。攻撃の段階に変われば姿が出る）",
        fx="姿が消える時の黒い霧", light_max=7, lit_speed=0.8),
    "ambush_strike": _ab(
        "透明化中にプレイヤーの背後（向きの差 behind_angle 度以上）range 以内に入ると、dmg_mult 倍の一撃と bleed_s 秒の出血",
        "proximity", cooldown=8.0, range=3.0, state="攻撃のアニメを使う（その瞬間は cloaked が解けて姿が出る）",
        behind_angle=110, dmg_mult=2.0, bleed_s=3.0),
    "ember_aura": _ab(
        "周り radius の生き物を interval 秒ごとに fire_s 秒燃やす。素手で殴った相手も燃える。雨の中では半径が半分",
        "passive", range=2.0, fx="舞う火の粉・ちりちり燃える音", radius=2.0, interval=1.0, fire_s=2.0),
    "fire_trail": _ab(
        "走った跡の足元が life 秒燃える（ブロックの火は置かない。スクリプトの当たり判定で interval 秒ごとに tick_dmg と炎上）",
        "chasing", fx="足跡に残る炎のパーティクル", life=3.0, interval=0.5, tick_dmg=1),
    "hive_summon": _ab(
        "夜、標的が range 以内なら interval 秒ごとに背中の胞子袋から count 体（pool から）を産み落とす（同時に max_alive まで）",
        "timer", cooldown=20.0, range=24.0, phases=("birth",),
        state="birth = 身をかがめ背中の袋が裂ける", fx="袋が裂ける粘液の音・胞子",
        interval=20.0, count=(2, 3), pool=["sprinter", "wallcrawler"], max_alive=6),
    # --- ボス ---
    "boss_phases": _ab(
        "体力の割合が thresholds を下回るたび次の段階へ: roar_s 秒の無敵の咆哮、ボスバーの色が変わり、"
        "攻撃間隔 × interval_step、速さ × speed_step（段階ごとに掛かる）",
        "on_phase", phases=("roar",), state="roar = 段階移行の咆哮", fx="衝撃波の輪・画面揺れ",
        thresholds=(0.6, 0.3), roar_s=2.0, interval_step=0.85, speed_step=1.1),
    "multi_head": _ab(
        "背中の余分な頭（heads 個。fused_bodies の extra_head_1..N）が弱点: 各頭は最大体力の head_hp 割合を持ち、"
        "当たると × head_mult。頭を潰すたび stun_s 秒怯み、攻撃力 × dmg_step。全部潰すと最終段階へ",
        "weak_spot",
        state="潰すたび nr:armor を 1 下げる（extra_head_n は gore.breakables で nr:armor >= n の間だけ表示）。怯みは nr:state stagger",
        fx="頭が弾ける脳と血の噴水", heads=3, head_hp=0.08, head_mult=2.0, stun_s=2.0, dmg_step=0.9),
    "tumor_spawn": _ab(
        "interval 秒ごとに腫瘍の袋を落とし、fuse 秒で裂けて pool から count 体が這い出す。袋は撃てば潰せる",
        "timer", cooldown=18.0, range=24.0, phases=("drop",), state="drop = 身をよじって腫瘍の袋を振り落とす",
        fx="袋が脈打つ・裂けて粘液", interval=18.0, fuse=2.0, count=2, pool=["crawler"]),
    "grab_throw_player": _ab(
        "標的が range 以内で掴み上げ（攻撃 grab_throw）、hold 秒で 8〜10 ブロック投げる。手を攻撃すると放す",
        "proximity", cooldown=12.0, range=3.0, state="攻撃 grab_throw のアニメ",
        hold=1.0, throw_h=3.0, throw_v=0.8, dmg=10),
    "regenerate": _ab(
        "delay 秒ダメージを受けないと毎秒最大体力の hp_per_s を回復。切られた腕は regrow_s 秒で生え戻る（gore.regrow）。"
        "切断後 burn_window 秒以内に断面へ火を当てると生えない。火・電気・UV を受けると suppress_s 秒回復が止まる",
        "passive", phases=("regrow",), state="regrow = 腕が生え戻る瞬間の身震い（直後に nr:arm_* を intact に戻す）",
        fx="断面から伸びる肉の糸・湿った音",
        hp_per_s=0.01, delay=3.0, regrow_s=20.0, burn_window=5.0, suppress_s=8.0),
    "blade_dash": _ab(
        "min〜max ブロック先へ crouch 秒かがんで一直線に dist ブロック駆け抜け、通り道の全員を斬る"
        "（dmg_mult 倍・bleed_s 秒の出血）。第 2 段階以降は chain 回続けて",
        "range_band", cooldown=6.0, range=12.0, phases=("crouch", "dash"),
        state="crouch = 刃を構えてかがむ、dash = 駆け抜け", fx="残像・斬撃の白い弧",
        min=4.0, max=12.0, crouch=0.4, dist=10.0, dmg_mult=1.2, bleed_s=4.0, chain=2),
    "uv_shatter": _ab(
        "UV 光を exposure 秒浴びるか段階が変わると叫び、radius 以内の UV ランプ（nr:uv_lamp）を off_s 秒消し、"
        "UV ライトを jam_s 秒使えなくする",
        ("in_light", "on_phase"), cooldown=30.0, range=24.0, phases=("shriek",),
        state="shriek = 胸を反らして叫ぶ（裂けた顔が開く）",
        fx="ガラスの割れる音・ランプの火花・画面の歪み", exposure=1.0, radius=24.0, off_s=8.0,
        jam_s=5.0),
    "summon_volatiles": _ab(
        "段階が変わった時と interval 秒ごとに、count 体の pool を dist ブロック先の屋上から呼ぶ（同時に max_alive まで）",
        ("on_phase", "timer"), cooldown=40.0, range=32.0, phases=("call",), state="call = 遠吠えで呼ぶ",
        fx="遠吠えの応答", interval=40.0, count=2, pool=["volatile"], dist=(20, 30), max_alive=4),
}

# ---------------------------------------------------------------------------
#  声（gen_nr_sounds が合成。効果音 nr.z.<voice>.<idle|alert|attack|hurt|death>）
# ---------------------------------------------------------------------------
# f0 = 基本周波数の範囲 Hz（None は声帯音なし）、vowel = 口の形（フォルマント）、noise = 息・雑音の量、
# rough = ざらつき（ジッタ・サブハーモニクス）、extra = 重ねる層。spec の voice_pitch で全体を移調する。
VOICE_EVENTS = ("idle", "alert", "attack", "hurt", "death")
VOICE_VOCAB = {
    "groan_male":   dict(desc="喉の奥の低いうめき。ゆっくり上下する", f0=(85, 130), vowel="o",
                         noise=0.35, rough=0.6, extra=()),
    "groan_female": dict(desc="かすれた高めのうめき・すすり泣き混じり", f0=(150, 230), vowel="a",
                         noise=0.3, rough=0.5, extra=()),
    "groan_old":    dict(desc="震える息の多い老いたうめき（6Hz の震え）", f0=(75, 115), vowel="u",
                         noise=0.55, rough=0.4, extra=("tremolo",)),
    "sob":          dict(desc="しゃくり上げるすすり泣きが途中でうめきに崩れる", f0=(180, 320), vowel="a",
                         noise=0.3, rough=0.3, extra=("hiccup",)),
    "wet_choke":    dict(desc="喉に血が詰まったごぼごぼした詰まり声", f0=(90, 160), vowel="e",
                         noise=0.5, rough=0.7, extra=("bubbles",)),
    "gurgle":       dict(desc="水の中で叫ぶようなこもった泡の声", f0=(60, 100), vowel="u",
                         noise=0.6, rough=0.6, extra=("bubbles", "lowpass")),
    "rasp_dry":     dict(desc="焼けた喉の乾いたひび割れたかすれ声", f0=(80, 120), vowel="a",
                         noise=0.7, rough=0.9, extra=("crackle",)),
    "muffled":      dict(desc="マスク越しのこもったうめきと呼吸器のしゅうしゅう音", f0=(85, 140), vowel="o",
                         noise=0.35, rough=0.5, extra=("lowpass", "respirator")),
    "snarl":        dict(desc="吠えるような短い荒い唸りと咆哮（男の俊敏型）", f0=(140, 280), vowel="a",
                         noise=0.4, rough=0.9, extra=()),
    "shriek_high":  dict(desc="耳を刺す甲高い金切り声", f0=(350, 950), vowel="i",
                         noise=0.3, rough=0.7, extra=()),
    "hiss":         dict(desc="息だけの長い威嚇の音と舌打ち", f0=None, vowel="s",
                         noise=0.95, rough=0.2, extra=("clicks",)),
    "chitter":      dict(desc="毎秒 18 回ほどの細かい歯鳴りとさえずり", f0=(600, 1400), vowel="i",
                         noise=0.5, rough=0.4, extra=("clicks",)),
    "howl":         dict(desc="喉の袋で共鳴するサイレンのような上昇する遠吠え", f0=(220, 750), vowel="o",
                         noise=0.2, rough=0.4, extra=("sac_resonance", "rise")),
    "retch":        dict(desc="えずき・吐き戻しの痙攣と液体の飛び散る音", f0=(100, 220), vowel="e",
                         noise=0.6, rough=0.8, extra=("splatter",)),
    "roar_deep":    dict(desc="胸を震わせる低い咆哮と重低音", f0=(45, 90), vowel="o",
                         noise=0.4, rough=0.8, extra=("subbass",)),
    "roar_giant":   dict(desc="何体分ものうめきが少しずつずれて重なる巨大な咆哮", f0=(30, 70), vowel="o",
                         noise=0.4, rough=0.9, extra=("subbass", "choir4")),
    "whimper":      dict(desc="上ずっていく泣き声に、速まる電子音のような脈動が重なる", f0=(220, 480), vowel="i",
                         noise=0.3, rough=0.5, extra=("beep_rise",)),
    "wail":         dict(desc="大きくうねる泣き叫び（ビブラートで上下に揺れる）", f0=(400, 1300), vowel="a",
                         noise=0.25, rough=0.5, extra=("vibrato",)),
    "whisper_rasp": dict(desc="ささやき声の詠唱が 0.5Hz の律動で繰り返される", f0=None, vowel="a",
                         noise=0.9, rough=0.5, extra=("chant",)),
    "click":        dict(desc="暗闇で獲物を探る舌打ち（反響定位）と細い吐息", f0=None, vowel="k",
                         noise=0.6, rough=0.2, extra=("clicks", "echo")),
    "volatile_screech": dict(desc="唸りと金切り声が何層にも重なる捕食者の叫び", f0=(250, 1600), vowel="a",
                             noise=0.4, rough=0.9, extra=("growl_layer", "echo")),
    "crackle":      dict(desc="焚き火のはぜる音に低い唸りが混じる", f0=(70, 140), vowel="o",
                         noise=0.7, rough=0.8, extra=("crackle", "fire")),
    "drone":        dict(desc="虫の羽音のような低いうなりと湿ったうめき", f0=(110, 180), vowel="u",
                         noise=0.5, rough=0.6, extra=("buzz",)),
    "distorted":    dict(desc="金属的にゆがんだ（リング変調の）叫び。人の声の名残がある", f0=(300, 900), vowel="a",
                         noise=0.3, rough=0.7, extra=("ringmod",)),
}

# ---------------------------------------------------------------------------
#  ゴアの例外（gore 辞書の鍵）
# ---------------------------------------------------------------------------
GORE_KEYS = {
    "armored":      "装甲で守られた部位のリスト（HIT_PARTS）。守られている間は armor_mult だけが体力へ通り、"
                    "切断・部位の状態は進まない。装甲の根拠になる服（armor）か変異（bone_plates / metal_fused）が必要",
    "armor_stages": "装甲の段階の初期値 = nr:armor の初期値（0..3）。装甲が無ければ 0",
    "armor_hp":     "1 段階の装甲の耐久（ダメージ点）。尽きると nr:armor が 1 下がる（能力 armor_shed）",
    "armor_strip":  "{部位: 段階} その部位は nr:armor >= 段階の間だけ守られる（表示も同じ）。無い部位は 1",
    "armor_mult":   "装甲越しに体力へ通る割合",
    "armor_break":  "{dtype: 倍率} 装甲の耐久の削れやすさ（打撃と爆発で剥がれ、刃と弾は滑る）",
    "breakables":   "{ボーン名: 段階} 装甲以外の壊れて消える部品（ボンベ・声の袋・懐中電灯・盾・余分な頭）。"
                    "そのボーンは nr:armor >= 段階の間だけ表示。ボーン名は語彙の bone（part_bones(z)）。"
                    "装甲の無い種類では nr:armor を「残っている部品の段階」として使う（initial_armor(z) で初期化）",
    "no_sever":     "切断されない部位（腕・脚は broken まで、頭は cracked まで、胴は gutted まで）",
    "sever_mult":   "切断の起きやすさの倍率（脆い = >1、太い骨 = <1）",
    "bleed_mult":   "血の量の倍率（噴水の長さ・血だまり・しぶき）",
    "blood":        "血の種類（BLOOD_VOCAB の鍵）",
    "crumble":      "True: 切られた部位・gib が炭の塊になって崩れ、血の噴水の代わりに灰が舞う",
    "explode":      "True: 死ぬと体が破裂して全身が gib になる（死体は残らない）。ダメージや雲は能力が出す",
    "explode_kind": "破裂の見た目: none / toxic / blast / acid / spores / water",
    "wet_burst":    "True: 頭が crushed・胴が halved の時に大量の体液が噴き出す（水死体・膨れた体）",
    "weak_spots":   "弱点のリスト: dict(part=当たり箱の部位, zone=WEAK_ZONES の鍵, mult=ダメージ倍率, "
                    "ability=当たった時に発動する能力の鍵か None, once=一度だけか)",
    "halve":        "False なら胴が halved にならない（gutted 止まり）",
    "head_mult":    "頭へのダメージ倍率",
    "pre_damage":   "{部位 or 'state': 値} スポーン時から壊れている部位（PROPERTY_ENUMS の値）",
    "regrow":       "{部位: 秒} 切断された部位が生え戻るまでの秒数（能力 regenerate）",
    "gib_extra":    "死んだ時に追加で出す汎用 gib の nr:part（11 腸 / 12 脳 / 13 肉片 / 14 骨 / 15 臓器）",
    "corpse":       "死体の後始末: normal（設定の秒数で消える）/ ash（崩れて灰）/ burst（破れた皮だけ）/ melt（酸で溶ける）",
    "stagger_frac": "一撃で最大体力のこの割合を超えるとよろめく",
    "crawl_legless": "脚を失ったら這う（False ならその場で倒れて動けない）",
}
GORE_DEFAULTS = dict(
    armored=[], armor_stages=0, armor_hp=0, armor_strip={}, armor_mult=0.25,
    armor_break=dict(slash=0.4, blunt=1.5, pierce=0.5, blast=2.0, fire=0.3, shock=0.5, toxic=0.0),
    breakables={}, no_sever=[], sever_mult=1.0, bleed_mult=1.0, blood="red", crumble=False, explode=False,
    explode_kind="none", wet_burst=False, weak_spots=[], halve=True, head_mult=2.0,
    pre_damage={}, regrow={}, gib_extra=[], corpse="normal", stagger_frac=0.25,
    crawl_legless=True,
)
EXPLODE_KINDS = ("none", "toxic", "blast", "acid", "spores", "water")
CORPSE_KINDS = ("normal", "ash", "burst", "melt")
# 弱点のゾーン（当たり箱の中のどこか。スクリプトが当たった点で判定）
WEAK_ZONES = {
    "throat": "頭の箱の下 40% と胴の箱の上端、正面側（喉・首の袋）",
    "back":   "胴の箱の背中側の半分（ボンベ・背骨・突進後の背中）",
    "belly":  "胴の箱の正面・下半分（膨れた腹）",
    "nodes":  "胴の箱の正面（光る結節）。どの部位でも射撃・刺突の命中なら可",
    "heads":  "胴の箱の背中側の上半分と肩（余分な頭）",
    "any":    "その部位の箱のどこでも",
}

# ---------------------------------------------------------------------------
#  エントリの組み立て補助
# ---------------------------------------------------------------------------
ZOMBIE_FIELDS = (
    "key", "ja", "en", "cls", "height_cm", "heads", "bulk", "limb", "hunch", "arm_len",
    "decay", "skin", "outfit", "mutations", "eyes", "hp", "speed", "damage", "attack",
    "locomotion", "resist", "gore", "abilities", "spawn", "loot", "voice",
    "bestiary_ja", "bestiary_en", "weakness_ja", "weakness_en",
)
# 任意の項目（_z が既定値を入れる）
ZOMBIE_OPTIONAL_FIELDS = {
    "attacks":          "主攻撃 attack 以外に使う攻撃（ATTACK_VOCAB の鍵のリスト）",
    "female":           "女性の骨格（rig の Build.female）",
    "digitigrade":      "踵の浮いた獣の脚（rig の Build.digitigrade）",
    "tone":             "生前の肌色 0..4（SKIN_TONES）",
    "voice_pitch":      "声の移調の倍率",
    "knockback_resist": "minecraft:knockback_resistance の値 0..1",
    "xp":               "倒した時の経験値（スクリプトが出す）",
    "aggro":            "標的を追う距離（ブロック。minecraft:follow_range）",
    "accent":           "図鑑・HUD の差し色 (R, G, B)",
    "boss":             "ボスだけ: dict(bar=(R, G, B), arena=半径, title_ja, title_en)",
}


def O(key, **params):
    """服・装備の部品 (OUTFIT_VOCAB の鍵, 引数)。"""
    return (key, params)


def M(key, **params):
    """変異 (MUTATION_VOCAB の鍵, 引数)。"""
    return (key, params)


def A(key, **params):
    """引数を上書きした能力 (ABILITY_VOCAB の鍵, 引数)。上書きが無ければ文字列だけでよい。"""
    return (key, params)


def _res(**kw):
    unknown = set(kw) - set(RESIST_DEFAULT)
    if unknown:
        raise KeyError(f"unknown resist keys {sorted(unknown)}")
    d = dict(RESIST_DEFAULT)
    d.update(kw)
    return d


def _gore(**kw):
    unknown = set(kw) - set(GORE_DEFAULTS)
    if unknown:
        raise KeyError(f"unknown gore keys {sorted(unknown)}")
    d = copy.deepcopy(GORE_DEFAULTS)
    if "armor_break" in kw:
        d["armor_break"].update(kw.pop("armor_break"))
    d.update(copy.deepcopy(kw))
    return d


def _spawn(time, weight, group, where="city", site=(), **extra):
    d = dict(time=time, weight=weight, group=tuple(group), where=where, site=list(site))
    d.update(extra)
    return d


def _z(**kw):
    d = dict(attacks=[], female=False, digitigrade=False, tone=1, voice_pitch=1.0,
             knockback_resist=0.0, xp=4, aggro=18, accent=(160, 30, 30), boss=None)
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
#  ゾンビ 50 体（この並び順が ztype）
# ---------------------------------------------------------------------------
ZOMBIES = [
    # =======================================================================
    #  一般感染者 common（24）— 街の住人だった者たち。体力 16〜40、遅い
    # =======================================================================
    _z(key="office_worker", ja="感染したサラリーマン", en="Infected Office Worker", cls="common",
       height_cm=176, heads=7.3, bulk=1.0, limb=1.0, hunch=14, arm_len=1.04,
       decay=2, skin="pale", tone=1,
       outfit=[O("hair", style="balding", color=(52, 42, 34), patchy=1),
               O("shirt", cut="dress", color=(222, 222, 214), open=1, tucked=False, bloody=2, torn=1),
               O("necktie", color=(118, 22, 34), color2=(200, 170, 90), pattern="stripe", bloody=1),
               O("suit_jacket", color=(52, 54, 62), missing_sleeve="l", torn=2, bloody=1),
               O("slacks", color=(48, 50, 58), torn=1, dirty=1),
               O("dress_shoes", kind="oxford"),
               O("name_badge", style="lanyard", color=(40, 90, 170)),
               O("wristwatch", kind="steel", cracked=True),
               O("glasses", kind="clear", cracked=True)],
       mutations=[M("bite_wound", on="neck", size=2), M("missing_cheek_teeth", side="l", size=1)],
       eyes="clouded", hp=24, speed=0.21, damage=4, attack="grab_bite", attacks=["swipe"],
       locomotion="shamble", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("any", 30, (2, 5), site=["office", "street", "plaza"]),
       loot=[("nr:money", 0, 3, 0.6), ("nr:rags", 0, 2, 0.5), ("nr:infected_trophy", 0, 1, 0.05),
             ("minecraft:rotten_flesh", 0, 2, 0.5)],
       voice="groan_male", accent=(118, 22, 34), xp=3,
       bestiary_ja="通勤途中で噛まれたまま、今も同じ通りをさまよう会社員。緩んだネクタイと割れた眼鏡が、"
                   "几帳面だった生前を物語る。群れで現れ、掴みかかってから噛みつく。",
       bestiary_en="Bitten on his morning commute, he still wanders the same street. The loosened tie and "
                   "cracked glasses hint at a tidy life cut short. Comes in groups and grabs before it bites.",
       weakness_ja="頭部への強打。動きが遅く、首を刎ねやすい。",
       weakness_en="Heavy blows to the head. Slow and easy to decapitate."),

    _z(key="office_clerk", ja="感染したOL", en="Infected Office Clerk", cls="common",
       height_cm=162, heads=7.2, bulk=0.88, limb=0.88, hunch=10, arm_len=1.0,
       decay=1, skin="pale", tone=0, female=True,
       outfit=[O("hair", style="bob", color=(40, 28, 22)),
               O("shirt", cut="blouse", color=(232, 226, 236), bloody=2, torn=1),
               O("pencil_skirt", color=(36, 40, 62), torn=1),
               O("dress_shoes", kind="heels", missing="r"),
               O("name_badge", style="clip", color=(200, 60, 60)),
               O("wristwatch", kind="dress", color=(210, 180, 120))],
       mutations=[M("torn_throat", size=1), M("hanging_skin", on=["forearm_l"], flaps=1)],
       eyes="clouded", hp=20, speed=0.20, damage=3, attack="grab_bite", attacks=["swipe"],
       locomotion="limp", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("any", 24, (2, 4), site=["office", "street", "shop"]),
       loot=[("nr:money", 0, 2, 0.5), ("nr:rags", 0, 1, 0.4), ("nr:bandage", 0, 1, 0.1),
             ("minecraft:rotten_flesh", 0, 2, 0.5)],
       voice="groan_female", accent=(200, 60, 60), xp=3,
       bestiary_ja="片方のヒールを失い、足を引きずって歩く会社員の女性。首の傷から今も血が滲み、名札が胸で揺れている。"
                   "単体では脆いが、オフィス街では数が多い。",
       bestiary_en="Missing one heel, she limps along with a dragging gait. Blood still seeps from her torn "
                   "throat and her ID badge swings on her chest. Fragile alone, but office districts are full of them.",
       weakness_ja="脚を払えばすぐ倒れる。腕も細く切り落としやすい。",
       weakness_en="Sweep the legs and she goes down. Her thin arms sever easily."),

    _z(key="construction_worker", ja="感染した建設作業員", en="Infected Construction Worker", cls="common",
       height_cm=181, heads=7.1, bulk=1.18, limb=1.15, hunch=12, arm_len=1.05,
       decay=2, skin="grey_green", tone=2,
       outfit=[O("hard_hat", color=(240, 196, 20), dented=1),
               O("hi_vis_vest", color=(210, 250, 40), dirty=2),
               O("t_shirt", color=(88, 90, 96), torn=1, dirty=2),
               O("work_pants", color=(70, 62, 48), knee_pads=True, dirty=2),
               O("boots", kind="work", color=(96, 64, 36)),
               O("gloves", kind="work", hands="r"),
               O("tool_belt", tools=["hammer", "tape", "pliers"]),
               O("beard", style="stubble", color=(60, 48, 38))],
       mutations=[M("impaled", obj="rebar", on="torso", angle=20),
                  M("bite_wound", on="forearm_r", size=1)],
       eyes="clouded", hp=32, speed=0.20, damage=5, attack="double_swipe", attacks=["slam"],
       locomotion="shamble", resist=_res(),
       gore=_gore(armored=["head"], armor_stages=1, armor_hp=8, armor_mult=0.3),
       abilities=["armor_shed"],
       spawn=_spawn("any", 14, (1, 3), site=["construction", "street", "warehouse"]),
       loot=[("nr:scrap", 1, 3, 0.7), ("nr:duct_tape", 0, 1, 0.3), ("minecraft:iron_nugget", 0, 3, 0.4),
             ("minecraft:rotten_flesh", 0, 2, 0.5)],
       voice="groan_male", voice_pitch=0.9, accent=(240, 196, 20), xp=4, knockback_resist=0.1,
       bestiary_ja="腹を鉄筋に貫かれたまま歩き続ける作業員。黄色いヘルメットが最初の一撃を弾くが、"
                   "外れれば頭はむき出しになる。体格が良く、両腕の振り下ろしは重い。",
       bestiary_en="A laborer still walking with a rebar spike through his gut. His yellow hard hat deflects "
                   "the first blow to the head, but once it flies off the skull is bare. Big-framed, his "
                   "two-handed swings hit hard.",
       weakness_ja="打撃でヘルメットを飛ばしてから頭を狙う。",
       weakness_en="Knock the hard hat off with a blunt hit, then go for the head."),

    _z(key="nurse", ja="感染した看護師", en="Infected Nurse", cls="common",
       height_cm=160, heads=7.2, bulk=0.9, limb=0.9, hunch=16, arm_len=1.02,
       decay=2, skin="jaundiced", tone=2, female=True,
       outfit=[O("hair", style="bun", color=(20, 18, 18)),
               O("scrubs", color=(120, 180, 200), stethoscope=True, bloody=3),
               O("surgical_mask", position="chin"),
               O("sneakers", color=(236, 236, 236), color2=(200, 200, 200), bloody=2),
               O("name_badge", style="clip", color=(60, 140, 200)),
               O("gloves", kind="surgical", color=(110, 140, 230), torn=1)],
       mutations=[M("bite_wound", on="forearm_l", size=2), M("missing_fingers", hand="l", count=2)],
       eyes="clouded", hp=20, speed=0.21, damage=3, attack="grab_bite", attacks=["swipe"],
       locomotion="shamble", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("any", 12, (2, 4), site=["hospital", "street"]),
       loot=[("nr:bandage", 0, 1, 0.35), ("nr:alcohol", 0, 1, 0.3), ("nr:chemicals", 0, 1, 0.2),
             ("minecraft:rotten_flesh", 0, 1, 0.4)],
       voice="groan_female", accent=(120, 180, 200), xp=3,
       bestiary_ja="最後まで患者を看ていた看護師。血に染まったスクラブと、指の欠けた手袋が凄惨な最期を語る。"
                   "死体からは包帯や消毒用アルコールが見つかることが多い。",
       bestiary_en="A nurse who stayed with her patients until the very end. Blood-soaked scrubs and a glove "
                   "with missing fingers tell of a brutal last shift. Her body often carries bandages and rubbing alcohol.",
       weakness_ja="体力が低く、刃物の一撃で腕や首が落ちる。",
       weakness_en="Low health; a single blade strike can take an arm or the head."),

    _z(key="patient", ja="感染した入院患者", en="Infected Patient", cls="common",
       height_cm=172, heads=7.4, bulk=0.82, limb=0.82, hunch=22, arm_len=1.04,
       decay=3, skin="ashen", tone=1,
       outfit=[O("hospital_gown", pattern="dots", iv_line=True, bloody=2, torn=1),
               O("bandage_wrap", on=["head"], bloody=2),
               O("hair", style="messy", color=(120, 116, 110), patchy=2)],
       mutations=[M("stitches", on=["torso"], kind="surgical"),
                  M("exposed_ribs", side="r", count=3, flesh=0.2)],
       eyes="milky", hp=18, speed=0.19, damage=3, attack="grab_bite", attacks=["bite"],
       locomotion="stagger", resist=_res(blunt=1.2, slash=1.1),
       gore=_gore(sever_mult=1.3, bleed_mult=0.8, blood="dark"), abilities=[],
       spawn=_spawn("any", 14, (3, 6), site=["hospital"]),
       loot=[("nr:bandage", 0, 1, 0.25), ("nr:chemicals", 0, 1, 0.15), ("nr:medkit", 0, 1, 0.05),
             ("minecraft:rotten_flesh", 0, 1, 0.4)],
       voice="wet_choke", accent=(170, 200, 210), xp=2,
       bestiary_ja="手術着のまま病棟から溢れ出た入院患者。痩せ細った体は脆く、縫合跡が裂けて肋骨がのぞく。"
                   "点滴の管を引きずりながら、ふらつく足取りで群れを成す。",
       bestiary_en="Patients who spilled out of the wards still in their gowns. Their wasted bodies are "
                   "brittle, surgical stitches split open over bare ribs. They stagger in crowds, IV lines trailing behind.",
       weakness_ja="非常に脆く、打撃でも手足がちぎれる。群れに囲まれないこと。",
       weakness_en="Extremely brittle; even blunt hits tear limbs off. Don't get surrounded."),

    _z(key="police_officer", ja="感染した警官", en="Infected Patrol Officer", cls="common",
       height_cm=178, heads=7.3, bulk=1.06, limb=1.05, hunch=10, arm_len=1.03,
       decay=2, skin="grey_green", tone=3,
       outfit=[O("police_uniform", color=(34, 46, 84), radio=True, belt=True, bloody=1),
               O("police_cap", color=(34, 46, 84)),
               O("slacks", color=(30, 38, 66)),
               O("boots", kind="combat", color=(18, 18, 20)),
               O("hair", style="short", color=(24, 20, 18))],
       mutations=[M("bite_wound", on="neck", size=1), M("missing_cheek_teeth", side="r", size=2)],
       eyes="clouded", hp=28, speed=0.22, damage=4, attack="grab_bite", attacks=["swipe"],
       locomotion="shamble", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("any", 12, (1, 3), site=["police", "street"]),
       loot=[("nr:ammo_pistol", 1, 4, 0.6), ("nr:battery", 0, 1, 0.3), ("nr:money", 0, 2, 0.3)],
       voice="groan_male", accent=(34, 46, 84), xp=4,
       bestiary_ja="最後まで持ち場を離れなかった巡査。肩の無線機は今もときおり雑音を吐く。"
                   "腰のホルスターに拳銃弾が残っていることがある。",
       bestiary_en="A patrol officer who never left his post. The radio on his shoulder still crackles now "
                   "and then. His holster often holds leftover pistol rounds.",
       weakness_ja="特別な防具はない。頭を狙えば素早く倒せる。",
       weakness_en="No special protection; headshots drop him fast."),

    _z(key="riot_police", ja="感染した機動隊員", en="Infected Riot Trooper", cls="common",
       height_cm=182, heads=7.2, bulk=1.25, limb=1.15, hunch=8, arm_len=1.03,
       decay=2, skin="pale", tone=1,
       outfit=[O("riot_helmet", visor="down"),
               O("riot_armor", color=(28, 30, 34), coverage="full", dirty=1),
               O("riot_shield", text="POLICE", cracked=1),
               O("slacks", color=(26, 28, 32)),
               O("boots", kind="combat", color=(16, 16, 18)),
               O("gloves", kind="leather", color=(16, 16, 18))],
       mutations=[M("bite_wound", on="forearm_r", size=1)],
       eyes="clouded", hp=40, speed=0.18, damage=5, attack="shield_bash", attacks=["swipe"],
       locomotion="shamble", resist=_res(slash=0.8, pierce=0.8),
       gore=_gore(armored=["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"], armor_stages=3,
                  armor_hp=10, armor_mult=0.2,
                  armor_strip=dict(arm_r=3, arm_l=3, leg_r=3, leg_l=3, torso=2, head=1),
                  breakables=dict(gear_shield=1)),
       abilities=["shield_block", "armor_shed"],
       spawn=_spawn("any", 6, (1, 3), site=["police", "street", "plaza"]),
       loot=[("nr:scrap", 1, 2, 0.5), ("nr:ammo_shotgun", 0, 2, 0.2), ("nr:duct_tape", 0, 1, 0.3),
             ("nr:infected_trophy", 0, 1, 0.15)],
       voice="muffled", accent=(200, 200, 210), xp=7, knockback_resist=0.4, aggro=16,
       bestiary_ja="機動隊の装備に身を包んだまま感染した隊員。前に構えた盾は正面からの攻撃をほとんど防ぎ、"
                   "装甲は刃と弾を通さない。装甲は打撃と爆発で段階的に剥がれ落ちる。",
       bestiary_en="A riot officer infected while still fully geared. The shield he holds in front blocks "
                   "almost every frontal attack, and the armor turns aside blades and bullets. The armor comes "
                   "off in stages under blunt force and explosions.",
       weakness_ja="背後か側面から。左腕を折れば盾が下がる。打撃で装甲を剥がす。",
       weakness_en="Flank him or get behind him. Break the left arm to drop the shield; strip the armor with blunt weapons."),

    _z(key="firefighter", ja="感染した消防士", en="Infected Firefighter", cls="common",
       height_cm=184, heads=7.2, bulk=1.3, limb=1.15, hunch=10, arm_len=1.04,
       decay=2, skin="grey_green", tone=2,
       outfit=[O("firefighter_helmet", color=(196, 160, 36), shield_text="7", burnt=1),
               O("firefighter_coat", color=(196, 160, 90), pants=True, burnt=1, dirty=2),
               O("boots", kind="fire", color=(20, 20, 20)),
               O("gloves", kind="work", color=(120, 90, 50), burnt=1),
               O("air_tank", hose=True, mask="hanging", dented=1)],
       mutations=[M("burn_scars", on=["head", "forearm_r"], coverage=0.4)],
       eyes="clouded", hp=34, speed=0.20, damage=5, attack="double_swipe", attacks=["grab_bite"],
       locomotion="shamble", resist=_res(fire=0.25, blast=0.8, slash=0.9),
       gore=_gore(weak_spots=[dict(part="torso", zone="back", mult=1.5, ability="tank_burst", once=True)],
                  breakables=dict(gear_tank=1)),
       abilities=["tank_burst"],
       spawn=_spawn("any", 6, (1, 2), site=["gas_station", "street", "apartment"]),
       loot=[("nr:scrap", 1, 2, 0.5), ("nr:duct_tape", 0, 1, 0.3), ("nr:bandage", 0, 1, 0.3),
             ("nr:infected_trophy", 0, 1, 0.1)],
       voice="groan_male", voice_pitch=0.95, accent=(196, 160, 36), xp=6, knockback_resist=0.2,
       bestiary_ja="炎の中で感染した消防士。防火服は炎をほとんど通さず、背中の空気ボンベを背負ったまま歩く。"
                   "ボンベを撃ち抜くと破裂して本人が吹き飛ぶ。",
       bestiary_en="A firefighter turned in the middle of a blaze. His turnout gear shrugs off flames, and he "
                   "still carries the air tank on his back. Puncture the tank and it bursts, blasting him off his feet.",
       weakness_ja="背中のボンベを刺突か射撃で破裂させる。火は効かない。",
       weakness_en="Pierce or shoot the tank on his back. Fire won't work."),

    _z(key="hazmat_worker", ja="感染した防護服作業員", en="Infected Hazmat Responder", cls="common",
       height_cm=178, heads=7.2, bulk=1.2, limb=1.1, hunch=16, arm_len=1.03,
       decay=3, skin="necrotic_purple", tone=1,
       outfit=[O("hazmat_suit", color=(236, 200, 40), visor_fog=2, torn=1, bloody=1),
               O("gas_mask", filters=2, lens="cracked"),
               O("gloves", kind="rubber", color=(40, 40, 40)),
               O("boots", kind="rubber", color=(40, 60, 40))],
       mutations=[M("pustules", on=["head", "neck"], density=2, color=(210, 200, 100)),
                  M("dark_veins", on=["head", "neck"], density=2)],
       eyes="clouded", hp=26, speed=0.19, damage=4, attack="swipe", attacks=["double_swipe"],
       locomotion="stagger", resist=_res(toxic=0.0, fire=1.3),
       gore=_gore(blood="bile", bleed_mult=0.9), abilities=["toxic_death_puff"],
       spawn=_spawn("any", 6, (1, 3), site=["hospital", "lab", "street"]),
       loot=[("nr:chemicals", 1, 2, 0.6), ("nr:duct_tape", 0, 2, 0.4), ("nr:battery", 0, 1, 0.2)],
       voice="muffled", accent=(236, 200, 40), xp=5,
       bestiary_ja="封じ込め作業の途中で倒れた防護服の作業員。曇ったバイザーの奥で、腫れ上がった顔が膿疱に覆われている。"
                   "防護服が裂けて倒れると、溜まっていた毒ガスが噴き出す。",
       bestiary_en="A containment worker who fell mid-operation. Behind the fogged visor, a swollen face is "
                   "covered in pustules. When the suit tears and he drops, the toxic gas trapped inside bursts out.",
       weakness_ja="毒は効かない。火に弱い。倒したらすぐ離れる。",
       weakness_en="Immune to toxins, weak to fire. Back off as soon as he drops."),

    _z(key="soldier", ja="感染した兵士", en="Infected Soldier", cls="common",
       height_cm=183, heads=7.4, bulk=1.15, limb=1.12, hunch=10, arm_len=1.03,
       decay=2, skin="grey_green", tone=3,
       outfit=[O("helmet_military", cover="camo", goggles=True, chinstrap="dangling"),
               O("military_vest", color=(70, 80, 56), pouches=6, radio=True),
               O("camo_fatigues", pattern="urban", color=(110, 112, 104), color2=(60, 62, 58), torn=1),
               O("boots", kind="combat", color=(60, 48, 36)),
               O("gloves", kind="leather", color=(24, 24, 24)),
               O("name_badge", style="dogtag", color=(170, 170, 176))],
       mutations=[M("bite_wound", on="arm_l", size=2), M("missing_cheek_teeth", side="l", size=1)],
       eyes="clouded", hp=36, speed=0.22, damage=5, attack="grab_bite", attacks=["double_swipe"],
       locomotion="shamble", resist=_res(),
       gore=_gore(armored=["head", "torso"], armor_stages=2, armor_hp=12, armor_mult=0.25,
                  armor_strip=dict(torso=2, head=1)),
       abilities=["armor_shed"],
       spawn=_spawn("any", 8, (2, 4), site=["street", "police", "parking"]),
       loot=[("nr:ammo_rifle", 1, 5, 0.6), ("nr:gunpowder_pouch", 0, 1, 0.3), ("nr:bandage", 0, 1, 0.3),
             ("nr:scrap", 0, 1, 0.3)],
       voice="groan_male", accent=(110, 112, 104), xp=6, knockback_resist=0.2,
       bestiary_ja="封鎖線を守っていた兵士の成れの果て。防弾ベストとヘルメットが急所を守り、弾を何発も受け止める。"
                   "認識票と、使われなかった小銃弾を持っていることが多い。",
       bestiary_en="What's left of the soldiers who held the quarantine line. A plate carrier and helmet "
                   "protect the vitals and soak up several rounds. Often carries dog tags and unspent rifle ammo.",
       weakness_ja="装甲は打撃で剥がれる。手足は無防備。",
       weakness_en="Blunt hits strip the armor. The limbs are unprotected."),

    _z(key="line_cook", ja="感染した料理人", en="Infected Line Cook", cls="common",
       height_cm=174, heads=7.0, bulk=1.25, limb=1.12, hunch=12, arm_len=1.0,
       decay=2, skin="bloated_pink", tone=2,
       outfit=[O("chef_coat", rolled_sleeves=True, bloody=3),
               O("apron", kind="cloth", length="full", stains=3, color=(60, 58, 56)),
               O("skull_cap", kind="kitchen", color=(230, 230, 230)),
               O("work_pants", color=(40, 40, 44), cargo=False, color2=(220, 220, 220)),
               O("boots", kind="rubber", color=(20, 20, 20))],
       mutations=[M("burn_scars", on=["forearm_r", "forearm_l"], coverage=0.5),
                  M("impaled", obj="knife", on="chest", angle=30)],
       eyes="clouded", hp=30, speed=0.20, damage=4, attack="double_swipe", attacks=["grab_bite"],
       locomotion="shamble", resist=_res(fire=0.8),
       gore=_gore(sever_mult=0.9, bleed_mult=1.2), abilities=[],
       spawn=_spawn("any", 10, (1, 3), site=["shop", "street"]),
       loot=[("nr:alcohol", 0, 2, 0.5), ("nr:blades", 0, 1, 0.35), ("nr:rags", 0, 1, 0.3),
             ("minecraft:rotten_flesh", 0, 2, 0.5)],
       voice="groan_male", voice_pitch=0.92, accent=(232, 230, 222), xp=4,
       bestiary_ja="厨房から出てきた太った料理人。肩に包丁が刺さったままで、両腕には古い火傷が残る。"
                   "エプロンのポケットに酒瓶や刃物の欠片が入っていることがある。",
       bestiary_en="A heavyset cook who stumbled out of the kitchen. A chef's knife is still lodged in his "
                   "shoulder and old burns cover both arms. His apron pockets often hold liquor or broken blades.",
       weakness_ja="腹回りが厚く、胴の切断は難しい。首か脚を狙う。",
       weakness_en="Thick around the middle, so cutting the torso is hard. Aim for the neck or legs."),

    _z(key="mechanic", ja="感染した整備士", en="Infected Mechanic", cls="common",
       height_cm=177, heads=7.2, bulk=1.08, limb=1.1, hunch=18, arm_len=1.06,
       decay=2, skin="grey_green", tone=4,
       outfit=[O("coveralls", color=(40, 70, 120), name_patch=True, dirty=3),
               O("baseball_cap", color=(180, 30, 30), backwards=True, dirty=2),
               O("boots", kind="work", color=(50, 40, 30)),
               O("gloves", kind="work", color=(30, 30, 30), hands="r", dirty=3),
               O("held_tool", kind="wrench", bloody=1)],
       mutations=[M("missing_fingers", hand="l", count=1),
                  M("skin_peeled", on=["forearm_l"], coverage=0.3)],
       eyes="clouded", hp=28, speed=0.21, damage=6, attack="tool_swing", attacks=["swipe"],
       locomotion="shamble", resist=_res(), gore=_gore(), abilities=["tool_wield"],
       spawn=_spawn("any", 10, (1, 2), site=["gas_station", "parking", "warehouse"]),
       loot=[("nr:scrap", 1, 3, 0.8), ("nr:duct_tape", 0, 1, 0.4), ("nr:battery", 0, 1, 0.3)],
       voice="groan_male", accent=(40, 70, 120), xp=5,
       bestiary_ja="整備工場のつなぎを着た感染者。右手にはレンチを握りしめたままで、殴られると重い。"
                   "腕を落とせばレンチも落ちる。",
       bestiary_en="An infected mechanic still in his garage coveralls. His right hand never let go of the "
                   "wrench, and its swings hurt. Take the arm and the wrench goes with it.",
       weakness_ja="右腕を切り落とす。レンチがなければただの感染者。",
       weakness_en="Cut off the right arm; without the wrench he's an ordinary infected."),

    _z(key="jogger", ja="感染したランナー", en="Infected Jogger", cls="common",
       height_cm=166, heads=7.6, bulk=0.85, limb=0.88, hunch=6, arm_len=1.0,
       decay=1, skin="flushed", tone=3, female=True,
       outfit=[O("hair", style="ponytail", color=(30, 24, 20)),
               O("t_shirt", cut="tank", color=(230, 60, 120), torn=1, bloody=1),
               O("running_shorts", color=(24, 24, 28)),
               O("sneakers", color=(240, 240, 240), color2=(40, 200, 240)),
               O("headphones", kind="earbuds", worn="neck", cord_dangling=True),
               O("wristwatch", kind="fitness", color=(30, 30, 30))],
       mutations=[M("bite_wound", on="torso", size=2, fresh=True),
                  M("hanging_skin", on=["arm_r"], flaps=1)],
       eyes="bloodshot", hp=18, speed=0.26, damage=3, attack="lunge", attacks=["grab_bite"],
       locomotion="run", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("day", 10, (1, 2), site=["street", "plaza"]),
       loot=[("nr:money", 0, 1, 0.3), ("nr:bandage", 0, 1, 0.2), ("nr:battery", 0, 1, 0.15)],
       voice="groan_female", voice_pitch=1.1, accent=(230, 60, 120), xp=4, aggro=24,
       bestiary_ja="朝のランニング中に感染した女性。軽装で身軽なため、一般感染者としては足が速い。"
                   "イヤホンのコードが首元で揺れている。",
       bestiary_en="A woman infected on her morning run. Light clothes keep her quick, fast for a common "
                   "infected. Earbud wires dangle at her neck.",
       weakness_ja="体力が低い。突進してきたところを迎え撃つ。",
       weakness_en="Low health. Meet her lunge with a counter-swing."),

    _z(key="drifter", ja="感染した路上生活者", en="Infected Drifter", cls="common",
       height_cm=170, heads=7.1, bulk=0.95, limb=0.9, hunch=24, arm_len=1.06,
       decay=3, skin="leathery_brown", tone=2,
       outfit=[O("hair", style="matted", color=(90, 84, 74), length=1.3),
               O("beard", style="full", color=(90, 84, 74)),
               O("hoodie", color=(60, 64, 52), hood="up", torn=2, dirty=3),
               O("layered_rags", kind="coat", layers=2, color=(86, 74, 60), torn=3, dirty=3),
               O("gloves", kind="fingerless", color=(70, 60, 50)),
               O("jeans", color=(50, 56, 70), ripped_knees=True, torn=3, dirty=3),
               O("boots", kind="work", color=(60, 46, 34), torn=2),
               O("backpack", kind="rucksack", color=(70, 80, 60), torn=2)],
       mutations=[M("fungal_growth", on=["neck", "chest"], coverage=0.25, color=(190, 180, 140), caps=4),
                  M("pustules", on=["forearm_l"], density=1)],
       eyes="clouded", hp=22, speed=0.19, damage=3, attack="swipe", attacks=["grab_bite"],
       locomotion="shamble", resist=_res(toxic=0.7, fire=1.3),
       gore=_gore(blood="dark", bleed_mult=0.7), abilities=[],
       spawn=_spawn("any", 14, (1, 3), site=["street", "sewer", "plaza"]),
       loot=[("nr:rags", 1, 3, 0.8), ("nr:alcohol", 0, 1, 0.4), ("nr:duct_tape", 0, 1, 0.25)],
       voice="groan_male", voice_pitch=0.88, accent=(86, 74, 60), xp=3,
       bestiary_ja="感染が広がる前から路上で暮らしていた男。何枚も重ねたボロ布の下で、菌糸が首筋を覆い始めている。"
                   "古い感染者で血はどす黒く、毒にもいくらか耐える。",
       bestiary_en="A man who lived on the streets long before the outbreak. Under layers of rags, fungus is "
                   "creeping over his neck. Long infected, his blood runs dark and he shrugs off some toxins.",
       weakness_ja="ボロ布はよく燃える。火炎瓶が有効。",
       weakness_en="The rags burn well. Molotovs work."),

    _z(key="bride", ja="感染した花嫁", en="Infected Bride", cls="common",
       height_cm=164, heads=7.4, bulk=0.88, limb=0.86, hunch=8, arm_len=1.02,
       decay=2, skin="pale", tone=0, female=True,
       outfit=[O("torn_dress", style="wedding", length="floor", train=True, torn=3, bloody=3),
               O("bridal_veil", length="long", torn=2),
               O("hair", style="bun", color=(150, 100, 60)),
               O("gloves", kind="satin", color=(244, 240, 232), bloody=2),
               O("dress_shoes", kind="heels", color=(240, 236, 226), missing="l")],
       mutations=[M("torn_throat", size=2), M("bite_wound", on="arm_r", size=1)],
       eyes="clouded", hp=22, speed=0.20, damage=3, attack="grab_bite", attacks=["swipe"],
       locomotion="limp", resist=_res(), gore=_gore(bleed_mult=1.2), abilities=[],
       spawn=_spawn("any", 2, (1, 1), site=["church"]),
       loot=[("nr:money", 1, 4, 0.6), ("minecraft:gold_nugget", 1, 3, 0.5), ("nr:infected_trophy", 0, 1, 0.1)],
       voice="sob", accent=(240, 236, 226), xp=5,
       bestiary_ja="式の当日に感染した花嫁。裾を引きずる純白のドレスは血に染まり、すすり泣くような声を漏らす。"
                   "教会の周りで、参列者だった感染者を連れていることが多い。",
       bestiary_en="A bride infected on her wedding day. The white train she drags is soaked in blood, and she "
                   "lets out sobbing moans. She is often found near the church, trailed by infected who were once her guests.",
       weakness_ja="片方のヒールを失い足が遅い。指輪の金を落とす。",
       weakness_en="Missing a heel, she is slow. Drops the gold of her ring."),

    _z(key="convict", ja="感染した囚人", en="Infected Convict", cls="common",
       height_cm=186, heads=7.2, bulk=1.2, limb=1.2, hunch=12, arm_len=1.06,
       decay=2, skin="grey_green", tone=3,
       outfit=[O("prison_jumpsuit", number="0451", top_tied_waist=True, dirty=2),
               O("t_shirt", cut="tank", color=(210, 210, 200), bloody=2, dirty=2),
               O("chain_shackles", kind="chain", wrists=True, chain_len=6, broken=True),
               O("hair", style="buzz", color=(20, 18, 16)),
               O("beard", style="stubble", color=(20, 18, 16)),
               O("sneakers", color=(220, 220, 220), color2=(220, 220, 220), dirty=2),
               O("tattoo", on=["arm_r", "arm_l", "chest"], motif="barbed")],
       mutations=[M("bite_wound", on="forearm_l", size=2), M("missing_cheek_teeth", side="l", size=1)],
       eyes="clouded", hp=34, speed=0.22, damage=5, attack="double_swipe", attacks=["headbutt"],
       locomotion="shamble", resist=_res(), gore=_gore(sever_mult=0.9), abilities=[],
       spawn=_spawn("any", 8, (1, 3), site=["police", "street"]),
       loot=[("nr:scrap", 0, 2, 0.5), ("nr:blades", 0, 1, 0.3), ("nr:rags", 0, 1, 0.3)],
       voice="groan_male", voice_pitch=0.9, accent=(230, 110, 30), xp=5, knockback_resist=0.1,
       bestiary_ja="護送中に感染した囚人。手首に残った手錠の鎖を振り回すように殴りかかる。"
                   "体格が良く、頭突きも使う。",
       bestiary_en="A convict infected during transport. He swings at you with the chain still hanging from "
                   "his cuffs. Heavyset, he also headbutts.",
       weakness_ja="腕を落とせば鎖の攻撃が消える。",
       weakness_en="Sever his arms to stop the chain swings."),

    _z(key="security_guard", ja="感染した警備員", en="Infected Security Guard", cls="common",
       height_cm=175, heads=7.0, bulk=1.3, limb=1.05, hunch=14, arm_len=1.02,
       decay=2, skin="pale", tone=2,
       outfit=[O("police_uniform", style="guard", color=(70, 74, 82), radio=False, belt=True),
               O("police_cap", style="guard", color=(50, 54, 62)),
               O("slacks", color=(40, 42, 48)),
               O("dress_shoes", kind="oxford"),
               O("flashlight", mount="shoulder", lit=True),
               O("name_badge", style="clip", color=(200, 200, 60))],
       mutations=[M("torn_throat", size=1), M("hanging_skin", on=["neck"], flaps=1)],
       eyes="clouded", hp=26, speed=0.19, damage=4, attack="grab_bite", attacks=["swipe"],
       locomotion="shamble", resist=_res(), gore=_gore(breakables=dict(gear_flashlight=1)),
       abilities=["flashlight_beam"],
       spawn=_spawn("any", 10, (1, 2), site=["shop", "warehouse", "parking", "office"]),
       loot=[("nr:battery", 1, 2, 0.7), ("nr:money", 0, 2, 0.3), ("minecraft:rotten_flesh", 0, 1, 0.4)],
       voice="groan_male", accent=(255, 240, 200), xp=4,
       bestiary_ja="夜間警備の途中で感染した警備員。肩の懐中電灯はまだ点いており、"
                   "その光に照らされると周りの感染者が集まってくる。死体から電池が手に入る。",
       bestiary_en="A night-shift guard infected on his rounds. The flashlight on his shoulder still works, "
                   "and if its beam lands on you, nearby infected come running. His body is a good source of batteries.",
       weakness_ja="背後から近づく。懐中電灯の光を避ける。",
       weakness_en="Approach from behind and stay out of the flashlight beam."),

    _z(key="surgeon", ja="感染した外科医", en="Infected Surgeon", cls="common",
       height_cm=168, heads=7.4, bulk=0.9, limb=0.9, hunch=12, arm_len=1.02,
       decay=2, skin="pale", tone=3, female=True,
       outfit=[O("scrubs", color=(40, 90, 80), gown=True, bloody=3),
               O("skull_cap", kind="surgical", color=(90, 140, 170)),
               O("surgical_mask", position="mouth", bloody=2),
               O("gloves", kind="surgical", color=(220, 210, 180), bloody=3),
               O("glasses", kind="loupe"),
               O("dress_shoes", kind="clog", color=(40, 90, 80)),
               O("held_tool", kind="scalpel", color=(200, 204, 210))],
       mutations=[M("stitches", on=["forearm_l"], kind="crude"), M("bite_wound", on="neck", size=1)],
       eyes="clouded", hp=22, speed=0.21, damage=4, attack="tool_swing", attacks=["grab_bite"],
       locomotion="shamble", resist=_res(), gore=_gore(), abilities=["tool_wield"],
       spawn=_spawn("any", 6, (1, 2), site=["hospital", "lab"]),
       loot=[("nr:bandage", 0, 2, 0.4), ("nr:alcohol", 0, 1, 0.4), ("nr:chemicals", 0, 1, 0.3),
             ("nr:medkit", 0, 1, 0.15), ("nr:blades", 0, 1, 0.2)],
       voice="groan_female", accent=(40, 90, 80), xp=5,
       bestiary_ja="手術中に感染した外科医。メスを手放さず、切りつけられると出血が続く。死体は医療品の宝庫。",
       bestiary_en="A surgeon infected mid-operation. She never let go of her scalpel, and its cuts keep "
                   "bleeding. Her body is a trove of medical supplies.",
       weakness_ja="右腕を落とせばメスが使えない。体力は低い。",
       weakness_en="Take the right arm and the scalpel is gone. Low health."),

    _z(key="punk", ja="感染したパンクス", en="Infected Punk", cls="common",
       height_cm=179, heads=7.5, bulk=0.95, limb=0.95, hunch=10, arm_len=1.04,
       decay=2, skin="pale", tone=1,
       outfit=[O("hair", style="mohawk", color=(210, 30, 90)),
               O("leather_jacket", studs=True, patches=3, torn=1),
               O("t_shirt", color=(30, 30, 30), print="band", color2=(230, 230, 230)),
               O("jeans", color=(30, 30, 40), ripped_knees=True, torn=3),
               O("boots", kind="combat", color=(20, 20, 20)),
               O("tattoo", on=["neck", "forearm_r"], motif="skull")],
       mutations=[M("missing_cheek_teeth", side="r", size=2), M("hanging_skin", on=["forearm_l"], flaps=2)],
       eyes="bloodshot", hp=24, speed=0.23, damage=4, attack="headbutt", attacks=["double_swipe"],
       locomotion="stagger", resist=_res(), gore=_gore(), abilities=[],
       spawn=_spawn("night", 10, (2, 3), site=["plaza", "street"]),
       loot=[("nr:money", 0, 2, 0.4), ("nr:alcohol", 0, 1, 0.4), ("nr:blades", 0, 1, 0.25),
             ("nr:duct_tape", 0, 1, 0.2)],
       voice="groan_male", voice_pitch=1.05, accent=(210, 30, 90), xp=4,
       bestiary_ja="スタッズの付いた革ジャンを着たパンクス。頭突きで体勢を崩してから殴りかかってくる。夜の繁華街に多い。",
       bestiary_en="A punk in a studded leather jacket. He headbutts to knock you off balance, then follows up "
                   "with punches. Common in nightlife districts.",
       weakness_ja="頭突きの前に一瞬止まる。そこを狙う。",
       weakness_en="He pauses for a beat before headbutting. Hit him then."),

    _z(key="elder", ja="感染した老人", en="Infected Elder", cls="common",
       height_cm=165, heads=7.0, bulk=0.92, limb=0.82, hunch=34, arm_len=1.02,
       decay=3, skin="ashen", tone=1,
       outfit=[O("hair", style="balding", color=(214, 214, 210), patchy=2),
               O("cardigan", color=(120, 90, 70), buttons_missing=2),
               O("shirt", cut="dress", pattern="check", color=(200, 190, 170)),
               O("slacks", color=(90, 86, 74)),
               O("dress_shoes", kind="loafer", color=(70, 46, 30)),
               O("glasses", kind="thick", cracked=True),
               O("wristwatch", kind="gold", color=(210, 180, 90))],
       mutations=[M("hanging_skin", on=["neck", "arm_r", "arm_l"], flaps=3)],
       eyes="milky", hp=16, speed=0.17, damage=2, attack="grab_bite", attacks=["bite"],
       locomotion="limp", resist=_res(blunt=1.3, slash=1.2),
       gore=_gore(sever_mult=1.4, bleed_mult=0.6, blood="dark"), abilities=[],
       spawn=_spawn("any", 10, (1, 3), site=["apartment", "church"]),
       loot=[("nr:money", 0, 3, 0.5), ("minecraft:gold_nugget", 0, 1, 0.2), ("nr:bandage", 0, 1, 0.25)],
       voice="groan_old", accent=(120, 90, 70), xp=2, aggro=14,
       bestiary_ja="腰の曲がった老人の感染者。動きは遅く力も弱いが、一度掴んだら離さない。"
                   "体は脆く、軽い一撃でも手足が取れる。",
       bestiary_en="A bent-backed elderly infected. Slow and weak, but once he grabs hold he won't let go. His "
                   "body is brittle; even a light hit can tear off a limb.",
       weakness_ja="掴まれる前に倒す。打撃でも十分。",
       weakness_en="Put him down before he grabs you. Blunt weapons are enough."),

    _z(key="charred", ja="焼け焦げた感染者", en="Charred Infected", cls="common",
       height_cm=174, heads=7.2, bulk=0.92, limb=0.9, hunch=18, arm_len=1.04,
       decay=3, skin="charred", tone=2,
       outfit=[O("shirt", cut="work", color=(60, 56, 50), burnt=3, torn=3),
               O("jeans", color=(40, 40, 44), burnt=3, torn=2),
               O("boots", kind="work", color=(30, 26, 22), burnt=3)],
       mutations=[M("charred_crust", coverage=0.85),
                  M("exposed_skull", coverage=0.3), M("missing_nose")],
       eyes="milky", hp=22, speed=0.20, damage=3, attack="swipe", attacks=["grab_bite"],
       locomotion="stagger", resist=_res(fire=0.0, blunt=1.5, slash=0.9, toxic=0.8),
       gore=_gore(crumble=True, blood="ash", bleed_mult=0.2, sever_mult=1.6, corpse="ash"),
       abilities=["ash_puff"],
       spawn=_spawn("any", 8, (1, 3), site=["gas_station", "street", "apartment"]),
       loot=[("minecraft:charcoal", 1, 2, 0.6), ("nr:scrap", 0, 1, 0.3)],
       voice="rasp_dry", accent=(120, 40, 20), xp=3,
       bestiary_ja="火災に巻き込まれ、全身が炭化した感染者。血はほとんど流れず、斬れば手足が炭のように崩れ落ちる。"
                   "殴ると灰が舞い上がり、一瞬視界を奪われる。",
       bestiary_en="An infected burned to a crisp in the fires. It barely bleeds, and cut limbs crumble like "
                   "charcoal. Striking it throws up a cloud of ash that blinds you for a moment.",
       weakness_ja="火は効かない。打撃と刃物で簡単に崩れる。",
       weakness_en="Fire won't work, but blades and blunt weapons break it apart easily."),

    _z(key="drowned", ja="水死した感染者", en="Waterlogged Infected", cls="common",
       height_cm=180, heads=7.2, bulk=1.35, limb=1.2, hunch=14, arm_len=1.04,
       decay=3, skin="drowned_blue", tone=2,
       outfit=[O("life_vest", deflated=True, torn=1, wet=True),
               O("shirt", cut="flannel", pattern="check", color=(110, 120, 100), torn=2, wet=True),
               O("work_pants", color=(60, 70, 60), wet=True),
               O("boots", kind="waders", color=(50, 60, 50), wet=True),
               O("beard", style="full", color=(60, 50, 40)),
               O("hair", style="messy", color=(60, 50, 40), wet=True)],
       mutations=[M("waterlogged", coverage=0.9, algae=(70, 110, 60)),
                  M("bloated_belly", size=2, veins=True),
                  M("hanging_skin", on=["forearm_r", "forearm_l"], flaps=2)],
       eyes="milky", hp=34, speed=0.18, damage=4, attack="grab_bite", attacks=["slam"],
       locomotion="shamble", resist=_res(fire=0.6, shock=1.8, blunt=1.2),
       gore=_gore(blood="water", bleed_mult=1.5, wet_burst=True), abilities=[],
       spawn=_spawn("any", 8, (1, 3), site=["waterfront", "sewer"]),
       loot=[("nr:rags", 0, 2, 0.5), ("nr:money", 0, 2, 0.3), ("minecraft:kelp", 0, 2, 0.3)],
       voice="gurgle", accent=(70, 110, 60), xp=4, knockback_resist=0.15,
       bestiary_ja="運河に沈み、水を吸って膨れ上がった感染者。ふやけた皮膚が手袋のように剥がれ、溺れたような声を出す。"
                   "全身が濡れているため電気がよく通る。",
       bestiary_en="An infected that sank in the canal and swelled with water. Its sodden skin peels away like "
                   "gloves, and it gurgles as if still drowning. Soaked through, it conducts electricity extremely well.",
       weakness_ja="電気（感電の改造・電気トラップ）が非常に有効。",
       weakness_en="Electricity is devastating: use shock mods and electric traps."),

    _z(key="crawler", ja="這いずる感染者", en="Legless Crawler", cls="common",
       height_cm=172, heads=7.2, bulk=0.95, limb=0.95, hunch=0, arm_len=1.06,
       decay=3, skin="grey_green", tone=0,
       outfit=[O("t_shirt", color=(150, 40, 40), torn=3, bloody=3),
               O("jeans", color=(50, 60, 80), torn=3, bloody=2),
               O("hair", style="messy", color=(70, 50, 30))],
       mutations=[M("exposed_ribs", side="l", count=2),
                  M("skin_peeled", on=["chest"], coverage=0.3)],
       eyes="clouded", hp=16, speed=0.16, damage=3, attack="bite_low", attacks=["grab_bite"],
       locomotion="crawl", resist=_res(),
       gore=_gore(pre_damage=dict(leg_r="cut_upper", leg_l="cut_lower", state="crawl"),
                  gib_extra=[11]),
       abilities=["ankle_grab"],
       spawn=_spawn("any", 10, (1, 2), site=["street", "parking", "sewer"]),
       loot=[("nr:rags", 0, 1, 0.4), ("nr:scrap", 0, 1, 0.3)],
       voice="wet_choke", voice_pitch=0.95, accent=(150, 40, 40), xp=3, aggro=10,
       bestiary_ja="両脚を失い、腕だけで地面を這う感染者。車の下や瓦礫の陰に潜み、通りかかった足首を掴む。",
       bestiary_en="An infected that lost both legs and drags itself along on its arms. It lurks under cars "
                   "and rubble and grabs the ankles of anyone passing by.",
       weakness_ja="足元に注意。踏みつけ（スニーク攻撃）でとどめを刺せる。",
       weakness_en="Watch your feet. Finish it with a stomp (sneak attack)."),

    _z(key="delivery_rider", ja="感染した配達員", en="Infected Courier", cls="common",
       height_cm=172, heads=7.3, bulk=0.95, limb=0.95, hunch=14, arm_len=1.03,
       decay=1, skin="jaundiced", tone=1,
       outfit=[O("scooter_helmet", visor="up", cracked=1),
               O("rain_jacket", color=(30, 120, 60), torn=1),
               O("backpack", kind="delivery_box", color=(30, 120, 60), lid_open=True, dirty=1),
               O("jeans", color=(30, 34, 48), torn=2),
               O("sneakers", color=(60, 60, 60), color2=(230, 230, 230)),
               O("gloves", kind="leather", color=(20, 20, 20))],
       mutations=[M("skin_peeled", on=["forearm_l", "leg_l", "head"], coverage=0.4),
                  M("bite_wound", on="arm_r", size=1)],
       eyes="clouded", hp=24, speed=0.21, damage=3, attack="grab_bite", attacks=["swipe"],
       locomotion="limp", resist=_res(),
       gore=_gore(armored=["head"], armor_stages=1, armor_hp=6, armor_mult=0.35),
       abilities=["armor_shed"],
       spawn=_spawn("any", 12, (1, 2), site=["street", "office", "apartment"]),
       loot=[("nr:money", 0, 2, 0.4), ("nr:battery", 0, 1, 0.3), ("minecraft:bread", 0, 1, 0.4)],
       voice="groan_male", voice_pitch=1.05, accent=(30, 120, 60), xp=4,
       bestiary_ja="配達中の事故で倒れ、そのまま感染した配達員。背中には潰れた配達箱を背負い、半身に擦り傷が広がっている。"
                   "ヘルメットが頭への最初の一撃を防ぐ。",
       bestiary_en="A courier who crashed mid-delivery and turned where he fell. A crushed delivery box rides "
                   "on his back and road rash covers half his body. His helmet stops the first blow to the head.",
       weakness_ja="ヘルメットを飛ばしてから頭を狙う。足を引きずっていて遅い。",
       weakness_en="Knock the helmet off, then go for the head. His limp makes him slow."),

    # =======================================================================
    #  俊敏型 viral（8）— 感染したばかりで速い。体力は低く、UV を嫌う
    # =======================================================================
    _z(key="sprinter", ja="疾走者", en="Sprinter", cls="viral",
       height_cm=178, heads=7.5, bulk=0.92, limb=0.95, hunch=20, arm_len=1.06,
       decay=1, skin="flushed", tone=2,
       outfit=[O("t_shirt", color=(60, 90, 140), torn=3, bloody=2),
               O("jeans", color=(40, 44, 60), torn=2),
               O("sneakers", color=(200, 200, 200), dirty=2),
               O("hair", style="short", color=(30, 24, 20))],
       mutations=[M("bite_wound", on="neck", size=3, fresh=True),
                  M("dark_veins", on=["neck", "head", "chest"], density=2)],
       eyes="bloodshot", hp=18, speed=0.34, damage=4, attack="lunge", attacks=["double_swipe"],
       locomotion="sprint", resist=_res(uv=0.4), gore=_gore(),
       abilities=["wall_climb", "pack_flank"],
       spawn=_spawn("any", 12, (2, 4), site=["street", "rooftop", "plaza"]),
       loot=[("nr:infected_trophy", 0, 1, 0.15), ("nr:rags", 0, 1, 0.3), ("nr:money", 0, 1, 0.2)],
       voice="snarl", accent=(200, 40, 50), xp=7, aggro=32,
       bestiary_ja="感染して間もない俊敏型。全力で走り、壁をよじ登って追いかけてくる。"
                   "群れで現れると、一体が正面から来るあいだに残りが回り込んでくる。",
       bestiary_en="A freshly turned viral. It sprints flat out and climbs walls to chase you down. In a pack, "
                   "one charges from the front while the rest circle around your flanks.",
       weakness_ja="体力は低い。UV ライトを嫌う。囲まれる前に一体ずつ。",
       weakness_en="Low health and averse to UV light. Pick them off before they surround you."),

    _z(key="leaper", ja="跳躍者", en="Leaper", cls="viral",
       height_cm=168, heads=7.6, bulk=0.85, limb=0.88, hunch=26, arm_len=1.08,
       decay=1, skin="flushed", tone=4, female=True,
       outfit=[O("hair", style="long", color=(20, 16, 14), length=1.2),
               O("hoodie", color=(130, 40, 50), hood="down", torn=2),
               O("jeans", cut="shorts", color=(90, 110, 150), torn=2)],
       mutations=[M("claws", length=1, hands="both"),
                  M("dark_veins", on=["neck", "arm_r", "arm_l"], density=2)],
       eyes="bloodshot", hp=16, speed=0.36, damage=4, attack="pounce", attacks=["claw_flurry"],
       locomotion="leap", resist=_res(uv=0.5), gore=_gore(),
       abilities=["pounce_pin", "wall_climb"],
       spawn=_spawn("any", 8, (1, 3), site=["rooftop", "street"]),
       loot=[("nr:infected_trophy", 0, 1, 0.2), ("nr:rags", 0, 1, 0.3)],
       voice="shriek_high", accent=(130, 40, 50), xp=8, aggro=32,
       bestiary_ja="高所から跳びかかって獲物を押し倒す俊敏型。押し倒されると噛みつかれ続けるため、"
                   "攻撃を連打して振りほどく必要がある。",
       bestiary_en="A viral that leaps from above and pins its prey. Once pinned, you keep getting bitten "
                   "until you mash attack to throw it off.",
       weakness_ja="跳躍の直前にしゃがむ。そこで横に避ける。",
       weakness_en="It crouches right before the leap. Sidestep then."),

    _z(key="wallcrawler", ja="壁這い", en="Wallcrawler", cls="viral",
       height_cm=175, heads=7.6, bulk=0.8, limb=0.82, hunch=30, arm_len=1.18,
       decay=2, skin="ashen", tone=2,
       outfit=[O("shirt", cut="work", sleeves="torn_off", color=(180, 170, 150), torn=3, dirty=2),
               O("slacks", color=(50, 50, 50), torn=3),
               O("hair", style="long", color=(40, 34, 30), length=1.1)],
       mutations=[M("eyeless", bleed=True), M("claws", length=2, hands="both"),
                  M("exposed_spine", length=8)],
       eyes="none", hp=16, speed=0.32, damage=4, attack="claw_flurry", attacks=["grab_bite"],
       locomotion="scuttle", resist=_res(uv=0.5, blunt=1.1), gore=_gore(),
       abilities=["wall_climb", "ceiling_ambush"],
       spawn=_spawn("any", 6, (1, 2), site=["sewer", "apartment", "parking", "warehouse"]),
       loot=[("nr:infected_trophy", 0, 1, 0.2), ("nr:mutated_tissue", 0, 1, 0.1)],
       voice="hiss", accent=(164, 160, 154), xp=8, aggro=24,
       bestiary_ja="目を失い、音だけで獲物を追う俊敏型。蜘蛛のように壁や天井に張り付き、真下を通った者に落ちてくる。",
       bestiary_en="An eyeless viral that hunts by sound alone. It clings to walls and ceilings like a spider "
                   "and drops onto anyone passing below.",
       weakness_ja="しゃがんで静かに歩けば気付かれにくい。天井に注意。",
       weakness_en="Sneaking quietly keeps you unnoticed. Check the ceilings."),

    _z(key="brawler", ja="拳闘者", en="Brawler", cls="viral",
       height_cm=185, heads=7.5, bulk=1.08, limb=1.15, hunch=14, arm_len=1.06,
       decay=0, skin="flushed", tone=3,
       outfit=[O("t_shirt", cut="tank", color=(30, 30, 30), torn=1),
               O("running_shorts", color=(200, 30, 30), color2=(240, 240, 240)),
               O("sneakers", kind="high_top", color=(240, 240, 240), color2=(200, 30, 30)),
               O("bandage_wrap", on=["hand_r", "hand_l"], bloody=2),
               O("hair", style="buzz", color=(20, 16, 14))],
       mutations=[M("dark_veins", on=["arm_r", "arm_l", "neck"], density=2),
                  M("bite_wound", on="chest", size=2)],
       eyes="bloodshot", hp=24, speed=0.31, damage=5, attack="claw_flurry", attacks=["headbutt", "double_swipe"],
       locomotion="sprint", resist=_res(blunt=0.9, uv=0.4), gore=_gore(),
       abilities=["dodge", "wall_climb"],
       spawn=_spawn("any", 6, (1, 2), site=["street", "plaza"]),
       loot=[("nr:infected_trophy", 0, 1, 0.25), ("nr:bandage", 0, 1, 0.3), ("nr:money", 0, 1, 0.2)],
       voice="snarl", voice_pitch=0.9, accent=(200, 30, 30), xp=10, aggro=32, knockback_resist=0.1,
       bestiary_ja="生前は格闘家だった俊敏型。拳に巻いたバンテージは血で固まり、こちらの攻撃を横に避けてから連打を返してくる。",
       bestiary_en="A viral that used to be a fighter. Its hand wraps are stiff with dried blood, and it "
                   "sidesteps your attacks before answering with a flurry of blows.",
       weakness_ja="連打の後に隙ができる。重い武器の大振りは避けられやすい。",
       weakness_en="It's open after a flurry. Big swings with heavy weapons are easy for it to dodge."),

    _z(key="rooftop_runner", ja="屋根渡り", en="Roofrunner", cls="viral",
       height_cm=176, heads=7.6, bulk=0.86, limb=0.9, hunch=22, arm_len=1.08,
       decay=1, skin="flushed", tone=1,
       outfit=[O("hoodie", color=(40, 40, 44), hood="up", torn=2),
               O("work_pants", color=(70, 76, 60), cargo=True, torn=1),
               O("sneakers", color=(180, 60, 30), color2=(40, 40, 40)),
               O("gloves", kind="fingerless", color=(20, 20, 20)),
               O("backpack", kind="daypack", color=(40, 40, 40), torn=2)],
       mutations=[M("dark_veins", on=["neck", "head"], density=1),
                  M("missing_cheek_teeth", side="l", size=1)],
       eyes="bloodshot", hp=14, speed=0.38, damage=4, attack="lunge", attacks=["double_swipe"],
       locomotion="sprint", resist=_res(uv=0.4), gore=_gore(),
       abilities=["parkour_chase", "wall_climb"],
       spawn=_spawn("any", 6, (1, 2), site=["rooftop"]),
       loot=[("nr:infected_trophy", 0, 1, 0.25), ("nr:duct_tape", 0, 1, 0.3), ("nr:bandage", 0, 1, 0.2)],
       voice="snarl", voice_pitch=1.1, accent=(180, 60, 30), xp=9, aggro=36,
       bestiary_ja="かつて屋上を駆けていたランナーの成れの果て。乗り越えや壁登りを使い、屋根から屋根へと追ってくる。"
                   "プレイヤーと同じ道を走ってくる唯一の感染者。",
       bestiary_en="What remains of a runner who once ruled the rooftops. It vaults and climbs to follow you "
                   "from roof to roof. It is the only infected that can take the same routes you do.",
       weakness_ja="体力は最低クラス。空中で迎え撃つかドロップキックで落とす。",
       weakness_en="Among the frailest infected. Hit it mid-air or drop-kick it off the roof."),

    _z(key="berserker", ja="狂乱者", en="Frenzied", cls="viral",
       height_cm=182, heads=7.3, bulk=1.05, limb=1.08, hunch=18, arm_len=1.05,
       decay=1, skin="flushed", tone=0,
       outfit=[O("shirt", cut="dress", sleeves="rolled", open=3, tucked=False, color=(200, 200, 190),
                 torn=2, bloody=3),
               O("necktie", color=(30, 30, 60), loosened=True, torn=1),
               O("slacks", color=(30, 30, 34), torn=1),
               O("dress_shoes", kind="oxford"),
               O("hair", style="messy", color=(150, 110, 70))],
       mutations=[M("dark_veins", on=["head", "neck", "chest", "arm_r", "arm_l"], density=3),
                  M("veins_glowing", on=["head", "neck", "chest", "arm_r", "arm_l"],
                    color=(230, 40, 30), pulse_hz=3.0, only_phase="frenzy.frenzy")],
       eyes="bloodshot", hp=22, speed=0.32, damage=5, attack="double_swipe", attacks=["claw_flurry", "tackle"],
       locomotion="sprint", resist=_res(uv=0.4), gore=_gore(bleed_mult=1.3),
       abilities=["frenzy", "wall_climb"],
       spawn=_spawn("any", 6, (1, 2), site=["street", "office"]),
       loot=[("nr:infected_trophy", 0, 1, 0.25), ("nr:money", 0, 2, 0.3)],
       voice="shriek_high", voice_pitch=0.8, accent=(230, 40, 30), xp=10, aggro=32,
       bestiary_ja="傷を負うほど凶暴になる俊敏型。体力が減ると全身の血管が赤く光り、速さも攻撃も増す。",
       bestiary_en="A viral that gets more savage the more it is hurt. When its health drops, every vein "
                   "glows red and it grows faster and hits harder.",
       weakness_ja="狂乱の前に一気に倒す。狂乱中は距離を取る。",
       weakness_en="Finish it before it frenzies. Keep your distance while it rages."),

    _z(key="deadfaker", ja="死にまね", en="Deadfaker", cls="viral",
       height_cm=174, heads=7.2, bulk=0.95, limb=0.95, hunch=12, arm_len=1.04,
       decay=2, skin="ashen", tone=3,
       outfit=[O("t_shirt", color=(200, 190, 170), bloody=3, torn=2),
               O("jeans", color=(60, 70, 90), bloody=2),
               O("sneakers", color=(120, 120, 120), bloody=1),
               O("hair", style="short", color=(30, 26, 22))],
       mutations=[M("exposed_ribs", side="l", count=3), M("torn_throat", size=2),
                  M("skin_peeled", on=["chest"], coverage=0.3)],
       eyes="bloodshot", hp=20, speed=0.33, damage=5, attack="lunge", attacks=["grab_bite"],
       locomotion="sprint", resist=_res(uv=0.4), gore=_gore(),
       abilities=["play_dead", "wall_climb"],
       spawn=_spawn("any", 6, (1, 1), site=["street", "parking", "hospital"]),
       loot=[("nr:infected_trophy", 0, 1, 0.3), ("nr:money", 0, 2, 0.3), ("nr:rags", 0, 1, 0.3)],
       voice="snarl", voice_pitch=0.95, accent=(96, 8, 10), xp=9, aggro=24,
       bestiary_ja="死体の山に紛れ、死んだふりをする俊敏型。近づいた獲物に跳ね起きて襲いかかる。"
                   "一度は死んだふりをし直すこともある。",
       bestiary_en="A viral that hides among the dead and plays possum. When prey comes close, it springs up "
                   "and attacks. It may even play dead a second time.",
       weakness_ja="怪しい死体には遠くから矢を一発。",
       weakness_en="Put an arrow into suspicious corpses from a distance."),

    _z(key="skitter", ja="逃げ足", en="Skitter", cls="viral",
       height_cm=170, heads=7.8, bulk=0.75, limb=0.75, hunch=36, arm_len=1.12,
       decay=2, skin="ashen", tone=0,
       outfit=[O("layered_rags", kind="loincloth", layers=1, color=(70, 64, 56), dirty=3)],
       mutations=[M("tumor_cluster", on="head", size=1, count=3, color=(200, 170, 190)),
                  M("exposed_spine", length=10),
                  M("pustules", on=["torso", "chest", "arm_r", "arm_l"], density=1,
                    color=(180, 255, 140), glow=(180, 255, 140))],
       eyes="glowing_green", hp=14, speed=0.38, damage=2, attack="swipe", attacks=["bite"],
       locomotion="scuttle", resist=_res(uv=0.6), gore=_gore(blood="bile"),
       abilities=["flee_bolt", "toxic_trail", "wall_climb"],
       spawn=_spawn("night", 3, (1, 1), site=["rooftop", "plaza"]),
       loot=[("nr:mutated_tissue", 1, 3, 1.0), ("nr:infected_trophy", 1, 1, 0.5), ("nr:inhibitor", 0, 1, 0.05)],
       voice="chitter", accent=(180, 255, 140), xp=14, aggro=16,
       bestiary_ja="光る結節に覆われた、毛のない痩せた感染者。人を見ると四つ足で逃げ出し、毒の跡を残す。"
                   "体内の変異組織は非常に価値が高い。",
       bestiary_en="A thin, hairless infected covered in glowing nodes. It bolts on all fours the moment it "
                   "sees you, leaving a toxic trail. The mutated tissue inside it is extremely valuable.",
       weakness_ja="逃げ足が速い。弓かクロスボウで先に足を止める。",
       weakness_en="Very fast when fleeing. Stop it first with a bow or crossbow."),

    # =======================================================================
    #  特殊感染者 special（11）— 変異で役割を持った個体。体力 60〜200
    # =======================================================================
    _z(key="klaxon", ja="叫喚者", en="Klaxon", cls="special",
       height_cm=178, heads=7.4, bulk=0.9, limb=0.88, hunch=24, arm_len=1.0,
       decay=3, skin="jaundiced", tone=1,
       outfit=[O("headphones", kind="over_ear", worn="neck", color=(30, 30, 30)),
               O("t_shirt", color=(90, 60, 110), print="logo", torn=3),
               O("jeans", color=(60, 64, 80), torn=2),
               O("sneakers", color=(200, 200, 200), dirty=2)],
       mutations=[M("throat_sac", size=3, veins=True),
                  M("exposed_lungs", side="both"),
                  M("elongated_jaw", length=1.4, split=True),
                  M("exposed_ribs", side="both", count=4)],
       eyes="bloodshot", hp=60, speed=0.24, damage=3, attack="scream", attacks=["swipe"],
       locomotion="stagger", resist=_res(pierce=1.3),
       gore=_gore(weak_spots=[dict(part="head", zone="throat", mult=3.0, ability="sac_rupture", once=True)],
                  breakables=dict(throat_sac=1), stagger_frac=0.2),
       abilities=["howl_alarm", "keep_distance", A("sac_rupture", kind="bile")],
       spawn=_spawn("any", 3, (1, 1), site=["street", "plaza", "rooftop"]),
       loot=[("nr:mutated_tissue", 1, 2, 0.8), ("nr:infected_trophy", 1, 1, 0.6), ("nr:chemicals", 0, 1, 0.3)],
       voice="howl", accent=(220, 180, 90), xp=20, aggro=28,
       bestiary_ja="喉の膨れた袋で警報のような叫びを上げる特殊感染者。叫ぶと周囲の感染者が集まり、俊敏型が呼び寄せられる。"
                   "自分は戦わず距離を取ろうとする。",
       bestiary_en="A special infected that sounds an alarm-like howl through the swollen sac in its throat. "
                   "Each howl draws in every nearby infected and calls fresh virals. It avoids fighting and keeps its distance.",
       weakness_ja="叫ぶ前に喉の袋を撃ち抜く。袋が破れると二度と叫べない。",
       weakness_en="Shoot the throat sac before it howls. Once burst, it can never howl again."),

    _z(key="spewer", ja="吐酸者", en="Spewer", cls="special",
       height_cm=176, heads=7.2, bulk=1.1, limb=0.95, hunch=20, arm_len=1.02,
       decay=3, skin="necrotic_purple", tone=2,
       outfit=[O("coveralls", color=(60, 90, 60), rolled_top=True, dirty=3),
               O("boots", kind="rubber", color=(30, 40, 30)),
               O("gloves", kind="rubber", color=(200, 120, 30))],
       mutations=[M("acid_sacs", where="neck", count=2, glow=(150, 255, 60)),
                  M("acid_sacs", where="cheeks", count=2, glow=(150, 255, 60)),
                  M("elongated_jaw", length=1.3, teeth="needle"),
                  M("pustules", on=["chest", "arm_l"], density=2, color=(150, 255, 60), glow=(150, 255, 60)),
                  M("skin_peeled", on=["chest", "head"], coverage=0.35)],
       eyes="glowing_green", hp=70, speed=0.22, damage=6, attack="spit", attacks=["vomit"],
       locomotion="stagger", resist=_res(toxic=0.0, fire=1.2),
       gore=_gore(blood="acid", corpse="melt",
                  weak_spots=[dict(part="head", zone="throat", mult=2.5, ability="sac_rupture", once=True)],
                  breakables=dict(acid_sac_neck=1, acid_sac_cheeks=1)),
       abilities=["acid_spit", "acid_puddle", A("sac_rupture", kind="acid", radius=2.0, dmg=3),
                  "keep_distance"],
       spawn=_spawn("any", 3, (1, 1), site=["sewer", "street", "warehouse"]),
       loot=[("nr:chemicals", 1, 3, 0.8), ("nr:mutated_tissue", 1, 2, 0.6), ("nr:infected_trophy", 1, 1, 0.5)],
       voice="retch", accent=(150, 255, 60), xp=22, aggro=24,
       bestiary_ja="首と頬に酸の袋を膨らませた特殊感染者。遠くから酸を吐きかけ、着弾した地面に酸だまりを残す。"
                   "死体は酸で溶けていく。",
       bestiary_en="A special infected with acid sacs swelling its neck and cheeks. It spits acid from range, "
                   "leaving acid pools wherever it lands. Its corpse dissolves in its own acid.",
       weakness_ja="首の袋を狙うと破裂する。毒は効かない。近距離は弱い。",
       weakness_en="Hit the sacs on its neck to burst them. Immune to toxins and weak up close."),

    _z(key="bruiser", ja="巨漢", en="Bruiser", cls="special",
       height_cm=210, heads=7.6, bulk=1.65, limb=1.6, hunch=18, arm_len=1.1,
       decay=2, skin="grey_green", tone=3,
       outfit=[O("apron", kind="butcher_leather", length="full", color=(70, 40, 30), stains=3),
               O("t_shirt", cut="tank", color=(200, 190, 170), bloody=3, torn=2),
               O("work_pants", color=(50, 50, 56), torn=1),
               O("boots", kind="work", color=(40, 30, 24)),
               O("gloves", kind="rubber", color=(200, 180, 60), hands="l"),
               O("held_tool", kind="rebar_sledge", color=(150, 146, 140), bloody=2),
               O("hair", style="shaved", color=(30, 26, 22))],
       mutations=[M("muscle_mass", on="arm_r", factor=1.4),
                  M("bone_spurs", on=["forearm_r"], count=2, length=2.5),
                  M("stitches", on=["chest"], kind="crude")],
       eyes="bloodshot", hp=160, speed=0.20, damage=10, attack="tool_swing", attacks=["ground_pound", "slam"],
       locomotion="brute", resist=_res(blunt=0.75, slash=0.9, pierce=0.9),
       gore=_gore(sever_mult=0.6, head_mult=1.5, stagger_frac=0.12),
       abilities=["ground_pound", "tool_wield", "heavy_body"],
       spawn=_spawn("any", 3, (1, 1), site=["warehouse", "construction", "street"]),
       loot=[("nr:scrap", 2, 4, 0.8), ("nr:mutated_tissue", 1, 2, 0.6), ("nr:infected_trophy", 1, 2, 0.8),
             ("nr:inhibitor", 0, 1, 0.08)],
       voice="roar_deep", accent=(150, 146, 140), xp=35, knockback_resist=0.9, aggro=24,
       bestiary_ja="コンクリート塊を付けた鉄筋を振り回す巨漢。右腕だけが異常に肥大し、振り下ろしと地面叩きで周囲を薙ぎ払う。"
                   "軽い武器では怯まない。",
       bestiary_en="A giant who swings a sledge made of rebar and a concrete block. Only its right arm is "
                   "grotesquely swollen, and its overhead smashes and ground pounds clear everything around it. "
                   "Light weapons won't even make it flinch.",
       weakness_ja="振り下ろしの後は隙だらけ。脚を折ると膝をつく。",
       weakness_en="Wide open after an overhead smash. Break a leg and it drops to one knee."),

    _z(key="wrecker", ja="解体屋", en="Wrecker", cls="special",
       height_cm=238, heads=8.0, bulk=1.85, limb=1.85, hunch=26, arm_len=1.22,
       decay=3, skin="bruised", tone=4,
       outfit=[O("work_pants", color=(56, 52, 44), torn=3, dirty=3),
               O("hard_hat", color=(200, 120, 30), dented=3, sticker=False)],
       mutations=[M("metal_fused", on=["arm_r", "forearm_r", "arm_l", "forearm_l", "chest"], kind="plate"),
                  M("metal_fused", on=["forearm_l"], kind="rebar"),
                  M("muscle_mass", on="chest", factor=1.3),
                  M("bone_spurs", on=["arm_r", "arm_l"], count=3, length=3.0),
                  M("skin_peeled", on=["torso"], coverage=0.4),
                  M("tumor_cluster", on="neck", size=2, count=3)],
       eyes="bloodshot", hp=200, speed=0.22, damage=12, attack="charge", attacks=["throw", "slam", "ground_pound"],
       locomotion="brute", resist=_res(blunt=0.6, slash=0.8, pierce=0.8, blast=0.8),
       gore=_gore(armored=["arm_r", "arm_l", "torso"], armor_stages=2, armor_hp=30, armor_mult=0.3,
                  armor_strip=dict(arm_r=2, arm_l=2, torso=1),
                  sever_mult=0.4, halve=False, head_mult=1.6, stagger_frac=0.1,
                  weak_spots=[dict(part="torso", zone="back", mult=1.8, ability=None, once=False)]),
       abilities=["rage_charge", "debris_throw", "ground_pound", "heavy_body", "armor_shed"],
       spawn=_spawn("any", 2, (1, 1), site=["construction", "warehouse", "plaza"]),
       loot=[("nr:scrap", 3, 6, 1.0), ("nr:mutated_tissue", 2, 4, 0.9), ("nr:infected_trophy", 2, 3, 1.0),
             ("nr:inhibitor", 0, 1, 0.15)],
       voice="roar_deep", voice_pitch=0.8, accent=(200, 120, 30), xp=55, knockback_resist=1.0, aggro=32,
       bestiary_ja="鉄板と鉄筋が肉に食い込んだ、身の丈 2 メートル半の怪物。瓦礫をもぎ取って投げ、一直線に突進してくる。"
                   "腕と胸の金属は打撃か爆発で剥がすしかない。",
       bestiary_en="A monster two and a half meters tall with steel plates and rebar fused into its flesh. It "
                   "tears up chunks of rubble to throw and charges in a straight line. The metal on its arms and "
                   "chest only comes off with blunt force or explosions.",
       weakness_ja="突進を避けて壁にぶつけると数秒怯む。そこで背中を攻める。",
       weakness_en="Sidestep its charge into a wall to stun it, then hit its back."),

    _z(key="gasbag", ja="膨れ袋", en="Gasbag", cls="special",
       height_cm=178, heads=7.0, bulk=2.0, limb=1.1, hunch=8, arm_len=0.98,
       decay=3, skin="bloated_pink", tone=1,
       outfit=[O("shirt", cut="dress", open=3, tucked=False, color=(220, 200, 160), torn=3),
               O("slacks", color=(60, 56, 50), torn=2),
               O("dress_shoes", kind="loafer", color=(60, 40, 30))],
       mutations=[M("bloated_belly", size=3, veins=True, stretch_marks=True),
                  M("pustules", on=["torso", "chest", "arm_r", "arm_l", "head"], density=3,
                    color=(180, 200, 80)),
                  M("hanging_skin", on=["chest"], flaps=2),
                  M("tumor_cluster", on="neck", size=2, count=4)],
       eyes="milky", hp=60, speed=0.17, damage=5, attack="vomit", attacks=["slam"],
       locomotion="waddle", resist=_res(toxic=0.0, blunt=1.3, pierce=1.5),
       gore=_gore(explode=True, explode_kind="toxic", blood="bile", bleed_mult=1.8,
                  gib_extra=[11, 13, 13, 15], corpse="burst", wet_burst=True,
                  weak_spots=[dict(part="torso", zone="belly", mult=2.0, ability="gas_cloud_death", once=True)]),
       abilities=["gas_cloud_death", "pustule_pop"],
       spawn=_spawn("any", 4, (1, 2), site=["sewer", "street", "hospital"]),
       loot=[("nr:chemicals", 1, 2, 0.7), ("nr:mutated_tissue", 1, 2, 0.6), ("nr:infected_trophy", 1, 1, 0.5)],
       voice="wet_choke", voice_pitch=0.75, accent=(180, 200, 80), xp=20, knockback_resist=0.5, aggro=16,
       bestiary_ja="腹がガスで膨れ上がった特殊感染者。腹を突き刺すか倒すと破裂し、毒ガスが辺りに広がる。"
                   "殴るたびに膿疱が弾けて毒液が飛ぶ。",
       bestiary_en="A special infected with a belly bloated with gas. Stab the belly or kill it and it bursts, "
                   "flooding the area with toxic gas. Every hit pops pustules that spray toxic fluid.",
       weakness_ja="遠くから矢か銃で腹を撃つ。近くで倒さないこと。",
       weakness_en="Shoot the belly from a distance with arrows or guns. Never kill it up close."),

    _z(key="ticker", ja="破裂者", en="Ticker", cls="special",
       height_cm=172, heads=7.2, bulk=1.25, limb=1.0, hunch=10, arm_len=1.0,
       decay=2, skin="necrotic_purple", tone=2,
       outfit=[O("jeans", color=(40, 44, 56), torn=3, bloody=1),
               O("hair", style="shaved", color=(30, 26, 22), patchy=3)],
       mutations=[M("explosive_nodes", count=9, glow=(255, 150, 40), pulse_hz=1.5),
                  M("tumor_cluster", on="chest", size=3, count=5, color=(220, 120, 90)),
                  M("veins_glowing", on=["chest", "torso", "neck", "head"], color=(255, 150, 40), pulse_hz=1.5)],
       eyes="glowing_orange", hp=60, speed=0.27, damage=12, attack="explode", attacks=[],
       locomotion="lurch", resist=_res(fire=2.0, blast=3.0),
       gore=_gore(explode=True, explode_kind="blast", bleed_mult=1.5, corpse="burst",
                  gib_extra=[11, 12, 13, 13, 14, 15],
                  weak_spots=[dict(part="torso", zone="nodes", mult=1.5, ability="detonate", once=True)]),
       abilities=["detonate"],
       spawn=_spawn("any", 3, (1, 1), site=["street", "parking", "gas_station"]),
       loot=[("nr:gunpowder_pouch", 1, 2, 0.6), ("nr:mutated_tissue", 1, 1, 0.5), ("nr:chemicals", 0, 1, 0.3)],
       voice="whimper", accent=(255, 150, 40), xp=18, aggro=24,
       bestiary_ja="全身の結節が橙色に脈打つ、歩く爆弾。近づくと点滅が速くなり、数秒後に爆発する。"
                   "爆発は周りの感染者も巻き込む。",
       bestiary_en="A walking bomb whose nodes pulse orange. The pulsing quickens as it closes in, and it "
                   "explodes seconds later. The blast takes nearby infected with it.",
       weakness_ja="結節を遠くから撃てば早めに爆発する。群れの中で起爆させる。",
       weakness_en="Shoot the nodes from range to set it off early, ideally in the middle of a horde."),

    _z(key="rammer", ja="突進者", en="Rammer", cls="special",
       height_cm=198, heads=7.8, bulk=1.5, limb=1.4, hunch=30, arm_len=1.1,
       decay=2, skin="bruised", tone=4,
       outfit=[O("t_shirt", cut="jersey", print="number", number="12", color=(180, 30, 40),
                 color2=(240, 240, 240), torn=2, dirty=2),
               O("running_shorts", color=(230, 230, 230), dirty=2),
               O("sneakers", kind="cleats", color=(30, 30, 30), color2=(230, 230, 230))],
       mutations=[M("bone_plates", on=["head", "chest", "arm_r", "arm_l"], thickness=2),
                  M("muscle_mass", on="neck", factor=1.5),
                  M("bone_spurs", on=["head"], count=2, length=3.0)],
       eyes="bloodshot", hp=120, speed=0.24, damage=9, attack="charge", attacks=["tackle", "double_swipe"],
       locomotion="brute", resist=_res(blunt=0.8, slash=0.9),
       gore=_gore(armored=["head"], armor_stages=2, armor_hp=25, armor_mult=0.2,
                  armor_break=dict(blunt=1.6, blast=1.5, slash=0.3, pierce=0.5),
                  sever_mult=0.7, stagger_frac=0.15,
                  weak_spots=[dict(part="torso", zone="back", mult=2.0, ability=None, once=False)]),
       abilities=["rage_charge", "bone_plate", "heavy_body", "armor_shed"],
       spawn=_spawn("any", 3, (1, 1), site=["street", "stadium", "plaza"]),
       loot=[("nr:infected_trophy", 1, 2, 0.9), ("nr:mutated_tissue", 1, 2, 0.6), ("nr:scrap", 0, 2, 0.4),
             ("nr:inhibitor", 0, 1, 0.05)],
       voice="roar_deep", voice_pitch=1.1, accent=(180, 30, 40), xp=35, knockback_resist=0.9, aggro=28,
       bestiary_ja="頭と肩が骨の装甲に覆われた突進型。頭を下げて一直線に突っ込み、壁にぶつかると数秒動けなくなる。"
                   "骨の兜は刃も矢も弾く。",
       bestiary_en="A charger whose head and shoulders are sheathed in bone armor. It lowers its head and "
                   "barrels straight at you, and if it slams into a wall it is stunned for several seconds. "
                   "The bone helm turns aside blades and arrows.",
       weakness_ja="壁を背にして突進を避け、気絶中に背中を斬る。骨の兜は打撃で割れる。",
       weakness_en="Dodge its charge with a wall at your back, then slash its back while it is stunned. "
                   "Blunt hits crack the bone helm."),

    _z(key="keener", ja="哭き女", en="Keener", cls="special",
       height_cm=186, heads=8.0, bulk=0.82, limb=0.85, hunch=22, arm_len=1.2,
       decay=2, skin="ashen", tone=0, female=True, digitigrade=True,
       outfit=[O("torn_dress", style="evening", length="knee", color=(40, 30, 40), torn=3, bloody=2),
               O("hair", style="long", color=(16, 16, 18), length=1.8)],
       mutations=[M("elongated_jaw", length=1.5, split=True, teeth="needle"),
                  M("claws", length=3, hands="both", color=(30, 24, 24)),
                  M("elongated_limbs", arms=1.15, legs=1.15),
                  M("exposed_spine", length=10, spikes=True)],
       eyes="milky", hp=140, speed=0.32, damage=8, attack="pounce", attacks=["scream", "claw_flurry"],
       locomotion="leap", resist=_res(uv=0.8), gore=_gore(blood="dark", stagger_frac=0.15),
       abilities=["long_leap", "keen_scream", "wall_climb"],
       spawn=_spawn("any", 2, (1, 1), site=["rooftop", "church", "apartment"]),
       loot=[("nr:mutated_tissue", 2, 3, 0.9), ("nr:infected_trophy", 1, 2, 1.0), ("nr:inhibitor", 0, 1, 0.1)],
       voice="wail", accent=(40, 30, 40), xp=45, knockback_resist=0.3, aggro=40,
       bestiary_ja="長い黒髪で顔を隠した、手足の長い女の感染者。屋根から屋根へ長い跳躍で迫り、金切り声で人を吹き飛ばす。",
       bestiary_en="A long-limbed female infected whose face is hidden by long black hair. It closes in with "
                   "huge leaps from roof to roof and blasts people back with its shriek.",
       weakness_ja="叫びの直後と着地の瞬間が狙い目。UV で怯む。",
       weakness_en="Strike right after a shriek or the moment it lands. UV makes it flinch."),

    _z(key="reanimator", ja="蘇生者", en="Reanimator", cls="special",
       height_cm=190, heads=7.8, bulk=0.95, limb=0.9, hunch=26, arm_len=1.15,
       decay=4, skin="fungal_ochre", tone=1,
       outfit=[O("layered_rags", kind="robe", layers=2, color=(20, 20, 24), color2=(230, 230, 230), torn=2)],
       mutations=[M("spore_vents", on=["chest", "arm_r", "arm_l", "head"], count=6, spores=(160, 255, 220)),
                  M("tendrils", where="mouth", count=6, length=1.0),
                  M("fungal_growth", on=["head", "neck", "chest"], coverage=0.5, color=(200, 190, 150),
                    caps=8, glow=(120, 255, 200)),
                  M("exposed_skull", coverage=0.4),
                  M("veins_glowing", on=["neck", "chest", "arm_r", "arm_l"], color=(120, 255, 200), pulse_hz=0.5)],
       eyes="glowing_cyan", hp=110, speed=0.20, damage=6, attack="swipe", attacks=["scream"],
       locomotion="stalk", resist=_res(fire=1.6, toxic=0.0, uv=0.6), gore=_gore(blood="dark"),
       abilities=["reanimate", "spore_cloud", "keep_distance"],
       spawn=_spawn("any", 2, (1, 1), site=["church", "hospital", "hive"]),
       loot=[("nr:mutated_tissue", 2, 3, 0.9), ("nr:uv_shroom", 1, 2, 0.7), ("nr:infected_trophy", 1, 2, 1.0),
             ("nr:inhibitor", 0, 1, 0.1)],
       voice="whisper_rasp", accent=(120, 255, 200), xp=45, knockback_resist=0.3, aggro=28,
       bestiary_ja="胞子をまとった僧衣の感染者。倒れた感染者を菌糸の触手で蘇らせ、胞子の雲で生存者の免疫を削る。"
                   "頭を潰された死体は蘇らない。",
       bestiary_en="A spore-cloaked infected in a priest's robe. It raises fallen infected with fungal tendrils "
                   "and its spore clouds drain survivors' immunity. Corpses with crushed heads stay dead.",
       weakness_ja="火に非常に弱い。蘇生の詠唱中に攻撃して止める。倒した感染者は頭を潰しておく。",
       weakness_en="Extremely weak to fire. Interrupt it mid-chant. Crush the heads of anything you kill."),

    _z(key="juggernaut", ja="装甲巨兵", en="Juggernaut", cls="special",
       height_cm=196, heads=7.2, bulk=1.6, limb=1.5, hunch=10, arm_len=1.04,
       decay=3, skin="necrotic_purple", tone=2,
       outfit=[O("bomb_suit", color=(40, 60, 50), visor="cracked", dirty=2, bloody=1),
               O("boots", kind="combat", color=(20, 20, 20)),
               O("gloves", kind="leather", color=(20, 20, 20))],
       mutations=[M("tumor_cluster", on="torso", size=2, count=4),
                  M("skin_peeled", on=["arm_r", "arm_l"], coverage=0.4),
                  M("dark_veins", on=["head", "neck"], density=3)],
       eyes="clouded", hp=180, speed=0.17, damage=9, attack="slam", attacks=["headbutt", "stomp"],
       locomotion="brute", resist=_res(blast=0.4, pierce=0.5, slash=0.6, blunt=0.9, fire=0.6, shock=1.4),
       gore=_gore(armored=list(HIT_PARTS), armor_stages=3, armor_hp=40, armor_mult=0.15,
                  armor_strip=dict(arm_r=3, arm_l=3, leg_r=2, leg_l=2, torso=1, head=1),
                  armor_break=dict(blunt=1.8, blast=0.6, pierce=0.5, slash=0.3, shock=1.5, fire=0.8),
                  sever_mult=0.8, stagger_frac=0.12),
       abilities=["armor_shed", "heavy_body", "enrage_unarmored"],
       spawn=_spawn("any", 2, (1, 1), site=["police", "street", "lab"]),
       loot=[("nr:scrap", 3, 5, 1.0), ("nr:gunpowder_pouch", 1, 2, 0.6), ("nr:battery", 1, 2, 0.5),
             ("nr:infected_trophy", 2, 3, 1.0), ("nr:inhibitor", 0, 1, 0.12)],
       voice="muffled", voice_pitch=0.8, accent=(40, 60, 50), xp=50, knockback_resist=1.0, aggro=24,
       bestiary_ja="爆発物処理の防護服を着たまま感染した隊員。爆発すら耐える分厚い装甲で全身を守り、ゆっくりと確実に迫ってくる。"
                   "装甲をすべて剥がすと怒り狂い、速くなる。",
       bestiary_en="A bomb-disposal technician infected inside his suit. Armor thick enough to survive "
                   "explosions covers him head to toe, and he advances slowly and relentlessly. Strip all of it "
                   "and he flies into a rage and speeds up.",
       weakness_ja="重い打撃で装甲を一段ずつ割る。電気が効く。",
       weakness_en="Crack the armor one stage at a time with heavy blunt hits. Electricity works."),

    _z(key="longarm", ja="長腕", en="Longarm", cls="special",
       height_cm=205, heads=8.4, bulk=0.8, limb=0.85, hunch=32, arm_len=1.6,
       decay=3, skin="ashen", tone=3,
       outfit=[O("suit_jacket", color=(24, 24, 28), missing_sleeve="both", torn=3),
               O("shirt", cut="dress", sleeves="torn_off", color=(200, 200, 190), torn=2, bloody=1),
               O("necktie", color=(20, 20, 24)),
               O("slacks", color=(20, 20, 24), short=True, torn=1),
               O("dress_shoes", kind="oxford")],
       mutations=[M("elongated_limbs", arms=1.6, legs=1.05, extra_joint=True),
                  M("claws", length=2, hands="both"),
                  M("hanging_skin", on=["arm_r", "arm_l"], flaps=3),
                  M("bone_spurs", on=["forearm_r", "forearm_l"], count=1, length=1.5),
                  M("elongated_jaw", length=1.2)],
       eyes="milky", hp=100, speed=0.23, damage=7, attack="long_grab", attacks=["double_swipe"],
       locomotion="knuckle", resist=_res(slash=1.3),
       gore=_gore(sever_mult=1.4, stagger_frac=0.18), abilities=["long_grab_drag", "wall_climb"],
       spawn=_spawn("any", 2, (1, 1), site=["parking", "apartment", "office"]),
       loot=[("nr:mutated_tissue", 1, 2, 0.8), ("nr:infected_trophy", 1, 2, 1.0), ("nr:money", 1, 3, 0.5)],
       voice="groan_male", voice_pitch=0.7, accent=(24, 24, 28), xp=35, knockback_resist=0.3, aggro=24,
       bestiary_ja="破れたスーツを着た、背の高い痩せた男。袖を突き破った腕は異様に長く、離れた獲物を掴んで引き寄せる。",
       bestiary_en="A tall, gaunt man in a torn suit. Its arms have burst through the sleeves, impossibly long, "
                   "and it grabs prey from a distance and drags them in.",
       weakness_ja="腕は細く、刃で簡単に切り落とせる。掴まれたら腕を攻撃。",
       weakness_en="The arms are thin and easy to sever with a blade. If grabbed, attack the arm."),

    # =======================================================================
    #  夜の捕食者 night（4）— 夜だけ現れ、UV に弱い。体力 120〜260
    # =======================================================================
    _z(key="volatile", ja="ボラタイル", en="Volatile", cls="night",
       height_cm=205, heads=8.2, bulk=1.0, limb=1.05, hunch=34, arm_len=1.25,
       decay=2, skin="nocturnal_grey", tone=0, digitigrade=True,
       outfit=[O("jeans", cut="shorts", color=(40, 40, 46), torn=3, dirty=3)],
       mutations=[M("elongated_jaw", length=1.8, split=True, teeth="needle"),
                  M("split_face", depth=2),
                  M("spine_ridge", count=9, length=2.0),
                  M("claws", length=3, hands="both", color=(30, 26, 26)),
                  M("exposed_ribs", side="both", count=3, flesh=0.5),
                  M("skin_peeled", on=["chest", "arm_r"], coverage=0.3)],
       eyes="glowing_yellow", hp=180, speed=0.38, damage=9, attack="pounce", attacks=["claw_flurry", "grab_bite"],
       locomotion="sprint", resist=_res(uv=2.0, blunt=0.9, slash=0.9, pierce=0.9),
       gore=_gore(blood="black", sever_mult=0.8, stagger_frac=0.15),
       abilities=["wall_climb", "uv_weak", "chase_call", "pounce_pin"],
       spawn=_spawn("night", 6, (1, 3), site=["street", "rooftop", "plaza", "hive"]),
       loot=[("nr:volatile_trophy", 1, 2, 1.0), ("nr:mutated_tissue", 2, 3, 1.0), ("nr:uv_shroom", 0, 1, 0.3),
             ("nr:inhibitor", 0, 1, 0.1)],
       voice="volatile_screech", accent=(255, 220, 80), xp=80, knockback_resist=0.4, aggro=48,
       bestiary_ja="夜の街を支配する捕食者。顎が裂けるように開き、背骨に沿って棘が並ぶ。"
                   "見つかれば追跡が始まり、壁も屋根も関係なく追ってくる。",
       bestiary_en="The predator that rules the city at night. Its jaw splits wide open and a row of spikes "
                   "runs down its spine. Once it spots you the chase begins, and no wall or rooftop will stop it.",
       weakness_ja="UV の光で大きく怯み、ダメージを受ける。UV の隠れ家に逃げ込む。",
       weakness_en="UV light staggers and burns it. Run for a UV safe zone."),

    _z(key="shade_stalker", ja="闇潜み", en="Shade Stalker", cls="night",
       height_cm=190, heads=8.0, bulk=0.85, limb=0.85, hunch=28, arm_len=1.2,
       decay=2, skin="shadow_black", tone=0, digitigrade=True,
       outfit=[O("layered_rags", kind="wraps", layers=1, color=(20, 20, 20), torn=3)],
       mutations=[M("elongated_limbs", arms=1.2, legs=1.1),
                  M("claws", length=2, hands="both", color=(14, 14, 18)),
                  M("exposed_spine", length=12, spikes=True),
                  M("missing_nose"),
                  M("elongated_jaw", length=1.3, teeth="needle")],
       eyes="glowing_white", hp=140, speed=0.34, damage=8, attack="claw_flurry", attacks=["grab_bite", "lunge"],
       locomotion="stalk", resist=_res(uv=2.5, slash=1.1),
       gore=_gore(blood="black", stagger_frac=0.18),
       abilities=["shadow_cloak", "ambush_strike", "uv_weak", "wall_climb"],
       spawn=_spawn("night", 3, (1, 1), site=["sewer", "warehouse", "parking", "apartment"]),
       loot=[("nr:volatile_trophy", 1, 1, 0.6), ("nr:mutated_tissue", 1, 3, 1.0), ("nr:uv_shroom", 0, 1, 0.3)],
       voice="click", accent=(240, 240, 255), xp=70, knockback_resist=0.3, aggro=40,
       bestiary_ja="暗闇に溶け込み、光る目だけを覗かせる夜の捕食者。背後から音もなく近づき、致命的な一撃を加える。"
                   "暗所では舌打ちのような音で獲物を探る。",
       bestiary_en="A night predator that melts into the dark until only its glowing eyes show. It slips up "
                   "silently from behind and strikes a deadly blow. In the dark it hunts with tongue-clicking sounds.",
       weakness_ja="明かりの中では姿が見え、動きも鈍る。懐中電灯と UV が有効。",
       weakness_en="In light it is visible and slow. Flashlights and UV work well."),

    _z(key="cinder_hunter", ja="焦熱鬼", en="Cinder Hunter", cls="night",
       height_cm=200, heads=8.0, bulk=1.1, limb=1.05, hunch=30, arm_len=1.2,
       decay=3, skin="cinder", tone=0, digitigrade=True,
       outfit=[O("boots", kind="fire", color=(30, 26, 22), burnt=3, torn=3)],
       mutations=[M("charred_crust", coverage=0.95, ember=(255, 120, 30)),
                  M("veins_glowing", on=["head", "neck", "chest", "torso", "arm_r", "arm_l", "leg_r", "leg_l"],
                    color=(255, 140, 40), pulse_hz=2.0),
                  M("spine_ridge", count=7, length=1.5),
                  M("claws", length=2, hands="both", color=(40, 20, 10)),
                  M("elongated_jaw", length=1.5, split=True, teeth="needle")],
       eyes="glowing_orange", hp=200, speed=0.35, damage=9, attack="claw_flurry", attacks=["pounce"],
       locomotion="sprint", resist=_res(fire=0.0, uv=1.5, blast=0.8, blunt=1.3),
       gore=_gore(crumble=True, blood="ember", bleed_mult=0.4, corpse="ash", stagger_frac=0.15),
       abilities=["ember_aura", "fire_trail", "uv_weak", "wall_climb"],
       spawn=_spawn("night", 2, (1, 1), site=["gas_station", "street", "apartment"]),
       loot=[("nr:volatile_trophy", 1, 2, 1.0), ("nr:mutated_tissue", 1, 2, 0.8),
             ("minecraft:blaze_powder", 0, 2, 0.4), ("nr:gunpowder_pouch", 0, 1, 0.3)],
       voice="crackle", accent=(255, 140, 40), xp=85, knockback_resist=0.4, aggro=44,
       bestiary_ja="体のひび割れから残り火がのぞく、焼けた捕食者。周囲に火の粉をまき散らし、走った跡が燃え上がる。"
                   "火は一切効かない。",
       bestiary_en="A burned predator with embers glowing through cracks in its body. It scatters sparks "
                   "around itself and leaves burning tracks wherever it runs. Fire does nothing to it.",
       weakness_ja="打撃で炭化した体が崩れる。UV と雨に弱い。",
       weakness_en="Blunt hits break its charred body apart. Vulnerable to UV and rain."),

    _z(key="hive_warden", ja="巣守り", en="Hive Warden", cls="night",
       height_cm=230, heads=8.0, bulk=1.7, limb=1.4, hunch=36, arm_len=1.25,
       decay=4, skin="fungal_ochre", tone=0,
       outfit=[],
       mutations=[M("fungal_growth", on=["head", "neck", "chest", "torso", "arm_r", "arm_l", "leg_r", "leg_l"],
                    coverage=0.8, color=(210, 200, 160), caps=12, glow=(140, 255, 190)),
                  M("spore_vents", on=["chest", "torso"], count=8, spores=(140, 255, 190)),
                  M("tumor_cluster", on="torso", size=3, count=6, color=(190, 170, 120)),
                  M("bone_spurs", on=["arm_r", "arm_l", "chest"], count=4, length=3.0),
                  M("tendrils", where="back", count=8, length=2.0),
                  M("eyeless", bleed=False)],
       eyes="none", hp=260, speed=0.22, damage=10, attack="slam", attacks=["ground_pound", "spit"],
       locomotion="brute", resist=_res(uv=1.5, fire=1.8, toxic=0.0, blunt=0.8, slash=1.1),
       gore=_gore(blood="dark", explode=True, explode_kind="spores", gib_extra=[13, 13, 15], corpse="burst",
                  sever_mult=0.6, halve=False, stagger_frac=0.1),
       abilities=["hive_summon", "spore_cloud", "uv_weak", "heavy_body"],
       spawn=_spawn("night", 1, (1, 1), where="structure", site=["hive", "sewer"]),
       loot=[("nr:volatile_trophy", 1, 2, 1.0), ("nr:uv_shroom", 2, 4, 1.0), ("nr:mutated_tissue", 2, 4, 1.0),
             ("nr:inhibitor", 0, 1, 0.2)],
       voice="drone", accent=(140, 255, 190), xp=120, knockback_resist=1.0, aggro=32,
       bestiary_ja="感染者の巣を守る、菌糸に覆われた巨体。背中の胞子袋から俊敏型を産み落とし、胞子の雲で免疫を奪う。"
                   "目はなく、発光する菌が体を照らす。",
       bestiary_en="A fungus-choked hulk that guards the infected hives. It births virals from spore sacs on its "
                   "back and drains your immunity with spore clouds. It has no eyes; glowing fungus lights its body.",
       weakness_ja="火と UV に弱い。産み落とされた俊敏型より先に本体を焼く。",
       weakness_en="Weak to fire and UV. Burn the warden before the virals it spawns."),

    # =======================================================================
    #  ボス boss（3）— 決まった場所（とチェイス 4）にだけ現れる。体力 600〜1500
    # =======================================================================
    _z(key="flesh_colossus", ja="肉塊の巨人", en="Flesh Colossus", cls="boss",
       height_cm=340, heads=8.5, bulk=2.4, limb=2.2, hunch=30, arm_len=1.3,
       decay=4, skin="raw_flesh", tone=2,
       outfit=[O("hi_vis_vest", color=(230, 120, 30), torn=3, bloody=3),
               O("suit_jacket", color=(40, 40, 46), missing_sleeve="both", torn=3, bloody=3),
               O("layered_rags", kind="wraps", layers=3, color=(110, 90, 80), torn=3, bloody=3)],
       mutations=[M("fused_bodies", torsos=3, heads=3, arms=2),
                  M("tumor_cluster", on="chest", size=3, count=8, color=(200, 130, 120)),
                  M("exposed_ribs", side="both", count=6, flesh=0.4),
                  M("bone_spurs", on=["arm_r", "arm_l", "chest", "torso"], count=6, length=4.0),
                  M("muscle_mass", on="arm_r", factor=1.5),
                  M("hanging_skin", on=["chest", "torso", "leg_r", "leg_l"], flaps=4),
                  M("skin_peeled", on=["arm_l", "leg_l"], coverage=0.5)],
       eyes="clouded", hp=1500, speed=0.20, damage=14, attack="ground_pound", attacks=["grab_throw", "slam", "charge"],
       locomotion="brute",
       resist=_res(slash=0.8, blunt=0.8, pierce=0.7, blast=1.0, fire=1.2, shock=0.8, toxic=0.5, uv=0.3),
       gore=_gore(no_sever=["leg_r", "leg_l", "head"], halve=False, sever_mult=0.3, bleed_mult=2.0,
                  head_mult=1.2, stagger_frac=0.06, gib_extra=[11, 11, 13, 13, 13, 14, 14, 15],
                  weak_spots=[dict(part="torso", zone="heads", mult=2.0, ability="multi_head", once=False)],
                  breakables=dict(extra_head_1=1, extra_head_2=2, extra_head_3=3)),
       abilities=[A("boss_phases", thresholds=(0.6, 0.3)), "multi_head", "tumor_spawn", "ground_pound",
                  "grab_throw_player", "heavy_body"],
       spawn=_spawn("any", 1, (1, 1), where="structure", site=["stadium", "plaza", "hospital"]),
       loot=[("nr:apex_trophy", 1, 1, 1.0), ("nr:inhibitor", 1, 2, 1.0), ("nr:mutated_tissue", 4, 8, 1.0),
             ("nr:scrap", 3, 6, 1.0)],
       voice="roar_giant", accent=(150, 58, 52), xp=600, knockback_resist=1.0, aggro=64,
       boss=dict(bar=(200, 40, 40), arena=24, title_ja="肉塊の巨人", title_en="Flesh Colossus"),
       bestiary_ja="何体もの感染者が融合した肉の山。背中から生えた複数の頭がそれぞれ呻き、腫瘍の袋を落として這う感染者を産む。"
                   "地面を叩けば衝撃波が走る。",
       bestiary_en="A mountain of flesh fused from many infected. Several heads sprouting from its back each "
                   "moan on their own, and it drops tumor sacs that hatch crawlers. Each ground slam sends out a shockwave.",
       weakness_ja="背中の頭が弱点。すべて潰すと最終段階になる。",
       weakness_en="The heads on its back are weak points. Crush them all to force the final phase."),

    _z(key="subject_zero", ja="被験体ゼロ", en="Subject Zero", cls="boss",
       height_cm=228, heads=8.2, bulk=1.15, limb=1.15, hunch=18, arm_len=1.2,
       decay=1, skin="lab_white", tone=1,
       outfit=[O("hospital_gown", color=(200, 210, 214), pattern="plain", iv_line=True, torn=3, bloody=2),
               O("chain_shackles", kind="leather_straps", wrists=True, ankles=True, broken=True,
                 color=(90, 70, 50)),
               O("hair", style="shaved", color=(200, 200, 200), patchy=1)],
       mutations=[M("bone_blades", hands="both", length=3),
                  M("surgical_ports", on=["chest", "neck", "arm_r", "arm_l"], tubes=6),
                  M("stitches", on=["head", "chest"], kind="staples"),
                  M("veins_glowing", on=["head", "neck", "chest", "torso", "arm_r", "arm_l"],
                    color=(120, 220, 255), pulse_hz=1.0),
                  M("exposed_spine", length=12, spikes=True)],
       eyes="bloodshot", hp=900, speed=0.32, damage=12, attack="blade_slash",
       attacks=["lunge", "pounce", "claw_flurry"],
       locomotion="stalk", resist=_res(fire=1.5, shock=1.6, uv=0.8, slash=0.85, pierce=0.9),
       gore=_gore(no_sever=["head"], halve=False, sever_mult=0.9, head_mult=1.5, stagger_frac=0.07,
                  regrow=dict(arm_r=20, arm_l=20)),
       abilities=[A("boss_phases", thresholds=(0.5,)), "regenerate", "blade_dash", "wall_climb"],
       spawn=_spawn("any", 1, (1, 1), where="structure", site=["lab", "hospital"]),
       loot=[("nr:apex_trophy", 1, 1, 1.0), ("nr:inhibitor", 1, 2, 1.0), ("nr:chemicals", 3, 5, 1.0),
             ("nr:immunity_booster", 1, 2, 1.0)],
       voice="distorted", accent=(120, 220, 255), xp=500, knockback_resist=0.8, aggro=48,
       boss=dict(bar=(120, 220, 255), arena=20, title_ja="被験体ゼロ", title_en="Subject Zero"),
       bestiary_ja="研究所で作られた最初の変異体。前腕から骨の刃が伸び、切り落とした腕すら再生する。"
                   "火で傷を焼けば再生は止まる。",
       bestiary_en="The first mutant engineered in the lab. Bone blades jut from its forearms, and even severed "
                   "arms grow back. Burn the wounds and the regeneration stops.",
       weakness_ja="火と電気で再生を止める。切断した直後に断面を焼く。",
       weakness_en="Fire and shock halt its regeneration. Burn the stump right after a cut."),

    _z(key="night_apex", ja="夜の頂点", en="Night Apex", cls="boss",
       height_cm=280, heads=8.8, bulk=1.4, limb=1.35, hunch=36, arm_len=1.35,
       decay=3, skin="nocturnal_grey", tone=0, digitigrade=True,
       outfit=[],
       mutations=[M("elongated_jaw", length=2.2, split=True, teeth="tusk"),
                  M("split_face", depth=3, glow=(255, 200, 60)),
                  M("spine_ridge", count=13, length=3.0),
                  M("claws", length=4, hands="both", color=(24, 20, 20)),
                  M("bone_plates", on=["head", "chest", "arm_r", "arm_l"], thickness=3, color=(200, 196, 180)),
                  M("veins_glowing", on=["neck", "chest", "torso", "arm_r", "arm_l"], color=(255, 200, 60),
                    pulse_hz=1.2),
                  M("exposed_ribs", side="both", count=4, flesh=0.6)],
       eyes="glowing_red", hp=1200, speed=0.36, damage=14, attack="pounce",
       attacks=["claw_flurry", "scream", "grab_throw"],
       locomotion="sprint", resist=_res(uv=1.0, blunt=0.8, slash=0.8, pierce=0.8, blast=0.9),
       gore=_gore(armored=["head", "torso"], armor_stages=2, armor_hp=120, armor_mult=0.2,
                  armor_strip=dict(torso=2, head=1),
                  armor_break=dict(blunt=1.5, blast=1.5, pierce=0.6, slash=0.4),
                  blood="black", no_sever=["head"], halve=False, sever_mult=0.5, stagger_frac=0.06),
       abilities=[A("boss_phases", thresholds=(0.66, 0.33)), "uv_shatter", "summon_volatiles", "chase_call",
                  "uv_weak", "wall_climb", "pounce_pin", "armor_shed"],
       spawn=_spawn("night", 1, (1, 1), where="structure", site=["rooftop", "church"],
                    trigger="chase_level_4"),
       loot=[("nr:apex_trophy", 1, 1, 1.0), ("nr:volatile_trophy", 2, 4, 1.0), ("nr:inhibitor", 1, 2, 1.0),
             ("nr:uv_shroom", 2, 4, 1.0)],
       voice="volatile_screech", voice_pitch=0.7, accent=(255, 50, 30), xp=700, knockback_resist=1.0, aggro=64,
       boss=dict(bar=(255, 200, 60), arena=32, title_ja="夜の頂点", title_en="Night Apex"),
       bestiary_ja="追跡の最終段階に姿を現す、夜の頂点に立つ捕食者。叫び一つで周囲の UV ライトを消し、"
                   "ボラタイルの群れを呼ぶ。骨の装甲が頭と胸を守る。",
       bestiary_en="The apex of the night, appearing only at the final chase level. A single shriek kills every "
                   "UV light around it and calls in a pack of volatiles. Bone armor shields its head and chest.",
       weakness_ja="装甲は打撃と爆発で割る。UV が消える前に UV 改造の武器で叩く。",
       weakness_en="Crack the armor with blunt force and explosives. Hit it with UV-modded weapons before the lights go out."),
]

# ---------------------------------------------------------------------------
#  引き出しの補助（下流の生成器・データ JS が使う）
# ---------------------------------------------------------------------------
ZTYPE = {z["key"]: i for i, z in enumerate(ZOMBIES)}
ZOMBIE_BY_KEY = {z["key"]: z for z in ZOMBIES}


def zombie_id(z) -> str:
    """エンティティ ID（nr:z_<key>）。z は辞書か鍵。"""
    key = z if isinstance(z, str) else z["key"]
    return f"nr:z_{key}"


def zombies_of_class(cls: str):
    return [z for z in ZOMBIES if z["cls"] == cls]


def ability_keys(z):
    """能力の鍵のリスト（上書き付きのタプルも鍵だけにする）。"""
    return [a if isinstance(a, str) else a[0] for a in z["abilities"]]


def ability_params(z, key: str) -> dict:
    """その種類の能力の数値（語彙の既定 + ZOMBIES 側の上書き）。持っていなければ KeyError。"""
    for a in z["abilities"]:
        k, over = (a, {}) if isinstance(a, str) else a
        if k == key:
            d = copy.deepcopy(ABILITY_VOCAB[k]["params"])
            d.update(over)
            return d
    raise KeyError(f"{z['key']} has no ability {key}")


def outfit_params(item) -> dict:
    """服の部品 (鍵, 引数) の引数を既定値で埋める（共通引数の既定: torn 等は 0）。"""
    key, over = item
    d = dict(torn=0, bloody=0, dirty=0, burnt=0, wet=False)
    d.update(copy.deepcopy(OUTFIT_VOCAB[key]["params"]))
    d.update(over)
    return d


def mutation_params(item) -> dict:
    key, over = item
    d = copy.deepcopy(MUTATION_VOCAB[key]["params"])
    d.update(over)
    return d


def all_attacks(z):
    """主攻撃 + 副攻撃（重複なし、主が先頭）。"""
    out = [z["attack"]]
    for a in z["attacks"]:
        if a not in out:
            out.append(a)
    return out


def armor_sources(z) -> set:
    """服（armor）と変異（bone_plates / metal_fused の on）が装甲にできる部位の集合。"""
    parts = set()
    for key, _p in z["outfit"]:
        parts.update(OUTFIT_VOCAB[key]["armor"])
    for item in z["mutations"]:
        if item[0] in MUTATION_ARMOR:
            on = mutation_params(item)["on"]
            for b in ([on] if isinstance(on, str) else on):
                parts.add(_BONE_TO_PART[b])
    return parts


def ability_states(z) -> dict:
    """nr:ability の値の割り当て {'能力.段階': 1..7}（能力の並び順・段階の順。0 = 何もしていない）。
    アニメ・レンダー・スクリプトは全部この表を使う（scripts/data/zombies.js に書き出す）。"""
    out, v = {}, 0
    for k in ability_keys(z):
        for ph in ABILITY_VOCAB[k]["phases"]:
            v += 1
            out[f"{k}.{ph}"] = v
    return out


def part_bones(z) -> set:
    """その種類の服・変異・能力が作る専用の子ボーン名（gore.breakables・held_debris が指す）。"""
    bones = set()
    for key, _p in z["outfit"]:
        if OUTFIT_VOCAB[key]["bone"]:
            bones.add(OUTFIT_VOCAB[key]["bone"])
    for item in z["mutations"]:
        tmpl = MUTATION_VOCAB[item[0]]["bone"]
        if not tmpl:
            continue
        p = mutation_params(item)
        if "{n}" in tmpl:
            bones.update(tmpl.format(n=n) for n in range(1, int(p["heads"]) + 1))
        else:
            bones.add(tmpl.format(**p))
    if "debris_throw" in ability_keys(z):
        bones.add("held_debris")
    return bones


def initial_armor(z) -> int:
    """スポーン時に入れる nr:armor（装甲の段階。装甲が無く壊れる部品があればその最大段階。どちらも無ければ 3）。"""
    g = z["gore"]
    if g["armored"]:
        return max([g["armor_stages"]] + list(g["breakables"].values()))
    if g["breakables"]:
        return max(g["breakables"].values())
    return 3


def zombie_collision(z):
    """当たり判定の (幅, 高さ) ブロック。猫背で背が縮み、体格で幅が増える。"""
    h = z["height_cm"] / 100.0 * (1.0 - z["hunch"] / 300.0)
    if z["gore"]["pre_damage"].get("state") == "crawl":
        h = 0.6
    w = min(2.2, max(0.6, 0.6 * (z["bulk"] ** 0.7) * (1.0 if z["cls"] != "boss" else 1.4)))
    return round(w, 2), round(h, 2)


def zombie_animations(z) -> dict:
    """その種類が使うアニメーション名（gen_nr_zombie_anim が全部作る）。"""
    loc = z["locomotion"]
    d = {"walk": f"animation.nr.z.walk_{loc}", "run": f"animation.nr.z.run_{loc}"}
    for a in all_attacks(z):
        d[f"atk_{a}"] = f"animation.nr.z.atk_{a}"
    for k in ability_keys(z):
        if ABILITY_VOCAB[k]["anim"]:
            d[f"ab_{k}"] = f"animation.nr.z.ab_{k}"
        for ph in ABILITY_VOCAB[k]["phases"]:
            d[f"ab_{k}_{ph}"] = f"animation.nr.z.ab_{k}_{ph}"
    return d


def zombie_sounds(z):
    """その種類の声の効果音 ID（nr.z.<voice>.<event>）。"""
    return [f"nr.z.{z['voice']}.{e}" for e in VOICE_EVENTS]


# ---------------------------------------------------------------------------
#  自己検査
# ---------------------------------------------------------------------------
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_EN_SENT = re.compile(r"[.!?](?=\s|$)")


def _sentences_ja(s: str) -> int:
    return s.count("。")


def _sentences_en(s: str) -> int:
    return len(_EN_SENT.findall(s))


def _check_params(where, vocab, item, extra_ok=(), errs=None):
    key, params = item
    if key not in vocab:
        errs.append(f"{where}: unknown key {key!r}")
        return
    allowed = set(vocab[key]["params"]) | set(extra_ok)
    for p in params:
        if p not in allowed:
            errs.append(f"{where}: {key} has no param {p!r}")
    for p, choices in vocab[key]["choices"].items():
        v = params.get(p, vocab[key]["params"].get(p))
        for x in (v if isinstance(v, (list, tuple)) else [v]):
            if x not in choices:
                errs.append(f"{where}: {key}.{p}={x!r} not in {choices}")
    for p, v in params.items():
        if p in ("color", "color2") or (isinstance(v, tuple) and len(v) == 3 and p in vocab[key]["params"]
                                        and isinstance(vocab[key]["params"][p], tuple)):
            if not (isinstance(v, tuple) and len(v) == 3 and all(isinstance(c, int) and 0 <= c <= 255 for c in v)):
                errs.append(f"{where}: {key}.{p} must be an (R, G, B) tuple")
    on = params.get("on")
    if on is not None:
        for b in ([on] if isinstance(on, str) else on):
            if b not in BODY_BONES:
                errs.append(f"{where}: {key} on={b!r} is not a body bone")


def check_zombies() -> list:
    """全項目を検査してエラーのリストを返す（空なら合格）。"""
    errs = []
    if len(ZOMBIES) != 50:
        errs.append(f"ZOMBIES has {len(ZOMBIES)} entries, expected 50")
    counts = {c: 0 for c in CLASS_ORDER}
    last = 0
    seen = set()
    allowed_fields = set(ZOMBIE_FIELDS) | set(ZOMBIE_OPTIONAL_FIELDS)
    for i, z in enumerate(ZOMBIES):
        key = z.get("key", f"#{i}")
        w = f"[{i}] {key}"
        for f in ZOMBIE_FIELDS:
            if f not in z:
                errs.append(f"{w}: missing field {f}")
        for f in z:
            if f not in allowed_fields:
                errs.append(f"{w}: unknown field {f}")
        if any(f not in z for f in ZOMBIE_FIELDS):
            continue
        # 鍵・並び
        if not _KEY_RE.match(key):
            errs.append(f"{w}: key is not snake_case ASCII")
        if key in seen:
            errs.append(f"{w}: duplicate key")
        seen.add(key)
        cls = z["cls"]
        if cls not in CLASS_INFO:
            errs.append(f"{w}: unknown cls {cls}")
            continue
        counts[cls] += 1
        ci = CLASS_ORDER.index(cls)
        if ci < last:
            errs.append(f"{w}: class order broken ({cls} after {CLASS_ORDER[last]})")
        last = max(last, ci)
        info = CLASS_INFO[cls]
        # 名前と文
        for f in ("ja", "en", "bestiary_ja", "bestiary_en", "weakness_ja", "weakness_en"):
            if not isinstance(z[f], str) or not z[f].strip():
                errs.append(f"{w}: empty {f}")
        if not 2 <= _sentences_ja(z["bestiary_ja"]) <= 3:
            errs.append(f"{w}: bestiary_ja has {_sentences_ja(z['bestiary_ja'])} sentences (want 2-3)")
        if not 2 <= _sentences_en(z["bestiary_en"]) <= 3:
            errs.append(f"{w}: bestiary_en has {_sentences_en(z['bestiary_en'])} sentences (want 2-3)")
        # 骨格（大人だけ）
        if not 150 <= z["height_cm"] <= 360:
            errs.append(f"{w}: height_cm {z['height_cm']} out of 150..360 (no children)")
        for f, lo, hi in (("heads", 6.5, 9.0), ("bulk", 0.7, 2.5), ("limb", 0.7, 2.4),
                          ("hunch", 0, 45), ("arm_len", 0.9, 1.7), ("decay", 0, 4), ("tone", 0, 4)):
            if not lo <= z[f] <= hi:
                errs.append(f"{w}: {f}={z[f]} out of {lo}..{hi}")
        for f in ("female", "digitigrade"):
            if not isinstance(z[f], bool):
                errs.append(f"{w}: {f} must be bool")
        # 語彙
        if z["skin"] not in SKIN_VOCAB:
            errs.append(f"{w}: unknown skin {z['skin']}")
        if z["eyes"] not in EYES_VOCAB:
            errs.append(f"{w}: unknown eyes {z['eyes']}")
        if z["locomotion"] not in LOCOMOTION_VOCAB:
            errs.append(f"{w}: unknown locomotion {z['locomotion']}")
        if z["voice"] not in VOICE_VOCAB:
            errs.append(f"{w}: unknown voice {z['voice']}")
        for a in [z["attack"]] + list(z["attacks"]):
            if a not in ATTACK_VOCAB:
                errs.append(f"{w}: unknown attack {a}")
        for item in z["outfit"]:
            _check_params(f"{w} outfit", OUTFIT_VOCAB, item, OUTFIT_COMMON_PARAMS, errs)
        for item in z["mutations"]:
            _check_params(f"{w} mutation", MUTATION_VOCAB, item, (), errs)
        vocab_ok = (all(k in OUTFIT_VOCAB for k, _ in z["outfit"])
                    and all(k in MUTATION_VOCAB for k, _ in z["mutations"]))
        akeys = []
        for a in z["abilities"]:
            k, over = (a, {}) if isinstance(a, str) else a
            akeys.append(k)
            if k not in ABILITY_VOCAB:
                errs.append(f"{w}: unknown ability {k}")
                continue
            for p in over:
                if p not in ABILITY_VOCAB[k]["params"]:
                    errs.append(f"{w}: ability {k} has no param {p!r}")
        if len(set(akeys)) != len(akeys):
            errs.append(f"{w}: duplicate abilities")
        if vocab_ok and all(k in ABILITY_VOCAB for k in akeys):
            states = ability_states(z)
            if len(states) > 7:
                errs.append(f"{w}: {len(states)} ability phases do not fit nr:ability 1..7")
            for item in z["mutations"]:
                ph = item[1].get("only_phase")
                if ph is not None and ph not in states:
                    errs.append(f"{w}: only_phase {ph!r} is not one of {sorted(states)}")
            if "multi_head" in akeys:
                heads = [mutation_params(m)["heads"] for m in z["mutations"] if m[0] == "fused_bodies"]
                if heads and heads[0] != ability_params(z, "multi_head")["heads"]:
                    errs.append(f"{w}: multi_head heads != fused_bodies heads")
                if heads and not 1 <= heads[0] <= 3:
                    errs.append(f"{w}: fused heads must fit nr:armor 1..3")
        if not 0.5 <= z["voice_pitch"] <= 1.5:
            errs.append(f"{w}: voice_pitch out of 0.5..1.5")
        # 釣り合い
        lo, hi = info["hp"]
        if not lo <= z["hp"] <= hi:
            errs.append(f"{w}: hp {z['hp']} out of {cls} range {info['hp']}")
        lo, hi = info["speed"]
        if not lo <= z["speed"] <= hi:
            errs.append(f"{w}: speed {z['speed']} out of {cls} range {info['speed']}")
        lo, hi = info["damage"]
        if not (lo <= z["damage"] <= hi and DAMAGE_RANGE[0] <= z["damage"] <= DAMAGE_RANGE[1]):
            errs.append(f"{w}: damage {z['damage']} out of {cls} range {info['damage']}")
        lo, hi = info["xp"]
        if not lo <= z["xp"] <= hi:
            errs.append(f"{w}: xp {z['xp']} out of {cls} range {info['xp']}")
        if not 0.0 <= z["knockback_resist"] <= 1.0:
            errs.append(f"{w}: knockback_resist out of 0..1")
        # 耐性
        if set(z["resist"]) != set(RESIST_DEFAULT):
            errs.append(f"{w}: resist keys must be exactly {sorted(RESIST_DEFAULT)}")
        if any(v < 0 for v in z["resist"].values()):
            errs.append(f"{w}: negative resist")
        if cls == "night" and "uv_weak" not in akeys:
            errs.append(f"{w}: night hunters must have uv_weak")
        if "uv_weak" in akeys and z["resist"]["uv"] <= 0:
            errs.append(f"{w}: uv_weak needs resist.uv > 0")
        # ゴア
        g = z["gore"]
        if set(g) != set(GORE_DEFAULTS):
            errs.append(f"{w}: gore keys differ from GORE_KEYS")
        if set(GORE_KEYS) != set(GORE_DEFAULTS):
            errs.append("GORE_KEYS and GORE_DEFAULTS differ")
        for p in g["armored"] + g["no_sever"]:
            if p not in HIT_PARTS:
                errs.append(f"{w}: gore part {p!r} unknown")
        if g["armored"]:
            if not 1 <= g["armor_stages"] <= 3:
                errs.append(f"{w}: armored but armor_stages={g['armor_stages']}")
            if g["armor_hp"] <= 0:
                errs.append(f"{w}: armored but armor_hp <= 0")
            missing = set(g["armored"]) - (armor_sources(z) if vocab_ok else set(HIT_PARTS))
            if missing:
                errs.append(f"{w}: armored parts {sorted(missing)} have no armor outfit/mutation")
            if "armor_shed" not in akeys and "shield_block" not in akeys:
                errs.append(f"{w}: armored types need ability armor_shed")
        elif g["armor_stages"] != 0:
            errs.append(f"{w}: armor_stages set without armored parts")
        for p, lvl in g["armor_strip"].items():
            if p not in g["armored"] or not 1 <= lvl <= max(1, g["armor_stages"]):
                errs.append(f"{w}: armor_strip {p}={lvl} invalid")
        for d in g["armor_break"]:
            if d not in DTYPES:
                errs.append(f"{w}: armor_break dtype {d!r} unknown")
        pb = part_bones(z) if vocab_ok and all(k in ABILITY_VOCAB for k in akeys) else set(g["breakables"])
        for b, lvl in g["breakables"].items():
            if b not in pb:
                errs.append(f"{w}: breakable bone {b!r} is not made by its outfit/mutations ({sorted(pb)})")
            if not 1 <= lvl <= 3:
                errs.append(f"{w}: breakable {b} level {lvl} out of 1..3")
        for need, bone_hint in (("tank_burst", "gear_tank"), ("flashlight_beam", "gear_flashlight"),
                                ("sac_rupture", None), ("multi_head", "extra_head_1")):
            if need in akeys:
                if bone_hint and bone_hint not in g["breakables"]:
                    errs.append(f"{w}: {need} needs breakables[{bone_hint}]")
                if bone_hint is None and not g["breakables"]:
                    errs.append(f"{w}: {need} needs its sac bones in breakables")
        if g["blood"] not in BLOOD_VOCAB:
            errs.append(f"{w}: unknown blood {g['blood']}")
        if g["explode_kind"] not in EXPLODE_KINDS:
            errs.append(f"{w}: unknown explode_kind {g['explode_kind']}")
        if g["explode"] != (g["explode_kind"] != "none"):
            errs.append(f"{w}: explode and explode_kind disagree")
        if g["corpse"] not in CORPSE_KINDS:
            errs.append(f"{w}: unknown corpse {g['corpse']}")
        for ws in g["weak_spots"]:
            if set(ws) != {"part", "zone", "mult", "ability", "once"}:
                errs.append(f"{w}: weak_spot keys {sorted(ws)}")
                continue
            if ws["part"] not in HIT_PARTS or ws["zone"] not in WEAK_ZONES:
                errs.append(f"{w}: weak_spot part/zone invalid")
            if ws["ability"] is not None and ws["ability"] not in akeys:
                errs.append(f"{w}: weak_spot ability {ws['ability']} not in abilities")
            if ws["ability"] is not None and "weak_spot" not in ABILITY_VOCAB[ws["ability"]]["trigger"]:
                errs.append(f"{w}: ability {ws['ability']} is not triggered by weak_spot")
        for p, v in g["pre_damage"].items():
            if p not in PROPERTY_ENUMS or v not in PROPERTY_ENUMS[p]:
                errs.append(f"{w}: pre_damage {p}={v} invalid")
        for p in g["regrow"]:
            if p not in HIT_PARTS:
                errs.append(f"{w}: regrow part {p} invalid")
        if g["regrow"] and "regenerate" not in akeys:
            errs.append(f"{w}: regrow needs ability regenerate")
        for n in g["gib_extra"]:
            if not 11 <= n <= 15:
                errs.append(f"{w}: gib_extra {n} not a generic gib part")
        if g["crumble"] and g["blood"] != "ash" and g["blood"] != "ember":
            errs.append(f"{w}: crumble wants ash/ember blood")
        # 能力が要る部品
        okeys = [k for k, _ in z["outfit"]]
        if "tool_wield" in akeys and "held_tool" not in okeys:
            errs.append(f"{w}: tool_wield without held_tool")
        if "tool_swing" in all_attacks(z) and "held_tool" not in okeys:
            errs.append(f"{w}: tool_swing without held_tool")
        if "shield_block" in akeys and "riot_shield" not in okeys:
            errs.append(f"{w}: shield_block without riot_shield")
        if "tank_burst" in akeys and "air_tank" not in okeys:
            errs.append(f"{w}: tank_burst without air_tank")
        if "flashlight_beam" in akeys and "flashlight" not in okeys:
            errs.append(f"{w}: flashlight_beam without flashlight")
        mkeys = [k for k, _ in z["mutations"]]
        if "multi_head" in akeys and "fused_bodies" not in mkeys:
            errs.append(f"{w}: multi_head without fused_bodies")
        if "sac_rupture" in akeys and not ({"throat_sac", "acid_sacs"} & set(mkeys)):
            errs.append(f"{w}: sac_rupture without a sac mutation")
        if "detonate" in akeys and "explosive_nodes" not in mkeys:
            errs.append(f"{w}: detonate without explosive_nodes")
        if z["eyes"] == "none" and "eyeless" not in mkeys:
            errs.append(f"{w}: eyes none without eyeless mutation")
        # スポーン
        s = z["spawn"]
        if s.get("time") not in SPAWN_TIMES:
            errs.append(f"{w}: spawn.time invalid")
        if not isinstance(s.get("weight"), int) or s["weight"] < 1:
            errs.append(f"{w}: spawn.weight must be int >= 1")
        grp = s.get("group", ())
        if len(grp) != 2 or not 1 <= grp[0] <= grp[1]:
            errs.append(f"{w}: spawn.group invalid")
        if s.get("where") not in SPAWN_WHERE:
            errs.append(f"{w}: spawn.where invalid")
        for site in s.get("site", []):
            if site not in SPAWN_SITES:
                errs.append(f"{w}: spawn.site {site} unknown")
        if cls == "boss" and s.get("where") != "structure":
            errs.append(f"{w}: bosses must spawn as structure")
        if cls == "night" and s.get("time") != "night":
            errs.append(f"{w}: night hunters spawn at night")
        # ルート
        if not z["loot"]:
            errs.append(f"{w}: empty loot")
        for row in z["loot"]:
            if len(row) != 4:
                errs.append(f"{w}: loot row {row} must be (item, min, max, chance)")
                continue
            item, lo, hi, ch = row
            if item not in SHARED_LOOT_ITEMS and not item.startswith("minecraft:"):
                errs.append(f"{w}: loot item {item} not shared/vanilla")
            if not (isinstance(lo, int) and isinstance(hi, int) and 0 <= lo <= hi):
                errs.append(f"{w}: loot {item} counts invalid")
            if not 0.0 < ch <= 1.0:
                errs.append(f"{w}: loot {item} chance invalid")
        if cls == "boss" and not any(r[0] == "nr:apex_trophy" for r in z["loot"]):
            errs.append(f"{w}: bosses drop nr:apex_trophy")
        if cls == "boss" and not isinstance(z["boss"], dict):
            errs.append(f"{w}: bosses need boss dict")
        if cls != "boss" and z["boss"] is not None:
            errs.append(f"{w}: only bosses have boss dict")
        if len(z["accent"]) != 3 or not all(0 <= c <= 255 for c in z["accent"]):
            errs.append(f"{w}: accent must be RGB")
    for c in CLASS_ORDER:
        if counts[c] != CLASS_INFO[c]["count"]:
            errs.append(f"class {c}: {counts[c]} entries, expected {CLASS_INFO[c]['count']}")
    # 能力の引数が指すゾンビの鍵
    for k, ab in ABILITY_VOCAB.items():
        for t in ab["trigger"]:
            if t not in ABILITY_TRIGGERS:
                errs.append(f"ability {k}: unknown trigger {t}")
        pool = ab["params"].get("pool")
        for p in pool or []:
            if p not in ZOMBIE_BY_KEY:
                errs.append(f"ability {k}: pool key {p} is not a zombie")
    for k, at in ATTACK_VOCAB.items():
        for f in ("effect", "effect2"):
            e = at.get(f)
            if e is not None and e not in ATTACK_EFFECTS:
                errs.append(f"attack {k}: unknown {f} {e}")
        if at["fallback"] is not None and at["fallback"] not in ATTACK_VOCAB:
            errs.append(f"attack {k}: unknown fallback {at['fallback']}")
    # 語彙の数（発注の約束）
    if not 35 <= len(OUTFIT_VOCAB) <= 60:
        errs.append(f"OUTFIT_VOCAB has {len(OUTFIT_VOCAB)} entries (want 35-60)")
    if not 25 <= len(MUTATION_VOCAB) <= 40:
        errs.append(f"MUTATION_VOCAB has {len(MUTATION_VOCAB)} entries (want 25-40)")
    for k, v in OUTFIT_VOCAB.items():
        for b in v["bones"]:
            if b not in BODY_BONES:
                errs.append(f"outfit {k}: bone {b} not a body bone")
    for k, v in MUTATION_VOCAB.items():
        for b in v["bones"]:
            if b not in BODY_BONES:
                errs.append(f"mutation {k}: bone {b} not a body bone")
    return errs


def unused_zombie_vocab() -> dict:
    """どのゾンビも使っていない語彙（情報として表示。エラーではない）。"""
    used = {"outfit": set(), "mutation": set(), "skin": set(), "eyes": set(), "attack": set(),
            "locomotion": set(), "ability": set(), "voice": set(), "blood": set()}
    for z in ZOMBIES:
        used["outfit"].update(k for k, _ in z["outfit"])
        used["mutation"].update(k for k, _ in z["mutations"])
        used["skin"].add(z["skin"])
        used["eyes"].add(z["eyes"])
        used["attack"].update(all_attacks(z))
        used["locomotion"].add(z["locomotion"])
        used["ability"].update(ability_keys(z))
        used["voice"].add(z["voice"])
        used["blood"].add(z["gore"]["blood"])
    vocab = {"outfit": OUTFIT_VOCAB, "mutation": MUTATION_VOCAB, "skin": SKIN_VOCAB, "eyes": EYES_VOCAB,
             "attack": ATTACK_VOCAB, "locomotion": LOCOMOTION_VOCAB, "ability": ABILITY_VOCAB,
             "voice": VOICE_VOCAB, "blood": BLOOD_VOCAB}
    return {k: sorted(set(vocab[k]) - used[k]) for k in vocab if set(vocab[k]) - used[k]}


def _table() -> str:
    def wcut(s, n):
        # 全角は幅 2 として切り詰め・詰め物をする
        out, w = "", 0
        for ch in s:
            cw = 2 if ord(ch) > 0x2E80 else 1
            if w + cw > n:
                break
            out += ch
            w += cw
        return out + " " * (n - w)

    head = (f"{'#':>2} {'key':<20}{'cls':<8}{wcut('名前', 22)}{'hp':>5}{'spd':>6}{'dmg':>4}  "
            f"{'attack':<13}{'loco':<9}{'skin':<16}{'eyes':<15}{'o':>2}{'m':>2}  abilities")
    lines = [head, "-" * len(head)]
    for i, z in enumerate(ZOMBIES):
        lines.append(
            f"{i:>2} {z['key']:<20}{z['cls']:<8}{wcut(z['ja'], 22)}{z['hp']:>5}{z['speed']:>6.2f}"
            f"{z['damage']:>4}  {z['attack']:<13}{z['locomotion']:<9}{z['skin']:<16}{z['eyes']:<15}"
            f"{len(z['outfit']):>2}{len(z['mutations']):>2}  {','.join(ability_keys(z))}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(_table())
    print()
    print("vocab sizes: outfit=%d mutation=%d skin=%d eyes=%d attack=%d locomotion=%d ability=%d voice=%d blood=%d"
          % (len(OUTFIT_VOCAB), len(MUTATION_VOCAB), len(SKIN_VOCAB), len(EYES_VOCAB), len(ATTACK_VOCAB),
             len(LOCOMOTION_VOCAB), len(ABILITY_VOCAB), len(VOICE_VOCAB), len(BLOOD_VOCAB)))
    print("classes: " + ", ".join(f"{c}={len(zombies_of_class(c))}" for c in CLASS_ORDER))
    unused = unused_zombie_vocab()
    if unused:
        print("unused vocab (info): " + "; ".join(f"{k}: {', '.join(v)}" for k, v in unused.items()))
    problems = check_zombies()
    if problems:
        print(f"\nNG: {len(problems)} problem(s)")
        for p in problems:
            print("  - " + p)
        sys.exit(1)
    print("\nOK: 50 zombies, all vocab references resolve")
