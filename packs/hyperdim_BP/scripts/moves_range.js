// ===========================================================================
//  ダガー「ノクス」・弓「アストライア」・盾「グレイシャル・イージス」・鞭「ローゼンケッテ」の技
// ===========================================================================
import {
  register, lunge, hover, plunge, ultOpen, warp, behind, safeAhead, standable, dirTo, body,
  bodyStop,
} from "./engine.js";
import { enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy, hit, freeze, bind, isTarget } from "./combat.js";
import { P, burst, slash, kanji, afterimage, sound, shake, flash, line, white } from "./fx.js";
import { shoot, blocked } from "./projectiles.js";
import { markAirborne } from "./mobility.js";
import {
  add, rand, yawRotate, chest, dist, norm, sub, effect, knock, valid, health, viewDir,
} from "./util.js";

function eye(p) {
  try { return p.getHeadLocation(); } catch (_) { return { ...p.location, y: p.location.y + 1.6 }; }
}

// ===========================================================================
//  ダガー — 紫の影。投げ・背後取り・闇
// ===========================================================================
register("dagger", {
  /** 戦技「影縫い」: 影の苦無を三本、扇に投げる。刺さった相手は影に縫い止められる。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "throw");
    sound(dim, "hd.shadow", p.location, 1.4, 0.8);
    ctx.at(3, () => {
      const v = viewDir(p);
      for (const deg of [-9, 0, 9]) {
        const d = norm(yawRotate(v, deg));
        shoot(p, add(eye(p), d, 0.8), d, {
          speed: 1.6, range: 24, radius: 0.5,
          trail: (dm, pos, prev) => {
            P(dm, "trail", pos, { color: c, size: 0.5, life: 0.25 });
            P(dm, "trail", prev, { color: ctx.deep, size: 0.35, life: 0.3 });
          },
          onHit: (e) => {
            hit(p, e, 4, { color: c, power: 0.9, sound: "hd.hit_slash" });
            bind(e, 50);
            P(dim, "circle", { ...e.location, y: e.location.y + 0.05 }, { color: c, size: 0.9, life: 2.4, spin: 30 });
            P(dim, "smoke", chest(e), { color: [0.16, 0.08, 0.22], count: 5, spread: 0.5, size: 1.2 });
          },
          onEnd: (pos) => P(dim, "cross", pos, { color: c, size: 0.6, life: 0.2 }),
        });
      }
    });
    return 10;
  },

  /** 突進技「瞬影」: 前方の敵の背後へ瞬間移動し、背中を斬る。敵がいなければ前へ瞬身。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    const tgt = nearestEnemy(p, p.location, 12, ctx.f, 60);
    const from = { ...p.location };
    afterimage(dim, from, c, 0.6);
    P(dim, "smoke", { ...from, y: from.y + 1 }, { color: [0.12, 0.06, 0.18], count: 8, spread: 0.6, size: 1.4 });
    sound(dim, "hd.shadow", from, 1.2, 1.0);
    if (tgt) {
      let spot = behind(tgt, 1.4);
      if (!standable(dim, spot)) spot = safeAhead(dim, tgt.location, dirTo(tgt.location, from), 1.4);
      warp(p, spot, chest(tgt));
      line(dim, "trail", { ...from, y: from.y + 1 }, { ...spot, y: spot.y + 1 }, 0.6, { color: ctx.deep, size: 0.6, life: 0.4 });
      body(p, "stab");
      ctx.at(2, () => {
        const at = chest(tgt);
        slash(dim, at, c, rand(200, 250), 1.3, "slash");
        P(dim, "cross", at, { color: hot, size: 1.2 });
        sound(dim, "hd.hit_slash", at, 0.8, 1.1);
        hit(p, tgt, 8.5, { color: c, power: 1.5, crit: true, kb: 0.5, up: 0.2, dir: dirTo(p.location, tgt.location) });
        effect(tgt, "blindness", 30, 0);
      });
    } else {
      const spot = safeAhead(dim, from, ctx.f, 8);
      warp(p, spot);
      line(dim, "trail", { ...from, y: from.y + 1 }, { ...spot, y: spot.y + 1 }, 0.6, { color: c, size: 0.6, life: 0.35 });
      afterimage(dim, spot, c, 0.4);
    }
    return 10;
  },

  /** 空中技「影落とし」: 回りながら落ち、着地で影の刃を八方へ咲かせる。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "frontflip");
    sound(dim, "hd.shadow", p.location, 1.0, 1.0);
    plunge(ctx, (l) => {
      body(p, "land");
      sound(dim, "hd.hit_slash", l, 0.7, 1.2);
      for (let k = 0; k < 8; k++) {
        const q = add(l, yawRotate({ x: 1, y: 0, z: 0 }, k * 45), 2.6);
        P(dim, "slash_thin", { ...q, y: q.y + 0.8 }, { color: c, rot: k * 45, size: 0.9, life: 0.4 });
        P(dim, "trail", { ...q, y: q.y + 0.5 }, { color: ctx.deep, size: 0.9, life: 0.5 });
      }
      P(dim, "ring_flat", { ...l, y: l.y + 0.08 }, { color: c, size: 3.6, life: 0.4 });
      P(dim, "smoke", { ...l, y: l.y + 0.5 }, { color: [0.12, 0.06, 0.18], count: 10, spread: 1.6, size: 1.6 });
      for (const e of enemiesNear(p, l, 3.8)) {
        hit(p, e, 6.5, { color: c, kb: 0.5, up: 0.3, power: 1.3 });
        effect(e, "weakness", 60, 0);
        effect(e, "darkness", 60, 0);
      }
    }, 26, 2.2);
    return 18;
  },

  /** 必殺「冥夜幻葬・ノクターン」: 夜に溶けて八方から斬り、紫の月で葬る。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 80, 12);
    const centre = { ...p.location };
    flash(dim, centre, 26, [0.12, 0.02, 0.2], 0.25, 0.6);
    effect(p, "invisibility", 64, 0);
    P(dim, "moon", { ...centre, y: centre.y + 7 }, { color: hot, size: 5, life: 3.4, rot: -20 });
    let foes = enemiesNear(p, centre, 12).slice(0, 5);
    for (const e of foes) effect(e, "darkness", 80, 0);
    for (let k = 0; k < 8; k++) {
      ctx.at(10 + k * 6, () => {
        foes = foes.filter(valid);
        const tgt = foes.length ? foes[k % foes.length] : null;
        const at = tgt ? chest(tgt) : add(centre, yawRotate(ctx.f, k * 45), 3);
        const from = add(at, yawRotate({ x: 1, y: 0, z: 0 }, rand(0, 360)), 3.2);
        afterimage(dim, from, c, 0.5);
        line(dim, "trail", { ...from, y: at.y }, add(at, sub(at, { ...from, y: at.y })), 0.5,
          { color: white(c, 0.2), size: 0.6, life: 0.3 });
        slash(dim, at, c, rand(0, 360), 1.4, "slash_thin");
        sound(dim, "hd.hit_slash", at, 1.2 + k * 0.05, 0.8);
        if (tgt) hit(p, tgt, 2.4, { color: c, power: 1.0, gauge: 0 });
      });
    }
    ctx.at(60, () => {
      foes = foes.filter(valid);
      const main = foes[0];
      if (main) {
        const spot = behind(main, 1.5);
        if (standable(dim, spot)) warp(p, spot, chest(main));
      }
      try { p.removeEffect?.("invisibility"); } catch (_) { }
      body(p, "stab");
    });
    ctx.at(63, () => {
      for (const e of foes.filter(valid)) {
        const at = chest(e);
        P(dim, "moon", at, { color: c, size: 2.4, life: 0.8, rot: rand(0, 360) });
        slash(dim, at, white(c, 0.3), rand(0, 360), 2.2, "slash_big", 0.5);
        hit(p, e, 8, { color: c, power: 2.0, crit: true, gauge: 0, kb: 0.6, up: 0.3 });
      }
      kanji(dim, { ...ctx.chest(), y: p.location.y + 3 }, 3, c, 3.2);
      flash(dim, centre, 26, white(c, 0.3), 0.05, 0.4);
      sound(dim, "hd.boom", p.location, 1.3, 1.2);
      sound(dim, "hd.shadow", p.location, 0.7, 1.4);
      shake(dim, p.location, 20, 0.55, 0.5);
    });
    return 66;
  },
});

// ===========================================================================
//  弓 — 金の聖光。引き絞って放つ。右クリックを離した時の状況で技が変わる
// ===========================================================================
function lightArrow(ctx, from, dir, dmg, o = {}) {
  const { p, dim, c, hot } = ctx;
  shoot(p, from, dir, {
    speed: o.speed ?? 2.6, range: o.range ?? 56, radius: o.radius ?? 0.55, pierce: o.pierce ?? 0,
    trail: (dm, pos, prev, age) => {
      line(dm, "trail", prev, pos, 0.7, { color: o.big ? hot : c, size: o.big ? 0.9 : 0.5, life: 0.3 });
      if (o.big && age % 2 === 0) P(dm, "star", pos, { color: hot, count: 1, spread: 0.2, life: 0.6 });
    },
    onHit: (e) => {
      if (dmg <= 0) return;
      hit(p, e, dmg, { color: c, power: o.big ? 1.6 : 1.0, kb: o.kb ?? 0.4, up: 0.15, dir: norm({ ...dir, y: 0 }), sound: "hd.hit_slash" });
      if (o.big) P(dim, "star", chest(e), { color: hot, count: 8, spread: 0.6, speed: 2 });
    },
    onEnd: (pos, why) => {
      if (why === "block") P(dim, "spark", pos, { color: c, count: 6, speed: 4 });
    },
  });
}

register("bow", {
  /** 戦技「聖光矢」: 溜めた長さで三段階。最大まで引くと三本の貫通矢。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    const charge = ctx.extra.charge ?? 0;
    const lv = charge >= 20 ? 2 : charge >= 8 ? 1 : 0;
    const v = viewDir(p);
    const from = add(eye(p), v, 0.7);
    sound(dim, "hd.arrow", from, [1.2, 1.0, 0.85][lv], 1.0);
    P(dim, "ring", from, { color: c, size: [0.6, 1.0, 1.6][lv], life: 0.2 });
    if (lv === 0) {
      lightArrow(ctx, from, v, 4);
    } else if (lv === 1) {
      lightArrow(ctx, from, v, 7, { pierce: 2, big: true });
    } else {
      for (const deg of [-5, 0, 5]) lightArrow(ctx, from, norm(yawRotate(v, deg)), 6.5, { pierce: 3, big: true, speed: 3.0 });
      P(dim, "flare", from, { color: white(c, 0.4), size: 1.4, rot: rand(-10, 10) });
      sound(dim, "hd.beam", from, 1.6, 0.5);
    }
    return 4;
  },

  /** 突進技「宙返り三連射」: 後ろへ宙返りしながら三本を扇に放つ。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    const f = ctx.f;
    body(p, "backflip");
    knock(p, -f.x, -f.z, 0.95, 0.62);
    markAirborne(p);
    afterimage(dim, p.location, c, 0.5);
    sound(dim, "hd.dash", p.location, 1.2, 0.8);
    P(dim, "feather", ctx.chest(), { color: [1, 0.97, 0.88], count: 8, spread: 0.6, speed: 2 });
    ctx.at(5, () => {
      const v = viewDir(p);
      const from = add(eye(p), v, 0.7);
      for (const deg of [-12, 0, 12]) lightArrow(ctx, from, norm(yawRotate(v, deg)), 5, { pierce: 1 });
      sound(dim, "hd.arrow", from, 1.1, 1.0);
    });
    return 12;
  },

  /** 空中技「星雨」: 狙った地点に魔法陣を描き、天から光の矢を降らせる。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    let spot;
    try {
      const hitE = p.getEntitiesFromViewDirection?.({ maxDistance: 26 })?.[0]?.entity;
      if (hitE) spot = { ...hitE.location };
    } catch (_) { }
    if (!spot) {
      try {
        const b = p.getBlockFromViewDirection?.({ maxDistance: 26 })?.block;
        if (b) spot = { x: b.location.x + 0.5, y: b.location.y + 1, z: b.location.z + 0.5 };
      } catch (_) { }
    }
    spot ??= add(p.location, ctx.f, 12);
    hover(ctx, 40, 0.25);
    body(p, "aim");
    sound(dim, "hd.charge", p.location, 1.2, 0.7);
    P(dim, "circle", { ...spot, y: spot.y + 0.06 }, { color: c, size: 3.6, life: 2.2, spin: 90 });
    P(dim, "circle_v", { ...spot, y: spot.y + 9 }, { color: hot, size: 3.0, life: 2.0, spin: -60 });
    // 弓から空へ一本
    lightArrow(ctx, add(eye(p), { x: 0, y: 1, z: 0 }, 0.8), { x: 0, y: 1, z: 0 }, 0, { range: 12, big: true });
    ctx.every(8, 14, 2, (i) => {
      for (let k = 0; k < 2; k++) {
        const q = { x: spot.x + rand(-3.6, 3.6), y: spot.y + 9, z: spot.z + rand(-3.6, 3.6) };
        shoot(p, q, { x: rand(-0.05, 0.05), y: -1, z: rand(-0.05, 0.05) }, {
          speed: 2.2, range: 16, radius: 0.9,
          trail: (dm, pos, prev) => line(dm, "trail", prev, pos, 0.8, { color: c, size: 0.6, life: 0.25 }),
          onHit: (e) => hit(p, e, 2, { color: c, power: 0.8, gauge: 1 }),
          onEnd: (pos) => {
            P(dim, "star", pos, { color: hot, count: 3, spread: 0.3, speed: 1.5 });
            P(dim, "ring_flat", { ...pos, y: pos.y + 0.05 }, { color: c, size: 0.8, life: 0.25 });
          },
        });
      }
      if (i % 3 === 0) sound(dim, "hd.arrow", spot, 1.4 + rand(0, 0.3), 0.6);
    });
    ctx.at(40, () => bodyStop(p));
    return 38;
  },

  /** 必殺「天穹神弓・ジャッジメント」: 神弓の陣を前に展開し、極太の光線で貫く。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 70, 0);
    body(p, "aim");
    ctx.every(2, 12, 2, (i) => {
      const v = viewDir(p);
      const at = add(eye(p), v, 2.4);
      P(dim, "circle_v", at, { color: c, size: 1.6 + i * 0.08, life: 0.35, spin: 120 });
      P(dim, "converge", at, { color: hot, count: 10, spread: 3.5, life: 0.4 });
      P(dim, "feather", ctx.chest(), { color: [1, 0.98, 0.9], count: 1, spread: 1.4 });
    });
    ctx.at(28, () => {
      const v = viewDir(p);
      const a = add(eye(p), v, 1.2);
      // 光線の届く長さ: 壁で止まる
      let L = 36;
      for (let d = 1; d <= 36; d += 0.5) {
        if (blocked(dim, add(a, v, d))) { L = d; break; }
      }
      const b = add(a, v, L);
      sound(dim, "hd.beam", a, 0.8, 2.0);
      sound(dim, "hd.boom", a, 1.3, 1.2);
      flash(dim, a, 30, [1, 0.95, 0.75], 0.08, 0.45);
      shake(dim, a, 28, 0.7, 0.6);
      for (let k = 0; k < 6; k++) {
        ctx.at(k * 2, () => {
          line(dim, "glow", a, b, 0.6, { color: white(c, 0.3), size: 2.2, life: 0.3 });
          line(dim, "trail", a, b, 1.2, { color: [1, 1, 1], size: 1.0, life: 0.25 });
          for (let d = 0; d < L; d += 3) {
            const q = add(a, v, d);
            P(dim, "ring", q, { color: c, size: 1.6, life: 0.25 });
          }
        });
      }
      P(dim, "flare", a, { color: white(c, 0.6), size: 4, life: 0.5 });
      P(dim, "impact", b, { color: hot, size: 4, life: 0.3 });
      kanji(dim, add(a, v, 4), 4, c, 3.0);
      for (const e of enemiesOnLine(p, a, b, 2.2)) {
        hit(p, e, 18, { color: c, kb: 1.6, up: 0.5, dir: norm({ ...v, y: 0 }), power: 2.2, crit: true, gauge: 0 });
      }
      // 光の雨: 光線に沿って羽根と星が降る
      ctx.every(6, 8, 3, () => {
        const q = add(a, v, rand(2, L));
        P(dim, "feather", { ...q, y: q.y + 3 }, { color: [1, 0.96, 0.84], count: 3, spread: 1.4 });
        P(dim, "star", { ...q, y: q.y + 1 }, { color: hot, count: 3, spread: 1.0 });
      });
    });
    ctx.at(44, () => bodyStop(p));
    return 46;
  },
});

// ===========================================================================
//  盾 — 氷の守護。構えて受け、貯めた衝撃を凍気にして返す
// ===========================================================================
register("shield", {
  /** 戦技「氷撃反射」: ガードで受けた衝撃を、前方への凍気の爆発に変えて返す。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    const stored = ctx.extra.absorbed ?? 0;
    const f = ctx.liveDir();
    body(p, "bash");
    sound(dim, "hd.ice", p.location, 0.9, 1.2);
    const dmg = Math.min(15, 4 + stored * 0.9);
    const n = 6;
    for (let k = 0; k < n; k++) {
      ctx.at(k, () => {
        const d = 1.2 + k * 0.9;
        const at = add(ctx.chest(), f, d);
        P(dim, "shard", at, { color: c, count: 6, speed: 4, spread: 0.3 + k * 0.1, grav: -10 });
        P(dim, "snow", at, { color: hot, count: 4, spread: 0.6 });
        P(dim, "hex", at, { color: c, size: 1.2 + k * 0.25, life: 0.3, rot: k * 20 });
      });
    }
    burst(dim, add(ctx.chest(), f, 1.4), c, 1.6);
    for (const e of enemiesInCone(p, ctx.chest(), f, 6.5, 50)) {
      hit(p, e, dmg, { color: c, kb: 1.3, up: 0.35, dir: f, power: 1.6, sound: "hd.ice" });
      freeze(e, 60);
    }
    return 10;
  },

  /** 突進技「氷河突撃」: 盾を前に突進し、触れた敵を弾き飛ばして凍らせる。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    const f = ctx.f;
    body(p, "lunge");
    sound(dim, "hd.dash", p.location, 0.8, 1.0);
    effect(p, "resistance", 16, 2);
    lunge(ctx, f, 1.35, 0.08);
    ctx.every(0, 9, 1, (i) => {
      const at = ctx.front(1.2, 1.0);
      P(dim, "hex", at, { color: c, size: 1.6, life: 0.15, rot: i * 15 });
      P(dim, "snow", { ...p.location, y: p.location.y + 0.3 }, { color: hot, count: 3, spread: 0.4 });
      P(dim, "trail", { ...p.location, y: p.location.y + 0.15 }, { color: c, size: 0.9, life: 0.6 });
      for (const e of enemiesNear(p, at, 2.3)) {
        if (ctx.once(e)) {
          hit(p, e, 6, { color: c, kb: 1.7, up: 0.45, dir: f, power: 1.4, sound: "hd.guard" });
          freeze(e, 40);
          P(dim, "shard", chest(e), { color: c, count: 10, speed: 6 });
        }
      }
    });
    ctx.at(10, () => burst(dim, ctx.front(1.4, 1.0), c, 1.3));
    return 14;
  },

  /** 空中技「氷槌」: 盾ごと落ちて叩きつけ、二重の輪で氷の棘を突き上げる。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    hover(ctx, 6, 0.4);
    body(p, "plunge");
    ctx.at(6, () => plunge(ctx, (l) => {
      body(p, "land");
      sound(dim, "hd.ice", l, 0.8, 1.4);
      sound(dim, "hd.hit_heavy", l, 1.0, 1.0);
      shake(dim, l, 14, 0.4, 0.35);
      P(dim, "ring_flat", { ...l, y: l.y + 0.08 }, { color: c, size: 5, life: 0.5 });
      [[2.4, 8, 0], [4.4, 12, 3]].forEach(([r, n, t]) => ctx.at(t, () => {
        for (let k = 0; k < n; k++) {
          const q = add(l, yawRotate({ x: 1, y: 0, z: 0 }, k * 360 / n), r);
          P(dim, "shard", { ...q, y: q.y + 0.2 }, { color: c, count: 4, speed: 5, grav: -8, spread: 0.2 });
          P(dim, "pillar", { ...q, y: q.y + 0.8 }, { color: hot, size: 0.35, height: 1.6, life: 0.6 });
        }
      }));
      for (const e of enemiesNear(p, l, 5)) {
        hit(p, e, 8, { color: c, up: 0.55, kb: 0.4, power: 1.5 });
        freeze(e, 70);
      }
    }));
    return 28;
  },

  /** 必殺「絶対氷壁・アブソリュート・イージス」: 氷の結界で身を守り、内の敵を凍らせて砕く。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 80, 0);
    body(p, "cast");
    const centre = { ...p.location };
    effect(p, "regeneration", 100, 2);
    effect(p, "absorption", 400, 2);
    // 半球の結界（六角の粒を半球面に並べる）
    ctx.every(4, 7, 9, (i) => {
      for (let lat = 0; lat < 4; lat++) {
        const el = lat * 22 + 6;
        const n = Math.max(4, Math.round(16 * Math.cos(el * Math.PI / 180)));
        for (let k = 0; k < n; k++) {
          const az = (k / n) * Math.PI * 2 + i * 0.2;
          const r = 5.2;
          P(dim, "hex", {
            x: centre.x + Math.cos(az) * Math.cos(el * Math.PI / 180) * r,
            y: centre.y + Math.sin(el * Math.PI / 180) * r,
            z: centre.z + Math.sin(az) * Math.cos(el * Math.PI / 180) * r,
          }, { color: c, size: 1.6, life: 0.55, rot: k * 10 });
        }
      }
    });
    ctx.at(10, () => {
      sound(dim, "hd.ice", centre, 0.7, 1.6);
      for (const e of enemiesNear(p, centre, 5.5)) {
        hit(p, e, 6, { color: c, kb: 2.0, up: 0.4, dir: dirTo(centre, e.location), power: 1.5, gauge: 0 });
        freeze(e, 60, true);
      }
    });
    for (let k = 0; k < 5; k++) {
      ctx.at(18 + k * 9, () => {
        for (const e of enemiesNear(p, centre, 10).slice(0, 6)) {
          const q = e.location;
          P(dim, "pillar", { ...q, y: q.y + 1.4 }, { color: c, size: 0.8, height: 3, life: 0.5 });
          P(dim, "shard", { ...q, y: q.y + 0.2 }, { color: hot, count: 10, speed: 6, grav: -10 });
          hit(p, e, 3, { color: c, up: 0.3, power: 1.0, gauge: 0 });
          freeze(e, 30, true);
        }
        sound(dim, "hd.ice", centre, 1.0 + k * 0.08, 0.9);
      });
    }
    ctx.at(66, () => {
      P(dim, "ring_flat", { ...centre, y: centre.y + 0.1 }, { color: c, size: 9, life: 0.6 });
      P(dim, "shard", { ...centre, y: centre.y + 2.5 }, { color: c, count: 40, speed: 10, spread: 3, grav: -14, size: 1.6 });
      kanji(dim, { ...centre, y: centre.y + 4 }, 4, c, 3.4);
      flash(dim, centre, 26, [0.85, 1, 1], 0.08, 0.45);
      sound(dim, "hd.boom", centre, 1.4, 1.2);
      sound(dim, "hd.ice", centre, 0.6, 1.8);
      shake(dim, centre, 20, 0.6, 0.5);
      for (const e of enemiesNear(p, centre, 8.5)) {
        hit(p, e, 7, { color: c, kb: 1.2, up: 0.6, power: 2.0, crit: true, gauge: 0 });
      }
      bodyStop(p);
    });
    return 70;
  },
});

// ===========================================================================
//  鞭 — 薔薇の茨。長い間合い・引き寄せ・吸血
// ===========================================================================
function lash(ctx, from, dir, length, amp, phase) {
  // 波打つ鞭の軌跡（正弦で左右にしならせる）
  const { dim, c } = ctx;
  const side = norm({ x: -dir.z, y: 0, z: dir.x });
  const pts = [];
  const n = Math.ceil(length / 0.4);
  for (let i = 0; i <= n; i++) {
    const d = (i / n) * length;
    const w = Math.sin(i / n * Math.PI * 2 + phase) * amp * (i / n);
    pts.push({ x: from.x + dir.x * d + side.x * w, y: from.y + dir.y * d, z: from.z + dir.z * d + side.z * w });
  }
  pts.forEach((q, i) => P(dim, "trail", q, { color: i === n ? white(c, 0.6) : c, size: i === n ? 1.0 : 0.45, life: 0.25 }));
  return pts[pts.length - 1];
}

register("whip", {
  /** 戦技「茨の鞭」: 9m 先まで届く二連の鞭打ち。茨で出血させる。 */
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "crack");
    [[4, 9.0, 7, 0.9], [10, 7.0, 3.5, -0.7]].forEach(([t, L, dmg, amp]) => ctx.at(t, () => {
      const v = viewDir(p);
      const from = add(eye(p), v, 0.6);
      const tip = lash(ctx, from, v, L, amp, rand(0, 3));
      sound(dim, "hd.crack", tip, rand(0.95, 1.1), 1.0);
      P(dim, "petal", tip, { color: c, count: 8, spread: 0.6, speed: 2 });
      P(dim, "impact", tip, { color: hot, size: 0.8 });
      ctx.struck.clear();
      for (const e of enemiesOnLine(p, from, tip, 1.2)) {
        hit(p, e, dmg, { color: c, power: 1.0, kb: 0.3 });
        effect(e, "poison", 50, 0);
      }
    }));
    return 16;
  },

  /** 突進技「薔薇の鎖」: 敵に絡めて引き寄せる。敵がいなければ壁や地面へ飛び移る。 */
  dash(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, "crack");
    const from = eye(p);
    const v = viewDir(p);
    let tgt;
    try {
      const hits = p.getEntitiesFromViewDirection?.({ maxDistance: 15 }) ?? [];
      tgt = hits.map((h) => h.entity).find((e) => isTarget(p, e));
    } catch (_) { }
    if (!tgt) tgt = nearestEnemy(p, p.location, 14, v, 18);
    sound(dim, "hd.crack", from, 0.9, 1.0);
    if (tgt) {
      const to = chest(tgt);
      line(dim, "trail", from, to, 0.35, { color: c, size: 0.4, life: 0.5 });
      P(dim, "petal", to, { color: c, count: 10, spread: 0.6 });
      const d = dirTo(to, p.location);
      const k = Math.min(1.8, dist(to, from) * 0.13 + 0.3);
      knock(tgt, d.x, d.z, k, 0.35);
      hit(p, tgt, 5.5, { color: c, power: 1.2 });
      bind(tgt, 30);
      ctx.at(6, () => {
        if (!valid(tgt)) return;
        P(dim, "cross", chest(tgt), { color: hot, size: 1.0 });
      });
    } else {
      let anchor;
      try {
        const b = p.getBlockFromViewDirection?.({ maxDistance: 18 })?.block;
        if (b) anchor = { x: b.location.x + 0.5, y: b.location.y + 0.5, z: b.location.z + 0.5 };
      } catch (_) { }
      if (anchor) {
        line(dim, "trail", from, anchor, 0.4, { color: c, size: 0.4, life: 0.6 });
        P(dim, "petal", anchor, { color: c, count: 8, spread: 0.5 });
        const to = sub(anchor, p.location);
        const h = Math.hypot(to.x, to.z) || 1;
        knock(p, to.x / h, to.z / h, Math.min(1.9, h * 0.16 + 0.35), Math.max(0.45, Math.min(1.2, to.y * 0.12 + 0.55)));
        markAirborne(p);
        body(p, "dash", "hd.move");
        sound(dim, "hd.dash", p.location, 1.3, 0.8);
      } else {
        lash(ctx, from, v, 10, 1.0, 0);
      }
    }
    return 12;
  },

  /** 空中技「薔薇旋風」: 宙で鞭を振り回し、周り 5m を薔薇の渦で切り刻む。 */
  air(ctx) {
    const { p, dim, c, hot } = ctx;
    hover(ctx, 30, 0.3);
    body(p, "spinarm");
    sound(dim, "hd.wind", p.location, 1.2, 1.0);
    ctx.every(0, 7, 4, (i) => {
      const l = ctx.chest();
      for (let k = 0; k < 10; k++) {
        const a = (k / 10) * Math.PI * 2 + i * 0.7;
        const r = 2.0 + (k % 3) * 1.2;
        P(dim, "trail", { x: l.x + Math.cos(a) * r, y: l.y - 0.3 + (k % 2) * 0.4, z: l.z + Math.sin(a) * r },
          { color: k % 2 ? c : hot, size: 0.6, life: 0.3 });
      }
      P(dim, "petal", l, { color: c, count: 6, spread: 3, speed: 3 });
      sound(dim, "hd.crack", l, 1.1 + i * 0.05, 0.6);
      if (i % 2 === 0) {
        for (const e of enemiesNear(p, l, 5.2)) {
          if (ctx.once(e, 4)) {
            hit(p, e, 2.4, { color: c, power: 0.9, kb: 0.0, up: 0.1 });
            const d = dirTo(e.location, p.location);
            knock(e, d.x, d.z, 0.25, 0.1);
          }
        }
      }
    });
    ctx.at(30, () => bodyStop(p));
    return 30;
  },

  /** 必殺「千薔薇葬送・ブラッディ・ローズ」: 薔薇の陣に入った敵を茨で縛り、命を吸う。 */
  ult(ctx) {
    const { p, dim, c, hot } = ctx;
    ultOpen(ctx, 84, 10);
    body(p, "cast");
    const centre = { ...p.location };
    P(dim, "circle2", { ...centre, y: centre.y + 0.07 }, { color: c, size: 9, life: 3.8, spin: 25 });
    P(dim, "vortex", centre, { color: c, size: 3.5, height: 6, life: 3.4, rate: 90 });
    const heal = (v) => {
      const h = health(p);
      try { if (h) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + v)); } catch (_) { }
      P(dim, "petal", ctx.chest(), { color: [1, 0.3, 0.5], count: 4, spread: 0.6 });
    };
    for (let k = 0; k < 6; k++) {
      ctx.at(10 + k * 8, () => {
        P(dim, "petal", { ...centre, y: centre.y + 2 }, { color: c, count: 16, spread: 6, speed: 3 });
        for (const e of enemiesNear(p, centre, 10).slice(0, 6)) {
          const q = e.location;
          P(dim, "pillar", { ...q, y: q.y + 1.2 }, { color: c, size: 0.5, height: 2.6, life: 0.5 });
          P(dim, "shard", { ...q, y: q.y + 0.3 }, { color: [0.3, 0.6, 0.25], count: 6, speed: 5, grav: -10 });
          hit(p, e, 2.6, { color: c, power: 1.0, gauge: 0 });
          bind(e, 20);
          heal(1.2);
        }
        sound(dim, "hd.crack", centre, 0.9 + k * 0.06, 0.9);
      });
    }
    ctx.at(62, () => {
      P(dim, "flare", { ...centre, y: centre.y + 1.5 }, { color: white(c, 0.5), size: 6 });
      P(dim, "ring_flat", { ...centre, y: centre.y + 0.1 }, { color: c, size: 10, life: 0.6 });
      P(dim, "petal", { ...centre, y: centre.y + 2 }, { color: c, count: 40, spread: 5, speed: 6, life: 2.4 });
      kanji(dim, { ...centre, y: centre.y + 4 }, 3, c, 3.4);
      flash(dim, centre, 26, [1, 0.4, 0.6], 0.06, 0.45);
      sound(dim, "hd.boom", centre, 1.2, 1.4);
      shake(dim, centre, 20, 0.6, 0.5);
      for (const e of enemiesNear(p, centre, 10)) {
        hit(p, e, 8, { color: c, kb: 1.0, up: 0.7, power: 2.0, crit: true, gauge: 0 });
      }
      heal(4);
      bodyStop(p);
    });
    return 68;
  },
});

