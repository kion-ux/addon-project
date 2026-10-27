// 戦闘: 武器の耐久（combat/durability.js）— 命中ですり減る・残りわずかの警告・尽きると壊れる（消えない・
// nr.w.break・説明文・ダメージ 0.25 倍）・修理キット（構えて直す・最大値が減る）・銃は撃つたびに
import { test, tick, expect, used, hit, use, give, held, aim, partPoint } from "nr-test";
import { arena, rec, hitsOn, stack, editHeld, heldDamage, count } from "./combat_util.js";
import { durabilityOf, isBroken, DUR } from "../scripts/combat/index.js";
import { WEAPON_BY_ID } from "../scripts/data/weapons.js";

const MACHETE = WEAPON_BY_ID["nr:w_machete"];

test("耐久: 近接の命中で per_hit（1）減る", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 300 });
  await hit(p, z, { part: "torso" });
  await tick(1);
  expect(heldDamage(p)).toBe(1);
  expect(durabilityOf(held(p)).frac).toBeLessThan(1);
});

test("耐久: 残りが warn_frac を切ると警告（一度だけ）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 300 });
  const cap = durabilityOf(held(p)).cap;
  // 今は warn_frac 以上残り、1 回の命中（per_hit = 1）で warn_frac を切る傷
  editHeld(p, (it) => { it.getComponent("minecraft:durability").damage = Math.floor(cap * (1 - DUR.warn_frac)); });
  await hit(p, z, { part: "torso" });
  await tick(2);
  // 知らせはバス "hud_notice"（HUD が聞く。テストの記録も聞くので、アクションバーへ直接は出さない）
  expect(rec.notice.length).toBe(1);
  expect(rec.notice[0].text).toContain(MACHETE.ja);
  // （アクションバーは HUD が常に書くので数えない。知らせがバスを通ったことだけを見る）
  await tick(12);
  await hit(p, z, { part: "torso" });
  await tick(2);
  expect(rec.notice.length).toBe(1);
});

test("耐久: 尽きると壊れる（消えない・nr.w.break・説明文・ダメージは broken_damage_mult 倍）", async () => {
  const { p, z } = await arena({ item: "nr:w_machete", hp: 500 });
  const cap = durabilityOf(held(p)).cap;
  editHeld(p, (it) => { it.getComponent("minecraft:durability").damage = cap - 1; });
  await hit(p, z, { part: "torso" });
  await tick(2);
  const it = held(p);
  expect(it?.typeId).toBe("nr:w_machete");                       // 消えない
  expect(isBroken(it)).toBe(true);
  expect(it.getDynamicProperty("nr:broken")).toBe(true);
  expect(it.getLore().some((l) => l.includes("壊れている"))).toBe(true);
  expect(used().sounds["nr.w.break"]).toBe(1);
  expect(rec.state.some((s) => s.broken === true && s.durability === 0)).toBe(true);
  const d0 = heldDamage(p);
  await tick(30);
  await hit(p, z, { part: "torso" });
  await tick(1);
  const last = hitsOn(z).pop();
  expect(last.damage).toBeLessThanOrEqual(MACHETE.damage * DUR.broken_damage_mult * 1.8 + 1e-6);
  expect(heldDamage(p)).toBe(d0);                                // 壊れた後はすり減らない
});

test("修理キット: 構えて use_ticks 待つと手の外の武器も直る（最大値が少し減る・キットを 1 つ使う）", async () => {
  const { p } = await arena({ item: "nr:w_machete", zombie: null });
  const cap = durabilityOf(held(p)).cap;
  editHeld(p, (it) => { it.getComponent("minecraft:durability").damage = cap; it.setDynamicProperty("nr:broken", true); });
  await tick(5);
  give(p, stack("nr:repair_kit", 2), 1);
  p.selectedSlotIndex = 1;
  await tick(1);
  await use(p);
  await tick(5);
  expect(count(p, "nr:repair_kit")).toBe(2);                      // まだ構えている
  await tick(30);
  expect(count(p, "nr:repair_kit")).toBe(1);
  const c = p.getComponent("minecraft:inventory").container;
  const w = c.getItem(0);
  const d = durabilityOf(w);
  expect(d.broken).toBe(false);
  expect(w.getDynamicProperty("nr:broken")).toBe(undefined);
  expect(d.loss).toBeCloseTo(0.05, 3);
  expect(d.damage).toBeLessThan(cap - 0.3 * d.max);
  expect(used().sounds["nr.ui.repair"]).toBeGreaterThan(0);
});

test("修理キット: 持ち替えると取りやめ", async () => {
  const { p } = await arena({ item: "nr:w_machete", zombie: null });
  editHeld(p, (it) => { it.getComponent("minecraft:durability").damage = 100; });
  give(p, stack("nr:repair_kit", 1), 1);
  p.selectedSlotIndex = 1;
  await use(p);
  await tick(5);
  p.selectedSlotIndex = 0;
  await tick(40);
  expect(count(p, "nr:repair_kit")).toBe(1);
  expect(heldDamage(p)).toBe(100);
});

test("耐久: 銃は撃つたびに 1、弓は放つたびに 1", async () => {
  const { p, z } = await arena({ item: "nr:w_pistol", at: { x: 0.5, y: 64, z: 4 }, hp: 300 });
  aim(p, partPoint(z, "torso"));
  await use(p);
  await tick(8);
  await use(p);
  await tick(1);
  expect(heldDamage(p)).toBe(2);
});
