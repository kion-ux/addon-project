// 乗り物（world/vehicles.js）と小道具（world/props.js）のテスト。
//
// 偽物（test_fakes/server.js）にはまだ EntityRideableComponent が無いので、このファイルの中だけ
// 「乗り物の部品」と「実機のエンジンがすること（使うと乗せる・座席に連れて動く・乗り手の入力で走る）」を
// 小さく足して確かめる（偽物へ正式に足すときは test_fakes/server.js と selftest へ移す。tests/README.md §6）。
import {
  test, tick, spawn, spawnPlayer, spawnZombie, interact, press, give, expect, prop, used, entities, blockAt, setTime,
  fill, mc, S, DATA,
} from "nr-test";
import { vehicleState, damageVehicle, vehicleOfRider } from "../scripts/world/vehicles.js";
import { propRecord, hitProp } from "../scripts/world/props.js";
import { hpOf, maxHpOf } from "../scripts/core/hp.js";
import { on } from "../scripts/core/bus.js";

// ---------------------------------------------------------------------------
//  乗り物の部品（このファイルの中だけ）
// ---------------------------------------------------------------------------
/** @type {Map<string, any[]>} 乗り物の ID → 乗っている人（座席の順） */
const RIDES = new Map();
function ridersList(v) {
  const l = (RIDES.get(v.id) ?? []).filter((e) => e._valid);
  RIDES.set(v.id, l);
  return l;
}
class Rideable {
  constructor(v) { this._v = v; }
  get typeId() { return "minecraft:rideable"; }
  get isValid() { return this._v._valid; }
  get entity() { return this._v; }
  get seatCount() { return this._v._comps()["minecraft:rideable"]?.seat_count ?? 1; }
  get controllingSeat() { return this._v._comps()["minecraft:rideable"]?.controlling_seat ?? 0; }
  getRiders() { return [...ridersList(this._v)]; }
  addRider(e) {
    const l = ridersList(this._v);
    if (l.includes(e) || l.length >= this.seatCount) return false;
    for (const other of RIDES.values()) if (other.includes(e)) return false;
    l.push(e);
    return true;
  }
  ejectRider(e) { const l = ridersList(this._v); const i = l.indexOf(e); if (i >= 0) l.splice(i, 1); }
  ejectRiders() { RIDES.set(this._v.id, []); }
}
const baseGetComponent = mc.Entity.prototype.getComponent;
mc.Entity.prototype.getComponent = function (id) {
  const n = String(id).includes(":") ? String(id) : `minecraft:${id}`;
  if (n === "minecraft:rideable" && this._comps()["minecraft:rideable"]) return new Rideable(this);
  return baseGetComponent.call(this, id);
};

/** 座席の位置へ乗り手を連れて行く（実機は rideable が毎 tick やる）。 */
function seatFollow(v) {
  for (const r of ridersList(v)) r._loc = { x: v._loc.x, y: v._loc.y + 0.6, z: v._loc.z };
}
/** 使う → 実機の rideable と同じく空いた座席へ乗せる。interact が取り消されなかったか を返す。 */
async function mount(p, v) {
  const ok = await interact(p, v);
  if (ok) new Rideable(v).addRider(p);
  seatFollow(v);
  await tick(2);
  return ok;
}
/** 乗り手の入力で走る代わり: 向いている方へ mps（m/s）で ticks tick 動かす（負なら後退）。 */
async function drive(v, mps, ticks) {
  for (let i = 0; i < ticks; i++) {
    if (!v._valid) break;
    const a = (v._rot.y * Math.PI) / 180;
    v._loc = { x: v._loc.x - Math.sin(a) * mps / 20, y: v._loc.y, z: v._loc.z + Math.cos(a) * mps / 20 };
    seatFollow(v);
    await tick(1);
  }
}
const noises = [];
on("noise", (d) => noises.push(d));
const SEVERED = new Set(["cut_lower", "cut_upper", "severed", "crushed", "halved", "gutted"]);

