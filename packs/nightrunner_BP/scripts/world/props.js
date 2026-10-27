// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 小道具 nr:prop_*（車の残骸・バス・コンテナ・ゴミ箱…）のバリアと使う場所
//
//  * 置く: 小道具が出たら（entitySpawn・entityLoad・ワールドの読み込み）、向きを data/prop_shapes.js の
//    0 / 90 / 180 / 270 のいちばん近いものに揃え、原点のマス B（整数の角）から spawn のずれの位置へ置き直し、
//    cells のマスに minecraft:barrier を置く（空気のマスだけ。立っているプレイヤーのマスは避ける）。
//    実際に置いたマスはエンティティの動的プロパティ nr:cells（JSON {b, rot, c}）に控える。
//  * 消す: 小道具が消えたら（entityRemove）、2 tick 後にまだ無く、そのチャンクが読み込まれていれば
//    控えのマスのバリアを空気に戻す（読み込みが外れただけならバリアは残し、戻ったとき nr:cells から読み直す）。
//  * 使う（プレイヤーがバリアか小道具そのものを「使う」）: 近い使う場所（points）で
//    loot_trunk / loot_cargo（nr:open で開け閉め、開けた時に spec の loot の表から出る。3 日で補充）、
//    loot_glovebox（LOOT_TABLES.glovebox）、open_doors（開け閉め）、lightbar（回転灯の切り替え）。
//  * 叩く・撃つ（entityHitBlock / projectileHitBlock / entityHitEntity / projectileHitEntity）: 窓の近くなら
//    窓が割れる（nr:smash_glass）。car_alarm のある車は TRAPS.car_alarm の確率でアラーム
//    （nr:alarm_on、lure_ticks の間鳴り続けてバス "noise" {pos, radius: lure_radius, source: "car_alarm"} を出す）。
//    重い着地（バス "noise" の source "landing"）で屋根に飛び乗った・近くの爆発でも鳴ることがある。
//  * 罠の小道具（プロパンボンベ・杭丸太）の仕掛けは world/traps.js の担当（ここはバリアだけ）。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { PROP_SHAPES } from "../data/prop_shapes.js";
import { PROP_BY_ID } from "../data/props.js";
import { TRAP_BY_KEY } from "../data/traps.js";
import { dropLoot } from "../gore/death.js";
import { emit, on } from "../core/bus.js";
import { particle, sound, PRIO } from "../core/fx.js";
import { valid, now, add, sub, dot, dist, getProp, trigger, isPlayer, safe, yawOf, rand, chance } from "../core/util.js";

/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

const PREFIX = "nr:prop_";
const CELLS_DP = "nr:cells";
const LOOT_DP = "nr:looted";
const BARRIER = "minecraft:barrier";
const AIR = "minecraft:air";
const RESTOCK_DAYS = 3;
const DIMENSIONS = ["overworld", "nether", "the_end"];
/** @type {Record<string, any>} */
const SHAPES = /** @type {any} */ (PROP_SHAPES) ?? {};
/** @type {Record<string, any>} */
const PROPS = /** @type {any} */ (PROP_BY_ID) ?? {};
/** @type {any} */
const ALARM = /** @type {any} */ (TRAP_BY_KEY)?.car_alarm ?? {};
const ALARM_CHANCE = Number(ALARM.trigger?.chance ?? 0.35);
const ALARM_RADIUS = Number(ALARM.effect?.lure_radius ?? 40);
const ALARM_TICKS = Number(ALARM.effect?.lure_ticks ?? 300);
const ALARM_REARM = 600;
/** 使う（右クリック）で動く場所 */
const USE_KINDS = new Set(["loot_trunk", "loot_cargo", "loot_glovebox", "open_doors", "lightbar"]);
/** @type {Record<string, Vector3>} */
const FACE = {
  Up: { x: 0, y: 0.5, z: 0 }, Down: { x: 0, y: -0.5, z: 0 }, North: { x: 0, y: 0, z: -0.5 },
  South: { x: 0, y: 0, z: 0.5 }, East: { x: 0.5, y: 0, z: 0 }, West: { x: -0.5, y: 0, z: 0 },
};

