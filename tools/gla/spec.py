# -*- coding: utf-8 -*-
"""GRAND LINE AWAKENING — 単一の定義元 / the one place the add-on is defined.

企画書 §09 が求めている「技の見た目・判定・コストを一つの定義にまとめる」を、
そのまま実装したもの。ここに書いた 形態・技・設定 から

    * BP のアイテム / エンティティ / レシピ
    * RP のモデル / アニメ / パーティクル / アタッチャブル
    * スクリプトが読む packs/gla_BP/scripts/data.js
    * ja_JP / en_US の言語ファイル
    * 検証 (validate.py) と挙動テスト (test_logic.py)

が生成される。技を1つ足すときに触るファイルはこの1枚だけ、というのが狙い。

数値は企画書と同じく「制作・検証の仮目標」で、実測値でも公式値でもない。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
#  識別子
# ---------------------------------------------------------------------------
NS = "gla"                      # 独自 namespace（企画書 §18 他パックとの競合）
PROJECT = "GrandLineAwakening"
VERSION = (1, 0, 0)
MIN_ENGINE = (1, 21, 30)

BP_DIR = "packs/gla_BP"
RP_DIR = "packs/gla_RP"

# 既存の怪獣8号パックと UUID が衝突しないよう、固定値で持つ。
UUID_BP_HEADER = "6f2a1c48-5d3b-4a91-9f07-2c8e41d6b530"
UUID_BP_DATA = "b1d4e907-33c6-4f52-8a1e-7d90c5b24e18"
UUID_BP_SCRIPT = "0c95a7f2-4e18-4b6d-93a5-1f6e28d7c044"
UUID_RP_HEADER = "3e8c50d1-9b27-4d6a-85f3-6a2b19e4c7d2"
UUID_RP_RES = "d7194b63-2a5f-4e08-91cc-4b83f2a60e95"

SERVER_MODULE = "1.13.0"
SERVER_UI_MODULE = "1.2.0"

# ---------------------------------------------------------------------------
#  気力 (energy)
# ---------------------------------------------------------------------------
ENERGY_MAX = 100.0
ENERGY_REGEN = 1.20        # 通常時 / 秒
ENERGY_REGEN_IDLE = 2.40   # 非戦闘 8 秒後 / 秒
LOW_ENERGY = 15.0          # これを割ると警告と解除予告

# ---------------------------------------------------------------------------
#  形態 (形態は6つ。ギア3は「技中だけの部分変形」で常時形態ではない)
# ---------------------------------------------------------------------------


@dataclass
class Form:
    key: str
    ja: str
    en: str
    geo: str                    # geometry 識別子の語幹
    upkeep: float               # 維持コスト / 秒
    enter: float                # 移行コスト
    unlock_hits: int            # 解放に必要な命中数
    effects: List[Tuple[str, int]] = field(default_factory=list)
    transient: bool = False     # 技の間だけ見た目が変わる形態か
    note: str = ""

    @property
    def geometry(self) -> str:
        return f"geometry.{NS}.{self.geo}"

    @property
    def texture(self) -> str:
        return self.geo

    @property
    def name_key(self) -> str:
        return f"{NS}.form.{self.key}"


FORMS: List[Form] = [
    Form("normal", "通常", "Normal", "luffy_normal",
         upkeep=0.0, enter=0.0, unlock_hits=0,
         effects=[],
         note="基本操作・コンボ・移動技の基準。軽快な重心移動と伸びる腕。"),
    Form("gear2", "ギア2", "Gear 2", "luffy_gear2",
         upkeep=0.85, enter=6.0, unlock_hits=20,
         effects=[("speed", 1), ("haste", 1)],
         note="前傾姿勢・加速・蒸気。短い予備動作と高速の連続攻撃。"),
    Form("gear3", "ギア3", "Gear 3", "luffy_gear3",
         upkeep=0.35, enter=8.0, unlock_hits=60,
         effects=[("resistance", 0)],
         transient=True,
         note="技中だけ腕脚が膨張する。常時形態としては通常の輪郭を保つ。"),
    Form("gear4_bound", "ギア4・バウンドマン", "Gear 4: Boundman", "luffy_g4_bound",
         upkeep=1.30, enter=14.0, unlock_hits=120,
         effects=[("strength", 1), ("resistance", 1), ("jump_boost", 1)],
         note="胸・腕のボリューム、圧縮される拳、弾む重心、覇気の模様。"),
    Form("gear4_snake", "ギア4・スネイクマン", "Gear 4: Snakeman", "luffy_g4_snake",
         upkeep=1.30, enter=14.0, unlock_hits=200,
         effects=[("speed", 2), ("strength", 0)],
         note="バウンドマンとは別の輪郭と構え。長い腕の軌道と方向転換。"),
    Form("gear5", "ギア5・ニカ", "Gear 5: Nika", "luffy_gear5",
         upkeep=2.10, enter=26.0, unlock_hits=320,
         effects=[("strength", 2), ("resistance", 2), ("speed", 1),
                  ("jump_boost", 2), ("regeneration", 0), ("fire_resistance", 0)],
         note="白い髪の房、眉、歯を見せる大笑い、衣装、帯、雲。弾性の強い動作。"),
]

FORM_BY_KEY: Dict[str, Form] = {f.key: f for f in FORMS}
FORM_ORDER: List[str] = [f.key for f in FORMS]

# ---------------------------------------------------------------------------
#  VFX の層 (企画書 §11)
#     1 予兆 / 2 軌道 / 3 接触 / 4 広がり / 5 余韻
#  層ごとに「何を守るか」が違うので、削るときもこの番号で削る。
# ---------------------------------------------------------------------------
LAYER_OMEN = 1
LAYER_TRAIL = 2
LAYER_IMPACT = 3
LAYER_SPREAD = 4
LAYER_ECHO = 5

LAYER_JA = {
    LAYER_OMEN: "予兆", LAYER_TRAIL: "軌道", LAYER_IMPACT: "接触",
    LAYER_SPREAD: "広がり", LAYER_ECHO: "余韻",
}

# 品質設定ごとに、どの層まで描くか。軽量は 予兆→接触 を残し、広がり・余韻を削る。
QUALITY = {
    "light": dict(ja="軽量", en="Light", layers=[1, 2, 3], density=0.45,
                  helpers=8, showpiece=1, cubes=(120, 220)),
    "standard": dict(ja="標準", en="Standard", layers=[1, 2, 3, 4], density=0.80,
                     helpers=16, showpiece=2, cubes=(250, 450)),
    "high": dict(ja="高品質", en="High", layers=[1, 2, 3, 4, 5], density=1.00,
                 helpers=24, showpiece=2, cubes=(500, 1000)),
}
QUALITY_ORDER = ["light", "standard", "high"]


def stage(t: int, layer: int, fx: str, form: str = "point", n: int = 1,
          r: float = 0.0, d: float = 0.0, spread: float = 0.0,
          sweep: float = 0.0, tilt: float = 0.0, at: str = "hand") -> dict:
    """技の演出1コマ。`t` は発動からの tick。

    `form` は effects.js 側の並べ方 —
    point/ring/arc/line/spiral/cone/pillar/fan/curtain/scatter/tail。
    `at` は原点 — hand / chest / eye / target / feet / ground。
    """
    s = {"t": t, "layer": layer, "fx": fx, "form": form}
    if n != 1:
        s["n"] = n
    for key, val in (("r", r), ("d", d), ("spread", spread),
                     ("sweep", sweep), ("tilt", tilt)):
        if val:
            s[key] = val
    if at != "hand":
        s["at"] = at
    return s


def snd(t: int, id: str, vol: float = 1.0, pitch: float = 1.0) -> dict:
    return {"t": t, "id": id, "v": vol, "p": pitch}


# ---------------------------------------------------------------------------
#  技 (24枠) — 企画書 §10
#  「技名と色を隠して録画を見ても、伸ばす技／連打／重い一撃が区別できること」
#  が検収条件なので、shape・windup・hits・knockback を意図的にばらしてある。
# ---------------------------------------------------------------------------


@dataclass
class Tech:
    slug: str
    form: str
    ja: str
    en: str
    shape: str                  # line|cone|sphere|arc|zone|self|dash|projectile|delayed
    cost: float
    cooldown: int               # tick
    windup: int                 # 予備動作 tick
    active: int                 # 有効時間 tick
    recover: int                # 後隙 tick
    reach: float = 0.0
    radius: float = 1.0
    damage: float = 0.0
    hits: int = 1
    hit_interval: int = 0       # 連打の間隔 tick
    kb_h: float = 0.0
    kb_v: float = 0.0
    terrain: bool = False       # ホストが許可したときだけ地形に触る技
    fire: int = 0               # 着火 tick
    anim: str = ""              # 空なら slug と同じ
    stages: List[dict] = field(default_factory=list)
    sfx: List[dict] = field(default_factory=list)
    self_effects: List[Tuple[str, int, int]] = field(default_factory=list)
    launch: Tuple[float, float] = (0.0, 0.0)   # 自分を飛ばす技 (前, 上)
    note: str = ""

    # -- 導出 ------------------------------------------------------------
    @property
    def id(self) -> str:
        return f"{NS}:{self.slug}"

    @property
    def anim_id(self) -> str:
        return f"animation.{NS}.tech.{self.anim or self.slug}"

    @property
    def name_key(self) -> str:
        return f"{NS}.tech.{self.slug}"

    @property
    def total(self) -> int:
        return self.windup + self.active + self.recover

    @property
    def dps_window(self) -> float:
        return self.damage * self.hits


def T(*a, **kw) -> Tech:
    return Tech(*a, **kw)


# --- 通常 / 4 -----------------------------------------------------------
_NORMAL = [
    T("pistol", "normal", "ゴム銃", "Rubber Pistol", "line",
      cost=5, cooldown=16, windup=4, active=6, recover=8,
      reach=9.0, radius=0.85, damage=7.0, kb_h=0.95, kb_v=0.22,
      stages=[
          stage(0, LAYER_OMEN, "gla:stretch_coil", "ring", 6, r=0.45),
          stage(4, LAYER_TRAIL, "gla:fist_trail", "line", 10, d=9.0),
          stage(4, LAYER_TRAIL, "gla:speed_line", "line", 6, d=9.0),
          stage(7, LAYER_IMPACT, "gla:impact_core", "point", at="target"),
          stage(7, LAYER_SPREAD, "gla:impact_ring", "ring", 8, r=1.1, at="target"),
          stage(12, LAYER_ECHO, "gla:rubber_snap", "scatter", 4, spread=0.6),
      ],
      sfx=[snd(0, "mob.slime.small", 0.7, 1.5), snd(7, "random.anvil_land", 0.55, 1.9)],
      note="伸長する単拳。品質見本の1本目 — 直線・単発・中程度のノックバック。"),

    T("bazooka", "normal", "ゴム大砲", "Rubber Bazooka", "cone",
      cost=11, cooldown=48, windup=10, active=6, recover=12,
      reach=6.0, radius=2.4, damage=11.0, kb_h=1.70, kb_v=0.48,
      stages=[
          stage(0, LAYER_OMEN, "gla:charge_draw", "ring", 10, r=0.9),
          stage(6, LAYER_OMEN, "gla:charge_draw", "ring", 8, r=0.55),
          stage(10, LAYER_TRAIL, "gla:palm_push", "cone", 14, d=6.0, r=2.4),
          stage(12, LAYER_IMPACT, "gla:impact_core", "point", at="target"),
          stage(12, LAYER_SPREAD, "gla:shock_fan", "fan", 12, r=2.6, sweep=110),
          stage(18, LAYER_ECHO, "gla:dust_low", "scatter", 6, spread=1.6, at="feet"),
      ],
      sfx=[snd(0, "mob.slime.big", 0.6, 0.9), snd(12, "random.explode", 0.75, 1.55)],
      note="両手の溜めから短い円錐。溜めがある分だけ判定が広い。"),

    T("gatling", "normal", "ゴム乱打", "Rubber Gatling", "line",
      cost=15, cooldown=66, windup=6, active=24, recover=10,
      reach=6.5, radius=1.15, damage=2.4, hits=12, hit_interval=2,
      kb_h=0.22, kb_v=0.04,
      stages=[
          stage(0, LAYER_OMEN, "gla:stretch_coil", "ring", 8, r=0.5),
          stage(6, LAYER_TRAIL, "gla:fist_blur", "scatter", 10, spread=0.9),
          stage(10, LAYER_TRAIL, "gla:fist_blur", "scatter", 10, spread=1.0),
          stage(14, LAYER_TRAIL, "gla:fist_blur", "scatter", 10, spread=1.1),
          stage(18, LAYER_TRAIL, "gla:fist_blur", "scatter", 10, spread=1.0),
          stage(26, LAYER_SPREAD, "gla:impact_ring", "ring", 6, r=1.3, at="target"),
          stage(32, LAYER_ECHO, "gla:rubber_snap", "scatter", 5, spread=0.7),
      ],
      sfx=[snd(6, "mob.slime.small", 0.5, 1.8), snd(12, "mob.slime.small", 0.5, 1.9),
           snd(18, "mob.slime.small", 0.5, 2.0)],
      note="品質見本の2本目 — 連打。1発は軽く、回数で差を出す。"),

    T("rocket", "normal", "ゴム推進", "Rubber Rocket", "dash",
      cost=8, cooldown=56, windup=6, active=8, recover=10,
      reach=3.0, radius=1.3, damage=5.0, kb_h=0.7, kb_v=0.35,
      launch=(1.65, 0.62),
      stages=[
          stage(0, LAYER_OMEN, "gla:stretch_coil", "ring", 10, r=0.7),
          stage(6, LAYER_TRAIL, "gla:speed_line", "tail", 12, d=4.0),
          stage(10, LAYER_TRAIL, "gla:speed_line", "tail", 10, d=4.0),
          stage(14, LAYER_ECHO, "gla:dust_low", "scatter", 5, spread=1.2, at="feet"),
      ],
      sfx=[snd(6, "mob.slime.big", 0.7, 1.35)],
      note="移動技。自分を飛ばす反動で当たる。攻撃判定は飛行中だけ。"),
]

# --- ギア2 / 4 ----------------------------------------------------------
_GEAR2 = [
    T("jet_pistol", "gear2", "JETゴム銃", "Jet Pistol", "line",
      cost=7, cooldown=13, windup=2, active=5, recover=5,
      reach=11.0, radius=0.85, damage=9.0, kb_h=1.05, kb_v=0.20,
      stages=[
          stage(0, LAYER_OMEN, "gla:steam_wisp", "ring", 5, r=0.4),
          stage(2, LAYER_TRAIL, "gla:jet_streak", "line", 12, d=11.0),
          stage(4, LAYER_IMPACT, "gla:impact_core", "point", at="target"),
          stage(4, LAYER_SPREAD, "gla:impact_ring", "ring", 6, r=1.0, at="target"),
          stage(8, LAYER_ECHO, "gla:steam_wisp", "scatter", 5, spread=0.8),
      ],
      sfx=[snd(0, "random.fizz", 0.5, 1.9), snd(4, "random.anvil_land", 0.6, 2.0)],
      note="予備動作を2tickまで詰めた版。命中時だけ強く光らせる。"),

    T("jet_gatling", "gear2", "JETゴム乱打", "Jet Gatling", "line",
      cost=21, cooldown=76, windup=4, active=26, recover=10,
      reach=7.5, radius=1.2, damage=2.9, hits=18, hit_interval=1,
      kb_h=0.18, kb_v=0.03,
      stages=[
          stage(0, LAYER_OMEN, "gla:steam_wisp", "ring", 8, r=0.5),
          stage(4, LAYER_TRAIL, "gla:jet_blur", "scatter", 12, spread=1.0),
          stage(9, LAYER_TRAIL, "gla:jet_blur", "scatter", 12, spread=1.1),
          stage(14, LAYER_TRAIL, "gla:jet_blur", "scatter", 12, spread=1.2),
          stage(19, LAYER_TRAIL, "gla:jet_blur", "scatter", 12, spread=1.1),
          stage(30, LAYER_SPREAD, "gla:shock_fan", "fan", 10, r=2.0, sweep=90),
          stage(34, LAYER_ECHO, "gla:steam_wisp", "scatter", 8, spread=1.4),
      ],
      sfx=[snd(4, "random.fizz", 0.45, 2.0), snd(12, "random.fizz", 0.45, 2.0),
           snd(20, "random.fizz", 0.45, 2.0)],
      note="ゴム乱打との差は密度と蒸気。判定回数を増やし1発を下げる。"),

    T("red_hawk", "gear2", "火拳銃", "Fire Fist Shot", "line",
      cost=14, cooldown=58, windup=8, active=6, recover=12,
      reach=10.0, radius=1.05, damage=14.0, kb_h=1.5, kb_v=0.30, fire=70,
      stages=[
          stage(0, LAYER_OMEN, "gla:ignite_coil", "spiral", 12, r=0.6, d=1.2),
          stage(5, LAYER_OMEN, "gla:ignite_coil", "spiral", 10, r=0.45, d=0.9),
          stage(8, LAYER_TRAIL, "gla:flame_trail", "line", 12, d=10.0),
          stage(11, LAYER_IMPACT, "gla:flame_burst", "point", at="target"),
          stage(11, LAYER_SPREAD, "gla:ember_fan", "fan", 12, r=2.2, sweep=120, at="target"),
          stage(18, LAYER_ECHO, "gla:ember_drift", "scatter", 6, spread=1.1),
      ],
      sfx=[snd(0, "fire.ignite", 0.6, 1.1), snd(11, "random.explode", 0.7, 1.35)],
      note="着火する直線。蒸気ではなく炎で、同じギア2の中でも読み分けられる。"),

    T("high_dodge", "gear2", "高速回避", "High-Speed Evade", "self",
      cost=5, cooldown=38, windup=1, active=6, recover=4,
      damage=0.0, launch=(1.9, 0.16),
      self_effects=[("speed", 2, 40), ("resistance", 1, 30)],
      stages=[
          stage(0, LAYER_OMEN, "gla:steam_wisp", "ring", 6, r=0.5),
          stage(1, LAYER_TRAIL, "gla:after_image", "tail", 8, d=3.2),
          stage(4, LAYER_TRAIL, "gla:after_image", "tail", 6, d=2.6),
          stage(9, LAYER_ECHO, "gla:steam_wisp", "scatter", 4, spread=0.8),
      ],
      sfx=[snd(0, "random.fizz", 0.45, 2.0)],
      note="〔補助〕ゲーム用の回避。ダメージなし。残像は補助に留める。"),
]

# --- ギア3 / 4 ----------------------------------------------------------
_GEAR3 = [
    T("gigant_pistol", "gear3", "巨人の銃", "Gigant Pistol", "line",
      cost=18, cooldown=68, windup=14, active=8, recover=18,
      reach=14.0, radius=2.0, damage=18.0, kb_h=2.2, kb_v=0.45,
      stages=[
          stage(0, LAYER_OMEN, "gla:inflate_puff", "ring", 10, r=0.8),
          stage(7, LAYER_OMEN, "gla:inflate_puff", "ring", 12, r=1.2),
          stage(14, LAYER_TRAIL, "gla:heavy_trail", "line", 12, d=14.0),
          stage(18, LAYER_IMPACT, "gla:impact_core_big", "point", at="target"),
          stage(18, LAYER_SPREAD, "gla:shock_ring_big", "ring", 14, r=2.6, at="target"),
          stage(26, LAYER_ECHO, "gla:deflate_puff", "scatter", 8, spread=1.3),
      ],
      sfx=[snd(0, "mob.slime.big", 0.8, 0.65), snd(18, "random.explode", 0.9, 1.0)],
      note="局所的な膨張。溜めが長い代わりに射程と判定が段違い。"),

    T("gigant_axe", "gear3", "巨人の斧", "Gigant Axe", "arc",
      cost=22, cooldown=88, windup=18, active=8, recover=22,
      reach=5.0, radius=3.4, damage=22.0, kb_h=1.3, kb_v=0.95, terrain=True,
      stages=[
          stage(0, LAYER_OMEN, "gla:inflate_puff", "ring", 10, r=0.9),
          stage(9, LAYER_OMEN, "gla:lift_dust", "ring", 10, r=1.8, at="feet"),
          stage(18, LAYER_TRAIL, "gla:heavy_arc", "arc", 12, r=3.2, sweep=150, tilt=1.2),
          stage(22, LAYER_IMPACT, "gla:slam_core", "point", at="ground"),
          stage(22, LAYER_SPREAD, "gla:ground_crack", "ring", 16, r=3.4, at="ground"),
          stage(24, LAYER_SPREAD, "gla:debris", "scatter", 10, spread=2.4, at="ground"),
          stage(34, LAYER_ECHO, "gla:dust_low", "scatter", 8, spread=2.6, at="ground"),
      ],
      sfx=[snd(0, "mob.slime.big", 0.8, 0.6), snd(22, "random.explode", 1.0, 0.75)],
      note="振り下ろし。着弾地点の周囲で判定するので、前方打撃とは別物になる。"),

    T("gigant_bazooka", "gear3", "巨人のバズーカ", "Gigant Bazooka", "cone",
      cost=26, cooldown=96, windup=16, active=8, recover=20,
      reach=9.0, radius=3.3, damage=24.0, kb_h=3.0, kb_v=0.70,
      stages=[
          stage(0, LAYER_OMEN, "gla:inflate_puff", "ring", 12, r=1.0),
          stage(8, LAYER_OMEN, "gla:charge_draw", "ring", 10, r=1.5),
          stage(16, LAYER_TRAIL, "gla:heavy_push", "cone", 16, d=9.0, r=3.3),
          stage(20, LAYER_IMPACT, "gla:impact_core_big", "point", at="target"),
          stage(20, LAYER_SPREAD, "gla:shock_fan", "fan", 16, r=3.6, sweep=120),
          stage(30, LAYER_ECHO, "gla:deflate_puff", "scatter", 10, spread=1.6),
      ],
      sfx=[snd(0, "mob.slime.big", 0.9, 0.6), snd(20, "random.explode", 1.0, 0.85)],
      note="両拳の押し込み。巨人の銃より近く、広く、反動が重い。"),

    T("elephant_gun", "gear3", "象銃", "Elephant Gun", "line",
      cost=24, cooldown=92, windup=16, active=8, recover=20,
      reach=12.0, radius=2.6, damage=26.0, kb_h=2.6, kb_v=0.50, terrain=True,
      stages=[
          stage(0, LAYER_OMEN, "gla:inflate_puff", "ring", 14, r=1.1),
          stage(8, LAYER_OMEN, "gla:inflate_puff", "ring", 14, r=1.6),
          stage(16, LAYER_TRAIL, "gla:heavy_trail", "line", 14, d=12.0),
          stage(20, LAYER_IMPACT, "gla:slam_core", "point", at="target"),
          stage(20, LAYER_SPREAD, "gla:shock_ring_big", "ring", 16, r=3.0, at="target"),
          stage(32, LAYER_ECHO, "gla:deflate_puff", "scatter", 10, spread=1.8),
      ],
      sfx=[snd(0, "mob.slime.big", 1.0, 0.55), snd(20, "random.explode", 1.0, 0.7)],
      note="ギア3で一番重い単発。腕の収縮まで見せて後隙を作る。"),
]

# --- ギア4・バウンドマン / 3 --------------------------------------------
_G4_BOUND = [
    T("kong_gun", "gear4_bound", "猿王銃", "Kong Gun", "line",
      cost=22, cooldown=78, windup=12, active=6, recover=16,
      reach=13.0, radius=2.2, damage=24.0, kb_h=3.2, kb_v=0.60,
      stages=[
          stage(0, LAYER_OMEN, "gla:haki_coat", "ring", 10, r=0.8),
          stage(5, LAYER_OMEN, "gla:compress", "ring", 12, r=0.55),
          stage(12, LAYER_TRAIL, "gla:haki_trail", "line", 12, d=13.0),
          stage(15, LAYER_IMPACT, "gla:impact_core_big", "point", at="target"),
          stage(15, LAYER_SPREAD, "gla:shock_ring_big", "ring", 14, r=2.8, at="target"),
          stage(22, LAYER_ECHO, "gla:bounce_puff", "scatter", 8, spread=1.2),
      ],
      sfx=[snd(5, "mob.slime.big", 0.8, 0.8), snd(15, "random.explode", 0.95, 0.95)],
      note="拳を圧縮してから射出。溜めの圧縮と射出後の弾みで読み分ける。"),

    T("rhino_schneider", "gear4_bound", "犀榴弾砲", "Rhino Schneider", "dash",
      cost=20, cooldown=72, windup=10, active=10, recover=14,
      reach=10.0, radius=1.8, damage=20.0, kb_h=2.4, kb_v=0.80,
      launch=(2.1, 0.5),
      stages=[
          stage(0, LAYER_OMEN, "gla:compress", "ring", 10, r=0.7, at="feet"),
          stage(10, LAYER_TRAIL, "gla:haki_trail", "tail", 12, d=4.0),
          stage(14, LAYER_TRAIL, "gla:bounce_puff", "scatter", 8, spread=1.0),
          stage(18, LAYER_IMPACT, "gla:impact_core", "point", at="target"),
          stage(18, LAYER_SPREAD, "gla:shock_fan", "fan", 12, r=2.2, sweep=100),
          stage(26, LAYER_ECHO, "gla:dust_low", "scatter", 6, spread=1.4, at="feet"),
      ],
      sfx=[snd(0, "mob.slime.big", 0.7, 1.0), snd(18, "random.anvil_land", 0.8, 0.9)],
      note="射出される膝。自分が動く分、距離の詰め方が他と違う。"),

    T("king_kong_gun", "gear4_bound", "大猿王銃", "King Kong Gun", "line",
      cost=40, cooldown=200, windup=26, active=10, recover=30,
      reach=18.0, radius=3.6, damage=42.0, kb_h=4.2, kb_v=0.90, terrain=True,
      stages=[
          stage(0, LAYER_OMEN, "gla:haki_coat", "ring", 12, r=1.0),
          stage(8, LAYER_OMEN, "gla:compress", "spiral", 16, r=1.4, d=1.8),
          stage(16, LAYER_OMEN, "gla:compress", "spiral", 16, r=0.9, d=1.2),
          stage(26, LAYER_TRAIL, "gla:haki_trail", "line", 16, d=18.0),
          stage(26, LAYER_TRAIL, "gla:speed_line", "line", 12, d=18.0),
          stage(31, LAYER_IMPACT, "gla:slam_core", "point", at="target"),
          stage(31, LAYER_SPREAD, "gla:shock_ring_big", "ring", 18, r=4.0, at="target"),
          stage(33, LAYER_SPREAD, "gla:debris", "scatter", 12, spread=3.0, at="target"),
          stage(46, LAYER_ECHO, "gla:dust_low", "scatter", 10, spread=2.6, at="ground"),
      ],
      sfx=[snd(0, "mob.slime.big", 1.0, 0.55), snd(16, "mob.slime.big", 1.0, 0.5),
           snd(31, "random.explode", 1.2, 0.6)],
      note="バウンドマンの決め技。26tickの溜めと30tickの後隙で重さを出す。"),
]

# --- ギア4・スネイクマン / 3 --------------------------------------------
_G4_SNAKE = [
    T("jet_culverin", "gear4_snake", "JET大蛇砲", "Jet Culverin", "arc",
      cost=16, cooldown=38, windup=5, active=8, recover=10,
      reach=14.0, radius=1.4, damage=15.0, kb_h=1.2, kb_v=0.25,
      stages=[
          stage(0, LAYER_OMEN, "gla:haki_coat", "ring", 6, r=0.5),
          stage(5, LAYER_TRAIL, "gla:snake_trail", "spiral", 16, r=1.6, d=14.0),
          stage(9, LAYER_IMPACT, "gla:impact_core", "point", at="target"),
          stage(9, LAYER_SPREAD, "gla:impact_ring", "ring", 8, r=1.4, at="target"),
          stage(15, LAYER_ECHO, "gla:haki_wisp", "scatter", 5, spread=0.9),
      ],
      sfx=[snd(5, "random.fizz", 0.5, 1.6), snd(9, "random.anvil_land", 0.6, 1.7)],
      note="曲がる軌道。同じ直線でも螺旋で並べると別物に見える。"),

    T("black_mamba", "gear4_snake", "黒い蛇群", "Black Mamba", "arc",
      cost=30, cooldown=118, windup=8, active=30, recover=16,
      reach=12.0, radius=1.6, damage=6.0, hits=8, hit_interval=4,
      kb_h=0.45, kb_v=0.10,
      stages=[
          stage(0, LAYER_OMEN, "gla:haki_coat", "ring", 8, r=0.6),
          stage(8, LAYER_TRAIL, "gla:snake_trail", "spiral", 14, r=1.8, d=12.0),
          stage(14, LAYER_TRAIL, "gla:snake_trail", "spiral", 14, r=2.2, d=12.0, tilt=0.8),
          stage(20, LAYER_TRAIL, "gla:snake_trail", "spiral", 14, r=1.4, d=12.0, tilt=-0.8),
          stage(26, LAYER_TRAIL, "gla:snake_trail", "spiral", 14, r=2.0, d=12.0),
          stage(38, LAYER_SPREAD, "gla:shock_fan", "fan", 12, r=2.4, sweep=140),
          stage(44, LAYER_ECHO, "gla:haki_wisp", "scatter", 8, spread=1.3),
      ],
      sfx=[snd(8, "random.fizz", 0.45, 1.5), snd(18, "random.fizz", 0.45, 1.7),
           snd(28, "random.fizz", 0.45, 1.9)],
      note="連撃の方向差。命中のたびに軌道の高さを変えて次の動きを読ませる。"),

    T("king_cobra", "gear4_snake", "王蛇", "King Cobra", "arc",
      cost=38, cooldown=176, windup=22, active=10, recover=26,
      reach=20.0, radius=3.0, damage=40.0, kb_h=3.6, kb_v=0.50,
      stages=[
          stage(0, LAYER_OMEN, "gla:haki_coat", "ring", 12, r=1.0),
          stage(10, LAYER_OMEN, "gla:compress", "spiral", 14, r=1.3, d=1.6),
          stage(22, LAYER_TRAIL, "gla:snake_trail", "spiral", 20, r=2.6, d=20.0),
          stage(22, LAYER_TRAIL, "gla:haki_trail", "line", 14, d=20.0),
          stage(27, LAYER_IMPACT, "gla:slam_core", "point", at="target"),
          stage(27, LAYER_SPREAD, "gla:shock_ring_big", "ring", 16, r=3.4, at="target"),
          stage(40, LAYER_ECHO, "gla:haki_wisp", "scatter", 10, spread=1.6),
      ],
      sfx=[snd(0, "mob.slime.big", 0.9, 0.7), snd(27, "random.explode", 1.1, 0.75)],
      note="スネイクマンの決め技。曲がる一撃で、猿王銃の直線と区別する。"),
]

# --- ギア5・ニカ / 6 ----------------------------------------------------
_GEAR5 = [
    T("giant", "gear5", "巨人化", "Giant", "self",
      cost=28, cooldown=280, windup=20, active=400, recover=10,
      damage=0.0,
      self_effects=[("strength", 2, 400), ("resistance", 2, 400),
                    ("health_boost", 2, 400), ("slowness", 0, 60)],
      stages=[
          stage(0, LAYER_OMEN, "gla:nika_pulse", "ring", 12, r=1.0),
          stage(10, LAYER_TRAIL, "gla:cloud_curl", "spiral", 16, r=1.8, d=2.4),
          stage(20, LAYER_IMPACT, "gla:nika_flash", "point", at="chest"),
          stage(20, LAYER_SPREAD, "gla:wind_ring", "ring", 18, r=3.0, at="feet"),
          stage(34, LAYER_ECHO, "gla:cloud_drift", "scatter", 8, spread=2.0),
      ],
      sfx=[snd(0, "mob.slime.big", 0.8, 0.5), snd(20, "random.levelup", 0.8, 0.7)],
      note="直接の攻撃判定は持たない自己強化。ギア5の誇張したポーズの土台。"),

    T("lightning_throw", "gear5", "雷の投擲", "Thrown Lightning", "projectile",
      cost=24, cooldown=88, windup=12, active=20, recover=14,
      reach=24.0, radius=2.4, damage=22.0, kb_h=1.6, kb_v=0.55,
      stages=[
          stage(0, LAYER_OMEN, "gla:bolt_gather", "spiral", 14, r=0.9, d=1.4),
          stage(12, LAYER_TRAIL, "gla:bolt_trail", "line", 16, d=24.0),
          stage(12, LAYER_TRAIL, "gla:bolt_fringe", "scatter", 8, spread=1.0),
          stage(24, LAYER_IMPACT, "gla:bolt_strike", "pillar", 10, r=0.6, d=4.0, at="target"),
          stage(24, LAYER_SPREAD, "gla:shock_ring_big", "ring", 12, r=2.6, at="target"),
          stage(34, LAYER_ECHO, "gla:bolt_fringe", "scatter", 6, spread=1.4, at="target"),
      ],
      sfx=[snd(0, "ambient.weather.thunder", 0.35, 1.8),
           snd(24, "random.explode", 0.85, 1.5)],
      note="掴んで投げる雷。ギア5で唯一の遠距離。立体感が要るので柱で見せる。"),

    T("rubber_ground", "gear5", "地面のゴム化", "Rubber Ground", "zone",
      cost=26, cooldown=140, windup=14, active=200, recover=12,
      reach=0.0, radius=6.0, damage=2.0, hits=1, kb_h=0.6, kb_v=1.30,
      stages=[
          stage(0, LAYER_OMEN, "gla:nika_pulse", "ring", 10, r=1.2, at="feet"),
          stage(14, LAYER_TRAIL, "gla:rubber_wave", "ring", 20, r=6.0, at="feet"),
          stage(14, LAYER_IMPACT, "gla:rubber_pop", "scatter", 10, spread=3.0, at="feet"),
          stage(60, LAYER_SPREAD, "gla:rubber_wave", "ring", 14, r=6.0, at="feet"),
          stage(120, LAYER_SPREAD, "gla:rubber_wave", "ring", 14, r=6.0, at="feet"),
          stage(210, LAYER_ECHO, "gla:cloud_drift", "scatter", 6, spread=2.4, at="feet"),
      ],
      sfx=[snd(14, "mob.slime.big", 0.8, 1.2)],
      note="足元を弾ませる区域。当たった相手は跳ねる — 上方向のノックバックが主役。"),

    T("under_strike", "gear5", "地中からの打撃", "Strike From Below", "delayed",
      cost=22, cooldown=98, windup=16, active=30, recover=14,
      reach=12.0, radius=2.2, damage=20.0, kb_h=0.8, kb_v=1.60,
      stages=[
          stage(0, LAYER_OMEN, "gla:nika_pulse", "ring", 8, r=0.8, at="feet"),
          stage(16, LAYER_TRAIL, "gla:ground_run", "line", 14, d=12.0, at="ground"),
          stage(28, LAYER_OMEN, "gla:ground_bulge", "ring", 10, r=2.0, at="target"),
          stage(36, LAYER_IMPACT, "gla:slam_core", "pillar", 8, r=0.8, d=3.0, at="target"),
          stage(36, LAYER_SPREAD, "gla:debris", "scatter", 10, spread=2.2, at="target"),
          stage(48, LAYER_ECHO, "gla:dust_low", "scatter", 6, spread=2.0, at="target"),
      ],
      sfx=[snd(16, "mob.slime.small", 0.6, 0.8), snd(36, "random.explode", 0.9, 0.9)],
      note="〔仮称〕予兆が地面を走ってから打ち上げる。遅延があるぶん避けられる。"),

    T("white_star", "gear5", "白い星銃", "White Star", "sphere",
      cost=34, cooldown=156, windup=18, active=10, recover=20,
      reach=0.0, radius=7.0, damage=26.0, kb_h=3.0, kb_v=0.60,
      stages=[
          stage(0, LAYER_OMEN, "gla:nika_pulse", "ring", 12, r=1.2),
          stage(9, LAYER_OMEN, "gla:cloud_curl", "spiral", 16, r=1.6, d=2.0),
          stage(18, LAYER_IMPACT, "gla:nika_flash", "point", at="chest"),
          stage(18, LAYER_SPREAD, "gla:wind_ring", "ring", 24, r=7.0, at="feet"),
          stage(20, LAYER_SPREAD, "gla:star_shard", "scatter", 14, spread=3.4),
          stage(32, LAYER_ECHO, "gla:cloud_drift", "scatter", 10, spread=3.0),
      ],
      sfx=[snd(18, "random.explode", 1.0, 1.2)],
      note="全方位。唯一「自分の周囲を全方向」で判定してよい技として明示する。"),

    T("bajrang_gun", "gear5", "猿神銃", "Bajrang Gun", "line",
      cost=58, cooldown=560, windup=40, active=14, recover=40,
      reach=26.0, radius=6.0, damage=70.0, kb_h=5.0, kb_v=1.00, terrain=True,
      stages=[
          stage(0, LAYER_OMEN, "gla:nika_pulse", "ring", 14, r=1.4),
          stage(10, LAYER_OMEN, "gla:cloud_curl", "spiral", 20, r=2.4, d=3.0),
          stage(22, LAYER_OMEN, "gla:haki_coat", "ring", 16, r=2.0),
          stage(32, LAYER_OMEN, "gla:compress", "spiral", 18, r=1.6, d=2.0),
          stage(40, LAYER_TRAIL, "gla:giant_fist", "line", 20, d=26.0),
          stage(40, LAYER_TRAIL, "gla:haki_trail", "line", 16, d=26.0),
          stage(47, LAYER_IMPACT, "gla:slam_core", "point", at="target"),
          stage(47, LAYER_SPREAD, "gla:shock_ring_big", "ring", 24, r=6.0, at="target"),
          stage(49, LAYER_SPREAD, "gla:debris", "scatter", 16, spread=4.0, at="target"),
          stage(64, LAYER_ECHO, "gla:dust_low", "scatter", 12, spread=3.4, at="ground"),
          stage(70, LAYER_ECHO, "gla:cloud_drift", "scatter", 10, spread=3.0),
      ],
      sfx=[snd(0, "mob.slime.big", 1.0, 0.45), snd(22, "ambient.weather.thunder", 0.5, 0.8),
           snd(47, "random.explode", 1.4, 0.5)],
      note="最大の一撃。40tickの溜めと40tickの後隙。これだけは連発させない。"),
]

TECHS: List[Tech] = _NORMAL + _GEAR2 + _GEAR3 + _G4_BOUND + _G4_SNAKE + _GEAR5
TECH_BY_SLUG: Dict[str, Tech] = {t.slug: t for t in TECHS}


def techs_of(form: str) -> List[Tech]:
    return [t for t in TECHS if t.form == form]


# ---------------------------------------------------------------------------
#  看板演出 — ニカ変身後の浮遊・大笑い (企画書 §08)
#  4.5秒 = 90 tick。各段の身体とVFXを表にして、スクリプトはこれを順に流すだけ。
# ---------------------------------------------------------------------------
SHOWPIECE_TICKS = 90
SHOWPIECE_SHORT_TICKS = 34          # 「演出短縮」を選んだときの版
SHOWPIECE_LIFT = 0.62               # 見た目 root の上げ幅（ブロック）。実座標は動かさない

SHOWPIECE: List[dict] = [
    dict(t=0, until=12, ja="息を吸い、身体を少し丸める", en="breathe in, curl",
         pose="curl",
         stages=[stage(0, LAYER_OMEN, "gla:heart_thud", "ring", 6, r=0.7, at="chest")],
         sfx=[snd(0, "mob.wither.spawn", 0.45, 0.42)],
         quiet=True),
    dict(t=12, until=24, ja="胸・肩・頭の順に持ち上がる", en="chest, shoulders, head rise",
         pose="lift",
         stages=[stage(0, LAYER_TRAIL, "gla:cloud_curl", "spiral", 10, r=0.9, d=1.2)],
         sfx=[snd(0, "mob.slime.small", 0.4, 0.6)]),
    dict(t=24, until=36, ja="髪・眉・衣装・雲へ切替。笑顔から大笑いへ",
         en="swap to Nika hair, brow, clothes, cloud; smile to laugh",
         pose="swap", swap_form=True,
         stages=[stage(0, LAYER_IMPACT, "gla:nika_rim", "ring", 12, r=1.1, at="chest"),
                 stage(4, LAYER_TRAIL, "gla:cloud_curl", "spiral", 12, r=1.4, d=1.6)],
         sfx=[snd(0, "random.levelup", 0.7, 0.8)]),
    dict(t=36, until=48, ja="見た目を浮かせ、膝を上げて背を反らす",
         en="float the display, knees up, back arches",
         pose="float", lift=True,
         stages=[stage(0, LAYER_SPREAD, "gla:wind_ring", "ring", 16, r=2.4, at="feet")],
         sfx=[snd(0, "mob.slime.big", 0.5, 0.9)]),
    dict(t=48, until=76, ja="腹や顔へ手を添え、口を開き大爆笑",
         en="hands to belly and face, big laugh",
         pose="laugh", lift=True,
         stages=[stage(0, LAYER_TRAIL, "gla:cloud_orbit", "ring", 10, r=1.8),
                 stage(12, LAYER_TRAIL, "gla:cloud_orbit", "ring", 10, r=2.0),
                 stage(22, LAYER_TRAIL, "gla:cloud_orbit", "ring", 10, r=1.7)],
         sfx=[snd(2, "mob.slime.small", 0.4, 1.3), snd(12, "mob.slime.small", 0.4, 1.5),
              snd(21, "mob.slime.small", 0.4, 1.2)],
         no_voice=True),
    dict(t=76, until=90, ja="身体を戻し、軽く着地して専用待機へ",
         en="settle, light landing, into the form idle",
         pose="settle",
         stages=[stage(0, LAYER_ECHO, "gla:wind_ring", "ring", 10, r=1.4, at="feet"),
                 stage(8, LAYER_ECHO, "gla:cloud_drift", "scatter", 5, spread=1.6)],
         sfx=[snd(6, "random.pop", 0.4, 0.8)]),
]

# ---------------------------------------------------------------------------
#  アイテム (企画書 §09 操作)
# ---------------------------------------------------------------------------


@dataclass
class Item:
    slug: str
    ja: str
    en: str
    icon: str
    category: str = "equipment"
    group: str = ""
    stack: int = 1
    wearable: Optional[str] = None
    glint: bool = False
    hidden: bool = False        # クリエイティブにも出さない（内部用）
    use_duration: float = 0.0
    ja_desc: str = ""
    en_desc: str = ""

    @property
    def id(self) -> str:
        return f"{NS}:{self.slug}"

    @property
    def name_key(self) -> str:
        return f"item.{NS}:{self.slug}"


ITEMS: List[Item] = [
    Item("devil_fruit", "悪魔の実（ゴム）", "Devil Fruit (Gum)", "devil_fruit",
         category="nature", use_duration=1.6, glint=True,
         ja_desc="食べると能力を得る。一度だけ。",
         en_desc="Eat once to gain the power."),
    Item("straw_hat", "麦わら帽子", "Straw Hat", "straw_hat",
         category="equipment",
         ja_desc="使う=変身／解除、しゃがみ+使う=形態を選ぶ。",
         en_desc="Use to transform or revert; sneak+use to pick a form."),
    Item("fist_wrap", "拳の包帯", "Fist Wrap", "fist_wrap",
         category="equipment",
         ja_desc="使う=選択中の技、しゃがみ+使う=次の技へ。",
         en_desc="Use for the selected technique; sneak+use to cycle."),
    Item("log_pose", "ログポース", "Log Pose", "log_pose",
         category="items",
         ja_desc="品質・演出・気力無限・訓練場・復旧の設定。",
         en_desc="Quality, effects, infinite energy, training ground, recovery."),
]

#  形態ごとの表示体。アタッチャブルは1つの識別子に1つの geometry しか持てないので、
#  形態の数だけ内部アイテムを用意し、スクリプトが頭スロットに着せ替える。
#  企画書 §14「アイテム増殖を防ぐ構造」に従い、この5つは配布処理を一切通らない —
#  変身で装備し、解除で外すだけ。レシピもクリエイティブ表示も持たない。
for _f in FORMS:
    ITEMS.append(Item(
        f"form_{_f.key}", f"形態表示体（{_f.ja}）", f"Form Body ({_f.en})",
        "straw_hat", wearable="slot.armor.head", hidden=True,
        ja_desc="内部用。変身中の見た目を描くためだけに装備される。",
        en_desc="Internal. Worn only to render the transformed body."))

ITEM_BY_SLUG: Dict[str, Item] = {i.slug: i for i in ITEMS}

FRUIT_ITEM = f"{NS}:devil_fruit"
HAT_ITEM = f"{NS}:straw_hat"
WRAP_ITEM = f"{NS}:fist_wrap"
POSE_ITEM = f"{NS}:log_pose"
def form_item(form_key: str) -> str:
    return f"{NS}:form_{form_key}"


FORM_ITEMS = [form_item(f.key) for f in FORMS]

# ---------------------------------------------------------------------------
#  エンティティ
# ---------------------------------------------------------------------------


@dataclass
class Mob:
    slug: str
    ja: str
    en: str
    geo: str
    health: float
    scale: float = 1.0
    collision: Tuple[float, float] = (0.8, 1.9)
    stationary: bool = True
    speed: float = 0.0
    summonable: bool = True
    despawn: int = 0            # tick。0 なら自然消滅しない
    ja_desc: str = ""

    @property
    def id(self) -> str:
        return f"{NS}:{self.slug}"

    @property
    def geometry(self) -> str:
        return f"geometry.{NS}.{self.geo}"


MOBS: List[Mob] = [
    Mob("training_dummy", "訓練用標的", "Training Dummy", "dummy",
        health=200.0, collision=(0.9, 2.0), stationary=True,
        ja_desc="単体の標的。命中回数と与ダメージを測るための的。"),
    Mob("training_swarm", "群れの標的", "Swarm Target", "dummy_small",
        health=24.0, scale=0.65, collision=(0.6, 1.2), stationary=False,
        speed=0.22, ja_desc="群れの標的。連打と全方位技の検証用。"),
    Mob("vfx_fist", "演出用の拳", "Effect Fist", "vfx_fist",
        health=1.0, collision=(0.1, 0.1), stationary=True, summonable=False,
        despawn=60, ja_desc="内部用。伸びる拳を立体で見せるための短命な表示体。"),
    Mob("thrown_bolt", "投げた雷", "Thrown Bolt", "vfx_bolt",
        health=1.0, collision=(0.2, 0.2), stationary=False, summonable=False,
        despawn=40, ja_desc="内部用。雷の投擲の飛翔体。"),
]

MOB_BY_SLUG: Dict[str, Mob] = {m.slug: m for m in MOBS}

# ---------------------------------------------------------------------------
#  状態 (企画書 §13)
# ---------------------------------------------------------------------------
PHASES = ["normal", "transforming", "active", "attacking", "recovering",
          "reverting", "safe_reset"]

PROPS = {
    "power": f"{NS}:power",          # 能力を得たか
    "form": f"{NS}:form",            # 現在の形態キー。normal でも「変身中」ではない
    "phase": f"{NS}:phase",
    "energy": f"{NS}:energy",
    "hits": f"{NS}:hits",            # 累計命中数（解放条件）
    "tech": f"{NS}:tech",            # 形態ごとの選択中インデックス (JSON)
    "quality": f"{NS}:quality",
    "shortfx": f"{NS}:shortfx",
    "camerafx": f"{NS}:camerafx",
    "infinite": f"{NS}:infinite",
    "stored_armor": f"{NS}:stored_armor",
    "session": f"{NS}:session",
    "terrain": f"{NS}:terrain",      # world: 地形破壊
    "pvp": f"{NS}:pvp",              # world: PvP
}

TAG_ACTIVE = "gla_active"

# 初期値。企画書 §09 のとおり 地形破壊 / PvP は OFF。
DEFAULTS = {
    "quality": "standard",
    "shortfx": False,
    "camerafx": True,
    "infinite": False,
    "terrain": False,
    "pvp": False,
}

# ---------------------------------------------------------------------------
#  訓練場 (企画書 §12) — 128x128 の港島。区画ごとに役割を決めてある。
# ---------------------------------------------------------------------------
TRAINING = dict(
    size=128,
    zones=[
        dict(key="plaza", ja="訓練広場", en="Training Plaza",
             purpose="標準距離で技を確認する",
             props="距離目盛り・単体/群れの標的・壁越し判定用の遮蔽物"),
        dict(key="studio", ja="撮影エリア", en="Capture Area",
             purpose="形態とアニメの比較",
             props="昼夜を揃えた背景・正面と斜めの基準位置・全身が入る床目印"),
        dict(key="load", ja="負荷テスト区画", en="Load Test Yard",
             purpose="同時戦闘時の重さを測る",
             props="人数と敵数を固定できる配置・連続発動する技の指定"),
        dict(key="course", ja="移動コース", en="Movement Course",
             purpose="見た目の追従を確認",
             props="段差・狭い入口・坂・ジャンプ・水際"),
    ],
    markers=[5, 10, 15, 20, 25],     # 距離目盛り（ブロック）
)

# ---------------------------------------------------------------------------
#  検収チェックリスト (企画書 §17) — README と QA 表の生成元
# ---------------------------------------------------------------------------
QA_CHECKS = [
    ("QA-01", "新規インポート", "BP/RPが認識され、依存不足・参照欠落・致命的エラーがない。"),
    ("QA-02", "更新導入", "既存版から更新し、保存した設定・解放状態を保つ。"),
    ("QA-03", "アイテム使用100回", "変身・技切替・設定操作で個数の増減がない。"),
    ("QA-04", "変身・解除20往復", "本体消失、二重表示、旧形態残留、予約技の暴発がない。"),
    ("QA-05", "全身の可視性", "前後の三人称、昼夜、屋内で形態と表情が判別できる。"),
    ("QA-06", "最大伸長・巨大拳", "描画範囲外への早すぎる消失、関節の穴、UV破綻がない。"),
    ("QA-07", "単発と連打の命中", "定義回数だけ命中し、背面・壁越し・自分へ誤爆しない。"),
    ("QA-08", "命中タイミング", "接触の見た目と判定時刻の差を原則1tick以内へ。"),
    ("QA-09", "気力無限", "消費だけ無効。無敵・連射無制限が生じない。"),
    ("QA-10", "地形破壊OFF", "すべての大技で地形変更と不要な火災を起こさない。"),
    ("QA-11", "死亡・再参加", "復旧し、操作制限と視点が残らない。"),
    ("QA-12", "場所の切替", "水中、段差、ディメンション移動後も追従と復旧が成立。"),
    ("QA-13", "2〜4人同時", "他人の形態・技・カメラが混ざらない。"),
    ("QA-14", "30分の連続戦闘", "劣化、残留エンティティの増加、クラッシュがない。"),
    ("QA-15", "タッチ操作・UI", "文字が切れず、技切替と発動を誤って同時受付しない。"),
]


# ---------------------------------------------------------------------------
#  生成物が参照するパーティクル一覧 — gen_particles.py と validate.py の突合用
# ---------------------------------------------------------------------------
def all_particles() -> List[str]:
    seen: List[str] = []
    for t in TECHS:
        for s in t.stages:
            if s["fx"] not in seen:
                seen.append(s["fx"])
    for step in SHOWPIECE:
        for s in step["stages"]:
            if s["fx"] not in seen:
                seen.append(s["fx"])
    for extra in ("gla:transform_burst", "gla:revert_puff", "gla:steam_idle",
                  "gla:cloud_idle", "gla:haki_idle", "gla:low_energy",
                  "gla:unlock_spark", "gla:target_mark"):
        if extra not in seen:
            seen.append(extra)
    return seen


def all_sounds() -> List[str]:
    """同梱しない、バニラの音だけを使う（企画書 §11 音の制作）。"""
    seen: List[str] = []
    for t in TECHS:
        for s in t.sfx:
            if s["id"] not in seen:
                seen.append(s["id"])
    for step in SHOWPIECE:
        for s in step.get("sfx", []):
            if s["id"] not in seen:
                seen.append(s["id"])
    return seen


def summary() -> str:
    lines = [f"{len(FORMS)} forms / {len(TECHS)} techniques / "
             f"{len(ITEMS)} items / {len(MOBS)} entities / "
             f"{len(all_particles())} particles"]
    for f in FORMS:
        ts = techs_of(f.key)
        lines.append(f"  {f.key:12s} {f.ja:18s} {len(ts)}技 "
                     f"upkeep {f.upkeep}/s unlock {f.unlock_hits}命中")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
    assert len(TECHS) == 24, f"技は24枠のはず: {len(TECHS)}"
    assert len({t.slug for t in TECHS}) == 24, "技IDが重複している"
    for t in TECHS:
        assert t.form in FORM_BY_KEY, f"{t.slug}: 未知の形態 {t.form}"
        assert t.stages, f"{t.slug}: 演出が空"
        layers = {s["layer"] for s in t.stages}
        assert LAYER_OMEN in layers, f"{t.slug}: 予兆がない"
    print("spec ok")
