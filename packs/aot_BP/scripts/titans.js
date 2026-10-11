// ===========================================================================
//  巨人 — うなじ・再生・掴み・払い・夜の休眠・奇行種・討伐（蒸発）
//
//  巨人の体の寸法は体型（minecraft:variant）ごとに全高に対する比で持っている
//  （aot_meta.js、tools/aot/aot_models.py の titan_metrics から生成）。
//  うなじは「首の後ろ」。膝をついていれば下がり、寝ていればもっと下がる。
// ===========================================================================
import { system, world } from "@minecraft/server";
import { BODY_META, PROP, TITAN_TYPES, TUNE, rankOf } from "./config.js";
import { P, blood, pose, shakeAround, slash, sound, steam } from "./fx.js";
import {
  add, boolProp, clamp, damage, dims, dist, dot, event, eye, health, now, numProp,
  pick, rand, rt, rayVsColumn, setProp, setVelocity, sub, title, valid, velocity, viewDir, yawFrame,
} from "./util.js";

// 巨人ごとの状態（スクリプト側）。world を読み直すと消えるので、最初に見た時に整える
const T = new Map();      // id -> { state, hurtAt, noRegenUntil, until, stepAt, swatCd, leapCd, wakeUntil, ... }
// 掴まれている者: victimId -> { titan, victim, t0, hits }
const GRAB = new Map();

export const isTitan = (e) => !!(e && TITAN_TYPES[e.typeId]);
export const typeOf = (e) => TITAN_TYPES[e.typeId];

function st(e) {
  let s = T.get(e.id);
  if (!s) {
    let prop;
    try { prop = e.getProperty?.("aot:state"); } catch (_) { }
    s = { state: prop ?? "unknown", hurtAt: -999, noRegenUntil: 0, until: 0, stepAt: 0,
          swatCd: 0, leapCd: now() + 80, wakeUntil: 0, groanAt: now() + 100 };
    T.set(e.id, s);
  }
  return s;
}

export function stateOf(e) { return st(e).state; }

function setState(e, s, ev) {
  const r = st(e);
  if (r.state === "dying") return;
  r.state = s;
  event(e, ev ?? `aot:st_${s}`);
}

export function isDying(e) { return st(e).state === "dying"; }

// ---------------------------------------------------------------------------
//  体の寸法
// ---------------------------------------------------------------------------
function bodyMeta(e) {
  let v = 0;
  try { v = e.getComponent("minecraft:variant")?.value ?? 0; } catch (_) { }
  return BODY_META[v] ?? BODY_META[0];
}

/** 巨人の前・右・高さと、各部位の位置。 */
export function frame(e) {
  const info = typeOf(e);
  const H = info.height;
  const m = bodyMeta(e);
  const { f, r } = yawFrame(e);
  const s = st(e).state;
  // 膝をつくと胸から上が前に出て下がる。寝ていると座り込んで首が前に垂れる
  let yk = 1.0;
  let fz = 0;
  if (s === "kneel") { yk = 0.66; fz = 0.12; } else if (s === "sleep") { yk = 0.52; fz = 0.16; }
  const L = e.location;
  const nape = add(add(L, { x: 0, y: m.napeY * H * yk, z: 0 }), f, (-m.napeZ + fz) * H);
  const eyes = add(add(L, { x: 0, y: m.eyeY * H * yk, z: 0 }), f, (-m.headZ + fz) * H * 0.9);
  const radius = Math.max(0.7, H * 0.085);
  return { H, f, r, nape, eyes, radius, info, m, base: L };
}

