// ===========================================================================
//  太陽 ソル・オーバードライブ（SOL OVERDRIVE）— 第 9 形態・恒星そのもの
//
//  白金と金の装甲、頭の後ろで回る棘のコロナの光輪、肩と背の紅炎（プロミネンス）、胸の核融合炉。
//  ナノウェポンは片手で振るう大剣「紅炎剣 プロミネンス・ブレイド」。
//  色: 発光 = 太陽の橙（SUN = ctx.c）/ 白熱（HOT = ctx.light）/ 金（GOLD）/ 紅炎（FLARE = ctx.accent）/
//      紅（CRIMSON）/ プラズマ（PLASMA）/ 超新星の芯の青白（NOVA。必殺の決め所だけ）
//
//   惑星技  ソーラー・フレア       剣を天に掲げて掌に太陽を溜め（0〜8）、前方の扇形をフレアで薙ぎ払う（9）。
//                                  焼かれた敵は燃え上がり、閃光で目が眩む（盲目・鈍化）。白い眩しさが遅れて弾ける（12）
//   機動技  コロナ・ドライブ       コロナの球をまとって突進（0〜13、ほぼ無敵）。触れた敵を焼いて弾き、
//                                  通った跡に 2.5 秒燃え続ける炎の軌跡を残す。最後に斬り上げの火柱（13）
//   空中技  プロミネンス・アーチ   宙で止まり、紅炎のループを三本、前方へ順に叩きつける（5 / 9 / 14）。
//                                  ループは地面から立ち上がって前へ倒れ込み、着いた所で炎の弧が爆ぜる
//   必殺    スーパーノヴァ         時を止め（ultOpen）、宙に浮いて周りの物を引き寄せながら恒星の核へ収縮（0〜49。
//                                  time_stop の止まる音 = 25 で内破、重力で押し潰す）。超新星の音の爆発（50）で
//                                  全周を吹き飛ばし、三重の衝撃波・噴出物・青白い芯の閃光、最後に残骸の星雲が漂う
//   三段目  紅炎の弧               縦の炎の弧で前方 5m を焼き払い、地を這う炎が走る
//   変身の締め 収縮した光が一気に膨らみ、コロナの輪が三重に広がる
//   パッシブ corona               体のまわりにコロナを纏い、1 秒ごとに 3.6m 以内の敵対的な相手を焦がす。
//                                  通常攻撃は相手に火をつけ、殴ってきた相手はコロナが焼き返す（1 秒に 1 回）
//
//  当たりは全て hit(ctx|p, e, 素の値, {...})。自動で狙うパッシブは hostilesNear（村人・動物・他人を焼かない）。
//  ローカルの補助（engine に無い物）: ignite（setOnFire があれば火をつける）・archPts（倒れ込むループの点）
// ===========================================================================
import {
  register, lunge, hover, ultOpen, zone, dirTo,
} from "../engine.js";
import {
  P, line, ring, arc, shock, emblem, flash, shake, sound, body, white, mix, afterimage, status, fxScale,
} from "../fx.js";
import { hit, hostilesNear, pull } from "../combat.js";
import {
  add, sub, up, norm, lerp3, yawRotate, yawDeg, rightOf, chest, dist, effect, onGround, valid, now,
} from "../util.js";

const KEY = "sol";
const SUN = [1.0, 0.675, 0.157];
const HOT = [1.0, 0.98, 0.87];
const GOLD = [1.0, 0.84, 0.32];
const FLARE = [1.0, 0.36, 0.1];
const CRIMSON = [0.78, 0.13, 0.05];
const PLASMA = [1.0, 0.52, 0.12];
const NOVA = [0.74, 0.9, 1.0];
const EAST = { x: 1, y: 0, z: 0 };

/** 相手に火をつける（setOnFire が無い版では何もしない。ブロックには燃え移らない）。 */
function ignite(e, seconds) {
  try { if (valid(e) && typeof e.setOnFire === "function") e.setOnFire(seconds, true); } catch (_) { }
}

/** 小さな太陽（溜めの芯・噴出の頭）。 */
function sunOrb(dim, q, s, i = 0) {
  P(dim, "glow", q, { color: HOT, size: s * 1.3, life: 0.16 });
  P(dim, "plasma", q, { color: i % 2 ? SUN : PLASMA, size: s * 0.8, life: 0.26, spin: 720 });
  if (i % 3 === 0) P(dim, "ring", q, { color: FLARE, size: s * 0.7, life: 0.2 });
}

/**
 * 紅炎のループの点列: 足 a・b を結ぶ半円が、高さ h で立ち、theta 度だけ前（f）へ倒れた形。
 * theta = 0 で垂直に立ち、90 で地面に伏せる。
 */
function archPts(a, b, h, f, theta, n = 7) {
  const mid = lerp3(a, b, 0.5);
  const half = dist(a, b) / 2;
  const L = norm(sub(b, a));
  const th = theta * Math.PI / 180;
  const V = { x: f.x * Math.sin(th), y: Math.cos(th), z: f.z * Math.sin(th) };
  const out = [];
  for (let i = 0; i <= n; i++) {
    const s = i / n * Math.PI;
    const c = -Math.cos(s) * half, k = Math.sin(s) * h;
    out.push({ x: mid.x + L.x * c + V.x * k, y: mid.y + L.y * c + V.y * k, z: mid.z + L.z * c + V.z * k });
  }
  return out;
}

