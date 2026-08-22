// 磁力エンジン / the magnetism engine
//
// このアドオンの根っこ。「何が金属か」「どれだけ強く効くか」を一箇所で決め、
// 技はすべてこの関数群の上に乗る。
//
// 走査コストについて
//   半径 r の球を全走査すると 4/3πr³ 回の getBlock になる。r=16 で約 1.7 万回。
//   毎 tick 回すと確実に重いので、
//     * 走査は技の発動時だけ
//     * 半径が大きいときは step を粗くして間引く
//     * 見つけた数に上限を設ける
//   の三点で必ず抑える。
import { world, system, ItemStack } from "@minecraft/server";
import {
  MAGNETIC_BLOCKS, MAGNETIC_ITEMS, IMMUNE_ITEMS, FAMILY, FX, ENTITY,
} from "./config.js";
import { distance, forward, hasFamily, normalise, safe, sub } from "./util.js";
import { fx, fxTrail } from "./effects.js";

const EQUIP_SLOTS = ["Head", "Chest", "Legs", "Feet", "Mainhand", "Offhand"];

/** そのブロックが磁力に応えるか。0 なら無反応。 */
export function blockStrength(typeId) {
  return MAGNETIC_BLOCKS[typeId] ?? 0;
}

/** 装備品の磁化強度。アダマンチウムだけは 0（唯一の対抗手段）。 */
export function itemStrength(typeId) {
  if (!typeId) return 0;
  for (const immune of IMMUNE_ITEMS) if (typeId.includes(immune)) return 0;
  for (const [material, factor] of Object.entries(MAGNETIC_ITEMS)) {
    if (typeId.includes(material)) return factor;
  }
  return 0;
}

/** そのエンティティが身につけている金属の総量（0 ～ 約 6）。 */
export function metalOn(entity) {
  let total = 0;
  const eq = safe(() => entity.getComponent("minecraft:equippable"));
  if (eq) {
    for (const slot of EQUIP_SLOTS) {
      const item = safe(() => eq.getEquipment(slot));
      if (item) total += itemStrength(item.typeId);
    }
  }
  // センチネルは全身が金属。文字通り彼の玩具になる。
  if (hasFamily(entity, FAMILY.sentinel)) total += 4.0;
  if (hasFamily(entity, FAMILY.mrd)) total += 1.2;
  return total;
}

/**
 * 周囲の磁性ブロックを探す。
 * @returns [{x,y,z,typeId,strength,distance}] を強度×近さの順に。
 */
export function scanMetal(dimension, centre, radius, limit = 48) {
  const found = [];
  // 半径が大きいほど粗く間引く。r=8 -> 1, r=16 -> 2, r=40 -> 4
  const step = radius <= 8 ? 1 : radius <= 20 ? 2 : 4;
  const r = Math.ceil(radius);
  const cx = Math.floor(centre.x), cy = Math.floor(centre.y), cz = Math.floor(centre.z);
  for (let dy = -r; dy <= r; dy += step) {
    const y = cy + dy;
    if (y < -64 || y > 320) continue;
    for (let dx = -r; dx <= r; dx += step) {
      for (let dz = -r; dz <= r; dz += step) {
        const d = Math.hypot(dx, dy, dz);
        if (d > radius) continue;
        const block = safe(() => dimension.getBlock({ x: cx + dx, y, z: cz + dz }));
        if (!block) continue;
        const strength = blockStrength(block.typeId);
        if (strength <= 0) continue;
        found.push({
          x: cx + dx, y, z: cz + dz, typeId: block.typeId, strength, distance: d,
        });
        if (found.length >= limit * 3) break;
      }
    }
  }
  found.sort((a, b) => (b.strength / (1 + b.distance)) - (a.strength / (1 + a.distance)));
  return found.slice(0, limit);
}

/** 磁性ブロックを引き剥がして鉄片エンティティに変える。 */
export function ripBlock(dimension, pos, ownerId) {
  const block = safe(() => dimension.getBlock(pos));
  if (!block || blockStrength(block.typeId) <= 0) return undefined;
  const centre = { x: pos.x + 0.5, y: pos.y + 0.5, z: pos.z + 0.5 };
  safe(() => block.setType("minecraft:air"));
  fx(dimension, FX.metal_rip, centre);
  const shard = safe(() => dimension.spawnEntity(ENTITY.metal_shard, centre));
  if (shard && ownerId) safe(() => shard.setDynamicProperty("marvel:owner", ownerId));
  return shard;
}

