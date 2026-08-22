// 怪獣の要塞度表示・討伐記録・識別怪獣のAI補強・味方の技
import { world, system } from "@minecraft/server";
import { FORTITUDE, IDENTIFIED, PROP, RANKS } from "./config.js";
import {
  tr, tell, actionbar, hasFamily, health, num, bar, allPlayers, distance,
  onCooldown, setCooldown, forward,
} from "./util.js";
import {
  fx, fxRing, fxLine, fxScatter, fxArc, fxCone, fxWall, fxColumn, sequence,
  sound, shakeNearby, targetsNear, hit, bleed, later,
} from "./effects.js";
import { wearsFullSuit } from "./weapons.js";

export function fortitudeOf(entity) {
  return FORTITUDE[entity.typeId];
}

export function isKaijuType(entity) {
  return entity.typeId in FORTITUDE || hasFamily(entity, "kaiju");
}

/** 余獣は個別に測定されないので "--"。 */
function fortitudeText(value) {
  return value === null || value === undefined ? "--" : value.toFixed(1);
}

export function rankKey(kills) {
  let key = RANKS[0][1];
  for (const [threshold, k] of RANKS) if (kills >= threshold) key = k;
  return key;
}

function objective() {
  try {
    return world.scoreboard.getObjective("kaiju8_kills")
      ?? world.scoreboard.addObjective("kaiju8_kills", "討伐数");
  } catch (_) { return undefined; }
}

// ===========================================================================
//  要塞度スキャン + 被弾リアクション
// ===========================================================================
world.afterEvents.entityHurt.subscribe((ev) => {
  const target = ev.hurtEntity;
  const source = ev.damageSource?.damagingEntity;
  if (!target) return;
  const isKaiju = isKaijuType(target);

  if (isKaiju || hasFamily(target, "defense_force")) {
    if (!onCooldown(target.id, "flash")) {
      setCooldown(target.id, "flash", 14);
      system.run(() => {
        try { target.triggerEvent("kaiju8:hurt_flash"); } catch (_) { }
      });
      if (isKaiju) bleed(target);
    }
  }
  // 戦闘服の遠隔シールド — 管制室からの被弾緩和演出
  if (target.typeId === "minecraft:player" && ev.damage >= 6 &&
      wearsFullSuit(target) && !onCooldown(target.id, "shield")) {
    setCooldown(target.id, "shield", 60);
    fxScatter(target.dimension, "kaiju8:suit_shield",
              { x: target.location.x, y: target.location.y + 1.0, z: target.location.z },
              6, 1.0);
  }
  if (!isKaiju || source?.typeId !== "minecraft:player") return;

  const fort = fortitudeOf(target);
  const hp = health(target);
  if (!hp) return;
  const ratio = hp.max > 0 ? hp.now / hp.max : 0;
  const identified = IDENTIFIED.has(target.typeId);
  const colour = identified ? "§c" : ratio > 0.5 ? "§a" : "§e";
  actionbar(source, {
    rawtext: [
      { translate: `entity.${target.typeId}.name` },
      { text: `  §7要塞度§r ${identified ? "§c" : "§6"}${fortitudeText(fort)}§r  ` },
      { text: `${colour}${bar(ratio, 10)}§r ${hp.now}/${hp.max}` },
    ],
  });
});

