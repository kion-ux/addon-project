// ===========================================================================
//  両手斧「ヴォルカニクス」と 両手かぎ爪「ベヒモス」の技
// ===========================================================================
import {
  register, lunge, hover, plunge, ultOpen, warp, safeAhead, dirTo, body, bodyStop,
} from "./engine.js";
import { enemiesNear, enemiesInCone, nearestEnemy, hit } from "./combat.js";
import { P, arc, burst, slash, kanji, afterimage, sound, shake, flash, ring, white } from "./fx.js";
import { add, rand, yawRotate, chest, dist, effect, knock, valid } from "./util.js";

function ignite(e, secs) {
  try { e.setOnFire(secs, true); } catch (_) { }
}

/** 地面から炎が噴き上がる一点。 */
function eruption(ctx, at, scaleK = 1, dmg = 7, radius = 2.3, gauge = 3) {
  const { p, dim, c, hot } = ctx;
  P(dim, "pillar", { ...at, y: at.y + 2.2 * scaleK }, { color: c, size: 0.9 * scaleK, height: 4.5 * scaleK, life: 0.5 });
  P(dim, "flame", { ...at, y: at.y + 0.3 }, { color: c, count: Math.round(12 * scaleK), spread: 0.7 * scaleK, speed: 2.5, size: 1.4 * scaleK, life: 0.7 });
  P(dim, "ring_flat", { ...at, y: at.y + 0.08 }, { color: c, size: 1.6 * scaleK, life: 0.4 });
  P(dim, "shard", { ...at, y: at.y + 0.3 }, { color: [0.42, 0.3, 0.26], count: 8, speed: 7, grav: -20, size: 1.4 });
  P(dim, "ember", { ...at, y: at.y + 0.5 }, { color: hot, count: 10, spread: 1.0, speed: 1.5 });
  P(dim, "smoke", { ...at, y: at.y + 1.2 }, { color: [0.2, 0.17, 0.18], count: 4, spread: 0.8, size: 1.6 });
  P(dim, "crack_flat", { ...at, y: at.y + 0.05 }, { color: c, size: 1.0 * scaleK, rot: rand(0, 360), life: 1.6 });
  sound(dim, "hd.fire", at, rand(0.85, 1.1), 0.9);
  for (const e of enemiesNear(p, { ...at, y: at.y + 1 }, radius)) {
    if (ctx.once(e)) {
      hit(p, e, dmg, { color: c, up: 0.55, kb: 0.3, power: 1.4, sound: "hd.hit_heavy", gauge });
      ignite(e, 3);
    }
  }
}

