// ===========================================================================
//  演出: パーティクル・音・画面揺れ・フラッシュ・カットイン・全身モーション
//
//  パーティクルは全て「白で描いて色を後から乗せる」汎用品なので、ここで
//  MolangVariableMap に色・大きさ・寿命・回転を詰めて渡す。
// ===========================================================================
import { MolangVariableMap } from "@minecraft/server";
import { ANIM_META } from "./anim_meta.js";
import { weaponOf } from "./config.js";
import { cmd, add, scale, basis, norm, rand, valid, allPlayers, dist, heldItem } from "./util.js";

const VARS = ["size", "life", "rot", "count", "speed", "spread", "vx", "vy", "vz", "var",
              "height", "spin", "rate", "grav"];

// 一度に出す粒の上限（技が重なってもクライアントが詰まらないように）
let budget = 0;
let budgetTick = -1;
const BUDGET_PER_TICK = 260;

function spendBudget(tick) {
  if (tick !== budgetTick) { budgetTick = tick; budget = 0; }
  return ++budget <= BUDGET_PER_TICK;
}

let tickRef = () => 0;
export function setTickSource(fn) { tickRef = fn; }

/**
 * パーティクルを一つ出す。
 * o.color [r,g,b] (0..1) / o.size / o.life / o.rot / o.count / o.speed / o.spread /
 * o.dir {x,y,z} / o.var / o.height / o.spin / o.rate / o.grav
 */
export function P(dim, id, loc, o = {}) {
  if (!dim || !loc) return;
  if (!spendBudget(tickRef())) return;
  try {
    const m = new MolangVariableMap();
    // 色を渡さなければパーティクル側の既定色（煙は灰、土煙は土色、光は白）になる
    const c = o.color;
    if (c) {
      m.setFloat("variable.cr", c[0]);
      m.setFloat("variable.cg", c[1]);
      m.setFloat("variable.cb", c[2]);
    }
    if (o.dir) { o.vx = o.dir.x; o.vy = o.dir.y; o.vz = o.dir.z; }
    for (const k of VARS) {
      if (typeof o[k] === "number" && Number.isFinite(o[k])) m.setFloat(`variable.${k}`, o[k]);
    }
    dim.spawnParticle(`hd:${id}`, loc, m);
  } catch (_) { }
}

export function white(c, t) {
  return [c[0] + (1 - c[0]) * t, c[1] + (1 - c[1]) * t, c[2] + (1 - c[2]) * t];
}

// ---------------------------------------------------------------------------
//  形のある演出
// ---------------------------------------------------------------------------
/** 点 a から b へ粒を並べる（光線・鎖・斬撃線）。 */
export function line(dim, id, a, b, step, o = {}) {
  const d = dist(a, b);
  const n = Math.max(1, Math.ceil(d / step));
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    P(dim, id, { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t }, o);
  }
}

/** 水平の輪。 */
export function ring(dim, id, c, radius, n, o = {}, y = 0.1) {
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    P(dim, id, { x: c.x + Math.cos(a) * radius, y: c.y + y, z: c.z + Math.sin(a) * radius }, o);
  }
}

/**
 * 3D の斬撃の軌跡。center を中心に、forward 方向を 0° として sweep 軸の側へ
 * a0→a1 度の円弧を描く。tilt で斬り筋を傾ける（0 = 水平、90 = 縦）。
 * steps 個の発光を ticks 回に分けて出すと「振り抜く」動きになる。
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
  pts.forEach((p, i) => {
    const k = i / steps;
    // 先端ほど太く白い（振り抜いた刃先）
    P(dim, "trail", p, { color: white(color, 0.15 + k * 0.35), size: size * (0.5 + k * 0.7),
                         life: (o.life ?? 0.22) * (0.6 + k * 0.6) });
    if (o.inner !== false) {
      const q = add(center, scale({ x: p.x - center.x, y: p.y - center.y, z: p.z - center.z }, 0.82));
      P(dim, "trail", q, { color, size: size * 0.45, life: (o.life ?? 0.22) * 0.8 });
    }
  });
  if (o.sparks !== false) {
    const tip = pts[pts.length - 1];
    P(dim, "spark", tip, { color, count: 4, speed: 5, size: 0.8 });
  }
  return pts;
}

/** 当たりの瞬間: 衝撃・火花・輪。power で規模が変わる。 */
export function burst(dim, loc, color, power = 1) {
  P(dim, "impact", loc, { color: white(color, 0.3), size: 0.9 * power, life: 0.14 + 0.04 * power });
  P(dim, "spark", loc, { color, count: Math.round(6 + 5 * power), speed: 6 + 2 * power, size: 1 });
  P(dim, "ring", loc, { color, size: 0.9 * power, life: 0.25 });
  if (power >= 1.5) P(dim, "glow", loc, { color: white(color, 0.5), size: 2.4 * power, life: 0.18 });
}