// ===========================================================================
//  討伐記録
// ===========================================================================
world.afterEvents.entityDie.subscribe((ev) => {
  const dead = ev.deadEntity;
  const killer = ev.damageSource?.damagingEntity;
  if (!dead) return;
  if (isKaijuType(dead)) {
    try {
      fxScatter(dead.dimension, "kaiju8:kaiju_blood",
                { x: dead.location.x, y: dead.location.y + 1, z: dead.location.z },
                10, 1.0);
      if (IDENTIFIED.has(dead.typeId)) {
        fx(dead.dimension, "kaiju8:core_break", dead.location);
        fxScatter(dead.dimension, "kaiju8:transform_smoke", dead.location, 14, 1.8);
      }
    } catch (_) { }
  }
  if (killer?.typeId !== "minecraft:player") return;
  if (!isKaijuType(dead)) return;

  system.run(() => {
    const kills = num(killer, PROP.kills, 0) + 1;
    killer.setDynamicProperty(PROP.kills, kills);
    try { objective()?.setScore(killer, kills); } catch (_) { }
    const before = rankKey(kills - 1);
    const now = rankKey(kills);
    tell(killer, {
      rawtext: [
        { translate: "kaiju8.msg.subjugated",
          with: { rawtext: [{ translate: `entity.${dead.typeId}.name` }] } },
        { text: `  §7(${kills})` },
      ],
    });
    if (before !== now) {
      sound(killer.dimension, "random.levelup", killer.location);
      try {
        killer.onScreenDisplay.setTitle(tr("kaiju8.title.promoted"), {
          fadeInDuration: 6, stayDuration: 40, fadeOutDuration: 14,
          subtitle: { rawtext: [{ translate: now }] },
        });
      } catch (_) { }
    }
    if (IDENTIFIED.has(dead.typeId)) {
      for (const p of allPlayers()) {
        tell(p, {
          rawtext: [{
            translate: "kaiju8.msg.identified_down",
            with: { rawtext: [{ translate: `entity.${dead.typeId}.name` }] },
          }],
        });
      }
    }
  });
});

// ===========================================================================
//  識別怪獣の追加AI
// ===========================================================================
let phase = 0;

export function tickKaiju() {
  phase++;
  const seen = new Set();
  for (const player of allPlayers()) {
    let kaiju;
    try {
      kaiju = player.dimension.getEntities({
        location: player.location, maxDistance: 72, families: ["identified_kaiju"],
      });
    } catch (_) { continue; }
    for (const k of kaiju) {
      if (seen.has(k.id)) continue;
      seen.add(k.id);
      try { driveIdentified(k); } catch (_) { }
    }
  }
}

function driveIdentified(k) {
  if (phase % 27 === 0 && Math.random() < 0.5) {
    try { k.triggerEvent("kaiju8:roar"); } catch (_) { }
    sound(k.dimension, "mob.enderdragon.growl", k.location,
          { volume: 2.4, pitch: 0.55 });
    fx(k.dimension, "kaiju8:roar_wave",
       { x: k.location.x, y: k.location.y + 2.0, z: k.location.z });
    fxRing(k.dimension, "kaiju8:kaiju_aura", k.location, 2.5, 12, 0.5);
    shakeNearby(k.dimension, k.location, 20, 0.30, 0.7);
    for (const p of allPlayers()) {
      if (p.dimension.id !== k.dimension.id) continue;
      if (distance(p.location, k.location) > 16) continue;
      try {
        p.addEffect("slowness", 50, { amplifier: 1, showParticles: true });
        p.addEffect("nausea", 70, { amplifier: 0, showParticles: false });
      } catch (_) { }
    }
  }

  if (k.typeId === "kaiju8:kaiju_no9") {
    try { k.addEffect("regeneration", 60, { amplifier: 1, showParticles: false }); }
    catch (_) { }
    if (phase % 4 === 0) {
      fx(k.dimension, "kaiju8:regen_knit",
         { x: k.location.x, y: k.location.y + 1.6, z: k.location.z });
      fx(k.dimension, "kaiju8:no9_regen",
         { x: k.location.x, y: k.location.y + 1.2, z: k.location.z });
    }
    if (phase % 9 === 0) {
      let brood = 0;
      try {
        brood = k.dimension.getEntities({
          location: k.location, maxDistance: 26, type: "kaiju8:yoju",
        }).length;
      } catch (_) { }
      if (brood < 5) {
        for (let i = 0; i < 2; i++) {
          const loc = {
            x: k.location.x + (Math.random() - 0.5) * 6,
            y: k.location.y + 1,
            z: k.location.z + (Math.random() - 0.5) * 6,
          };
          try { k.dimension.spawnEntity("kaiju8:yoju", loc); } catch (_) { }
          fxScatter(k.dimension, "kaiju8:transform_smoke", loc, 8, 0.8);
        }
        sound(k.dimension, "mob.evocation_illager.prepare_summon", k.location,
              { pitch: 0.55 });
      }
    }
  }

  if (k.typeId === "kaiju8:kaiju_no10" && phase % 4 === 0) {
    fx(k.dimension, "kaiju8:kaiju10_seam",
       { x: k.location.x, y: k.location.y + 1.6, z: k.location.z });
  }

  if (k.typeId === "kaiju8:kaiju_no8" && phase % 3 === 0) {
    try { k.addEffect("regeneration", 60, { amplifier: 0, showParticles: false }); }
    catch (_) { }
    fx(k.dimension, "kaiju8:no8_aura",
       { x: k.location.x, y: k.location.y + 1.4, z: k.location.z });
    fx(k.dimension, "kaiju8:seam_glow",
       { x: k.location.x, y: k.location.y + 0.9, z: k.location.z });
  }
}

