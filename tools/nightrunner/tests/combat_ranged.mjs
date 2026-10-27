// 戦闘: 飛び道具（combat/ranged.js）— 銃のヒットスキャン（部位・弾倉・弾・リロード・連射・貫通・散弾）と
// 弓・クロスボウの nr:proj_*（着弾点 → 部位、entityHurt で二重に数えない）
import { test, tick, spawnZombie, expect, prop, used, use, startUse, stopUse, releaseUse, give, held, aim, partPoint, entities } from "nr-test";
import { arena, rec, hitsOn, stack, editHeld, count, heldDamage } from "./combat_util.js";
import { hitscan, magOf, isReloading } from "../scripts/combat/index.js";
import { heldInfo, eyeRay } from "../scripts/combat/common.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";
import { initHp } from "../scripts/core/hp.js";

const W = (/** @type {string} */ k) => WEAPON_BY_ID[`nr:w_${k}`];
/** @param {any} p */
const mag = (p) => held(p).getDynamicProperty("nr:mag");

test("銃: 拳銃で頭を撃つ → hitscan の一撃が頭に当たり、弾倉が 1 減る（演出・音の知らせ・weapon_state）", async () => {
  const { p, z } = await arena({ item: "nr:w_pistol", at: { x: 0.5, y: 64, z: 3.6 } });
  give(p, stack("nr:ammo_pistol", 24), 1);
  aim(p, partPoint(z, "head"));
  await use(p);
  await tick(1);
  const r = hitsOn(z)[0];
  expect(r).toBeDefined();
  expect(r.source).toBe("hitscan");
  expect(r.part).toBe("head");
  expect(r.dtype).toBe("pierce");
  expect(r.headshot || r.killed || r.part === "head").toBe(true);
  expect(mag(p)).toBe(W("pistol").mag - 1);
  expect(used().particles["nr:muzzle_flash"]).toBe(1);
  expect(used().particles["nr:bullet_tracer"]).toBeGreaterThan(0);
  expect(used().sounds["nr.w.pistol"]).toBe(1);
  expect(used().anims["animation.nr.p.pistol_fire"]).toBe(1);
  expect(rec.noise.some((n) => n.source === "gun" && n.radius === W("pistol").noise)).toBe(true);
  const st = rec.state.filter((s) => s.player.id === p.id).pop();
  expect(st.mag).toBe(W("pistol").mag - 1);
  expect(st.ammo).toBe(24);
  expect(heldDamage(p)).toBe(1);                         // 撃つたびに耐久 1
});

test("銃: 攻撃の速さより速くは撃てない（同じ tick の itemUse と itemStartUse も 1 発）", async () => {
  const { p, z } = await arena({ item: "nr:w_pistol", at: { x: 0.5, y: 64, z: 3.6 }, hp: 300 });
  aim(p, partPoint(z, "torso"));
  await use(p);
  await startUse(p);
  await tick(1);
  await use(p);
  await tick(1);
  expect(mag(p)).toBe(W("pistol").mag - 1);
  await tick(6);
  await use(p);
  expect(mag(p)).toBe(W("pistol").mag - 2);
});

test("銃: 弾倉が空なら空撃ち → 自動リロード → reload_ticks 後に満タン、持ち物の弾が減る", async () => {
  const { p } = await arena({ item: "nr:w_pistol", zombie: null });
  give(p, stack("nr:ammo_pistol", 20), 1);
  editHeld(p, (it) => it.setDynamicProperty("nr:mag", 0));
  await use(p);
  await tick(1);
  expect(used().sounds["nr.w.empty_click"]).toBe(1);
  expect(isReloading(p)).toBe(true);
  expect(used().anims["animation.nr.p.pistol_reload"]).toBe(1);
  await tick(W("pistol").reload_ticks + 2);
  expect(isReloading(p)).toBe(false);
  expect(mag(p)).toBe(W("pistol").mag);
  expect(count(p, "nr:ammo_pistol")).toBe(20 - W("pistol").mag);
});

test("銃: 弾が無いとリロードできない・持ち替えるとリロードは取りやめ", async () => {
  const { p } = await arena({ item: "nr:w_pistol", zombie: null });
  editHeld(p, (it) => it.setDynamicProperty("nr:mag", 0));
  await use(p);
  await tick(1);
  expect(isReloading(p)).toBe(false);
  give(p, stack("nr:ammo_pistol", 5), 1);
  await tick(10);
  await use(p);
  expect(isReloading(p)).toBe(true);
  p.selectedSlotIndex = 2;
  await tick(2);
  expect(isReloading(p)).toBe(false);
  expect(count(p, "nr:ammo_pistol")).toBe(5);
});

test("散弾銃: 近距離で頭を撃つと頭が弾ける（ペレットは部位ごとにまとめて 1 回の applyHit）", async () => {
  const { p, z } = await arena({ item: "nr:w_pump_shotgun", at: { x: 0.5, y: 64, z: 2.6 } });
  aim(p, partPoint(z, "head"));
  await use(p);
  await tick(2);
  const hs = hitsOn(z);
  expect(hs.length).toBeGreaterThan(0);
  expect(hs.length).toBeLessThanOrEqual(6);
  expect(new Set(hs.map((r) => r.part)).size).toBe(hs.length);
  expect(prop(z, "nr:head")).toBe("crushed");
  expect(hs.some((r) => r.crushed)).toBe(true);
  expect(used().sounds["nr.w.shotgun"]).toBe(1);
});

