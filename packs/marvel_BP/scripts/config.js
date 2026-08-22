// ===========================================================================
//  自動生成ファイル — 手で編集しないこと。
//  tools/marvel/contract.py を直して `python3 tools/marvel/gen_config.py`。
// ===========================================================================

export const NS = "marvel";

/** 動的プロパティ名 */
export const PROP = {
  "mutant": "marvel:mutant",
  "hero": "marvel:hero",
  "form": "marvel:form",
  "stage": "marvel:stage",
  "mag": "marvel:mag",
  "mastery": "marvel:mastery",
  "tech": "marvel:tech",
  "flying": "marvel:flying",
  "sight": "marvel:sight",
  "barrier": "marvel:barrier",
  "stored": "marvel:stored_armor",
  "casting": "marvel:casting"
};

/** タグ */
export const TAG = {
  "form": "marvel_form",
  "ally": "marvel_ally",
  "hostile": "marvel_hostile",
  "bound": "marvel_bound",
  "emp": "marvel_emp"
};

/** タイプファミリ */
export const FAMILY = {
  "mutant": "mutant",
  "brotherhood": "brotherhood",
  "sentinel": "sentinel",
  "mrd": "mrd",
  "prop": "marvel_prop"
};

/** 磁力ゲージ */
export const MAG_MAX = 100.0;
export const MAG_REGEN = 3.0;
export const MAG_REGEN_STAGE3 = 6.0;
export const MAG_DRAIN = 0.6;

/** 段階の解禁条件 [撃破数, 段階] */
export const STAGE_THRESHOLDS = [
  [
    0,
    1
  ],
  [
    25,
    2
  ],
  [
    80,
    3
  ]
];

/** 磁力が効くブロックと、その磁化強度 */
export const MAGNETIC_BLOCKS = {
  "minecraft:iron_block": 1.0,
  "minecraft:iron_ore": 0.55,
  "minecraft:deepslate_iron_ore": 0.55,
  "minecraft:raw_iron_block": 0.85,
  "minecraft:iron_bars": 0.45,
  "minecraft:iron_door": 0.6,
  "minecraft:iron_trapdoor": 0.6,
  "minecraft:heavy_weighted_pressure_plate": 0.4,
  "minecraft:anvil": 1.2,
  "minecraft:chipped_anvil": 1.1,
  "minecraft:damaged_anvil": 1.0,
  "minecraft:chain": 0.35,
  "minecraft:rail": 0.3,
  "minecraft:golden_rail": 0.35,
  "minecraft:detector_rail": 0.35,
  "minecraft:activator_rail": 0.35,
  "minecraft:hopper": 0.7,
  "minecraft:cauldron": 0.6,
  "minecraft:gold_block": 0.7,
  "minecraft:gold_ore": 0.4,
  "minecraft:deepslate_gold_ore": 0.4,
  "minecraft:raw_gold_block": 0.6,
  "minecraft:copper_block": 0.8,
  "minecraft:copper_ore": 0.45,
  "minecraft:deepslate_copper_ore": 0.45,
  "minecraft:raw_copper_block": 0.7,
  "minecraft:cut_copper": 0.75,
  "minecraft:exposed_copper": 0.75,
  "minecraft:weathered_copper": 0.7,
  "minecraft:oxidized_copper": 0.65,
  "minecraft:lightning_rod": 0.5,
  "minecraft:netherite_block": 1.4,
  "minecraft:ancient_debris": 1.0,
  "minecraft:cauldron_block": 0.6,
  "minecraft:blast_furnace": 0.55,
  "minecraft:furnace": 0.3,
  "minecraft:iron_chain": 0.35,
  "minecraft:redstone_block": 0.5,
  "minecraft:redstone_ore": 0.3,
  "minecraft:crying_obsidian": 0.0
};

/** 装備の素材名 -> 圧壊倍率 */
export const MAGNETIC_ITEMS = {
  "iron": 1.0,
  "gold": 0.8,
  "chainmail": 0.9,
  "netherite": 1.3,
  "copper": 0.85,
  "shield": 0.5
};
export const IMMUNE_ITEMS = [
  "adamantium"
];