// ---------------------------------------------------------------------------
//  BP の形（vanilla の horse / camel と同じ部品）
// ---------------------------------------------------------------------------
test("乗り物の BP: rideable（先頭が運転席・プレイヤーだけ）・input_ground_controlled・落下無効・nr:blood / nr:lights", async () => {
  const vs = DATA.vehicles?.VEHICLES ?? [];
  expect(vs.length).toBe(4);
  for (const v of vs) {
    const def = S.DEFS.entities[v.id];
    expect(!!def).toBe(true);
    const c = def.components;
    const rd = c["minecraft:rideable"];
    expect(rd.seat_count).toBe(v.seat_count);
    expect(rd.controlling_seat).toBe(0);
    expect(rd.family_types).toEqual(["player"]);
    const seats = Array.isArray(rd.seats) ? rd.seats : [rd.seats];
    expect(seats.length).toBe(v.seat_count);
    seats.forEach((s, i) => { expect(s.min_rider_count ?? 0).toBe(i); });
    expect(!!c["minecraft:input_ground_controlled"]).toBe(true);
    expect(!!c["minecraft:movement.basic"]).toBe(true);
    expect(c["minecraft:movement"].value).toBe(v.speed);
    expect(c["minecraft:health"].max).toBe(v.health);
    expect(c["minecraft:pushable"].is_pushable).toBe(false);
    expect(!!c["minecraft:is_stackable"]).toBe(false);
    expect(c["minecraft:damage_sensor"].triggers.some((t) => t.cause === "fall" && t.deals_damage === "no")).toBe(true);
    expect(c["minecraft:type_family"].family).toContain("nr_vehicle");
    expect(Object.keys(def.props).sort()).toEqual(["nr:blood", "nr:lights"]);
  }
  // 速さの順: バイクがいちばん速い
  const bike = vs.find((v) => v.key === "dirt_bike");
  expect(Math.max(...vs.map((v) => v.speed))).toBe(bike.speed);
});

