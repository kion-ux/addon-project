// ===========================================================================
//  スラスター機動（変身中だけ）と解除の長押し、ナノ・バリア
//
//   二段ジャンプ    空中でジャンプ → 背中のスラスターで跳ぶ（形態ごとに air_jumps 回）
//   ホバー          空中でジャンプ長押し → ゆっくり上昇／滞空（星力を毎秒 hover_cost 消費）
//   ブースト・ダッシュ 空中でスニーク → 視線の方向へ噴射（air_dash 回）
//   回避ステップ    地上でスニークを素早く 2 回 → 移動方向（止まっていれば後ろ）へ。直後は無敵
//   ジャスト回避    回避の無敵中に攻撃を受けると発動（超新星 +15、周りの敵が鈍る）
//   ヒーロー着地    高所から落ちると片膝をつく。機動の後の落下ダメージは無効
//   疾走            ダッシュ中は speed 効果（形態ごと）と足元の噴射
//   変身解除        スニークしたまま 2 秒静止
//   ナノ・バリア    スニーク＋右クリック（ゲージ未満）。0.7 秒ほぼ無敵・飛び道具を弾き返す
// ===========================================================================
import { COMMON, PLANETS } from "./data.js";
import {
  S, isReady, isBusy, energy, addEnergy, addRecord, setNovaRaw,
} from "./state.js";
import { P, afterimage, body, bodyStop, sound, white, ring, announce, title, glyph } from "./fx.js";
import { addNova, entitiesNear } from "./combat.js";
import {
  allPlayers, knock, effect, removeEffect, flatDir, viewDir, health, valid, now, velocity, BUS,
  chest, rightOf, norm, sub, scale, isPlayer, report,
} from "./util.js";

/** 強さの調整値（実機で跳びすぎ／足りない場合はここだけ直す）。 */
export const TUNE = {
  jumpUp: 0.7,         // 二段ジャンプの上向き速度
  jumpCarry: 0.5,      // 二段ジャンプで足す水平速度
  boost: 1.15,         // ブースト・ダッシュの水平速度
  boostUp: 0.14,
  step: 1.15,          // 回避ステップの水平速度
  stepUp: 0.18,
  stepWindow: 7,       // スニーク 2 回押しの受付 (tick)
  stepCooldown: 14,
  iframes: 8,          // 回避直後の無敵 (tick)
  hoverDelay: 7,       // ジャンプを押し続けてからホバーになるまで (tick)
  heroVy: -0.95,       // ヒーロー着地になる落下速度
  stillEps: 0.035,     // 静止とみなす 1 tick の移動量 (m)
};

const mv = new Map();   // playerId -> 機動の状態

function M(p) {
  let m = mv.get(p.id);
  if (!m) {
    m = { sneak: false, jump: false, ground: true, airT: 0, jumps: 0, dashes: 0, lastSneak: -99,
          stepCd: 0, noFall: false, noFallUntil: -1, minVy: 0, dodgeUntil: -1, justCd: 0, jumpHeld: 0,
          hovering: false, hoverT: 0, last: null, used: false, groundT: 0 };
    mv.set(p.id, m);
  }
  return m;
}

/** 技・機動で宙に浮いたら、次の着地まで落下ダメージを消す。 */
export function markAirborne(p) {
  if (!valid(p) || !isPlayer(p)) return;
  const m = M(p);
  m.noFall = true;
  m.used = true;
}

/** ジャンプのボタン（新しい版の inputInfo があれば使い、無ければ isJumping）。 */
function jumpPressed(p) {
  try {
    const info = p.inputInfo;
    if (info && typeof info.getButtonState === "function") {
      return String(info.getButtonState("Jump")) === "Pressed";
    }
  } catch (_) { }
  try { return p.isJumping === true; } catch (_) { return false; }
}

