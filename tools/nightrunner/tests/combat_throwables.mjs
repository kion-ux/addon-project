// 戦闘: 投げ物（combat/throwables.js）— 火炎瓶の火の海・パイプ爆弾の爆風（距離で弱まる・手足が千切れる）・
// 爆竹の誘い・UV 発煙筒（夜の種類だけ焼く）・投げナイフ（刺さる・拾える）
import { test, tick, spawnZombie, expect, prop, used, use, give, held, aim, partPoint, fill, mc } from "nr-test";
import { arena, rec, hitsOn, stack, count } from "./combat_util.js";
import { explode, activeZones } from "../scripts/combat/index.js";
import { initHp } from "../scripts/core/hp.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";

const W = (/** @type {string} */ k) => WEAPON_BY_ID[`nr:w_${k}`];
const CUTS = /cut_lower|cut_upper|severed|crushed|halved|gutted/;

test("火炎瓶: 割れると火の海、中のゾンビは燃え（nr:burn）、火のダメージが続く。束から 1 つ減る", async () => {
  const { p, z } = await arena({ item: stack("nr:w_molotov", 3), at: { x: 0.5, y: 64, z: 3.6 }, hp: 400 });
  aim(p, { x: 0.5, y: 64.1, z: 3.0 });
  await use(p);
  await tick(1);
  expect(count(p, "nr:w_molotov")).toBe(2);
  expect(used().anims["animation.nr.p.throw_underhand"]).toBe(1);
  await tick(30);
  expect(used().sounds["nr.fx.glass_break"]).toBe(1);
  expect(used().particles["nr:ground_fire"]).toBeGreaterThan(0);
  expect(rec.fire.length).toBe(1);
  expect(activeZones().some((x) => x.kind === "fire")).toBe(true);
  const fireHits = hitsOn(z, (r) => r.dtype === "fire");
  expect(fireHits.length).toBeGreaterThan(1);
  expect(prop(z, "nr:burn")).toBeGreaterThanOrEqual(1);
});

test("パイプ爆弾: 近いゾンビは手足が千切れ、遠いゾンビは距離で弱い（falloff）", async () => {
  const { p, z } = await arena({ item: stack("nr:w_pipe_bomb", 2), at: { x: 0.5, y: 64, z: 4.0 } });
  const far = spawnZombie("office_worker", { x: 4.0, y: 64, z: 4.0 });
  initHp(far, 300);
  await tick(1);
  const dim = mc.world.getDimension("overworld");
  const n = explode(dim, { x: 0.5, y: 64.6, z: 4.6 }, W("pipe_bomb"), p);
  await tick(2);
  expect(n).toBeGreaterThanOrEqual(2);
  const a = hitsOn(z)[0], b = hitsOn(far)[0];
  expect(a.dtype).toBe("blast");
  expect(b.dtype).toBe("blast");
  expect(a.damage).toBeGreaterThan(b.damage);
  expect(a.changes.some((c) => CUTS.test(c.to))).toBe(true);
  expect(used().particles["nr:explosion"]).toBe(1);
  expect(used().sounds["nr.fx.explosion"]).toBe(1);
  expect(rec.noise.some((x) => x.source === "explosion" && x.radius >= 64)).toBe(true);
});

test("パイプ爆弾: 投げると導火線（ビープの誘い）→ fuse_ticks で爆発", async () => {
  const { p, z } = await arena({ item: stack("nr:w_pipe_bomb", 2), at: { x: 0.5, y: 64, z: 5.0 }, hp: 300 });
  aim(p, { x: 0.5, y: 64.1, z: 4.0 });
  await use(p);
  await tick(W("pipe_bomb").special.fuse_ticks - 10);
  expect(used().particles["nr:explosion"]).toBe(0);
  expect(rec.noise.some((x) => x.source === "pipe_bomb")).toBe(true);
  await tick(16);
  expect(used().particles["nr:explosion"]).toBe(1);
  expect(hitsOn(z, (r) => r.dtype === "blast").length).toBe(1);
});

test("爆竹: 落ちるとはじけ続けて音で誘う（noise を何度も・lure）", async () => {
  const { p } = await arena({ item: stack("nr:w_firecracker", 2), zombie: null });
  aim(p, { x: 0.5, y: 64.1, z: 4.0 });
  await use(p);
  await tick(60);
  expect(rec.lure.length).toBe(1);
  expect(rec.lure[0].radius).toBe(W("firecracker").special.lure_radius);
  expect(rec.noise.filter((x) => x.source === "firecracker").length).toBeGreaterThanOrEqual(3);
  expect(used().particles["nr:firecracker_pop"]).toBeGreaterThan(3);
});

test("UV 発煙筒: 夜の種類は焼かれて怯み、普通のゾンビは平気。中のプレイヤーは免疫が戻る", async () => {
  const { p, z } = await arena({ item: stack("nr:w_uv_flare", 2), zombie: "volatile", at: { x: 0.5, y: 64, z: 4.0 }, hp: 400 });
  const ow = spawnZombie("office_worker", { x: 2.0, y: 64, z: 4.0 });
  await tick(1);
  aim(p, { x: 0.5, y: 64.1, z: 3.0 });
  await use(p);
  await tick(50);
  expect(rec.uv.length).toBe(1);
  const uvHits = hitsOn(z, (r) => r.dtype === "uv" && r.damage > 0);
  expect(uvHits.length).toBeGreaterThan(0);
  expect(used().anims["animation.nr.z.uv_recoil"]).toBeGreaterThan(0);
  expect(hitsOn(ow, (r) => r.dtype === "uv").length).toBe(0);
  expect(rec.immunity.some((x) => x.player.id === p.id && x.source === "uv_flare")).toBe(true);
  expect(used().particles["nr:uv_glow"]).toBeGreaterThan(0);
});

test("投げナイフ: 刺さって狙った部位に当たる（一度だけ数える）", async () => {
  const { p, z } = await arena({ item: stack("nr:w_throwing_knives", 4), at: { x: 0.5, y: 64, z: 3.6 }, hp: 200 });
  aim(p, partPoint(z, "head"));
  await use(p);
  await tick(6);
  const hs = hitsOn(z);
  expect(hs.length).toBe(1);
  expect(hs[0].source).toBe("projectile");
  expect(hs[0].part).toBe("head");
  expect(hs[0].hit.weapon.id).toBe("nr:w_throwing_knives");
  expect(count(p, "nr:w_throwing_knives")).toBe(3);
});

test("投げナイフ: 壁に刺さったナイフは近くを通ると拾える", async () => {
  const { p } = await arena({ item: stack("nr:w_throwing_knives", 3), zombie: null });
  fill({ x: -2, y: 64, z: 5 }, { x: 3, y: 67, z: 5 }, "minecraft:stone");
  for (let i = 0; i < 3; i++) {
    aim(p, { x: 0.5, y: 65.5, z: 5 });
    await use(p);
    await tick(14);
  }
  expect(count(p, "nr:w_throwing_knives")).toBe(0);
  p.teleport({ x: 0.5, y: 64, z: 4.0 });
  await tick(12);
  expect(count(p, "nr:w_throwing_knives")).toBeGreaterThanOrEqual(1);
  expect(held(p)?.typeId ?? "nr:w_throwing_knives").toBe("nr:w_throwing_knives");
  give(p, "nr:w_machete", 8);
});
