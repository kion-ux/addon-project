// 仮の空: 半球光と太陽、霧。
export class Sky {
  constructor(game) { this.game = game; this.dayTime = 0.4; this.nightFactor = 0; }
  init() {
    const { THREE, scene } = this.game;
    scene.background = new THREE.Color(0x9cc7e0);
    scene.fog = new THREE.Fog(0x9cc7e0, 30, 200);
    this.hemi = new THREE.HemisphereLight(0xdfefff, 0x8a7a60, 1.4); scene.add(this.hemi);
    this.sun = new THREE.DirectionalLight(0xfff1d6, 2.2); this.sun.position.set(40, 80, 30); scene.add(this.sun);
    this.sunDir = this.sun.position.clone().normalize();
  }
  update() {}
  setDayTime(t) { this.dayTime = t; }
  applyQuality() {}
}
