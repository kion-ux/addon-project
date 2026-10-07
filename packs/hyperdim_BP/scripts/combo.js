// ===========================================================================
//  通常攻撃の三連コンボ
//  当てるたびに 1→2→3 段目と進み（1.3 秒あけると 1 段目に戻る）、段ごとに全身の
//  振りと斬撃の向きが変わる。三段目はフィニッシュで、武器ごとの追撃が入る。
// ===========================================================================
import { addGauge, hit, freeze } from "./combat.js";
import { P, arc, body, burst, slash, sound, shake, white } from "./fx.js";
import { dirTo } from "./engine.js";
import { chest, flatDir, rand, now, effect } from "./util.js";

const combos = new Map();   // playerId -> { step, last }
const WINDOW = 26;

export function comboStep(player) {
  const s = combos.get(player.id);
  if (!s || now() - s.last > WINDOW) return 0;
  return s.step;
}

export function onMeleeHit(player, target, w) {
  const s = combos.get(player.id) ?? { step: 0, last: -99 };
  const step = now() - s.last <= WINDOW ? (s.step % 3) + 1 : 1;
  combos.set(player.id, { step, last: now() });
  body(player, w.combo[step - 1]);
  addGauge(player, step === 3 ? 10 : 6);
  const dim = player.dimension;
  const c = w.color;
  const at = chest(target);
  const f = flatDir(player);
  const tilt = step === 1 ? 30 : step === 2 ? -30 : 80;
  sound(dim, w.swing, player.location, rand(0.95, 1.1) + step * 0.05, 0.8);
  sound(dim, w.hitSound, at, rand(0.9, 1.1), 0.8);
  (FINISH[w.key] ?? FINISH.default)({ player, target, w, dim, c, at, f, step, tilt });
}

const swingArc = (o, r = 1.9, size = 0.9) =>
  arc(o.dim, chest(o.player), o.f, r, o.step === 2 ? 70 : -70, o.step === 2 ? -70 : 70, o.tilt, o.c,
    { size, steps: 12, life: 0.2, sparks: false });