/** アイテム */
export const ITEM = {
  "x_gene": "marvel:x_gene",
  "magneto_helmet": "marvel:magneto_helmet",
  "brotherhood_pin": "marvel:brotherhood_pin",
  "cerebro": "marvel:cerebro",
  "brotherhood_beacon": "marvel:brotherhood_beacon",
  "magneto_form": "marvel:magneto_form",
  "metal_scrap": "marvel:metal_scrap",
  "magnetic_alloy": "marvel:magnetic_alloy",
  "sentinel_core": "marvel:sentinel_core",
  "adamantium_ingot": "marvel:adamantium_ingot"
};

/** 技 */
export const TECH = {
  "repulse": {
    "item": "marvel:tech_repulse",
    "ja": "磁力斥力",
    "en": "Repulse",
    "pose": "cast",
    "clip": "repulse",
    "cost": 12,
    "cd": 20,
    "stage": 1,
    "colour": "#7B4BC8",
    "hold": 22,
    "form": "marvel:magneto_form_repulse",
    "ultimate": false
  },
  "attract": {
    "item": "marvel:tech_attract",
    "ja": "磁力引力",
    "en": "Attract",
    "pose": "cast",
    "clip": "attract",
    "cost": 10,
    "cd": 20,
    "stage": 1,
    "colour": "#4B7BC8",
    "hold": 22,
    "form": "marvel:magneto_form_attract",
    "ultimate": false
  },
  "disarm": {
    "item": "marvel:tech_disarm",
    "ja": "金属剥奪",
    "en": "Disarm",
    "pose": "cast",
    "clip": "disarm",
    "cost": 16,
    "cd": 60,
    "stage": 1,
    "colour": "#C8C04B",
    "hold": 22,
    "form": "marvel:magneto_form_disarm",
    "ultimate": false
  },
  "lance": {
    "item": "marvel:tech_lance",
    "ja": "磁界斬",
    "en": "Magnetic Lance",
    "pose": "cast",
    "clip": "lance",
    "cost": 14,
    "cd": 30,
    "stage": 1,
    "colour": "#9B5BE0",
    "hold": 22,
    "form": "marvel:magneto_form_lance",
    "ultimate": false
  },
  "shard_storm": {
    "item": "marvel:tech_shard_storm",
    "ja": "鉄片嵐",
    "en": "Shard Storm",
    "pose": "raise",
    "clip": "shard_storm",
    "cost": 26,
    "cd": 80,
    "stage": 2,
    "colour": "#B04BC8",
    "hold": 34,
    "form": "marvel:magneto_form_shard_storm",
    "ultimate": false
  },
  "barrier": {
    "item": "marvel:tech_barrier",
    "ja": "磁力障壁",
    "en": "Magnetic Barrier",
    "pose": "guard",
    "clip": "barrier",
    "cost": 20,
    "cd": 110,
    "stage": 1,
    "colour": "#4BC8C0",
    "hold": 40,
    "form": "marvel:magneto_form_barrier",
    "ultimate": false
  },
  "iron_bind": {
    "item": "marvel:tech_iron_bind",
    "ja": "鋼鉄拘束",
    "en": "Iron Bind",
    "pose": "cast",
    "clip": "iron_bind",
    "cost": 22,
    "cd": 90,
    "stage": 2,
    "colour": "#8E8E9A",
    "hold": 22,
    "form": "marvel:magneto_form_iron_bind",
    "ultimate": false
  },
  "crush": {
    "item": "marvel:tech_crush",
    "ja": "磁気圧壊",
    "en": "Crush",
    "pose": "cast",
    "clip": "crush",
    "cost": 30,
    "cd": 120,
    "stage": 2,
    "colour": "#C8344B",
    "hold": 22,
    "form": "marvel:magneto_form_crush",
    "ultimate": false
  },
  "uprising": {
    "item": "marvel:tech_uprising",
    "ja": "大地隆起",
    "en": "Ore Uprising",
    "pose": "raise",
    "clip": "uprising",
    "cost": 34,
    "cd": 140,
    "stage": 2,
    "colour": "#C8843A",
    "hold": 34,
    "form": "marvel:magneto_form_uprising",
    "ultimate": false
  },
  "emp": {
    "item": "marvel:tech_emp",
    "ja": "EMPパルス",
    "en": "EMP Pulse",
    "pose": "focus",
    "clip": "emp",
    "cost": 24,
    "cd": 140,
    "stage": 2,
    "colour": "#4BE0FF",
    "hold": 26,
    "form": "marvel:magneto_form_emp",
    "ultimate": false
  },
  "polarity": {
    "item": "marvel:tech_polarity",
    "ja": "磁極反転",
    "en": "Polarity Reversal",
    "pose": "raise",
    "clip": "polarity",
    "cost": 28,
    "cd": 160,
    "stage": 2,
    "colour": "#6B4BE0",
    "hold": 34,
    "form": "marvel:magneto_form_polarity",
    "ultimate": false
  },
  "flight": {
    "item": "marvel:tech_flight",
    "ja": "磁気飛行",
    "en": "Magnetic Flight",
    "pose": "fly",
    "clip": "flight",
    "cost": 8,
    "cd": 10,
    "stage": 1,
    "colour": "#9B7BE0",
    "hold": 0,
    "form": "marvel:magneto_form_flight",
    "ultimate": false
  },
  "throne": {
    "item": "marvel:tech_throne",
    "ja": "鋼鉄の玉座",
    "en": "Steel Throne",
    "pose": "cast",
    "clip": "throne",
    "cost": 18,
    "cd": 100,
    "stage": 2,
    "colour": "#8E9AA8",
    "hold": 22,
    "form": "marvel:magneto_form_throne",
    "ultimate": false
  },
  "sight": {
    "item": "marvel:tech_sight",
    "ja": "磁力視",
    "en": "Magnetic Sight",
    "pose": "focus",
    "clip": "sight",
    "cost": 6,
    "cd": 40,
    "stage": 1,
    "colour": "#4BC8FF",
    "hold": 26,
    "form": "marvel:magneto_form_sight",
    "ultimate": false
  },
  "sphere": {
    "item": "marvel:tech_sphere",
    "ja": "磁界の棺",
    "en": "Sphere of Ruin",
    "pose": "raise",
    "clip": "sphere",
    "cost": 70,
    "cd": 400,
    "stage": 3,
    "colour": "#E04B7B",
    "hold": 34,
    "form": "marvel:magneto_form_sphere",
    "ultimate": true
  }
};
export const TECH_ORDER = [
  "repulse",
  "attract",
  "disarm",
  "lance",
  "flight",
  "sight",
  "barrier",
  "shard_storm",
  "iron_bind",
  "crush",
  "uprising",
  "emp",
  "polarity",
  "throne",
  "sphere"
];

