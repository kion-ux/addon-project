// ===========================================================================
//  火星 アレス（ARES）— 重装の軍神
//
//  真紅と錆色の厚い装甲・横向きの扇の鶏冠・角の生えた大肩当て・背中を回る二つの衛星（フォボスとダイモス）。
//  軍神斧 アレス・ブレイカー（kind axe）: 三日月の赤熱した刃・背のトゲ・柄に沿った杭打ち機。
//  色: 発光 = 溶岩の橙（ctx.c / LAVA）/ 赤熱（MAGMA）/ 白熱（HOT）/ 赤い砂（SAND・DUST）/
//      フォボスとダイモスの岩（ROCK_P / ROCK_D）/ 恐怖の暗い赤（FEAR）
//
//   惑星技  赤砂嵐 ダストストーム   溜めて吼え、赤い砂嵐を 3 秒まとう。周り 4m の敵を削り、目を潰して鈍らせる
//   機動技  軍神突撃 ウォーパス     肩から低く突っ込み、前の敵を捕まえてまとめて押し込み、最後に斧で打ち上げる
//   空中技  オリンポス・インパクト  一瞬浮いて斧を振りかぶり、真下へ落ちる。着地の衝撃のあと、
//                                   周りに六つの溶岩の噴火口が順に割れて噴き上がり、しばらく燃え続ける
//   必殺    恐怖と戦慄 フォボス＆ダイモス  背の二つの衛星を天へ放って巨大な隕石に変え、続けざまに落とす。
//                                   最後に雄叫び — 生き残った敵は恐怖ですくむ（弱体・鈍化・後ずさり）
//   三段目  杭打ち                  振り下ろした斧の杭打ち機が火を噴き、地面ごと吹き飛ばす
//   変身の締め 赤い砂嵐が渦巻いて吹き飛び、足元から溶岩の割れ目が六方へ走る
//   パッシブ war_cry                敵を倒すと雄叫びを上げ、周りの敵対的な相手が弱体・鈍化する（1.5 秒に 1 回）
// ===========================================================================
import {
  register, lunge, hover, plunge, ultOpen, zone, dirTo,
} from "../engine.js";
import {
  P, line, ring, arc, shock, emblem, flash, shake, sound, body, white, afterimage, status, fxScale,
} from "../fx.js";
import { hit, launch, hostilesNear } from "../combat.js";
import {
  add, up, lerp3, norm, sub, yawRotate, rightOf, chest, onGround, effect, valid, rand, now, hdist,
} from "../util.js";

const KEY = "mars";
const LAVA = [1.0, 0.45, 0.13];
const MAGMA = [1.0, 0.24, 0.06];
const HOT = [1.0, 0.86, 0.58];
const SAND = [0.82, 0.38, 0.2];
const DUST = [0.6, 0.3, 0.19];
const ROCK_P = [0.5, 0.39, 0.33];
const ROCK_D = [0.7, 0.6, 0.52];
const FEAR = [0.5, 0.04, 0.04];
const SMOKE = [0.2, 0.15, 0.14];
const DOWN = { x: 0, y: -1, z: 0 };

// ---------------------------------------------------------------------------
//  小さな道具（このファイルの中だけ）
// ---------------------------------------------------------------------------
/** loc の真下の地面（深く探す: 空中技・隕石用）。 */
function groundBelow(dim, loc, depth = 40) { return onGround(dim, loc, depth); }

/** 燃やす（API が無い・失敗しても無視）。 */
function ignite(e, seconds) {
  try { if (valid(e)) e.setOnFire?.(seconds, true); } catch (_) { }
}

/** a から b へ地面を走る溶岩のひび（折れ線 2 本・line_n の 1 回ずつ）。 */
function crack(dim, a, b, color, size = 0.5, life = 0.9) {
  const d = sub(b, a);
  const side = { x: -d.z, y: 0, z: d.x };
  const mid = add(lerp3(a, b, 0.5), side, rand(-0.18, 0.18));
  line(dim, "trail", up(a, 0.12), up(mid, 0.12), 0.3, { color, size, life });
  line(dim, "trail", up(mid, 0.12), up(b, 0.12), 0.3, { color: white(color, 0.2), size: size * 0.85, life });
}

/** 噴火口がひと吹きする（柱・炎・火の粉・溶岩の滴・岩・煙・小さな衝撃波）。 */
function erupt(dim, g, k = 1) {
  P(dim, "pillar", up(g, 0.05), { color: LAVA, size: 1.1 * k, height: 4.5 * k, life: 0.6 });
  P(dim, "flame", up(g, 0.3), { color: LAVA, count: 10, spread: 0.6 * k, speed: 4.5, size: 1.3 * k });
  P(dim, "ember", up(g, 0.5), { color: white(LAVA, 0.2), count: 14, spread: 0.5, speed: 6 });
  P(dim, "droplet", up(g, 0.6), { color: MAGMA, count: 8, speed: 6, spread: 0.3 });
  P(dim, "debris", up(g, 0.3), { color: SMOKE, count: 6, speed: 7 });
  P(dim, "shock_flat", up(g, 0.07), { color: MAGMA, size: 0.9 * k, life: 0.4 });
  if (fxScale() >= 1) P(dim, "smoke", up(g, 1.4), { color: SMOKE, count: 5, size: 1.5, spread: 0.4, speed: 1.6 });
}

