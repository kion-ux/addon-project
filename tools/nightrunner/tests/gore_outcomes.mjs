// ゴア: ダメージ種別 × 部位の結果（DESIGN §4 の表）・ゴアレベル・装甲の段階・這い・spec の例外
import { test, tick, spawnZombie, spawnPlayer, expect, prop, used, aim, despawn, S } from "nr-test";
import { partCenter, shapesReady, setGore, defaults, partsNow, CUT } from "./gore_util.js";
import { applyHit, partState, stateOf } from "../scripts/gore/gore.js";
import { gibCount } from "../scripts/gore/gibs.js";
import { on, EV } from "../scripts/core/bus.js";

/** @type {Record<string, any[]>} */
const seen = {};
for (const k of Object.values(EV)) on(k, (d) => (seen[k] ??= []).push(d));
const count = (k) => (seen[k] ?? []).length;

const AT = { x: 0.5, y: 64, z: 3.5 };
/** @type {any} */
let P;
/** @type {any} */
let Z;
/**
 * 新しいゾンビ（プレイヤーの方を向く）。プレイヤーはテストの間ひとり（人数で体力が増える設定 difficulty_scaling
 * があるので、増やさない）。前のゾンビは消す（イベントなし）。
 */
async function setup(key = "office_worker") {
  await shapesReady;
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  if (Z && Z.isValid) despawn(Z);
  Z = spawnZombie(key, AT);
  await tick(1);
  return { p: P, z: Z };
}
function strike(p, z, part, sub, o) {
  return applyHit(z, { attacker: p, source: "melee", crit: false, part, point: partCenter(z, part, sub), ...o });
}
/** 目からのレイで（点を渡さない。弱点のゾーンは当たった面で決まる）。 */
function strikeRay(p, z, part, sub, o) {
  aim(p, partCenter(z, part, sub));
  return applyHit(z, { attacker: p, source: "melee", crit: false, ...o });
}

// [dtype, 部位, 箱, 追加, 期待する nr:<部位> の値]
const CASES = [
  ["slash", "head", 0, { weight: "medium", gorePower: 0.75, damage: 30 }, "severed"],
  ["slash", "arm_r", 1, { weight: "medium", gorePower: 0.75, damage: 30 }, "cut_lower"],
  ["slash", "arm_l", 0, { weight: "medium", gorePower: 0.75, damage: 30 }, "cut_upper"],
  ["slash", "leg_r", 1, { weight: "medium", gorePower: 0.75, damage: 26 }, "cut_lower"],
  ["slash", "leg_l", 0, { weight: "medium", gorePower: 0.75, damage: 26 }, "cut_upper"],
  ["slash", "torso", 0, { weight: "medium", gorePower: 0.75, damage: 20 }, "gutted"],
  ["slash", "torso", 1, { weight: "heavy", gorePower: 1.0, damage: 20 }, "halved"],
  ["blunt", "head", 0, { weight: "heavy", gorePower: 0.9, damage: 30 }, "crushed"],
  ["blunt", "head", 0, { weight: "light", gorePower: 0.3, damage: 4 }, "cracked"],
  ["blunt", "arm_r", 0, { weight: "medium", gorePower: 0.6, damage: 20 }, "broken"],
  ["blunt", "leg_l", 1, { weight: "medium", gorePower: 0.6, damage: 20 }, "broken"],
  ["blunt", "torso", 0, { weight: "heavy", gorePower: 0.9, damage: 20 }, "intact"],
  ["pierce", "head", 0, { weight: "heavy", gorePower: 0.95, damage: 30 }, "crushed"],
  ["pierce", "head", 0, { weight: "medium", gorePower: 0.5, damage: 30 }, "cracked"],
  ["pierce", "arm_r", 1, { weight: "heavy", gorePower: 0.95, damage: 20 }, "cut_lower"],
  ["pierce", "arm_l", 1, { weight: "light", gorePower: 0.4, damage: 20 }, "wounded"],
  ["pierce", "leg_r", 0, { weight: "light", gorePower: 0.4, damage: 20 }, "wounded"],
  ["pierce", "torso", 0, { weight: "medium", gorePower: 0.5, damage: 12 }, "slashed"],
  ["blast", "head", 0, { weight: "heavy", power: 1.6, damage: 30 }, "crushed"],
  ["blast", "arm_r", 0, { weight: "heavy", power: 1.6, damage: 20 }, "cut_upper"],
  ["blast", "leg_l", 1, { weight: "heavy", power: 1.6, damage: 20 }, "cut_upper"],
  ["blast", "torso", 0, { weight: "heavy", power: 1.6, damage: 30 }, "halved"],
];

