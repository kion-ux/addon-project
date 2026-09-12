// 技 / 24枠の実行基盤
//
// 企画書 §10 の「使い回すのは実行基盤であり、全技を同じアニメと同じ爆発にしない」
// を守るための1本道。ここは時間と判定の面倒だけを見て、見た目の違いは
// spec.py の stages（層と並べ方）が作る。
//
//   予備動作(windup) → 有効時間(active) → 後隙(recover)
//
// 命中は必ず action_id 経由。粒子や表示体は攻撃責任を持たない（企画書 §09）。
import { system } from "@minecraft/server";
import { TECH_BY_ID, TECHS_BY_FORM } from "./data.js";
import { tr, tell, later, viewDir, normalise, forward, cooldownLeft,
  setCooldown, clamp, hasFamily,
} from "./util.js";
import { makeContext, playStage, playSfx, shake, spawnHelper, spawn,
} from "./fx.js";
import { beginAction, endAction, mayHit, inCone, alongRay, aroundPoint,
  allAround, impactPoint, groundUnder, strike, bounce, terrainAllowed,
} from "./combat.js";
import { phase, setPhase, formKey, quality, cameraFx, spend, energy,
  infinite, busy, setBusy, addHits, markFight, playAnim, selectedTech,
  techIndex, setTechIndex, beginCast, castIs, endCast,
} from "./state.js";

/** 押しっぱなし・連打で同じ発動が二重に走らないようにする受付間隔。 */
const INPUT_GAP = 4;
const lastUse = new Map();
const lastDeny = new Map();

function denySound(player) {
  const now = system.currentTick;
  if (now - (lastDeny.get(player.id) ?? -99) < 8) return;
  lastDeny.set(player.id, now);
  try {
    player.dimension.playSound("note.bass", player.location,
                               { volume: 0.4, pitch: 0.7 });
  } catch (_) { }
}

export function forgetPlayer(id) {
  lastUse.delete(id);
  lastDeny.delete(id);
}

// ---------------------------------------------------------------------------
//  技の切り替え（しゃがみ＋使用）
//  発動とは排他的に処理し、切替後に勝手に技が出ないようにする（企画書 §09）。
// ---------------------------------------------------------------------------
export function cycleTech(player, step = 1) {
  const form = formKey(player);
  if (!form) { tell(player, tr("gla.msg.not_transformed")); return; }
  const list = TECHS_BY_FORM[form] ?? [];
  if (list.length < 2) return;
  const next = (((techIndex(player, form) + step) % list.length) + list.length)
               % list.length;
  setTechIndex(player, form, next);
  // 切り替えだけで終わらせる。切替直後に技が漏れないよう、受付を
  // 通常より1つ分長く空ける（企画書 §09 切替後に勝手に技が出ない）。
  lastUse.set(player.id, system.currentTick + INPUT_GAP);
  const tech = TECH_BY_ID[list[next]];
  try {
    player.dimension.playSound("random.click", player.location,
                               { volume: 0.5, pitch: 1.4 });
  } catch (_) { }
  tell(player, { rawtext: [{ translate: "gla.msg.tech_selected" },
                           { text: " §e" }, { translate: tech.name }] });
}

// ---------------------------------------------------------------------------
//  発動
// ---------------------------------------------------------------------------
export function useSelected(player) {
  const form = formKey(player);
  if (!form) { tell(player, tr("gla.msg.not_transformed")); return false; }
  const id = selectedTech(player);
  if (!id) return false;
  return cast(player, TECH_BY_ID[id]);
}