/** 噴火口の燃え残り（設置範囲の見た目）。 */
function ventVisual(d, c, age) {
  P(d, "flame", up(c, 0.15), { color: LAVA, count: 2, spread: 0.45, speed: 1.6, size: 0.9 });
  if (age % 9 === 0) P(d, "ember", up(c, 0.3), { color: LAVA, count: 4, spread: 0.5, speed: 2 });
  if (age % 12 === 0) P(d, "smoke", up(c, 0.9), { color: SMOKE, count: 2, size: 1.0, speed: 0.8 });
  if (age % 15 === 0) P(d, "ring_flat", up(c, 0.06), { color: MAGMA, size: 0.7, life: 0.5 });
}

/** 背中の衛星の位置（side: -1 フォボス = 右肩の後ろ / 1 ダイモス = 左肩の後ろ）。 */
function moonOnBack(p, side) {
  let f = { x: 0, y: 0, z: 1 };
  try {
    const v = p.getViewDirection();
    const l = Math.hypot(v.x, v.z);
    if (l > 1e-4) f = { x: v.x / l, y: 0, z: v.z / l };
  } catch (_) { }
  const r = rightOf(f);
  const l = p.location;
  return { x: l.x - f.x * 0.75 + r.x * 0.6 * -side, y: l.y + 1.45, z: l.z - f.z * 0.75 + r.z * 0.6 * -side };
}

/** 岩の衛星（size が大きいほど巨大化）。rock は岩肌の色。 */
function moonFx(dim, q, size, rock, i = 0) {
  P(dim, "glow", q, { color: white(LAVA, 0.15), size: size * 1.25, life: 0.12 });
  P(dim, "glow", q, { color: rock, size: size * 0.95, life: 0.12 });
  if (size > 1.4 && i % 2 === 0) P(dim, "smoke", q, { color: SMOKE, count: 2, size: size * 0.6, spread: size * 0.2 });
  if (size > 2.5 && i % 3 === 0) P(dim, "ring", q, { color: MAGMA, size: size * 0.9, life: 0.12 });
}

/**
 * 衛星を巨大な隕石にして落とす（予告 → 落下 → 着弾 → 燃えるクレーター）。
 * 着弾までの tick を返す。g0 は落とす地点、R は爆発の半径、dmg は素のダメージ。
 */
function moonfall(ctx, g0, o) {
  const { dim } = ctx;
  const g = groundBelow(dim, g0, 16);
  const R = o.radius, rock = o.rock, sz = o.size;
  const delay = o.delay, fall = o.fall;
  const top = { x: g.x - ctx.f.x * 7, y: g.y + 22, z: g.z - ctx.f.z * 7 };
  const dir = norm(sub(g, top));
  for (let t = 0; t < delay + fall; t += 4) {
    ctx.at(t, () => P(dim, "warning", up(g, 0.06), { color: [1, 0.2, 0.1], size: R / 1.2, life: 0.25 }));
  }
  ctx.at(0, () => P(dim, "circle", up(g, 0.05), { color: LAVA, size: R / 1.1, life: (delay + fall) / 20 + 0.6, spin: 80 }));
  ctx.at(Math.max(0, delay + fall - 23), () => sound(dim, "astro.meteor", top, o.pitch ?? 0.8, 1.6));
  for (let i = 0; i <= fall; i++) {
    ctx.at(delay + i, () => {
      const q = lerp3(top, g, i / fall);
      P(dim, "meteor", q, { color: LAVA, dir, size: sz * 0.8, len: sz * 2.6, life: 0.12 });
      moonFx(dim, q, sz, rock, i);
      if (i % 2 === 0) P(dim, "ember", q, { color: LAVA, count: 5, speed: 3, spread: sz * 0.3 });
    });
  }
  ctx.at(delay + fall, () => {
    P(dim, "flare", up(g, 1.0), { color: white(LAVA, 0.5), size: R * 0.6, life: 0.3 });
    P(dim, "impact", up(g, 0.8), { color: white(MAGMA, 0.3), size: R * 0.8, life: 0.22 });
    P(dim, "lens", up(g, 1.4), { color: white(LAVA, 0.4), size: 1.4, life: 0.4 });
    shock(dim, g, LAVA, R, { debris: 20 });
    P(dim, "debris", up(g, 0.4), { color: rock, count: 12, speed: 9 });
    P(dim, "dust", up(g, 0.3), { color: SAND, count: 30, speed: 8, size: 1.8, spread: R * 0.3 });
    P(dim, "pillar", up(g, 0.05), { color: MAGMA, size: 2.2, height: 9, life: 0.6 });
    P(dim, "ember", up(g, 0.6), { color: LAVA, count: 24, speed: 8, spread: 1.2 });
    P(dim, "smoke", up(g, 1.0), { color: SMOKE, count: 10, size: 2.2, spread: R * 0.3, speed: 2 });
    P(dim, "circle", up(g, 0.06), { color: MAGMA, size: R / 1.3, life: 2.0, spin: -40 });
    sound(dim, "astro.explosion_big", g, o.pitch ?? 0.75, 1.6);
    sound(dim, "astro.impact_heavy", g, 0.6, 1.3);
    sound(dim, "astro.explosion", g, 0.9, 1.0);
    shake(dim, g, 30, 0.9, 0.6);
    flash(dim, g, 22, white(LAVA, 0.35), 0.05, 0.45);
    for (const e of ctx.foes(R + 0.5, up(g, 1.0))) {
      if (!ctx.once(e, 1, o.tag)) continue;
      hit(ctx, e, o.damage, { color: MAGMA, up: 0.85, kb: 1.0, dir: dirTo(g, e.location), power: 2.2, sound: "astro.hit_heavy" });
      ignite(e, 4);
    }
    // 燃えるクレーター
    zone(ctx, g, {
      radius: R * 0.6, ticks: 60, every: 10, delay: 8, damage: 2, height: 2,
      hit: { color: LAVA, power: 0.5 }, visualEvery: 3,
      visual(d, c, age) {
        ventVisual(d, c, age);
        if (age % 6 === 0) P(d, "flame", up(c, 0.2), { color: MAGMA, count: 3, spread: R * 0.4, speed: 1.4 });
      },
      onPulse(list) { for (const e of list) ignite(e, 2); },
    });
    try { o.onImpact?.(g); } catch (_) { }
  });
  return delay + fall;
}

