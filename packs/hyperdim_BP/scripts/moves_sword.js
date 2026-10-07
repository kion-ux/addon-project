// ===========================================================================
//  大剣「ディメンション・ブレイカー」と 双剣「ゼファー＆ガスト」の技
// ===========================================================================
import {
  register, lunge, hover, plunge, ultOpen, warp, behind, safeAhead, dirTo, body, bodyStop,
} from "./engine.js";
import { enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy, hit } from "./combat.js";
import { P, arc, burst, slash, kanji, afterimage, sound, shake, flash, line, white } from "./fx.js";
import { add, rand, yawRotate, chest, dist, norm, sub, knock, valid } from "./util.js";

// ===========================================================================
//  大剣 — 蒼の次元断。重く、溜めが長く、一撃と範囲が大きい
// ===========================================================================
register("greatsword", {
  /** 戦技「次元断」: 溜めて振り下ろすと、次元の裂け目が地を這って 12m 先まで走る。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "heavy");
    sound(dim, "hd.charge", p.location, 0.9, 0.9);
    P(dim, "circle", { ...p.location, y: p.location.y + 0.05 }, { color: c, size: 2.2, life: 0.9, spin: 120 });
    ctx.every(0, 6, 2, (i) => {
      P(dim, "converge", ctx.front(1.0, 2.6), { color: hot, count: 8, spread: 2.0, life: 0.35, size: 0.9 });
      P(dim, "orbit", ctx.chest(), { color: c, count: 4, spread: 1.6, life: 0.5 });
    });
    ctx.at(14, () => {
      const f = ctx.liveDir();
      sound(dim, "hd.swing_heavy", p.location, 0.8, 1.0);
      sound(dim, "hd.boom", p.location, 1.3, 0.8);
      shake(dim, p.location, 14, 0.35, 0.35);
      arc(dim, ctx.chest(), f, 2.4, -70, 80, 90, c, { size: 1.3, steps: 16 });
      const base = { ...p.location };
      for (let k = 0; k < 9; k++) {
        ctx.at(k, () => {
          const d = 1.6 + k * 1.3;
          const at = { x: base.x + f.x * d, y: base.y, z: base.z + f.z * d };
          slash(dim, { ...at, y: at.y + 1.3 }, c, rand(-8, 8), 1.4 + k * 0.05, "slash_big", 0.3);
          P(dim, "crack_flat", { ...at, y: at.y + 0.06 }, { color: c, size: 1.0, rot: rand(0, 360), life: 1.2 });
          P(dim, "rift", { ...at, y: at.y + 0.9 }, { color: hot, size: 0.8, rot: 90 + rand(-15, 15), life: 0.5 });
          P(dim, "star", { ...at, y: at.y + 1.0 }, { color: hot, count: 3, spread: 0.6 });
          P(dim, "pillar", { ...at, y: at.y + 1.5 }, { color: c, size: 0.6, height: 3.2, life: 0.35 });
          for (const e of enemiesNear(p, { ...at, y: at.y + 1 }, 1.9)) {
            if (ctx.once(e)) hit(p, e, 10, { color: c, kb: 0.9, up: 0.35, dir: f, power: 1.5, sound: "hd.hit_heavy" });
          }
        });
      }
    });
    return 28;
  },

  /** 突進技「流星突」: 切先を前に突き出して一直線に駆け抜け、最後に炸裂する。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    const f = ctx.f;
    body(p, "lunge");
    sound(dim, "hd.dash", p.location, 0.8, 1.0);
    lunge(ctx, f, 1.55, 0.1);
    P(dim, "ring", ctx.chest(), { color: c, size: 1.8, life: 0.25 });
    ctx.every(0, 9, 1, (i) => {
      const l = p.location;
      afterimage(dim, l, c, 0.35);
      P(dim, "trail", ctx.front(1.8, 1.1), { color: hot, size: 1.6, life: 0.2 });
      P(dim, "speedline", { x: l.x, y: l.y + 1, z: l.z }, { color: c, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 14 });
      for (const e of enemiesNear(p, ctx.front(1.0, 1.0), 2.3)) {
        if (ctx.once(e)) hit(p, e, 7, { color: c, kb: 1.1, up: 0.25, dir: f, sound: "hd.hit_slash" });
      }
    });
    ctx.at(10, () => {
      const at = ctx.front(1.6, 1.0);
      burst(dim, at, c, 2.0);
      P(dim, "star", at, { color: hot, count: 12, spread: 1.4, speed: 2 });
      P(dim, "ring_flat", { ...p.location, y: p.location.y + 0.1 }, { color: c, size: 3.2 });
      sound(dim, "hd.boom", at, 1.6, 0.6);
      shake(dim, at, 10, 0.25, 0.25);
      for (const e of enemiesNear(p, at, 3.0)) {
        hit(p, e, 4, { color: c, kb: 0.8, up: 0.4, dir: f });
      }
    });
    return 16;
  },

  /** 空中技「天墜」: 宙で一瞬止まり、真下へ叩きつけて次元の柱を六本立てる。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    hover(ctx, 8, 0.45);
    body(p, "plunge");
    sound(dim, "hd.charge", p.location, 1.3, 0.7);
    P(dim, "circle2", { ...p.location, y: p.location.y - 0.5 }, { color: c, size: 1.8, life: 0.6, spin: -200 });
    ctx.at(7, () => {
      sound(dim, "hd.swing_heavy", p.location, 0.7, 1.0);
      plunge(ctx, (l) => {
        body(p, "land");
        sound(dim, "hd.boom", l, 1.0, 1.0);
        shake(dim, l, 16, 0.45, 0.4);
        P(dim, "ring_flat", { ...l, y: l.y + 0.08 }, { color: c, size: 5.5, life: 0.5 });
        P(dim, "ring_thin_flat", { ...l, y: l.y + 0.1 }, { color: hot, size: 7, life: 0.7 });
        P(dim, "dust", { ...l, y: l.y + 0.1 }, { count: 22, speed: 7, size: 1.6 });
        for (let k = 0; k < 6; k++) {
          const a = k * 60 + 30;
          const q = add(l, yawRotate({ x: 1, y: 0, z: 0 }, a), 3.4);
          ctx.at(k, () => {
            P(dim, "pillar", { ...q, y: q.y + 2.5 }, { color: c, size: 0.9, height: 5.5, life: 0.5 });
            P(dim, "crack_flat", { ...q, y: q.y + 0.06 }, { color: c, size: 1.2, rot: a, life: 1.2 });
          });
        }
        for (const e of enemiesNear(p, l, 5.2)) {
          hit(p, e, 9, { color: c, kb: 0.7, up: 0.65, power: 1.6, sound: "hd.hit_heavy" });
        }
      });
    });
    return 30;
  },

  /** 必殺「終焉次元斬・アポカリプス」: 時を止め、空間ごと七度断ち、最後に天から斬り落とす。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 84, 14);
    const centre = { ...p.location };
    P(dim, "circle2", { ...centre, y: centre.y + 0.07 }, { color: hot, size: 5.5, life: 3.6, spin: -40 });
    ctx.every(0, 10, 2, () => {
      P(dim, "star", { x: centre.x + rand(-6, 6), y: centre.y + rand(0.5, 4), z: centre.z + rand(-6, 6) },
        { color: hot, count: 2, spread: 0.3 });
      P(dim, "converge", { ...ctx.chest(), y: p.location.y + 3.2 }, { color: c, count: 6, spread: 3, life: 0.4 });
    });
    ctx.at(4, () => P(dim, "pillar", { ...centre, y: centre.y + 6 }, { color: c, size: 2.2, height: 14, life: 1.0 }));
    // 七度の次元断: 敵を通る直線で空間を切り裂く
    for (let k = 0; k < 7; k++) {
      ctx.at(20 + k * 4, () => {
        const foes = enemiesNear(p, centre, 14);
        const tgt = foes.length ? foes[k % foes.length] : null;
        const mid = tgt ? chest(tgt) : { x: centre.x + rand(-5, 5), y: centre.y + rand(1, 3), z: centre.z + rand(-5, 5) };
        const ang = rand(0, Math.PI);
        const d = { x: Math.cos(ang), y: rand(-0.5, 0.5), z: Math.sin(ang) };
        const a = add(mid, d, -7), b = add(mid, d, 7);
        line(dim, "trail", a, b, 0.45, { color: white(c, 0.3), size: 0.9, life: 0.4 });
        P(dim, "rift", mid, { color: hot, size: 2.2, rot: rand(0, 180), life: 0.9 });
        slash(dim, mid, c, rand(0, 360), 1.8, "slash_thin", 0.3);
        sound(dim, "hd.hit_slash", mid, 0.8 + k * 0.08, 1.0);
        for (const e of enemiesOnLine(p, a, b, 1.4)) {
          hit(p, e, 2.5, { color: c, power: 1.2, gauge: 0 });
        }
      });
    }
    // 天からの一太刀
    ctx.at(50, () => {
      body(p, "ult_slam");
      sound(dim, "hd.swing_heavy", p.location, 0.6, 1.2);
      arc(dim, ctx.chest(), ctx.liveDir(), 4.5, -100, 90, 90, c, { size: 2.2, steps: 22, life: 0.4 });
    });
    ctx.at(54, () => {
      const at = ctx.front(3.0, 1.5);
      slash(dim, at, c, 0, 3.4, "slash_big", 0.6);
      P(dim, "flare", at, { color: white(c, 0.6), size: 5, life: 0.4 });
      kanji(dim, add(at, { x: 0, y: 1.8, z: 0 }), 0, c, 3.2);
      flash(dim, centre, 30, [1, 1, 1], 0.1, 0.5);
      sound(dim, "hd.boom", at, 0.8, 1.6);
      shake(dim, centre, 24, 0.7, 0.6);
      P(dim, "ring_flat", { ...centre, y: centre.y + 0.1 }, { color: c, size: 10, life: 0.7 });
      for (const e of enemiesNear(p, centre, 10.5)) {
        hit(p, e, 12, { color: c, kb: 1.4, up: 0.6, power: 2.2, crit: true, gauge: 0, sound: "hd.hit_heavy" });
      }
    });
    ctx.every(60, 8, 3, () => {
      P(dim, "star", { x: centre.x + rand(-7, 7), y: centre.y + rand(2, 6), z: centre.z + rand(-7, 7) },
        { color: hot, count: 3, spread: 0.5, life: 1.4 });
    });
    return 64;
  },
});

// ===========================================================================
//  双剣 — 翠の疾風。軽く、手数が多く、跳ね回る
// ===========================================================================
register("twinblades", {
  /** 戦技「疾風連刃」: 左右の刃で六連、最後に十字で吹き飛ばす。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "rapid");
    ctx.every(0, 6, 3, (i) => {
      const f = ctx.liveDir();
      const side = i % 2 ? 1 : -1;
      arc(dim, ctx.chest(), f, 1.9, side * 70, -side * 60, side * rand(10, 40), c, { size: 0.8, steps: 10, life: 0.18 });
      slash(dim, ctx.front(1.6, 1.1), c, side * rand(30, 70) + (side > 0 ? 180 : 0), 0.9, "slash_thin");
      P(dim, "wind", ctx.front(1.0, 1.0), { color: hot, count: 2, dir: f, speed: 6 });
      sound(dim, "hd.swing", p.location, 1.2 + i * 0.05, 0.8);
      lunge(ctx, f, 0.25, 0.0);
      for (const e of enemiesInCone(p, ctx.chest(), f, 3.6, 70)) {
        hit(p, e, 1.6, { color: c, power: 0.8, gauge: 2, sound: "hd.hit_slash" });
      }
    });
    ctx.at(18, () => {
      const f = ctx.liveDir();
      const at = ctx.front(1.8, 1.1);
      P(dim, "cross", at, { color: white(c, 0.2), size: 1.4 });
      P(dim, "wind", at, { color: c, count: 8, dir: f, speed: 9, spread: 0.6 });
      sound(dim, "hd.wind", at, 1.2, 1.0);
      for (const e of enemiesInCone(p, ctx.chest(), f, 3.8, 75)) {
        hit(p, e, 3.5, { color: c, kb: 1.0, up: 0.35, dir: f, power: 1.3 });
      }
    });
    return 22;
  },

  /** 突進技「旋風斬」: 竜巻をまとって回転しながら駆け抜ける。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "whirl");
    sound(dim, "hd.wind", p.location, 1.0, 1.0);
    lunge(ctx, ctx.f, 1.25, 0.12);
    ctx.every(0, 10, 2, (i) => {
      const l = p.location;
      P(dim, "vortex", l, { color: c, size: 1.6, height: 2.6, life: 0.3, rate: 70 });
      P(dim, "slash_flat", { ...l, y: l.y + 1.0 }, { color: c, size: 1.1, rot: i * 72 });
      if (i % 2 === 0) {
        sound(dim, "hd.swing", l, 1.3, 0.6);
        for (const e of enemiesNear(p, { ...l, y: l.y + 1 }, 2.7)) {
          if (ctx.once(e, 3)) hit(p, e, 2.2, { color: c, kb: 0.4, up: 0.2, power: 0.9, sound: "hd.hit_slash" });
        }
      }
    });
    ctx.at(21, () => {
      bodyStop(p);
      P(dim, "ring_flat", { ...p.location, y: p.location.y + 0.1 }, { color: c, size: 3.0 });
      P(dim, "wind", ctx.chest(), { color: hot, count: 10, dir: { x: 0, y: 1, z: 0 }, speed: 6, spread: 1.2 });
    });
    return 22;
  },

  /** 空中技「燕返し」: 前の敵へ斜めに急降下して十字に斬り、宙返りで離脱する。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    const tgt = nearestEnemy(p, p.location, 9, ctx.v, 55);
    const aim = tgt ? chest(tgt) : add(p.location, { x: ctx.f.x * 6, y: -2, z: ctx.f.z * 6 });
    const to = sub(aim, p.location);
    const d = norm(to);
    body(p, "frontflip");
    sound(dim, "hd.dash", p.location, 1.3, 0.9);
    knock(p, d.x, d.z, Math.min(1.6, Math.hypot(to.x, to.z) * 0.22 + 0.4), Math.max(-1.6, d.y * 1.2));
    let done = false;
    for (let t = 1; t <= 9; t++) {
      ctx.at(t, () => {
        if (done) return;
        afterimage(dim, p.location, c, 0.3);
        const near = tgt && dist(p.location, tgt.location) < 2.6;
        if (near || t === 9 || p.isOnGround) {
          done = true;
          const at = ctx.front(1.0, 1.0);
          P(dim, "cross", at, { color: white(c, 0.25), size: 1.6 });
          arc(dim, ctx.chest(), ctx.liveDir(), 1.8, -80, 80, 45, c, { size: 0.9 });
          arc(dim, ctx.chest(), ctx.liveDir(), 1.8, 80, -80, -45, c, { size: 0.9 });
          sound(dim, "hd.hit_slash", at, 1.2, 1.0);
          for (const e of enemiesNear(p, at, 2.8)) {
            hit(p, e, 7, { color: c, kb: 0.3, up: -0.2, power: 1.4 });
          }
          ctx.at(2, () => {
            body(p, "backflip", "hd.move");
            const f = ctx.liveDir();
            knock(p, -f.x, -f.z, 0.7, 0.7);
            P(dim, "wind", ctx.chest(), { color: hot, count: 6, dir: { x: 0, y: 1, z: 0 }, speed: 5 });
          });
        }
      });
    }
    return 18;
  },

  /** 必殺「千刃嵐舞・テンペスト」: 周りの敵の間を風になって渡り斬り、竜巻で締める。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 80, 14);
    const home = { ...p.location };
    let foes = enemiesNear(p, home, 14).slice(0, 6);
    const hops = Math.max(4, foes.length);
    let last = { ...home };
    for (let k = 0; k < hops; k++) {
      ctx.at(10 + k * 7, () => {
        foes = foes.filter((e) => valid(e));
        const tgt = foes.length ? foes[k % foes.length] : null;
        const from = { ...p.location };
        let dest;
        if (tgt) {
          const side = yawRotate(dirTo(tgt.location, from), rand(-70, 70));
          dest = safeAhead(dim, tgt.location, side, 1.6);
        } else {
          dest = safeAhead(dim, home, yawRotate(ctx.f, k * 90), 3.5);
        }
        afterimage(dim, from, c, 0.6);
        line(dim, "trail", { ...from, y: from.y + 1 }, { ...dest, y: dest.y + 1 }, 0.5,
          { color: white(c, 0.2), size: 0.8, life: 0.35 });
        warp(p, dest, tgt ? chest(tgt) : undefined);
        body(p, k % 2 ? "combo1" : "combo2");
        const at = tgt ? chest(tgt) : { ...dest, y: dest.y + 1 };
        slash(dim, at, c, rand(0, 360), 1.3, "slash");
        P(dim, "cross", at, { color: hot, size: 1.1 });
        P(dim, "wind", at, { color: c, count: 6, speed: 7, spread: 0.6 });
        sound(dim, "hd.hit_slash", at, 1.0 + k * 0.06, 1.0);
        if (tgt) hit(p, tgt, 4, { color: c, power: 1.3, gauge: 0 });
        last = dest;
      });
    }
    const end = 12 + hops * 7;
    ctx.at(end, () => {
      const centre = foes.length ? foes[0].location : last;
      P(dim, "vortex", centre, { color: c, size: 2.8, height: 7, life: 1.4, rate: 120 });
      P(dim, "vortex", centre, { color: hot, size: 1.6, height: 5, life: 1.2, rate: 80 });
      kanji(dim, { ...centre, y: centre.y + 3.5 }, 0, c, 3.0);
      flash(dim, centre, 24, white(c, 0.5), 0.05, 0.35);
      sound(dim, "hd.wind", centre, 0.8, 1.6);
      sound(dim, "hd.boom", centre, 1.4, 0.8);
      shake(dim, centre, 18, 0.5, 0.5);
      for (const e of enemiesNear(p, centre, 5.5)) {
        hit(p, e, 7, { color: c, kb: 0.2, up: 1.05, power: 2, crit: true, gauge: 0 });
      }
    });
    return end + 6;
  },
});
