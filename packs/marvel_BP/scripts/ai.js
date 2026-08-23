// NPC の振る舞い / what the mobs do when nobody is scripting them
//
// Bedrock の behavior コンポーネントだけでは「技を撃つ」表現ができないので、
// 一秒ごとに近くの NPC を見て、間合いに応じて mark_variant を切り替え、
// 対応するアニメーションと実際の効果をこちらから起こす。
//
// センチネル戦の設計（DIRECTION §7-5）
// -----------------------------------
// 全身金属 = `metalOn 4.0` = 「最高の的」。ただし **一段構えにしない**。
//   * 通常機   : crush か emp で装甲を剥ぐ → `marvel_exposed` 20 秒 → 物理 2 倍。
//                 磁力で開けて、素手で決める。二段になって初めて戦闘になる。
//   * プライム : HP 1400 の 3 段階。**同じ攻略が二度通らない** ように作る。
//                 1 磁力が 100% 通る / 2 適応してドローンを呼ぶ / 3 EMP 無効
//   * アダマンチウム : 磁力が 0 の相手を混ぜる。
//                 **効かない相手がいて初めて、効く快感が立つ。**
import { world, system } from "@minecraft/server";
import { FX, SOUND, FAMILY, ENTITY, PROP, TAG } from "./config.js";
import {
  allPlayers, distance, forward, hasFamily, normalise, safe, sub, title, tr,
} from "./util.js";
import { chord, fade, fx, fxRing, fxScatter, hit, knock, shake, shakeNearby, sound } from "./effects.js";
import { metalOn } from "./magnetism.js";
import {
  damageBonus, T_ADAMANTIUM, T_ADAPTED, T_EXPOSED, T_JAMMED, T_TOWED,
} from "./techniques.js";
import { refreshStage, stageOf } from "./transform.js";

const SENTINELS = new Set([ENTITY.sentinel, ENTITY.prime_sentinel,
                           ENTITY.sentinel_drone]);

//: プライムのフェーズ。タグで持つ。dynamic property と違って
//: エンティティ側の宣言が要らず、/tag で覗けるので調整中に助かる。
const T_PHASE2 = "marvel_phase2";
const T_PHASE3 = "marvel_phase3";
//: アダマンチウム抽選済みの印。毎秒引き直すと個体が点滅する。
const T_ROLLED = "marvel_rolled";

/** mark_variant を切り替えて、対応するアニメーションを再生させる。 */
function act(entity, variant) {
  safe(() => entity.triggerEvent(`marvel:act${variant}`));
}

function has(entity, tag) {
  return safe(() => entity.hasTag(tag)) === true;
}

function healthOf(entity) {
  const c = safe(() => entity.getComponent("minecraft:health"));
  return typeof c?.currentValue === "number" ? c.currentValue : undefined;
}

function nearestTarget(entity, radius) {
  const found = safe(() => entity.dimension.getEntities({
    location: entity.location, maxDistance: radius,
  })) ?? [];
  let best;
  let bestD = Infinity;
  for (const e of found) {
    if (e.id === entity.id) continue;
    const isTarget = e.typeId === "minecraft:player"
      || hasFamily(e, FAMILY.mutant) || hasFamily(e, FAMILY.brotherhood);
    if (!isTarget) continue;
    const d = distance(e.location, entity.location);
    if (d < bestD) { bestD = d; best = e; }
  }
  return best ? { entity: best, distance: bestD } : undefined;
}

// ===========================================================================
//  1. 素手の一撃に乗る倍率
// ===========================================================================
//  ここは **一箇所にまとめる**。コア露出（物理 2 倍）と磁力視（金属持ちへ
//  +20%）を別々の購読で足すと、片方の追撃をもう片方が拾って際限なく増える。
//: 二重計上を防ぐ札。applyDamage は同じ tick に entityHurt を呼び返す。
const amplifying = new Set();