/** 生き残りの中から二つ目の落下点を選ぶ（first から 2.5〜12m の、いちばん体力の残っている敵の足元）。 */
function secondTarget(ctx, first) {
  let best = null, bh = -1;
  for (const e of ctx.foes(12, up(first, 1))) {
    let h = 0;
    try { h = e.getComponent("minecraft:health")?.currentValue ?? 0; } catch (_) { }
    if (hdist(e.location, first) < 2.5 || h <= bh) continue;
    best = e; bh = h;
  }
  if (best) return { ...best.location };
  const f = ctx.liveDir();
  return { x: first.x + f.x * 4, y: first.y, z: first.z + f.z * 4 };
}

// ---------------------------------------------------------------------------
//  パッシブ: 軍神の雄叫び（敵を倒すと、周りの敵がすくむ）
// ---------------------------------------------------------------------------
const roarAt = new Map();   // playerId -> 最後に吼えた tick

function warCry(p) {
  const t = now();
  if ((roarAt.get(p.id) ?? -999) > t - 30) return;
  roarAt.set(p.id, t);
  const dim = p.dimension;
  const l = p.location;
  const c = chest(p);
  sound(dim, "astro.nemesis_roar", l, 1.35, 0.7);
  sound(dim, "astro.gust", l, 0.8, 0.5);
  P(dim, "ring", up(c, 0.4), { color: MAGMA, size: 2.4, life: 0.3 });
  P(dim, "shock_flat", up(l, 0.08), { color: MAGMA, size: 2.6, life: 0.45 });
  P(dim, "dust", up(l, 0.1), { color: SAND, count: 10, speed: 5, size: 1.2 });
  let n = 0;
  for (const e of hostilesNear(p, c, 8)) {
    effect(e, "weakness", 100, 1);
    effect(e, "slowness", 60, 1);
    if (n++ < 6) {
      P(dim, "aura", e.location, { color: FEAR, count: 5, spread: 0.45, life: 0.8 });
      P(dim, "smoke", up(e.location, 2.1), { color: FEAR, count: 2, size: 0.6, speed: 0.6 });
    }
  }
  status(p, n ? `§c軍神の雄叫び §7— ${n} 体がすくむ` : "§c軍神の雄叫び", 30);
}