// ===========================================================================
//  味方の技 — 隊員が本当にキャラクターらしく戦う
// ===========================================================================
function nearestKaiju(ally, radius) {
  try {
    const found = ally.dimension.getEntities({
      location: ally.location, maxDistance: radius, families: ["kaiju"],
    });
    if (!found.length) return undefined;
    found.sort((a, b) => distance(ally.location, a.location)
                       - distance(ally.location, b.location));
    return found[0];
  } catch (_) { return undefined; }
}

function toward(from, to) {
  const dx = to.location.x - from.location.x;
  const dy = (to.location.y + 1) - (from.location.y + 1.4);
  const dz = to.location.z - from.location.z;
  const len = Math.hypot(dx, dy, dz) || 1;
  return { x: dx / len, y: dy / len, z: dz / len };
}

// ===========================================================================
//  味方隊員の技
//  隊員はモーションを一の型／二の型で交互に出すので、演出もそれに合わせて
//  二種類持たせる。同じ「斬撃線ひとつ」が全員から出ていた状態をやめる。
//  run(ally, target, second) — second が true なら二の型。
// ===========================================================================
function eye(ally) {
  return { x: ally.location.x, y: ally.location.y + 1.4, z: ally.location.z };
}

function nearby(ally, target, radius, damage, each) {
  for (const t of targetsNear(ally, radius)) {
    if (t.id !== target.id && !hasFamily(t, "kaiju")) continue;
    if (hit(ally, t, damage)) bleed(t);
    if (each) each(t);
  }
}

function above(target, y = 1.1) {
  return { x: target.location.x, y: target.location.y + y, z: target.location.z };
}

function groundAt(target) {
  return { x: target.location.x, y: target.location.y + 0.1, z: target.location.z };
}

/** 狙撃: 一条の射線を通す。 */
function snipe(range, damage, beam, impact, snd, pitch) {
  return (ally, target) => {
    const dir = toward(ally, target);
    const from = eye(ally);
    fxLine(ally.dimension, beam, from, dir, range, 1.1);
    fx(ally.dimension, "kaiju8:muzzle_flash", forward(from, dir, 1.0));
    if (hit(ally, target, damage)) bleed(target);
    fxScatter(ally.dimension, impact, above(target), 7, 0.8);
    sound(ally.dimension, snd, ally.location, { pitch, volume: 1.1 });
  };
}

