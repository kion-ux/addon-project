// ゴア: 死亡・死体・ルート・経験値・オーバーキル・死体の切断・落下のゴア・特殊な死（DESIGN §4 / §5）
import { test, tick, spawnZombie, spawnPlayer, expect, prop, used, despawn, entities, hit, give, setGround, mc } from "nr-test";
import { partCenter, shapesReady, defaults, setGore, partsNow, CUT } from "./gore_util.js";
import { applyHit, stateOf } from "../scripts/gore/gore.js";
import { corpseCount, corpseList, clearCorpses, dropLoot, dropXp, kill, isCorpse } from "../scripts/gore/death.js";
import { clearGibs } from "../scripts/gore/gibs.js";
import { hpOf } from "../scripts/core/hp.js";
import { set as setSetting } from "../scripts/core/settings.js";
import { on, EV } from "../scripts/core/bus.js";

/** @type {Record<string, any[]>} */
const seen = {};
for (const k of [EV.KILL, EV.CORPSE, EV.HIT, EV.SEVER]) on(k, (d) => (seen[k] ??= []).push(d));
const last = (k) => (seen[k] ?? [])[(seen[k] ?? []).length - 1];
const count = (k) => (seen[k] ?? []).length;
/** spawnItem の数（偽物は "minecraft:item(<ID>)" で数える）。 @param {any} u */
const itemsOf = (u) => Object.entries(u.spawned).filter(([k]) => k.startsWith("minecraft:item")).reduce((a, [, n]) => a + Number(n), 0);
/** その名前の音の数（正規表現）。 @param {any} u @param {RegExp} re */
const soundsLike = (u, re) => Object.entries(u.sounds).filter(([k]) => re.test(k)).reduce((a, [, n]) => a + Number(n), 0);

const AT = { x: 0.5, y: 64, z: 3.5 };
/** @type {any} */
let P;
/** プレイヤー 1 人（体力の人数補正を増やさない）と新しいゾンビ。 */
async function setup(key = "office_worker", at = AT) {
  await shapesReady;
  defaults();
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  const z = spawnZombie(key, at);
  await tick(1);
  return { p: P, z };
}
/** 体力で死なせる一撃（胴への重い打撃。切断は起きない）。 */
function finish(p, z, o = {}) {
  return applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "light", part: "torso", point: partCenter(z, "torso", 0), damage: 999, gorePower: 0, crit: false, ...o });
}

test("death: 体力 0 で死ぬ（nr:on_death・state dead・pose・死体・KILL・経験値）", async () => {
  clearCorpses();
  const { p, z } = await setup();
  const kills0 = count(EV.KILL);
  const res = finish(p, z);
  expect(res.killed).toBe(true);
  expect(hpOf(z)).toBe(0);
  expect(stateOf(z)).toBe("dead");
  expect(prop(z, "nr:state")).toBe("dead");
  expect(used().events["nr:on_death"]).toBe(1);
  const pose = prop(z, "nr:pose");
  expect(Number.isInteger(pose) && pose >= 0 && pose <= 7).toBe(true);
  expect(isCorpse(z)).toBe(true);
  expect(corpseCount()).toBe(1);
  expect(count(EV.KILL)).toBe(kills0 + 1);
  const k = last(EV.KILL);
  expect(k.key).toBe("office_worker");
  expect(k.byPlayer).toBe(true);
  expect(k.corpse).toBe(true);
  expect(last(EV.CORPSE).created).toBe(true);
  // 経験値（spec の xp 3 → オーブ 1 つ）と死の声
  expect(used().spawned["minecraft:xp_orb"]).toBeGreaterThan(0);
  expect(soundsLike(used(), /^nr\.z\.[a-z_]+\.death$/)).toBeGreaterThan(0);
  // 死体は二度死なない
  expect(kill(z, { attacker: p })).toBe(false);
  await tick(2);
  expect(used().events["nr:on_death"]).toBe(1);
});

