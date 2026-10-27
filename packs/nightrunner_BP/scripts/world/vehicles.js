// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 乗れる乗り物（nr:veh_*。gen_nr_vehicles・data/vehicles.js）
//
//  * 乗る・降りる・座席は BP の minecraft:rideable（使うで乗る、しゃがむで降りる。先頭の座席が運転席）、
//    走るのは minecraft:input_ground_controlled（乗り手の入力）。このモジュールは乗っている人を毎 tick 見て:
//    エンジンの始動・停止・アイドリング／走行の音（2 秒のループを鳴らし直す）、夜の前照灯（nr:lights）、
//    ジャンプでクラクション（noise）、エンジンの音で感染者を呼ぶ（バス "noise"）。運転中は 10 tick ごとに
//    バス "vehicle" {player, vehicle, key, hp, maxHp, speed（m/s）, blood}（HUD 向け）。
//  * 轢く: 運転中に roadkill.min_mps より速いと、車の鼻先（data の shape.front・half_w。後退なら後ろ）の
//    この 1 tick に通った範囲にいるゾンビ（死体も）へ applyHit（dtype blunt・weight heavy・source "vehicle"・
//    dir = 進む向き・parts = 脚・胴（速いと腕・頭も）・outcome = 速さと roadkill.sever / head / plow で手足が
//    ちぎれる・頭が潰れる・棘の鋤なら胴が裂ける）→ 速さに比例して吹き飛ばす。gib は跳ね飛ばす。
//    当たるたびに nr:blood（0..3。車のテクスチャが血まみれになる）を上げ、車も少し傷む。
//  * 傷み: 壁にぶつかる（速さが一気に落ちる）と衝突の音・揺れ・車と乗り手のダメージ。乗っている人への
//    ゾンビの攻撃は shield の割合だけ車が肩代わりする（乗り手の体力を戻して車が受ける）。
//    体力（BP の minecraft:health）が尽きる・死ぬと爆発（death.detonate = 周りのゾンビへ blast の applyHit）、
//    焼けた残骸の小道具（data の wreck）とくず鉄を残して消える。くず鉄・修理キットを持って使うと直る。
//  * 偽物（tools/nightrunner/test_fakes）に EntityRideableComponent が無い間も動くように、乗り手は
//    getRiders が無ければ「誰も乗っていない」として扱う。
// ===========================================================================
import { world, system, EntityDamageCause, InputButton, ButtonState, GameMode } from "@minecraft/server";
import { VEHICLE_BY_ID } from "../data/vehicles.js";
import { applyHit } from "../gore/gore.js";
import { detonate, dropLoot, isCorpse } from "../gore/death.js";
import { GIB_ID, kick } from "../gore/gibs.js";
import { zombieSpec } from "../core/hp.js";
import { emit } from "../core/bus.js";
import { gore } from "../core/settings.js";
import { particle, sound, shake, PRIO } from "../core/fx.js";
import {
  valid, now, add, sub, scale, dot, norm, clamp, clamp01, lenXZ, yawForward, yawOf, toLocal, toWorld, isZombie,
  isPlayer, getProp, setProp, safe, despawn, warnOnce, rand,
} from "../core/util.js";

/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Dimension} Dimension */

/** applyHit の source（gore.js の SOURCES に無い間は melee として扱われる。crit は false で渡す）。 */
export const VEHICLE_SOURCE = "vehicle";
const PREFIX = "nr:veh_";
/** @type {Record<string, any>} */
const SPECS = /** @type {any} */ (VEHICLE_BY_ID) ?? {};
const VEHICLE_IDS = Object.keys(SPECS);
const DIMENSIONS = ["overworld", "nether", "the_end"];
const BLOOD_DP = "nr:veh_blood";
/** nr:blood の段階になる血の点（轢いた数 + ちぎれた部位 + 仕留めた数） */
const BLOOD_STEPS = [0, 1, 5, 12];
const BLOOD_FADE_TICKS = 2400;       // 最後に轢いてから 2 分ごとに半分になる（水に入ると落ちる）
const CLOSED_KINDS = new Set(["sedan", "taxi", "police", "pickup", "ambulance", "box_truck", "army_truck",
  "garbage_truck", "bus"]);
/** 直す材料（使うと直る。満タンなら普通に乗る） */
const REPAIR = /** @type {Record<string, number>} */ ({ "nr:repair_kit": 0.5, "nr:scrap": 0.12, "nr:duct_tape": 0.08 });
const SCRAP_LOOT = [["nr:scrap", 2, 5, 1], ["nr:duct_tape", 1, 2, 0.4], ["nr:battery", 1, 1, 0.3]];