/** アイテム ID -> 技キー */
export const TECH_BY_ITEM = {
  "marvel:tech_repulse": "repulse",
  "marvel:tech_attract": "attract",
  "marvel:tech_disarm": "disarm",
  "marvel:tech_lance": "lance",
  "marvel:tech_shard_storm": "shard_storm",
  "marvel:tech_barrier": "barrier",
  "marvel:tech_iron_bind": "iron_bind",
  "marvel:tech_crush": "crush",
  "marvel:tech_uprising": "uprising",
  "marvel:tech_emp": "emp",
  "marvel:tech_polarity": "polarity",
  "marvel:tech_flight": "flight",
  "marvel:tech_throne": "throne",
  "marvel:tech_sight": "sight",
  "marvel:tech_sphere": "sphere"
};

/** ブラザーフッドの技 */
export const ALLY_TECH = {
  "mystique": [
    {
      "key": "shapeshift",
      "ja": "擬態",
      "en": "Shapeshift",
      "cost": 14,
      "cd": 120,
      "colour": "#1E4E8C",
      "form": "marvel:mystique_form_shapeshift"
    },
    {
      "key": "venom_strike",
      "ja": "毒撃",
      "en": "Venom Strike",
      "cost": 10,
      "cd": 50,
      "colour": "#3AC86B",
      "form": "marvel:mystique_form_venom_strike"
    },
    {
      "key": "vanish",
      "ja": "影渡り",
      "en": "Vanish",
      "cost": 12,
      "cd": 90,
      "colour": "#2A2A5E",
      "form": "marvel:mystique_form_vanish"
    }
  ],
  "sabretooth": [
    {
      "key": "rend",
      "ja": "裂爪",
      "en": "Rend",
      "cost": 10,
      "cd": 30,
      "colour": "#C8344B",
      "form": "marvel:sabretooth_form_rend"
    },
    {
      "key": "feral_roar",
      "ja": "獣咆",
      "en": "Feral Roar",
      "cost": 16,
      "cd": 100,
      "colour": "#C8843A",
      "form": "marvel:sabretooth_form_feral_roar"
    },
    {
      "key": "regenerate",
      "ja": "超回復",
      "en": "Regenerate",
      "cost": 20,
      "cd": 160,
      "colour": "#3AC86B",
      "form": "marvel:sabretooth_form_regenerate"
    }
  ],
  "toad": [
    {
      "key": "tongue_lash",
      "ja": "舌鞭",
      "en": "Tongue Lash",
      "cost": 8,
      "cd": 40,
      "colour": "#4A6B2A",
      "form": "marvel:toad_form_tongue_lash"
    },
    {
      "key": "leap",
      "ja": "大跳躍",
      "en": "Great Leap",
      "cost": 10,
      "cd": 50,
      "colour": "#6B8E3A",
      "form": "marvel:toad_form_leap"
    },
    {
      "key": "slime_spit",
      "ja": "粘液弾",
      "en": "Slime Spit",
      "cost": 12,
      "cd": 60,
      "colour": "#8EC84B",
      "form": "marvel:toad_form_slime_spit"
    }
  ],
  "juggernaut": [
    {
      "key": "unstoppable",
      "ja": "無停止突進",
      "en": "Unstoppable",
      "cost": 26,
      "cd": 140,
      "colour": "#8E1F1F",
      "form": "marvel:juggernaut_form_unstoppable"
    },
    {
      "key": "quake_stomp",
      "ja": "地砕き",
      "en": "Quake Stomp",
      "cost": 20,
      "cd": 100,
      "colour": "#6B5A48",
      "form": "marvel:juggernaut_form_quake_stomp"
    },
    {
      "key": "hurl",
      "ja": "投擲",
      "en": "Hurl",
      "cost": 16,
      "cd": 80,
      "colour": "#8E8E9A",
      "form": "marvel:juggernaut_form_hurl"
    }
  ],
  "quicksilver": [
    {
      "key": "blitz",
      "ja": "音速連撃",
      "en": "Blitz",
      "cost": 18,
      "cd": 70,
      "colour": "#C8CBD2",
      "form": "marvel:quicksilver_form_blitz"
    },
    {
      "key": "afterimage",
      "ja": "残像",
      "en": "Afterimage",
      "cost": 14,
      "cd": 90,
      "colour": "#8EB4E0",
      "form": "marvel:quicksilver_form_afterimage"
    },
    {
      "key": "sonic_dash",
      "ja": "超加速",
      "en": "Sonic Dash",
      "cost": 10,
      "cd": 40,
      "colour": "#4B9BE0",
      "form": "marvel:quicksilver_form_sonic_dash"
    }
  ],
  "pyro": [
    {
      "key": "flame_wave",
      "ja": "炎波",
      "en": "Flame Wave",
      "cost": 16,
      "cd": 60,
      "colour": "#D8621E",
      "form": "marvel:pyro_form_flame_wave"
    },
    {
      "key": "fire_serpent",
      "ja": "炎蛇",
      "en": "Fire Serpent",
      "cost": 22,
      "cd": 100,
      "colour": "#E88A2A",
      "form": "marvel:pyro_form_fire_serpent"
    },
    {
      "key": "ignite",
      "ja": "発火",
      "en": "Ignite",
      "cost": 8,
      "cd": 30,
      "colour": "#F0B23A",
      "form": "marvel:pyro_form_ignite"
    }
  ],
  "avalanche": [
    {
      "key": "tremor",
      "ja": "震動",
      "en": "Tremor",
      "cost": 14,
      "cd": 60,
      "colour": "#6B5A48",
      "form": "marvel:avalanche_form_tremor"
    },
    {
      "key": "rockfall",
      "ja": "落盤",
      "en": "Rockfall",
      "cost": 22,
      "cd": 110,
      "colour": "#8E7A5A",
      "form": "marvel:avalanche_form_rockfall"
    },
    {
      "key": "fissure",
      "ja": "地割れ",
      "en": "Fissure",
      "cost": 26,
      "cd": 130,
      "colour": "#5A4A38",
      "form": "marvel:avalanche_form_fissure"
    }
  ],
  "blob": [
    {
      "key": "immovable",
      "ja": "不動",
      "en": "Immovable",
      "cost": 18,
      "cd": 120,
      "colour": "#C4A05A",
      "form": "marvel:blob_form_immovable"
    },
    {
      "key": "belly_bounce",
      "ja": "弾き返し",
      "en": "Belly Bounce",
      "cost": 14,
      "cd": 70,
      "colour": "#D8B46A",
      "form": "marvel:blob_form_belly_bounce"
    },
    {
      "key": "body_slam",
      "ja": "のしかかり",
      "en": "Body Slam",
      "cost": 20,
      "cd": 90,
      "colour": "#8E7A4A",
      "form": "marvel:blob_form_body_slam"
    }
  ],
  "scarlet_witch": [
    {
      "key": "hex_bolt",
      "ja": "ヘックス弾",
      "en": "Hex Bolt",
      "cost": 12,
      "cd": 40,
      "colour": "#8E1224",
      "form": "marvel:scarlet_witch_form_hex_bolt"
    },
    {
      "key": "chaos_field",
      "ja": "混沌領域",
      "en": "Chaos Field",
      "cost": 24,
      "cd": 130,
      "colour": "#C82A4B",
      "form": "marvel:scarlet_witch_form_chaos_field"
    },
    {
      "key": "telekinesis",
      "ja": "念動",
      "en": "Telekinesis",
      "cost": 18,
      "cd": 80,
      "colour": "#E04B7B",
      "form": "marvel:scarlet_witch_form_telekinesis"
    }
  ]
};

