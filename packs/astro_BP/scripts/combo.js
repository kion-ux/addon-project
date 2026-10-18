// ===========================================================================
//  通常攻撃の三段コンボ（変身中にナノウェポンで殴った時）
//  当てるたびに 1→2→3 段目と進み（combo_reset_ticks あくと 1 段目に戻る）、段ごとに全身の振りと
//  斬撃の向きが変わる。三段目は planets/<key>.js の combo3(ctx, target) が追撃する。
//  ダメージそのものはバニラの攻撃（ナノウェポンの攻撃力）。ここでは演出・ゲージ・追撃だけ。
//
//  連打の扱い: 統合版には攻撃のクールダウンが無いので、振りを数えるのは MIN_GAP tick に 1 回まで
//  （それより速い振りはバニラのダメージだけで、段も超新星ゲージも進まない）。三段目の後は追撃の長さ
//  （combo3 の返り値）が終わるまで次の段を始めない。
//
//  演出の時刻: 全身モーションは「構え → 振り抜き」なので、斬撃・火花・当たりの音はモーションの
//  当たりのキー（STRIKE）に合わせて遅らせる。combo3 も当たりの時刻に呼ぶ（惑星の combo3 が自分で
//  モーションに合わせて待つ場合は meta.combo3Synced: true で、すぐに呼ぶ）。
// ===========================================================================
import { COMMON, PLANETS } from "./data.js";
import { ANIM_META } from "./anim_meta.js";
import { S, isReady } from "./state.js";
import { addNova, addXp } from "./combat.js";
import { P, arc, body, hasBody, sound, white, slash } from "./fx.js";
import { makeCtx, moveImpl, MOVES } from "./engine.js";
import { chest, flatDir, rand, now, BUS, report, yawDeg, valid, clamp } from "./util.js";

const combos = new Map();   // playerId -> { step, last, next }

/** 振りを数える最小の間隔（tick）。 */
export const MIN_GAP = 8;

/**
 * 全身モーション <key>.combo1〜3 の「当たる」キーの時刻（秒）。tools/astro/planets/<key>/body.py の
 * c1_hit / c2_hit / c3_hit（回転斬りは最初に刃が前へ出るキー）。ANIM_META に 3 番目の値があればそちらを使う。
 */
const STRIKE = {
  mercury: [0.15, 0.17, 0.16],
  venus: [0.18, 0.2, 0.18],
  earth: [0.17, 0.2, 0.3],
  mars: [0.21, 0.23, 0.34],
  jupiter: [0.2, 0.21, 0.34],
  saturn: [0.17, 0.2, 0.18],
  uranus: [0.16, 0.19, 0.22],
  neptune: [0.18, 0.27, 0.32],
  sol: [0.21, 0.22, 0.36],
};

/** 段 step のモーションの当たりまでの tick（モーションが無ければ 0 = バニラの振りのまま）。 */
function strikeTicks(key, step, anim) {
  if (!hasBody(anim)) return 0;
  const m = ANIM_META[anim];
  const s = Number.isFinite(m?.[2]) ? m[2] : (STRIKE[key]?.[step - 1] ?? [0.17, 0.2, 0.3][step - 1]);
  return clamp(Math.round(s * 20), 0, 10);
}

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
  const t = now();
  const prev = combos.get(p.id) ?? { step: 0, last: -999, next: -1 };
  if (t < prev.next) return;   // 連打: 前の振り（三段目は追撃）が終わるまで数えない
  const step = t - prev.last <= COMMON.combo_reset_ticks ? (prev.step % 3) + 1 : 1;
  const s = { step, last: t, next: t + MIN_GAP };
  combos.set(p.id, s);
  // 形態のコンボのモーションがあれば使う。無ければ 1・2 段目はバニラの振りのまま、3 段目は共通の回転斬り
  const anim = `${key}.combo${step}`;
  if (hasBody(anim)) body(p, anim);
  else if (step === 3) body(p, "spin");
  addNova(p, COMMON.nova_on_hit);
  if (target.typeId !== "astro:hologram_target") addXp(p, key, COMMON.xp_on_hit);
  BUS.emit("hit", p, target, pl.damage, null);
  const dim = p.dimension;
  const c = pl.color;
  const ctx = makeCtx(p, key, step === 3 ? "combo3" : "melee", { target });
  const T = strikeTicks(key, step, anim);
  const at0 = chest(target);
  // 刃が当たる瞬間の演出（モーションの当たりのキーに合わせる）
  ctx.at(Math.max(0, T - 2), () => {
    sound(dim, step === 3 ? "astro.swing_heavy" : "astro.swing", p.location, rand(0.95, 1.1) + step * 0.05, 0.8);
  });
  ctx.at(T, () => {
    const at = valid(target) ? chest(target) : at0;
    const f = flatDir(p);
    const tilt = step === 1 ? 30 : step === 2 ? -30 : 80;
    sound(dim, step === 3 ? "astro.hit_heavy" : "astro.hit", at, rand(0.9, 1.1), 0.8);
    arc(dim, chest(p), f, 1.9, step === 2 ? 70 : -70, step === 2 ? -70 : 70, tilt, c,
      { size: 0.9, steps: 10, life: 0.2, sparks: false });
    slash(dim, at, white(c, 0.2), yawDeg(f) + (step === 2 ? 200 : -20), 1.0, "slash", 0.2);
    P(dim, "spark", at, { color: c, count: 5, speed: 5, size: 0.8 });
  });
  if (step === 3) {
    const impl = moveImpl(key, "combo3");
    const synced = MOVES[key]?.meta?.combo3Synced === true;
    s.next = t + Math.max(MIN_GAP, synced ? 0 : T);
    ctx.at(synced ? 0 : T, () => {
      try {
        const d = Number(impl?.(ctx, target)) || 10;
        // 追撃が終わるまで次の段を始めない
        s.next = Math.max(s.next, now() + clamp(Math.round(d), MIN_GAP, 30));
      } catch (e) { report(`${key}.combo3`, e); }
    });
  }
}

export function forgetCombo(id) { combos.delete(id); }
