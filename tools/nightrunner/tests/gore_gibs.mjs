// ゴア: ちぎれた部位 nr:gib と「物理」（DESIGN §5）— 出る・飛ぶ・跳ねる・転がって止まる・血の尾と血だまり・
// 上限と寿命・蹴れる・崩れる・爆風で飛ぶ・ゴア 0 では出ない
import { test, tick, spawnZombie, spawnPlayer, expect, prop, used, hit, entities, DATA, mc } from "nr-test";
import { shapesReady, defaults, setGore } from "./gore_util.js";
import { spawnGib, spawnChunks, gibCount, clearGibs, gibList, kick, GIB, GIB_ID, GENERIC_ZTYPE } from "../scripts/gore/gibs.js";
import { detonate } from "../scripts/gore/death.js";
import { set as setSetting } from "../scripts/core/settings.js";
import { on, EV } from "../scripts/core/bus.js";

let gibEvents = 0;
on(EV.GIB, () => { gibEvents++; });

/** @type {any} */
let P;
async function setup(key = "office_worker") {
  await shapesReady;
  defaults();
  clearGibs();
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  const z = spawnZombie(key, { x: 0.5, y: 64, z: 3.5 });
  await tick(1);
  return { p: P, z };
}
/** @param {any} e */
const speed = (e) => { const v = e.getVelocity(); return Math.hypot(v.x, v.y, v.z); };

test("gibs: spawnGib はプロパティを入れて打たれた向きへ飛ばす", async () => {
  const { z } = await setup();
  const ev0 = gibEvents;
  const g = spawnGib(z, "arm_r", { x: 1, y: 0, z: 0 }, 1);
  expect(g).toBeDefined();
  expect(g.typeId).toBe(GIB_ID);
  expect(gibEvents).toBe(ev0 + 1);
  expect(prop(g, "nr:part")).toBe(GIB.arm_r);
  expect(prop(g, "nr:ztype")).toBe(DATA.zombies.ZTYPE.office_worker);
  const spin = prop(g, "nr:spin");
  expect(spin >= 1 && spin <= 7).toBe(true);
  expect(prop(g, "nr:bleed")).toBe(1);
  expect([0, 1, 2, 3]).toContain(prop(g, "nr:rest"));
  expect([0, 1]).toContain(prop(g, "nr:side"));
  const x0 = g.location.x;
  await tick(4);
  expect(g.location.x - x0).toBeGreaterThan(0.3);     // +X へ飛んだ
  expect(gibCount()).toBe(1);
  // 汎用（腸・脳・肉片…）は ztype を指定できる
  const c = spawnGib(undefined, GIB.guts, { x: 0, y: 1, z: 0 }, 0.5, { at: { x: 2.5, y: 65, z: 2.5 }, dim: mc.world.getDimension("overworld"), ztype: GENERIC_ZTYPE });
  expect(prop(c, "nr:part")).toBe(GIB.guts);
  expect(prop(c, "nr:ztype")).toBe(63);
});

test("gibs: 着地で跳ね、転がりが摩擦で止まると nr:spin = 0・血だまり。動く間は血の尾", async () => {
  const { z } = await setup();
  const g = spawnGib(z, "leg_l", { x: 0, y: 1, z: -1 }, 1.8, { at: { x: 0.5, y: 70, z: 6.5 } });
  let bounced = false;
  let prevVy = 0;
  let falling = false;
  for (let i = 0; i < 160; i++) {
    await tick(1);
    const vy = g.getVelocity().y;
    if (vy < -0.15) falling = true;
    if (falling && prevVy < -0.05 && vy > 0.02) bounced = true;
    prevVy = vy;
  }
  const u = used();
  expect(bounced).toBe(true);
  expect(u.sounds["nr.gore.gib_land"]).toBeGreaterThan(0);
  expect(u.particles["nr:blood_trail"]).toBeGreaterThan(0);
  expect(speed(g)).toBeLessThan(0.05);
  expect(prop(g, "nr:spin")).toBe(0);
  expect(u.particles["nr:blood_pool"]).toBeGreaterThan(0);
  expect(g.location.y).toBeLessThan(64.6);              // 地面の上で止まった
});

