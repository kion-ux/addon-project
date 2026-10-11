// ===========================================================================
//  進撃の巨人アドオン — 定数と調整値
//  実機で「飛びすぎる／足りない」などがあれば、まずここ（TUNE）だけを直す。
// ===========================================================================
export { BODY_META, TITAN_TYPES, SOLDIER_TYPES } from "./aot_meta.js";

export const ITEM = {
  blades: "aot:odm_blades",
  spear: "aot:thunder_spear",
  gas: "aot:gas_canister",
  spare: "aot:spare_blades",
  steel: "aot:hardened_steel",
  journal: "aot:survey_journal",
  flare: "aot:flare_gun",
  gear: "aot:odm_gear",
  jacket: "aot:survey_jacket",
  boots: "aot:survey_boots",
};

export const PROP = {
  gas: "aot:gas",               // 0..GAS_MAX
  kills: "aot:kills",           // 討伐数
  kit: "aot:kit_taken",         // 装備の支給を受けたか
  hud: "aot:hud_off",           // HUD を消しているか
  flare: "aot:flare_color",     // 信煙弾の色
  welcomed: "aot:welcomed",
  // world
  spawns: "aot:no_natural_titans",
  grab: "aot:no_grab",
};

export const GAS_MAX = 100;

export const TUNE = {
  anchorRange: 45,        // アンカーが届く距離 (m)
  reelAccel: 0.17,        // 巻き取りの加速 (m/tick²)
  reelLift: 0.07,         // 巻き取り中の重力の打ち消し
  maxSpeed: 1.75,         // 立体機動の最高速 (m/tick)
  arrive: 1.4,            // アンカーに着いたとみなす距離
  coastTicks: 26,         // 切り離した後、慣性で飛ぶ時間
  coastDrag: 0.975,       // その間の水平の減速（バニラの空気抵抗より弱い）
  boost: 1.05,            // ガス噴射の速さ
  boostCd: 10,
  spinCd: 30,
  spinRadius: 3.6,
  // ガスの消費
  gasAnchor: 1.0,
  gasReel: 0.12,          // tick ごと
  gasBoost: 6,
  gasSpin: 5,
  gasBrake: 1.5,
  // うなじ
  fastSpeed: 0.3,         // 討伐に必要な速さ（m/tick）
  recentWire: 25,         // ワイヤーを使ってから「勢いがある」とみなす tick
  passRadius: 1.7,        // 巻き取りでうなじの脇を抜けた時に自動で斬る距離（+ うなじ半径）
  shallow: 0.4,           // 浅い斬撃: 最大体力に対する割合
  ankleChance: 0.3,
  kneelTicks: 120,
  blindTicks: 120,
  // 巨人
  regenDelay: 60,         // 最後に斬られてから再生が始まるまで
  regenRate: 0.015,       // 10 tick ごとに最大体力のこの割合
  grabChance: 0.35,
  dyingTicks: 88,
};

/** 階級（討伐数）。 */
export const RANKS = [
  [0, "aot.rank.trainee"],
  [1, "aot.rank.recruit"],
  [5, "aot.rank.soldier"],
  [15, "aot.rank.elite"],
  [40, "aot.rank.squad_leader"],
  [100, "aot.rank.section_commander"],
  [250, "aot.rank.captain"],
];

export function rankOf(kills) {
  let key = RANKS[0][1];
  for (const [n, k] of RANKS) if (kills >= n) key = k;
  return key;
}

/** 調査兵団の腕前: うなじを削ぐ成功率・攻撃の間隔 (tick)・二連撃 */
export const SKILL = {
  "aot:levi_ackerman": { rate: 0.97, cd: 30, twin: true },
  "aot:mikasa_ackerman": { rate: 0.92, cd: 36, twin: true },
  "aot:eren_yeager": { rate: 0.62, cd: 50 },
  "aot:armin_arlert": { rate: 0.40, cd: 70 },
  "aot:hange_zoe": { rate: 0.68, cd: 54 },
  "aot:erwin_smith": { rate: 0.70, cd: 56, leader: true },
  "aot:jean_kirstein": { rate: 0.72, cd: 50 },
  "aot:sasha_blouse": { rate: 0.66, cd: 50 },
  "aot:connie_springer": { rate: 0.64, cd: 50 },
  "aot:survey_soldier": { rate: 0.50, cd: 64 },
};

export const FLARE_COLORS = [
  { key: "aot.flare.green", c: [0.25, 0.75, 0.32] },
  { key: "aot.flare.red", c: [0.85, 0.16, 0.14] },
  { key: "aot.flare.black", c: [0.10, 0.10, 0.11] },
  { key: "aot.flare.yellow", c: [0.92, 0.82, 0.22] },
];
