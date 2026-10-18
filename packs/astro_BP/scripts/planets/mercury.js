// ===========================================================================
//  水星 クイックシルバー（QUICKSILVER）— 最速の形態
//
//  鏡面の銀の流線形。液体金属のナノマシン。右半身は昼側の灼熱（橙）、左半身は夜側の極寒（シアン）。
//  色: 発光 = 夜側のシアン（ctx.c / NIGHT）/ 昼側の灼熱（DAY = ctx.accent）/ 液体金属の銀（SILVER / LIQUID）
//
//   惑星技  水銀閃            抜刀の構え → 前方 7m を一瞬で駆け抜けて通り道を斬る → 残った水銀が遅れて弾ける
//   機動技  ヘルメスの翼       近くの敵の周りを三度跳び回り（瞬間移動）、そのたびに斬りつける。最後に翼の斬撃
//   空中技  マーキュリー・レイン 宙で止まり、背に液体金属の針を並べ、前下方の円へ三斉射の針の雨。最後に針が溶けて弾ける
//   必殺    近日点突破 ペリヘリオン・ドライブ
//                             時を止め、敵の群れを囲む軌道を八度（八芒星の弦）斬り抜ける。止まった時の中に
//                             斬撃の線が残り、刃を振り下ろした瞬間、昼側の灼熱と夜側の極寒が同時に炸裂する
//   三段目  水銀の飛沫          液体金属の刃が伸び、前方 4m を薙ぐ（飛沫が弧に沿って飛ぶ）
//   変身の締め 液体金属の飛沫が全身を流れ落ちて固まり、残像が八方へ走る
//   パッシブ afterimage        疾走中は液体金属の残像が残り、残像に触れた敵（敵対的な相手だけ）を斬る。
//                             被弾すると身体が液体のように揺らいで残像を置き去りにし、一瞬加速する
//
//  全身モーション（planets/mercury/body.py）: combo1〜3 / flash_slash / hermes_wings / needle_rain /
//  peri_draw / peri_finish / flourish
// ===========================================================================
import {
  register, hover, warp, safeAhead, standable, ultOpen, projectile, dirTo,
} from "../engine.js";
import {
  P, line, ring, arc, shock, emblem, flash, shake, sound, body, white, afterimage, fxScale,
} from "../fx.js";
import {
  hit, enemiesNear, enemiesOnLine, nearestHostile, hostilesNear, freeze,
} from "../combat.js";
import {
  add, sub, up, norm, lerp3, yawRotate, yawDeg, rightOf, chest, hdist, dist, onGround, effect,
  valid, now, finite, clamp, rand,
} from "../util.js";

const KEY = "mercury";
const SILVER = [0.86, 0.9, 0.96];
const LIQUID = [0.72, 0.78, 0.88];
const DAY = [1.0, 0.59, 0.24];          // 昼側の灼熱（= PLANETS.mercury.accent）
const DAY_HOT = [1.0, 0.86, 0.62];
const NIGHT = [0.47, 0.94, 1.0];        // 夜側の極寒（= 発光色）
const NIGHT_ICE = [0.78, 0.98, 1.0];
const EAST = { x: 1, y: 0, z: 0 };
const UP = { x: 0, y: 1, z: 0 };

// ---------------------------------------------------------------------------
//  小さな道具
// ---------------------------------------------------------------------------
/** e の位置（消えていれば null）。 */
function posOf(e) {
  try { return valid(e) ? { ...e.location } : null; } catch (_) { return null; }
}

/** 液体金属の残像: 銀の人型 + 昼/夜の縁の色 + 足元に滴る滴。 */
function quickImage(dim, feet, k = 0, life = 0.45) {
  afterimage(dim, feet, SILVER, life);
  afterimage(dim, feet, k % 2 ? NIGHT : DAY, life * 0.7);
  P(dim, "droplet", up(feet, 1.0), { color: LIQUID, count: 4, spread: 0.35, speed: 1.2, size: 0.9 });
}

/** a → b の液体金属の軌跡（芯の白 + 銀 + 色の縁 + 飛び散る滴）。 */
function quickTrail(dim, a, b, col, life = 0.3) {
  line(dim, "trail", a, b, 0.3, { color: white(col, 0.55), size: 0.9, life });
  line(dim, "glow", a, b, 0.5, { color: col, size: 0.55, life: life * 1.4, spread: 0.12 });
  const d = norm(sub(b, a));
  P(dim, "speedline", lerp3(a, b, 0.5), { color: SILVER, count: 6, dir: d, speed: 18, spread: 0.6 });
}

/** 滴の飛沫（当たり・水銀の溜まりが弾ける時）。 */
function splashAt(dim, q, power = 1) {
  P(dim, "droplet", q, { color: LIQUID, count: Math.round(8 * power), speed: 3 + 2 * power, spread: 0.3, size: 1.1 });
  P(dim, "splash", { ...q, y: q.y - 0.5 }, { color: SILVER, count: 1, spread: 0.3 * power, size: 0.8 * power });
}

