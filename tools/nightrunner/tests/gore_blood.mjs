// ゴア: 血の演出 — 壁・地面の血痕、血だまり、断面の噴水、血の種類、近くで仕留めた時の画面の返り血、ゴアレベル
import { test, tick, spawnZombie, spawnPlayer, expect, used, prop, fill, mc } from "nr-test";
import { shapesReady, defaults, setGore, partCenter } from "./gore_util.js";
import { applyHit } from "../scripts/gore/gore.js";
import { splatWall, splatGround, pool, spray, fountain, fountainCount, fountainTicks, screenBlood } from "../scripts/gore/blood.js";
import { set as setSetting } from "../scripts/core/settings.js";

/** @type {any} */
let P;
async function setup(at = { x: 0.5, y: 64, z: 2.0 }, key = "office_worker") {
  await shapesReady;
  defaults();
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  P.teleport({ x: 0.5, y: 64, z: 0.5 });
  const z = spawnZombie(key, at);
  await tick(1);
  return { p: P, z };
}
const dim = () => mc.world.getDimension("overworld");

test("blood: 壁の向きで血痕を貼り分ける（±X → wall_x、±Z → wall_z、上向きの面 → 地面）", async () => {
  await setup();
  fill({ x: -2, y: 64, z: 6 }, { x: 3, y: 67, z: 6 }, "minecraft:stone");      // 南（+Z）の壁
  fill({ x: 5, y: 64, z: 0 }, { x: 5, y: 67, z: 5 }, "minecraft:stone");       // 東（+X）の壁
  expect(splatWall(dim(), { x: 0.5, y: 65.2, z: 3.0 }, { x: 0, y: 0, z: 1 }, 1, { reach: 4 })).toBe(true);
  expect(splatWall(dim(), { x: 3.0, y: 65.2, z: 2.5 }, { x: 1, y: 0, z: 0 }, 1, { reach: 4 })).toBe(true);
  expect(splatWall(dim(), { x: 0.5, y: 65.2, z: 2.5 }, { x: 0, y: -1, z: 0 }, 1, { reach: 4 })).toBe(true);
  expect(splatWall(dim(), { x: 0.5, y: 65.2, z: 2.5 }, { x: -1, y: 0, z: 0 }, 1, { reach: 2 })).toBe(false);   // 何も無い
  expect(splatGround(dim(), { x: 1.5, y: 65.5, z: 1.5 }, 1)).toBe(true);
  expect(pool(dim(), { x: 1.5, y: 64.2, z: 1.5 }, 1)).toBe(true);
  const u = used();
  expect(u.particles["nr:blood_splat_wall_z"]).toBe(1);
  expect(u.particles["nr:blood_splat_wall_x"]).toBe(1);
  expect(u.particles["nr:blood_splat_ground"]).toBe(2);
  expect(u.particles["nr:blood_pool"]).toBe(1);
  // 寿命（Molang の v.life）はゴアで伸びる
  expect(u.molangVars["nr:blood_pool variable.life"]).toBe(1);
  // blood_decal_mult = 0 なら貼らない
  setSetting("blood_decal_mult", 0);
  expect(splatGround(dim(), { x: 1.5, y: 65.5, z: 1.5 }, 1)).toBe(false);
  defaults();
});

test("blood: 断面の噴水はロケータを追って数秒続き、止まる（ゴア 0 では出ない）", async () => {
  const { z } = await setup();
  const n0 = fountainCount();
  expect(fountain(z, "loc_neck")).toBe(true);
  expect(fountainCount()).toBe(n0 + 1);
  await tick(30);
  expect(used().particles["nr:blood_fountain"]).toBeGreaterThan(5);
  expect(used().sounds["nr.gore.spurt"]).toBe(1);
  await tick(fountainTicks() + 5);
  expect(fountainCount()).toBe(n0);
  setGore(0);
  expect(fountain(z, "loc_neck")).toBe(false);
  defaults();
});

test("blood: 血の種類（灰の種類は血の代わりに灰、胆汁は緑の飛沫を足す）", async () => {
  await setup();
  spray(dim(), { x: 0.5, y: 65, z: 2 }, { x: 0, y: 0, z: 1 }, 1.5, { kind: "ash" });
  let u = used();
  expect(u.particles["nr:char_flakes"]).toBe(1);
  expect(u.particles["nr:blood_spray"]).toBe(0);
  spray(dim(), { x: 0.5, y: 65, z: 2 }, { x: 0, y: 0, z: 1 }, 1.5, { kind: "bile" });
  u = used();
  expect(u.particles["nr:blood_spray"]).toBe(1);
  expect(u.particles["nr:toxic_burst"]).toBe(1);
  expect(pool(dim(), { x: 1.5, y: 64.2, z: 1.5 }, 1, { kind: "ash" })).toBe(false);
});

test("blood: 近くで首を落とすと画面に返り血（遠い・ゴア < 50・設定オフでは出ない）", async () => {
  const { p, z } = await setup({ x: 0.5, y: 64, z: 1.8 });
  const c0 = used().camera;
  const r = applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", part: "head", point: partCenter(z, "head", 0), damage: 40, gorePower: 1, crit: false });
  expect(r.decap).toBe(true);
  expect(used().camera).toBeGreaterThan(c0);
  // 遠い
  const far = await setup({ x: 0.5, y: 64, z: 7.5 });
  await tick(20);
  const c1 = used().camera;
  applyHit(far.z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", part: "head", point: partCenter(far.z, "head", 0), damage: 40, gorePower: 1, crit: false });
  expect(used().camera).toBe(c1);
  // ゴア 40・設定オフ
  await tick(20);
  setGore(40);
  expect(screenBlood(p, p.getHeadLocation(), 1)).toBe(false);
  defaults();
  setSetting("screen_blood", false);
  expect(screenBlood(p, p.getHeadLocation(), 1)).toBe(false);
  defaults();
  expect(screenBlood(p, p.getHeadLocation(), 1)).toBe(true);
  expect(screenBlood(p, p.getHeadLocation(), 1)).toBe(false);       // 続けては出ない（16 tick の間）
  void prop;
});

test("blood: ゴア 100 の命中は飛沫・血痕、ゴア 0 は肉の手応えだけ", async () => {
  const { p, z } = await setup();
  fill({ x: -2, y: 64, z: 4 }, { x: 3, y: 67, z: 4 }, "minecraft:stone");
  for (let i = 0; i < 4; i++) {
    applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "light", part: "torso", point: partCenter(z, "torso", 0), damage: 1, gorePower: 0, crit: false, dir: { x: 0, y: 0, z: 1 } });
    await tick(11);
  }
  let u = used();
  expect(u.particles["nr:hit_flesh"]).toBe(4);
  expect(u.particles["nr:blood_spray"]).toBeGreaterThan(3);
  const z2 = (await setup({ x: 0.5, y: 64, z: 2.5 })).z;
  setGore(0);
  const before = used();
  applyHit(z2, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", part: "arm_r", point: partCenter(z2, "arm_r", 1), damage: 30, gorePower: 1, crit: false });
  await tick(30);
  u = used();
  expect(u.particles["nr:hit_flesh"] - before.particles["nr:hit_flesh"]).toBe(1);
  expect(u.particles["nr:blood_spray"] - before.particles["nr:blood_spray"]).toBe(0);
  expect(u.particles["nr:blood_fountain"] - before.particles["nr:blood_fountain"]).toBe(0);
  defaults();
});
