// ===========================================================================
//  スクリプト弾（光の矢・影の苦無・星の雨）
//  エンティティを作らず位置と速度だけを持ち、毎 tick 小刻みに進めて
//  ブロックと標的を調べる。軌跡の演出は弾ごとに trail で差し替える。
// ===========================================================================
import { isTarget } from "./combat.js";
import { valid, add, dist, chest } from "./util.js";

const shots = [];
const MAX_SHOTS = 80;

const PASS = /(short_grass|tallgrass|tall_grass|fern|flower|sapling|torch|vine|snow_layer|carpet|button|lever|rail|pressure_plate|_sign|banner|bush|kelp|seagrass|mushroom|wheat|carrots|potatoes|beetroot|sugar_cane|dandelion|poppy|tulip|orchid|allium|azure_bluet|oxeye|cornflower|lily_of|rose_bush|peony|lilac|sunflower|web|structure_void|light_block|^minecraft:air$|fire|scaffolding|redstone_wire|tripwire|petals|glow_lichen|hanging_roots|moss_carpet|pink_petals)/;

export function blocked(dim, pos) {
  try {
    const b = dim.getBlock({ x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) });
    if (!b) return false;
    if (b.isAir || b.isLiquid) return false;
    return !PASS.test(b.typeId);
  } catch (_) { return false; }
}

/**
 * o.speed (block/tick) / o.range / o.radius / o.pierce (貫通数) / o.gravity /
 * o.trail(dim, pos, prev, age) / o.onHit(e, pos) / o.onEnd(pos, reason) / o.homing (entity)
 */
export function shoot(owner, from, dir, o = {}) {
  if (shots.length >= MAX_SHOTS) shots.shift();
  shots.push({
    owner, dim: owner.dimension, pos: { ...from }, vel: { x: dir.x * (o.speed ?? 2), y: dir.y * (o.speed ?? 2), z: dir.z * (o.speed ?? 2) },
    left: o.range ?? 40, radius: o.radius ?? 0.6, pierce: o.pierce ?? 0, gravity: o.gravity ?? 0,
    hits: new Set(), age: 0, o,
  });
}

export function tickShots() {
  for (let i = shots.length - 1; i >= 0; i--) {
    const s = shots[i];
    if (!valid(s.owner)) { shots.splice(i, 1); continue; }
    s.age++;
    s.vel.y -= s.gravity;
    if (s.o.homing && valid(s.o.homing)) {
      const to = chest(s.o.homing);
      const d = dist(to, s.pos) || 1;
      const sp = Math.hypot(s.vel.x, s.vel.y, s.vel.z);
      const k = 0.35;
      s.vel = {
        x: s.vel.x * (1 - k) + (to.x - s.pos.x) / d * sp * k,
        y: s.vel.y * (1 - k) + (to.y - s.pos.y) / d * sp * k,
        z: s.vel.z * (1 - k) + (to.z - s.pos.z) / d * sp * k,
      };
    }
    const sp = Math.hypot(s.vel.x, s.vel.y, s.vel.z);
    const n = Math.max(1, Math.ceil(sp / 0.5));
    const step = { x: s.vel.x / n, y: s.vel.y / n, z: s.vel.z / n };
    const prev = { ...s.pos };
    let done = false;
    for (let k = 0; k < n && !done; k++) {
      s.pos = add(s.pos, step);
      s.left -= sp / n;
      if (blocked(s.dim, s.pos)) {
        s.o.onEnd?.(s.pos, "block");
        done = true;
        break;
      }
      let near = [];
      try { near = s.dim.getEntities({ location: s.pos, maxDistance: s.radius + 1.2 }); } catch (_) { }
      for (const e of near) {
        if (s.hits.has(e.id) || !isTarget(s.owner, e)) continue;
        const c = chest(e);
        // 体の縦の広がりを見て、足元から頭までのどこかに当たればよい
        const dy = Math.max(0, Math.abs(s.pos.y - c.y) - 0.7);
        const dh = Math.hypot(s.pos.x - c.x, s.pos.z - c.z);
        if (Math.hypot(dh, dy) > s.radius + 0.45) continue;
        s.hits.add(e.id);
        try { s.o.onHit?.(e, { ...s.pos }); } catch (_) { }
        if (s.hits.size > s.pierce) {
          s.o.onEnd?.(s.pos, "entity");
          done = true;
          break;
        }
      }
      if (s.left <= 0) {
        s.o.onEnd?.(s.pos, "range");
        done = true;
      }
    }
    try { s.o.trail?.(s.dim, s.pos, prev, s.age); } catch (_) { }
    if (done) shots.splice(i, 1);
  }
}

export function activeShots() { return shots.length; }
