// プレイヤー: パルクール（player/parkour.js）— 乗り越え・壁登り・縁つかまり・壁走りと壁蹴り・スライディング・
// 受け身と重い着地・ゴミ袋・ドロップキック・グラップリングフック・パラグライダー・掴まれた状態
import { test, tick, expect, used, fill, setBlock, spawnZombie, hit, use, aim, press, setInput } from "nr-test";
import { emit } from "../scripts/core/bus.js";
import { initHp } from "../scripts/core/hp.js";
import { runner, rec, moves, hp, sprint, tapJump, tapSneak, untilGround, until } from "./player_util.js";
import { parkourState, isGrabbed, COST, fallDamage } from "../scripts/player/parkour.js";
import { staminaOf, setStamina, STAMINA } from "../scripts/player/stamina.js";
import { PARKOUR_TUNING } from "../scripts/data/settings.js";

const PT = PARKOUR_TUNING;
const STONE = "minecraft:stone";

// ---------------------------------------------------------------------------
//  乗り越え
// ---------------------------------------------------------------------------
test("乗り越え: ダッシュ中に 1 段の障害物へジャンプすると vault で越える（スタミナ vault）", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 3 }, { x: 3, y: 64, z: 3 }, STONE);
  await sprint(p, 4);
  const s0 = staminaOf(p).value;
  await tapJump(p);
  await tick(1);
  expect(parkourState(p).mode).toBe("vault");
  expect(moves(p)).toContain("vault");
  expect(used().anims["animation.nr.p.vault"]).toBe(1);
  expect(used().sounds["nr.pk.vault"]).toBe(1);
  expect(staminaOf(p).value).toBe(s0 - STAMINA.jump - COST.vault);
  await tick(14);
  expect(p.location.z).toBeGreaterThan(4);
});

test("乗り越え: スキル speed_vault なら 2 段も vault_high で越える", async () => {
  const p = await runner({ skills: ["speed_vault"] });
  fill({ x: -3, y: 64, z: 3 }, { x: 3, y: 65, z: 3 }, STONE);
  await sprint(p, 4);
  await tapJump(p);
  await tick(1);
  expect(parkourState(p).mode).toBe("vault");
  expect(rec.parkour.find((d) => d.move === "vault")?.high).toBe(true);
  expect(used().anims["animation.nr.p.vault_high"]).toBe(1);
  await tick(25);
  expect(p.location.z).toBeGreaterThan(4);
});

test("乗り越え: 2 段の壁はスキルが無ければ vault しない（縁つかまりになる）・息切れ中もしない", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 3 }, { x: 3, y: 65, z: 3 }, STONE);
  await sprint(p, 4);
  await tapJump(p);
  await tick(1);
  expect(parkourState(p).mode).not.toBe("vault");
  const q = await runner({ at: { x: 10.5, y: 64, z: 0.5 } });
  fill({ x: 7, y: 64, z: 3 }, { x: 13, y: 64, z: 3 }, STONE);
  setStamina(q, 5);
  await sprint(q, 4);
  await tapJump(q);
  await tick(1);
  expect(parkourState(q).mode).toBe("");
});

// ---------------------------------------------------------------------------
//  壁登り・縁つかまり・よじ登り
// ---------------------------------------------------------------------------
test("壁登り: 壁に向かってジャンプを長押しすると登り（climb_loop・スタミナが減る）、天辺で mantle して上に立つ", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 1 }, { x: 3, y: 73, z: 1 }, STONE);
  await press(p, "Jump", true);
  await tick(8);
  expect(parkourState(p).mode).toBe("climb");
  expect(used().anims["animation.nr.p.climb_loop"]).toBe(1);
  const y1 = p.location.y, s1 = staminaOf(p).value;
  await tick(10);
  expect(p.location.y).toBeGreaterThan(y1 + 0.8);
  expect(staminaOf(p).value).toBeLessThan(s1 - COST.climb * 8);
  expect(await until(() => parkourState(p).mode === "mantle", 80)).toBeGreaterThan(-1);
  await press(p, "Jump", false);
  expect(used().anims["animation.nr.p.mantle"]).toBe(1);
  expect(await until(() => p.isOnGround && p.location.y > 73.9, 40)).toBeGreaterThan(-1);
  expect(p.location.z).toBeGreaterThan(1);
  expect(moves(p).filter((m) => m === "climb_block").length).toBeGreaterThan(3);
});

test("壁登り: ジャンプを離すと止まって落ちる", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 1 }, { x: 3, y: 73, z: 1 }, STONE);
  await press(p, "Jump", true);
  await tick(12);
  expect(parkourState(p).mode).toBe("climb");
  await press(p, "Jump", false);
  await tick(1);
  expect(parkourState(p).mode).toBe("");
  expect(await untilGround(p, 60)).toBeGreaterThan(0);
});