/**
 * @typedef {{e: Entity, id: string, key: string, dimId: string, b: number[], rot: string, cells: number[][],
 *   open: boolean, lights: number, glass: boolean, alarmUntil: number, alarmNext: number, alarmStart: number,
 *   alarmRearm: number, alarmBy?: Entity}} PRec
 * @typedef {{b: number[], rot: string, c: number[][]}} Saved
 */
/** @type {Map<string, PRec>} */
const recs = new Map();
/** @type {Map<string, string>} "dim|x|y|z" → 小道具の ID */
const cellIndex = new Map();
/** @type {Map<string, {dimId: string, data: Saved}>} 消える直前に読んだ控え */
const pending = new Map();
/** @type {Set<string>} 鳴っているアラーム */
const alarms = new Set();

// ---------------------------------------------------------------------------
//  引き出し
// ---------------------------------------------------------------------------
/** nr:prop_* か。 @param {Entity | undefined} e */
export function isProp(e) {
  try { return !!e && typeof e.typeId === "string" && e.typeId.startsWith(PREFIX); } catch { return false; }
}
/** @param {Entity} e */
function keyOf(e) { return e.typeId.slice(PREFIX.length); }
/** yaw → "0" / "90" / "180" / "270"（いちばん近い 90 度）。 @param {number} yaw */
export function rotKeyOf(yaw) { return String((((Math.round(yaw / 90) * 90) % 360) + 360) % 360); }
/** @param {string} dimId @param {number} x @param {number} y @param {number} z */
function ck(dimId, x, y, z) { return `${dimId}|${x}|${y}|${z}`; }
/** そのマスのバリアを置いた小道具（無ければ undefined）。 @param {Dimension} dim @param {Vector3} pos @returns {Entity | undefined} */
export function propAt(dim, pos) {
  const id = cellIndex.get(ck(dim.id, Math.floor(pos.x), Math.floor(pos.y), Math.floor(pos.z)));
  const r = id ? recs.get(id) : undefined;
  return r && valid(r.e) ? r.e : undefined;
}
/** 置いたバリアの控え（テスト・建物の担当用）。 @param {Entity} e @returns {{b: number[], rot: string, cells: number[][]} | undefined} */
export function propRecord(e) {
  const r = valid(e) ? recs.get(e.id) : undefined;
  return r ? { b: [...r.b], rot: r.rot, cells: r.cells.map((c) => [...c]) } : undefined;
}
/** @param {Entity} e @returns {Saved | undefined} */
function readSaved(e) {
  try {
    const s = e.getDynamicProperty(CELLS_DP);
    if (typeof s !== "string") return undefined;
    const d = JSON.parse(s);
    return d && Array.isArray(d.b) && Array.isArray(d.c) ? d : undefined;
  } catch { return undefined; }
}

// ---------------------------------------------------------------------------
//  置く・控える・消す
// ---------------------------------------------------------------------------
/** 出た・読み込まれた小道具: 控えがあれば索引だけ、無ければ揃えてバリアを置く。 @param {Entity} e */
function setup(e) {
  if (!isProp(e) || !valid(e) || recs.has(e.id)) return;
  if (!SHAPES[keyOf(e)]) return;
  const saved = readSaved(e);
  if (saved) index(e, saved);
  else place(e);
}

