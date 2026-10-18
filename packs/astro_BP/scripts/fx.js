// ===========================================================================
//  演出: パーティクル・音・画面揺れ・フラッシュ・カットイン・全身モーション・グリフ
//
//  パーティクルは全て白で描いたスプライトで、色はここで MolangVariableMap に詰めて渡す
//  （DESIGN §4.7。変数 v.cr v.cg v.cb / v.size v.life v.rot v.count v.speed v.spread /
//   v.vx v.vy v.vz / v.var / v.height v.spin v.rate v.grav v.len）。
//  ID は "astro:" を付けずに渡す（P(dim, "glow", …) → astro:glow）。
//
//  予算: 1 tick に出すパーティクル（spawnParticle の回数）は BUDGET_PER_TICK × 設定の倍率まで。
//  超えた分は黙って捨てるので、大事な層（当たりの光）を先に、飾り（火の粉）を後に出すこと。
// ===========================================================================
import { MolangVariableMap } from "@minecraft/server";
import { ANIM_META } from "./anim_meta.js";
import { PLANETS } from "./data.js";
import { G } from "./glyphs.js";
import {
  cmd, add, scale, basis, rand, valid, allPlayers, dist, now, fmt, report, yawDeg,
} from "./util.js";

/** DESIGN §4.7 のパーティクル ID（"astro:" を除く）。 */
export const PARTICLES = [
  "glow", "trail", "dot", "spark", "star", "impact", "flare",
  "ring", "ring_flat", "shock_flat", "circle", "circle_v", "hex_circle", "emblem", "hex", "scan",
  "pillar", "beam", "slash", "slash_big", "slash_flat", "cross", "thrust",
  "speedline", "wind", "vortex", "converge", "orbit", "aura", "nano", "nano_stream",
  "smoke", "dust", "debris", "ember", "flame", "plasma", "bolt", "arc", "shard", "ice", "diamond",
  "droplet", "splash", "bubble", "wave", "cloud", "aurora", "meteor", "black_hole", "void",
  "warning", "afterimage", "lens",
];

const VARS = ["size", "life", "rot", "count", "speed", "spread", "vx", "vy", "vz", "var",
              "height", "spin", "rate", "grav", "len"];

// ---------------------------------------------------------------------------
//  予算
// ---------------------------------------------------------------------------
export const BUDGET_PER_TICK = 260;
let budget = 0;
let budgetTick = -1;
let fxK = 1.0;

/** 演出の量の倍率（main が全員の設定の最小値を毎秒入れる）。 */
export function setFxScale(k) { fxK = Math.max(0.2, Math.min(2, k)); }
/** 今の演出の量の倍率（0.5 少ない / 1 標準 / 1.5 多い）。飾りの層を省く判断に使える。 */
export function fxScale() { return fxK; }

function spend() {
  const t = now();
  if (t !== budgetTick) { budgetTick = t; budget = 0; }
  return ++budget <= BUDGET_PER_TICK * fxK;
}

/** この tick に残っている予算（大きな演出の前に確かめる用）。 */
export function budgetLeft() {
  if (now() !== budgetTick) return Math.floor(BUDGET_PER_TICK * fxK);
  return Math.max(0, Math.floor(BUDGET_PER_TICK * fxK) - budget);
}

/**
 * パーティクルを一つ出す。
 * @param {Dimension} dim
 * @param {string} id     "glow" など（"astro:" は付けない。":" を含めばそのまま使う）
 * @param {{x,y,z}} loc
 * @param {object} [o]    color [r,g,b] 0..1 / size / life（秒）/ rot（度）/ count / speed / spread /
 *                        dir {x,y,z}（= vx,vy,vz）/ var / height / spin / rate / grav / len
 */
export function P(dim, id, loc, o = {}) {
  if (!dim || !loc) return;
  if (!Number.isFinite(loc.x) || !Number.isFinite(loc.y) || !Number.isFinite(loc.z)) return;
  if (!spend()) return;
  try {
    const m = new MolangVariableMap();
    const c = o.color;
    if (c) {
      m.setFloat("variable.cr", c[0]);
      m.setFloat("variable.cg", c[1]);
      m.setFloat("variable.cb", c[2]);
    }
    const vals = o.dir ? { ...o, vx: o.dir.x, vy: o.dir.y, vz: o.dir.z } : o;
    for (const k of VARS) {
      let v = vals[k];
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      if (k === "count" && fxK < 1) v = Math.max(1, Math.round(v * fxK));
      m.setFloat(`variable.${k}`, v);
    }
    dim.spawnParticle(id.includes(":") ? id : `astro:${id}`, loc, m);
  } catch (_) { /* 範囲外のチャンク等 */ }
}

