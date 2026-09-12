// =========================================================================
//  GRAND LINE AWAKENING — 実行時テーブル
//  自動生成ファイル。編集しないこと。生成元: tools/gla/spec.py
//  （企画書 §09「技の見た目・判定・コストを一つの定義にまとめる」）
// =========================================================================
export const NS = "gla";
export const ENERGY_MAX = 100.0;
export const ENERGY_REGEN = 1.2;
export const ENERGY_REGEN_IDLE = 2.4;
export const LOW_ENERGY = 15.0;
export const PHASES = [
  "normal",
  "transforming",
  "active",
  "attacking",
  "recovering",
  "reverting",
  "safe_reset"
];
export const PROP = {
  "power": "gla:power",
  "form": "gla:form",
  "lastform": "gla:lastform",
  "phase": "gla:phase",
  "energy": "gla:energy",
  "hits": "gla:hits",
  "tech": "gla:tech",
  "quality": "gla:quality",
  "shortfx": "gla:shortfx",
  "camerafx": "gla:camerafx",
  "infinite": "gla:infinite",
  "stored_armor": "gla:stored_armor",
  "session": "gla:session",
  "terrain": "gla:terrain",
  "pvp": "gla:pvp"
};
export const TAG_ACTIVE = "gla_active";
export const DEFAULTS = {
  "quality": "standard",
  "shortfx": false,
  "camerafx": true,
  "infinite": false,
  "terrain": false,
  "pvp": false
};
export const QUALITY = {
  "light": {
    "ja": "軽量",
    "en": "Light",
    "layers": [
      1,
      2,
      3
    ],
    "density": 0.45,
    "helpers": 8,
    "showpiece": 1,
    "cubes": [
      120,
      220
    ]
  },
  "standard": {
    "ja": "標準",
    "en": "Standard",
    "layers": [
      1,
      2,
      3,
      4
    ],
    "density": 0.8,
    "helpers": 16,
    "showpiece": 2,
    "cubes": [
      250,
      450
    ]
  },
  "high": {
    "ja": "高品質",
    "en": "High",
    "layers": [
      1,
      2,
      3,
      4,
      5
    ],
    "density": 1.0,
    "helpers": 24,
    "showpiece": 2,
    "cubes": [
      500,
      1000
    ]
  }
};
export const QUALITY_ORDER = [
  "light",
  "standard",
  "high"
];
export const FORMS = [
  {
    "key": "normal",
    "name": "gla.form.normal",
    "item": "gla:form_normal",
    "upkeep": 0.0,
    "enter": 0.0,
    "unlock": 0,
    "effects": [],
    "transient": false
  },
  {
    "key": "gear2",
    "name": "gla.form.gear2",
    "item": "gla:form_gear2",
    "upkeep": 0.85,
    "enter": 6.0,
    "unlock": 20,
    "effects": [
      [
        "speed",
        1
      ],
      [
        "haste",
        1
      ]
    ],
    "transient": false
  },
  {
    "key": "gear3",
    "name": "gla.form.gear3",
    "item": "gla:form_gear3",
    "upkeep": 0.35,
    "enter": 8.0,
    "unlock": 60,
    "effects": [
      [
        "resistance",
        0
      ]
    ],
    "transient": true
  },
  {
    "key": "gear4_bound",
    "name": "gla.form.gear4_bound",
    "item": "gla:form_gear4_bound",
    "upkeep": 1.3,
    "enter": 14.0,
    "unlock": 120,
    "effects": [
      [
        "strength",
        1
      ],
      [
        "resistance",
        1
      ],
      [
        "jump_boost",
        1
      ]
    ],
    "transient": false
  },
  {
    "key": "gear4_snake",
    "name": "gla.form.gear4_snake",
    "item": "gla:form_gear4_snake",
    "upkeep": 1.3,
    "enter": 14.0,
    "unlock": 200,
    "effects": [
      [
        "speed",
        2
      ],
      [
        "strength",
        0
      ]
    ],
    "transient": false
  },
  {
    "key": "gear5",
    "name": "gla.form.gear5",
    "item": "gla:form_gear5",
    "upkeep": 2.1,
    "enter": 26.0,
    "unlock": 320,
    "effects": [
      [
        "strength",
        2
      ],
      [
        "resistance",
        2
      ],
      [
        "speed",
        1
      ],
      [
        "jump_boost",
        2
      ],
      [
        "regeneration",
        0
      ],
      [
        "fire_resistance",
        0
      ]
    ],
    "transient": false
  }
];
export const FORM_ORDER = [
  "normal",
  "gear2",
  "gear3",
  "gear4_bound",
  "gear4_snake",
  "gear5"
];
export const TECHS = [
  {
    "id": "pistol",
    "form": "normal",
    "name": "gla.tech.pistol",
    "shape": "line",
    "cost": 5,
    "cd": 16,
    "windup": 4,
    "active": 6,
    "recover": 8,
    "reach": 9.0,
    "radius": 0.85,
    "damage": 7.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.95,
    "kbV": 0.22,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.pistol",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:stretch_coil",
        "form": "ring",
        "n": 6,
        "r": 0.45
      },
      {
        "t": 4,
        "layer": 2,
        "fx": "gla:fist_trail",
        "form": "line",
        "n": 10,
        "d": 9.0
      },
      {
        "t": 4,
        "layer": 2,
        "fx": "gla:speed_line",
        "form": "line",
        "n": 6,
        "d": 9.0
      },
      {
        "t": 7,
        "layer": 3,
        "fx": "gla:impact_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 7,
        "layer": 4,
        "fx": "gla:impact_ring",
        "form": "ring",
        "n": 8,
        "r": 1.1,
        "at": "target"
      },
      {
        "t": 12,
        "layer": 5,
        "fx": "gla:rubber_snap",
        "form": "scatter",
        "n": 4,
        "spread": 0.6
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.small",
        "v": 0.7,
        "p": 1.5
      },
      {
        "t": 7,
        "id": "random.anvil_land",
        "v": 0.55,
        "p": 1.9
      }
    ]
  },
  {
    "id": "bazooka",
    "form": "normal",
    "name": "gla.tech.bazooka",
    "shape": "cone",
    "cost": 11,
    "cd": 48,
    "windup": 10,
    "active": 6,
    "recover": 12,
    "reach": 6.0,
    "radius": 2.4,
    "damage": 11.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.7,
    "kbV": 0.48,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.bazooka",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:charge_draw",
        "form": "ring",
        "n": 10,
        "r": 0.9
      },
      {
        "t": 6,
        "layer": 1,
        "fx": "gla:charge_draw",
        "form": "ring",
        "n": 8,
        "r": 0.55
      },
      {
        "t": 10,
        "layer": 2,
        "fx": "gla:palm_push",
        "form": "cone",
        "n": 14,
        "r": 2.4,
        "d": 6.0
      },
      {
        "t": 12,
        "layer": 3,
        "fx": "gla:impact_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 12,
        "layer": 4,
        "fx": "gla:shock_fan",
        "form": "fan",
        "n": 12,
        "r": 2.6,
        "sweep": 110
      },
      {
        "t": 18,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 6,
        "spread": 1.6,
        "at": "feet"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.6,
        "p": 0.9
      },
      {
        "t": 12,
        "id": "random.explode",
        "v": 0.75,
        "p": 1.55
      }
    ]
  },
  {
    "id": "gatling",
    "form": "normal",
    "name": "gla.tech.gatling",
    "shape": "line",
    "cost": 15,
    "cd": 66,
    "windup": 6,
    "active": 24,
    "recover": 10,
    "reach": 6.5,
    "radius": 1.15,
    "damage": 2.4,
    "hits": 12,
    "gap": 2,
    "kbH": 0.22,
    "kbV": 0.04,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.gatling",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:stretch_coil",
        "form": "ring",
        "n": 8,
        "r": 0.5
      },
      {
        "t": 6,
        "layer": 2,
        "fx": "gla:fist_blur",
        "form": "scatter",
        "n": 10,
        "spread": 0.9
      },
      {
        "t": 10,
        "layer": 2,
        "fx": "gla:fist_blur",
        "form": "scatter",
        "n": 10,
        "spread": 1.0
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:fist_blur",
        "form": "scatter",
        "n": 10,
        "spread": 1.1
      },
      {
        "t": 18,
        "layer": 2,
        "fx": "gla:fist_blur",
        "form": "scatter",
        "n": 10,
        "spread": 1.0
      },
      {
        "t": 26,
        "layer": 4,
        "fx": "gla:impact_ring",
        "form": "ring",
        "n": 6,
        "r": 1.3,
        "at": "target"
      },
      {
        "t": 32,
        "layer": 5,
        "fx": "gla:rubber_snap",
        "form": "scatter",
        "n": 5,
        "spread": 0.7
      }
    ],
    "sfx": [
      {
        "t": 6,
        "id": "mob.slime.small",
        "v": 0.5,
        "p": 1.8
      },
      {
        "t": 12,
        "id": "mob.slime.small",
        "v": 0.5,
        "p": 1.9
      },
      {
        "t": 18,
        "id": "mob.slime.small",
        "v": 0.5,
        "p": 2.0
      }
    ]
  },
  {
    "id": "rocket",
    "form": "normal",
    "name": "gla.tech.rocket",
    "shape": "dash",
    "cost": 8,
    "cd": 56,
    "windup": 6,
    "active": 8,
    "recover": 10,
    "reach": 3.0,
    "radius": 1.3,
    "damage": 5.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.7,
    "kbV": 0.35,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.rocket",
    "launch": [
      1.65,
      0.62
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:stretch_coil",
        "form": "ring",
        "n": 10,
        "r": 0.7
      },
      {
        "t": 6,
        "layer": 2,
        "fx": "gla:speed_line",
        "form": "tail",
        "n": 12,
        "d": 4.0
      },
      {
        "t": 10,
        "layer": 2,
        "fx": "gla:speed_line",
        "form": "tail",
        "n": 10,
        "d": 4.0
      },
      {
        "t": 14,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 5,
        "spread": 1.2,
        "at": "feet"
      }
    ],
    "sfx": [
      {
        "t": 6,
        "id": "mob.slime.big",
        "v": 0.7,
        "p": 1.35
      }
    ]
  },
  {
    "id": "jet_pistol",
    "form": "gear2",
    "name": "gla.tech.jet_pistol",
    "shape": "line",
    "cost": 7,
    "cd": 13,
    "windup": 2,
    "active": 5,
    "recover": 5,
    "reach": 11.0,
    "radius": 0.85,
    "damage": 9.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.05,
    "kbV": 0.2,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.jet_pistol",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:steam_wisp",
        "form": "ring",
        "n": 5,
        "r": 0.4
      },
      {
        "t": 2,
        "layer": 2,
        "fx": "gla:jet_streak",
        "form": "line",
        "n": 12,
        "d": 11.0
      },
      {
        "t": 4,
        "layer": 3,
        "fx": "gla:impact_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 4,
        "layer": 4,
        "fx": "gla:impact_ring",
        "form": "ring",
        "n": 6,
        "r": 1.0,
        "at": "target"
      },
      {
        "t": 8,
        "layer": 5,
        "fx": "gla:steam_wisp",
        "form": "scatter",
        "n": 5,
        "spread": 0.8
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "random.fizz",
        "v": 0.5,
        "p": 1.9
      },
      {
        "t": 4,
        "id": "random.anvil_land",
        "v": 0.6,
        "p": 2.0
      }
    ]
  },
  {
    "id": "jet_gatling",
    "form": "gear2",
    "name": "gla.tech.jet_gatling",
    "shape": "line",
    "cost": 21,
    "cd": 76,
    "windup": 4,
    "active": 26,
    "recover": 10,
    "reach": 7.5,
    "radius": 1.2,
    "damage": 2.9,
    "hits": 18,
    "gap": 1,
    "kbH": 0.18,
    "kbV": 0.03,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.jet_gatling",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:steam_wisp",
        "form": "ring",
        "n": 8,
        "r": 0.5
      },
      {
        "t": 4,
        "layer": 2,
        "fx": "gla:jet_blur",
        "form": "scatter",
        "n": 12,
        "spread": 1.0
      },
      {
        "t": 9,
        "layer": 2,
        "fx": "gla:jet_blur",
        "form": "scatter",
        "n": 12,
        "spread": 1.1
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:jet_blur",
        "form": "scatter",
        "n": 12,
        "spread": 1.2
      },
      {
        "t": 19,
        "layer": 2,
        "fx": "gla:jet_blur",
        "form": "scatter",
        "n": 12,
        "spread": 1.1
      },
      {
        "t": 30,
        "layer": 4,
        "fx": "gla:shock_fan",
        "form": "fan",
        "n": 10,
        "r": 2.0,
        "sweep": 90
      },
      {
        "t": 34,
        "layer": 5,
        "fx": "gla:steam_wisp",
        "form": "scatter",
        "n": 8,
        "spread": 1.4
      }
    ],
    "sfx": [
      {
        "t": 4,
        "id": "random.fizz",
        "v": 0.45,
        "p": 2.0
      },
      {
        "t": 12,
        "id": "random.fizz",
        "v": 0.45,
        "p": 2.0
      },
      {
        "t": 20,
        "id": "random.fizz",
        "v": 0.45,
        "p": 2.0
      }
    ]
  },
  {
    "id": "red_hawk",
    "form": "gear2",
    "name": "gla.tech.red_hawk",
    "shape": "line",
    "cost": 14,
    "cd": 58,
    "windup": 8,
    "active": 6,
    "recover": 12,
    "reach": 10.0,
    "radius": 1.05,
    "damage": 14.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.5,
    "kbV": 0.3,
    "terrain": false,
    "fire": 70,
    "anim": "animation.gla.tech.red_hawk",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:ignite_coil",
        "form": "spiral",
        "n": 12,
        "r": 0.6,
        "d": 1.2
      },
      {
        "t": 5,
        "layer": 1,
        "fx": "gla:ignite_coil",
        "form": "spiral",
        "n": 10,
        "r": 0.45,
        "d": 0.9
      },
      {
        "t": 8,
        "layer": 2,
        "fx": "gla:flame_trail",
        "form": "line",
        "n": 12,
        "d": 10.0
      },
      {
        "t": 11,
        "layer": 3,
        "fx": "gla:flame_burst",
        "form": "point",
        "at": "target"
      },
      {
        "t": 11,
        "layer": 4,
        "fx": "gla:ember_fan",
        "form": "fan",
        "n": 12,
        "r": 2.2,
        "sweep": 120,
        "at": "target"
      },
      {
        "t": 18,
        "layer": 5,
        "fx": "gla:ember_drift",
        "form": "scatter",
        "n": 6,
        "spread": 1.1
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "fire.ignite",
        "v": 0.6,
        "p": 1.1
      },
      {
        "t": 11,
        "id": "random.explode",
        "v": 0.7,
        "p": 1.35
      }
    ]
  },
  {
    "id": "high_dodge",
    "form": "gear2",
    "name": "gla.tech.high_dodge",
    "shape": "self",
    "cost": 5,
    "cd": 38,
    "windup": 1,
    "active": 6,
    "recover": 4,
    "reach": 0.0,
    "radius": 1.0,
    "damage": 0.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.0,
    "kbV": 0.0,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.high_dodge",
    "launch": [
      1.9,
      0.16
    ],
    "buffs": [
      [
        "speed",
        2,
        40
      ],
      [
        "resistance",
        1,
        30
      ]
    ],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:steam_wisp",
        "form": "ring",
        "n": 6,
        "r": 0.5
      },
      {
        "t": 1,
        "layer": 2,
        "fx": "gla:after_image",
        "form": "tail",
        "n": 8,
        "d": 3.2
      },
      {
        "t": 4,
        "layer": 2,
        "fx": "gla:after_image",
        "form": "tail",
        "n": 6,
        "d": 2.6
      },
      {
        "t": 9,
        "layer": 5,
        "fx": "gla:steam_wisp",
        "form": "scatter",
        "n": 4,
        "spread": 0.8
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "random.fizz",
        "v": 0.45,
        "p": 2.0
      }
    ]
  },
  {
    "id": "gigant_pistol",
    "form": "gear3",
    "name": "gla.tech.gigant_pistol",
    "shape": "line",
    "cost": 18,
    "cd": 68,
    "windup": 14,
    "active": 8,
    "recover": 18,
    "reach": 14.0,
    "radius": 2.0,
    "damage": 18.0,
    "hits": 1,
    "gap": 0,
    "kbH": 2.2,
    "kbV": 0.45,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.gigant_pistol",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 10,
        "r": 0.8
      },
      {
        "t": 7,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 12,
        "r": 1.2
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:heavy_trail",
        "form": "line",
        "n": 12,
        "d": 14.0
      },
      {
        "t": 18,
        "layer": 3,
        "fx": "gla:impact_core_big",
        "form": "point",
        "at": "target"
      },
      {
        "t": 18,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 14,
        "r": 2.6,
        "at": "target"
      },
      {
        "t": 26,
        "layer": 5,
        "fx": "gla:deflate_puff",
        "form": "scatter",
        "n": 8,
        "spread": 1.3
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.8,
        "p": 0.65
      },
      {
        "t": 18,
        "id": "random.explode",
        "v": 0.9,
        "p": 1.0
      }
    ]
  },
  {
    "id": "gigant_axe",
    "form": "gear3",
    "name": "gla.tech.gigant_axe",
    "shape": "slam",
    "cost": 22,
    "cd": 88,
    "windup": 18,
    "active": 8,
    "recover": 22,
    "reach": 5.0,
    "radius": 3.4,
    "damage": 22.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.3,
    "kbV": 0.95,
    "terrain": true,
    "fire": 0,
    "anim": "animation.gla.tech.gigant_axe",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 10,
        "r": 0.9
      },
      {
        "t": 9,
        "layer": 1,
        "fx": "gla:lift_dust",
        "form": "ring",
        "n": 10,
        "r": 1.8,
        "at": "feet"
      },
      {
        "t": 18,
        "layer": 2,
        "fx": "gla:heavy_arc",
        "form": "arc",
        "n": 12,
        "r": 3.2,
        "sweep": 150,
        "tilt": 1.2
      },
      {
        "t": 22,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "point",
        "at": "ground"
      },
      {
        "t": 22,
        "layer": 4,
        "fx": "gla:ground_crack",
        "form": "ring",
        "n": 16,
        "r": 3.4,
        "at": "ground"
      },
      {
        "t": 24,
        "layer": 4,
        "fx": "gla:debris",
        "form": "scatter",
        "n": 10,
        "spread": 2.4,
        "at": "ground"
      },
      {
        "t": 34,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 8,
        "spread": 2.6,
        "at": "ground"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.8,
        "p": 0.6
      },
      {
        "t": 22,
        "id": "random.explode",
        "v": 1.0,
        "p": 0.75
      }
    ]
  },
  {
    "id": "gigant_bazooka",
    "form": "gear3",
    "name": "gla.tech.gigant_bazooka",
    "shape": "cone",
    "cost": 26,
    "cd": 96,
    "windup": 16,
    "active": 8,
    "recover": 20,
    "reach": 9.0,
    "radius": 3.3,
    "damage": 24.0,
    "hits": 1,
    "gap": 0,
    "kbH": 3.0,
    "kbV": 0.7,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.gigant_bazooka",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 12,
        "r": 1.0
      },
      {
        "t": 8,
        "layer": 1,
        "fx": "gla:charge_draw",
        "form": "ring",
        "n": 10,
        "r": 1.5
      },
      {
        "t": 16,
        "layer": 2,
        "fx": "gla:heavy_push",
        "form": "cone",
        "n": 16,
        "r": 3.3,
        "d": 9.0
      },
      {
        "t": 20,
        "layer": 3,
        "fx": "gla:impact_core_big",
        "form": "point",
        "at": "target"
      },
      {
        "t": 20,
        "layer": 4,
        "fx": "gla:shock_fan",
        "form": "fan",
        "n": 16,
        "r": 3.6,
        "sweep": 120
      },
      {
        "t": 30,
        "layer": 5,
        "fx": "gla:deflate_puff",
        "form": "scatter",
        "n": 10,
        "spread": 1.6
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.9,
        "p": 0.6
      },
      {
        "t": 20,
        "id": "random.explode",
        "v": 1.0,
        "p": 0.85
      }
    ]
  },
  {
    "id": "elephant_gun",
    "form": "gear3",
    "name": "gla.tech.elephant_gun",
    "shape": "line",
    "cost": 24,
    "cd": 92,
    "windup": 16,
    "active": 8,
    "recover": 20,
    "reach": 12.0,
    "radius": 2.6,
    "damage": 26.0,
    "hits": 1,
    "gap": 0,
    "kbH": 2.6,
    "kbV": 0.5,
    "terrain": true,
    "fire": 0,
    "anim": "animation.gla.tech.elephant_gun",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 14,
        "r": 1.1
      },
      {
        "t": 8,
        "layer": 1,
        "fx": "gla:inflate_puff",
        "form": "ring",
        "n": 14,
        "r": 1.6
      },
      {
        "t": 16,
        "layer": 2,
        "fx": "gla:heavy_trail",
        "form": "line",
        "n": 14,
        "d": 12.0
      },
      {
        "t": 20,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 20,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 16,
        "r": 3.0,
        "at": "target"
      },
      {
        "t": 32,
        "layer": 5,
        "fx": "gla:deflate_puff",
        "form": "scatter",
        "n": 10,
        "spread": 1.8
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 1.0,
        "p": 0.55
      },
      {
        "t": 20,
        "id": "random.explode",
        "v": 1.0,
        "p": 0.7
      }
    ]
  },
  {
    "id": "kong_gun",
    "form": "gear4_bound",
    "name": "gla.tech.kong_gun",
    "shape": "line",
    "cost": 22,
    "cd": 78,
    "windup": 12,
    "active": 6,
    "recover": 16,
    "reach": 13.0,
    "radius": 2.2,
    "damage": 24.0,
    "hits": 1,
    "gap": 0,
    "kbH": 3.2,
    "kbV": 0.6,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.kong_gun",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 10,
        "r": 0.8
      },
      {
        "t": 5,
        "layer": 1,
        "fx": "gla:compress",
        "form": "ring",
        "n": 12,
        "r": 0.55
      },
      {
        "t": 12,
        "layer": 2,
        "fx": "gla:haki_trail",
        "form": "line",
        "n": 12,
        "d": 13.0
      },
      {
        "t": 15,
        "layer": 3,
        "fx": "gla:impact_core_big",
        "form": "point",
        "at": "target"
      },
      {
        "t": 15,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 14,
        "r": 2.8,
        "at": "target"
      },
      {
        "t": 22,
        "layer": 5,
        "fx": "gla:bounce_puff",
        "form": "scatter",
        "n": 8,
        "spread": 1.2
      }
    ],
    "sfx": [
      {
        "t": 5,
        "id": "mob.slime.big",
        "v": 0.8,
        "p": 0.8
      },
      {
        "t": 15,
        "id": "random.explode",
        "v": 0.95,
        "p": 0.95
      }
    ]
  },
  {
    "id": "rhino_schneider",
    "form": "gear4_bound",
    "name": "gla.tech.rhino_schneider",
    "shape": "dash",
    "cost": 20,
    "cd": 72,
    "windup": 10,
    "active": 10,
    "recover": 14,
    "reach": 10.0,
    "radius": 1.8,
    "damage": 20.0,
    "hits": 1,
    "gap": 0,
    "kbH": 2.4,
    "kbV": 0.8,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.rhino_schneider",
    "launch": [
      2.1,
      0.5
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:compress",
        "form": "ring",
        "n": 10,
        "r": 0.7,
        "at": "feet"
      },
      {
        "t": 10,
        "layer": 2,
        "fx": "gla:haki_trail",
        "form": "tail",
        "n": 12,
        "d": 4.0
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:bounce_puff",
        "form": "scatter",
        "n": 8,
        "spread": 1.0
      },
      {
        "t": 18,
        "layer": 3,
        "fx": "gla:impact_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 18,
        "layer": 4,
        "fx": "gla:shock_fan",
        "form": "fan",
        "n": 12,
        "r": 2.2,
        "sweep": 100
      },
      {
        "t": 26,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 6,
        "spread": 1.4,
        "at": "feet"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.7,
        "p": 1.0
      },
      {
        "t": 18,
        "id": "random.anvil_land",
        "v": 0.8,
        "p": 0.9
      }
    ]
  },
  {
    "id": "king_kong_gun",
    "form": "gear4_bound",
    "name": "gla.tech.king_kong_gun",
    "shape": "line",
    "cost": 40,
    "cd": 200,
    "windup": 26,
    "active": 10,
    "recover": 30,
    "reach": 18.0,
    "radius": 3.6,
    "damage": 42.0,
    "hits": 1,
    "gap": 0,
    "kbH": 4.2,
    "kbV": 0.9,
    "terrain": true,
    "fire": 0,
    "anim": "animation.gla.tech.king_kong_gun",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 12,
        "r": 1.0
      },
      {
        "t": 8,
        "layer": 1,
        "fx": "gla:compress",
        "form": "spiral",
        "n": 16,
        "r": 1.4,
        "d": 1.8
      },
      {
        "t": 16,
        "layer": 1,
        "fx": "gla:compress",
        "form": "spiral",
        "n": 16,
        "r": 0.9,
        "d": 1.2
      },
      {
        "t": 26,
        "layer": 2,
        "fx": "gla:haki_trail",
        "form": "line",
        "n": 16,
        "d": 18.0
      },
      {
        "t": 26,
        "layer": 2,
        "fx": "gla:speed_line",
        "form": "line",
        "n": 12,
        "d": 18.0
      },
      {
        "t": 31,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 31,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 18,
        "r": 4.0,
        "at": "target"
      },
      {
        "t": 33,
        "layer": 4,
        "fx": "gla:debris",
        "form": "scatter",
        "n": 12,
        "spread": 3.0,
        "at": "target"
      },
      {
        "t": 46,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 10,
        "spread": 2.6,
        "at": "ground"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 1.0,
        "p": 0.55
      },
      {
        "t": 16,
        "id": "mob.slime.big",
        "v": 1.0,
        "p": 0.5
      },
      {
        "t": 31,
        "id": "random.explode",
        "v": 1.2,
        "p": 0.6
      }
    ]
  },
  {
    "id": "jet_culverin",
    "form": "gear4_snake",
    "name": "gla.tech.jet_culverin",
    "shape": "arc",
    "cost": 16,
    "cd": 38,
    "windup": 5,
    "active": 8,
    "recover": 10,
    "reach": 14.0,
    "radius": 1.4,
    "damage": 15.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.2,
    "kbV": 0.25,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.jet_culverin",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 6,
        "r": 0.5
      },
      {
        "t": 5,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 16,
        "r": 1.6,
        "d": 14.0
      },
      {
        "t": 9,
        "layer": 3,
        "fx": "gla:impact_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 9,
        "layer": 4,
        "fx": "gla:impact_ring",
        "form": "ring",
        "n": 8,
        "r": 1.4,
        "at": "target"
      },
      {
        "t": 15,
        "layer": 5,
        "fx": "gla:haki_wisp",
        "form": "scatter",
        "n": 5,
        "spread": 0.9
      }
    ],
    "sfx": [
      {
        "t": 5,
        "id": "random.fizz",
        "v": 0.5,
        "p": 1.6
      },
      {
        "t": 9,
        "id": "random.anvil_land",
        "v": 0.6,
        "p": 1.7
      }
    ]
  },
  {
    "id": "black_mamba",
    "form": "gear4_snake",
    "name": "gla.tech.black_mamba",
    "shape": "arc",
    "cost": 30,
    "cd": 118,
    "windup": 8,
    "active": 30,
    "recover": 16,
    "reach": 12.0,
    "radius": 1.6,
    "damage": 6.0,
    "hits": 8,
    "gap": 4,
    "kbH": 0.45,
    "kbV": 0.1,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.black_mamba",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 8,
        "r": 0.6
      },
      {
        "t": 8,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 14,
        "r": 1.8,
        "d": 12.0
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 14,
        "r": 2.2,
        "d": 12.0,
        "tilt": 0.8
      },
      {
        "t": 20,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 14,
        "r": 1.4,
        "d": 12.0,
        "tilt": -0.8
      },
      {
        "t": 26,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 14,
        "r": 2.0,
        "d": 12.0
      },
      {
        "t": 38,
        "layer": 4,
        "fx": "gla:shock_fan",
        "form": "fan",
        "n": 12,
        "r": 2.4,
        "sweep": 140
      },
      {
        "t": 44,
        "layer": 5,
        "fx": "gla:haki_wisp",
        "form": "scatter",
        "n": 8,
        "spread": 1.3
      }
    ],
    "sfx": [
      {
        "t": 8,
        "id": "random.fizz",
        "v": 0.45,
        "p": 1.5
      },
      {
        "t": 18,
        "id": "random.fizz",
        "v": 0.45,
        "p": 1.7
      },
      {
        "t": 28,
        "id": "random.fizz",
        "v": 0.45,
        "p": 1.9
      }
    ]
  },
  {
    "id": "king_cobra",
    "form": "gear4_snake",
    "name": "gla.tech.king_cobra",
    "shape": "arc",
    "cost": 38,
    "cd": 176,
    "windup": 22,
    "active": 10,
    "recover": 26,
    "reach": 20.0,
    "radius": 3.0,
    "damage": 40.0,
    "hits": 1,
    "gap": 0,
    "kbH": 3.6,
    "kbV": 0.5,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.king_cobra",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 12,
        "r": 1.0
      },
      {
        "t": 10,
        "layer": 1,
        "fx": "gla:compress",
        "form": "spiral",
        "n": 14,
        "r": 1.3,
        "d": 1.6
      },
      {
        "t": 22,
        "layer": 2,
        "fx": "gla:snake_trail",
        "form": "spiral",
        "n": 20,
        "r": 2.6,
        "d": 20.0
      },
      {
        "t": 22,
        "layer": 2,
        "fx": "gla:haki_trail",
        "form": "line",
        "n": 14,
        "d": 20.0
      },
      {
        "t": 27,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 27,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 16,
        "r": 3.4,
        "at": "target"
      },
      {
        "t": 40,
        "layer": 5,
        "fx": "gla:haki_wisp",
        "form": "scatter",
        "n": 10,
        "spread": 1.6
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.9,
        "p": 0.7
      },
      {
        "t": 27,
        "id": "random.explode",
        "v": 1.1,
        "p": 0.75
      }
    ]
  },
  {
    "id": "giant",
    "form": "gear5",
    "name": "gla.tech.giant",
    "shape": "self",
    "cost": 28,
    "cd": 280,
    "windup": 20,
    "active": 400,
    "recover": 10,
    "reach": 0.0,
    "radius": 1.0,
    "damage": 0.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.0,
    "kbV": 0.0,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.giant",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [
      [
        "strength",
        2,
        400
      ],
      [
        "resistance",
        2,
        400
      ],
      [
        "health_boost",
        2,
        400
      ],
      [
        "slowness",
        0,
        60
      ]
    ],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:nika_pulse",
        "form": "ring",
        "n": 12,
        "r": 1.0
      },
      {
        "t": 10,
        "layer": 2,
        "fx": "gla:cloud_curl",
        "form": "spiral",
        "n": 16,
        "r": 1.8,
        "d": 2.4
      },
      {
        "t": 20,
        "layer": 3,
        "fx": "gla:nika_flash",
        "form": "point",
        "at": "chest"
      },
      {
        "t": 20,
        "layer": 4,
        "fx": "gla:wind_ring",
        "form": "ring",
        "n": 18,
        "r": 3.0,
        "at": "feet"
      },
      {
        "t": 34,
        "layer": 5,
        "fx": "gla:cloud_drift",
        "form": "scatter",
        "n": 8,
        "spread": 2.0
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.8,
        "p": 0.5
      },
      {
        "t": 20,
        "id": "random.levelup",
        "v": 0.8,
        "p": 0.7
      }
    ]
  },
  {
    "id": "lightning_throw",
    "form": "gear5",
    "name": "gla.tech.lightning_throw",
    "shape": "projectile",
    "cost": 24,
    "cd": 88,
    "windup": 12,
    "active": 20,
    "recover": 14,
    "reach": 24.0,
    "radius": 2.4,
    "damage": 22.0,
    "hits": 1,
    "gap": 0,
    "kbH": 1.6,
    "kbV": 0.55,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.lightning_throw",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:bolt_gather",
        "form": "spiral",
        "n": 14,
        "r": 0.9,
        "d": 1.4
      },
      {
        "t": 12,
        "layer": 2,
        "fx": "gla:bolt_trail",
        "form": "line",
        "n": 16,
        "d": 24.0
      },
      {
        "t": 12,
        "layer": 2,
        "fx": "gla:bolt_fringe",
        "form": "scatter",
        "n": 8,
        "spread": 1.0
      },
      {
        "t": 24,
        "layer": 3,
        "fx": "gla:bolt_strike",
        "form": "pillar",
        "n": 10,
        "r": 0.6,
        "d": 4.0,
        "at": "target"
      },
      {
        "t": 24,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 12,
        "r": 2.6,
        "at": "target"
      },
      {
        "t": 34,
        "layer": 5,
        "fx": "gla:bolt_fringe",
        "form": "scatter",
        "n": 6,
        "spread": 1.4,
        "at": "target"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "ambient.weather.thunder",
        "v": 0.35,
        "p": 1.8
      },
      {
        "t": 24,
        "id": "random.explode",
        "v": 0.85,
        "p": 1.5
      }
    ]
  },
  {
    "id": "rubber_ground",
    "form": "gear5",
    "name": "gla.tech.rubber_ground",
    "shape": "zone",
    "cost": 26,
    "cd": 140,
    "windup": 14,
    "active": 200,
    "recover": 12,
    "reach": 0.0,
    "radius": 6.0,
    "damage": 2.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.6,
    "kbV": 1.3,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.rubber_ground",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:nika_pulse",
        "form": "ring",
        "n": 10,
        "r": 1.2,
        "at": "feet"
      },
      {
        "t": 14,
        "layer": 2,
        "fx": "gla:rubber_wave",
        "form": "ring",
        "n": 20,
        "r": 6.0,
        "at": "feet"
      },
      {
        "t": 14,
        "layer": 3,
        "fx": "gla:rubber_pop",
        "form": "scatter",
        "n": 10,
        "spread": 3.0,
        "at": "feet"
      },
      {
        "t": 60,
        "layer": 4,
        "fx": "gla:rubber_wave",
        "form": "ring",
        "n": 14,
        "r": 6.0,
        "at": "feet"
      },
      {
        "t": 120,
        "layer": 4,
        "fx": "gla:rubber_wave",
        "form": "ring",
        "n": 14,
        "r": 6.0,
        "at": "feet"
      },
      {
        "t": 210,
        "layer": 5,
        "fx": "gla:cloud_drift",
        "form": "scatter",
        "n": 6,
        "spread": 2.4,
        "at": "feet"
      }
    ],
    "sfx": [
      {
        "t": 14,
        "id": "mob.slime.big",
        "v": 0.8,
        "p": 1.2
      }
    ]
  },
  {
    "id": "under_strike",
    "form": "gear5",
    "name": "gla.tech.under_strike",
    "shape": "delayed",
    "cost": 22,
    "cd": 98,
    "windup": 16,
    "active": 30,
    "recover": 14,
    "reach": 12.0,
    "radius": 2.2,
    "damage": 20.0,
    "hits": 1,
    "gap": 0,
    "kbH": 0.8,
    "kbV": 1.6,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.under_strike",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:nika_pulse",
        "form": "ring",
        "n": 8,
        "r": 0.8,
        "at": "feet"
      },
      {
        "t": 16,
        "layer": 2,
        "fx": "gla:ground_run",
        "form": "line",
        "n": 14,
        "d": 12.0,
        "at": "ground"
      },
      {
        "t": 28,
        "layer": 1,
        "fx": "gla:ground_bulge",
        "form": "ring",
        "n": 10,
        "r": 2.0,
        "at": "target"
      },
      {
        "t": 36,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "pillar",
        "n": 8,
        "r": 0.8,
        "d": 3.0,
        "at": "target"
      },
      {
        "t": 36,
        "layer": 4,
        "fx": "gla:debris",
        "form": "scatter",
        "n": 10,
        "spread": 2.2,
        "at": "target"
      },
      {
        "t": 48,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 6,
        "spread": 2.0,
        "at": "target"
      }
    ],
    "sfx": [
      {
        "t": 16,
        "id": "mob.slime.small",
        "v": 0.6,
        "p": 0.8
      },
      {
        "t": 36,
        "id": "random.explode",
        "v": 0.9,
        "p": 0.9
      }
    ]
  },
  {
    "id": "white_star",
    "form": "gear5",
    "name": "gla.tech.white_star",
    "shape": "sphere",
    "cost": 34,
    "cd": 156,
    "windup": 18,
    "active": 10,
    "recover": 20,
    "reach": 0.0,
    "radius": 7.0,
    "damage": 26.0,
    "hits": 1,
    "gap": 0,
    "kbH": 3.0,
    "kbV": 0.6,
    "terrain": false,
    "fire": 0,
    "anim": "animation.gla.tech.white_star",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:nika_pulse",
        "form": "ring",
        "n": 12,
        "r": 1.2
      },
      {
        "t": 9,
        "layer": 1,
        "fx": "gla:cloud_curl",
        "form": "spiral",
        "n": 16,
        "r": 1.6,
        "d": 2.0
      },
      {
        "t": 18,
        "layer": 3,
        "fx": "gla:nika_flash",
        "form": "point",
        "at": "chest"
      },
      {
        "t": 18,
        "layer": 4,
        "fx": "gla:wind_ring",
        "form": "ring",
        "n": 24,
        "r": 7.0,
        "at": "feet"
      },
      {
        "t": 20,
        "layer": 4,
        "fx": "gla:star_shard",
        "form": "scatter",
        "n": 14,
        "spread": 3.4
      },
      {
        "t": 32,
        "layer": 5,
        "fx": "gla:cloud_drift",
        "form": "scatter",
        "n": 10,
        "spread": 3.0
      }
    ],
    "sfx": [
      {
        "t": 18,
        "id": "random.explode",
        "v": 1.0,
        "p": 1.2
      }
    ]
  },
  {
    "id": "bajrang_gun",
    "form": "gear5",
    "name": "gla.tech.bajrang_gun",
    "shape": "line",
    "cost": 58,
    "cd": 560,
    "windup": 40,
    "active": 14,
    "recover": 40,
    "reach": 26.0,
    "radius": 6.0,
    "damage": 70.0,
    "hits": 1,
    "gap": 0,
    "kbH": 5.0,
    "kbV": 1.0,
    "terrain": true,
    "fire": 0,
    "anim": "animation.gla.tech.bajrang_gun",
    "launch": [
      0.0,
      0.0
    ],
    "buffs": [],
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:nika_pulse",
        "form": "ring",
        "n": 14,
        "r": 1.4
      },
      {
        "t": 10,
        "layer": 1,
        "fx": "gla:cloud_curl",
        "form": "spiral",
        "n": 20,
        "r": 2.4,
        "d": 3.0
      },
      {
        "t": 22,
        "layer": 1,
        "fx": "gla:haki_coat",
        "form": "ring",
        "n": 16,
        "r": 2.0
      },
      {
        "t": 32,
        "layer": 1,
        "fx": "gla:compress",
        "form": "spiral",
        "n": 18,
        "r": 1.6,
        "d": 2.0
      },
      {
        "t": 40,
        "layer": 2,
        "fx": "gla:giant_fist",
        "form": "line",
        "n": 20,
        "d": 26.0
      },
      {
        "t": 40,
        "layer": 2,
        "fx": "gla:haki_trail",
        "form": "line",
        "n": 16,
        "d": 26.0
      },
      {
        "t": 47,
        "layer": 3,
        "fx": "gla:slam_core",
        "form": "point",
        "at": "target"
      },
      {
        "t": 47,
        "layer": 4,
        "fx": "gla:shock_ring_big",
        "form": "ring",
        "n": 24,
        "r": 6.0,
        "at": "target"
      },
      {
        "t": 49,
        "layer": 4,
        "fx": "gla:debris",
        "form": "scatter",
        "n": 16,
        "spread": 4.0,
        "at": "target"
      },
      {
        "t": 64,
        "layer": 5,
        "fx": "gla:dust_low",
        "form": "scatter",
        "n": 12,
        "spread": 3.4,
        "at": "ground"
      },
      {
        "t": 70,
        "layer": 5,
        "fx": "gla:cloud_drift",
        "form": "scatter",
        "n": 10,
        "spread": 3.0
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 1.0,
        "p": 0.45
      },
      {
        "t": 22,
        "id": "ambient.weather.thunder",
        "v": 0.5,
        "p": 0.8
      },
      {
        "t": 47,
        "id": "random.explode",
        "v": 1.4,
        "p": 0.5
      }
    ]
  }
];
export const TECHS_BY_FORM = {
  "normal": [
    "pistol",
    "bazooka",
    "gatling",
    "rocket"
  ],
  "gear2": [
    "jet_pistol",
    "jet_gatling",
    "red_hawk",
    "high_dodge"
  ],
  "gear3": [
    "gigant_pistol",
    "gigant_axe",
    "gigant_bazooka",
    "elephant_gun"
  ],
  "gear4_bound": [
    "kong_gun",
    "rhino_schneider",
    "king_kong_gun"
  ],
  "gear4_snake": [
    "jet_culverin",
    "black_mamba",
    "king_cobra"
  ],
  "gear5": [
    "giant",
    "lightning_throw",
    "rubber_ground",
    "under_strike",
    "white_star",
    "bajrang_gun"
  ]
};
export const SHOWPIECE = [
  {
    "t": 0,
    "until": 12,
    "pose": "curl",
    "stages": [
      {
        "t": 0,
        "layer": 1,
        "fx": "gla:heart_thud",
        "form": "ring",
        "n": 6,
        "r": 0.7,
        "at": "chest"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.wither.spawn",
        "v": 0.45,
        "p": 0.42
      }
    ],
    "lift": false,
    "swap": false,
    "quiet": true
  },
  {
    "t": 12,
    "until": 24,
    "pose": "lift",
    "stages": [
      {
        "t": 0,
        "layer": 2,
        "fx": "gla:cloud_curl",
        "form": "spiral",
        "n": 10,
        "r": 0.9,
        "d": 1.2
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.small",
        "v": 0.4,
        "p": 0.6
      }
    ],
    "lift": false,
    "swap": false,
    "quiet": false
  },
  {
    "t": 24,
    "until": 36,
    "pose": "swap",
    "stages": [
      {
        "t": 0,
        "layer": 3,
        "fx": "gla:nika_rim",
        "form": "ring",
        "n": 12,
        "r": 1.1,
        "at": "chest"
      },
      {
        "t": 4,
        "layer": 2,
        "fx": "gla:cloud_curl",
        "form": "spiral",
        "n": 12,
        "r": 1.4,
        "d": 1.6
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "random.levelup",
        "v": 0.7,
        "p": 0.8
      }
    ],
    "lift": false,
    "swap": true,
    "quiet": false
  },
  {
    "t": 36,
    "until": 48,
    "pose": "float",
    "stages": [
      {
        "t": 0,
        "layer": 4,
        "fx": "gla:wind_ring",
        "form": "ring",
        "n": 16,
        "r": 2.4,
        "at": "feet"
      }
    ],
    "sfx": [
      {
        "t": 0,
        "id": "mob.slime.big",
        "v": 0.5,
        "p": 0.9
      }
    ],
    "lift": true,
    "swap": false,
    "quiet": false
  },
  {
    "t": 48,
    "until": 76,
    "pose": "laugh",
    "stages": [
      {
        "t": 0,
        "layer": 2,
        "fx": "gla:cloud_orbit",
        "form": "ring",
        "n": 10,
        "r": 1.8
      },
      {
        "t": 12,
        "layer": 2,
        "fx": "gla:cloud_orbit",
        "form": "ring",
        "n": 10,
        "r": 2.0
      },
      {
        "t": 22,
        "layer": 2,
        "fx": "gla:cloud_orbit",
        "form": "ring",
        "n": 10,
        "r": 1.7
      }
    ],
    "sfx": [
      {
        "t": 2,
        "id": "mob.slime.small",
        "v": 0.4,
        "p": 1.3
      },
      {
        "t": 12,
        "id": "mob.slime.small",
        "v": 0.4,
        "p": 1.5
      },
      {
        "t": 21,
        "id": "mob.slime.small",
        "v": 0.4,
        "p": 1.2
      }
    ],
    "lift": true,
    "swap": false,
    "quiet": false
  },
  {
    "t": 76,
    "until": 90,
    "pose": "settle",
    "stages": [
      {
        "t": 0,
        "layer": 5,
        "fx": "gla:wind_ring",
        "form": "ring",
        "n": 10,
        "r": 1.4,
        "at": "feet"
      },
      {
        "t": 8,
        "layer": 5,
        "fx": "gla:cloud_drift",
        "form": "scatter",
        "n": 5,
        "spread": 1.6
      }
    ],
    "sfx": [
      {
        "t": 6,
        "id": "random.pop",
        "v": 0.4,
        "p": 0.8
      }
    ],
    "lift": false,
    "swap": false,
    "quiet": false
  }
];
export const SHOWPIECE_TICKS = 90;
export const SHOWPIECE_SHORT_TICKS = 34;
export const SHOWPIECE_LIFT = 0.62;
export const TRAINING = {
  "size": 128,
  "zones": [
    {
      "key": "plaza",
      "ja": "訓練広場",
      "en": "Training Plaza",
      "purpose": "標準距離で技を確認する",
      "props": "距離目盛り・単体/群れの標的・壁越し判定用の遮蔽物"
    },
    {
      "key": "studio",
      "ja": "撮影エリア",
      "en": "Capture Area",
      "purpose": "形態とアニメの比較",
      "props": "昼夜を揃えた背景・正面と斜めの基準位置・全身が入る床目印"
    },
    {
      "key": "load",
      "ja": "負荷テスト区画",
      "en": "Load Test Yard",
      "purpose": "同時戦闘時の重さを測る",
      "props": "人数と敵数を固定できる配置（標的20体ぶん・プレイヤー4人ぶんの目印）"
    },
    {
      "key": "course",
      "ja": "移動コース",
      "en": "Movement Course",
      "purpose": "見た目の追従を確認",
      "props": "段差・狭い入口・坂・ジャンプ・水際"
    }
  ],
  "markers": [
    5,
    10,
    15,
    20,
    25
  ]
};

export const ITEM = {
  fruit: "gla:devil_fruit",
  hat: "gla:straw_hat",
  wrap: "gla:fist_wrap",
  pose: "gla:log_pose",
};

export const FORM_ITEMS = [
  "gla:form_normal",
  "gla:form_gear2",
  "gla:form_gear3",
  "gla:form_gear4_bound",
  "gla:form_gear4_snake",
  "gla:form_gear5"
];

export const MOB = {
  "training_dummy": "gla:training_dummy",
  "training_swarm": "gla:training_swarm",
  "vfx_fist": "gla:vfx_fist",
  "thrown_bolt": "gla:thrown_bolt"
};

/** 形態キー -> 定義 */
export const FORM_BY_KEY = Object.fromEntries(FORMS.map((f) => [f.key, f]));
/** 技ID -> 定義 */
export const TECH_BY_ID = Object.fromEntries(TECHS.map((t) => [t.id, t]));