test("outcomes: ゴア 100 で dtype × 部位の結果（DESIGN §4 の表）", async () => {
  defaults();
  for (const [dtype, part, sub, o, want] of CASES) {
    const { p, z } = await setup();
    const res = strike(p, z, part, sub, { dtype, source: dtype === "blast" ? "blast" : "melee", ...o });
    expect(res.part).toBe(part);
    expect(`${dtype} ${part}:${sub} → ${prop(z, `nr:${part}`)}`).toBe(`${dtype} ${part}:${sub} → ${want}`);
    if (want === "severed" || want === "crushed") expect(res.killed).toBe(true);
    await tick(2);
  }
  expect(count(EV.DECAP)).toBeGreaterThan(0);
  expect(count(EV.CRUSH)).toBeGreaterThan(0);
  expect(count(EV.HALVED)).toBeGreaterThan(0);
  expect(count(EV.GUTTED)).toBeGreaterThan(0);
  const u = used();
  for (const id of ["nr:sever_burst", "nr:head_explode", "nr:blood_spray", "nr:hit_flesh", "nr:gut_strands", "nr:bone_shards"]) {
    expect(`${id} ${u.particles[id] > 0}`).toBe(`${id} true`);
  }
  for (const id of ["nr.gore.decap", "nr.gore.sever", "nr.gore.head_pop", "nr.gore.bone_crack", "nr.gore.gut_spill", "nr.gore.slash_flesh"]) {
    expect(`${id} ${u.sounds[id] > 0}`).toBe(`${id} true`);
  }
  expect(u.spawned["nr:gib"]).toBeGreaterThan(5);
});

test("outcomes: 頭を斬り落とすと gib（頭）・首の噴水・断面の飛沫・即死", async () => {
  const { p, z } = await setup();
  const before = gibCount();
  const res = strike(p, z, "head", 0, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 40 });
  expect(res.decap).toBe(true);
  expect(res.killed).toBe(true);
  expect(res.severed).toContain("head");
  expect(gibCount()).toBeGreaterThan(before);
  await tick(12);
  expect(used().particles["nr:blood_fountain"]).toBeGreaterThan(0);
  expect(prop(z, "nr:state")).toBe("dead");
  expect(used().events["nr:on_death"]).toBe(1);
});

test("outcomes: 打撃の胴は肋骨が折れて倒れ（down）、時間が経つと起き上がる", async () => {
  const { p, z } = await setup();
  const res = strike(p, z, "torso", 0, { dtype: "blunt", weight: "heavy", gorePower: 0.9, damage: 18 });
  expect(res.knockdown).toBe(true);
  expect(prop(z, "nr:state")).toBe("down");
  expect(prop(z, "nr:torso")).toBe("intact");
  expect(used().anims["animation.nr.z.knockdown"]).toBe(1);
  await tick(60);
  expect(prop(z, "nr:state")).toBe("normal");
  expect(used().anims["animation.nr.z.getup"]).toBe(1);
});

test("outcomes: ゴア 0 では何も落ちない・血も出ない（wounded / broken だけ）", async () => {
  setGore(0);
  for (const [dtype, part, sub, o] of CASES) {
    const { p, z } = await setup();
    strike(p, z, part, sub, { dtype, ...o });
    for (const [k, v] of Object.entries(partsNow(prop, z))) {
      expect(`${dtype} ${k}=${v} ${CUT.has(v) || v === "jawless" || v === "cracked" || v === "gutted" || v === "slashed"}`).toBe(`${dtype} ${k}=${v} false`);
    }
    await tick(1);
  }
  const u = used();
  await tick(40);          // 死体が落ち着いても血だまりは出ない
  const u2 = used();
  for (const id of Object.keys(u2.particles)) expect(`${id} ${/blood|sever|head_explode|gore_chunks|gut/.test(id)}`).toBe(`${id} false`);
  expect(u2.spawned["nr:gib"]).toBe(0);
  void u;
  defaults();
});

test("outcomes: ゴア 50 では真っ二つにならない（halved は min_g 60）", async () => {
  setGore(50);
  const { p, z } = await setup();
  strike(p, z, "torso", 1, { dtype: "slash", weight: "heavy", gorePower: 1.0, damage: 20 });
  expect(prop(z, "nr:torso")).toBe("gutted");
  defaults();
});

test("outcomes: 弱い一撃の積み重ねで部位体力を超えると落ちる", async () => {
  const { p, z } = await setup();
  let n = 0;
  while (prop(z, "nr:arm_r") !== "cut_lower" && n < 10) {
    strike(p, z, "arm_r", 1, { dtype: "slash", weight: "light", gorePower: 0.4, damage: 2 });
    n++;
  }
  expect(prop(z, "nr:arm_r")).toBe("cut_lower");
  expect(n).toBeGreaterThan(2);
  // 前腕を落とした後に上腕を斬ると cut_upper（下がる方向には変わらない）
  strike(p, z, "arm_r", 0, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 6 });
  expect(prop(z, "nr:arm_r")).toBe("cut_upper");
  strike(p, z, "arm_r", 0, { dtype: "blunt", weight: "heavy", gorePower: 1, damage: 6 });
  expect(prop(z, "nr:arm_r")).toBe("cut_upper");
});

