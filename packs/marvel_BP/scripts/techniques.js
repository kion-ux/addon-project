// マグニートーの技 15 / Magneto's fifteen techniques
//
// 一つの技は、必ず次の四つを揃える。どれが欠けても安っぽくなる。
//   1. 三人称の構え   pose() で体アイテムを差し替える
//   2. 一人称の手元   技アイテムの attachable が自動で反応する
//   3. 画面の演出     パーティクル・音・画面揺れ・（必殺技なら）暗転とタイトル
//   4. 実際の効果     ダメージ・ノックバック・ブロック操作
import { world, system } from "@minecraft/server";
import {
  PROP, TECH, FX, SOUND, ENTITY, FAMILY, MAG_MAX,
} from "./config.js";
import {
  Cooldowns, add, distance, forward, hasFamily, normalise, num, safe, scale,
  setProp, str, sub, tell, title, tr,
} from "./util.js";
import {
  chord, cone, fade, fx, fxRing, fxScatter, fxSphere, fxSpiral, fxTrail, hit,
  hitstop, knock, lookTarget, ray, shake, shakeNearby, sound,
} from "./effects.js";
import {
  drag, drawFieldLines, launchShard, metalOn, pullItems, revealMetal, ripBlock,
  scanMetal, stripEquipment,
} from "./magnetism.js";
import { isTransformed, magOf, pose, spendMag, stageOf } from "./transform.js";

export const cooldowns = new Cooldowns();

const DAMAGE_SCALE = { 1: 0.7, 2: 1.0, 3: 1.35 };

function power(player) {
  return DAMAGE_SCALE[stageOf(player)] ?? 1.0;
}

/** 敵味方の判定。ブラザーフッドと自分は撃たない。 */
function hostile(entity, player) {
  if (!entity || entity.id === player.id) return false;
  if (hasFamily(entity, FAMILY.prop)) return false;
  if (hasFamily(entity, FAMILY.brotherhood)) return false;
  return true;
}

// ===========================================================================
//  技の本体
// ===========================================================================
const ACTION = {};

// --- 1. 磁力斥力 -------------------------------------------------------------
ACTION.repulse = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const dir = player.getViewDirection();
  const p = power(player);

  fx(dim, FX.repulse_wave, at);
  fxRing(dim, FX.mag_push, at, 1.4, 12, 0.8);
  fxScatter(dim, FX.mag_spark, at, 8, 1.6);
  chord(dim, at, [[SOUND.repulse, 0, { volume: 1.0, pitch: 1.5 }],
                  [SOUND.mag_release, 2, { volume: 0.6, pitch: 1.8 }]]);
  shake(player, 0.3, 0.3);
  shakeNearby(dim, at, 12, 0.22, 0.3);

  let struck = 0;
  for (const { entity, dir: to, distance: d } of cone(player, 10, 0.1)) {
    const metal = metalOn(entity);
    const force = (1.1 + metal * 0.55) * p * (1 - d / 14);
    hit(player, entity, (8 + metal * 3) * p);
    knock(entity, to, force * 2.4, 0.55 + metal * 0.08);
    fx(dim, FX.mag_push, entity.location);
    struck++;
  }
  // 足元の緩い金属も吹き飛ぶ
  pullItems(dim, at, 8, forward(at, dir, 10), 0.5);
  return struck > 0 || true;
};

// --- 2. 磁力引力 -------------------------------------------------------------
ACTION.attract = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const hand = player.getHeadLocation();
  const p = power(player);

  fx(dim, FX.attract_funnel, at);
  fxSpiral(dim, FX.mag_pull, { x: at.x, y: at.y + 0.4, z: at.z }, 4.0, 2.0, 2, 24);
  sound(dim, SOUND.attract, at, { volume: 0.9, pitch: 0.9 });

  const targets = [];
  for (const { entity, distance: d } of cone(player, 16, -0.25)) {
    const metal = metalOn(entity);
    drag(entity, at, 0.9 + metal * 0.28, 0.28);
    targets.push(entity.location);
    if (metal > 0) hit(player, entity, 2 * p);
  }
  pullItems(dim, at, 16, at, 0.85);
  drawFieldLines(dim, hand, targets);
  return true;
};

