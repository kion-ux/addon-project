// ===========================================================================
//  宇宙からの侵略者 — ヴォイド・ドローン／ヴォイド・センチネル／虚星王ネメシス
//  （攻撃パターン・予告・召喚・撃破演出）と、ホログラム標的の DPS 表示。
//
//  エンティティ・モデル・アニメは tools/astro/gen_astro_entities.py が作る。ここはその約束どおりに
//  プロパティ astro:mode（アニメの状態）・astro:phase（ボスの形態）とイベント astro:engage /
//  astro:disengage（ドローンの徘徊の切り替え）を動かす。仕様と数値は tools/astro/ENEMIES.md。
//
//  配線（main.js → enemies.js のフックから呼ぶ。または installInvaders() で自分で購読する）:
//    tickInvaders(tick?)                    毎 tick（2 tick ごとでも可。経過 tick は自分で数える）
//    onInvaderHurt(entity, damage, source, opts?)  entityHurt。戻り値は enemies.js と同じ
//                                           「true = ダメージ数字を出さない」（常に false）
//    onInvaderDie(entity, source)           entityDie（ボスの撃破演出・ドローンの爆発・標的の復活）
//    onInvaderSpawn(entity)                 entitySpawn（無くても 10 tick ごとの走査で拾う）
//    summonNemesis(player, opts?)           ヴォイド・シグナル: 夜の地上でだけ降臨。opts.force で無条件
//    summonHologram(player)                 ホログラム標的を目の前に
//    isInvader(entity)                      侵略者（ドローン・センチネル・ネメシス）か
//
//  予告: 危険な攻撃は全て 0.5 秒以上前に地面の警告（astro:warning）・照準線・溜めの光で知らせる。
//  上限: 同時に動く危険物（光線・隕石・衝撃波・黒孔）は HAZARD_CAP、ボルトは BOLT_CAP、
//        ボスの子機は MINION_CAP まで。ブロックは一切壊さない（爆発もパーティクルと自前のダメージだけ）。
// ===========================================================================
import { world, system, MolangVariableMap } from "@minecraft/server";
import * as FX from "./fx.js";

// ---------------------------------------------------------------------------
//  ID と数値
// ---------------------------------------------------------------------------
export const INVADER = {
  drone: "astro:void_drone",
  sentinel: "astro:void_sentinel",
  boss: "astro:nemesis",
  target: "astro:hologram_target",
  bolt: "astro:void_bolt",
  text: "astro:dmg_text",
};
const SIGNAL = "astro:void_signal";
const KIND = { [INVADER.drone]: "drone", [INVADER.sentinel]: "sentinel", [INVADER.boss]: "boss" };
const MINION_TAG = "astro_minion";
const DIMENSIONS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];

export const CFG = {
  drone: {
    range: 22, keepMin: 6.5, keepMax: 9.5, height: 3.0, maxSpeed: 0.3, period: 60, jitter: 14,
    charge: 12, boltSpeed: 0.9, boltDamage: 4, minRange: 2.5,
  },
  sentinel: {
    range: 16, trigger: 5.0, period: 120, jitter: 24, windup: 16, waveRadius: 6.5, waveSpeed: 0.6,
    waveDamage: 6, jumpClear: 0.9,
  },
  boss: {
    range: 48, hover: 4.2, keep: 10, maxSpeed: [0, 0.22, 0.3], gap: [0, [46, 66], [26, 38]],
    beamDamage: [0, 7, 8], meteorDamage: [0, 8, 9], meteorCount: [0, 5, 8], meteorRadius: 2.6,
    holeDamage: [0, 7, 8], dashDamage: [0, 10, 11], summon: [0, 2, 3],
  },
  target: { window: 100 },
};
const HAZARD_CAP = 18;          // 同時に動く危険物（光線・隕石・衝撃波・黒孔）
const BOLT_CAP = 24;            // 飛んでいるボルト
const MINION_CAP = 6;           // ボス 1 体あたりの子機
const FX_PER_TICK = 70;         // 侵略者の演出だけの粒の予算（fx.js の全体予算の内側でさらに絞る）

const MAG = [1.0, 0.23, 0.81];
const VIO = [0.67, 0.3, 1.0];
const RED = [1.0, 0.22, 0.3];
const WHITE = [1, 1, 1];

// ---------------------------------------------------------------------------
//  小道具（util.js に頼らない。API の版差は try で吸収）
// ---------------------------------------------------------------------------
const now = () => system.currentTick;
const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const add = (a, b, k = 1) => ({ x: a.x + b.x * k, y: a.y + b.y * k, z: a.z + b.z * k });
const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
const up = (a, y) => ({ x: a.x, y: a.y + y, z: a.z });
const len = (a) => Math.hypot(a.x, a.y, a.z);
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
const hdist = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
const lerp3 = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t, z: a.z + (b.z - a.z) * t });
function norm(a) {
  const l = len(a) || 1;
  return { x: a.x / l, y: a.y / l, z: a.z / l };
}
function flat(a) {
  const l = Math.hypot(a.x, a.z);
  return l < 1e-4 ? { x: 0, y: 0, z: 1 } : { x: a.x / l, y: 0, z: a.z / l };
}
const rightOf = (f) => ({ x: -f.z, y: 0, z: f.x });
const finite = (v) => v && Number.isFinite(v.x) && Number.isFinite(v.y) && Number.isFinite(v.z);

const warned = new Set();
function report(where, err) {
  const key = `${where}:${err?.message ?? err}`;
  if (warned.has(key)) return;
  if (warned.size > 200) warned.clear();
  warned.add(key);
  console.warn(`[astro] invaders.${where}: ${err?.stack ?? err}`);
}

function valid(e) {
  if (!e) return false;
  try {
    const v = e.isValid;
    return typeof v === "function" ? v.call(e) : v !== false;
  } catch (_) { return false; }
}
function typeOf(e) {
  try { return e.typeId; } catch (_) { return undefined; }
}
function hp(e) {
  try {
    const h = e.getComponent("minecraft:health");
    return h ? { cur: h.currentValue, max: h.effectiveMax, h } : undefined;
  } catch (_) { return undefined; }
}
function alive(e) {
  if (!valid(e)) return false;
  const h = hp(e);
  return !h || h.cur > 0;
}
function velocity(e) {
  try { return e.getVelocity(); } catch (_) { return { x: 0, y: 0, z: 0 }; }
}
function setMode(e, m) {
  try { if (e.getProperty?.("astro:mode") !== m) e.setProperty("astro:mode", m); } catch (_) { }
}
function event(e, name) {
  try { e.triggerEvent(name); } catch (_) { }
}
function impulse(e, v) {
  if (!finite(v)) return;
  try { e.applyImpulse(v); } catch (_) { }
}
/** 目標の速度 target へ寄せる（P 制御。applyImpulse はプレイヤー以外に効く）。 */
function steer(e, target, k = 0.35) {
  const v = velocity(e);
  impulse(e, { x: (target.x - v.x) * k, y: (target.y - v.y) * k, z: (target.z - v.z) * k });
}
/** 向きを変える（yaw: 0 = +Z、時計回り。pitch: 上が負）。 */
function face(e, at) {
  try {
    const l = e.location;
    const d = sub(at, l);
    const yaw = Math.atan2(-d.x, d.z) * 180 / Math.PI;
    const pitch = -Math.atan2(d.y, Math.hypot(d.x, d.z)) * 180 / Math.PI;
    if (typeof e.setRotation === "function") e.setRotation({ x: clamp(pitch, -40, 40), y: yaw });
  } catch (_) { }
}
/** applyKnockback は 1.x (dx, dz, 水平, 垂直) と 2.x ({x,z}*強さ, 垂直) で引数が違う。 */
function knock(e, dx, dz, h, v) {
  if (![dx, dz, h, v].every(Number.isFinite)) return;
  try { e.applyKnockback(dx, dz, h, v); return; } catch (_) { /* 2.x */ }
  try { e.applyKnockback({ x: dx * h, z: dz * h }, v); } catch (_) { }
}
function gameMode(p) {
  try { return String(p.getGameMode?.() ?? "survival").toLowerCase(); } catch (_) { return "survival"; }
}
function players(dim) {
  let list = [];
  try { list = world.getAllPlayers(); } catch (_) { return []; }
  return list.filter((p) => {
    if (!alive(p)) return false;
    try { if (dim && p.dimension.id !== dim.id) return false; } catch (_) { return false; }
    const gm = gameMode(p);
    return gm !== "creative" && gm !== "spectator";
  });
}
function nearestPlayer(e, range) {
  let best, bd = range;
  let loc;
  try { loc = e.location; } catch (_) { return undefined; }
  for (const p of players(e.dimension)) {
    const d = dist(p.location, loc);
    if (d < bd) { bd = d; best = p; }
  }
  return best;
}
const chest = (p) => up(p.location, 1.0);

