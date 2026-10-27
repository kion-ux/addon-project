// combat のテストの補助（tests/combat_*.mjs が使う。.js はテストではなく補助として一緒に写される）
import { tick, spawnPlayer, spawnZombie, give, held, mc, S, __drain } from "nr-test";
import { shapesReady, defaults, setGore } from "./gore_util.js";
import { on, EV } from "../scripts/core/bus.js";
import { initHp } from "../scripts/core/hp.js";
import { CEV, setSkillQuery, setStaminaQuery } from "../scripts/combat/index.js";

export { setGore };

/** バスの記録（テストごとに reset）。 */
export const rec = { hits: [], kills: [], stamina: [], noise: [], state: [], finisher: [], immunity: [], lure: [], uv: [], fire: [] };
on(EV.HIT, (r) => rec.hits.push(r));
on(EV.KILL, (k) => rec.kills.push(k));
on(CEV.STAMINA_COST, (d) => rec.stamina.push(d));
on(CEV.NOISE, (d) => rec.noise.push(d));
on(CEV.WEAPON_STATE, (d) => rec.state.push(d));
on(CEV.FINISHER, (d) => rec.finisher.push(d));
on(CEV.IMMUNITY, (d) => rec.immunity.push(d));
on(CEV.LURE, (d) => rec.lure.push(d));
on(CEV.UV_ZONE, (d) => rec.uv.push(d));
on(CEV.FIRE_ZONE, (d) => rec.fire.push(d));
export function reset() { for (const k of Object.keys(rec)) rec[k].length = 0; }

/** そのゾンビへの applyHit の結果（記録から）。 @param {any} z @param {(r: any) => boolean} [f] */
export function hitsOn(z, f) { return rec.hits.filter((r) => r.zombie?.id === z.id && (!f || f(r))); }

/** @type {any} */
let P;
/**
 * プレイヤー（手に item）とゾンビを並べる。skills はスキルの鍵の配列（setSkillQuery）。
 * @param {{item?: any, zombie?: string | null, at?: any, hp?: number, skills?: string[], wait?: number}} [o]
 */
export async function arena(o = {}) {
  await shapesReady;
  defaults();
  const skills = o.skills ?? [];
  setSkillQuery((_p, k) => skills.includes(k));
  setStaminaQuery(undefined);
  if (!P || !P.isValid) P = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  P.teleport({ x: 0.5, y: 64, z: 0.5 });
  P.setRotation({ x: 0, y: 0 });
  P.getComponent("minecraft:inventory").container.clearAll();
  P.selectedSlotIndex = 0;
  if (o.item) give(P, o.item, 0);
  const zk = o.zombie === undefined ? "office_worker" : o.zombie;
  const z = zk ? spawnZombie(zk, o.at ?? { x: 0.5, y: 64, z: 2.6 }) : undefined;
  if (z && o.hp) initHp(z, o.hp);
  await tick(o.wait ?? 30);
  reset();
  return { p: P, z };
}

/** ItemStack（数つき）。 @param {string} id @param {number} [n] */
export function stack(id, n = 1) { return new mc.ItemStack(id, n); }

/** 手の ItemStack を書き換えて戻す。 @param {any} p @param {(it: any) => void} fn */
export function editHeld(p, fn) {
  const it = held(p);
  fn(it);
  give(p, it, p.selectedSlotIndex);
  return held(p);
}
/** 手の武器の耐久（エンジンの傷）。 @param {any} p */
export function heldDamage(p) { return held(p)?.getComponent("minecraft:durability")?.damage; }

/** プレイヤーがブロックを叩く（entityHitBlock）。 @param {any} p @param {{x: number, y: number, z: number}} pos */
export async function hitBlock(p, pos) {
  const dim = mc.world.getDimension("overworld");
  const block = dim.getBlock(pos);
  S.queueAfter("entityHitBlock", { damagingEntity: p, hitBlock: block, blockFace: "North", hitBlockPermutation: block.permutation });
  S.flush();
  await __drain();
}

/** 持ち物の数。 @param {any} p @param {string} id */
export function count(p, id) {
  const c = p.getComponent("minecraft:inventory").container;
  let n = 0;
  for (let i = 0; i < c.size; i++) { const it = c.getItem(i); if (it?.typeId === id) n += it.amount; }
  return n;
}