// --- 3. 金属剥奪 -------------------------------------------------------------
ACTION.disarm = (player) => {
  const dim = player.dimension;
  const p = power(player);
  let stripped = 0;
  for (const { entity, distance: d } of cone(player, 12, 0.25)) {
    const n = stripEquipment(entity, dim);
    if (n > 0) {
      stripped += n;
      fx(dim, FX.disarm_flash, { x: entity.location.x, y: entity.location.y + 1.1, z: entity.location.z });
      fx(dim, FX.metal_rip, entity.location);
      hit(player, entity, 4 * p);
      hitstop(entity, 6);
    } else if (metalOn(entity) === 0) {
      fx(dim, FX.mag_glyph, entity.location);
    }
  }
  if (stripped) {
    chord(dim, player.location, [[SOUND.disarm, 0, { pitch: 0.9 }],
                                 [SOUND.metal_hit, 4, { volume: 0.6, pitch: 1.4 }]]);
    shake(player, 0.18, 0.25);
  } else {
    tell(player, tr("msg.no_target"));
    sound(dim, SOUND.ui_select, player.location, { pitch: 0.6 });
  }
  return true;
};

// --- 4. 磁界斬 ---------------------------------------------------------------
ACTION.lance = (player) => {
  const dim = player.dimension;
  const eye = player.getHeadLocation();
  const dir = player.getViewDirection();
  const p = power(player);

  fx(dim, FX.mag_glyph, forward(eye, dir, 1.0));
  chord(dim, player.location, [[SOUND.lance, 0, { volume: 1.0, pitch: 1.1 }],
                               [SOUND.shard, 3, { volume: 0.7, pitch: 1.6 }]]);
  shake(player, 0.22, 0.22);

  launchShard(player, forward(eye, dir, 1.2), dir, 2.2, 16 * p);
  // 芯の左右に一本ずつ添えて「束」に見せる
  for (const off of [-0.35, 0.35]) {
    const side = normalise({ x: -dir.z, y: 0, z: dir.x });
    launchShard(player, add(forward(eye, dir, 1.0), scale(side, off)), dir, 2.1, 8 * p);
  }
  for (const { entity, along } of ray(player, 20, 1.3)) {
    hit(player, entity, 14 * p);
    knock(entity, dir, 0.9, 0.25);
    fx(dim, FX.lance_impact, entity.location);
    break;                                   // 最初の一体を貫いたら止める
  }
  fx(dim, FX.lance_streak, forward(eye, dir, 3.0));
  return true;
};

// --- 5. 鉄片嵐 ---------------------------------------------------------------
ACTION.shard_storm = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const p = power(player);
  const found = scanMetal(dim, at, 10, 14);

  fx(dim, FX.storm_swirl, at);
  sound(dim, SOUND.mag_charge, at, { volume: 1.0, pitch: 1.5 });

  // 周囲の金属を実際に引き剥がして弾に変える（無ければ磁界から作る）
  let ammo = 0;
  for (const m of found) {
    if (ammo >= 8) break;
    const shard = ripBlock(dim, { x: m.x, y: m.y, z: m.z }, player.id);
    if (shard) { safe(() => shard.remove()); ammo++; }
  }
  const shots = Math.max(10, 10 + ammo * 2);

  let fired = 0;
  const step = () => {
    if (fired >= shots) return;
    const eye = player.getHeadLocation();
    const dir = player.getViewDirection();
    const spread = 0.20;
    const jitter = {
      x: dir.x + (Math.random() - 0.5) * spread,
      y: dir.y + (Math.random() - 0.5) * spread * 0.6,
      z: dir.z + (Math.random() - 0.5) * spread,
    };
    launchShard(player, forward(eye, normalise(jitter), 1.1), normalise(jitter),
                2.0, (6 + ammo * 0.7) * p);
    fx(dim, FX.shard_burst, forward(eye, dir, 1.0));
    if (fired % 3 === 0) sound(dim, SOUND.shard, player.location, { volume: 0.5, pitch: 1.2 + Math.random() * 0.5 });
    fired++;
    system.runTimeout(step, 2);
  };
  step();
  shake(player, 0.2, 1.2);
  return true;
};