// ===========================================================================
//  両手斧 — 紅蓮。地面ごと叩き割り、炎を噴かせる
// ===========================================================================
register("greataxe", {
  /** 戦技「爆炎断」: 振り下ろした地点から前へ三度、溶岩が噴き上がる。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "heavy");
    sound(dim, "hd.charge", p.location, 0.75, 0.8);
    ctx.every(0, 6, 2, () => {
      P(dim, "flame", ctx.front(0.4, 2.8), { color: c, count: 4, spread: 0.4, speed: 1.0 });
      P(dim, "aura", p.location, { color: c, count: 3, spread: 0.6 });
    });
    ctx.at(14, () => {
      const f = ctx.liveDir();
      arc(dim, ctx.chest(), f, 2.6, -80, 75, 90, c, { size: 1.3, steps: 16 });
      sound(dim, "hd.hit_heavy", p.location, 0.7, 1.2);
      shake(dim, p.location, 14, 0.4, 0.35);
      const base = { ...p.location };
      [2.4, 5.0, 7.6].forEach((d, k) => {
        ctx.at(k * 3, () => eruption(ctx, { x: base.x + f.x * d, y: base.y, z: base.z + f.z * d }, 1 + k * 0.15));
      });
    });
    return 30;
  },

  /** 突進技「炎輪旋」: 斧を振り回し、炎の輪をまとって前進し続ける。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "whirl");
    sound(dim, "hd.fire", p.location, 0.8, 1.0);
    ctx.every(0, 11, 3, (i) => {
      const f = ctx.liveDir();
      if (i % 2 === 0) lunge(ctx, f, 0.75, 0.05);
      const l = p.location;
      ring(dim, "flame", l, 2.2, 8, { color: c, count: 1, spread: 0.1, speed: 0.6, size: 1.1 }, 0.4);
      P(dim, "slash_flat", { ...l, y: l.y + 1.0 }, { color: c, size: 1.3, rot: i * 95 });
      sound(dim, "hd.swing_heavy", l, 1.1 + (i % 3) * 0.08, 0.7);
      if (i % 2 === 0) {
        for (const e of enemiesNear(p, { ...l, y: l.y + 1 }, 2.9)) {
          if (ctx.once(e, 4)) {
            hit(p, e, 2.5, { color: c, kb: 0.6, up: 0.15, power: 1.0, sound: "hd.hit_heavy" });
            ignite(e, 2);
          }
        }
      }
    });
    ctx.at(34, () => {
      bodyStop(p);
      burst(dim, ctx.chest(), c, 1.6);
      P(dim, "ring_flat", { ...p.location, y: p.location.y + 0.1 }, { color: c, size: 3.4 });
    });
    return 34;
  },

  /** 空中技「隕鉄落」: 隕石のように落ち、着地点をクレーターにする。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    hover(ctx, 6, 0.55);
    body(p, "plunge");
    P(dim, "flame", ctx.chest(), { color: c, count: 10, spread: 0.6 });
    ctx.at(6, () => {
      plunge(ctx, (l) => {
        body(p, "land");
        sound(dim, "hd.boom", l, 0.8, 1.2);
        shake(dim, l, 16, 0.5, 0.45);
        P(dim, "ring_flat", { ...l, y: l.y + 0.08 }, { color: c, size: 6, life: 0.5 });
        P(dim, "dust", { ...l, y: l.y + 0.1 }, { count: 24, speed: 7, size: 1.8 });
        for (let k = 0; k < 8; k++) {
          const q = add(l, yawRotate({ x: 1, y: 0, z: 0 }, k * 45), 3.0);
          ctx.at(1 + (k % 2) * 2, () => {
            P(dim, "flame", { ...q, y: q.y + 0.2 }, { color: c, count: 6, spread: 0.4, speed: 2.5, size: 1.2 });
            P(dim, "crack_flat", { ...q, y: q.y + 0.05 }, { color: c, size: 1.3, rot: k * 45, life: 1.6 });
          });
        }
        P(dim, "shard", { ...l, y: l.y + 0.4 }, { color: [0.35, 0.26, 0.22], count: 16, speed: 9, grav: -20, size: 1.6 });
        for (const e of enemiesNear(p, l, 5.5)) {
          hit(p, e, 9, { color: c, kb: 0.7, up: 0.7, power: 1.7, sound: "hd.hit_heavy" });
          ignite(e, 4);
        }
      }, 34, 3.0);
    });
    return 30;
  },

  /** 必殺「紅蓮獄炎・ヴォルカニック・エンド」: 五つの火口が噴き、最後に大地が爆ぜる。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 90, 12);
    const centre = { ...p.location };
    ctx.at(18, () => {
      body(p, "ult_slam");
      sound(dim, "hd.hit_heavy", centre, 0.6, 1.5);
      shake(dim, centre, 20, 0.5, 0.4);
      P(dim, "crack_flat", { ...centre, y: centre.y + 0.05 }, { color: c, size: 3.5, rot: 0, life: 3.0 });
      P(dim, "crack_flat", { ...centre, y: centre.y + 0.05 }, { color: c, size: 3.5, rot: 72, life: 3.0 });
    });
    for (let k = 0; k < 5; k++) {
      ctx.at(24 + k * 4, () => {
        const q = add(centre, yawRotate(ctx.f, k * 72), 4.6);
        ctx.struck.clear();
        eruption(ctx, q, 1.8, 4, 3.0, 0);
        P(dim, "pillar", { ...q, y: q.y + 5 }, { color: hot, size: 1.4, height: 10, life: 0.8 });
      });
    }
    ctx.at(48, () => {
      P(dim, "circle", { ...centre, y: centre.y + 0.08 }, { color: c, size: 7, life: 1.4, spin: 200 });
      P(dim, "converge", { ...centre, y: centre.y + 1 }, { color: hot, count: 30, spread: 8, life: 0.6, size: 1.6 });
      sound(dim, "hd.charge", centre, 0.6, 1.4);
    });
    ctx.at(62, () => {
      flash(dim, centre, 32, [1, 0.55, 0.3], 0.1, 0.5);
      sound(dim, "hd.boom", centre, 0.6, 2.0);
      sound(dim, "hd.fire", centre, 0.7, 1.6);
      shake(dim, centre, 28, 0.9, 0.7);
      P(dim, "ring_flat", { ...centre, y: centre.y + 0.1 }, { color: c, size: 11, life: 0.8 });
      P(dim, "impact", { ...centre, y: centre.y + 1.5 }, { color: hot, size: 6, life: 0.3 });
      P(dim, "flare", { ...centre, y: centre.y + 1.5 }, { color: white(c, 0.5), size: 6 });
      P(dim, "flame", { ...centre, y: centre.y + 0.5 }, { color: c, count: 40, spread: 4, speed: 4, size: 2 });
      P(dim, "smoke", { ...centre, y: centre.y + 2 }, { color: [0.18, 0.14, 0.14], count: 16, spread: 3, size: 3, speed: 2 });
      kanji(dim, { ...centre, y: centre.y + 4.5 }, 2, c, 4.0);
      for (const e of enemiesNear(p, centre, 9.5)) {
        hit(p, e, 14, { color: c, kb: 1.2, up: 1.0, power: 2.4, crit: true, gauge: 0, sound: "hd.hit_heavy" });
        ignite(e, 6);
      }
    });
    return 70;
  },
});

// ===========================================================================
//  かぎ爪 — 琥珀の獣。至近距離で引き裂き、跳びかかる
// ===========================================================================
function clawMark(ctx, at, rot, size = 1.2) {
  const { dim, c, hot } = ctx;
  P(dim, "claw", at, { color: c, rot, size });
  P(dim, "spark", at, { color: hot, count: 5, speed: 5 });
}

register("claws", {
  /** 戦技「獣王連爪」: 左右交互の四連撃から、両爪の大十字。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "rapid");
    ctx.every(0, 4, 4, (i) => {
      const f = ctx.liveDir();
      lunge(ctx, f, 0.35, 0.0);
      const side = i % 2 ? 1 : -1;
      clawMark(ctx, ctx.front(1.5, 1.1), side * rand(20, 40), 1.1);
      sound(dim, "hd.swing", p.location, 1.3 + i * 0.05, 0.8);
      for (const e of enemiesInCone(p, ctx.chest(), f, 3.4, 65)) {
        hit(p, e, 2.4, { color: c, power: 0.9, sound: "hd.hit_slash" });
      }
    });
    ctx.at(16, () => {
      body(p, "clawx");
      const f = ctx.liveDir();
      const at = ctx.front(1.7, 1.1);
      ctx.at(3, () => {
        clawMark(ctx, at, 45, 1.8);
        clawMark(ctx, at, -45, 1.8);
        burst(dim, at, c, 1.4);
        sound(dim, "hd.hit_heavy", at, 1.2, 1.0);
        for (const e of enemiesInCone(p, ctx.chest(), f, 3.6, 70)) {
          hit(p, e, 4.5, { color: c, kb: 1.0, up: 0.4, dir: f, power: 1.4 });
        }
      });
    });
    return 24;
  },

  /** 突進技「猛獣突進」: 弧を描いて跳びかかり、組み伏せて裂く。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "clawx");
    sound(dim, "hd.roar", p.location, 1.5, 0.5);
    lunge(ctx, ctx.f, 1.25, 0.55);
    let done = false;
    for (let t = 1; t <= 14; t++) {
      ctx.at(t, () => {
        if (done) return;
        afterimage(dim, p.location, c, 0.3);
        const foes = enemiesNear(p, ctx.front(0.8, 0.8), 2.4);
        if (foes.length || (t > 4 && p.isOnGround)) {
          done = true;
          const at = ctx.front(1.2, 1.0);
          clawMark(ctx, at, 30, 1.6);
          clawMark(ctx, at, -30, 1.6);
          P(dim, "dust", { ...p.location, y: p.location.y + 0.1 }, { count: 10, speed: 4 });
          sound(dim, "hd.hit_heavy", at, 1.1, 1.0);
          for (const e of foes.length ? foes : enemiesNear(p, at, 2.6)) {
            hit(p, e, 8, { color: c, kb: 0.2, up: -0.3, power: 1.5 });
            effect(e, "slowness", 24, 3);
          }
        }
      });
    }
    return 16;
  },

  /** 空中技「天裂爪」: 斬り上げで自分も敵も空へ打ち上げる。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "uppercut");
    sound(dim, "hd.swing", p.location, 0.9, 1.0);
    ctx.at(2, () => {
      knock(p, ctx.f.x, ctx.f.z, 0.3, 0.75);
      const f = ctx.liveDir();
      arc(dim, ctx.chest(), f, 2.0, 100, -60, 90, c, { size: 1.0 });
      clawMark(ctx, ctx.front(1.4, 1.6), 90, 1.8);
      P(dim, "speedline", ctx.chest(), { color: hot, count: 8, dir: { x: 0, y: -1, z: 0 }, speed: 12 });
      for (const e of enemiesInCone(p, ctx.chest(), f, 3.8, 75)) {
        hit(p, e, 7, { color: c, up: 1.1, kb: 0.15, dir: f, power: 1.5, sound: "hd.hit_heavy" });
      }
    });
    return 16;
  },

  /** 必殺「獣神解放・ベヒモス・ロア」: 咆哮で薙ぎ払い、一体に十二連の乱撃。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 80, 0);
    body(p, "roar");
    const centre = { ...p.location };
    ctx.at(4, () => {
      sound(dim, "hd.roar", centre, 0.9, 1.6);
      shake(dim, centre, 22, 0.6, 0.6);
      [3, 6, 9].forEach((r, k) => ctx.at(k * 2, () =>
        P(dim, "ring_flat", { ...centre, y: centre.y + 0.1 + k * 0.3 }, { color: c, size: r, life: 0.5 })));
      P(dim, "dust", { ...centre, y: centre.y + 0.1 }, { count: 30, speed: 9, size: 1.8 });
      P(dim, "aura", centre, { color: c, count: 20, spread: 1.0, size: 1.6 });
      for (let k = 0; k < 6; k++) {
        const q = add(centre, yawRotate({ x: 1, y: 0, z: 0 }, k * 60 + rand(-15, 15)), rand(1.5, 3.5));
        P(dim, "bolt", { ...q, y: q.y + 1.4 }, { color: hot, size: 1.3, life: 0.2 });
      }
      for (const e of enemiesNear(p, centre, 10)) {
        hit(p, e, 3, { color: c, kb: 1.4, up: 0.4, power: 1.0, gauge: 0 });
        effect(e, "weakness", 100, 1);
        effect(e, "slowness", 30, 4);
      }
      effect(p, "strength", 200, 1);
      effect(p, "speed", 200, 1);
    });
    let tgt;
    ctx.at(18, () => {
      tgt = nearestEnemy(p, p.location, 11);
      if (tgt) {
        const spot = safeAhead(dim, tgt.location, dirTo(tgt.location, p.location), 1.3);
        afterimage(dim, p.location, c, 0.5);
        warp(p, spot, chest(tgt));
        effect(tgt, "slowness", 50, 6);
      }
    });
    for (let k = 0; k < 12; k++) {
      ctx.at(22 + k * 3, () => {
        if (k % 3 === 0) body(p, k % 2 ? "combo1" : "combo2");
        const at = tgt && valid(tgt) ? chest(tgt) : ctx.front(1.5, 1.1);
        clawMark(ctx, add(at, { x: rand(-0.4, 0.4), y: rand(-0.4, 0.4), z: rand(-0.4, 0.4) }), rand(0, 360), 1.2);
        sound(dim, "hd.hit_slash", at, 0.9 + k * 0.04, 0.8);
        if (tgt && valid(tgt)) hit(p, tgt, 1.4, { color: c, power: 0.8, gauge: 0, quiet: k % 2 === 1 });
      });
    }
    ctx.at(60, () => body(p, "clawx"));
    ctx.at(63, () => {
      const at = tgt && valid(tgt) ? chest(tgt) : ctx.front(1.6, 1.1);
      clawMark(ctx, at, 45, 3.0);
      clawMark(ctx, at, -45, 3.0);
      P(dim, "cross", at, { color: white(c, 0.4), size: 2.4 });
      kanji(dim, add(at, { x: 0, y: 1.8, z: 0 }), 1, c, 3.2);
      flash(dim, at, 26, white(c, 0.4), 0.06, 0.4);
      sound(dim, "hd.boom", at, 1.1, 1.4);
      shake(dim, at, 20, 0.7, 0.5);
      for (const e of enemiesNear(p, at, 4)) {
        hit(p, e, 10, { color: c, kb: 0.6, up: 1.1, power: 2.2, crit: true, gauge: 0 });
      }
    });
    return 70;
  },
});