/** @param {Entity} e */
function place(e) {
  const shp = SHAPES[keyOf(e)];
  const rot = rotKeyOf(yawOf(e));
  const R = shp?.rot?.[rot];
  if (!R) return;
  const loc = e.location;
  const b = [Math.round(loc.x - R.spawn[0]), Math.floor(loc.y + 1e-3), Math.round(loc.z - R.spawn[1])];
  const pos = { x: b[0] + R.spawn[0], y: b[1], z: b[2] + R.spawn[1] };
  safe("prop-snap", () => e.teleport(pos, { rotation: { x: 0, y: R.yaw } }));
  const dim = e.dimension;
  /** @type {Set<string>} */
  const occupied = new Set();
  for (const p of safe("prop-players", () => dim.getPlayers({ location: pos, maxDistance: 12 })) ?? []) {
    const fx = Math.floor(p.location.x), fy = Math.floor(p.location.y), fz = Math.floor(p.location.z);
    occupied.add(`${fx}|${fy}|${fz}`);
    occupied.add(`${fx}|${fy + 1}|${fz}`);
  }
  /** @type {number[][]} */
  const placed = [];
  for (const c of R.cells ?? []) {
    const x = b[0] + c[0], y = b[1] + c[1], z = b[2] + c[2];
    if (occupied.has(`${x}|${y}|${z}`)) continue;
    let block;
    try { block = dim.getBlock({ x, y, z }); } catch { block = undefined; }
    if (!block || !block.isAir) continue;
    try { dim.setBlockType({ x, y, z }, BARRIER); placed.push([x, y, z]); } catch { /* 世界の外・読み込まれていない */ }
  }
  /** @type {Saved} */
  const data = { b, rot, c: placed };
  try { e.setDynamicProperty(CELLS_DP, JSON.stringify(data)); } catch { /* 無効 */ }
  index(e, data);
}

/** @param {Entity} e @param {Saved} data */
function index(e, data) {
  const dimId = e.dimension.id;
  /** @type {PRec} */
  const r = {
    e, id: e.id, key: keyOf(e), dimId, b: data.b, rot: String(data.rot ?? "0"), cells: data.c ?? [],
    open: Number(getProp(e, "nr:open", 0)) === 1, lights: Number(getProp(e, "nr:lights", 0)) || 0,
    glass: Number(getProp(e, "nr:glass", 0)) === 1, alarmUntil: 0, alarmNext: 0, alarmStart: 0, alarmRearm: 0,
    alarmBy: undefined,
  };
  recs.set(e.id, r);
  for (const [x, y, z] of r.cells) cellIndex.set(ck(dimId, x, y, z), e.id);
}

/** @param {string} id */
function unindex(id) {
  const r = recs.get(id);
  if (!r) return;
  recs.delete(id);
  alarms.delete(id);
  for (const [x, y, z] of r.cells) {
    const k = ck(r.dimId, x, y, z);
    if (cellIndex.get(k) === id) cellIndex.delete(k);
  }
}

/** 控えのマスのうち、まだバリアのものを空気に戻す。 @param {Dimension} dim @param {number[][]} cells @returns {number} */
function clearBarriers(dim, cells) {
  let n = 0;
  for (const [x, y, z] of cells) {
    try {
      const b = dim.getBlock({ x, y, z });
      if (b?.typeId === BARRIER) { dim.setBlockType({ x, y, z }, AIR); n++; }
    } catch { /* 読み込まれていない */ }
  }
  return n;
}

world.afterEvents.entitySpawn.subscribe((ev) => { if (isProp(ev.entity)) safe("prop-spawn", () => setup(ev.entity)); });
world.afterEvents.entityLoad.subscribe((ev) => { if (isProp(ev.entity)) safe("prop-load", () => setup(ev.entity)); });
world.afterEvents.worldLoad.subscribe(() => {
  for (const d of DIMENSIONS) {
    safe("prop-scan", () => { for (const e of world.getDimension(d).getEntities({ families: ["nr_prop"] })) setup(e); });
  }
});
// 消える直前（読むだけ。書き換えは after と system.run で）
world.beforeEvents.entityRemove.subscribe((ev) => {
  const e = ev.removedEntity;
  if (!isProp(e) || recs.has(e.id)) return;
  const saved = readSaved(e);
  if (saved) pending.set(e.id, { dimId: e.dimension.id, data: saved });
});
world.afterEvents.entityRemove.subscribe((ev) => {
  if (!ev.typeId.startsWith(PREFIX)) return;
  const id = ev.removedEntityId;
  const r = recs.get(id);
  const p = pending.get(id);
  pending.delete(id);
  const dimId = r ? r.dimId : p?.dimId;
  const data = r ? { b: r.b, rot: r.rot, c: r.cells } : p?.data;
  unindex(id);
  if (!dimId || !data) return;
  system.runTimeout(() => safe("prop-remove", () => afterRemove(id, dimId, data)), 2);
});