world.afterEvents.entityHurt.subscribe((ev) => {
  const victim = ev.hurtEntity;
  const attacker = ev.damageSource?.damagingEntity;
  if (!victim || attacker?.typeId !== "minecraft:player") return;
  // 追撃自身は cause が "override" なので、ここで確実に弾かれる。
  if (ev.damageSource.cause !== "entityAttack") return;
  if (ev.damage <= 0 || amplifying.has(victim.id)) return;

  let extra = 0;
  if (has(victim, T_EXPOSED)) extra += 1.0;                 // 剥いだ後は 2 倍
  extra += damageBonus(attacker, victim) - 1.0;             // 磁力視の +20%
  if (extra <= 0) return;

  amplifying.add(victim.id);
  system.run(() => {
    // cause を "override" にするのは、直前の一撃が張った 10 tick の無敵を
    // 抜けるため。entityAttack のまま二発目を撃つと黙って消える。
    safe(() => victim.applyDamage(Math.max(1, Math.round(ev.damage * extra)),
      { cause: "override", damagingEntity: attacker }));
    if (has(victim, T_EXPOSED)) {
      fx(victim.dimension, FX.sentinel_spark,
         { x: victim.location.x, y: victim.location.y + 1.4, z: victim.location.z });
    }
    amplifying.delete(victim.id);
  });
});

// ===========================================================================
//  2. アダマンチウム — 磁力が効かない相手
// ===========================================================================
function rollAdamantium(entity) {
  if (has(entity, T_ROLLED)) return;
  safe(() => entity.addTag(T_ROLLED));
  // MRD は 3 割がアダマンチウム装備。センチネルは全身が磁性体なので対象外。
  if (!hasFamily(entity, FAMILY.mrd)) return;
  if (Math.random() > 0.30) return;
  safe(() => entity.addTag(T_ADAMANTIUM));
}

// ===========================================================================
//  3. 通常のセンチネル
// ===========================================================================
const beamCooldown = new Map();

function fireBeam(s, charge = 22, damage = 14, speed = 1.6) {
  act(s, 2);
  const eye = safe(() => s.getHeadLocation()) ?? s.location;
  fx(s.dimension, FX.sentinel_beam_charge, eye);
  sound(s.dimension, SOUND.sentinel_beam, s.location, { volume: 1.0, pitch: 0.9 });
  system.runTimeout(() => {
    if (!safe(() => s.isValid?.() !== false)) return;
    if (has(s, TAG.emp)) return;               // EMP 中は撃てない
    const t = nearestTarget(s, 30);
    if (!t) return;
    const dir = normalise(sub(
      { x: t.entity.location.x, y: t.entity.location.y + 1.0, z: t.entity.location.z },
      eye));
    const bolt = safe(() => s.dimension.spawnEntity(ENTITY.sentinel_beam,
      forward(eye, dir, 1.6)));
    if (!bolt) return;
    let step = 0;
    const fly = system.runInterval(() => {
      if (++step > 24 || !safe(() => bolt.isValid?.() !== false)) {
        safe(() => bolt.remove());
        system.clearRun(fly);
        return;
      }
      const next = forward(bolt.location, dir, speed);
      safe(() => bolt.teleport(next));
      fx(s.dimension, FX.sentinel_beam_trail, next);
      for (const e of safe(() => s.dimension.getEntities({ location: next, maxDistance: 1.6 })) ?? []) {
        if (e.id === s.id || e.id === bolt.id) continue;
        if (hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.prop)) continue;
        hit(s, e, damage);
        fx(s.dimension, FX.sentinel_beam_impact, e.location);
        safe(() => bolt.remove());
        system.clearRun(fly);
        break;
      }
    }, 1);
  }, charge);
}