/**
 * @typedef {{e: Entity, id: string, spec: any, last?: Vector3, lastTick: number, speed: number, fwd: number,
 *   hist: number[], fhist: number[], yaw: number, yawRate: number, driver?: string, riders: string[], engineAt: number,
 *   noiseAt: number, hornAt: number, crashAt: number, skidAt: number, bloodPts: number, bloodAt: number,
 *   blood: number, lights: number, cool: Map<string, number>, dead: boolean, hits: number, kills: number}} VRec
 */
/** @type {Map<string, VRec>} */
const recs = new Map();
/** @type {Map<string, string>} 乗っている人の ID → 乗り物の ID */
const riderOf = new Map();

// ---------------------------------------------------------------------------
//  引き出し
// ---------------------------------------------------------------------------
/** nr:veh_* か。 @param {Entity | undefined} e */
export function isVehicle(e) {
  try { return !!e && typeof e.typeId === "string" && e.typeId.startsWith(PREFIX); } catch { return false; }
}
/** data/vehicles.js の行（エンティティか ID）。 @param {Entity | string | undefined} e @returns {any} */
export function vehicleSpec(e) {
  const id = typeof e === "string" ? e : e?.typeId;
  return id ? SPECS[id] : undefined;
}
/** @param {Entity} e */
function rideableOf(e) {
  try {
    const rc = e.getComponent("minecraft:rideable");
    return rc && typeof rc.getRiders === "function" ? rc : undefined;
  } catch { return undefined; }
}
/** 乗っている全員（座席の順。先頭が運転席）。 @param {Entity} e @returns {Entity[]} */
export function ridersOf(e) {
  const rc = valid(e) ? rideableOf(e) : undefined;
  if (!rc) return [];
  try { return rc.getRiders().filter((x) => valid(x)); } catch { return []; }
}
/** 運転している人（先頭の座席のプレイヤー）。 @param {Entity} e @returns {Player | undefined} */
export function driverOf(e) {
  const r = ridersOf(e)[0];
  return r && isPlayer(r) ? /** @type {Player} */ (r) : undefined;
}
/** その人が乗っている乗り物。 @param {Entity} p @returns {Entity | undefined} */
export function vehicleOfRider(p) {
  if (!valid(p)) return undefined;
  const id = riderOf.get(p.id);
  const r = id ? recs.get(id) : undefined;
  return r && !r.dead && valid(r.e) ? r.e : undefined;
}
/**
 * いまの様子（テスト・HUD 用）。
 * @param {Entity} e
 * @returns {{speed: number, fwd: number, driver?: string, riders: string[], blood: number, bloodPts: number, hp: number, maxHp: number, hits: number, kills: number} | undefined}
 */
export function vehicleState(e) {
  const r = valid(e) ? track(e) : undefined;
  if (!r) return undefined;
  const hp = healthOf(e);
  return { speed: r.speed, fwd: r.fwd, driver: r.driver, riders: [...r.riders], blood: r.blood, bloodPts: r.bloodPts,
    hp: hp.cur, maxHp: hp.max, hits: r.hits, kills: r.kills };
}
/** @param {Entity} e */
function healthOf(e) {
  try {
    const hc = e.getComponent("minecraft:health");
    if (hc) return { hc, cur: hc.currentValue, max: hc.effectiveMax };
  } catch { /* 無効 */ }
  return { hc: undefined, cur: 0, max: 0 };
}

/** @param {Entity} e @returns {VRec | undefined} */
function track(e) {
  if (!isVehicle(e) || !valid(e)) return undefined;
  let r = recs.get(e.id);
  if (r) { r.e = e; return r; }
  const spec = vehicleSpec(e);
  if (!spec) { warnOnce(`veh:${e.typeId}`, "data/vehicles.js に無い乗り物", e.typeId); return undefined; }
  const blood = clamp(Math.round(Number(getProp(e, "nr:blood", 0)) || 0), 0, 3);
  let saved = 0;
  try { saved = Number(e.getDynamicProperty(BLOOD_DP)) || 0; } catch { saved = 0; }
  r = {
    e, id: e.id, spec, last: undefined, lastTick: -10, speed: 0, fwd: 0, hist: [0, 0, 0, 0], fhist: [0, 0, 0, 0],
    yaw: yawOf(e), yawRate: 0,
    driver: undefined, riders: [], engineAt: 0, noiseAt: 0, hornAt: -100, crashAt: -100, skidAt: -100,
    bloodPts: Math.max(saved, BLOOD_STEPS[blood]), bloodAt: now(), blood, lights: Number(getProp(e, "nr:lights", 0)) || 0,
    cool: new Map(), dead: false, hits: 0, kills: 0,
  };
  recs.set(e.id, r);
  return r;
}
/** @param {string} id */
function forget(id) {
  const r = recs.get(id);
  recs.delete(id);
  if (!r) return;
  for (const pid of r.riders) if (riderOf.get(pid) === id) riderOf.delete(pid);
}