// ---------------------------------------------------------------------------
//  色
// ---------------------------------------------------------------------------
/** c を白へ t (0..1) だけ寄せる。 */
export function white(c, t) {
  return [c[0] + (1 - c[0]) * t, c[1] + (1 - c[1]) * t, c[2] + (1 - c[2]) * t];
}
/** a と b を t で混ぜる。 */
export function mix(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}
/** c を k 倍に暗くする。 */
export function shade(c, k) { return [c[0] * k, c[1] * k, c[2] * k]; }

// ---------------------------------------------------------------------------
//  形のある演出
// ---------------------------------------------------------------------------
/** 点 a から b へ step m 間隔で粒を並べる（光線・鎖・斬撃線）。 */
export function line(dim, id, a, b, step, o = {}) {
  const d = dist(a, b);
  const n = Math.min(60, Math.max(1, Math.ceil(d / Math.max(0.1, step))));
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    P(dim, id, { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t }, o);
  }
}

/** 中心 c・半径 radius の水平の輪に n 個並べる（y は c.y からの高さ）。 */
export function ring(dim, id, c, radius, n, o = {}, y = 0.1) {
  const off = o.phase ?? 0;
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2 + off;
    P(dim, id, { x: c.x + Math.cos(a) * radius, y: c.y + y, z: c.z + Math.sin(a) * radius }, o);
  }
}

/**
 * 3D の斬撃の軌跡。center を中心に forward を 0° として a0→a1 度の円弧を描く。
 * tilt で斬り筋を傾ける（0 = 水平、90 = 縦）。o.steps / o.size / o.life / o.inner / o.sparks /
 * o.id（既定 "trail"）。返り値は円弧の点の配列（当たり判定に使える）。
 */
export function arc(dim, center, forward, radius, a0, a1, tilt, color, o = {}) {
  const { f, r, u } = basis(forward);
  const tr = tilt * Math.PI / 180;
  const s = { x: r.x * Math.cos(tr) + u.x * Math.sin(tr), y: r.y * Math.cos(tr) + u.y * Math.sin(tr),
              z: r.z * Math.cos(tr) + u.z * Math.sin(tr) };
  const steps = o.steps ?? 14;
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const a = (a0 + (a1 - a0) * (i / steps)) * Math.PI / 180;
    pts.push({
      x: center.x + (f.x * Math.cos(a) + s.x * Math.sin(a)) * radius,
      y: center.y + (f.y * Math.cos(a) + s.y * Math.sin(a)) * radius,
      z: center.z + (f.z * Math.cos(a) + s.z * Math.sin(a)) * radius,
    });
  }
  const size = o.size ?? 0.9;
  const id = o.id ?? "trail";
  pts.forEach((p, i) => {
    const k = i / steps;
    // 先端ほど太く白い（振り抜いた刃先）
    P(dim, id, p, { color: white(color, 0.15 + k * 0.35), size: size * (0.5 + k * 0.7),
                    life: (o.life ?? 0.22) * (0.6 + k * 0.6) });
    if (o.inner !== false && i % 2 === 0) {
      const q = add(center, scale({ x: p.x - center.x, y: p.y - center.y, z: p.z - center.z }, 0.8));
      P(dim, "trail", q, { color, size: size * 0.45, life: (o.life ?? 0.22) * 0.8 });
    }
  });
  if (o.sparks !== false) {
    P(dim, "spark", pts[pts.length - 1], { color, count: 4, speed: 5, size: 0.8 });
  }
  return pts;
}

/** 当たりの瞬間: 衝撃・火花・輪。power で規模が変わる（1 = 普通、2 = 大技）。 */
export function burst(dim, loc, color, power = 1) {
  P(dim, "impact", loc, { color: white(color, 0.3), size: 0.9 * power, life: 0.14 + 0.04 * power });
  P(dim, "spark", loc, { color, count: Math.round(6 + 5 * power), speed: 6 + 2 * power, size: 1 });
  P(dim, "ring", loc, { color, size: 0.9 * power, life: 0.25 });
  if (power >= 1.5) P(dim, "glow", loc, { color: white(color, 0.5), size: 2.4 * power, life: 0.18 });
}

/**
 * 地を走る衝撃波（足元の輪＋土煙＋破片）。loc は地面の高さ。
 * o.size（半径の目安、既定 radius）/ o.life / o.dust（false で土煙なし）/ o.debris（破片の数）
 */