/** 巨人の体を縦の柱として、半直線が当たるか（アンカー・雷槍・視線の判定）。 */
export function rayTitans(dim, o, dir, maxDist, skipId) {
  let best = null;
  let near = [];
  try { near = dim.getEntities({ location: o, maxDistance: maxDist + 16, families: ["titan"] }); }
  catch (_) { return null; }
  for (const t of near) {
    if (t.id === skipId || !isTitan(t)) continue;
    const info = typeOf(t);
    const rad = info.hitW * 0.5;
    const hit = rayVsColumn(o, dir, maxDist, t.location, info.height * 0.96);
    if (hit.d > rad) continue;
    const s = Math.max(0, hit.s - Math.sqrt(Math.max(0, rad * rad - hit.d * hit.d)));
    if (!best || s < best.s) best = { entity: t, s, at: add(o, dir, s) };
  }
  return best;
}

// ---------------------------------------------------------------------------
//  斬られた時
// ---------------------------------------------------------------------------
/**
 * 刃で巨人を斬った。kind: "hit"（通常攻撃）/ "pass"（巻き取りで脇を抜けた）/ "spin"（回転斬り）
 * fast: 勢いがあるか。返り値: "nape" | "shallow" | "ankle" | "eyes" | "body"
 */
export function bladeCut(attacker, titan, kind, fast) {
  if (!valid(titan) || isDying(titan)) return "none";
  const F = frame(titan);
  const dim = titan.dimension;
  const o = attacker.typeId === "minecraft:player" ? eye(attacker) : add(attacker.location, { x: 0, y: 1.0, z: 0 });
  const dir = attacker.typeId === "minecraft:player" ? viewDir(attacker) : { x: 0, y: 0, z: 0 };
  const behind = dot(F.f, { x: o.x - F.nape.x, y: 0, z: o.z - F.nape.z }) < F.radius * 0.6;
  const above = o.y > F.nape.y + 0.6;
  let onNape = false;
  if (kind === "spin" || kind === "pass") {
    onNape = dist(o, F.nape) <= F.radius + (kind === "spin" ? TUNE.spinRadius : TUNE.passRadius);
  } else {
    const ray = { s: 0, d: dist(o, F.nape) };
    const toN = sub(F.nape, o);
    const along = clamp(dot(toN, dir), 0, 6.5);
    ray.d = dist(add(o, dir, along), F.nape);
    onNape = ray.d <= F.radius + 0.7 || dist(o, F.nape) <= F.radius + 1.4;
  }
  if (onNape && (behind || above || kind === "spin")) {
    if (fast || kind !== "hit") {
      napeKill(titan, attacker);
      return "nape";
    }
    // 浅い: うなじに届いたが勢いが足りない
    const h = health(titan);
    const s = st(titan);
    s.noRegenUntil = now() + 100;
    s.hurtAt = now();
    damage(titan, (h?.effectiveMax ?? 100) * TUNE.shallow, attacker);
    blood(dim, F.nape, 1.2, F.f);
    steam(dim, F.nape, 1.0);
    sound(dim, "aot.cut", F.nape, 0.8, 1.0);
    return "shallow";
  }
  // 足首（腱）
  const low = o.y < F.base.y + F.H * 0.30;
  if (low && kind === "hit") {
    blood(dim, add(F.base, { x: 0, y: F.H * 0.08, z: 0 }), 0.9);
    if (Math.random() < TUNE.ankleChance && st(titan).state !== "sleep") {
      kneel(titan);
      return "ankle";
    }
    return "body";
  }
  // 目
  if (kind === "hit") {
    const toE = sub(F.eyes, o);
    const along = clamp(dot(toE, dir), 0, 6.5);
    if (dist(add(o, dir, along), F.eyes) < F.radius * 1.2 && dot(F.f, sub(o, F.eyes)) > 0) {
      blind(titan);
      blood(dim, F.eyes, 0.8);
      return "eyes";
    }
  }
  return "body";
}

export function kneel(t) {
  const s = st(t);
  if (s.state === "dying" || s.state === "sleep") return;
  setState(t, "kneel");
  s.until = now() + TUNE.kneelTicks;
  try { t.getComponent("minecraft:movement")?.setCurrentValue(0); } catch (_) { }
  sound(t.dimension, "aot.titan_fall", t.location, 1.3, 0.6);
  P(t.dimension, "dust", t.location, { count: 14, spread: typeOf(t).height * 0.1, speed: 4 });
}