// ---------------------------------------------------------------------------
//  見つける（出現・読み込み・ワールドの読み込み）
// ---------------------------------------------------------------------------
world.afterEvents.entitySpawn.subscribe((ev) => { if (isVehicle(ev.entity)) safe("veh-spawn", () => track(ev.entity)); });
world.afterEvents.entityLoad.subscribe((ev) => { if (isVehicle(ev.entity)) safe("veh-load", () => track(ev.entity)); });
world.afterEvents.entityRemove.subscribe((ev) => { if (ev.typeId.startsWith(PREFIX)) forget(ev.removedEntityId); });
world.afterEvents.playerLeave.subscribe((ev) => { riderOf.delete(ev.playerId); });
world.afterEvents.worldLoad.subscribe(() => {
  for (const d of DIMENSIONS) {
    safe("veh-scan", () => {
      for (const e of world.getDimension(d).getEntities({ families: ["nr_drivable"] })) track(e);
    });
  }
});

// ---------------------------------------------------------------------------
//  毎 tick
// ---------------------------------------------------------------------------
system.runInterval(() => {
  if (!recs.size) return;
  const t = now();
  for (const [id, r] of recs) {
    if (r.dead || !valid(r.e)) { forget(id); continue; }
    safe("veh-step", () => step(r, t));
  }
}, 1);

/** @param {VRec} r @param {number} t */
function step(r, t) {
  const e = r.e;
  const loc = e.location;
  const yaw = yawOf(e);
  const fwdDir = yawForward(yaw);
  const riders = ridersOf(e);
  updateRiders(r, riders, t);
  // 速さ（前の tick との差。テレポートのような飛びは数えない）
  let speed = 0, fs = 0, moved = 0;
  if (r.last && r.lastTick === t - 1) {
    const d = sub(loc, r.last);
    const h = lenXZ(d);
    if (h < 3) { speed = h * 20; fs = dot(d, fwdDir) * 20; moved = Math.abs(dot(d, fwdDir)); }
  }
  const dyaw = ((((yaw - r.yaw) % 360) + 540) % 360) - 180;
  r.yawRate = dyaw * 20;
  r.yaw = yaw;
  r.last = loc;
  r.lastTick = t;
  r.speed = speed;
  r.fwd = fs;
  r.hist.push(speed);
  r.fhist.push(fs);
  if (r.hist.length > 4) { r.hist.shift(); r.fhist.shift(); }
  const d0 = riders[0];
  const driver = d0 && isPlayer(d0) ? /** @type {Player} */ (d0) : undefined;
  if (driver) {
    if (Math.abs(fs) >= Number(r.spec.roadkill?.min_mps ?? 4)) roadkill(r, driver, fs, moved, fwdDir, yaw, t);
    crashCheck(r, driver, t);
    engine(r, driver, speed, fs, fwdDir, t);
  }
  if (r.bloodPts > 0 && t - r.bloodAt >= BLOOD_FADE_TICKS) {
    r.bloodPts = Math.floor(r.bloodPts / 2);
    r.bloodAt = t;
    syncBlood(r);
  }
  if (driver && t % 10 === 0) {
    const hp = healthOf(e);
    emit("vehicle", { player: driver, vehicle: e, key: r.spec.key, hp: hp.cur, maxHp: hp.max, speed, blood: r.blood });
  }
  if (t % 20 === 0) {
    updateLights(r);
    damageFx(r);
    if (r.bloodPts > 0 && safe("veh-water", () => e.isInWater)) { r.bloodPts = 0; syncBlood(r); }
  }
}