/** 斉射: 何発かに分けて撃ち込む。 */
function volley(shots, gap, range, damage, muzzle, impact, snd, pitch) {
  return (ally, target) => {
    const steps = [];
    for (let i = 0; i < shots; i++) {
      steps.push([i * gap, () => {
        const dir = toward(ally, target);
        const from = eye(ally);
        fx(ally.dimension, muzzle, forward(from, dir, 1.0));
        fxLine(ally.dimension, "kaiju8:beam_trail", from, dir, range, 1.8);
        if (hit(ally, target, damage)) bleed(target);
        fxWall(ally.dimension, impact, above(target, 0.9), dir, 0.2, 1.8, 1.8, 3, 2);
        sound(ally.dimension, snd, ally.location,
              { pitch: pitch + i * 0.06, volume: 0.95 });
      }]);
    }
    sequence(steps);
  };
}

/** 連撃: 弧を描いて何度も斬る。 */
function flurry(times, gap, damage, arcs, snd, pitch, radius) {
  return (ally, target) => {
    const steps = [];
    for (let i = 0; i < times; i++) {
      steps.push([i * gap, () => {
        const dir = toward(ally, target);
        fxArc(ally.dimension, arcs[i % arcs.length], eye(ally), dir, radius,
              150, 5, i % 2 ? -0.4 : 0.4);
        if (hit(ally, target, damage)) bleed(target);
        sound(ally.dimension, snd, ally.location,
              { pitch: pitch + (i % 3) * 0.09, volume: 0.85 });
      }]);
    }
    sequence(steps);
  };
}

/** 叩きつけ: 地面を割る。 */
function smash(damage, radius, ring, snd, pitch, quake) {
  return (ally, target) => {
    const g =groundAt(target);
    fx(ally.dimension, ring, g);
    fxScatter(ally.dimension, "kaiju8:impact_dust", g, 9, 1.5);
    fxScatter(ally.dimension, "kaiju8:debris", g, 7, 1.1);
    fxColumn(ally.dimension, "kaiju8:crack_burst", g, 2.4, 5, 0.5);
    nearby(ally, target, radius, damage);
    sound(ally.dimension, snd, ally.location, { pitch, volume: 1.2 });
    shakeNearby(ally.dimension, g, 12, quake, 0.38);
  };
}

/** 薙ぎ払い: 横一線に払う。 */
function sweep(damage, radius, arc, snd, pitch) {
  return (ally, target) => {
    const dir = toward(ally, target);
    fxArc(ally.dimension, arc, eye(ally), dir, radius * 0.7, 175, 9, -0.2);
    nearby(ally, target, radius, damage,
           (t) => fxScatter(ally.dimension, "kaiju8:crack_burst", above(t), 4, 0.7));
    sound(ally.dimension, snd, ally.location, { pitch, volume: 1.1 });
    shakeNearby(ally.dimension, ally.location, 9, 0.16, 0.3);
  };
}