/** 対象を `to` の方向へ動かす。引き寄せ・押し出しの共通処理。 */
export function drag(entity, toward, power, vertical = 0.15) {
  const from = entity.location;
  const d = sub(toward, from);
  const len = Math.hypot(d.x, d.y, d.z) || 1;
  const n = { x: d.x / len, y: d.y / len, z: d.z / len };
  try {
    entity.applyImpulse({
      x: n.x * power, y: n.y * power * 0.6 + vertical, z: n.z * power,
    });
    return true;
  } catch (_) {
    // プレイヤーには applyImpulse が効かないので knockback を使う
    try {
      entity.applyKnockback(n.x * power, n.z * power, power * 0.6, n.y * power * 0.4 + vertical);
      return true;
    } catch (_e) { return false; }
  }
}

/** 相手の金属装備を剥ぎ取って地面に落とす。剥がした数を返す。 */
export function stripEquipment(target, dimension) {
  const eq = safe(() => target.getComponent("minecraft:equippable"));
  if (!eq) return 0;
  let stripped = 0;
  for (const slot of EQUIP_SLOTS) {
    const item = safe(() => eq.getEquipment(slot));
    if (!item || itemStrength(item.typeId) <= 0) continue;
    if (!safe(() => { eq.setEquipment(slot, undefined); return true; })) continue;
    safe(() => dimension.spawnItem(new ItemStack(item.typeId, item.amount ?? 1),
      { x: target.location.x, y: target.location.y + 1.0, z: target.location.z }));
    stripped++;
  }
  return stripped;
}

/** 落ちているアイテムのうち、磁力に応えるものを引き寄せる。 */
export function pullItems(dimension, centre, radius, toward, power = 0.55) {
  let moved = 0;
  const items = safe(() => dimension.getEntities({
    location: centre, maxDistance: radius, type: "minecraft:item",
  })) ?? [];
  for (const item of items) {
    const stack = safe(() => item.getComponent("minecraft:item")?.itemStack);
    if (stack && itemStrength(stack.typeId) <= 0
        && !MAGNETIC_BLOCKS[stack.typeId]) continue;
    if (drag(item, toward, power, 0.25)) moved++;
  }
  return moved;
}

/** 磁力線を描く。技の説得力は、この線が出るかどうかで随分変わる。 */
export function drawFieldLines(dimension, from, targets, id = FX.mag_line, max = 8) {
  let n = 0;
  for (const t of targets) {
    if (n++ >= max) break;
    fxTrail(dimension, id, from, t, 1.0);
  }
}

/** 磁力視 — 壁越しに金属を光らせる。一人称の楽しさはここ。 */
export function revealMetal(player, radius = 20) {
  const found = scanMetal(player.dimension, player.location, radius, 60);
  for (const m of found) {
    fx(player.dimension, FX.sight_ping,
       { x: m.x + 0.5, y: m.y + 0.5, z: m.z + 0.5 });
  }
  const wearers = safe(() => player.dimension.getEntities({
    location: player.location, maxDistance: radius,
  })) ?? [];
  for (const e of wearers) {
    if (e.id === player.id) continue;
    if (metalOn(e) <= 0) continue;
    fx(player.dimension, FX.mag_glyph,
       { x: e.location.x, y: e.location.y + 1.2, z: e.location.z });
  }
  return found.length;
}

/** 鉄片を撃ち出す。当たり判定はスクリプト側で毎 tick 見る。 */
const projectiles = [];

export function launchShard(player, origin, dir, speed, damage,
                           typeId = ENTITY.metal_shard, life = 60) {
  const e = safe(() => player.dimension.spawnEntity(typeId, origin));
  if (!e) return undefined;
  safe(() => e.setRotation({ x: 0, y: 0 }));
  projectiles.push({
    entity: e, dir: normalise(dir), speed, damage, life,
    ownerId: player.id, born: system.currentTick,
  });
  return e;
}

/** 毎 tick: 飛んでいる鉄片を進め、当たったら処理する。 */
export function tickProjectiles(onHit) {
  for (let i = projectiles.length - 1; i >= 0; i--) {
    const p = projectiles[i];
    const e = p.entity;
    if (!safe(() => e.isValid?.() !== false) || system.currentTick - p.born > p.life) {
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    const here = e.location;
    const next = forward(here, p.dir, p.speed);
    // ブロックに当たったか
    const block = safe(() => e.dimension.getBlock(next));
    if (block && !block.isAir && !block.isLiquid) {
      fx(e.dimension, FX.lance_impact, here);
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    // エンティティに当たったか
    const near = safe(() => e.dimension.getEntities({
      location: next, maxDistance: 1.4,
    })) ?? [];
    let struck = false;
    for (const t of near) {
      if (t.id === e.id || t.id === p.ownerId) continue;
      if (hasFamily(t, FAMILY.prop)) continue;
      if (hasFamily(t, FAMILY.brotherhood)) continue;
      onHit?.(p, t);
      struck = true;
      break;
    }
    if (struck) {
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    safe(() => e.teleport(next, { facingLocation: forward(next, p.dir, 2) }));
    fx(e.dimension, FX.shard_trail, here);
  }
}

export function projectileCount() {
  return projectiles.length;
}