// ---------------------------------------------------------------------------
//  乗る・降りる・エンジン・灯り・クラクション
// ---------------------------------------------------------------------------
/** @param {VRec} r @param {Entity[]} riders @param {number} t */
function updateRiders(r, riders, t) {
  const ids = riders.map((x) => x.id);
  const d0 = riders[0];
  const driver = d0 && isPlayer(d0) ? /** @type {Player} */ (d0) : undefined;
  const closed = CLOSED_KINDS.has(String(r.spec.kind));
  for (const p of riders) {
    if (r.riders.includes(p.id)) continue;
    riderOf.set(p.id, r.id);
    if (closed) sound(r.e.dimension, "nr.veh.door", p.location, { volume: 0.9, pitch: rand(0.95, 1.05) });
    if (isPlayer(p)) {
      const key = p === driver ? "nr.veh.hint.driver" : "nr.veh.hint.passenger";
      safe("veh-hint", () => /** @type {Player} */ (p).onScreenDisplay.setActionBar({ rawtext: [{ translate: key }] }));
    }
  }
  for (const id of r.riders) {
    if (ids.includes(id)) continue;
    if (riderOf.get(id) === r.id) riderOf.delete(id);
    if (closed) sound(r.e.dimension, "nr.veh.door", r.e.location, { volume: 0.9, pitch: rand(0.95, 1.05) });
  }
  r.riders = ids;
  const did = driver?.id;
  if (did !== r.driver) {
    r.driver = did;
    if (driver) {
      sound(r.e.dimension, "nr.veh.start", add(r.e.location, { x: 0, y: 0.8, z: 0 }), { volume: 1.2 });
      r.engineAt = t + 40;           // 始動の音（2.2 秒）の後からアイドリング
      r.noiseAt = t + 20;
    } else {
      sound(r.e.dimension, "nr.veh.stop", add(r.e.location, { x: 0, y: 0.8, z: 0 }), { volume: 1.0 });
    }
    updateLights(r);
  }
}

/** エンジンの音（2 秒のループを鳴らし直す。動いていれば少し前に置いて、置き去りにしない）と感染者を呼ぶ音。
 * @param {VRec} r @param {Player} driver @param {number} speed @param {number} fs @param {Vector3} fwdDir @param {number} t */
function engine(r, driver, speed, fs, fwdDir, t) {
  const e = r.e, dim = e.dimension, sp = r.spec;
  const moving = speed > 2.5;
  if (t >= r.engineAt) {
    const id = moving ? "nr.veh.engine_drive" : "nr.veh.engine_idle";
    const k = clamp01(speed / Math.max(8, Number(sp.max_mps) || 14));
    const base = sp.kind === "dirt_bike" ? 1.25 : sp.weight === "heavy" ? 0.9 : 1.0;
    const at = add(add(e.location, scale(fwdDir, (fs / 20) * 10)), { x: 0, y: 0.8, z: 0 });
    sound(dim, id, at, { volume: moving ? 1.1 : 0.7, pitch: clamp((0.85 + 0.45 * k) * base, 0.5, 2) });
    r.engineAt = t + (moving ? 20 : 40);
  }
  if (t >= r.noiseAt) {
    emit("noise", { pos: e.location, radius: 10 + speed * 0.8, dim, source: "vehicle", player: driver });
    r.noiseAt = t + 40;
  }
  if (speed > 7 && t % 3 === 0) {
    const sh = sp.shape ?? {};
    particle(dim, "dust_trail", toWorld(e.location, r.yaw, [0, 0.15, -(Number(sh.back) || 1.5)]), undefined, PRIO.LOW);
  }
  // 速いまま急に向きを変える・急ブレーキでタイヤが鳴る
  const prev = r.hist[r.hist.length - 2] ?? speed;
  if (((speed > 7 && Math.abs(r.yawRate) > 160) || (prev > 8 && prev - speed > 3 && speed > 2)) && t - r.skidAt > 30) {
    r.skidAt = t;
    sound(dim, "nr.veh.skid", e.location, { volume: 1.0, pitch: rand(0.9, 1.1) });
  }
}

/** 夜に運転していれば前照灯。 @param {VRec} r */
function updateLights(r) {
  let want = 0;
  if (r.driver && r.spec.lights_on_night !== false) {
    const tod = safe("veh-time", () => world.getTimeOfDay()) ?? 6000;
    want = tod >= 12500 && tod < 23500 ? 1 : 0;
  }
  if (want !== r.lights && setProp(r.e, "nr:lights", want)) r.lights = want;
}

world.afterEvents.playerButtonInput.subscribe((ev) => {
  const p = ev.player;
  const veh = vehicleOfRider(p);
  if (!veh) return;
  const r = recs.get(veh.id);
  if (!r || r.driver !== p.id) return;
  const t = now();
  if (t - r.hornAt < 12) return;
  r.hornAt = t;
  const sp = r.spec;
  sound(veh.dimension, "nr.veh.horn", add(veh.location, { x: 0, y: 1, z: 0 }),
    { volume: 2.5, pitch: sp.kind === "dirt_bike" ? 1.3 : sp.weight === "heavy" ? 0.85 : 1.0 });
  emit("noise", { pos: veh.location, radius: 36, dim: veh.dimension, source: "horn", player: p });
}, { buttons: [InputButton.Jump], state: ButtonState.Pressed });