function sneaking(p) {
  try { return p.isSneaking === true; } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
//  毎 tick
// ---------------------------------------------------------------------------
export function tickMobility() {
  for (const p of allPlayers()) {
    try { tickOne(p); } catch (e) { report("mobility", e); }
  }
}

function tickOne(p) {
  const m = M(p);
  const st = S(p);
  const t = now();
  let ground = false;
  try { ground = !!p.isOnGround; } catch (_) { }
  const vel = velocity(p);
  const loc = p.location;
  const moved = m.last ? Math.hypot(loc.x - m.last.x, loc.z - m.last.z) : 0;
  m.last = { x: loc.x, y: loc.y, z: loc.z };

  // ---- 着地 --------------------------------------------------------------
  const ready = isReady(p);
  if (ground) {
    if (!m.ground) {
      if (ready && m.minVy < TUNE.heroVy && m.used) heroLanding(p, m.minVy);
      if (m.noFall) m.noFallUntil = t + 4;   // 着地した tick の落下ダメージまで消す
    }
    m.groundT++;
    m.airT = 0; m.jumps = 0; m.dashes = 0; m.minVy = 0;
    if (m.groundT > 2) { m.noFall = false; m.used = false; }
  } else {
    m.groundT = 0;
    m.airT++;
    m.minVy = Math.min(m.minVy, vel.y);
  }
  m.ground = ground;

  const sneak = sneaking(p);
  const sneakEdge = sneak && !m.sneak;
  m.sneak = sneak;
  const jump = jumpPressed(p);
  const jumpEdge = jump && !m.jump;
  m.jump = jump;
  m.jumpHeld = jump ? m.jumpHeld + 1 : 0;

  if (!ready) {
    if (m.hovering) stopHover(p, m, true);
    st.revertHold = 0;
    return;
  }
  const pl = PLANETS[st.form];
  const mob = pl.mobility;
  const c = pl.color;

  // ---- バリア ------------------------------------------------------------
  if (st.barrierUntil > t) tickBarrier(p, pl, st.barrierUntil - t);

  let inWater = false;
  try { inWater = !!p.isInWater; } catch (_) { }

  // ---- 変身解除の長押し（スニークしたまま静止） ------------------------------
  if (ground && sneak && moved < TUNE.stillEps && !isBusy(p)) {
    st.revertHold++;
    if (st.revertHold >= COMMON.revert_hold_ticks) {
      st.revertHold = 0;
      BUS.emit("revert", p, "manual");
      return;
    }
  } else {
    st.revertHold = 0;
  }

  // ---- 疾走 --------------------------------------------------------------
  let sprinting = false;
  try { sprinting = !!p.isSprinting; } catch (_) { }
  if (sprinting && ground) {
    if (mob.sprint >= 0) effect(p, "speed", 10, mob.sprint);
    if (t % 3 === 0) {
      const f = flatDir(p);
      const back = { x: loc.x - f.x * 0.5, y: loc.y + 0.15, z: loc.z - f.z * 0.5 };
      P(p.dimension, "flame", back, { color: c, count: 1, dir: { x: -f.x, y: 0.1, z: -f.z }, speed: 2, size: 0.5, life: 0.25 });
      P(p.dimension, "wind", back, { color: white(c, 0.3), count: 1, dir: { x: -f.x, y: 0.05, z: -f.z }, speed: 4, size: 0.7, spread: 0.3 });
    }
  }

  // ---- ホバー（空中でジャンプ長押し → 浮遊、離すと低速落下、スニークで降りる） ----
  if (m.hovering) {
    if (ground || inWater) stopHover(p, m, false);
    else if (sneakEdge) stopHover(p, m, true);
    else tickHover(p, m, pl, jump && energy(p) > 0);
  } else if (!ground && jump && m.jumpHeld >= TUNE.hoverDelay && m.airT >= 4 && energy(p) > 1 && !inWater) {
    startHover(p, m, pl);
  }

  // ---- 二段ジャンプ ------------------------------------------------------
  if (!ground && jumpEdge && m.airT >= 4 && m.jumps < mob.air_jumps && !inWater) {
    m.jumps++;
    const f = flatDir(p);
    const hv = Math.hypot(vel.x, vel.z);
    const dir = hv > 0.05 ? { x: vel.x / hv, z: vel.z / hv } : { x: f.x, z: f.z };
    knock(p, dir.x, dir.z, Math.min(1.0, hv + TUNE.jumpCarry * 0.5), TUNE.jumpUp);
    m.noFall = true; m.used = true; m.minVy = 0;
    thrustFx(p, pl, { x: 0, y: -1, z: 0 }, 1.0);
    P(p.dimension, "ring_flat", { x: loc.x, y: loc.y + 0.05, z: loc.z }, { color: c, size: 1.3, life: 0.35 });
    P(p.dimension, "circle", { x: loc.x, y: loc.y + 0.02, z: loc.z }, { color: c, size: 0.9, life: 0.45, spin: 240 });
    sound(p.dimension, "astro.jump", loc, 1.0 + m.jumps * 0.12, 0.8);
    body(p, "airjump", "astro.move");
    return;
  }

  // ---- ブースト・ダッシュ（空中でスニーク） -----------------------------
  if (!ground && sneakEdge && m.airT >= 3 && m.dashes < mob.air_dash) {
    m.dashes++;
    const f = flatDir(p);
    knock(p, f.x, f.z, TUNE.boost, TUNE.boostUp);
    m.noFall = true; m.used = true; m.minVy = 0;
    dashFx(p, pl, f);
    thrustFx(p, pl, { x: -f.x, y: -0.2, z: -f.z }, 1.3);
    sound(p.dimension, "astro.boost", loc, 1.0 + m.dashes * 0.06, 0.9);
    body(p, "boost", "astro.move");
    return;
  }

  // ---- 回避ステップ（地上でスニーク 2 回） --------------------------------
  if (ground && sneakEdge) {
    if (t - m.lastSneak <= TUNE.stepWindow && t >= m.stepCd) {
      m.stepCd = t + TUNE.stepCooldown;
      m.lastSneak = -99;
      const hv = Math.hypot(vel.x, vel.z);
      const f = flatDir(p);
      const dir = hv > 0.04 ? { x: vel.x / hv, y: 0, z: vel.z / hv } : { x: -f.x, y: 0, z: -f.z };
      knock(p, dir.x, dir.z, TUNE.step, TUNE.stepUp);
      effect(p, "resistance", TUNE.iframes, 4);
      m.dodgeUntil = t + TUNE.iframes + 2;
      m.noFall = true;
      dashFx(p, pl, dir);
      sound(p.dimension, "astro.step", loc, 1.2, 0.9);
      body(p, "step", "astro.move");
    } else {
      m.lastSneak = t;
    }
  }
}

// ---------------------------------------------------------------------------
//  ホバー
// ---------------------------------------------------------------------------
function startHover(p, m, pl) {
  m.hovering = true;
  m.hoverT = 0;
  m.lifting = false;
  m.noFall = true; m.used = true;
  sound(p.dimension, "astro.hover", p.location, 1.0, 0.8);
  sound(p.dimension, "astro.thrust", p.location, 1.1, 0.6);
  body(p, "hover", "astro.pose");
}

/** ホバーの上昇力（0..1）→ 浮遊の Lv（amp 0..2 = Lv1..3）。 */
export function hoverAmp(h) { return h >= 0.85 ? 2 : h >= 0.55 ? 1 : 0; }

function tickHover(p, m, pl, lifting) {
  m.hoverT++;
  m.minVy = 0;
  m.noFall = true;
  const h = pl.mobility.hover ?? 0.5;
  if (lifting) {
    // 効果はクライアント側で動くので、ラグがあってもなめらか
    if (!m.lifting || m.hoverT % 3 === 0) {
      removeEffect(p, "slow_falling");
      effect(p, "levitation", 6, hoverAmp(h));
    }
    addEnergy(p, -COMMON.hover_cost / 20);
    if (m.hoverT % 2 === 0) thrustFx(p, pl, { x: 0, y: -1, z: 0 }, 0.6 + h * 0.4);
    if (m.hoverT % 8 === 0) sound(p.dimension, "astro.hover", p.location, 0.9 + Math.random() * 0.2, 0.45);
  } else {
    if (m.lifting || m.hoverT % 4 === 0) {
      removeEffect(p, "levitation");
      effect(p, "slow_falling", 8, 0);
    }
    if (m.hoverT % 4 === 0) thrustFx(p, pl, { x: 0, y: -1, z: 0 }, 0.35);
  }
  m.lifting = lifting;
}

/** ホバーをやめる。drop = スニークで降りる（効果を両方外す）。 */
function stopHover(p, m, drop = false) {
  m.hovering = false;
  m.lifting = false;
  removeEffect(p, "levitation");
  if (drop) removeEffect(p, "slow_falling");
  m.noFall = true;
  bodyStop(p, "astro.pose");
}

export function isHovering(p) { return !!mv.get(p.id)?.hovering; }

// ---------------------------------------------------------------------------
//  演出
// ---------------------------------------------------------------------------
/** 背中のスラスターの噴射（dir = 噴き出す向き）。 */
export function thrustFx(p, pl, dir, k = 1) {
  const f = flatDir(p);
  const l = p.location;
  const back = { x: l.x - f.x * 0.32, y: l.y + 1.15, z: l.z - f.z * 0.32 };
  const r = rightOf(f);
  for (const s of [-1, 1]) {
    const q = { x: back.x + r.x * 0.18 * s, y: back.y, z: back.z + r.z * 0.18 * s };
    P(p.dimension, "flame", q, { color: pl.color, dir, speed: 4 * k, count: Math.round(2 * k), size: 0.6 * k, life: 0.22 });
  }
  P(p.dimension, "glow", back, { color: white(pl.color, 0.5), size: 0.8 * k, life: 0.12 });
  if (k >= 1) P(p.dimension, "ember", back, { color: pl.accent ?? pl.color, dir, speed: 3, count: 3, size: 0.4 });
}

function dashFx(p, pl, dir) {
  const l = p.location;
  const c = pl.color;
  afterimage(p.dimension, l, c, 0.45);
  P(p.dimension, "speedline", { x: l.x, y: l.y + 1.0, z: l.z },
    { color: white(c, 0.3), count: 8, dir: { x: -dir.x, y: 0, z: -dir.z }, speed: 16, spread: 0.7 });
  P(p.dimension, "ring", { x: l.x, y: l.y + 1.0, z: l.z }, { color: c, size: 1.2, life: 0.22 });
  for (let i = 1; i <= 3; i++) {
    const d = i * 0.9;
    P(p.dimension, "trail", { x: l.x + dir.x * d, y: l.y + 1.0, z: l.z + dir.z * d },
      { color: c, size: 1.6 - i * 0.3, life: 0.2 });
  }
}

function heroLanding(p, vy) {
  const pl = PLANETS[S(p).form];
  if (!pl) return;
  const l = p.location;
  const k = Math.min(2.4, -vy);
  body(p, "land", "astro.move");
  P(p.dimension, "shock_flat", { x: l.x, y: l.y + 0.06, z: l.z }, { color: pl.color, size: 1.4 + k, life: 0.45 });
  P(p.dimension, "ring_flat", { x: l.x, y: l.y + 0.08, z: l.z }, { color: white(pl.color, 0.4), size: 1.8 + k, life: 0.4 });
  P(p.dimension, "dust", { x: l.x, y: l.y + 0.1, z: l.z }, { count: Math.round(10 + k * 6), spread: 0.4, speed: 4 + k * 2, size: 1.2 });
  ring(p.dimension, "spark", l, 0.8, 6, { color: pl.color, count: 2, speed: 3 });
  sound(p.dimension, "astro.land", l, 1.1, 0.5 + k * 0.2);
}

// ---------------------------------------------------------------------------
//  ジャスト回避・落下ダメージ
// ---------------------------------------------------------------------------
/** 回避の無敵中に攻撃されたか（entityHitEntity / entityHurt から）。発動したら true。 */
export function tryJustDodge(p, attacker) {
  const m = mv.get(p.id);
  if (!m || !isReady(p) || now() > m.dodgeUntil || now() < m.justCd) return false;
  const pl = PLANETS[S(p).form];
  m.justCd = now() + 30;
  m.dodgeUntil = -1;
  const l = p.location;
  const c = chest(p);
  sound(p.dimension, "astro.just_dodge", l, 1.0, 1.0);
  sound(p.dimension, "astro.time_stop", l, 1.4, 0.6);
  P(p.dimension, "ring", c, { color: white(pl.color, 0.4), size: 2.6, life: 0.4 });
  P(p.dimension, "hex_circle", { x: l.x, y: l.y + 0.05, z: l.z }, { color: pl.color, size: 2.2, life: 0.9, spin: 180 });
  for (let i = 0; i < 6; i++) {
    const a = i * Math.PI / 3;
    afterimage(p.dimension, { x: l.x + Math.cos(a) * 0.9, y: l.y, z: l.z + Math.sin(a) * 0.9 }, pl.color, 0.5);
  }
  P(p.dimension, "speedline", c, { color: pl.color, count: 14, speed: 14, spread: 1.2 });
  title(p, " ", `§r${glyph("icon.sync", "")}§r ${pl.tc}JUST DODGE §r${glyph("icon.sync", "")}`, { fadeIn: 0, stay: 14, fadeOut: 6 });
  // 周りの敵の時間が遅れる、自分は加速
  for (const e of entitiesNear(p.dimension, l, 7)) {
    if (!valid(e) || e.id === p.id) continue;
    try { if (e.typeId === "astro:dmg_text" || e.typeId === "minecraft:item") continue; } catch (_) { continue; }
    effect(e, "slowness", 50, 4);
  }
  if (attacker && valid(attacker)) effect(attacker, "weakness", 60, 1);
  effect(p, "speed", 60, 2);
  addNova(p, COMMON.nova_on_just_dodge);
  addRecord(p, "justDodges", 1);
  return true;
}

export function isDodging(p) { return (mv.get(p.id)?.dodgeUntil ?? -1) >= now(); }

/** 落下ダメージを打ち消す（entityHurt から）。消したら true。 */
export function cancelFall(p, damage) {
  const m = mv.get(p.id);
  if (!m) return false;
  if (!(m.noFall || m.noFallUntil >= now() || m.hovering)) return false;
  const h = health(p);
  if (!h) return false;
  try {
    if (h.currentValue > 0) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + damage));
    return true;
  } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
