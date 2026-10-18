// ===========================================================================
//  土星 クロノス（KRONOS）— 環を従える時の王
//
//  淡い金とアイボリーの装甲、腰を斜めに回る大環、胸の六角形、肩と背の文字盤。武器は環刃 クロノス・リング。
//  色: 発光 = 氷青の B 環（ICE = ctx.c 寄り）/ 淡い金の A 環（GOLD）/ 縞の褐色（BAND）/
//      時の紫（VIOLET = ctx.accent）/ 白い芯（ICE_HOT）
//
//   惑星技  リング・ソー           環刃を投げる。12m 先（壁に当たればそこ）で時を巻き戻すように折り返し、
//                                  行きと帰りで敵を刻む（同じ相手にも当たり直す）
//   機動技  環転 リング・スライド  足元に環を作って乗り、視線の向きへ滑走する。通り道の敵を左右へ斬り払い
//                                  （1 体に 2 回まで）、最後に横へ一閃して止まる
//   空中技  六角極渦 ヘキサゴン    宙で止まり、狙った地点の上空に六角形の嵐を集めて落とす。着地点に 4 秒残る
//                                  六角柱の嵐が、中の敵を鈍らせて刻み続ける
//   必殺    クロノス・ホライズン   時を止める時計の陣（12 の刻み・針が回って止まる）を広げ、止まった敵を
//                                  地平線のような巨大な環の一閃で両断する。時が動き出すと切り口が遅れて爆ぜる
//   三段目  環断                   環刃が水平に広がり、周りを一周薙ぐ
//   変身の締め 大環が広がって地平線のように一閃し、足元に時計の陣
//   パッシブ ring_orbit            環の欠片が体の周りを回り、触れた（2.3m 以内の）敵対的な相手を 1 秒ごとに削る。
//                                  攻撃が当たるたびに欠片が増え（3〜6 個）、多いほど強く削る。殴られると欠片が
//                                  跳ね返って反撃、倒すと欠片が散る。低速落下は passive.effects が掛ける
// ===========================================================================
import {
  register, lunge, hover, ultOpen, projectile, zone, dirTo,
} from "../engine.js";
import {
  P, line, arc, shock, emblem, flash, shake, sound, body, white, mix, afterimage, fxScale,
} from "../fx.js";
import {
  hit, freeze, hostilesNear,
} from "../combat.js";
import {
  add, up, norm, sub, yawRotate, yawDeg, rightOf, chest, effect, now, valid, clamp, rand, dot,
  onGround, hdist,
} from "../util.js";

const KEY = "saturn";
const ICE = [0.6, 0.85, 1.0];          // B 環の氷青
const ICE_HOT = [0.88, 0.96, 1.0];     // 白い芯
const GOLD = [1.0, 0.84, 0.5];         // A 環の淡い金
const BAND = [0.86, 0.62, 0.38];       // 縞の褐色
const VIOLET = [0.62, 0.52, 1.0];      // 時の紫
const UPV = { x: 0, y: 1, z: 0 };
const EAST = { x: 1, y: 0, z: 0 };

// ---------------------------------------------------------------------------
//  形の補助
// ---------------------------------------------------------------------------
/** 前方 f の軸まわりに deg だけ傾けた輪の法線（0 で水平の輪）。土星の環の傾きに。 */
function tiltN(f, deg) {
  const r = rightOf(f);
  const a = deg * Math.PI / 180;
  return norm({ x: r.x * Math.sin(a), y: Math.cos(a), z: r.z * Math.sin(a) });
}

/** 法線 n の輪を ring_n 1 回で描く（spread = 半径）。o: count size life var speed */
function ringN(dim, c, radius, n, color, o = {}) {
  P(dim, "ring_n", c, {
    color, dir: n, spread: radius, count: o.count ?? clamp(Math.round(radius * 9), 12, 48),
    size: o.size ?? 0.8, life: o.life ?? 0.3, var: o.var ?? 0, speed: o.speed,
  });
}

/** 土星の環一式: 氷青の B 環・淡い金の A 環・点の F 環（3 回）。 */
function saturnRings(dim, c, r, n, life = 0.3, k = 1) {
  ringN(dim, c, r, n, ICE, { size: 0.9 * k, life, var: 0 });
  ringN(dim, c, r * 1.25, n, GOLD, { size: 0.75 * k, life, var: 1 });
  ringN(dim, c, r * 1.42, n, white(ICE, 0.4), { size: 0.5 * k, life: life * 0.8, var: 4, count: clamp(Math.round(r * 5), 10, 40) });
}