export function shock(dim, loc, color, radius = 3, o = {}) {
  const g = { x: loc.x, y: loc.y + 0.08, z: loc.z };
  P(dim, "shock_flat", g, { color, size: o.size ?? radius, life: o.life ?? 0.5 });
  P(dim, "ring_flat", { ...g, y: g.y + 0.04 }, { color: white(color, 0.35), size: (o.size ?? radius) * 1.1, life: (o.life ?? 0.5) * 0.8 });
  if (o.dust !== false) P(dim, "dust", { ...g, y: g.y + 0.1 }, { count: Math.round(8 + radius * 3), speed: 3 + radius, size: 1.2, spread: radius * 0.3 });
  if (o.debris) P(dim, "debris", { ...g, y: g.y + 0.2 }, { count: o.debris, speed: 5 + radius, spread: radius * 0.25 });
}

/**
 * 光線（beam パーティクル: a から b へ伸びる帯）＋両端の光。
 * o.size（太さ）/ o.life / o.core（芯の色。既定 白寄り）/ o.ends（false で端の光なし）
 */
export function beam(dim, a, b, color, o = {}) {
  const d = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z };
  const L = Math.hypot(d.x, d.y, d.z);
  if (L < 0.05) return;
  const n = { x: d.x / L, y: d.y / L, z: d.z / L };
  P(dim, "beam", a, { color, dir: n, len: L, size: o.size ?? 0.5, life: o.life ?? 0.25 });
  P(dim, "beam", a, { color: o.core ?? white(color, 0.7), dir: n, len: L, size: (o.size ?? 0.5) * 0.45, life: (o.life ?? 0.25) * 0.8 });
  if (o.ends !== false) {
    P(dim, "glow", a, { color: white(color, 0.4), size: (o.size ?? 0.5) * 2.4, life: 0.15 });
    P(dim, "flare", b, { color: white(color, 0.5), size: (o.size ?? 0.5) * 2.0, life: 0.2 });
  }
}

/**
 * ナノマシンの奔流: from から to へ螺旋を描いて流れ込む粒の列＋明滅する粒。
 * o.count / o.life（秒）/ o.size / o.spread
 */
export function swarm(dim, from, to, color, o = {}) {
  const d = { x: to.x - from.x, y: to.y - from.y, z: to.z - from.z };
  P(dim, "nano_stream", from, { color, dir: d, count: o.count ?? 10, life: o.life ?? 0.3, size: o.size ?? 0.5, spread: o.spread ?? 0.35 });
  P(dim, "nano", from, { color: white(color, 0.3), dir: d, count: Math.max(2, Math.round((o.count ?? 10) / 3)), life: o.life ?? 0.3, size: (o.size ?? 0.5) * 0.8 });
}

/**
 * 惑星紋章の陣（水平）。planet は惑星キー・PLANETS[key]・order（1..9）のどれでもよい。
 * o.size / o.life / o.spin / o.color（既定 その惑星の発光色）
 */
export function emblem(dim, loc, planet, o = {}) {
  const pl = typeof planet === "string" ? PLANETS[planet] : (typeof planet === "object" ? planet : null);
  const order = typeof planet === "number" ? planet : (pl?.order ?? 1);
  P(dim, "emblem", loc, { color: o.color ?? pl?.color ?? [1, 1, 1], var: Math.max(0, order - 1),
                          size: o.size ?? 2.4, life: o.life ?? 1.2, spin: o.spin ?? 40 });
}

export function slash(dim, loc, color, rot, size = 1, kind = "slash", life) {
  P(dim, kind, loc, { color, rot, size, life });
}

/** 人型の残像（スーツの輪郭）。loc は足元。 */
export function afterimage(dim, loc, color, life = 0.4, rot) {
  P(dim, "afterimage", { x: loc.x, y: loc.y + 1.0, z: loc.z }, { color, size: 1.0, life, rot });
}

/** 効果音（astro.<名前> を渡す）。 */
export function sound(dim, id, loc, pitch = 1, volume = 1) {
  if (!dim || !loc) return;
  try { dim.playSound(id, loc, { pitch, volume }); } catch (_) { }
}

// ---------------------------------------------------------------------------
//  画面
// ---------------------------------------------------------------------------
/** 近くのプレイヤーの画面を揺らす（intensity 0..1 目安、seconds 秒）。 */
export function shake(dim, loc, radius, intensity, seconds = 0.3) {
  for (const p of allPlayers()) {
    try {
      if (p.dimension?.id !== dim.id) continue;
      const d = dist(p.location, loc);
      if (d > radius) continue;
      const k = Math.min(4, intensity * (1 - d / radius * 0.6));
      cmd(p, `camerashake add @s ${fmt(k)} ${fmt(seconds)} positional`);
    } catch (_) { }
  }
}

