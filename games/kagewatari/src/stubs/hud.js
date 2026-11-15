// 仮の HUD: タイトルの「はじめる」だけ。
export class Hud {
  constructor(game) { this.game = game; }
  init() {
    const b = document.createElement('button');
    b.textContent = 'はじめる'; b.style.cssText = 'position:absolute;left:50%;top:60%;transform:translateX(-50%);font-size:20px;padding:12px 28px';
    b.onclick = () => { this.game.audio.unlock?.(); this.game.startNewGame(); };
    document.getElementById('menu-layer').appendChild(b); this.btn = b;
  }
  update() { this.btn.hidden = this.game.state !== 'title'; }
  toast() {} banner() {} flash() {} openShop() {} openMap() {} closeMap() {}
}