// ---------------------------------------------------------------------------
//  轢く
// ---------------------------------------------------------------------------
/**
 * 鼻先（後退なら後ろ）のこの 1 tick に通った範囲のゾンビ（死体も）と gib。
 * @param {VRec} r @param {Player} driver @param {number} fs 前向きの速さ（m/s、後退は負）@param {number} moved この tick に進んだ距離
 * @param {Vector3} fwdDir @param {number} yaw @param {number} t
 */
function roadkill(r, driver, fs, moved, fwdDir, yaw, t) {
  const sh = r.spec.shape ?? {};
  const back = fs < 0;
  const v = Math.abs(fs);
  const dir = back ? scale(fwdDir, -1) : fwdDir;
  const edge = Number(back ? sh.back : sh.front) || 2;
  const halfW = (Number(sh.half_w) || 1) + 0.35;
  const height = Number(sh.height) || 1.6;
  const e = r.e, loc = e.location, dim = e.dimension;
  const reach = moved + 0.9;
  const center = add(loc, scale(dir, edge - reach / 2 + 0.3));
  const radius = Math.hypot(halfW, reach / 2 + 0.6) + 0.5;
  /** @type {Entity[]} */
  let near = [];
  try { near = dim.getEntities({ location: center, maxDistance: radius, families: ["nr_zombie"] }); } catch { near = []; }
  for (const z of near) {
    if (!valid(z) || (r.cool.get(z.id) ?? -1) > t) continue;
    const ruf = toLocal(loc, yaw, z.location);
    const f = back ? -ruf[2] : ruf[2];
    if (Math.abs(ruf[0]) > halfW) continue;
    if (f > edge + 0.55 || f < edge - reach - 0.4) continue;
    if (ruf[1] > height || ruf[1] < -1.6) continue;
    r.cool.set(z.id, t + 12);
    safe("veh-hit", () => hitZombie(r, driver, z, v, dir, back));
  }
  /** @type {Entity[]} */
  let gibs = [];
  try { gibs = dim.getEntities({ location: center, maxDistance: radius, type: GIB_ID }); } catch { gibs = []; }
  for (const g of gibs) {
    if ((r.cool.get(g.id) ?? -1) > t) continue;
    r.cool.set(g.id, t + 8);
    kick(g, dir, clamp(v / 9, 0.4, 1.6));
  }
  if (r.cool.size > 64) for (const [k, until] of r.cool) if (until <= t) r.cool.delete(k);
}

/**
 * 1 体を轢く。速さ s（0..1 = min_mps..full_mps）で、脚 → 腕 → 頭の順に効く部位とちぎれる確率が増える。
 * @param {VRec} r @param {Player} driver @param {Entity} z @param {number} v 速さ（m/s）@param {Vector3} dir 進む向き @param {boolean} back
 */
