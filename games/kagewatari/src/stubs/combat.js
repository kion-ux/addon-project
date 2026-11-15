// 仮の戦い: 何もしない。
export class Combat {
  constructor(game) { this.game = game; this.damageMul = 1; this.assassinationCandidate = null; this.counterCandidate = null; this.lockTarget = null; this.projectiles = []; }
  init() {}
  update() {}
  npcStrike() { return 'miss'; }
  spawnProjectile() {}
}