function stomp(s, radius = 4.5, damage = 16) {
  act(s, 1);
  system.runTimeout(() => {
    if (!safe(() => s.isValid?.() !== false)) return;
    fx(s.dimension, FX.slam_ring, s.location);
    fxRing(s.dimension, FX.impact_dust, s.location, radius * 0.55, 10, 0.1);
    shakeNearby(s.dimension, s.location, 12, 0.35, 0.4);
    for (const e of safe(() => s.dimension.getEntities({ location: s.location, maxDistance: radius })) ?? []) {
      if (e.id === s.id || hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.prop)) continue;
      hit(s, e, damage);
      knock(e, normalise(sub(e.location, s.location)), 1.4, 0.7);
    }
    sound(s.dimension, "random.explode", s.location, { volume: 0.9, pitch: 0.7 });
  }, 12);
}

function tickSentinel(s) {
  // EMP で沈黙している間は何もしない。**ダメージ 0 の技が効いている実感**は
  // 「相手が本当に止まっていること」でしか出せない。
  if (has(s, TAG.emp)) {
    if (Math.random() < 0.5) {
      fx(s.dimension, FX.emp_arc,
         { x: s.location.x, y: s.location.y + 1.6, z: s.location.z });
    }
    return;
  }
  const target = nearestTarget(s, 26);
  if (!target) {
    if (Math.random() < 0.12) act(s, 5);          // 走査
    return;
  }
  const now = system.currentTick;
  if ((beamCooldown.get(s.id) ?? 0) > now) return;

  if (target.distance > 6) {
    beamCooldown.set(s.id, now + 110);
    fireBeam(s);
  } else if (target.distance <= 5) {
    beamCooldown.set(s.id, now + 60);
    stomp(s);
  }
}

// ===========================================================================
//  4. プライム・センチネル — 3 段階
// ===========================================================================
function phaseOf(s) {
  return has(s, T_PHASE3) ? 3 : has(s, T_PHASE2) ? 2 : 1;
}

/** フェーズの切り替わりを、周りのプレイヤー全員に見せる。 */
function bossShout(s, radius, numeral) {
  const banner = {
    rawtext: [{ text: "§c" }, { translate: `entity.${ENTITY.prime_sentinel}.name` },
              { text: `  §7${numeral}` }],
  };
  for (const p of allPlayers()) {
    if (distance(p.location, s.location) > radius) continue;
    title(p, banner, undefined, 4, 34, 14);
    shake(p, 0.30, 1.50, "rotational");
  }
}

function enterPhase2(s) {
  safe(() => s.addTag(T_PHASE2));
  // 適応。磁力の効きが 4.0 -> 1.0 に落ち、圧壊が通らなくなる。
  safe(() => s.addTag(T_ADAPTED));
  act(s, 4);                                     // 3.2 秒の変形クリップ
  safe(() => s.addEffect("resistance", 60, { amplifier: 2, showParticles: false }));
  fxScatter(s.dimension, FX.sentinel_smoke, s.location, 16, 2.2);
  fxRing(s.dimension, FX.sentinel_spark, s.location, 2.6, 16, 1.2);
  chord(s.dimension, s.location, [
    [SOUND.sentinel_beam, 0, { volume: 1.4, pitch: 0.6 }],
    [SOUND.transform_2, 8, { volume: 1.2, pitch: 0.7 }],
  ]);
  bossShout(s, 40, "II");

  // ドローン 4 体。**attract で墜として本体へぶつける** のが正解の攻略。
  for (let i = 0; i < 4; i++) {
    const a = (i / 4) * Math.PI * 2;
    const at = {
      x: s.location.x + Math.cos(a) * 4.0,
      y: s.location.y + 3.0,
      z: s.location.z + Math.sin(a) * 4.0,
    };
    const drone = safe(() => s.dimension.spawnEntity(ENTITY.sentinel_drone, at));
    if (drone) fx(s.dimension, FX.transform_ring, at);
  }
}