test("outcomes: 脚を落とすと這う（nr:to_crawl・nr:state crawl・うつ伏せの箱）", async () => {
  const { p, z } = await setup();
  const res = strike(p, z, "leg_r", 1, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 12 });
  expect(res.crawl).toBe(true);
  expect(used().events["nr:to_crawl"]).toBe(1);
  expect(stateOf(z)).toBe("crawl");
  await tick(1);
  expect(prop(z, "nr:state")).toBe("crawl");
  expect(count(EV.CRAWL)).toBeGreaterThan(0);
});

test("outcomes: 両脚が折れると這う、片脚だけなら鈍足", async () => {
  const { p, z } = await setup();
  strike(p, z, "leg_r", 0, { dtype: "blunt", weight: "medium", gorePower: 0.6, damage: 12 });
  expect(prop(z, "nr:leg_r")).toBe("broken");
  expect(stateOf(z)).not.toBe("crawl");          // 片脚だけ: 這わない（よろめくことはある）
  expect(used().effects["slowness"]).toBe(1);
  await tick(12);
  strike(p, z, "leg_l", 0, { dtype: "blunt", weight: "medium", gorePower: 0.6, damage: 12 });
  expect(prop(z, "nr:leg_l")).toBe("broken");
  expect(stateOf(z)).toBe("crawl");
});

test("outcomes: 胴が真っ二つでも生きていれば上半身で這う", async () => {
  const { p, z } = await setup("drowned");
  const res = strike(p, z, "torso", 1, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 30 });
  expect(res.halved).toBe(true);
  expect(res.killed).toBe(false);
  expect(stateOf(z)).toBe("crawl");
  expect(used().spawned["nr:gib"]).toBeGreaterThan(1);
});

test("outcomes: 装甲の段階（riot_police）: 守られている間は切れず火花、段階が尽きると外れて部位が通る", async () => {
  const { p, z } = await setup("riot_police");
  expect(prop(z, "nr:armor")).toBe(3);
  const breaks0 = count(EV.ARMOR_BREAK);
  const r1 = strike(p, z, "arm_r", 1, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 30 });
  expect(r1.armored).toBe(true);
  expect(prop(z, "nr:arm_r")).toBe("intact");
  expect(used().particles["nr:hit_spark"]).toBeGreaterThan(0);
  let n = 0;
  while (prop(z, "nr:armor") === 3 && n < 6) { strike(p, z, "arm_r", 1, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 30 }); n++; }
  expect(prop(z, "nr:armor")).toBe(2);
  expect(count(EV.ARMOR_BREAK)).toBe(breaks0 + 1);
  expect(prop(z, "nr:arm_r")).toBe("intact");
  // nr:armor = 2: 腕（armor_strip 3）はもう守られない。胴（2）と頭（1）はまだ
  const r2 = strike(p, z, "arm_r", 1, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 30 });
  expect(r2.armored).toBe(false);
  expect(prop(z, "nr:arm_r")).toBe("cut_lower");
  const r3 = strike(p, z, "torso", 0, { dtype: "blunt", weight: "heavy", gorePower: 1, damage: 10 });
  expect(r3.armored).toBe(true);
  // 打撃は装甲を早く剥がす（armor_break.blunt 1.5）
  let m = 0;
  while (prop(z, "nr:armor") === 2 && m < 6) { strike(p, z, "torso", 0, { dtype: "blunt", weight: "heavy", gorePower: 1, damage: 10 }); m++; }
  expect(prop(z, "nr:armor")).toBe(1);
  expect(m).toBeLessThan(3);
});

test("outcomes: 火で焼ける（nr:burn）・感電（nr:shock が戻る）・毒は部位を変えない・UV は昼の感染者に効かない", async () => {
  const { p, z } = await setup();
  const r = strike(p, z, "torso", 0, { dtype: "fire", source: "fire", damage: 7 });
  expect(prop(z, "nr:burn")).toBeGreaterThan(0);
  expect(r.changes).toHaveLength(0);
  strike(p, z, "torso", 0, { dtype: "shock", source: "shock", damage: 1, stunTicks: 10 });
  expect(prop(z, "nr:shock")).toBe(1);
  await tick(12);
  expect(prop(z, "nr:shock")).toBe(0);
  const t = strike(p, z, "arm_r", 0, { dtype: "toxic", source: "toxic", damage: 2 });
  expect(t.changes).toHaveLength(0);
  const hp0 = t.hp;
  const u = strike(p, z, "head", 0, { dtype: "uv", source: "trap", damage: 10 });
  expect(u.damage).toBe(0);
  expect(u.hp).toBe(hp0);
  const { z: night } = await setup("cinder_hunter");
  const n = strike(p, night, "torso", 0, { dtype: "uv", source: "trap", damage: 10 });
  expect(n.damage >= 0).toBe(true);
});