/** @param {string} id @param {string} dimId @param {Saved} data */
function afterRemove(id, dimId, data) {
  const back = world.getEntity(id);
  if (back) { setup(back); return; }                // 読み直された
  const dim = world.getDimension(dimId);
  let loaded = false;
  try { loaded = dim.isChunkLoaded({ x: data.b[0], y: data.b[1], z: data.b[2] }); } catch { loaded = false; }
  if (!loaded) return;                              // 読み込みが外れただけ（戻れば nr:cells から読む）
  clearBarriers(dim, data.c);
}

// ---------------------------------------------------------------------------
//  使う（開ける・取る・回転灯）
// ---------------------------------------------------------------------------
/**
 * 狙った点にいちばん近い、その種類の使う場所。
 * @param {PRec} r @param {Vector3} aim @param {Set<string>} kinds @param {number} slack
 * @returns {{kind: string, wp: Vector3} | undefined}
 */
function nearestPoint(r, aim, kinds, slack) {
  const shp = SHAPES[r.key];
  const pts = shp?.rot?.[r.rot]?.points ?? [];
  /** @type {{kind: string, wp: Vector3} | undefined} */
  let best;
  let bd = Infinity;
  const base = r.e.location;
  pts.forEach((/** @type {any} */ pt, /** @type {number} */ i) => {
    if (!kinds.has(pt.kind)) return;
    const wp = add(base, { x: pt.p[0], y: pt.p[1], z: pt.p[2] });
    const rad = Number(shp.points?.[i]?.radius ?? 1);
    const d = dist(wp, aim);
    if (d <= rad + slack && d < bd) { bd = d; best = { kind: pt.kind, wp }; }
  });
  return best;
}
/** その種類の使う場所があるか。 @param {PRec} r @param {string} kind */
function hasKind(r, kind) { return (SHAPES[r.key]?.points ?? []).some((/** @type {any} */ p) => p.kind === kind); }

/** 視線の上で、エンティティの中心にいちばん近い点。 @param {Player} p @param {Entity} e */
function aimPoint(p, e) {
  const eye = p.getHeadLocation();
  const dir = p.getViewDirection();
  const c = add(e.location, { x: 0, y: 1, z: 0 });
  const t = Math.max(0, dot(sub(c, eye), dir));
  return add(eye, { x: dir.x * t, y: dir.y * t, z: dir.z * t });
}

/**
 * 使う。動いたら true。
 * @param {Entity} e 小道具 @param {Player} player @param {Vector3} aim 狙った点
 */
export function useProp(e, player, aim) {
  if (!isProp(e) || !valid(e)) return false;
  setup(e);
  const r = recs.get(e.id);
  if (!r) return false;
  const pt = nearestPoint(r, aim, USE_KINDS, 1.2);
  if (!pt) return false;
  const dim = e.dimension;
  switch (pt.kind) {
    case "loot_trunk":
    case "loot_cargo": {
      if (r.open) {
        trigger(e, "nr:close");
        r.open = false;
        sound(dim, "nr.veh.door", pt.wp, { volume: 1.0, pitch: rand(0.85, 0.95) });
        return true;
      }
      trigger(e, "nr:open");
      r.open = true;
      sound(dim, "nr.veh.door", pt.wp, { volume: 1.0, pitch: rand(1.0, 1.1) });
      lootOnce(r, player, pt.kind, pt.wp, PROPS[e.typeId]?.loot);
      return true;
    }
    case "loot_glovebox":
      sound(dim, "nr.veh.door", pt.wp, { volume: 0.7, pitch: 1.3 });
      lootOnce(r, player, pt.kind, pt.wp, "glovebox");
      return true;
    case "open_doors":
      trigger(e, r.open ? "nr:close" : "nr:open");
      r.open = !r.open;
      sound(dim, "nr.world.door", pt.wp, { volume: 1.0 });
      return true;
    case "lightbar":
      r.lights = r.lights ? 0 : 1;
      trigger(e, r.lights ? "nr:lights_on" : "nr:lights_off");
      sound(dim, "nr.ui.click", pt.wp, { volume: 1.0 });
      return true;
    default:
      return false;
  }
}

