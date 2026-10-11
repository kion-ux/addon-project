// ===========================================================================
//  立体機動装置 — アンカー・巻き取り・ガス・回転斬り・着地・刃の消耗
//
//  右クリックを押した瞬間に視線の先（45m）へアンカーを撃ち込み、押している間
//  ワイヤーを巻き取って体を引き寄せる。離すと切り離し、少しのあいだ慣性で飛ぶ。
//  ワイヤーの長さは巻き取るほど短くなり、伸びる向きの速度は打ち消す（振り子になる）。
//  プレイヤーの速度はノックバックで直接与える（applyKnockback は速度を置き換える）。
// ===========================================================================
import { EquipmentSlot, ItemStack } from "@minecraft/server";
import { GAS_MAX, ITEM, PROP, TUNE } from "./config.js";
import { P, blood, body, gasPuff, pose, slash, sound, steam, wire } from "./fx.js";
import {
  bladeCut, frame, isDying, isGrabbed, isTitan, rayTitans, struggle,
} from "./titans.js";
import {
  add, clamp, consume, container, count, damage, dist, dot, effect, equipped, eye, heldItem,
  isCreative, len, norm, now, numProp, rand, rt, scale, selectedSlot, setProp, setVelocity, sub, title,
  valid, velocity, viewDir, yawFrame,
} from "./util.js";

const S = new Map();     // playerId -> state

export function state(p) {
  let s = S.get(p.id);
  if (!s) {
    s = { anchor: null, reeling: false, rope: 0, releasedAt: -999, coastUntil: 0, coastV: null,
          spinCd: 0, boostCd: 0, sneak: false, jump: false, noFallUntil: 0, lastUse: -1,
          heldKey: null, posed: null, reelSnd: 0, lastBlades: null };
    S.set(p.id, s);
  }
  return s;
}

export function forget(id) { S.delete(id); }

// ---------------------------------------------------------------------------
//  装備とガス
// ---------------------------------------------------------------------------
export function wearsGear(p) { return equipped(p, EquipmentSlot.Legs)?.typeId === ITEM.gear; }
export function holdsBlades(p) { return heldItem(p)?.typeId === ITEM.blades; }

export function gas(p) { return isCreative(p) ? GAS_MAX : numProp(p, PROP.gas, GAS_MAX); }
export function useGas(p, n) {
  if (isCreative(p)) return true;
  const g = numProp(p, PROP.gas, GAS_MAX);
  if (g <= 0) return false;
  setProp(p, PROP.gas, Math.max(0, g - n));
  if (g - n <= 0) {
    title(p, rt(" "), rt("§c", { t: "aot.title.no_gas" }), 24);
  }
  return true;
}

export function refill(p) {
  if (numProp(p, PROP.gas, GAS_MAX) >= GAS_MAX - 0.5) {
    try { p.sendMessage(rt("§7", { t: "aot.msg.gas_full" })); } catch (_) { }
    return false;
  }
  setProp(p, PROP.gas, GAS_MAX);
  sound(p.dimension, "aot.gas", p.location, 0.7, 1.0);
  gasPuff(p.dimension, add(p.location, { x: 0, y: 0.9, z: 0 }), { x: 0, y: 0.4, z: 0 }, 1.2);
  try { p.sendMessage(rt("§b", { t: "aot.msg.gas_refilled" })); } catch (_) { }
  return true;
}

function hip(p, side = 0) {
  const { r } = yawFrame(p);
  return add(add(p.location, { x: 0, y: 0.85, z: 0 }), r, side * 0.32);
}

