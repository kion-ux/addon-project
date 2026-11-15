// 仮のカメラ: 背後から追う。
export class CameraRig {
  constructor(game) { this.game = game; this.mode = 'third'; this.yaw = 0; this.pitch = -0.25; this.distance = 4.3; }
  init() {}
  update() {
    const g = this.game, p = g.player.position, s = g.input.state;
    this.yaw -= s.look.dx; this.pitch = Math.max(-1.1, Math.min(0.7, this.pitch + s.look.dy));
    const cp = Math.cos(this.pitch), d = this.distance;
    g.camera.position.set(p.x + Math.sin(this.yaw) * cp * d, p.y + 1.55 - Math.sin(this.pitch) * d, p.z + Math.cos(this.yaw) * cp * d);
    g.camera.lookAt(p.x, p.y + 1.55, p.z);
  }
  setMode(m) { this.mode = m; } toggleMode() { this.mode = this.mode === 'third' ? 'first' : 'third'; }
  snapBehindPlayer() { this.yaw = this.game.player.yaw; }
  shake() {} punch() {}
  project(v, out = {}) { const p = v.clone().project(this.game.camera); out.x = (p.x + 1) / 2 * innerWidth; out.y = (1 - p.y) / 2 * innerHeight; out.visible = p.z < 1; return out; }
}