function enterPhase3(s) {
  safe(() => s.addTag(T_PHASE3));
  act(s, 4);
  // 装甲パージ。浮いて、EMP が通らなくなる。
  safe(() => s.addEffect("levitation", 20, { amplifier: 0, showParticles: false }));
  safe(() => s.addEffect("slow_falling", 20000, { amplifier: 0, showParticles: false }));
  safe(() => s.addTag(T_JAMMED));                // この個体には EMP が効かない
  fxScatter(s.dimension, FX.debris_chunk, s.location, 24, 2.6);
  fxScatter(s.dimension, FX.sentinel_smoke, s.location, 18, 2.4);
  chord(s.dimension, s.location, [
    [SOUND.sentinel_die, 0, { volume: 1.2, pitch: 1.3 }],
    [SOUND.emp, 6, { volume: 1.2, pitch: 0.7 }],
  ]);
  bossShout(s, 40, "III");
}

function tickPrime(s) {
  const hp = healthOf(s);
  const phase = phaseOf(s);
  if (hp !== undefined) {
    if (hp <= 900 && phase < 2) { enterPhase2(s); return; }
    if (hp <= 400 && phase < 3) { enterPhase3(s); return; }
  }
  if (has(s, TAG.emp) && phase < 3) {
    fx(s.dimension, FX.emp_arc, { x: s.location.x, y: s.location.y + 2.4, z: s.location.z });
    return;
  }

  const target = nearestTarget(s, 34);
  if (!target) { if (Math.random() < 0.2) act(s, 5); return; }
  const now = system.currentTick;
  if ((beamCooldown.get(s.id) ?? 0) > now) return;

  if (phase === 3) {
    // ジャミング場。射程内のプレイヤーは再充填が 1.5 倍になる。
    for (const p of allPlayers()) {
      if (distance(p.location, s.location) > 26) { safe(() => p.removeTag(T_JAMMED)); continue; }
      safe(() => p.addTag(T_JAMMED));
      fx(p.dimension, FX.emp_arc, { x: p.location.x, y: p.location.y + 2.2, z: p.location.z });
    }
    beamCooldown.set(s.id, now + 50);
    fireBeam(s, 14, 18, 2.0);
    if (target.distance <= 7) stomp(s, 6.0, 22);
    return;
  }

  if (phase === 2) {
    beamCooldown.set(s.id, now + 80);
    // ドローンが全部落ちていたら呼び直す。攻略が「待つだけ」にならないように。
    const drones = safe(() => s.dimension.getEntities({
      location: s.location, maxDistance: 24, type: ENTITY.sentinel_drone,
    })) ?? [];
    if (!drones.length && Math.random() < 0.4) {
      const at = { x: s.location.x, y: s.location.y + 3.4, z: s.location.z };
      safe(() => s.dimension.spawnEntity(ENTITY.sentinel_drone, at));
      fx(s.dimension, FX.transform_ring, at);
    }
    if (target.distance > 7) fireBeam(s, 18, 16, 1.8); else stomp(s, 5.4, 20);
    return;
  }

  beamCooldown.set(s.id, now + 90);
  if (target.distance > 6) fireBeam(s, 22, 15, 1.6); else stomp(s, 5.0, 18);
}

/** 牽引されたドローンが本体に当たったら、本体が大きく削れる。 */
function tickDrones(prime) {
  const drones = safe(() => prime.dimension.getEntities({
    location: prime.location, maxDistance: 8, type: ENTITY.sentinel_drone,
  })) ?? [];
  for (const d of drones) {
    if (!has(d, T_TOWED)) continue;
    if (distance(d.location, prime.location) > 3.5) continue;
    safe(() => d.removeTag(T_TOWED));
    // 手柄は **牽引したプレイヤー** のもの。攻撃元をドローンにすると
    // トドメがドローン扱いになり、撃破数が入らない。
    let tower;
    let best = 30;
    for (const p of allPlayers()) {
      const dd = distance(p.location, prime.location);
      if (dd < best) { best = dd; tower = p; }
    }
    hit(tower ?? d, prime, 90);                   // 自軍の残骸で殴られる
    fx(prime.dimension, FX.core_break, d.location);
    fxScatter(prime.dimension, FX.debris_chunk, d.location, 10, 1.4);
    chord(prime.dimension, d.location, [
      [SOUND.metal_hit, 0, { volume: 1.3, pitch: 0.6 }],
      [SOUND.sentinel_die, 3, { volume: 1.0, pitch: 1.1 }],
    ]);
    shakeNearby(prime.dimension, prime.location, 20, 0.4, 0.4);
    safe(() => d.remove());
  }
}

