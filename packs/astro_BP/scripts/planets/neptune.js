// ===========================================================================
//  海王星 トリトン（TRITON）— 深淵の騎士
//
//  紺碧と藍の装甲・白い波頭のヒレ・三叉の冠。武器は深淵三叉槍 トリトン（三叉槍）。
//  色: 発光 = 生物発光の水色（ctx.c = AQUA）/ 泡の白（FOAM = ctx.accent）/ 紺碧（AZURE）/
//      深淵の藍（ABYSS）/ 大暗斑の暗い渦（STORM）/ トリトンの窒素の氷（TRITON 薄紅・NITRO 白）
//
//   惑星技  超音速の風 スーパーソニック  体をひねって風を穂先へ集め（0〜7）、秒速 600m の風の刃を突き出す（8）。
//                                       前方 14m を貫く一閃と、遅れて追いつく衝撃波（ソニックブーム）の二段
//   機動技  大暗斑 ダークスポット        足元に暗い渦を開いて飛び込み（5）、8m 先の出口の渦から回りながら抜ける。
//                                       通り道の敵を斬り、残った入口の渦は 3 秒間敵を引き込み、最後に潰れて弾ける
//   空中技  トリトンの逆行              宙で止まり、槍を逆行する衛星に変えて真下へ投げる（8）。着弾点を中心に
//                                       窒素の間欠泉が六本噴き上がり（二度）、敵を打ち上げて凍えさせる
//   必殺    アビサル・テンペスト         時を止め、巨大な渦潮で敵を引きずり回し（6〜46）、超音速の嵐で巻き上げて
//                                       風の刃で刻む（32〜50）。四方から大津波が押し寄せ（50）、槍を突き立てて押し潰す（60）
//   三段目  波濤突き                    突きの先から水の槍が 5m 先まで伸びる
//   変身の締め 渦潮が足元から巻き上がり、波頭が輪になって砕ける
//   パッシブ tide                      水中か雨の中（空の下）では潮が満ち、与ダメージ +25%（当たった敵を潮の重さで鈍らせる）
// ===========================================================================
import {
  register, lunge, hover, warp, safeAhead, ultOpen, projectile, zone,
} from "../engine.js";
import {
  P, line, ring, beam, emblem, flash, shake, sound, body, white, mix, afterimage, status,
} from "../fx.js";
import {
  hit, enemiesNear, enemiesOnLine, launch,
} from "../combat.js";
import {
  add, up, sub, norm, dist, hdist, yawRotate, yawDeg, chest, dirTo, effect, onGround, blocked,
  valid, clamp, world,
} from "../util.js";

const KEY = "neptune";
const AQUA = [0.31, 0.89, 1.0];
const FOAM = [0.92, 0.96, 1.0];
const AZURE = [0.18, 0.46, 1.0];
const ABYSS = [0.06, 0.12, 0.36];
const STORM = [0.16, 0.3, 0.78];     // 暗い渦（加算の粒は暗い色だと消えるので、紺に寄せた青）
const TRITON = [1.0, 0.8, 0.88];     // トリトンの窒素の氷（薄紅）
const NITRO = [0.86, 0.92, 1.0];
const PLUME = [0.22, 0.24, 0.32];    // 間欠泉の暗い噴煙（半透明の粒）
const EAST = { x: 1, y: 0, z: 0 };
const DOWN = { x: 0, y: -1, z: 0 };
const UPV = { x: 0, y: 1, z: 0 };

// ---------------------------------------------------------------------------
//  小さな道具
// ---------------------------------------------------------------------------
/** a から dir へ最大 maxD 進んで、最初に固いブロックに当たる手前までの距離。 */
function clearRange(dim, a, dir, maxD) {
  for (let s = 0.5; s <= maxD; s += 0.5) {
    if (blocked(dim, add(a, dir, s))) return Math.max(0.5, s - 0.3);
  }
  return maxD;
}

/** 渦の向き（中心から見て時計回り = 逆行。少し内向き）。 */
function swirlDir(centre, at, inward = 0.6) {
  const r = dirTo(centre, at);
  return norm({ x: r.z * 0.8 - r.x * inward, y: 0, z: -r.x * 0.8 - r.z * inward });
}

/** 暗い渦の見た目（大暗斑）。c は地面、k は大きさの倍率。 */
function darkVortex(dim, c, k, age) {
  if (age % 10 === 0) {
    P(dim, "black_hole", up(c, 1.0), { color: STORM, size: 0.75 * k, life: 0.6, spin: -240 });
    P(dim, "lens", up(c, 1.0), { color: STORM, size: 0.5 * k, life: 0.5 });
    P(dim, "vortex", c, { color: mix(STORM, AQUA, 0.35), rate: 60, life: 0.5, spread: 1.4 * k, height: 2.6, spin: -540 });
  }
  if (age % 4 === 0) {
    ring(dim, "dot", c, (2.6 - (age % 16) * 0.12) * k, 18, { color: age % 8 ? AQUA : STORM, size: 0.7, life: 0.3 }, 0.12);
  }
  if (age % 6 === 2) {
    P(dim, "converge", up(c, 1.0), { color: mix(AQUA, STORM, 0.4), count: 10, spread: 3.2 * k, life: 0.45, size: 0.8 });
    P(dim, "bubble", up(c, 0.4), { color: white(AQUA, 0.3), count: 4, spread: 1.4 * k, speed: 0.6 });
  }
}

