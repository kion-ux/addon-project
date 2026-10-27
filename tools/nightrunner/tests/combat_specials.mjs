// 戦闘: 武器の special とスキルの細かい効果（combat/melee.js・ranged.js・throwables.js）— 銃床で殴る・
// 背後の倍率（コンバットナイフ）・溜め攻撃は突き（heavy_is_stab）・刺し止め / 押し返し / よろめき（afterMeleeHit）・
// skull_crusher・dismember_mastery・一振りで 2 体（熊手 hits_max）・地面叩き（杭打ちハンマー）・水平二連の 2 発同時・
// スコープ・弓のスタミナ・パイプ爆弾の肉片（gib_burst）・HUD への weapon_state
import { test, tick, spawnZombie, expect, used, hit, use, press, startUse, releaseUse, give, held, aim, partPoint, mc } from "nr-test";
import { arena, rec, hitsOn, stack, heldDamage } from "./combat_util.js";
import { afterMeleeHit, weaponHit, explode, setSkillQuery, isScoped, isReloading } from "../scripts/combat/index.js";
import { heldInfo } from "../scripts/combat/common.js";
import { stateOf } from "../scripts/gore/gore.js";
import { initHp } from "../scripts/core/hp.js";
import { on, EV } from "../scripts/core/bus.js";
import { lenXZ } from "../scripts/core/util.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";
import { COMBAT_TUNING } from "../scripts/data/settings.js";

const W = (/** @type {string} */ k) => WEAPON_BY_ID[`nr:w_${k}`];
/** @param {any} p */
const mag = (p) => held(p).getDynamicProperty("nr:mag");
/** Math.random を v に固定して fn を呼ぶ（確率の効果を確かめる）。 @param {number} v @param {() => void} fn */
function withRandom(v, fn) {
  const r = Math.random;
  Math.random = () => v;
  try { fn(); } finally { Math.random = r; }
}
/** gib の出現（EV.GIB）の記録。 */
const gibs = [];
on(EV.GIB, (g) => gibs.push(g));

test("銃床: 拳銃で殴ると軽い打撃（貫通・切断の武器の値は使わない）・モーション shove・スタミナ bash", async () => {
  const { p, z } = await arena({ item: "nr:w_pistol", hp: 300 });
  await hit(p, z, { part: "head" });
  await tick(1);
  const r = hitsOn(z)[0];
  expect(r).toBeDefined();
  expect(r.source).toBe("melee");
  expect(r.dtype).toBe("blunt");
  expect(r.weight).toBe("light");
  expect(r.hit.weapon).toBe(undefined);
  expect(r.damage).toBeLessThanOrEqual(3 * 2 * 1.5 + 1e-6);            // 3 × 頭 2 ×（会心 1.5）
  expect(r.severed.length).toBe(0);
  expect(used().anims["animation.nr.p.shove"]).toBe(1);
  expect(rec.stamina.some((s) => s.reason === "bash")).toBe(true);
  expect(mag(p) ?? W("pistol").mag).toBe(W("pistol").mag);           // 撃っていない
});

test("背後の倍率: コンバットナイフで背中を刺すと backstab_mult（2.5）倍", async () => {
  const { p } = await arena({ item: "nr:w_combat_knife", zombie: null });
  const back = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.4 }, { yaw: 0 });      // 南（プレイヤーと同じ向き）を向く
  initHp(back, 400);
  await tick(2);
  await hit(p, back, { part: "torso" });
  await tick(1);
  const r = hitsOn(back)[0];
  expect(r.backstab).toBe(true);
  expect(r.damage).toBeGreaterThanOrEqual(W("combat_knife").damage * W("combat_knife").special.backstab_mult * 0.99);
});

test("溜め攻撃が突きの武器（heavy_is_stab）: 突きのモーションで pierce の一撃", async () => {
  const { p, z } = await arena({ item: "nr:w_combat_knife", hp: 300 });
  await startUse(p);
  await tick(12);
  await releaseUse(p, undefined, 12);
  expect(used().anims["animation.nr.p.stab_heavy"]).toBe(1);
  expect(used().anims["animation.nr.p.slash_1h_heavy"]).toBe(0);
  await tick(6);
  const r = hitsOn(z)[0];
  expect(r).toBeDefined();
  expect(r.dtype).toBe("pierce");
  expect(r.hit.heavy).toBe(true);
});

