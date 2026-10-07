// ===========================================================================
//  武器と技の定義
// ===========================================================================

export const NS = "hd";
export const GAUGE_MAX = 100;
export const PROP_GAUGE = "hd:gauge";

// 武器の重さ: 軽いほどダッシュ時の加速と空中機動の回数が増える
export const WEIGHT = {
  light: { sprint: 2, airJumps: 2, airDash: 2, dash: 2.9 },
  mid:   { sprint: 1, airJumps: 1, airDash: 1, dash: 2.6 },
  heavy: { sprint: 0, airJumps: 1, airDash: 1, dash: 2.2 },
};

/**
 * 各武器:
 *  color   発光色 (0..1)      deep  影の色
 *  hold    持っている間の全身姿勢（playanimation）
 *  combo   通常攻撃 1→2→3 段目の全身モーション
 *  moves   skill = 右クリック / dash = ダッシュ中に右クリック /
 *          air = 空中で右クリック / ult = スニーク＋右クリック（ゲージ 100%）
 *          cd は再使用までの tick
 */
export const WEAPONS = {
  "hd:greatsword": {
    key: "greatsword", name: "次元断剣 ディメンション・ブレイカー", short: "次元断剣",
    color: [0.27, 0.69, 1.0], deep: [0.07, 0.2, 0.55], tc: "§b",
    weight: "heavy", hold: "hold_2h", combo: ["combo1", "combo2", "combo3"],
    hitSound: "hd.hit_heavy", swing: "hd.swing_heavy", kanji: 0,
    moves: {
      skill: { name: "次元断", en: "DIMENSION CUT", cd: 110 },
      dash: { name: "流星突", en: "METEOR DRIVE", cd: 90 },
      air: { name: "天墜", en: "SKYFALL", cd: 100 },
      ult: { name: "終焉次元斬", en: "APOCALYPSE", cd: 200 },
    },
  },
  "hd:twinblades": {
    key: "twinblades", name: "疾風双刃 ゼファー＆ガスト", short: "疾風双刃",
    color: [0.25, 1.0, 0.63], deep: [0.04, 0.38, 0.25], tc: "§a",
    weight: "light", hold: "hold_dual", combo: ["combo1", "combo2", "rapid"],
    hitSound: "hd.hit_slash", swing: "hd.swing", kanji: 0,
    moves: {
      skill: { name: "疾風連刃", en: "GALE RUSH", cd: 90 },
      dash: { name: "旋風斬", en: "CYCLONE DANCE", cd: 90 },
      air: { name: "燕返し", en: "SWALLOW DIVE", cd: 80 },
      ult: { name: "千刃嵐舞", en: "TEMPEST", cd: 200 },
    },
  },
  "hd:greataxe": {
    key: "greataxe", name: "紅蓮戦斧 ヴォルカニクス", short: "紅蓮戦斧",
    color: [1.0, 0.34, 0.16], deep: [0.5, 0.05, 0.04], tc: "§c",
    weight: "heavy", hold: "hold_2h", combo: ["combo2", "combo1", "combo3"],
    hitSound: "hd.hit_heavy", swing: "hd.swing_heavy", kanji: 2,
    moves: {
      skill: { name: "爆炎断", en: "BURNING CREST", cd: 120 },
      dash: { name: "炎輪旋", en: "BLAZE WHEEL", cd: 110 },
      air: { name: "隕鉄落", en: "METEOR CRASH", cd: 100 },
      ult: { name: "紅蓮獄炎", en: "VOLCANIC END", cd: 200 },
    },
  },
  "hd:dagger": {
    key: "dagger", name: "影刃 ノクス", short: "影刃",
    color: [0.7, 0.36, 1.0], deep: [0.2, 0.06, 0.4], tc: "§d",
    weight: "light", hold: null, combo: ["stab", "combo2", "thrust"],
    hitSound: "hd.hit_slash", swing: "hd.swing", kanji: 3,
    moves: {
      skill: { name: "影縫い", en: "SHADOW STITCH", cd: 70 },
      dash: { name: "瞬影", en: "BLINK STRIKE", cd: 90 },
      air: { name: "影落とし", en: "NIGHTFALL", cd: 90 },
      ult: { name: "冥夜幻葬", en: "NOCTURNE", cd: 200 },
    },
  },
  "hd:bow": {
    key: "bow", name: "聖光弓 アストライア", short: "聖光弓",
    color: [1.0, 0.84, 0.36], deep: [0.59, 0.36, 0.04], tc: "§e",
    weight: "mid", hold: null, combo: ["thrust", "combo1", "combo2"],
    hitSound: "hd.hit_slash", swing: "hd.swing", kanji: 1, charge: true,
    moves: {
      skill: { name: "聖光矢", en: "HOLY ARROW", cd: 8 },
      dash: { name: "宙返り三連射", en: "BACKFLIP TRISHOT", cd: 90 },
      air: { name: "星雨", en: "STAR RAIN", cd: 120 },
      ult: { name: "天穹神弓", en: "JUDGEMENT", cd: 200 },
    },
  },
  "hd:shield": {
    key: "shield", name: "氷晶盾 グレイシャル・イージス", short: "氷晶盾",
    color: [0.51, 0.96, 1.0], deep: [0.11, 0.43, 0.59], tc: "§3",
    weight: "mid", hold: null, combo: ["bash", "combo1", "bash"],
    hitSound: "hd.guard", swing: "hd.swing_heavy", kanji: 4, guard: true,
    moves: {
      skill: { name: "氷撃反射", en: "FROST REVENGE", cd: 20 },
      dash: { name: "氷河突撃", en: "GLACIER CHARGE", cd: 90 },
      air: { name: "氷槌", en: "ICE HAMMER", cd: 100 },
      ult: { name: "絶対氷壁", en: "ABSOLUTE AEGIS", cd: 200 },
    },
  },
  "hd:whip": {
    key: "whip", name: "薔薇鞭 ローゼンケッテ", short: "薔薇鞭",
    color: [1.0, 0.31, 0.7], deep: [0.47, 0.04, 0.28], tc: "§d",
    weight: "mid", hold: null, combo: ["crack", "combo1", "crack"],
    hitSound: "hd.crack", swing: "hd.swing", kanji: 3,
    moves: {
      skill: { name: "茨の鞭", en: "THORN LASH", cd: 70 },
      dash: { name: "薔薇の鎖", en: "ROSE GRAPPLE", cd: 80 },
      air: { name: "薔薇旋風", en: "ROSE CYCLONE", cd: 100 },
      ult: { name: "千薔薇葬送", en: "BLOODY ROSE", cd: 200 },
    },
  },
  "hd:claws": {
    key: "claws", name: "獣王爪 ベヒモス", short: "獣王爪",
    color: [1.0, 0.61, 0.14], deep: [0.47, 0.2, 0.02], tc: "§6",
    weight: "light", hold: "hold_claw", combo: ["clawx", "combo1", "uppercut"],
    hitSound: "hd.hit_slash", swing: "hd.swing", kanji: 1,
    moves: {
      skill: { name: "獣王連爪", en: "BEAST FANG", cd: 90 },
      dash: { name: "猛獣突進", en: "WILD POUNCE", cd: 80 },
      air: { name: "天裂爪", en: "SKY RIPPER", cd: 90 },
      ult: { name: "獣神解放", en: "BEHEMOTH ROAR", cd: 200 },
    },
  },
};

export const MOVE_LABEL = { skill: "戦技", dash: "突進", air: "空中", ult: "必殺" };

export function weaponOf(item) {
  return item ? WEAPONS[item.typeId] : undefined;
}

// 当たり判定から外すもの
export const IGNORE_TYPES = new Set([
  "minecraft:item", "minecraft:xp_orb", "minecraft:arrow", "minecraft:snowball",
  "minecraft:egg", "minecraft:ender_pearl", "minecraft:fishing_hook", "minecraft:painting",
  "minecraft:armor_stand", "minecraft:leash_knot", "minecraft:fireball",
  "minecraft:small_fireball", "minecraft:thrown_trident", "minecraft:splash_potion",
  "minecraft:xp_bottle", "minecraft:tnt", "minecraft:falling_block", "minecraft:minecart",
  "minecraft:boat", "minecraft:chest_boat", "minecraft:area_effect_cloud",
  "minecraft:lightning_bolt", "minecraft:wind_charge_projectile",
  "hd:dmg_text",
]);
