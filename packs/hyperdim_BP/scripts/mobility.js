// ===========================================================================
//  機動 — アクションゲームの足回り（超次元武器を持っている間だけ）
//
//   二段ジャンプ   空中でもう一度ジャンプ（軽い武器は三段まで）
//   空中ダッシュ   空中でスニーク → 視線の方向へ滑空ダッシュ
//   回避ステップ   地上でスニークを素早く 2 回 → 移動方向（止まっていれば後ろ）へ
//                  跳ぶ。跳んだ直後は無敵
//   疾走          ダッシュ中は武器の重さに応じて加速し、足元に属性色の風
//   着地          高所から落ちると片膝をつくヒーロー着地。落下ダメージは無効
// ===========================================================================
import { WEIGHT, weaponOf } from "./config.js";
import { P, afterimage, body, sound, white, ring } from "./fx.js";
import {
  allPlayers, heldItem, knock, effect, flatDir, health, valid, now,
} from "./util.js";

// 強さの調整値（実機で跳びすぎ／足りない場合はここだけ直す）
export const TUNE = {
  jumpUp: 0.68,        // 二段ジャンプの上向き速度
  jumpCarry: 0.55,     // 二段ジャンプで足す水平速度
  airDash: 1.05,       // 空中ダッシュの水平速度
  airDashUp: 0.16,
  step: 1.15,          // 回避ステップの水平速度
  stepUp: 0.18,
  stepWindow: 7,       // スニーク 2 回押しの受付 (tick)
  stepCooldown: 14,
  iframes: 8,          // 回避直後の無敵 (tick)
};

const st = new Map();   // playerId -> state

function state(p) {
  let s = st.get(p.id);
  if (!s) {
    s = { sneak: false, jump: false, ground: true, airT: 0, jumps: 0, dashes: 0,
          lastSneak: -99, stepCd: 0, noFall: false, minVy: 0, holdKey: null };
    st.set(p.id, s);
  }
  return s;
}

/** 技・機動で宙に浮いたら、次の着地まで落下ダメージを消す。 */
export function markAirborne(p) {
  if (!valid(p) || p.typeId !== "minecraft:player") return;
  state(p).noFall = true;
}

function jumpPressed(p) {
  try {
    const info = p.inputInfo;
    if (info && typeof info.getButtonState === "function") {
      return String(info.getButtonState("Jump")) === "Pressed";
    }
  } catch (_) { }
  return p.isJumping === true;
}

