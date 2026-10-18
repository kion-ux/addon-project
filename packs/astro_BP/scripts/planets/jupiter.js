// ===========================================================================
//  木星 ゼウス（ZEUS）— 雷帝機装の技
//
//  ガス惑星の王。クリームと褐色の縞の重装甲、胸で渦巻く大赤斑、肩のテスラコイル、王冠の兜、
//  雷霆鎚 ケラウノス。色: 電光の青（VOLT = ctx.c）/ 白熱の芯（HOT）/ 大赤斑の錆色（GRS = ctx.accent）/
//  雲の帯のクリームと褐色（CREAM / TAN）/ 嵐の暗い雲（STORM）/ ガリレオ衛星の色（IO EUROPA GANYMEDE CALLISTO）
//
//   惑星技  雷霆 ケラウノス          鎚を天へ掲げて雷を受け（5）、前の敵へ落雷 → 最大 5 体まで連鎖（10〜）
//   機動技  重力スイングバイ          前方に重力の井戸（0〜10。敵を一点へ吸い寄せる）→ その中を突き抜け（10〜18）、
//                                     井戸が潰れて弾け（中心を抜けた瞬間）、抜け際に鎚で薙ぐ（17）
//   空中技  大赤斑 グレートレッドスポット 嵐の渦をまとって宙で回り（0〜8。周りを吸い込んで雷で打つ）、渦ごと降りて
//                                     着地で嵐の目が炸裂 → 残った渦がしばらく敵を吸い込み雷で打つ
//   必殺    ガリレオの審判            時を止め、四衛星を天に呼ぶ → イオ（噴火）・エウロパ（氷）・ガニメデ（重力）・
//                                     カリスト（衝突）を次々に落とし、最後に嵐の雲から極大の雷霆（68）
//   三段目  雷槌                      叩きつけた鎚に落雷し、周りの敵を感電させる
//   変身の締め 落雷が三度、胸の大赤斑が渦巻く
//   パッシブ static                   攻撃が当たるたびに静電気が溜まり（肩のコイルが放電で示す）、5 回目で近くの敵へ連鎖放電。
//                                     攻撃を受けても 1 溜まる
// ===========================================================================
import {
  register, lunge, hover, plunge, safeAhead, ultOpen, zone, meteor, chain, dirTo,
} from "../engine.js";
import {
  P, ring, arc, shock, beam, emblem, flash, shake, sound, body, white, mix, afterimage, fxScale,
} from "../fx.js";
import {
  hit, nearestEnemy, hostilesNear, freeze, pull,
} from "../combat.js";
import { S } from "../state.js";
import {
  add, up, sub, norm, lerp3, rightOf, flatDir, chest, dist, hdist, valid, effect, yawRotate, yawDeg,
  onGround, now,
} from "../util.js";

const KEY = "jupiter";
const VOLT = [0.55, 0.93, 1.0];
const HOT = [0.86, 0.98, 1.0];
const DEEP = [0.16, 0.36, 0.72];
const GRS = [0.85, 0.28, 0.17];
const GRS_HOT = [1.0, 0.56, 0.32];
const CREAM = [0.95, 0.87, 0.72];
const TAN = [0.79, 0.56, 0.35];
const STORM = [0.36, 0.38, 0.46];
const IO = [1.0, 0.84, 0.26];
const IO_LAVA = [1.0, 0.42, 0.1];
const EUROPA = [0.82, 0.94, 1.0];
const GANYMEDE = [0.66, 0.6, 0.56];
const GRAVITY = [0.62, 0.48, 1.0];
const CALLISTO = [0.5, 0.42, 0.36];
const UPV = { x: 0, y: 1, z: 0 };
const EAST = { x: 1, y: 0, z: 0 };

// ---------------------------------------------------------------------------
//  演出の部品
// ---------------------------------------------------------------------------
/** 天からの落雷（地面の点 g へ）。size で太さ、quiet で音なし。 */
function skyStrike(dim, g, size = 1, color = VOLT, quiet = false) {
  const b = up(g, 0.05);
  P(dim, "bolt", b, { color, dir: UPV, len: 10 + size * 3, size: 0.9 * size, life: 0.26 });
  P(dim, "bolt", b, { color: HOT, dir: UPV, len: 10 + size * 3, size: 0.4 * size, life: 0.2 });
  P(dim, "impact", up(g, 0.5), { color: white(color, 0.4), size: 1.2 * size, life: 0.18 });
  P(dim, "ring_flat", up(g, 0.08), { color, size: 0.9 * size, life: 0.35 });
  P(dim, "arc", up(g, 0.6), { color: HOT, count: 3, spread: 0.6 * size, size: 0.8 * size, life: 0.3 });
  P(dim, "spark", up(g, 0.3), { color, count: Math.round(6 + 4 * size), speed: 6 + size * 2, size: 0.9 });
  if (!quiet) {
    sound(dim, "astro.thunder", g, 1.25 + Math.random() * 0.2, 0.55 + size * 0.25);
    sound(dim, "astro.zap", g, 0.9, 0.7);
  }
}

/** 電光の弧（a → b）。 */
function zapLine(dim, a, b, color = VOLT, size = 0.5) {
  const d = sub(b, a);
  const L = Math.hypot(d.x, d.y, d.z);
  if (!(L > 0.05)) return;
  P(dim, "bolt", a, { color, dir: norm(d), len: L, size, life: 0.18 });
}

/** 掲げた鎚頭のあたり（頭上やや前）。 */
function hammerTop(ctx) {
  return ctx.local(0.3, 0.3, 3.0);
}