// ===========================================================================
//  5. ブラザーフッドの仲間
// ===========================================================================
//  仲間は「3 種の持ち技を、間合いで選ぶ」。全員が同じ殴り方をすると
//  9 人揃えた意味が無くなる。
const allyCooldown = new Map();

//: [近距離の技, 中距離の技, 立ち回りの技]
const ALLY_PLAY = {
  mystique: ["poison", "poison", "cloak"],
  sabretooth: ["claw", "claw", "rage"],
  toad: ["tongue", "tongue", "slime"],
  juggernaut: ["slam", "charge", "slam"],
  quicksilver: ["blitz", "blitz", "blur"],
  pyro: ["flame", "flame", "flame"],
  avalanche: ["quake", "rocks", "quake"],
  blob: ["slam", "slam", "brace"],
  scarlet_witch: ["hex", "hex", "curse"],
};

function allyStrike(a, target, move) {
  const dim = a.dimension;
  const dir = normalise(sub(target.location, a.location));
  switch (move) {
    case "flame":
      fx(dim, FX.flame_wave, target.location);
      fx(dim, FX.ember_rise, target.location);
      safe(() => target.setOnFire(6, true));
      hit(a, target, 12);
      break;
    case "hex":
      fx(dim, FX.hex_bolt_trail, target.location);
      fx(dim, FX.chaos_motes, target.location);
      hit(a, target, 14);
      safe(() => target.addEffect("weakness", 120, { amplifier: 2 }));
      break;
    case "curse":
      fx(dim, FX.hex_wave, a.location);
      safe(() => target.addEffect("mining_fatigue", 160, { amplifier: 2 }));
      safe(() => target.addEffect("blindness", 80, { amplifier: 0 }));
      break;
    case "blitz":
      fx(dim, FX.blur_after, a.location);
      safe(() => a.teleport(forward(target.location, { x: -dir.x, y: 0, z: -dir.z }, 1.4)));
      fx(dim, FX.speed_line, a.location);
      hit(a, target, 10);
      break;
    case "blur":
      fx(dim, FX.blur_after, a.location);
      safe(() => a.addEffect("speed", 160, { amplifier: 4, showParticles: false }));
      break;
    case "charge":
      fx(dim, FX.quake_dust, a.location);
      safe(() => a.addEffect("speed", 100, { amplifier: 3, showParticles: false }));
      safe(() => a.addEffect("resistance", 100, { amplifier: 3, showParticles: false }));
      knock(target, dir, 1.2, 0.4);
      hit(a, target, 14);
      break;
    case "slam":
      fx(dim, FX.slam_ring, target.location);
      fx(dim, FX.quake_dust, target.location);
      hit(a, target, 18);
      knock(target, dir, 1.6, 0.7);
      shakeNearby(dim, target.location, 10, 0.25, 0.4);
      break;
    case "brace":
      fx(dim, FX.slam_ring, a.location);
      safe(() => a.addEffect("resistance", 200, { amplifier: 4, showParticles: false }));
      safe(() => a.addEffect("absorption", 200, { amplifier: 3 }));
      break;
    case "quake":
      fx(dim, FX.quake_crack, target.location);
      fxRing(dim, FX.quake_dust, target.location, 2.2, 8, 0.1);
      hit(a, target, 16);
      safe(() => target.addEffect("slowness", 120, { amplifier: 2 }));
      break;
    case "rocks":
      fx(dim, FX.rock_fall, { x: target.location.x, y: target.location.y + 5, z: target.location.z });
      hit(a, target, 14);
      break;
    case "claw":
      fx(dim, FX.claw_slash, target.location);
      hit(a, target, 16);
      safe(() => target.addEffect("wither", 80, { amplifier: 0 }));
      break;
    case "rage":
      fx(dim, FX.roar_wave, a.location);
      safe(() => a.addEffect("strength", 200, { amplifier: 2, showParticles: false }));
      safe(() => target.addEffect("weakness", 120, { amplifier: 1 }));
      sound(dim, "mob.ravager.roar", a.location, { volume: 1.2, pitch: 0.8 });
      break;
    case "tongue":
      fx(dim, FX.tongue_slime, target.location);
      hit(a, target, 8);
      safe(() => target.addEffect("slowness", 120, { amplifier: 2 }));
      break;
    case "slime":
      fx(dim, FX.slime_splat, target.location);
      safe(() => target.addEffect("blindness", 100, { amplifier: 0 }));
      break;
    case "poison":
      fx(dim, FX.venom_drip, target.location);
      hit(a, target, 10);
      safe(() => target.addEffect("poison", 120, { amplifier: 1 }));
      break;
    case "cloak":
      fxScatter(dim, FX.shift_shimmer, a.location, 10, 1.0);
      safe(() => a.addEffect("invisibility", 120, { amplifier: 0, showParticles: false }));
      break;
    default:
      hit(a, target, 10);
      break;
  }
}

