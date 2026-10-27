// ゴア: ゾンビの「本当の体力」（DESIGN §4）— nr:hp と大きなプール、entityHurt の流れ、予約（二重に数えない）、
// setMeleeResolver（hit / false / undefined）、難易度・人数、/kill（プールを超えた死）
import { test, tick, spawnZombie, spawnPlayer, expect, hit, used, despawn } from "nr-test";
import { partCenter, shapesReady, defaults } from "./gore_util.js";
import { applyHit, setMeleeResolver, stateOf } from "../scripts/gore/gore.js";
import { hpOf, maxHpOf, baseHp, hurtVanilla, reserve, consumeReservation } from "../scripts/core/hp.js";
import { set as setSetting } from "../scripts/core/settings.js";
import { on, EV } from "../scripts/core/bus.js";

/** @type {any[]} */
const hits = [];
on(EV.HIT, (r) => hits.push(r));
/** @type {any[]} */
const kills = [];
on(EV.KILL, (k) => kills.push(k));

/** @type {any} */
let P;
async function setup(key = "office_worker") {
  await shapesReady;
  defaults();
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  P.teleport({ x: 0.5, y: 64, z: 0.5 });
  const z = spawnZombie(key, { x: 0.5, y: 64, z: 2.6 });
  await tick(1);
  return { p: P, z };
}
/** @param {any} z */
const pool = (z) => z.getComponent("minecraft:health").currentValue;

test("hp: 出現で nr:hp = spec の hp（normal）、minecraft:health は 1000 のプール", async () => {
  const { z } = await setup();
  expect(hpOf(z)).toBe(24);
  expect(maxHpOf(z)).toBe(24);
  expect(baseHp("office_worker")).toBe(24);
  expect(z.getDynamicProperty("nr:hp")).toBe(24);
  expect(pool(z)).toBe(1000);
});

test("hp: 近接の一撃（entityHurt）は本当の体力から引かれ、プールは満タンに戻る", async () => {
  const { p, z } = await setup();
  const n0 = hits.length;
  await hit(p, z, { part: "torso", damage: 5 });
  await tick(1);
  expect(hits.length).toBe(n0 + 1);
  const r = hits[hits.length - 1];
  expect(r.source).toBe("melee");
  expect(r.damage).toBeGreaterThanOrEqual(5);              // 会心なら 1.5 倍
  expect(hpOf(z)).toBeCloseTo(24 - r.damage, 3);
  expect(pool(z)).toBe(1000);
  expect(z.isValid).toBe(true);
});

test("hp: スクリプトの applyHit は赤い点滅（hurtVanilla）を出すが、entityHurt で二重に数えない", async () => {
  const { p, z } = await setup();
  const h0 = used().hurts;
  const r = applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "light", part: "torso", point: partCenter(z, "torso", 0), damage: 5, crit: false, gorePower: 0 });
  expect(r.damage).toBe(5);
  await tick(3);
  expect(used().hurts).toBeGreaterThan(h0);                 // バニラの被弾は起きた
  expect(hpOf(z)).toBe(19);                                 // でも本当の体力は 1 回分だけ
  expect(pool(z)).toBe(1000);
  // hurtVanilla だけなら本当の体力は減らない
  expect(hurtVanilla(z, 3, p)).toBe(true);
  await tick(2);
  expect(hpOf(z)).toBe(19);
  // 予約は原因ごと・一度きり
  reserve(z, "contact");
  expect(consumeReservation(z, "fall")).toBe(false);
  expect(consumeReservation(z, "contact")).toBe(true);
  expect(consumeReservation(z, "contact")).toBe(false);
});

test("hp: setMeleeResolver（hit で上書き / false で無視 / undefined で既定）", async () => {
  const { p, z } = await setup();
  setMeleeResolver(() => ({ dtype: "slash", weight: "heavy", gorePower: 1, damage: 30, crit: false }));
  try {
    await hit(p, z, { part: "arm_r", point: partCenter(z, "arm_r", 1), damage: 2 });
    const r = hits[hits.length - 1];
    expect(r.dtype).toBe("slash");
    expect(r.part).toBe("arm_r");
    expect(r.severed).toContain("arm_r");
    await tick(12);
    setMeleeResolver(() => false);
    const n0 = hits.length;
    const hp0 = hpOf(z);
    await hit(p, z, { part: "torso", damage: 9 });
    await tick(1);
    expect(hits.length).toBe(n0);
    expect(hpOf(z)).toBe(hp0);
    await tick(12);
    setMeleeResolver(() => undefined);
    await hit(p, z, { part: "torso", damage: 10 });
    await tick(1);
    expect(hits.length).toBe(n0 + 1);
    expect(hits[hits.length - 1].dtype).toBe("blunt");        // 素手 = 既定の解決
  } finally {
    setMeleeResolver(undefined);
  }
});

test("hp: 難易度 hard は × 1.3、人数で強くする設定なら 2 人目から × 1.2（hard）", async () => {
  await setup();
  setSetting("difficulty", "hard");
  const { z } = await setup();
  void z;
  setSetting("difficulty", "hard");
  const z2 = spawnZombie("office_worker", { x: 2.5, y: 64, z: 3.5 });
  await tick(1);
  expect(hpOf(z2)).toBe(31);                                // 24 × 1.3 = 31.2 → 0.5 刻み
  const p2 = spawnPlayer({ x: -3.5, y: 64, z: 0.5 });
  const z3 = spawnZombie("office_worker", { x: 3.5, y: 64, z: 3.5 });
  await tick(1);
  expect(hpOf(z3)).toBe(37.5);                              // × 1.3 × (1 + 0.2)
  setSetting("difficulty_scaling", false);
  expect(baseHp("office_worker")).toBe(31);
  despawn(p2);
  defaults();
});

test("hp: /kill（プールを超えた死 → entityDie）は全身が弾ける", async () => {
  const { z } = await setup();
  const k0 = kills.length;
  z.kill();
  await tick(3);
  expect(kills.length).toBe(k0 + 1);
  expect(kills[kills.length - 1].overkill).toBe(true);
  expect(z.isValid).toBe(false);
  expect(used().spawned["nr:gib"]).toBeGreaterThan(3);
});

test("hp: 体力が尽きると死ぬ（何度かの一撃の合計）", async () => {
  const { p, z } = await setup();
  let n = 0;
  while (stateOf(z) !== "dead" && n < 20) {
    applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "light", part: "torso", point: partCenter(z, "torso", 0), damage: 5, crit: false, gorePower: 0, noKnockback: true });
    n++;
    await tick(2);
  }
  expect(n).toBe(5);                                        // 24 / 5 → 5 発目
  expect(hpOf(z)).toBe(0);
  expect(kills[kills.length - 1].cause).toBe("hp");
});