//  ナノ・バリア（スニーク＋右クリック、超新星ゲージ未満）
// ---------------------------------------------------------------------------
/** バリアを張る（engine から）。張れたら true。 */
export function barrier(p) {
  const st = S(p);
  const t = now();
  const pl = PLANETS[st.form];
  if (!pl) return false;
  if (st.barrierCd > t) {
    announce(p, `§r${glyph("icon.barrier", "")}§r §7ナノ・バリア §cあと ${((st.barrierCd - t) / 20).toFixed(1)} 秒`, 16);
    sound(p.dimension, "astro.alert", p.location, 0.7, 0.35);
    return false;
  }
  st.barrierUntil = t + COMMON.barrier_ticks;
  st.barrierCd = t + COMMON.barrier_cd;
  st.revertHold = 0;
  effect(p, "resistance", COMMON.barrier_ticks + 1, 4);
  sound(p.dimension, "astro.barrier", p.location, 1.0, 1.0);
  body(p, "barrier", "astro.act");
  const c = chest(p);
  P(p.dimension, "hex_circle", { ...p.location, y: p.location.y + 0.05 }, { color: pl.color, size: 2.0, life: 0.7, spin: 90 });
  P(p.dimension, "ring", c, { color: white(pl.color, 0.4), size: 2.2, life: 0.3 });
  shell(p, pl, 1.0);
  return true;
}