// ---------------------------------------------------------------------------
//  乗る・エンジン・クラクション・灯り
// ---------------------------------------------------------------------------
test("使うで乗る: 運転席に着くとエンジンがかかり、案内が出て、ジャンプでクラクション", async () => {
  setTime(18000);
  const p = spawnPlayer({ x: 0, y: 64, z: -3 });
  const v = spawn("nr:veh_beater_sedan", { x: 0.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  const before = S.log.actionbars;
  expect(await mount(p, v)).toBe(true);
  expect(vehicleState(v).driver).toBe(p.id);
  expect(vehicleOfRider(p)).toBe(v);
  expect(used().sounds["nr.veh.start"]).toBeGreaterThan(0);
  expect(used().sounds["nr.veh.door"]).toBeGreaterThan(0);
  expect(S.log.actionbars).toBeGreaterThan(before);
  await tick(45);
  expect(used().sounds["nr.veh.engine_idle"]).toBeGreaterThan(0);
  expect(prop(v, "lights")).toBe(1);                       // 夜は前照灯
  const n0 = noises.length;
  await press(p, "Jump");
  await tick(1);
  expect(used().sounds["nr.veh.horn"]).toBe(1);
  expect(noises.slice(n0).some((d) => d.source === "horn" && d.radius >= 30)).toBe(true);
  await press(p, "Jump", false);
  // 降りる（実機はしゃがむ）→ エンジンが止まり、灯りが消える
  new Rideable(v).ejectRider(p);
  await tick(21);
  expect(vehicleState(v).driver).toBe(undefined);
  expect(used().sounds["nr.veh.stop"]).toBeGreaterThan(0);
  expect(prop(v, "lights")).toBe(0);
});

test("走ると走行のエンジン音と、感染者を呼ぶ音（noise）", async () => {
  setTime(1000);
  const p = spawnPlayer({ x: 20, y: 64, z: 0 });
  const v = spawn("nr:veh_dirt_bike", { x: 20.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  await mount(p, v);
  const n0 = noises.length;
  await drive(v, 15, 50);
  expect(vehicleState(v).speed).toBeCloseTo(15, 1);
  expect(used().sounds["nr.veh.engine_drive"]).toBeGreaterThan(0);
  expect(noises.slice(n0).some((d) => d.source === "vehicle" && d.player === p)).toBe(true);
  expect(prop(v, "lights")).toBe(0);                       // 昼は消えたまま
});

// ---------------------------------------------------------------------------
//  轢く
// ---------------------------------------------------------------------------
test("轢く: バギーで速く突っ込むと手足がちぎれて吹き飛び、gib が飛び、車が血まみれになる", async () => {
  const p = spawnPlayer({ x: 40, y: 64, z: -3 });
  const v = spawn("nr:veh_survivor_buggy", { x: 40.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  await mount(p, v);
  const zs = [spawnZombie("office_worker", { x: 40.5, y: 64, z: 7 }), spawnZombie("office_worker", { x: 41.0, y: 64, z: 8.5 }),
    spawnZombie("office_worker", { x: 40.0, y: 64, z: 10 })];
  await tick(1);
  await drive(v, 14, 16);
  await tick(3);
  const st = vehicleState(v);
  expect(st.hits).toBeGreaterThanOrEqual(3);
  expect(st.kills).toBeGreaterThanOrEqual(2);
  const u = used();
  const cuts = Object.entries(u.props).filter(([k, n]) => n > 0 && /^nr:(arm|leg)_[rl]=cut_(upper|lower)$/.test(k));
  expect(cuts.length).toBeGreaterThan(0);                  // 手足がちぎれた
  expect(u.spawned["nr:gib"] ?? 0).toBeGreaterThan(0);
  expect(u.sounds["nr.gore.smash"] ?? 0).toBeGreaterThan(0);
  expect(prop(v, "blood")).toBeGreaterThanOrEqual(2);
  for (const z of zs) {
    if (!z._valid) continue;                               // 弾け飛んだ
    expect(z._loc.z).toBeGreaterThan(12);                  // 前へ吹き飛んだ
  }
  expect(st.hp).toBeLessThan(st.maxHp);                    // 車も少し傷む
});

test("轢く: 遅いと当たらない（ゾンビは無傷・血も付かない）", async () => {
  const p = spawnPlayer({ x: 60, y: 64, z: -3 });
  const v = spawn("nr:veh_beater_sedan", { x: 60.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  await mount(p, v);
  const z = spawnZombie("office_worker", { x: 60.5, y: 64, z: 4 });
  await tick(1);
  const hp0 = hpOf(z);
  await drive(v, 2.5, 50);
  expect(hpOf(z)).toBe(hp0);
  expect(prop(z, "leg_r")).toBe("intact");
  expect(vehicleState(v).hits).toBe(0);
  expect(prop(v, "blood")).toBe(0);
});

test("轢く: 後退でも当たる（弱い）・誰も乗っていない車は轢かない", async () => {
  const p = spawnPlayer({ x: 80, y: 64, z: 10 });
  const v = spawn("nr:veh_pickup_truck", { x: 80.5, y: 64, z: 0.5 }, { yaw: 0 });
  const z = spawnZombie("office_worker", { x: 80.5, y: 64, z: -12 });
  await tick(1);
  await drive(v, -10, 10);                                  // 誰も乗っていない（後ろの端は z -7.4 まで）
  expect(hpOf(z)).toBe(maxHpOf(z));
  await mount(p, v);
  await drive(v, -10, 14);
  expect(hpOf(z)).toBeLessThan(maxHpOf(z));
});

// ---------------------------------------------------------------------------
//  傷む・壊れる・直す
// ---------------------------------------------------------------------------
test("壁にぶつかる（速さが一気に落ち、鼻先に壁）と衝突の音と車のダメージ。壁が無ければ（止まっただけ）何もない", async () => {
  const p = spawnPlayer({ x: 100, y: 64, z: -3 });
  const v = spawn("nr:veh_beater_sedan", { x: 100.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  await mount(p, v);
  await drive(v, 13, 8);
  await drive(v, 0, 4);                                     // 壁は無い（位置の更新が遅れた・急に止めた）
  expect(used().sounds["nr.veh.crash"] ?? 0).toBe(0);
  expect(vehicleState(v).hp).toBe(vehicleState(v).maxHp);
  await drive(v, 13, 8);
  const front = DATA.vehicles.VEHICLE_BY_ID["nr:veh_beater_sedan"].shape.front;
  const wz = Math.floor(v._loc.z + front + 0.6);
  fill({ x: 98, y: 64, z: wz }, { x: 103, y: 66, z: wz }, "minecraft:stone");
  await drive(v, 0, 4);
  expect(used().sounds["nr.veh.crash"]).toBeGreaterThan(0);
  const st = vehicleState(v);
  expect(st.hp).toBeLessThan(st.maxHp);
});

test("乗っている人へのゾンビの攻撃は車が肩代わりする（セダンは 8 割）", async () => {
  const p = spawnPlayer({ x: 120, y: 64, z: -3 });
  const v = spawn("nr:veh_beater_sedan", { x: 120.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  await mount(p, v);
  const z = spawnZombie("office_worker", { x: 121.5, y: 64, z: 0.5 });
  await tick(1);
  const hc = p.getComponent("minecraft:health");
  const before = hc.currentValue;
  p.applyDamage(5, { cause: mc.EntityDamageCause.entityAttack, damagingEntity: z });
  await tick(2);
  expect(hc.currentValue).toBeCloseTo(before - 5 + 4, 3);
  const st = vehicleState(v);
  expect(st.hp).toBeLessThan(st.maxHp);
  expect(used().sounds["nr.fx.metal_clang"]).toBeGreaterThan(0);
});

test("壊れると爆発（近くのゾンビに blast）、焼けた残骸の小道具とくず鉄が残り、乗り手は降ろされる", async () => {
  const p = spawnPlayer({ x: 140, y: 64, z: -3 });
  const v = spawn("nr:veh_survivor_buggy", { x: 140.5, y: 64, z: 0.5 }, { yaw: 90 });
  await tick(1);
  await mount(p, v);
  const z = spawnZombie("office_worker", { x: 143.5, y: 64, z: 0.5 });
  await tick(1);
  const hp0 = hpOf(z);
  expect(damageVehicle(v, 9999, { attacker: p })).toBe(true);
  await tick(3);
  expect(v._valid).toBe(false);
  expect(used().sounds["nr.fx.explosion"]).toBeGreaterThan(0);
  expect(!z._valid || hpOf(z) < hp0 || prop(z, "state") === "dead").toBe(true);
  const wrecks = entities("nr:prop_burnt_car");
  expect(wrecks.length).toBe(1);
  const rec = propRecord(wrecks[0]);
  expect(rec.rot).toBe("90");                              // 車の向きのまま
  expect(rec.cells.length).toBeGreaterThan(0);             // 残骸のバリア
  expect(entities("minecraft:item").length).toBeGreaterThan(0);
  expect(ridersList(v).length).toBe(0);
  expect(vehicleOfRider(p)).toBe(undefined);
});

test("くず鉄を持って使うと直る（満タンなら普通に乗る）", async () => {
  const p = spawnPlayer({ x: 160, y: 64, z: -3 });
  const v = spawn("nr:veh_pickup_truck", { x: 160.5, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  damageVehicle(v, 100);
  const hp0 = vehicleState(v).hp;
  give(p, new mc.ItemStack("nr:scrap", 3), 0);
  const ok = await interact(p, v);
  expect(ok).toBe(false);                                  // 乗らずに直す
  await tick(2);
  expect(vehicleState(v).hp).toBeGreaterThan(hp0);
  expect(p.getComponent("minecraft:inventory").container.getItem(0).amount).toBe(2);
  expect(used().sounds["nr.ui.repair"]).toBe(1);
});

// ---------------------------------------------------------------------------
//  小道具のバリア（prop_shapes.js の yaw ごとのマス）
// ---------------------------------------------------------------------------
for (const rot of [0, 90, 180, 270]) {
  test(`小道具のバリア: yaw ${rot} 付近で出すと ${rot} に揃い、cells にバリア、消すと空気に戻る`, async () => {
    const shp = DATA.prop_shapes.PROP_SHAPES.sedan_wreck;
    const R = shp.rot[String(rot)];
    const yaw = rot === 270 ? -86 : rot === 180 ? -177 : rot + 4;
    const e = spawn("nr:prop_sedan_wreck", { x: 200.3 + rot / 10, y: 64, z: -5.2 }, { yaw });
    await tick(2);
    const rec = propRecord(e);
    expect(rec.rot).toBe(String(rot));
    expect(e.location.x).toBeCloseTo(rec.b[0] + R.spawn[0], 4);
    expect(e.location.z).toBeCloseTo(rec.b[2] + R.spawn[1], 4);
    expect(e.getRotation().y).toBeCloseTo(R.yaw, 4);
    expect(rec.cells.length).toBe(R.cells.length);
    for (const [dx, dy, dz] of R.cells) {
      expect(blockAt({ x: rec.b[0] + dx, y: rec.b[1] + dy, z: rec.b[2] + dz })).toBe("minecraft:barrier");
    }
    e.remove();
    await tick(4);
    for (const [dx, dy, dz] of R.cells) {
      expect(blockAt({ x: rec.b[0] + dx, y: rec.b[1] + dy, z: rec.b[2] + dz })).toBe("minecraft:air");
    }
  });
}

test("小道具のバリア: 立っているプレイヤーのマスと、空気でないマスには置かない", async () => {
  const shp = DATA.prop_shapes.PROP_SHAPES.city_bus;
  const R = shp.rot["0"];
  // 先に置いて B を知る
  const probe = spawn("nr:prop_city_bus", { x: 300, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  const b = propRecord(probe).b;
  probe.remove();
  await tick(4);
  const [cx, cy, cz] = R.cells[0];
  const [px, , pz] = R.cells[R.cells.length - 1];
  mc.world.getDimension("overworld").setBlockType({ x: b[0] + cx, y: b[1] + cy, z: b[2] + cz }, "minecraft:stone");
  spawnPlayer({ x: b[0] + px + 0.5, y: 64, z: b[2] + pz + 0.5 });
  const e = spawn("nr:prop_city_bus", { x: 300, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(1);
  const rec = propRecord(e);
  expect(rec.cells.length).toBeLessThan(R.cells.length);
  expect(blockAt({ x: b[0] + cx, y: b[1] + cy, z: b[2] + cz })).toBe("minecraft:stone");
  e.remove();
  await tick(4);
  expect(blockAt({ x: b[0] + cx, y: b[1] + cy, z: b[2] + cz })).toBe("minecraft:stone");   // 自分のでないマスは消さない
});

// ---------------------------------------------------------------------------
//  使う・叩く
// ---------------------------------------------------------------------------
/** その種類の使う場所に一番近いバリアのマス。 */
function cellNear(e, kind) {
  const shp = DATA.prop_shapes.PROP_SHAPES[e.typeId.slice(8)];
  const rec = propRecord(e);
  const pt = shp.rot[rec.rot].points.find((q) => q.kind === kind);
  const w = { x: e.location.x + pt.p[0], y: e.location.y + pt.p[1], z: e.location.z + pt.p[2] };
  let best, bd = Infinity;
  for (const [x, y, z] of rec.cells) {
    const d = Math.hypot(x + 0.5 - w.x, y + 1 - w.y, z + 0.5 - w.z);
    if (d < bd) { bd = d; best = { x, y, z }; }
  }
  return { cell: best, point: w };
}

test("トランク: 後ろのバリアを使うと開いてルートが出る、閉じて開け直しても 2 度は出ない", async () => {
  const p = spawnPlayer({ x: 400, y: 64, z: -6 });
  const e = spawn("nr:prop_sedan_wreck", { x: 400, y: 64, z: 0.5 }, { yaw: 180 });
  await tick(2);
  const { cell } = cellNear(e, "loot_trunk");
  await interact(p, cell);
  await tick(1);
  expect(prop(e, "open")).toBe(1);
  const items = entities("minecraft:item").length;
  expect(items).toBeGreaterThan(0);
  expect(used().sounds["nr.veh.door"]).toBeGreaterThan(0);
  await interact(p, cell);
  await tick(1);
  expect(prop(e, "open")).toBe(0);
  const bars = S.log.actionbars;
  await interact(p, cell);
  await tick(1);
  expect(prop(e, "open")).toBe(1);
  expect(entities("minecraft:item").length).toBe(items);   // 補充はまだ
  expect(S.log.actionbars).toBeGreaterThan(bars);          // 「もう何も無い」
});

test("グローブボックス: 運転席側を使うと glovebox の表から出る", async () => {
  const p = spawnPlayer({ x: 420, y: 64, z: -6 });
  const e = spawn("nr:prop_sedan_wreck", { x: 420, y: 64, z: 0.5 }, { yaw: 0 });
  await tick(2);
  const { cell } = cellNear(e, "loot_glovebox");
  await interact(p, cell);
  await tick(1);
  expect(entities("minecraft:item").length).toBeGreaterThan(0);
  expect(prop(e, "open")).toBe(0);                          // トランクは開かない
});

test("叩くと窓が割れ、アラームが鳴り続けて感染者を呼び、時間で止まる", async () => {
  const p = spawnPlayer({ x: 440, y: 64, z: -6 });
  const e = spawn("nr:prop_sedan_wreck", { x: 440, y: 64, z: 0.5 }, { yaw: 90 });
  await tick(2);
  const { point } = cellNear(e, "breakable_glass");
  const n0 = noises.length;
  hitProp(e, p, point, { alarmChance: 1 });
  await tick(1);
  expect(prop(e, "glass")).toBe(1);
  expect(prop(e, "alarm")).toBe(1);
  expect(used().sounds["nr.fx.glass_break"]).toBe(1);
  await tick(60);
  expect(used().sounds["nr.trap.alarm"]).toBeGreaterThanOrEqual(3);
  const alarm = noises.slice(n0).filter((d) => d.source === "car_alarm");
  expect(alarm.length).toBeGreaterThanOrEqual(2);
  expect(alarm[0].radius).toBe(DATA.traps.TRAP_BY_KEY.car_alarm.effect.lure_radius);
  await tick(DATA.traps.TRAP_BY_KEY.car_alarm.effect.lure_ticks);
  expect(prop(e, "alarm")).toBe(0);
});