export function slash(dim, loc, color, rot, size = 1, kind = "slash", life) {
  P(dim, kind, loc, { color, rot, size, life });
}

export function kanji(dim, loc, idx, color, size = 2.6) {
  P(dim, "kanji", loc, { color: white(color, 0.25), var: idx, size, life: 1.0, rot: rand(-12, 12) });
}

export function afterimage(dim, loc, color, life = 0.4) {
  P(dim, "afterimage", { x: loc.x, y: loc.y + 1.0, z: loc.z }, { color, size: 1.0, life });
}

export function sound(dim, id, loc, pitch = 1, volume = 1) {
  try { dim.playSound(id, loc, { pitch, volume }); } catch (_) { }
}

// ---------------------------------------------------------------------------
//  画面
// ---------------------------------------------------------------------------
/** 近くのプレイヤーの画面を揺らす。 */
export function shake(dim, loc, radius, intensity, seconds = 0.3) {
  for (const p of allPlayers()) {
    if (p.dimension?.id !== dim.id) continue;
    const d = dist(p.location, loc);
    if (d > radius) continue;
    const k = intensity * (1 - d / radius * 0.6);
    cmd(p, `camerashake add @s ${k.toFixed(2)} ${seconds.toFixed(2)} positional`);
  }
}

/** 色付きのフラッシュ（camera fade）。必殺技の決め所で使う。 */
export function flash(dim, loc, radius, color, hold = 0.08, out = 0.35) {
  const [r, g, b] = color.map((c) => Math.round(Math.min(1, c) * 255));
  for (const p of allPlayers()) {
    if (p.dimension?.id !== dim.id) continue;
    if (dist(p.location, loc) > radius) continue;
    cmd(p, `camera @s fade time 0.04 ${hold.toFixed(2)} ${out.toFixed(2)} color ${r} ${g} ${b}`);
  }
}

/** 必殺技のカットイン: 技名を大きく、英名を下に。周りのプレイヤーにも見える。 */
export function cutin(player, tc, name, en) {
  const dim = player.dimension;
  for (const p of allPlayers()) {
    if (p.dimension?.id !== dim.id) continue;
    if (dist(p.location, player.location) > 28) continue;
    try {
      const self = p.id === player.id;
      p.onScreenDisplay.setTitle(`${tc}§l${name}`, {
        subtitle: self ? `§f§o${en}` : `§7— ${player.name} —  §f§o${en}`,
        fadeInDuration: 2, stayDuration: 26, fadeOutDuration: 8,
      });
    } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  全身モーション（playanimation）
//  モーションは武器ごとに「持ち姿勢からの差分」で書き出してあるので、持っている武器の
//  版を選んで再生する（animation.hd.p.<武器>.<名前>）。
// ---------------------------------------------------------------------------
function play(player, name, controller, blendOut) {
  if (!valid(player)) return;
  try {
    if (typeof player.playAnimation === "function") {
      player.playAnimation(name, { blendOutTime: blendOut, controller, stopExpression: "0" });
      return;
    }
  } catch (_) { /* コマンドへ */ }
  cmd(player, `playanimation @s ${name} none ${blendOut} "0" ${controller}`);
}

export function body(player, anim, controller = "hd.act", blendOut) {
  const w = weaponOf(heldItem(player));
  if (!w) return;
  const key = `${w.key}.${anim}`;
  const meta = ANIM_META[key];
  if (!meta) return;
  // 一回転して終わるモーションはブレンドすると逆回転して見えるので切る
  play(player, `animation.hd.p.${key}`, controller, blendOut ?? (meta[1] ? 0.12 : 0.0));
}

/** ループする全身モーションを止める（同じコントローラに空のモーションを流す）。 */
export function bodyStop(player, controller = "hd.act") {
  play(player, "animation.hd.p.none", controller, 0.15);
}

/** 武器ごとの持ち姿勢（両手持ち・逆手・獣の構え…）。武器が無ければ解除。 */
export function holdPose(player, w) {
  if (w && ANIM_META[`hold.${w.key}`]) play(player, `animation.hd.p.hold.${w.key}`, "hd.hold", 0.2);
  else play(player, "animation.hd.p.none", "hd.hold", 0.2);
}

export function dirToYawDeg(d) {
  return Math.atan2(-d.x, d.z) * 180 / Math.PI;
}

export { norm };
