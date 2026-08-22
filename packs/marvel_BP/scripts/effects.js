// 演出 / particles, sound, camera work, hit detection
//
// 「映画のような」を担っているのは、実はパーティクル単体ではなく
//   画面の揺れ・一瞬の暗転・タイトル・音の重ね方
// の組み合わせ。ここにその語彙をまとめる。
import { system } from "@minecraft/server";
import { distance, forward, hasFamily, isPlayer, normalise, safe, sub } from "./util.js";
import { FAMILY } from "./config.js";

// ---------------------------------------------------------------- particles
export function fx(dimension, id, location) {
  try { dimension.spawnParticle(id, location); } catch (_) { }
}

export function fxRing(dimension, id, centre, radius, count, y = 0.2) {
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * radius,
      y: centre.y + y,
      z: centre.z + Math.sin(a) * radius,
    });
  }
}

export function fxLine(dimension, id, origin, dir, length, step = 1.1) {
  for (let d = 0; d <= length; d += step) fx(dimension, id, forward(origin, dir, d));
}

export function fxScatter(dimension, id, centre, count, spread = 1.0) {
  for (let i = 0; i < count; i++) {
    fx(dimension, id, {
      x: centre.x + (Math.random() - 0.5) * spread * 2,
      y: centre.y + Math.random() * spread,
      z: centre.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

/** 球殻に撒く。障壁・磁界の棺のように「面」を見せたいとき。 */
export function fxSphere(dimension, id, centre, radius, count) {
  for (let i = 0; i < count; i++) {
    const u = Math.random() * 2 - 1;
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(1 - u * u);
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * r * radius,
      y: centre.y + u * radius,
      z: centre.z + Math.sin(a) * r * radius,
    });
  }
}

/** 二点間を結ぶ。磁力線の表現。 */
export function fxTrail(dimension, id, from, to, step = 0.7) {
  const d = sub(to, from);
  const len = Math.hypot(d.x, d.y, d.z);
  if (len < 0.01) return;
  const dir = { x: d.x / len, y: d.y / len, z: d.z / len };
  for (let t = 0; t <= len; t += step) fx(dimension, id, forward(from, dir, t));
}

/** 螺旋。引き寄せ・巻き上げの「流れ」を見せる。 */
export function fxSpiral(dimension, id, centre, radius, height, turns, count) {
  for (let i = 0; i < count; i++) {
    const t = i / count;
    const a = t * Math.PI * 2 * turns;
    const r = radius * (1 - t * 0.75);
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * r,
      y: centre.y + height * t,
      z: centre.z + Math.sin(a) * r,
    });
  }
}

// ---------------------------------------------------------------- sound
export function sound(dimension, id, location, opts) {
  try { dimension.playSound(id, location, opts); } catch (_) { }
}

/** 音を少しずらして重ねる。単発より遥かに「厚く」なる。 */
export function chord(dimension, location, layers) {
  for (const [id, delay, opts] of layers) {
    if (delay <= 0) sound(dimension, id, location, opts);
    else system.runTimeout(() => sound(dimension, id, location, opts), delay);
  }
}

// ---------------------------------------------------------------- camera
/** 画面を揺らす。重さの表現で一番効く。 */
export function shake(player, intensity = 0.2, seconds = 0.3, type = "positional") {
  try {
    player.runCommand(
      `camerashake add @s ${intensity.toFixed(2)} ${seconds.toFixed(2)} ${type}`);
  } catch (_) { }
}

export function shakeNearby(dimension, centre, radius, intensity, seconds) {
  let players = [];
  try {
    players = dimension.getEntities({
      location: centre, maxDistance: radius, type: "minecraft:player",
    });
  } catch (_) { return; }
  for (const p of players) {
    const d = distance(p.location, centre);
    shake(p, Math.max(0.05, intensity * (1 - d / radius)), seconds);
  }
}

/** 一瞬の暗転／発光。必殺技の直前に挟むと画が締まる。 */
export function fade(player, colour = { red: 0.55, green: 0.30, blue: 0.95 },
                     inSec = 0.12, holdSec = 0.10, outSec = 0.35) {
  try {
    player.camera.fade({
      fadeColor: colour,
      fadeTime: { fadeInTime: inSec, holdTime: holdSec, fadeOutTime: outSec },
    });
  } catch (_) { }
}