test("散弾: 1 本ずつレイを飛ばし、1 本ずつ部位を決める", async () => {
  const { p, z } = await arena({ item: "nr:w_pump_shotgun", at: { x: 0.5, y: 64, z: 3.0 }, hp: 400 });
  aim(p, partPoint(z, "torso"));
  const h = heldInfo(p);
  const { eye, dir } = eyeRay(p);
  const res = hitscan(p, h.w, h.item, eye, dir, h.w.spread);
  expect(res.pellets.length).toBe(W("pump_shotgun").pellets);
  const onZ = res.pellets.filter((x) => x.entity === z.id);
  expect(onZ.length).toBeGreaterThanOrEqual(4);
  for (const x of onZ) expect(["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"]).toContain(x.part);
  expect(res.tracers.length).toBe(W("pump_shotgun").pellets);
});

test("ライフル: 一列に並んだ 2 体を貫通する（overpenetrate）", async () => {
  const { p, z } = await arena({ item: "nr:w_hunting_rifle", at: { x: 0.5, y: 64, z: 4.0 }, hp: 200 });
  const z2 = spawnZombie("office_worker", { x: 0.5, y: 64, z: 6.0 });
  initHp(z2, 200);
  await tick(1);
  aim(p, partPoint(z, "torso"));
  await use(p);
  await tick(1);
  expect(hitsOn(z).length).toBe(1);
  expect(hitsOn(z2).length).toBe(1);
  expect(hitsOn(z2)[0].damage).toBeLessThan(hitsOn(z)[0].damage);
});
test("短機関銃: 押している間撃ち続け、離すと止まる", async () => {
  const { p, z } = await arena({ item: "nr:w_scrap_smg", at: { x: 0.5, y: 64, z: 4.0 }, hp: 900 });
  aim(p, partPoint(z, "torso"));
  await startUse(p);
  await tick(10);
  const fired = W("scrap_smg").mag - mag(p);
  expect(fired).toBeGreaterThanOrEqual(5);
  await stopUse(p, undefined, 10);
  await tick(10);
  expect(W("scrap_smg").mag - mag(p)).toBe(fired);
});

test("弓: 引いて放つと nr:proj_arrow が飛び、着弾点から部位が決まる（一度だけ数える・矢が減る）", async () => {
  const { p, z } = await arena({ item: "nr:w_survivor_bow", at: { x: 0.5, y: 64, z: 6.5 }, hp: 200 });
  give(p, stack("nr:survivor_arrow", 5), 1);
  aim(p, partPoint(z, "head"));
  await startUse(p);
  expect(used().anims["animation.nr.p.bow_draw"]).toBe(1);
  await tick(20);
  await releaseUse(p, undefined, 20);
  expect(count(p, "nr:survivor_arrow")).toBe(4);
  expect(used().spawned["nr:proj_arrow"]).toBe(1);
  await tick(6);
  const hs = hitsOn(z);
  expect(hs.length).toBe(1);
  expect(hs[0].source).toBe("projectile");
  expect(hs[0].part).toBe("head");
  expect(hs[0].hit.weapon.id).toBe("nr:w_survivor_bow");
  expect(hs[0].damage).toBeGreaterThan(W("survivor_bow").damage);      // 頭（headshot_mult）
  expect(used().anims["animation.nr.p.bow_release"]).toBe(1);
});

test("弓: 胴を狙えば胴、脚を狙えば脚（着弾点の部位）", async () => {
  const { p, z } = await arena({ item: "nr:w_survivor_bow", at: { x: 0.5, y: 64, z: 5.5 }, hp: 300 });
  give(p, stack("nr:survivor_arrow", 5), 1);
  for (const part of ["torso", "leg_r"]) {
    aim(p, partPoint(z, part));
    await startUse(p);
    await tick(20);
    await releaseUse(p, undefined, 20);
    await tick(6);
  }
  const parts = hitsOn(z).map((r) => r.part);
  expect(parts[0]).toBe("torso");
  expect(parts[1]).toBeOneOf(["leg_r", "leg_l"]);
});

test("クロスボウ: 空なら装填（ボルト 1 本・reload_ticks）→ 使うと撃つ", async () => {
  const { p, z } = await arena({ item: "nr:w_crossbow", at: { x: 0.5, y: 64, z: 6.5 }, hp: 200 });
  give(p, stack("nr:bolt", 3), 1);
  editHeld(p, (it) => it.setDynamicProperty("nr:mag", 0));
  aim(p, partPoint(z, "torso"));
  await use(p);
  expect(isReloading(p)).toBe(true);
  await tick(W("crossbow").reload_ticks + 2);
  expect(mag(p)).toBe(1);
  expect(count(p, "nr:bolt")).toBe(2);
  await use(p);
  expect(used().spawned["nr:proj_bolt"]).toBe(1);
  await tick(5);
  expect(hitsOn(z).length).toBe(1);
  expect(hitsOn(z)[0].source).toBe("projectile");
  expect(magOf(heldInfo(p), W("crossbow"))).toBe(0);
});

test("刺さった矢は近くを通ると拾える", async () => {
  const { p } = await arena({ item: "nr:w_survivor_bow", zombie: null });
  give(p, stack("nr:survivor_arrow", 6), 1);
  p.setRotation({ x: 30, y: 0 });
  for (let i = 0; i < 4; i++) {
    await startUse(p);
    await tick(20);
    await releaseUse(p, undefined, 20);
    await tick(15);
  }
  expect(count(p, "nr:survivor_arrow")).toBe(2);
  const arrows = entities("nr:proj_arrow");
  expect(arrows.length).toBeGreaterThan(0);
  p.teleport(arrows[0].location);
  await tick(12);
  expect(count(p, "nr:survivor_arrow")).toBeGreaterThan(2);
});
