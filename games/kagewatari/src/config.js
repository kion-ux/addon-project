// 影渡り — 調整値のすべて。モジュールは数値を直書きせず、ここを読む。
// 単位: メートル / 秒 / ラジアン。Y が上、北が -Z。

export const CONFIG = {
  seed: 20261115,

  world: {
    size: 420,               // 街の一辺 (x, z ともに -210..210)
    half: 210,
    groundY: 0,              // 通りの高さ
    seaLevel: -1.2,          // 海・運河の水面
    seaFloor: -6,
    navCell: 2,              // NPC 用ナビグリッドの一マス
    chunk: 60,               // 静的ジオメトリをまとめる単位
    killY: -40,              // これより落ちたら復帰
  },

  render: {
    fov: 68,
    fovFirst: 78,
    near: 0.1,
    far: 420,
    // quality ごとの設定
    quality: {
      low:    { pixelRatio: 1.0, shadows: false, shadowMap: 0,    fogFar: 110, npcScale: 0.6, antialias: false, drawDistance: 110 },
      medium: { pixelRatio: 1.5, shadows: true,  shadowMap: 1024, fogFar: 150, npcScale: 0.85, antialias: false, drawDistance: 150 },
      high:   { pixelRatio: 2.0, shadows: true,  shadowMap: 2048, fogFar: 200, npcScale: 1.0, antialias: true,  drawDistance: 200 },
    },
    dynamicResolution: true, // fps が落ちたら描画解像度を下げる
    minPixelRatio: 0.75,
  },

  time: {
    dayLength: 600,          // 一日 = 10 分
    startDayTime: 0.30,      // 0=真夜中, 0.25=夜明け, 0.5=正午, 0.75=日没
    maxDt: 1 / 20,
  },

  input: {
    joystickRadius: 56,      // px（見た目の半径）
    joystickDeadzone: 0.12,
    sprintThreshold: 0.86,   // スティックをここまで倒すと疾走
    lookSensitivityTouch: 0.0058, // rad / px
    lookSensitivityMouse: 0.0024,
    lookSensitivityKeys: 2.4,     // rad / s（矢印キー）
  },

  player: {
    radius: 0.35,
    height: 1.8,
    crouchHeight: 1.2,
    eyeHeight: 1.62,
    crouchEyeHeight: 1.1,
    walkSpeed: 2.2,
    runSpeed: 5.0,
    sprintSpeed: 8.0,
    crouchSpeed: 1.9,
    swimSpeed: 2.6,
    accelGround: 32,
    decelGround: 26,
    accelAir: 7,
    turnSpeed: 12,           // 三人称での向き変え rad/s
    gravity: 25,
    maxFallSpeed: 42,
    jumpVelocity: 7.4,
    sprintJumpVelocity: 7.8,
    sprintJumpBoost: 1.18,   // 疾走ジャンプの水平速度倍率
    coyoteTime: 0.12,
    jumpBuffer: 0.15,
    stepHeight: 0.45,
    vaultMaxHeight: 1.35,    // 走りながら自動で乗り越える高さ
    vaultMaxDepth: 2.2,
    mantleMaxHeight: 2.3,    // ジャンプで手を掛けて上がれる高さ
    climbSpeedUp: 2.7,
    climbSpeedSide: 2.3,
    climbLeapHeight: 2.0,    // 壁でジャンプ → 上へ跳ねる高さ
    wallRunTime: 1.0,
    wallRunSpeed: 8.5,
    wallRunGravity: 0.25,    // 壁走り中の重力倍率
    wallJumpVelocity: { out: 6.5, up: 7.0 },
    autoGapJumpMax: 6.5,     // 疾走中、屋根の端で自動で飛び移る最大距離
    edgeBrake: true,         // 歩き（スティック小）の時は高所の端で止まる
    edgeBrakeDrop: 2.5,
    rollFallHeight: 4,       // これ以上の落下は受け身（移動中）
    safeFallHeight: 4,
    deadlyFallHeight: 18,
    fallDamagePerMeter: 9,   // safeFallHeight を超えた 1m ごと
    diveMinHeight: 8,        // この高さ以上から水へ落ちると飛び込み姿勢
    maxHp: 100,
    hpRegenDelay: 5,
    hpRegenRate: 9,
    knivesMax: 5,
  },

  combat: {
    comboWindow: 0.45,       // 次の斬撃を受け付ける猶予
    slash: [
      { damage: 26, duration: 0.40, hitTime: 0.16, range: 2.4, arc: 1.6, lunge: 2.2 },
      { damage: 26, duration: 0.40, hitTime: 0.16, range: 2.4, arc: 1.6, lunge: 2.2 },
      { damage: 42, duration: 0.55, hitTime: 0.24, range: 2.6, arc: 2.0, lunge: 2.8, guardBreak: true },
    ],
    softLockRange: 4.5,
    assassinateRange: 2.1,
    assassinateDuration: 0.9,
    airAssassinateRange: 2.6,
    airAssassinateMaxDrop: 9,
    counterWindow: 0.42,     // 敵の振りかぶりの最後この秒数がカウンター受付
    counterSlowMo: { scale: 0.25, duration: 0.45 },
    dodgeDuration: 0.42,
    dodgeDistance: 4.2,
    dodgeIFrames: [0.04, 0.32],
    knife: { speed: 32, gravity: 4, damageUnaware: 999, damageAware: 45, range: 28, cooldown: 0.35 },
    hitStop: 0.06,
    maxAttackers: 2,         // 同時に斬りかかってくる敵の数
  },

  ai: {
    thinkRate: 8,            // 判断の回数 / 秒
    visionRange: 21,
    visionRangeNight: 12,
    visionHalfAngle: 1.0,    // 約 57 度
    archerVisionRange: 30,
    detectRate: 0.9,         // 1 秒あたりの基本の気づき量
    detectDecay: 0.18,
    suspiciousAt: 0.5,
    combatAt: 1.0,
    alertRadius: 24,
    loseTrackTime: 7,
    searchTime: 14,
    hearingSprint: 6,
    hearingLand: 10,
    hearingCombat: 16,
    roofDetectMul: 0.55,     // 地上の衛兵は屋根の上に気づきにくい
    restrictedMul: 1.8,
    walkSpeed: 1.5,
    runSpeed: 5.2,
    attackRange: 2.1,
    windup: 0.75,
    strikeTime: 0.12,
    recover: 0.55,
    attackCooldown: [1.2, 2.4],
    civilianCount: 46,
    guardCount: 44,
    archerCount: 12,
    animLodNear: 35,
    animLodFar: 90,
  },

  enemies: {
    guard:  { hp: 100, damage: 14, speed: 5.2, blockChance: 0.30, reach: 2.1 },
    spear:  { hp: 110, damage: 17, speed: 5.0, blockChance: 0.25, reach: 2.9 },
    brute:  { hp: 240, damage: 30, speed: 4.2, blockChance: 0.55, reach: 2.4, counterImmune: true },
    archer: { hp: 70,  damage: 11, speed: 4.8, blockChance: 0.10, reach: 1.8, arrowSpeed: 34, fireInterval: 2.6 },
    target: { hp: 150, damage: 16, speed: 5.4, blockChance: 0.35, reach: 2.2 },
  },

  progression: {
    towerRevealRadius: 95,
    chestMoney: [60, 160],
    collectibleMoney: 25,
    contractMoney: 500,
    upgrades: {
      blade:  [{ cost: 400, mul: 1.25 }, { cost: 900, mul: 1.55 }],
      armor:  [{ cost: 350, hp: 130 }, { cost: 800, hp: 170 }],
      pouch:  [{ cost: 250, knives: 8 }, { cost: 600, knives: 12 }],
    },
    knifeRefillCost: 40,
    medicineCost: 30,
  },

  camera: {
    distance: 4.3,
    distanceSprint: 4.9,
    distanceCombat: 5.4,
    distanceClimb: 4.8,
    height: 1.55,            // 注視点の足元からの高さ
    shoulder: 0.45,          // 右肩越しのずらし
    pitchMin: -1.15,
    pitchMax: 0.75,
    pitchMinFirst: -1.45,
    pitchMaxFirst: 1.45,
    collisionPadding: 0.25,
    smooth: 14,
    autoCenterDelay: 2.5,    // スティック操作のみの時、背後へ回り込み始めるまで
    autoCenterSpeed: 1.6,
  },
};

// 画面・端末から既定の品質を推定する
export function defaultQuality() {
  const touch = typeof matchMedia === 'function' && matchMedia('(pointer: coarse)').matches;
  const mem = typeof navigator !== 'undefined' ? navigator.deviceMemory || 4 : 4;
  if (touch) return mem >= 6 ? 'medium' : 'low';
  return 'high';
}
