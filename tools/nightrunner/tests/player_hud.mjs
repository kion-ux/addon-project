// プレイヤー: HUD（player/hud.js）— アクションバーの文（体力・スタミナ・免疫・武器・掴まれ）、ちらつかない間隔、
// ゴアのコンボの見出しと音、レベルアップ、見出しの優先度、設定で隠す
import { test, tick, expect, used, mark, since, spawnZombie } from "nr-test";
import { emit } from "../scripts/core/bus.js";
import { initHp } from "../scripts/core/hp.js";
import { applyHit } from "../scripts/gore/gore.js";
import { shapesReady } from "../scripts/gore/hitloc.js";
import { runner, setSetting } from "./player_util.js";
import { hudText, composeHud, lastTitle, bar, fmtTime, HUD } from "../scripts/player/hud.js";
import { consumeStamina } from "../scripts/player/stamina.js";
import { setImmunity } from "../scripts/player/immunity.js";
import { addXp } from "../scripts/player/skills.js";
import { GORE_COMBOS } from "../scripts/data/settings.js";
import { XP_TO_NEXT } from "../scripts/data/skills.js";

/** @param {any} p @param {Record<string, any>} o */
function weapon(p, o) {
  emit("weapon_state", { player: p, id: "", key: "", name: "", kind: "", durability: -1, broken: false, ammo: -1, mag: -1, magMax: 0, reloading: false, mods: {}, ...o });
}

test("HUD: 部品（棒・時間）", () => {
  expect(bar(1, 10)).toBe("■■■■■■■■■■");
  expect(bar(0.5, 10)).toBe("■■■■■□□□□□");
  expect(bar(0, 4)).toBe("□□□□");
  expect(bar(NaN, 3)).toBe("□□□");
  expect(fmtTime(300)).toBe("5:00");
  expect(fmtTime(59.2)).toBe("1:00");
  expect(fmtTime(9)).toBe("0:09");
  expect(fmtTime(-3)).toBe("0:00");
});

test("HUD: アクションバーに体力とスタミナの棒。昼で免疫が満タンなら免疫は出さない", async () => {
  const p = await runner();
  await tick(HUD.every * 2);
  const t = hudText(p);
  expect(t).toContain("❤ 20");
  expect(t).toContain("⚡ ■■■■■■■■■■");
  expect(t).not.toContain("☣");
  expect(p.onScreenDisplay.actionBar).toBe(t);
  consumeStamina(p, 50);
  await tick(HUD.every);
  expect(hudText(p)).toContain("⚡ ■■■■■□□□□□");
});

test("HUD: 夜は免疫の残り時間（減っている ▼）、少ないと色が変わる", async () => {
  const p = await runner({ time: 18000 });
  await tick(20);
  expect(hudText(p)).toContain("☣ 4:5");
  expect(hudText(p)).toContain("▼");
  setImmunity(p, 9);
  await tick(HUD.every);
  expect(hudText(p)).toContain("§c☣ 0:0");
});

test("HUD: 手の武器（バス weapon_state）: 名前・耐久・弾・装填中・破損", async () => {
  const p = await runner();
  weapon(p, { id: "nr:w_machete", key: "machete", name: "マチェーテ", kind: "melee", durability: 0.75 });
  expect(composeHud(p)).toContain("マチェーテ §a75%");
  weapon(p, { id: "nr:w_pistol", key: "pistol", name: "拳銃", kind: "gun", durability: 0.15, ammo: 24, mag: 5, magMax: 12, reloading: true });
  const t = composeHud(p);
  expect(t).toContain("拳銃 §c15%");
  expect(t).toContain("5§7/24");
  expect(t).toContain("装填中");
  weapon(p, { name: "鉄パイプ", durability: 0, broken: true });
  expect(composeHud(p)).toContain("鉄パイプ §c破損");
  weapon(p, {});
  expect(composeHud(p)).not.toContain("§f拳銃");
});

test("HUD: 変わらなければ出し直さない（keepAlive の間隔だけ）。変わればすぐ", async () => {
  const p = await runner();
  await tick(HUD.every * 3);
  const m0 = mark();
  await tick(HUD.keepAlive - HUD.every * 2);
  expect(since(m0).actionbars).toBeLessThan(2);
  const m1 = mark();
  await tick(HUD.keepAlive + HUD.every);
  expect(since(m1).actionbars).toBeGreaterThan(0);
  const m2 = mark();
  consumeStamina(p, 30);
  await tick(HUD.every);
  expect(since(m2).actionbars).toBe(1);
});

test("HUD: 掴まれている間は「振りほどけ」の連打の棒", async () => {
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 1.6 });
  await tick(1);
  emit("grabbed", { player: p, zombie: z });
  await tick(HUD.every);
  expect(hudText(p)).toContain("振りほどけ");
  emit("grab_end", { player: p });
  await tick(HUD.every);
  expect(hudText(p)).not.toContain("振りほどけ");
});

test("HUD: 首を飛ばすと見出し DECAPITATED と nr.ui.combo、頭を撃つと HEADSHOT と nr.ui.headshot", async () => {
  await shapesReady;
  const p = await runner();
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.5 });
  initHp(z, 400);
  await tick(1);
  applyHit(z, { attacker: p, source: "melee", dtype: "slash", weight: "heavy", damage: 50, part: "head", outcome: "severed" });
  await tick(2);
  expect(lastTitle(p).title).toContain(GORE_COMBOS.decapitated.en);
  expect(p.onScreenDisplay.title).toContain("DECAPITATED");
  expect(lastTitle(p).subtitle).toContain(GORE_COMBOS.decapitated.ja);
  expect(used().sounds["nr.ui.combo"]).toBe(1);
  await tick(40);
  const z2 = spawnZombie("office_worker", { x: 3.5, y: 64, z: 2.5 });
  initHp(z2, 900);
  await tick(1);
  applyHit(z2, { attacker: p, source: "hitscan", dtype: "pierce", weight: "light", damage: 1, part: "head", noGore: true });
  await tick(2);
  expect(lastTitle(p).title).toContain(GORE_COMBOS.headshot.en);
  expect(used().sounds["nr.ui.headshot"]).toBe(1);
});

test("HUD: レベルアップの見出しは小さなコンボの見出しで上書きされない", async () => {
  await shapesReady;
  const p = await runner();
  addXp(p, "parkour", XP_TO_NEXT[1]);
  expect(lastTitle(p).title).toContain("LEVEL UP");
  const z = spawnZombie("office_worker", { x: 0.5, y: 64, z: 2.5 });
  initHp(z, 900);
  await tick(1);
  applyHit(z, { attacker: p, source: "hitscan", dtype: "pierce", weight: "light", damage: 1, part: "head", noGore: true });
  await tick(2);
  expect(lastTitle(p).title).toContain("LEVEL UP");
});

test("HUD: 設定 hud_enabled が false なら消して出さない", async () => {
  const p = await runner();
  await tick(HUD.every * 2);
  expect(hudText(p)).not.toBe("");
  setSetting("hud_enabled", false);
  await tick(HUD.every);
  expect(hudText(p)).toBe("");
  expect(p.onScreenDisplay.actionBar).toBe("");
  const m = mark();
  await tick(HUD.keepAlive * 2);
  expect(since(m).actionbars).toBe(0);
  setSetting("hud_enabled", true);
});
