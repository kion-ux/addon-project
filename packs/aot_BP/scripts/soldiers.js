// ===========================================================================
//  調査兵団（味方 NPC）の立体機動
//
//  巨人を見つけると: アンカーを巨人の肩に刺す → ワイヤーで飛ぶ → うなじの後ろへ
//  回り込んで回転斬り → 離脱して着地。成功率と間隔はキャラごと（config.SKILL）。
//  失敗すると、巨人の手に捕まることもある（プレイヤーが助けられる）。
//  エルヴィンが近くにいると、周りの兵士と仲間のプレイヤーが奮い立つ（心臓を捧げよ）。
// ===========================================================================
import { SKILL, SOLDIER_TYPES } from "./config.js";
import { P, gasPuff, slash, sound, wire } from "./fx.js";
import { frame, isDying, isGrabbed, isTitan, napeKill, tryGrab, typeOf } from "./titans.js";
import {
  add, damage, dims, dist, effect, event, health, len, norm, now, rand, scale, setVelocity, sub,
  valid, yawFrame,
} from "./util.js";

const SOLDIERS = new Set(SOLDIER_TYPES);
const A = new Map();      // id -> { phase, titan, anchorLocal, t0, cd, side }

export const isSoldier = (e) => !!e && SOLDIERS.has(e.typeId);

function rec(e) {
  let r = A.get(e.id);
  if (!r) {
    r = { phase: "idle", cd: now() + Math.round(rand(20, 60)), side: Math.random() < 0.5 ? -1 : 1 };
    A.set(e.id, r);
  }
  return r;
}

function setPhase(e, r, phase, state) {
  r.phase = phase;
  r.t0 = now();
  if (state) event(e, `aot:st_${state}`);
}

function nearestTitan(e, radius) {
  let best = null;
  let bd = 1e9;
  let list = [];
  try { list = e.dimension.getEntities({ location: e.location, maxDistance: radius, families: ["titan"] }); }
  catch (_) { return null; }
  for (const t of list) {
    if (!isTitan(t) || isDying(t)) continue;
    const d = dist(e.location, t.location);
    if (d < bd) { bd = d; best = t; }
  }
  return best;
}

function anchorWorld(r) {
  const t = r.titan;
  const { f, r: right } = yawFrame(t);
  return add(add(add(t.location, f, r.anchor.f), right, r.anchor.r), { x: 0, y: r.anchor.y, z: 0 });
}

