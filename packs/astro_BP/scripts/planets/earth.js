// ===========================================================================
//  地球 ガイア（GAIA）— 惑星の技の見本（リファレンス実装）
//
//  青と白の騎士。緑の大陸線・白い雲のマント・肩を回る月の子機ルナ・ビット。
//  色: 発光 = 森の緑（ctx.c）/ 海の青（OCEAN）/ オーロラの緑と紫（AURORA_G / AURORA_P = ctx.accent）/
//      月の白（MOON）
//
//   惑星技  潮汐斬 タイダル・エッジ   月の引力で満ちる三日月の波。12m 進み、触れた敵を押し流す
//   機動技  磁気圏突撃 マグネトスフィア 磁気圏の泡をまとって突進（ほぼ無敵・飛び道具を弾く・敵を弾き飛ばす）
//   空中技  月墜 ルナ・フォール       ルナ・ビットを巨大化させて狙った地点へ落とす（予告 → 落下 → クレーター）
//   必殺    ガイア・レゾナンス         剣を大地に突き立て、地殻の柱を三重の輪で突き上げる。オーロラが味方を癒やす
//   三段目  オーロラ斬                 オーロラの斬撃が前方へ扇に広がる
//   変身の締め 海と森の色の輪が足元から広がり、オーロラの幕が立つ
//   パッシブ luna_bit                 約 2 秒ごとに 6m 以内の敵対的な相手を月の子機が小さな光線で撃つ
//
//  書き方のこつ（他の惑星もこの形で）:
//   * 技は「溜め（予兆）→ 放つ → 余韻」の 3 拍。ctx.at / ctx.every で時間割を組み、最後に技の長さを返す
//   * 1 つの瞬間に複数のパーティクルを重ねる（芯の白 + 惑星色 + 飛び散る粒 + 地面の輪）
//   * 当たりは ctx.once(e, 1, "タグ") で一度だけ。ダメージは hit(ctx, e, 素の値, {...})
//   * 音は 2 つ重ねると厚くなる（振り + 属性の音）。大技は shake と flash も
// ===========================================================================
import {
  register, lunge, hover, ultOpen, projectile, dirTo,
} from "../engine.js";
import {
  P, line, ring, arc, shock, beam, emblem, flash, shake, sound, body, white, mix, afterimage,
} from "../fx.js";
import {
  hit, enemiesNear, nearestHostile, launch, alliesNear, heal,
} from "../combat.js";
import { reflectProjectiles } from "../mobility.js";
import {
  add, up, lerp3, norm, sub, yawRotate, yawDeg, rightOf, flatDir, chest, hdist, groundY, onGround,
  effect, now, valid, blocked,
} from "../util.js";

const KEY = "earth";
const OCEAN = [0.26, 0.62, 1.0];
const FOREST = [0.33, 1.0, 0.57];
const AURORA_G = [0.4, 1.0, 0.7];
const AURORA_P = [0.8, 0.44, 1.0];
const MOON = [0.88, 0.92, 1.0];
const EAST = { x: 1, y: 0, z: 0 };

/** 右肩の上を回るルナ・ビットの位置。 */
function lunaPos(p, phase = now()) {
  const f = flatDir(p);
  const r = rightOf(f);
  const a = phase * 0.18;
  const l = p.location;
  return {
    x: l.x + r.x * (0.55 + Math.cos(a) * 0.25) + f.x * Math.sin(a) * 0.35,
    y: l.y + 1.95 + Math.sin(a * 0.5) * 0.08,
    z: l.z + r.z * (0.55 + Math.cos(a) * 0.25) + f.z * Math.sin(a) * 0.35,
  };
}

