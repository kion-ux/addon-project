// ===========================================================================
//  天王星 ウラノス（OURANOS）— 傾天弩 ティルト・ボウガン
//
//  横倒しの氷の巨星。淡い青緑の結晶の装甲、背中で 98° 傾いて縦に回る環、ダイヤの鶏冠。
//  色: 冷たい白青（ICE = ctx.c）/ 濃い氷の青（AZURE）/ 霜の白（FROST）/ 青緑（TEAL）/ 霧（MIST）
//
//   惑星技  絶対零度矢 アブソリュート・アロー  構えて溜め（0〜7）→ 貫く冷気の矢（8）。当たった敵は凍りつき、
//                                          着弾点から氷の棘が突き上がる（棘は 2.5 秒残って足を鈍らせ、砕ける）。
//                                          98° ロールの後は三本同時に扇で撃つ
//   機動技  98° ロール                     横倒しに一回転して横へ転がり避ける（ほぼ無敵）。元の場所に氷の分身が
//                                          残って周りの足を鈍らせ、1.7 秒後に砕けて周りを凍らせる。次の惑星技を三連に
//   空中技  ダイヤモンド・レイン           宙で止まり、前上方へ二連射（6 / 11）。狙った地点の空に結晶の雲が開き、
//                                          半径 5.5m にダイヤの雨が降る（16〜44。鈍化）。最後に中央で結晶が噴き上がる（46）
//   必殺    アクシアル・ティルト           時を止め、98° 傾いた巨大な環が立つ（4）。重力が横倒しになって敵が横へ
//                                          放り出され（12〜26）、氷の棺に閉じ込められ（28）、構えた一射（51）の光が
//                                          全ての棺を貫いて粉々に砕く（53）。環が崩れてオーロラと雪（58〜）
//   三段目  氷晶散弾                       至近距離へ扇の散弾（7 筋の閃光 + 結晶片）。前方 5.5m の敵を凍えさせる
//   変身の締め 横倒しの環が回って氷晶が散り、足元から地面が凍っていく
//   パッシブ frost_aura                    1 秒ごとに 4.5m 以内の敵対的な相手の足を鈍らせる。殴ってきた相手は
//                                          凍えて（鈍化・弱体化・凍傷のダメージ）、倒した敵は氷になって砕ける
// ===========================================================================
import {
  register, lunge, hover, ultOpen, projectile, zone, safeAhead, dirTo,
} from "../engine.js";
import {
  P, line, ring, shock, beam, emblem, flash, shake, sound, body, white, mix, afterimage, status, fxScale,
} from "../fx.js";
import {
  hit, freeze, launch, hostilesNear, isTarget,
} from "../combat.js";
import {
  add, up, norm, basis, yawRotate, chest, hdist, effect, now, valid, rand, clamp, finite,
  onGround,
} from "../util.js";

const KEY = "uranus";
const ICE = [0.67, 1.0, 1.0];         // = ctx.c（冷たい白青）
const AZURE = [0.42, 0.86, 1.0];      // 濃い氷の青（明るい所でも色が分かる）
const FROST = [0.9, 0.97, 1.0];       // 霜の白
const TEAL = [0.18, 0.62, 0.66];      // 副装甲の青緑
const MIST = [0.8, 0.92, 0.96];       // 冷気の霧（半透明の smoke）
const DOWN = { x: 0, y: -1, z: 0 };
const TILT = 98 * Math.PI / 180;      // 自転軸の傾き

/** 次の惑星技を三連にする期限（98° ロール）: playerId -> tick。 */
const armed = new Map();
/** 98° ロールの向き（交互）: playerId -> +1 右 / -1 左。 */
const rollSide = new Map();
/** frost_aura の反撃の間隔: `${playerId}|${attackerId}` -> tick。 */
const chillCd = new Map();
let spikeSeq = 0;               // 氷の棘ごとの当たりのタグ

// ---------------------------------------------------------------------------
//  補助
// ---------------------------------------------------------------------------
/** 今の視線（上下は -0.45〜0.6 に収める。真上・真下を見ていても前へ撃つ）。 */
function aimDir(ctx) {
  const v = ctx.liveView();
  const f = ctx.liveDir();
  const y = clamp(Number.isFinite(v.y) ? v.y : 0, -0.45, 0.6);
  const k = Math.sqrt(Math.max(0, 1 - y * y));
  return { x: f.x * k, y, z: f.z * k };
}

/** 弩の先（矢の出る所）。目より少し下・右。 */
function muzzle(ctx, d) {
  const l = ctx.p.location;
  const f = ctx.liveDir();
  return { x: l.x + d.x * 1.1 - f.z * 0.3, y: l.y + 1.35 + d.y * 1.1, z: l.z + d.z * 1.1 + f.x * 0.3 };
}

/** 98° 傾いた環の面の法線（縦に立ち、横へ 20° ひねる）。 */
function tiltNormal(f, side = 1) {
  return norm({ x: f.x - f.z * 0.36 * side, y: Math.tan(TILT - Math.PI / 2), z: f.z + f.x * 0.36 * side });
}

/** 法線 n の輪の上の点（角度 a ラジアン、半径 r）。 */
function onRing(c, n, r, a) {
  const { r: u, u: v } = basis(n);
  const ca = Math.cos(a), sa = Math.sin(a);
  return { x: c.x + (u.x * ca + v.x * sa) * r, y: c.y + (u.y * ca + v.y * sa) * r, z: c.z + (u.z * ca + v.z * sa) * r };
}