/** 嵐の渦（大赤斑）: 錆色の渦 + クリームの雲の帯 + 中の電光。center は足元。 */
function stormFx(dim, center, i, R = 2.4) {
  if (i % 6 === 0) {
    P(dim, "vortex", up(center, -0.3), { color: GRS, spread: R * 0.9, height: 4.2, rate: 70, life: 0.35, spin: 720 });
    P(dim, "vortex", up(center, 0.2), { color: CREAM, spread: R * 0.6, height: 3.2, rate: 40, life: 0.35, spin: -540 });
  }
  if (i % 2 === 0) {
    P(dim, "orbit", up(center, 1.2), { color: mix(GRS, TAN, (i % 4) / 4), count: 6, spread: R, life: 0.5, spin: 520 });
    P(dim, "wind", up(center, 0.8 + (i % 3) * 0.6), { color: CREAM, count: 2, spread: R * 0.8, speed: 6,
                                                      dir: yawRotate(EAST, i * 47) });
  }
  if (i % 3 === 0) {
    const a = i * 1.9;
    const q = { x: center.x + Math.cos(a) * R, y: center.y + 1 + (i % 2), z: center.z + Math.sin(a) * R };
    P(dim, "arc", q, { color: VOLT, count: 2, spread: 0.5, size: 0.9, life: 0.2 });
  }
}

/** 四衛星の天の輪（必殺の前半）: 頭上を回る四つの光。 */
function moonOrbitPos(base, k, t) {
  const a = t * 0.16 + k * Math.PI / 2;
  return { x: base.x + Math.cos(a) * 2.6, y: base.y + Math.sin(t * 0.2 + k) * 0.3, z: base.z + Math.sin(a) * 2.6 };
}

const MOONS = [
  { name: "io", color: IO, hot: IO_LAVA },
  { name: "europa", color: EUROPA, hot: [0.55, 0.85, 1.0] },
  { name: "ganymede", color: GANYMEDE, hot: GRAVITY },
  { name: "callisto", color: CALLISTO, hot: [1.0, 0.62, 0.3] },
];

// ---------------------------------------------------------------------------
//  パッシブ static の放電
// ---------------------------------------------------------------------------
/** 静電気の溜まり（変身のたびに空になる作業用の st に置く）。 */
function staticOf(p) {
  try {
    const ps = S(p).passive ?? {};
    return ps;
  } catch (_) { return {}; }
}

function discharge(p, target) {
  const dim = p.dimension;
  const from = valid(target) ? chest(target) : chest(p);
  sound(dim, "astro.zap", from, 0.8, 1.0);
  sound(dim, "astro.thunder", from, 1.6, 0.45);
  P(dim, "flare", from, { color: HOT, size: 1.0, life: 0.18 });
  P(dim, "ring", from, { color: VOLT, size: 1.4, life: 0.25 });
  P(dim, "arc", from, { color: VOLT, count: 5, spread: 0.7, size: 1.0, life: 0.3 });
  if (valid(target)) hit(p, target, 4, { color: VOLT, power: 1.1, sound: "astro.zap", nova: 1, xp: 1 });
  // 近くの敵対的な相手へ飛び移る（最大 3 体）
  const tid = valid(target) ? target.id : "";
  const foes = hostilesNear(p, from, 7).filter((e) => e.id !== tid)
    .sort((a, b) => dist(a.location, from) - dist(b.location, from)).slice(0, 3);
  let prev = from;
  for (const e of foes) {
    if (!valid(e)) continue;
    const to = chest(e);
    zapLine(dim, prev, to, VOLT, 0.55);
    zapLine(dim, prev, to, HOT, 0.25);
    P(dim, "arc", to, { color: VOLT, count: 3, spread: 0.5, life: 0.25 });
    hit(p, e, 4, { color: VOLT, power: 1.0, sound: "astro.zap", nova: 1, xp: 1 });
    prev = to;
  }
}