export function blind(t) {
  const s = st(t);
  if (s.state === "dying" || s.state === "sleep") return;
  s.state = "blind";
  event(t, "aot:blind");
  s.until = now() + TUNE.blindTicks;
}

/** 体が傷ついた（スクリプト／バニラどちらのダメージでも）。蒸気と血。 */
export function onTitanHurt(t, amount, cause, attacker) {
  const s = st(t);
  s.hurtAt = now();
  if (s.state === "sleep") {         // 寝込みを襲われたら起きる
    s.wakeUntil = now() + 400;
    s.state = "idle";
    event(t, "aot:wake");
  }
  if (cause === "entityAttack" || cause === "projectile") {
    const F = frame(t);
    const at = attacker ? add(t.location, { x: 0, y: clamp(attacker.location.y - t.location.y + 1.2, 0.3, F.H * 0.9), z: 0 })
      : add(t.location, { x: 0, y: F.H * 0.5, z: 0 });
    blood(t.dimension, at, 0.6 + Math.min(1, amount / 6));
    steam(t.dimension, at, 0.5);
  }
}

// ---------------------------------------------------------------------------
//  討伐: うつ伏せに倒れ、4 秒蒸気を上げて消える
// ---------------------------------------------------------------------------
export function napeKill(t, killer) {
  const s = st(t);
  if (s.state === "dying") return;
  const F = frame(t);
  const dim = t.dimension;
  s.state = "dying";
  s.until = now() + TUNE.dyingTicks;
  s.killer = killer;
  event(t, "aot:die");
  try { t.getComponent("minecraft:movement")?.setCurrentValue(0); } catch (_) { }
  releaseGrabbedBy(t);
  // うなじから血しぶきと蒸気
  blood(dim, F.nape, 2.4, F.f);
  P(dim, "blood_mist", F.nape, { count: 6, size: 2.2, spread: 0.8 });
  steam(dim, F.nape, 2.2);
  slash(dim, F.nape, rand(0, 360), F.radius * 2.4, [1.0, 0.85, 0.8]);
  P(dim, "flash", F.nape, { size: F.radius * 2, color: [1.0, 0.9, 0.8] });
  sound(dim, "aot.nape", F.nape, rand(0.9, 1.05), 1.4);
  sound(dim, "aot.steam", F.nape, 1.0, 1.2);
  const info = typeOf(t);
  // 倒れて地面に着いた時の地響き
  s.fallAt = now() + 24;
  s.fallDone = false;
  if (killer && killer.typeId === "minecraft:player") credit(killer, t, info);
}

function credit(player, t, info) {
  const kills = numProp(player, PROP.kills, 0) + 1;
  const before = rankOf(kills - 1);
  setProp(player, PROP.kills, kills);
  sound(player.dimension, "aot.kill", player.location, 1.0, 0.8);
  title(player, rt("§c", { t: "aot.title.kill" }),
        rt("§f", { t: `entity.${t.typeId}.name` }, "  §7", { t: "aot.title.kill_count", w: [kills] }), 26);
  const after = rankOf(kills);
  if (after !== before) {
    try {
      player.sendMessage(rt("§6", { t: "aot.msg.rank_up" }, " §e", { t: after }));
    } catch (_) { }
    sound(player.dimension, "random.levelup", player.location, 0.8, 0.8);
  }
  // 経験値（巨人は素材を落とさない）
  const orbs = Math.max(1, Math.round(info.xp / 10));
  for (let i = 0; i < orbs; i++) {
    try { t.dimension.spawnEntity("minecraft:xp_orb", add(player.location, { x: rand(-1, 1), y: 0.5, z: rand(-1, 1) })); }
    catch (_) { }
  }
}

