// プレイヤー: 免疫（player/immunity.js）— 暗さで減る・UV ランプとアイテムで戻る・0 のダメージ・警告・設定
import { test, tick, expect, used, fill, setBlock, setLight, completeUse, mc } from "nr-test";
import { emit } from "../scripts/core/bus.js";
import { runner, rec, hp, setSetting } from "./player_util.js";
import { immunityOf, setImmunity, lightInfo, lampCount, IMMUNITY, IMMUNITY_KEY, DAYLIGHT_REGEN_PER_S } from "../scripts/player/immunity.js";
import { PARKOUR_TUNING } from "../scripts/data/settings.js";

const IM = PARKOUR_TUNING.immunity;
const system = mc.system;
const NIGHT = 18000;

test("免疫: 昼の屋外では減らない", async () => {
  const p = await runner();
  await tick(100);
  expect(immunityOf(p).value).toBe(IM.max_s);
  expect(immunityOf(p).dark).toBe(false);
});

test("免疫: 夜の屋外では drain_per_s ずつ減る（暗さは light ≤ dark_light_level）", async () => {
  const p = await runner({ time: NIGHT });
  await tick(100);
  const im = immunityOf(p);
  expect(im.dark).toBe(true);
  expect(im.draining).toBe(true);
  expect(im.value).toBeCloseTo(IM.max_s - IM.drain_per_s * 5, 0);
  expect(lightInfo(p).eff).toBeLessThan(IM.dark_light_level + 0.01);
});

test("免疫: 昼でも屋根の下の暗がりでは減り、松明の近くでは夜でも減らない", async () => {
  const p = await runner();
  fill({ x: -4, y: 67, z: -4 }, { x: 4, y: 67, z: 4 }, "minecraft:stone");
  await tick(60);
  expect(immunityOf(p).dark).toBe(true);
  expect(immunityOf(p).value).toBeLessThan(IM.max_s - 2);
  const q = await runner({ time: NIGHT, at: { x: 20.5, y: 64, z: 0.5 } });
  setBlock({ x: 21, y: 64, z: 1 }, "minecraft:torch");
  await tick(60);
  expect(immunityOf(q).dark).toBe(false);
  expect(immunityOf(q).value).toBe(IM.max_s);
});

test("免疫: 実機の getLightLevel が時刻で暗くならない時（空の光 = 全体の光）も、夜は暗く、近くの光源で明るい", async () => {
  const p = await runner({ time: NIGHT });
  setLight(15);
  await tick(20);
  expect(lightInfo(p).dark).toBe(true);
  setBlock({ x: 1, y: 64, z: 1 }, "minecraft:torch");
  await tick(20);
  expect(lightInfo(p).dark).toBe(false);
  expect(immunityOf(p).dark).toBe(false);
});

test("免疫: UV ランプ（nr:uv_lamp・nr:powered）の範囲では夜でも uv_regen で戻る", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, 100);
  setBlock({ x: 3, y: 64, z: 0 }, "nr:uv_lamp");
  await tick(25);
  expect(lampCount()).toBeGreaterThan(0);
  const v = immunityOf(p).value;
  await tick(40);
  expect(immunityOf(p).uv).toBe(true);
  expect(immunityOf(p).value).toBeGreaterThan(v + IM.uv_regen_per_s * 1.5);
  // 消えたランプ（nr:powered = 0）は効かない
  setBlock({ x: 3, y: 64, z: 0 }, "minecraft:air");
  setBlock({ x: 3, y: 64, z: 0 }, "nr:uv_lamp", { "nr:powered": 0, "minecraft:cardinal_direction": "north" });
  await tick(25);
  expect(immunityOf(p).uv).toBe(false);
});

test("免疫: 昼の日なたではゆっくり戻る", async () => {
  const p = await runner();
  setImmunity(p, 100);
  await tick(100);
  expect(immunityOf(p).value).toBeCloseTo(100 + DAYLIGHT_REGEN_PER_S * 5, 0);
});

test("免疫: 免疫アンプルで immunity_s 戻り pause_s の間は減らない。UV キノコでも戻る", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, 50);
  await completeUse(p, "nr:immunity_booster");
  expect(immunityOf(p).value).toBe(230);
  expect(immunityOf(p).paused).toBe(true);
  expect(used().sounds["nr.pl.immunity_restore"]).toBe(1);
  await tick(100);
  expect(immunityOf(p).value).toBe(230);
  await completeUse(p, "nr:uv_shroom");
  expect(immunityOf(p).value).toBe(275);
  expect(rec.immunity.filter((d) => d.kind === "restore").length).toBe(2);
});

test("免疫: バス immunity_restore・uv_zone でも戻る", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, 100);
  emit("immunity_restore", { player: p, seconds: 30, source: "uv_mod" });
  expect(immunityOf(p).value).toBe(130);
  emit("uv_zone", { dim: p.dimension, pos: p.location, radius: 6, until: system.currentTick + 40, source: "uv_flare" });
  await tick(30);
  expect(immunityOf(p).uv).toBe(true);
  expect(immunityOf(p).value).toBeGreaterThan(140);
});

test("免疫: warn_s を下回るたびに警告（音・バス）", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, IM.warn_s[0] + 1);
  await tick(50);
  const w = rec.immunity.filter((d) => d.kind === "warn");
  expect(w.length).toBe(1);
  expect(w[0].threshold).toBe(IM.warn_s[0]);
  expect(used().sounds["nr.pl.immunity_warn"]).toBe(1);
});

test("免疫: 0 になると damage_interval_ticks ごとに damage_at_zero のダメージ・心音・赤い画面・吐き気", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, 0);
  await tick(IM.damage_interval_ticks * 2 + 4);
  expect(hp(p)).toBeLessThan(20 - IM.damage_at_zero * 2 + 0.01);
  expect(rec.immunity.some((d) => d.kind === "zero")).toBe(true);
  expect(used().sounds["nr.pl.heartbeat"]).toBeGreaterThan(1);
  expect(used().camera).toBeGreaterThan(0);
  expect(p.getEffect("nausea")).toBeTruthy();
});

test("免疫: heartbeat_below_s 未満で心音が鳴る（0 でなくても）", async () => {
  const p = await runner({ time: NIGHT });
  setImmunity(p, IM.heartbeat_below_s - 5);
  await tick(45);
  expect(used().sounds["nr.pl.heartbeat"]).toBeGreaterThan(1);
  expect(hp(p)).toBe(20);
});

test("免疫: 設定 immunity_enabled が false なら減らず、満タンに戻る。値は動的プロパティに保存", async () => {
  const p = await runner({ time: NIGHT });
  await tick(200);
  expect(immunityOf(p).value).toBeLessThan(IM.max_s - 5);
  expect(p.getDynamicProperty(IMMUNITY_KEY)).toBeLessThan(IM.max_s);
  setSetting("immunity_enabled", false);
  await tick(20);
  expect(immunityOf(p).value).toBe(IM.max_s);
  expect(immunityOf(p).draining).toBe(false);
  setSetting("immunity_enabled", true);
  expect(IMMUNITY.max).toBe(IM.max_s);
});