/** 窒素の間欠泉（トリトン）: 白い柱・暗い噴煙・氷の粒・根元のしぶき。big で二度目の大きな噴出。 */
function geyserFx(dim, g, big) {
  const h = big ? 9 : 6.5;
  P(dim, "pillar", up(g, 0.05), { color: NITRO, size: big ? 1.2 : 0.9, height: h, life: 0.7 });
  P(dim, "splash", up(g, 0.05), { color: white(TRITON, 0.4), size: big ? 1.8 : 1.3, life: 0.45 });
  P(dim, "speedline", up(g, 0.8), { color: FOAM, count: 6, dir: UPV, speed: 20, spread: 0.4 });
  P(dim, "ice", up(g, 1.2), { color: TRITON, count: big ? 8 : 5, speed: 7, spread: 0.3 });
  P(dim, "smoke", up(g, h * 0.55), { color: PLUME, count: big ? 6 : 4, speed: 2.5, size: 1.4, spread: 0.6 });
  if (big) P(dim, "cloud", up(g, h), { color: white(NITRO, 0.2), count: 2, spread: 1.0, life: 1.6, dir: { x: 0.1, y: 0.4, z: 0 } });
}

// ---------------------------------------------------------------------------
//  パッシブ「潮」: 水中か雨の中（空の下）で潮が満ちる
// ---------------------------------------------------------------------------
const TIDE = new Map();       // playerId -> { on }
const RAIN = new Map();       // dimensionId -> 雨か（weatherChange で覚える。getWeather が無い版の代わり）
try {
  world.afterEvents?.weatherChange?.subscribe?.((ev) => {
    try {
      const id = typeof ev.dimension === "string" ? ev.dimension : ev.dimension?.id;
      const w = ev.newWeather ?? (ev.raining || ev.lightning ? "Rain" : "Clear");
      if (id) RAIN.set(id, String(w) !== "Clear");
    } catch (_) { }
  });
} catch (_) { }

function raining(dim) {
  try {
    if (typeof dim.getWeather === "function") {
      const w = dim.getWeather();
      if (w !== undefined) return String(w) !== "Clear";
    }
  } catch (_) { }
  return RAIN.get(dim.id) ?? false;
}

function underSky(dim, loc) {
  try {
    if (typeof dim.getTopmostBlock === "function") {
      const b = dim.getTopmostBlock({ x: loc.x, z: loc.z });
      if (b) return b.location.y < loc.y + 1.5;
    }
  } catch (_) { }
  for (let dy = 2; dy <= 24; dy += 2) if (blocked(dim, { x: loc.x, y: loc.y + dy, z: loc.z })) return false;
  return true;
}

function tideNow(p) {
  try {
    if (p.isInWater) return true;
    const dim = p.dimension;
    return raining(dim) && underSky(dim, p.location);
  } catch (_) { return false; }
}