test("death: ルートの表（確率 1）・LOOT_TABLES の名前・経験値のオーブ", async () => {
  await setup();
  const dim = mc.world.getDimension("overworld");
  const before = entities("minecraft:item").length;
  const n = dropLoot(dim, { x: 3.5, y: 64, z: 3.5 }, [["minecraft:bone", 2, 2, 1], ["minecraft:rotten_flesh", 1, 1, 0]]);
  expect(n).toBe(1);
  expect(entities("minecraft:item").length).toBe(before + 1);
  const m = dropLoot(dim, { x: 3.5, y: 64, z: 3.5 }, ["gore_remains"]);
  expect(m).toBeGreaterThanOrEqual(0);
  const orbs = dropXp(dim, { x: 3.5, y: 64, z: 3.5 }, 10);
  expect(orbs).toBe(3);
  expect(dropXp(dim, { x: 3.5, y: 64, z: 3.5 }, 0)).toBe(0);
});

test("death: 殺すと spec の loot を落とす（noLoot なら落とさない）", async () => {
  let items = 0;
  for (let i = 0; i < 4; i++) {
    const { p, z } = await setup("office_worker", { x: 0.5 + i, y: 64, z: 4.5 });
    const before = itemsOf(used());
    finish(p, z);
    items += itemsOf(used()) - before;
  }
  expect(items).toBeGreaterThan(0);
  const { p, z } = await setup();
  const before = itemsOf(used());
  kill(z, { attacker: p, noLoot: true, noXp: true });
  expect(itemsOf(used()) - before).toBe(0);
});

test("death: 死体の寿命（corpse_lifetime_s）と上限（max_corpses。古い順に消える）", async () => {
  clearCorpses();
  const { p, z } = await setup();
  expect(setSetting("corpse_lifetime_s", 10)).toBe(true);       // 設定の範囲 10..600 秒
  finish(p, z);
  expect(corpseCount()).toBe(1);
  await tick(150);
  expect(z.isValid).toBe(true);
  await tick(55);
  expect(z.isValid).toBe(false);
  expect(corpseCount()).toBe(0);
  expect(last(EV.CORPSE).created).toBe(false);
  defaults();
  setSetting("max_corpses", 2);
  const zs = [];
  for (let i = 0; i < 3; i++) {
    const s = await setup("office_worker", { x: -1.5 + i * 1.5, y: 64, z: 4.5 });
    setSetting("max_corpses", 2);
    finish(s.p, s.z);
    zs.push(s.z);
  }
  await tick(2);
  expect(corpseCount()).toBe(2);
  expect(zs[0].isValid).toBe(false);
  expect(zs[2].isValid).toBe(true);
  expect(corpseList().map((e) => e.id)).toContain(zs[2].id);
  defaults();
  clearCorpses();
});

test("death: 死体でもさらに切断できる（corpse: true・体力は減らない）", async () => {
  const { p, z } = await setup();
  finish(p, z);
  await tick(3);
  const r = applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", part: "arm_r", sub: 1, point: partCenter(z, "arm_r", 1), damage: 30, gorePower: 1, crit: false });
  expect(r.corpse).toBe(true);
  expect(r.damage).toBe(0);
  expect(r.killed).toBe(false);
  expect(prop(z, "nr:arm_r")).toBe("cut_lower");
  expect(hpOf(z)).toBe(0);
  expect(used().spawned["nr:gib"]).toBeGreaterThan(0);
  // 頭も落とせる（死体の首が飛ぶ）
  const h = applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", part: "head", point: partCenter(z, "head", 0), damage: 40, gorePower: 1, crit: false });
  expect(h.decap).toBe(true);
  expect(prop(z, "nr:head")).toBe("severed");
  expect(used().events["nr:on_death"]).toBe(1);        // 二度目の死は無い
});

test("death: 死体を手の武器で殴ると切断が進む（entityHitEntity → applyHit corpse）", async () => {
  const { p, z } = await setup();
  finish(p, z);
  await tick(3);
  give(p, "nr:w_machete", 0);
  const hits0 = count(EV.HIT);
  let n = 0;
  while (!CUT.has(prop(z, "nr:leg_l")) && n < 8) {
    await hit(p, z, { part: "leg_l" });
    await tick(11);
    n++;
  }
  expect(count(EV.HIT)).toBeGreaterThan(hits0);
  expect(last(EV.HIT).corpse).toBe(true);
  expect(CUT.has(prop(z, "nr:leg_l"))).toBe(true);
  expect(prop(z, "nr:state")).toBe("dead");
});