test("縁つかまり: 3 段の壁へ軽くジャンプすると縁にぶら下がり（ledge_hang）、ジャンプでよじ登る", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 1 }, { x: 3, y: 66, z: 1 }, STONE);
  await tapJump(p);
  expect(await until(() => parkourState(p).mode === "hang", 20)).toBeGreaterThan(-1);
  expect(used().anims["animation.nr.p.ledge_hang"]).toBe(1);
  await tick(10);
  expect(parkourState(p).mode).toBe("hang");
  expect(p.location.y).toBeGreaterThan(64.8);
  await tapJump(p);
  await tick(1);
  expect(parkourState(p).mode).toBe("mantle");
  expect(await until(() => p.isOnGround && p.location.y > 66.9, 40)).toBeGreaterThan(-1);
  expect(p.location.z).toBeGreaterThan(1);
});

test("縁つかまり: スニークで手を離して落ちる", async () => {
  const p = await runner();
  fill({ x: -3, y: 64, z: 1 }, { x: 3, y: 66, z: 1 }, STONE);
  await tapJump(p);
  await until(() => parkourState(p).mode === "hang", 20);
  await tapSneak(p);
  await tick(1);
  expect(parkourState(p).mode).toBe("");
  expect(used().anims["animation.nr.p.none"]).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------
//  壁走り・壁蹴り
// ---------------------------------------------------------------------------
test("壁走り: スキル wall_run があれば、右の壁沿いにダッシュジャンプ（長押し）で壁を走る（wallrun_r）→ 壁蹴り", async () => {
  const p = await runner({ skills: ["wall_run", "wall_jump"] });
  fill({ x: -1, y: 64, z: -2 }, { x: -1, y: 67, z: 30 }, STONE);
  await sprint(p, 3);
  await press(p, "Jump", true);
  expect(await until(() => parkourState(p).mode === "wallrun", 10)).toBeGreaterThan(-1);
  expect(used().anims["animation.nr.p.wallrun_r"]).toBe(1);
  expect(moves(p)).toContain("wallrun");
  const z0 = p.location.z;
  await tick(8);
  expect(p.location.z - z0).toBeGreaterThan(2.5);
  expect(p.isOnGround).toBe(false);
  expect(used().particles["nr:wall_scrape"]).toBeGreaterThan(0);
  const x0 = p.location.x;
  await press(p, "Jump", false);
  await press(p, "Jump", true);
  await tick(1);
  expect(moves(p)).toContain("walljump");
  expect(used().anims["animation.nr.p.wall_jump"]).toBe(1);
  await tick(3);
  expect(p.location.x).toBeGreaterThan(x0 + 1);
});

test("壁走り: 左の壁なら wallrun_l、スキルが無ければ走らない", async () => {
  const p = await runner({ skills: ["wall_run"] });
  fill({ x: 1, y: 64, z: -2 }, { x: 1, y: 67, z: 30 }, STONE);
  await sprint(p, 3);
  await press(p, "Jump", true);
  expect(await until(() => parkourState(p).mode === "wallrun", 10)).toBeGreaterThan(-1);
  expect(used().anims["animation.nr.p.wallrun_l"]).toBe(1);
  const q = await runner({ at: { x: 20.5, y: 64, z: 0.5 } });
  fill({ x: 19, y: 64, z: -2 }, { x: 19, y: 67, z: 30 }, STONE);
  await sprint(q, 3);
  await press(q, "Jump", true);
  await tick(8);
  expect(parkourState(q).mode).toBe("");
});

// ---------------------------------------------------------------------------
//  スライディング
// ---------------------------------------------------------------------------
test("スライディング: ダッシュ中にスニークで滑る（速さが乗って遠くへ・dust_slide・スタミナ slide）", async () => {
  const p = await runner();
  await sprint(p, 5);
  const z0 = p.location.z, s0 = staminaOf(p).value;
  await press(p, "Sneak", true);
  await tick(1);
  expect(parkourState(p).mode).toBe("slide");
  expect(staminaOf(p).value).toBe(s0 - COST.slide);
  await tick(10);
  expect(p.location.z - z0).toBeGreaterThan(2);
  expect(used().anims["animation.nr.p.slide"]).toBe(1);
  expect(used().particles["nr:dust_slide"]).toBeGreaterThan(0);
  await tick(20);
  expect(parkourState(p).mode).toBe("");
});

test("スライディング: スキル slide_tackle なら前の感染者の脚を払って倒す", async () => {
  const p = await runner({ skills: ["slide_tackle"] });
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 5.5 });
  initHp(z, 300);
  await sprint(p, 4);
  await press(p, "Sneak", true);
  await tick(12);
  const r = rec.hits.find((h) => h.attacker === p && h.dtype === "blunt" && /^leg_/.test(h.part));
  expect(r).toBeTruthy();
  expect(r.knockdown).toBe(true);
});

