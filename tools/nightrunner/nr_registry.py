# -*- coding: utf-8 -*-
"""NIGHT RUNNER — 演出 ID の登録簿（作る側と使う側の契約）。

パーティクル・効果音・プレイヤーのモーション・ゾンビの一発アニメの ID を**先に固定**する。
* 作る側（gen_nr_particles / gen_nr_sounds / gen_nr_player_anim / gen_nr_zombie_anim）は
  ここに載っている ID を**すべて**作る（増やすのは自由。増やしたら使う側に伝わるよう data JS にも出る）。
* 使う側（packs/nightrunner_BP/scripts/ の手書き JS）は**ここに載っている ID だけ**を使う。
  テスト（test_nr.py）は、スクリプトが使った ID が RP に実在するかを検査する。

スクリプトからパーティクルへ値を渡すときは `MolangVariableMap.setFloat("variable.<名前>", 値)`、
パーティクル側は `v.<名前> ?? 既定値` で読む（HyperDim と同じ流儀）。共通の変数名:
  count 個数 / spread 広がり(ブロック) / speed 速さ / dx,dy,dz 向き(単位ベクトル) /
  size 大きさの倍率 / life 寿命(秒) / cr,cg,cb 色(0..1) / gore ゴアレベル(0..1) / radius 半径
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
#  パーティクル  nr:<name>  ->  (説明, 読む変数)
# ---------------------------------------------------------------------------
PARTICLES = {
    # --- 血 -------------------------------------------------------------
    "blood_spray":        ("向き付きの血の噴き出し。滴は重力で落ち、地面に当たると血痕を作る", "dx dy dz speed count spread size gore"),
    "blood_burst":        ("全方向に弾ける血（打撃・切断の瞬間）", "count speed size gore"),
    "blood_mist":         ("細かい血の霧（頭が弾ける・散弾）", "size life gore"),
    "blood_drip":         ("ぽたぽた落ちる数滴", "count size"),
    "blood_fountain":     ("首・肩の断面から拍動して噴く噴水。v.life 秒続く", "dx dy dz life size gore"),
    "blood_splat_ground": ("地面に貼り付く血痕（平ら・上向き）", "size life"),
    "blood_splat_wall_x": ("±X を向いた壁の血痕（v.dx の符号で向き）", "dx size life"),
    "blood_splat_wall_z": ("±Z を向いた壁の血痕（v.dz の符号で向き）", "dz size life"),
    "blood_pool":         ("広がっていく血だまり（死体・gib の下）", "size life"),
    "blood_trail":        ("動く gib・這うゾンビが残す小さな血の点", "size"),
    "bleed_stump":        ("断面からの持続的な滴り（クライアントのアニメコントローラがロケータで出す）", ""),
    "bloody_footprint":   ("血を踏んだ足跡（平ら）", "size life"),
    # --- 肉片・骨 -----------------------------------------------------------
    "gore_chunks":        ("回転しながら飛んで跳ねる肉片", "count speed spread size"),
    "bone_shards":        ("白い骨片", "count speed"),
    "brain_matter":       ("脳の欠片（桃灰色）", "count speed"),
    "gut_strands":        ("糸を引く内臓の切れ端", "count speed"),
    "head_explode":       ("頭が弾ける複合演出（血・霧・肉片・骨・脳）", "dx dy dz size gore"),
    "sever_burst":        ("切断の瞬間の断面からの飛沫", "dx dy dz size gore"),
    "body_explode":       ("全身が弾け飛ぶ（爆発・オーバーキル）", "size gore"),
    "hit_flesh":          ("肉に当たった小さな飛沫（ヒットの手応え）", "dx dy dz"),
    "hit_spark":          ("装甲・金属に当たった火花", "dx dy dz"),
    # --- 属性・状態 -----------------------------------------------------------
    "burn_flesh":         ("焼ける肉の煙と火の粉", "size"),
    "char_flakes":        ("炭化した体が崩れる灰", "count size"),
    "fire_burst":         ("着火の炎", "size"),
    "ground_fire":        ("地面で燃え続ける炎（火炎瓶・油）", "radius life"),
    "explosion":          ("爆発（火球・煙・破片）", "size"),
    "smoke_dark":         ("黒煙", "size life"),
    "shock_arcs":         ("体のまわりの放電", "size"),
    "shock_spark":        ("感電の火花の弾け", "count"),
    "toxic_gas":          ("緑の毒ガスの雲", "radius life"),
    "toxic_burst":        ("膨れた感染者が破裂する緑の肉片", "size"),
    "acid_spit_trail":    ("酸の唾の軌跡", ""),
    "acid_splash":        ("酸の飛び散り（地面で泡立つ）", "radius life"),
    "fungal_spores":      ("菌の胞子が漂う", "radius"),
    "uv_glow":            ("UV の青紫の光の靄", "radius"),
    "uv_burn":            ("UV で焼かれる夜の感染者の煙", "size"),
    "uv_cone":            ("UV ライトの円錐（懐中電灯）", "dx dy dz"),
    "scream_wave":        ("叫びの波紋（広がる輪）", "radius"),
    "shockwave_ground":   ("地面を叩く衝撃の輪と瓦礫", "radius"),
    "revenant_aura":      ("リヴナント系の黒い靄", "size"),
    "night_eyes":         ("夜の捕食者の光る目の残光", ""),
    # --- パルクール・戦闘 -------------------------------------------------------
    "dust_land":          ("着地の土煙", "size"),
    "dust_slide":         ("スライディングの土煙", "dx dz"),
    "wall_scrape":        ("壁走り・壁登りの削れ", ""),
    "speed_lines":        ("全力疾走のスピード線", "dx dy dz"),
    "grapple_line":       ("フックのロープの点（スクリプトが線上に並べる）", ""),
    "kick_impact":        ("ドロップキックの衝撃", "dx dy dz"),
    "muzzle_flash":       ("銃口の閃光", "dx dy dz size"),
    "bullet_tracer":      ("弾道の光の筋", "dx dy dz speed"),
    "impact_dust":        ("弾がブロックに当たった土埃", ""),
    "swing_trail":        ("近接武器の振りの軌跡（属性色）", "dx dy dz cr cg cb"),
    # --- 世界・UI ---------------------------------------------------------------
    "loot_glint":         ("落ちている物資のきらめき", ""),
    "safezone_ring":      ("UV の安全地帯の境界", "radius"),
    "chase_marker":       ("追ってくる夜の捕食者の頭上の赤い脈動", ""),
    "sense_ping":         ("サバイバーセンスで見えた感染者の印", "cr cg cb"),
    "trap_spark":         ("罠の作動の火花", ""),
    "alarm_flash":        ("車のアラームの点滅", ""),
    "heal_sparkle":       ("回復のきらめき", ""),
}

# ---------------------------------------------------------------------------
#  効果音  nr.<分類>.<名前>  ->  説明
#  ゾンビの声は spec の VOICE_VOCAB から  nr.z.<voice>.<idle|alert|attack|hurt|death>
#  特殊能力は spec の ABILITY_VOCAB から   nr.ab.<ability>
#  （この二つは下の derived_* が並べる）
# ---------------------------------------------------------------------------
SOUNDS = {
    # ゴア
    "nr.gore.slash_flesh": "刃が肉を裂く", "nr.gore.blunt_flesh": "鈍器が肉を潰す",
    "nr.gore.pierce_flesh": "刺さる・弾が入る", "nr.gore.bone_crack": "骨が折れる",
    "nr.gore.bone_crunch": "骨が砕ける", "nr.gore.sever": "四肢がちぎれる",
    "nr.gore.decap": "首が飛ぶ", "nr.gore.head_pop": "頭が弾ける",
    "nr.gore.splat": "血肉が叩きつけられる", "nr.gore.squish": "ぐちゃっと潰れる",
    "nr.gore.spurt": "血が噴く", "nr.gore.gut_spill": "内臓がこぼれる",
    "nr.gore.gib_land": "ちぎれた部位が落ちる", "nr.gore.body_fall": "体が倒れる",
    "nr.gore.drip": "血が滴る", "nr.gore.burst": "体が破裂する",
    # 武器
    "nr.w.swing_light": "軽い風切り", "nr.w.swing_heavy": "重い風切り",
    "nr.w.hit_metal": "金属音", "nr.w.hit_wood": "木の打撃音", "nr.w.break": "武器が壊れる",
    "nr.w.bow_draw": "弓を引く", "nr.w.bow_release": "弓を放つ",
    "nr.w.crossbow_shot": "クロスボウを撃つ", "nr.w.crossbow_reload": "クロスボウの装填",
    "nr.w.pistol": "拳銃", "nr.w.revolver": "リボルバー", "nr.w.shotgun": "散弾銃",
    "nr.w.rifle": "ライフル", "nr.w.smg": "短機関銃", "nr.w.reload": "弾倉の交換",
    "nr.w.pump": "ポンプの往復", "nr.w.empty_click": "弾切れ", "nr.w.throw": "投げる",
    "nr.w.knife_stick": "投げナイフが刺さる",
    # 爆発・属性
    "nr.fx.explosion": "爆発", "nr.fx.fire_ignite": "着火", "nr.fx.fire_loop": "燃え続ける",
    "nr.fx.electric_zap": "放電", "nr.fx.electric_buzz": "通電の唸り",
    "nr.fx.toxic_hiss": "毒ガスの噴出", "nr.fx.acid_sizzle": "酸で溶ける",
    "nr.fx.uv_hum": "UV ライトの唸り", "nr.fx.uv_burn": "UV で焼ける",
    "nr.fx.glass_break": "ガラスが割れる", "nr.fx.metal_clang": "金属が鳴る",
    # パルクール
    "nr.pk.step_run": "走る足音", "nr.pk.jump": "跳ぶ", "nr.pk.land_soft": "軽い着地",
    "nr.pk.land_hard": "重い着地", "nr.pk.roll": "受け身", "nr.pk.vault": "乗り越え",
    "nr.pk.grab": "縁をつかむ", "nr.pk.climb": "よじ登る", "nr.pk.wallrun": "壁を走る",
    "nr.pk.slide": "スライディング", "nr.pk.dropkick": "ドロップキック",
    "nr.pk.grapple_fire": "フックの発射", "nr.pk.grapple_reel": "巻き取り",
    "nr.pk.glider_open": "グライダーを開く", "nr.pk.glider_wind": "滑空の風",
    "nr.pk.breath": "息切れ",
    # 罠・世界
    "nr.trap.spike": "スパイク", "nr.trap.beartrap": "トラバサミ",
    "nr.trap.electric": "電気トラップ", "nr.trap.alarm": "車のアラーム",
    "nr.trap.click": "仕掛けの作動音", "nr.world.barricade_hit": "バリケードを叩く",
    "nr.world.door": "扉",
    # プレイヤーの状態
    "nr.pl.heartbeat": "心音（免疫低下）", "nr.pl.immunity_warn": "免疫の警告",
    "nr.pl.immunity_restore": "免疫の回復", "nr.pl.hurt": "被弾", "nr.pl.heal": "回復",
    "nr.pl.levelup": "スキルポイント獲得", "nr.pl.grabbed": "掴まれた",
    # 夜と追跡
    "nr.chase.start": "追跡開始", "nr.chase.level_up": "追跡レベル上昇",
    "nr.chase.end": "追跡を振り切った", "nr.night.start": "夜が来る",
    "nr.day.start": "夜明け",
    # UI
    "nr.ui.click": "クリック", "nr.ui.open": "端末を開く", "nr.ui.craft": "クラフト",
    "nr.ui.error": "エラー", "nr.ui.combo": "ゴアコンボ", "nr.ui.headshot": "ヘッドショット",
    "nr.ui.kill": "撃破",
    # ボス
    "nr.boss.intro": "ボスの出現", "nr.boss.phase": "ボスの段階移行",
    "nr.boss.death": "ボス撃破",
}

ZOMBIE_VOICE_EVENTS = ("idle", "alert", "attack", "hurt", "death")

# ---------------------------------------------------------------------------
#  プレイヤーのモーション  animation.nr.p.<name>  ->  (説明, 長さ秒)
#  スクリプトは player.playAnimation("animation.nr.p.<name>", {blendOutTime, controller}) で再生
# ---------------------------------------------------------------------------
PLAYER_ANIMS = {
    # パルクール
    "vault": ("走りながら手をついて乗り越える", 0.45),
    "mantle": ("縁から体を引き上げる", 0.6),
    "climb_loop": ("壁を登る（ループ）", 0.5),
    "ledge_hang": ("縁にぶら下がる（ループ）", 1.0),
    "wallrun_l": ("左手側の壁を走る（ループ）", 0.5),
    "wallrun_r": ("右手側の壁を走る（ループ）", 0.5),
    "wall_jump": ("壁を蹴って跳ぶ", 0.4),
    "slide": ("スライディング", 0.7),
    "roll": ("前転の受け身", 0.55),
    "hard_land": ("重い着地", 0.5),
    "dropkick": ("両足のドロップキック", 0.6),
    "kick": ("前蹴り", 0.4),
    "stomp": ("倒れた相手を踏みつける", 0.5),
    "shove": ("組みついた相手を押しのける", 0.4),
    "grabbed_struggle": ("掴まれてもがく（ループ）", 0.4),
    "grapple_fire": ("フックを撃つ", 0.3),
    "grapple_pull": ("ロープに引かれて飛ぶ（ループ）", 0.5),
    "glide": ("パラグライダー（ループ）", 1.0),
    # 近接（各型 3 振り + 溜め）
    **{f"{s}_{n}": (f"{s} の振り {n}", 0.5)
       for s in ("slash_1h", "slash_2h", "blunt_1h", "blunt_2h", "stab")
       for n in ("1", "2", "3", "heavy")},
    # 飛び道具
    "bow_draw": ("弓を引く（保持）", 0.6), "bow_release": ("弓を放つ", 0.3),
    "crossbow_fire": ("クロスボウを撃つ", 0.3), "crossbow_reload": ("クロスボウの装填", 1.0),
    "pistol_fire": ("拳銃の反動", 0.2), "pistol_reload": ("拳銃の装填", 1.1),
    "rifle_fire": ("ライフルの反動", 0.35), "rifle_reload": ("ライフルの装填", 1.6),
    "shotgun_fire": ("散弾銃の反動", 0.4), "shotgun_pump": ("ポンプ", 0.45),
    "shotgun_reload": ("散弾の装填", 1.4), "smg_fire": ("短機関銃の連射の揺れ", 0.15),
    "throw_overhand": ("振りかぶって投げる", 0.5), "throw_underhand": ("下手投げ", 0.45),
    # その他
    "heal": ("包帯・救急キット", 1.2), "inject": ("ブースターを打つ", 0.8),
    "uv_flash": ("UV ライトをかざす", 0.5),
    "finisher_stomp": ("とどめの踏み潰し", 0.8), "finisher_decap": ("とどめの首刈り", 0.9),
}

# ---------------------------------------------------------------------------
#  ゾンビの一発アニメ  animation.nr.z.<name>  ->  説明
#  スクリプトは zombie.playAnimation("animation.nr.z.<name>", {blendOutTime: 0.15}) で再生。
#  常時の状態（歩き・這い・死体・ぶら下がる腕…）は gen_nr_zombie_anim のコントローラが
#  プロパティから自動で切り替えるので、スクリプトは呼ばない。
#  特殊能力は spec の ABILITY_VOCAB から  animation.nr.z.ab_<ability>（下の derived_* が並べる）
# ---------------------------------------------------------------------------
ZOMBIE_ONESHOTS = {
    "react_head": "頭に当たって仰け反る", "react_torso": "胴に当たってよろめく",
    "react_arm_r": "右腕を弾かれる", "react_arm_l": "左腕を弾かれる",
    "react_leg_r": "右脚を払われて膝が落ちる", "react_leg_l": "左脚を払われて膝が落ちる",
    "react_heavy": "重い一撃で大きく後ろへよろける", "knockdown": "倒れる",
    "getup": "起き上がる", "grab": "プレイヤーに組みつく", "bite": "組みついて噛む",
    "shoved": "押しのけられる", "climb_up": "縁へよじ登る", "stunned": "感電・気絶",
    "burn_flail": "燃えてもがく", "uv_recoil": "UV にひるむ", "alert": "気づいて振り向く",
    "sever_recoil": "部位を失ってのけぞる", "kicked": "蹴り飛ばされる",
}


def derived_voice_sounds(voice_keys):
    return [f"nr.z.{v}.{e}" for v in sorted(voice_keys) for e in ZOMBIE_VOICE_EVENTS]


def derived_ability_sounds(ability_keys):
    return [f"nr.ab.{a}" for a in sorted(ability_keys)]


def derived_ability_anims(ability_keys):
    return [f"ab_{a}" for a in sorted(ability_keys)]


def all_sound_ids(spec=None):
    ids = list(SOUNDS)
    if spec is not None:
        ids += derived_voice_sounds(spec.VOICE_VOCAB.keys())
        ids += derived_ability_sounds(spec.ABILITY_VOCAB.keys())
    return ids


def all_zombie_oneshots(spec=None):
    names = list(ZOMBIE_ONESHOTS)
    if spec is not None:
        names += derived_ability_anims(spec.ABILITY_VOCAB.keys())
    return names


if __name__ == "__main__":
    print(f"particles {len(PARTICLES)} / sounds {len(SOUNDS)} / player anims {len(PLAYER_ANIMS)}"
          f" / zombie one-shots {len(ZOMBIE_ONESHOTS)}")
