// ゴア: 1 tick のパーティクル予算（DESIGN §11: ≤ 300）— 優先度ごとの割合・設定・群れの全身爆発でも超えない
import { test, tick, spawnZombie, spawnPlayer, expect, used, particlePeak, S, mc } from "nr-test";
import { shapesReady, defaults } from "./gore_util.js";
import { take, left, can, pressure, stats, PRIO } from "../scripts/core/budget.js";
import { particle } from "../scripts/core/fx.js";
import { applyHit } from "../scripts/gore/gore.js";
import { detonate } from "../scripts/gore/death.js";
import { clearGibs } from "../scripts/gore/gibs.js";
import { clearCorpses } from "../scripts/gore/death.js";
import { set as setSetting } from "../scripts/core/settings.js";

test("budget: 優先度ごとの割合（LOW 55% / NORMAL 80% / HIGH 95% / CRITICAL 100%）で 1 tick 300 まで", async () => {
  defaults();
  await tick(1);
  const dim = mc.world.getDimension("overworld");
  const at = { x: 0.5, y: 65, z: 0.5 };
  let low = 0, high = 0, crit = 0;
  for (let i = 0; i < 400; i++) if (particle(dim, "blood_drip", at, { count: 1 }, PRIO.LOW)) low++;
  expect(low).toBe(165);
  expect(can(1, PRIO.LOW)).toBe(false);
  expect(pressure(PRIO.LOW)).toBe(0);
  expect(pressure(PRIO.CRITICAL)).toBeGreaterThan(0);
  for (let i = 0; i < 400; i++) if (particle(dim, "hit_flesh", at, undefined, PRIO.HIGH)) high++;
  expect(high).toBe(285 - 165);
  for (let i = 0; i < 400; i++) if (particle(dim, "head_explode", at, { size: 1 }, PRIO.CRITICAL)) crit++;
  expect(crit).toBe(15);
  const st = stats();
  expect(st.used).toBe(300);
  expect(st.cap).toBe(300);
  expect(st.denied).toBeGreaterThan(0);
  expect(S.perTick).toBeLessThanOrEqual(300);
  // 次の tick には戻る
  await tick(1);
  expect(left(PRIO.CRITICAL)).toBe(300);
  expect(take(10, PRIO.NORMAL)).toBe(10);
  expect(take(500, PRIO.NORMAL, true)).toBe(0);           // all = true: 全部取れないなら取らない
  expect(take(500, PRIO.NORMAL, false)).toBe(240 - 10);  // all = false: 取れるだけ
});

test("budget: 設定 particle_budget で上限が下がる（範囲 50..300）", async () => {
  expect(setSetting("particle_budget", 50)).toBe(true);
  await tick(1);
  expect(left(PRIO.CRITICAL)).toBe(50);
  expect(left(PRIO.LOW)).toBe(27);
  setSetting("particle_budget", 1000);                     // 範囲の外は丸める
  await tick(1);
  expect(left(PRIO.CRITICAL)).toBe(300);
  defaults();
});

test("budget: 群れ（24 体）を一度に爆破して全身が弾けても 1 tick 300 を超えない", async () => {
  await shapesReady;
  defaults();
  clearGibs();
  clearCorpses();
  spawnPlayer({ x: 0.5, y: 64, z: -6.5 });
  const zs = [];
  for (let i = 0; i < 24; i++) zs.push(spawnZombie("office_worker", { x: -2.5 + (i % 6), y: 64, z: 1.5 + Math.floor(i / 6) }));
  await tick(1);
  // 同じ tick に全員へ: 爆発（全身の部位）と近くの感染者への重い打撃
  detonate(mc.world.getDimension("overworld"), { x: 0.5, y: 64.5, z: 3.0 }, { radius: 4, dmg: 200 });
  for (const z of zs) if (z.isValid) applyHit(z, { dtype: "blast", source: "blast", weight: "heavy", damage: 300, power: 2 });
  await tick(3);
  const u = used();
  expect(u.spawned["nr:gib"]).toBeGreaterThan(10);
  expect(particlePeak()).toBeLessThanOrEqual(300);
  expect(stats().deniedTotal).toBeGreaterThan(0);          // 予算が効いて断った分がある
  await tick(40);
  expect(particlePeak()).toBeLessThanOrEqual(300);
  clearGibs();
  clearCorpses();
});