function hitZombie(r, driver, z, v, dir, back) {
  const sp = r.spec, rk = sp.roadkill ?? {};
  const s = clamp01((v - Number(rk.min_mps)) / Math.max(0.5, Number(rk.full_mps) - Number(rk.min_mps)));
  const k = back ? 0.6 : 1.0;
  const corpse = isCorpse(z);
  const zs = zombieSpec(z);
  const mass = clamp((Number(zs?.hp) || 30) / 30, 0.6, 4);
  const sev = Number(rk.sever) * k;
  const damage = Number(rk.damage) * v * (0.55 + 0.45 * s) * k;
  const power = clamp(Number(rk.power) * (0.45 + 1.4 * s) * k, 0.3, 2.4);
  /** @type {Record<string, [string, number]>} */
  const outcome = {
    leg: [s > 0.55 ? "cut_upper" : "cut_lower", clamp01(sev * (0.15 + 0.85 * s) * s * 1.2)],
    arm: ["cut_upper", clamp01(sev * Math.pow(s, 1.5) * 0.75)],
    head: ["crushed", clamp01(Number(rk.head) * s * s * k)],
    torso: rk.plow && !back ? ["halved", clamp01(0.6 * Math.pow(s, 1.4))] : ["gutted", clamp01(0.3 * sev * s * s)],
  };
  const parts = ["leg_r", "leg_l", "torso"];
  if (s > 0.25 || corpse) parts.push("arm_r", "arm_l");
  if (s > 0.5 || corpse) parts.push("head");
  const hitDir = norm(add(dir, { x: 0, y: 0.25 + 0.25 * s, z: 0 }));
  const point = add(z.location, { x: 0, y: 0.9, z: 0 });
  const res = applyHit(z, {
    attacker: driver, dtype: "blunt", weight: sp.weight === "light" ? "medium" : "heavy", damage, power,
    source: VEHICLE_SOURCE, dir: hitDir, point, parts, outcome, knockdown: true, crit: false, corpse,
    gorePower: clamp(0.45 + 0.6 * s + (rk.plow ? 0.2 : 0), 0, 1.3),
  });
  r.hits++;
  if (res?.killed) r.kills++;
  // 吹き飛ばす（gore.js の押し返しより強く。重いゾンビほど飛ばない）
  if (valid(z)) {
    try {
      if (res?.killed || corpse || isCorpse(z)) {
        const kf = (0.25 + 0.055 * v) * Number(rk.power) * k / Math.sqrt(mass);
        z.applyImpulse({ x: dir.x * kf, y: (0.25 + 0.02 * v) * k / Math.sqrt(mass), z: dir.z * kf });
      } else {
        const kb = (0.35 + 0.06 * v) * Number(rk.power) * k / Math.sqrt(mass);
        z.applyKnockback({ x: dir.x * kb, z: dir.z * kb }, Math.min(0.8, (0.2 + 0.03 * v) / Math.sqrt(mass)));
      }
    } catch { /* 物理が無い・消えた */ }
  }
  const dim = r.e.dimension;
  sound(dim, s > 0.45 ? "nr.gore.smash" : "nr.gore.blunt_flesh", point, { volume: 1.1 + s, pitch: rand(0.85, 1.05) });
  if (s > 0.35) sound(dim, "nr.gore.bone_crunch", point, { volume: 1.0, pitch: rand(0.9, 1.1) });
  shake(driver, 0.2 + 0.6 * s, 0.25);
  addBlood(r, 1 + (res?.severed?.length ?? 0) + (res?.killed ? 1 : 0));
  damageVehicle(r.e, Number(rk.self_damage) * (0.3 + 0.7 * s) * mass, { cause: "roadkill" });
}

/** @param {VRec} r @param {number} n */
function addBlood(r, n) {
  if (gore() <= 0.02) return;
  r.bloodPts = Math.min(99, r.bloodPts + n);
  r.bloodAt = now();
  syncBlood(r);
}
/** @param {VRec} r */
function syncBlood(r) {
  const lv = gore() <= 0.02 ? 0 : r.bloodPts >= BLOOD_STEPS[3] ? 3 : r.bloodPts >= BLOOD_STEPS[2] ? 2 : r.bloodPts >= BLOOD_STEPS[1] ? 1 : 0;
  if (lv !== r.blood && setProp(r.e, "nr:blood", lv)) r.blood = lv;
  try { r.e.setDynamicProperty(BLOOD_DP, r.bloodPts); } catch { /* 無効 */ }
}

// ---------------------------------------------------------------------------
//  ぶつかる・傷む・壊れる・直す
// ---------------------------------------------------------------------------
/**
 * 速かったのに 2 tick 続けて速さが 3 割未満で、進んでいた向きの鼻先に固いブロック（壁・バリア）がある → ぶつかった。
 * （サーバーの位置の更新が遅れただけの止まりを衝突にしない）
 * @param {VRec} r @param {Player} driver @param {number} t
 */
function crashCheck(r, driver, t) {
  const h = r.hist, f = r.fhist;
  if (h.length < 4 || t - r.crashAt < 20) return;
  const before = Math.max(h[0], h[1]);
  if (before < 7 || h[2] >= before * 0.3 || h[3] >= before * 0.3) return;
  const e = r.e, dim = e.dimension, sp = r.spec;
  const sgn = (Math.abs(f[0]) > Math.abs(f[1]) ? f[0] : f[1]) < 0 ? -1 : 1;
  const edge = Number(sgn < 0 ? sp.shape?.back : sp.shape?.front) || 2;
  if (!blockedAhead(e, scale(yawForward(r.yaw), sgn), edge + 1.2)) return;
  r.crashAt = t;
  const dv = before - h[3];
  const front = toWorld(e.location, r.yaw, [0, 0.8, edge * sgn]);
  sound(dim, "nr.veh.crash", front, { volume: clamp(0.6 + dv / 12, 0.6, 2.2), pitch: rand(0.9, 1.05) });
  particle(dim, "impact_dust", front, undefined, PRIO.NORMAL);
  particle(dim, "hit_spark", front, { dx: 0, dy: 1, dz: 0 }, PRIO.NORMAL);
  emit("noise", { pos: front, radius: 24, dim, source: "vehicle", player: driver });
  const wm = sp.weight === "heavy" ? 0.8 : sp.weight === "light" ? 1.3 : 1.0;
  for (const id of r.riders) {
    const p = world.getEntity(id);
    if (!p || !isPlayer(p)) continue;
    shake(/** @type {Player} */ (p), clamp(0.5 + dv / 10, 0.5, 2.5), 0.4);
    const hurt = (dv - 11) * 0.6 * wm * (1 - 0.5 * Number(sp.shield || 0));
    if (hurt > 0) safe("veh-crash-hurt", () => p.applyDamage(hurt, { cause: EntityDamageCause.flyIntoWall }));
  }
  if (dv > 6) damageVehicle(e, (dv - 6) * 2.2 * wm, { attacker: driver, cause: "crash" });
}

