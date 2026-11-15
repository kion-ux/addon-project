// 仮の入力: キーボードと、テスト用の注入だけ。
const NAMES = ['jump', 'attack', 'dodge', 'throw', 'sense', 'crouch', 'interact', 'view', 'map', 'pause'];
const KEYS = { Space: 'jump', KeyJ: 'attack', KeyK: 'dodge', KeyR: 'throw', KeyF: 'sense', KeyC: 'crouch', KeyE: 'interact', KeyV: 'view', KeyM: 'map', Escape: 'pause' };
export class Input {
  constructor(game) {
    this.game = game; this.keys = new Set(); this.override = null;
    this.state = { move: { x: 0, y: 0 }, moveMag: 0, sprint: false, look: { dx: 0, dy: 0 }, buttons: {}, device: 'keyboard' };
    for (const n of NAMES) this.state.buttons[n] = { down: false, pressed: false, released: false, heldTime: 0 };
  }
  init() {
    addEventListener('keydown', (e) => { this.keys.add(e.code); this.game.audio.unlock?.(); });
    addEventListener('keyup', (e) => this.keys.delete(e.code));
  }
  setOverride(p) { this.override = p; }
  update(dt) {
    const s = this.state, o = this.override, k = this.keys;
    let mx = (k.has('KeyD') ? 1 : 0) - (k.has('KeyA') ? 1 : 0), my = (k.has('KeyW') ? 1 : 0) - (k.has('KeyS') ? 1 : 0);
    let sprint = k.has('ShiftLeft'), lx = 0, ly = 0;
    if (o) { mx = o.move?.x ?? 0; my = o.move?.y ?? 0; sprint = !!o.sprint; lx = o.look?.dx ?? 0; ly = o.look?.dy ?? 0; }
    const m = Math.hypot(mx, my); if (m > 1) { mx /= m; my /= m; }
    s.move.x = mx; s.move.y = my; s.moveMag = Math.min(1, m); s.sprint = sprint; s.look.dx = lx; s.look.dy = ly;
    for (const n of NAMES) {
      const down = o ? !!o.buttons?.[n] : [...k].some((c) => KEYS[c] === n);
      const b = s.buttons[n];
      b.pressed = down && !b.down; b.released = !down && b.down; b.heldTime = down ? b.heldTime + dt : 0; b.down = down;
    }
  }
  setButtonLabel() {} setButtonVisible() {} setButtonHighlight() {}
}