/** 被弾時の液体化（onHurt）の再使用（playerId → tick）。 */
const hurtCd = new Map();

/** 水平な前方 f に対する「右」（プレイヤーから見て右 = 昼側）。 */
function daySide(f) { return rightOf(f); }

register(KEY, {
  // =========================================================================
  //  惑星技「水銀閃」
  //  0〜5: 抜刀の構え（刃に銀が集まり、通り道に点線の予兆）/ 6: 前方 7m を瞬時に駆け抜ける
  //  （通り道の敵を斬る・四つの残像・液体金属の軌跡）/ 8〜18: 通り道に水銀の溜まりが光る /
  //  20: 残った水銀が遅れて弾ける（溜まりと斬った敵の位置で破裂）
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "mercury.flash_slash");
    sound(dim, "astro.liquid", p.location, 1.4, 0.7);
    sound(dim, "astro.beam_charge", p.location, 1.9, 0.45);
    ctx.every(0, 3, 2, (i) => {
      const f = ctx.liveDir();
      const blade = ctx.local(-0.3, 0.6, 0.7);
      P(dim, "converge", blade, { color: SILVER, count: 8, spread: 1.4, life: 0.25, size: 0.7 });
      P(dim, "glow", blade, { color: white(NIGHT, 0.4), size: 0.6 + i * 0.25, life: 0.15 });
      if (i === 1) {
        const from = up(ctx.loc(), 0.1);
        line(dim, "dot", from, add(from, f, 7), 0.4, { color: white(NIGHT, 0.3), size: 0.6, life: 0.3 });
        P(dim, "ring_flat", up(ctx.loc(), 0.08), { color: SILVER, size: 0.9, life: 0.3 });
      }
    });
    const pools = [];
    const cut = [];
    ctx.at(6, () => {
      const f = ctx.liveDir();
      const from = ctx.loc();
      const dest = safeAhead(dim, from, f, 7);
      const a = up(from, 1.0);
      const b = up(dest, 1.0);
      // 当たり（瞬間移動の前に、通り道の線で判定する）
      for (const e of enemiesOnLine(ctx, a, b, 1.5)) {
        if (!ctx.once(e, 1, "pass")) continue;
        const q = posOf(e);
        if (q && cut.length < 4) cut.push(q);
        hit(ctx, e, 8, { color: SILVER, kb: 0.25, up: 0.25, dir: f, power: 1.4, sound: "astro.hit_metal" });
        P(dim, "cross", chest(e), { color: white(NIGHT, 0.3), size: 1.1, rot: yawDeg(f) + 45, life: 0.25 });
      }
      warp(ctx, dest, add(dest, f, 6));
      // 駆け抜けた跡: 残像 4 つ・液体金属の軌跡・横一文字の閃光
      const L = Math.max(0.5, hdist(from, dest));
      for (let k = 0; k < 4; k++) quickImage(dim, lerp3(from, dest, k / 4), k, 0.5 + k * 0.08);
      quickTrail(dim, a, b, NIGHT, 0.35);
      line(dim, "trail", up(a, 0.25), up(b, 0.25), 0.4, { color: DAY_HOT, size: 0.5, life: 0.3 });
      P(dim, "slash_flat", lerp3(a, b, 0.5), { color: white(SILVER, 0.2), size: Math.max(1, L / 3.2), rot: yawDeg(f) + 90, life: 0.3 });
      P(dim, "thrust", a, { color: white(NIGHT, 0.5), dir: f, len: L + 1, size: 1.4, life: 0.22 });
      P(dim, "flare", b, { color: white(SILVER, 0.5), size: 1.4, rot: yawDeg(f), life: 0.2 });
      sound(dim, "astro.swing_heavy", dest, 1.35, 1.0);
      sound(dim, "astro.boost", from, 1.5, 0.8);
      sound(dim, "astro.gust", dest, 1.2, 0.7);
      shake(dim, dest, 8, 0.25, 0.2);
      // 水銀の溜まり（通り道に 4 つ）
      for (let k = 1; k <= 4; k++) pools.push(onGround(dim, lerp3(from, dest, k / 4.5), 4));
    });
    // 溜まりが光って震える（遅れて弾ける予兆）
    ctx.every(8, 6, 2, (i) => {
      for (const q of pools) {
        P(dim, "ring_flat", up(q, 0.06), { color: i % 2 ? NIGHT : SILVER, size: 0.35 + i * 0.05, life: 0.2 });
        if (i % 2 === 0) P(dim, "droplet", up(q, 0.2), { color: LIQUID, count: 2, speed: 1.6, spread: 0.2 });
      }
      if (i === 2) sound(dim, "astro.liquid", pools[1] ?? ctx.loc(), 1.8, 0.5);
    });
    // 20: 残った水銀が弾ける
    ctx.at(20, () => {
      const spots = pools.concat(cut.map((q) => ({ ...q })));
      spots.forEach((q, k) => {
        const c = up(q, 0.7);
        splashAt(dim, c, 1.3);
        P(dim, "impact", c, { color: k % 2 ? NIGHT : DAY, size: 1.1, life: 0.18 });
        P(dim, "ring", c, { color: white(SILVER, 0.3), size: 1.2, life: 0.25 });
        if (k % 2 === 0) P(dim, "spark", c, { color: k % 4 ? NIGHT : DAY, count: 6, speed: 6 });
      });
      for (const q of spots.slice(0, 6)) {
        for (const e of ctx.foes(2.0, up(q, 0.8))) {
          if (ctx.once(e, 1, "pop")) hit(ctx, e, 5, { color: NIGHT, kb: 0.4, up: 0.45, dir: dirTo(q, posOf(e) ?? q), power: 1.2, sound: "astro.splash" });
        }
      }
      const mid = pools[1] ?? ctx.loc();
      sound(dim, "astro.splash", mid, 1.3, 1.0);
      sound(dim, "astro.explosion", mid, 1.7, 0.6);
      sound(dim, "astro.liquid", mid, 0.9, 0.8);
      shake(dim, mid, 10, 0.25, 0.25);
    });
    return 14;
  },

  // =========================================================================
  //  機動技「ヘルメスの翼」
  //  近くの敵（視線の先 12m → 周り 8m）の周りを三度跳び回る（2 / 10 / 18 tick）。跳ぶたびに残像と羽の風切り、
  //  背後から斬りつけ、最後の一撃で打ち上げて翼の形の斬撃（20）。敵がいなければ前へ三度跳んで斬る。
  //  跳んでいる間は被ダメージが減る。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    body(p, "mercury.hermes_wings");
    effect(p, "resistance", 24, 2);
    sound(dim, "astro.boost", p.location, 1.4, 0.9);
    sound(dim, "astro.wind", p.location, 1.6, 0.6);
    // 見ている相手（意図して狙った）→ 無ければ周りの敵対的な相手だけ（村人や動物を勝手に狙わない）
    let target = ctx.nearest(12, 70) ?? nearestHostile(ctx, ctx.chest(), 8);
    let last = posOf(target);
    const ANG = [130, -110, 10];
    P(dim, "wind", ctx.chest(), { color: SILVER, count: 4, spread: 0.8, speed: 8, dir: UP });
    for (let i = 0; i < 3; i++) {
      ctx.at(2 + i * 8, () => {
        // 標的が倒れていたら、最後の位置の近くの次の相手へ
        if (!posOf(target) && last) target = nearestHostile(ctx, up(last, 1), 6);
        const T = posOf(target);
        const from = ctx.loc();
        const col = i % 2 ? NIGHT : DAY;
        quickImage(dim, from, i, 0.55);
        P(dim, "wind", up(from, 1.2), { color: white(col, 0.3), count: 3, spread: 0.6, speed: 10, dir: UP });
        sound(dim, "astro.just_dodge", from, 1.3 + i * 0.12, 0.7);
        sound(dim, "astro.gust", from, 1.5, 0.5);
        if (T) {
          last = T;
          const d0 = dirTo(T, from);
          const dest = add(T, yawRotate(d0, ANG[i]), 2.1);
          const ok = standable(dim, dest) && warp(ctx, dest, up(T, 1.0));
          if (!ok) warp(ctx, add(T, d0, 1.8), up(T, 1.0));
          const at = ctx.loc();
          quickTrail(dim, up(from, 1.0), up(at, 1.0), col, 0.3);
          const f = dirTo(at, T);
          const tc = up(T, 1.0);
          P(dim, i === 2 ? "slash_big" : "slash", tc, { color: white(col, 0.25), size: i === 2 ? 0.9 : 1.2, rot: i * 70 - 40, var: i % 2, life: 0.25 });
          P(dim, "flare", tc, { color: white(col, 0.5), size: 1.0, rot: yawDeg(f), life: 0.15 });
          splashAt(dim, tc, 0.8);
          sound(dim, "astro.swing", at, 1.2 + i * 0.1, 1.0);
          // 跳べずに離れたままなら斬らない（遠くからの当たりにしない）
          if (valid(target) && hdist(at, T) < 4.5) {
            hit(ctx, target, i === 2 ? 7 : 5, { color: col, kb: i === 2 ? 0.4 : 0.1, up: i === 2 ? 0.65 : 0.15, dir: f, power: i === 2 ? 1.6 : 1.2, sound: "astro.hit_metal" });
          }
          for (const e of ctx.foes(2.4, tc)) {
            if (e.id === target?.id || !ctx.once(e, 1, `w${i}`)) continue;
            hit(ctx, e, 3, { color: col, kb: 0.3, up: 0.2, dir: dirTo(T, posOf(e) ?? T) });
          }
        } else {
          // 敵がいない: 前へ短く跳んで斬る
          const f = ctx.liveDir();
          const dest = safeAhead(dim, from, f, 3.2);
          warp(ctx, dest, add(dest, f, 4));
          quickTrail(dim, up(from, 1.0), up(dest, 1.0), col, 0.3);
          arc(dim, ctx.chest(), f, 1.9, -60, 60, i * 30 - 30, col, { size: 0.8, steps: 9 });
          sound(dim, "astro.swing", dest, 1.3, 0.9);
          for (const e of ctx.cone(3.2, 60, ctx.chest(), f)) {
            if (ctx.once(e, 1, `w${i}`)) hit(ctx, e, 5, { color: col, kb: 0.4, up: 0.2, dir: f });
          }
        }
      });
    }
    // 20: 翼の斬撃（左右に開く二枚の大きな弧）と羽の舞い
    ctx.at(20, () => {
      const c = posOf(target) ? up(posOf(target), 1.0) : ctx.front(1.6, 1.0);
      const f = dirTo(ctx.loc(), c);
      P(dim, "slash_big", c, { color: DAY, size: 1.1, rot: yawDeg(f) - 20, var: 0, life: 0.35 });
      P(dim, "slash_big", c, { color: NIGHT, size: 1.1, rot: yawDeg(f) + 20, var: 1, life: 0.35 });
      P(dim, "star", c, { color: SILVER, count: 10, spread: 1.4, speed: 2, life: 0.6 });
      P(dim, "ring", c, { color: white(SILVER, 0.3), size: 1.8, life: 0.3 });
      sound(dim, "astro.swing_heavy", c, 1.4, 0.9);
      sound(dim, "astro.wind", c, 1.2, 0.7);
      shake(dim, c, 8, 0.3, 0.25);
    });
    return 24;
  },

  // =========================================================================
  //  空中技「マーキュリー・レイン」
  //  0: 宙で止まり、前下方の狙った地点に陣（半径 3.2m）/ 0〜5: 背中に液体金属の針が並ぶ /
  //  6・12・18: 三斉射（各 7 本。陣の中の敵を優先して狙う）/ 22: 刺さった針が溶けて弾け、敵の足を鈍らせる
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 30, 0.25);
    body(p, "mercury.needle_rain");
    const raw = ctx.aim(18);
    const g = finite(raw) ? raw : ctx.ground(ctx.local(6, 0, 0));
    const R = 3.2;
    sound(dim, "astro.liquid", p.location, 1.6, 0.8);
    sound(dim, "astro.beam_charge", p.location, 1.5, 0.5);
    P(dim, "circle", up(g, 0.06), { color: NIGHT, size: R / 1.2, life: 1.5, spin: 80 });
    P(dim, "ring_flat", up(g, 0.08), { color: DAY, size: R / 1.1, life: 0.6 });
    ring(dim, "dot", g, R, 24, { color: SILVER, size: 0.6, life: 1.2 }, 0.15);
    // 背に並ぶ針（昼と夜の二列の光）
    ctx.every(0, 4, 2, (i) => {
      const c = up(ctx.loc(), 2.4);
      const r = rightOf(ctx.liveDir());
      for (const s of [-1, 1]) {
        P(dim, "glow", add(add(c, r, s * (0.6 + i * 0.25)), ctx.liveDir(), -0.4), { color: s < 0 ? NIGHT : DAY, size: 0.45, life: 0.3 });
      }
      P(dim, "converge", c, { color: SILVER, count: 6, spread: 1.2, life: 0.25, size: 0.6 });
    });
    const NEEDLES = 7;
    for (let v = 0; v < 3; v++) {
      ctx.at(6 + v * 6, () => {
        const foes = enemiesNear(ctx, up(g, 0.8), R + 1.2);
        const base = up(ctx.loc(), 2.3);
        const f = ctx.liveDir();
        const r = rightOf(f);
        sound(dim, "astro.laser", base, 1.9 + v * 0.1, 0.6);
        sound(dim, "astro.swing", base, 1.7, 0.6);
        P(dim, "flare", base, { color: white(SILVER, 0.5), size: 0.9, life: 0.12 });
        for (let k = 0; k < NEEDLES; k++) {
          const side = (k / (NEEDLES - 1)) * 2 - 1;
          const from = add(base, r, side * 1.4);
          let to;
          const foe = foes.length ? foes[(k + v) % foes.length] : null;
          const fp = posOf(foe);
          if (fp && k % 2 === 0) to = { x: fp.x + rand(-0.3, 0.3), y: fp.y + 1.0, z: fp.z + rand(-0.3, 0.3) };
          else {
            const a = rand(0, Math.PI * 2), rr = Math.sqrt(Math.random()) * R;
            to = { x: g.x + Math.cos(a) * rr, y: g.y + 0.1, z: g.z + Math.sin(a) * rr };
          }
          const dir = norm(sub(to, from));
          const col = side < 0 ? NIGHT : DAY;
          projectile(ctx, from, dir, {
            speed: 1.7, range: dist(from, to) + 3, radius: 0.55, pierce: 0, life: 24,
            onHit(e) {
              if (ctx.once(e, 6, "needle")) hit(ctx, e, 2.6, { color: col, kb: 0.05, up: 0.05, dir, power: 0.8, sound: "astro.hit_metal" });
            },
            trail(d, pos, prev, age) {
              P(d, "thrust", prev, { color: white(col, 0.35), dir, len: 1.3, size: 0.32, life: 0.08 });
              if (age === 1) P(d, "trail", pos, { color: SILVER, size: 0.5, life: 0.2 });
            },
            onEnd(pos, reason) {
              if (reason === "owner" || reason === "stopped") return;
              P(dim, "droplet", pos, { color: LIQUID, count: 3, speed: 2.5, spread: 0.1, size: 0.8 });
              if (k % 2 === 0) P(dim, "spark", pos, { color: col, count: 3, speed: 4 });
              if (k === 3) sound(dim, "astro.splash", pos, 1.8, 0.4);
            },
          });
        }
      });
    }
    // 22: 刺さった針が溶けて弾ける（陣の中の敵を鈍らせる）
    ctx.at(24, () => {
      P(dim, "shock_flat", up(g, 0.08), { color: SILVER, size: R / 1.5, life: 0.45 });
      P(dim, "splash", up(g, 0.1), { color: SILVER, count: 3, spread: R * 0.5, size: 1.2 });
      ring(dim, "glow", g, R * 0.8, 20, { color: NIGHT, size: 0.5, life: 0.4, speed: 2 }, 0.2);
      P(dim, "droplet", up(g, 0.4), { color: LIQUID, count: 16, speed: 5, spread: R * 0.4 });
      sound(dim, "astro.splash", g, 1.1, 0.9);
      sound(dim, "astro.liquid", g, 0.8, 0.8);
      for (const e of ctx.foes(R + 0.5, up(g, 0.8))) {
        if (!ctx.once(e, 1, "melt")) continue;
        hit(ctx, e, 4, { color: NIGHT, up: 0.2, power: 1.0, sound: "astro.splash" });
        freeze(e, 50);
      }
    });
    return 26;
  },

  // =========================================================================
  //  必殺「近日点突破 ペリヘリオン・ドライブ」
  //  0: ultOpen（時を止める）/ 2〜8: 低い抜刀の構え。右に太陽（昼）、左に冷光（夜）、敵の群れを囲む軌道 /
  //  10〜38: 4 tick ごとに八度、八芒星の弦を斬り抜ける（瞬間移動・残像・弦の光は止まった時の中に残る）/
  //  40: 刃を天へ（peri_finish）/ 44: 光が中心へ集まる / 50: 振り下ろした瞬間、昼側の灼熱と夜側の極寒が
  //  同時に炸裂（右半分は紅炎、左半分は氷晶、中央は白い閃光）/ 52〜64: 余韻（火の粉と氷の欠片が舞う）
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 72, 14);
    const f0 = ctx.f;
    const rgt = daySide(f0);
    const foes0 = enemiesNear(ctx, ctx.chest(), 14);
    let C;
    if (foes0.length) {
      let sx = 0, sy = 0, sz = 0, n = 0;
      for (const e of foes0) {
        const q = posOf(e);
        if (!q) continue;
        sx += q.x; sy += q.y; sz += q.z; n++;
      }
      C = n ? { x: sx / n, y: sy / n, z: sz / n } : ctx.local(4, 0, 0);
    } else {
      C = ctx.local(4, 0, 0);
    }
    C = onGround(dim, C, 6);
    let spread = 0;
    for (const e of foes0) { const q = posOf(e); if (q) spread = Math.max(spread, hdist(q, C)); }
    const R = clamp(spread + 2.2, 3.6, 6.5);
    const startAng = Math.atan2(ctx.loc().z - C.z, ctx.loc().x - C.x);
    const pt = (k) => {
      const a = startAng + k * (Math.PI * 3 / 4);
      return onGround(dim, { x: C.x + Math.cos(a) * R, y: C.y + 0.5, z: C.z + Math.sin(a) * R }, 4);
    };
    ctx.at(2, () => body(p, "mercury.peri_draw"));
    // 構え: 太陽と冷光、軌道の予兆
    ctx.every(2, 4, 2, (i) => {
      const sun = add(up(ctx.loc(), 3.2), rgt, 2.2);
      const moon = add(up(ctx.loc(), 2.6), rgt, -2.2);
      P(dim, "glow", sun, { color: DAY_HOT, size: 2.0 + i * 0.4, life: 0.25 });
      P(dim, "flame", sun, { color: DAY, count: 3, spread: 0.4, speed: 1 });
      P(dim, "glow", moon, { color: NIGHT_ICE, size: 1.4 + i * 0.3, life: 0.25 });
      P(dim, "ice", moon, { color: NIGHT, count: 2, spread: 0.4, speed: 0.6 });
      if (i === 0) {
        P(dim, "circle", up(C, 0.06), { color: NIGHT, size: R / 1.2, life: 3.0, spin: 40 });
        P(dim, "hex_circle", up(C, 0.07), { color: DAY, size: R / 1.8, life: 3.0, spin: -60 });
        emblem(dim, up(C, 0.08), KEY, { size: R / 3.2, life: 3.0, spin: 25, color: SILVER });
        sound(dim, "astro.clock_tick", C, 0.8, 1.0);
      }
      ring(dim, "dot", C, R, 32, { color: i % 2 ? NIGHT : DAY, size: 0.55, life: 0.5 }, 0.25 + i * 0.25);
    });
    // 8: 軌道へ跳ぶ（いちばん近い軌道の点）
    ctx.at(8, () => {
      quickImage(dim, ctx.loc(), 0, 0.9);
      quickTrail(dim, ctx.chest(), up(pt(0), 1.0), SILVER, 0.3);
      warp(ctx, pt(0), up(C, 1.0));
      sound(dim, "astro.just_dodge", C, 1.2, 0.8);
    });
    // 10〜38: 八度の弦（八芒星 {8/3}: 135° ずつ進むと 8 回で元の点へ戻る）を斬り抜ける
    for (let i = 0; i < 8; i++) {
      ctx.at(10 + i * 4, () => {
        const a = pt(i);
        const b = pt(i + 1);
        const col = i % 2 ? NIGHT : DAY;
        const A = up(a, 1.0), B = up(b, 1.0);
        quickImage(dim, ctx.loc(), i, 0.9);
        warp(ctx, b, up(C, 1.0));
        // 止まった時の中に残る弦の光
        line(dim, "trail", A, B, 0.35, { color: white(col, 0.4), size: 0.75, life: 2.2 });
        line(dim, "glow", up(A, -0.6), up(B, -0.6), 0.5, { color: col, size: 0.45, life: 2.0 });
        P(dim, "slash_flat", lerp3(A, B, 0.5), { color: white(col, 0.2), size: R / 2.6, rot: yawDeg(norm(sub(B, A))) + 90, life: 0.35 });
        P(dim, "speedline", lerp3(A, B, 0.5), { color: SILVER, count: 6, dir: norm(sub(B, A)), speed: 24, spread: 0.5 });
        sound(dim, "astro.swing", B, 1.45 + i * 0.05, 0.9);
        if (i % 2 === 0) sound(dim, "astro.clock_tick", C, 1.0 + i * 0.05, 0.7);
        for (const e of enemiesOnLine(ctx, A, B, 1.7)) {
          if (!ctx.once(e, 1, `chord${i}`)) continue;
          hit(ctx, e, 4.5, { color: col, power: 1.1, sound: "astro.hit_metal", nova: 0 });
          freeze(e, 30, true);
          P(dim, "cross", chest(e), { color: white(col, 0.3), size: 0.9, rot: i * 45, life: 0.3 });
        }
      });
    }
    // 40: 構え直して刃を天へ
    ctx.at(40, () => {
      body(p, "mercury.peri_finish");
      sound(dim, "astro.beam_charge", C, 0.8, 1.0);
      sound(dim, "astro.time_stop", C, 1.3, 0.6);
    });
    ctx.every(42, 4, 2, (i) => {
      P(dim, "converge", up(C, 1.2), { color: i % 2 ? NIGHT : DAY, count: 14, spread: R, life: 0.35, size: 1.0 });
      P(dim, "glow", up(C, 1.2), { color: white(SILVER, 0.5), size: 1.0 + i * 0.5, life: 0.2 });
      P(dim, "orbit", up(C, 1.2), { color: i % 2 ? DAY : NIGHT, count: 8, spread: R * 0.5, life: 0.5 });
    });
    // 50: 昼と夜が同時に炸裂する
    ctx.at(50, () => {
      const c1 = up(C, 1.2);
      const dayC = add(c1, rgt, R * 0.45);
      const nightC = add(c1, rgt, -R * 0.45);
      // 中央の白い閃光
      P(dim, "lens", c1, { color: white(SILVER, 0.6), size: 2.4, life: 0.6 });
      P(dim, "flare", c1, { color: [1, 1, 1], size: 3.0, life: 0.35 });
      // 昼側: 紅炎と火柱
      P(dim, "impact", dayC, { color: DAY_HOT, size: R * 0.7, life: 0.25 });
      P(dim, "flame", dayC, { color: DAY, count: 16, spread: R * 0.4, speed: 4 });
      P(dim, "ember", dayC, { color: DAY_HOT, count: 20, spread: R * 0.4, speed: 6 });
      P(dim, "pillar", add(C, rgt, R * 0.45), { color: DAY, size: 1.2, height: 6, life: 0.7 });
      // 夜側: 氷晶と凍てつく柱
      P(dim, "impact", nightC, { color: NIGHT_ICE, size: R * 0.7, life: 0.25 });
      P(dim, "ice", nightC, { color: NIGHT_ICE, count: 16, spread: R * 0.4, speed: 5 });
      P(dim, "shard", nightC, { color: NIGHT, count: 14, spread: R * 0.4, speed: 7 });
      P(dim, "pillar", add(C, rgt, -R * 0.45), { color: NIGHT, size: 1.2, height: 6, life: 0.7 });
      shock(dim, C, white(SILVER, 0.3), R + 1.5, { debris: 12 });
      P(dim, "ring", c1, { color: DAY, size: R * 0.9, life: 0.45 });
      P(dim, "ring", up(c1, 0.3), { color: NIGHT, size: R * 1.1, life: 0.5 });
      sound(dim, "astro.explosion_big", C, 1.0, 1.5);
      sound(dim, "astro.flare", dayC, 1.0, 1.2);
      sound(dim, "astro.ice_shatter", nightC, 0.9, 1.2);
      sound(dim, "astro.corona", C, 1.2, 0.8);
      shake(dim, C, 26, 0.9, 0.6);
      flash(dim, C, 30, white(DAY, 0.6), 0.06, 0.5);
      for (const e of ctx.foes(R + 1.8, c1)) {
        const q = posOf(e);
        if (!q || !ctx.once(e, 1, "fin")) continue;
        const away = dirTo(C, q);
        hit(ctx, e, 15, { color: white(SILVER, 0.3), kb: 1.3, up: 0.7, dir: away, power: 2.2, crit: true, sound: "astro.hit_heavy" });
        // 昼の灼熱（燃える）と夜の極寒（凍える）を同時に
        try { if (typeof e.setOnFire === "function") e.setOnFire(3, true); } catch (_) { }
        effect(e, "slowness", 60, 2);
        P(dim, "flame", chest(e), { color: DAY, count: 4, spread: 0.3, speed: 2 });
        P(dim, "ice", chest(e), { color: NIGHT_ICE, count: 4, spread: 0.3, speed: 2 });
      }
    });
    // 余韻: 右に火の粉、左に氷の欠片、境に水銀の滴
    ctx.every(54, 5, 3, (i) => {
      const c1 = up(C, 0.6 + i * 0.3);
      P(dim, "ember", add(c1, rgt, R * 0.5), { color: DAY, count: 6, spread: R * 0.4, speed: 2 });
      P(dim, "ice", add(c1, rgt, -R * 0.5), { color: NIGHT_ICE, count: 4, spread: R * 0.4, speed: 1.5 });
      P(dim, "droplet", c1, { color: LIQUID, count: 5, spread: 0.6, speed: 3 });
      if (i === 0) P(dim, "smoke", c1, { count: 6, spread: 1.2, speed: 1, size: 1.4 });
    });
    return 64;
  },

  // =========================================================================
  //  三段目「水銀の飛沫」: 液体金属の刃が伸び、前方 4m を薙ぐ（弧に沿って飛沫が飛ぶ）
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    const c0 = ctx.chest();
    const pts = arc(dim, c0, f, 3.8, 75, -75, 6, SILVER, { size: 1.1, steps: 12, life: 0.3 });
    arc(dim, c0, f, 3.1, 70, -70, 6, NIGHT, { size: 0.6, steps: 8, inner: false, sparks: false, life: 0.25 });
    pts.forEach((q, k) => { if (k % 3 === 0) P(dim, "droplet", q, { color: LIQUID, count: 3, speed: 4, spread: 0.2, dir: f }); });
    P(dim, "slash_flat", up(ctx.local(1.6, 0, 0), 0.9), { color: white(SILVER, 0.2), size: 1.4, rot: yawDeg(f), life: 0.3 });
    P(dim, "spark", pts[pts.length - 1], { color: DAY, count: 6, speed: 6 });
    sound(dim, "astro.swing_heavy", p.location, 1.3, 0.9);
    sound(dim, "astro.liquid", p.location, 1.5, 0.7);
    for (const e of ctx.cone(4.6, 75, c0, f)) {
      hit(ctx, e, 5, { color: SILVER, kb: 0.9, up: 0.3, dir: f, power: 1.3, sound: "astro.hit_metal" });
    }
    if (target && valid(target)) splashAt(dim, chest(target), 0.8);
    return 10;
  },

  // =========================================================================
  //  変身の締め: 液体金属の飛沫が頭から全身を流れ落ちて固まり（走査線が下から上へ）、
  //  昼と夜の残像が八方へ走る
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    body(p, "mercury.flourish");
    sound(dim, "astro.liquid", g, 1.0, 1.0);
    sound(dim, "astro.armor_lock", g, 1.3, 0.6);
    ctx.every(0, 4, 2, (i) => {
      P(dim, "droplet", up(ctx.loc(), 2.0 - i * 0.45), { color: LIQUID, count: 10, spread: 0.45, speed: 1.2, size: 1.0 });
      ring(dim, "glow", ctx.loc(), 0.7, 14, { color: SILVER, size: 0.35, life: 0.25 }, 1.9 - i * 0.5);
    });
    ctx.at(6, () => {
      P(dim, "scan", up(g, 0.02), { color: SILVER, height: 2.1, life: 0.4 });
      P(dim, "ring_flat", up(g, 0.06), { color: SILVER, size: 1.0, life: 0.4 });
      P(dim, "flare", ctx.chest(), { color: white(SILVER, 0.6), size: 1.4, life: 0.25 });
      sound(dim, "astro.gust", g, 1.4, 0.8);
      sound(dim, "astro.boost", g, 1.6, 0.6);
    });
    for (const [t, d] of [[8, 1.2], [10, 2.4], [12, 3.6]]) {
      ctx.at(t, () => {
        for (let k = 0; k < 8; k++) {
          const dir = yawRotate(EAST, k * 45);
          const q = add(g, dir, d);
          afterimage(dim, q, k % 2 ? NIGHT : DAY, 0.35);
          if (d < 2) P(dim, "speedline", up(q, 1.0), { color: SILVER, count: 2, dir, speed: 16, spread: 0.3 });
        }
      });
    }
    ctx.at(12, () => emblem(dim, up(g, 0.05), KEY, { size: 1.4, life: 1.4, color: SILVER }));
    return 16;
  },

  // =========================================================================
  //  パッシブ「afterimage」
  //   tick: 疾走中は 5 tick ごとに液体金属の残像を置く（0.8 秒残る。最大 5 体）。残像に触れた敵対的な
  //         相手を斬る（同じ残像は同じ相手に一度だけ）
  //   onHit: 当たった所に水銀の飛沫 / onHurt: 体が液体のように揺らいで残像を置き去りにし、一瞬加速
  //   （3 秒に 1 回）/ onKill: 倒した相手が水銀に溶けて飛び散る
  // =========================================================================
  passive: {
    tick(p, st) {
      const dim = p.dimension;
      const t = now();
      const imgs = st.imgs ?? (st.imgs = []);
      let sprint = false;
      try { sprint = !!p.isSprinting; } catch (_) { }
      if (sprint) {
        const feet = { ...p.location };
        if (finite(feet)) {
          const k = st.n ?? 0;
          quickImage(dim, feet, k, 0.8);
          if (k % 3 === 0) sound(dim, "astro.liquid", feet, 1.8, 0.2);
          imgs.push({ at: feet, until: t + 16, hit: new Set() });
          if (imgs.length > 5) imgs.shift();
        }
      }
      for (let i = imgs.length - 1; i >= 0; i--) {
        const im = imgs[i];
        if (im.until < t) { imgs.splice(i, 1); continue; }
        for (const e of hostilesNear(p, up(im.at, 1.0), 1.3)) {
          if (im.hit.has(e.id)) continue;
          im.hit.add(e.id);
          const c = chest(e);
          P(dim, "slash", c, { color: white(SILVER, 0.2), size: 0.8, rot: (st.n * 50) % 360, life: 0.2 });
          P(dim, "droplet", c, { color: LIQUID, count: 4, speed: 3, spread: 0.2 });
          hit(p, e, 2.5, { color: SILVER, nova: 1, xp: 1, power: 0.7, sound: "astro.hit_metal" });
        }
      }
    },
    onHit(p, target, dmg, ctx) {
      if (ctx || !valid(target) || fxScale() < 0.75) return;
      try { P(p.dimension, "droplet", chest(target), { color: LIQUID, count: 4, speed: 3, spread: 0.2 }); } catch (_) { }
    },
    onHurt(p, attacker, dmg) {
      const t = now();
      if ((hurtCd.get(p.id) ?? -999) > t) return;
      hurtCd.set(p.id, t + 60);
      const dim = p.dimension;
      const feet = { ...p.location };
      if (!finite(feet)) return;
      quickImage(dim, feet, 0, 0.6);
      P(dim, "droplet", up(feet, 1.2), { color: LIQUID, count: 8, speed: 3, spread: 0.3 });
      sound(dim, "astro.liquid", feet, 1.3, 0.6);
      effect(p, "speed", 30, 2);
    },
    onKill(p, victim) {
      const q = posOf(victim);
      if (!q) return;
      const dim = p.dimension;
      splashAt(dim, up(q, 0.8), 1.2);
      P(dim, "ring_flat", up(q, 0.06), { color: SILVER, size: 0.8, life: 0.35 });
      sound(dim, "astro.splash", q, 1.5, 0.5);
    },
  },
  meta: {},
});