export function cast(player, tech) {
  if (!tech) return false;

  const now = system.currentTick;
  if (now < (lastUse.get(player.id) ?? -99) + INPUT_GAP) return false;

  if (busy(player) || phase(player) === "transforming") { denySound(player); return false; }
  if (phase(player) === "attacking" || phase(player) === "recovering") {
    denySound(player);
    return false;
  }
  const left = cooldownLeft(player.id, tech.id);
  if (left > 0) {
    denySound(player);
    tell(player, tr("gla.msg.cooldown", String(Math.ceil(left / 20))));
    return false;
  }
  if (!infinite(player) && energy(player) < tech.cost) {
    denySound(player);
    tell(player, tr("gla.msg.no_energy"));
    return false;
  }
  // ここから先は必ず走り切る。ここまでで弾かないと、企画書 §09 の
  // 「多重受付を防ぐ」が守れない。
  lastUse.set(player.id, now);
  if (!spend(player, tech.cost)) { denySound(player); return false; }
  setCooldown(player.id, tech.id, tech.cd);
  setPhase(player, "attacking");
  setBusy(player, tech.windup + tech.active);
  markFight(player);
  playAnim(player, tech.anim);

  const token = beginCast(player);
  const actionId = beginAction(tech.hits, tech.gap);
  runStages(player, tech, actionId, token);
  runSfx(player, tech, token);
  scheduleHits(player, tech, actionId, token);
  applySelfBuffs(player, tech, token);
  applyLaunch(player, tech, token);

  later(tech.windup + tech.active, () => {
    if (!castIs(player, token)) return;
    if (phase(player) === "attacking") setPhase(player, "recovering");
  });
  later(tech.windup + tech.active + tech.recover, () => {
    endAction(actionId);
    if (!castIs(player, token)) return;
    endCast(player, token);
    if (phase(player) === "recovering") setPhase(player, "active");
  });
  return true;
}

// ---------------------------------------------------------------------------
//  演出 — 予約した時刻に1コマずつ流す
// ---------------------------------------------------------------------------
function runStages(player, tech, actionId, token) {
  const q = quality(player);
  for (const st of tech.stages) {
    // 「接触」の層で対象を原点にするコマは、ここでは絶対に流さない。
    // 当たったときに resolve() が実際の着弾点で出す。時間で出してしまうと
    // 空振りでも命中の演出が出て、位置も前回の着弾点になってしまう
    // （企画書 §11: 命中時のみ強くする。空振りと同じ演出にしない）。
    if (st.layer >= 3 && st.at === "target") continue;
    later(st.t + 1, () => {
      if (!stillCasting(player, token)) return;
      const ctx = makeContext(player, q, lastImpact.get(player.id));
      // 足元ではなく「実際の地面」に置きたいコマだけ取り直す。
      // 空中で撃ったときに叩きつけの演出が宙に浮かないように。
      if (st.at === "ground") ctx.ground = groundUnder(player);
      playStage(ctx, st);
    });
  }
  // 大技だけ、命中の瞬間に軽く揺らす。設定で切れる。
  if (tech.damage >= 24 && cameraFx(player)) {
    later(tech.windup + 2, () => {
      if (!stillCasting(player, token)) return;
      shake(player, clamp(tech.damage / 140, 0.1, 0.5), 0.28);
    });
  }
}

function runSfx(player, tech, token) {
  for (const s of tech.sfx) {
    later(s.t + 1, () => {
      if (!stillCasting(player, token)) return;
      playSfx(player.dimension, player.location, s);
    });
  }
}

function stillCasting(player, token) {
  if (token !== undefined && !castIs(player, token)) return false;
  try {
    if (!player.dimension) return false;
  } catch (_) { return false; }
  const p = phase(player);
  return p === "attacking" || p === "recovering";
}

// ---------------------------------------------------------------------------
//  判定 — shape ごとに違う形で取る
// ---------------------------------------------------------------------------
const lastImpact = new Map();    // playerId -> 直近の着弾点（演出の原点に使う）

function scheduleHits(player, tech, actionId, token) {
  if (tech.damage <= 0 && tech.shape !== "zone") return;
  const beats = Math.max(1, tech.hits);
  const gap = tech.gap || Math.max(1, Math.floor(tech.active / beats));

  if (tech.shape === "delayed") {
    // 予兆が地面を走ってから打ち上げる。避けられる時間を作る。
    later(tech.windup + Math.max(6, Math.floor(tech.active * 0.6)), () => {
      resolve(player, tech, actionId, token);
    });
    return;
  }
  if (tech.shape === "zone") {
    // 区域技は active の間、定期的に判定する
    const every = 10;
    for (let t = tech.windup; t < tech.windup + tech.active; t += every) {
      later(t + 1, () => resolveZone(player, tech, actionId, token));
    }
    return;
  }
  if (tech.shape === "projectile") {
    flyProjectile(player, tech, actionId, token);
    return;
  }
  if (tech.shape === "dash") {
    // 飛行中ずっと判定する
    for (let t = 0; t < tech.active; t += 2) {
      later(tech.windup + t + 1, () => resolve(player, tech, actionId, token));
    }
    return;
  }
  if (tech.shape === "line" && tech.reach >= 8) {
    later(tech.windup, () => { if (stillCasting(player, token)) throwFist(player, tech); });
  }
  for (let i = 0; i < beats; i++) {
    later(tech.windup + i * gap + 1, () => resolve(player, tech, actionId, token));
  }
}

