// プレイヤー: スタミナ（player/stamina.js）— 消費・回復の遅れ・息切れ・バス・スキル・飲み物・ジャンプ
import { test, tick, expect, used, completeUse, press } from "nr-test";
import { emit } from "../scripts/core/bus.js";
import { runner, rec, until } from "./player_util.js";
import {
  consumeStamina, staminaOf, setStamina, canAfford, isExhausted, maxStamina, STAMINA, RECOVER_AT,
} from "../scripts/player/stamina.js";
import { PARKOUR_TUNING } from "../scripts/data/settings.js";

const ST = PARKOUR_TUNING.stamina;

test("スタミナ: 使うと減り、regen_delay_ticks の間は戻らず、その後 regen_per_tick ずつ戻る", async () => {
  const p = await runner();
  expect(staminaOf(p).value).toBe(ST.max);
  expect(consumeStamina(p, 50, { reason: "test" })).toBe(true);
  expect(staminaOf(p).value).toBe(ST.max - 50);
  await tick(ST.regen_delay_ticks - 2);
  expect(staminaOf(p).value).toBe(ST.max - 50);
  await tick(12);
  const v = staminaOf(p).value;
  expect(v).toBeGreaterThan(ST.max - 50);
  expect(v).toBeLessThan(ST.max - 50 + ST.regen_per_tick * 14);
  await tick(200);
  expect(staminaOf(p).value).toBe(ST.max);
});

test("スタミナ: 足りない技は断る（force は 0 まで減らす）", async () => {
  const p = await runner();
  setStamina(p, 30);
  expect(consumeStamina(p, 40)).toBe(false);
  expect(staminaOf(p).value).toBe(30);
  expect(canAfford(p, 20)).toBe(true);
  expect(consumeStamina(p, 40, { force: true })).toBe(true);
  expect(staminaOf(p).value).toBe(0);
});

test("スタミナ: バス stamina_cost で減り（攻撃）、負の量で戻る。変わるとバス stamina を出す", async () => {
  const p = await runner();
  emit("stamina_cost", { player: p, amount: 15, reason: "melee" });
  expect(staminaOf(p).value).toBe(ST.max - 15);
  emit("stamina_cost", { player: p, amount: -5, reason: "finisher" });
  expect(staminaOf(p).value).toBe(ST.max - 10);
  const last = rec.stamina.filter((d) => d.player === p).at(-1);
  expect(last.value).toBe(ST.max - 10);
  expect(last.max).toBe(ST.max);
  expect(last.exhausted).toBe(false);
});

test("スタミナ: exhausted_below 未満で息切れ（鈍足・息の音・技を断る）、その 3 倍まで戻ると抜ける", async () => {
  const p = await runner();
  emit("stamina_cost", { player: p, amount: ST.max - 5, reason: "melee" });
  expect(isExhausted(p)).toBe(true);
  expect(rec.stamina.at(-1).exhausted).toBe(true);
  await tick(2);
  const slow = p.getEffect("slowness");
  expect(slow?.amplifier).toBe(ST.exhausted_slow_amp);
  expect(used().sounds["nr.pk.breath"]).toBeGreaterThan(0);
  expect(consumeStamina(p, 2)).toBe(false);
  // 戻る: RECOVER_AT（30）まで息切れのまま
  await until(() => staminaOf(p).value >= RECOVER_AT - 2, 200);
  expect(staminaOf(p).value).toBeLessThan(RECOVER_AT);
  expect(isExhausted(p)).toBe(true);
  await until(() => staminaOf(p).value >= RECOVER_AT, 20);
  await tick(1);
  expect(isExhausted(p)).toBe(false);
  expect(rec.stamina.at(-1).exhausted).toBe(false);
});

test("スタミナ: クリエイティブは減らない", async () => {
  const p = await runner();
  p.setGameMode("Creative");
  expect(consumeStamina(p, 60)).toBe(true);
  expect(staminaOf(p).value).toBe(ST.max);
});

test("スタミナ: スキル second_wind で最大 +10・回復 ×1.25", async () => {
  const p = await runner({ skills: ["second_wind"] });
  expect(maxStamina(p)).toBe(ST.max + 10);
  setStamina(p, 50);
  consumeStamina(p, 10);
  await tick(ST.regen_delay_ticks + 10);
  const v = staminaOf(p).value;
  // 10 tick 分の回復が 1.25 倍（偽物の tick の境目で ±1 tick）
  expect(v).toBeGreaterThan(40 + ST.regen_per_tick * 1.25 * 9 - 0.01);
  expect(v).toBeLessThan(40 + ST.regen_per_tick * 1.25 * 12 + 0.01);
});

test("スタミナ: エナジードリンクで満タン、しばらく回復が速い", async () => {
  const p = await runner();
  setStamina(p, 10);
  await completeUse(p, "nr:energy_drink");
  expect(staminaOf(p).value).toBe(ST.max);
  consumeStamina(p, 40);
  await tick(ST.regen_delay_ticks + 10);
  expect(staminaOf(p).value).toBeGreaterThan(60 + ST.regen_per_tick * 1.5 * 9 - 0.01);
});

test("スタミナ: ジャンプで jump だけ減る", async () => {
  const p = await runner();
  await press(p, "Jump", true);
  await press(p, "Jump", false);
  expect(staminaOf(p).value).toBe(ST.max - STAMINA.jump);
});