// ---------------------------------------------------------------------------
//  アンカー
// ---------------------------------------------------------------------------
/** アンカーを撃つ。巨人に当たれば巨人に刺さり、巨人が動けば一緒に動く。 */
export function fireAnchor(p) {
  const s = state(p);
  if (s.anchor) return;
  if (!wearsGear(p)) {
    title(p, rt(" "), rt("§7", { t: "aot.title.need_gear" }), 30);
    return;
  }
  if (isGrabbed(p)) return;
  if (gas(p) <= 0) {
    title(p, rt(" "), rt("§c", { t: "aot.title.no_gas" }), 24);
    sound(p.dimension, "random.click", p.location, 0.6, 0.8);
    return;
  }
  const o = eye(p);
  const dir = viewDir(p);
  const dim = p.dimension;
  let hit = null;
  try {
    const b = dim.getBlockFromRay(o, dir, { maxDistance: TUNE.anchorRange,
                                            includeLiquidBlocks: false, includePassableBlocks: false });
    if (b) {
      const at = add(b.block.location, b.faceLocation);
      hit = { pos: at, s: dist(o, at) };
    }
  } catch (_) { }
  const tHit = rayTitans(dim, o, dir, TUNE.anchorRange);
  sound(dim, "aot.anchor", p.location, rand(0.95, 1.1), 1.0);
  useGas(p, TUNE.gasAnchor);
  if (tHit && (!hit || tHit.s < hit.s)) {
    const t = tHit.entity;
    const { f, r } = yawFrame(t);
    const rel = sub(tHit.at, t.location);
    s.anchor = { entity: t, local: { f: dot(rel, f), r: dot(rel, r), y: rel.y } };
  } else if (hit) {
    s.anchor = { pos: hit.pos };
  } else {
    // 何にも刺さらない: ワイヤーが伸び切って戻るだけ
    const end = add(o, dir, TUNE.anchorRange);
    wire(dim, hip(p, -1), end, { life: 0.2 });
    wire(dim, hip(p, 1), end, { life: 0.2 });
    return;
  }
  const at = anchorPos(s);
  s.rope = dist(hip(p), at);
  s.reeling = true;
  sound(dim, "aot.hook", at, rand(0.9, 1.1), 1.0);
  P(dim, "spark", at, { count: 6, speed: 4 });
  if (s.anchor.entity) blood(dim, at, 0.5);
  pose(p, "fly");
  s.posed = "fly";
}

export function anchorPos(s) {
  const a = s.anchor;
  if (!a) return null;
  if (a.pos) return a.pos;
  const t = a.entity;
  if (!valid(t)) return null;
  const { f, r } = yawFrame(t);
  return add(add(add(t.location, f, a.local.f), r, a.local.r), { x: 0, y: a.local.y, z: 0 });
}

export function releaseAnchor(p, quiet = false) {
  const s = state(p);
  if (!s.anchor) return;
  s.anchor = null;
  s.reeling = false;
  s.releasedAt = now();
  s.coastUntil = now() + TUNE.coastTicks;
  s.coastV = velocity(p);
  if (!quiet) sound(p.dimension, "random.click", p.location, 1.4, 0.4);
}

