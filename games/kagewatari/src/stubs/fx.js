// 仮の演出: 何もしない。
export class Fx {
  constructor(game) { this.game = game; }
  init() {}
  computeTimeScale() { return 1; }
  hitStop() {} slowMo() {} burst() {} startTrail() {} ring() {}
  update() {}
}
