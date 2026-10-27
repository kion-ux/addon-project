// ゴア: 当たった部位の判定（DESIGN §4「当たった部位の判定」・§12 の当たり箱）
// 立ち姿勢・寝た姿勢（down / dead）・うつ伏せ（crawl）で、全部位の箱の中心を狙うと、その部位に当たること。
// 近接 = プレイヤーの目から視線のレイ（entityHurt → applyHit）、飛び道具 = 着弾点、外れ = 狙いの高さ。
import { test, tick, spawnZombie, spawnPlayer, hit, shoot, expect, aim, setBlock } from "nr-test";
import {
  locate, partCenter, pointPart, heightPart, boxesOf, shapesReady, PARTS, toLocalPoint,
} from "./gore_util.js";
import { setState } from "../scripts/gore/gore.js";
import { on, EV } from "../scripts/core/bus.js";

/** @type {any[]} */
const hits = [];
on(EV.HIT, (r) => hits.push(r));
const last = () => hits[hits.length - 1];

test("hitloc: 立ち姿勢で全部位・上下の箱を目からのレイで当てる", async () => {
  await shapesReady;
  const p = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.7 });
  await tick(1);
  for (const part of PARTS) {
    const n = boxesOf(z).boxes[part].length;
    for (let sub = 0; sub < n; sub++) {
      aim(p, partCenter(z, part, sub));
      const r = locate(z, { attacker: p });
      expect(`${r.part}:${r.sub}`).toBe(`${part}:${sub}`);
      expect(r.how).toBe("ray");
    }
  }
});

test("hitloc: 近接の一撃（entityHurt）で狙った部位が applyHit に届く", async () => {
  await shapesReady;
  const p = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  for (const part of PARTS) {
    const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.7 });
    await tick(1);
    const n0 = hits.length;
    await hit(p, z, { point: partCenter(z, part, 0), damage: 0.5 });
    expect(hits.length).toBeGreaterThan(n0);
    expect(last().part).toBe(part);
    expect(last().source).toBe("melee");
  }
});

test("hitloc: 飛び道具は着弾点の箱（部位ごと）", async () => {
  await shapesReady;
  const p = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  for (const part of PARTS) {
    const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 4.5 });
    await tick(1);
    await shoot(p, z, { point: partCenter(z, part, 0), damage: 0.5 });
    expect(last().part).toBe(part);
    expect(last().source).toBe("projectile");
  }
});

test("hitloc: 仰向け（down）・死体（dead）・うつ伏せ（crawl）の箱で全部位", async () => {
  await shapesReady;
  for (const state of ["down", "crawl"]) {
    const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 3.5 }, { yaw: 0 });
    setState(z, state);
    await tick(1);
    const pose = boxesOf(z).pose;
    expect(pose).toBe(state === "crawl" ? "prone" : "lie");
    for (const part of PARTS) {
      const n = boxesOf(z).boxes[part].length;
      for (let sub = 0; sub < n; sub++) {
        const r = pointPart(z, partCenter(z, part, sub));
        expect(`${state}:${r.part}:${r.sub}`).toBe(`${state}:${part}:${sub}`);
      }
    }
    // 寝た体は頭と足が水平に離れている（頭が lie は後ろ = -f、prone は前 = +f）
    const head = toLocalPoint(z, partCenter(z, "head", 0)), foot = toLocalPoint(z, partCenter(z, "leg_r", 1));
    expect(Math.abs(head[2] - foot[2])).toBeGreaterThan(0.8);
    expect(head[2] < foot[2]).toBe(state !== "crawl");
    expect(head[1]).toBeLessThan(0.7);
  }
});

test("hitloc: 寝た体を上から殴る（レイ）と狙った部位", async () => {
  await shapesReady;
  setBlock({ x: 0, y: 66, z: 6 }, "minecraft:stone");
  const p = spawnPlayer({ x: 0.5, y: 67, z: 6.5 });
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 4.5 }, { yaw: 0 });
  setState(z, "down");
  await tick(1);
  for (const part of PARTS) {
    aim(p, partCenter(z, part, 0));
    const r = locate(z, { attacker: p });
    expect(r.part).toBe(part);
  }
});

test("hitloc: 箱を外したら狙いの高さで決める", async () => {
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 3.5 }, { yaw: 0 });
  await tick(1);
  const H = boxesOf(z).shape.height;
  expect(heightPart(z, 64 + H * 0.95).part).toBe("head");
  expect(heightPart(z, 64 + H * 0.6).part).toBe("torso");
  expect(heightPart(z, 64 + H * 0.6, 0.6).part).toBe("arm_r");
  expect(heightPart(z, 64 + H * 0.6, -0.6).part).toBe("arm_l");
  expect(heightPart(z, 64 + H * 0.3, 0.1).part).toBe("leg_r");
  expect(heightPart(z, 64 + H * 0.1, -0.1).part).toBe("leg_l");
  expect(heightPart(z, 64 + H * 0.1, -0.1).sub).toBe(1);
});
