// ===========================================================================
//  NIGHT RUNNER: 感染都市 — とどめ（踏みつけ・処刑の首刎ね）
//
//  * 踏みつけ（スキル stomp。入力: 倒れた・這う敵の上でスニーク＋攻撃）: 頭への重い打撃
//    （stomp_damage、stomp_head_crush なら頭が弾ける）。stomp_kill_crawler なら這う敵は必ず死ぬ。
//    モーション finisher_stomp。
//  * 処刑（スキル finisher。入力: よろめいた敵に強撃 = 溜め攻撃か、power_attack のスニーク攻撃）:
//    刃なら首が飛び（severed）、打撃・突きなら頭が弾ける（crushed）。必ず死ぬ（ボスは除く）。
//    finisher_on_stun なら感電で痺れた敵にも。モーション finisher_decap、体力 finisher_heal 回復、
//    スタミナ finisher_stamina 回復（stamina_cost を負で出す）。
//  * どちらも hit._finisher を付けて applyHit（melee.js の解決・溜め攻撃から）。結果は EV.HIT で受け、
//    回復・必ず死ぬ・バス "finisher" {player, zombie, kind, result} をここでやる。
//  * ゴアレベルの下限（GORE_TUNING.min_g）は gore.js が守る（G = 0 では首は飛ばないが、死ぬのは同じ）。
// ===========================================================================
import { stateOf } from "../gore/gore.js";
import { kill, isCorpse } from "../gore/death.js";
import { emit, on, EV } from "../core/bus.js";
import { playerAnim, shake, particle, PRIO } from "../core/fx.js";
import { valid, dist, getProp, norm, add, safe, isPlayer } from "../core/util.js";
import { CEV, hasSkill, skillEff, spendStamina, isBoss } from "./common.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */

/** 踏みつけの届く距離（ブロック）。 */
export const STOMP_RANGE = 2.8;

/** 踏みつけられるか（スキル stomp・スニーク中・相手が倒れているか這っている）。 @param {Player} p @param {Entity} z */
export function canStomp(p, z) {
  if (!valid(p) || !valid(z) || isCorpse(z) || !p.isSneaking || !hasSkill(p, "stomp")) return false;
  const s = stateOf(z);
  if (s !== "down" && s !== "crawl") return false;
  return dist(p.location, z.location) <= STOMP_RANGE;
}

/**
 * 踏みつけの hit（melee.js の解決が返す）。モーションもここで出す。
 * @param {Player} p @param {Entity} z @returns {any}
 */
export function stompHit(p, z) {
  const eff = skillEff(p, "stomp") ?? {};
  playerAnim(p, "finisher_stomp");
  shake(p, 0.35, 0.2);
  const dir = norm({ x: z.location.x - p.location.x, y: -1.2, z: z.location.z - p.location.z });
  return {
    attacker: p, source: "melee", dtype: "blunt", weight: "heavy", part: "head",
    damage: Math.max(1, Number(eff.stomp_damage) || 20), power: 1.3, gorePower: 1.1, crit: false, heavy: false,
    weapon: undefined, mods: undefined, noKnockback: true, dir,
    outcome: eff.stomp_head_crush ? { head: "crushed" } : undefined,
    _finisher: "stomp", _killCrawler: !!eff.stomp_kill_crawler && stateOf(z) === "crawl",
  };
}

/** 処刑できるか（スキル finisher・ボスでない・よろめき中か痺れている）。 @param {Player} p @param {Entity} z */
export function canExecute(p, z) {
  if (!valid(p) || !valid(z) || isCorpse(z) || isBoss(z) || !hasSkill(p, "finisher")) return false;
  const s = stateOf(z);
  if (s === "stagger") return true;
  const eff = skillEff(p, "finisher") ?? {};
  return !!eff.finisher_on_stun && Number(getProp(z, "nr:shock", 0)) === 1;
}

/**
 * 処刑の hit（溜め攻撃・スニークの強撃から）。base は武器の一撃（damage・mods）。
 * @param {Player} p @param {Entity} z @param {any} w @param {{damage?: number, mods?: Record<string, number>}} [base] @returns {any}
 */
export function decapHit(p, z, w, base) {
  playerAnim(p, "finisher_decap");
  shake(p, 0.5, 0.25);
  const blade = w?.dtype === "slash" || w?.alt_dtype === "slash";
  const dtype = blade ? "slash" : w?.dtype === "pierce" ? "pierce" : "blunt";
  const dir = norm({ x: z.location.x - p.location.x, y: 0, z: z.location.z - p.location.z });
  particle(z.dimension, "speed_lines", add(p.getHeadLocation(), dir), { dx: dir.x, dy: 0, dz: dir.z }, PRIO.LOW);
  return {
    attacker: p, source: "melee", dtype, weight: "heavy", part: "head",
    damage: Math.max(1, Number(base?.damage) || Number(w?.damage) || 8), power: 1.5, gorePower: 1.3, crit: true, heavy: true,
    weapon: w, mods: base?.mods, dir, outcome: { head: blade ? "severed" : "crushed" },
    _finisher: "decap",
  };
}

// 結果を受けて: 必ず死ぬ・回復・知らせ
on(EV.HIT, (res) => {
  const hit = res?.hit;
  const kind = hit?._finisher;
  if (!kind || res.corpse || res.blocked) return;
  const p = isPlayer(res.attacker) ? /** @type {Player} */ (res.attacker) : undefined;
  const z = res.zombie;
  const mustDie = kind === "decap" ? !isBoss(z) : !!hit._killCrawler;
  if (mustDie && !res.killed && valid(z) && !isCorpse(z)) {
    res.killed = !!safe("finisher.kill", () => kill(z, { attacker: p, hit, cause: "finisher", byPlayer: !!p, dir: hit.dir, power: 1.2 }));
  }
  if (p && kind === "decap") {
    const eff = skillEff(p, "finisher") ?? {};
    const heal = Number(eff.finisher_heal) || 0;
    if (heal > 0) safe("finisher.heal", () => {
      const hc = /** @type {any} */ (p.getComponent("minecraft:health"));
      if (hc) hc.setCurrentValue(Math.min(hc.effectiveMax, hc.currentValue + heal));
    });
    const sta = Number(eff.finisher_stamina) || 0;
    if (sta > 0) spendStamina(p, -sta, "finisher");
  }
  if (p) emit(CEV.FINISHER, { player: p, zombie: z, kind, result: res });
});