/** 月（ルナ・ビット）の光。size が大きいほど巨大化。 */
function moonFx(dim, q, size) {
  P(dim, "glow", q, { color: MOON, size: size * 1.2, life: 0.12 });
  P(dim, "glow", q, { color: white(OCEAN, 0.5), size: size * 1.6, life: 0.1 });
  if (size > 1.5) {
    P(dim, "ring", q, { color: white(MOON, 0.2), size: size * 1.3, life: 0.1 });
    P(dim, "dust", { ...q, y: q.y - size * 0.4 }, { color: MOON, count: 2, speed: 1, size: 0.6 });
  }
}

/** 磁気圏の泡: 球面の六角セル＋双極子の磁力線（オーロラ色）。 */
function magnetosphere(dim, c, f, i) {
  const n = 10;
  const ph = i * 0.42;
  for (let k = 0; k < n; k++) {
    const yv = 1 - (k + 0.5) / n * 2;
    const rr = Math.sqrt(1 - yv * yv);
    const a = k * 2.39996 + ph;
    P(dim, "hex", { x: c.x + Math.cos(a) * rr * 1.7, y: c.y + yv * 1.5, z: c.z + Math.sin(a) * rr * 1.7 },
      { color: k % 2 ? OCEAN : white(AURORA_G, 0.2), size: 0.6, life: 0.12 });
  }
  if (i % 2 === 0) {
    const r = rightOf(f);
    for (const s of [-1, 1]) {
      for (let t = 0; t <= 6; t++) {
        const a = t / 6 * Math.PI;
        const q = { x: c.x + r.x * s * Math.sin(a) * 2.1 - f.x * 0.3, y: c.y + Math.cos(a) * 1.8,
                    z: c.z + r.z * s * Math.sin(a) * 2.1 - f.z * 0.3 };
        P(dim, "dot", q, { color: mix(AURORA_G, AURORA_P, t / 6), size: 0.4, life: 0.14 });
      }
    }
  }
  P(dim, "ring", c, { color: AURORA_G, size: 2.1, life: 0.1, rot: i * 25 });
}