/** 討伐以外で体力が尽きた（爆発・大量の攻撃）。バニラの死亡に蒸気を足す。 */
export function onTitanDie(t, killer) {
  const s = T.get(t.id);
  if (s?.state === "dying") { T.delete(t.id); return; }
  const info = typeOf(t);
  const at = add(t.location, { x: 0, y: info.height * 0.3, z: 0 });
  steam(t.dimension, at, 2.5);
  P(t.dimension, "steam2", at, { count: 6, size: info.height * 0.3, spread: info.height * 0.2 });
  sound(t.dimension, "aot.steam", at, 0.9, 1.2);
  releaseGrabbedBy(t);
  if (killer?.typeId === "minecraft:player") credit(killer, t, info);
  T.delete(t.id);
}

// ---------------------------------------------------------------------------
//  掴みと食べる
// ---------------------------------------------------------------------------
export function tryGrab(t, victim) {
  const info = typeOf(t);
  if (!info.grab || GRAB.has(victim.id) || isDying(t)) return false;
  if (boolProp(world, PROP.grab, false)) return false;
  for (const g of GRAB.values()) if (g.titan.id === t.id) return false;
  const s = st(t);
  if (s.state !== "idle" && s.state !== "unknown") return false;
  if (Math.random() > TUNE.grabChance) return false;
  GRAB.set(victim.id, { titan: t, victim, t0: now(), hits: 0 });
  setState(t, "grab");
  if (victim.typeId === "minecraft:player") {
    pose(victim, "grabbed");
    title(victim, rt("§4", { t: "aot.title.grabbed" }), rt("§7", { t: "aot.title.grabbed_hint" }), 40);
  } else {
    event(victim, "aot:st_grabbed");
  }
  sound(t.dimension, "aot.titan_groan", t.location, 0.8, 1.2);
  return true;
}

export function isGrabbed(e) { return GRAB.has(e.id); }

export function release(victimId, why) {
  const g = GRAB.get(victimId);
  if (!g) return;
  GRAB.delete(victimId);
  if (valid(g.titan) && !isDying(g.titan)) setState(g.titan, "idle");
  if (valid(g.victim)) {
    if (g.victim.typeId === "minecraft:player") pose(g.victim, null);
    else event(g.victim, "aot:st_idle");
    if (why === "escape" && valid(g.titan)) {
      const { f } = yawFrame(g.titan);
      setVelocity(g.victim, { x: f.x * 0.8, y: 0.6, z: f.z * 0.8 });
    }
  }
}

function releaseGrabbedBy(t) {
  for (const [vid, g] of [...GRAB]) if (g.titan.id === t.id) release(vid, "drop");
}

/** 掴まれた者がもがく（刃で斬る）。3 回で手を斬って抜け出す。 */
export function struggle(victim, strong) {
  const g = GRAB.get(victim.id);
  if (!g) return false;
  g.hits += strong ? 3 : 1;
  const dim = victim.dimension;
  blood(dim, victim.location, 0.8);
  sound(dim, "aot.cut", victim.location, 1.1, 1.0);
  if (g.hits >= 3) {
    damage(g.titan, typeOf(g.titan).hp * 0.08, victim);
    steam(dim, victim.location, 1.0);
    release(victim.id, "escape");
    if (victim.typeId === "minecraft:player") {
      title(victim, rt("§a", { t: "aot.title.escaped" }), rt(""), 20);
    }
    return true;
  }
  return false;
}

function handPos(t, s) {
  const F = frame(t);
  const t0 = GRAB.get(s)?.t0 ?? now();
  const age = now() - t0;
  if (age < 30) {                          // 胸の前に掴んで持つ
    return add(add(add(F.base, { x: 0, y: F.H * 0.55, z: 0 }), F.f, F.H * 0.30), F.r, -F.H * 0.08);
  }
  // 口へ運ぶ
  const k = clamp((age - 30) / 14, 0, 1);
  const chestP = add(add(F.base, { x: 0, y: F.H * 0.55, z: 0 }), F.f, F.H * 0.30);
  const mouth = add(add(F.base, { x: 0, y: F.m.eyeY * F.H - F.H * 0.09, z: 0 }), F.f, F.H * 0.13);
  return { x: chestP.x + (mouth.x - chestP.x) * k, y: chestP.y + (mouth.y - chestP.y) * k,
           z: chestP.z + (mouth.z - chestP.z) * k };
}