/** ルートは場所ごとに一度（RESTOCK_DAYS 日で補充）。 @param {PRec} r @param {Player} player @param {string} kind @param {Vector3} wp @param {string | undefined} table */
function lootOnce(r, player, kind, wp, table) {
  if (!table) return false;
  /** @type {Record<string, number>} */
  let st = {};
  try { const s = r.e.getDynamicProperty(LOOT_DP); if (typeof s === "string") st = JSON.parse(s) ?? {}; } catch { st = {}; }
  const day = safe("prop-day", () => world.getDay()) ?? 0;
  if (st[kind] !== undefined && day - st[kind] < RESTOCK_DAYS) {
    if (isPlayer(player)) safe("prop-empty", () => player.onScreenDisplay.setActionBar({ rawtext: [{ translate: "nr.prop.empty" }] }));
    return false;
  }
  const out = add(wp, { x: 0, y: -0.3, z: 0 });
  dropLoot(r.e.dimension, out, [table], { scatter: 0.35 });
  particle(r.e.dimension, "loot_glint", out, undefined, PRIO.LOW);
  st[kind] = day;
  try { r.e.setDynamicProperty(LOOT_DP, JSON.stringify(st)); } catch { /* 無効 */ }
  return true;
}

world.afterEvents.playerInteractWithBlock.subscribe((ev) => {
  if (!ev.isFirstEvent || ev.block.typeId !== BARRIER) return;
  const e = propAt(ev.block.dimension, ev.block.location);
  if (!e) return;
  const aim = add(ev.block.location, ev.faceLocation);
  safe("prop-use", () => useProp(e, ev.player, aim));
});
world.afterEvents.playerInteractWithEntity.subscribe((ev) => {
  const e = ev.target;
  if (!isProp(e)) return;
  safe("prop-use", () => useProp(e, ev.player, aimPoint(ev.player, e)));
});

// ---------------------------------------------------------------------------
//  叩く・撃つ（窓が割れる・アラーム）
// ---------------------------------------------------------------------------
const GLASS = new Set(["breakable_glass"]);
/**
 * @param {Entity} e 小道具 @param {Entity | undefined} by 叩いた・撃った人 @param {Vector3} aim 当たった点
 * @param {{alarmChance?: number}} [o]
 */
export function hitProp(e, by, aim, o = {}) {
  if (!isProp(e) || !valid(e)) return;
  setup(e);
  const r = recs.get(e.id);
  if (!r) return;
  const dim = e.dimension;
  if (!r.glass && nearestPoint(r, aim, GLASS, 0.7)) {
    r.glass = true;
    trigger(e, "nr:smash_glass");
    sound(dim, "nr.fx.glass_break", aim, { volume: 1.2, pitch: rand(0.9, 1.1) });
    particle(dim, "impact_dust", aim, undefined, PRIO.NORMAL);
  }
  if (hasKind(r, "car_alarm") && chance(o.alarmChance ?? ALARM_CHANCE)) startAlarm(e, by);
}