/** 進む向きの reach ブロック以内に固いブロックがあるか（膝と胸の高さの 2 本のレイ）。
 * @param {Entity} e @param {Vector3} dir @param {number} reach */
function blockedAhead(e, dir, reach) {
  for (const y of [0.45, 1.05]) {
    const hit = safe("veh-ray", () => e.dimension.getBlockFromRay(add(e.location, { x: 0, y, z: 0 }), dir,
      { maxDistance: reach, includeLiquidBlocks: false, includePassableBlocks: false }));
    if (hit) return true;
  }
  return false;
}

/**
 * 乗り物に傷（体力を減らす。尽きたら壊れる）。
 * @param {Entity} e @param {number} amount @param {{attacker?: Entity, cause?: string}} [o] @returns {boolean}
 */
export function damageVehicle(e, amount, o = {}) {
  if (!valid(e) || !(amount > 0)) return false;
  const r = track(e);
  if (!r || r.dead) return false;
  const hp = healthOf(e);
  if (!hp.hc) return false;
  const nv = hp.cur - amount;
  if (nv <= 0.5) { destroyVehicle(e, o.attacker); return true; }
  try { hp.hc.setCurrentValue(nv); } catch { /* 無効 */ }
  return true;
}

/** 体力が少ないと煙、さらに少ないと火。 @param {VRec} r */
function damageFx(r) {
  const hp = healthOf(r.e);
  if (!hp.max || hp.cur / hp.max >= 0.35) return;
  const sm = r.spec.shape?.smoke ?? [0, 1, 0];
  const at = toWorld(r.e.location, r.yaw, [-sm[0], sm[1], -sm[2]]);
  particle(r.e.dimension, "smoke_dark", at, { size: 0.8, life: 2.5 }, PRIO.LOW);
  if (hp.cur / hp.max < 0.15) particle(r.e.dimension, "flame", at, { size: 0.7 }, PRIO.LOW);
}

/**
 * 壊す: 乗っている人を降ろし、爆発（death.detonate = 周りのゾンビへ blast の applyHit・gib と死体が飛ぶ・
 * プレイヤーへのダメージ）、焼けた残骸の小道具とくず鉄を残して消える。
 * @param {Entity} e @param {Entity} [attacker] @returns {boolean}
 */
export function destroyVehicle(e, attacker) {
  if (!valid(e) || !isVehicle(e)) return false;
  const r = track(e);
  if (!r || r.dead) return false;
  r.dead = true;
  const sp = r.spec;
  const dim = e.dimension, loc = e.location, yaw = yawOf(e);
  const riders = ridersOf(e);
  const driver = riders[0] && isPlayer(riders[0]) ? riders[0] : undefined;
  const by = attacker ?? driver;
  const rc = rideableOf(e);
  try { rc?.ejectRiders(); } catch { /* 無効 */ }
  for (const p of riders) {
    if (riderOf.get(p.id) === r.id) riderOf.delete(p.id);
    if (isPlayer(p)) safe("veh-wreck-msg", () => /** @type {Player} */ (p).onScreenDisplay.setActionBar({ rawtext: [{ translate: "nr.veh.wrecked" }] }));
  }
  const heavy = sp.weight === "heavy", light = sp.weight === "light";
  sound(dim, "nr.veh.crash", loc, { volume: 2.2, pitch: rand(0.8, 0.95) });
  detonate(dim, add(loc, { x: 0, y: 0.8, z: 0 }), {
    radius: light ? 3 : heavy ? 5 : 4.5, dmg: light ? 8 : heavy ? 16 : 14, attacker: by, exclude: e.id,
  });
  particle(dim, "fire_burst", add(loc, { x: 0, y: 1, z: 0 }), { size: light ? 1 : 2 }, PRIO.HIGH);
  emit("noise", { pos: loc, radius: 64, dim, source: "explosion", player: by && isPlayer(by) ? by : undefined });
  if (sp.wreck) {
    try {
      const w = dim.spawnEntity(`nr:prop_${sp.wreck}`, loc);
      w.setRotation({ x: 0, y: yaw });
    } catch (err) { warnOnce(`veh-wreck:${sp.wreck}`, "残骸を出せない", sp.wreck, err); }
  }
  dropLoot(dim, add(loc, { x: 0, y: 0.5, z: 0 }), SCRAP_LOOT, { scatter: light ? 0.5 : 1.0 });
  despawn(e);
  forget(r.id);
  return true;
}

