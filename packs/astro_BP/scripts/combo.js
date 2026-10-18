// ===========================================================================
//  通常攻撃の三段コンボ（変身中にナノウェポンで殴った時）
//  当てるたびに 1→2→3 段目と進み（combo_reset_ticks あくと 1 段目に戻る）、段ごとに全身の振りと
//  斬撃の向きが変わる。三段目は planets/<key>.js の combo3(ctx, target) が追撃する。
//  ダメージそのものはバニラの攻撃（ナノウェポンの攻撃力）。ここでは演出・ゲージ・追撃だけ。
// ===========================================================================
import { COMMON, PLANETS } from "./data.js";
import { S, isReady } from "./state.js";
import { addNova, addXp } from "./combat.js";
import { P, arc, body, hasBody, sound, white, slash } from "./fx.js";
import { makeCtx, moveImpl } from "./engine.js";
import { chest, flatDir, rand, now, BUS, report, yawDeg } from "./util.js";

const combos = new Map();   // playerId -> { step, last }

/** 今のコンボの段（0 = コンボ中でない）。 */
export function comboStep(p) {
  const s = combos.get(p.id);
  if (!s || now() - s.last > COMMON.combo_reset_ticks) return 0;
  return s.step;
}

/** entityHitEntity から（変身中・ナノウェポンを持っている・相手が標的のとき）。 */
export function onMeleeHit(p, target) {
  if (!isReady(p)) return;
  const key = S(p).form;
  const pl = PLANETS[key];
  const s = combos.get(p.id) ?? { step: 0, last: -999 };
  const step = now() - s.last <= COMMON.combo_reset_ticks ? (s.step % 3) + 1 : 1;
  combos.set(p.id, { step, last: now() });
  // 形態のコンボのモーションがあれば使う。無ければ 1・2 段目はバニラの振りのまま、3 段目は共通の回転斬り
  const anim = `${key}.combo${step}`;
  if (hasBody(anim)) body(p, anim);
  else if (step === 3) body(p, "spin");
  addNova(p, COMMON.nova_on_hit);
  if (target.typeId !== "astro:hologram_target") addXp(p, key, COMMON.xp_on_hit);
  BUS.emit("hit", p, target, pl.damage, null);
  const dim = p.dimension;
  const c = pl.color;
  const at = chest(target);
  const f = flatDir(p);
  const tilt = step === 1 ? 30 : step === 2 ? -30 : 80;
  sound(dim, step === 3 ? "astro.swing_heavy" : "astro.swing", p.location, rand(0.95, 1.1) + step * 0.05, 0.8);
  sound(dim, step === 3 ? "astro.hit_heavy" : "astro.hit", at, rand(0.9, 1.1), 0.8);
  arc(dim, chest(p), f, 1.9, step === 2 ? 70 : -70, step === 2 ? -70 : 70, tilt, c,
    { size: 0.9, steps: 10, life: 0.2, sparks: false });
  slash(dim, at, white(c, 0.2), yawDeg(f) + (step === 2 ? 200 : -20), 1.0, "slash", 0.2);
  P(dim, "spark", at, { color: c, count: 5, speed: 5, size: 0.8 });
  if (step === 3) {
    try {
      const ctx = makeCtx(p, key, "combo3", { target });
      moveImpl(key, "combo3")?.(ctx, target);
    } catch (e) { report(`${key}.combo3`, e); }
  }
}

export function forgetCombo(id) { combos.delete(id); }