// ---------------------------------------------------------------------------
//  毎 tick
// ---------------------------------------------------------------------------
export function tickODM(p) {
  const s = state(p);
  const t0 = now();
  const dim = p.dimension;
  const ground = !!p.isOnGround;
  const v = velocity(p);
  const blades = holdsBlades(p);
  const gear = wearsGear(p);

  // ---- 入力の立ち上がり ----
  const sneak = !!p.isSneaking;
  const sneakEdge = sneak && !s.sneak;
  s.sneak = sneak;
  const jump = p.isJumping === true;
  const jumpEdge = jump && !s.jump;
  s.jump = jump;

  // ---- 掴まれている: スニークで指を斬って抜ける ----
  if (isGrabbed(p)) {
    if (sneakEdge && blades && gas(p) >= 10) {
      useGas(p, 10);
      body(p, "spin");
      struggle(p, true);
    }
    return;
  }

  // ---- 持ち姿勢 ----
  const key = blades ? "blades" : (heldItem(p)?.typeId === ITEM.spear ? "spear" : null);
  if (key !== s.heldKey) {
    s.heldKey = key;
    pose(p, key === "blades" ? "hold" : key === "spear" ? "hold_spear" : null, "aot.hold");
    if (!blades && s.anchor) releaseAnchor(p, true);
  }

  // ---- アンカー: 巻き取り ----
  if (s.anchor) {
    const at = anchorPos(s);
    const from = hip(p);
    if (!at || !gear || (s.anchor.entity && isDying(s.anchor.entity) && dist(from, at) > 6)) {
      releaseAnchor(p);
    } else {
      const d = sub(at, from);
      const L = len(d);
      wire(dim, hip(p, -1), at);
      wire(dim, hip(p, 1), add(at, { x: 0, y: 0.15, z: 0 }));
      const sp0 = len(v);
      // 巨人に刺したまま、うなじの脇を勢いよく抜けたら斬る（着く直前も含む）
      const t = s.anchor.entity;
      if (t && valid(t) && blades && (sp0 > 0.5 || L < TUNE.arrive) && passNape(p, t, v)) {
        // 斬って離脱した
      } else if (L < TUNE.arrive) {
        releaseAnchor(p, true);
        setVelocity(p, { x: v.x * 0.6, y: Math.max(v.y, 0.42), z: v.z * 0.6 });
      } else if (L > TUNE.anchorRange + 6) {
        releaseAnchor(p);
      } else if (s.reeling) {
        if (!useGas(p, TUNE.gasReel)) {
          releaseAnchor(p);
        } else {
          const dir = scale(d, 1 / L);
          let nv = add(add(v, dir, TUNE.reelAccel), { x: 0, y: TUNE.reelLift, z: 0 });
          s.rope = Math.min(s.rope, L);
          const radial = dot(nv, dir);
          if (radial < 0) nv = sub(nv, scale(dir, radial));
          const sp = len(nv);
          if (sp > TUNE.maxSpeed) nv = scale(nv, TUNE.maxSpeed / sp);
          setVelocity(p, nv);
          s.noFallUntil = t0 + 60;
          if (t0 >= s.reelSnd) {
            s.reelSnd = t0 + 9;
            sound(dim, "aot.reel", p.location, 0.9 + Math.min(0.5, sp * 0.3), 0.5);
          }
          if (t0 % 2 === 0) gasPuff(dim, add(p.location, { x: 0, y: 0.8, z: 0 }), scale(dir, -1), 0.6);
          if (sp > 1.1 && t0 % 3 === 0) {
            P(dim, "speedline", add(p.location, { x: 0, y: 1.0, z: 0 }), { dir: scale(dir, -1), count: 3 });
          }
        }
      }
    }
  } else if (t0 < s.coastUntil && !ground && s.coastV) {
    // ---- 切り離した後の滑空: バニラより弱い空気抵抗で弧を描く ----
    const c = s.coastV;
    const nv = { x: c.x * TUNE.coastDrag, y: Math.min(v.y, c.y - 0.07), z: c.z * TUNE.coastDrag };
    s.coastV = nv;
    if (Math.hypot(nv.x, nv.z) > 0.25) setVelocity(p, nv);
  }

  // ---- 空中でジャンプ: ガス噴射 ----
  if (gear && blades && !ground && jumpEdge && t0 >= s.boostCd) {
    if (useGas(p, TUNE.gasBoost)) {
      s.boostCd = t0 + TUNE.boostCd;
      const d = viewDir(p);
      const nv = add(scale(v, 0.4), d, TUNE.boost);
      setVelocity(p, { x: nv.x, y: Math.max(nv.y, 0.2), z: nv.z });
      s.coastUntil = t0 + TUNE.coastTicks;
      s.coastV = nv;
      s.releasedAt = t0;
      s.noFallUntil = t0 + 60;
      gasPuff(dim, add(p.location, { x: 0, y: 0.8, z: 0 }), scale(d, -1), 1.6);
      sound(dim, "aot.boost", p.location, rand(0.95, 1.1), 1.0);
      body(p, "boost");
    }
  }

  // ---- 空中でスニーク: 回転斬り ----
  if (gear && blades && !ground && sneakEdge && t0 >= s.spinCd) {
    if (useGas(p, TUNE.gasSpin)) {
      s.spinCd = t0 + TUNE.spinCd;
      spin(p);
    }
  }

  // ---- 着地の直前にガスを噴いて衝撃を殺す ----
  if (gear && !ground && !s.anchor && v.y < -0.75 && gas(p) > 0) {
    let below = 99;
    try {
      const b = dim.getBlockFromRay(p.location, { x: 0, y: -1, z: 0 },
                                    { maxDistance: 6, includeLiquidBlocks: true, includePassableBlocks: false });
      if (b) below = p.location.y - (b.block.location.y + b.faceLocation.y);
    } catch (_) { }
    if (below < Math.max(1.8, -v.y * 3.2)) {
      useGas(p, TUNE.gasBrake);
      effect(p, "resistance", 30, 4);
      s.noFallUntil = t0 + 40;
      setVelocity(p, { x: v.x * 0.7, y: -0.32, z: v.z * 0.7 });
      gasPuff(dim, p.location, { x: 0, y: -1, z: 0 }, 1.4);
      sound(dim, "aot.gas", p.location, 1.1, 0.8);
    }
  }

  // ---- 姿勢: 飛んでいる間は飛行姿勢 ----
  const flying = !ground && (s.anchor || t0 < s.coastUntil);
  if (flying && s.posed !== "fly") { pose(p, "fly"); s.posed = "fly"; }
  if (!flying && s.posed === "fly") { pose(p, null); s.posed = null; }

  // ---- 刃が折れて手から消えたら、替え刃から新しい刃を出す ----
  watchBlades(p, s);
}