/** 変身できるキャラ */
export const HERO = {
  "magneto": {
    "ja": "マグニートー",
    "en": "Magneto",
    "form": "marvel:magneto_form",
    "health": 520,
    "damage": 14,
    "lead": true
  },
  "mystique": {
    "ja": "ミスティーク",
    "en": "Mystique",
    "form": "marvel:mystique_form",
    "health": 140,
    "damage": 9,
    "lead": false
  },
  "sabretooth": {
    "ja": "セイバートゥース",
    "en": "Sabretooth",
    "form": "marvel:sabretooth_form",
    "health": 260,
    "damage": 16,
    "lead": false
  },
  "toad": {
    "ja": "トード",
    "en": "Toad",
    "form": "marvel:toad_form",
    "health": 120,
    "damage": 7,
    "lead": false
  },
  "juggernaut": {
    "ja": "ジャガーノート",
    "en": "Juggernaut",
    "form": "marvel:juggernaut_form",
    "health": 700,
    "damage": 26,
    "lead": false
  },
  "quicksilver": {
    "ja": "クイックシルバー",
    "en": "Quicksilver",
    "form": "marvel:quicksilver_form",
    "health": 130,
    "damage": 8,
    "lead": false
  },
  "pyro": {
    "ja": "パイロ",
    "en": "Pyro",
    "form": "marvel:pyro_form",
    "health": 130,
    "damage": 9,
    "lead": false
  },
  "avalanche": {
    "ja": "アバランチ",
    "en": "Avalanche",
    "form": "marvel:avalanche_form",
    "health": 200,
    "damage": 14,
    "lead": false
  },
  "blob": {
    "ja": "ブロブ",
    "en": "Blob",
    "form": "marvel:blob_form",
    "health": 560,
    "damage": 18,
    "lead": false
  },
  "scarlet_witch": {
    "ja": "スカーレット・ウィッチ",
    "en": "Scarlet Witch",
    "form": "marvel:scarlet_witch_form",
    "health": 170,
    "damage": 12,
    "lead": false
  }
};
export const HERO_ORDER = [
  "magneto",
  "mystique",
  "sabretooth",
  "toad",
  "juggernaut",
  "quicksilver",
  "pyro",
  "avalanche",
  "blob",
  "scarlet_witch"
];