function tickAlly(a) {
  const now = system.currentTick;
  if ((allyCooldown.get(a.id) ?? 0) > now) return;
  const found = safe(() => a.dimension.getEntities({
    location: a.location, maxDistance: 16,
  })) ?? [];
  let target;
  let best = Infinity;
  for (const e of found) {
    if (hasFamily(e, FAMILY.brotherhood)) continue;
    const foe = hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.mrd)
      || safe(() => e.matches({ families: ["monster"] })) === true;
    if (!foe) continue;
    const d = distance(e.location, a.location);
    if (d < best) { best = d; target = e; }
  }
  if (!target) return;

  allyCooldown.set(a.id, now + 70 + Math.floor(Math.random() * 40));
  act(a, 2);
  const kit = ALLY_PLAY[a.typeId.split(":")[1]] ?? ["slam", "slam", "slam"];
  // 近い / 遠い / たまに立ち回り。三つ目が入るだけで「考えている」ように見える。
  const move = Math.random() < 0.22 ? kit[2] : (best <= 4.0 ? kit[0] : kit[1]);
  system.runTimeout(() => {
    if (!safe(() => a.isValid?.() !== false)) return;
    if (!safe(() => target.isValid?.() !== false)) return;
    allyStrike(a, target, move);
  }, 8);
}

/** 磁力を帯びたプレイヤーの近くでは、センチネルの金属が軋む。 */
function tickMagnetPressure() {
  for (const player of allPlayers()) {
    if (!safe(() => player.hasTag(TAG.form))) continue;
    const near = safe(() => player.dimension.getEntities({
      location: player.location, maxDistance: 10,
    })) ?? [];
    for (const e of near) {
      if (!hasFamily(e, FAMILY.sentinel)) continue;
      if (metalOn(e) <= 0) continue;
      if (Math.random() > 0.3) continue;
      fx(e.dimension, FX.mag_spark,
         { x: e.location.x, y: e.location.y + 1.4, z: e.location.z });
    }
    // アダマンチウムの相手は、見ただけで判るようにしておく。
    for (const e of near) {
      if (!has(e, T_ADAMANTIUM) || Math.random() > 0.25) continue;
      fx(e.dimension, FX.mag_glyph,
         { x: e.location.x, y: e.location.y + 1.8, z: e.location.z });
    }
  }
}

