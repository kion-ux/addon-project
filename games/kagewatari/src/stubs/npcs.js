// 仮の NPC: 誰もいない。
export class NpcManager {
  constructor(game) { this.game = game; this.list = []; this.alertLevel = 0; }
  init() {}
  update() {}
  reset() {} calmDown() {}
  spawnGuard() { return null; } spawnTarget() { return null; } removeNpc() {}
  nearest() { return null; } queryRadius(p, r, out = []) { out.length = 0; return out; }
  noise() {} combatants() { return []; } applyQuality() {}
}
