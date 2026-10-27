// 戦闘: 武器の改造（combat/mods.js）— 材料を払って付ける・保存（動的プロパティ・説明文）・付けられない理由・
// 火炎（燃える・持続）・感電（痺れ・連鎖）・出血・毒（鈍足）・UV（夜の種類に倍率・仕留めると免疫）・衝撃・固有の改造
import { test, tick, spawnZombie, expect, prop, used, hit, give, held } from "nr-test";
import { arena, rec, hitsOn, stack, count, editHeld } from "./combat_util.js";
import {
  canApplyMod, applyMod, removeMod, effectiveMods, modDamageMult, onModHit, dotsOn, startDot, readMods,
} from "../scripts/combat/index.js";
import { applyHit } from "../scripts/gore/gore.js";
import { initHp } from "../scripts/core/hp.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";
import { MOD_BY_KEY } from "../scripts/data/mods.js";

const W = (/** @type {string} */ k) => WEAPON_BY_ID[`nr:w_${k}`];

/** 確率の効果が出るまで onModHit を呼ぶ（最大 n 回）。 @param {any} res @param {() => boolean} done @param {number} [n] */
function procUntil(res, done, n = 30) {
  for (let i = 0; i < n && !done(); i++) onModHit(res);
  return done();
}

test("改造: 材料を払って手の武器に火炎 I を付ける（nr:mods の JSON と説明文）", async () => {
  const { p } = await arena({ item: "nr:w_machete", zombie: null });
  for (const [id, n] of MOD_BY_KEY.fire.tiers[0].cost) give(p, stack(id, n), 1 + MOD_BY_KEY.fire.tiers[0].cost.findIndex((c) => c[0] === id));
  const chk = canApplyMod(p, "fire", 1);
  expect(chk.ok).toBe(true);
  const r = applyMod(p, "fire", 1);
  expect(r.ok).toBe(true);
  for (const [id] of MOD_BY_KEY.fire.tiers[0].cost) expect(count(p, id)).toBe(0);
  const it = held(p);
  expect(JSON.parse(it.getDynamicProperty("nr:mods"))).toEqual({ fire: 1 });
  expect(it.getLore().some((l) => l.includes("火炎 I"))).toBe(true);
  expect(used().sounds["nr.w.mod_fire"]).toBe(1);
  expect(rec.state.some((s) => s.mods.fire === 1)).toBe(true);
});

test("改造: 材料不足・付けられない改造・枠が一杯・同じ段階は付かない（理由つき）", async () => {
  const { p } = await arena({ item: "nr:w_machete", zombie: null });
  expect(canApplyMod(p, "fire", 1).reason).toBe("materials");
  expect(canApplyMod(p, "fire", 1).missing.length).toBeGreaterThan(0);
  expect(canApplyMod(p, "impact", 1).reason).toBe("not_allowed");          // 刃物に衝撃は付かない
  expect(applyMod(p, "fire", 1, { free: true }).ok).toBe(true);
  expect(canApplyMod(p, "fire", 1).reason).toBe("tier");
  expect(canApplyMod(p, "shock", 1).reason).toBe("no_slot");               // ありふれた = 枠 1
  expect(applyMod(p, "fire", 2, { free: true }).ok).toBe(true);             // 段階を上げるのは枠を使わない
  expect(readMods(held(p))).toEqual({ fire: 2 });
  expect(removeMod(p, "fire")).toBe(true);
  expect(held(p).getDynamicProperty("nr:mods")).toBe(undefined);
  give(p, stack("nr:scrap", 5), 0);
  expect(canApplyMod(p, "fire", 1).reason).toBe("no_weapon");               // 重ねられる物には付かない
});

test("改造: 付けた武器で殴ると gore.js の hit.mods に入る（近接の解決）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 300 });
  applyMod(p, "bleed", 2, { free: true });
  await hit(p, z, { part: "torso" });
  await tick(1);
  expect(hitsOn(z)[0].hit.mods).toEqual({ bleed: 2 });
});

