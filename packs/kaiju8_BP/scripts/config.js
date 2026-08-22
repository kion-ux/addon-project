// 怪獣8号 アドオン - 定数定義 / shared constants
export const NS = "kaiju8";

/** 要塞度 (fortitude) — 討伐庁の脅威評価。
 *  余獣は個別に測定されないので null（UI では "--"）。 */
export const FORTITUDE = {
  "kaiju8:parasite_kaiju": null,
  "kaiju8:yoju": null,
  "kaiju8:honju": 6.8,
  "kaiju8:kaiju_no8": 9.8,
  "kaiju8:kaiju_no9": 8.5,
  "kaiju8:kaiju_no10": 8.3,
};

/** 6.0以上=本獣級 / 8.0以上=大怪獣級 / 9.0以上=識別種 */
export const FORTITUDE_CLASS = [
  [9.0, "kaiju8.class.identified"],
  [8.0, "kaiju8.class.great"],
  [6.0, "kaiju8.class.honju"],
  [0.0, "kaiju8.class.yoju"],
];

/** Identified-kaiju class (識別怪獣) get the red threat colour. */
export const IDENTIFIED = new Set([
  "kaiju8:kaiju_no8",
  "kaiju8:kaiju_no9",
  "kaiju8:kaiju_no10",
]);

export const PROP = {
  power: "kaiju8:power",          // 怪獣8号の力を得たか
  form: "kaiju8:form",            // 変身中か
  energy: "kaiju8:energy",        // 怪獣化エネルギー 0-100
  release: "kaiju8:release",      // 解放戦力 % (1-100)
  kills: "kaiju8:kills",          // 討伐数
  storedArmor: "kaiju8:stored_armor",
  alerts: "kaiju8:alerts",        // world: 怪獣災害 on/off
};

export const TAG_NO8 = "kaiju8_no8";

export const TRANSFORM_ITEM = "kaiju8:no8_power";
export const FORM_ITEM = "kaiju8:no8_form";
export const PARASITE_ITEM = "kaiju8:parasite_kaiju";
export const DETECTOR_ITEM = "kaiju8:kaiju_detector";

/** 解放戦力の帯 (仕様書 §2)。数値のみで表示し、オーラは出さない。 */
export const RELEASE_BANDS = [
  [90, "§6"], [60, "§e"], [30, "§a"], [10, "§b"], [0, "§7"],
];

export const SUIT = [
  "kaiju8:combat_suit_helmet",
  "kaiju8:combat_suit_chestplate",
  "kaiju8:combat_suit_leggings",
  "kaiju8:combat_suit_boots",
];

/** 解放戦力 without the full combat suit is capped — the body cannot take it. */
export const RELEASE_CAP_NO_SUIT = 15;
export const RELEASE_SAFE = 30;

/** 階級 (rank) thresholds by 討伐数. */
export const RANKS = [
  [0, "kaiju8.rank.cadet"],
  [10, "kaiju8.rank.member"],
  [50, "kaiju8.rank.senior"],
  [150, "kaiju8.rank.vice_captain"],
  [400, "kaiju8.rank.captain"],
  [1000, "kaiju8.rank.director"],
];

export const ENERGY_MAX = 100;
export const ENERGY_DRAIN = 0.30;   // per second while transformed
export const ENERGY_REGEN = 0.55;   // per second while human
export const ENERGY_HIT_COST = 1.2; // per landed hit

/** Items that carry 技 — kept in sync with techniques.js. */
export const TECH_ITEMS = [
  "kaiju8:combat_knife",
  "kaiju8:df_rifle",
  "kaiju8:twin_sw2033",
  "kaiju8:axe_03ax",
  "kaiju8:cannon_t25",
  "kaiju8:gunblade_gs3305",
  "kaiju8:no8_power",
];