export function barrierActive(p) { return S(p).barrierUntil > now(); }

/** 六角のセルを球面に並べる。 */
function shell(p, pl, k) {
  const c = chest(p);
  const n = Math.round(10 * k);
  const ph = (now() * 0.37) % (Math.PI * 2);
  for (let i = 0; i < n; i++) {
    const yv = 1 - (i + 0.5) / n * 2;
    const r = Math.sqrt(1 - yv * yv);
    const a = i * 2.39996 + ph;
    const q = { x: c.x + Math.cos(a) * r * 1.35, y: c.y + yv * 1.25, z: c.z + Math.sin(a) * r * 1.35 };
    P(p.dimension, "hex", q, { color: i % 3 ? pl.color : white(pl.color, 0.5), size: 0.55, life: 0.18 });
  }
}

function tickBarrier(p, pl, left) {
  if (left % 2 === 0) shell(p, pl, 1);
  reflectProjectiles(p, chest(p), 2.8, pl.color);
}

/** バリア中に殴られた（entityHurt / entityHitEntity から）。 */
export function onBarrierHit(p, attacker) {
  if (!barrierActive(p)) return false;
  const pl = PLANETS[S(p).form];
  const c = chest(p);
  sound(p.dimension, "astro.barrier_hit", c, 0.9 + Math.random() * 0.3, 1.0);
  P(p.dimension, "hex", c, { color: white(pl.color, 0.5), size: 2.2, life: 0.25 });
  P(p.dimension, "spark", c, { color: pl.color, count: 10, speed: 6 });
  if (attacker && valid(attacker) && attacker.id !== p.id) {
    const d = norm(sub(attacker.location, p.location));
    knock(attacker, d.x, d.z, 0.9, 0.25);
  }
  return true;
}