/** 巻き取りでうなじの脇を抜けたか。抜けたら斬って、巨人から離れる向きへ跳ぶ。 */
function passNape(p, t, v) {
  const F = frame(t);
  if (dist(eye(p), F.nape) > F.radius + TUNE.passRadius) return false;
  swingAt(p, t, "pass");
  releaseAnchor(p, true);
  const out = norm({ x: -F.f.x + v.x * 0.5, y: 0.5, z: -F.f.z + v.z * 0.5 });
  setVelocity(p, scale(out, 0.9));
  return true;
}

/** 落下ダメージを消すか（entityHurt から呼ぶ）。 */
export function shouldCancelFall(p) {
  const s = S.get(p.id);
  return !!s && now() < s.noFallUntil;
}

// ---------------------------------------------------------------------------
//  斬撃
// ---------------------------------------------------------------------------
/** 勢いがあるか（うなじを深く削げるか）。 */
export function hasMomentum(p) {
  const s = state(p);
  const v = velocity(p);
  return len(v) >= TUNE.fastSpeed || !!s.anchor || now() - s.releasedAt <= TUNE.recentWire;
}

/** 巨人を刃で斬る（通常攻撃・脇を抜ける・回転斬り）。 */
export function swingAt(p, t, kind) {
  const res = bladeCut(p, t, kind, kind !== "hit" || hasMomentum(p));
  const dim = p.dimension;
  const at = add(eye(p), viewDir(p), 1.2);
  if (res === "nape") {
    body(p, kind === "spin" ? "spin" : "slash");
    wearBlades(p, 2);
  } else if (res === "shallow") {
    title(p, rt(" "), rt("§e", { t: "aot.title.shallow" }), 20);
    wearBlades(p, 1);
  } else if (res === "ankle") {
    title(p, rt(" "), rt("§6", { t: "aot.title.ankle" }), 20);
  } else if (res === "eyes") {
    title(p, rt(" "), rt("§6", { t: "aot.title.eyes" }), 20);
  } else if (res === "body") {
    sound(dim, "aot.cut", at, rand(0.9, 1.1), 0.8);
  }
  // 普通の当たりの刃こぼれはバニラの耐久が受け持つ。限界なら替え刃に交換するだけ
  if (res !== "nape" && res !== "shallow") wearBlades(p, 0);
  slash(dim, at, rand(-40, 40), 1.6);
  return res;
}

