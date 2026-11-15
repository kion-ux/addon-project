// 仮の進行: 目標なし。
export class Missions {
  constructor(game) {
    this.game = game; this.money = 0; this.upgrades = { blade: 0, armor: 0, pouch: 0 };
    this.towers = []; this.contracts = []; this.collectibles = []; this.chests = []; this.races = []; this.shops = [];
    this.objective = null; this.interactPrompt = null; this.activeRace = null;
    this.stats = { kills: 0, assassinations: 0, counters: 0, synced: 0, collectibles: 0, chests: 0, contracts: 0, playTime: 0 };
  }
  init() {}
  update(dt) { this.stats.playTime += dt; }
  loadState() {} saveState() { return { money: this.money }; }
  respawnPoint() { return this.game.city.spawnPoints.player; }
  fastTravel() {} buyUpgrade() { return false; } buyItem() { return false; } applyUpgrades() {} track() {}
  isRevealed() { return true; }
}