/** 視界を色で染める。一人称で「磁界の中にいる」感じを出す。 */
export function fog(player, id, name = "marvel_field") {
  try { player.runCommand(`fog @s push ${id} ${name}`); } catch (_) { }
}

export function fogPop(player, name = "marvel_field") {
  try { player.runCommand(`fog @s pop ${name}`); } catch (_) { }
}

/** ヒットストップ。一瞬だけ相手を止めると、当たった重みが出る。 */
export function hitstop(entity, ticks = 3) {
  try {
    entity.addEffect("slowness", ticks, { amplifier: 6, showParticles: false });
  } catch (_) { }
}

// ---------------------------------------------------------------- targeting
export function targetsNear(entity, radius, includeAllies = false) {
  try {
    return entity.dimension.getEntities({
      location: entity.location, maxDistance: radius,
      excludeTypes: ["minecraft:item", "minecraft:xp_orb", "minecraft:arrow"],
    }).filter((e) => e.id !== entity.id
      && !hasFamily(e, FAMILY.prop)
      && (includeAllies || !hasFamily(e, FAMILY.brotherhood))
      && !isPlayer(e));
  } catch (_) { return []; }
}

/** 正面の扇。`dot` は 1 が真正面、-1 が全周。 */
export function cone(attacker, radius, dot, includeAllies = false) {
  const dir = attacker.getViewDirection();
  const from = attacker.getHeadLocation ? attacker.getHeadLocation() : attacker.location;
  const out = [];
  for (const target of targetsNear(attacker, radius, includeAllies)) {
    const to = sub({ x: target.location.x, y: target.location.y + 0.8, z: target.location.z }, from);
    const n = normalise(to);
    if (n.x * dir.x + n.y * dir.y + n.z * dir.z < dot) continue;
    out.push({ entity: target, dir: n, distance: Math.hypot(to.x, to.y, to.z) });
  }
  return out.sort((a, b) => a.distance - b.distance);
}

/** 視線上の直線。貫通技に使う。 */
export function ray(attacker, length, width, includeAllies = false) {
  const dir = attacker.getViewDirection();
  const eye = attacker.getHeadLocation ? attacker.getHeadLocation() : attacker.location;
  const out = [];
  for (const target of targetsNear(attacker, length + 2, includeAllies)) {
    const to = sub({ x: target.location.x, y: target.location.y + 0.8, z: target.location.z }, eye);
    const along = to.x * dir.x + to.y * dir.y + to.z * dir.z;
    if (along < 0 || along > length) continue;
    const perp = Math.hypot(to.x - dir.x * along, to.y - dir.y * along, to.z - dir.z * along);
    if (perp > width) continue;
    out.push({ entity: target, along });
  }
  return out.sort((a, b) => a.along - b.along);
}

/** 視線の先で最初に当たるもの（エンティティ優先、無ければブロック）。 */
export function lookTarget(player, range = 32) {
  const hitEntity = safe(() => player.getEntitiesFromViewDirection({ maxDistance: range })
    ?.filter((h) => h.entity?.id !== player.id)?.[0]?.entity);
  if (hitEntity) return { entity: hitEntity, location: hitEntity.location };
  const hitBlock = safe(() => player.getBlockFromViewDirection({ maxDistance: range }));
  if (hitBlock?.block) {
    const b = hitBlock.block.location;
    return { block: hitBlock.block, location: { x: b.x + 0.5, y: b.y + 0.5, z: b.z + 0.5 } };
  }
  const dir = player.getViewDirection();
  const eye = player.getHeadLocation();
  return { location: forward(eye, dir, range * 0.6) };
}

export function hit(attacker, target, damage) {
  try {
    target.applyDamage(Math.max(1, Math.round(damage)),
      { cause: "entityAttack", damagingEntity: attacker });
    return true;
  } catch (_) { return false; }
}

export function knock(entity, dir, power, vertical = 0.5) {
  try {
    entity.applyKnockback(dir.x * power, dir.z * power, power, vertical);
  } catch (_) {
    try { entity.applyImpulse({ x: dir.x * power * 0.4, y: vertical, z: dir.z * power * 0.4 }); }
    catch (_e) { }
  }
}