// --- 6. 磁力障壁 -------------------------------------------------------------
ACTION.barrier = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const duration = 140 + stageOf(player) * 40;

  const dome = safe(() => dim.spawnEntity(ENTITY.barrier_dome,
    { x: at.x, y: at.y + 0.2, z: at.z }));
  setProp(player, PROP.barrier, system.currentTick + duration);
  fx(dim, FX.barrier_hex, at);
  fxSphere(dim, FX.barrier_hex, { x: at.x, y: at.y + 1.4, z: at.z }, 3.2, 22);
  fx(dim, FX.mag_ring, at);
  chord(dim, at, [[SOUND.barrier, 0, { volume: 1.0, pitch: 1.2 }],
                  [SOUND.mag_charge, 4, { volume: 0.6, pitch: 1.6 }]]);
  safe(() => player.addEffect("resistance", duration, { amplifier: 3, showParticles: false }));

  if (dome) {
    let left = duration;
    const follow = system.runInterval(() => {
      left -= 4;
      if (left <= 0 || !isTransformed(player)) {
        safe(() => dome.remove());
        setProp(player, PROP.barrier, 0);
        fx(dim, FX.barrier_break, player.location);
        sound(dim, SOUND.barrier_hit, player.location, { pitch: 1.4, volume: 0.6 });
        system.clearRun(follow);
        return;
      }
      safe(() => dome.teleport({ x: player.location.x, y: player.location.y + 0.2, z: player.location.z }));
      // ドームに触れた矢や弾を弾き返す
      const shots = safe(() => dim.getEntities({
        location: player.location, maxDistance: 3.6,
      })) ?? [];
      for (const s of shots) {
        if (!s.typeId?.includes("arrow") && !s.typeId?.includes("fireball")
            && !s.typeId?.includes("_bolt") && !s.typeId?.includes("beam")) continue;
        const away = normalise(sub(s.location, player.location));
        safe(() => s.applyImpulse(scale(away, 1.4)));
        fx(dim, FX.barrier_hex, s.location);
        sound(dim, SOUND.barrier_hit, s.location, { volume: 0.5, pitch: 1.8 });
      }
    }, 4);
  }
  return true;
};

// --- 7. 鋼鉄拘束 -------------------------------------------------------------
ACTION.iron_bind = (player) => {
  const dim = player.dimension;
  const target = lookTarget(player, 24);
  if (!target.entity) { tell(player, tr("msg.no_target")); return false; }

  const e = target.entity;
  const cage = safe(() => dim.spawnEntity(ENTITY.iron_cage, e.location));
  safe(() => e.addTag("marvel_bound"));
  safe(() => e.addEffect("slowness", 120, { amplifier: 6, showParticles: false }));
  safe(() => e.addEffect("weakness", 120, { amplifier: 2, showParticles: false }));
  fx(dim, FX.bind_weld, e.location);
  fxRing(dim, FX.mag_spark, e.location, 1.2, 10, 0.4);
  chord(dim, e.location, [[SOUND.bind, 0, { volume: 1.0, pitch: 0.8 }],
                          [SOUND.metal_hit, 6, { volume: 0.7, pitch: 1.1 }]]);
  drawFieldLines(dim, player.getHeadLocation(), [e.location]);

  let left = 120;
  const keep = system.runInterval(() => {
    left -= 5;
    if (left <= 0 || !safe(() => e.isValid?.() !== false)) {
      safe(() => cage?.remove());
      safe(() => e.removeTag("marvel_bound"));
      system.clearRun(keep);
      return;
    }
    safe(() => cage?.teleport(e.location));
    safe(() => e.teleport(cage ? cage.location : e.location));
    fx(dim, FX.bind_weld, e.location);
  }, 5);
  return true;
};

// --- 8. 磁気圧壊 -------------------------------------------------------------
ACTION.crush = (player) => {
  const dim = player.dimension;
  const target = lookTarget(player, 22);
  if (!target.entity) { tell(player, tr("msg.no_target")); return false; }

  const e = target.entity;
  const metal = metalOn(e);
  const p = power(player);
  if (metal <= 0) {
    tell(player, tr("msg.immune"));
    fx(dim, FX.mag_glyph, e.location);
    sound(dim, SOUND.ui_select, e.location, { pitch: 0.5 });
    hit(player, e, 4 * p);
    return true;
  }
  const damage = (10 + metal * 9) * p;
  fx(dim, FX.crush_implode, e.location);
  fx(dim, FX.crush_blood, { x: e.location.x, y: e.location.y + 1.0, z: e.location.z });
  fxRing(dim, FX.mag_spark, e.location, 1.0, 10, 0.6);
  chord(dim, e.location, [[SOUND.crush, 0, { volume: 1.2, pitch: 0.7 }],
                          [SOUND.metal_hit, 3, { volume: 0.9, pitch: 0.9 }]]);
  hit(player, e, damage);
  hitstop(e, 8);
  shake(player, 0.32, 0.4);
  shakeNearby(dim, e.location, 10, 0.28, 0.4);
  stripEquipment(e, dim);
  return true;
};