register(KEY, {
  // =========================================================================
  //  惑星技「赤砂嵐 ダストストーム」
  //  身を縮めて砂を吸い寄せ（0〜5）、吼えると同時に赤い砂嵐が噴き上がる（6）。砂嵐は 3 秒間体に付いて回り、
  //  周り 4m の敵を 0.5 秒ごとに削って目を潰し（盲目）、足を鈍らせる。最後に外へ吹き散らす（66）。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "mars.storm_call");
    sound(dim, "astro.wind", p.location, 0.6, 0.9);
    sound(dim, "astro.gust", p.location, 0.7, 0.6);
    ctx.every(0, 3, 2, (i) => {
      const g = ctx.ground(ctx.loc());
      P(dim, "converge", ctx.chest(), { color: SAND, count: 10, spread: 3.5, life: 0.3, size: 0.9 });
      ring(dim, "dot", g, 3.8 - i * 1.1, 18, { color: SAND, size: 0.6, life: 0.25 }, 0.15);
      P(dim, "dust", up(g, 0.1), { color: DUST, count: 6, speed: 2, spread: 2.5 });
    });
    ctx.every(0, 6, 10, (i) => status(p, `§6赤砂嵐 §c${"▰".repeat(6 - i)}§8${"▱".repeat(i)}`, 12));
    ctx.at(6, () => {
      const g = ctx.ground(ctx.loc());
      sound(dim, "astro.nemesis_roar", g, 1.5, 0.55);
      sound(dim, "astro.gust", g, 0.8, 1.1);
      sound(dim, "astro.explosion", g, 1.4, 0.5);
      P(dim, "flare", ctx.chest(), { color: white(LAVA, 0.4), size: 1.4, life: 0.25 });
      P(dim, "shock_flat", up(g, 0.08), { color: SAND, size: 3.0, life: 0.5 });
      P(dim, "dust", up(g, 0.2), { color: SAND, count: 26, speed: 9, size: 1.6, spread: 1.0 });
      P(dim, "vortex", g, { color: SAND, rate: 80, life: 1.2, spread: 2.2, height: 4, spin: 600 });
      shake(dim, g, 10, 0.35, 0.3);
      for (const e of ctx.foes(4.6, up(g, 1))) {
        if (ctx.once(e, 1, "burst")) hit(ctx, e, 3, { color: SAND, kb: 0.3, up: 0.15, dir: dirTo(g, e.location) });
      }
    });
    zone(ctx, ctx.loc(), {
      radius: 4.2, ticks: 66, every: 10, delay: 10, follow: p, height: 3,
      damage: 2, hit: { color: SAND, power: 0.6, kb: 0.15 },
      effects: [["blindness", 50, 0], ["slowness", 24, 1]],
      visualEvery: 2,
      visual(d, c, age) {
        if (age < 6) return;
        const mid = up(c, 1.0);
        if (age % 20 === 6) P(d, "vortex", c, { color: SAND, rate: 70, life: 1.05, spread: 2.6, height: 3.6, spin: 560 });
        if (age % 6 === 0) ring(d, "dot", c, 3.9, 16, { color: white(SAND, 0.2), size: 0.55, life: 0.3 }, 0.6);
        const a = rand(0, Math.PI * 2), r = rand(1.6, 3.8);
        const q = { x: c.x + Math.cos(a) * r, y: c.y + 0.4, z: c.z + Math.sin(a) * r };
        P(d, "dust", q, { color: SAND, count: 4, speed: 3, size: 1.1, spread: 0.6 });
        if (age % 4 === 0) {
          const tan = { x: -Math.sin(a), y: 0.15, z: Math.cos(a) };
          P(d, "wind", q, { color: white(SAND, 0.15), dir: tan, count: 3, speed: 9, spread: 0.8 });
        }
        if (age % 8 === 2) P(d, "cloud", up(q, 0.6), { color: DUST, count: 2, life: 1.4, spread: 1.0, size: 0.8, dir: { x: -Math.sin(a) * 1.5, y: 0.2, z: Math.cos(a) * 1.5 } });
        if (age % 6 === 4) P(d, "ember", mid, { color: LAVA, count: 4, spread: 2.4, speed: 1.5 });
        if (age % 10 === 0) sound(d, "astro.wind", mid, 0.7 + rand(-0.05, 0.05), 0.55);
      },
      onPulse(list, z) {
        let n = 0;
        for (const e of list) {
          if (n++ >= 6) break;
          const q = chest(e);
          P(dim, "dust", q, { color: SAND, count: 5, speed: 3, size: 0.8 });
          P(dim, "spark", q, { color: LAVA, count: 3, speed: 4, size: 0.7 });
        }
        if (list.length) sound(dim, "astro.hit", z.center, 0.6, 0.4);
      },
      onEnd(z) {
        if (z.age < 60 || !ctx.alive()) return;            // 解除・死亡で消えた時は吹き散らさない
        const g = ctx.ground(z.center);
        P(dim, "shock_flat", up(g, 0.08), { color: SAND, size: 3.2, life: 0.5 });
        P(dim, "dust", up(g, 0.2), { color: SAND, count: 24, speed: 10, size: 1.6, spread: 1.6 });
        ring(dim, "dot", g, 2.0, 24, { color: SAND, size: 0.7, life: 0.5, speed: 6 }, 0.5);
        P(dim, "smoke", up(g, 1.2), { color: DUST, count: 6, size: 1.8, spread: 1.6, speed: 2 });
        sound(dim, "astro.gust", g, 1.0, 0.8);
        for (const e of ctx.foes(4.6, up(g, 1))) {
          if (ctx.once(e, 1, "scatter")) hit(ctx, e, 3, { color: SAND, kb: 1.1, up: 0.25, dir: dirTo(g, e.location) });
        }
      },
    });
    return 14;
  },

  // =========================================================================
  //  機動技「軍神突撃 ウォーパス」
  //  左肩を前に低く突っ込む（0〜13）。肩の前の敵を捕まえて一緒に押し込み、踏み込みごとに地面が鳴る。
  //  最後に斧を振り上げ、捕まえた敵と前の敵をまとめて打ち上げる（14）。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    const back = { x: -f.x, y: 0, z: -f.z };
    body(p, "mars.warpath");
    sound(dim, "astro.boost", p.location, 0.7, 1.0);
    sound(dim, "astro.thrust", p.location, 0.8, 0.8);
    sound(dim, "astro.sentinel_step", p.location, 0.7, 0.9);
    effect(p, "resistance", 20, 2);
    const pinned = new Map();
    ctx.every(0, 7, 2, () => lunge(ctx, f, 1.15, 0.02));
    ctx.every(0, 14, 1, (i) => {
      const c0 = ctx.chest();
      const front = ctx.local(1.3, 0, 1.0);
      P(dim, "wind", front, { color: SAND, dir: f, count: 3, speed: 10, spread: 0.6 });
      P(dim, "speedline", c0, { color: LAVA, count: 3, dir: back, speed: 14, spread: 0.8 });
      if (i % 2 === 0) {
        P(dim, "dust", ctx.ground(ctx.loc()), { color: DUST, count: 6, speed: 4, spread: 0.6 });
        P(dim, "glow", front, { color: white(MAGMA, 0.2), size: 1.6, life: 0.1 });
      }
      if (i % 3 === 0) afterimage(dim, p.location, MAGMA, 0.3);
      if (i % 4 === 0) {
        sound(dim, "astro.sentinel_step", p.location, 0.75, 0.8);
        P(dim, "flame", up(ctx.ground(ctx.loc()), 0.1), { color: LAVA, count: 4, spread: 0.4, speed: 1.2 });
      }
      for (const e of ctx.foes(2.3, front)) {
        if (pinned.has(e.id)) continue;
        pinned.set(e.id, e);
        if (ctx.once(e, 1, "ram")) {
          hit(ctx, e, 4, { color: LAVA, kb: 1.2, up: 0.05, dir: f, power: 1.3, sound: "astro.hit_metal" });
          P(dim, "impact", chest(e), { color: HOT, size: 1.2, life: 0.15 });
        }
      }
      for (const e of pinned.values()) if (valid(e)) launch(e, 0.04, 1.05, f);   // 肩の前に押し込む
    });
    ctx.at(14, () => {
      const g = ctx.ground(ctx.local(1.6, 0, 0));
      sound(dim, "astro.swing_heavy", p.location, 0.8, 1.0);
      sound(dim, "astro.explosion", g, 1.2, 0.8);
      arc(dim, ctx.chest(), f, 2.2, -70, 80, 90, LAVA, { size: 1.2, steps: 12 });
      P(dim, "flare", up(g, 1.2), { color: white(LAVA, 0.5), size: 1.4, life: 0.25 });
      P(dim, "pillar", add(g, f, 0.6), { color: LAVA, size: 1.2, height: 4.5, life: 0.4 });
      shock(dim, g, LAVA, 3, { debris: 10 });
      shake(dim, g, 12, 0.5, 0.35);
      const targets = new Map(pinned);
      for (const e of ctx.foes(3.2, ctx.local(1.5, 0, 1))) targets.set(e.id, e);
      for (const e of targets.values()) {
        if (!valid(e) || !ctx.once(e, 1, "launch")) continue;
        hit(ctx, e, 8, { color: MAGMA, up: 1.15, kb: 0.5, dir: f, power: 1.9, sound: "astro.hit_heavy" });
        ignite(e, 2);
      }
    });
    return 20;
  },

  // =========================================================================
  //  空中技「オリンポス・インパクト」
  //  一瞬浮いて斧を振りかぶり（0〜5。真下の着地点に予告の陣）、火球になって真下へ落ちる（6〜）。
  //  着地の衝撃（中央に大ダメージ）のあと、周りに溶岩のひびが走り、六つの噴火口が順に割れて噴き上がる。
  //  噴火口は 2.5 秒燃え続ける。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    body(p, "mars.olympus_dive");
    hover(ctx, 6, 0.45);
    sound(dim, "astro.thrust", p.location, 0.7, 0.9);
    sound(dim, "astro.beam_charge", p.location, 1.3, 0.5);
    const mark = groundBelow(dim, ctx.loc());
    ctx.at(0, () => {
      P(dim, "warning", up(mark, 0.06), { color: MAGMA, size: 3.2, life: 1.0 });
      P(dim, "circle", up(mark, 0.05), { color: LAVA, size: 3.0, life: 1.2, spin: 120 });
    });
    ctx.every(0, 6, 1, () => {
      const axe = ctx.local(0.2, 0.4, 2.6);
      P(dim, "converge", axe, { color: LAVA, count: 6, spread: 1.4, life: 0.25 });
      P(dim, "ember", axe, { color: HOT, count: 2, spread: 0.3, speed: 1 });
    });
    let landed = false;
    ctx.at(6, () => {
      sound(dim, "astro.boost", p.location, 0.6, 1.0);
      plunge(ctx, (loc) => { landed = true; olympusLand(ctx, loc); }, 34, 2.8);
    });
    ctx.every(7, 30, 1, (i) => {
      if (landed) return;
      const l = p.location;
      P(dim, "meteor", up(l, 1.0), { color: LAVA, dir: DOWN, size: 1.4, len: 3.5, life: 0.1 });
      if (i % 2 === 0) P(dim, "ember", up(l, 1.0), { color: LAVA, count: 3, speed: 2 });
    });
    return 30;
  },

  // =========================================================================
  //  必殺「恐怖と戦慄 フォボス＆ダイモス」
  //  時を止め（ultOpen）、左手を天へ掲げる。背中の二つの衛星が空へ昇りながら巨大になる（6〜24）。
  //  フォボスが狙った地点へ落ち（40）、生き残りのいちばん丈夫な敵へダイモスが続けて落ちる（56）。
  //  最後に雄叫び（64）— 生き残った敵は恐怖ですくむ（弱体・鈍化・後ずさり、暗い赤の気配）。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 100, 16);
    ctx.at(4, () => body(p, "mars.moon_call"));
    const T1 = ctx.aim(24);
    const f = ctx.f;
    // 衛星が背中から天へ昇る
    const sky = [-1, 1].map((s) => ({ x: T1.x - f.x * 7 + ctx.r.x * s * 3, y: T1.y + 22, z: T1.z - f.z * 7 + ctx.r.z * s * 3 }));
    ctx.at(6, () => {
      sound(dim, "astro.gravity", p.location, 0.6, 1.0);
      sound(dim, "astro.beam_charge", p.location, 0.7, 0.8);
    });
    ctx.at(14, () => sound(dim, "astro.nemesis_charge", p.location, 0.9, 0.9));
    ctx.every(6, 19, 1, (i) => {
      const k = i / 18;
      [[-1, ROCK_P, 3.2], [1, ROCK_D, 2.4]].forEach(([s, rock, big]) => {
        const from = moonOnBack(p, s);
        const q = lerp3(from, sky[(s + 1) / 2], k * k);
        moonFx(dim, q, 0.4 + k * big, rock, i);
        if (i % 2 === 0) P(dim, "trail", q, { color: LAVA, size: 0.8 + k * 1.6, life: 0.35 });
      });
    });
    ctx.every(25, 4, 3, () => {
      moonFx(dim, sky[0], 3.6, ROCK_P);
      moonFx(dim, sky[1], 2.6, ROCK_D);
    });
    // フォボス（大きく、狙った地点へ）
    ctx.at(20, () => moonfall(ctx, T1, { radius: 5, damage: 16, rock: ROCK_P, size: 3.6, delay: 10, fall: 10, tag: "phobos", pitch: 0.7 }));
    // ダイモス（小さく速く、生き残りへ）
    ctx.at(36, () => {
      const T2 = secondTarget(ctx, T1);
      moonfall(ctx, T2, { radius: 4, damage: 13, rock: ROCK_D, size: 2.6, delay: 12, fall: 8, tag: "deimos", pitch: 0.95 });
    });
    // 雄叫び — 生き残りは恐怖ですくむ
    ctx.at(62, () => body(p, "mars.war_roar"));
    ctx.at(64, () => {
      const g = ctx.ground(ctx.loc());
      sound(dim, "astro.nemesis_roar", g, 0.9, 1.3);
      sound(dim, "astro.explosion_big", g, 0.6, 0.8);
      sound(dim, "astro.gust", g, 0.6, 1.0);
      P(dim, "shock_flat", up(g, 0.08), { color: MAGMA, size: 6, life: 0.7 });
      P(dim, "ring", ctx.chest(), { color: MAGMA, size: 4, life: 0.4 });
      P(dim, "lens", ctx.chest(), { color: white(MAGMA, 0.3), size: 2.2, life: 0.5 });
      P(dim, "dust", up(g, 0.2), { color: SAND, count: 30, speed: 12, size: 1.8, spread: 1.4 });
      emblem(dim, up(g, 0.06), KEY, { size: 4, life: 2.0, spin: 30 });
      shake(dim, g, 26, 0.8, 0.6);
      flash(dim, g, 26, [0.55, 0.06, 0.04], 0.08, 0.5);
      let n = 0;
      for (const e of ctx.foes(16, up(g, 1))) {
        effect(e, "weakness", 140, 2);
        effect(e, "slowness", 100, 3);
        if (ctx.once(e, 1, "fear")) {
          hit(ctx, e, 4, { color: FEAR, kb: 0.9, up: 0.25, dir: dirTo(g, e.location), power: 1.2, sound: "astro.hit" });
        }
        if (n++ < 8) {
          P(dim, "aura", e.location, { color: FEAR, count: 6, spread: 0.5, life: 0.9 });
          P(dim, "smoke", up(e.location, 2.2), { color: FEAR, count: 3, size: 0.8 });
        }
      }
      status(p, n ? `§4恐怖と戦慄 §7— ${n} 体がすくむ` : "§4恐怖と戦慄", 40);
    });
    ctx.every(70, 4, 8, () => {
      let n = 0;
      for (const e of ctx.foes(16)) {
        if (n++ >= 8) break;
        P(dim, "aura", e.location, { color: FEAR, count: 3, spread: 0.4, life: 0.7 });
      }
    });
    return 84;
  },

  // =========================================================================
  //  三段目「杭打ち」: 振り下ろした斧（全身モーションの叩きつけ = 7 tick 目）の杭打ち機が火を噴き、
  //  地面ごと周りを吹き飛ばす
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    sound(dim, "astro.thrust", p.location, 0.7, 0.7);
    ctx.at(1, () => P(dim, "converge", ctx.local(1.2, 0, 1.6), { color: LAVA, count: 8, spread: 1.0, life: 0.25 }));
    ctx.at(6, () => {
      const g = ctx.ground(add(ctx.loc(), f, 1.9));
      P(dim, "thrust", up(g, 2.4), { color: HOT, dir: DOWN, len: 2.4, size: 1.2, life: 0.18 });
      P(dim, "flare", up(g, 0.4), { color: white(LAVA, 0.5), size: 1.2, life: 0.22 });
      P(dim, "impact", up(g, 0.5), { color: white(MAGMA, 0.3), size: 1.6, life: 0.18 });
      shock(dim, g, LAVA, 3.0, { debris: 10 });
      P(dim, "flame", up(g, 0.2), { color: LAVA, count: 8, spread: 0.6, speed: 3.5 });
      P(dim, "ember", up(g, 0.4), { color: LAVA, count: 12, speed: 6 });
      if (fxScale() >= 1) P(dim, "smoke", up(g, 0.8), { color: SMOKE, count: 4, size: 1.3, speed: 1.5 });
      for (let k = 0; k < 4; k++) crack(dim, g, add(g, yawRotate(f, -60 + k * 40), 2.4), MAGMA, 0.4, 0.7);
      sound(dim, "astro.explosion", g, 1.1, 0.9);
      sound(dim, "astro.hit_metal", g, 0.7, 0.9);
      sound(dim, "astro.impact_heavy", g, 1.0, 0.8);
      shake(dim, g, 10, 0.45, 0.3);
      for (const e of ctx.foes(3.2, up(g, 0.8))) {
        hit(ctx, e, 6, { color: LAVA, up: 0.75, kb: 0.6, dir: dirTo(g, e.location), power: 1.6, sound: "astro.hit_heavy" });
      }
    });
    return 10;
  },

  // =========================================================================
  //  変身の締め: 赤い砂嵐が足元で渦巻いて吹き飛び（0〜4）、溶岩の割れ目が六方へ走って先で炎が噴く（5〜15）
  // =========================================================================
  burst(ctx) {
    const { dim } = ctx;
    const g = ctx.ground(ctx.loc());
    sound(dim, "astro.wind", g, 0.7, 0.9);
    sound(dim, "astro.gust", g, 0.9, 0.7);
    P(dim, "vortex", g, { color: SAND, rate: 90, life: 0.6, spread: 1.8, height: 4, spin: 720 });
    P(dim, "cloud", up(g, 1.0), { color: DUST, count: 4, spread: 1.6, life: 1.0, size: 0.9 });
    P(dim, "dust", up(g, 0.2), { color: SAND, count: 12, speed: 3, spread: 1.2 });
    ctx.at(4, () => {
      sound(dim, "astro.gust", g, 0.7, 1.0);
      sound(dim, "astro.explosion", g, 1.5, 0.5);
      P(dim, "shock_flat", up(g, 0.08), { color: SAND, size: 2.6, life: 0.5 });
      P(dim, "dust", up(g, 0.2), { color: SAND, count: 24, speed: 10, size: 1.4, spread: 0.8 });
      ring(dim, "dot", g, 1.0, 24, { color: SAND, size: 0.7, life: 0.5, speed: 6 }, 0.4);
      P(dim, "flare", ctx.chest(), { color: white(LAVA, 0.5), size: 1.3, life: 0.3 });
      emblem(dim, up(g, 0.05), KEY, { size: 1.6, life: 1.8 });
    });
    const f = ctx.f;
    const ends = [];
    for (let k = 0; k < 6; k++) ends.push(add(g, yawRotate(f, k * 60 + 30), 3.6));
    ctx.every(5, 3, 3, (i) => {
      for (let k = 0; k < 6; k++) {
        const a = lerp3(g, ends[k], i / 3);
        const b = lerp3(g, ends[k], (i + 1) / 3);
        crack(dim, a, b, i === 2 ? LAVA : MAGMA, 0.45, 1.2);
      }
      sound(dim, "astro.impact_heavy", g, 1.3 + i * 0.1, 0.5);
    });
    ctx.at(14, () => {
      for (const q of ends) P(dim, "flame", up(q, 0.1), { color: LAVA, count: 5, spread: 0.3, speed: 3 });
      P(dim, "ember", up(g, 0.4), { color: LAVA, count: 16, speed: 4, spread: 2 });
      sound(dim, "astro.flare", g, 0.8, 0.7);
    });
    return 20;
  },

  // =========================================================================
  //  パッシブ「軍神の雄叫び」war_cry
  //  tick: 背の煙突から時々火の粉 / onKill: 雄叫びで周りの敵対的な相手が弱体・鈍化する
  // =========================================================================
  passive: {
    tick(p, st) {
      if (st.n % 4 !== 0) return;
      const dim = p.dimension;
      const side = st.n % 8 === 0 ? -1 : 1;
      const q = moonOnBack(p, side);
      P(dim, "ember", up(q, 0.25), { color: LAVA, count: 2, spread: 0.1, speed: 0.6 });
    },
    onKill(p, victim) {
      warCry(p);
    },
  },
  meta: {},
});