test("一撃の後: 鉄筋の槍は刺して止める・熊手は押し返す・警棒は確率でよろめかせる", async () => {
  const { p, z } = await arena({ zombie: "office_worker", hp: 500 });
  const base = (/** @type {string} */ k, extra = {}) => ({
    hit: { source: "melee", weapon: W(k), dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, dtype: W(k).dtype,
    damage: 1, maxHp: 500, killed: false, corpse: false, staggered: false, knockdown: false, crawl: false, ...extra,
  });
  afterMeleeHit(base("pitchfork"));
  expect(lenXZ(z.getVelocity())).toBeCloseTo(W("pitchfork").special.push_back, 3);
  withRandom(0.99, () => afterMeleeHit(base("police_baton")));
  await tick(1);
  expect(stateOf(z)).toBe("normal");
  withRandom(0, () => afterMeleeHit(base("police_baton")));
  await tick(1);
  expect(stateOf(z)).toBe("stagger");
  const z2 = spawnZombie("office_worker", { x: 2.5, y: 64, z: 2.6 });
  initHp(z2, 500);
  await tick(1);
  afterMeleeHit({ ...base("rebar_spear"), zombie: z2 });
  await tick(1);
  expect(stateOf(z2)).toBe("stagger");
});

test("skull_crusher: 打撃は blunt_stagger_mult 倍よろめきやすい（スキルが無ければよろめかない）", async () => {
  const { p, z } = await arena({ zombie: "office_worker", hp: 100, skills: [] });
  const frac = COMBAT_TUNING.stagger_threshold;
  const res = { hit: { source: "melee", weapon: W("pipe_wrench"), dir: { x: 0, y: 0, z: 1 } }, zombie: z, attacker: p, dtype: "blunt",
    damage: 100 * frac * 0.9, maxHp: 100, killed: false, staggered: false };
  afterMeleeHit(res);
  await tick(1);
  expect(stateOf(z)).toBe("normal");
  setSkillQuery((_p, k) => k === "skull_crusher");
  afterMeleeHit(res);
  await tick(1);
  expect(stateOf(z)).toBe("stagger");
});

test("dismember_mastery: 手足を斬る一撃のゴアの強さが上がる（胴は slash_gore_add だけ）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 300 });
  const h = heldInfo(p);
  aim(p, partPoint(z, "arm_r"));
  setSkillQuery(() => false);
  const a = weaponHit(p, z, h.w, h.item, { spam: 1 });
  setSkillQuery((_p, k) => k === "dismember_mastery");
  const b = weaponHit(p, z, h.w, h.item, { spam: 1 });
  expect(b.gorePower).toBeGreaterThan(a.gorePower + 0.25);
  aim(p, partPoint(z, "torso"));
  const c = weaponHit(p, z, h.w, h.item, { spam: 1 });
  setSkillQuery(() => false);
  const d = weaponHit(p, z, h.w, h.item, { spam: 1 });
  expect(c.gorePower - d.gorePower).toBeCloseTo(0.2, 5);
});

test("熊手（hits_max 2）: 普通の振りで一列の奥の 2 体目にも当たる（少し弱く）", async () => {
  const { p, z } = await arena({ item: "nr:w_pitchfork", hp: 300 });
  const z2 = spawnZombie("office_worker", { x: 0.5, y: 64, z: 3.7 });
  initHp(z2, 300);
  await tick(1);
  await hit(p, z, { part: "torso" });
  await tick(2);
  expect(hitsOn(z).length).toBe(1);
  expect(hitsOn(z2).length).toBe(1);
  expect(hitsOn(z2)[0].source).toBe("melee");
});

test("杭打ちハンマー: 溜め攻撃の後に地面を叩き、横のゾンビの脚に重い打撃（近ければ倒れる）", async () => {
  const { p, z } = await arena({ item: "nr:w_piston_hammer", hp: 400 });
  const side = spawnZombie("office_worker", { x: 2.0, y: 64, z: 2.2 });
  initHp(side, 400);
  await tick(1);
  await startUse(p);
  await tick(20);
  await releaseUse(p, undefined, 20);
  await tick(10);
  expect(hitsOn(z).length).toBe(1);
  const r = hitsOn(side)[0];
  expect(r).toBeDefined();
  expect(r.dtype).toBe("blunt");
  expect(r.hit.parts).toEqual(["leg_r", "leg_l"]);
  expect(r.knockdown).toBe(true);
  expect(used().particles["nr:shockwave_ground"]).toBeGreaterThan(0);
});