/** 水平の正六角形の頂点（rot 度から 60° おき）。 */
function hexVerts(c, R, rot) {
  const out = [];
  for (let k = 0; k < 6; k++) {
    const d = yawRotate(EAST, rot + k * 60);
    out.push({ x: c.x + d.x * R, y: c.y, z: c.z + d.z * R });
  }
  return out;
}

/** 水平の六角形の線（line_n 6 回）。 */
function hexOutline(dim, c, R, rot, color, o = {}) {
  const v = hexVerts(c, R, rot);
  for (let k = 0; k < 6; k++) {
    line(dim, o.id ?? "glow", v[k], v[(k + 1) % 6], o.step ?? 0.55, { color, size: o.size ?? 0.8, life: o.life ?? 0.2 });
  }
  return v;
}

/** 投げた環刃の見た目（毎 tick）: 傾いた二重の環・回る三日月・火花・軌跡。 */
function sawFx(dim, pos, prev, age, f) {
  const n = tiltN(f, 16);
  ringN(dim, pos, 0.95, n, ICE, { count: 18, size: 0.95, life: 0.1 });
  ringN(dim, pos, 1.25, n, GOLD, { count: 14, size: 0.7, life: 0.1, var: 1 });
  P(dim, "slash_flat", pos, { color: ICE_HOT, rot: age * 47, size: 0.42, life: 0.12, var: age % 2 });
  P(dim, "glow", pos, { color: white(ICE, 0.5), size: 1.1, life: 0.08 });
  line(dim, "glow", prev, pos, 0.4, { color: ICE, size: 0.55, life: 0.25 });
  if (age % 2 === 0) P(dim, "spark", pos, { color: GOLD, count: 3, speed: 5, size: 0.7 });
}

// ---------------------------------------------------------------------------
//  パッシブの作業用（プレイヤーごと）: 欠片の数と反撃の再使用
// ---------------------------------------------------------------------------
const orbit = new Map();   // playerId -> { shards, until, hurtCd }
let selfHit = false;        // 欠片自身の当たり（onHit で欠片を増やさない）
function orbitOf(p) {
  let o = orbit.get(p.id);
  if (!o) { o = { shards: 3, until: 0, hurtCd: 0 }; orbit.set(p.id, o); }
  if (o.shards > 3 && now() > o.until) { o.shards--; o.until = now() + 100; }
  return o;
}
function addShard(p, k = 1) {
  const o = orbitOf(p);
  o.shards = Math.min(6, o.shards + k);
  o.until = now() + 160;
}

