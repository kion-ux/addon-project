// ===========================================================================
//  金星 モーニングスター（MORNING STAR）— 明けの明星の女神
//
//  金とクリームの装甲・花弁のスカート・肩の雲のポッド・額の八芒星と光輪。武器は明星杖 ルシファー・セプター。
//  色: 硫黄の発光（SULFUR = ctx.c）/ 硫酸（ACID）/ 黄色い硫酸雲（CLOUD）/ 金（GOLD）/
//      明けの明星の白金（STAR）/ 薔薇色（ROSE = ctx.accent）/ 温室の熱（HEAT）
//
//   惑星技  硫酸雲 アシッド・ヴェール  杖の星に雲を集めて硫酸雲の弾を放つ。着弾点に 4 秒残る黄色い雲が毒と鈍化で蝕む
//   機動技  逆行旋 レトログレード      金星の自転のように逆回り（時計回り）に二回転しながら突進。触れた敵を背後へ投げ、
//                                      最後に杖で後ろを薙ぎ払う
//   空中技  温室熱波 グリーンハウス    宙で熱を溜め、星を真下へ向けて急降下。着地点に 465℃ の熱の天蓋（半球）を張る
//   必殺    明けの明星 モーニングスター 時を止め、天に巨大な八芒星を灯す → 標的へ星光の柱を次々に降らせ、最後に明星そのもの
//                                      が落ちる大柱 → 硫酸雲が空を覆い、硫酸の雨が降り注ぐ
//   三段目  星屑の花                    ピルエットの後、足元に八枚の花弁の星の花が咲き、周りの敵を灼く
//   変身の締め 黄色い雲が渦を巻いて晴れ、頭上に明星（八芒星）が灯る
//   パッシブ acid_thorns               殴ってきた相手を硫酸で灼き（小さなダメージ）、毒で蝕む。肩の雲のポッドが雲を吐く
// ===========================================================================
import { register, lunge, hover, plunge, ultOpen, projectile, zone, dirTo } from "../engine.js";
import {
  P, ring, arc, shock, beam, emblem, flash, shake, sound, body, white, mix, afterimage, fxScale,
} from "../fx.js";
import { hit } from "../combat.js";
import {
  add, up, norm, yawRotate, yawDeg, rightOf, flatDir, chest, dist, onGround, effect, now, valid,
  rand, finite,
} from "../util.js";

const KEY = "venus";
const SULFUR = [0.89, 1.0, 0.38];
const ACID = [0.8, 0.95, 0.26];
const CLOUD = [0.97, 0.89, 0.52];
const RAIN_CLOUD = [0.78, 0.72, 0.38];
const GOLD = [1.0, 0.78, 0.32];
const CREAM = [1.0, 0.95, 0.84];
const STAR = [1.0, 0.95, 0.66];
const ROSE = [1.0, 0.5, 0.66];
const HEAT = [1.0, 0.55, 0.16];
const EAST = { x: 1, y: 0, z: 0 };
const thornCd = new Map();     // `${playerId}|${attackerId}` -> 最後に棘が働いた tick
let thornBusy = false;         // 棘の一撃の間は onHit の演出を出さない

// ---------------------------------------------------------------------------
//  補助
// ---------------------------------------------------------------------------
/** 杖の星の頭のおおよその位置（右手で斜め前上に構えた時）。fwd/right/lift で構えに合わせる。 */
function staffHead(p, f = flatDir(p), fwd = 1.0, right = 0.5, lift = 1.6) {
  const r = rightOf(f);
  const l = p.location;
  return { x: l.x + f.x * fwd + r.x * right, y: l.y + lift, z: l.z + f.z * fwd + r.z * right };
}

/**
 * 八芒星（縦の面。面は f の向きを向く）。長い光条 4 本（白金寄り）と短い光条 4 本、芯の光。
 * 光条は beam（中心から外へ伸びる帯）なので 1 本 1 回。rot で面内に回す（度）。
 */
function eightStar(dim, c, f, size, color, life = 0.25, rot = 0) {
  const r = rightOf(f);
  for (let k = 0; k < 8; k++) {
    const a = (k * 45 + rot) * Math.PI / 180;
    const d = { x: r.x * Math.sin(a), y: Math.cos(a), z: r.z * Math.sin(a) };
    const long = k % 2 === 0;
    P(dim, "beam", c, { color: long ? white(color, 0.45) : color, dir: d, len: long ? size : size * 0.55,
                        size: long ? 0.22 + size * 0.07 : 0.14 + size * 0.04, life });
  }
  P(dim, "glow", c, { color: white(color, 0.6), size: 0.6 + size * 0.35, life });
}

/** 硫酸雲の塊（ゆっくり膨らんで漂う。半透明）。 */
function acidPuff(dim, at, size, count = 2, life = 1.6, spread = 0.4) {
  P(dim, "cloud", at, { color: CLOUD, count, size, life, spread, dir: { x: rand(-0.12, 0.12), y: 0.08, z: rand(-0.12, 0.12) } });
}