register(KEY, {
  // =========================================================================
  //  惑星技「潮汐斬 タイダル・エッジ」
  //  ルナ・ビットの引力で剣に潮が満ち（0〜7）、三日月の波を放つ（8）。波は地形に沿って 12m 進み、
  //  触れた敵を斬って押し流す。終点で波が砕ける。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    body(p, "earth.tidal_slash");
    sound(dim, "astro.gravity", p.location, 1.6, 0.4);
    sound(dim, "astro.water_wave", p.location, 1.3, 0.6);
    ctx.every(0, 4, 2, (i) => {
      const bit = lunaPos(p);
      const blade = ctx.local(0.8, 0.3, 1.2);
      P(dim, "glow", bit, { color: MOON, size: 0.6 + i * 0.15, life: 0.15 });
      beam(dim, bit, blade, MOON, { size: 0.12, life: 0.12, ends: false });
      P(dim, "converge", blade, { color: OCEAN, count: 8, spread: 1.6, life: 0.3, size: 0.6 });
      P(dim, "droplet", blade, { color: OCEAN, count: 4, spread: 0.5, speed: 1 });
    });
    ctx.at(8, () => {
      const f = ctx.liveDir();
      const r = rightOf(f);
      const rot = yawDeg(f);
      sound(dim, "astro.swing_heavy", p.location, 0.9, 1.0);
      sound(dim, "astro.water_wave", p.location, 1.0, 1.2);
      sound(dim, "astro.splash", p.location, 1.1, 0.8);
      arc(dim, ctx.chest(), f, 2.2, -80, 80, 8, OCEAN, { size: 1.2, steps: 14 });
      arc(dim, ctx.chest(), f, 1.8, -70, 70, 8, FOREST, { size: 0.7, steps: 10, inner: false, sparks: false });
      P(dim, "splash", ctx.local(1.5, 0, 1.0), { color: OCEAN, count: 12, speed: 4, spread: 0.6 });
      shake(dim, p.location, 8, 0.2, 0.2);
      const start = ctx.local(1.2, 0, 0.9);
      // 波頭そのもの（wave は自分で前へ進む: 17 m/s ≒ 弾の速さ、0.7 秒で 12m）
      P(dim, "wave", { ...start, y: start.y - 0.8 }, { color: OCEAN, dir: f, speed: 17, size: 1.1, life: 0.7 });
      projectile(ctx, start, f, {
        speed: 0.85, range: 12, radius: 1.7, pierce: Infinity, life: 30, blocks: false,
        damage: 9, hitOpts: { color: OCEAN, kb: 1.5, up: 0.3, dir: f, power: 1.4, sound: "astro.splash" },
        trail(d, pos, prev, age, s) {
          // 地形に沿って進む（2 段までの段差を越える）。越えられない壁・丘に当たったらそこで砕ける
          // （ブロックを抜けないので、壁の向こうの相手に当たらない）
          const gy = groundY(d, pos, 3, 2);
          if (blocked(d, { x: pos.x, y: gy + 0.5, z: pos.z })) { s.end("block"); return; }
          s.pos.y = gy + 0.9;
          const q = s.pos;
          if (age === 7) P(d, "wave", { ...q, y: gy + 0.05 }, { color: white(OCEAN, 0.15), dir: f, speed: 17, size: 1.0, life: 0.35 });
          P(d, "slash_flat", { ...q, y: gy + 0.35 }, { color: white(OCEAN, 0.3), size: 1.1, rot, life: 0.15 });
          for (const sd of [-1, 1]) {
            const h = add(q, r, 1.6 * sd);
            P(d, "splash", h, { color: OCEAN, count: 3, speed: 2.5, spread: 0.3 });
            P(d, "droplet", up(h, 0.4), { color: white(OCEAN, 0.4), count: 2, speed: 1.5 });
          }
          if (age % 2 === 0) P(d, "bubble", q, { color: white(OCEAN, 0.4), count: 3, spread: 0.8, speed: 0.6 });
          if (age % 3 === 0) P(d, "star", up(q, 0.8), { color: MOON, count: 1, spread: 0.6, life: 0.4 });
          if (age % 4 === 0) sound(d, "astro.water_wave", q, 1.3, 0.4);
          // 潮に呑まれた敵は波と一緒に押し流される
          for (const e of enemiesNear(ctx, q, 2.0)) launch(e, 0.12, 0.75, f);
        },
        onEnd(pos) {
          const g = onGround(dim, pos, 4);
          P(dim, "splash", up(g, 0.6), { color: OCEAN, count: 20, speed: 5, spread: 1.2 });
          P(dim, "ring_flat", up(g, 0.06), { color: OCEAN, size: 1.8, life: 0.5 });
          P(dim, "bubble", up(g, 0.5), { color: white(OCEAN, 0.4), count: 8, spread: 1.0, speed: 1 });
          sound(dim, "astro.splash", g, 0.9, 1.0);
        },
      });
    });
    return 16;
  },

  // =========================================================================
  //  機動技「磁気圏突撃 マグネトスフィア」
  //  磁気圏の泡をまとって突進する。突進中はほぼ無敵（resistance 4）、飛び道具を弾き返し、
  //  触れた敵を横へ弾き飛ばす。最後に磁場が外へ弾けて周りを押し返す。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    body(p, "earth.charge");
    sound(dim, "astro.barrier", p.location, 0.8, 1.0);
    sound(dim, "astro.boost", p.location, 0.9, 1.0);
    sound(dim, "astro.gravity", p.location, 1.2, 0.6);
    effect(p, "resistance", 18, 4);
    ctx.every(0, 6, 2, () => lunge(ctx, f, 1.05, 0.04));
    ctx.every(0, 14, 1, (i) => {
      const c0 = ctx.chest();
      magnetosphere(dim, c0, f, i);
      P(dim, "speedline", c0, { color: OCEAN, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 14, spread: 0.8 });
      if (i % 3 === 0) afterimage(dim, p.location, AURORA_G, 0.3);
      reflectProjectiles(p, c0, 3.0, AURORA_G);
      for (const e of ctx.foes(2.4, c0)) {
        if (!ctx.once(e, 1, "ram")) continue;
        const away = dirTo(p.location, e.location);
        hit(ctx, e, 7, { color: AURORA_G, kb: 1.9, up: 0.55, dir: away, power: 1.5, sound: "astro.hit_metal" });
        P(dim, "arc", chest(e), { color: AURORA_P, size: 1.2, life: 0.25 });
        sound(dim, "astro.barrier_hit", chest(e), 1.1, 0.8);
      }
    });
    ctx.at(14, () => {
      const g = ctx.ground(ctx.loc());
      shock(dim, g, OCEAN, 3.5, { debris: 6 });
      P(dim, "ring", ctx.chest(), { color: AURORA_G, size: 3.2, life: 0.3 });
      P(dim, "flare", ctx.chest(), { color: white(AURORA_G, 0.5), size: 1.1, life: 0.2 });
      sound(dim, "astro.impact_heavy", g, 1.2, 0.8);
      sound(dim, "astro.gravity", g, 0.8, 0.8);
      for (const e of ctx.foes(3.6)) {
        if (ctx.once(e, 1, "pulse")) hit(ctx, e, 3, { color: OCEAN, kb: 1.0, up: 0.3, dir: dirTo(g, e.location) });
      }
    });
    return 18;
  },

  // =========================================================================
  //  空中技「月墜 ルナ・フォール」
  //  宙で止まり、ルナ・ビットを狙った地点の上空へ打ち上げて巨大化させる（0〜9）。地面には予告の陣。
  //  月が落ちて（18〜26）クレーターの衝撃波（26）と、遅れて広がる二つ目の波（30）。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 22, 0.3);
    body(p, "earth.luna_call");
    const target = ctx.aim(22);
    const top = { x: target.x - ctx.f.x * 3, y: target.y + 11, z: target.z - ctx.f.z * 3 };
    sound(dim, "astro.gravity", p.location, 1.4, 0.8);
    sound(dim, "astro.beam_charge", p.location, 0.8, 0.6);
    ctx.at(0, () => {
      P(dim, "circle", up(target, 0.05), { color: MOON, size: 4.0, life: 1.6, spin: 60 });
      emblem(dim, up(target, 0.07), KEY, { color: AURORA_P, size: 3.2, life: 1.6 });
    });
    ctx.every(0, 7, 4, () => P(dim, "warning", up(target, 0.06), { color: [1, 0.3, 0.3], size: 3.8, life: 0.25 }));
    ctx.every(0, 10, 1, (i) => {
      const from = lunaPos(p);
      const q = lerp3(from, top, i / 9);
      moonFx(dim, q, 0.5 + i * 0.32);
      if (i % 2 === 0) P(dim, "trail", q, { color: MOON, size: 0.8, life: 0.3 });
    });
    ctx.at(3, () => sound(dim, "astro.meteor", top, 0.8, 1.3));   // 着弾音は 1.15 秒後 = 26 tick
    ctx.every(10, 4, 2, () => moonFx(dim, top, 3.6));
    const fallDir = norm(sub(target, top));
    for (let i = 0; i <= 8; i++) {
      ctx.at(18 + i, () => {
        const q = lerp3(top, up(target, 1.2), i / 8);
        moonFx(dim, q, 3.6);
        P(dim, "trail", q, { color: MOON, size: 2.4, life: 0.3 });
        P(dim, "speedline", q, { color: white(MOON, 0.2), count: 4, dir: { x: -fallDir.x, y: -fallDir.y, z: -fallDir.z }, speed: 10, spread: 1.2 });
      });
    }
    ctx.at(26, () => {
      const g = ctx.ground(target);
      P(dim, "flare", up(g, 1.0), { color: white(MOON, 0.4), size: 2.2, life: 0.3 });
      P(dim, "impact", up(g, 0.8), { color: MOON, size: 3.5, life: 0.22 });
      P(dim, "lens", up(g, 1.2), { color: white(OCEAN, 0.5), size: 1.6, life: 0.35 });
      shock(dim, g, MOON, 4.5, { debris: 18 });
      ring(dim, "debris", g, 2.5, 8, { count: 3, speed: 6 }, 0.3);
      P(dim, "dust", up(g, 0.3), { count: 30, speed: 6, size: 1.6, spread: 1.5 });
      sound(dim, "astro.explosion_big", g, 0.8, 1.4);
      sound(dim, "astro.impact_heavy", g, 0.7, 1.2);
      shake(dim, g, 22, 0.7, 0.5);
      flash(dim, g, 12, white(MOON, 0.3), 0.04, 0.45);
      for (const e of ctx.foes(4.6, up(g, 0.8))) {
        if (ctx.once(e, 1, "moon")) hit(ctx, e, 14, { color: MOON, kb: 1.0, up: 0.75, dir: dirTo(g, e.location), power: 2.0, sound: "astro.hit_heavy" });
      }
    });
    ctx.at(30, () => {
      const g = ctx.ground(target);
      P(dim, "shock_flat", up(g, 0.08), { color: OCEAN, size: 5, life: 0.6 });
      ring(dim, "dust", g, 6, 12, { count: 2, speed: 2 }, 0.2);
      for (const e of ctx.foes(7.6, up(g, 0.8))) {
        if (ctx.once(e, 1, "wave")) hit(ctx, e, 5, { color: OCEAN, kb: 1.2, up: 0.35, dir: dirTo(g, e.location) });
      }
    });
    return 28;
  },

  // =========================================================================
  //  必殺「ガイア・レゾナンス」
  //  時を止め（ultOpen）、剣を大地に突き立てる（12）。大陸の光の線が地面を走り、地殻の柱が三重の輪で
  //  内から外へ突き上がる（18 / 28 / 38）。オーロラの幕が味方を癒やし（16〜70）、最後に大地が共鳴して爆ぜる（70）。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 90, 14);
    const centre = ctx.ground(ctx.loc());
    ctx.at(4, () => body(p, "earth.plant_sword"));
    ctx.at(12, () => {
      const tip = ctx.ground(ctx.local(0.9, 0, 0));
      P(dim, "impact", up(tip, 0.3), { color: FOREST, size: 2.0, life: 0.2 });
      P(dim, "pillar", up(tip, 0.05), { color: AURORA_G, size: 0.6, height: 3, life: 0.4 });
      emblem(dim, up(centre, 0.06), KEY, { size: 6, life: 4.0, spin: 20 });
      P(dim, "hex_circle", up(centre, 0.05), { color: OCEAN, size: 8, life: 3.5, spin: -15 });
      sound(dim, "astro.impact_heavy", tip, 0.8, 1.2);
      sound(dim, "astro.gravity", tip, 0.7, 1.0);
      shake(dim, centre, 20, 0.5, 0.5);
      for (let k = 0; k < 8; k++) {
        const d = yawRotate(EAST, k * 45 + 22.5);
        line(dim, "trail", up(centre, 0.12), add(up(centre, 0.12), d, 10), 0.9, { color: k % 2 ? FOREST : OCEAN, size: 0.5, life: 1.2 });
      }
    });
    // 三重の地殻の柱
    const RINGS = [[18, 3.5, 8, 9], [28, 6.5, 12, 10], [38, 9.5, 16, 11]];
    for (const [t, R, n, dmg] of RINGS) {
      ctx.at(t - 4, () => ring(dim, "dot", centre, R, n * 2, { color: FOREST, size: 0.5, life: 0.3 }, 0.12));
      ctx.at(t, () => {
        sound(dim, "astro.impact_heavy", centre, 0.9 + R * 0.02, 1.0);
        sound(dim, "astro.explosion", centre, 0.7, 0.9);
        shake(dim, centre, 22, 0.4, 0.35);
        P(dim, "shock_flat", up(centre, 0.08), { color: FOREST, size: (R + 1) / 1.5, life: 0.5 });
        for (let i = 0; i < n; i++) {
          const q = onGround(dim, add(centre, yawRotate(EAST, i / n * 360 + R * 10), R), 6);
          ctx.at(i % 3, () => {
            P(dim, "pillar", up(q, 0.05), { color: i % 2 ? FOREST : mix(FOREST, OCEAN, 0.5), size: 0.9, height: 3.6, life: 0.6 });
            P(dim, "debris", up(q, 0.4), { count: 5, speed: 6, spread: 0.4 });
            P(dim, "dust", up(q, 0.2), { count: 4, speed: 3 });
            if (i % 2 === 0) P(dim, "shard", up(q, 1.2), { color: OCEAN, count: 3, speed: 4 });
          });
        }
        for (const e of ctx.foes(R + 2, up(centre, 1))) {
          const d = hdist(e.location, centre);
          if (Math.abs(d - R) > 1.9 || !ctx.once(e, 1, `ring${R}`)) continue;
          hit(ctx, e, dmg, { color: FOREST, up: 0.95, kb: 0.4, dir: dirTo(centre, e.location), power: 1.8, sound: "astro.hit_heavy" });
        }
      });
    }
    // オーロラの幕（aurora 1 回で半径 spread の輪に帯が並ぶ）。自分と自分のペットを癒やす（他のプレイヤーは含めない）
    for (const t of [16, 44]) {
      ctx.at(t, () => {
        P(dim, "aurora", up(centre, 0.1), { color: AURORA_G, spread: 8, count: 16, height: 5.5, life: 3.0, spin: 6 });
        P(dim, "aurora", up(centre, 0.1), { color: AURORA_P, spread: 6.5, count: 12, height: 4.5, life: 3.0, spin: -8 });
      });
    }
    ctx.every(16, 10, 6, (i) => {
      if (i % 2 === 0) {
        for (const a of alliesNear(p, centre, 12)) {
          heal(a, 2);
          effect(a, "regeneration", 60, 1);
          P(dim, "star", chest(a), { color: AURORA_G, count: 4, spread: 0.6, life: 0.6 });
        }
        sound(dim, "astro.wind", centre, 1.3, 0.5);
      }
    });
    ctx.at(37, () => sound(dim, "astro.supernova", centre, 1.2, 0.9));   // 1.66 秒後 = 70 で弾ける
    ctx.at(70, () => {
      P(dim, "lens", up(centre, 1.5), { color: white(FOREST, 0.5), size: 3, life: 0.6 });
      P(dim, "flare", up(centre, 1.2), { color: white(AURORA_G, 0.6), size: 2.6, life: 0.4 });
      shock(dim, centre, AURORA_G, 12, { debris: 20 });
      P(dim, "ring", up(centre, 1.0), { color: AURORA_P, size: 9, life: 0.5 });
      flash(dim, centre, 32, white(AURORA_G, 0.6), 0.1, 0.5);
      sound(dim, "astro.explosion_big", centre, 0.8, 1.5);
      shake(dim, centre, 26, 0.8, 0.6);
      for (const e of ctx.foes(12, up(centre, 1))) {
        hit(ctx, e, 12, { color: AURORA_G, kb: 1.4, up: 0.6, dir: dirTo(centre, e.location), power: 2.2, crit: true });
      }
      for (const a of alliesNear(p, centre, 12)) heal(a, 4);
    });
    return 76;
  },

  // =========================================================================
  //  三段目「オーロラ斬」: オーロラの斬撃が前方へ扇に広がる
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    for (let k = -2; k <= 2; k++) {
      arc(dim, ctx.chest(), yawRotate(f, k * 22), 2.6 + Math.abs(k) * 0.1, -30, 30, 10 + k * 6,
        k % 2 ? AURORA_P : AURORA_G, { size: 0.9, steps: 7, sparks: false, life: 0.3 });
      P(dim, "aurora", add(ctx.loc(), yawRotate(f, k * 22), 3.2), { color: mix(AURORA_G, AURORA_P, (k + 2) / 4), spread: 0, count: 1, size: 1.2, height: 2.6, life: 0.6 });
    }
    P(dim, "slash_big", ctx.local(2, 0, 1.1), { color: AURORA_G, rot: yawDeg(f), size: 1.0, life: 0.3 });
    sound(dim, "astro.swing_heavy", p.location, 1.0, 0.9);
    sound(dim, "astro.wind", p.location, 1.4, 0.6);
    for (const e of ctx.cone(5, 60, ctx.chest(), f)) {
      hit(ctx, e, 5, { color: AURORA_G, kb: 1.0, up: 0.3, dir: f, power: 1.3 });
    }
    return 10;
  },

  // =========================================================================
  //  変身の締め: 海と森の色の輪が足元から広がり、オーロラの幕が立つ。ルナ・ビットが軌道に乗る
  // =========================================================================
  burst(ctx) {
    const { p, dim } = ctx;
    const g = ctx.ground(ctx.loc());
    sound(dim, "astro.water_wave", g, 1.0, 1.0);
    sound(dim, "astro.wind", g, 1.1, 0.8);
    emblem(dim, up(g, 0.05), KEY, { size: 1.6, life: 1.8 });
    P(dim, "flare", ctx.chest(), { color: white(FOREST, 0.5), size: 1.3, life: 0.3 });
    ctx.every(0, 5, 3, (i) => {
      P(dim, "ring_flat", up(g, 0.06 + i * 0.01), { color: i % 2 ? FOREST : OCEAN, size: 0.8 + i * 0.8, life: 0.6 });
      ring(dim, i % 2 ? "dot" : "droplet", g, 1.2 + i * 1.4, 10, { color: i % 2 ? FOREST : OCEAN, size: 0.5, life: 0.5 }, 0.2);
    });
    ctx.at(2, () => {
      P(dim, "aurora", up(g, 0.1), { color: AURORA_G, spread: 3.2, count: 12, height: 4, life: 2.2, spin: 10 });
      P(dim, "aurora", up(g, 0.1), { color: AURORA_P, spread: 2.6, count: 10, height: 3.2, life: 2.2, spin: -12 });
    });
    ctx.every(0, 8, 2, (i) => P(dim, "glow", lunaPos(p, now() + i * 4), { color: MOON, size: 0.5, life: 0.2 }));
    return 20;
  },

  // =========================================================================
  //  パッシブ「ルナ・ビット」: 約 2 秒ごとに 6m 以内の敵対的な相手を小さな光線で撃つ
  // =========================================================================
  passive: {
    tick(p, st) {
      const dim = p.dimension;
      if (st.n % 2 === 0) P(dim, "glow", lunaPos(p), { color: MOON, size: 0.35, life: 0.3 });
      st.cd = (st.cd ?? 20) - 5;
      if (st.cd > 0) return;
      const foe = nearestHostile(p, chest(p), 6);
      if (!foe || !valid(foe)) return;
      st.cd = 40;
      const from = lunaPos(p);
      const to = chest(foe);
      beam(dim, from, to, MOON, { size: 0.18, life: 0.15 });
      P(dim, "spark", to, { color: OCEAN, count: 5, speed: 4 });
      sound(dim, "astro.laser", from, 1.6, 0.45);
      hit(p, foe, 3, { color: MOON, nova: 1, xp: 1, power: 0.7, sound: "astro.zap" });
    },
  },
});