/** 凍りつく: 六角の氷の殻・氷晶・青い光。 */
function encase(dim, e, big = false) {
  if (!valid(e)) return;
  const c = chest(e);
  P(dim, "hex", c, { color: big ? FROST : ICE, count: big ? 20 : 12, spread: big ? 1.15 : 0.9, size: big ? 0.8 : 0.6, life: big ? 2.6 : 1.1 });
  P(dim, "ice", c, { color: FROST, count: big ? 8 : 4, spread: 0.6, speed: 1.2 });
  P(dim, "glow", c, { color: AZURE, size: big ? 2.4 : 1.5, life: 0.25 });
  if (big) P(dim, "pillar", up(e.location, 0.02), { color: white(ICE, 0.3), size: 1.5, height: 2.6, life: 2.4 });
}

/** 粉々に砕ける: 結晶片・氷晶・ダイヤ・閃光・輪。 */
function shatterFx(dim, c, power = 1) {
  P(dim, "impact", c, { color: white(ICE, 0.5), size: 1.2 * power, life: 0.18 });
  P(dim, "shard", c, { color: ICE, count: Math.round(10 * power), speed: 6 + 2 * power, spread: 0.4 });
  P(dim, "ice", c, { color: FROST, count: Math.round(6 * power), speed: 4 + power, spread: 0.5 });
  P(dim, "diamond", c, { color: white(AZURE, 0.4), count: Math.round(4 * power), speed: 3 + power, spread: 0.4 });
  P(dim, "ring", c, { color: AZURE, size: 0.9 * power, life: 0.25 });
}

/**
 * 着弾点から突き上がる氷の棘（中央の太い棘と、まわりの n 本）。当たった敵を突き上げて凍らせる。
 * 棘は zone で 2.5 秒残って足を鈍らせ、最後に砕ける。
 */
function iceSpikes(ctx, g, n = 5, R = 1.6, tag = "spike") {
  const { dim } = ctx;
  const pts = [{ x: g.x, y: g.y, z: g.z, h: 2.8, s: 0.6 }];
  const a0 = rand(0, Math.PI * 2);
  for (let i = 0; i < n; i++) {
    const a = a0 + i / n * Math.PI * 2;
    const r = R * (0.75 + 0.25 * (i % 2));
    const q = onGround(dim, { x: g.x + Math.cos(a) * r, y: g.y + 1, z: g.z + Math.sin(a) * r }, 3);
    pts.push({ ...q, h: 1.3 + (i % 3) * 0.45, s: 0.36 });
  }
  sound(dim, "astro.ice_crack", g, 0.9, 1.1);
  sound(dim, "astro.ice_shatter", g, 1.3, 0.7);
  P(dim, "shock_flat", up(g, 0.08), { color: AZURE, size: (R + 1) / 1.5, life: 0.45 });
  P(dim, "ring_flat", up(g, 0.1), { color: FROST, size: R / 1.1, life: 0.5 });
  P(dim, "smoke", up(g, 0.3), { color: MIST, count: 5, spread: R * 0.5, speed: 0.8, size: 1.1 });
  pts.forEach((q, i) => {
    ctx.at(i === 0 ? 0 : 1 + (i % 3), () => {
      P(dim, "pillar", up(q, 0.03), { color: i === 0 ? white(ICE, 0.35) : ICE, size: q.s, height: q.h, life: 0.9 });
      P(dim, "diamond", up(q, q.h * 0.8), { color: FROST, count: 2, speed: 1.5, spread: 0.15, size: 1.1 });
      P(dim, "shard", up(q, 0.3), { color: ICE, count: 4, speed: 4, spread: 0.2 });
    });
  });
  for (const e of ctx.foes(R + 1.0, up(g, 0.8))) {
    if (!ctx.once(e, 1, tag)) continue;
    hit(ctx, e, 5, { color: ICE, up: 0.55, kb: 0.2, dir: dirTo(g, e.location), power: 1.3, sound: "astro.ice_crack" });
    freeze(e, 40, true);
  }
  // 残る棘: 鈍化の範囲。8 tick ごとに棘が瞬き、最後に砕ける
  zone(ctx, g, {
    radius: R + 0.6, ticks: 50, every: 10, effects: [["slowness", 20, 2]], visualEvery: 2,
    visual(d, c, age) {
      if (age % 8 !== 4) return;
      for (const q of pts) P(d, "pillar", up(q, 0.03), { color: mix(ICE, TEAL, 0.25), size: q.s * 0.8, height: q.h, life: 0.45 });
      if (fxScale() >= 1) P(d, "ice", up(c, 0.6), { color: FROST, count: 2, spread: R, speed: 0.3, size: 0.7 });
    },
    onEnd(z) {
      for (const q of pts.slice(0, 4)) P(dim, "shard", up(q, q.h * 0.5), { color: ICE, count: 5, speed: 4, spread: 0.3 });
      P(dim, "ice", up(z.center, 0.8), { color: FROST, count: 8, speed: 3, spread: R * 0.6 });
      sound(dim, "astro.ice_shatter", z.center, 1.5, 0.6);
    },
  });
}