/** 2 tick ごと。 */
export function tickMobility(onHoldChange) {
  for (const p of allPlayers()) {
    const s = state(p);
    const w = weaponOf(heldItem(p));
    const key = w?.key ?? null;
    if (key !== s.holdKey) {
      s.holdKey = key;
      onHoldChange?.(p, w);
    }
    const ground = !!p.isOnGround;
    let vel = { x: 0, y: 0, z: 0 };
    try { vel = p.getVelocity(); } catch (_) { }

    // ---- 着地 --------------------------------------------------------
    if (ground) {
      if (!s.ground && w && s.minVy < -0.95) heroLanding(p, w, s.minVy);
      s.airT = 0; s.jumps = 0; s.dashes = 0; s.minVy = 0;
      if (s.ground) s.noFall = false;
    } else {
      s.airT += 2;
      s.minVy = Math.min(s.minVy, vel.y);
    }
    s.ground = ground;

    const sneak = !!p.isSneaking;
    const sneakEdge = sneak && !s.sneak;
    s.sneak = sneak;
    const jump = jumpPressed(p);
    const jumpEdge = jump && !s.jump;
    s.jump = jump;
    if (!w) continue;
    const wt = WEIGHT[w.weight] ?? WEIGHT.mid;
    const t = now();

    // ---- 疾走 --------------------------------------------------------
    if (p.isSprinting && ground) {
      if (wt.sprint > 0) effect(p, "speed", 8, wt.sprint - 1);
      if (t % 4 === 0) {
        const f = flatDir(p);
        P(p.dimension, "wind", { x: p.location.x - f.x * 0.6, y: p.location.y + 0.2, z: p.location.z - f.z * 0.6 },
          { color: w.color, count: 1, dir: { x: -f.x, y: 0.05, z: -f.z }, speed: 4, size: 0.8, spread: 0.3 });
      }
    }

    // ---- 二段ジャンプ ------------------------------------------------
    if (!ground && jumpEdge && s.airT >= 4 && s.jumps < wt.airJumps && !p.isInWater) {
      s.jumps++;
      const f = flatDir(p);
      const hv = Math.hypot(vel.x, vel.z);
      const dir = hv > 0.05 ? { x: vel.x / hv, z: vel.z / hv } : { x: f.x, z: f.z };
      knock(p, dir.x, dir.z, Math.min(1.0, hv + TUNE.jumpCarry * 0.5), TUNE.jumpUp);
      s.noFall = true;
      s.minVy = 0;
      const l = p.location;
      P(p.dimension, "ring_flat", { x: l.x, y: l.y + 0.05, z: l.z }, { color: w.color, size: 1.3, life: 0.35 });
      P(p.dimension, "circle", { x: l.x, y: l.y + 0.02, z: l.z }, { color: w.color, size: 0.9, life: 0.45, spin: 240 });
      P(p.dimension, "dot", { x: l.x, y: l.y + 0.2, z: l.z }, { color: white(w.color, 0.4), count: 12, spread: 0.6, speed: 2.4, grav: -6 });
      sound(p.dimension, "hd.jump", l, 1.0 + s.jumps * 0.12, 0.8);
      body(p, "airjump", "hd.move");
      continue;
    }

    // ---- 空中ダッシュ -------------------------------------------------
    if (!ground && sneakEdge && s.airT >= 4 && s.dashes < wt.airDash) {
      s.dashes++;
      const f = flatDir(p);
      knock(p, f.x, f.z, TUNE.airDash, TUNE.airDashUp);
      s.noFall = true;
      s.minVy = 0;
      dashFx(p, w, f);
      sound(p.dimension, "hd.dash", p.location, 1.1, 0.9);
      body(p, "dash", "hd.move");
      continue;
    }

    // ---- 回避ステップ（スニーク 2 回押し） --------------------------------
    if (ground && sneakEdge) {
      if (t - s.lastSneak <= TUNE.stepWindow && t >= s.stepCd) {
        s.stepCd = t + TUNE.stepCooldown;
        s.lastSneak = -99;
        const hv = Math.hypot(vel.x, vel.z);
        const f = flatDir(p);
        const dir = hv > 0.04 ? { x: vel.x / hv, y: 0, z: vel.z / hv } : { x: -f.x, y: 0, z: -f.z };
        knock(p, dir.x, dir.z, TUNE.step, TUNE.stepUp);
        effect(p, "resistance", TUNE.iframes, 4);
        s.noFall = true;
        dashFx(p, w, dir);
        sound(p.dimension, "hd.step", p.location, 1.2, 0.9);
        body(p, "step", "hd.move");
      } else {
        s.lastSneak = t;
      }
    }
  }
}

function dashFx(p, w, dir) {
  const l = p.location;
  afterimage(p.dimension, l, w.color, 0.45);
  P(p.dimension, "speedline", { x: l.x, y: l.y + 1.0, z: l.z },
    { color: white(w.color, 0.3), count: 8, dir: { x: -dir.x, y: 0, z: -dir.z }, speed: 16, spread: 0.7 });
  P(p.dimension, "ring", { x: l.x, y: l.y + 1.0, z: l.z }, { color: w.color, size: 1.2, life: 0.22 });
  for (let i = 1; i <= 3; i++) {
    const d = i * 0.9;
    P(p.dimension, "trail", { x: l.x + dir.x * d, y: l.y + 1.0, z: l.z + dir.z * d },
      { color: w.color, size: 1.6 - i * 0.3, life: 0.2 });
  }
}

function heroLanding(p, w, vy) {
  const l = p.location;
  const k = Math.min(2.4, -vy);
  body(p, "land", "hd.move");
  P(p.dimension, "ring_flat", { x: l.x, y: l.y + 0.05, z: l.z }, { color: w.color, size: 1.6 + k, life: 0.45 });
  P(p.dimension, "dust", { x: l.x, y: l.y + 0.1, z: l.z }, { count: Math.round(10 + k * 6), spread: 0.4, speed: 4 + k * 2, size: 1.2 });
  ring(p.dimension, "spark", l, 0.8, 6, { color: w.color, count: 2, speed: 3 });
  sound(p.dimension, "hd.hit_heavy", l, 1.2, 0.5 + k * 0.2);
}

/** 落下ダメージを打ち消す（entityHurt から呼ぶ）。 */
export function cancelFall(p, damage) {
  const s = st.get(p.id);
  if (!s?.noFall) return false;
  const h = health(p);
  if (!h) return false;
  try {
    if (h.currentValue > 0) h.setCurrentValue(Math.min(h.effectiveMax, h.currentValue + damage));
    return true;
  } catch (_) { return false; }
}

export function forget(id) { st.delete(id); }