function tickGrabs() {
  for (const [vid, g] of [...GRAB]) {
    const { titan, victim } = g;
    if (!valid(titan) || !valid(victim) || isDying(titan)) { release(vid, "drop"); continue; }
    const age = now() - g.t0;
    const at = handPos(titan, vid);
    try {
      victim.teleport({ x: at.x, y: at.y - 0.9, z: at.z }, { dimension: titan.dimension, keepVelocity: false });
    } catch (_) { }
    if (age === 30) setState(titan, "eat");
    if (age === 50) {
      const info = typeOf(titan);
      damage(victim, info.dmg * 1.8, titan, "entityAttack");
      blood(titan.dimension, at, 1.6);
      sound(titan.dimension, "aot.titan_bite", at, rand(0.8, 1.0), 1.4);
      shakeAround(titan.dimension, at, 8, 0.3, 0.3);
      release(vid, "drop");
    }
  }
}

// ---------------------------------------------------------------------------
//  毎 tick / 10 tick
// ---------------------------------------------------------------------------
function isNight() {
  try {
    const t = world.getTimeOfDay();
    return t > 13000 && t < 23000;
  } catch (_) { return false; }
}

const nearPlayers = (dim, at, r) => {
  try { return dim.getPlayers({ location: at, maxDistance: r }); } catch (_) { return []; }
};

function targetsNear(t, r) {
  let out = [];
  try {
    out = t.dimension.getEntities({ location: t.location, maxDistance: r })
      .filter((e) => e.typeId === "minecraft:player" || e.typeId.startsWith("aot:") && !isTitan(e)
        || e.typeId === "minecraft:villager_v2");
  } catch (_) { }
  return out.filter((e) => {
    if (e.typeId !== "minecraft:player") return true;
    try { return String(e.getGameMode?.() ?? "survival").toLowerCase() !== "creative"; } catch (_) { return true; }
  });
}

/** 毎 tick: 掴み・討伐の演出（蒸気と地響き）。 */
export function tickTitansFast() {
  tickGrabs();
  const t0 = now();
  for (const [id, s] of [...T]) {
    if (s.state !== "dying") continue;
    const e = s.entity;
    if (!valid(e)) { T.delete(id); continue; }
    const F = frame(e);
    // 倒れた体（前へ伸びる）から蒸気
    if ((t0 + id.length) % 4 === 0) {
      const k = Math.random();
      const at = add(add(F.base, { x: 0, y: F.H * 0.12, z: 0 }), F.f, F.H * (0.1 + 0.8 * k));
      steam(e.dimension, at, 1.0 + F.H * 0.08);
    }
    if (!s.fallDone && t0 >= s.fallAt) {
      s.fallDone = true;
      const at = add(F.base, F.f, F.H * 0.45);
      sound(e.dimension, "aot.titan_fall", at, rand(0.8, 1.0), Math.min(2.5, 0.6 + F.H / 6));
      P(e.dimension, "dust", at, { count: 24, spread: F.H * 0.25, speed: 4 + F.H * 0.4, size: 1 + F.H * 0.1 });
      P(e.dimension, "ring_flat", add(at, { x: 0, y: 0.1, z: 0 }), { size: F.H * 0.7 });
      shakeAround(e.dimension, at, F.H * 3, Math.min(0.5, F.H * 0.03), 0.5);
    }
    if (t0 >= s.until) {
      // 消える瞬間: 大きな蒸気。消えなければ自分で消す（instant_despawn の保険）
      const at = add(F.base, F.f, F.H * 0.4);
      for (let i = 0; i < 3; i++) steam(e.dimension, add(at, { x: rand(-1, 1) * F.H * 0.2, y: F.H * 0.1, z: rand(-1, 1) * F.H * 0.2 }), 2.0 + F.H * 0.1);
      if (t0 >= s.until + 30) {
        try { e.remove(); } catch (_) { }
        T.delete(id);
      }
    }
  }
}

