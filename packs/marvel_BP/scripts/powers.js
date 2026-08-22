// ブラザーフッドの技 27 / the Brotherhood's kits
//
// マグニートーほど作り込まないが、「その能力らしさ」だけは外さない。
// 発動の枠組み（構えの差し替え・消費・クールダウン）は techniques.js と共通で、
// **拍も同じ式で数える** — `clipBeat()` が唯一の出どころ。
//
// 分担は 15 技と同じ。体に付く VFX は ally クリップ（担当 6/7）が locator から
// 出しているので、ここが出すのは **標的側と世界側だけ**。
import { system } from "@minecraft/server";
import { ALLY_TECH, FX, SOUND, ENTITY, PROP } from "./config.js";
import {
  Cooldowns, forward, normalise, safe, setProp, sub, tell, tr,
} from "./util.js";
import {
  chord, fx, fxRing, fxScatter, fxSphere, hit, hitstop, knock, lookTarget,
  selfPush, shake, shakeNearby, sound,
} from "./effects.js";
import { drag } from "./magnetism.js";
import { heroOf, isTransformed, magOf, pose, spendMag } from "./transform.js";
import {
  clipBeat, coneOf, enemiesNear, hostile, launchCapped, rayOf,
} from "./techniques.js";

export const allyCooldowns = new Cooldowns();

//: 技 -> [系統, クリップ長 L 秒]。`gen_anim_tech.ALLY_TIMING` と同じ値。
//: これも本来は contract 側から来るべき表（担当 10 への申し送り）。
const ALLY_CLIP = {
  shapeshift: ["heavy", 1.20], venom_strike: ["light", 0.66], vanish: ["light", 0.84],
  rend: ["light", 0.74], feral_roar: ["heavy", 1.10], regenerate: ["heavy", 1.30],
  tongue_lash: ["light", 0.78], leap: ["light", 0.84], slime_spit: ["light", 0.72],
  unstoppable: ["heavy", 1.40], quake_stomp: ["heavy", 1.00], hurl: ["heavy", 1.06],
  blitz: ["light", 0.76], afterimage: ["light", 0.80], sonic_dash: ["light", 0.68],
  flame_wave: ["light", 0.86], fire_serpent: ["heavy", 1.16], ignite: ["light", 0.60],
  tremor: ["heavy", 1.00], rockfall: ["heavy", 1.20], fissure: ["heavy", 1.30],
  immovable: ["heavy", 1.10], belly_bounce: ["light", 0.84], body_slam: ["heavy", 1.06],
  hex_bolt: ["light", 0.70], chaos_field: ["heavy", 1.34], telekinesis: ["heavy", 1.10],
};

//: 構えを保つ技（クリップ側が "hold_on_last_frame"）。効果の持続に従わせる。
const ALLY_SUSTAIN = { immovable: 300, telekinesis: 80 };

function eyeOf(p) {
  return safe(() => p.getHeadLocation()) ?? p.location;
}

function above(e, dy = 1.0) {
  return { x: e.location.x, y: e.location.y + dy, z: e.location.z };
}

