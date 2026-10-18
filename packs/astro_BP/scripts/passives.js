// ===========================================================================
//  惑星ごとの常時効果（パッシブ）
//
//  * PLANETS[key].passive.effects（[id, Lv]）を変身中ずっと掛け続ける（毎秒、切れかけたら掛け直す）
//  * planets/<key>.js の passive フック:
//      tick(p, st)              PASSIVE_EVERY tick ごと（st はプレイヤー×形態ごとの作業用オブジェクト。
//                               st.n 呼ばれた回数 / st.t 今の tick。変身のたびに空に戻る）
//      onHit(p, target, dmg, ctx)  自分の攻撃が当たった（ctx は技の文脈。通常攻撃なら null）
//      onHurt(p, attacker, dmg) 攻撃を受けた（attacker は居ないこともある）
//      onKill(p, victim)        敵を倒した
//      dmgMul(p)                与ダメージの倍率（海王星の「水中・雨で上がる」など。既定 1）
//  フックの中で hit() を呼んでも onHit は二重に呼ばれない（再入の防止）。
// ===========================================================================
import { PLANETS } from "./data.js";
import { S, isReady } from "./state.js";
import { setDamageMulHook } from "./combat.js";
import { MOVES } from "./engine.js";
import { allPlayers, effect, getEffect, BUS, report, now, valid } from "./util.js";

/** passive.tick を呼ぶ間隔（tick）。 */
export const PASSIVE_EVERY = 5;

function hooks(key) { return MOVES[key]?.passive ?? null; }

const busy = new Set();   // 再入防止: `${playerId}:${hook}`

function call(p, name, ...args) {
  const st = S(p);
  const key = st.form;
  if (!key || st.seq) return undefined;
  const fn = hooks(key)?.[name];
  if (typeof fn !== "function") return undefined;
  const tag = `${p.id}:${name}`;
  if (busy.has(tag)) return undefined;
  busy.add(tag);
  try { return fn(p, ...args); } catch (e) { report(`${key}.passive.${name}`, e); return undefined; }
  finally { busy.delete(tag); }
}

/** PASSIVE_EVERY tick ごと（main から）。 */
export function tickPassives() {
  for (const p of allPlayers()) {
    if (!isReady(p)) continue;
    const st = S(p);
    const ps = st.passive ?? (st.passive = {});
    ps.n = (ps.n ?? 0) + 1;
    ps.t = now();
    call(p, "tick", ps);
  }
}

/** 毎秒（main から）: effects を掛け直す（暗視は 10 秒未満でちらつくので長めに）。 */
export function tickPassiveEffects() {
  for (const p of allPlayers()) {
    if (!isReady(p)) continue;
    const pl = PLANETS[S(p).form];
    for (const [id, amp] of pl.passive?.effects ?? []) {
      const cur = getEffect(p, id);
      const want = id === "night_vision" ? 400 : 260;
      if (!cur || cur.amplifier < amp || cur.duration < want - 60) effect(p, id, want, amp, false);
    }
  }
}

BUS.on("hit", (p, target, dmg, ctx) => { if (valid(p)) call(p, "onHit", target, dmg, ctx ?? null); });
BUS.on("hurt", (p, attacker, dmg) => { if (valid(p)) call(p, "onHurt", attacker, dmg); });
BUS.on("kill", (p, victim) => { if (valid(p)) call(p, "onKill", victim); });

setDamageMulHook((p, key) => {
  const fn = hooks(key)?.dmgMul;
  if (typeof fn !== "function") return 1;
  const k = Number(fn(p));
  return Number.isFinite(k) && k > 0 ? k : 1;
});
