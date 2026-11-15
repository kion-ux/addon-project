// 仮のプレイヤー: 箱が地面を歩くだけ。
export class Player {
  constructor(game) {
    const { THREE } = game; this.game = game;
    this.position = new THREE.Vector3(); this.velocity = new THREE.Vector3(); this.yaw = 0; this.state = 'ground';
    this.onGround = true; this.crouching = false; this.sprinting = false; this.inWater = false; this.isOnRoof = false; this.isHidden = false; this.senseActive = false;
    this.hp = 100; this.maxHp = 100; this.knives = 5; this.knivesMax = 5; this.alive = true; this.visibility = 1; this.radius = 0.35; this.height = 1.8;
    this.action = null; this.invulnerable = false; this.fallStartY = 0; this.rig = null;
  }
  init() {
    const { THREE, scene } = this.game;
    this.mesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, 1.8, 0.4).translate(0, 0.9, 0), new THREE.MeshLambertMaterial({ color: 0x2c3550 }));
    scene.add(this.mesh); this.spawnAt(this.game.city.spawnPoints.player);
  }
  update(dt) {
    const s = this.game.input.state, cam = this.game.camRig, sp = s.sprint ? 8 : 5;
    const fx = -Math.sin(cam.yaw), fz = -Math.cos(cam.yaw), rx = Math.cos(cam.yaw), rz = -Math.sin(cam.yaw);
    const vx = (fx * s.move.y + rx * s.move.x) * sp, vz = (fz * s.move.y + rz * s.move.x) * sp;
    this.velocity.set(vx, this.velocity.y - 25 * dt, vz);
    if (s.moveMag > 0.1) this.yaw = Math.atan2(-vx, -vz);
    const r = this.game.collision.moveCapsule(this.position, this.radius, this.height, { x: vx * dt, y: this.velocity.y * dt, z: vz * dt }, { stepHeight: 0.45 });
    if (r.onGround) { this.velocity.y = s.buttons.jump.pressed ? 7.4 : 0; }
    this.onGround = r.onGround; this.mesh.position.copy(this.position); this.mesh.rotation.y = this.yaw;
  }
  spawnAt(p) { this.position.set(p.x, p.y, p.z); this.yaw = p.yaw || 0; this.velocity.set(0, 0, 0); }
  teleport(v, yaw) { this.position.copy(v); if (yaw != null) this.yaw = yaw; this.velocity.set(0, 0, 0); }
  respawn(p) { this.hp = this.maxHp; this.alive = true; this.state = 'ground'; this.spawnAt(p); }
  damage(n) { this.hp = Math.max(0, this.hp - n); return n; }
  heal(n) { this.hp = Math.min(this.maxHp, this.hp + n); }
  canAct() { return false; }
  startAction() { return false; }
  cancelAction() {}
  headPosition(out) { return out.set(this.position.x, this.position.y + 1.62, this.position.z); }
  saveState() { return { hp: this.hp, knives: this.knives }; }
  loadState(d) { if (d) { this.hp = d.hp ?? this.hp; this.knives = d.knives ?? this.knives; } }
}
