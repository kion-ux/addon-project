// 怪獣の要塞度表示・討伐記録・識別怪獣のAI補強・味方の技
import { world, system } from "@minecraft/server";
import { FORTITUDE, IDENTIFIED, PROP, RANKS } from "./config.js";
import {
  tr, tell, actionbar, hasFamily, health, num, bar, allPlayers, distance,
  onCooldown, setCooldown, forward,
} from "./util.js";
import {
  fx, fxRing, fxLine, fxScatter, sound, shakeNearby, hit, bleed, later,
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

const ALLY_TECH = {
  // 亜白ミナ: 識別怪獣兵器2号の狙撃
  "kaiju8:mina_ashiro": { range: 30, cd: 5, run: beamShot(30, 26, 1.6) },
  "kaiju8:gen_narumi": { range: 26, cd: 4, run: beamShot(26, 20, 1.4) },
  "kaiju8:isao_shinomiya": { range: 30, cd: 4, run: beamShot(30, 24, 1.5) },
  "kaiju8:haruichi_izumo": { range: 22, cd: 5, run: beamShot(22, 12, 1.2) },
  // 保科宗四郎: 双刃刀の連撃
  "kaiju8:soshiro_hoshina": {
    range: 5.5, cd: 4,
    run(ally, target) {
      for (let i = 0; i < 3; i++) {
        later(i * 3, () => {
          try {
            fx(ally.dimension, "kaiju8:slash_air",
               { x: target.location.x, y: target.location.y + 1.1, z: target.location.z });
            if (hit(ally, target, 9)) bleed(target);
            sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.5 });
          } catch (_) { }
        });
      }
    },
  },
  // 神楽木葵: 隊内随一の膂力
  "kaiju8:aoi_kaguragi": {
    range: 4.8, cd: 6,
    run(ally, target) {
      const g = { x: target.location.x, y: target.location.y + 0.1, z: target.location.z };
      fx(ally.dimension, "kaiju8:shock_ring_gold", g);
      fxScatter(ally.dimension, "kaiju8:impact_dust", g, 6, 1.2);
      if (hit(ally, target, 16)) bleed(target);
      sound(ally.dimension, "random.anvil_land", ally.location, { pitch: 0.7 });
    },
  },
  // 古橋伊春
  "kaiju8:iharu_furuhashi": {
    range: 4.5, cd: 4,
    run(ally, target) {
      fx(ally.dimension, "kaiju8:slash_air",
         { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
      if (hit(ally, target, 11)) bleed(target);
      sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.3 });
    },
  },
  // 四ノ宮キコル: 大型戦斧の叩きつけ
  "kaiju8:kikoru_shinomiya": {
    range: 5.0, cd: 6,
    run(ally, target) {
      const g = { x: target.location.x, y: target.location.y + 0.1, z: target.location.z };
      fx(ally.dimension, "kaiju8:shock_ring_gold", g);
      fxScatter(ally.dimension, "kaiju8:impact_dust", g, 8, 1.4);
      fxScatter(ally.dimension, "kaiju8:debris", g, 6, 1.0);
      if (hit(ally, target, 20)) bleed(target);
      sound(ally.dimension, "random.anvil_land", ally.location, { pitch: 0.6 });
      shakeNearby(ally.dimension, g, 10, 0.22, 0.35);
    },
  },
  // 日比野カフカ / 市川レノ / 一般隊員
  "kaiju8:kafka_hibino": {
    range: 4.5, cd: 5,
    run(ally, target) {
      fx(ally.dimension, "kaiju8:slash_air",
         { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
      if (hit(ally, target, 10)) bleed(target);
      sound(ally.dimension, "mob.ravager.bite", ally.location, { pitch: 1.2 });
    },
  },
};

function beamShot(range, damage, spread) {
  return (ally, target) => {
    const dir = toward(ally, target);
    const eye = { x: ally.location.x, y: ally.location.y + 1.4, z: ally.location.z };
    fxLine(ally.dimension, "kaiju8:beam_trail", eye, dir, range, 1.4);
    fx(ally.dimension, "kaiju8:muzzle_flash", forward(eye, dir, 1.0));
    if (hit(ally, target, damage)) bleed(target);
    fxScatter(ally.dimension, "kaiju8:beam_impact",
              { x: target.location.x, y: target.location.y + 1, z: target.location.z },
              6, 0.8);
    sound(ally.dimension, "mob.wither.shoot", ally.location, { pitch: 0.8, volume: 1.1 });
  };
}

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
      try { spec.run(ally, target); } catch (_) { }
    }
  }
}