export const ALLY_TECH = {
  // ---- 亜白ミナ: 狙撃と斉射 ------------------------------------------
  "kaiju8:mina_ashiro": {
    range: 30, cd: 5,
    one: snipe(30, 30, "kaiju8:railgun_lance", "kaiju8:beam_impact",
               "mob.wither.death", 1.35),
    two: volley(3, 5, 30, 13, "kaiju8:cannon_muzzle", "kaiju8:beam_impact",
                "mob.wither.shoot", 0.75),
  },
  // ---- 四ノ宮功: 斉射のあとに一撃 ------------------------------------
  "kaiju8:isao_shinomiya": {
    range: 30, cd: 4,
    one: volley(3, 4, 30, 12, "kaiju8:cannon_muzzle", "kaiju8:impact_dust",
                "mob.wither.shoot", 0.65),
    two: snipe(30, 28, "kaiju8:railgun_lance", "kaiju8:beam_impact",
               "mob.wither.death", 1.15),
  },
  // ---- 鳴海弦: 銃剣の乱撃と、刺してから撃つ刺突 -----------------------
  "kaiju8:gen_narumi": {
    range: 26, cd: 4,
    one: flurry(5, 2, 9, ["kaiju8:burst_slash", "kaiju8:slash_heavy"],
                "mob.ravager.bite", 1.7, 2.4),
    two(ally, target) {
      const dir = toward(ally, target);
      sequence([
        [0, () => {
          fxLine(ally.dimension, "kaiju8:slash_heavy", eye(ally), dir, 4.5, 1.5);
          sound(ally.dimension, "item.trident.riptide_1", ally.location,
                { pitch: 1.5 });
        }],
        [4, () => {
          if (hit(ally, target, 22)) bleed(target);
          fxScatter(ally.dimension, "kaiju8:cauterize", above(target), 10, 0.7);
          fx(ally.dimension, "kaiju8:muzzle_flash", above(target, 0.9));
          sound(ally.dimension, "random.explode", ally.location,
                { pitch: 1.3, volume: 1.0 });
          shakeNearby(ally.dimension, target.location, 10, 0.2, 0.3);
        }],
      ]);
    },
  },
  // ---- 出雲ハルイチ: 制圧射撃と精密射撃 ------------------------------
  "kaiju8:haruichi_izumo": {
    range: 22, cd: 5,
    one: volley(5, 2, 22, 5, "kaiju8:muzzle_flash", "kaiju8:impact_dust",
                "random.explode", 1.6),
    two: snipe(22, 16, "kaiju8:beam_trail", "kaiju8:beam_impact",
               "mob.wither.shoot", 1.1),
  },
  // ---- 市川レノ: 精密射撃と速射 --------------------------------------
  "kaiju8:reno_ichikawa": {
    range: 22, cd: 5,
    one: snipe(22, 15, "kaiju8:beam_trail", "kaiju8:beam_impact",
               "mob.wither.shoot", 1.25),
    two: volley(2, 3, 22, 9, "kaiju8:muzzle_flash", "kaiju8:impact_dust",
                "random.explode", 1.75),
  },
  // ---- 一般隊員 ------------------------------------------------------
  "kaiju8:defense_force_officer": {
    range: 20, cd: 6,
    one: snipe(20, 10, "kaiju8:beam_trail", "kaiju8:impact_dust",
               "mob.wither.shoot", 1.4),
    two: volley(4, 2, 20, 4, "kaiju8:muzzle_flash", "kaiju8:impact_dust",
                "random.explode", 1.7),
  },
  // ---- 保科宗四郎: 二刀の連撃と八重討ち --------------------------------
  "kaiju8:soshiro_hoshina": {
    range: 5.5, cd: 4,
    one: flurry(3, 3, 9, ["kaiju8:slash_air", "kaiju8:slash_cross"],
                "mob.ravager.bite", 1.55, 1.9),
    two(ally, target) {
      // 八重討ち。的の周りを回りながら八度斬る
      const steps = [];
      for (let i = 0; i < 8; i++) {
        steps.push([i * 2, () => {
          const a = (i / 8) * Math.PI * 2;
          fx(ally.dimension, "kaiju8:slash_air", {
            x: target.location.x + Math.cos(a) * 1.5,
            y: target.location.y + 0.6 + (i % 3) * 0.55,
            z: target.location.z + Math.sin(a) * 1.5,
          });
          if (hit(ally, target, 7)) bleed(target);
          sound(ally.dimension, "mob.ravager.bite", ally.location,
                { pitch: 1.35 + (i % 4) * 0.12, volume: 0.8 });
        }]);
      }
      steps.push([17, () => {
        fxScatter(ally.dimension, "kaiju8:slash_scatter", above(target), 14, 1.2);
        shakeNearby(ally.dimension, target.location, 10, 0.24, 0.35);
      }]);
      sequence(steps);
    },
  },
  // ---- 四ノ宮キコル: 叩きつけと薙ぎ払い --------------------------------
  "kaiju8:kikoru_shinomiya": {
    range: 5.0, cd: 6,
    one: smash(22, 4.2, "kaiju8:shock_ring_gold", "random.anvil_land", 0.6, 0.26),
    two: sweep(17, 5.4, "kaiju8:axe_crescent", "random.anvil_land", 1.2),
  },
  // ---- 神楽木葵: 隊内随一の膂力。薙ぎが先、返しが叩きつけ ---------------
  "kaiju8:aoi_kaguragi": {
    range: 4.8, cd: 6,
    one: sweep(15, 5.0, "kaiju8:axe_arc", "random.anvil_land", 1.05),
    two: smash(19, 4.0, "kaiju8:shock_ring", "random.anvil_land", 0.5, 0.3),
  },
  // ---- 古橋伊春: 霞討ちと十字斬り --------------------------------------
  "kaiju8:iharu_furuhashi": {
    range: 4.5, cd: 4,
    two(ally, target) {
      const dir = toward(ally, target);
      fx(ally.dimension, "kaiju8:slash_cross", above(target));
      fxArc(ally.dimension, "kaiju8:slash_air", eye(ally), dir, 1.7, 120, 5, 0.5);
      fxArc(ally.dimension, "kaiju8:slash_air", eye(ally), dir, 1.7, 120, 5, -0.5);
      if (hit(ally, target, 13)) bleed(target);
      sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.25 });
    },
    one(ally, target) {
      const dir = toward(ally, target);
      sequence([
        [0, () => {
          fxLine(ally.dimension, "kaiju8:slash_scatter", eye(ally), dir, 4.0, 1.0);
          sound(ally.dimension, "item.trident.riptide_1", ally.location,
                { pitch: 1.8, volume: 0.8 });
        }],
        [3, () => {
          fx(ally.dimension, "kaiju8:slash_air", above(target));
          if (hit(ally, target, 12)) bleed(target);
          sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.5 });
        }],
      ]);
    },
  },
  // ---- 日比野カフカ: 素手の一撃とナイフ --------------------------------
  "kaiju8:kafka_hibino": {
    range: 4.5, cd: 5,
    one(ally, target) {
      fx(ally.dimension, "kaiju8:fist_shock", above(target, 1.0));
      if (hit(ally, target, 12)) bleed(target);
      fxScatter(ally.dimension, "kaiju8:impact_dust",groundAt(target), 5, 0.9);
      sound(ally.dimension, "mob.ravager.stun", ally.location,
            { pitch: 0.95, volume: 1.0 });
    },
    two(ally, target) {
      const dir = toward(ally, target);
      fxArc(ally.dimension, "kaiju8:slash_air", eye(ally), dir, 1.5, 110, 4, 0.3);
      if (hit(ally, target, 10)) bleed(target);
      sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.2 });
    },
  },
};

const techAlt = new Map();   // allyId -> 次は二の型か

export function tickAllies() {
  const seen = new Set();
  for (const player of allPlayers()) {
    let allies;
    try {
      allies = player.dimension.getEntities({
        location: player.location, maxDistance: 48, families: ["defense_force"],
      });
    } catch (_) { continue; }
    for (const ally of allies) {
      if (seen.has(ally.id)) continue;
      seen.add(ally.id);
      const spec = ALLY_TECH[ally.typeId];
      if (!spec) continue;
      if (onCooldown(ally.id, "tech")) continue;
      const target = nearestKaiju(ally, spec.range);
      if (!target) continue;
      setCooldown(ally.id, "tech", spec.cd * 20);
      // 一の型と二の型を交互に出す。同じ振りが続くと嘘くさい
      const second = !techAlt.get(ally.id);
      techAlt.set(ally.id, second);
      try { ally.triggerEvent(second ? "kaiju8:tech2" : "kaiju8:tech"); }
      catch (_) { }
      // モーションと演出を必ず同じ型で揃える
      const run = (second ? spec.two : spec.one) ?? spec.one ?? spec.two;
      try { run(ally, target); } catch (_) { }
    }
  }
}
