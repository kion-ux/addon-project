// 戦闘: 近接武器（combat/melee.js）— 武器の表のダメージ・振りのモーションと連携・連打の弱まり・スタミナ・
// 切断と頭の破壊・溜め攻撃（長押し → 離す）・gib を蹴る・壁を叩く
import { test, tick, spawnZombie, expect, prop, used, hit, startUse, releaseUse, held, mc } from "nr-test";
import { arena, rec, hitsOn, hitBlock, heldDamage } from "./combat_util.js";
import { spawnGib, clearGibs } from "../scripts/gore/gibs.js";
import { hpOf } from "../scripts/core/hp.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";

const MACHETE = WEAPON_BY_ID["nr:w_machete"];

test("近接: マチェーテの一撃は武器の表のダメージ・斬撃（バニラの minecraft:damage ではない）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete" });
  await hit(p, z, { part: "torso" });
  await tick(1);
  const r = hitsOn(z)[0];
  expect(r).toBeDefined();
  expect(r.source).toBe("melee");
  expect(r.dtype).toBe("slash");
  expect(r.hit.weapon.id).toBe("nr:w_machete");
  expect(r.damage).toBeGreaterThanOrEqual(MACHETE.damage * 0.99);     // 8（会心なら 1.8 倍）。バニラの 4 ではない
  expect(hpOf(z)).toBeCloseTo(24 - r.damage, 3);
  expect(hitsOn(z).length).toBe(1);                                   // entityHurt と entityHitEntity で二重にならない
});

test("近接: 振りのモーション・風切り音・振りの軌跡・スタミナ（stamina_cost）・音の知らせ", async () => {
  const { p, z } = await arena({ item: "nr:w_machete" });
  await hit(p, z, { part: "torso" });
  await tick(1);
  expect(used().anims["animation.nr.p.slash_1h_1"]).toBe(1);
  expect(used().sounds["nr.w.swing_light"]).toBeGreaterThan(0);
  expect(used().particles["nr:swing_trail"]).toBeGreaterThan(0);
  expect(rec.stamina.length).toBe(1);
  expect(rec.stamina[0].amount).toBe(MACHETE.stamina_cost);
  expect(rec.stamina[0].player.id).toBe(p.id);
  expect(rec.noise.some((n) => n.source === "melee")).toBe(true);
});

test("近接: 振りは combo_window の間で 1 → 2 → 3 と回り、間が空くと 1 に戻る", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 500 });
  await hit(p, z, { part: "torso" });
  await tick(11);
  await hit(p, z, { part: "torso" });
  await tick(11);
  await hit(p, z, { part: "torso" });
  await tick(60);
  await hit(p, z, { part: "torso" });
  await tick(1);
  const a = used().anims;
  expect(a["animation.nr.p.slash_1h_1"]).toBe(2);
  expect(a["animation.nr.p.slash_1h_2"]).toBe(1);
  expect(a["animation.nr.p.slash_1h_3"]).toBe(1);
});

test("近接: 攻撃の速さより速い連打は弱い（0.2 + 0.8 × 溜まり²）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete" });
  const z2 = spawnZombie("office_worker", { x: 1.6, y: 64, z: 2.6 });
  await tick(1);
  await hit(p, z, { part: "torso" });
  await tick(2);
  await hit(p, z2, { part: "torso" });
  await tick(1);
  const a = hitsOn(z)[0], b = hitsOn(z2)[0];
  expect(a.damage).toBeGreaterThan(b.damage * 2);
  expect(b.damage).toBeLessThan(MACHETE.damage * 0.5);
});

test("近接: 消防斧（両手の刃・重い）で腕を斬ると腕が落ちる", async () => {
  const { p, z } = await arena({ item: "nr:w_fire_axe" });
  await hit(p, z, { part: "arm_r" });
  await tick(2);
  expect(prop(z, "nr:arm_r")).toBeOneOf(["cut_lower", "cut_upper"]);
  expect(hitsOn(z)[0].weight).toBe("heavy");
});

test("近接: パイプレンチ（打撃）で頭を殴ると頭が割れる・潰れる", async () => {
  const { p, z } = await arena({ item: "nr:w_pipe_wrench" });
  await hit(p, z, { part: "head" });
  await tick(12);
  await hit(p, z, { part: "head" });
  await tick(2);
  expect(hitsOn(z)[0].dtype).toBe("blunt");
  expect(prop(z, "nr:head")).toBeOneOf(["cracked", "crushed"]);
});

test("溜め攻撃: 長押しで溜めて離すと重い一撃（heavy のモーション・スタミナ × 1.8・耐久 2）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 200 });
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  expect(used().anims["animation.nr.p.slash_1h_heavy"]).toBe(1);
  expect(rec.stamina.some((s) => s.reason === "heavy" && Math.abs(s.amount - MACHETE.stamina_cost * 1.8) < 0.11)).toBe(true);
  await tick(6);
  const r = hitsOn(z)[0];
  expect(r).toBeDefined();
  expect(r.hit.heavy).toBe(true);
  expect(r.source).toBe("melee");
  expect(heldDamage(p)).toBe(2);
});

test("溜め攻撃: 溜めが足りないと何も起きない", async () => {
  const { p, z } = await arena({ item: "nr:w_machete" });
  await startUse(p);
  await tick(3);
  await releaseUse(p, undefined, 3);
  await tick(8);
  expect(hitsOn(z).length).toBe(0);
  expect(used().anims["animation.nr.p.slash_1h_heavy"]).toBe(0);
});

test("溜め攻撃: 両手の刃の横振りは前の 2 体にまとめて当たる", async () => {
  const { p, z } = await arena({ item: "nr:w_fire_axe", hp: 300 });
  const z2 = spawnZombie("office_worker", { x: 1.5, y: 64, z: 2.3 });
  await tick(1);
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  await tick(8);
  expect(hitsOn(z).length).toBe(1);
  expect(hitsOn(z2).length).toBe(1);
});

test("gib: 重い武器で殴った gib は強く蹴り飛ばされる", async () => {
  const { p } = await arena({ item: "nr:w_fire_axe", zombie: null });
  clearGibs();
  const g = spawnGib(undefined, "chunk", { x: 0, y: 0, z: 1 }, 0.01, { at: { x: 0.5, y: 64.2, z: 2.2 }, dim: mc.world.getDimension("overworld") });
  await tick(40);
  const z0 = g.location.z;
  await hit(p, g, { point: g.location });
  expect(g.getVelocity().z).toBeGreaterThan(0.9);          // gibs.js だけ（素手）なら 0.75
  await tick(3);
  expect(g.location.z - z0).toBeGreaterThan(0.6);
});

test("壁を叩く: 金属音・火花・耐久 per_wall", async () => {
  const { p } = await arena({ item: "nr:w_machete", zombie: null });
  const pos = { x: 0, y: 65, z: 2 };
  mc.world.getDimension("overworld").setBlockType(pos, "minecraft:stone");
  await hitBlock(p, pos);
  await tick(1);
  expect(used().sounds["nr.w.hit_metal"]).toBeGreaterThan(0);
  expect(used().particles["nr:hit_spark"]).toBeGreaterThan(0);
  expect(heldDamage(p)).toBe(2);
  expect(held(p).typeId).toBe("nr:w_machete");
});
