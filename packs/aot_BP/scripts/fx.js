// ===========================================================================
//  演出 — パーティクル・効果音・画面揺れ・全身モーション
//
//  パーティクルは白で描いたスプライトを、MolangVariableMap で渡す色・大きさ・
//  寿命・向きで染めて使う（tools/aot/gen_aot_particles.py）。1 tick に出す数には
//  上限を設けて、巨人が何体いてもクライアントが詰まらないようにしてある。
// ===========================================================================
import { MolangVariableMap } from "@minecraft/server";
import { ANIM_META } from "./anim_meta.js";
import { add, cmd, dist, now, norm, sub, valid } from "./util.js";

const VARS = ["size", "life", "count", "speed", "vx", "vy", "vz", "spread", "rot", "len", "rise"];
const BUDGET = 320;
let budgetTick = -1;
let spent = 0;

function spend(n) {
  const t = now();
  if (t !== budgetTick) { budgetTick = t; spent = 0; }
  if (spent + n > BUDGET) return false;
  spent += n;
  return true;
}

/** パーティクル。o: {color:[r,g,b] (0..1), size, life, count, speed, dir, spread, rot, len} */
export function P(dim, id, loc, o = {}) {
  if (!dim || !loc) return;
  if (!spend(Math.max(1, o.count ?? 1))) return;
  try {
    const m = new MolangVariableMap();
    const c = o.color;
    if (c) {
      m.setFloat("variable.cr", c[0]);
      m.setFloat("variable.cg", c[1]);
      m.setFloat("variable.cb", c[2]);
    }
    if (o.dir) { o.vx = o.dir.x; o.vy = o.dir.y; o.vz = o.dir.z; }
    for (const k of VARS) {
      if (typeof o[k] === "number" && Number.isFinite(o[k])) m.setFloat(`variable.${k}`, o[k]);
    }
    dim.spawnParticle(`aot:${id}`, loc, m);
  } catch (_) { }
}

export function sound(dim, id, loc, pitch = 1.0, volume = 1.0) {
  try { dim.playSound(id, loc, { pitch, volume }); } catch (_) { }
}

/** 画面揺れ。巨人の足音や爆発は距離で弱める。 */
export function shake(p, intensity, seconds = 0.3, type = "positional") {
  if (intensity <= 0.01) return;
  cmd(p, `camerashake add @s ${Math.min(1, intensity).toFixed(2)} ${seconds.toFixed(2)} ${type}`);
}

export function shakeAround(dim, centre, radius, intensity, seconds = 0.3) {
  let players = [];
  try { players = dim.getPlayers({ location: centre, maxDistance: radius }); } catch (_) { return; }
  for (const p of players) {
    const k = 1 - dist(p.location, centre) / radius;
    shake(p, intensity * k, seconds);
  }
}

// ---------------------------------------------------------------------------
//  ワイヤー: 長い線を数本の細長い粒で描く（1 本 6m まで）
// ---------------------------------------------------------------------------
export function wire(dim, a, b, o = {}) {
  const d = sub(b, a);
  const L = Math.hypot(d.x, d.y, d.z);
  if (L < 0.05) return;
  const n = Math.max(1, Math.ceil(L / 6));
  const dir = norm(d);
  const seg = L / n;
  for (let i = 0; i < n; i++) {
    const mid = add(a, dir, seg * (i + 0.5));
    P(dim, "wire", mid, { dir, len: seg + 0.05, life: o.life ?? 0.1, size: o.size ?? 1.0,
                          color: o.color });
  }
}

// ---------------------------------------------------------------------------
//  巨人の血と蒸気
// ---------------------------------------------------------------------------
export function blood(dim, at, k = 1.0, dir) {
  P(dim, "blood", at, { count: Math.round(8 * k), speed: 3 + 3 * k, spread: 0.3 * k, size: 1 + k * 0.6,
                        dir });
  P(dim, "blood_mist", at, { count: Math.max(1, Math.round(2 * k)), size: 1 + k, spread: 0.4 * k });
}

export function steam(dim, at, k = 1.0) {
  P(dim, Math.random() < 0.5 ? "steam" : "steam2", at,
    { count: Math.max(1, Math.round(2 * k)), size: 0.8 + k * 0.8, spread: 0.4 + k * 0.5,
      life: 1.8 + k * 0.8, rise: 1.2 + k * 0.4 });
}

export function slash(dim, at, rot, size = 1.4, color) {
  P(dim, "slash", at, { rot, size, color: color ?? [0.8, 0.92, 1.0] });
}

export function gasPuff(dim, at, dir, k = 1.0) {
  P(dim, "gas", at, { count: Math.round(2 + 2 * k), dir, speed: 3 + 3 * k, size: 0.6 + 0.4 * k,
                      spread: 0.1 });
}

// ---------------------------------------------------------------------------
//  全身モーション（playanimation）。player.entity.json は上書きしない
// ---------------------------------------------------------------------------
function play(p, name, controller, blendOut) {
  if (!valid(p)) return;
  try {
    if (typeof p.playAnimation === "function") {
      p.playAnimation(name, { blendOutTime: blendOut, controller, stopExpression: "0" });
      return;
    }
  } catch (_) { /* コマンドへ */ }
  cmd(p, `playanimation @s ${name} none ${blendOut} "0" ${controller}`);
}

/** 一回だけ流す動き（回転斬り・うなじ斬り・刃の交換…）。 */
export function body(p, anim, controller = "aot.act") {
  if (ANIM_META[anim] === undefined) return;
  play(p, `animation.aot.p.${anim}`, controller, anim === "spin" ? 0.0 : 0.12);
}

/** ループする姿勢（構え・飛行・掴まれ）。null で解除。 */
export function pose(p, anim, controller = "aot.move") {
  if (!anim) { play(p, "animation.aot.p.none", controller, 0.2); return; }
  if (ANIM_META[anim] === undefined) return;
  play(p, `animation.aot.p.${anim}`, controller, 0.2);
}