register(KEY, {
  // =========================================================================
  //  惑星技「超音速の風 スーパーソニック」
  //  体をひねって風を穂先へ集め（0〜7。足元から風が吸い込まれ、穂先に照準の陣）、8 tick 目に
  //  秒速 600m の風の刃を突き出す: 白い芯の一閃が 14m（壁の手前まで）を貫き、マッハの輪が連なる。
  //  3 tick 遅れてソニックブームが追いつき、もう一度打つ。通り道には凝結の滴と風の筋が残る。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "neptune.sonic_thrust");
    sound(dim, "astro.wind", p.location, 0.6, 0.8);
    sound(dim, "astro.beam_charge", p.location, 1.5, 0.6);
    ctx.every(0, 4, 2, (i) => {
      const tip = ctx.local(1.5, 0.35, 1.25);
      P(dim, "converge", tip, { color: white(AQUA, 0.3), count: 12, spread: 2.4 - i * 0.3, life: 0.3, size: 0.8 });
      P(dim, "orbit", tip, { color: FOAM, count: 6, spread: 0.9 - i * 0.1, life: 0.3, spin: -720 });
      P(dim, "wind", ctx.local(-0.6, 0, 0.4), { color: FOAM, count: 3, spread: 1.0, speed: 5, dir: ctx.f });
      if (i === 0) P(dim, "circle_v", tip, { color: AQUA, size: 0.45, life: 0.5, dir: ctx.liveView(), spin: 360 });
      status(p, `§b超音速の風 §f${"▰".repeat(i + 1)}§8${"▱".repeat(3 - i)}`, 3);
    });
    ctx.at(4, () => sound(dim, "astro.gust", p.location, 1.5, 0.5));
    ctx.at(8, () => {
      // 視線の上下は ±27° まで（真上・真下を向いていても水平の向きは開始時の前方で補う）
      const v = ctx.liveView();
      const h = Math.hypot(v.x, v.z);
      const hx = h > 0.08 ? v.x / h : ctx.f.x, hz = h > 0.08 ? v.z / h : ctx.f.z;
      const d = norm({ x: hx, y: clamp(v.y / Math.max(h, 0.08), -0.5, 0.5), z: hz });
      const flat = norm({ x: d.x, y: 0, z: d.z });
      const from = add(up(ctx.loc(), 1.15), d, 0.9);
      const L = clearRange(dim, from, d, 14);
      const to = add(from, d, L);
      // 放つ: 突きの閃光・白い芯の一閃・幅の広い一瞬の帯・マッハの輪・速度線
      P(dim, "thrust", from, { color: white(AQUA, 0.5), dir: d, len: Math.min(5, L), size: 1.7, life: 0.2 });
      beam(dim, from, to, AQUA, { size: 0.75, life: 0.32, core: FOAM });
      P(dim, "beam", from, { color: white(FOAM, 0.2), dir: d, len: L, size: 1.7, life: 0.1 });
      P(dim, "ring", from, { color: FOAM, size: 1.5, life: 0.25 });
      P(dim, "speedline", from, { color: FOAM, dir: d, count: 12, speed: 32, spread: 0.6 });
      line(dim, "glow", from, to, 0.6, { color: AQUA, size: 0.5, life: 0.35, spread: 0.3 });
      for (const k of [1.6, 4.2, 7.4, 11.0]) {
        if (k >= L) break;
        ctx.at(Math.floor(k / 4), () => P(dim, "circle_v", add(from, d, k), {
          color: k > 5 ? FOAM : AQUA, dir: d, size: 0.32 + k * 0.05, life: 0.35, spin: 540,
        }));
      }
      sound(dim, "astro.swing_heavy", p.location, 0.8, 1.0);
      sound(dim, "astro.beam_fire", p.location, 1.6, 0.9);
      sound(dim, "astro.gust", p.location, 1.0, 1.1);
      shake(dim, p.location, 10, 0.35, 0.25);
      for (const e of enemiesOnLine(ctx, from, to, 1.4)) {
        if (!ctx.once(e, 1, "blade")) continue;
        hit(ctx, e, 9, { color: AQUA, kb: 1.3, up: 0.25, dir: flat, power: 1.5, sound: "astro.hit_heavy" });
        P(dim, "slash", chest(e), { color: FOAM, size: 0.9, rot: yawDeg(flat) + 90, life: 0.2 });
      }
      // 遅れて追いつくソニックブーム
      ctx.at(3, () => {
        sound(dim, "astro.explosion", add(from, d, L * 0.5), 1.7, 0.7);
        sound(dim, "astro.wind", add(from, d, L * 0.5), 1.4, 0.8);
        for (const k of [0.35, 0.7, 1.0]) {
          const q = add(from, d, L * k);
          P(dim, "ring", q, { color: white(AQUA, 0.4), size: 1.6, life: 0.3 });
          const g = onGround(dim, q, 4);
          if (q.y - g.y < 2.6) P(dim, "dust", up(g, 0.1), { count: 8, speed: 4, size: 1.0, spread: 0.6 });
        }
        for (const e of enemiesOnLine(ctx, from, to, 2.4)) {
          if (ctx.once(e, 1, "boom")) hit(ctx, e, 3, { color: FOAM, up: 0.35, kb: 0.4, dir: flat, power: 1.2, sound: "astro.splash" });
        }
      });
      // 余韻: 凝結の滴と風の筋が通り道に残る
      ctx.every(2, 4, 2, (i) => {
        const q = add(from, d, L * (0.2 + i * 0.22));
        P(dim, "droplet", q, { color: white(AQUA, 0.3), count: 4, spread: 0.6, speed: 1.2 });
        P(dim, "wind", q, { color: FOAM, count: 2, spread: 0.6, speed: 3, dir: d });
      });
    });
    return 18;
  },

  // =========================================================================
  //  機動技「大暗斑 ダークスポット」
  //  足元の前に暗い渦（大暗斑）を開き（0〜4）、そこへ飛び込んで（5）8m 先の出口の渦から抜ける。
  //  通り道の敵を斬って入口へ引き戻し、出口では回転斬り（9）。残った入口の渦は 3 秒間敵を引き込み、
  //  時々削り、最後に潰れて弾ける。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    body(p, "neptune.vortex_dive");
    effect(p, "resistance", 14, 3);
    const gate = ctx.ground(add(ctx.loc(), f, 1.2));
    sound(dim, "astro.gravity", p.location, 0.55, 1.0);
    sound(dim, "astro.water_wave", p.location, 0.7, 0.8);
    lunge(ctx, f, 0.45, 0.05);
    ctx.every(0, 5, 1, (i) => {
      darkVortex(dim, gate, 0.6 + i * 0.12, i * 2);
      if (i === 0) P(dim, "ring_flat", up(gate, 0.08), { color: STORM, size: 1.4, life: 0.4 });
    });
    ctx.at(5, () => {
      const from = ctx.loc();
      afterimage(dim, from, STORM, 0.45);
      P(dim, "splash", up(gate, 0.05), { color: mix(AQUA, STORM, 0.4), size: 1.6, life: 0.4 });
      P(dim, "bubble", up(gate, 0.6), { color: white(AQUA, 0.3), count: 10, spread: 0.9, speed: 1.2 });
      sound(dim, "astro.splash", from, 0.7, 1.0);
      const dest = safeAhead(dim, from, f, 8);
      const moved = dist(dest, from) > 1.5 && warp(ctx, dest, add(dest, f, 4));
      const out = moved ? dest : from;
      // 通り道: 闇の筋と、斬られて入口の渦へ引き戻される敵
      line(dim, "trail", up(from, 1.0), up(out, 1.0), 0.5, { color: STORM, size: 0.8, life: 0.3, spread: 0.3 });
      P(dim, "speedline", up(out, 1.0), { color: AQUA, dir: f, count: 8, speed: 20, spread: 0.7 });
      for (const e of enemiesOnLine(ctx, up(from, 1.0), up(out, 1.0), 1.7)) {
        if (!ctx.once(e, 1, "path")) continue;
        hit(ctx, e, 5, { color: AQUA, kb: 0.7, up: 0.3, dir: dirTo(e.location, gate), power: 1.4, sound: "astro.hit_metal" });
        P(dim, "slash", chest(e), { color: STORM, size: 1.0, rot: yawDeg(f), life: 0.22 });
      }
      // 出口の渦
      const og = ctx.ground(out);
      P(dim, "vortex", og, { color: AQUA, rate: 80, life: 0.45, spread: 1.0, height: 2.4, spin: 720 });
      P(dim, "ring_flat", up(og, 0.08), { color: FOAM, size: 1.6, life: 0.45 });
      P(dim, "splash", up(og, 0.05), { color: AQUA, size: 1.5, life: 0.45 });
      ring(dim, "glow", og, 1.4, 14, { color: AQUA, size: 0.6, life: 0.4, speed: 3 }, 0.2);
      sound(dim, "astro.water_wave", og, 1.1, 1.0);
    });
    // 出口で回転斬り
    ctx.at(9, () => {
      const c = ctx.chest();
      P(dim, "slash_flat", up(ctx.loc(), 0.9), { color: AQUA, size: 1.1, rot: yawDeg(ctx.liveDir()), life: 0.3 });
      P(dim, "wind", c, { color: FOAM, count: 6, spread: 1.4, speed: 6 });
      sound(dim, "astro.swing_heavy", c, 1.1, 0.9);
      for (const e of ctx.foes(3.2, c)) {
        if (ctx.once(e, 1, "spin")) hit(ctx, e, 2, { color: AQUA, kb: 0.9, up: 0.3, dir: dirTo(c, e.location) });
      }
    });
    // 残った入口の渦: 3 秒間引き込み、時々削り、最後に潰れて弾ける
    zone(ctx, gate, {
      radius: 5.0, ticks: 60, every: 3, delay: 6, pull: 0.45, height: 3,
      visualEvery: 1,
      visual(d, c, age) { darkVortex(d, c, 1.15, age); },
      onPulse(list, z) {
        if (z.pulses % 6 !== 0) return;
        for (const e of list) hit(ctx, e, 1, { color: STORM, quiet: true, nova: 1, xp: 1 });
        if (list.length) sound(dim, "astro.water_wave", z.center, 0.6, 0.5);
      },
      onEnd(z) {
        if (!ctx.alive()) return;          // 解除・死亡・退出で消えた時は弾けない
        const c = z.center;
        P(dim, "splash", up(c, 0.05), { color: AQUA, size: 2.2, life: 0.5 });
        P(dim, "shock_flat", up(c, 0.08), { color: STORM, size: 2.2, life: 0.45 });
        P(dim, "droplet", up(c, 0.8), { color: white(AQUA, 0.3), count: 14, speed: 6, spread: 0.6 });
        P(dim, "bubble", up(c, 0.6), { color: white(AQUA, 0.4), count: 10, spread: 1.6, speed: 1.4 });
        sound(dim, "astro.splash", c, 0.8, 1.0);
        sound(dim, "astro.explosion", c, 1.4, 0.6);
        for (const e of enemiesNear(ctx, up(c, 0.8), 3.6)) {
          if (ctx.once(e, 1, "collapse")) hit(ctx, e, 3, { color: AQUA, up: 0.7, kb: 0.4, dir: dirTo(c, e.location), power: 1.4 });
        }
      },
    });
    return 16;
  },

  // =========================================================================
  //  空中技「トリトンの逆行」
  //  宙で止まり、頭上で槍を逆行する衛星（薄紅の氷の月と逆回りの軌道）に変える（0〜7）。地面には予告の陣。
  //  8 tick 目に真下へ投げ下ろし、着弾で氷の衝撃。そこを中心に窒素の間欠泉が六本、順に噴き上がって
  //  敵を打ち上げ（凍えて鈍る）、14 tick 後にもう一度大きく噴く。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 18, 0.32);
    body(p, "neptune.retro_throw");
    const below = ctx.ground(ctx.loc());
    sound(dim, "astro.gravity", p.location, 1.3, 0.7);
    sound(dim, "astro.ring_spin", p.location, 0.8, 0.8);
    sound(dim, "astro.beam_charge", p.location, 1.1, 0.5);
    P(dim, "circle", up(below, 0.06), { color: TRITON, size: 2.0, life: 1.4, spin: -90 });
    ctx.every(0, 2, 4, () => P(dim, "warning", up(below, 0.07), { color: [1, 0.35, 0.4], size: 3.0, life: 0.3 }));
    const hand = () => up(ctx.local(0.3, 0.45, 0), 2.3);
    ctx.every(0, 8, 1, (i) => {
      const q = hand();
      P(dim, "glow", q, { color: white(TRITON, 0.3), size: 0.4 + i * 0.1, life: 0.12 });
      if (i % 2 === 0) {
        P(dim, "orbit", q, { color: TRITON, count: 8, spread: 1.1 - i * 0.06, life: 0.3, spin: -720 });
        P(dim, "converge", q, { color: AQUA, count: 6, spread: 1.6, life: 0.25, size: 0.6 });
      }
    });
    ctx.at(8, () => {
      const q = hand();
      const dir = norm(sub(below, q));
      sound(dim, "astro.swing_heavy", q, 0.8, 1.0);
      sound(dim, "astro.gust", q, 1.2, 0.9);
      sound(dim, "astro.laser", q, 0.6, 0.6);
      P(dim, "ring", q, { color: TRITON, size: 1.2, life: 0.2 });
      let done = false;
      const impact = (pos) => {
        if (done) return;
        done = true;
        const g = onGround(dim, pos, 6);
        P(dim, "impact", up(g, 0.6), { color: white(TRITON, 0.3), size: 2.6, life: 0.2 });
        P(dim, "flare", up(g, 0.8), { color: white(TRITON, 0.5), size: 1.6, life: 0.25 });
        P(dim, "shock_flat", up(g, 0.08), { color: NITRO, size: 2.7, life: 0.5 });
        P(dim, "ring_flat", up(g, 0.1), { color: AQUA, size: 3.6, life: 0.5 });
        P(dim, "debris", up(g, 0.2), { count: 10, speed: 7, spread: 0.6 });
        P(dim, "ice", up(g, 0.6), { color: TRITON, count: 10, speed: 6, spread: 0.5 });
        sound(dim, "astro.impact_heavy", g, 0.9, 1.1);
        sound(dim, "astro.ice_shatter", g, 0.8, 1.0);
        shake(dim, g, 16, 0.55, 0.4);
        for (const e of enemiesNear(ctx, up(g, 0.8), 3.8)) {
          if (ctx.once(e, 1, "moon")) hit(ctx, e, 9, { color: TRITON, kb: 0.6, up: 0.5, dir: dirTo(g, e.location), power: 1.8, sound: "astro.hit_heavy" });
        }
        // 窒素の間欠泉: 中心 + 半径 2.6 の五本が順に、14 tick 後にもう一度大きく
        const pts = [g];
        for (let k = 0; k < 5; k++) pts.push(onGround(dim, add(g, yawRotate(EAST, k * 72 + 18), 2.6), 4));
        for (const big of [false, true]) {
          pts.forEach((q2, k) => {
            ctx.at((big ? 14 : 2) + k * 2, () => {
              geyserFx(dim, q2, big);
              if (k % 2 === 0) sound(dim, big ? "astro.gust" : "astro.ice_crack", q2, big ? 0.7 : 1.2, 0.8);
              if (k === 0) sound(dim, "astro.water_wave", q2, big ? 0.8 : 1.4, 0.9);
              for (const e of enemiesNear(ctx, up(q2, 1.0), big ? 2.3 : 1.9)) {
                if (!ctx.once(e, 1, `${big ? "G" : "g"}${k}`)) continue;
                hit(ctx, e, big ? 4 : 3, { color: NITRO, up: big ? 1.0 : 0.8, kb: 0.15, dir: dirTo(q2, e.location), power: 1.2, sound: "astro.ice_crack" });
                effect(e, "slowness", 50, 1);
              }
            });
          });
        }
      };
      projectile(ctx, q, dir, {
        speed: 1.5, range: 48, life: 40, radius: 1.1, pierce: Infinity,
        damage: 6, hitOpts: { color: TRITON, power: 1.2, up: -0.2 },
        trail(d, pos, prev, age) {
          P(d, "glow", pos, { color: white(TRITON, 0.3), size: 1.4, life: 0.12 });
          P(d, "orbit", pos, { color: AQUA, count: 4, spread: 0.9, life: 0.15, spin: -900 });
          P(d, "trail", prev, { color: FOAM, size: 1.0, life: 0.25 });
          if (age % 2 === 0) P(d, "speedline", pos, { color: white(TRITON, 0.4), count: 3, dir: UPV, speed: 12, spread: 0.4 });
        },
        onEnd(pos, reason) { if (reason !== "owner" && ctx.alive()) impact(pos); },
      });
    });
    return 26;
  },

  // =========================================================================
  //  必殺「アビサル・テンペスト」
  //  時を止め（ultOpen）、足元から巨大な渦潮を広げる（6〜50）: 内へ縮む水の輪と回る波頭、敵は渦に沿って
  //  引きずり回され、時々削られる。槍を立てて渦をかき回し（18）、超音速の嵐が敵を巻き上げ（32）、
  //  暗い嵐雲の下で風の刃が宙の敵を刻む（34〜50）。四方の大津波が押し寄せ（50・54）、
  //  跳び上がった騎士が槍を大地に突き立てると津波が一斉に崩れ落ちて押し潰す（60）。泡と霧の余韻（62〜80）。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 90, 14);
    const centre = ctx.ground(ctx.loc());
    sound(dim, "astro.water_wave", centre, 0.5, 1.2);
    ctx.at(6, () => {
      emblem(dim, up(centre, 0.06), KEY, { size: 4.5, life: 4.5, spin: -25 });
      P(dim, "circle", up(centre, 0.05), { color: AQUA, size: 7.0, life: 4.0, spin: 40 });
      sound(dim, "astro.gravity", centre, 0.5, 1.2);
    });
    // 渦潮
    zone(ctx, centre, {
      radius: 9.5, ticks: 50, delay: 6, every: 2, height: 4,
      visualEvery: 1,
      visual(d, c, age) {
        if (age < 6) return;
        if (age % 3 === 0) {
          ring(d, "glow", c, 9 - ((age * 0.5) % 8), 26, { color: age % 6 ? AQUA : FOAM, size: 0.7, life: 0.3 }, 0.15);
        }
        if (age % 4 === 0) {
          for (let k = 0; k < 4; k++) {
            const a = -age * 12 + k * 90;
            const q = add(c, yawRotate(EAST, a), 6.5);
            P(d, "wave", q, { color: k % 2 ? AZURE : AQUA, dir: yawRotate(EAST, a - 90), speed: 9, size: 1.3, life: 0.6 });
          }
        }
        if (age % 8 === 0) P(d, "vortex", c, { color: AQUA, rate: 90, life: 0.6, spread: 4.0, height: 5, spin: -360 });
        if (age % 6 === 3) P(d, "bubble", up(c, 0.6), { color: white(AQUA, 0.4), count: 10, spread: 5, speed: 1.0 });
        if (age % 10 === 5) P(d, "ring_flat", up(c, 0.1), { color: FOAM, size: 8, life: 0.5 });
        if (age % 12 === 0) sound(d, "astro.water_wave", c, 0.6 + (age % 24 ? 0.1 : 0), 0.9);
      },
      onPulse(list, z) {
        if (z.age >= 31) return;           // 32 で嵐が巻き上げる（ここで速度を上書きすると浮かない）
        for (const e of list) {
          launch(e, 0.04, hdist(e.location, z.center) > 1.6 ? 0.55 : 0.15, swirlDir(z.center, e.location));
          if (z.pulses % 5 === 0) hit(ctx, e, 2, { color: AQUA, quiet: true, nova: 1, xp: 1 });
        }
      },
    });
    ctx.at(18, () => {
      body(p, "neptune.tempest_stir");
      sound(dim, "astro.wind", centre, 0.5, 1.2);
    });
    // 超音速の嵐: 巻き上げ
    ctx.at(30, () => {
      P(dim, "cloud", up(centre, 9), { color: [0.22, 0.28, 0.5], count: 8, spread: 6, life: 3.0, dir: { x: 0, y: 0, z: 0.2 } });
      sound(dim, "astro.thunder", centre, 0.9, 0.9);
    });
    ctx.at(32, () => {
      P(dim, "vortex", centre, { color: white(AQUA, 0.3), rate: 140, life: 1.0, spread: 6.5, height: 9, spin: -900 });
      for (let k = 0; k < 8; k++) {
        const a = k * 45;
        P(dim, "wind", up(add(centre, yawRotate(EAST, a), 5), 1.5), { color: FOAM, count: 4, dir: yawRotate(EAST, a - 90), speed: 14, spread: 1.0 });
      }
      ring(dim, "glow", centre, 7, 30, { color: FOAM, size: 0.8, life: 0.5, speed: -6 }, 0.3);
      sound(dim, "astro.gust", centre, 0.6, 1.5);
      sound(dim, "astro.wind", centre, 0.8, 1.4);
      shake(dim, centre, 22, 0.5, 0.6);
      for (const e of ctx.foes(11, up(centre, 1))) {
        if (!ctx.once(e, 1, "lift")) continue;
        hit(ctx, e, 4, { color: FOAM, power: 1.3, nova: 1 });
        launch(e, 1.05, 0.25, swirlDir(centre, e.location, 0.3));
      }
    });
    ctx.at(40, () => {
      P(dim, "bolt", up(centre, 10), { color: white(AQUA, 0.3), dir: DOWN, len: 10, size: 1.2, life: 0.25 });
      P(dim, "impact", up(centre, 0.6), { color: AQUA, size: 2.0, life: 0.18 });
      sound(dim, "astro.thunder", centre, 1.1, 1.1);
    });
    ctx.every(34, 5, 4, (i) => {
      sound(dim, "astro.swing", centre, 1.3 + i * 0.08, 0.8);
      for (const e of ctx.foes(12, up(centre, 2))) {
        P(dim, "slash", chest(e), { color: i % 2 ? FOAM : AQUA, size: 1.2, rot: i * 70, var: i % 2, life: 0.2 });
        P(dim, "wind", chest(e), { color: FOAM, count: 2, spread: 0.6, speed: 6 });
        if (ctx.once(e, 1, `blade${i}`)) hit(ctx, e, 2, { color: FOAM, up: 0.22, kb: 0.1, nova: 1 });
      }
    });
    // 大津波
    ctx.at(50, () => {
      body(p, "neptune.tidal_crash");
      sound(dim, "astro.water_wave", centre, 0.45, 1.6);
      sound(dim, "astro.gravity", centre, 0.4, 1.0);
    });
    for (const [t, R, sz] of [[50, 11.5, 2.8], [54, 9, 2.3]]) {
      ctx.at(t, () => {
        for (let k = 0; k < 12; k++) {
          const a = k * 30 + (t === 54 ? 15 : 0);
          const q = add(centre, yawRotate(EAST, a), R);
          P(dim, "wave", q, { color: k % 2 ? AZURE : mix(AZURE, FOAM, 0.3), dir: yawRotate(EAST, a + 180), speed: 12, size: sz, life: 0.9 });
          if (k % 3 === 0) P(dim, "splash", onGround(dim, q, 5), { color: FOAM, size: 1.6, life: 0.5 });
        }
        sound(dim, "astro.water_wave", centre, 0.55 + (t - 50) * 0.03, 1.4);
      });
    }
    ctx.at(60, () => {
      P(dim, "lens", up(centre, 1.5), { color: white(AQUA, 0.5), size: 3.0, life: 0.6 });
      P(dim, "splash", up(centre, 0.05), { color: FOAM, size: 3.0, count: 6, spread: 4.0, life: 0.6 });
      P(dim, "shock_flat", up(centre, 0.08), { color: FOAM, size: 7, life: 0.6 });
      P(dim, "ring_flat", up(centre, 0.12), { color: AQUA, size: 9, life: 0.6 });
      P(dim, "droplet", up(centre, 1.0), { color: white(AQUA, 0.3), count: 30, speed: 9, spread: 2.0 });
      P(dim, "bubble", up(centre, 0.8), { color: white(AQUA, 0.5), count: 20, spread: 5, speed: 1.6 });
      ring(dim, "glow", centre, 2.0, 32, { color: FOAM, size: 1.0, life: 0.6, speed: 12 }, 0.2);
      flash(dim, centre, 32, white(AQUA, 0.5), 0.1, 0.5);
      shake(dim, centre, 28, 0.9, 0.7);
      sound(dim, "astro.explosion_big", centre, 0.7, 1.6);
      sound(dim, "astro.splash", centre, 0.6, 1.6);
      sound(dim, "astro.impact_heavy", centre, 0.7, 1.3);
      for (const e of ctx.foes(11.5, up(centre, 1))) {
        hit(ctx, e, 14, { color: AQUA, kb: 0.5, up: -0.9, dir: dirTo(centre, e.location), power: 2.4, crit: true, sound: "astro.hit_heavy" });
        effect(e, "slowness", 60, 2);
      }
    });
    ctx.every(62, 6, 3, (i) => {
      P(dim, "ring_flat", up(centre, 0.1), { color: FOAM, size: 6 + i * 1.6, life: 0.5 });
      P(dim, "droplet", up(add(centre, yawRotate(EAST, i * 67), 3 + i), 6), { color: white(AQUA, 0.3), count: 8, spread: 3, speed: 1 });
      if (i === 0) P(dim, "cloud", up(centre, 0.8), { color: white(NITRO, 0.3), count: 6, spread: 7, life: 2.5, dir: { x: 0.2, y: 0.05, z: 0 } });
      if (i % 2 === 0) sound(dim, "astro.splash", centre, 1.0 + i * 0.1, 0.6);
    });
    return 82;
  },

  // =========================================================================
  //  三段目「波濤突き」: 突きの先から水の槍が 5m 先まで伸びる
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    const from = add(up(ctx.loc(), 1.1), f, 0.8);
    const L = clearRange(dim, from, f, 5);
    const to = add(from, f, L);
    P(dim, "thrust", from, { color: white(AQUA, 0.35), dir: f, len: L, size: 1.4, life: 0.22 });
    beam(dim, from, to, AZURE, { size: 0.6, life: 0.25, core: FOAM, ends: false });
    P(dim, "wave", up(ctx.loc(), 0.05), { color: AQUA, dir: f, speed: 14, size: 0.7, life: 0.4 });
    P(dim, "droplet", to, { color: white(AQUA, 0.3), count: 10, speed: 4, spread: 0.3 });
    P(dim, "splash", onGround(dim, to, 3), { color: AQUA, size: 1.0, life: 0.4 });
    sound(dim, "astro.swing_heavy", p.location, 1.1, 0.9);
    sound(dim, "astro.splash", to, 1.2, 0.8);
    for (const e of enemiesOnLine(ctx, from, to, 1.1)) {
      hit(ctx, e, 5, { color: AQUA, kb: 1.0, up: 0.2, dir: f, power: 1.3, sound: "astro.splash" });
    }
    if (target && valid(target)) P(dim, "bubble", chest(target), { color: white(AQUA, 0.4), count: 5, spread: 0.4, speed: 1 });
    return 10;
  },

  // =========================================================================
  //  変身の締め: 渦潮が足元から巻き上がり（0〜8）、波頭が輪になって外へ砕ける（12）
  // =========================================================================
  burst(ctx) {
    const { dim } = ctx;
    const g = ctx.ground(ctx.loc());
    sound(dim, "astro.water_wave", g, 0.9, 1.0);
    sound(dim, "astro.wind", g, 1.2, 0.6);
    emblem(dim, up(g, 0.05), KEY, { size: 1.6, life: 1.8, spin: -40 });
    P(dim, "vortex", g, { color: AQUA, rate: 80, life: 0.7, spread: 1.0, height: 3.2, spin: -720 });
    P(dim, "flare", ctx.chest(), { color: white(AQUA, 0.5), size: 1.3, life: 0.3 });
    ctx.every(0, 3, 4, (i) => {
      P(dim, "ring_flat", up(g, 0.06 + i * 0.01), { color: i % 2 ? FOAM : AQUA, size: 0.8 + i * 0.9, life: 0.5 });
      P(dim, "bubble", up(g, 0.4), { color: white(AQUA, 0.4), count: 6, spread: 0.8 + i * 0.4, speed: 1.2 });
    });
    ctx.at(6, () => P(dim, "vortex", g, { color: FOAM, rate: 70, life: 0.5, spread: 1.6, height: 3.8, spin: -900 }));
    ctx.at(12, () => {
      for (let k = 0; k < 6; k++) {
        const a = k * 60;
        P(dim, "wave", add(g, yawRotate(EAST, a), 0.6), { color: k % 2 ? AZURE : AQUA, dir: yawRotate(EAST, a), speed: 6, size: 0.8, life: 0.7 });
      }
      P(dim, "splash", up(g, 0.05), { color: FOAM, size: 1.8, life: 0.5 });
      ring(dim, "glow", g, 1.2, 16, { color: FOAM, size: 0.6, life: 0.5, speed: 4 }, 0.2);
      P(dim, "droplet", up(g, 1.2), { color: white(AQUA, 0.3), count: 14, speed: 5, spread: 0.6 });
      sound(dim, "astro.splash", g, 1.0, 1.0);
    });
    return 20;
  },

  // =========================================================================
  //  パッシブ「潮」: 水中か、雨の中で空の下にいる間は潮が満ちて与ダメージ +25%。
  //  満ちている間は泡がまとわりつき、当てた敵は潮の重さで鈍る。倒した敵は泡になって海へ還る。
  // =========================================================================
  passive: {
    tick(p, st) {
      if (st.n % 4 === 1) {
        const was = TIDE.get(p.id)?.on ?? false;
        const on = tideNow(p);
        TIDE.set(p.id, { on });
        if (on && !was) {
          status(p, "§b潮が満ちる §7— 与ダメージ +25%", 40);
          sound(p.dimension, "astro.water_wave", p.location, 1.4, 0.6);
          P(p.dimension, "ring_flat", up(p.location, 0.08), { color: AQUA, size: 1.2, life: 0.5 });
        }
      }
      if (TIDE.get(p.id)?.on && st.n % 2 === 0) {
        P(p.dimension, "bubble", chest(p), { color: white(AQUA, 0.4), count: 2, spread: 0.6, speed: 0.4 });
      }
    },
    onHit(p, target, dmg, ctx) {
      if (!TIDE.get(p.id)?.on || !valid(target)) return;
      effect(target, "slowness", 30, 0);
      P(p.dimension, "splash", up(target.location, 0.05), { color: AQUA, size: 0.7, life: 0.35 });
    },
    onHurt(p, attacker, dmg) {
      if (!TIDE.get(p.id)?.on) return;
      P(p.dimension, "bubble", chest(p), { color: white(AQUA, 0.4), count: 5, spread: 0.5, speed: 1.2 });
    },
    onKill(p, victim) {
      try {
        const l = victim.location;
        P(p.dimension, "bubble", up(l, 0.8), { color: white(AQUA, 0.4), count: 10, spread: 0.6, speed: 1.4 });
        P(p.dimension, "splash", up(l, 0.05), { color: AQUA, size: 1.0, life: 0.4 });
      } catch (_) { }
    },
    dmgMul(p) { return TIDE.get(p.id)?.on ? 1.25 : 1; },
  },

  meta: { noDamage: [] },
});