/** 硫酸が触れた所の泡と滴（蝕む演出）。 */
function corrode(dim, at, k = 1) {
  P(dim, "bubble", at, { color: ACID, count: Math.round(4 * k), spread: 0.45, speed: 0.5 });
  P(dim, "droplet", at, { color: ACID, count: Math.round(5 * k), speed: 2.2, size: 0.8 });
}

// ---------------------------------------------------------------------------
//  惑星技の着弾: 硫酸雲（4 秒残る）
// ---------------------------------------------------------------------------
function acidBloom(ctx, pos) {
  const dim = ctx.dim;
  if (!finite(pos)) return;
  const g = onGround(dim, pos, 6);
  const R = 3.2;
  // 着弾: 硫酸の飛沫・閃光・地を走る黄緑の輪・雲が一気に膨らむ
  P(dim, "impact", up(g, 0.8), { color: white(SULFUR, 0.3), size: 1.7, life: 0.16 });
  P(dim, "splash", up(g, 0.15), { color: ACID, count: 2, spread: 1.0 });
  P(dim, "shock_flat", up(g, 0.08), { color: SULFUR, size: R / 1.5, life: 0.45 });
  P(dim, "droplet", up(g, 0.7), { color: ACID, count: 16, speed: 5.5, spread: 0.4 });
  P(dim, "cloud", up(g, 1.0), { color: CLOUD, count: 7, spread: 2.0, size: 1.15, life: 4.0, dir: { x: 0, y: 0.05, z: 0 } });
  P(dim, "smoke", up(g, 0.4), { color: [0.62, 0.56, 0.22], count: 6, spread: 1.2, size: 1.3 });
  ring(dim, "dot", g, R, 24, { color: SULFUR, size: 1.0, life: 0.6, speed: 2 }, 0.2);
  sound(dim, "astro.splash", g, 0.7, 1.1);
  sound(dim, "astro.explosion", g, 1.5, 0.6);
  sound(dim, "astro.liquid", g, 0.6, 0.9);
  shake(dim, g, 10, 0.18, 0.2);
  zone(ctx, g, {
    radius: R, ticks: 80, every: 10, delay: 4, damage: 1.2, height: 2.6,
    hit: { color: ACID, nova: 1, xp: 1 },
    effects: [["poison", 50, 1], ["slowness", 24, 1]],
    visualEvery: 2,
    visual(d, c, age) {
      if (age % 8 === 0) {
        const a = rand(0, Math.PI * 2), rr = rand(0, R * 0.8);
        acidPuff(d, { x: c.x + Math.cos(a) * rr, y: c.y + 0.6, z: c.z + Math.sin(a) * rr }, rand(0.9, 1.3), 2, 1.8, 0.6);
      }
      if (age % 6 === 0) ring(d, "dot", c, R, 18, { color: SULFUR, size: 0.8, life: 0.45 }, 0.15);
      if (age % 4 === 2) P(d, "bubble", up(c, 0.3), { color: ACID, count: 4, spread: R * 0.7, speed: 0.6 });
      if (age % 20 === 0) P(d, "hex_circle", up(c, 0.05), { color: mix(SULFUR, GOLD, 0.4), size: R / 1.2, life: 1.1, spin: 24 });
    },
    onPulse(foes, z) {
      if (!foes.length) return;
      sound(dim, "astro.liquid", z.center, 1.4, 0.45);
      for (const e of foes.slice(0, 6)) corrode(dim, chest(e), 0.8);
    },
    onEnd(z) {
      // 雲が晴れる: 大きく膨らんで薄れ、硫黄の粒が舞い上がる
      acidPuff(dim, up(z.center, 0.8), 1.5, 4, 1.4, 1.6);
      P(dim, "dot", up(z.center, 0.6), { color: SULFUR, count: 14, spread: R * 0.6, speed: 0.8, grav: 1.2 });
    },
  });
}

