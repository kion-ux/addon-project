// player/ のテストの補助（tests/player_*.mjs が使う。.js はテストではなく補助として一緒に写される）
import { tick, spawnPlayer, setGround, setTime, setLight, press, setInput } from "nr-test";
import { on, EV } from "../scripts/core/bus.js";
import { reset as resetSettings, set as setSetting } from "../scripts/core/settings.js";
import { grantSkill } from "../scripts/player/skills.js";

export { setSetting };

/** バスの記録（runner() ごとに空にする）。 */
export const rec = {
  parkour: /** @type {any[]} */ ([]), shove: /** @type {any[]} */ ([]), stamina: /** @type {any[]} */ ([]),
  level: /** @type {any[]} */ ([]), combo: /** @type {any[]} */ ([]), immunity: /** @type {any[]} */ ([]),
  noise: /** @type {any[]} */ ([]), hits: /** @type {any[]} */ ([]),
};
on("parkour", (d) => rec.parkour.push(d));
on("shove", (d) => rec.shove.push(d));
on("stamina", (d) => rec.stamina.push(d));
on("level_up", (d) => rec.level.push(d));
on("gore_combo", (d) => rec.combo.push(d));
on("immunity", (d) => rec.immunity.push(d));
on("noise", (d) => rec.noise.push(d));
on(EV.HIT, (d) => rec.hits.push(d));
export function clearRec() { for (const k of Object.keys(rec)) /** @type {any} */ (rec)[k].length = 0; }

/** その人の技の名前（記録の順）。 @param {any} p */
export function moves(p) { return rec.parkour.filter((d) => d.player === p).map((d) => d.move); }

/**
 * 走者を出す（平らな地面 y=64・朝・設定は既定）。o.skills はスキルの鍵の配列。
 * @param {{at?: any, item?: any, yaw?: number, time?: number, skills?: string[], wait?: number}} [o]
 */
export async function runner(o = {}) {
  resetSettings();
  setGround(64);
  setTime(o.time ?? 1000);
  setLight(null);
  const p = spawnPlayer(o.at ?? { x: 0.5, y: 64, z: 0.5 }, o.item, { yaw: o.yaw ?? 0 });
  // 初回参加のあいさつ（ui/welcome.js: 最初の持ち物と基本のスキル）を済んだことにして、テストの条件を変えない
  p.setDynamicProperty("nr:welcomed", true);
  await tick(o.wait ?? 2);
  for (const k of o.skills ?? []) grantSkill(p, k);
  clearRec();
  return p;
}

/** 体力。 @param {any} p */
export function hp(p) { return p.getComponent("minecraft:health").currentValue; }

/** n tick 走る（前へ・ダッシュ）。 @param {any} p @param {number} n */
export async function sprint(p, n) {
  await setInput(p, { y: 1, sprint: true });
  await tick(n);
}

/** ジャンプを軽く押す（押して離す）。 @param {any} p */
export async function tapJump(p) {
  await press(p, "Jump", true);
  await press(p, "Jump", false);
}

/** スニークを軽く押す。 @param {any} p */
export async function tapSneak(p) {
  await press(p, "Sneak", true);
  await press(p, "Sneak", false);
}

/** 着地するまで（最大 n tick）。 @param {any} p @param {number} [n] */
export async function untilGround(p, n = 120) {
  for (let i = 0; i < n; i++) { await tick(1); if (p.isOnGround) return i + 1; }
  return -1;
}

/** 条件が真になるまで（最大 n tick）。 @param {() => boolean} f @param {number} [n] */
export async function until(f, n = 120) {
  for (let i = 0; i < n; i++) { if (f()) return i; await tick(1); }
  return f() ? n : -1;
}