test("outcomes: spec の例外 no_sever / halve = false（subject_zero）", async () => {
  const { p, z } = await setup("subject_zero");
  strike(p, z, "head", 0, { dtype: "slash", weight: "heavy", gorePower: 1.2, damage: 60 });
  expect(["intact", "wounded", "jawless"]).toContain(prop(z, "nr:head"));
  strike(p, z, "torso", 1, { dtype: "slash", weight: "heavy", gorePower: 1.2, damage: 800 });
  expect(prop(z, "nr:torso")).toBe("gutted");     // 強い一撃でも halved にはならない
});

test("outcomes: spec の regrow（subject_zero の腕は 20 秒で生え戻る）", async () => {
  const { p, z } = await setup("subject_zero");
  strike(p, z, "arm_l", 0, { dtype: "slash", weight: "heavy", gorePower: 1.2, damage: 500 });
  expect(prop(z, "nr:arm_l")).toBe("cut_upper");
  await tick(20 * 20 + 12);
  expect(prop(z, "nr:arm_l")).toBe("intact");
  expect(count(EV.REGROW)).toBeGreaterThan(0);
});

test("outcomes: spec の pre_damage（crawler は脚が無く這った状態で出る）", async () => {
  const { z } = await setup("crawler");
  await tick(1);
  expect(prop(z, "nr:leg_r")).toBe("cut_upper");
  expect(prop(z, "nr:leg_l")).toBe("cut_lower");
  expect(prop(z, "nr:state")).toBe("crawl");
});

test("outcomes: 装甲の無い種類の壊れる部品（firefighter の背中のボンベ = 弱点）", async () => {
  const { p, z } = await setup("firefighter");
  p.teleport({ x: 0.5, y: 64, z: 6.5 });         // 背中の側から目のレイで（点を渡さない）
  expect(prop(z, "nr:armor")).toBe(1);
  const res = strikeRay(p, z, "torso", 0, { dtype: "pierce", source: "projectile", gorePower: 0.4, damage: 4 });
  p.teleport({ x: 0.5, y: 64, z: 0.5 });
  expect(res.weak?.ability ?? "none").toBe("tank_burst");
  expect(prop(z, "nr:armor")).toBe(0);
  expect(count(EV.WEAKSPOT)).toBeGreaterThan(0);
});

test("outcomes: 膨れた感染者（gasbag）の腹を刺すと破裂して毒の雲", async () => {
  const { p, z } = await setup("gasbag");
  const res = strikeRay(p, z, "torso", 1, { dtype: "pierce", source: "projectile", gorePower: 0.4, damage: 2 });
  expect(res.weak?.ability ?? "none").toBe("gas_cloud_death");
  expect(res.killed).toBe(true);
  await tick(25);
  expect(z.isValid).toBe(false);
  const u = used();
  expect(u.particles["nr:toxic_burst"]).toBeGreaterThan(0);
  expect(u.particles["nr:toxic_gas"]).toBeGreaterThan(0);
});

test("outcomes: 結節の感染者（ticker）は死ぬと爆発し、近くのゾンビを gib にする", async () => {
  const { p, z } = await setup("ticker");
  const near = spawnZombie("office_worker", { x: 2.0, y: 64, z: 3.5 });
  await tick(1);
  strike(p, z, "torso", 0, { dtype: "blunt", weight: "heavy", damage: 200 });
  await tick(15);
  const u = used();
  expect(u.particles["nr:explosion"]).toBe(1);
  // 近くの感染者は爆風で死ぬか部位が飛ぶ
  const torn = Object.values(partsNow(prop, near)).some((v) => CUT.has(v));
  expect(prop(near, "nr:state") === "dead" || torn).toBe(true);
  expect(u.spawned["nr:gib"]).toBeGreaterThan(4);
  void S;
});

test("outcomes: 炭になる種類（charred）は血の代わりに灰、gib は崩れる、死体は灰", async () => {
  const { p, z } = await setup("charred");
  strike(p, z, "arm_r", 0, { dtype: "slash", weight: "heavy", gorePower: 1, damage: 10 });
  expect(prop(z, "nr:arm_r")).toBe("cut_upper");
  await tick(5);
  const u = used();
  expect(u.particles["nr:char_flakes"]).toBeGreaterThan(0);
  expect(u.particles["nr:blood_fountain"]).toBe(0);
  strike(p, z, "torso", 0, { dtype: "blunt", weight: "heavy", damage: 100 });
  await tick(100);
  expect(z.isValid).toBe(false);
  void partState;
});