const FINISH = {
  default(o) {
    swingArc(o);
    if (o.step === 3) {
      burst(o.dim, o.at, o.c, 1.4);
      hit(o.player, o.target, 2, { color: o.c, kb: 0.8, up: 0.3, quiet: true, gauge: 0 });
    }
  },
  greatsword(o) {
    swingArc(o, 2.4, 1.2);
    slash(o.dim, o.at, o.c, o.step === 2 ? 200 : -20, 1.2, "slash");
    if (o.step === 3) {
      slash(o.dim, o.at, white(o.c, 0.2), 90, 2.0, "slash_big", 0.35);
      P(o.dim, "ring_flat", { ...o.player.location, y: o.player.location.y + 0.1 }, { color: o.c, size: 3.2 });
      P(o.dim, "dust", { ...o.target.location, y: o.target.location.y + 0.1 }, { count: 10, speed: 5 });
      shake(o.dim, o.at, 10, 0.3, 0.25);
      hit(o.player, o.target, 4, { color: o.c, kb: 1.2, up: 0.5, dir: o.f, power: 1.6, gauge: 0 });
    }
  },
  twinblades(o) {
    arc(o.dim, chest(o.player), o.f, 1.8, -70, 70, 35, o.c, { size: 0.7, steps: 10, sparks: false });
    arc(o.dim, chest(o.player), o.f, 1.8, 70, -70, -35, o.c, { size: 0.7, steps: 10, sparks: false });
    if (o.step === 3) {
      P(o.dim, "cross", o.at, { color: white(o.c, 0.2), size: 1.3 });
      P(o.dim, "wind", o.at, { color: o.c, count: 6, dir: o.f, speed: 8 });
      hit(o.player, o.target, 3, { color: o.c, kb: 0.9, up: 0.35, dir: o.f, gauge: 0 });
    }
  },
  greataxe(o) {
    swingArc(o, 2.3, 1.1);
    P(o.dim, "flame", o.at, { color: o.c, count: 4, spread: 0.3, speed: 1.5 });
    if (o.step === 3) {
      const g = o.target.location;
      P(o.dim, "flame", { ...g, y: g.y + 0.2 }, { color: o.c, count: 14, spread: 0.7, speed: 2.6, size: 1.3 });
      P(o.dim, "crack_flat", { ...g, y: g.y + 0.05 }, { color: o.c, size: 1.2, rot: rand(0, 360) });
      P(o.dim, "pillar", { ...g, y: g.y + 1.6 }, { color: o.c, size: 0.7, height: 3.2, life: 0.4 });
      sound(o.dim, "hd.fire", g, 1.1, 0.9);
      shake(o.dim, o.at, 10, 0.3, 0.25);
      hit(o.player, o.target, 5, { color: o.c, up: 0.65, kb: 0.4, dir: o.f, power: 1.6, gauge: 0 });
      try { o.target.setOnFire(3, true); } catch (_) { }
    }
  },
  dagger(o) {
    swingArc(o, 1.5, 0.6);
    // 背後からの一撃は会心
    let tf = { x: 0, z: 1 };
    try { const d = o.target.getViewDirection(); tf = { x: d.x, z: d.z }; } catch (_) { }
    const l = Math.hypot(tf.x, tf.z) || 1;
    const backstab = (tf.x / l) * o.f.x + (tf.z / l) * o.f.z > 0.45;
    if (backstab) {
      P(o.dim, "cross", o.at, { color: white(o.c, 0.3), size: 1.2 });
      sound(o.dim, "hd.shadow", o.at, 1.6, 0.7);
      hit(o.player, o.target, 4, { color: o.c, crit: true, power: 1.4, gauge: 2 });
    }
    if (o.step === 3) {
      P(o.dim, "smoke", o.at, { color: [0.14, 0.06, 0.2], count: 6, spread: 0.5, size: 1.2 });
      slash(o.dim, o.at, o.c, rand(0, 360), 1.2, "slash_thin");
      hit(o.player, o.target, 3, { color: o.c, kb: 0.5, up: 0.2, gauge: 0 });
    }
  },
  bow(o) {
    swingArc(o, 1.6, 0.6);
    if (o.step === 3) {
      P(o.dim, "star", o.at, { color: o.c, count: 8, spread: 0.6, speed: 2 });
      hit(o.player, o.target, 2, { color: o.c, kb: 1.2, up: 0.3, dir: o.f, gauge: 0 });
    }
  },
  shield(o) {
    P(o.dim, "hex", o.at, { color: o.c, size: 1.2, life: 0.25 });
    P(o.dim, "snow", o.at, { color: o.c, count: 4, spread: 0.4 });
    if (o.step === 3) {
      P(o.dim, "shard", o.at, { color: o.c, count: 12, speed: 6 });
      sound(o.dim, "hd.ice", o.at, 1.2, 0.8);
      hit(o.player, o.target, 3, { color: o.c, kb: 1.3, up: 0.3, dir: o.f, gauge: 0 });
      freeze(o.target, 24);
    }
  },
  whip(o) {
    P(o.dim, "petal", o.at, { color: o.c, count: 5, spread: 0.5, speed: 2 });
    slash(o.dim, o.at, o.c, rand(0, 360), 0.9, "slash_thin");
    if (o.step === 3) {
      P(o.dim, "impact", o.at, { color: white(o.c, 0.3), size: 1.0 });
      hit(o.player, o.target, 3, { color: o.c, kb: 0.6, gauge: 0 });
      effect(o.target, "poison", 40, 0);
    }
  },
  claws(o) {
    P(o.dim, "claw", o.at, { color: o.c, rot: o.step === 2 ? 30 : -30, size: 1.2 });
    P(o.dim, "spark", o.at, { color: white(o.c, 0.3), count: 6, speed: 5 });
    if (o.step === 3) {
      P(o.dim, "claw", o.at, { color: o.c, rot: 45, size: 1.7 });
      P(o.dim, "claw", o.at, { color: o.c, rot: -45, size: 1.7 });
      hit(o.player, o.target, 4, { color: o.c, up: 0.7, kb: 0.3, dir: dirTo(o.player.location, o.target.location), power: 1.4, gauge: 0 });
    }
  },
};

export function forgetCombo(id) { combos.delete(id); }