test("death: オーバーキル（プールを超えるバニラの死）は全身が弾ける", async () => {
  clearGibs();
  const { p, z } = await setup();
  const kills0 = count(EV.KILL);
  z.applyDamage(5000, { cause: mc.EntityDamageCause.entityAttack, damagingEntity: p });
  await tick(3);
  expect(z.isValid).toBe(false);
  expect(count(EV.KILL)).toBe(kills0 + 1);
  expect(last(EV.KILL).overkill).toBe(true);
  expect(last(EV.KILL).corpse).toBe(false);
  const u = used();
  expect(u.particles["nr:body_explode"]).toBeGreaterThan(0);
  expect(u.spawned["nr:gib"]).toBeGreaterThan(5);
  expect(u.sounds["nr.gore.burst"]).toBeGreaterThan(0);
});

test("death: オーバーキルでもゴア 50 なら弾けない（overkill_burst_min_g 70）", async () => {
  clearGibs();
  const { p, z } = await setup();
  setGore(50);
  z.applyDamage(5000, { cause: mc.EntityDamageCause.entityAttack, damagingEntity: p });
  await tick(3);
  expect(z.isValid).toBe(false);
  expect(used().spawned["nr:gib"]).toBe(0);
  expect(used().particles["nr:body_explode"]).toBe(0);
  defaults();
});

test("death: 高い所から落ちた死体は着地の衝撃で脚が折れる・ちぎれる", async () => {
  const { p, z } = await setup("office_worker", { x: 0.5, y: 84, z: 4.5 });
  finish(p, z);
  for (let i = 0; i < 60 && z.isValid && !z.isOnGround; i++) await tick(1);
  await tick(3);
  const legs = [prop(z, "nr:leg_r"), prop(z, "nr:leg_l")];
  expect(legs.some((v) => v !== "intact")).toBe(true);
  expect(used().sounds["nr.gore.body_fall"]).toBeGreaterThan(0);
  expect(last(EV.HIT).hit.source).toBe("fall");
});

test("death: 生きたまま高い所から落ちると脚が折れる（落下ダメージ → applyHit source fall）", async () => {
  const { z } = await setup("office_worker", { x: 0.5, y: 76, z: 4.5 });
  const hp0 = hpOf(z);
  for (let i = 0; i < 60 && z.isValid && !z.isOnGround; i++) await tick(1);
  await tick(2);
  expect(hpOf(z)).toBeLessThan(hp0);
  const legs = [prop(z, "nr:leg_r"), prop(z, "nr:leg_l")];
  expect(legs.some((v) => v !== "intact")).toBe(true);
  expect(used().hurts).toBeGreaterThan(0);
  expect(last(EV.HIT).hit.source).toBe("fall");
});

test("death: 溶ける死体（spewer: corpse melt）は酸の泡を出して消える", async () => {
  clearCorpses();
  const { p, z } = await setup("spewer");
  finish(p, z);
  expect(corpseCount()).toBe(1);
  await tick(130);
  expect(z.isValid).toBe(false);
  expect(used().particles["nr:acid_splash"]).toBeGreaterThan(0);
  expect(used().sounds["nr.fx.acid_sizzle"]).toBeGreaterThan(0);
});

test("death: 胞子を撒いて弾ける種類（hive_warden: explode spores）は体が残らない", async () => {
  const { p, z } = await setup("hive_warden");
  finish(p, z);
  await tick(3);
  expect(z.isValid).toBe(false);
  expect(used().particles["nr:fungal_spores"]).toBeGreaterThan(0);
  expect(last(EV.KILL).explode).toBe("spores");
  expect(last(EV.KILL).corpse).toBe(false);
});

test("death: 頭が潰れた・首が飛んだ即死は KILL に headshot / decap が付く", async () => {
  const { p, z } = await setup();
  applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "heavy", part: "head", point: partCenter(z, "head", 0), damage: 40, gorePower: 1, crit: false });
  expect(prop(z, "nr:head")).toBe("crushed");
  const k = last(EV.KILL);
  expect(k.crushed).toBe(true);
  expect(k.headshot).toBe(true);
  expect(stateOf(z)).toBe("dead");
  void partsNow; void despawn; void setGround;
});