// ---------------------------------------------------------------------------
//  着地
// ---------------------------------------------------------------------------
test("受け身: 着地の直前にスニークで前転し、落下ダメージは (落下 − safe_height) × fall_dmg_mult", async () => {
  const p = await runner({ at: { x: 0.5, y: 73, z: 0.5 } });
  await until(() => p.location.y < 66, 60);
  await tapSneak(p);
  expect(await untilGround(p, 20)).toBeGreaterThan(0);
  await tick(2);
  expect(moves(p)).toContain("roll");
  expect(hp(p)).toBe(20 - Math.round((9 - PT.fall.safe_height) * PT.roll.fall_dmg_mult));
  expect(used().anims["animation.nr.p.roll"]).toBe(1);
  expect(used().sounds["nr.pk.roll"]).toBe(1);
});

test("重い着地: 受け身なしの高い落下は hard_land・鈍足・音（ゾンビへの noise）、ダメージは安全な高さを超えた分だけ", async () => {
  const p = await runner({ at: { x: 0.5, y: 73, z: 0.5 } });
  expect(await untilGround(p, 60)).toBeGreaterThan(0);
  await tick(1);
  expect(moves(p)).toContain("hard_land");
  expect(hp(p)).toBe(20 - (9 - PT.fall.safe_height));
  expect(used().anims["animation.nr.p.hard_land"]).toBe(1);
  expect(used().sounds["nr.pk.land_hard"]).toBe(1);
  expect(p.getEffect("slowness")).toBeTruthy();
  expect(rec.noise.some((n) => n.source === "landing")).toBe(true);
});

test("落下: 安全な高さ（safe_height）までは無傷、ゴミ袋（タグ landing）の上は高くても無傷", async () => {
  const p = await runner({ at: { x: 0.5, y: 69, z: 0.5 } });
  await untilGround(p, 60);
  await tick(1);
  expect(hp(p)).toBe(20);
  setBlock({ x: 5, y: 64, z: 0 }, "nr:trash_bags");
  const q = await runner({ at: { x: 5.5, y: 74, z: 0.5 } });
  await untilGround(q, 60);
  await tick(1);
  expect(hp(q)).toBe(20);
  expect(moves(q)).toContain("landing_pile");
  expect(fallDamage(q, 20, false, true)).toBe(0);
  expect(fallDamage(q, 20, true, false)).toBe(Math.round((20 - PT.fall.safe_height) * PT.roll.fall_dmg_mult));
});

// ---------------------------------------------------------------------------
//  ドロップキック
// ---------------------------------------------------------------------------
test("ドロップキック: スキル dropkick・空中でスニーク＋攻撃で、重い打撃の applyHit と大きな吹き飛び", async () => {
  const p = await runner({ skills: ["dropkick"] });
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.6 });
  initHp(z, 300);
  await tick(2);
  const s0 = staminaOf(p).value;
  await tapJump(p);
  await tick(6);
  await press(p, "Sneak", true);
  await hit(p, z, { part: "torso" });
  expect(moves(p)).toContain("dropkick");
  const r = rec.hits.find((h) => h.attacker === p && h.dtype === "blunt" && h.weight === "heavy" && h.source === "melee");
  expect(r).toBeTruthy();
  await tick(1);
  expect(z.getVelocity().z).toBeGreaterThan(1);
  expect(staminaOf(p).value).toBeLessThan(s0 - COST.dropkick + 0.01);
  expect(used().anims["animation.nr.p.dropkick"]).toBe(1);
  expect(used().particles["nr:kick_impact"]).toBeGreaterThan(0);
});

test("ドロップキック: 地面の上・スキルなしでは出ない", async () => {
  const p = await runner({ skills: ["dropkick"] });
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.6 });
  initHp(z, 300);
  await tick(2);
  await press(p, "Sneak", true);
  await hit(p, z);
  expect(moves(p)).not.toContain("dropkick");
  const q = await runner({ at: { x: 8.5, y: 64, z: 0.5 } });
  const z2 = spawnZombie("office_worker", { x: 8.5, y: 64, z: 2.6 });
  initHp(z2, 300);
  await tick(2);
  await tapJump(q);
  await tick(6);
  await press(q, "Sneak", true);
  await hit(q, z2);
  expect(moves(q)).not.toContain("dropkick");
});