// ---------------------------------------------------------------------------
//  空中技の着地: 465℃ の熱の天蓋
// ---------------------------------------------------------------------------
function greenhouse(ctx, l) {
  const { p, dim } = ctx;
  const g = onGround(dim, l, 4);
  const R = 5.0;
  body(p, "venus.dome");
  sound(dim, "astro.impact_heavy", g, 0.9, 1.2);
  sound(dim, "astro.explosion", g, 0.8, 1.0);
  sound(dim, "astro.corona", g, 0.9, 1.0);
  shake(dim, g, 18, 0.55, 0.45);
  flash(dim, g, 10, [1, 0.72, 0.32], 0.04, 0.45);
  P(dim, "impact", up(g, 0.6), { color: white(HEAT, 0.3), size: 2.6, life: 0.2 });
  P(dim, "flare", up(g, 0.9), { color: white(GOLD, 0.4), size: 2.2, life: 0.3 });
  shock(dim, g, HEAT, 4.5, { debris: 10 });
  P(dim, "ember", up(g, 0.4), { color: HEAT, count: 20, speed: 4, spread: 1.5 });
  emblem(dim, up(g, 0.07), KEY, { size: 2.2, life: 3.5, spin: 25, color: HEAT });
  for (const e of ctx.foes(4.4, up(g, 0.8))) {
    if (ctx.once(e, 1, "dive")) {
      hit(ctx, e, 9, { color: HEAT, kb: 0.9, up: 0.55, dir: dirTo(g, e.location), power: 1.7 });
    }
  }
  // 天蓋が立ち上がる（下から上へ輪が積み上がる）
  for (let k = 0; k < 5; k++) {
    ctx.at(2 + k * 2, () => {
      const h = k * 1.15;
      const rr = Math.sqrt(Math.max(0.2, R * R - h * h));
      ring(dim, "hex", g, rr, Math.round(10 + rr * 5), { color: mix(HEAT, GOLD, k / 5), size: 1.0, life: 0.6 }, h + 0.1);
      if (k === 4) P(dim, "flare", up(g, R), { color: white(GOLD, 0.5), size: 1.6, life: 0.35 });
    });
  }
  zone(ctx, g, {
    radius: R, ticks: 70, every: 10, delay: 10, damage: 1.6, height: 4.5,
    hit: { color: HEAT, nova: 1, xp: 1 },
    effects: [["weakness", 30, 0]],
    visualEvery: 2,
    visual(d, c, age) {
      // 半球の天蓋（高さを変えた輪を 5 段。1 段 1 回の ring_n）
      if (age % 6 === 0) {
        for (let k = 0; k < 5; k++) {
          const h = k * 1.15;
          const rr = Math.sqrt(Math.max(0.2, R * R - h * h));
          ring(d, k < 3 ? "hex" : "glow", c, rr, Math.round(10 + rr * 4), { color: mix(HEAT, GOLD, k / 5), size: 0.9, life: 0.4 }, h + 0.1);
        }
      }
      if (age % 4 === 0) P(d, "ember", up(c, 0.5), { color: HEAT, count: 6, spread: R * 0.6, speed: 1.2 });
      if (age % 8 === 4) P(d, "aura", c, { color: HEAT, count: 8, spread: R * 0.85, size: 1.3 });
      if (age % 10 === 5) P(d, "ring_flat", up(c, 0.1), { color: HEAT, size: R / 1.1, life: 0.5 });
      if (age % 16 === 0) sound(d, "astro.corona", c, 0.8, 0.45);
    },
    onPulse(foes) {
      for (const e of foes.slice(0, 6)) {
        P(dim, "flame", chest(e), { color: HEAT, count: 3, spread: 0.3, speed: 1.5 });
        try { e.setOnFire?.(2, true); } catch (_) { }
      }
    },
    onEnd(z) {
      // 天蓋が弾けて熱が外へ逃げる
      shock(dim, z.center, GOLD, R, { debris: 0, dust: false });
      P(dim, "ring", up(z.center, 1.5), { color: HEAT, size: 2.5, life: 0.4 });
      P(dim, "smoke", up(z.center, 0.8), { color: [0.5, 0.42, 0.3], count: 8, spread: R * 0.4, size: 1.6 });
      sound(dim, "astro.gust", z.center, 0.8, 0.8);
    },
  });
}

// ---------------------------------------------------------------------------
//  必殺: 星光の柱 1 本
// ---------------------------------------------------------------------------
function starPillar(ctx, S, g, base, big = false) {
  const dim = ctx.dim;
  const w = big ? 2.4 : 1.0;
  beam(dim, S, up(g, 0.2), STAR, { size: big ? 3.0 : 1.4, life: big ? 0.6 : 0.35 });
  P(dim, "pillar", up(g, 0.05), { color: STAR, size: 1.8 * w, height: 14, life: big ? 1.0 : 0.7 });
  P(dim, "pillar", up(g, 0.05), { color: white(STAR, 0.7), size: 0.8 * w, height: 14, life: big ? 0.8 : 0.5 });
  P(dim, "impact", up(g, 0.9), { color: white(STAR, 0.4), size: 2.4 * w, life: 0.2 });
  P(dim, "star", up(g, 1.0), { color: STAR, count: big ? 18 : 10, spread: 1.5 * w, speed: 3 });
  shock(dim, g, GOLD, big ? 6.5 : 3.0, { debris: big ? 18 : 8 });
  sound(dim, "astro.beam_fire", g, big ? 0.6 : 0.85, 1.2);
  sound(dim, big ? "astro.explosion_big" : "astro.explosion", g, 0.9, 1.1);
  shake(dim, g, big ? 28 : 16, big ? 0.8 : 0.35, big ? 0.6 : 0.3);
  const R = big ? 6.5 : 2.9;
  for (const e of ctx.foes(R, up(g, 1))) {
    if (!ctx.once(e, 1, big ? "big" : "pillar")) continue;
    hit(ctx, e, base, { color: STAR, up: big ? 0.8 : 0.55, kb: big ? 1.0 : 0.35, dir: dirTo(g, e.location),
                        power: big ? 2.4 : 1.9, crit: big, sound: "astro.hit_heavy" });
  }
}