/** すべての変身体アイテム（掃除用） */
export const FORM_ITEMS = [
  "marvel:avalanche_form",
  "marvel:avalanche_form_fissure",
  "marvel:avalanche_form_rockfall",
  "marvel:avalanche_form_tremor",
  "marvel:blob_form",
  "marvel:blob_form_belly_bounce",
  "marvel:blob_form_body_slam",
  "marvel:blob_form_immovable",
  "marvel:juggernaut_form",
  "marvel:juggernaut_form_hurl",
  "marvel:juggernaut_form_quake_stomp",
  "marvel:juggernaut_form_unstoppable",
  "marvel:magneto_form",
  "marvel:magneto_form_attract",
  "marvel:magneto_form_barrier",
  "marvel:magneto_form_crush",
  "marvel:magneto_form_disarm",
  "marvel:magneto_form_emp",
  "marvel:magneto_form_flight",
  "marvel:magneto_form_iron_bind",
  "marvel:magneto_form_lance",
  "marvel:magneto_form_polarity",
  "marvel:magneto_form_repulse",
  "marvel:magneto_form_shard_storm",
  "marvel:magneto_form_sight",
  "marvel:magneto_form_sphere",
  "marvel:magneto_form_throne",
  "marvel:magneto_form_uprising",
  "marvel:mystique_form",
  "marvel:mystique_form_shapeshift",
  "marvel:mystique_form_vanish",
  "marvel:mystique_form_venom_strike",
  "marvel:pyro_form",
  "marvel:pyro_form_fire_serpent",
  "marvel:pyro_form_flame_wave",
  "marvel:pyro_form_ignite",
  "marvel:quicksilver_form",
  "marvel:quicksilver_form_afterimage",
  "marvel:quicksilver_form_blitz",
  "marvel:quicksilver_form_sonic_dash",
  "marvel:sabretooth_form",
  "marvel:sabretooth_form_feral_roar",
  "marvel:sabretooth_form_regenerate",
  "marvel:sabretooth_form_rend",
  "marvel:scarlet_witch_form",
  "marvel:scarlet_witch_form_chaos_field",
  "marvel:scarlet_witch_form_hex_bolt",
  "marvel:scarlet_witch_form_telekinesis",
  "marvel:toad_form",
  "marvel:toad_form_leap",
  "marvel:toad_form_slime_spit",
  "marvel:toad_form_tongue_lash"
];

