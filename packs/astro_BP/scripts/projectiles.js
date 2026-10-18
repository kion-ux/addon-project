// ===========================================================================
//  スクリプト弾（エネルギー波・矢・環刃・槍…）
//
//  エンティティを作らず「位置と速度」だけを持ち、毎 tick 小刻みに進めてブロックと標的を調べる。
//  見た目は弾ごとの trail() で描く。ブーメラン（行って戻る）・追尾・貫通・多段に対応。
//  エンティティの問い合わせは 1 発につき 1 tick 1 回（その tick に進む区間をまとめて調べる）。
// ===========================================================================
import { isTarget, entitiesNear, hit } from "./combat.js";
import { valid, add, dist, chest, norm, sub, blocked, report, now } from "./util.js";

const shots = [];
export const MAX_SHOTS = 80;

/**
 * スクリプト弾を撃つ（engine.js の projectile() と同じもの）。
 * @param src   ctx（技の文脈。解除・死亡で弾も消える）かプレイヤー
 * @param from  発射位置
 * @param dir   向き（正規化しなくてよい）
 * @param o     speed 1 tick に進む距離（既定 1.2）/ range 射程 m（既定 30）/ radius 当たりの半径（0.6）/
 *              pierce 貫通できる数（0 = 最初の 1 体で終わる、Infinity = 全部）/ gravity 毎 tick の落下 /
 *              life 最長 tick（100）/ blocks false でブロックを抜ける /
 *              homing 追尾する相手（エンティティ。true なら前方の一番近い敵を自動で）/ turn 追尾の強さ 0..1（0.35）/
 *              returns true で射程の端（か returnAt tick）で持ち主へ戻る（ブーメラン。戻りは同じ相手に再び当たる）/
 *              returnAt 折り返す tick / hitEvery 同じ相手に何 tick おきに当たり直すか（貫通弾の多段）/
 *              damage と hitOpts を渡すと当たった相手に hit(src, e, damage, hitOpts) を自動で行う /
 *              trail(dim, pos, prev, age, shot) 毎 tick の見た目 /
 *              onHit(e, pos, shot) 当たった時 / onEnd(pos, reason, shot) 終わった時
 *              （reason: "block" | "entity" | "range" | "life" | "owner" | "returned" | "stopped"）
 * @returns shot（shot.stop() で消せる。shot.pos / shot.vel / shot.age / shot.back を読める）
 */
export function shoot(src, from, dir, o = {}) {
  const ctx = src && src.p && src.kind ? src : null;
  const owner = ctx ? ctx.p : src;
  if (!valid(owner)) return null;
  if (shots.length >= MAX_SHOTS) {
    const old = shots.shift();
    try { old.o.onEnd?.(old.pos, "stopped", old); } catch (_) { }
  }
  const d = norm(dir);
  const sp = o.speed ?? 1.2;
  const shot = {
    owner, ctx, dim: ctx?.dim ?? owner.dimension, pos: { ...from }, vel: { x: d.x * sp, y: d.y * sp, z: d.z * sp },
    speed: sp, left: o.range ?? 30, radius: o.radius ?? 0.6, pierce: o.pierce ?? 0, gravity: o.gravity ?? 0,
    hits: new Map(), age: 0, back: false, o, done: false, travelled: 0,
    stop() { shot.done = true; },
  };
  if (o.homing === true) {
    shot.homing = autoTarget(owner, from, d, o.range ?? 30);
  } else if (o.homing) {
    shot.homing = o.homing;
  }
  shots.push(shot);
  return shot;
}

function autoTarget(owner, from, d, range) {
  let best, bs = -Infinity;
  for (const e of entitiesNear(owner.dimension, from, Math.min(range, 32))) {
    if (!isTarget(owner, e)) continue;
    const to = sub(chest(e), from);
    const l = Math.hypot(to.x, to.y, to.z) || 1;
    const c = (to.x * d.x + to.y * d.y + to.z * d.z) / l;
    if (c < 0.6) continue;
    const score = c * 2 - l / range;
    if (score > bs) { bs = score; best = e; }
  }
  return best;
}

function end(s, reason) {
  if (s.done && reason !== "stopped") return;
  s.done = true;
  try { s.o.onEnd?.({ ...s.pos }, reason, s); } catch (e) { report("projectile.onEnd", e); }
}

