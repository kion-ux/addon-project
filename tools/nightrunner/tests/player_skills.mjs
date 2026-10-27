// プレイヤー: 経験値・レベル・スキル（player/skills.js）— レベルの曲線・ポイント・購入と前提・保存・
// パルクールと戦闘の経験値（ゴアのコンボを二重に数えない・夜は 2 倍）・デバッグのコマンド
import { test, tick, expect, used, spawnZombie, setTime, scriptEvent } from "nr-test";
import { emit } from "../scripts/core/bus.js";
import { initHp } from "../scripts/core/hp.js";
import { applyHit } from "../scripts/gore/gore.js";
import { shapesReady } from "../scripts/gore/hitloc.js";
import { runner, rec } from "./player_util.js";
import {
  levelFromXp, addXp, xpOf, levelOf, pointsOf, buySkill, canBuy, hasSkill, ownedSkills, skillNum, grantSkill, resetSkills, progressOf,
  SKILLS_KEY, XP_KEY,
} from "../scripts/player/skills.js";
import { hasSkill as combatHasSkill } from "../scripts/combat/common.js";
import { PROGRESSION, XP_TO_NEXT, SKILLS } from "../scripts/data/skills.js";
import { GORE_COMBOS } from "../scripts/data/settings.js";

const CXP = PROGRESSION.combat_xp;
const PXP = PROGRESSION.parkour_xp;

test("スキル: レベルは XP_TO_NEXT の累計（1 から）", () => {
  expect(levelFromXp(0).level).toBe(1);
  expect(levelFromXp(XP_TO_NEXT[1] - 1).level).toBe(1);
  expect(levelFromXp(XP_TO_NEXT[1]).level).toBe(2);
  expect(levelFromXp(XP_TO_NEXT[1] + XP_TO_NEXT[2]).level).toBe(3);
  expect(levelFromXp(XP_TO_NEXT[1] + 10).into).toBe(10);
  expect(levelFromXp(1e9).level).toBe(PROGRESSION.max_level);
});

test("スキル: 経験値でレベルが上がるとバス level_up・音・ポイント（木ごと）、経験値は動的プロパティ nr:xp に保存", async () => {
  const p = await runner();
  expect(pointsOf(p, "parkour")).toBe(0);
  addXp(p, "parkour", XP_TO_NEXT[1] + 5, "test");
  expect(levelOf(p, "parkour")).toBe(2);
  expect(pointsOf(p, "parkour")).toBe(PROGRESSION.points_per_level);
  expect(pointsOf(p, "combat")).toBe(0);
  expect(rec.level.length).toBe(1);
  expect(rec.level[0].tree).toBe("parkour");
  expect(used().sounds["nr.pl.levelup"]).toBe(1);
  addXp(p, "combat", 7, "test");
  await tick(21);
  const saved = JSON.parse(String(p.getDynamicProperty(XP_KEY)));
  expect(saved.parkour).toBe(XP_TO_NEXT[1] + 5);
  expect(saved.combat).toBe(7);
  expect(progressOf(p).parkour.level).toBe(2);
});

test("スキル: ポイントと前提が無ければ買えない。買うと nr:skills（JSON {鍵: 1}）に書き、combat の既定の読み方でも持っている", async () => {
  const p = await runner();
  expect(canBuy(p, "second_wind").reason).toBe("points");
  addXp(p, "parkour", XP_TO_NEXT[1] + XP_TO_NEXT[2]);
  expect(canBuy(p, "wall_run").reason).toBe("requires:speed_vault");
  expect(buySkill(p, "second_wind").ok).toBe(true);
  expect(hasSkill(p, "second_wind")).toBe(true);
  expect(buySkill(p, "second_wind").reason).toBe("owned");
  expect(pointsOf(p, "parkour")).toBe(1);
  expect(JSON.parse(String(p.getDynamicProperty(SKILLS_KEY)))).toEqual({ second_wind: 1 });
  expect(combatHasSkill(p, "second_wind")).toBe(true);
  expect(canBuy(p, "power_attack").reason).toBe("points");
  resetSkills(p);
  expect(ownedSkills(p)).toEqual([]);
  expect(pointsOf(p, "parkour")).toBe(2);
});