const KIT = {
  // --- ミスティーク --------------------------------------------------------
  shapeshift: (p) => {
    fxScatter(p.dimension, FX.shift_shimmer, p.location, 14, 1.2);
    sound(p.dimension, SOUND.attract, p.location, { pitch: 1.5 });
    safe(() => p.addEffect("invisibility", 200, { amplifier: 0, showParticles: false }));
    safe(() => p.addEffect("speed", 200, { amplifier: 1, showParticles: false }));
    // 化けている間は敵意が逸れる — 近くの敵の狙いを一度切る。
    for (const e of enemiesNear(p, 12)) {
      safe(() => e.addEffect("blindness", 60, { amplifier: 0, showParticles: false }));
    }
    shake(p, 0.08, 0.14, "rotational");
  },
  venom_strike: (p) => {
    for (const { entity } of coneOf(p, 5, 0.4)) {
      hit(p, entity, 12);
      safe(() => entity.addEffect("poison", 160, { amplifier: 2 }));
      safe(() => entity.addEffect("weakness", 120, { amplifier: 1 }));
      fx(p.dimension, FX.venom_drip, above(entity, 1.0));
    }
    sound(p.dimension, SOUND.disarm, p.location, { pitch: 1.3 });
  },
  vanish: (p) => {
    const dir = p.getViewDirection();
    const to = forward(p.location, { x: -dir.x, y: 0, z: -dir.z }, 6);
    fxScatter(p.dimension, FX.shift_shimmer, p.location, 10, 1.0);
    safe(() => p.teleport({ x: to.x, y: p.location.y, z: to.z }));
    fxScatter(p.dimension, FX.shift_shimmer, p.location, 10, 1.0);
    safe(() => p.addEffect("invisibility", 100, { amplifier: 0, showParticles: false }));
    sound(p.dimension, SOUND.attract, p.location, { pitch: 1.8 });
  },

  // --- セイバートゥース ----------------------------------------------------
  rend: (p) => {
    chord(p.dimension, p.location, [["mob.wolf.growl", 0, { pitch: 0.6 }],
                                    ["random.bowhit", 3, { pitch: 0.8 }]]);
    for (const { entity, dir } of coneOf(p, 6, 0.15)) {
      hit(p, entity, 20);
      knock(entity, dir, 1.1, 0.35);
      safe(() => entity.addEffect("wither", 100, { amplifier: 0 }));
      fx(p.dimension, FX.claw_slash, above(entity, 1.0));
      fx(p.dimension, FX.blood_red, above(entity, 1.1));
      hitstop(entity, 4);
    }
    shake(p, 0.08, 0.12, "rotational");
  },
  feral_roar: (p) => {
    chord(p.dimension, p.location, [["mob.ravager.roar", 0, { volume: 1.4, pitch: 0.7 }]]);
    for (const r of [4, 9, 14]) {
      system.runTimeout(() => fxRing(p.dimension, FX.roar_wave, p.location, r, 10 + r, 1.0),
                        Math.round(r * 0.5));
    }
    for (const e of enemiesNear(p, 12)) {
      safe(() => e.addEffect("weakness", 180, { amplifier: 1 }));
      safe(() => e.addEffect("slowness", 120, { amplifier: 1 }));
      knock(e, normalise(sub(e.location, p.location)), 0.8, 0.3);
    }
    safe(() => p.addEffect("strength", 200, { amplifier: 2, showParticles: false }));
    shake(p, 0.14, 0.20, "rotational");
    shakeNearby(p.dimension, p.location, 14, 0.24, 0.20);
  },
  regenerate: (p) => {
    fxRing(p.dimension, FX.regen_knit, p.location, 1.0, 12, 0.8);
    safe(() => p.addEffect("regeneration", 200, { amplifier: 3 }));
    safe(() => p.addEffect("absorption", 300, { amplifier: 2 }));
    sound(p.dimension, "random.levelup", p.location, { pitch: 0.8 });
  },

  // --- トード ---------------------------------------------------------------
  tongue_lash: (p) => {
    const target = lookTarget(p, 14);
    sound(p.dimension, "mob.slime.attack", p.location, { pitch: 0.9 });
    if (!target.entity || !hostile(target.entity, p)) { tell(p, tr("msg.no_target")); return; }
    // 舌は「線」で見せる。着地点だけに出すと何が起きたか判らない。
    const eye = eyeOf(p);
    const to = above(target.entity, 0.9);
    for (let t = 0; t <= 1.0; t += 0.12) {
      fx(p.dimension, FX.tongue_slime, {
        x: eye.x + (to.x - eye.x) * t, y: eye.y + (to.y - eye.y) * t,
        z: eye.z + (to.z - eye.z) * t,
      });
    }
    drag(target.entity, p.location, 1.6, 0.35);
    hit(p, target.entity, 8);
  },
  leap: (p) => {
    const dir = p.getViewDirection();
    fxRing(p.dimension, FX.leap_dust, p.location, 1.2, 10, 0.1);
    selfPush(p, dir.x, dir.z, 2.6, 1.2);
    safe(() => p.addEffect("slow_falling", 90, { amplifier: 0, showParticles: false }));
    sound(p.dimension, "mob.slime.jump", p.location, { pitch: 0.7 });
  },
  slime_spit: (p) => {
    const dir = p.getViewDirection();
    launchCapped(p, forward(eyeOf(p), dir, 1.0), dir, 1.4, 8, ENTITY.fire_bolt, 40);
    for (const { entity } of rayOf(p, 12, 1.6)) {
      safe(() => entity.addEffect("blindness", 140, { amplifier: 0 }));
      safe(() => entity.addEffect("slowness", 160, { amplifier: 2 }));
      fx(p.dimension, FX.slime_splat, above(entity, 1.2));
    }
    sound(p.dimension, "mob.slime.squish", p.location, { pitch: 1.2 });
  },

  // --- ジャガーノート -------------------------------------------------------
  unstoppable: (p) => {
    chord(p.dimension, p.location, [["mob.ravager.roar", 0, { volume: 1.3, pitch: 0.6 }]]);
    safe(() => p.addEffect("speed", 120, { amplifier: 3, showParticles: false }));
    safe(() => p.addEffect("resistance", 120, { amplifier: 4, showParticles: false }));
    safe(() => p.addEffect("strength", 120, { amplifier: 3, showParticles: false }));
    let ticks = 0;
    const run = system.runInterval(() => {
      ticks += 2;
      if (ticks > 100 || !isTransformed(p)) { system.clearRun(run); return; }
      const d = p.getViewDirection();
      selfPush(p, d.x, d.z, 1.1, 0.02);
      fx(p.dimension, FX.impact_dust, p.location);
      // 走り出したら止まらない。轢いた相手は前へ飛ぶ。
      for (const { entity, dir: to } of coneOf(p, 3.4, 0.0)) {
        hit(p, entity, 22);
        knock(entity, to, 2.2, 0.8);
        fx(p.dimension, FX.slam_ring, entity.location);
      }
    }, 2);
    shake(p, 0.14, 0.30, "rotational");
  },
  quake_stomp: (p) => {
    fx(p.dimension, FX.quake_crack, p.location);
    fxRing(p.dimension, FX.quake_dust, p.location, 2.6, 12, 0.1);
    chord(p.dimension, p.location, [["random.explode", 0, { volume: 1.1, pitch: 0.6 }]]);
    for (const e of enemiesNear(p, 8)) {
      hit(p, e, 24);
      knock(e, { x: 0, y: 1, z: 0 }, 0.4, 1.1);
    }
    shake(p, 0.14, 0.20, "rotational");
    shakeNearby(p.dimension, p.location, 18, 0.4, 0.20);
  },
  hurl: (p) => {
    const target = lookTarget(p, 10);
    const dir = p.getViewDirection();
    if (target.entity && hostile(target.entity, p)) {
      knock(target.entity, dir, 3.4, 1.0);
      hit(p, target.entity, 18);
      fx(p.dimension, FX.debris_chunk, above(target.entity, 0.8));
    } else {
      launchCapped(p, forward(eyeOf(p), dir, 1.4), dir, 1.6, 22, ENTITY.debris, 60);
    }
    sound(p.dimension, "random.explode", p.location, { volume: 0.7, pitch: 1.2 });
  },

  // --- クイックシルバー -----------------------------------------------------
  blitz: (p) => {
    const targets = coneOf(p, 14, -0.2).slice(0, 6);
    if (!targets.length) { tell(p, tr("msg.no_target")); return; }
    let i = 0;
    const step = () => {
      if (i >= targets.length) return;
      const t = targets[i++];
      if (safe(() => t.entity.isValid?.() !== false)) {
        const behind = forward(t.entity.location,
                               normalise(sub(p.location, t.entity.location)), 1.4);
        safe(() => p.teleport({ x: behind.x, y: t.entity.location.y, z: behind.z }));
        fx(p.dimension, FX.blur_after, p.location);
        hit(p, t.entity, 14);
        hitstop(t.entity, 3);
        sound(p.dimension, "random.bowhit", t.entity.location, { pitch: 1.6 });
      }
      system.runTimeout(step, 3);
    };
    step();
  },
  afterimage: (p) => {
    for (let i = 0; i < 4; i++) {
      system.runTimeout(() => fx(p.dimension, FX.blur_after, p.location), i * 3);
    }
    safe(() => p.addEffect("speed", 160, { amplifier: 5, showParticles: false }));
    safe(() => p.addEffect("resistance", 160, { amplifier: 3, showParticles: false }));
    sound(p.dimension, SOUND.attract, p.location, { pitch: 2.0 });
  },
  sonic_dash: (p) => {
    const dir = p.getViewDirection();
    selfPush(p, dir.x, dir.z, 3.2, 0.25);
    safe(() => p.addEffect("speed", 120, { amplifier: 4, showParticles: false }));
    for (let i = 1; i <= 5; i++) {
      system.runTimeout(() => fx(p.dimension, FX.speed_line, p.location), i * 2);
    }
    sound(p.dimension, "mob.enderdragon.flap", p.location, { pitch: 1.8 });
  },

  // --- パイロ ---------------------------------------------------------------
  flame_wave: (p) => {
    const dir = p.getViewDirection();
    const eye = eyeOf(p);
    // 波は「前へ走る」ように時間差で出す。同時に出すと壁になる。
    for (let i = 0; i < 8; i++) {
      system.runTimeout(() => {
        const at = forward(eye, dir, 1.5 + i * 1.2);
        fx(p.dimension, FX.flame_wave, at);
        fx(p.dimension, FX.ember_rise, at);
      }, i);
    }
    for (const { entity } of coneOf(p, 11, 0.25)) {
      hit(p, entity, 16);
      safe(() => entity.setOnFire(6, true));
      fx(p.dimension, FX.flame_wave, above(entity, 0.8));
    }
    chord(p.dimension, p.location, [["mob.ghast.fireball", 0, { pitch: 1.2 }]]);
    shake(p, 0.08, 0.16, "rotational");
  },
  fire_serpent: (p) => {
    const dir = p.getViewDirection();
    launchCapped(p, forward(eyeOf(p), dir, 1.2), dir, 1.2, 20, ENTITY.fire_bolt, 90);
    fx(p.dimension, FX.flame_serpent, forward(eyeOf(p), dir, 2.0));
    sound(p.dimension, "mob.blaze.shoot", p.location, { pitch: 0.8 });
  },
  ignite: (p) => {
    const target = lookTarget(p, 18);
    fx(p.dimension, FX.ember_rise, target.location);
    for (const e of enemiesNear(p, 4, target.location)) {
      safe(() => e.setOnFire(8, true));
      hit(p, e, 8);
    }
    sound(p.dimension, "fire.ignite", target.location, { pitch: 1.0 });
  },

  // --- アバランチ -----------------------------------------------------------
  tremor: (p) => {
    fx(p.dimension, FX.quake_crack, p.location);
    for (const e of enemiesNear(p, 12)) {
      hit(p, e, 12);
      safe(() => e.addEffect("slowness", 160, { amplifier: 3 }));
      knock(e, { x: 0, y: 1, z: 0 }, 0.2, 0.5);
      fx(p.dimension, FX.quake_dust, e.location);
    }
    shakeNearby(p.dimension, p.location, 20, 0.45, 0.9);
    sound(p.dimension, "ambient.cave", p.location, { volume: 1.2, pitch: 0.5 });
  },
  rockfall: (p) => {
    const target = lookTarget(p, 20);
    for (let i = 0; i < 8; i++) {
      system.runTimeout(() => {
        const at = {
          x: target.location.x + (Math.random() - 0.5) * 5,
          y: target.location.y + 7,
          z: target.location.z + (Math.random() - 0.5) * 5,
        };
        fx(p.dimension, FX.rock_fall, at);
        launchCapped(p, at, { x: 0, y: -1, z: 0 }, 1.2, 16, ENTITY.debris, 40);
      }, i * 4);
    }
    sound(p.dimension, "random.explode", target.location, { volume: 0.9, pitch: 0.7 });
  },
  fissure: (p) => {
    const dir = p.getViewDirection();
    for (let d = 2; d <= 16; d += 1.6) {
      const at = forward(p.location, { x: dir.x, y: 0, z: dir.z }, d);
      system.runTimeout(() => {
        // 割れ目が走る。先に地面が割れて、遅れて土埃。
        fx(p.dimension, FX.quake_crack, at);
        system.runTimeout(() => fx(p.dimension, FX.quake_dust, at), 2);
        for (const e of enemiesNear(p, 2.6, at)) {
          hit(p, e, 20);
          knock(e, { x: 0, y: 1, z: 0 }, 0.3, 0.9);
        }
      }, Math.round(d * 1.5));
    }
    shake(p, 0.14, 0.30, "rotational");
  },

  // --- ブロブ ---------------------------------------------------------------
  immovable: (p) => {
    fx(p.dimension, FX.slam_ring, p.location);
    safe(() => p.addEffect("resistance", 300, { amplifier: 4, showParticles: false }));
    safe(() => p.addEffect("slowness", 300, { amplifier: 5, showParticles: false }));
    safe(() => p.addEffect("absorption", 300, { amplifier: 4 }));
    sound(p.dimension, "random.anvil_land", p.location, { pitch: 0.5 });
    shakeNearby(p.dimension, p.location, 10, 0.3, 0.4);
  },
  belly_bounce: (p) => {
    for (const { entity, dir } of coneOf(p, 5, -0.2)) {
      hit(p, entity, 14);
      knock(entity, dir, 3.0, 0.9);
      fx(p.dimension, FX.impact_dust, entity.location);
    }
    sound(p.dimension, "mob.slime.big", p.location, { pitch: 0.6 });
    shake(p, 0.08, 0.16, "rotational");
  },
  body_slam: (p) => {
    const dir = p.getViewDirection();
    selfPush(p, dir.x, dir.z, 1.6, 0.9);
    // 跳んでから落ちるまでが技。着地の 12 tick 後に効果を出す。
    system.runTimeout(() => {
      fx(p.dimension, FX.slam_ring, p.location);
      fxRing(p.dimension, FX.quake_dust, p.location, 2.4, 10, 0.1);
      for (const e of enemiesNear(p, 6)) {
        hit(p, e, 26);
        knock(e, normalise(sub(e.location, p.location)), 1.4, 0.7);
      }
      shakeNearby(p.dimension, p.location, 16, 0.45, 0.5);
      sound(p.dimension, "random.explode", p.location, { volume: 1.0, pitch: 0.5 });
    }, 12);
  },

  // --- スカーレット・ウィッチ -------------------------------------------------
  hex_bolt: (p) => {
    const dir = p.getViewDirection();
    launchCapped(p, forward(eyeOf(p), dir, 1.1), dir, 1.8, 18, ENTITY.hex_bolt, 70);
    fx(p.dimension, FX.hex_bolt_trail, forward(eyeOf(p), dir, 1.4));
    sound(p.dimension, "mob.evocation_illager.cast_spell", p.location, { pitch: 1.2 });
  },
  chaos_field: (p) => {
    fxSphere(p.dimension, FX.chaos_motes, p.location, 6, 20);
    for (const r of [5, 10, 14]) {
      system.runTimeout(() => fxRing(p.dimension, FX.hex_wave, p.location, r, 10 + r, 1.2),
                        Math.round(r * 0.6));
    }
    for (const e of enemiesNear(p, 14)) {
      safe(() => e.addEffect("weakness", 220, { amplifier: 3 }));
      safe(() => e.addEffect("blindness", 160, { amplifier: 0 }));
      safe(() => e.addEffect("mining_fatigue", 220, { amplifier: 2 }));
      fx(p.dimension, FX.chaos_motes, above(e, 1.2));
    }
    sound(p.dimension, "mob.evocation_illager.prepare_attack", p.location, { pitch: 0.9 });
  },
  telekinesis: (p) => {
    const target = lookTarget(p, 20);
    if (!target.entity || !hostile(target.entity, p)) { tell(p, tr("msg.no_target")); return; }
    const e = target.entity;
    fx(p.dimension, FX.tk_lift, e.location);
    safe(() => e.addEffect("levitation", 80, { amplifier: 3 }));
    hit(p, e, 10);
    let n = 0;
    const lift = system.runInterval(() => {
      if (++n > 12 || !safe(() => e.isValid?.() !== false)) {
        system.clearRun(lift);
        // 吊るし上げて、落とす。落とすところまでが技。
        safe(() => e.applyImpulse({ x: 0, y: -1.6, z: 0 }));
        fx(p.dimension, FX.slam_ring, e.location);
        sound(p.dimension, "random.anvil_land", e.location, { volume: 0.8, pitch: 0.7 });
        return;
      }
      fx(p.dimension, FX.chaos_motes, above(e, 1.0));
    }, 5);
    sound(p.dimension, "mob.evocation_illager.cast_spell", p.location, { pitch: 0.8 });
  },
};