// --- 9. 大地隆起 -------------------------------------------------------------
ACTION.uprising = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const dir = player.getViewDirection();
  const p = power(player);
  const centre = forward({ x: at.x, y: at.y, z: at.z }, dir, 6);

  fx(dim, FX.uprising_soil, centre);
  fxRing(dim, FX.uprising_pillar, centre, 2.6, 8, 0.2);
  chord(dim, centre, [[SOUND.uprising, 0, { volume: 1.3, pitch: 0.75 }],
                      [SOUND.metal_hit, 8, { volume: 0.9, pitch: 0.8 }]]);
  shake(player, 0.4, 0.6);
  shakeNearby(dim, centre, 16, 0.34, 0.6);

  // 地中の金属を柱にして突き上げる
  const found = scanMetal(dim, centre, 8, 20);
  let raised = 0;
  for (const m of found) {
    if (raised >= 10) break;
    const shard = ripBlock(dim, { x: m.x, y: m.y, z: m.z }, player.id);
    if (!shard) continue;
    safe(() => shard.applyImpulse({ x: (Math.random() - 0.5) * 0.3, y: 1.4, z: (Math.random() - 0.5) * 0.3 }));
    system.runTimeout(() => safe(() => shard.remove()), 70);
    raised++;
  }
  for (const e of safe(() => dim.getEntities({ location: centre, maxDistance: 7 })) ?? []) {
    if (!hostile(e, player)) continue;
    hit(player, e, (14 + raised * 1.6) * p);
    knock(e, { x: 0, y: 1, z: 0 }, 0.5, 1.35);
    fx(dim, FX.debris_chunk, e.location);
  }
  return true;
};

// --- 10. EMPパルス -----------------------------------------------------------
ACTION.emp = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const p = power(player);

  fx(dim, FX.emp_wave, at);
  fxRing(dim, FX.emp_arc, at, 3.0, 14, 0.6);
  chord(dim, at, [[SOUND.emp, 0, { volume: 1.2, pitch: 1.3 }],
                  [SOUND.mag_release, 8, { volume: 0.8, pitch: 1.9 }]]);
  shake(player, 0.28, 0.5);

  let hits = 0;
  for (const e of safe(() => dim.getEntities({ location: at, maxDistance: 18 })) ?? []) {
    if (!hostile(e, player)) continue;
    const machine = hasFamily(e, FAMILY.sentinel);
    const metal = metalOn(e);
    if (!machine && metal <= 0) continue;
    hit(player, e, (machine ? 34 : 6 + metal * 4) * p);
    safe(() => e.addEffect("slowness", machine ? 160 : 80, { amplifier: 4 }));
    safe(() => e.addEffect("weakness", machine ? 160 : 80, { amplifier: 2 }));
    safe(() => e.addTag("marvel_emp"));
    fx(dim, FX.emp_arc, e.location);
    fx(dim, FX.sentinel_spark, e.location);
    hits++;
  }
  // レッドストーン機構も黙らせる（演出として周囲を暗転させる）
  fxSphere(dim, FX.emp_arc, at, 6, 16);
  return hits >= 0;
};

// --- 11. 磁極反転 ------------------------------------------------------------
ACTION.polarity = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const duration = 120;

  fx(dim, FX.polarity_field, at);
  fxSphere(dim, FX.mag_glyph, { x: at.x, y: at.y + 2.0, z: at.z }, 5.0, 18);
  chord(dim, at, [[SOUND.polarity, 0, { volume: 1.0, pitch: 0.8 }],
                  [SOUND.mag_charge, 6, { volume: 0.8, pitch: 1.7 }]]);
  shake(player, 0.24, 0.6);

  const victims = [];
  for (const e of safe(() => dim.getEntities({ location: at, maxDistance: 12 })) ?? []) {
    if (!hostile(e, player)) continue;
    victims.push(e);
    safe(() => e.addEffect("levitation", duration, { amplifier: 1 }));
    safe(() => e.addEffect("slow_falling", duration + 60, { amplifier: 0, showParticles: false }));
    fx(dim, FX.tk_lift, e.location);
  }
  let left = duration;
  const hold = system.runInterval(() => {
    left -= 6;
    if (left <= 0) { system.clearRun(hold); return; }
    for (const e of victims) {
      if (!safe(() => e.isValid?.() !== false)) continue;
      fx(dim, FX.mag_glyph, e.location);
    }
  }, 6);
  return true;
};