/** 2 tick ごと。 */
export function tickSoldiers() {
  const t0 = now();
  const alive = new Set();
  for (const dim of dims()) {
    let list = [];
    try { list = dim.getEntities({ families: ["aot_soldier"] }); } catch (_) { continue; }
    for (const e of list) {
      if (!isSoldier(e)) continue;
      alive.add(e.id);
      if (isGrabbed(e)) continue;
      const r = rec(e);
      const skill = SKILL[e.typeId] ?? SKILL["aot:survey_soldier"];
      switch (r.phase) {
        case "idle": {
          if (t0 < r.cd) break;
          const t = nearestTitan(e, 30);
          if (!t) { r.cd = t0 + 20; break; }
          const F = frame(t);
          // 肩（うなじの横）に刺す
          r.titan = t;
          r.side = -r.side;
          r.anchor = { f: -F.m.napeZ * F.H, r: r.side * F.H * 0.12, y: F.m.napeY * F.H * 0.96 };
          setPhase(e, r, "fly", "fly");
          sound(dim, "aot.anchor", e.location, rand(0.95, 1.1), 0.8);
          break;
        }
        case "fly": {
          const t = r.titan;
          if (!valid(t) || isDying(t) || t0 - r.t0 > 60) { setPhase(e, r, "retreat", "fly"); break; }
          const F = frame(t);
          const at = anchorWorld(r);
          const from = add(e.location, { x: 0, y: 0.9, z: 0 });
          wire(dim, from, at);
          // うなじの後ろ上へ回り込む
          const goal = add(add(F.nape, F.f, -F.radius * 1.6), { x: 0, y: F.radius * 0.6, z: 0 });
          const d = sub(goal, from);
          const L = len(d);
          if (L < 1.6 + F.radius * 0.5) { setPhase(e, r, "slash", "slash"); break; }
          const sp = Math.min(1.25, 0.5 + L * 0.08);
          setVelocity(e, scale(norm(d), sp));
          if (t0 % 2 === 0) gasPuff(dim, from, scale(norm(d), -1), 0.5);
          if (t0 % 8 === 0) sound(dim, "aot.reel", e.location, 1.1, 0.4);
          break;
        }
        case "slash": {
          const t = r.titan;
          if (!valid(t) || isDying(t)) { setPhase(e, r, "retreat", "fly"); break; }
          if (t0 - r.t0 === 2) {
            const F = frame(t);
            sound(dim, "aot.swing", e.location, 1.0, 1.0);
            slash(dim, F.nape, rand(0, 360), F.radius * 2.2);
            if (Math.random() < skill.rate) {
              napeKill(t, e);
            } else {
              // 浅い。巨人が振り向いて掴みにくることがある
              const h = health(t);
              damage(t, (h?.effectiveMax ?? 100) * 0.15, e, "entityAttack");
              P(dim, "blood", F.nape, { count: 8, speed: 4 });
              if (typeOf(t).grab && Math.random() < 0.3) tryGrab(t, e);
            }
          }
          if (skill.twin && t0 - r.t0 === 8 && valid(t) && !isDying(t)) {
            const F = frame(t);
            slash(dim, F.nape, rand(0, 360), F.radius * 2.0);
            if (Math.random() < skill.rate) napeKill(t, e);
          }
          if (t0 - r.t0 >= 10) setPhase(e, r, "retreat", "fly");
          break;
        }
        case "retreat": {
          const t = r.titan;
          if (t0 - r.t0 === 0 || t0 - r.t0 === 1) {
            const away = valid(t) ? norm({ x: e.location.x - t.location.x, y: 0, z: e.location.z - t.location.z })
              : { x: 0, y: 0, z: 0 };
            setVelocity(e, { x: away.x * 0.9, y: 0.55, z: away.z * 0.9 });
            gasPuff(dim, add(e.location, { x: 0, y: 0.8, z: 0 }), { x: -away.x, y: -0.5, z: -away.z }, 1.0);
          }
          if ((e.isOnGround && t0 - r.t0 > 6) || t0 - r.t0 > 50) {
            setPhase(e, r, "idle", "idle");
            r.cd = t0 + skill.cd + Math.round(rand(0, 20));
          }
          break;
        }
        default:
          r.phase = "idle";
      }
    }
  }
  for (const id of [...A.keys()]) if (!alive.has(id)) A.delete(id);
}

/** 10 秒ごと: エルヴィンの号令。巨人が近くにいる時だけ。 */
export function tickRally() {
  for (const dim of dims()) {
    let erwins = [];
    try { erwins = dim.getEntities({ type: "aot:erwin_smith" }); } catch (_) { continue; }
    for (const e of erwins) {
      let near = [];
      try { near = dim.getEntities({ location: e.location, maxDistance: 32, families: ["titan"] }); } catch (_) { }
      if (!near.length) continue;
      sound(dim, "aot.kill", e.location, 0.7, 1.4);
      P(dim, "ring", add(e.location, { x: 0, y: 1, z: 0 }), { size: 8, life: 0.6, color: [0.6, 0.9, 0.7] });
      let allies = [];
      try { allies = dim.getEntities({ location: e.location, maxDistance: 20 }); } catch (_) { }
      for (const a of allies) {
        if (a.typeId !== "minecraft:player" && !isSoldier(a)) continue;
        effect(a, "strength", 220, 0, false);
        effect(a, "speed", 220, 0, false);
        if (a.typeId === "minecraft:player") {
          try { a.onScreenDisplay.setActionBar({ rawtext: [{ text: "§a" }, { translate: "aot.msg.rally" }] }); }
          catch (_) { }
        }
      }
    }
  }
}

export function forgetSoldier(id) { A.delete(id); }
export { dist };