register(KEY, {
  // =========================================================================
  //  惑星技「リング・ソー」
  //  手元で環刃が唸りを上げて回り（0〜5）、円盤投げのように放つ（6）。環刃は 12m 進み（壁ならそこで）、
  //  時を巻き戻すように紫の文字盤を残して折り返し、持ち主の手へ帰る。行きも帰りも通り道の敵を刻む。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "saturn.ring_throw");
    sound(dim, "astro.ring_spin", p.location, 0.8, 0.8);
    sound(dim, "astro.clock_tick", p.location, 1.2, 0.5);
    ctx.every(0, 3, 2, (i) => {
      const hand = ctx.local(0.3, 0.9, 1.15);
      ringN(dim, hand, 0.5 + i * 0.14, tiltN(ctx.f, 20), ICE, { count: 14, life: 0.12, size: 0.7 });
      P(dim, "converge", hand, { color: ICE, count: 6, spread: 1.4, life: 0.25, size: 0.5 });
      P(dim, "spark", hand, { color: GOLD, count: 3, speed: 3, size: 0.6 });
    });
    ctx.at(6, () => {
      const f = ctx.liveDir();
      const v = ctx.liveView();
      const dir = norm({ x: f.x, y: clamp(v.y, -0.3, 0.3), z: f.z });
      const from = add(ctx.chest(), f, 0.9);
      sound(dim, "astro.swing_heavy", p.location, 1.1, 1.0);
      sound(dim, "astro.ring_spin", p.location, 1.3, 1.0);
      sound(dim, "astro.gust", p.location, 1.4, 0.5);
      P(dim, "flare", from, { color: white(ICE, 0.5), size: 1.0, life: 0.16 });
      arc(dim, ctx.chest(), f, 1.6, 70, -70, 6, ICE, { size: 0.8, steps: 9, sparks: false, life: 0.25 });
      shake(dim, p.location, 6, 0.12, 0.15);
      let turned = false;
      projectile(ctx, from, dir, {
        speed: 0.95, range: 12, radius: 1.25, pierce: Infinity, returns: true, hitEvery: 4, life: 70,
        damage: 4.5, hitOpts: { color: ICE, kb: 0.35, up: 0.12, power: 1.1, sound: "astro.hit_metal" },
        trail(d, pos, prev, age, s) {
          sawFx(d, pos, prev, age, f);
          if (age % 4 === 0) sound(d, "astro.ring_spin", pos, s.back ? 1.1 : 1.4, 0.45);
          if (s.back && !turned) {
            // 折り返し: 時を巻き戻す紫の文字盤と金の輪
            turned = true;
            P(d, "circle_v", pos, { color: VIOLET, size: 0.75, life: 0.55, dir: { x: -dir.x, y: 0, z: -dir.z }, spin: -360 });
            P(d, "ring", pos, { color: GOLD, size: 1.6, life: 0.3 });
            P(d, "star", pos, { color: white(VIOLET, 0.4), count: 6, spread: 0.8, life: 0.5 });
            sound(d, "astro.clock_tick", pos, 1.6, 0.9);
            sound(d, "astro.ring_spin", pos, 0.8, 0.7);
          }
        },
        onHit(e, pos, s) {
          const c = chest(e);
          P(dim, "spark", c, { color: GOLD, count: 6, speed: 6, size: 0.8, dir: norm(s.vel) });
          P(dim, "slash", c, { color: ICE_HOT, rot: rand(-40, 40), size: 0.8, life: 0.18 });
          P(dim, "shard", c, { color: ICE, count: 3, speed: 3 });
        },
        onEnd(pos, reason) {
          if (reason === "returned") {
            P(dim, "flare", pos, { color: white(ICE, 0.5), size: 0.8, life: 0.14 });
            P(dim, "nano", pos, { color: GOLD, count: 8, life: 0.3, size: 0.5 });
            sound(dim, "astro.assemble_click", pos, 1.3, 0.7);
            sound(dim, "astro.ring_spin", pos, 1.6, 0.4);
          } else if (reason !== "owner") {
            P(dim, "ring", pos, { color: ICE, size: 1.2, life: 0.25 });
            P(dim, "nano", pos, { color: ICE, count: 10, life: 0.4, size: 0.5 });
          }
        },
      });
    });
    return 16;
  },

  // =========================================================================
  //  機動技「環転 リング・スライド」
  //  足元に土星の環を作って乗り（0）、視線の向きへ舵を切りながら滑走する（0〜14）。環は地面を削って
  //  金の火花を後ろへ散らし、通り道の敵を左右へ斬り払う。最後に横へ一閃して止まる（15）。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    body(p, "saturn.ring_slide");
    sound(dim, "astro.ring_spin", p.location, 0.7, 1.0);
    sound(dim, "astro.boost", p.location, 1.0, 0.9);
    sound(dim, "astro.gust", p.location, 1.2, 0.6);
    effect(p, "resistance", 18, 1);
    const g0 = ctx.ground(ctx.loc());
    P(dim, "ring_flat", up(g0, 0.08), { color: ICE, size: 1.0, life: 0.35 });
    P(dim, "flare", up(g0, 0.3), { color: white(GOLD, 0.4), size: 0.9, life: 0.15 });
    saturnRings(dim, up(g0, 0.15), 0.9, UPV, 0.3);
    const last = new Map();
    ctx.every(0, 7, 2, () => lunge(ctx, ctx.liveDir(), 1.05, 0.02));
    ctx.every(0, 15, 1, (i) => {
      const l = ctx.loc();
      const f = ctx.liveDir();
      const r = rightOf(f);
      const g = { x: l.x, y: l.y + 0.14, z: l.z };
      const n = tiltN(f, 8);
      ringN(dim, g, 0.95, n, ICE, { count: 16, size: 0.85, life: 0.1 });
      ringN(dim, g, 1.2, n, GOLD, { count: 12, size: 0.6, life: 0.1, var: 1 });
      P(dim, "slash_flat", g, { color: ICE_HOT, rot: i * 55, size: 0.4, life: 0.12, var: i % 2 });
      P(dim, "spark", add(g, f, -0.9), { color: GOLD, count: 4, speed: 5, size: 0.7, dir: norm({ x: -f.x, y: 0.5, z: -f.z }) });
      P(dim, "speedline", up(l, 1.0), { color: ICE, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 14, spread: 0.7 });
      if (i % 2 === 0) P(dim, "dust", add(g, f, -0.6), { count: 4, speed: 2, size: 0.8 });
      if (i % 4 === 0) {
        afterimage(dim, l, i % 8 ? GOLD : ICE, 0.3);
        sound(dim, "astro.ring_spin", l, 1.2, 0.45);
      }
      for (const e of ctx.foes(1.9, add(ctx.chest(), f, 0.6))) {
        if (i - (last.get(e.id) ?? -99) < 6 || !ctx.once(e, 2, "slide")) continue;
        last.set(e.id, i);
        const s = dot(sub(e.location, l), r) >= 0 ? 1 : -1;
        const away = norm({ x: r.x * s + f.x * 0.4, y: 0, z: r.z * s + f.z * 0.4 });
        P(dim, "slash", chest(e), { color: ICE_HOT, rot: s > 0 ? 30 : -30, size: 0.9, life: 0.2 });
        hit(ctx, e, 7, { color: ICE, kb: 1.1, up: 0.4, dir: away, power: 1.3, sound: "astro.hit_metal" });
      }
    });
    ctx.at(15, () => {
      const l = ctx.loc();
      const f = ctx.liveDir();
      const g = ctx.ground(l);
      sound(dim, "astro.swing_heavy", l, 1.1, 1.0);
      sound(dim, "astro.ring_spin", l, 0.6, 0.8);
      sound(dim, "astro.land", l, 1.2, 0.6);
      P(dim, "slash_flat", up(l, 1.0), { color: ICE, rot: yawDeg(f), size: 1.15, life: 0.3, var: 1 });
      arc(dim, ctx.chest(), f, 2.3, -100, 100, 0, GOLD, { size: 0.8, steps: 12, life: 0.3 });
      shock(dim, g, ICE, 2.6, { debris: 6 });
      ringN(dim, up(g, 0.3), 1.0, UPV, GOLD, { count: 24, speed: 6, life: 0.35, var: 1 });
      shake(dim, l, 8, 0.25, 0.2);
      for (const e of ctx.foes(2.8)) {
        if (ctx.once(e, 1, "sweep")) hit(ctx, e, 5, { color: GOLD, kb: 1.0, up: 0.3, dir: dirTo(l, e.location) });
      }
    });
    return 19;
  },

  // =========================================================================
  //  空中技「六角極渦 ヘキサゴン」
  //  宙で止まり、環刃を頭上に掲げる。狙った地点の 9m 上に六角形の嵐が渦を巻いて集まり（0〜9）、
  //  六角柱になって落ちる（10〜14）。着地点に 4 秒残る六角柱の嵐が、中の敵を鈍らせて刻み続ける。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 20, 0.3);
    body(p, "saturn.hex_cast");
    const target = ctx.aim(24);
    const R = 4.2;
    const rot0 = yawDeg(ctx.f) + 30;
    sound(dim, "astro.wind", p.location, 0.8, 0.9);
    sound(dim, "astro.gravity", p.location, 1.3, 0.7);
    sound(dim, "astro.beam_charge", p.location, 0.9, 0.6);
    ctx.at(0, () => {
      P(dim, "hex_circle", up(target, 0.06), { color: ICE, size: R / 1.2, life: 0.9, spin: 40 });
      P(dim, "circle", up(target, 0.08), { color: VIOLET, size: R / 1.8, life: 0.8, spin: -60 });
    });
    ctx.every(0, 5, 2, (i) => {
      const top = up(target, 9 - i * 0.3);
      hexOutline(dim, top, R * (0.45 + i * 0.13), rot0 + i * 14, i % 2 ? ICE : white(ICE, 0.4), { life: 0.22, size: 0.85 });
      P(dim, "converge", top, { color: ICE, count: 10, spread: 3.2, life: 0.4, size: 0.9 });
      P(dim, "wind", top, { color: white(ICE, 0.3), count: 3, spread: 2.5, speed: 4 });
      const hand = ctx.local(0.2, 0.3, 2.6);
      P(dim, "hex", hand, { color: VIOLET, count: 3, spread: 0.6, life: 0.3, size: 0.6 });
    });
    ctx.at(9, () => {
      sound(dim, "astro.gust", target, 0.8, 1.2);
      sound(dim, "astro.thunder", target, 1.5, 0.5);
      line(dim, "glow", ctx.local(0.4, 0.3, 1.6), up(target, 9), 0.5, { color: ICE_HOT, size: 0.7, life: 0.25 });
    });
    // 落ちる六角柱（上下の六角と縦の稜）
    for (let k = 0; k <= 4; k++) {
      ctx.at(10 + k, () => {
        const y = 9 * (1 - k / 4);
        const bot = hexOutline(dim, up(target, y + 0.1), R, rot0 + k * 10, ICE_HOT, { life: 0.15, size: 1.0 });
        if (k % 2 === 0) {
          for (const v of bot) line(dim, "glow", up(v, 3), v, 0.6, { color: ICE, size: 0.7, life: 0.15 });
        }
        P(dim, "speedline", up(target, y + 1.5), { color: ICE, count: 4, dir: { x: 0, y: -1, z: 0 }, speed: 18, spread: R * 0.6 });
      });
    }
    ctx.at(14, () => {
      const g = ctx.ground(target);
      P(dim, "impact", up(g, 1.0), { color: white(ICE, 0.3), size: 2.4, life: 0.2 });
      P(dim, "flare", up(g, 0.8), { color: white(ICE, 0.5), size: 2.0, life: 0.25 });
      shock(dim, g, ICE, R, { debris: 10 });
      P(dim, "hex_circle", up(g, 0.06), { color: ICE, size: R / 1.2, life: 4.0, spin: 25 });
      P(dim, "hex_circle", up(g, 0.09), { color: VIOLET, size: R / 1.7, life: 4.0, spin: -45 });
      P(dim, "vortex", up(g, 0.1), { color: ICE, spread: R * 0.55, height: 4, life: 4.0, rate: 55, spin: 420, size: 1.1 });
      for (const v of hexVerts(up(g, 0.05), R, rot0)) {
        P(dim, "pillar", v, { color: white(ICE, 0.2), size: 0.7, height: 3.5, life: 0.6 });
      }
      sound(dim, "astro.impact_heavy", g, 1.0, 1.1);
      sound(dim, "astro.explosion", g, 1.3, 0.8);
      sound(dim, "astro.wind", g, 0.7, 1.2);
      shake(dim, g, 14, 0.45, 0.35);
      for (const e of ctx.foes(R + 0.5, up(g, 1.0))) {
        if (ctx.once(e, 1, "drop")) hit(ctx, e, 6, { color: ICE, pull: g, kb: 0.4, up: 0.25, power: 1.6 });
      }
      zone(ctx, g, {
        radius: R, ticks: 80, every: 8, damage: 1.5, height: 3.5,
        effects: [["slowness", 24, 2]], hit: { color: ICE },
        visualEvery: 2,
        visual(d, c, age) {
          const rot = rot0 + age * 3;
          const bot = hexOutline(d, up(c, 0.15), R, rot, age % 4 ? ICE : white(ICE, 0.35), { life: 0.14, size: 0.85 });
          if (age % 4 === 0) {
            hexOutline(d, up(c, 3.3), R * 0.92, rot, ICE, { life: 0.22, size: 0.7 });
            for (let k = 0; k < 6; k += 2) line(d, "glow", bot[k], up(bot[k], 3.3), 0.7, { color: white(ICE, 0.2), size: 0.6, life: 0.22 });
          }
          if (age % 6 === 0) {
            P(d, "wind", up(c, 1.2), { color: white(ICE, 0.3), count: 4, spread: R * 0.6, speed: 6 });
            P(d, "shard", up(c, 1.6), { color: GOLD, count: 3, spread: R * 0.5, speed: 3 });
          }
          if (age % 10 === 0) sound(d, "astro.wind", c, 1.1, 0.5);
        },
        onPulse(foes, z) {
          for (const e of foes) {
            if (!valid(e)) continue;
            const q = chest(e);
            P(dim, "slash", q, { color: ICE_HOT, rot: rand(0, 360), size: 0.7, life: 0.16 });
            P(dim, "spark", q, { color: GOLD, count: 3, speed: 4, size: 0.6 });
          }
          if (foes.length) sound(dim, "astro.hit_metal", z.center, rand(1.3, 1.6), 0.5);
        },
        onEnd(z) {
          const c = z.center;
          hexOutline(dim, up(c, 0.2), R * 0.6, rot0, white(ICE, 0.3), { life: 0.4, size: 0.7, id: "star" });
          P(dim, "shard", up(c, 1.2), { color: ICE, count: 10, spread: R * 0.5, speed: 4 });
          sound(dim, "astro.ice_shatter", c, 1.3, 0.6);
        },
      });
    });
    return 22;
  },

  // =========================================================================
  //  必殺「クロノス・ホライズン」
  //  時を止め（ultOpen。止まる音は 25 tick 後）、環刃を天に掲げる。足元に時計の陣が広がり、12 の刻みが
  //  一つずつ灯り、針が回る（2〜24）。25 で時が止まり、陣の中の敵は紫の六角に閉じ込められる。
  //  大環が胸の高さで広がって溜め（30〜42）、44 で地平線のような巨大な環の一閃。時が動き出すと
  //  切り口が遅れて爆ぜ（52）、時計の陣が砕ける（58）。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 70, 16);
    const C = ctx.ground(ctx.loc());
    const F = ctx.f;
    const RC = 8;          // 時計の陣の半径
    const R = 13;          // 一閃の半径
    ctx.at(2, () => body(p, "saturn.horizon"));
    ctx.at(2, () => {
      P(dim, "circle", up(C, 0.05), { color: GOLD, size: RC / 1.2, life: 3.2, spin: 12 });
      P(dim, "hex_circle", up(C, 0.07), { color: VIOLET, size: 3.6, life: 3.2, spin: -20 });
      emblem(dim, up(C, 0.09), KEY, { size: 2.2, life: 3.2, spin: 30 });
      ringN(dim, up(C, 0.12), RC, UPV, GOLD, { count: 48, size: 0.7, life: 1.6, var: 4 });
      sound(dim, "astro.gravity", C, 0.6, 1.0);
    });
    // 12 の刻みが一つずつ灯る
    for (let h = 0; h < 12; h++) {
      ctx.at(2 + h * 2, () => {
        const d = yawRotate(F, h * 30);
        const q = onGround(dim, add(C, d, RC), 6);
        const major = h % 3 === 0;
        P(dim, "pillar", up(q, 0.05), { color: major ? GOLD : ICE, size: major ? 0.9 : 0.6, height: major ? 3.2 : 2.0, life: 2.4 });
        P(dim, "star", up(q, 1.0), { color: white(VIOLET, 0.3), count: 3, spread: 0.4, life: 0.6 });
        sound(dim, "astro.clock_tick", C, major ? 0.9 : 1.2, 0.8);
      });
    }
    // 針が回る（長針は速く、短針はゆっくり）
    ctx.every(2, 12, 2, (i) => {
      const c0 = up(C, 0.3);
      line(dim, "glow", c0, add(c0, yawRotate(F, i * 36), RC * 0.9), 0.5, { color: ICE_HOT, size: 0.9, life: 0.14 });
      line(dim, "glow", c0, add(c0, yawRotate(F, 90 + i * 4), RC * 0.55), 0.5, { color: VIOLET, size: 1.2, life: 0.14 });
    });
    // 時が止まる
    ctx.at(25, () => {
      const c0 = up(C, 0.3);
      flash(dim, C, 30, white(VIOLET, 0.6), 0.05, 0.4);
      P(dim, "lens", ctx.chest(), { color: VIOLET, size: 2.0, life: 0.6 });
      ringN(dim, up(C, 1.0), RC, UPV, VIOLET, { count: 40, size: 1.1, life: 0.8, var: 3 });
      line(dim, "glow", c0, add(c0, yawRotate(F, 12 * 36), RC * 0.9), 0.5, { color: VIOLET, size: 1.0, life: 1.4 });
      line(dim, "glow", c0, add(c0, yawRotate(F, 90 + 12 * 4), RC * 0.55), 0.5, { color: VIOLET, size: 1.3, life: 1.4 });
      sound(dim, "astro.clock_tick", C, 0.5, 1.2);
      sound(dim, "astro.ice_crack", C, 0.7, 0.8);
      for (const e of ctx.foes(RC + 4, up(C, 1))) {
        freeze(e, 40, true);
        const q = chest(e);
        P(dim, "hex", q, { color: VIOLET, count: 10, spread: 0.9, life: 1.8, size: 0.7 });
        P(dim, "circle_v", up(q, 1.3), { color: VIOLET, size: 0.35, life: 1.6, dir: dirTo(e.location, C), spin: 0 });
      }
    });
    // 大環が胸の高さで広がって溜める
    ctx.at(30, () => sound(dim, "astro.beam_charge", C, 0.7, 1.0));
    ctx.every(30, 7, 2, (i) => {
      const rr = 2 + i * 1.8;
      saturnRings(dim, ctx.chest(), rr, tiltN(F, 6), 0.2, 1.1);
      P(dim, "converge", ctx.local(0.4, 0.6, 1.4), { color: ICE, count: 8, spread: 2.5, life: 0.3, size: 0.8 });
      if (i % 2 === 0) sound(dim, "astro.ring_spin", C, 0.6 + i * 0.1, 0.9);
    });
    // 一閃
    ctx.at(44, () => {
      const c = ctx.chest();
      const f = ctx.liveDir();
      ringN(dim, c, R, UPV, ICE_HOT, { count: 48, size: 1.6, life: 0.6 });
      ringN(dim, c, R * 0.82, UPV, GOLD, { count: 40, size: 1.2, life: 0.5, var: 1 });
      ringN(dim, c, R * 0.6, UPV, ICE, { count: 32, size: 1.0, life: 0.4 });
      for (let k = 0; k < 6; k++) {
        P(dim, "slash_flat", c, { color: k % 2 ? GOLD : ICE, rot: yawDeg(f) + k * 60, size: 3.4, life: 0.45, var: 1 });
      }
      P(dim, "slash_big", c, { color: white(ICE, 0.5), rot: 90, size: 2.4, life: 0.4 });
      P(dim, "flare", c, { color: ICE_HOT, size: 4, life: 0.35 });
      P(dim, "lens", c, { color: ICE, size: 3, life: 0.6 });
      shock(dim, C, ICE, R, { debris: 20 });
      sound(dim, "astro.swing_heavy", c, 0.6, 1.5);
      sound(dim, "astro.explosion_big", c, 0.9, 1.3);
      sound(dim, "astro.ring_spin", c, 0.5, 1.4);
      sound(dim, "astro.gust", c, 0.8, 1.0);
      shake(dim, C, 30, 0.9, 0.7);
      flash(dim, C, 32, white(ICE, 0.7), 0.06, 0.5);
      for (const e of ctx.foes(R + 1.5, c)) {
        if (Math.abs(e.location.y + 1 - c.y) > 4 || !ctx.once(e, 1, "horizon")) continue;
        P(dim, "slash", chest(e), { color: ICE_HOT, rot: 90, size: 1.6, life: 0.3 });
        hit(ctx, e, 24, { color: ICE, kb: 1.6, up: 0.35, dir: dirTo(C, e.location), power: 2.2, crit: 0.35, sound: "astro.hit_heavy" });
      }
    });
    // 時が動き出す: 切り口が遅れて爆ぜる
    ctx.at(52, () => {
      sound(dim, "astro.clock_tick", C, 1.6, 1.0);
      sound(dim, "astro.explosion", C, 1.2, 1.0);
      ringN(dim, up(C, 0.3), RC, UPV, VIOLET, { count: 40, speed: 3, life: 0.6, var: 3 });
      for (const e of ctx.foes(R + 4, up(C, 1))) {
        if (!ctx.once(e, 1, "sever")) continue;
        const q = chest(e);
        P(dim, "cross", q, { color: VIOLET, size: 1.6, life: 0.3 });
        P(dim, "shard", q, { color: GOLD, count: 6, speed: 4 });
        hit(ctx, e, 10, { color: VIOLET, up: 0.7, kb: 0.4, dir: dirTo(C, e.location), power: 1.8, crit: true });
      }
    });
    // 時計の陣が砕ける
    ctx.at(58, () => {
      ringN(dim, up(C, 0.6), RC, UPV, GOLD, { count: 36, speed: 4, life: 0.7, var: 1 });
      P(dim, "shard", up(C, 1.0), { color: ICE, count: 16, spread: RC * 0.6, speed: 4 });
      P(dim, "ring_flat", up(C, 0.1), { color: GOLD, size: RC / 1.05, life: 0.6 });
      P(dim, "lens", up(C, 1.5), { color: white(GOLD, 0.4), size: 2.4, life: 0.5 });
      sound(dim, "astro.ice_shatter", C, 0.8, 1.2);
      sound(dim, "astro.clock_tick", C, 0.7, 0.8);
    });
    return 66;
  },

  // =========================================================================
  //  三段目「環断」: 環刃が水平に広がり、周りを一周薙ぐ
  // =========================================================================
  combo3(ctx) {
    const { p, dim } = ctx;
    const c = ctx.chest();
    const f = ctx.liveDir();
    sound(dim, "astro.swing_heavy", p.location, 1.1, 0.9);
    sound(dim, "astro.ring_spin", p.location, 1.2, 0.8);
    P(dim, "slash_flat", c, { color: ICE, rot: yawDeg(f), size: 1.1, life: 0.3, var: 1 });
    ringN(dim, c, 1.0, UPV, ICE, { count: 24, speed: 6, life: 0.35, size: 0.9 });
    ringN(dim, up(c, 0.05), 1.2, UPV, GOLD, { count: 20, speed: 5, life: 0.35, size: 0.7, var: 1 });
    ctx.at(3, () => {
      P(dim, "slash_flat", ctx.chest(), { color: GOLD, rot: yawDeg(f) + 180, size: 1.15, life: 0.3, var: 1 });
      sound(dim, "astro.swing", p.location, 1.3, 0.7);
    });
    for (const e of ctx.foes(3.4, c)) {
      hit(ctx, e, 5, { color: ICE, kb: 0.9, up: 0.25, dir: dirTo(p.location, e.location), power: 1.3 });
    }
    return 12;
  },

  // =========================================================================
  //  変身の締め: 大環が広がって地平線のように一閃し、足元に時計の陣
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    const f = ctx.f;
    sound(dim, "astro.ring_spin", g, 0.8, 1.0);
    sound(dim, "astro.clock_tick", g, 1.0, 0.8);
    emblem(dim, up(g, 0.05), KEY, { size: 1.6, life: 2.0 });
    P(dim, "circle", up(g, 0.07), { color: GOLD, size: 2.2, life: 1.6, spin: 60 });
    ringN(dim, up(g, 0.1), 2.6, UPV, GOLD, { count: 12, size: 1.0, life: 1.4, var: 1 });
    P(dim, "flare", ctx.chest(), { color: white(ICE, 0.5), size: 1.2, life: 0.3 });
    ctx.every(0, 4, 3, (i) => {
      saturnRings(dim, up(g, 1.0), 1.0 + i * 1.5, tiltN(f, 22 - i * 5), 0.35);
    });
    ctx.at(8, () => {
      P(dim, "slash_flat", up(g, 1.0), { color: ICE, rot: yawDeg(f), size: 1.8, life: 0.35, var: 1 });
      P(dim, "slash_flat", up(g, 1.0), { color: GOLD, rot: yawDeg(f) + 180, size: 1.6, life: 0.35, var: 1 });
      ringN(dim, up(g, 1.0), 1.5, UPV, ICE_HOT, { count: 36, speed: 8, life: 0.4 });
      sound(dim, "astro.swing_heavy", g, 1.3, 0.7);
      sound(dim, "astro.clock_tick", g, 1.5, 0.6);
    });
    ctx.every(2, 6, 3, () => P(dim, "orbit", up(g, 1.0), { color: GOLD, count: 4, spread: 1.6, life: 0.5, size: 0.9 }));
    return 20;
  },

  // =========================================================================
  //  パッシブ「環の欠片 ring_orbit」
  // =========================================================================
  passive: {
    tick(p, st) {
      const dim = p.dimension;
      const o = orbitOf(p);
      const n = st.n ?? 0;
      const c = { x: p.location.x, y: p.location.y + 0.95, z: p.location.z };
      if (n % 2 === 0) {
        P(dim, "orbit", c, { color: n % 4 ? GOLD : ICE, count: o.shards, spread: 1.5, life: 0.55, size: 0.9, spin: 330 });
      }
      if (n % 6 === 0 && fxScale() >= 1) {
        ringN(dim, c, 1.5, tiltN({ x: 0, y: 0, z: 1 }, 18), white(ICE, 0.3), { count: 16, size: 0.45, life: 0.3, var: 4 });
      }
      st.cd = (st.cd ?? 10) - 5;
      if (st.cd > 0) return;
      const foes = hostilesNear(p, chest(p), 2.3).slice(0, Math.ceil(o.shards / 2));
      if (!foes.length) return;
      st.cd = 20;
      for (const e of foes) {
        const q = chest(e);
        P(dim, "spark", q, { color: GOLD, count: 4, speed: 4, size: 0.6 });
        P(dim, "shard", q, { color: ICE, count: 2, speed: 2 });
        selfHit = true;
        try {
          hit(p, e, 1.5 + 0.3 * (o.shards - 3), { color: GOLD, nova: 1, xp: 1, power: 0.5, kb: 0.15, sound: "astro.hit_metal" });
        } finally { selfHit = false; }
      }
      sound(dim, "astro.ring_spin", c, 1.8, 0.3);
    },
    onHit(p, target, dmg, ctx) {
      // 当たるたびに欠片が一つ増える（技の多段は 1 技につき 1 つまで）
      if (selfHit) return;
      try {
        if (ctx && !ctx.once(target, 1, "orbit_shard")) return;
      } catch (_) { return; }
      addShard(p, 1);
    },
    onHurt(p, attacker) {
      // 殴られると欠片が跳ね返って反撃する（1.5 秒に 1 回）
      const o = orbitOf(p);
      if (!attacker || !valid(attacker) || now() < o.hurtCd) return;
      if (hdist(attacker.location, p.location) > 4) return;
      o.hurtCd = now() + 30;
      const dim = p.dimension;
      const from = chest(p);
      const to = chest(attacker);
      line(dim, "star", from, to, 0.4, { color: GOLD, size: 0.8, life: 0.25 });
      P(dim, "spark", to, { color: ICE, count: 5, speed: 5, size: 0.7 });
      sound(dim, "astro.ring_spin", to, 1.7, 0.5);
      selfHit = true;
      try {
        hit(p, attacker, 2, { color: GOLD, nova: 1, xp: 1, power: 0.6, kb: 0.4, sound: "astro.hit_metal" });
      } finally { selfHit = false; }
    },
    onKill(p, victim) {
      // 倒すと欠片が散り、新しい欠片が軌道に加わる
      addShard(p, 1);
      let q;
      try { q = chest(victim); } catch (_) { return; }
      const dim = p.dimension;
      P(dim, "shard", q, { color: GOLD, count: 8, speed: 4 });
      ringN(dim, q, 0.6, UPV, mix(ICE, GOLD, 0.5), { count: 16, speed: 4, life: 0.35, var: 1 });
    },
  },
});