test("火炎: 当たると燃え、持続ダメージで nr:burn が上がる", async () => {
  const { p, z } = await arena({ zombie: "office_worker", hp: 300 });
  const res = { hit: { mods: { fire: 3 }, dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, point: z.location };
  expect(procUntil(res, () => dotsOn(z).some((d) => d.kind === "fire"))).toBe(true);
  await tick(31);
  const f = hitsOn(z, (r) => r.dtype === "fire");
  expect(f.length).toBeGreaterThanOrEqual(2);
  expect(f.every((r) => r.hit._mod === true)).toBe(true);
  expect(prop(z, "nr:burn")).toBeGreaterThanOrEqual(1);
  expect(used().sounds["nr.w.mod_fire"]).toBeGreaterThan(0);
});

test("感電: 痺れて（nr:shock）近くの敵へ連鎖する", async () => {
  const { p, z } = await arena({ zombie: "office_worker", hp: 300 });
  const z2 = spawnZombie("office_worker", { x: 2.0, y: 64, z: 2.6 });
  initHp(z2, 300);
  await tick(1);
  const res = { hit: { mods: { shock: 3 }, dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, point: z.location };
  expect(procUntil(res, () => hitsOn(z, (r) => r.dtype === "shock").length > 0)).toBe(true);
  expect(prop(z, "nr:shock")).toBe(1);
  expect(hitsOn(z2, (r) => r.dtype === "shock").length).toBe(1);
  expect(used().particles["nr:shock_spark"]).toBeGreaterThan(0);
});

test("出血と毒: 持続ダメージ（出血は斬撃、毒は鈍足つき）", async () => {
  const { p, z } = await arena({ zombie: "office_worker", hp: 300 });
  const bleed = { hit: { mods: { bleed: 3 }, dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, point: z.location };
  expect(procUntil(bleed, () => dotsOn(z).some((d) => d.kind === "bleed"))).toBe(true);
  const tox = { hit: { mods: { toxic: 3 }, dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, point: z.location };
  expect(procUntil(tox, () => dotsOn(z).some((d) => d.kind === "toxic"))).toBe(true);
  expect(z.getEffect("slowness")).toBeDefined();
  await tick(21);
  expect(hitsOn(z, (r) => r.dtype === "slash" && r.hit._mod).length).toBeGreaterThanOrEqual(1);
  expect(hitsOn(z, (r) => r.dtype === "toxic" && r.hit._mod).length).toBeGreaterThanOrEqual(1);
  expect(used().particles["nr:toxic_gas"]).toBeGreaterThan(0);
});

test("UV: 夜の種類には night_mult 倍、普通の種類は 1 倍。UV の改造で仕留めると免疫が戻る", async () => {
  const { p, z } = await arena({ zombie: "volatile" });
  const ow = spawnZombie("office_worker", { x: 2, y: 64, z: 2.6 });
  await tick(1);
  expect(modDamageMult({ uv: 1 }, z)).toBeCloseTo(MOD_BY_KEY.uv.tiers[0].night_mult, 5);
  expect(modDamageMult({ uv: 1 }, ow)).toBe(1);
  applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", damage: 9999, mods: { uv: 2 }, crit: false });
  await tick(1);
  expect(rec.immunity.some((x) => x.player.id === p.id && x.seconds === MOD_BY_KEY.uv.tiers[1].immunity_on_kill_s)).toBe(true);
});

test("衝撃: 当たると白い輪と破裂音（押し返し・骨折は gore.js）", async () => {
  const { p, z } = await arena({ item: "nr:w_pipe_wrench", hp: 300 });
  expect(applyMod(p, "impact", 1, { free: true }).ok).toBe(true);
  await hit(p, z, { part: "torso" });
  await tick(1);
  expect(used().particles["nr:impact_ring"]).toBeGreaterThan(0);
  expect(used().sounds["nr.w.mod_impact"]).toBeGreaterThan(0);
});

test("固有の改造: 回転ノコの薙刀は感電を持ち、保存した改造と合わさる", async () => {
  expect(effectiveMods(W("buzzsaw_glaive"), undefined)).toEqual({ shock: 1 });
  const { p } = await arena({ item: "nr:w_buzzsaw_glaive", zombie: null });
  applyMod(p, "fire", 1, { free: true });
  expect(effectiveMods(W("buzzsaw_glaive"), held(p))).toEqual({ fire: 1, shock: 1 });
  void editHeld; void startDot;
});