register(KEY, {
  // =========================================================================
  //  惑星技「雷霆 ケラウノス」
  //  0〜8 鎚を天へ掲げ、頭上に嵐の雲が集まって鎚頭へ電気が吸い込まれる / 5 天の雷が鎚を打つ /
  //  10 前の敵へ落雷（鎚から一筋 + 天から一筋）→ 3 tick ごとに次の敵へ連鎖（最大 5 体）/ 余韻の煙と火花
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "jupiter.keraunos");
    sound(dim, "astro.beam_charge", p.location, 1.25, 0.7);
    sound(dim, "astro.wind", p.location, 0.6, 0.6);
    ctx.at(0, () => {
      P(dim, "cloud", up(ctx.loc(), 5.2), { color: STORM, count: 6, spread: 2.0, life: 1.6, size: 1.3,
                                           dir: { x: 0, y: 0.05, z: 0 } });
      P(dim, "circle_v", hammerTop(ctx), { color: VOLT, size: 0.6, life: 0.5, dir: UPV, spin: 180 });
    });
    ctx.every(0, 5, 2, (i) => {
      const top = hammerTop(ctx);
      P(dim, "converge", top, { color: VOLT, count: 10, spread: 1.8, life: 0.3, size: 0.8 });
      P(dim, "arc", top, { color: HOT, count: 2 + i, spread: 0.35 + i * 0.1, size: 0.7, life: 0.2 });
      if (i % 2 === 0) P(dim, "glow", top, { color: VOLT, size: 0.8 + i * 0.25, life: 0.15 });
    });
    ctx.at(5, () => {
      const top = hammerTop(ctx);
      P(dim, "bolt", top, { color: VOLT, dir: UPV, len: 7, size: 1.0, life: 0.25 });
      P(dim, "bolt", top, { color: HOT, dir: UPV, len: 7, size: 0.45, life: 0.2 });
      P(dim, "flare", top, { color: HOT, size: 1.2, life: 0.2 });
      P(dim, "glow", top, { color: VOLT, size: 2.4, life: 0.2 });
      sound(dim, "astro.thunder", top, 1.35, 0.8);
      sound(dim, "astro.zap", top, 1.1, 0.9);
      shake(dim, p.location, 6, 0.15, 0.2);
    });
    ctx.at(10, () => {
      const top = hammerTop(ctx);
      const from = ctx.local(1.3, 0.1, 1.5);
      let first = nearestEnemy(ctx, ctx.chest(), 16, ctx.liveView(), 40) ?? nearestEnemy(ctx, ctx.chest(), 7);
      sound(dim, "astro.beam_fire", from, 1.3, 0.8);
      P(dim, "flare", from, { color: HOT, size: 1.4, life: 0.2, rot: yawDeg(ctx.liveDir()) });
      zapLine(dim, top, from, HOT, 0.4);
      if (!first) {
        // 狙いの地点へ落とす（そこに居る敵に当たれば、そこから連鎖）
        const g = ctx.aim(14);
        zapLine(dim, from, up(g, 0.6), VOLT, 0.7);
        skyStrike(dim, g, 1.4);
        shock(dim, g, VOLT, 2.6, { debris: 4 });
        shake(dim, g, 12, 0.3, 0.3);
        for (const e of ctx.foes(2.8, up(g, 0.8))) {
          if (ctx.once(e, 1, "ground")) hit(ctx, e, 9, { color: VOLT, power: 1.4, up: 0.3 });
        }
        first = nearestEnemy(ctx, up(g, 0.8), 4);
        if (!first) return;
      }
      chain(ctx, first, {
        max: 5, range: 7.5, damage: 10, falloff: 0.88, delay: 3, from, color: VOLT,
        hit: { power: 1.4, up: 0.28, kb: 0.25 }, sound: "astro.zap",
        onHit(e, i) {
          if (!valid(e)) return;
          const g = ctx.ground(e.location);
          skyStrike(dim, g, i === 0 ? 1.5 : 1.1, VOLT, i > 1);
          P(dim, "arc", chest(e), { color: HOT, count: 4, spread: 0.6, size: 1.0, life: 0.4 });
          freeze(e, 14);
          if (i === 0) {
            shock(dim, g, VOLT, 2.4, { debris: 4 });
            shake(dim, g, 14, 0.35, 0.3);
            flash(dim, g, 10, white(VOLT, 0.5), 0.02, 0.4);
          }
          // 余韻: 焦げた煙と火花
          ctx.at(6, () => {
            P(dim, "smoke", up(g, 0.4), { color: STORM, count: 3, speed: 1, size: 0.9 });
            P(dim, "ember", up(g, 0.4), { color: VOLT, count: 5, speed: 2, size: 0.5 });
          });
        },
      });
    });
    return 24;
  },

  // =========================================================================
  //  機動技「重力スイングバイ」
  //  0 前方 5.5m（壁の手前まで）に重力の井戸 / 0〜10 敵を井戸の中心へ吸い寄せる /
  //  10〜18 井戸めがけて突進し、すれ違う敵を打ち上げる。中心を抜けた瞬間に井戸が潰れて弾ける /
  //  17 抜け際に鎚で薙ぎ払う
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    body(p, "jupiter.swingby");
    const ahead = safeAhead(dim, ctx.loc(), f, 5.5);
    const W = up(ahead, 1.0);
    const Wg = ctx.ground(ahead);
    let collapsed = false;
    sound(dim, "astro.gravity", W, 0.6, 1.2);
    sound(dim, "astro.beam_charge", p.location, 0.7, 0.6);
    ctx.at(0, () => {
      P(dim, "black_hole", W, { color: GRAVITY, size: 0.85, life: 1.0, spin: 260 });
      P(dim, "lens", W, { color: mix(GRAVITY, VOLT, 0.4), size: 0.8, life: 0.8 });
      P(dim, "circle", up(Wg, 0.05), { color: VOLT, size: 2.4, life: 1.0, spin: -120 });
      beam(dim, ctx.local(0.8, -0.4, 1.4), W, GRAVITY, { size: 0.25, life: 0.3, ends: false });
    });
    ctx.every(0, 6, 2, (i) => {
      P(dim, "converge", W, { color: mix(GRAVITY, CREAM, 0.3), count: 14, spread: 3.2, life: 0.35, size: 0.9 });
      P(dim, "orbit", W, { color: i % 2 ? TAN : VOLT, count: 8, spread: 1.6, life: 0.5, spin: 600 });
      ring(dim, "dot", Wg, 4.5 - i * 0.6, 20, { color: GRAVITY, size: 0.5, life: 0.25 }, 0.15);
      if (i % 2 === 0) sound(dim, "astro.gravity", W, 0.8 + i * 0.1, 0.6);
      for (const e of ctx.foes(8, W)) {
        pull(e, W, 0.8, 0.08);
        if (i === 0) freeze(e, 16);
        if (i % 2 === 0) P(dim, "speedline", chest(e), { color: GRAVITY, count: 3, dir: dirTo(e.location, W), speed: 8, spread: 0.4 });
      }
    });
    effect(p, "resistance", 24, 2);
    const collapse = () => {
      if (collapsed) return;
      collapsed = true;
      P(dim, "flare", W, { color: white(GRAVITY, 0.5), size: 1.8, life: 0.25 });
      P(dim, "black_hole", W, { color: GRAVITY, size: 0.35, life: 0.3, spin: 900 });
      P(dim, "impact", W, { color: white(VOLT, 0.3), size: 2.0, life: 0.2 });
      shock(dim, Wg, GRAVITY, 3.5, { debris: 6 });
      P(dim, "ring", W, { color: VOLT, size: 2.4, life: 0.3 });
      sound(dim, "astro.impact_heavy", W, 1.1, 1.0);
      sound(dim, "astro.gravity", W, 1.5, 0.9);
      shake(dim, W, 12, 0.4, 0.3);
      for (const e of ctx.foes(4.2, W)) {
        if (ctx.once(e, 1, "crush")) {
          hit(ctx, e, 5, { color: GRAVITY, up: 0.85, kb: 0.4, dir: dirTo(W, e.location), power: 1.6,
                           sound: "astro.hit_heavy" });
        }
      }
    };
    ctx.every(10, 4, 2, () => lunge(ctx, f, 1.35, 0.05));
    ctx.every(10, 9, 1, (i) => {
      const c0 = ctx.chest();
      if (i % 3 === 0) afterimage(dim, p.location, VOLT, 0.3);
      P(dim, "speedline", c0, { color: VOLT, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 14, spread: 0.8 });
      P(dim, "ring", c0, { color: mix(GRAVITY, VOLT, 0.5), size: 1.3, life: 0.1, rot: i * 30 });
      if (i % 2 === 0) P(dim, "arc", c0, { color: HOT, count: 2, spread: 0.8, life: 0.15 });
      if (i === 0) sound(dim, "astro.boost", p.location, 0.85, 1.0);
      for (const e of ctx.foes(2.6, c0)) {
        if (!ctx.once(e, 1, "pass")) continue;
        hit(ctx, e, 6, { color: VOLT, kb: 0.5, up: 0.7, dir: f, power: 1.4, sound: "astro.hit_metal" });
        zapLine(dim, c0, chest(e), VOLT, 0.5);
      }
      if (!collapsed && (hdist(p.location, W) < 1.6 || i >= 5)) collapse();
    });
    ctx.at(17, () => {
      const d = ctx.liveDir();
      sound(dim, "astro.swing_heavy", p.location, 0.8, 1.1);
      sound(dim, "astro.zap", p.location, 1.2, 0.6);
      arc(dim, ctx.chest(), d, 2.6, 70, -80, 6, VOLT, { size: 1.1, steps: 12 });
      arc(dim, ctx.chest(), d, 2.1, 60, -70, 6, TAN, { size: 0.6, steps: 8, inner: false, sparks: false });
      for (const e of ctx.cone(4.2, 75, ctx.chest(), d)) {
        if (ctx.once(e, 1, "sweep")) hit(ctx, e, 4, { color: VOLT, kb: 1.3, up: 0.35, dir: rightOf(d), power: 1.3 });
      }
    });
    ctx.at(20, () => {
      const g = ctx.ground(ctx.loc());
      P(dim, "dust", up(g, 0.1), { count: 10, speed: 3, size: 1.0 });
      P(dim, "ring_flat", up(g, 0.08), { color: VOLT, size: 1.2, life: 0.35 });
    });
    return 22;
  },

  // =========================================================================
  //  空中技「大赤斑 グレートレッドスポット」
  //  0〜8 宙で止まり、錆色の嵐の渦をまとって回る。周り 6.5m の敵を吸い込み、渦の電光が打つ /
  //  8〜 渦ごと降りる（吸い込みと電光は続く）/ 着地 嵐の目が炸裂（衝撃波・環状の落雷・打ち上げ）/
  //  残った渦が 2 秒、中の敵を吸い込んで雷で打つ
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 8, 0.28);
    body(p, "jupiter.storm_dive");
    sound(dim, "astro.wind", p.location, 0.6, 1.1);
    sound(dim, "astro.gust", p.location, 0.8, 0.9);
    sound(dim, "astro.gravity", p.location, 0.7, 0.7);
    let landed = false;
    const swirl = (i) => {
      const l = ctx.loc();
      stormFx(dim, l, i, 2.4);
      if (i % 2 === 0) {
        for (const e of ctx.foes(6.5, up(l, 0.5))) pull(e, l, 0.55, 0.12);
      }
      if (i % 3 === 1) {
        const foes = ctx.foes(5.5, up(l, 0.5));
        const e = foes[i % Math.max(1, foes.length)];
        if (e && ctx.once(e, 3, "zap")) {
          const from = { x: l.x + Math.cos(i) * 2.2, y: l.y + 2.2, z: l.z + Math.sin(i) * 2.2 };
          zapLine(dim, from, chest(e), VOLT, 0.6);
          hit(ctx, e, 2, { color: VOLT, power: 0.9, sound: "astro.zap" });
        }
      }
      if (i % 5 === 0) sound(dim, "astro.wind", l, 0.7 + (i % 3) * 0.1, 0.6);
    };
    ctx.every(0, 8, 1, swirl);
    ctx.at(8, () => {
      plunge(ctx, (loc) => {
        landed = true;
        body(p, "jupiter.storm_land");
        const g = ctx.ground(loc);
        P(dim, "flare", up(g, 1.0), { color: white(GRS_HOT, 0.4), size: 2.0, life: 0.3 });
        P(dim, "impact", up(g, 0.8), { color: GRS_HOT, size: 3.0, life: 0.22 });
        shock(dim, g, GRS, 5.5, { debris: 14 });
        P(dim, "shock_flat", up(g, 0.12), { color: VOLT, size: 2.4, life: 0.4 });
        P(dim, "vortex", up(g, -0.2), { color: GRS, spread: 3.2, height: 5.5, rate: 90, life: 1.0, spin: 720 });
        P(dim, "vortex", up(g, 0.2), { color: CREAM, spread: 2.2, height: 4.0, rate: 50, life: 1.0, spin: -600 });
        P(dim, "lens", up(g, 1.2), { color: white(GRS, 0.5), size: 1.4, life: 0.4 });
        sound(dim, "astro.explosion_big", g, 0.9, 1.3);
        sound(dim, "astro.thunder", g, 1.0, 1.1);
        sound(dim, "astro.impact_heavy", g, 0.8, 1.0);
        shake(dim, g, 20, 0.7, 0.5);
        flash(dim, g, 12, white(GRS_HOT, 0.5), 0.03, 0.45);
        for (const e of ctx.foes(5.5, up(g, 0.8))) {
          if (ctx.once(e, 1, "eye")) {
            hit(ctx, e, 8, { color: GRS_HOT, kb: 0.6, up: 0.85, dir: dirTo(g, e.location), power: 2.0,
                              sound: "astro.hit_heavy" });
          }
        }
        // 嵐の目の周りに落雷の輪
        for (let k = 0; k < 6; k++) {
          ctx.at(1 + k, () => {
            const q = onGround(dim, add(g, yawRotate(EAST, k * 60 + 15), 3.6), 5);
            skyStrike(dim, q, 1.0, VOLT, k % 2 === 1);
          });
        }
        // 残った渦（2 秒）: 吸い込み + 雷
        zone(ctx, g, {
          radius: 4.2, ticks: 40, every: 12, delay: 6, damage: 1, pull: 0.45, color: GRS,
          hit: { color: VOLT, sound: "astro.zap", power: 0.8 },
          visual(d, c, age) {
            stormFx(d, c, age, 3.0);
            if (age % 10 === 0) P(d, "cloud", up(c, 3.6), { color: mix(TAN, STORM, 0.5), count: 4, spread: 2.5, life: 1.2, size: 1.2 });
          },
          onPulse(foes, z) {
            const e = foes[z.pulses % Math.max(1, foes.length)];
            if (e && valid(e)) skyStrike(dim, ctx.ground(e.location), 0.8, VOLT, z.pulses % 2 === 0);
          },
          visualEvery: 2,
        });
      }, 24, 1.8);
    });
    ctx.every(9, 24, 1, (i) => { if (!landed) swirl(i + 8); });
    return 34;
  },

  // =========================================================================
  //  必殺「ガリレオの審判」
  //  0 時を止める（ultOpen）/ 4〜 鎚を天へ、左手で衛星を一つずつ指す（jupiter.judgement）/
  //  6〜 頭上に四衛星の輪 / 15 イオ（噴火）→ 24 エウロパ（氷）→ 33 ガニメデ（重力）→ 42 カリスト（衝突）を投げ、
  //  それぞれ 14 tick 後に着弾 / 56〜 狙いの上に嵐の雲が渦巻く / 60 跳んで振りかぶり /
  //  68 極大の雷霆（ケラウノス）が落ちて大地ごと打つ / 〜92 余韻
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 110, 16);
    const centre = ctx.aim(16);
    const base = up(ctx.loc(), 7.5);
    const fired = [false, false, false, false];
    ctx.at(4, () => body(p, "jupiter.judgement"));
    // 頭上の四衛星（投げるまで回る）
    ctx.at(6, () => {
      sound(dim, "astro.ring_spin", base, 0.7, 1.0);
      P(dim, "circle", base, { color: TAN, size: 2.6, life: 2.4, spin: 60 });
    });
    ctx.every(6, 24, 2, (i) => {
      const t = now();
      MOONS.forEach((m, k) => {
        if (fired[k]) return;
        const q = moonOrbitPos(base, k, t);
        P(dim, "glow", q, { color: m.color, size: 1.6, life: 0.14 });
        if (i % 2 === 0) P(dim, "trail", q, { color: white(m.color, 0.3), size: 1.0, life: 0.35 });
        if (i % 4 === k % 4) P(dim, "ring", q, { color: m.hot, size: 0.9, life: 0.2 });
      });
    });
    // 狙う相手（いなければ狙いの地点の周りへ）
    const pickTarget = (k) => {
      const foes = ctx.foes(16, up(centre, 1)).sort((a, b) => dist(a.location, centre) - dist(b.location, centre));
      if (foes.length) return foes[k % foes.length];
      return onGround(dim, add(centre, yawRotate(EAST, k * 90 + 45), k === 0 ? 0 : 2.6), 8);
    };
    const launch_ = (k, t, o) => {
      ctx.at(t, () => {
        const m = MOONS[k];
        const q = moonOrbitPos(base, k, now());
        fired[k] = true;
        const tgt = pickTarget(k);
        const tl = tgt && valid(tgt) ? { ...tgt.location } : (tgt && Number.isFinite(tgt.x) ? tgt : null);
        if (!tl) return;
        const g = onGround(dim, tl);
        const h = Math.max(5, q.y - g.y);
        sound(dim, "astro.swing", q, 0.6 + k * 0.1, 0.8);
        P(dim, "flare", q, { color: white(m.color, 0.4), size: 1.6, life: 0.2 });
        meteor(ctx, tl, {
          delay: 8, fall: 6, height: h, from: { x: (q.x - g.x) / h, z: (q.z - g.z) / h },
          color: m.color, size: 1.8 + k * 0.25, quiet: true, ...o,
        });
      });
    };
    // イオ: 噴火（溶岩の柱と火の粉、燃やす）
    launch_(0, 15, {
      radius: 3.6, damage: 4, hit: { color: IO_LAVA, up: 0.6, power: 1.8 },
      onImpact(g) {
        P(dim, "flare", up(g, 0.8), { color: white(IO, 0.4), size: 2.0, life: 0.25 });
        P(dim, "impact", up(g, 0.6), { color: IO_LAVA, size: 2.8, life: 0.2 });
        shock(dim, g, IO_LAVA, 3.6, { debris: 8 });
        P(dim, "pillar", up(g, 0.05), { color: IO_LAVA, size: 1.6, height: 7, life: 0.8 });
        P(dim, "flame", up(g, 0.3), { color: IO_LAVA, count: 14, spread: 1.2, speed: 4 });
        P(dim, "ember", up(g, 0.5), { color: IO, count: 22, speed: 8, size: 0.8 });
        P(dim, "smoke", up(g, 1.5), { color: [0.3, 0.24, 0.2], count: 8, speed: 2, size: 1.8, spread: 1 });
        sound(dim, "astro.explosion_big", g, 1.0, 1.2);
        sound(dim, "astro.flare", g, 0.8, 0.9);
        shake(dim, g, 18, 0.5, 0.35);
        for (const e of ctx.foes(3.8, up(g, 0.8))) {
          try { if (typeof e.setOnFire === "function") e.setOnFire(4, true); } catch (_) { }
        }
        for (let k = 0; k < 3; k++) {
          ctx.at(3 + k * 2, () => {
            const q = onGround(dim, add(g, yawRotate(EAST, k * 120 + 30), 1.8), 4);
            P(dim, "pillar", up(q, 0.05), { color: IO, size: 0.8, height: 4, life: 0.5 });
            P(dim, "ember", up(q, 0.4), { color: IO_LAVA, count: 8, speed: 6, size: 0.6 });
          });
        }
      },
    });
    // エウロパ: 氷（凍らせる）
    launch_(1, 24, {
      radius: 3.8, damage: 4, hit: { color: EUROPA, up: 0.3, power: 1.8, sound: "astro.ice_crack" },
      onImpact(g) {
        P(dim, "flare", up(g, 0.8), { color: white(EUROPA, 0.4), size: 2.0, life: 0.25 });
        P(dim, "impact", up(g, 0.6), { color: EUROPA, size: 2.6, life: 0.2 });
        shock(dim, g, [0.55, 0.85, 1.0], 3.8, { debris: 4 });
        P(dim, "ice", up(g, 0.8), { color: EUROPA, count: 16, speed: 6, spread: 0.8 });
        P(dim, "shard", up(g, 0.6), { color: [0.7, 0.9, 1.0], count: 14, speed: 7 });
        P(dim, "hex", up(g, 1.0), { color: white(EUROPA, 0.3), count: 10, spread: 1.6, size: 0.9, life: 0.8 });
        P(dim, "ring_flat", up(g, 0.1), { color: EUROPA, size: 2.2, life: 0.6 });
        sound(dim, "astro.ice_shatter", g, 0.9, 1.2);
        sound(dim, "astro.impact_heavy", g, 1.1, 0.8);
        shake(dim, g, 16, 0.4, 0.3);
        for (const e of ctx.foes(4.2, up(g, 0.8))) {
          freeze(e, 70, true);
          P(dim, "ice", chest(e), { color: EUROPA, count: 6, spread: 0.5, speed: 1 });
          P(dim, "hex", chest(e), { color: EUROPA, count: 5, spread: 0.6, size: 0.7, life: 1.2 });
        }
      },
    });
    // ガニメデ: 重力（一点へ吸い込んで押し潰す）
    launch_(2, 33, {
      radius: 4.0, damage: 3, hit: { color: GRAVITY, power: 1.6 },
      onImpact(g) {
        const c = up(g, 1.0);
        P(dim, "black_hole", c, { color: GRAVITY, size: 1.3, life: 0.9, spin: 320 });
        P(dim, "lens", c, { color: GRAVITY, size: 1.1, life: 0.6 });
        P(dim, "converge", c, { color: white(GRAVITY, 0.3), count: 20, spread: 4, life: 0.4 });
        shock(dim, g, GRAVITY, 4.0, { debris: 6 });
        sound(dim, "astro.gravity", g, 0.6, 1.3);
        sound(dim, "astro.explosion", g, 0.7, 0.9);
        shake(dim, g, 16, 0.4, 0.4);
        ctx.every(1, 4, 2, () => {
          for (const e of ctx.foes(6.5, c)) pull(e, g, 0.9, 0.04);
          ring(dim, "dot", g, 4.5, 18, { color: GRAVITY, size: 0.5, life: 0.2 }, 0.2);
        });
        ctx.at(9, () => {
          P(dim, "impact", c, { color: white(GRAVITY, 0.4), size: 2.4, life: 0.2 });
          P(dim, "shock_flat", up(g, 0.1), { color: GRAVITY, size: 1.6, life: 0.4 });
          P(dim, "dust", up(g, 0.1), { count: 16, speed: 4, size: 1.2 });
          sound(dim, "astro.impact_heavy", g, 0.6, 1.2);
          for (const e of ctx.foes(3.2, c)) {
            if (ctx.once(e, 1, "crush")) hit(ctx, e, 3, { color: GRAVITY, up: 0.1, power: 1.8, sound: "astro.hit_heavy" });
          }
        });
      },
    });
    // カリスト: 衝突（いちばん大きなクレーター）
    launch_(3, 42, {
      radius: 5.0, damage: 6, hit: { color: [1.0, 0.62, 0.3], kb: 1.0, up: 0.7, power: 2.0 },
      onImpact(g) {
        P(dim, "flare", up(g, 1.0), { color: white([1.0, 0.62, 0.3], 0.4), size: 2.6, life: 0.3 });
        P(dim, "impact", up(g, 0.8), { color: [1.0, 0.62, 0.3], size: 3.8, life: 0.22 });
        shock(dim, g, [1.0, 0.62, 0.3], 6, { debris: 20 });
        P(dim, "dust", up(g, 0.3), { count: 30, speed: 7, size: 1.6, spread: 1.5 });
        P(dim, "smoke", up(g, 0.8), { color: [0.32, 0.28, 0.26], count: 10, speed: 2.5, size: 2.2, spread: 1.6 });
        ring(dim, "debris", g, 3, 8, { count: 3, speed: 6 }, 0.3);
        sound(dim, "astro.explosion_big", g, 0.75, 1.5);
        sound(dim, "astro.impact_heavy", g, 0.6, 1.3);
        shake(dim, g, 24, 0.75, 0.5);
        flash(dim, g, 14, [1.0, 0.8, 0.6], 0.03, 0.45);
      },
    });
    // 極大の雷霆: 嵐の雲が渦巻き → 跳んで振り下ろす → 天を裂く雷
    ctx.at(54, () => {
      sound(dim, "astro.thunder", up(centre, 8), 0.55, 1.2);
      sound(dim, "astro.wind", centre, 0.5, 1.0);
      emblem(dim, up(centre, 0.07), KEY, { size: 4.0, life: 2.0, spin: 40 });
      P(dim, "hex_circle", up(centre, 0.06), { color: VOLT, size: 6.5, life: 1.8, spin: -30 });
    });
    ctx.every(54, 7, 2, (i) => {
      P(dim, "cloud", up(centre, 11), { color: mix(STORM, DEEP, 0.4), count: 6, spread: 6, life: 1.6, size: 1.8,
                                        dir: { x: 0, y: 0.02, z: 0 } });
      P(dim, "arc", up(centre, 10 + (i % 2)), { color: VOLT, count: 4, spread: 4, size: 1.6, life: 0.25 });
      P(dim, "warning", up(centre, 0.08), { color: [1, 0.3, 0.25], size: 7.5, life: 0.25 });
      P(dim, "converge", hammerTop(ctx), { color: VOLT, count: 10, spread: 2.4, life: 0.3 });
      if (i === 3) sound(dim, "astro.beam_charge", p.location, 0.6, 1.0);
    });
    ctx.at(60, () => body(p, "jupiter.thunderfall"));
    ctx.at(68, () => {
      const g = centre;
      for (const [dx, dz, s] of [[0, 0, 3.2], [0.7, 0.3, 1.8], [-0.6, -0.4, 1.6]]) {
        P(dim, "bolt", { x: g.x + dx, y: g.y + 0.05, z: g.z + dz }, { color: VOLT, dir: UPV, len: 24, size: s, life: 0.4 });
      }
      P(dim, "bolt", up(g, 0.05), { color: HOT, dir: UPV, len: 24, size: 1.2, life: 0.35 });
      P(dim, "pillar", up(g, 0.05), { color: HOT, size: 3.2, height: 16, life: 0.6 });
      P(dim, "lens", up(g, 1.5), { color: white(VOLT, 0.5), size: 3.0, life: 0.6 });
      P(dim, "flare", up(g, 1.2), { color: HOT, size: 3.0, life: 0.4 });
      shock(dim, g, VOLT, 9.5, { debris: 24 });
      zapLine(dim, hammerTop(ctx), up(g, 0.4), HOT, 0.8);
      sound(dim, "astro.thunder", g, 0.6, 1.9);
      sound(dim, "astro.explosion_big", g, 0.7, 1.5);
      sound(dim, "astro.impact_heavy", g, 0.55, 1.4);
      shake(dim, g, 32, 1.0, 0.8);
      flash(dim, g, 40, white(VOLT, 0.7), 0.1, 0.5);
      for (const e of ctx.foes(9.5, up(g, 1))) {
        if (ctx.once(e, 1, "keraunos")) {
          hit(ctx, e, 10, { color: VOLT, kb: 0.8, up: 0.95, dir: dirTo(g, e.location), power: 2.4, crit: true });
        }
      }
    });
    // 外の敵にも天から雷（輪のように内から外へ）
    for (let k = 0; k < 8; k++) {
      ctx.at(70 + k, () => {
        const q = onGround(dim, add(centre, yawRotate(EAST, k * 45 + 10), 5.2 + (k % 2) * 1.6), 6);
        skyStrike(dim, q, 1.2, VOLT, k % 3 !== 0);
      });
    }
    ctx.at(71, () => {
      for (const e of ctx.foes(16, up(centre, 1))) {
        if (hdist(e.location, centre) <= 9.5 || !ctx.once(e, 1, "outer")) continue;
        skyStrike(dim, ctx.ground(e.location), 1.2, VOLT, true);
        hit(ctx, e, 6, { color: VOLT, up: 0.5, power: 1.6 });
      }
    });
    ctx.at(72, () => {
      P(dim, "shock_flat", up(centre, 0.12), { color: white(VOLT, 0.3), size: 5.5, life: 0.7 });
      ring(dim, "star", centre, 7, 36, { color: HOT, size: 0.8, life: 0.8, speed: 3 }, 0.4);
    });
    ctx.every(74, 8, 3, (i) => {
      const q = add(centre, yawRotate(EAST, i * 67), 1.5 + i * 0.7);
      P(dim, "arc", up(q, 0.3), { color: VOLT, count: 3, spread: 1.2, size: 1.0, life: 0.3 });
      P(dim, "smoke", up(q, 0.4), { color: STORM, count: 2, speed: 1, size: 1.4 });
      if (i % 3 === 0) sound(dim, "astro.zap", q, 0.7 + i * 0.05, 0.5);
    });
    return 92;
  },

  // =========================================================================
  //  三段目「雷槌」: 叩きつけた鎚に天から落雷し、周りの敵を感電させる（全身モーションは combo3 が自動）
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    sound(dim, "astro.swing_heavy", p.location, 0.75, 1.0);
    ctx.at(2, () => {
      const top = hammerTop(ctx);
      P(dim, "converge", top, { color: VOLT, count: 8, spread: 1.4, life: 0.25 });
      P(dim, "arc", top, { color: HOT, count: 3, spread: 0.5, life: 0.2 });
    });
    ctx.at(7, () => {
      const g = ctx.ground(ctx.local(2.0, 0, 0));
      skyStrike(dim, g, 1.3);
      shock(dim, g, VOLT, 3.2, { debris: 6 });
      P(dim, "flare", up(g, 0.6), { color: HOT, size: 1.4, life: 0.2 });
      sound(dim, "astro.impact_heavy", g, 1.0, 0.9);
      shake(dim, g, 10, 0.35, 0.25);
      const foes = ctx.foes(3.4, up(g, 0.9));
      if (valid(target) && !foes.some((e) => e.id === target.id) && dist(target.location, g) < 5) foes.push(target);
      for (const e of foes) {
        zapLine(dim, up(g, 0.4), chest(e), VOLT, 0.5);
        P(dim, "arc", chest(e), { color: HOT, count: 3, spread: 0.5, life: 0.3 });
        hit(ctx, e, 5, { color: VOLT, kb: 0.6, up: 0.35, dir: dirTo(g, e.location), power: 1.3, sound: "astro.zap" });
        freeze(e, 10);
      }
    });
    return 12;
  },

  // =========================================================================
  //  変身の締め: 落雷が三度（左右、最後に真上から本人へ）、胸の大赤斑が渦巻く
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    const f = ctx.f;
    emblem(dim, up(g, 0.05), KEY, { size: 1.8, life: 1.8 });
    sound(dim, "astro.wind", g, 0.7, 0.8);
    [[0, 2.4, -60], [4, 2.4, 60], [8, 0, 0]].forEach(([t, d, a], k) => {
      ctx.at(t, () => {
        const q = d > 0 ? onGround(dim, add(g, yawRotate(f, a), d), 4) : g;
        skyStrike(dim, q, k === 2 ? 1.6 : 1.1);
        if (k === 2) {
          P(dim, "flare", ctx.chest(), { color: HOT, size: 1.6, life: 0.3 });
          shock(dim, g, VOLT, 3.0);
          shake(dim, g, 10, 0.4, 0.35);
          flash(dim, g, 8, white(VOLT, 0.6), 0.02, 0.45);
        }
      });
    });
    ctx.every(9, 6, 2, (i) => {
      const c = ctx.chest();
      P(dim, "orbit", c, { color: i % 2 ? GRS : CREAM, count: 8, spread: 0.9, life: 0.5, spin: 720 });
      P(dim, "plasma", c, { color: GRS_HOT, count: 1, size: 0.9, life: 0.3, spin: 540 });
      if (i % 2 === 0) P(dim, "arc", up(c, 0.8), { color: VOLT, count: 3, spread: 0.7, life: 0.2 });
    });
    ctx.at(10, () => {
      P(dim, "vortex", up(g, 0.1), { color: GRS, spread: 1.6, height: 3.2, rate: 60, life: 0.8, spin: 720 });
      ring(dim, "dot", g, 2.4, 24, { color: TAN, size: 0.5, life: 0.5, speed: 2 }, 0.2);
      sound(dim, "astro.gust", g, 0.9, 0.8);
    });
    return 22;
  },

  // =========================================================================
  //  パッシブ static: 当たるたびに 1、攻撃を受けても 1 溜まり、5 で連鎖放電
  // =========================================================================
  passive: {
    tick(p, st) {
      const n = st.charge ?? 0;
      const dim = p.dimension;
      const f = flatDir(p);
      const r = rightOf(f);
      const l = p.location;
      if (n > 0 && st.n % 2 === 0) {
        for (const s of [-1, 1]) {
          const q = { x: l.x + r.x * 0.62 * s - f.x * 0.05, y: l.y + 1.92, z: l.z + r.z * 0.62 * s - f.z * 0.05 };
          P(dim, "arc", q, { color: n >= 4 ? HOT : VOLT, count: Math.min(4, n), spread: 0.1 + 0.05 * n,
                             size: 0.32 + 0.05 * n, life: 0.2 });
        }
        if (n >= 4 && st.n % 4 === 0) sound(dim, "astro.zap", up(l, 1.8), 1.8, 0.2);
      } else if (st.n % 8 === 0 && fxScale() >= 1) {
        // 待機中: 肩のコイルの間を時々弱い放電が渡る
        const a = { x: l.x + r.x * 0.62, y: l.y + 1.9, z: l.z + r.z * 0.62 };
        const b = { x: l.x - r.x * 0.62, y: l.y + 1.9, z: l.z - r.z * 0.62 };
        if (Math.random() < 0.3) zapLine(dim, a, lerp3(a, b, 0.35), VOLT, 0.2);
      }
    },
    onHit(p, target, dmg, ctx) {
      const ps = staticOf(p);
      const n = (ps.charge ?? 0) + 1;
      if (valid(target)) P(p.dimension, "arc", chest(target), { color: VOLT, count: 1, spread: 0.3, size: 0.6, life: 0.15 });
      // 5 回目で放電。放電の後 1 秒は溜まっても 4 で止まる（多段の技で放電が続かないように）
      if (n < 5 || now() < (ps.dischargeAt ?? -99) + 20) { ps.charge = Math.min(4, n); return; }
      ps.charge = 0;
      ps.dischargeAt = now();
      discharge(p, target);
    },
    onHurt(p, attacker, dmg) {
      const ps = staticOf(p);
      ps.charge = Math.min(4, (ps.charge ?? 0) + 1);
      P(p.dimension, "arc", chest(p), { color: VOLT, count: 2, spread: 0.6, size: 0.6, life: 0.2 });
    },
    onKill(p, victim) {
      if (!valid(victim)) return;
      const q = chest(victim);
      P(p.dimension, "arc", q, { color: VOLT, count: 4, spread: 0.6, life: 0.3 });
      P(p.dimension, "spark", q, { color: HOT, count: 6, speed: 4 });
    },
  },
});