/**
 * 伸びる拳の表示体。平面のパーティクルでは伸びる腕の立体感が出ないので、
 * 直線技だけは拳のモデルを飛ばす（企画書 §11 2Dと3Dを使い分ける）。
 *
 * 当たり判定はここに持たせない。判定は resolve() が action_id 経由で行う
 * （企画書 §09 見た目エンティティに独立した攻撃責任を持たせない）。
 * 予算を超えたら黙って粒子だけで済ませ、寿命が来たら必ず消す。
 */
function throwFist(player, tech) {
  const q = quality(player);
  const dir = normalise(viewDir(player));
  const loc = player.location;
  const start = { x: loc.x, y: loc.y + 1.3, z: loc.z };
  const fist = spawnHelper(player.dimension, "gla:vfx_fist",
                           forward(start, dir, 0.8), q);
  if (!fist) return;
  const outTicks = Math.max(2, Math.round(tech.active * 0.45));
  const total = outTicks * 2;
  for (let i = 1; i <= total; i++) {
    later(i, () => {
      // 往きは伸び、還りは縮む。腕が戻るところまで見せる。
      const t = i <= outTicks ? i / outTicks : (total - i) / outTicks;
      const at = forward(start, dir, 0.8 + tech.reach * t);
      try { fist.teleport(at, { facingLocation: forward(at, dir, 2) }); }
      catch (_) {
        try { fist.teleport(at); } catch (__) { }
      }
    });
  }
  later(total + 2, () => { try { fist.remove(); } catch (_) { } });
}

function targetsFor(player, tech) {
  const dir = normalise(viewDir(player));
  const loc = player.location;
  const origin = { x: loc.x, y: loc.y + 1.3, z: loc.z };
  switch (tech.shape) {
    case "line":
      // 伸びる拳 — 通過した軌道で当てる
      return alongRay(player, origin, dir, tech.reach, tech.radius);
    case "cone":
      return inCone(player, origin, dir, tech.reach, 42);
    case "arc":
      // 曲がる軌道。少し広めの角度で、射程は長い。
      return inCone(player, origin, dir, tech.reach, 58);
    case "slam": {
      // 叩きつけ — 前方の地面に落ちた点の周囲。前方打撃とは別物にする。
      const at = impactPoint(player, origin, dir, Math.max(2, tech.reach));
      return aroundPoint(player, { x: at.x, y: at.y - 0.3, z: at.z }, tech.radius);
    }
    case "sphere":
      // 宣言した全方位技だけがここへ来る（spec.ALL_AROUND）
      return allAround(player, tech.radius);
    case "dash":
      return inCone(player, origin, dir, Math.max(2.5, tech.radius * 1.6), 70);
    case "delayed": {
      // 地面を走ってから打ち上げる。着弾点からの見通しで判定するので、
      // 壁の裏には届かない（企画書 §09 壁越しの命中を除外する）。
      const at = impactPoint(player, origin, dir, tech.reach);
      return aroundPoint(player, { x: at.x, y: at.y - 0.4, z: at.z }, tech.radius);
    }
    default:
      return inCone(player, origin, dir, Math.max(2, tech.reach), 50);
  }
}

function resolve(player, tech, actionId, token) {
  if (!stillCasting(player, token)) return;
  const found = targetsFor(player, tech);
  if (!found.length) return;
  let landed = 0;
  for (const e of found) {
    if (!mayHit(actionId, e)) continue;
    let at;
    try { at = { x: e.location.x, y: e.location.y + 0.9, z: e.location.z }; }
    catch (_) { continue; }
    if (!strike(player, e, tech.damage, tech.kbH, tech.kbV, tech.fire)) continue;
    lastImpact.set(player.id, at);
    // 訓練用の標的に当たったときだけ、当たった位置へ印を出す。
    // 「拳が当たった場所を説明できるか」を確かめるための補助（企画書 §17）。
    if (hasFamily(e, "gla_target")) spawn(player.dimension, "gla:target_mark", at);
    landed++;
  }
  if (landed) {
    addHits(player, landed);
    markFight(player);
    // 接触の層だけは、命中したときにだけ出す（企画書 §11 空振りと同じ演出にしない）
    const ctx = makeContext(player, quality(player), lastImpact.get(player.id));
    for (const st of tech.stages) {
      if (st.layer >= 3 && st.at === "target") playStage(ctx, st);
    }
  }
}