/** アラームを鳴らす（鳴り終わってから ALARM_REARM tick は鳴らない）。 @param {Entity} e @param {Entity} [by] */
export function startAlarm(e, by) {
  const r = valid(e) ? recs.get(e.id) : undefined;
  const t = now();
  if (!r || alarms.has(r.id) || t < r.alarmRearm) return false;
  trigger(e, "nr:alarm_on");
  r.alarmStart = t;
  r.alarmUntil = t + ALARM_TICKS;
  r.alarmRearm = r.alarmUntil + ALARM_REARM;
  r.alarmNext = t;
  r.alarmBy = by;
  alarms.add(r.id);
  alarmTick(r, t);
  return true;
}
/** @param {PRec} r @param {number} t */
function alarmTick(r, t) {
  const e = r.e, dim = e.dimension;
  const at = add(e.location, { x: 0, y: 1, z: 0 });
  sound(dim, "nr.trap.alarm", at, { volume: 3.0 });
  particle(dim, "alarm_flash", at, undefined, PRIO.LOW);
  if ((t - r.alarmStart) % 40 < 20) {
    emit("noise", { pos: at, radius: ALARM_RADIUS, dim, source: "car_alarm",
      player: r.alarmBy && isPlayer(r.alarmBy) ? r.alarmBy : undefined, ticks: Math.max(0, r.alarmUntil - t),
      spawnViral: ALARM.effect?.spawn_viral });
  }
  r.alarmNext = t + 20;
}
system.runInterval(() => {
  if (!alarms.size) return;
  const t = now();
  for (const id of [...alarms]) {
    const r = recs.get(id);
    if (!r || !valid(r.e)) { alarms.delete(id); continue; }
    if (t >= r.alarmUntil) { trigger(r.e, "nr:alarm_off"); alarms.delete(id); continue; }
    if (t >= r.alarmNext) safe("prop-alarm", () => alarmTick(r, t));
  }
}, 10);

world.afterEvents.entityHitBlock.subscribe((ev) => {
  const b = ev.hitBlock;
  if (b.typeId !== BARRIER) return;
  const e = propAt(b.dimension, b.location);
  if (!e) return;
  const aim = add(add(b.location, { x: 0.5, y: 0.5, z: 0.5 }), FACE[String(ev.blockFace)] ?? { x: 0, y: 0, z: 0 });
  safe("prop-hit", () => hitProp(e, ev.damagingEntity, aim));
});
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const e = ev.hitEntity;
  if (!isProp(e)) return;
  const by = ev.damagingEntity;
  const aim = isPlayer(by) ? aimPoint(/** @type {Player} */ (by), e) : add(e.location, { x: 0, y: 1, z: 0 });
  safe("prop-hit", () => hitProp(e, by, aim));
});
world.afterEvents.projectileHitBlock.subscribe((ev) => {
  const hit = safe("prop-proj-block", () => ev.getBlockHit());
  if (!hit || hit.block.typeId !== BARRIER) return;
  const e = propAt(ev.dimension, hit.block.location);
  if (e) safe("prop-hit", () => hitProp(e, ev.source, ev.location));
});
world.afterEvents.projectileHitEntity.subscribe((ev) => {
  const hit = safe("prop-proj-entity", () => ev.getEntityHit());
  const e = hit?.entity;
  if (e && isProp(e)) safe("prop-hit", () => hitProp(e, ev.source, ev.location));
});

// 屋根に飛び乗った（重い着地）・近くの爆発でもアラームが鳴ることがある
on("noise", (/** @type {any} */ d) => {
  if (!d || !d.dim || !d.pos) return;
  if (d.source === "landing") {
    const e = propAt(d.dim, { x: d.pos.x, y: d.pos.y - 0.5, z: d.pos.z });
    if (e) safe("prop-land", () => hitProp(e, d.player, d.pos));
  } else if (d.source === "explosion") {
    /** @type {Entity[]} */
    let near = [];
    try { near = d.dim.getEntities({ location: d.pos, maxDistance: 8, families: ["nr_prop"] }); } catch { near = []; }
    for (const e of near) {
      const r = recs.get(e.id);
      if (r && hasKind(r, "car_alarm") && chance(ALARM_CHANCE)) startAlarm(e, d.player);
    }
  }
});