/** ループを描く（点ごとの炎と、点の間を埋める光の線）。 */
function drawArch(dim, pts, hot, big) {
  for (let i = 0; i < pts.length; i++) {
    const q = pts[i];
    P(dim, "flame", q, { color: i % 2 ? FLARE : SUN, count: big ? 3 : 2, spread: 0.25, size: big ? 1.5 : 1.2, life: 0.35 });
    if (i < pts.length - 1) line(dim, "glow", q, pts[i + 1], 0.35, { color: hot ? HOT : PLASMA, size: big ? 0.9 : 0.7, life: 0.12 });
  }
}

/** 扇形（中心の向き f・半角 deg）の地面の縁の線（予告）。 */
function fanEdges(dim, g, f, range, deg, color) {
  for (const s of [-1, 1]) {
    const d = yawRotate(f, s * deg);
    line(dim, "dot", up(g, 0.08), up(add(g, d, range), 0.08), 0.5, { color, size: 0.55, life: 0.45 });
  }
}

const retaliate = new Map();   // playerId -> 次にコロナが焼き返せる tick

register(KEY, {
  // =========================================================================
  //  惑星技「ソーラー・フレア」
  //  剣を天に掲げ、左の掌の前に小さな太陽を溜める（0〜8。地面に扇の予告線）。9 で前方の扇形（8.5m・半角 55°）を
  //  フレアで薙ぎ払い、10〜13 で炎の波面が扇に広がる。当たった敵は燃え、閃光で目が眩む。12 で白い眩しさが弾ける
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "sol.solar_flare");
    sound(dim, "astro.corona", p.location, 1.25, 0.9);
    sound(dim, "astro.beam_charge", p.location, 1.1, 0.6);
    ctx.every(0, 5, 2, (i) => {
      const palm = ctx.local(1.0, -0.15, 1.35);
      sunOrb(dim, palm, 0.45 + i * 0.16, i);
      P(dim, "converge", palm, { color: i % 2 ? SUN : HOT, count: 10, spread: 1.8, life: 0.35, size: 0.7 });
      P(dim, "ember", ctx.local(0.2, 0.4, 2.6), { color: SUN, count: 4, spread: 0.4, speed: 1.4 });
      if (i === 1 || i === 3) fanEdges(dim, ctx.ground(ctx.loc()), ctx.liveDir(), 8.5, 55, FLARE);
      status(p, `§6☀ §fSOLAR FLARE §6${"▰".repeat(i + 1)}§8${"▱".repeat(4 - i)}`, 4);
    });
    ctx.at(9, () => {
      const f = ctx.liveDir();
      const c0 = ctx.chest();
      const g0 = ctx.ground(ctx.loc());
      const rot = yawDeg(f);
      sound(dim, "astro.flare", c0, 1.0, 1.4);
      sound(dim, "astro.swing_heavy", c0, 0.8, 1.0);
      sound(dim, "astro.explosion", c0, 1.4, 0.6);
      shake(dim, c0, 10, 0.4, 0.3);
      flash(dim, add(c0, f, 3), 7, white(SUN, 0.55), 0.04, 0.45);
      // 放つ瞬間: 掌の前の閃光と、扇の薙ぎ払い
      P(dim, "flare", add(c0, f, 1.2), { color: HOT, size: 3.2, life: 0.3, rot: 0 });
      P(dim, "impact", add(c0, f, 1.2), { color: white(SUN, 0.3), size: 2.2, life: 0.18 });
      P(dim, "slash_big", add(c0, f, 2.0), { color: SUN, rot: rot + 90, size: 1.4, life: 0.35, var: 1 });
      arc(dim, c0, f, 2.6, 70, -70, 6, FLARE, { size: 1.3, steps: 12, life: 0.3 });
      // 当たり: 扇形の中の敵を焼いて押し、目を眩ませる
      for (const e of ctx.cone(8.5, 55, c0, f)) {
        if (!ctx.once(e, 1, "flare")) continue;
        hit(ctx, e, 11, { color: SUN, kb: 1.0, up: 0.3, dir: f, power: 1.7, sound: "astro.hit_heavy" });
        if (!valid(e)) continue;
        effect(e, "blindness", 70, 0);
        effect(e, "slowness", 50, 1);
        ignite(e, 5);
        const q = chest(e);
        P(dim, "flame", q, { color: FLARE, count: 6, spread: 0.4, size: 1.1 });
        P(dim, "flare", up(q, 0.4), { color: HOT, size: 1.0, life: 0.2 });
      }
    });
    // 炎の波面が扇に広がる（距離ごとに 1 tick ずつ）
    ctx.every(10, 4, 1, (i) => {
      const f = ctx.liveDir();
      const o = ctx.loc();
      const d = 2.0 + i * 2.0;
      for (let k = -2; k <= 2; k++) {
        const q = add(o, yawRotate(f, k * 24), d);
        P(dim, "flame", up(q, 0.9), { color: k % 2 ? FLARE : SUN, count: 4, spread: 0.6 + i * 0.15, size: 1.3 + i * 0.15, life: 0.45 });
      }
      P(dim, "plasma", up(add(o, f, d), 1.0), { color: PLASMA, size: 1.2 + i * 0.4, life: 0.3 });
      P(dim, "ember", up(add(o, f, d), 0.8), { color: GOLD, count: 8, spread: 1.0 + i * 0.5, speed: 2.5 });
      if (i === 3) {
        const g = ctx.ground(add(o, f, d));
        P(dim, "ring_flat", up(g, 0.08), { color: CRIMSON, size: 2.4, life: 0.6 });
        P(dim, "smoke", up(g, 0.4), { count: 6, spread: 2.0, speed: 1.0, size: 1.4 });
      }
    });
    // 眩しさ: 遅れて扇の中ほどで白い光が弾ける
    ctx.at(12, () => {
      const f = ctx.liveDir();
      const q = add(ctx.chest(), f, 4.5);
      P(dim, "lens", q, { color: white(SUN, 0.6), size: 1.6, life: 0.45 });
      P(dim, "flare", q, { color: HOT, size: 2.6, life: 0.25, rot: 0 });
      P(dim, "star", q, { color: HOT, count: 10, spread: 2.4, life: 0.6 });
      sound(dim, "astro.corona", q, 1.6, 0.5);
    });
    return 22;
  },

  // =========================================================================
  //  機動技「コロナ・ドライブ」
  //  コロナの球（輪・プラズマ・炎）をまとって突進する（0〜13。ほぼ無敵・触れた敵を焼いて弾く）。
  //  通った跡に燃え続ける炎の軌跡（2.5 秒。中の敵を焼き続ける）。13 で斬り上げの火柱と爆発
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    const r = ctx.r;
    body(p, "sol.corona_drive");
    sound(dim, "astro.boost", p.location, 0.85, 1.0);
    sound(dim, "astro.corona", p.location, 1.4, 0.9);
    sound(dim, "astro.flare", p.location, 1.5, 0.5);
    effect(p, "resistance", 16, 3);
    P(dim, "ring", ctx.chest(), { color: SUN, size: 1.8, life: 0.25 });
    P(dim, "flare", ctx.chest(), { color: HOT, size: 1.6, life: 0.2 });
    ctx.every(0, 6, 2, () => lunge(ctx, f, 1.15, 0.05));
    let lastTrail = null;
    ctx.every(0, 14, 1, (i) => {
      const c0 = ctx.chest();
      // コロナの球: 水平の輪・縦の輪・芯のプラズマ・後ろへなびく炎
      ring(dim, "glow", c0, 1.25, 22, { color: i % 2 ? SUN : GOLD, size: 0.8, life: 0.12 }, 0.05);
      P(dim, "ring_n", c0, { color: FLARE, dir: f, spread: 1.3, count: 18, size: 0.7, life: 0.12 });
      P(dim, "plasma", c0, { color: PLASMA, size: 1.4, life: 0.15, spin: 900 });
      P(dim, "flame", add(c0, f, -0.9), { color: FLARE, count: 3, spread: 0.5, size: 1.3, life: 0.3 });
      P(dim, "speedline", c0, { color: SUN, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 16, spread: 0.8 });
      if (i % 3 === 0) afterimage(dim, p.location, i % 2 ? FLARE : SUN, 0.35);
      // 炎の軌跡: 3 tick ごとに地面へ燃える跡を置く（2.5 秒、中の敵を焼く）
      const g = ctx.ground(ctx.loc());
      if (i % 3 === 0 && (!lastTrail || dist(g, lastTrail) > 1.2)) {
        lastTrail = g;
        zone(ctx, g, {
          radius: 1.35, ticks: 50, every: 10, damage: 2, height: 2.0,
          hit: { color: FLARE, power: 0.6, nova: 1, xp: 1 },
          effects: [["slowness", 15, 0]],
          visual(d, cz, age) {
            const fade = 1 - age / 50;
            P(d, "flame", up(cz, 0.2), { color: age % 4 ? FLARE : SUN, count: 3, spread: 0.7, size: 0.8 + fade * 0.7, life: 0.5 });
            if (age % 6 === 0) P(d, "ember", up(cz, 0.3), { color: GOLD, count: 4, spread: 0.8, speed: 1.2 });
            if (age % 10 === 0) P(d, "smoke", up(cz, 0.6), { count: 2, spread: 0.6, speed: 0.8, size: 1.0 });
          },
          onPulse(enemies) { for (const e of enemies) ignite(e, 2); },
        });
        P(dim, "ring_flat", up(g, 0.08), { color: CRIMSON, size: 1.1, life: 0.4 });
      }
      // 触れた敵: 焼いて横へ弾く
      for (const e of ctx.foes(2.5, c0)) {
        if (!ctx.once(e, 1, "drive")) continue;
        const side = (e.location.x - c0.x) * r.x + (e.location.z - c0.z) * r.z >= 0 ? 1 : -1;
        const away = norm({ x: f.x * 0.5 + r.x * side, y: 0, z: f.z * 0.5 + r.z * side });
        hit(ctx, e, 8, { color: SUN, kb: 1.7, up: 0.5, dir: away, power: 1.6, sound: "astro.hit_heavy" });
        if (!valid(e)) continue;
        ignite(e, 4);
        P(dim, "flame", chest(e), { color: FLARE, count: 6, spread: 0.4, size: 1.1 });
        sound(dim, "astro.flare", chest(e), 1.7, 0.5);
      }
    });
    // 斬り上げの火柱
    ctx.at(13, () => {
      const at = ctx.local(1.4, 0, 0);
      const g = ctx.ground(at);
      sound(dim, "astro.explosion", g, 1.1, 1.0);
      sound(dim, "astro.swing_heavy", g, 1.0, 0.9);
      shake(dim, g, 12, 0.45, 0.3);
      P(dim, "pillar", up(g, 0.05), { color: SUN, size: 1.6, height: 7, life: 0.55 });
      P(dim, "pillar", up(g, 0.05), { color: HOT, size: 0.7, height: 8, life: 0.4 });
      P(dim, "slash_big", up(g, 1.6), { color: FLARE, rot: yawDeg(f) + 90, size: 1.1, life: 0.35 });
      P(dim, "flame", up(g, 0.5), { color: FLARE, count: 10, spread: 1.0, size: 1.6, speed: 3 });
      P(dim, "ember", up(g, 0.5), { color: GOLD, count: 16, spread: 1.0, speed: 5 });
      shock(dim, g, SUN, 3.2, { debris: 6 });
      for (const e of ctx.foes(3.2, up(g, 1.0))) {
        if (!ctx.once(e, 1, "rise")) continue;
        hit(ctx, e, 5, { color: SUN, kb: 0.4, up: 0.85, dir: f, power: 1.4 });
        ignite(e, 3);
      }
    });
    return 18;
  },

  // =========================================================================
  //  空中技「プロミネンス・アーチ」
  //  宙で止まり（hover）、紅炎のループを三本、前方 3.2 / 5.8 / 9m へ順に叩きつける（5 / 9 / 14）。
  //  ループは地面から立ち上がり（後ろへ反る → 垂直 → 前へ倒れ込む）、伏せた所で炎の弧が爆ぜる。
  //  着く場所には 6 tick 前から予告の線。三本目は大きく、衝撃波が広がる
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 24, 0.28);
    body(p, "sol.prominence");
    sound(dim, "astro.corona", p.location, 1.0, 1.0);
    sound(dim, "astro.beam_charge", p.location, 0.75, 0.6);
    const f = ctx.f;
    const r = ctx.r;
    const o = ctx.loc();
    // [叩きつける tick, 前への距離, 半幅, 高さ, 素のダメージ]。一・二本目は浮かせて次のループの通り道に残す
    const ARCHES = [[5, 3.2, 2.3, 3.0, 7], [9, 5.8, 2.6, 3.4, 7], [14, 9.0, 3.0, 4.4, 11]];
    ARCHES.forEach(([t, dist0, half, h, dmg], k) => {
      const big = k === 2;
      const mid = onGround(dim, add(o, f, dist0), 14);
      const a = add(mid, r, -half);
      const b = add(mid, r, half);
      // 予告: 着く所に横一文字の点線と、紅の輪
      ctx.at(Math.max(0, t - 6), () => {
        line(dim, "dot", up(a, 0.08), up(b, 0.08), 0.4, { color: FLARE, size: 0.6, life: 0.4 });
        P(dim, "ring_flat", up(add(mid, f, h * 0.5), 0.07), { color: CRIMSON, size: h * 0.9, life: 0.35 });
      });
      // 剣から紅炎が飛び出す
      ctx.at(Math.max(0, t - 4), () => {
        const tip = ctx.local(1.2, 0.3, 1.8);
        sunOrb(dim, tip, big ? 1.0 : 0.7, k);
        sound(dim, "astro.swing_heavy", tip, 0.9 + k * 0.08, 0.9);
        sound(dim, "astro.flare", tip, 1.2 - k * 0.12, 0.7);
      });
      // 立ち上がって倒れ込む（3 tick）
      [[-25, t - 3], [10, t - 2], [55, t - 1]].forEach(([theta, tt]) => {
        ctx.at(Math.max(0, tt), () => drawArch(dim, archPts(up(a, 0.1), up(b, 0.1), h, f, theta), theta > 30, big));
      });
      // 叩きつけ
      ctx.at(t, () => {
        const pts = archPts(up(a, 0.15), up(b, 0.15), h, f, 90, 6);
        const centre = add(mid, f, h * 0.45);
        for (const q of pts) P(dim, "flame", up(q, 0.3), { color: FLARE, count: big ? 5 : 4, spread: 0.4, size: big ? 1.8 : 1.4, speed: 2 });
        for (const q of [a, b]) {
          P(dim, "pillar", up(q, 0.05), { color: SUN, size: big ? 1.3 : 1.0, height: big ? 6 : 4.5, life: 0.5 });
          P(dim, "flame", up(q, 0.5), { color: HOT, count: 4, spread: 0.3, size: 1.4, speed: 3 });
        }
        P(dim, "impact", up(centre, 0.6), { color: white(SUN, 0.3), size: big ? 3.0 : 2.0, life: 0.2 });
        P(dim, "ember", up(centre, 0.4), { color: GOLD, count: big ? 24 : 14, spread: h * 0.5, speed: 5 });
        shock(dim, centre, big ? FLARE : SUN, big ? 5.5 : 3.4, { debris: big ? 12 : 6 });
        sound(dim, big ? "astro.explosion_big" : "astro.explosion", centre, big ? 0.9 : 1.1, big ? 1.3 : 1.0);
        sound(dim, "astro.impact_heavy", centre, 1.0 - k * 0.1, 1.0);
        shake(dim, centre, big ? 22 : 14, big ? 0.7 : 0.4, big ? 0.5 : 0.3);
        if (big) {
          flash(dim, centre, 14, white(FLARE, 0.4), 0.04, 0.45);
          P(dim, "lens", up(centre, 1.2), { color: white(SUN, 0.5), size: 1.8, life: 0.4 });
          P(dim, "smoke", up(centre, 0.6), { count: 10, spread: 2.2, speed: 1.4, size: 1.8 });
        }
        for (const e of ctx.foes(h * 0.5 + 2.4, up(centre, 0.8))) {
          if (!ctx.once(e, 1, `arch${k}`)) continue;
          hit(ctx, e, dmg, { color: FLARE, kb: big ? 1.4 : 0.3, up: big ? 0.8 : 0.62, dir: f, power: big ? 2.0 : 1.5,
                             sound: big ? "astro.hit_heavy" : "astro.hit" });
          ignite(e, big ? 5 : 3);
        }
      });
    });
    return 20;
  },

  // =========================================================================
  //  必殺「スーパーノヴァ」（この アドオンでいちばん大きな演出）
  //    0  時を止める（ultOpen: カットイン・time_stop・無敵・周りの足止め）。宙へ浮き、足元に陣
  //   2〜24 周りの光と物を吸い寄せる（収束の筋・縮む炎の輪・軌道の光）。敵を中心へ引き寄せる
  //   10  身を丸める（sol.nova_collapse）。17 で supernova を鳴らす（1.66 秒後 = 50 で爆発）
  //   25  time_stop の止まる音に合わせて内破。28〜46 重力で押し潰す（6 tick ごと）。星が白く縮み、
  //       36 で黒い芯（中性子星）。40・44 で地面に光の亀裂。臨界のメーターが満ちる
  //   50  超新星爆発（sol.nova_burst）: 白金の閃光・十字のフレア・柱・紋章・噴出物・全周を吹き飛ばす
  //  51〜60 三重の衝撃波（球殻の輪が広がる）。54 で二の波
  //  58〜80 残骸の星雲（紅と金の雲）・降る火の粉・焦げた地面
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 90, 16);
    const centre = ctx.ground(ctx.loc());
    const BOOM = 50;
    let core = up(centre, 2.6);
    const coreNow = () => { core = up(ctx.loc(), 1.1); return core; };
    ctx.at(1, () => {
      hover(ctx, 60, 0.5);
      P(dim, "hex_circle", up(centre, 0.06), { color: CRIMSON, size: 5.5, life: 3.4, spin: -40 });
      P(dim, "circle", up(centre, 0.05), { color: GOLD, size: 7.5, life: 3.4, spin: 25 });
      emblem(dim, up(centre, 0.07), KEY, { size: 4.2, life: 3.6, spin: 30 });
      sound(dim, "astro.corona", centre, 0.8, 1.2);
    });
    ctx.at(8, () => sound(dim, "astro.gravity", centre, 0.6, 1.0));
    ctx.at(10, () => body(p, "sol.nova_collapse"));
    ctx.at(BOOM - 33, () => sound(dim, "astro.supernova", centre, 1.0, 1.6));
    ctx.at(26, () => hover(ctx, 34, 0.08));
    // ---- 収束（2〜24）: 吸い込む筋・縮む炎の輪・軌道の光 ----
    ctx.every(2, 12, 2, (i) => {
      const c0 = coreNow();
      P(dim, "converge", c0, { color: i % 2 ? SUN : HOT, count: 18, spread: 7 - i * 0.3, life: 0.5, size: 1.1 });
      P(dim, "orbit", c0, { color: PLASMA, count: 10, spread: 2.4 - i * 0.08, life: 0.5, spin: 520 });
      P(dim, "plasma", c0, { color: SUN, size: 1.2 + i * 0.12, life: 0.25, spin: 600 });
      ring(dim, "glow", centre, Math.max(1.5, 10 - i * 0.75), 36, { color: i % 2 ? FLARE : GOLD, size: 1.1, life: 0.22 }, 0.15);
      if (i % 3 === 0) P(dim, "vortex", centre, { color: FLARE, rate: 50, life: 0.6, spread: 3.2, height: 4, spin: -600 });
    });
    // ---- 引き寄せ（4〜46）。敵から核へ光の糸 ----
    ctx.every(4, 15, 3, (i) => {
      const c0 = coreNow();
      const list = ctx.foes(16, c0);
      for (let k = 0; k < list.length; k++) {
        const e = list[k];
        if (!valid(e)) continue;
        pull(e, centre, 0.3 + i * 0.02, 0.06);
        if (k < 6 && i % 2 === 0) line(dim, "trail", chest(e), c0, 0.6, { color: FLARE, size: 0.45, life: 0.2 });
      }
    });
    // ---- 内破（25）: time_stop の止まる音 ----
    ctx.at(25, () => {
      const c0 = coreNow();
      P(dim, "converge", c0, { color: HOT, count: 32, spread: 11, life: 0.6, size: 1.6 });
      P(dim, "lens", c0, { color: NOVA, size: 2.2, life: 0.5 });
      P(dim, "ring", c0, { color: HOT, size: 4, life: 0.3 });
      sound(dim, "astro.impact_heavy", c0, 0.5, 1.2);
      sound(dim, "astro.gravity", c0, 0.45, 1.2);
      shake(dim, c0, 24, 0.3, 0.3);
    });
    // ---- 収縮する星（26〜49） ----
    ctx.every(26, 24, 1, (i) => {
      const c0 = coreNow();
      const s = Math.max(0.55, 3.0 - i * 0.11);
      P(dim, "glow", c0, { color: i > 18 && i % 2 ? NOVA : HOT, size: s * 2.2, life: 0.12 });
      if (i % 2 === 0) P(dim, "plasma", c0, { color: SUN, size: s * 1.1, life: 0.2, spin: 900 });
      if (i % 3 === 0) P(dim, "ring", c0, { color: PLASMA, size: s, life: 0.18 });
      if (i % 4 === 1) P(dim, "converge", c0, { color: FLARE, count: 12, spread: 4.5, life: 0.35, size: 0.9 });
      if (i % 4 === 0) {
        const fill = Math.min(5, 1 + Math.floor(i / 5));
        status(p, `§6☀ §fSUPERNOVA §c臨界 §6${"▰".repeat(fill)}§8${"▱".repeat(5 - fill)}`, 6);
      }
    });
    ctx.at(36, () => {
      const c0 = coreNow();
      P(dim, "black_hole", c0, { size: 0.45, life: 0.8, spin: 720 });
      P(dim, "lens", c0, { color: NOVA, size: 0.9, life: 0.8 });
      sound(dim, "astro.gravity", c0, 0.8, 0.9);
    });
    // ---- 重力で押し潰す（28〜46）----
    ctx.every(28, 4, 6, () => {
      const c0 = coreNow();
      for (const e of ctx.foes(13, c0)) {
        if (!ctx.once(e, 4, "crush")) continue;
        hit(ctx, e, 2.5, { color: FLARE, pull: centre, kb: 0.35, up: 0.05, power: 0.8, nova: 0 });
      }
    });
    // ---- 臨界: 地面の光の亀裂と、高まる揺れ ----
    for (const [t, col] of [[40, FLARE], [44, GOLD], [47, HOT]]) {
      ctx.at(t, () => {
        for (let k = 0; k < 8; k++) {
          const d = yawRotate(EAST, k * 45 + t * 7);
          line(dim, "dot", up(centre, 0.1), up(add(centre, d, 5 + (t - 40) * 1.2), 0.1), 0.6, { color: col, size: 0.6, life: 0.35 });
        }
        shake(dim, centre, 26, 0.12 + (t - 40) * 0.03, 0.25);
        P(dim, "ring_flat", up(centre, 0.1), { color: col, size: 1.5, life: 0.3 });
      });
    }
    // ---- 超新星（50） ----
    ctx.at(BOOM, () => {
      const c0 = coreNow();
      const g = ctx.ground(ctx.loc());
      body(p, "sol.nova_burst");
      sound(dim, "astro.explosion_big", c0, 0.7, 1.6);
      sound(dim, "astro.flare", c0, 0.6, 1.4);
      sound(dim, "astro.impact_heavy", c0, 0.6, 1.4);
      flash(dim, c0, 48, [1.0, 0.96, 0.84], 0.12, 0.7);
      shake(dim, c0, 48, 1.2, 1.0);
      P(dim, "lens", c0, { color: HOT, size: 5, life: 0.8 });
      P(dim, "flare", c0, { color: HOT, size: 5, life: 0.45, rot: 0 });
      P(dim, "flare", c0, { color: SUN, size: 3.5, life: 0.4, rot: 90 });
      P(dim, "impact", c0, { color: white(SUN, 0.4), size: 4.5, life: 0.25 });
      P(dim, "glow", c0, { color: white(SUN, 0.5), size: 12, life: 0.3 });
      P(dim, "plasma", c0, { color: FLARE, size: 3.2, life: 0.6, spin: 400 });
      P(dim, "ring", c0, { color: PLASMA, size: 7, life: 0.5 });
      P(dim, "shock_flat", up(g, 0.08), { color: HOT, size: 6.5, life: 0.7 });
      P(dim, "pillar", up(g, 0.05), { color: HOT, size: 3.0, height: 24, life: 0.9 });
      P(dim, "pillar", up(g, 0.05), { color: SUN, size: 5.0, height: 16, life: 0.8 });
      emblem(dim, up(g, 0.09), KEY, { size: 6, life: 2.0, spin: 60 });
      P(dim, "spark", c0, { color: GOLD, count: 40, speed: 14, size: 1.4 });
      P(dim, "ember", c0, { color: SUN, count: 40, spread: 2.0, speed: 6 });
      for (const e of ctx.foes(16, c0)) {
        if (!ctx.once(e, 1, "nova")) continue;
        hit(ctx, e, 24, { color: SUN, kb: 2.4, up: 0.95, dir: dirTo(c0, e.location), power: 2.6, crit: true,
                          sound: "astro.hit_heavy" });
        ignite(e, 6);
      }
    });
    // ---- 球殻の衝撃波（51〜60）: 水平・縦 2 枚の輪が広がる ----
    ctx.every(BOOM + 1, 10, 1, (i) => {
      const c0 = core;
      const R = 2.2 + i * 1.6;
      const col = mix(HOT, FLARE, i / 9);
      const f = ctx.f;
      ring(dim, "glow", c0, R, 40, { color: col, size: 1.6, life: 0.22 }, 0);
      P(dim, "ring_n", c0, { color: col, dir: f, spread: R, count: 40, size: 1.4, life: 0.22 });
      P(dim, "ring_n", c0, { color: mix(col, GOLD, 0.4), dir: rightOf(f), spread: R, count: 40, size: 1.4, life: 0.22 });
      if (i % 2 === 0) P(dim, "dust", up(centre, 0.2), { count: 14, spread: R * 0.8, speed: 4, size: 1.6 });
    });
    // 噴出物（52）: 炎の火球が全周へ飛び散る
    ctx.at(BOOM + 2, () => {
      if (fxScale() < 0.75) return;
      for (let k = 0; k < 8; k++) {
        const d = yawRotate(EAST, k * 45 + 20);
        P(dim, "meteor", core, { color: k % 2 ? FLARE : SUN, dir: { x: d.x, y: 0.35, z: d.z }, speed: 18, size: 1.2, life: 0.8, count: 8 });
      }
    });
    // 二の波・三の波（53 / 56）: 少し遅れて外まで届く
    ctx.at(BOOM + 3, () => {
      P(dim, "shock_flat", up(centre, 0.1), { color: NOVA, size: 8.5, life: 0.7 });
      P(dim, "ring", core, { color: NOVA, size: 10, life: 0.45 });
      sound(dim, "astro.explosion_big", centre, 0.55, 1.2);
      for (const e of ctx.foes(22, core)) {
        if (!ctx.once(e, 1, "wave")) continue;
        hit(ctx, e, 6, { color: NOVA, kb: 1.6, up: 0.5, dir: dirTo(centre, e.location), power: 1.6 });
      }
    });
    ctx.at(BOOM + 6, () => {
      P(dim, "shock_flat", up(centre, 0.12), { color: CRIMSON, size: 10.5, life: 0.8 });
      P(dim, "smoke", up(centre, 0.6), { count: 12, spread: 5, speed: 2.5, size: 2.4 });
      shake(dim, centre, 40, 0.5, 0.5);
    });
    // ---- 残骸の星雲（58〜80）----
    ctx.at(BOOM + 8, () => {
      P(dim, "cloud", up(core, 0.4), { color: mix(CRIMSON, FLARE, 0.4), count: 7, spread: 4.5, life: 2.6, size: 1.6 });
      P(dim, "cloud", up(core, 1.4), { color: mix(GOLD, SUN, 0.5), count: 5, spread: 3.0, life: 2.4, size: 1.3 });
      P(dim, "ring_flat", up(centre, 0.06), { color: CRIMSON, size: 6.5, life: 2.0 });
      sound(dim, "astro.corona", centre, 0.6, 0.8);
    });
    ctx.every(BOOM + 10, 6, 4, (i) => {
      P(dim, "ember", up(centre, 3.5), { color: i % 2 ? GOLD : FLARE, count: 12, spread: 5, speed: 1.0 });
      P(dim, "plasma", core, { color: SUN, size: 0.9 - i * 0.1, life: 0.3, spin: 400 });
      if (i % 2 === 0) P(dim, "smoke", up(centre, 0.8), { count: 4, spread: 4, speed: 0.8, size: 1.6 });
    });
    return 80;
  },

  // =========================================================================
  //  三段目「紅炎の弧」: 縦の炎の弧で前方 5m を焼き払い、地を這う炎が走る
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    const c0 = ctx.chest();
    arc(dim, up(c0, 0.3), f, 2.4, -150, 30, 90, FLARE, { size: 1.2, steps: 10, life: 0.3, sparks: false });
    P(dim, "slash_big", add(c0, f, 1.6), { color: SUN, rot: yawDeg(f) + 90, size: 1.1, life: 0.3 });
    P(dim, "flare", add(c0, f, 1.4), { color: HOT, size: 1.6, life: 0.2 });
    for (let k = 1; k <= 4; k++) {
      ctx.at(k, () => {
        const g = ctx.ground(add(ctx.loc(), f, 1.2 * k + 0.8));
        P(dim, "flame", up(g, 0.3), { color: k % 2 ? FLARE : SUN, count: 5, spread: 0.5, size: 1.4, speed: 2 });
        if (k === 4) P(dim, "ring_flat", up(g, 0.07), { color: CRIMSON, size: 1.4, life: 0.4 });
      });
    }
    sound(dim, "astro.swing_heavy", c0, 0.9, 0.9);
    sound(dim, "astro.flare", c0, 1.35, 0.7);
    for (const e of ctx.cone(5, 50, c0, f)) {
      hit(ctx, e, 6, { color: FLARE, kb: 1.0, up: 0.35, dir: f, power: 1.4 });
      ignite(e, 4);
    }
    if (target && valid(target)) P(dim, "flame", chest(target), { color: SUN, count: 6, spread: 0.4, size: 1.2 });
    return 10;
  },

  // =========================================================================
  //  変身の締め: 収縮した光が一気に膨らみ、コロナの輪が三重に広がる
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    sound(dim, "astro.corona", g, 1.0, 1.0);
    ctx.every(0, 2, 1, (i) => {
      P(dim, "converge", ctx.chest(), { color: HOT, count: 16, spread: 2.6 - i, life: 0.25, size: 0.9 });
      P(dim, "glow", ctx.chest(), { color: HOT, size: 1.4 - i * 0.5, life: 0.1 });
    });
    ctx.at(2, () => {
      const c0 = ctx.chest();
      sound(dim, "astro.flare", c0, 1.1, 0.9);
      P(dim, "flare", c0, { color: HOT, size: 2.4, life: 0.3, rot: 0 });
      P(dim, "lens", c0, { color: white(SUN, 0.5), size: 1.3, life: 0.4 });
      P(dim, "plasma", c0, { color: SUN, size: 1.6, life: 0.4 });
      P(dim, "pillar", up(g, 0.05), { color: SUN, size: 1.4, height: 8, life: 0.6 });
      emblem(dim, up(g, 0.05), KEY, { size: 1.8, life: 1.8 });
      P(dim, "ember", c0, { color: GOLD, count: 16, spread: 1.0, speed: 3 });
    });
    // コロナの輪が三重に広がる
    for (let k = 0; k < 3; k++) {
      ctx.at(3 + k * 3, () => {
        const c0 = ctx.chest();
        P(dim, "ring", c0, { color: k === 1 ? FLARE : SUN, size: 1.4 + k * 0.9, life: 0.4 });
        P(dim, "ring_flat", up(g, 0.06 + k * 0.01), { color: k === 1 ? CRIMSON : GOLD, size: 1.2 + k * 1.1, life: 0.6 });
        ring(dim, "star", g, 1.4 + k * 1.3, 12, { color: HOT, size: 0.8, life: 0.7, speed: 1.5 }, 0.5 + k * 0.4);
        P(dim, "flame", up(g, 0.3), { color: FLARE, count: 6, spread: 1.0 + k * 0.6, size: 1.0 });
      });
    }
    P(dim, "aura", g, { color: SUN, count: 8, spread: 0.6, life: 1.0 });
    return 14;
  },

  // =========================================================================
  //  パッシブ「コロナ」
  // =========================================================================
  passive: {
    /** 体のまわりのコロナ（軽く）と、1 秒ごとに近くの敵対的な相手を焦がす。 */
    tick(p, st) {
      const dim = p.dimension;
      const loc = p.location;
      if (st.n % 2 === 0) P(dim, "aura", loc, { color: st.n % 4 ? SUN : FLARE, count: 3, spread: 0.45, size: 0.8, life: 0.6 });
      if (st.n % 8 === 0) ring(dim, "dot", loc, 1.1, 14, { color: GOLD, size: 0.6, life: 0.5 }, 1.0);
      st.cd = (st.cd ?? 10) - 5;
      if (st.cd > 0) return;
      const c0 = chest(p);
      const foes = hostilesNear(p, c0, 3.6).slice(0, 4);
      if (!foes.length) { st.cd = 5; return; }
      st.cd = 20;
      sound(dim, "astro.flare", c0, 1.8, 0.25);
      for (const e of foes) {
        if (!valid(e)) continue;
        const q = chest(e);
        line(dim, "trail", c0, q, 0.5, { color: SUN, size: 0.35, life: 0.2 });
        P(dim, "flame", q, { color: FLARE, count: 4, spread: 0.3, size: 0.8 });
        P(dim, "ember", q, { color: GOLD, count: 4, spread: 0.4 });
        hit(p, e, 1.5, { color: FLARE, power: 0.5, quiet: true, nova: 1, xp: 1 });
        ignite(e, 2);
      }
    },
    /** 通常攻撃は相手に火をつける（技は技の中で焼く）。 */
    onHit(p, target, dmg, ctx) {
      if (ctx || !valid(target)) return;
      ignite(target, 3);
      try { P(p.dimension, "flame", chest(target), { color: FLARE, count: 3, spread: 0.3, size: 0.7 }); } catch (_) { }
    },
    /** 殴ってきた近くの相手を、コロナが焼き返す（1 秒に 1 回）。 */
    onHurt(p, attacker, dmg) {
      if (!attacker || !valid(attacker) || !valid(p)) return;
      const t = now();
      if ((retaliate.get(p.id) ?? 0) > t) return;
      let d = 99;
      try { d = dist(attacker.location, p.location); } catch (_) { return; }
      if (d > 5) return;
      retaliate.set(p.id, t + 20);
      const dim = p.dimension;
      const q = chest(attacker);
      P(dim, "flame", q, { color: FLARE, count: 6, spread: 0.4, size: 1.0 });
      P(dim, "ring", chest(p), { color: SUN, size: 1.2, life: 0.2 });
      sound(dim, "astro.flare", q, 1.6, 0.4);
      if (hit(p, attacker, 2, { color: FLARE, power: 0.6, kb: 0.5, up: 0.15, nova: 1, xp: 0 })) ignite(attacker, 3);
    },
    /** 倒した相手は小さな太陽になって弾ける。 */
    onKill(p, victim) {
      let at;
      try { at = chest(victim); } catch (_) { return; }
      if (!at || !Number.isFinite(at.x)) return;
      const dim = p.dimension;
      P(dim, "flare", at, { color: HOT, size: 1.2, life: 0.2 });
      P(dim, "ember", at, { color: SUN, count: 10, spread: 0.5, speed: 3 });
      P(dim, "ring", at, { color: FLARE, size: 1.0, life: 0.25 });
    },
  },
});