function steer(s, to, k) {
  const d = dist(to, s.pos) || 1;
  const sp = s.speed;
  s.vel = {
    x: s.vel.x * (1 - k) + (to.x - s.pos.x) / d * sp * k,
    y: s.vel.y * (1 - k) + (to.y - s.pos.y) / d * sp * k,
    z: s.vel.z * (1 - k) + (to.z - s.pos.z) / d * sp * k,
  };
  // 速さを保つ
  const v = Math.hypot(s.vel.x, s.vel.y, s.vel.z) || 1;
  s.vel = { x: s.vel.x / v * sp, y: s.vel.y / v * sp, z: s.vel.z / v * sp };
}

/** 毎 tick（main から）。 */
export function tickShots() {
  for (let i = shots.length - 1; i >= 0; i--) {
    const s = shots[i];
    try {
      if (s.done) { shots.splice(i, 1); continue; }
      if (!valid(s.owner) || (s.ctx && !s.ctx.alive())) { end(s, "owner"); shots.splice(i, 1); continue; }
      s.age++;
      if (s.age > (s.o.life ?? 100)) { end(s, "life"); shots.splice(i, 1); continue; }
      s.vel.y -= s.gravity;
      if (s.back) {
        steer(s, chest(s.owner), 0.55);
      } else if (s.homing && valid(s.homing)) {
        steer(s, chest(s.homing), s.o.turn ?? 0.35);
      }
      if (s.o.returns && !s.back && (s.left <= 0 || (s.o.returnAt && s.age >= s.o.returnAt))) {
        s.back = true;
        if (s.o.rehit !== false) s.hits.clear();
        s.left = Infinity;
      }
      const sp = Math.hypot(s.vel.x, s.vel.y, s.vel.z);
      const n = Math.max(1, Math.ceil(sp / 0.5));
      const step = { x: s.vel.x / n, y: s.vel.y / n, z: s.vel.z / n };
      const prev = { ...s.pos };
      // この tick に進む区間の周りを一度だけ問い合わせる
      const mid = add(s.pos, s.vel, 0.5);
      const cand = entitiesNear(s.dim, mid, sp / 2 + s.radius + 1.6).filter((e) => isTarget(s.owner, e));
      for (let k = 0; k < n && !s.done; k++) {
        s.pos = add(s.pos, step);
        s.left -= sp / n;
        s.travelled += sp / n;
        // 戻りの環刃は壁を抜けて持ち主へ帰る
        if (s.o.blocks !== false && !s.back && blocked(s.dim, s.pos)) {
          if (s.o.returns) {
            s.pos = add(s.pos, step, -1);
            s.back = true; s.left = Infinity;
            if (s.o.rehit !== false) s.hits.clear();
            break;
          }
          end(s, "block");
          break;
        }
        for (const e of cand) {
          if (s.done) break;
          const last = s.hits.get(e.id);
          if (last !== undefined && !(s.o.hitEvery && s.age - last >= s.o.hitEvery)) continue;
          if (!valid(e)) continue;
          const c = chest(e);
          const dy = Math.max(0, Math.abs(s.pos.y - c.y) - 0.7);
          const dh = Math.hypot(s.pos.x - c.x, s.pos.z - c.z);
          if (Math.hypot(dh, dy) > s.radius + 0.45) continue;
          const first = last === undefined;
          s.hits.set(e.id, s.age);
          try {
            if (s.o.damage) hit(s.ctx ?? s.owner, e, s.o.damage, { dir: norm(s.vel), ...(s.o.hitOpts ?? {}) });
            s.o.onHit?.(e, { ...s.pos }, s);
          } catch (err) { report("projectile.onHit", err); }
          if (first) s.pierced = (s.pierced ?? 0) + 1;
          if ((s.pierced ?? 0) > s.pierce) { end(s, "entity"); break; }
        }
        if (s.done) break;
        if (s.back && dist(s.pos, chest(s.owner)) < 1.3) { end(s, "returned"); break; }
        if (s.left <= 0 && !s.o.returns) { end(s, "range"); break; }
      }
      try { s.o.trail?.(s.dim, s.pos, prev, s.age, s); } catch (err) { report("projectile.trail", err); }
      if (s.done) shots.splice(i, 1);
    } catch (err) {
      report("projectiles", err);
      shots.splice(i, 1);
    }
  }
}

export function activeShots() { return shots.length; }

/** 持ち主の弾を全部消す（解除・退出）。 */
export function clearShots(ownerId) {
  for (const s of shots) if (s.owner?.id === ownerId) s.done = true;
}

export { now };