// ===========================================================================
//  6. 毎秒の入り口
// ===========================================================================
/** 一秒ごとに呼ぶ。 */
export function tickAI() {
  //: 複数人が同じ mob を見ていても、処理は一体につき一度だけ。
  const seen = new Set();
  for (const player of allPlayers()) {
    const near = safe(() => player.dimension.getEntities({
      location: player.location, maxDistance: 40,
    })) ?? [];
    for (const e of near) {
      if (seen.has(e.id)) continue;
      seen.add(e.id);
      rollAdamantium(e);
      if (e.typeId === ENTITY.prime_sentinel) {
        tickPrime(e);
        tickDrones(e);
      } else if (SENTINELS.has(e.typeId)) {
        tickSentinel(e);
      } else if (hasFamily(e, FAMILY.brotherhood)) {
        tickAlly(e);
      }
    }
  }
  tickMagnetPressure();
}

// ===========================================================================
//  7. 撃破 — 熟練度と段階
// ===========================================================================
/** 昇格演出（3 秒）。§7-4 の手順そのまま。 */
function celebrate(player, stage) {
  const dim = player.dimension;
  fade(player, { red: 1.0, green: 1.0, blue: 1.0 }, 0.06, 0.05, 0.70);
  shake(player, 0.50, 1.00, "rotational");
  title(player, tr(`class.stage${stage}`), tr("msg.stage_up"), 6, 44, 20);
  chord(dim, player.location, [
    [SOUND.transform_2, 0, { volume: 1.4, pitch: 0.9 }],
    [SOUND.mag_release, 8, { volume: 1.0, pitch: 1.4 }],
    ["random.levelup", 16, { volume: 1.0, pitch: 0.7 }],
  ]);
  fx(dim, FX.transform_ring, player.location);
  fxScatter(dim, FX.transform_burst, player.location, 10, 1.4);
  // 半径 20 の金属が一斉に応える。段階が上がったことを世界の側で見せる。
  let n = 0;
  const glint = system.runInterval(() => {
    if (++n > 5) { system.clearRun(glint); return; }
    fxRing(dim, FX.metal_glint, player.location, 4.0 * n, 12 + n * 4, 0.6);
  }, 4);
}

/** センチネル撃破で熟練度が上がる。 */
world.afterEvents.entityDie.subscribe((ev) => {
  const killer = ev.damageSource?.damagingEntity;
  if (killer?.typeId !== "minecraft:player") return;
  const dead = ev.deadEntity;
  if (!dead?.typeId?.startsWith("marvel:")) return;
  if (hasFamily(dead, FAMILY.brotherhood)) return;

  const prime = dead.typeId === ENTITY.prime_sentinel;
  system.run(() => {
    const before = safe(() => killer.getDynamicProperty(PROP.mastery)) ?? 0;
    const mastery = (typeof before === "number" ? before : 0) + (prime ? 5 : 1);
    safe(() => killer.setDynamicProperty(PROP.mastery, mastery));

    // **ここで段階を見直す。** 呼ばれないと mastery だけ増えて段階 3 に一生届かない。
    const was = stageOf(killer);
    const now = refreshStage(killer);
    if (now > was) celebrate(killer, now);

    if (SENTINELS.has(dead.typeId)) {
      fx(dead.dimension, FX.core_break, dead.location);
      chord(dead.dimension, dead.location, [
        [SOUND.sentinel_die, 0, { volume: 1.1, pitch: 0.8 }],
        [SOUND.metal_hit, 5, { volume: 0.8, pitch: 0.7 }],
      ]);
    }
    if (!prime) return;

    // プライム撃破: 10 秒の減速演出。倒した瞬間だけ世界がゆっくりになる。
    safe(() => killer.removeTag(T_JAMMED));
    fxScatter(dead.dimension, FX.core_break, dead.location, 8, 2.0);
    shakeNearby(dead.dimension, dead.location, 30, 0.6, 1.5);
    safe(() => killer.addEffect("speed", 200, { amplifier: 1, showParticles: false }));
    for (const e of safe(() => dead.dimension.getEntities({
      location: dead.location, maxDistance: 24,
    })) ?? []) {
      if (e.typeId === "minecraft:player") continue;
      safe(() => e.addEffect("slowness", 200, { amplifier: 5, showParticles: false }));
    }
  });
});
