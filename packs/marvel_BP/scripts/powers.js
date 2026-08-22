// ブラザーフッドの技 / the Brotherhood's kits
//
// マグニートーほど作り込まないが、「その能力らしさ」だけは外さない。
// 発動の枠組み（構えの差し替え・消費・クールダウン）は techniques.js と共通。
import { system } from "@minecraft/server";
import { ALLY_TECH, FX, SOUND, ENTITY, FAMILY, PROP } from "./config.js";
import {
  Cooldowns, forward, hasFamily, normalise, safe, setProp, sub, tell, tr,
} from "./util.js";
import {
  chord, cone, fx, fxRing, fxScatter, fxSphere, hit, hitstop, knock,
  lookTarget, ray, shake, shakeNearby, sound,
} from "./effects.js";
import { drag, launchShard } from "./magnetism.js";
import { heroOf, isTransformed, magOf, pose, spendMag } from "./transform.js";

export const allyCooldowns = new Cooldowns();

function hostile(entity, player) {
  if (!entity || entity.id === player.id) return false;
  if (hasFamily(entity, FAMILY.prop)) return false;
  if (hasFamily(entity, FAMILY.brotherhood)) return false;
  return true;
}

const KIT = {
  // --- ミスティーク --------------------------------------------------------
  shapeshift: (p) => {
    fxScatter(p.dimension, FX.shift_shimmer, p.location, 14, 1.2);
    sound(p.dimension, SOUND.attract, p.location, { pitch: 1.5 });
    safe(() => p.addEffect("invisibility", 200, { amplifier: 0, showParticles: false }));
    safe(() => p.addEffect("speed", 200, { amplifier: 1, showParticles: false }));
    shake(p, 0.12, 0.3);
  },
  venom_strike: (p) => {
    for (const { entity } of cone(p, 5, 0.4)) {
      hit(p, entity, 12);
      safe(() => entity.addEffect("poison", 160, { amplifier: 2 }));
      safe(() => entity.addEffect("weakness", 120, { amplifier: 1 }));
      fx(p.dimension, FX.venom_drip, entity.location);
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
    fx(p.dimension, FX.claw_slash, forward(p.getHeadLocation(), p.getViewDirection(), 1.6));
    chord(p.dimension, p.location, [["mob.wolf.growl", 0, { pitch: 0.6 }],
                                    ["random.bowhit", 3, { pitch: 0.8 }]]);
    for (const { entity, dir } of cone(p, 6, 0.15)) {
      hit(p, entity, 20);
      knock(entity, dir, 1.1, 0.35);
      safe(() => entity.addEffect("wither", 100, { amplifier: 0 }));
      fx(p.dimension, FX.claw_slash, entity.location);
      hitstop(entity, 4);
    }
    shake(p, 0.24, 0.25);
  },
  feral_roar: (p) => {
    fx(p.dimension, FX.roar_wave, p.location);
    chord(p.dimension, p.location, [["mob.ravager.roar", 0, { volume: 1.4, pitch: 0.7 }]]);
    for (const e of safe(() => p.dimension.getEntities({ location: p.location, maxDistance: 12 })) ?? []) {
      if (!hostile(e, p)) continue;
      safe(() => e.addEffect("weakness", 180, { amplifier: 1 }));
      safe(() => e.addEffect("slowness", 120, { amplifier: 1 }));
      knock(e, normalise(sub(e.location, p.location)), 0.8, 0.3);
    }
    safe(() => p.addEffect("strength", 200, { amplifier: 2, showParticles: false }));
    shake(p, 0.3, 0.6);
    shakeNearby(p.dimension, p.location, 14, 0.24, 0.5);
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
    fx(p.dimension, FX.tongue_slime, forward(p.getHeadLocation(), p.getViewDirection(), 2.0));
    sound(p.dimension, "mob.slime.attack", p.location, { pitch: 0.9 });
    if (target.entity) {
      drag(target.entity, p.location, 1.6, 0.35);
      hit(p, target.entity, 8);
      fx(p.dimension, FX.tongue_slime, target.entity.location);
    }
  },
  leap: (p) => {
    const dir = p.getViewDirection();
    fxRing(p.dimension, FX.leap_dust, p.location, 1.2, 10, 0.1);
    safe(() => p.applyKnockback(dir.x, dir.z, 2.6, 1.2));
    safe(() => p.addEffect("slow_falling", 90, { amplifier: 0, showParticles: false }));
    sound(p.dimension, "mob.slime.jump", p.location, { pitch: 0.7 });
  },
  slime_spit: (p) => {
    const dir = p.getViewDirection();
    const eye = p.getHeadLocation();
    launchShard(p, forward(eye, dir, 1.0), dir, 1.4, 8, ENTITY.fire_bolt, 40);
    for (const { entity } of ray(p, 12, 1.6)) {
      safe(() => entity.addEffect("blindness", 140, { amplifier: 0 }));
      safe(() => entity.addEffect("slowness", 160, { amplifier: 2 }));
      fx(p.dimension, FX.slime_splat, entity.location);
    }
    sound(p.dimension, "mob.slime.squish", p.location, { pitch: 1.2 });
  },

  // --- ジャガーノート -------------------------------------------------------
  unstoppable: (p) => {
    const dir = p.getViewDirection();
    fx(p.dimension, FX.quake_dust, p.location);
    chord(p.dimension, p.location, [["mob.ravager.roar", 0, { volume: 1.3, pitch: 0.6 }]]);
    safe(() => p.addEffect("speed", 120, { amplifier: 3, showParticles: false }));
    safe(() => p.addEffect("resistance", 120, { amplifier: 4, showParticles: false }));
    safe(() => p.addEffect("strength", 120, { amplifier: 3, showParticles: false }));
    let ticks = 0;
    const run = system.runInterval(() => {
      ticks += 2;
      if (ticks > 100 || !isTransformed(p)) { system.clearRun(run); return; }
      const d = p.getViewDirection();
      safe(() => p.applyKnockback(d.x, d.z, 1.1, 0.02));
      fx(p.dimension, FX.impact_dust, p.location);
      for (const { entity, dir: to } of cone(p, 3.4, 0.0)) {
        hit(p, entity, 22);
        knock(entity, to, 2.2, 0.8);
        fx(p.dimension, FX.slam_ring, entity.location);
      }
    }, 2);
    shake(p, 0.3, 1.0);
  },
  quake_stomp: (p) => {
    fx(p.dimension, FX.slam_ring, p.location);
    fx(p.dimension, FX.quake_crack, p.location);
    fxRing(p.dimension, FX.quake_dust, p.location, 2.6, 12, 0.1);
    chord(p.dimension, p.location, [["random.explode", 0, { volume: 1.1, pitch: 0.6 }]]);
    for (const e of safe(() => p.dimension.getEntities({ location: p.location, maxDistance: 8 })) ?? []) {
      if (!hostile(e, p)) continue;
      hit(p, e, 24);
      knock(e, { x: 0, y: 1, z: 0 }, 0.4, 1.1);
    }
    shake(p, 0.5, 0.5);
    shakeNearby(p.dimension, p.location, 18, 0.4, 0.5);
  },
  hurl: (p) => {
    const target = lookTarget(p, 10);
    const dir = p.getViewDirection();
    if (target.entity) {
      knock(target.entity, dir, 3.4, 1.0);
      hit(p, target.entity, 18);
      fx(p.dimension, FX.debris_chunk, target.entity.location);
    } else {
      launchShard(p, forward(p.getHeadLocation(), dir, 1.4), dir, 1.6, 22,
                  ENTITY.debris, 60);
    }
    sound(p.dimension, "random.explode", p.location, { volume: 0.7, pitch: 1.2 });
  },

  // --- クイックシルバー -----------------------------------------------------
  blitz: (p) => {
    const targets = cone(p, 14, -0.2).slice(0, 6);
    fx(p.dimension, FX.speed_line, p.location);
    let i = 0;
    const step = () => {
      if (i >= targets.length) return;
      const t = targets[i++];
      if (safe(() => t.entity.isValid?.() !== false)) {
        const behind = forward(t.entity.location, normalise(sub(p.location, t.entity.location)), 1.4);
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
    fx(p.dimension, FX.speed_line, p.location);
    safe(() => p.applyKnockback(dir.x, dir.z, 3.2, 0.25));
    safe(() => p.addEffect("speed", 120, { amplifier: 4, showParticles: false }));
    for (let i = 1; i <= 5; i++) {
      system.runTimeout(() => fx(p.dimension, FX.blur_after, p.location), i * 2);
    }
    sound(p.dimension, "mob.enderdragon.flap", p.location, { pitch: 1.8 });
  },

  // --- パイロ ---------------------------------------------------------------
  flame_wave: (p) => {
    const dir = p.getViewDirection();
    const eye = p.getHeadLocation();
    for (let d = 1; d <= 10; d += 1.2) {
      const at = forward(eye, dir, d);
      fx(p.dimension, FX.flame_wave, at);
      fx(p.dimension, FX.ember_rise, at);
    }
    for (const { entity } of cone(p, 11, 0.25)) {
      hit(p, entity, 16);
      safe(() => entity.setOnFire(6, true));
      fx(p.dimension, FX.flame_wave, entity.location);
    }
    chord(p.dimension, p.location, [["mob.ghast.fireball", 0, { pitch: 1.2 }]]);
    shake(p, 0.2, 0.4);
  },
  fire_serpent: (p) => {
    const dir = p.getViewDirection();
    launchShard(p, forward(p.getHeadLocation(), dir, 1.2), dir, 1.2, 20,
                ENTITY.fire_bolt, 90);
    fx(p.dimension, FX.flame_serpent, p.location);
    sound(p.dimension, "mob.blaze.shoot", p.location, { pitch: 0.8 });
  },
  ignite: (p) => {
    const target = lookTarget(p, 18);
    fx(p.dimension, FX.ember_rise, target.location);
    for (const e of safe(() => p.dimension.getEntities({ location: target.location, maxDistance: 4 })) ?? []) {
      if (!hostile(e, p)) continue;
      safe(() => e.setOnFire(8, true));
      hit(p, e, 8);
    }
    sound(p.dimension, "fire.ignite", p.location, { pitch: 1.0 });
  },

  // --- アバランチ -----------------------------------------------------------
  tremor: (p) => {
    fx(p.dimension, FX.quake_dust, p.location);
    fx(p.dimension, FX.quake_crack, p.location);
    for (const e of safe(() => p.dimension.getEntities({ location: p.location, maxDistance: 12 })) ?? []) {
      if (!hostile(e, p)) continue;
      hit(p, e, 12);
      safe(() => e.addEffect("slowness", 160, { amplifier: 3 }));
      knock(e, { x: 0, y: 1, z: 0 }, 0.2, 0.5);
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
        launchShard(p, at, { x: 0, y: -1, z: 0 }, 1.2, 16, ENTITY.debris, 40);
      }, i * 4);
    }
    sound(p.dimension, "random.explode", target.location, { volume: 0.9, pitch: 0.7 });
  },
  fissure: (p) => {
    const dir = p.getViewDirection();
    for (let d = 2; d <= 16; d += 1.6) {
      const at = forward(p.location, { x: dir.x, y: 0, z: dir.z }, d);
      system.runTimeout(() => {
        fx(p.dimension, FX.quake_crack, at);
        fx(p.dimension, FX.quake_dust, at);
        for (const e of safe(() => p.dimension.getEntities({ location: at, maxDistance: 2.6 })) ?? []) {
          if (!hostile(e, p)) continue;
          hit(p, e, 20);
          knock(e, { x: 0, y: 1, z: 0 }, 0.3, 0.9);
        }
      }, Math.round(d * 1.5));
    }
    shake(p, 0.4, 1.0);
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
    fx(p.dimension, FX.slam_ring, p.location);
    for (const { entity, dir } of cone(p, 5, -0.2)) {
      hit(p, entity, 14);
      knock(entity, dir, 3.0, 0.9);
      fx(p.dimension, FX.impact_dust, entity.location);
    }
    sound(p.dimension, "mob.slime.big", p.location, { pitch: 0.6 });
    shake(p, 0.26, 0.3);
  },
  body_slam: (p) => {
    const dir = p.getViewDirection();
    safe(() => p.applyKnockback(dir.x, dir.z, 1.6, 0.9));
    system.runTimeout(() => {
      fx(p.dimension, FX.slam_ring, p.location);
      fx(p.dimension, FX.quake_dust, p.location);
      for (const e of safe(() => p.dimension.getEntities({ location: p.location, maxDistance: 6 })) ?? []) {
        if (!hostile(e, p)) continue;
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
    launchShard(p, forward(p.getHeadLocation(), dir, 1.1), dir, 1.8, 18,
                ENTITY.hex_bolt, 70);
    fx(p.dimension, FX.hex_bolt_trail, forward(p.getHeadLocation(), dir, 1.4));
    sound(p.dimension, "mob.evocation_illager.cast_spell", p.location, { pitch: 1.2 });
  },
  chaos_field: (p) => {
    fx(p.dimension, FX.hex_wave, p.location);
    fxSphere(p.dimension, FX.chaos_motes, p.location, 6, 20);
    for (const e of safe(() => p.dimension.getEntities({ location: p.location, maxDistance: 14 })) ?? []) {
      if (!hostile(e, p)) continue;
      safe(() => e.addEffect("weakness", 220, { amplifier: 3 }));
      safe(() => e.addEffect("blindness", 160, { amplifier: 0 }));
      safe(() => e.addEffect("mining_fatigue", 220, { amplifier: 2 }));
      fx(p.dimension, FX.chaos_motes, e.location);
    }
    sound(p.dimension, "mob.evocation_illager.prepare_attack", p.location, { pitch: 0.9 });
  },
  telekinesis: (p) => {
    const target = lookTarget(p, 20);
    if (!target.entity) { tell(p, tr("msg.no_target")); return; }
    const e = target.entity;
    fx(p.dimension, FX.tk_lift, e.location);
    safe(() => e.addEffect("levitation", 80, { amplifier: 3 }));
    hit(p, e, 10);
    let n = 0;
    const lift = system.runInterval(() => {
      if (++n > 12 || !safe(() => e.isValid?.() !== false)) {
        system.clearRun(lift);
        safe(() => e.applyImpulse({ x: 0, y: -1.6, z: 0 }));
        fx(p.dimension, FX.slam_ring, e.location);
        return;
      }
      fx(p.dimension, FX.chaos_motes, e.location);
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
    tell(player, tr("msg.cooldown"));
    return false;
  }
  if (magOf(player) < spec.cost) { tell(player, tr("msg.no_mag")); return false; }

  pose(player, spec.form, 24);
  system.runTimeout(() => safe(() => KIT[spec.key]?.(player)), 6);
  allyCooldowns.set(player.id, spec.key, spec.cd);
  spendMag(player, spec.cost);
  setProp(player, PROP.tech, spec.key);
  return true;
}

export function allyKitOf(hero) {
  return ALLY_TECH[hero] ?? [];
}