test("水平二連: 2 発込めてスニーク＋使うと 2 発同時（弾倉 2 → 0・耐久 2）、普通に使うと 1 発", async () => {
  const { p, z } = await arena({ item: "nr:w_double_barrel", at: { x: 0.5, y: 64, z: 2.6 }, hp: 900 });
  aim(p, partPoint(z, "torso"));
  await use(p);
  await tick(1);
  expect(mag(p)).toBe(1);
  await tick(20);
  give(p, stack("nr:ammo_shotgun", 4), 1);
  await press(p, "Sneak", true);
  await use(p);                          // 1 発しか無い時のスニーク＋使うは手でリロード
  await press(p, "Sneak", false);
  await tick(W("double_barrel").reload_ticks + 2);
  expect(mag(p)).toBe(2);
  const before = heldDamage(p);
  await press(p, "Sneak", true);
  await use(p);
  await tick(1);
  await press(p, "Sneak", false);
  expect(mag(p)).toBe(0);
  expect(heldDamage(p) - before).toBe(2);
  expect(used().sounds["nr.w.shotgun"]).toBe(2);
});

test("スコープ: 猟銃を持ってスニークを続けると視野が狭まり（覗いている間の使うは撃つ）、やめると戻る", async () => {
  const { p, z } = await arena({ item: "nr:w_hunting_rifle", at: { x: 0.5, y: 64, z: 5.0 }, hp: 900 });
  give(p, stack("nr:ammo_rifle", 10), 1);
  aim(p, partPoint(z, "torso"));
  const c0 = used().camera;
  await press(p, "Sneak", true);
  await tick(8);
  expect(isScoped(p)).toBe(true);
  expect(used().camera).toBe(c0 + 1);
  await tick(4);
  expect(used().camera).toBe(c0 + 1);    // 一度だけ
  await use(p);
  await tick(1);
  expect(mag(p)).toBe(W("hunting_rifle").mag - 1);     // リロードではなく撃つ
  expect(isReloading(p)).toBe(false);
  await press(p, "Sneak", false);
  await tick(4);
  expect(isScoped(p)).toBe(false);
  expect(used().camera).toBe(c0 + 2);
  await tick(20);
  await press(p, "Sneak", true);         // スニークと同時に使う（覗く前）は手でリロード
  await use(p);
  await press(p, "Sneak", false);
  expect(isReloading(p)).toBe(true);
});

test("弓: 放つとスタミナ（stamina_cost × 引き）", async () => {
  const { p } = await arena({ item: "nr:w_survivor_bow", zombie: null });
  give(p, stack("nr:survivor_arrow", 3), 1);
  await startUse(p);
  await tick(20);
  await releaseUse(p, undefined, 20);
  const s = rec.stamina.find((x) => x.reason === "bow");
  expect(s).toBeDefined();
  expect(s.amount).toBeCloseTo(W("survivor_bow").stamina_cost, 1);
});

test("パイプ爆弾（gib_burst）: 爆心の近くの体から肉片が飛ぶ（無い武器なら出ない）", async () => {
  const { p, z } = await arena({ zombie: "office_worker", at: { x: 0.5, y: 64, z: 4.0 }, hp: 5000 });
  const dim = mc.world.getDimension("overworld");
  const pb = W("pipe_bomb");
  gibs.length = 0;
  explode(dim, { x: 0.5, y: 64.6, z: 5.2 }, { ...pb, special: { ...pb.special, gib_burst: false } }, p);
  await tick(1);
  expect(gibs.filter((g) => g.zombie?.id === z.id).length).toBe(0);     // 体力が多いと手足は千切れない
  explode(dim, { x: 0.5, y: 64.6, z: 5.2 }, pb, p);
  await tick(1);
  expect(gibs.filter((g) => g.zombie?.id === z.id).length).toBeGreaterThan(0);
});

test("weapon_state: 手の武器の名前・耐久・弾・弾倉を HUD へ（持ち替えた時と減った時）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 300 });
  await tick(5);
  await hit(p, z, { part: "torso" });
  await tick(5);
  const st = rec.state.filter((s) => s.player.id === p.id).pop();
  expect(st.name).toBe(W("machete").ja);
  expect(st.kind).toBe("melee");
  expect(st.durability).toBeGreaterThan(0.99);
  expect(st.durability).toBeLessThan(1);
  expect(st.ammo).toBe(-1);
  expect(st.mag).toBe(-1);
  give(p, stack("nr:scrap", 3), 0);
  await tick(5);
  const st2 = rec.state.filter((s) => s.player.id === p.id).pop();
  expect(st2.name).toBe("");
  expect(st2.durability).toBe(-1);
});
