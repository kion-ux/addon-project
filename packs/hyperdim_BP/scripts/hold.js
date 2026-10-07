// ===========================================================================
//  「押している間」の武器 — 弓の引き絞りと、盾のガード
//
//  弓: 右クリックで引き始め、離した瞬間の状況で技が決まる
//      地上 → 戦技「聖光矢」（溜め 0.4 秒で LV1、1 秒で LV2）／ 空中 → 「星雨」
//      ダッシュ中に引き始める → 「宙返り三連射」／ スニーク＋ゲージ満タン → 必殺
//  盾: 右クリックの間ガード（被ダメージ 60% 減）。構えた直後 0.3 秒はジャストガードで
//      ダメージを完全に消して相手を凍らせる。離すと、受けた衝撃を「氷撃反射」で返す
//
//  itemStartUse / itemStopUse が来ない版でも動くよう、itemUse を開始の代わりに使い、
//  終わりの合図が来なければ一定時間で自動的に締める。
// ===========================================================================
import { GAUGE_MAX } from "./config.js";
import { gauge, hit, freeze, addGauge } from "./combat.js";
import { perform, isBusy, dirTo } from "./engine.js";
import { P, body, bodyStop, sound, kanji, white } from "./fx.js";
import { health, effect, now, valid, flatDir, chest, add } from "./util.js";

const drawing = new Map();   // playerId -> { w, start, maxed }
const guarding = new Map();  // playerId -> { w, start, absorbed, parries }

const PERFECT = 6;           // ジャストガードの受付 (tick)
const MAX_DRAW = 100;        // 終わりの合図が来ない時の自動発射
const MAX_GUARD = 90;

// ---------------------------------------------------------------------------
export function startUse(player, w) {
  if (drawing.has(player.id) || guarding.has(player.id)) return;
  if (isBusy(player)) return;
  // 押した瞬間に決まる技
  if (player.isSneaking && gauge(player) >= GAUGE_MAX) { perform(player, w, "ult"); return; }
  if (w.guard) {
    if (!player.isOnGround) { perform(player, w, "air"); return; }
    if (player.isSprinting) { perform(player, w, "dash"); return; }
    guarding.set(player.id, { player, w, start: now(), absorbed: 0, parries: 0 });
    body(player, "guard");
    sound(player.dimension, "hd.guard", player.location, 1.3, 0.6);
    return;
  }
  if (w.charge) {
    if (player.isSprinting && player.isOnGround) { perform(player, w, "dash"); return; }
    drawing.set(player.id, { player, w, start: now(), maxed: false });
    body(player, "aim");
    sound(player.dimension, "hd.charge", player.location, 1.5, 0.4);
  }
}

export function stopUse(player) {
  const d = drawing.get(player.id);
  if (d) {
    drawing.delete(player.id);
    bodyStop(player);
    if (isBusy(player)) return;
    const charge = now() - d.start;
    const kind = !player.isOnGround && !player.isInWater ? "air" : "skill";
    perform(player, d.w, kind, { charge });
    return;
  }
  const g = guarding.get(player.id);
  if (g) {
    guarding.delete(player.id);
    bodyStop(player);
    if (g.absorbed > 0) perform(player, g.w, "skill", { absorbed: g.absorbed });
  }
}

export function isDrawing(player) { return drawing.get(player.id); }
export function isGuarding(player) { return guarding.get(player.id); }

/** 毎 tick。 */
export function tickHold(heldOf) {
  const t = now();
  for (const [id, d] of [...drawing]) {
    const player = d.player;
    if (!player || !valid(player) || heldOf(player)?.key !== d.w.key) {
      drawing.delete(id);
      if (valid(player)) bodyStop(player);
      continue;
    }
    const age = t - d.start;
    const front = add(chest(player), flatDir(player), 0.9);
    if (age % 3 === 0) {
      P(player.dimension, "converge", front, { color: d.w.color, count: 4, spread: 1.2, life: 0.25, size: 0.6 });
    }
    if (age === 8 || (age >= 20 && !d.maxed)) {
      if (age >= 20) d.maxed = true;
      P(player.dimension, "ring", front, { color: white(d.w.color, 0.4), size: age >= 20 ? 1.6 : 1.0, life: 0.25 });
      sound(player.dimension, "hd.ding", player.location, age >= 20 ? 1.5 : 1.2, 0.5);
    }
    if (age >= MAX_DRAW) stopUse(player);
  }
  for (const [id, g] of [...guarding]) {
    const player = g.player;
    if (!player || !valid(player) || heldOf(player)?.key !== g.w.key) {
      guarding.delete(id);
      if (valid(player)) bodyStop(player);
      continue;
    }
    const age = t - g.start;
    effect(player, "resistance", 4, age < PERFECT ? 3 : 2);
    if (age % 4 === 0) {
      const at = add(chest(player), flatDir(player), 1.0);
      P(player.dimension, "hex", at, { color: g.w.color, size: age < PERFECT ? 1.8 : 1.4, life: 0.25, rot: age * 6 });
    }
    if (age >= MAX_GUARD) stopUse(player);
  }
}

/** ガード中に被弾した。ジャストガードなら打ち消して反撃。 */
export function onGuardHurt(player, damage, attacker) {
  const g = guarding.get(player.id);
  if (!g) return false;
  const age = now() - g.start;
  const dim = player.dimension;
  const at = add(chest(player), flatDir(player), 0.9);
  if (age < PERFECT) {
    // ジャストガード: 受けたダメージを戻し、相手を凍らせて弾く
    const h = health(player);
    try { if (h) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + damage)); } catch (_) { }
    g.parries++;
    g.absorbed += damage * 2 + 4;
    sound(dim, "hd.parry", at, 1.0, 1.2);
    P(dim, "impact", at, { color: white(g.w.color, 0.5), size: 1.6 });
    P(dim, "shard", at, { color: g.w.color, count: 14, speed: 7 });
    kanji(dim, add(at, { x: 0, y: 1.2, z: 0 }), 4, g.w.color, 1.8);
    addGauge(player, 12);
    if (attacker && valid(attacker)) {
      hit(player, attacker, 4, { color: g.w.color, kb: 1.2, up: 0.3, dir: dirTo(player.location, attacker.location), gauge: 0 });
      freeze(attacker, 40, true);
    }
  } else {
    g.absorbed += damage * 1.5 + 2;
    sound(dim, "hd.guard", at, 0.9 + Math.random() * 0.2, 1.0);
    P(dim, "hex", at, { color: g.w.color, size: 2.0, life: 0.3 });
    P(dim, "spark", at, { color: g.w.color, count: 8, speed: 5 });
    addGauge(player, 4);
  }
  return true;
}

export function forgetHold(id) { drawing.delete(id); guarding.delete(id); }