/** 絶対零度の矢を 1 本撃つ。main は中央の矢（輪の飾り付き）。 */
function fireArrow(ctx, from, d, main) {
  const { dim } = ctx;
  let spikes = 0;
  projectile(ctx, from, d, {
    speed: 1.7, range: 24, radius: 0.75, pierce: Infinity, life: 20,
    damage: main ? 9 : 7,
    hitOpts: { color: AZURE, kb: 0.35, up: 0.1, power: 1.3, sound: "astro.ice_crack" },
    trail(dd, pos, prev, age) {
      line(dd, "trail", prev, pos, 0.3, { color: white(AZURE, 0.35), size: 0.55, life: 0.35 });
      P(dd, "thrust", add(pos, d, -1.4), { color: white(ICE, 0.55), dir: d, len: 1.6, size: 0.6, life: 0.08 });
      if (age % 2 === 0) P(dd, "ice", pos, { color: FROST, count: 1, spread: 0.15, speed: 0.4, size: 0.55 });
      if (main && age % 3 === 1) P(dd, "ring", pos, { color: AZURE, size: 0.55, life: 0.18 });
    },
    onHit(e) {
      freeze(e, 60, true);
      encase(dim, e);
    },
    onEnd(pos, reason) {
      if (!pos || !finite(pos) || reason === "owner") return;
      const g = onGround(dim, pos, 4);
      if (Math.abs(g.y - pos.y) > 3.5) {
        shatterFx(dim, pos, 1.2);          // 空中で尽きた: 冷気が弾けるだけ
        sound(dim, "astro.ice_shatter", pos, 1.6, 0.5);
        return;
      }
      if (spikes++ === 0) iceSpikes(ctx, g, main ? 6 : 4, main ? 1.7 : 1.2, `spike${++spikeSeq}`);
    },
  });
}

/** 氷の分身（98° ロールで元の場所に残る）。足を鈍らせ、34 tick 後に砕けて周りを凍らせる。 */
function iceDecoy(ctx, at) {
  const { dim } = ctx;
  const g = ctx.ground(at);
  afterimage(dim, g, white(ICE, 0.2), 0.6);
  P(dim, "hex", up(g, 1.0), { color: FROST, count: 14, spread: 0.9, size: 0.6, life: 0.6 });
  zone(ctx, g, {
    radius: 3.2, ticks: 34, every: 6, effects: [["slowness", 16, 1]], visualEvery: 2,
    visual(d, c, age) {
      if (age % 8 === 0) afterimage(d, c, white(ICE, 0.25), 0.5);
      if (age % 8 === 4) P(d, "hex", up(c, 1.0), { color: ICE, count: 10, spread: 0.85, size: 0.55, life: 0.45 });
      if (age % 4 === 2) P(d, "ice", up(c, 1.2), { color: FROST, count: 1, spread: 0.6, speed: 0.3, size: 0.6 });
      if (age % 12 === 0) ring(d, "dot", c, 3.2, 22, { color: AZURE, size: 0.5, life: 0.6 }, 0.1);
    },
  });
  ctx.at(34, () => {
    const c = up(g, 1.0);
    shatterFx(dim, c, 1.8);
    shock(dim, g, AZURE, 3.2, { dust: false });
    P(dim, "smoke", up(g, 0.4), { color: MIST, count: 6, spread: 1.2, speed: 1.2, size: 1.2 });
    sound(dim, "astro.ice_shatter", c, 1.0, 1.0);
    sound(dim, "astro.hit_metal", c, 0.8, 0.5);
    for (const e of ctx.foes(3.6, c)) {
      if (!ctx.once(e, 1, "decoy")) continue;
      hit(ctx, e, 7, { color: ICE, kb: 0.9, up: 0.35, dir: dirTo(g, e.location), power: 1.4, sound: "astro.ice_crack" });
      freeze(e, 40, false);
      encase(dim, e);
    }
  });
}

