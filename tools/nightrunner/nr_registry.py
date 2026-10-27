# -*- coding: utf-8 -*-
"""NIGHT RUNNER — 演出 ID の登録簿（作る側と使う側の契約）。

パーティクル・効果音・プレイヤーのモーション・ゾンビの一発アニメの ID を**先に固定**する。
* 作る側（gen_nr_particles / gen_nr_sounds / gen_nr_player_anim / gen_nr_zombie_anim）は
  ここに載っている ID を**すべて**作る（増やすのは自由。増やしたら使う側に伝わるよう data JS にも出る）。
* 使う側（packs/nightrunner_BP/scripts/ の手書き JS）は**ここに載っている ID だけ**を使う。
  テスト（test_nr.py）は、スクリプトが使った ID が RP に実在するかを検査する。
* **演出 ID の正はここだけ**。spec（nr_spec_catalog の武器の音・改造・罠・アイテムの use.anim、
  ANIM_SETS / PLAYER_MOTIONS）はここにある名前だけを参照する（nr_spec.py の自己検査が確かめる）。
* spec から機械的に決まる ID（ゾンビの声 nr.z.*、能力の音 nr.ab.*、ゾンビの種類ごとのアニメ
  walk_/run_/atk_/ab_*）は手で並べず、`all_sound_ids(spec)` / `all_zombie_anim_names(spec)` /
  `all_zombie_oneshots(spec)` が spec（`zombie_animations(z)`）を呼んで並べる。作る側も使う側もこれを使う。
* `python3 tools/nightrunner/nr_registry.py` で単体の検査、spec との突き合わせは `nr_spec.py`。

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
    "revenant_aura":      ("蘇生者（reanimator）が死体へ伸ばす青緑の光の筋と黒い靄", "size"),
    "night_eyes":         ("夜の捕食者の光る目の残光", ""),
    # --- パルクール・戦闘 -------------------------------------------------------
    "dust_land":          ("着地・落下物・振り子丸太の土煙", "size"),
    "dust_slide":         ("スライディングの土煙", "dx dz"),
    "wall_scrape":        ("壁走り・壁登りの削れ", ""),
    "speed_lines":        ("全力疾走のスピード線", "dx dy dz"),
    "grapple_line":       ("フックのロープの点（スクリプトが線上に並べる）", ""),
    "kick_impact":        ("ドロップキックの衝撃", "dx dy dz"),
    "muzzle_flash":       ("銃口の閃光", "dx dy dz size"),
    "bullet_tracer":      ("弾道の光の筋", "dx dy dz speed"),
    "impact_dust":        ("弾がブロックに当たった土埃", ""),
    "swing_trail":        ("近接武器の振りの軌跡（属性色）", "dx dy dz cr cg cb"),
    "shell_casing":       ("排莢（真鍮の薬莢が跳ねて転がる）", "dx dy dz"),
    "arrow_trail":        ("矢・ボルトの細い風切りの尾", ""),
    "fuse_spark":         ("導火線の火花（パイプ爆弾・爆竹）", ""),
    "firecracker_pop":    ("爆竹のはじける閃光と赤い紙片", ""),
    # --- 武器の改造の見た目（nr_spec_catalog.MODS の visual）----------------------------
    "flame":              ("小さな炎（燃える布・ドラム缶の火・火炎の改造の武器）", "size"),
    "ember_trail":        ("火の粉の尾（火炎の改造）", ""),
    "toxic_drip":         ("毒の改造の緑の滴り", ""),
    "uv_trail":           ("UV の改造の紫の光の尾", ""),
    "impact_ring":        ("衝撃の改造の命中の白い輪", "dx dy dz"),
    "dust_trail":         ("砂ぼこりの尾（衝撃の改造・投げた瓦礫）", ""),
    # --- 世界・UI ---------------------------------------------------------------
    "loot_glint":         ("落ちている物資のきらめき", ""),
    "safezone_ring":      ("UV の安全地帯の境界", "radius"),
    "chase_marker":       ("追ってくる夜の捕食者の頭上の赤い脈動", ""),
    "sense_ping":         ("感知（player/sense.js）で見えた感染者の印", "cr cg cb"),
    "trap_spark":         ("罠の作動・待機中の小さな火花", ""),
    "flame_jet":          ("一方向へ噴き出す炎（ガス管・撃たれたボンベ）", "dx dy dz life"),
    "flies":              ("遺骸にたかる蝿", ""),
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
    "nr.gore.chop": "重い刃が肉と骨に食い込む（両手刃・重い片手刃の命中）",
    "nr.gore.smash": "重い打撃が肉と骨を叩き潰す（両手打撃・振り子丸太の命中）",
    # 武器
    "nr.w.swing_light": "軽い風切り", "nr.w.swing_heavy": "重い風切り",
    "nr.w.hit_metal": "金属音", "nr.w.hit_wood": "木の打撃音", "nr.w.break": "武器が壊れる",
    "nr.w.bow_draw": "弓を引く", "nr.w.bow_release": "弓を放つ",
    "nr.w.crossbow_shot": "クロスボウを撃つ", "nr.w.crossbow_reload": "クロスボウの装填",
    "nr.w.pistol": "拳銃", "nr.w.revolver": "リボルバー", "nr.w.shotgun": "散弾銃",
    "nr.w.rifle": "ライフル", "nr.w.smg": "短機関銃", "nr.w.reload": "弾倉の交換",
    "nr.w.pump": "ポンプの往復", "nr.w.empty_click": "弾切れ", "nr.w.throw": "投げる",
    "nr.w.knife_stick": "投げナイフが刺さる",
    "nr.w.reload_revolver": "シリンダーを振り出して 1 発ずつ込める", "nr.w.reload_shell": "散弾を 1 発ずつ込める",
    "nr.w.bolt_cycle": "ボルトを引いて戻す（ライフルの次弾）",
    # 武器の改造の発動（nr_spec_catalog.MODS の sound）
    "nr.w.mod_fire": "火炎の改造が燃え上がる", "nr.w.mod_shock": "感電の改造の放電",
    "nr.w.mod_bleed": "出血の改造で血が噴く", "nr.w.mod_toxic": "毒の改造の霧が噴く",
    "nr.w.mod_uv": "UV の改造が焼く唸り", "nr.w.mod_impact": "衝撃の改造の小さな破裂",
    # 爆発・属性
    "nr.fx.explosion": "爆発", "nr.fx.fire_ignite": "着火", "nr.fx.fire_loop": "燃え続ける",
    "nr.fx.electric_zap": "放電", "nr.fx.electric_buzz": "通電の唸り",
    "nr.fx.toxic_hiss": "毒ガスの噴出", "nr.fx.acid_sizzle": "酸で溶ける",
    "nr.fx.uv_hum": "UV ライトの唸り", "nr.fx.uv_burn": "UV で焼ける",
    "nr.fx.glass_break": "ガラスが割れる", "nr.fx.metal_clang": "金属が鳴る",
    "nr.fx.explosion_big": "大爆発（プロパンボンベ）", "nr.fx.gas_hiss": "ボンベ・ガス管から漏れるガスの噴出",
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
    "nr.trap.click": "仕掛けの作動音", "nr.trap.gas_burst": "ガス管が裂けて火を噴く",
    "nr.trap.uv_burst": "UV トラップが一斉に点く唸り", "nr.trap.rope_snap": "吊り縄が切れる",
    "nr.trap.wire": "有刺鉄線が服と肉を引っかく", "nr.world.barricade_hit": "バリケードを叩く",
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
    # 道具・回復アイテムを使う音（nr_spec_catalog の use.sound）
    "nr.ui.bandage": "包帯を巻く", "nr.ui.medkit": "救急キットを開けて手当てする",
    "nr.ui.inject": "注射を打つ（空気の抜ける音）", "nr.ui.eat": "食べる", "nr.ui.drink": "缶を開けて飲む",
    "nr.ui.pills": "錠剤の瓶を振る", "nr.ui.repair": "テープを巻いて武器を直す",
    "nr.ui.lockpick": "鍵穴を探るピックの金属音", "nr.ui.uv_on": "UV ライトが点く",
    "nr.ui.zoom": "双眼鏡のピントを合わせる",
    # ボス
    "nr.boss.intro": "ボスの出現", "nr.boss.phase": "ボスの段階移行",
    "nr.boss.death": "ボス撃破",
    # 乗り物（scripts/world/vehicles.js。gen_nr_sounds は名前から型を選んで作る: エンジンは 2 秒のループ）
    "nr.veh.engine_idle": "エンジンのアイドリング（2 秒のループ）", "nr.veh.engine_drive": "走るエンジンの唸り（2 秒のループ）",
    "nr.veh.start": "セルを回してエンジンがかかる", "nr.veh.stop": "エンジンが止まる",
    "nr.veh.horn": "クラクション", "nr.veh.crash": "車体が壁にぶつかって潰れる",
    "nr.veh.skid": "タイヤが鳴る急ブレーキ・横滑り", "nr.veh.door": "車の扉・トランクの開け閉め",
}

ZOMBIE_VOICE_EVENTS = ("idle", "alert", "attack", "hurt", "death")

# ---------------------------------------------------------------------------
#  プレイヤーのモーション  animation.nr.p.<name>  ->  (説明, 長さ秒)
#  スクリプトは player.playAnimation("animation.nr.p.<name>", {controller, blendOutTime, stopExpression,
#  nextState}) で再生（reference/rendering.md §9）。層（controller 名）は nr.p.move（パルクールの全身）/
#  nr.p.act（攻撃・投擲・使う動作）/ nr.p.hold（武器の構え・全力疾走のループ）。
#  「ループ」と書いたものは stopExpression で止めるか、同じ層に none を流して止める。
#  nr_spec_catalog の PLAYER_MOTIONS・ANIM_SETS・アイテムの use.anim はここの名前だけを使う。
# ---------------------------------------------------------------------------
PLAYER_ANIMS = {
    # 止める（同じ controller に流すと前のアニメが消える）
    "none": ("何もしない（同じ層の再生を止める）", 0.05),
    # パルクール
    "vault": ("走りながら片手をついて低い障害物を乗り越える", 0.45),
    "vault_high": ("2 段の障害物を両手で押して越える（スピードヴォルト）", 0.55),
    "mantle": ("縁から体を引き上げる", 0.6),
    "climb_loop": ("壁を登る。両手を交互に上へ（ループ）", 0.5),
    "ledge_hang": ("縁にぶら下がる（ループ）", 1.0),
    "wallrun_l": ("左手側の壁を走る（ループ）", 0.5),
    "wallrun_r": ("右手側の壁を走る（ループ）", 0.5),
    "wall_jump": ("壁を蹴って跳ぶ", 0.4),
    "slide": ("スライディング", 0.7),
    "slide_tackle": ("スライディングで感染者の足を払う", 0.7),
    "roll": ("前転の受け身", 0.55),
    "hard_land": ("重い着地。膝をつく", 0.5),
    "dropkick": ("両足のドロップキック", 0.6),
    "kick": ("前蹴り", 0.4),
    "stomp": ("倒れた相手を踏みつける", 0.5),
    "shove": ("組みついた相手を押しのける", 0.4),
    "grabbed_struggle": ("掴まれてもがき、振りほどく（ループ）", 0.4),
    "grapple_fire": ("フックを撃つ", 0.3),
    "grapple_pull": ("ロープに引かれて飛ぶ（ループ）", 0.5),
    "glide_open": ("パラグライダーを開く", 0.5),
    "glide": ("パラグライダー（ループ）", 1.0),
    # 素手・共通の戦闘の動き
    "parry": ("受け流し（武器か腕で弾く）", 0.35),
    "dodge_l": ("左へ跳んで回避", 0.35),
    "dodge_r": ("右へ跳んで回避", 0.35),
    "ground_pound": ("空中から両手打撃を地面へ叩きつける", 0.8),
    # 近接（各型 3 振り + 溜め。nr_spec_catalog.ANIM_SETS の swings / heavy）。長さ = ANIM_SETS の
    # 終わりの tick × 0.05 秒（gen_nr_player_anim がクリップの長さと突き合わせる）
    **{f"{s}_{n}": (f"{s} の振り {n}", sec)
       for s, secs in (("slash_1h", (0.5, 0.5, 0.6, 1.1)), ("slash_2h", (0.85, 0.85, 1.0, 1.5)),
                       ("blunt_1h", (0.6, 0.6, 0.7, 1.2)), ("blunt_2h", (1.0, 1.1, 1.1, 1.7)),
                       ("stab", (0.55, 0.55, 0.7, 1.2)))
       for n, sec in zip(("1", "2", "3", "heavy"), secs)},
    # 武器の構え・持って走る（層 nr.p.hold のループ。ANIM_SETS の idle / sprint）
    "hold_1h": ("片手武器の構え（ループ）", 1.0),
    "hold_2h": ("両手武器の構え（ループ）", 1.0),
    "hold_spear": ("槍の構え（ループ）", 1.0),
    "hold_bow": ("弓を下げて持つ（ループ）", 1.0),
    "hold_pistol": ("拳銃を下げて持つ（ループ）", 1.0),
    "hold_rifle": ("長物（クロスボウ・ライフル・散弾銃・短機関銃）を抱える（ループ）", 1.0),
    "sprint_1h": ("片手武器を持って全力疾走（ループ）", 0.6),
    "sprint_2h": ("両手武器を抱えて全力疾走（ループ）", 0.6),
    # 飛び道具
    "bow_draw": ("弓を引く", 0.6), "bow_hold": ("引き絞ったまま狙う（ループ）", 1.0),
    "bow_release": ("弓を放つ", 0.3),
    "crossbow_aim": ("クロスボウを肩付けで狙う（ループ）", 1.0),
    "crossbow_fire": ("クロスボウを撃つ", 0.3), "crossbow_reload": ("クロスボウの装填", 1.0),
    "pistol_aim": ("拳銃を両手で狙う（ループ）", 1.0),
    "pistol_fire": ("拳銃の反動", 0.2), "pistol_reload": ("拳銃の装填", 1.1),
    "rifle_aim": ("ライフル・短機関銃を肩付けで狙う（ループ）", 1.0),
    "rifle_fire": ("ライフルの反動", 0.35), "rifle_reload": ("ライフル・短機関銃の弾倉の交換", 1.6),
    "rifle_bolt": ("ボルトを引いて戻す", 0.6),
    "shotgun_aim": ("散弾銃を肩付けで狙う（ループ）", 1.0),
    "shotgun_fire": ("散弾銃の反動", 0.4), "shotgun_pump": ("ポンプ", 0.45),
    "shotgun_reload": ("散弾の装填", 1.4), "smg_fire": ("短機関銃の連射の揺れ", 0.15),
    "throw_wind": ("振りかぶって溜める（保持）", 0.4),
    "throw_overhand": ("振りかぶって投げる（throw_wind の続き）", 0.5), "throw_underhand": ("下手投げ", 0.45),
    # 道具・回復（nr_spec_catalog のアイテムの use.anim）
    "heal": ("包帯を巻く・救急キットで手当てする・武器にテープを巻く", 1.2),
    "inject": ("注射を打つ（注射薬・免疫アンプル・抑制血清）", 0.8),
    "consume": ("口元へ運んで食べる・飲む（缶詰・飲み物・錠剤・キノコ）", 1.0),
    "uv_flash": ("UV ライトを前へかざす", 0.5),
    "raise_item": ("手に持った物を顔の前へ上げて見る（双眼鏡・端末）", 0.5),
    "lockpick": ("しゃがんで鍵穴をピックで探る（ループ）", 1.0),
    "finisher_stomp": ("とどめの踏み潰し", 0.8), "finisher_decap": ("とどめの首刈り", 0.9),
}

# ---------------------------------------------------------------------------
#  ゾンビの一発アニメ  animation.nr.z.<name>  ->  説明
#  スクリプトは zombie.playAnimation("animation.nr.z.<name>", {controller: "nr.z.os", blendOutTime: 0.15,
#  stopExpression: "q.any_animation_finished", nextState: "none"}) で再生。
#  常時の状態（歩き・這い・死体・ぶら下がる腕…）は gen_nr_zombie_anim のコントローラが
#  プロパティから自動で切り替えるので、スクリプトは呼ばない。
#  種類ごとのアニメ（移動 walk_/run_<locomotion>、攻撃 atk_<attack>、能力 ab_<ability>_<phase> と
#  ab_<ability>）は spec の zombie_animations(z) が正。下の all_zombie_anim_names(spec) などがそこから並べる
#  （名前の約束を二か所に書かない）。
# ---------------------------------------------------------------------------
ZOMBIE_ONESHOTS = {
    "none": "何もしない（再生中の一発ものを止める）",
    "react_head": "頭に当たって仰け反る", "react_torso": "胴に当たってよろめく",
    "react_arm_r": "右腕を弾かれる", "react_arm_l": "左腕を弾かれる",
    "react_leg_r": "右脚を払われて膝が落ちる", "react_leg_l": "左脚を払われて膝が落ちる",
    "react_heavy": "重い一撃で大きく後ろへよろける", "knockdown": "倒れる",
    "getup": "起き上がる", "grab": "プレイヤーに組みつく", "bite": "組みついて噛む",
    "shoved": "押しのけられる", "climb_up": "縁へよじ登る", "stunned": "感電・気絶",
    "burn_flail": "燃えてもがく", "uv_recoil": "UV にひるむ", "alert": "気づいて振り向く",
    "sever_recoil": "部位を失ってのけぞる", "kicked": "蹴り飛ばされる",
}

# パーティクルが読んでよい変数（MolangVariableMap に入れる名前。docstring の共通の変数名）
PARTICLE_VARS = ("count", "spread", "speed", "dx", "dy", "dz", "size", "life", "cr", "cg", "cb", "gore", "radius")

_ZPREFIX = "animation.nr.z."


# ---------------------------------------------------------------------------
#  spec から機械的に決まる ID（spec は nr_spec モジュールか、同じ名前を持つもの）
# ---------------------------------------------------------------------------
def derived_voice_sounds(voice_keys):
    """ゾンビの声 nr.z.<voice>.<idle|alert|attack|hurt|death>。"""
    return [f"nr.z.{v}.{e}" for v in sorted(voice_keys) for e in ZOMBIE_VOICE_EVENTS]


def derived_ability_sounds(ability_keys):
    """特殊能力の音 nr.ab.<ability>。"""
    return [f"nr.ab.{a}" for a in sorted(ability_keys)]


def zombie_anim_names(spec, z):
    """1 体の全アニメの短い名前（animation.nr.z. を除いた形）。spec.zombie_animations(z) が正。"""
    out = []
    for full in spec.zombie_animations(z).values():
        if not full.startswith(_ZPREFIX):
            raise ValueError(f"{z['key']}: animation id {full!r} must start with {_ZPREFIX}")
        out.append(full[len(_ZPREFIX):])
    return out


def all_zombie_anim_names(spec):
    """全種類のアニメの短い名前（重複なし・並べ替え済み）。gen_nr_zombie_anim はこれを全部作る。"""
    return sorted({n for z in spec.ZOMBIES for n in zombie_anim_names(spec, z)})


def derived_ability_anims(spec):
    """能力のアニメ ab_<ability>_<phase> と ab_<ability>（anim=True の能力）。"""
    return [n for n in all_zombie_anim_names(spec) if n.startswith("ab_")]


def derived_attack_anims(spec):
    """攻撃のアニメ atk_<attack>。"""
    return [n for n in all_zombie_anim_names(spec) if n.startswith("atk_")]


def derived_locomotion_anims(spec):
    """移動のアニメ walk_<locomotion> / run_<locomotion>。"""
    return [n for n in all_zombie_anim_names(spec) if n.startswith(("walk_", "run_"))]


def all_sound_ids(spec=None):
    ids = list(SOUNDS)
    if spec is not None:
        ids += derived_voice_sounds(spec.VOICE_VOCAB.keys())
        ids += derived_ability_sounds(spec.ABILITY_VOCAB.keys())
    return ids


def all_particle_ids():
    return [f"nr:{n}" for n in PARTICLES]


def all_player_anim_ids():
    return [f"animation.nr.p.{n}" for n in PLAYER_ANIMS]


def all_zombie_oneshots(spec=None):
    """スクリプトが playAnimation で呼んでよいゾンビのアニメの短い名前。
    共通の一発もの（ZOMBIE_ONESHOTS）+ spec があれば攻撃 atk_* と能力 ab_*（zombie_animations の命名）。"""
    names = list(ZOMBIE_ONESHOTS)
    if spec is not None:
        names += derived_attack_anims(spec) + derived_ability_anims(spec)
    return names


def all_zombie_anim_ids(spec):
    """animation.nr.z.<name> の完全な ID（一発もの + 全種類のアニメ）。"""
    names = list(ZOMBIE_ONESHOTS) + all_zombie_anim_names(spec)
    return [_ZPREFIX + n for n in dict.fromkeys(names)]


# ---------------------------------------------------------------------------
#  自己検査（spec を渡すと、spec が参照する ID が全部ここにあるかも見る）
# ---------------------------------------------------------------------------
def check(spec=None):
    import re
    errs = []
    name_re = re.compile(r"^[a-z][a-z0-9_]*$")
    sound_re = re.compile(r"^nr(\.[a-z0-9_]+){2,3}$")
    for n, (desc, vars_) in PARTICLES.items():
        if not name_re.match(n):
            errs.append(f"particle {n!r}: not snake_case")
        if not desc:
            errs.append(f"particle {n}: empty description")
        for v in vars_.split():
            if v not in PARTICLE_VARS:
                errs.append(f"particle {n}: unknown variable {v!r} (allowed {PARTICLE_VARS})")
    for k, desc in SOUNDS.items():
        if not sound_re.match(k) or not desc:
            errs.append(f"sound {k!r}: bad id or empty description")
        if k.startswith(("nr.z.", "nr.ab.")):
            errs.append(f"sound {k}: nr.z.* / nr.ab.* are derived from the spec, do not list them")
    for n, (desc, sec) in PLAYER_ANIMS.items():
        if not name_re.match(n) or not desc or not sec > 0:
            errs.append(f"player anim {n!r}: bad name/description/length")
    for n, desc in ZOMBIE_ONESHOTS.items():
        if not name_re.match(n) or not desc:
            errs.append(f"zombie one-shot {n!r}: bad name/description")
        if n.startswith(("ab_", "atk_", "walk_", "run_")):
            errs.append(f"zombie one-shot {n}: prefix is reserved for zombie_animations(z)")
    if spec is None:
        return errs
    sounds = all_sound_ids(spec)
    if len(sounds) != len(set(sounds)):
        errs.append("sound ids: duplicates between SOUNDS and the derived voice/ability sounds")
    for v in spec.VOICE_VOCAB:
        if not name_re.match(v):
            errs.append(f"voice {v!r}: not snake_case")
    for a in spec.ABILITY_VOCAB:
        if not name_re.match(a):
            errs.append(f"ability {a!r}: not snake_case")
    znames = set(all_zombie_anim_names(spec))
    for n in sorted(znames & set(ZOMBIE_ONESHOTS)):
        errs.append(f"zombie anim {n}: clashes with ZOMBIE_ONESHOTS")
    for n in sorted(znames):
        if not re.match(r"^(walk|run|atk|ab)_[a-z0-9_]+$", n):
            errs.append(f"zombie anim {n}: not walk_/run_/atk_/ab_")
    # spec（カタログ）が参照する ID はすべて登録簿にあること
    if hasattr(spec, "required_sounds"):
        for sid in sorted(set(spec.required_sounds()) - set(sounds)):
            errs.append(f"spec sound {sid} is not in nr_registry (add it to SOUNDS)")
    if hasattr(spec, "required_particles"):
        for pid in sorted(set(spec.required_particles()) - set(all_particle_ids())):
            errs.append(f"spec particle {pid} is not in nr_registry.PARTICLES")
    if hasattr(spec, "required_player_animations"):
        for aid in sorted(set(spec.required_player_animations()) - set(all_player_anim_ids())):
            errs.append(f"spec player animation {aid} is not in nr_registry.PLAYER_ANIMS")
    return errs


if __name__ == "__main__":
    import sys
    problems = check()
    print(f"particles {len(PARTICLES)} / sounds {len(SOUNDS)} / player anims {len(PLAYER_ANIMS)}"
          f" / zombie one-shots {len(ZOMBIE_ONESHOTS)}")
    for p in problems:
        print("  NG", p)
    if problems:
        sys.exit(1)
    print("OK（spec と突き合わせる検査は python3 tools/nightrunner/nr_spec.py）")