/** 10 tick ごと: 再生・足音・払い・奇行種・昼夜・状態の期限。 */
export function tickTitans() {
  const night = isNight();
  const t0 = now();
  const seen = new Set();
  for (const dim of dims()) {
    let titans = [];
    try { titans = dim.getEntities({ families: ["titan"] }); } catch (_) { continue; }
    for (const t of titans) {
      if (!isTitan(t)) continue;
      seen.add(t.id);
      const s = st(t);
      s.entity = t;
      if (s.state === "dying") continue;
      const info = typeOf(t);
      // 最初に見た時（読み込み直後など）に状態を揃える
      if (s.state === "unknown") {
        s.state = night ? "sleep" : "idle";
        event(t, night ? "aot:sleep" : "aot:wake");
        // 膝をついたまま保存されていると足の速さが 0 のまま残るので戻す
        try { t.getComponent("minecraft:movement")?.resetToDefaultValue(); } catch (_) { }
      }
      // ---- 期限つきの状態 ----
      if ((s.state === "kneel" || s.state === "blind") && t0 >= s.until) {
        if (s.state === "kneel") {
          try { t.getComponent("minecraft:movement")?.resetToDefaultValue(); } catch (_) { }
          setState(t, "idle");
        } else {
          s.state = "idle";
          event(t, "aot:unblind");
        }
      }
      if ((s.state === "swat" || s.state === "leap") && t0 >= s.until) setState(t, "idle");
      // ---- 昼と夜 ----
      if (night && s.state === "idle" && t0 > s.wakeUntil && t0 - s.hurtAt > 200 && !grabbing(t)) {
        s.state = "sleep";
        event(t, "aot:sleep");
      } else if (!night && s.state === "sleep") {
        s.state = "idle";
        event(t, "aot:wake");
      }
      // ---- 再生 ----
      const h = health(t);
      if (h && h.currentValue < h.effectiveMax && t0 - s.hurtAt > TUNE.regenDelay && t0 > s.noRegenUntil) {
        try { h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + h.effectiveMax * TUNE.regenRate)); } catch (_) { }
        const F = frame(t);
        const k = 1 - h.currentValue / h.effectiveMax;
        steam(dim, add(F.base, { x: rand(-0.3, 0.3) * F.H * 0.2, y: F.H * rand(0.2, 0.8), z: rand(-0.3, 0.3) * F.H * 0.2 }),
              0.4 + k * 1.2);
        if (Math.random() < 0.15) sound(dim, "aot.steam", t.location, 1.2, 0.5);
      }
      if (s.state === "sleep") continue;
      tickMotion(t, s, info, dim, t0);
    }
  }
  for (const id of [...T.keys()]) if (!seen.has(id) && T.get(id)?.state !== "dying") T.delete(id);
}

function grabbing(t) {
  for (const g of GRAB.values()) if (g.titan.id === t.id) return true;
  return false;
}

