// ui/: /scriptevent のコマンド（一式・ゴアレベル・設定・ゾンビを出す・片付け）と、初回参加のあいさつ
import { test, tick, expect, spawnPlayer, spawnZombie, scriptEvent, entities } from "nr-test";
import * as settings from "../scripts/core/settings.js";
import { welcome, STARTER_SKILLS } from "../scripts/ui/welcome.js";
import { hasSkill } from "../scripts/player/skills.js";
import { WEAPONS } from "../scripts/data/weapons.js";

/** @param {any} p */
function inventoryIds(p) {
  const c = p.getComponent("minecraft:inventory").container;
  const ids = new Set();
  for (let i = 0; i < c.size; i++) { const it = c.getItem(i); if (it) ids.add(it.typeId); }
  return ids;
}

test("nr:gore で 0..100 に丸めて設定し、範囲外は端に寄せる", async () => {
  const p = spawnPlayer();
  await tick(1);
  await scriptEvent("nr:gore", "40", p);
  expect(settings.get("gore_level")).toBe(40);
  await scriptEvent("nr:gore", "250", p);
  expect(settings.get("gore_level")).toBe(100);
  await scriptEvent("nr:set", "max_gibs 80", p);
  expect(settings.get("max_gibs")).toBe(80);
});

test("nr:kit melee / ranged で近接と道具・飛び道具と弾が入る（まだ無い物は飛ばす）", async () => {
  const p = spawnPlayer();
  await tick(1);
  await scriptEvent("nr:kit", "melee", p);
  const ids = inventoryIds(p);
  expect(ids.has("nr:w_machete")).toBe(true);
  expect(ids.has("nr:bandage")).toBe(true);
  expect(WEAPONS.length).toBeGreaterThan(20);
  const q = spawnPlayer({ x: 3, y: 64, z: 0 });
  await tick(1);
  await scriptEvent("nr:kit", "ranged", q);
  expect(inventoryIds(q).has("nr:ammo_shotgun")).toBe(true);
  expect(inventoryIds(q).has("nr:w_machete")).toBe(false);
});

test("nr:spawn で鍵・区分・all を出し、nr:clear all で片付く", async () => {
  const p = spawnPlayer();
  await tick(1);
  await scriptEvent("nr:spawn", "office_worker 3", p);
  expect(entities("nr:z_office_worker").length).toBe(3);
  await scriptEvent("nr:spawn", "viral 4", p);
  await scriptEvent("nr:clear", "all", p);
  await tick(2);
  expect(entities().filter((e) => e.typeId.startsWith("nr:z_")).length).toBe(0);
});

test("nr:clear（all 無し）は生きているゾンビを残す", async () => {
  const p = spawnPlayer();
  spawnZombie("nurse", { x: 0, y: 64, z: 4 });
  await tick(1);
  await scriptEvent("nr:clear", "", p);
  await tick(2);
  expect(entities("nr:z_nurse").length).toBe(1);
});

test("初回参加: 最初の持ち物と基本のパルクール技を一度だけ与える", async () => {
  const p = spawnPlayer();
  await tick(1);
  expect(welcome(p)).toBe(true);
  for (const k of STARTER_SKILLS) expect(hasSkill(p, k)).toBe(true);
  expect(inventoryIds(p).has("nr:survivor_terminal")).toBe(true);
  expect(welcome(p)).toBe(false);
});