/** 空中技の着地: 衝撃 → ひび → 六つの噴火口が順に噴き上がり、燃え続ける。 */
function olympusLand(ctx, loc) {
  const { p, dim } = ctx;
  const g = ctx.ground(loc);
  body(p, "mars.olympus_land");
  P(dim, "flare", up(g, 1.0), { color: white(LAVA, 0.5), size: 2.0, life: 0.3 });
  P(dim, "impact", up(g, 0.8), { color: HOT, size: 3.2, life: 0.22 });
  P(dim, "lens", up(g, 1.2), { color: white(LAVA, 0.4), size: 1.4, life: 0.35 });
  shock(dim, g, LAVA, 4.2, { debris: 16 });
  P(dim, "dust", up(g, 0.3), { color: SAND, count: 24, speed: 7, size: 1.6, spread: 1.2 });
  emblem(dim, up(g, 0.06), KEY, { size: 2.4, life: 1.6, spin: 60 });
  sound(dim, "astro.explosion_big", g, 0.9, 1.3);
  sound(dim, "astro.impact_heavy", g, 0.7, 1.2);
  sound(dim, "astro.sentinel_slam", g, 0.8, 1.0);
  shake(dim, g, 18, 0.7, 0.45);
  for (const e of ctx.foes(3.6, up(g, 1))) {
    if (ctx.once(e, 1, "slam")) {
      hit(ctx, e, 8, { color: MAGMA, up: 0.55, kb: 0.7, dir: dirTo(g, e.location), power: 2.0, sound: "astro.hit_heavy" });
    }
  }
  const f = ctx.liveDir();
  for (let k = 0; k < 6; k++) {
    const q = onGround(dim, add(g, yawRotate(f, k * 60 + 30), 3.4), 6);
    ctx.at(2 + k * 2, () => {
      crack(dim, g, q, MAGMA, 0.5, 1.6);
      P(dim, "ember", up(q, 0.2), { color: LAVA, count: 4, speed: 1.5, spread: 0.3 });
      sound(dim, "astro.impact_heavy", q, 1.6, 0.5);
    });
    ctx.at(6 + k * 2, () => {
      erupt(dim, q, 1);
      sound(dim, "astro.explosion", q, 1.2 + k * 0.04, 0.7);
      if (k % 2 === 0) sound(dim, "astro.flare", q, 0.7, 0.6);
      for (const e of ctx.foes(1.9, up(q, 1))) {
        if (!ctx.once(e, 1, `vent${k}`)) continue;
        hit(ctx, e, 6, { color: LAVA, up: 0.95, kb: 0.2, dir: dirTo(g, e.location), power: 1.5 });
        ignite(e, 3);
      }
      zone(ctx, q, {
        radius: 1.4, ticks: 50, every: 10, delay: 10, damage: 2, height: 2,
        hit: { color: LAVA, power: 0.5 }, visualEvery: 3, visual: ventVisual,
        onPulse(list) { for (const e of list) ignite(e, 2); },
      });
    });
  }
  ctx.at(18, () => shake(dim, g, 14, 0.3, 0.4));
}