world.afterEvents.entityHurt.subscribe((ev) => {
  const e = ev.hurtEntity;
  if (!isVehicle(e) || !valid(e)) return;
  const r = track(e);
  if (!r || r.dead) return;
  const at = add(e.location, { x: 0, y: 0.9, z: 0 });
  sound(e.dimension, "nr.fx.metal_clang", at, { volume: 0.9, pitch: rand(0.85, 1.1) });
  particle(e.dimension, "hit_spark", at, { dx: 0, dy: 1, dz: 0 }, PRIO.LOW);
  if (healthOf(e).cur <= 0.5) destroyVehicle(e, ev.damageSource?.damagingEntity);
}, { entityTypes: VEHICLE_IDS });

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (isVehicle(e) && valid(e)) destroyVehicle(e, ev.damageSource?.damagingEntity);
}, { entityTypes: VEHICLE_IDS });

// 乗っている人へのゾンビの攻撃を車が肩代わりする（shield の割合だけ乗り手の体力を戻し、車が受ける）
world.afterEvents.entityHurt.subscribe((ev) => {
  const p = ev.hurtEntity;
  const by = ev.damageSource?.damagingEntity;
  if (!by || !isZombie(by) || !isPlayer(p)) return;
  const veh = vehicleOfRider(p);
  if (!veh) return;
  const shield = Number(vehicleSpec(veh)?.shield) || 0;
  const dmg = Number(ev.damage) || 0;
  if (shield <= 0 || dmg <= 0) return;
  safe("veh-shield", () => {
    const hc = p.getComponent("minecraft:health");
    if (hc && hc.currentValue > 0) hc.setCurrentValue(Math.min(hc.effectiveMax, hc.currentValue + dmg * shield));
  });
  damageVehicle(veh, dmg * (0.6 + shield), { attacker: by, cause: "zombie" });
  sound(veh.dimension, "nr.fx.metal_clang", p.location, { volume: 0.9, pitch: rand(0.9, 1.1) });
  particle(veh.dimension, "hit_spark", add(p.location, { x: 0, y: 1, z: 0 }), { dx: 0, dy: 1, dz: 0 }, PRIO.LOW);
}, { entityTypes: ["minecraft:player"] });

// 直す: くず鉄・テープ・修理キットを持って使う（傷んでいる時だけ。満タンなら普通に乗る）
world.beforeEvents.playerInteractWithEntity.subscribe((ev) => {
  const e = ev.target;
  if (!isVehicle(e)) return;
  const id = ev.itemStack?.typeId;
  if (!id || !(id in REPAIR)) return;
  const hp = healthOf(e);
  if (!hp.max || hp.cur >= hp.max - 0.5) return;
  ev.cancel = true;
  const p = ev.player;
  system.run(() => safe("veh-repair", () => repair(e, p, id)));
});

/** @param {Entity} e @param {Player} p @param {string} itemId */
function repair(e, p, itemId) {
  if (!valid(e) || !valid(p)) return;
  const hp = healthOf(e);
  if (!hp.hc) return;
  const inv = p.getComponent("minecraft:inventory")?.container;
  const slot = p.selectedSlotIndex;
  const it = inv?.getItem(slot);
  if (!inv || !it || it.typeId !== itemId) return;
  if (p.getGameMode() !== GameMode.Creative) {
    if (it.amount > 1) { it.amount -= 1; inv.setItem(slot, it); } else inv.setItem(slot);
  }
  hp.hc.setCurrentValue(Math.min(hp.max, hp.cur + hp.max * REPAIR[itemId]));
  sound(e.dimension, "nr.ui.repair", e.location, { volume: 1.0 });
  particle(e.dimension, "hit_spark", add(e.location, { x: 0, y: 1, z: 0 }), { dx: 0, dy: 1, dz: 0 }, PRIO.LOW);
}