// ---------------------------------------------------------------------------
//  道具
// ---------------------------------------------------------------------------
test("グラップリングフック: 壁を狙って使うと鉤が飛び（grapple_line）、体ごと引き寄せられる", async () => {
  const p = await runner({ item: "nr:grappling_hook" });
  fill({ x: -2, y: 64, z: 12 }, { x: 2, y: 72, z: 12 }, STONE);
  aim(p, { x: 0.5, y: 70.5, z: 12 });
  await use(p);
  expect(parkourState(p).mode).toBe("grapple");
  expect(used().sounds["nr.pk.grapple_fire"]).toBe(1);
  expect(used().anims["animation.nr.p.grapple_fire"]).toBe(1);
  expect(await until(() => parkourState(p).mode === "", 60)).toBeGreaterThan(-1);
  expect(moves(p)).toContain("grapple");
  expect(p.location.z).toBeGreaterThan(9);
  expect(p.location.y).toBeGreaterThan(66);
  expect(used().particles["nr:grapple_line"]).toBeGreaterThan(3);
  expect(used().anims["animation.nr.p.grapple_pull"]).toBe(1);
  // 待ち時間の間は撃てない
  aim(p, { x: 0.5, y: 70.5, z: 12 });
  await use(p);
  expect(parkourState(p).mode).toBe("");
});

test("グラップリングフック: 何も無い空・近すぎる所には撃てない", async () => {
  const p = await runner({ item: "nr:grappling_hook" });
  aim(p, { x: 0.5, y: 90, z: 10 });
  await use(p);
  expect(parkourState(p).mode).toBe("");
  expect(used().sounds["nr.ui.error"]).toBe(1);
});

test("パラグライダー: 空中で使うと開いてゆっくり前へ滑空（低速落下）、スニークで畳む", async () => {
  const p = await runner({ at: { x: 0.5, y: 84, z: 0.5 }, item: "nr:paraglider" });
  await tick(2);
  await use(p);
  expect(parkourState(p).mode).toBe("glide");
  expect(used().anims["animation.nr.p.glide"]).toBe(1);
  expect(used().sounds["nr.pk.glider_open"]).toBe(1);
  const y0 = p.location.y, z0 = p.location.z;
  await tick(20);
  expect(y0 - p.location.y).toBeLessThan(4);
  expect(p.location.z - z0).toBeGreaterThan(6);
  expect(p.getEffect("slow_falling")).toBeTruthy();
  expect(moves(p)).toContain("glide_s");
  await tapSneak(p);
  await tick(1);
  expect(parkourState(p).mode).toBe("");
});

test("パラグライダー: 地面では開かない", async () => {
  const p = await runner({ item: "nr:paraglider" });
  await use(p);
  expect(parkourState(p).mode).toBe("");
});

// ---------------------------------------------------------------------------
//  掴まれた
// ---------------------------------------------------------------------------
test("掴まれた: バス grabbed で動けず（鈍足）もがき、ジャンプ・攻撃の連打で振りほどくとバス shove", async () => {
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 1.6 });
  initHp(z, 300);
  await tick(1);
  emit("grabbed", { player: p, zombie: z });
  expect(isGrabbed(p)).toBe(true);
  expect(used().anims["animation.nr.p.grabbed_struggle"]).toBe(1);
  expect(used().sounds["nr.pl.grabbed"]).toBe(1);
  await tick(1);
  expect(p.getEffect("slowness")?.amplifier).toBe(7);
  for (let i = 0; i < 7; i++) { await tapJump(p); await tick(2); }
  expect(rec.shove.length).toBe(0);
  expect(staminaOf(p).value).toBe(PT.stamina.max);       // 振りほどく連打はジャンプのスタミナを使わない
  await hit(p, z);
  expect(rec.shove.length).toBe(1);
  expect(rec.shove[0].zombie).toBe(z);
  expect(rec.shove[0].player).toBe(p);
  expect(isGrabbed(p)).toBe(false);
  expect(used().anims["animation.nr.p.shove"]).toBe(1);
});

test("掴まれた: ゾンビ側の grab_end・ゾンビが消えたら離れる", async () => {
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 1.6 });
  await tick(1);
  emit("grabbed", { player: p, zombie: z });
  emit("grab_end", { player: p, zombie: z });
  expect(isGrabbed(p)).toBe(false);
  emit("grabbed", { player: p, zombie: z });
  z.remove();
  await tick(2);
  expect(isGrabbed(p)).toBe(false);
  await setInput(p, { y: 0 });
});