/** エンティティ */
export const ENTITY = {
  "magneto": "marvel:magneto",
  "mystique": "marvel:mystique",
  "sabretooth": "marvel:sabretooth",
  "toad": "marvel:toad",
  "juggernaut": "marvel:juggernaut",
  "quicksilver": "marvel:quicksilver",
  "pyro": "marvel:pyro",
  "avalanche": "marvel:avalanche",
  "blob": "marvel:blob",
  "scarlet_witch": "marvel:scarlet_witch",
  "sentinel": "marvel:sentinel",
  "prime_sentinel": "marvel:prime_sentinel",
  "sentinel_drone": "marvel:sentinel_drone",
  "mrd_trooper": "marvel:mrd_trooper",
  "metal_shard": "marvel:metal_shard",
  "debris": "marvel:debris",
  "hex_bolt": "marvel:hex_bolt",
  "fire_bolt": "marvel:fire_bolt",
  "sentinel_beam": "marvel:sentinel_beam",
  "barrier_dome": "marvel:barrier_dome",
  "steel_platform": "marvel:steel_platform",
  "orbit_shard": "marvel:orbit_shard",
  "ruin_sphere": "marvel:ruin_sphere",
  "iron_cage": "marvel:iron_cage"
};

/** パーティクル */
export const FX = {
  "mag_field": "marvel:mag_field",
  "mag_pull": "marvel:mag_pull",
  "mag_push": "marvel:mag_push",
  "mag_line": "marvel:mag_line",
  "mag_glyph": "marvel:mag_glyph",
  "mag_spark": "marvel:mag_spark",
  "mag_aura": "marvel:mag_aura",
  "mag_aura_max": "marvel:mag_aura_max",
  "mag_ring": "marvel:mag_ring",
  "mag_ring_wide": "marvel:mag_ring_wide",
  "mag_dust": "marvel:mag_dust",
  "shard_spark": "marvel:shard_spark",
  "shard_trail": "marvel:shard_trail",
  "shard_burst": "marvel:shard_burst",
  "metal_glint": "marvel:metal_glint",
  "metal_rip": "marvel:metal_rip",
  "debris_chunk": "marvel:debris_chunk",
  "debris_dust": "marvel:debris_dust",
  "rust_flake": "marvel:rust_flake",
  "repulse_wave": "marvel:repulse_wave",
  "attract_funnel": "marvel:attract_funnel",
  "disarm_flash": "marvel:disarm_flash",
  "lance_streak": "marvel:lance_streak",
  "lance_impact": "marvel:lance_impact",
  "storm_swirl": "marvel:storm_swirl",
  "barrier_hex": "marvel:barrier_hex",
  "barrier_break": "marvel:barrier_break",
  "bind_weld": "marvel:bind_weld",
  "crush_implode": "marvel:crush_implode",
  "crush_blood": "marvel:crush_blood",
  "uprising_soil": "marvel:uprising_soil",
  "uprising_pillar": "marvel:uprising_pillar",
  "emp_wave": "marvel:emp_wave",
  "emp_arc": "marvel:emp_arc",
  "polarity_field": "marvel:polarity_field",
  "throne_dust": "marvel:throne_dust",
  "sight_ping": "marvel:sight_ping",
  "sphere_core": "marvel:sphere_core",
  "sphere_orbit": "marvel:sphere_orbit",
  "sphere_collapse": "marvel:sphere_collapse",
  "sphere_detonate": "marvel:sphere_detonate",
  "flight_trail": "marvel:flight_trail",
  "flight_burst": "marvel:flight_burst",
  "cape_wind": "marvel:cape_wind",
  "transform_burst": "marvel:transform_burst",
  "transform_ring": "marvel:transform_ring",
  "revert_smoke": "marvel:revert_smoke",
  "levitate_dust": "marvel:levitate_dust",
  "shift_shimmer": "marvel:shift_shimmer",
  "venom_drip": "marvel:venom_drip",
  "claw_slash": "marvel:claw_slash",
  "roar_wave": "marvel:roar_wave",
  "regen_knit": "marvel:regen_knit",
  "tongue_slime": "marvel:tongue_slime",
  "leap_dust": "marvel:leap_dust",
  "slime_splat": "marvel:slime_splat",
  "quake_dust": "marvel:quake_dust",
  "quake_crack": "marvel:quake_crack",
  "rock_fall": "marvel:rock_fall",
  "blur_after": "marvel:blur_after",
  "speed_line": "marvel:speed_line",
  "flame_wave": "marvel:flame_wave",
  "flame_serpent": "marvel:flame_serpent",
  "ember_rise": "marvel:ember_rise",
  "hex_wave": "marvel:hex_wave",
  "hex_bolt_trail": "marvel:hex_bolt_trail",
  "chaos_motes": "marvel:chaos_motes",
  "tk_lift": "marvel:tk_lift",
  "slam_ring": "marvel:slam_ring",
  "sentinel_beam_charge": "marvel:sentinel_beam_charge",
  "sentinel_beam_trail": "marvel:sentinel_beam_trail",
  "sentinel_beam_impact": "marvel:sentinel_beam_impact",
  "sentinel_spark": "marvel:sentinel_spark",
  "sentinel_smoke": "marvel:sentinel_smoke",
  "sentinel_scan": "marvel:sentinel_scan",
  "core_break": "marvel:core_break",
  "mrd_muzzle": "marvel:mrd_muzzle",
  "impact_dust": "marvel:impact_dust",
  "heavy_land": "marvel:heavy_land",
  "hurt_spark": "marvel:hurt_spark",
  "blood_red": "marvel:blood_red"
};

/** サウンド（バニラのイベント名） */
export const SOUND = {
  "transform": "mob.evocation_illager.prepare_attack",
  "transform_2": "beacon.activate",
  "revert": "beacon.deactivate",
  "mag_charge": "beacon.ambient",
  "mag_release": "mob.warden.sonic_boom",
  "repulse": "random.explode",
  "attract": "mob.shulker.teleport",
  "disarm": "random.break",
  "lance": "item.trident.throw",
  "shard": "random.bowhit",
  "barrier": "block.beacon.power_select",
  "barrier_hit": "random.anvil_land",
  "bind": "random.anvil_use",
  "crush": "random.anvil_land",
  "uprising": "mob.ravager.roar",
  "emp": "mob.warden.sonic_charge",
  "polarity": "portal.travel",
  "flight": "mob.enderdragon.flap",
  "sight": "mob.warden.heartbeat",
  "sphere_charge": "mob.warden.charge",
  "sphere_blast": "mob.warden.sonic_boom",
  "metal_hit": "random.anvil_land",
  "sentinel_step": "mob.ravager.step",
  "sentinel_beam": "mob.guardian.attack",
  "sentinel_die": "random.explode",
  "ui_select": "random.click",
  "ui_open": "random.orb"
};