test("gibs: 上限 max_gibs を超えると古い順に消える", async () => {
  const { z } = await setup();
  expect(setSetting("max_gibs", 4)).toBe(true);
  const made = [];
  for (let i = 0; i < 6; i++) made.push(spawnGib(z, GIB.chunk, { x: i - 3, y: 1, z: 1 }, 0.5));
  expect(gibCount()).toBe(4);
  expect(made[0].isValid).toBe(false);
  expect(made[1].isValid).toBe(false);
  expect(made[5].isValid).toBe(true);
  expect(gibList().map((e) => e.id)).toContain(made[5].id);
  // 上限を下げると今あるものも減る
  setSetting("max_gibs", 0);
  expect(gibCount()).toBe(0);
  expect(spawnGib(z, GIB.chunk, { x: 0, y: 1, z: 1 }, 0.5)).toBeUndefined();
  defaults();
  await tick(1);
  expect(entities(GIB_ID).filter((e) => e.isValid).length).toBe(0);   // 上限 0 で全部消えた
});

test("gibs: 寿命 gib_lifetime_s で消える", async () => {
  const { z } = await setup();
  expect(setSetting("gib_lifetime_s", 10)).toBe(true);
  const g = spawnGib(z, "head", { x: 0, y: 0, z: 1 }, 0.6);
  await tick(150);
  expect(g.isValid).toBe(true);
  await tick(75);                                        // 止まった gib の寿命は 20 tick ごとに見る
  expect(g.isValid).toBe(false);
  expect(gibCount()).toBe(0);
  defaults();
});

test("gibs: プレイヤーが殴ると蹴り飛ばせる（止まっていても）", async () => {
  const { p, z } = await setup();
  const g = spawnGib(z, "head", { x: 0, y: 0, z: -1 }, 0.3, { at: { x: 0.5, y: 64.3, z: 2.0 } });
  await tick(80);
  expect(prop(g, "nr:spin")).toBe(0);
  const z0 = g.location.z;
  await hit(p, g, { point: g.location });
  await tick(3);
  expect(g.location.z - z0).toBeGreaterThan(0.4);       // 視線の向き（+Z）へ飛んだ
  expect(prop(g, "nr:spin")).toBeGreaterThan(0);
  expect(used().sounds["nr.gore.squish"]).toBeGreaterThan(0);
  // kick() は gib 以外には効かない
  expect(kick(z, { x: 1, y: 0, z: 0 })).toBe(false);
});

test("gibs: 爆風は止まった gib も吹き飛ばす", async () => {
  const { z } = await setup();
  const g = spawnGib(z, GIB.chunk, { x: 0, y: 0, z: 1 }, 0.2, { at: { x: 3.5, y: 64.3, z: 3.5 } });
  await tick(80);
  const y0 = g.location.y;
  detonate(mc.world.getDimension("overworld"), { x: 3.0, y: 64.2, z: 3.5 }, { radius: 3, dmg: 0, exclude: z.id });
  await tick(3);
  expect(g.location.y - y0).toBeGreaterThan(0.2);
});

test("gibs: 炭になる種類（crumble）の gib は数秒で灰になって崩れる", async () => {
  const { z } = await setup("charred");
  const g = spawnGib(z, "arm_l", { x: 1, y: 0, z: 0 }, 0.8);
  expect(prop(g, "nr:bleed")).toBe(0);
  await tick(85);
  expect(g.isValid).toBe(false);
  expect(used().particles["nr:char_flakes"]).toBeGreaterThan(0);
  expect(used().particles["nr:blood_trail"]).toBe(0);
});

test("gibs: ゴア 0 では肉片を出さない・ゴアで数が比例する", async () => {
  const { z } = await setup();
  setGore(0);
  expect(spawnChunks(z, 10, { x: 0, y: 1, z: 0 })).toBe(0);
  setGore(50);
  expect(spawnChunks(z, 10, { x: 0, y: 1, z: 0 })).toBe(5);
  defaults();
  clearGibs();
  expect(spawnChunks(z, 10, { x: 0, y: 1, z: 0 })).toBe(10);
  clearGibs();
});