function tickMotion(t, s, info, dim, t0) {
  const v = velocity(t);
  const moving = Math.hypot(v.x, v.z) > 0.03;
  const F = frame(t);
  // ---- 足音と画面揺れ（7m 級以上） ----
  if (info.height >= 7 && moving && t0 >= s.stepAt) {
    s.stepAt = t0 + Math.round(10 + info.height * 1.2);
    const side = (Math.floor(t0 / 10) % 2) ? 1 : -1;
    const foot = add(F.base, F.r, side * F.H * 0.06);
    sound(dim, "aot.titan_step", foot, rand(0.75, 0.95) - info.height * 0.01, Math.min(2.2, info.height / 6));
    P(dim, "dust", add(foot, { x: 0, y: 0.1, z: 0 }), { count: 6, spread: F.H * 0.05, speed: 2 + F.H * 0.15 });
    shakeAround(dim, foot, info.height * 2.6, Math.min(0.35, info.height * 0.018), 0.25);
  }
  // ---- うめき声 ----
  if (t0 >= s.groanAt) {
    s.groanAt = t0 + Math.round(rand(160, 420));
    if (nearPlayers(dim, t.location, 32).length) {
      sound(dim, "aot.titan_groan", add(F.base, { x: 0, y: F.H * 0.85, z: 0 }), rand(0.7, 1.0) - info.height * 0.015, 1.0);
    }
  }
  if (s.state !== "idle") return;
  // ---- 払い: 上半身の前に浮いた者を叩き落とす ----
  if (info.height >= 7 && t0 >= s.swatCd) {
    for (const e of targetsNear(t, F.H * 0.75)) {
      const rel = { x: e.location.x - F.base.x, y: e.location.y - F.base.y, z: e.location.z - F.base.z };
      const hd = Math.hypot(rel.x, rel.z);
      const front = (rel.x * F.f.x + rel.z * F.f.z) / (hd || 1);
      if (rel.y < F.H * 0.42 || rel.y > F.H * 1.05 || hd > F.H * 0.55 || front < 0.25) continue;
      s.swatCd = t0 + 60;
      setState(t, "swat");
      s.until = t0 + 18;
      const target = e;
      // 振りが届く頃（0.4 秒後）に当てる
      system.runTimeout(() => {
        if (!valid(target) || !valid(t) || isDying(t)) return;
        const F2 = frame(t);
        const d = sub(target.location, F2.base);
        const l = Math.hypot(d.x, d.z) || 1;
        if (dist(target.location, add(F2.base, { x: 0, y: F2.H * 0.7, z: 0 })) > F2.H * 0.75) return;
        damage(target, info.dmg * 0.8, t, "entityAttack");
        setVelocity(target, { x: d.x / l * 1.6, y: -0.3, z: d.z / l * 1.6 });
        sound(dim, "aot.hook", target.location, 0.6, 1.4);
        P(dim, "flash", target.location, { size: 1.6, color: [1, 1, 1] });
      }, 8);
      break;
    }
  }
  // ---- 奇行種: 跳躍と全力疾走 ----
  if (info.abnormal && t0 >= s.leapCd) {
    s.leapCd = t0 + Math.round(rand(80, 160));
    const prey = targetsNear(t, 28).filter((e) => e.typeId === "minecraft:player" || e.typeId.startsWith("aot:"));
    if (prey.length) {
      const target = pick(prey);
      const d = sub(target.location, t.location);
      const l = Math.hypot(d.x, d.z) || 1;
      setState(t, "leap");
      s.until = t0 + 30;
      setVelocity(t, { x: d.x / l * 1.6, y: 0.9, z: d.z / l * 1.6 });
      sound(dim, "aot.titan_groan", t.location, 1.3, 1.6);
      s.landAt = t0 + 10;
    }
  }
  // 奇行種の着地の衝撃
  if (info.abnormal && s.landAt && t0 >= s.landAt && t.isOnGround) {
    s.landAt = 0;
    P(dim, "dust", t.location, { count: 18, spread: 1.5, speed: 6 });
    P(dim, "ring_flat", add(t.location, { x: 0, y: 0.1, z: 0 }), { size: 5 });
    sound(dim, "aot.titan_step", t.location, 0.7, 2.0);
    shakeAround(dim, t.location, 24, 0.35, 0.4);
    for (const e of targetsNear(t, 3.5)) damage(e, 6, t, "entityAttack");
  }
}

export function forgetTitan(id) { T.delete(id); }

/** 雷槍・爆発などでうなじ以外に大きな傷を与えた時（再生を止める）。 */
export function heavyWound(t, ticks = 120) {
  const s = st(t);
  s.hurtAt = now();
  s.noRegenUntil = now() + ticks;
}

export function titanState(id) { return T.get(id); }

/** プレイヤーの手を離す（死亡・退出）。 */
export function forgetVictim(id) { if (GRAB.has(id)) release(id, "drop"); }

export { GRAB };