function solid(dim, pos) {
  try {
    const b = dim.getBlock({ x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) });
    if (!b) return false;
    if (b.isAir || b.isLiquid) return false;
    const id = b.typeId;
    return !/(grass|fern|flower|torch|vine|snow_layer|carpet|sapling|bush|tulip|poppy|dandelion|rail|button|lever|pressure_plate|sign|banner)/.test(id);
  } catch (_) { return false; }
}
/** pos から下に地面を探し、上面の y（見つからなければ pos.y - down）。 */
function groundY(dim, pos, down = 10, upMax = 3) {
  let y = Math.floor(pos.y);
  for (let k = 0; k < upMax && solid(dim, { x: pos.x, y, z: pos.z }); k++) y++;
  for (let k = 0; k <= down; k++) {
    if (solid(dim, { x: pos.x, y: y - 1, z: pos.z })) return y;
    y--;
  }
  return pos.y - down;
}
function airBox(dim, c, rx, h) {
  for (const dx of [-rx, 0, rx]) {
    for (const dz of [-rx, 0, rx]) {
      for (let dy = 0; dy < h; dy += 1.5) {
        if (solid(dim, { x: c.x + dx, y: c.y + dy, z: c.z + dz })) return false;
      }
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
//  演出（fx.js があればその予算と演出の量の設定に乗る。無ければ自前で出す）
// ---------------------------------------------------------------------------
let fxTick = -1;
let fxSpent = 0;
const VARS = ["size", "life", "rot", "count", "speed", "spread", "vx", "vy", "vz", "var", "height", "spin",
  "rate", "grav", "len"];

function P(dim, id, loc, o = {}) {
  if (!dim || !finite(loc)) return;
  const t = now();
  if (t !== fxTick) { fxTick = t; fxSpent = 0; }
  const cost = 1 + (typeof o.count === "number" ? o.count / 8 : 0);
  if (fxSpent + cost > FX_PER_TICK) return;
  fxSpent += cost;
  if (typeof FX.P === "function") { FX.P(dim, id, loc, o); return; }
  try {
    const m = new MolangVariableMap();
    if (o.color) {
      m.setFloat("variable.cr", o.color[0]);
      m.setFloat("variable.cg", o.color[1]);
      m.setFloat("variable.cb", o.color[2]);
    }
    const vals = o.dir ? { ...o, vx: o.dir.x, vy: o.dir.y, vz: o.dir.z } : o;
    for (const k of VARS) {
      if (typeof vals[k] === "number" && Number.isFinite(vals[k])) m.setFloat(`variable.${k}`, vals[k]);
    }
    dim.spawnParticle(`astro:${id}`, loc, m);
  } catch (_) { }
}
function snd(dim, id, loc, pitch = 1, volume = 1) {
  if (!dim || !finite(loc)) return;
  if (typeof FX.sound === "function") { FX.sound(dim, `astro.${id}`, loc, pitch, volume); return; }
  try { dim.playSound(`astro.${id}`, loc, { pitch, volume }); } catch (_) { }
}
function shake(dim, loc, radius, k, sec = 0.3) {
  if (typeof FX.shake === "function") { FX.shake(dim, loc, radius, k, sec); return; }
  for (const p of players(dim)) {
    const d = dist(p.location, loc);
    if (d > radius) continue;
    try { p.runCommand(`camerashake add @s ${(Math.min(4, k * (1 - d / radius * 0.6))).toFixed(2)} ${sec} positional`); } catch (_) { }
  }
}
function titleNear(dim, loc, radius, text, sub, stay = 50) {
  for (const p of players(dim)) {
    if (dist(p.location, loc) > radius) continue;
    try { p.onScreenDisplay.setTitle(text, { subtitle: sub, fadeInDuration: 4, stayDuration: stay, fadeOutDuration: 14 }); } catch (_) { }
  }
}
function tell(p, text) {
  if (typeof FX.announce === "function") { FX.announce(p, text, 50); return; }
  try { p.onScreenDisplay.setActionBar(text); } catch (_) { }
  try { p.sendMessage(text); } catch (_) { }
}
/** 地面に置く警告（半径 r m、秒 s）。warning の直径は 2.4 × size m。 */
function warn(dim, at, r, sec, color = RED) {
  P(dim, "warning", up(at, 0.08), { size: r / 1.2, life: sec, color, spin: 60 });
}
function blast(dim, at, size = 1, color = MAG) {
  P(dim, "impact", at, { size: 1.6 * size, life: 0.35, color: WHITE });
  P(dim, "flare", at, { size: 1.4 * size, life: 0.3, color });
  P(dim, "spark", at, { count: Math.round(8 * size), speed: 6 * size, size: 0.9, color, life: 0.6 });
  P(dim, "smoke", at, { count: Math.round(4 * size), size: 0.9 * size, spread: 0.4 * size, life: 1.2 });
}

// ---------------------------------------------------------------------------
//  ダメージ（プレイヤーへ）。外から差し替え可能な判定（無敵中は false を返す等）
// ---------------------------------------------------------------------------
let damageFilter = null;
/** fn(player, amount, source, kind) → false で無効、数値でその量に差し替え。 */
export function setInvaderDamageFilter(fn) { damageFilter = typeof fn === "function" ? fn : null; }

function hurt(p, amount, source, kind = "entityAttack") {
  if (!alive(p) || !(amount > 0)) return false;
  if (damageFilter) {
    try {
      const r = damageFilter(p, amount, source, kind);
      if (r === false) return false;
      if (typeof r === "number") amount = r;
    } catch (e) { report("filter", e); }
  }
  try {
    if (valid(source)) return p.applyDamage(amount, { cause: kind, damagingEntity: source });
    return p.applyDamage(amount, { cause: kind });
  } catch (_) {
    try { return p.applyDamage(amount); } catch (_) { return false; }
  }
}

// ---------------------------------------------------------------------------
//  予定（ここで回す。持ち主が消えたら取り消す）と危険物
// ---------------------------------------------------------------------------
const tasks = [];      // { due, fn, owner }
const hazards = [];    // { step(t) → 続けるなら true, owner }
const bolts = [];      // { e, real, pos, dir, speed, born, owner, dmg, dim, last }

function later(ticks, owner, fn) { tasks.push({ due: now() + Math.max(1, Math.round(ticks)), fn, owner }); }
function canHazard(n = 1) { return hazards.length + n <= HAZARD_CAP; }
function addHazard(h) {
  if (!canHazard()) return false;
  hazards.push(h);
  return true;
}

// ---------------------------------------------------------------------------
//  登録（10 tick ごとに走査。entitySpawn でも即時に入る）
// ---------------------------------------------------------------------------
const reg = new Map();     // id → { e, kind, st }
let lastTick = -1;
let scanAt = 0;

export function isInvader(e) { return !!KIND[typeOf(e)]; }

function register(e) {
  const kind = KIND[typeOf(e)];
  if (!kind || !valid(e)) return undefined;
  let r = reg.get(e.id);
  if (r) { r.e = e; return r; }
  r = { e, kind, st: { born: now(), mode: 0, next: now() + Math.round(rand(20, 50)), last: e.location, dim: e.dimension } };
  reg.set(e.id, r);
  if (kind === "boss") bossInit(r);
  if (kind === "drone") r.st.keep = rand(CFG.drone.keepMin, CFG.drone.keepMax);
  return r;
}

function scan() {
  for (const id of DIMENSIONS) {
    let dim;
    try { dim = world.getDimension(id); } catch (_) { continue; }
    let list = [];
    try { list = dim.getEntities({ families: ["astro_invader"] }); } catch (_) {
      for (const t of [INVADER.drone, INVADER.sentinel, INVADER.boss]) {
        try { list.push(...dim.getEntities({ type: t })); } catch (_) { }
      }
    }
    for (const e of list) register(e);
  }
}

export function onInvaderSpawn(e) {
  try {
    const t = typeOf(e);
    if (t === INVADER.target) { holoName(e, 0, 0); return; }
    register(e);
  } catch (err) { report("spawn", err); }
}

// ---------------------------------------------------------------------------
//  毎 tick
// ---------------------------------------------------------------------------
export function tickInvaders() {
  const t = now();
  const n = lastTick < 0 ? 1 : clamp(t - lastTick, 1, 4);
  lastTick = t;
  if (t >= scanAt) {
    scanAt = t + 10;
    try { scan(); } catch (err) { report("scan", err); }
  }
  // 時間割（予定・ボスの技・危険物・ボルト）は経過した tick を一つずつ進める（2 tick ごとの呼び出しでも
  // 「k === 20」のような節目を飛ばさない）。AI（位置取り・技の選択）は 1 回だけ。
  for (let s = n - 1; s >= 0; s--) timeline(t - s);
  for (const [id, r] of reg) {
    if (!valid(r.e)) { reg.delete(id); continue; }
    try {
      r.st.last = r.e.location;
      r.st.dim = r.e.dimension;
      if (!alive(r.e)) continue;
      if (r.kind === "drone") droneTick(r, t, n);
      else if (r.kind === "sentinel") sentinelTick(r, t, n);
      else bossTick(r, t, n);
    } catch (err) { report(r.kind, err); }
  }
  if (t >= holoAt) { holoAt = t + 10; holoSweep(t); }
}
let holoAt = 0;

function timeline(tt) {
  for (let i = tasks.length - 1; i >= 0; i--) {
    const k = tasks[i];
    if (k.due > tt) continue;
    tasks.splice(i, 1);
    if (k.owner && !alive(k.owner)) continue;
    try { k.fn(tt); } catch (err) { report("task", err); }
  }
  for (const r of reg.values()) {
    const act = r.st.act;
    if (r.kind !== "boss" || !act || !alive(r.e)) continue;
    const k = tt - act.t0;
    if (k < 0) continue;
    let keep = false;
    try { keep = act.step(k, tt); } catch (err) { report(`boss.${act.name}`, err); }
    if (!keep && r.st.act === act) {
      r.st.act = null;
      setMode(r.e, 0);
      const g = CFG.boss.gap[r.st.phase];
      r.st.next = tt + Math.round(rand(g[0], g[1]));
    }
  }
  for (let i = hazards.length - 1; i >= 0; i--) {
    let keep = false;
    try { keep = hazards[i].step(tt); } catch (err) { report("hazard", err); }
    if (!keep) hazards.splice(i, 1);
  }
  for (let i = bolts.length - 1; i >= 0; i--) {
    let keep = false;
    try { keep = boltStep(bolts[i], tt, 1); } catch (err) { report("bolt", err); }
    if (!keep) bolts.splice(i, 1);
  }
}

// ===========================================================================
//  ヴォイド・ドローン: 6〜10 m の距離を保って周りを回り、0.6 秒の溜め（眼が光り照準線が伸びる）の後に
//  ボルトを撃つ（約 3 秒ごと）。
// ===========================================================================
function droneEye(e) {
  const l = e.location;
  return up(l, 0.62);
}

function droneTick(r, t, dt) {
  const e = r.e;
  const st = r.st;
  const C = CFG.drone;
  if (!st.tgt || !alive(st.tgt) || t >= (st.retarget ?? 0)) {
    st.tgt = nearestPlayer(e, C.range);
    st.retarget = t + 10;
  }
  const tgt = st.tgt;
  const pos = e.location;
  const dim = e.dimension;
  // 下の噴射の光
  if (t % 4 === 0) P(dim, "trail", up(pos, 0.15), { size: 0.9, life: 0.25, color: VIO });
  if (!tgt) {
    if (st.engaged) { event(e, "astro:disengage"); st.engaged = false; }
    if (st.mode) { setMode(e, 0); st.mode = 0; }
    return;
  }
  if (!st.engaged) { event(e, "astro:engage"); st.engaged = true; st.orbit = Math.random() < 0.5 ? -1 : 1; }
  // ---- 位置取り: 標的から st.keep m・高さ +3 の輪の上を回る ----
  const tp = tgt.location;
  let away = flat(sub(pos, tp));
  const ang = (st.orbit ?? 1) * 0.012 * dt * (st.mode ? 0.2 : 1);
  away = { x: away.x * Math.cos(ang) - away.z * Math.sin(ang), y: 0, z: away.x * Math.sin(ang) + away.z * Math.cos(ang) };
  const want = add(tp, away, st.keep ?? 8);
  want.y = tp.y + C.height + Math.sin(t * 0.05 + (st.born % 7)) * 0.6;
  if (t >= (st.floorAt ?? 0)) {
    st.floor = groundY(dim, want, 8, 4);
    st.floorAt = t + 10;
  }
  if (Number.isFinite(st.floor)) want.y = Math.max(want.y, st.floor + 1.6);
  const d = sub(want, pos);
  const sp = Math.min(C.maxSpeed * (st.mode ? 0.25 : 1), len(d) * 0.09);
  const dn = norm(d);
  steer(e, { x: dn.x * sp, y: clamp(dn.y * sp, -0.2, 0.2), z: dn.z * sp }, 0.3);
  // ---- うなり ----
  if (t >= (st.hum ?? 0)) {
    st.hum = t + 18 + Math.round(rand(0, 6));
    if (dist(pos, tp) < 14) snd(dim, "drone_hum", pos, rand(0.92, 1.08), 0.45);
  }
  // ---- 攻撃: 溜め → 発射 ----
  const range = dist(pos, tp);
  if (st.mode === 0 && t >= st.next && range > C.minRange && range < C.range && bolts.length < BOLT_CAP) {
    st.mode = 1;
    setMode(e, 1);
    st.fireAt = t + C.charge;
    snd(dim, "beam_charge", pos, 1.7, 0.55);
    P(dim, "converge", droneEye(e), { count: 10, spread: 1.4, life: 0.55, size: 0.6, color: MAG });
  }
  if (st.mode === 1) {
    const eye = droneEye(e);
    const aim = chest(tgt);
    if (t % 2 === 0) {
      P(dim, "glow", eye, { size: 0.7 + (1 - (st.fireAt - t) / C.charge) * 0.8, life: 0.15, color: MAG });
      // 照準線（予告）: 眼から標的の胸へ細い点線
      P(dim, "line_n", eye, { vx: aim.x - eye.x, vy: aim.y - eye.y, vz: aim.z - eye.z, count: 10, size: 0.35, life: 0.12, color: RED, var: 4 });
    }
    if (t >= st.fireAt) {
      st.mode = 2;
      setMode(e, 2);
      st.modeEnd = t + 8;
      st.next = t + C.period + Math.round(rand(-C.jitter, C.jitter));
      fireBolt(e, eye, aim);
    }
  } else if (st.mode === 2 && t >= st.modeEnd) {
    st.mode = 0;
    setMode(e, 0);
  }
}

function fireBolt(owner, from, to, speed = CFG.drone.boltSpeed, dmg = CFG.drone.boltDamage) {
  const dim = owner.dimension;
  const dir = norm(sub(to, from));
  const start = add(from, dir, 0.6);
  snd(dim, "drone_laser", from, rand(0.95, 1.1), 0.9);
  P(dim, "flare", start, { size: 0.9, life: 0.2, color: MAG });
  if (bolts.length >= BOLT_CAP) return;
  let b;
  try { b = dim.spawnEntity(INVADER.bolt, start); } catch (_) { b = undefined; }
  let real = false;
  if (b) {
    try {
      const pc = b.getComponent("minecraft:projectile");
      if (pc && typeof pc.shoot === "function") {
        try { pc.owner = owner; } catch (_) { }
        pc.shoot({ x: dir.x * speed, y: dir.y * speed, z: dir.z * speed }, { uncertainty: 0 });
        real = true;
      }
    } catch (_) { real = false; }
  }
  bolts.push({ e: b, real, pos: start, dir, speed, born: now(), owner, dmg, dim, last: start });
}

/** ボルト: 本物の投射物なら軌跡と着弾の光だけ。shoot が無い版では自前で飛ばして当てる。 */
function boltStep(b, t, dt) {
  const age = t - b.born;
  if (b.real) {
    if (!valid(b.e)) { boltImpact(b, b.last); return false; }
    try { b.last = b.e.location; } catch (_) { }
    P(b.dim, "trail", b.last, { size: 1.3, life: 0.22, color: MAG });
    if (age > 80) { try { b.e.remove(); } catch (_) { } return false; }
    return true;
  }
  const from = b.pos;
  const to = add(from, b.dir, b.speed * dt);
  // 当たり: 線分 from→to の近くのプレイヤー
  for (const p of players(b.dim)) {
    const c = chest(p);
    if (segDist(c, from, to) < 0.75) {
      hurt(p, b.dmg, valid(b.owner) ? b.owner : undefined, "projectile");
      knock(p, b.dir.x, b.dir.z, 0.35, 0.15);
      boltImpact(b, c);
      return false;
    }
  }
  if (solid(b.dim, to) || age > 70) { boltImpact(b, to); return false; }
  b.pos = to;
  b.last = to;
  if (valid(b.e)) { try { b.e.teleport(to); } catch (_) { } }
  P(b.dim, "trail", to, { size: 1.3, life: 0.22, color: MAG });
  if (age % 2 === 0) P(b.dim, "glow", to, { size: 0.5, life: 0.1, color: MAG });
  return true;
}

function boltImpact(b, at) {
  if (!finite(at)) return;
  if (valid(b.e)) { try { b.e.remove(); } catch (_) { } }
  P(b.dim, "impact", at, { size: 0.8, life: 0.2, color: MAG });
  P(b.dim, "spark", at, { count: 5, speed: 4, size: 0.6, color: MAG, life: 0.4 });
  snd(b.dim, "hit", at, 1.5, 0.5);
}

function segDist(p, a, b) {
  const ab = sub(b, a);
  const l2 = ab.x * ab.x + ab.y * ab.y + ab.z * ab.z;
  let k = 0;
  if (l2 > 1e-9) k = clamp(((p.x - a.x) * ab.x + (p.y - a.y) * ab.y + (p.z - a.z) * ab.z) / l2, 0, 1);
  return dist(p, add(a, ab, k));
}

// ===========================================================================
//  ヴォイド・センチネル: 近接はバニラ AI。5 m 以内にプレイヤーがいると約 6 秒ごとに
//  両腕を振りかぶり（0.8 秒・足元に半径 6.5 m の警告）、叩きつけて地を走る衝撃波を出す。
//  衝撃波は地面の高さを走るので、跳べば避けられる。
// ===========================================================================
function sentinelTick(r, t, dt) {
  const e = r.e;
  const st = r.st;
  const C = CFG.sentinel;
  const dim = e.dimension;
  const pos = e.location;
  // 足音
  const v = velocity(e);
  if (Math.hypot(v.x, v.z) > 0.04 && t >= (st.step ?? 0)) {
    st.step = t + 9;
    snd(dim, "sentinel_step", pos, rand(0.9, 1.1), 0.7);
    if ((st.stepN = (st.stepN ?? 0) + 1) % 2 === 0) P(dim, "dust", up(pos, 0.05), { count: 4, size: 0.6, spread: 0.4, life: 0.6 });
  }
  if (st.mode !== 0) return;
  if (t < st.next) return;
  if (!st.tgt || !alive(st.tgt) || t >= (st.retarget ?? 0)) {
    st.tgt = nearestPlayer(e, C.range);
    st.retarget = t + 10;
  }
  const tgt = st.tgt;
  if (!tgt) return;
  const tp = tgt.location;
  if (hdist(tp, pos) > C.trigger || Math.abs(tp.y - pos.y) > 3) return;
  let onGround = true;
  try { onGround = e.isOnGround !== false; } catch (_) { }
  if (!onGround || !canHazard()) return;
  // ---- 振りかぶり（予告 0.8 秒） ----
  st.mode = 1;
  setMode(e, 1);
  const centre = { x: pos.x, y: pos.y, z: pos.z };
  face(e, tp);
  try { e.addEffect("slowness", C.windup + 14, { amplifier: 6, showParticles: false }); } catch (_) { }
  warn(dim, centre, C.waveRadius, C.windup / 20 + 0.15);
  P(dim, "circle", up(centre, 0.1), { size: 1.6, life: 1.0, color: MAG, spin: 120 });
  P(dim, "converge", up(pos, 2.4), { count: 14, spread: 2.0, life: 0.7, size: 0.8, color: MAG });
  snd(dim, "beam_charge", pos, 0.7, 0.8);
  snd(dim, "alert", pos, 0.8, 0.6);
  later(C.windup, e, () => sentinelSlam(r, centre));
  later(C.windup + 18, null, () => {
    st.mode = 0;
    if (valid(e)) setMode(e, 0);
  });
  st.next = t + C.period + Math.round(rand(-C.jitter, C.jitter));
}

function sentinelSlam(r, centre) {
  const e = r.e;
  const C = CFG.sentinel;
  const dim = e.dimension;
  r.st.mode = 2;
  setMode(e, 2);
  snd(dim, "sentinel_slam", centre, 1.0, 1.0);
  shake(dim, centre, 14, 0.7, 0.4);
  const g = up(centre, 0.1);
  P(dim, "shock_flat", g, { size: C.waveRadius / 2.2, life: 0.55, color: MAG });
  P(dim, "impact", up(centre, 0.4), { size: 2.2, life: 0.3, color: WHITE });
  P(dim, "dust", g, { count: 18, size: 1.2, spread: 1.4, speed: 4, life: 1.0 });
  P(dim, "debris", up(centre, 0.3), { count: 10, speed: 5, size: 0.9, life: 1.4 });
  const hit = new Set();
  const t0 = now();
  addHazard({
    owner: e,
    step(t) {
      const rad = 0.8 + (t - t0) * C.waveSpeed;
      if (rad > C.waveRadius) return false;
      P(dim, "ring_n", g, { count: 22, spread: rad, size: 0.7, life: 0.12, color: (t - t0) % 2 ? MAG : VIO });
      if ((t - t0) % 3 === 0) P(dim, "dust", g, { count: 6, size: 0.9, spread: rad, speed: 1, life: 0.6 });
      for (const p of players(dim)) {
        if (hit.has(p.id)) continue;
        const pl = p.location;
        const d = hdist(pl, centre);
        if (Math.abs(d - rad) > 0.9) continue;
        if (pl.y - centre.y > C.jumpClear || pl.y < centre.y - 2) continue;     // 跳べば避けられる
        hit.add(p.id);
        hurt(p, C.waveDamage, valid(e) ? e : undefined, "entityAttack");
        const f = flat(sub(pl, centre));
        knock(p, f.x, f.z, 0.7, 0.4);
        P(dim, "impact", up(pl, 0.4), { size: 1.0, life: 0.2, color: MAG });
      }
      return true;
    },
  });
}

// ===========================================================================
//  虚星王 ネメシス
//  第一形態: 光線の薙ぎ払い / ドローン召喚 / 隕石雨 / 黒孔 / 突進 を間を置いて繰り返す。
//  第二形態（体力 50% 以下）: 咆哮して覚醒。間隔が短く、光線は二本の交差、隕石は 8 個、
//  召喚は 3 体、突進は二連。全ての攻撃に 0.5 秒以上の予告（警告の輪・赤い点線・溜めの光と音）。
// ===========================================================================
const BOSS_MOVES = ["beam", "summon", "meteor", "blackhole", "dash"];

function bossInit(r) {
  const st = r.st;
  st.phase = 1;
  try { st.phase = r.e.getProperty?.("astro:phase") === 2 ? 2 : 1; } catch (_) { }
  st.anchor = r.e.location;
  st.act = null;
  st.lastMove = "";
  st.next = now() + 50;
  if (!st.quietIntro) bossRoar(r, false);
}

function bossEye(e) {
  const l = e.location;
  let f = { x: 0, y: 0, z: 1 };
  try { f = flat(e.getViewDirection()); } catch (_) { }
  return add(up(l, 2.1), f, 0.75);
}

function bossCore(e) { return up(e.location, 2.1); }

function minions(boss) {
  let list = [];
  try { list = boss.dimension.getEntities({ type: INVADER.drone, tags: [MINION_TAG], location: boss.location, maxDistance: 48 }); } catch (_) { }
  return list.filter((d) => {
    try { return d.hasTag(`astro_m_${boss.id}`); } catch (_) { return false; }
  });
}

function bossTick(r, t, dt) {
  const e = r.e;
  const st = r.st;
  const C = CFG.boss;
  const dim = e.dimension;
  // ---- 形態 ----
  const h = hp(e);
  if (st.phase === 1 && h && h.cur <= h.max * 0.5 && !st.act?.locked) {
    st.phase = 2;
    try { e.setProperty("astro:phase", 2); } catch (_) { }
    st.act = null;
    bossRoar(r, true);
  }
  // ---- 標的 ----
  if (!st.tgt || !alive(st.tgt) || t >= (st.retarget ?? 0)) {
    st.tgt = nearestPlayer(e, C.range);
    st.retarget = t + 20;
  }
  const tgt = st.tgt;
  const pos = e.location;
  // ---- 漂う虚空の粒 ----
  if (t % 6 === 0) {
    const a = rand(0, Math.PI * 2);
    P(dim, "void", add(bossCore(e), { x: Math.cos(a) * 2.2, y: rand(-1.5, 1.5), z: Math.sin(a) * 2.2 }), { count: 1, size: 1.0, life: 1.0, color: VIO });
  }
  if (st.phase === 2 && t % 5 === 0) P(dim, "ember", up(pos, 1.2), { count: 3, spread: 1.6, size: 0.8, life: 1.0, color: MAG });
  // ---- 位置取り（突進中は突進が動かす） ----
  if (!st.act?.moves) {
    let want;
    if (tgt) {
      const tp = tgt.location;
      const away = flat(sub(pos, tp));
      want = add(tp, away, C.keep);
      want.y = tp.y + C.hover;
      face(e, up(tp, 1.4));
    } else {
      want = up(st.anchor ?? pos, 0);
    }
    if (t >= (st.floorAt ?? 0)) {
      st.floor = groundY(dim, want, 12, 6);
      st.floorAt = t + 10;
    }
    if (Number.isFinite(st.floor)) want.y = Math.max(want.y, st.floor + 1.4);
    const d = sub(want, pos);
    const slow = st.act ? 0.15 : (t < (st.recover ?? 0) ? 0.3 : 1);
    const sp = Math.min(C.maxSpeed[st.phase] * slow, len(d) * 0.06);
    const dn = norm(d);
    steer(e, { x: dn.x * sp, y: clamp(dn.y * sp, -0.15, 0.15), z: dn.z * sp }, 0.25);
  }
  if (st.act || !tgt || t < st.next) return;
  // ---- 次の技を選ぶ ----
  const range = dist(pos, tgt.location);
  const options = BOSS_MOVES.filter((m) => {
    if (m === st.lastMove) return false;
    if (m === "summon") return minions(e).length < MINION_CAP;
    if (m === "blackhole") return range < 16 && canHazard(2);
    if (m === "meteor") return canHazard(3);
    if (m === "dash") return range < 20;
    return range < 26;
  });
  if (!options.length) { st.next = t + 20; return; }
  const name = options[Math.floor(Math.random() * options.length)];
  st.lastMove = name;
  st.act = BOSS_ACTS[name](r, tgt);
  st.act.name = name;
  st.act.t0 = t + 1;          // 次の tick の時間割で k = 0 から
}

function bossRoar(r, awaken) {
  const e = r.e;
  const st = r.st;
  const dim = e.dimension;
  const c = bossCore(e);
  st.act = {
    name: "roar", locked: true, t0: now() + 1,
    step(k) {
      if (k === 0) {
        setMode(e, 7);
        snd(dim, "nemesis_roar", c, awaken ? 0.8 : 1.0, 1.0);
        P(dim, "lens", c, { size: 3, life: 0.8, color: MAG });
        P(dim, "ring", c, { size: 4, life: 0.6, color: VIO });
        shake(dim, c, 24, awaken ? 1.0 : 0.6, 0.8);
        if (awaken) {
          titleNear(dim, c, 64, "§5§l虚星王 覚醒", "§dPHASE 2 — 空が裂ける", 40);
          P(dim, "void", c, { count: 5, size: 2.4, spread: 1.5, life: 1.6, color: VIO });
        }
      }
      if (awaken && k === 10) {
        // 覚醒の衝撃: 近くのプレイヤーを押し返す（予告は 0.5 秒の咆哮）
        P(dim, "shock_flat", up(e.location, 0.1), { size: 4, life: 0.6, color: MAG });
        for (const p of players(dim)) {
          const d = dist(p.location, c);
          if (d > 8) continue;
          const f = flat(sub(p.location, c));
          knock(p, f.x, f.z, 1.2, 0.5);
          hurt(p, 3, e, "entityAttack");
        }
      }
      if (k % 4 === 0) P(dim, "converge", c, { count: 12, spread: 4, size: 1.0, life: 0.5, color: awaken ? MAG : VIO });
      return k < 30;
    },
  };
}

// ---- 各技 --------------------------------------------------------------------
const BOSS_ACTS = {
  // 光線の薙ぎ払い: 標的を横切る地面の線を 1.0 秒予告し、1.2 秒かけて眼から光線を走らせる。
  // 第二形態は逆向きの二本目が交差する。
  beam(r, tgt) {
    const e = r.e;
    const dim = e.dimension;
    const st = r.st;
    const P2 = st.phase === 2;
    const T = tgt.location;
    const f = flat(sub(T, e.location));
    const rt = rightOf(f);
    const gy = groundY(dim, T, 6, 3);
    const W = 7.5;
    const lines = [[add(add(T, rt, -W), f, -1), add(add(T, rt, W), f, 1)]];
    if (P2) lines.push([add(add(T, rt, W), f, -1.6), add(add(T, rt, -W), f, 1.6)]);
    for (const L of lines) for (const p of L) p.y = gy + 0.1;
    const hitAt = new Map();
    const dmg = CFG.boss.beamDamage[st.phase];
    if (!canHazard(lines.length)) return { step: () => false };
    return {
      step(k, tt) {
        const eye = bossEye(e);
        if (k === 0) {
          setMode(e, 1);
          snd(dim, "nemesis_charge", eye, 1.0, 1.0);
          snd(dim, "beam_charge", eye, 0.8, 1.0);
          P(dim, "converge", eye, { count: 22, spread: 3.0, life: 0.9, size: 1.2, color: MAG });
          P(dim, "circle_v", eye, { dir: norm(sub(T, eye)), size: 1.6, life: 1.1, color: MAG });
          for (const [a, b] of lines) {
            P(dim, "line_n", a, { vx: b.x - a.x, vy: 0, vz: b.z - a.z, count: 36, size: 0.6, life: 1.0, color: RED, var: 4 });
            for (let i = 0; i <= 4; i++) warn(dim, lerp3(a, b, i / 4), 0.9, 1.0);
          }
        }
        if (k < 20) {
          if (k % 3 === 0) P(dim, "glow", eye, { size: 1.5 + k * 0.08, life: 0.2, color: MAG });
          return true;
        }
        if (k === 20) {
          setMode(e, 2);
          const until = tt + 26;
          for (let i = 0; i < lines.length; i++) addHazard({ owner: e, step: (t2) => t2 < until });
          snd(dim, "beam_fire", eye, 0.8, 1.0);
          snd(dim, "laser", eye, 0.7, 1.0);
          shake(dim, eye, 20, 0.5, 1.2);
        }
        const s = (k - 20) / 24;
        if (s > 1) return k < 50;
        lines.forEach(([a, b], li) => {
          const G = lerp3(a, b, s);
          const dv = sub(G, eye);
          const dn = norm(dv);
          P(dim, "beam", eye, { dir: dn, len: len(dv), size: 1.7, life: 0.12, color: MAG });
          if (k % 2 === 0) {
            P(dim, "spark", G, { count: 4, speed: 5, size: 0.8, color: MAG, life: 0.4 });
            P(dim, "ember", G, { count: 2, spread: 0.3, size: 0.8, life: 0.8, color: MAG });
          }
          for (const p of players(dim)) {
            const key = `${p.id}:${li}`;
            if (hitAt.has(key)) continue;          // 一本の光線は一人に一度だけ当たる
            if (segDist(chest(p), eye, G) < 1.2 || segDist(up(p.location, 0.2), eye, G) < 1.0) {
              hitAt.set(key, k);
              hurt(p, dmg, e, "entityAttack");
              knock(p, dn.x, dn.z, 0.4, 0.25);
              P(dim, "impact", chest(p), { size: 1.2, life: 0.2, color: MAG });
            }
          }
        });
        return true;
      },
    };
  },

  // ドローン召喚: 周りに虚空の門を開き（1.2 秒）、2〜3 機のドローンを呼ぶ。子機は最大 6。
  summon(r) {
    const e = r.e;
    const dim = e.dimension;
    const st = r.st;
    const n = Math.min(CFG.boss.summon[st.phase], MINION_CAP - minions(e).length);
    const gates = [];
    const c = bossCore(e);
    for (let i = 0; i < n; i++) {
      const a = (i / Math.max(1, n)) * Math.PI * 2 + rand(0, 1);
      let g = { x: c.x + Math.cos(a) * 4.0, y: c.y + rand(-0.5, 1.2), z: c.z + Math.sin(a) * 4.0 };
      if (solid(dim, g) || solid(dim, up(g, 1))) g = up(c, 2.5);
      gates.push(g);
    }
    return {
      step(k) {
        if (k === 0) {
          setMode(e, 3);
          snd(dim, "nemesis_roar", c, 1.3, 0.8);
          for (const g of gates) {
            P(dim, "void", g, { count: 3, size: 1.6, spread: 0.4, life: 1.4, color: VIO });
            P(dim, "converge", g, { count: 14, spread: 2.0, life: 1.0, size: 0.8, color: MAG });
          }
        }
        if (k % 6 === 0 && k < 24) for (const g of gates) P(dim, "ring", g, { size: 1.0 + k / 24, life: 0.3, color: VIO });
        if (k === 24) {
          for (const g of gates) {
            let d;
            try { d = dim.spawnEntity(INVADER.drone, g); } catch (_) { d = undefined; }
            if (!d) continue;
            try { d.addTag(MINION_TAG); d.addTag(`astro_m_${e.id}`); } catch (_) { }
            const rr = register(d);
            if (rr) rr.st.next = now() + Math.round(rand(30, 60));
            P(dim, "impact", g, { size: 1.6, life: 0.3, color: MAG });
            P(dim, "ring", g, { size: 2.0, life: 0.4, color: MAG });
            snd(dim, "drone_hum", g, 1.3, 0.8);
          }
        }
        return k < 36;
      },
    };
  },

  // 隕石雨: 5（第二形態 8）個の隕石。落ちる所に 1.3 秒前から警告の輪。最初の 1 個は標的の足元。
  meteor(r, tgt) {
    const e = r.e;
    const dim = e.dimension;
    const st = r.st;
    const n = CFG.boss.meteorCount[st.phase];
    const every = st.phase === 2 ? 4 : 5;
    return {
      step(k) {
        if (k === 0) {
          setMode(e, 4);
          snd(dim, "nemesis_roar", bossCore(e), 0.75, 1.0);
          P(dim, "circle", up(e.location, 0.1), { size: 3, life: 1.2, color: VIO, spin: 90 });
          P(dim, "pillar", bossCore(e), { size: 1.5, height: 14, life: 0.6, color: VIO });
        }
        const i = (k - 6) / every;
        if (k >= 6 && Number.isInteger(i) && i < n) {
          let at;
          const ps = players(dim).filter((p) => dist(p.location, e.location) < 40);
          const who = i === 0 || !ps.length ? tgt : ps[Math.floor(Math.random() * ps.length)];
          const base = alive(who) ? who.location : (tgt?.location ?? e.location);
          at = i === 0 ? { ...base } : add(base, { x: rand(-6, 6), y: 0, z: rand(-6, 6) });
          at.y = groundY(dim, up(at, 4), 14, 4);
          meteor(e, at, CFG.boss.meteorDamage[st.phase]);
        }
        return k < 6 + n * every + 4;
      },
    };
  },

  // 黒孔: 標的と自分の間に重力の井戸（予告 1.0 秒）。3 秒間引き寄せ、中心では削る。
  // 最後に 0.6 秒の予告の後に弾ける。
  blackhole(r, tgt) {
    const e = r.e;
    const dim = e.dimension;
    const st = r.st;
    const T = tgt.location;
    const H = up(lerp3(T, e.location, 0.35), 1.4);
    H.y = Math.max(H.y, groundY(dim, H, 8, 3) + 1.4);
    blackHole(e, H, CFG.boss.holeDamage[st.phase], st.phase);
    return {
      step(k) {
        if (k === 0) setMode(e, 5);
        return k < 34;
      },
    };
  },

  // 突進: 赤い点線で進路を 0.8 秒予告し、眼を光らせてから一直線に突っ込む。第二形態は二連。
  dash(r, tgt) {
    const e = r.e;
    const dim = e.dimension;
    const st = r.st;
    const reps = st.phase === 2 ? 2 : 1;
    let rep = 0;
    let k0 = 0;
    let dir, end, hitSet, stalled = 0;
    const plan = () => {
      const from = e.location;
      const T = alive(tgt) ? tgt.location : add(from, { x: 0, y: 0, z: 6 });
      const aim = up(T, -0.6);
      const dv = sub(aim, from);
      const L = clamp(len(dv) + 3, 6, 18);
      dir = norm({ x: dv.x, y: clamp(dv.y, -6, 2), z: dv.z });
      end = add(from, dir, L);
      hitSet = new Set();
      const gy = groundY(dim, T, 6, 3);
      const g0 = { x: from.x, y: gy + 0.1, z: from.z };
      const g1 = { x: end.x, y: gy + 0.1, z: end.z };
      setMode(e, 1);
      face(e, up(T, 1));
      snd(dim, "nemesis_charge", bossCore(e), 1.2, 1.0);
      P(dim, "line_n", g0, { vx: g1.x - g0.x, vy: 0, vz: g1.z - g0.z, count: 30, size: 0.7, life: 0.8, color: RED, var: 4 });
      warn(dim, g1, 2.2, 0.8);
      P(dim, "converge", bossCore(e), { count: 16, spread: 3.0, life: 0.7, size: 1.0, color: MAG });
    };
    return {
      moves: false,
      step(k) {
        const kk = k - k0;
        if (kk === 0) { plan(); this.moves = false; }
        if (kk < 16) {
          steer(e, { x: -dir.x * 0.05, y: 0.02, z: -dir.z * 0.05 }, 0.3);   // 後ろへ溜める
          if (kk % 3 === 0) P(dim, "glow", bossEye(e), { size: 2.0, life: 0.2, color: RED });
          return true;
        }
        if (kk === 16) {
          setMode(e, 6);
          this.moves = true;
          snd(dim, "gust", bossCore(e), 0.7, 1.0);
          snd(dim, "nemesis_roar", bossCore(e), 1.4, 0.6);
        }
        const pos = e.location;
        const left = dist(pos, end);
        const going = kk < 16 + 18 && left > 1.2 && stalled < 4;
        if (going) {
          steer(e, { x: dir.x * 1.05, y: dir.y * 1.05, z: dir.z * 1.05 }, 0.9);
          const v = velocity(e);
          stalled = len(v) < 0.2 && kk > 18 ? stalled + 1 : 0;
          const c = bossCore(e);
          P(dim, "void", c, { count: 1, size: 1.8, life: 0.6, color: VIO });
          P(dim, "speedline", c, { dir: { x: -dir.x, y: -dir.y, z: -dir.z }, count: 4, spread: 1.4, size: 1.2, life: 0.3, color: MAG });
          for (const p of players(dim)) {
            if (hitSet.has(p.id)) continue;
            if (dist(chest(p), c) < 2.8) {
              hitSet.add(p.id);
              hurt(p, CFG.boss.dashDamage[st.phase], e, "entityAttack");
              knock(p, dir.x, dir.z, 1.6, 0.6);
              blast(dim, chest(p), 1.0, MAG);
              snd(dim, "hit_heavy", chest(p), 0.8, 1.0);
            }
          }
          return true;
        }
        // 止まる（壁に当たったら衝撃）
        if (this.moves) {
          this.moves = false;
          steer(e, { x: 0, y: 0, z: 0 }, 1.0);
          setMode(e, 0);
          if (stalled >= 4) { blast(dim, bossCore(e), 1.4, VIO); shake(dim, e.location, 16, 0.8, 0.4); snd(dim, "impact_heavy", e.location, 0.8, 1.0); }
          rep++;
          if (rep < reps) { k0 = k + 8; stalled = 0; return true; }
          st.recover = now() + 24;    // 隙（ゆっくりしか動けない）
          return false;
        }
        return kk < 60;
      },
    };
  },
};

/** 隕石 1 個: 1.3 秒前から警告、0.7 秒前から空を落ちてくる。 */
function meteor(owner, at, dmg) {
  const dim = owner.dimension;
  const R = CFG.boss.meteorRadius;
  const t0 = now();
  const WARN = 26;
  const FALL = 14;
  const sky = add(at, { x: rand(-4, 4), y: 16, z: rand(-4, 4) });
  const dir = norm(sub(at, sky));
  if (!canHazard()) return false;
  warn(dim, at, R, WARN / 20);
  P(dim, "glow", up(at, 0.2), { size: 1.2, life: WARN / 20, color: RED });
  return addHazard({
    owner,
    step(t) {
      const k = t - t0;
      if (k === WARN - 23) snd(dim, "meteor", at, rand(0.9, 1.1), 1.0);   // 音の着弾は 1.15 秒目
      if (k >= WARN - FALL && k < WARN) {
        const s = (k - (WARN - FALL)) / FALL;
        P(dim, "meteor", lerp3(sky, at, s), { dir, size: 1.5, len: 5, life: 0.12, count: 8, color: [1, 0.45, 0.85] });
      }
      if (k < WARN) return true;
      // 着弾
      blast(dim, up(at, 0.6), 1.8, MAG);
      P(dim, "shock_flat", up(at, 0.1), { size: R / 1.6, life: 0.5, color: MAG });
      P(dim, "debris", up(at, 0.4), { count: 10, speed: 6, size: 1.0, life: 1.4 });
      P(dim, "ember", up(at, 0.4), { count: 8, spread: 1.2, size: 1.0, life: 1.2, color: [1, 0.5, 0.3] });
      P(dim, "lens", up(at, 1.0), { size: 1.2, life: 0.4, color: MAG });
      snd(dim, "explosion", at, rand(0.9, 1.1), 1.0);
      shake(dim, at, 14, 0.6, 0.35);
      for (const p of players(dim)) {
        const pl = p.location;
        if (hdist(pl, at) > R + 0.4 || Math.abs(pl.y - at.y) > 3) continue;
        hurt(p, dmg, valid(owner) ? owner : undefined, "entityExplosion");
        const f = flat(sub(pl, at));
        knock(p, f.x, f.z, 0.8, 0.5);
      }
      return false;
    },
  });
}

/** 黒孔: 予告 1.0 秒 → 3 秒の吸引（中心 2.2 m で削る）→ 予告 0.6 秒 → 弾ける。 */
function blackHole(owner, H, dmg, phase) {
  const dim = owner.dimension;
  const t0 = now();
  const PULL0 = 20;
  const PULL1 = PULL0 + (phase === 2 ? 70 : 60);
  const POP = PULL1 + 12;
  const R = 11;
  const g = { x: H.x, y: groundY(dim, H, 8, 2) + 0.08, z: H.z };
  P(dim, "converge", H, { count: 24, spread: 4.5, life: 1.0, size: 1.2, color: VIO });
  P(dim, "void", H, { count: 3, size: 1.5, spread: 0.6, life: 1.0, color: VIO });
  warn(dim, g, 3.0, PULL0 / 20);
  snd(dim, "gravity", H, 0.7, 1.0);
  snd(dim, "nemesis_charge", H, 0.7, 0.8);
  return addHazard({
    owner,
    step(t) {
      const k = t - t0;
      if (k === PULL0) {
        P(dim, "black_hole", H, { size: 1.7, life: (PULL1 - PULL0 + 12) / 20, spin: 140 });
        snd(dim, "gravity", H, 0.5, 1.0);
      }
      if (k >= PULL0 && k < PULL1) {
        if ((k - PULL0) % 20 === 0) P(dim, "lens", H, { size: 1.4, life: 1.0, color: VIO });
        if (k % 4 === 0) P(dim, "converge", H, { count: 10, spread: 6, life: 0.5, size: 1.0, color: VIO });
        if (k % 4 === 0) {
          for (const p of players(dim)) {
            const d = dist(p.location, H);
            if (d > R || d < 0.6) continue;
            const f = flat(sub(H, p.location));
            const s = 0.12 + 0.24 * (1 - d / R);
            knock(p, f.x, f.z, s, clamp((H.y - p.location.y) * 0.04, -0.05, 0.12));
          }
        }
        if (k % 10 === 0) {
          for (const p of players(dim)) {
            if (dist(chest(p), H) < 2.2) hurt(p, 3, valid(owner) ? owner : undefined, "magic");
          }
        }
      }
      if (k === PULL1) {
        warn(dim, g, 4.5, (POP - PULL1) / 20);
        P(dim, "ring", H, { size: 3, life: 0.6, color: MAG });
        snd(dim, "nemesis_charge", H, 1.5, 1.0);
      }
      if (k < POP) return true;
      P(dim, "lens", H, { size: 3.0, life: 0.6, color: MAG });
      P(dim, "shock_flat", g, { size: 3.0, life: 0.5, color: VIO });
      blast(dim, H, 2.0, VIO);
      snd(dim, "explosion_big", H, 1.3, 1.0);
      shake(dim, H, 18, 0.8, 0.5);
      for (const p of players(dim)) {
        const d = dist(chest(p), H);
        if (d > 4.5) continue;
        hurt(p, dmg, valid(owner) ? owner : undefined, "magic");
        const f = flat(sub(p.location, H));
        knock(p, f.x, f.z, 1.1, 0.5);
      }
      return false;
    },
  });
}

// ---------------------------------------------------------------------------
//  ネメシスの降臨（ヴォイド・シグナル）
// ---------------------------------------------------------------------------
let summoning = null;     // { until }

function isNight() {
  try {
    const tod = world.getTimeOfDay();
    return tod >= 13000 && tod <= 23000;
  } catch (_) { return true; }
}

function bossNear(dim, loc, radius) {
  for (const r of reg.values()) {
    if (r.kind !== "boss" || !alive(r.e)) continue;
    try { if (r.e.dimension.id === dim.id && dist(r.e.location, loc) < radius) return true; } catch (_) { }
  }
  try { return dim.getEntities({ type: INVADER.boss, location: loc, maxDistance: radius }).length > 0; } catch (_) { return false; }
}

function skyOpen(dim, loc) {
  for (let dy = 2; dy <= 14; dy++) if (solid(dim, up(loc, dy))) return false;
  return true;
}

function consumeOne(p, typeId) {
  if (gameMode(p) === "creative") return true;
  try {
    const inv = p.getComponent("minecraft:inventory")?.container;
    let slot = p.selectedSlotIndex;
    if (typeof slot !== "number") slot = p.selectedSlot ?? 0;
    const it = inv?.getItem(slot);
    if (!it || it.typeId !== typeId) return false;
    if (it.amount > 1) { it.amount -= 1; inv.setItem(slot, it); } else inv.setItem(slot, undefined);
    return true;
  } catch (_) { return false; }
}

/**
 * ヴォイド・シグナルを使った / ボスを呼ぶ。決まり: オーバーワールドの夜（13000〜23000）・空が見える場所・
 * 近く（160 m）にネメシスがいない時だけ。成功すると 3.3 秒の降臨演出の後に出現する。
 * @param {Player} p
 * @param {{force?: boolean, consume?: boolean}} [opts] force = 決まりを無視（/scriptevent astro:boss）、
 *        consume = 手のシグナルを 1 つ減らす（既定: force でなければ true。クリエイティブでは減らさない）
 * @returns {boolean} 降臨を始めたか
 */
export function summonNemesis(p, opts = {}) {
  const force = !!opts.force;
  const consume = opts.consume ?? !force;
  if (!valid(p)) return false;
  const dim = p.dimension;
  const loc = p.location;
  if (summoning && summoning.until > now()) { tell(p, "§5…虚空が開きつつある"); return false; }
  if (!force) {
    if (dim.id !== "minecraft:overworld") { tell(p, "§5ヴォイド・シグナルは地上（オーバーワールド）の空にしか届かない"); return false; }
    if (!isNight()) { tell(p, "§5シグナルは夜空にしか届かない。夜を待て"); return false; }
    if (!skyOpen(dim, loc)) { tell(p, "§5空の見える場所で使え"); return false; }
    if (bossNear(dim, loc, 160)) { tell(p, "§5虚星王はすでにこの空にいる"); return false; }
  }
  // 出現点: 正面 8〜10 m・地面 +1.5 の、4 ブロックの高さが空いている所
  let f = { x: 0, y: 0, z: 1 };
  try { f = flat(p.getViewDirection()); } catch (_) { }
  let at;
  for (const [deg, d] of [[0, 9], [30, 9], [-30, 9], [0, 6], [60, 7], [-60, 7], [180, 7]]) {
    const r = deg * Math.PI / 180;
    const dd = { x: f.x * Math.cos(r) - f.z * Math.sin(r), y: 0, z: f.x * Math.sin(r) + f.z * Math.cos(r) };
    const c = add(loc, dd, d);
    c.y = groundY(dim, up(c, 3), 8, 6) + 1.5;
    if (airBox(dim, c, 1, 4.5)) { at = c; break; }
  }
  if (!at) {
    if (!force) { tell(p, "§5開けた場所で使え（虚星王が降りる空間が無い）"); return false; }
    at = up(loc, 3);
  }
  if (consume && !consumeOne(p, SIGNAL)) return false;
  summoning = { until: now() + 70 };
  const g = { x: at.x, y: groundY(dim, at, 8, 2) + 0.08, z: at.z };
  const core = up(at, 2.1);
  snd(dim, "nemesis_spawn", core, 1.0, 1.0);
  titleNear(dim, at, 64, "§5§l虚星王 ネメシス", "§dVOID STAR — NEMESIS", 50);
  P(dim, "circle", g, { size: 3.2, life: 3.3, color: VIO, spin: 40 });
  P(dim, "warning", g, { size: 2.0, life: 3.2, color: VIO });
  P(dim, "void", core, { count: 4, size: 2.6, spread: 1.0, life: 2.0, color: VIO });
  for (let k = 10; k <= 60; k += 5) {
    later(k, null, () => {
      P(dim, "converge", core, { count: 18, spread: 5, life: 0.6, size: 1.2, color: k % 10 ? MAG : VIO });
      if (k % 10 === 0) {
        const s = add(core, { x: rand(-3, 3), y: 12, z: rand(-3, 3) });
        const dv = sub(core, s);
        P(dim, "bolt", s, { dir: norm(dv), len: len(dv), size: 1.4, life: 0.25, color: VIO });
        shake(dim, core, 30, 0.3, 0.3);
      }
    });
  }
  later(50, null, () => P(dim, "black_hole", core, { size: 1.4, life: 1.0, spin: 200 }));
  later(66, null, () => {
    summoning = null;
    let b;
    try { b = dim.spawnEntity(INVADER.boss, at); } catch (err) { report("summon", err); return; }
    face(b, up(loc, 1.4));
    const r = register(b);
    if (r) r.st.next = now() + 40;
    P(dim, "lens", core, { size: 4, life: 0.8, color: MAG });
    P(dim, "ring", core, { size: 5, life: 0.6, color: VIO });
    P(dim, "shock_flat", g, { size: 4, life: 0.6, color: VIO });
    blast(dim, core, 2.0, VIO);
    shake(dim, core, 32, 1.0, 0.8);
  });
  return true;
}

// ---------------------------------------------------------------------------
//  ホログラム標的: 倒れない。直近 5 秒の合計と DPS を頭上に出す
// ---------------------------------------------------------------------------
const holoLogs = new Map();      // id → { e, log: [{t, d}] }

function holoName(e, sum, dps) {
  try { e.nameTag = `§bホログラム標的\n§f5秒合計 §c${sum.toFixed(1)} §7| §fDPS §6${dps.toFixed(1)}`; } catch (_) { }
}

function holoHurt(e, dmg) {
  const t = now();
  const rec = holoLogs.get(e.id) ?? { e, log: [] };
  rec.e = e;
  rec.log = rec.log.filter((x) => t - x.t <= CFG.target.window);
  rec.log.push({ t, d: dmg });
  holoLogs.set(e.id, rec);
  const h = hp(e);
  try { if (h) h.h.setCurrentValue(h.max); } catch (_) { }
  const sum = rec.log.reduce((a, x) => a + x.d, 0);
  const span = Math.max(20, t - rec.log[0].t) / 20;
  holoName(e, sum, sum / span);
  try { P(e.dimension, "hex", up(e.location, 1.2), { size: 1.0, life: 0.25, color: [0.4, 0.95, 1], count: 3, spread: 0.5 }); } catch (_) { }
}

function holoSweep(t) {
  for (const [id, rec] of holoLogs) {
    if (!valid(rec.e)) { holoLogs.delete(id); continue; }
    rec.log = rec.log.filter((x) => t - x.t <= CFG.target.window);
    if (!rec.log.length) { holoName(rec.e, 0, 0); holoLogs.delete(id); }
  }
}

/** ホログラム標的を目の前 3 m に出す。 */
export function summonHologram(p) {
  let f = { x: 0, y: 0, z: 1 };
  try { f = flat(p.getViewDirection()); } catch (_) { }
  const at = add(p.location, f, 3);
  let e;
  try { e = p.dimension.spawnEntity(INVADER.target, at); } catch (_) { return undefined; }
  holoName(e, 0, 0);
  face(e, p.location);
  P(p.dimension, "scan", at, { size: 1.0, height: 2.2, life: 0.6, color: [0.4, 0.95, 1] });
  snd(p.dimension, "ui_select", at, 0.8, 1.0);
  return e;
}

// ---------------------------------------------------------------------------
//  被弾・撃破
// ---------------------------------------------------------------------------
const lastHitSound = new Map();

/**
 * entityHurt から。侵略者なら被弾の音と火花、ホログラム標的なら体力を戻して DPS を出す
 * （opts.hologram === false なら標的は扱わない。enemies.js が自分で DPS を出す場合）。
 * @returns {boolean} enemies.onEntityHurt と同じ「true = ダメージ数字を出さない」。常に false
 */
export function onInvaderHurt(e, damage, source, opts = {}) {
  try {
    const type = typeOf(e);
    if (type === INVADER.target) {
      if (opts.hologram !== false) holoHurt(e, damage);
      return false;
    }
    const kind = KIND[type];
    if (!kind) return false;
    const r = register(e);
    const t = now();
    if ((lastHitSound.get(e.id) ?? -9) <= t - 3) {
      lastHitSound.set(e.id, t);
      if (lastHitSound.size > 200) lastHitSound.clear();
      const pitch = kind === "drone" ? 1.4 : kind === "sentinel" ? 1.0 : 0.7;
      snd(e.dimension, "hit_metal", e.location, pitch * rand(0.95, 1.05), 0.8);
      const c = kind === "boss" ? up(e.location, 2.1) : up(e.location, kind === "drone" ? 0.6 : 1.4);
      P(e.dimension, "spark", c, { count: 5, speed: 4, size: 0.7, color: kind === "boss" ? VIO : MAG, life: 0.4 });
    }
    // ドローンは殴られた相手を狙い直す
    const atk = source?.damagingEntity;
    if (r && valid(atk) && typeOf(atk) === "minecraft:player") { r.st.tgt = atk; r.st.retarget = t + 40; }
  } catch (err) { report("hurt", err); }
  return false;
}

/** entityDie から。爆発の演出・ボスの撃破演出・子機の撤退・標的の復活。 */
export function onInvaderDie(e, source) {
  let type, loc, dim, id;
  try { type = e.typeId; id = e.id; } catch (_) { return; }
  const r = reg.get(id);
  try { loc = e.location; dim = e.dimension; } catch (_) { loc = r?.st.last; dim = r?.st.dim; }
  if (!loc || !dim) return;
  try {
    if (type === INVADER.target) {
      const cause = source?.cause;
      if (cause !== "selfDestruct" && cause !== "void" && cause !== "suicide") {
        later(10, null, () => {
          try {
            const n = dim.spawnEntity(INVADER.target, loc);
            holoName(n, 0, 0);
            P(dim, "scan", loc, { size: 1.0, height: 2.2, life: 0.6, color: [0.4, 0.95, 1] });
          } catch (_) { }
        });
      }
      return;
    }
    const kind = KIND[type];
    if (!kind) return;
    reg.delete(id);
    if (kind === "drone") {
      const c = up(loc, 0.6);
      blast(dim, c, 1.0, MAG);
      P(dim, "debris", c, { count: 5, speed: 4, size: 0.6, life: 1.2 });
      snd(dim, "explosion", c, 1.5, 0.7);
    } else if (kind === "sentinel") {
      const c = up(loc, 1.3);
      blast(dim, c, 1.5, MAG);
      P(dim, "debris", c, { count: 9, speed: 5, size: 0.9, life: 1.4 });
      later(8, null, () => { blast(dim, up(loc, 0.6), 1.2, VIO); snd(dim, "explosion", loc, 1.1, 0.9); });
      snd(dim, "explosion", c, 1.2, 0.9);
      shake(dim, c, 10, 0.4, 0.3);
    } else {
      bossDeath(e, dim, loc);
    }
  } catch (err) { report("die", err); }
}

function bossDeath(e, dim, loc) {
  const core = up(loc, 2.1);
  // 子機は虚空へ撤退
  for (const r of [...reg.values()]) {
    if (r.kind !== "drone" || !valid(r.e)) continue;
    let mine = false;
    try { mine = r.e.hasTag(`astro_m_${e.id}`); } catch (_) { }
    if (!mine) continue;
    const d = r.e;
    later(Math.round(rand(4, 30)), null, () => {
      try {
        P(dim, "void", up(d.location, 0.6), { count: 2, size: 1.2, life: 0.8, color: VIO });
        P(dim, "converge", up(d.location, 0.6), { count: 8, spread: 1.2, life: 0.4, color: VIO });
        d.remove();
      } catch (_) { }
    });
  }
  // 予定と危険物は打ち切る（落下中の隕石も消す）
  for (let i = hazards.length - 1; i >= 0; i--) if (hazards[i].owner && !alive(hazards[i].owner)) hazards.splice(i, 1);
  snd(dim, "nemesis_roar", core, 0.6, 1.0);
  shake(dim, core, 40, 1.2, 1.0);
  // 連鎖爆発 → 最後の大爆発 → タイトル
  for (let i = 0; i < 9; i++) {
    later(4 + i * 5, null, () => {
      const at = add(core, { x: rand(-2.6, 2.6), y: rand(-2, 2.4), z: rand(-2.6, 2.6) });
      blast(dim, at, 1.4, i % 2 ? MAG : VIO);
      snd(dim, "explosion", at, rand(0.8, 1.2), 1.0);
      if (i % 3 === 0) shake(dim, core, 30, 0.6, 0.3);
    });
  }
  later(52, null, () => {
    P(dim, "lens", core, { size: 5, life: 1.0, color: WHITE });
    P(dim, "ring", core, { size: 7, life: 0.8, color: MAG });
    P(dim, "shock_flat", { x: core.x, y: loc.y + 0.1, z: core.z }, { size: 6, life: 0.8, color: VIO });
    P(dim, "black_hole", core, { size: 2.4, life: 1.2, spin: 300 });
    blast(dim, core, 3.0, WHITE);
    P(dim, "star", core, { count: 24, spread: 4, speed: 3, size: 1.2, life: 2.0, color: [1, 0.85, 0.5] });
    snd(dim, "explosion_big", core, 0.8, 1.0);
    shake(dim, core, 48, 1.5, 1.0);
    titleNear(dim, core, 80, "§6§l虚星王 撃破", "§eVOID STAR NEMESIS — DEFEATED", 70);
  });
}

// ---------------------------------------------------------------------------
//  まとめて購読（main.js / enemies.js を使わずに単独で動かす場合）
// ---------------------------------------------------------------------------
let installed = false;
/**
 * @param {{tick?: boolean, itemUse?: boolean, hurt?: boolean, die?: boolean, spawn?: boolean}} [o]
 *   それぞれ false で購読しない（main.js 側で既に配線している物は false にする）
 */
export function installInvaders(o = {}) {
  if (installed) return;
  installed = true;
  const ev = world.afterEvents;
  if (o.tick !== false) system.runInterval(() => { try { tickInvaders(); } catch (err) { report("tick", err); } }, 1);
  if (o.itemUse !== false) {
    ev.itemUse?.subscribe((e) => {
      try { if (e.itemStack?.typeId === SIGNAL) summonNemesis(e.source); } catch (err) { report("itemUse", err); }
    });
  }
  if (o.hurt !== false) ev.entityHurt?.subscribe((e) => onInvaderHurt(e.hurtEntity, e.damage, e.damageSource));
  if (o.die !== false) ev.entityDie?.subscribe((e) => onInvaderDie(e.deadEntity, e.damageSource));
  if (o.spawn !== false) ev.entitySpawn?.subscribe((e) => onInvaderSpawn(e.entity));
}

/** テスト・デバッグ用: 今の状態の要約。 */
export function invaderStats() {
  const kinds = { drone: 0, sentinel: 0, boss: 0 };
  for (const r of reg.values()) kinds[r.kind]++;
  return { ...kinds, hazards: hazards.length, bolts: bolts.length, tasks: tasks.length };
}
