// 戦闘: とどめ（combat/finishers.js）— 踏みつけ（スキル stomp・這う／倒れた敵・頭が弾けて必ず死ぬ）・
// 処刑（スキル finisher・よろめいた敵に溜め攻撃・首が飛ぶ・回復とスタミナ）・スキルが無ければ普通の一撃・ゴア 0
import { test, tick, expect, prop, used, hit, press, startUse, releaseUse } from "nr-test";
import { arena, rec, hitsOn, setGore } from "./combat_util.js";
import { setState, stagger, stateOf } from "../scripts/gore/gore.js";
import { isCorpse } from "../scripts/gore/death.js";
import { SKILL_BY_KEY } from "../scripts/data/skills.js";

test("踏みつけ: スキル stomp があればスニーク＋攻撃で這う敵の頭を踏み潰し、必ず死ぬ", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", skills: ["stomp"], at: { x: 0.5, y: 64, z: 1.6 }, hp: 200 });
  setState(z, "crawl");
  await tick(2);
  await press(p, "Sneak", true);
  await hit(p, z, { part: "head" });
  await tick(2);
  await press(p, "Sneak", false);
  expect(used().anims["animation.nr.p.finisher_stomp"]).toBe(1);
  expect(prop(z, "nr:head")).toBe("crushed");
  expect(isCorpse(z) || stateOf(z) === "dead").toBe(true);
  expect(rec.finisher.length).toBe(1);
  expect(rec.finisher[0].kind).toBe("stomp");
  const r = hitsOn(z)[0];
  expect(r.dtype).toBe("blunt");
  expect(r.part).toBe("head");
});

test("踏みつけ: スキルが無ければ普通の武器の一撃", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", skills: [], at: { x: 0.5, y: 64, z: 1.6 }, hp: 200 });
  setState(z, "crawl");
  await tick(2);
  await press(p, "Sneak", true);
  await hit(p, z, { part: "head" });
  await tick(2);
  await press(p, "Sneak", false);
  expect(used().anims["animation.nr.p.finisher_stomp"]).toBe(0);
  expect(rec.finisher.length).toBe(0);
  expect(hitsOn(z)[0].dtype).toBe("slash");
});

test("処刑: よろめいた敵に溜め攻撃で首が飛ぶ（スキル finisher）・体力とスタミナが戻る", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", skills: ["finisher"], hp: 400 });
  const hc = p.getComponent("minecraft:health");
  hc.setCurrentValue(10);
  stagger(z, 80);
  await tick(2);
  expect(stateOf(z)).toBe("stagger");
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  await tick(6);
  expect(used().anims["animation.nr.p.finisher_decap"]).toBe(1);
  expect(prop(z, "nr:head")).toBe("severed");
  expect(isCorpse(z) || stateOf(z) === "dead").toBe(true);
  const eff = SKILL_BY_KEY.finisher.effect;
  expect(hc.currentValue).toBe(10 + eff.finisher_heal);
  expect(rec.stamina.some((s) => s.amount === -eff.finisher_stamina && s.reason === "finisher")).toBe(true);
  expect(rec.finisher.some((f) => f.kind === "decap")).toBe(true);
});

test("処刑: 打撃の武器なら頭が弾ける", async () => {
  const { p, z } = await arena({ item: "nr:w_pipe_wrench", skills: ["finisher"], hp: 400 });
  stagger(z, 80);
  await tick(2);
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  await tick(6);
  expect(prop(z, "nr:head")).toBe("crushed");
  expect(isCorpse(z) || stateOf(z) === "dead").toBe(true);
});

test("処刑: ゴアレベル 0 では首は飛ばないが、必ず死ぬ", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", skills: ["finisher"], hp: 400 });
  setGore(0);
  stagger(z, 80);
  await tick(2);
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  await tick(6);
  expect(prop(z, "nr:head")).not.toBe("severed");
  expect(isCorpse(z) || stateOf(z) === "dead").toBe(true);
});

test("処刑: よろめいていない敵への溜め攻撃は普通の重い一撃", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", skills: ["finisher"], hp: 400 });
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  await tick(6);
  expect(used().anims["animation.nr.p.finisher_decap"]).toBe(0);
  expect(hitsOn(z)[0].hit.heavy).toBe(true);
  expect(isCorpse(z)).toBe(false);
});