/** 色付きのフラッシュ（camera fade）。大技の決め所で使う。color は 0..1。 */
export function flash(dim, loc, radius, color, hold = 0.08, out = 0.35) {
  const [r, g, b] = color.map((c) => Math.round(Math.max(0, Math.min(1, c)) * 255));
  for (const p of allPlayers()) {
    try {
      if (p.dimension?.id !== dim.id) continue;
      if (dist(p.location, loc) > radius) continue;
      cmd(p, `camera @s fade time 0.04 ${fmt(hold)} ${fmt(out)} color ${r} ${g} ${b}`);
    } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  グリフ（glyphs.js の G）。無いキーは fallback に落とす
// ---------------------------------------------------------------------------
/** G を path（"emblem.earth" や ["move", key, "skill", "ready"]）でたどる。 */
export function glyph(path, fallback = "") {
  const parts = Array.isArray(path) ? path : String(path).split(".");
  let v = G;
  for (const k of parts) {
    if (v === undefined || v === null) return fallback;
    v = v[k];
  }
  return typeof v === "string" ? v : fallback;
}

// ---------------------------------------------------------------------------
//  アクションバーの優先表示（HUD に上書きされないように）
// ---------------------------------------------------------------------------
const hold = new Map();   // playerId -> 期限 tick

/** アクションバーに text を出し、ticks の間 HUD を止める。 */
export function announce(p, text, ticks = 30) {
  hold.set(p.id, now() + ticks);
  try { p.onScreenDisplay.setActionBar(text); } catch (_) { }
}
export function hudHeld(p) { return (hold.get(p.id) ?? 0) > now(); }
export function forgetFx(id) { hold.delete(id); }

/** 画面中央のタイトル（失敗しても無視）。 */
export function title(p, text, sub, o = {}) {
  try {
    p.onScreenDisplay.setTitle(text, {
      subtitle: sub, fadeInDuration: o.fadeIn ?? 2, stayDuration: o.stay ?? 30, fadeOutDuration: o.fadeOut ?? 8,
    });
  } catch (_) { }
}

/**
 * 必殺技のカットイン: 技名を大きく、紋章と英名を下に。周り 28m のプレイヤーにも見える。
 * planet は data.js の PLANETS[key]。
 */
export function cutin(player, planet, name, en) {
  const dim = player.dimension;
  const em = glyph(["emblem", planet.key], planet.symbol ?? "");
  for (const p of allPlayers()) {
    try {
      if (p.dimension?.id !== dim.id) continue;
      if (dist(p.location, player.location) > 28) continue;
      const self = p.id === player.id;
      title(p, `${planet.tc}${name}`,
        self ? `§r${em}§r §f${en}` : `§r${em}§r §7${player.name} — §f${en}`,
        { fadeIn: 2, stay: 28, fadeOut: 8 });
    } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  全身モーション（playanimation）
//  名前は animation.astro.p.<name>。ANIM_META（anim_meta.js）に無い名前は再生しない。
//  コントローラ: astro.act（技・コンボ）/ astro.move（機動）/ astro.pose（変身・ホバー）
// ---------------------------------------------------------------------------
function play(player, name, controller, blendOut) {
  if (!valid(player)) return false;
  try {
    if (typeof player.playAnimation === "function") {
      player.playAnimation(name, { blendOutTime: blendOut, controller, stopExpression: "0" });
      return true;
    }
  } catch (_) { /* コマンドへ */ }
  return cmd(player, `playanimation @s ${name} none ${fmt(blendOut)} "0" ${controller}`);
}

/** そのモーションがあるか（anim_meta.js に載っているか）。 */
export function hasBody(name) { return !!ANIM_META[name]; }
/** モーションの長さ（tick）。無ければ fallback。 */
export function bodyTicks(name, fallback = 10) {
  const m = ANIM_META[name];
  return m ? Math.round(m[0] * 20) : fallback;
}

/**
 * 全身モーションを再生する。name は "henshin" や "earth.tidal_slash"（animation.astro.p. を除く）。
 * 無いモーションは何もしない（false）。
 */
export function body(player, name, controller = "astro.act", blendOut) {
  const meta = ANIM_META[name];
  if (!meta) return false;
  try {
    return play(player, `animation.astro.p.${name}`, controller, blendOut ?? (meta[1] ? 0.12 : 0.0));
  } catch (e) { report("fx.body", e); return false; }
}

/** ループする全身モーションを止める（同じコントローラに none を流す）。 */
export function bodyStop(player, controller = "astro.act") {
  if (!ANIM_META.none) return false;
  return play(player, "animation.astro.p.none", controller, 0.15);
}

export { yawDeg, rand };