// --- 12. 磁気飛行 ------------------------------------------------------------
ACTION.flight = (player) => {
  const dim = player.dimension;
  const flying = num(player, PROP.flying, 0) === 1;
  if (flying) {
    setProp(player, PROP.flying, 0);
    sound(dim, SOUND.revert, player.location, { pitch: 1.4, volume: 0.6 });
    return true;
  }
  setProp(player, PROP.flying, 1);
  fx(dim, FX.flight_burst, player.location);
  fxRing(dim, FX.levitate_dust, player.location, 1.4, 10, 0.1);
  chord(dim, player.location, [[SOUND.flight, 0, { volume: 1.0, pitch: 1.1 }],
                               [SOUND.mag_charge, 4, { volume: 0.5, pitch: 1.6 }]]);
  safe(() => player.applyImpulse({ x: 0, y: 0.9, z: 0 }));
  return true;
};

// --- 13. 鋼鉄の玉座 ----------------------------------------------------------
ACTION.throne = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const platform = safe(() => dim.spawnEntity(ENTITY.steel_platform,
    { x: at.x, y: at.y - 0.2, z: at.z }));
  if (!platform) return false;
  fx(dim, FX.throne_dust, at);
  fxRing(dim, FX.mag_spark, at, 1.8, 10, 0.2);
  chord(dim, at, [[SOUND.metal_hit, 0, { volume: 0.9, pitch: 0.8 }],
                  [SOUND.mag_charge, 5, { volume: 0.7, pitch: 1.3 }]]);
  system.runTimeout(() => {
    safe(() => platform.getComponent("minecraft:rideable")?.addRider(player));
  }, 6);
  system.runTimeout(() => safe(() => platform.remove()), 900);
  return true;
};

// --- 14. 磁力視 --------------------------------------------------------------
ACTION.sight = (player) => {
  const dim = player.dimension;
  const duration = 200 + stageOf(player) * 60;
  setProp(player, PROP.sight, system.currentTick + duration);
  const found = revealMetal(player, 22);
  safe(() => player.addEffect("night_vision", duration + 40, { amplifier: 0, showParticles: false }));
  sound(dim, SOUND.sight, player.location, { volume: 0.8, pitch: 1.4 });
  fx(dim, FX.sight_ping, player.getHeadLocation());
  tell(player, { rawtext: [{ translate: "marvel.msg.scan" }, { text: ` §b${found}` }] });
  return true;
};

// --- 15. 磁界の棺（必殺技）---------------------------------------------------
ACTION.sphere = (player) => {
  const dim = player.dimension;
  const at = { x: player.location.x, y: player.location.y + 3.4, z: player.location.z };
  const p = power(player);

  title(player, tr("title.ultimate"), tr("title.ultimate_sub"), 6, 44, 20);
  fade(player, { red: 0.85, green: 0.20, blue: 0.42 }, 0.14, 0.10, 0.6);
  chord(dim, player.location, [
    [SOUND.sphere_charge, 0, { volume: 1.4, pitch: 0.8 }],
    [SOUND.mag_charge, 10, { volume: 1.0, pitch: 1.2 }],
  ]);

  const sphere = safe(() => dim.spawnEntity(ENTITY.ruin_sphere, at));
  const dragged = [];

  // --- 溜め: 半径 40 の金属を全部引き寄せる
  let ticks = 0;
  const charge = system.runInterval(() => {
    ticks += 4;
    const centre = { x: player.location.x, y: player.location.y + 3.4, z: player.location.z };
    safe(() => sphere?.teleport(centre));
    fxSphere(dim, FX.sphere_orbit, centre, 3.6 - ticks * 0.02, 10);
    fx(dim, FX.sphere_core, centre);
    shake(player, 0.12 + ticks * 0.004, 0.3);

    if (ticks === 8) {
      for (const m of scanMetal(dim, player.location, 40, 40)) {
        const shard = ripBlock(dim, { x: m.x, y: m.y, z: m.z }, player.id);
        if (shard) dragged.push(shard);
      }
      pullItems(dim, player.location, 40, centre, 1.2);
    }
    for (const s of dragged) {
      if (!safe(() => s.isValid?.() !== false)) continue;
      drag(s, centre, 1.1, 0.3);
      fx(dim, FX.metal_glint, s.location);
    }
    for (const e of safe(() => dim.getEntities({ location: player.location, maxDistance: 30 })) ?? []) {
      if (!hostile(e, player)) continue;
      if (metalOn(e) <= 0) continue;
      drag(e, centre, 0.55, 0.2);
      fxTrail(dim, FX.mag_line, e.location, centre, 1.6);
    }

    if (ticks >= 44) {
      system.clearRun(charge);
      detonate(player, dim, centre, dragged, sphere, p);
    }
  }, 4);
  return true;
};