const reflected = new Map();   // projectileId -> tick

/**
 * 近くの飛び道具（minecraft:projectile を持つエンティティ）を弾き返す。
 * バリアと、突進技などの「盾をまとう」技から使える。弾いた数を返す。
 */
export function reflectProjectiles(p, center, radius = 2.8, color = [1, 1, 1]) {
  let n = 0;
  const t = now();
  if (reflected.size > 200) reflected.clear();
  for (const e of entitiesNear(p.dimension, center, radius)) {
    try {
      if (!valid(e) || e.typeId === "minecraft:player") continue;
      const proj = e.getComponent("minecraft:projectile");
      if (!proj) continue;
      if ((reflected.get(e.id) ?? -99) > t - 10) continue;
      if (proj.owner && proj.owner.id === p.id) continue;
      reflected.set(e.id, t);
      const away = norm(sub(e.location, center));
      const v = scale({ x: away.x, y: Math.max(0.1, away.y), z: away.z }, 1.3);
      try { proj.owner = p; } catch (_) { }
      let ok = false;
      try { if (typeof proj.shoot === "function") { proj.shoot(v); ok = true; } } catch (_) { }
      if (!ok) {
        try { e.clearVelocity?.(); } catch (_) { }
        try { e.applyImpulse(v); } catch (_) { }
      }
      P(p.dimension, "hex", e.location, { color: white(color, 0.4), size: 1.0, life: 0.2 });
      sound(p.dimension, "astro.barrier_hit", e.location, 1.3, 0.6);
      n++;
    } catch (_) { }
  }
  return n;
}

/** 状態を捨てる（退出・リスポーン）。 */
export function forgetMobility(id) { mv.delete(id); }

/** 変身・解除の時に機動の状態を戻す（ホバーを止める）。 */
export function resetMobility(p) {
  const m = mv.get(p.id);
  if (m?.hovering) stopHover(p, m, true);
  if (m) { m.dodgeUntil = -1; m.jumps = 0; m.dashes = 0; }
}

export { setNovaRaw, viewDir };