function resolveZone(player, tech, actionId, token) {
  if (!stillCasting(player, token)) return;
  const centre = groundUnder(player);
  for (const e of aroundPoint(player, centre, tech.radius)) {
    if (!mayHit(actionId, e)) continue;
    if (tech.damage > 0) strike(player, e, tech.damage, 0, 0);
    bounce(e, tech.kbV || 1.0);
  }
}

/**
 * 飛翔体。表示体を出せたらそれを飛ばし、出せなければ判定だけ前に送る。
 * 表示体はあくまで見た目で、当たり判定はここが持つ（企画書 §09）。
 */
function flyProjectile(player, tech, actionId, token) {
  const q = quality(player);
  later(tech.windup + 1, () => {
    if (!stillCasting(player, token)) return;
    const dir = normalise(viewDir(player));
    const loc = player.location;
    const start = { x: loc.x, y: loc.y + 1.4, z: loc.z };
    const helper = spawnHelper(player.dimension, "gla:thrown_bolt", start, q);
    const speed = 1.6;
    const steps = Math.ceil(tech.reach / speed);
    for (let i = 1; i <= steps; i++) {
      later(i, () => {
        if (!stillCasting(player, token)) {
          if (helper) { try { helper.remove(); } catch (_) { } }
          return;
        }
        const at = forward(start, dir, speed * i);
        if (helper) { try { helper.teleport(at); } catch (_) { } }
        const near = aroundPoint(player, at, Math.max(1.2, tech.radius * 0.6));
        let landed = 0;
        for (const e of near) {
          if (!mayHit(actionId, e)) continue;
          if (strike(player, e, tech.damage, tech.kbH, tech.kbV, tech.fire)) landed++;
        }
        if (landed || i === steps) {
          lastImpact.set(player.id, at);
          if (landed) { addHits(player, landed); markFight(player); }
          if (helper) { try { helper.remove(); } catch (_) { } }
          const ctx = makeContext(player, q, at);
          for (const st of tech.stages) {
            if (st.layer >= 3 && st.at === "target") playStage(ctx, st);
          }
        }
      });
    }
    // 表示体は必ず片付ける。孤児にしない（企画書 §14 所有者と寿命）。
    later(steps + 6, () => { if (helper) { try { helper.remove(); } catch (_) { } } });
  });
}

// ---------------------------------------------------------------------------
//  自己強化と移動
// ---------------------------------------------------------------------------
function applySelfBuffs(player, tech, token) {
  if (!tech.buffs?.length) return;
  later(Math.max(1, tech.windup), () => {
    if (!castIs(player, token)) return;
    for (const [id, amp, ticks] of tech.buffs) {
      try {
        player.addEffect(id, ticks, { amplifier: amp, showParticles: false });
      } catch (_) { }
    }
  });
}

function applyLaunch(player, tech, token) {
  const [fwd, up] = tech.launch ?? [0, 0];
  if (!fwd && !up) return;
  later(Math.max(1, tech.windup), () => {
    if (!castIs(player, token)) return;
    try {
      const d = normalise(viewDir(player));
      const l = Math.hypot(d.x, d.z) || 1;
      player.applyKnockback(d.x / l, d.z / l, fwd, up);
    } catch (_) {
      try { player.applyKnockback({ x: 0, z: 0 }, fwd, up); } catch (__) { }
    }
  });
}

export function forgetImpact(id) {
  lastImpact.delete(id);
}

/**
 * 地形を変える技は、ホストが明示的に許可したときだけ。
 * 現状はどの技も地形を書き換えない — 許可されたときに「何が起きうるか」を
 * ここに集約しておき、勝手に増えないようにする（企画書 §09 / QA-10）。
 */
export function terrainEffect(player, tech, at) {
  if (!tech.terrain) return false;
  if (!terrainAllowed()) return false;
  // 許可されていても、行うのは足元の草を踏み荒らす程度の見た目変化に留める。
  // 実際のブロック破壊はホストの検証済みルールが決まるまで実装しない。
  return false;
}

export function cooldownInfo(player) {
  const form = formKey(player);
  if (!form) return [];
  return (TECHS_BY_FORM[form] ?? []).map((id) => ({
    id, left: cooldownLeft(player.id, id),
  }));
}