function detonate(player, dim, centre, dragged, sphere, p) {
  fx(dim, FX.sphere_collapse, centre);
  system.runTimeout(() => {
    fx(dim, FX.sphere_detonate, centre);
    fxSphere(dim, FX.shard_burst, centre, 3.0, 30);
    fxScatter(dim, FX.debris_chunk, centre, 20, 4.0);
    chord(dim, centre, [
      [SOUND.sphere_blast, 0, { volume: 1.6, pitch: 0.7 }],
      [SOUND.repulse, 2, { volume: 1.2, pitch: 0.8 }],
      [SOUND.metal_hit, 5, { volume: 1.0, pitch: 0.6 }],
    ]);
    shake(player, 0.9, 1.2, "rotational");
    shakeNearby(dim, centre, 40, 0.7, 1.0);
    fade(player, { red: 1.0, green: 0.85, blue: 0.95 }, 0.05, 0.05, 0.8);

    for (const e of safe(() => dim.getEntities({ location: centre, maxDistance: 22 })) ?? []) {
      if (!hostile(e, player)) continue;
      const metal = metalOn(e);
      const d = distance(e.location, centre);
      const damage = (60 + metal * 20) * p * Math.max(0.25, 1 - d / 24);
      hit(player, e, damage);
      knock(e, normalise(sub(e.location, centre)), 3.2, 1.1);
      fx(dim, FX.crush_implode, e.location);
      hitstop(e, 10);
    }
    // 集めた鉄片を四方へ撃ち出す
    for (const s of dragged) {
      if (!safe(() => s.isValid?.() !== false)) continue;
      safe(() => s.applyImpulse({
        x: (Math.random() - 0.5) * 3.4, y: Math.random() * 1.6,
        z: (Math.random() - 0.5) * 3.4,
      }));
      system.runTimeout(() => safe(() => s.remove()), 50);
    }
    safe(() => sphere?.remove());
  }, 10);
}

// ===========================================================================
//  発動口
// ===========================================================================
export function useTechnique(player, techKey) {
  const spec = TECH[techKey];
  if (!spec) return false;
  if (!isTransformed(player)) {
    tell(player, tr("msg.no_power"));
    return false;
  }
  if (stageOf(player) < spec.stage) {
    tell(player, tr("msg.locked"));
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 0.5 });
    return false;
  }
  if (!cooldowns.ready(player.id, techKey)) {
    const left = Math.ceil(cooldowns.remaining(player.id, techKey) / 20);
    tell(player, { rawtext: [{ translate: "marvel.msg.cooldown" }, { text: ` §7${left}s` }] });
    return false;
  }
  if (magOf(player) < spec.cost) {
    tell(player, tr("msg.no_mag"));
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 0.4 });
    return false;
  }

  // 1. 三人称の構えへ差し替える（＝技アニメーションの再生）
  pose(player, spec.form, spec.hold || 22);
  setProp(player, PROP.tech, techKey);

  // 2. 構えの「溜め」が乗ってから効果を出す。撃発と画が合う。
  const delay = spec.ultimate ? 10 : Math.max(3, Math.round((spec.hold || 22) * 0.32));
  system.runTimeout(() => {
    safe(() => ACTION[techKey]?.(player));
  }, delay);

  cooldowns.set(player.id, techKey, spec.cd);
  spendMag(player, spec.cost);
  return true;
}

export function techniqueOf(itemId) {
  for (const [key, spec] of Object.entries(TECH)) {
    if (spec.item === itemId) return key;
  }
  return undefined;
}