export function useAllyTechnique(player, index) {
  const hero = heroOf(player);
  const kit = ALLY_TECH[hero];
  if (!kit || !kit[index]) return false;
  const spec = kit[index];
  if (!isTransformed(player)) { tell(player, tr("msg.no_power")); return false; }
  if (!allyCooldowns.ready(player.id, spec.key)) {
    const left = Math.ceil(allyCooldowns.remaining(player.id, spec.key) / 20);
    tell(player, { rawtext: [{ translate: "marvel.msg.cooldown" }, { text: ` §7${left}s` }] });
    return false;
  }
  if (magOf(player) < spec.cost) { tell(player, tr("msg.no_mag")); return false; }

  const [family, length] = ALLY_CLIP[spec.key] ?? ["light", 0.8];
  const beat = clipBeat(family, length);
  // 保持系は効果の持続に、それ以外はクリップ長 + 余韻に従う。
  pose(player, spec.form, ALLY_SUSTAIN[spec.key] ?? beat.hold);
  // 撃発 t_d ちょうどで効果を出す。ここが 15 技と同じ式であることが大事。
  system.runTimeout(() => safe(() => KIT[spec.key]?.(player)), beat.delay);
  allyCooldowns.set(player.id, spec.key, spec.cd);
  spendMag(player, spec.cost);
  setProp(player, PROP.tech, spec.key);
  return true;
}

export function allyKitOf(hero) {
  return ALLY_TECH[hero] ?? [];
}

/** UI と HUD が「あと何秒か」を出せるように。 */
export function allyCooldownLeft(player, key) {
  return allyCooldowns.remaining(player.id, key);
}