register(KEY, {
  // =========================================================================
  //  惑星技「絶対零度矢 アブソリュート・アロー」
  //  両手で目の高さに構える（0〜7）: 冷気が弩の先へ吸い込まれ、照準の陣が回る。8 tick 目に撃つ（反動）。
  //  矢は 24m を一瞬で貫き、当たった敵は凍りつく。着弾点（地面）から氷の棘が突き上がる。
  //  98° ロールの後なら三本を扇に撃つ（左右の矢も着弾点に小さな棘）。
  // =========================================================================
  skill(ctx) {
    const { p, dim } = ctx;
    const triple = (armed.get(p.id) ?? -1) >= now();
    if (triple) armed.delete(p.id);
    body(p, "uranus.aim_shot");
    sound(dim, "astro.beam_charge", p.location, 1.5, 0.7);
    sound(dim, "astro.ice_crack", p.location, 1.4, 0.5);
    if (triple) sound(dim, "astro.ring_spin", p.location, 1.5, 0.6);
    ctx.every(0, 4, 2, (i) => {
      const d = aimDir(ctx);
      const m = muzzle(ctx, d);
      P(dim, "converge", m, { color: AZURE, count: 10, spread: 1.6, life: 0.3, size: 0.7 });
      P(dim, "glow", m, { color: ICE, size: 0.5 + i * 0.25, life: 0.15 });
      if (i === 0) P(dim, "circle_v", add(m, d, 0.7), { color: ICE, dir: d, size: 0.55, life: 0.5, spin: 160 });
      if (i % 2 === 1) P(dim, "smoke", m, { color: MIST, count: 2, spread: 0.3, speed: 0.4, size: 0.6 });
      if (triple) {
        for (const a of [-11, 11]) P(dim, "glow", muzzle(ctx, yawRotate(d, a * 2)), { color: AZURE, size: 0.4 + i * 0.15, life: 0.15 });
      }
      status(p, `§b絶対零度 ${"▰".repeat(i + 1)}${"▱".repeat(3 - i)}${triple ? " §f×3" : ""}`, 4);
    });
    ctx.at(8, () => {
      const d = aimDir(ctx);
      const m = muzzle(ctx, d);
      sound(dim, "astro.beam_fire", m, 1.35, 1.0);
      sound(dim, "astro.ice_shatter", m, 1.6, 0.6);
      sound(dim, "astro.swing", m, 1.5, 0.5);
      P(dim, "flare", m, { color: white(ICE, 0.5), size: 1.2, life: 0.15 });
      P(dim, "ring", m, { color: AZURE, size: triple ? 1.5 : 1.0, life: 0.2 });
      P(dim, "ice", m, { color: FROST, count: 5, spread: 0.3, speed: 3 });
      shake(dim, p.location, 6, 0.15, 0.15);
      const fan = triple ? [-11, 0, 11] : [0];
      for (const a of fan) fireArrow(ctx, m, a ? yawRotate(d, a) : d, a === 0);
    });
    return 16;
  },

  // =========================================================================
  //  機動技「98° ロール」
  //  横倒しに一回転しながら斜め前へ転がって避ける（交互に右・左。壁があれば反対へ）。転がる間はほぼ無敵。
  //  元の場所に氷の分身が残り、周りの足を鈍らせて 1.7 秒後に砕ける。次の惑星技は三本同時（10 秒以内）。
  // =========================================================================
  dash(ctx) {
    const { p, dim } = ctx;
    const f = ctx.f;
    const r = ctx.r;
    const room = (s) => hdist(safeAhead(dim, p.location, { x: r.x * s, y: 0, z: r.z * s }, 4), p.location);
    let side = -(rollSide.get(p.id) ?? -1);
    if (room(side) < 2 && room(-side) > room(side)) side = -side;
    rollSide.set(p.id, side);
    const sd = { x: r.x * side, y: 0, z: r.z * side };
    const dir = norm({ x: sd.x * 0.85 + f.x * 0.55, y: 0, z: sd.z * 0.85 + f.z * 0.55 });
    const start = ctx.loc();
    body(p, side > 0 ? "uranus.roll" : "uranus.roll_l");
    effect(p, "resistance", 14, 4);
    sound(dim, "astro.gust", p.location, 1.2, 0.9);
    sound(dim, "astro.boost", p.location, 1.1, 0.7);
    sound(dim, "astro.ice_crack", p.location, 1.6, 0.5);
    ctx.every(0, 3, 2, () => lunge(ctx, dir, 1.15, 0.16));
    // 転がる軸（進む向き）のまわりを巡る氷の螺旋と、霜の残像
    ctx.every(0, 12, 1, (i) => {
      const c0 = ctx.chest();
      const a = i * 0.9 * side;
      const { r: u, u: v } = basis(dir);
      for (const k of [0, Math.PI]) {
        const q = { x: c0.x + (u.x * Math.cos(a + k) + v.x * Math.sin(a + k)) * 0.9,
                    y: c0.y + (u.y * Math.cos(a + k) + v.y * Math.sin(a + k)) * 0.9,
                    z: c0.z + (u.z * Math.cos(a + k) + v.z * Math.sin(a + k)) * 0.9 };
        P(dim, "trail", q, { color: k ? AZURE : FROST, size: 0.7, life: 0.4 });
      }
      P(dim, "wind", c0, { color: FROST, dir: { x: -dir.x, y: 0, z: -dir.z }, count: 2, speed: 8, spread: 0.6 });
      if (i % 3 === 0) afterimage(dim, p.location, white(AZURE, 0.35), 0.3);
      if (i % 2 === 1) P(dim, "ice", c0, { color: FROST, count: 2, spread: 0.6, speed: 1 });
    });
    iceDecoy(ctx, start);
    armed.set(p.id, now() + 200);
    ctx.at(10, () => {
      const c = ctx.chest();
      sound(dim, "astro.ring_spin", c, 1.4, 0.7);
      P(dim, "ring_n", c, { color: ICE, count: 24, spread: 1.1, dir: tiltNormal(ctx.liveDir(), side), life: 0.5, var: 1 });
      for (let k = 0; k < 3; k++) P(dim, "diamond", onRing(c, tiltNormal(ctx.liveDir(), side), 1.1, k * 2.094), { color: FROST, count: 1, speed: 0.2, size: 1.1, life: 0.6 });
      status(p, "§b三連装填 §f×3 §7（次の惑星技）", 30);
    });
    ctx.at(12, () => {
      const g = ctx.ground(ctx.loc());
      P(dim, "ring_flat", up(g, 0.06), { color: AZURE, size: 1.3, life: 0.4 });
      P(dim, "dust", up(g, 0.1), { color: MIST, count: 8, speed: 2, size: 0.9 });
    });
    return 14;
  },

  // =========================================================================
  //  空中技「ダイヤモンド・レイン」
  //  宙で止まって狙った地点（近すぎれば 7m 先）に結晶の陣を敷き、前上方へ二連射（6 / 11）。
  //  地点の空に結晶の雲（傾いた輪）が開き、16〜44 tick にダイヤの雨（半径 5.5m、4 tick ごとに削って鈍らせる）。
  //  46 tick 目に中央で結晶が噴き上がり、周りを打ち上げる。
  // =========================================================================
  air(ctx) {
    const { p, dim } = ctx;
    hover(ctx, 30, 0.32);
    body(p, "uranus.rain_shot");
    let target = ctx.aim(24);
    if (!target || !finite(target) || hdist(target, p.location) < 5) {
      target = add(p.location, ctx.f, 7);
    }
    const g = ctx.ground(target);
    const R = 5.5;
    const sky = up(g, 11);
    const n = tiltNormal(ctx.f);
    sound(dim, "astro.beam_charge", p.location, 1.3, 0.6);
    sound(dim, "astro.wind", g, 1.4, 0.6);
    P(dim, "circle", up(g, 0.05), { color: ICE, size: R / 1.2, life: 2.5, spin: 40 });
    emblem(dim, up(g, 0.07), KEY, { color: AZURE, size: R / 2.2, life: 2.3, spin: -30 });
    ring(dim, "dot", g, R, 40, { color: AZURE, size: 0.6, life: 1.0 }, 0.12);
    for (const [t, k] of [[6, -1], [11, 1]]) {
      ctx.at(t, () => {
        const d = aimDir(ctx);
        const m = muzzle(ctx, { x: d.x * 0.6, y: 0.8, z: d.z * 0.6 });
        const to = add(sky, ctx.r, k * 1.4);
        beam(dim, m, to, AZURE, { size: 0.35, life: 0.3 });
        P(dim, "flare", m, { color: white(ICE, 0.5), size: 1.0, life: 0.15 });
        P(dim, "lens", to, { color: white(ICE, 0.4), size: 1.0, life: 0.5 });
        P(dim, "diamond", to, { color: FROST, count: 8, speed: 4, spread: 0.4 });
        sound(dim, "astro.beam_fire", m, 1.5, 0.8);
        sound(dim, "astro.ice_crack", to, 1.3, 0.8);
        shake(dim, p.location, 6, 0.12, 0.12);
      });
    }
    // 空の結晶の雲: 傾いた輪と六角の陣
    ctx.every(12, 4, 8, (i) => {
      P(dim, "ring_n", sky, { color: i % 2 ? ICE : AZURE, count: 40, spread: R * 0.9, dir: n, life: 0.5, var: 1 });
      P(dim, "ring_n", sky, { color: FROST, count: 28, spread: R * 0.75, life: 0.5, var: 3 });
      P(dim, "smoke", sky, { color: MIST, count: 5, spread: R * 0.5, speed: 0.3, size: 2.0 });
      if (i === 0) sound(dim, "astro.ring_spin", sky, 1.0, 0.8);
    });
    // ダイヤの雨（見た目）
    ctx.every(14, 16, 2, (i) => {
      for (let k = 0; k < 3; k++) {
        const a = rand(0, Math.PI * 2), r = Math.sqrt(Math.random()) * R;
        const q = { x: g.x + Math.cos(a) * r, y: g.y, z: g.z + Math.sin(a) * r };
        P(dim, "speedline", up(q, 6), { color: white(ICE, 0.4), dir: DOWN, count: 3, speed: 26, spread: 0.6, life: 0.3 });
        P(dim, "diamond", up(q, 7), { color: FROST, count: 2, speed: 0.5, spread: 0.6, grav: -30, life: 0.45, size: 0.9 });
      }
      for (let k = 0; k < 2; k++) {
        const a = rand(0, Math.PI * 2), r = Math.sqrt(Math.random()) * R;
        const q = onGround(dim, { x: g.x + Math.cos(a) * r, y: g.y + 1, z: g.z + Math.sin(a) * r }, 3);
        P(dim, "shard", up(q, 0.2), { color: ICE, count: 4, speed: 3, spread: 0.2 });
        P(dim, "ring_flat", up(q, 0.06), { color: AZURE, size: 0.4, life: 0.3 });
      }
      if (i % 2 === 0) sound(dim, "astro.ice_crack", g, rand(1.6, 2.0), 0.5);
    });
    // ダイヤの雨（当たり）: 16〜44 tick、4 tick ごと
    zone(ctx, g, {
      radius: R, ticks: 46, delay: 16, every: 4, damage: 2.0, height: 3.5,
      effects: [["slowness", 30, 1]], visualEvery: 99, visual() { },
      hit: { color: ICE, power: 0.6 },
      onPulse(foes) { for (const e of foes.slice(0, 6)) P(dim, "ice", chest(e), { color: FROST, count: 2, spread: 0.4, speed: 1 }); },
    });
    // 締め: 中央で結晶が噴き上がる
    ctx.at(46, () => {
      P(dim, "lens", up(g, 1.2), { color: white(ICE, 0.5), size: 1.8, life: 0.4 });
      P(dim, "pillar", up(g, 0.03), { color: white(ICE, 0.3), size: 1.6, height: 5.5, life: 0.7 });
      P(dim, "diamond", up(g, 1.0), { color: FROST, count: 16, speed: 7, spread: 0.6 });
      shatterFx(dim, up(g, 1.0), 2);
      shock(dim, g, AZURE, R, { dust: false });
      for (let k = 0; k < 6; k++) {
        const q = onGround(dim, add(g, yawRotate({ x: 1, y: 0, z: 0 }, k * 60 + 30), 2.6), 3);
        ctx.at(k % 3, () => P(dim, "pillar", up(q, 0.03), { color: ICE, size: 0.5, height: 2.2, life: 0.6 }));
      }
      sound(dim, "astro.ice_shatter", g, 0.9, 1.3);
      sound(dim, "astro.explosion", g, 1.3, 0.8);
      shake(dim, g, 16, 0.45, 0.35);
      for (const e of ctx.foes(R * 0.7, up(g, 0.8))) {
        if (!ctx.once(e, 1, "burst")) continue;
        hit(ctx, e, 6, { color: ICE, up: 0.55, kb: 0.4, dir: dirTo(g, e.location), power: 1.6 });
      }
    });
    return 30;
  },

  // =========================================================================
  //  必殺「アクシアル・ティルト」
  //  時を止め（ultOpen）、98° 傾いた巨大な環が立って回る（4〜）。左手で世界を傾ける（tilt_cast）と
  //  重力が横倒しになり、14m 以内の敵が右へ放り出される（12〜26）。28 tick 目に全員を氷の棺に閉じ込め、
  //  片膝の構え（44）から一射（51）。光は全ての棺へ枝分かれして貫き、53 tick 目に粉々に砕く（会心）。
  //  環が崩れ、天王星のオーロラと雪が残る（58〜）。
  // =========================================================================
  ult(ctx) {
    const { p, dim } = ctx;
    ultOpen(ctx, 86, 14);
    const centre = ctx.ground(ctx.loc());
    const f = ctx.f;
    const side = ctx.r;
    // 98° 傾いた重力: 下向きを 98° 横へ倒す（ほぼ真横、わずかに上）
    const grav = norm({ x: side.x * Math.sin(TILT), y: -Math.cos(TILT), z: side.z * Math.sin(TILT) });
    const n = tiltNormal(f);
    const ringC = up(centre, 4.0);
    const caught = new Map();
    let phase = 0;
    ctx.at(4, () => {
      body(p, "uranus.tilt_cast");
      sound(dim, "astro.gravity", centre, 0.6, 1.2);
      sound(dim, "astro.ring_spin", centre, 0.7, 1.2);
      emblem(dim, up(centre, 0.06), KEY, { size: 5, life: 3.8, spin: -24 });
      P(dim, "hex_circle", up(centre, 0.05), { color: AZURE, size: 6, life: 3.6, spin: 18 });
      P(dim, "circle_v", ringC, { color: ICE, dir: n, size: 2.4, life: 3.0, spin: 70 });
    });
    // 巨大な環（傾いた輪 + 回る 5 つの氷の衛星）
    ctx.every(6, 13, 4, (i) => {
      P(dim, "ring_n", ringC, { color: i % 2 ? ICE : AZURE, count: 48, spread: 7.2, dir: n, life: 0.45, var: 1 });
      P(dim, "ring_n", ringC, { color: TEAL, count: 36, spread: 6.4, dir: n, life: 0.45, var: 4 });
    });
    ctx.every(6, 26, 2, () => {
      phase += 0.21;
      for (let k = 0; k < 5; k++) {
        const q = onRing(ringC, n, 7.2, phase + k * 1.2566);
        P(dim, "glow", q, { color: FROST, size: 0.9, life: 0.15 });
        if (k % 2 === 0) P(dim, "diamond", q, { color: ICE, count: 1, speed: 0.2, size: 1.2, life: 0.2 });
      }
    });
    // 重力が横倒しになる
    ctx.at(12, () => {
      sound(dim, "astro.gravity", centre, 0.5, 1.4);
      sound(dim, "astro.gust", centre, 0.7, 1.2);
      shake(dim, centre, 24, 0.4, 0.5);
      flash(dim, centre, 24, white(AZURE, 0.6), 0.04, 0.46);
    });
    ctx.every(12, 8, 2, (i) => {
      let k = 0;
      for (const e of ctx.foes(15, up(centre, 1))) {
        caught.set(e.id, e);
        if (k++ >= 12) continue;
        launch(e, i === 0 ? 0.42 : 0.12, i === 0 ? 1.5 : 0.65, grav);
        if (i % 2 === 0) {
          P(dim, "speedline", chest(e), { color: FROST, dir: grav, count: 3, speed: 14, spread: 0.5 });
          P(dim, "ice", chest(e), { color: ICE, count: 2, spread: 0.4, speed: 1 });
        }
      }
      for (let j = 0; j < 3; j++) {
        const q = add(up(centre, rand(0.5, 4)), f, rand(-8, 8));
        P(dim, "speedline", add(q, side, rand(-8, 4)), { color: white(ICE, 0.3), dir: grav, count: 5, speed: 20, spread: 1.5 });
      }
      P(dim, "wind", up(centre, 1.2), { color: FROST, dir: grav, count: 6, speed: 12, spread: 4 });
      if (i % 3 === 0) sound(dim, "astro.wind", centre, 0.8 + i * 0.05, 0.9);
    });
    // 氷の棺
    ctx.at(28, () => {
      sound(dim, "astro.ice_crack", centre, 0.7, 1.4);
      sound(dim, "astro.ice_shatter", centre, 0.6, 0.6);
      let k = 0;
      for (const e of caught.values()) {
        if (!valid(e) || k++ >= 12) continue;
        freeze(e, 60, true);
        encase(dim, e, true);
        hit(ctx, e, 6, { color: ICE, power: 1.2, sound: "astro.ice_crack" });
      }
    });
    ctx.every(36, 2, 8, () => {
      let k = 0;
      for (const e of caught.values()) {
        if (!valid(e) || k++ >= 12) continue;
        P(dim, "hex", chest(e), { color: FROST, count: 12, spread: 1.15, size: 0.75, life: 0.5 });
      }
    });
    // 構え → 一射
    ctx.at(31, () => sound(dim, "astro.beam_charge", p.location, 0.8, 1.2));   // 1.0 秒の溜め音 → 51 で発射
    ctx.every(32, 10, 2, (i) => {
      const d = aimDir(ctx);
      const m = muzzle(ctx, d);
      P(dim, "converge", m, { color: i % 2 ? AZURE : FROST, count: 14, spread: 2.6, life: 0.35, size: 0.9 });
      P(dim, "glow", m, { color: ICE, size: 0.6 + i * 0.12, life: 0.15 });
      if (i === 6) P(dim, "circle_v", add(m, d, 0.8), { color: ICE, dir: d, size: 0.9, life: 0.6, spin: 220 });
      status(p, `§b絶対零度 ${"▰".repeat(Math.min(5, 1 + (i >> 1)))}${"▱".repeat(Math.max(0, 4 - (i >> 1)))}`, 4);
    });
    ctx.at(44, () => body(p, "uranus.zero_shot"));
    ctx.at(51, () => {
      const d = aimDir(ctx);
      const m = muzzle(ctx, d);
      sound(dim, "astro.beam_fire", m, 0.8, 1.4);
      sound(dim, "astro.ice_shatter", m, 0.8, 1.2);
      beam(dim, m, add(m, d, 18), ICE, { size: 1.2, life: 0.4 });
      P(dim, "flare", m, { color: white(ICE, 0.6), size: 2.0, life: 0.25 });
      let k = 0;
      for (const e of caught.values()) {
        if (!valid(e) || k++ >= 8) continue;
        beam(dim, m, chest(e), AZURE, { size: 0.45, life: 0.3, ends: false });
      }
      flash(dim, p.location, 24, white(ICE, 0.5), 0.05, 0.45);
      shake(dim, p.location, 20, 0.5, 0.3);
      // 光の通り道の敵（棺に入っていない相手も）
      for (const e of ctx.cone(18, 12, m, d)) {
        if (caught.has(e.id) || !ctx.once(e, 1, "zero")) continue;
        hit(ctx, e, 10, { color: ICE, kb: 0.8, up: 0.2, dir: { x: d.x, y: 0, z: d.z }, power: 1.6 });
        freeze(e, 40, true);
      }
    });
    ctx.at(53, () => {
      let k = 0;
      for (const e of caught.values()) {
        if (!valid(e) || k++ >= 12) continue;
        const c = chest(e);
        shatterFx(dim, c, 2.2);
        shock(dim, onGround(dim, e.location, 3), ICE, 2.4, { dust: false });
        hit(ctx, e, 16, { color: ICE, kb: 1.0, up: 0.5, dir: dirTo(centre, e.location), power: 2.2, crit: true, sound: "astro.hit_heavy" });
      }
      sound(dim, "astro.explosion_big", centre, 1.1, 1.2);
      sound(dim, "astro.ice_shatter", centre, 0.7, 1.5);
      shake(dim, centre, 26, 0.8, 0.5);
    });
    // 環が崩れ、オーロラと雪
    ctx.at(58, () => {
      P(dim, "lens", ringC, { color: white(ICE, 0.5), size: 3.2, life: 0.7 });
      P(dim, "ring_n", ringC, { color: FROST, count: 48, spread: 7.2, speed: -9, dir: n, life: 0.7, var: 1 });
      P(dim, "aurora", up(centre, 0.1), { color: AZURE, spread: 7, count: 14, height: 5, life: 2.4, spin: 8 });
      P(dim, "aurora", up(centre, 0.1), { color: mix(ICE, TEAL, 0.4), spread: 5, count: 10, height: 4, life: 2.4, spin: -10 });
      shock(dim, centre, ICE, 9, { dust: false });
      sound(dim, "astro.wind", centre, 0.8, 1.0);
      sound(dim, "astro.ring_spin", centre, 0.6, 1.0);
    });
    ctx.every(60, 10, 4, () => {
      const q = add(up(centre, rand(5, 7)), { x: rand(-1, 1), y: 0, z: rand(-1, 1) }, rand(0, 7));
      P(dim, "ice", q, { color: FROST, count: 3, spread: 2, speed: 0.3, grav: -2, life: 2.0, size: 0.8 });
    });
    return 64;
  },

  // =========================================================================
  //  三段目「氷晶散弾」: 至近距離へ扇の散弾。前方 5.5m（半角 40°）を凍えさせて押し返す。反動で少し下がる
  // =========================================================================
  combo3(ctx, target) {
    const { p, dim } = ctx;
    const f = ctx.liveDir();
    const d = aimDir(ctx);
    const m = muzzle(ctx, d);
    sound(dim, "astro.beam_fire", m, 1.7, 0.8);
    sound(dim, "astro.ice_shatter", m, 1.4, 0.8);
    sound(dim, "astro.hit_metal", m, 1.2, 0.5);
    P(dim, "flare", m, { color: white(ICE, 0.5), size: 1.3, life: 0.15 });
    P(dim, "ring", m, { color: AZURE, size: 1.2, life: 0.2 });
    for (let k = -3; k <= 3; k++) {
      const dd = yawRotate(d, k * 9);
      P(dim, "thrust", m, { color: k % 2 ? AZURE : white(ICE, 0.4), dir: { x: dd.x, y: dd.y + (k % 2) * 0.05, z: dd.z }, len: 4.4 - Math.abs(k) * 0.35, size: 0.5, life: 0.16 });
    }
    P(dim, "shard", add(m, d, 1.4), { color: ICE, count: 12, speed: 9, spread: 0.4 });
    P(dim, "ice", add(m, d, 2.2), { color: FROST, count: 6, speed: 5, spread: 0.8 });
    P(dim, "smoke", add(m, d, 1.0), { color: MIST, count: 3, spread: 0.4, speed: 1.2, size: 0.8 });
    lunge(ctx, { x: -f.x, y: 0, z: -f.z }, 0.35, 0.05);
    for (const e of ctx.cone(5.5, 40, ctx.chest(), d)) {
      hit(ctx, e, 5, { color: ICE, kb: 1.0, up: 0.25, dir: f, power: 1.3, sound: "astro.ice_crack" });
      freeze(e, 30, false);
      encase(dim, e);
    }
    if (target && valid(target)) P(dim, "impact", chest(target), { color: white(ICE, 0.4), size: 1.4, life: 0.15 });
    return 10;
  },

  // =========================================================================
  //  変身の締め: 横倒しの環が体のまわりで回り（5 つの衛星）、氷晶が散って、足元から地面が凍っていく
  // =========================================================================
  burst(ctx) {
    const { dim } = ctx;
    const g = ctx.ground(ctx.loc());
    const c = up(g, 1.1);
    const n = tiltNormal(ctx.f);
    sound(dim, "astro.ring_spin", g, 0.9, 1.0);
    sound(dim, "astro.ice_crack", g, 1.0, 0.9);
    sound(dim, "astro.wind", g, 1.2, 0.7);
    emblem(dim, up(g, 0.05), KEY, { size: 1.8, life: 1.8 });
    ctx.every(0, 8, 2, (i) => {
      P(dim, "ring_n", c, { color: i % 2 ? ICE : AZURE, count: 36, spread: 1.5 + i * 0.12, dir: n, life: 0.25, var: 1 });
      for (let k = 0; k < 5; k++) {
        P(dim, "glow", onRing(c, n, 1.5 + i * 0.12, i * 0.55 + k * 1.2566), { color: FROST, size: 0.5, life: 0.15 });
      }
    });
    ctx.at(10, () => {
      shatterFx(dim, c, 1.6);
      P(dim, "diamond", c, { color: FROST, count: 8, speed: 4, spread: 0.5 });
      P(dim, "flare", c, { color: white(ICE, 0.5), size: 1.4, life: 0.3 });
      sound(dim, "astro.ice_shatter", c, 1.2, 0.9);
    });
    ctx.every(10, 4, 3, (i) => {
      P(dim, "ring_flat", up(g, 0.06 + i * 0.01), { color: i % 2 ? ICE : AZURE, size: 1 + i * 1.1, life: 0.7 });
      ring(dim, "hex", g, 1.2 + i * 1.3, 16, { color: i % 2 ? FROST : AZURE, size: 0.6, life: 1.4 }, 0.08);
    });
    ctx.at(12, () => {
      P(dim, "hex_circle", up(g, 0.05), { color: ICE, size: 2.4, life: 2.0, spin: 20 });
      P(dim, "smoke", up(g, 0.2), { color: MIST, count: 8, spread: 2, speed: 0.6, size: 1.4 });
    });
    return 20;
  },

  // =========================================================================
  //  パッシブ frost_aura
  // =========================================================================
  passive: {
    /** 1 秒ごとに 4.5m 以内の敵対的な相手の足を鈍らせる。三連装填中は弩のまわりに 3 つの光。 */
    tick(p, st) {
      const dim = p.dimension;
      st.cd = (st.cd ?? 0) - 5;
      if (st.n % 4 === 0 && fxScale() >= 1) {
        P(dim, "ice", up(p.location, 0.4), { color: FROST, count: 1, spread: 0.5, speed: 0.2, size: 0.5, life: 0.8 });
      }
      if (st.cd <= 0) {
        st.cd = 20;
        const foes = hostilesNear(p, chest(p), 4.5);
        if (foes.length) {
          ring(dim, "dot", p.location, 4.5, 24, { color: AZURE, size: 0.4, life: 0.5 }, 0.15);
          for (const e of foes.slice(0, 8)) {
            effect(e, "slowness", 30, 1);
            P(dim, "ice", up(e.location, 0.3), { color: FROST, count: 2, spread: 0.4, speed: 0.4, size: 0.6 });
          }
        }
      }
      const until = armed.get(p.id);
      if (until !== undefined) {
        if (until < now()) {
          armed.delete(p.id);
          sound(dim, "astro.power_down", p.location, 1.6, 0.4);
        } else if (st.n % 2 === 0) {
          const c = up(p.location, 1.35);
          const n = tiltNormal({ x: 0, y: 0, z: 1 });
          for (let k = 0; k < 3; k++) P(dim, "glow", onRing(c, n, 0.9, now() * 0.25 + k * 2.094), { color: AZURE, size: 0.35, life: 0.3 });
        }
      }
    },
    /** 殴ってきた相手を凍えさせる（鈍化・弱体化・凍傷）。同じ相手には 1 秒に 1 回。 */
    onHurt(p, attacker, dmg) {
      if (!attacker || !valid(attacker) || attacker.id === p.id || !isTarget(p, attacker)) return;
      const k = `${p.id}|${attacker.id}`;
      if ((chillCd.get(k) ?? -99) > now()) return;
      chillCd.set(k, now() + 20);
      if (chillCd.size > 200) chillCd.clear();
      const dim = p.dimension;
      freeze(attacker, 50, false);
      effect(attacker, "weakness", 50, 0);
      encase(dim, attacker);
      sound(dim, "astro.ice_crack", chest(attacker), 1.3, 0.7);
      hit(p, attacker, 2, { color: ICE, quiet: true, nova: 0, xp: 0 });
    },
    /** 倒した敵は氷になって砕ける（見た目）。 */
    onKill(p, victim) {
      try {
        if (!victim) return;
        const c = chest(victim);
        if (!finite(c)) return;
        shatterFx(p.dimension, c, 1.4);
        sound(p.dimension, "astro.ice_shatter", c, 1.3, 0.7);
      } catch (_) { /* もう居ない */ }
    },
  },

  meta: { noDamage: [] },
});