function spin(p) {
  const dim = p.dimension;
  body(p, "spin");
  sound(dim, "aot.swing", p.location, 0.8, 1.2);
  sound(dim, "aot.gas", p.location, 1.2, 0.8);
  const c = add(p.location, { x: 0, y: 1.0, z: 0 });
  for (let i = 0; i < 6; i++) slash(dim, add(c, { x: rand(-1, 1), y: rand(-0.5, 0.5), z: rand(-1, 1) }), i * 60, 2.0);
  gasPuff(dim, c, { x: 0, y: -1, z: 0 }, 1.0);
  let near = [];
  try { near = dim.getEntities({ location: c, maxDistance: 14 }); } catch (_) { }
  let hits = 0;
  for (const e of near) {
    if (e.id === p.id || e.typeId === "minecraft:item" || e.typeId === "minecraft:xp_orb") continue;
    if (isTitan(e)) {
      const F = frame(e);
      if (dist(c, F.nape) <= F.radius + TUNE.spinRadius) {
        swingAt(p, e, "spin");
        hits++;
      } else if (dist(c, e.location) < 3 + F.H * 0.1 || Math.abs(c.y - e.location.y) < F.H &&
                 Math.hypot(c.x - e.location.x, c.z - e.location.z) < 2.6) {
        damage(e, 5, p, "entityAttack");
        hits++;
      }
    } else if (dist(c, e.location) < TUNE.spinRadius && !e.typeId.startsWith("aot:")
               && e.typeId !== "minecraft:player") {
      damage(e, 7, p, "entityAttack");
      hits++;
    }
  }
  if (hits) wearBlades(p, 1);
}

// ---------------------------------------------------------------------------
//  刃の消耗と交換
// ---------------------------------------------------------------------------
export function wearBlades(p, n) {
  if (isCreative(p)) return;
  const inv = container(p);
  if (!inv) return;
  const slot = selectedSlot(p);
  const it = inv.getItem(slot);
  if (it?.typeId !== ITEM.blades) return;
  let d;
  try { d = it.getComponent("minecraft:durability"); } catch (_) { }
  if (!d) return;
  const next = d.damage + n;
  if (next >= d.maxDurability - 2) {
    swapBlades(p, slot, it);
    return;
  }
  try { d.damage = next; inv.setItem(slot, it); } catch (_) { }
}

/** 刃こぼれした刃を捨てて、替え刃を差し込む。 */
export function swapBlades(p, slot, it) {
  const inv = container(p);
  const dim = p.dimension;
  if (!consume(p, ITEM.spare, 1)) {
    title(p, rt(" "), rt("§c", { t: "aot.title.no_spare" }), 30);
    return false;
  }
  try {
    const fresh = it ?? new ItemStack(ITEM.blades, 1);
    const d = fresh.getComponent("minecraft:durability");
    if (d) d.damage = 0;
    inv.setItem(slot, fresh);
  } catch (_) { }
  body(p, "reload");
  sound(dim, "aot.swap", p.location, rand(0.95, 1.05), 1.0);
  P(dim, "spark", add(p.location, { x: 0, y: 0.9, z: 0 }), { count: 6, speed: 3 });
  try { p.sendMessage(rt("§7", { t: "aot.msg.swapped", w: [count(p, ITEM.spare)] })); } catch (_) { }
  return true;
}

function watchBlades(p, s) {
  const inv = container(p);
  if (!inv) return;
  const slot = selectedSlot(p);
  const it = inv.getItem(slot);
  if (it?.typeId === ITEM.blades) {
    let wear = 0;
    try {
      const d = it.getComponent("minecraft:durability");
      wear = d ? d.damage / Math.max(1, d.maxDurability) : 0;
    } catch (_) { }
    s.lastBlades = { slot, t: now(), wear };
    return;
  }
  // 直前まで刃こぼれした刃を持っていた枠が空になった = 折れた（捨てた時は交換しない）
  if (s.lastBlades && s.lastBlades.slot === slot && !it && now() - s.lastBlades.t <= 2
      && s.lastBlades.wear >= 0.85) {
    s.lastBlades = null;
    sound(p.dimension, "aot.break", p.location, 1.0, 1.0);
    if (count(p, ITEM.spare) > 0) swapBlades(p, slot, new ItemStack(ITEM.blades, 1));
  } else if (s.lastBlades && now() - s.lastBlades.t > 2) {
    s.lastBlades = null;
  }
}

export { steam, clamp };