register(KEY, {
  // =========================================================================
  //  惑星技「硫酸雲 アシッド・ヴェール」
  //  杖を肩の後ろへ引き（0〜5）、星の頭に黄色い雲を集めて、硫酸雲の弾を放つ（6）。
  //  弾は少し弧を描いて飛び、最初の敵か地面で弾けて 4 秒残る雲になる（毒 II・鈍化・1.2/0.5 秒）。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "venus.acid_cast");
    sound(dim, "astro.gust", p.location, 1.3, 0.6);
    sound(dim, "astro.liquid", p.location, 0.7, 0.7);
    ctx.every(0, 3, 2, (i) => {
      const h = staffHead(p, ctx.liveDir(), -0.4, 0.6, 2.3);
      P(dim, "converge", h, { color: SULFUR, count: 10, spread: 1.6, life: 0.3, size: 0.7 });
      P(dim, "glow", h, { color: ACID, size: 0.6 + i * 0.3, life: 0.15 });
      acidPuff(dim, h, 0.3 + i * 0.12, 1, 0.5, 0.2);
      if (i === 2) P(dim, "orbit", h, { color: CLOUD, count: 8, spread: 0.9, life: 0.4 });
    });
    ctx.at(6, () => {
      const v = ctx.liveView();
      const f = ctx.liveDir();
      const dir = norm({ x: v.x, y: Math.max(-0.35, Math.min(0.6, v.y)) + 0.1, z: v.z });
      const from = add(up(ctx.loc(), 1.5), f, 1.1);
      sound(dim, "astro.swing", p.location, 1.2, 0.8);
      sound(dim, "astro.splash", p.location, 1.4, 0.6);
      sound(dim, "astro.wind", p.location, 1.5, 0.5);
      P(dim, "ring", from, { color: SULFUR, size: 1.2, life: 0.25 });
      P(dim, "flare", from, { color: white(SULFUR, 0.4), size: 0.9, life: 0.2 });
      acidPuff(dim, from, 0.5, 3, 0.8, 0.4);
      projectile(ctx, from, dir, {
        speed: 0.85, range: 22, radius: 0.9, gravity: 0.03, life: 60,
        damage: 7, hitOpts: { color: ACID, kb: 0.4, up: 0.15, sound: "astro.splash" },
        trail(d, pos, prev, age) {
          P(d, "glow", pos, { color: ACID, size: 1.1, life: 0.12 });
          P(d, "plasma", pos, { color: SULFUR, size: 0.55, life: 0.15, count: 2 });
          if (age % 2 === 0) acidPuff(d, pos, 0.45, 1, 0.9, 0.2);
          if (age % 3 === 0) P(d, "droplet", pos, { color: ACID, count: 3, speed: 1.5, size: 0.8 });
          if (age % 6 === 0) sound(d, "astro.liquid", pos, 1.6, 0.35);
        },
        onEnd(pos, reason) {
          if (reason === "owner" || reason === "stopped") return;
          acidBloom(ctx, pos);
        },
      });
    });
    return 14;
  },

  // =========================================================================
  //  機動技「逆行旋 レトログレード」
  //  金星の自転と同じ逆回り（時計回り）に二回転しながら突進（0〜12）。回る杖と雲の輪に触れた敵を掴んで
  //  背後へ投げ飛ばす。最後に杖で後ろを薙ぎ払い（14）、残った敵もまとめて後ろへ。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    body(p, "venus.retrograde");
    sound(dim, "astro.boost", p.location, 0.9, 1.0);
    sound(dim, "astro.ring_spin", p.location, 0.8, 1.0);
    sound(dim, "astro.gust", p.location, 1.1, 0.8);
    effect(p, "resistance", 16, 2);
    P(dim, "vortex", ctx.loc(), { color: SULFUR, rate: 60, life: 0.7, spread: 1.3, height: 2.4, spin: -540 });
    ctx.every(0, 5, 3, () => lunge(ctx, f, 0.95, 0.05));
    ctx.every(0, 13, 1, (i) => {
      const c0 = ctx.chest();
      const yaw = yawDeg(f) - i * 55;
      // 回る杖の星（体の周りを時計回り）と、薙ぐ光の弧
      const sd = yawRotate(f, i * 55 + 90);
      const tip = add(c0, sd, 1.7);
      P(dim, "slash_flat", up(c0, -0.15), { color: i % 2 ? GOLD : SULFUR, size: 0.75, rot: yaw, var: 1, life: 0.15 });
      P(dim, "glow", tip, { color: STAR, size: 0.8, life: 0.12 });
      P(dim, "trail", tip, { color: GOLD, size: 0.9, life: 0.3 });
      if (i % 2 === 0) P(dim, "orbit", c0, { color: CLOUD, count: 6, spread: 1.5, spin: -480, life: 0.4 });
      if (i % 3 === 0) afterimage(dim, p.location, mix(GOLD, SULFUR, 0.4), 0.3);
      if (i % 3 === 1) acidPuff(dim, add(c0, sd, -1.2), 0.5, 1, 0.7, 0.2);
      P(dim, "wind", c0, { color: CREAM, count: 2, dir: { x: -f.x, y: 0, z: -f.z }, speed: 6, spread: 0.9 });
      for (const e of ctx.foes(2.4, c0)) {
        if (!ctx.once(e, 1, "grab")) continue;
        const lf = ctx.liveDir();
        const back = { x: -lf.x, y: 0, z: -lf.z };
        hit(ctx, e, 8, { color: GOLD, kb: 1.9, up: 0.75, dir: back, power: 1.4, sound: "astro.hit_metal" });
        P(dim, "wind", chest(e), { color: CLOUD, count: 5, dir: back, speed: 8, spread: 0.5 });
        P(dim, "star", chest(e), { color: STAR, count: 5, spread: 0.4, life: 0.5 });
        sound(dim, "astro.gust", chest(e), 1.3, 0.7);
      }
    });
    ctx.at(14, () => {
      const lf = ctx.liveDir();
      const back = { x: -lf.x, y: 0, z: -lf.z };
      const c0 = ctx.chest();
      sound(dim, "astro.swing_heavy", c0, 0.9, 1.0);
      sound(dim, "astro.gust", c0, 0.8, 0.9);
      P(dim, "slash_big", add(c0, back, 1.2), { color: SULFUR, rot: 90, size: 0.8, life: 0.3, var: 1 });
      arc(dim, c0, back, 2.2, -80, 80, 0, GOLD, { size: 0.9, steps: 10, sparks: false });
      shock(dim, ctx.ground(ctx.loc()), SULFUR, 2.8, { dust: true });
      acidPuff(dim, add(c0, back, 1.6), 0.9, 3, 1.2, 0.9);
      for (const e of ctx.foes(3.4, c0)) {
        if (ctx.once(e, 1, "sweep")) hit(ctx, e, 4, { color: SULFUR, kb: 1.4, up: 0.5, dir: back, power: 1.3 });
      }
    });
    return 20;
  },

  // =========================================================================
  //  空中技「温室熱波 グリーンハウス」
  //  宙で止まって杖の星に熱を溜め（0〜5）、星を真下へ向けて急降下（6〜）。着地点に 465℃ の熱の天蓋（半球、
  //  半径 5m・3.5 秒）を張る: 着地の一撃 9・中の敵は焼かれ（1.6/0.5 秒・燃焼）弱体化。最後に天蓋が弾ける。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 7, 0.32);
    body(p, "venus.dive");
    sound(dim, "astro.beam_charge", p.location, 1.3, 0.7);
    sound(dim, "astro.corona", p.location, 1.2, 0.5);
    const below = ctx.ground(ctx.loc());
    P(dim, "circle", up(below, 0.06), { color: HEAT, size: 2.2, life: 1.2, spin: -120 });
    ctx.every(0, 3, 2, (i) => {
      const h = staffHead(p, ctx.liveDir(), 0.6, 0.35, 2.2);
      P(dim, "converge", h, { color: HEAT, count: 10, spread: 1.5, life: 0.3 });
      P(dim, "glow", h, { color: white(HEAT, 0.3), size: 0.7 + i * 0.3, life: 0.15 });
      P(dim, "ember", h, { color: HEAT, count: 4, spread: 0.4, speed: 1 });
    });
    ctx.at(6, () => {
      sound(dim, "astro.swing_heavy", p.location, 0.8, 1.0);
      sound(dim, "astro.thrust", p.location, 0.9, 0.9);
      plunge(ctx, (l) => greenhouse(ctx, l), 30, 2.6);
    });
    ctx.every(7, 8, 2, () => {
      let air = true;
      try { air = !p.isOnGround; } catch (_) { }
      if (!air) return;
      P(dim, "flame", ctx.chest(), { color: HEAT, count: 3, spread: 0.35, speed: 1.5 });
      P(dim, "ember", ctx.chest(), { color: GOLD, count: 3, spread: 0.4 });
    });
    return 30;
  },

  // =========================================================================
  //  必殺「明けの明星 モーニングスター」
  //  時を止め（ultOpen）、杖を天へ掲げる。杖から光が昇り、空に巨大な八芒星が灯って育つ（4〜）。
  //  標的の足元に予告 → 星光の柱が次々に落ちる（30〜）→ 明星そのものが落ちる大柱（54、会心）
  //  → 硫酸雲が空を覆い、硫酸の雨が 3 秒降り注ぐ（62〜122、毒と鈍化）。雨が上がると最後に星が瞬く。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 104, 16);
    const centre = ctx.ground(ctx.loc());
    const f = ctx.f;
    const S = { x: centre.x + f.x * 3, y: centre.y + 13, z: centre.z + f.z * 3 };
    ctx.at(3, () => body(p, "venus.star_call"));
    sound(dim, "astro.beam_charge", centre, 0.7, 1.2);
    ctx.at(8, () => sound(dim, "astro.flare", S, 0.8, 1.4));
    ctx.at(21, () => sound(dim, "astro.supernova", S, 1.1, 1.2));     // 1.66 秒後（54）に弾ける
    // 杖から天へ昇る光
    ctx.every(4, 6, 4, (i) => {
      const h = staffHead(p, ctx.liveDir(), 0.8, 0.4, 2.9);
      beam(dim, h, S, STAR, { size: 0.25 + i * 0.05, life: 0.25, ends: false });
      P(dim, "converge", S, { color: STAR, count: 14, spread: 3 + i * 0.5, life: 0.4 });
    });
    // 空の明星（育ちながらゆっくり回る八芒星）
    ctx.every(6, 18, 3, (i) => {
      const s = Math.min(6.5, 1.5 + i * 0.55);
      eightStar(dim, S, f, s, STAR, 0.22, i * 5);
      if (i % 2 === 0) P(dim, "lens", S, { color: white(STAR, 0.4), size: s * 0.32, life: 0.3 });
      if (i % 3 === 0) P(dim, "star", S, { color: white(STAR, 0.5), count: 6, spread: s * 0.5, life: 0.8 });
    });
    ctx.at(16, () => {
      P(dim, "circle_v", S, { color: GOLD, size: 3.0, life: 2.4, dir: { x: -f.x, y: 0, z: -f.z }, spin: 40 });
      P(dim, "ring", S, { color: STAR, size: 4, life: 0.5 });
      emblem(dim, up(centre, 0.06), KEY, { size: 4.5, life: 4.5, spin: 18, color: GOLD });
    });
    // 星光の柱（最大 6 本。標的が少なければ周りへ）
    ctx.at(22, () => {
      const spots = ctx.foes(16, up(centre, 1)).slice(0, 6).map((e) => onGround(dim, e.location));
      for (let k = spots.length; k < 4; k++) {
        spots.push(onGround(dim, add(centre, yawRotate(f, k * 90 + 45), 4.5)));
      }
      spots.forEach((g, k) => {
        ctx.at(k * 4, () => P(dim, "warning", up(g, 0.06), { color: [1, 0.85, 0.4], size: 2.4, life: 0.45 }));
        ctx.at(8 + k * 4, () => starPillar(ctx, S, g, 8));
      });
    });
    ctx.at(28, () => body(p, "venus.star_fall"));
    // 明星そのものが落ちる大柱
    ctx.at(48, () => {
      const tgt = ctx.foes(14, up(centre, 1))[0];
      const g = tgt ? onGround(dim, tgt.location) : onGround(dim, add(centre, f, 4));
      ctx.at(0, () => P(dim, "warning", up(g, 0.06), { color: [1, 0.6, 0.3], size: 5.5, life: 0.35 }));
      ctx.at(6, () => {
        starPillar(ctx, S, g, 12, true);
        eightStar(dim, up(g, 1.5), f, 4, STAR, 0.4);
        P(dim, "lens", up(g, 2), { color: white(STAR, 0.5), size: 2.6, life: 0.6 });
        flash(dim, g, 30, white(STAR, 0.5), 0.08, 0.5);
      });
    });
    // 硫酸の雨
    ctx.at(60, () => {
      body(p, "venus.rain");
      sound(dim, "astro.gust", centre, 0.6, 1.2);
      sound(dim, "astro.water_wave", centre, 0.6, 0.9);
      P(dim, "cloud", up(centre, 7.5), { color: RAIN_CLOUD, count: 8, spread: 7, size: 2.6, life: 3.5, dir: { x: 0, y: -0.05, z: 0 } });
    });
    ctx.at(62, () => {
      const R = 9;
      zone(ctx, centre, {
        radius: R, ticks: 60, every: 8, damage: 1.0, height: 5,
        hit: { color: ACID, nova: 1, xp: 1 },
        effects: [["poison", 60, 1], ["slowness", 30, 1]],
        visualEvery: 2,
        visual(d, c, age) {
          const n = fxScale() >= 1 ? 3 : 2;
          for (let k = 0; k < n; k++) {
            const a = rand(0, Math.PI * 2), rr = Math.sqrt(Math.random()) * R;
            P(d, "droplet", { x: c.x + Math.cos(a) * rr, y: c.y + 6.5, z: c.z + Math.sin(a) * rr },
              { color: ACID, count: 4, spread: 1.5, speed: 1.5, grav: -24, life: 0.55, size: 1.1 });
          }
          const a2 = rand(0, Math.PI * 2), r2 = Math.sqrt(Math.random()) * R;
          P(d, "splash", { x: c.x + Math.cos(a2) * r2, y: c.y + 0.1, z: c.z + Math.sin(a2) * r2 }, { color: ACID, count: 1, spread: 0.3 });
          if (age % 10 === 0) P(d, "cloud", up(c, 7.2), { color: RAIN_CLOUD, count: 4, spread: R * 0.75, size: 2.4, life: 2.2 });
          if (age % 6 === 0) P(d, "bubble", up(c, 0.2), { color: ACID, count: 5, spread: R * 0.6, speed: 0.5 });
          if (age % 12 === 0) ring(d, "dot", c, R, 32, { color: SULFUR, size: 0.9, life: 0.5 }, 0.15);
          if (age % 6 === 0) sound(d, "astro.liquid", c, rand(1.1, 1.5), 0.5);
        },
        onPulse(foes) { for (const e of foes.slice(0, 6)) corrode(dim, chest(e), 0.7); },
        onEnd(z) {
          // 雨が上がる: 雲が晴れ、明けの明星が最後に瞬く
          const at = up(z.center, 6);
          eightStar(dim, at, f, 2.4, STAR, 0.5, 22.5);
          P(dim, "lens", at, { color: white(STAR, 0.5), size: 1.2, life: 0.8 });
          P(dim, "star", up(z.center, 2), { color: STAR, count: 16, spread: 4, life: 1.2 });
          sound(dim, "astro.flare", at, 1.6, 0.8);
        },
      });
    });
    return 96;
  },

  // =========================================================================
  //  三段目「星屑の花」: ピルエットの間、星が足元に円を描き（0〜8）、差し出した瞬間（10）に八枚の花弁の
  //  星の花が咲いて周り 3.4m を灼く（5・燃焼）
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    sound(dim, "astro.ring_spin", p.location, 1.4, 0.7);
    sound(dim, "astro.wind", p.location, 1.5, 0.5);
    ctx.every(0, 5, 2, (i) => {
      const c0 = ctx.chest();
      const d = yawRotate(ctx.f, -i * 72 - 90);
      P(dim, "slash_flat", up(c0, -0.1), { color: i % 2 ? GOLD : ROSE, rot: yawDeg(d), size: 0.7, life: 0.2 });
      P(dim, "star", add(c0, d, 1.5), { color: STAR, count: 3, spread: 0.2, life: 0.6 });
    });
    ctx.at(10, () => {
      const g = ctx.ground(ctx.loc());
      for (let k = 0; k < 8; k++) {
        const d = yawRotate(EAST, k * 45 + 22.5);
        P(dim, "slash_flat", add(up(g, 0.25), d, 1.5), { color: k % 2 ? ROSE : GOLD, rot: yawDeg(d), size: 0.55, life: 0.45 });
      }
      P(dim, "ring_flat", up(g, 0.1), { color: GOLD, size: 1.6, life: 0.5 });
      ring(dim, "star", g, 2.6, 16, { color: STAR, size: 1.2, life: 0.8, speed: 1.5 }, 0.4);
      P(dim, "flare", up(g, 1.0), { color: white(ROSE, 0.4), size: 1.2, life: 0.25 });
      P(dim, "ember", up(g, 0.5), { color: GOLD, count: 10, spread: 1.8, speed: 1.5 });
      eightStar(dim, up(g, 1.2), ctx.liveDir(), 1.2, STAR, 0.3);
      sound(dim, "astro.flare", g, 1.3, 0.8);
      sound(dim, "astro.swing_heavy", g, 1.2, 0.8);
      for (const e of ctx.foes(3.4, up(g, 1))) {
        hit(ctx, e, 5, { color: ROSE, kb: 0.8, up: 0.35, dir: dirTo(g, e.location), power: 1.3 });
        try { e.setOnFire?.(2, true); } catch (_) { }
      }
    });
    return 12;
  },

  // =========================================================================
  //  変身の締め: 黄色い雲が足元で渦を巻き（0〜7）、外へ吹き払われて晴れ（8）、頭上に明星が灯る（10〜）
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    sound(dim, "astro.wind", g, 0.9, 1.0);
    sound(dim, "astro.gust", g, 0.8, 0.8);
    P(dim, "vortex", g, { color: CLOUD, rate: 70, life: 0.45, spread: 1.6, height: 3.0, spin: 540 });
    ctx.every(0, 4, 2, (i) => {
      for (let k = 0; k < 5; k++) {
        const a = (k * 72 + i * 40) * Math.PI / 180;
        const rr = 2.0 - i * 0.25;
        const at = { x: g.x + Math.cos(a) * rr, y: g.y + 0.6 + i * 0.3, z: g.z + Math.sin(a) * rr };
        P(dim, "cloud", at, { color: CLOUD, count: 1, size: 1.0, life: 0.7, dir: { x: -Math.sin(a) * 2, y: 0.3, z: Math.cos(a) * 2 } });
      }
    });
    ctx.at(8, () => {
      sound(dim, "astro.gust", g, 1.2, 1.0);
      P(dim, "ring_flat", up(g, 0.08), { color: GOLD, size: 2.2, life: 0.6 });
      ring(dim, "glow", g, 1.2, 24, { color: CREAM, size: 0.8, life: 0.5, speed: 6 }, 1.0);
      P(dim, "wind", up(g, 1), { color: CREAM, count: 8, spread: 1.2, speed: 7 });
      P(dim, "cloud", up(g, 1.2), { color: CLOUD, count: 6, spread: 2.5, size: 1.3, life: 1.0, dir: { x: 0, y: 0.6, z: 0 } });
    });
    ctx.at(10, () => {
      const S = up(ctx.loc(), 3.4);
      eightStar(dim, S, ctx.f, 1.6, STAR, 0.6);
      P(dim, "lens", S, { color: STAR, size: 0.8, life: 0.8 });
      P(dim, "star", S, { color: white(STAR, 0.4), count: 8, spread: 0.8, life: 1.0 });
      emblem(dim, up(g, 0.05), KEY, { size: 1.6, life: 1.8 });
      sound(dim, "astro.flare", S, 1.4, 0.9);
    });
    ctx.every(13, 3, 3, (i) => eightStar(dim, up(ctx.loc(), 3.4), ctx.f, 1.3 - i * 0.3, STAR, 0.25, 22.5 * (i + 1)));
    return 20;
  },

  // =========================================================================
  //  パッシブ「acid_thorns」: 殴ってきた相手（6m 以内）を硫酸で灼き（2）、毒 II で蝕む（同じ相手へは 0.6 秒に 1 回）。
  //  肩の雲のポッドが時々雲を吐き、通常攻撃の当たりには硫酸の飛沫。倒した相手は黄色い雲になって晴れる
  // =========================================================================
  passive: {
    tick(p, st) {
      if (st.n % 4 !== 0) return;
      const f = flatDir(p);
      const r = rightOf(f);
      const l = p.location;
      for (const s of [-1, 1]) {
        P(p.dimension, "cloud", { x: l.x + r.x * s * 0.62 - f.x * 0.1, y: l.y + 1.55, z: l.z + r.z * s * 0.62 - f.z * 0.1 },
          { color: CLOUD, count: 1, size: 0.25, life: 1.2, dir: { x: r.x * s * 0.2, y: 0.25, z: r.z * s * 0.2 } });
      }
    },
    onHurt(p, attacker, dmg) {
      if (!attacker || !valid(attacker) || !valid(p) || attacker.id === p.id) return;
      let at;
      try { at = chest(attacker); } catch (_) { return; }
      if (!finite(at) || dist(at, p.location) > 6) return;      // 「殴ってきた」相手（遠くの射手は除く）
      const k = `${p.id}|${attacker.id}`;
      if ((thornCd.get(k) ?? -99) > now() - 12) return;
      thornCd.set(k, now());
      if (thornCd.size > 64) for (const [kk, t] of thornCd) if (t < now() - 200) thornCd.delete(kk);
      const dim = p.dimension;
      effect(attacker, "poison", 80, 1);
      thornBusy = true;
      try { hit(p, attacker, 2, { color: ACID, nova: 0, xp: 0, power: 0.8, sound: "astro.liquid" }); }
      finally { thornBusy = false; }
      corrode(dim, at, 1.2);
      acidPuff(dim, at, 0.5, 2, 1.0, 0.3);
      P(dim, "hex", chest(p), { color: SULFUR, size: 0.9, life: 0.25 });
    },
    onHit(p, target, dmg, ctx) {
      if (ctx || thornBusy || !valid(target)) return;            // 通常攻撃だけ
      try { P(p.dimension, "droplet", chest(target), { color: ACID, count: 4, speed: 2.2, size: 0.8 }); } catch (_) { }
    },
    onKill(p, victim) {
      let at;
      try { at = chest(victim); } catch (_) { return; }
      if (!finite(at)) return;
      const dim = p.dimension;
      acidPuff(dim, at, 0.8, 4, 1.5, 0.6);
      P(dim, "star", up(at, 0.5), { color: STAR, count: 6, spread: 0.5, life: 0.8 });
      sound(dim, "astro.flare", at, 1.8, 0.4);
    },
  },
  meta: {},
});