test("スキル: skillNum は _add を足し、_mult を掛け、無ければ既定値", async () => {
  const p = await runner({ skills: ["second_wind", "safe_roll", "climb_sprint"] });
  expect(skillNum(p, "stamina_max_add", 0)).toBe(10);
  expect(skillNum(p, "climb_speed_mult", 1)).toBe(1.35);
  expect(skillNum(p, "roll_fall_mult", 0.4)).toBe(0.15);
  expect(skillNum(p, "glide_sink_mult", 1)).toBe(1);
  expect(skillNum(p, "roll_window_ticks", 6)).toBe(8);
});

test("スキル: パルクールの技の経験値（バス parkour → parkour_xp）", async () => {
  const p = await runner();
  emit("parkour", { player: p, move: "vault" });
  emit("parkour", { player: p, move: "climb_block" });
  emit("parkour", { player: p, move: "glide_s" });
  emit("parkour", { player: p, move: "hard_land" });
  expect(xpOf(p, "parkour")).toBeCloseTo(PXP.vault + PXP.climb_per_block + PXP.glide_per_s, 5);
  emit("xp", { player: p, tree: "parkour", amount: PXP.chase_escape_per_level, reason: "chase" });
  expect(xpOf(p, "parkour")).toBeCloseTo(PXP.vault + PXP.climb_per_block + PXP.glide_per_s + PXP.chase_escape_per_level, 5);
});

test("スキル: 仕留めると種類（cls）の経験値。夜は night_mult 倍", async () => {
  await shapesReady;
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.5 });
  initHp(z, 10);
  await tick(1);
  applyHit(z, { attacker: p, source: "melee", dtype: "blunt", weight: "medium", damage: 999, part: "torso", noGore: true });
  await tick(2);
  expect(xpOf(p, "combat")).toBe(CXP.common);
  expect(rec.combo.at(-1).kills).toBe(1);
  setTime(18000);
  const z2 = spawnZombie("office_worker", { x: 2.5, y: 64, z: 2.5 });
  initHp(z2, 10);
  await tick(1);
  applyHit(z2, { attacker: p, source: "melee", dtype: "blunt", weight: "medium", damage: 999, part: "torso", noGore: true });
  await tick(2);
  expect(xpOf(p, "combat")).toBe(CXP.common + CXP.common * CXP.night_mult);
});

test("スキル: 首を飛ばして仕留めると「斬首」1 つだけ（SEVER・HEADSHOT と二重に数えない）＋種類の経験値", async () => {
  await shapesReady;
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.5 });
  initHp(z, 400);
  await tick(1);
  applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", damage: 50, part: "head", outcome: "severed" });
  await tick(2);
  const c = rec.combo.at(-1);
  expect(c.list.map((r) => r.key)).toEqual(["decapitated"]);
  expect(xpOf(p, "combat")).toBe(GORE_COMBOS.decapitated.xp + CXP.common);
});

test("スキル: 腕を 2 本落とすと「部位切断 ×2」、3 体を続けて仕留めると「まとめて仕留めた」", async () => {
  await shapesReady;
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.5 });
  initHp(z, 900);
  await tick(1);
  applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", damage: 5, part: "arm_r", outcome: "cut_upper" });
  applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", damage: 5, part: "arm_l", outcome: "cut_upper" });
  await tick(2);
  const row = rec.combo.at(-1).list.find((r) => r.key === "dismember");
  expect(row?.n).toBe(2);
  expect(row?.xp).toBe(GORE_COMBOS.dismember.xp * 2);
  for (let i = 0; i < 3; i++) {
    const zi = spawnZombie("office_worker", { x: 4.5 + i * 2, y: 64, z: 2.5 });
    initHp(zi, 10);
    await tick(1);
    applyHit(zi, { attacker: p, source: "melee", dtype: "blunt", weight: "medium", damage: 999, part: "torso", noGore: true });
    await tick(5);
  }
  expect(rec.combo.some((c) => c.list.some((r) => r.key === "multi_kill"))).toBe(true);
});

test("スキル: /scriptevent nr:skill all で全部、reset で外す。nr:xp で経験値", async () => {
  const p = await runner();
  await scriptEvent("nr:skill", "all", p);
  expect(ownedSkills(p).length).toBe(SKILLS.length);
  await scriptEvent("nr:skill", "reset", p);
  expect(ownedSkills(p).length).toBe(0);
  await scriptEvent("nr:skill", "wall_run", p);
  expect(hasSkill(p, "wall_run")).toBe(true);
  await scriptEvent("nr:xp", "combat 150", p);
  expect(xpOf(p, "combat")).toBe(150);
  expect(grantSkill(p, "no_such_skill")).toBe(false);
});
