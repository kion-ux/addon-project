// ===========================================================================
//  技システム / Technique system
//  武器を持ってスニークすると技を「切り返し」、右クリックで発動する。
//
//  ✅ 印は原作にある技（保科流刀伐術／抜討術・隊式斧術・隊式銃剣術）、
//  ⚠️ 印は原作に技名が存在せず本アドオンで名付けたもの。
// ===========================================================================
import { system } from "@minecraft/server";
import { actionbar, knockback, forward } from "./util.js";
import {
  fx, fxRing, fxLine, fxScatter, fxArc, fxSpiral, fxColumn, fxCone, fxWall,
  sequence, trail, sound, shake, shakeNearby, cone, ray, hit,
  bleed, later, targetsNear,
} from "./effects.js";
import { NUMBERS, wornNumbers, setAbilityById } from "./numbers.js";

const SEL = "kaiju8:tech_select";

// ---------------------------------------------------------------- helpers
function swing(player, ctx, opt) {
  const hits = cone(player, opt.radius, opt.dot);
  for (const h of hits) {
    if (!hit(player, h.entity, opt.damage * ctx.mult)) continue;
    bleed(h.entity);
    if (opt.kb) knockback(h.entity, h.dx, h.dz, opt.kb, opt.up ?? 0.2);
    if (opt.particle) {
      fxScatter(player.dimension, opt.particle,
                { x: h.entity.location.x, y: h.entity.location.y + 1,
                  z: h.entity.location.z }, 3, 0.6);
    }
    if (opt.effect) opt.effect(player, h.entity);
  }
  return hits.length;
}

function ahead(player, distance = 1.9) {
  return forward(player.getHeadLocation(), player.getViewDirection(), distance);
}

function arcFx(player, distance = 1.9, id = "kaiju8:slash_air") {
  fx(player.dimension, id, ahead(player, distance));
}

function dash(player, power, lift = 0.28, jets = true) {
  const dir = player.getViewDirection();
  knockback(player, dir.x, dir.z, power, lift);
  fxScatter(player.dimension, "kaiju8:dash_dust", player.location, 8, 0.7);
  if (jets) fx(player.dimension, "kaiju8:energy_boost", ahead(player, 0.6));
}

function afterimages(player, ticks = 8) {
  for (let i = 0; i < ticks; i++) {
    later(i * 2, () => {
      try {
        fx(player.dimension, "kaiju8:afterimage",
           { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
      } catch (_) { }
    });
  }
}

/** 斬った跡。怪獣は紫の体液を噴く。 */
function wound(player, target, jets = 3, spread = 0.4) {
  const at = { x: target.location.x, y: target.location.y + 1.1, z: target.location.z };
  fx(player.dimension, "kaiju8:blood_mist", at);
  fxScatter(player.dimension, "kaiju8:sever_spurt",
            { x: at.x, y: at.y - 0.1, z: at.z }, jets, spread);
}

/** ray() は距離順に並んでいるので、奥の敵ほど遅れて斬れる。 */
function inDepth(hits, per, fn) {
  hits.forEach((h) => later(Math.floor(h.along / per), () => {
    try { fn(h); } catch (_) { }
  }));
}

function ground(player) {
  return { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
}

/** `muzzle` に null を渡すと共通の銃口炎を出さない（武器ごとに火を変えたいとき）。 */
function shoot(player, typeId, speed, spread = 0, muzzle = "kaiju8:muzzle_flash") {
  const dir = player.getViewDirection();
  const origin = forward(player.getHeadLocation(), dir, 0.9);
  let proj;
  try { proj = player.dimension.spawnEntity(typeId, origin); } catch (_) { return; }
  try {
    const pc = proj.getComponent("minecraft:projectile");
    if (pc) {
      pc.owner = player;
      pc.shoot({
        x: (dir.x + (Math.random() - 0.5) * spread) * speed,
        y: (dir.y + (Math.random() - 0.5) * spread) * speed,
        z: (dir.z + (Math.random() - 0.5) * spread) * speed,
      });
    }
  } catch (_) { }
  if (muzzle) {
    fx(player.dimension, muzzle, origin);
    fxScatter(player.dimension, "kaiju8:muzzle_sparks", origin, 5, 0.25);
  }
  return proj;
}

// 拳銃の連射リズム。何発目かで薬莢・曳光・反動の向きが変わる
const pistolBeat = new Map();

// 跳躍系は着地で炸裂する
const pendingSlams = new Map();

export function registerSlam(player, mult, kind) {
  pendingSlams.set(player.id, { at: system.currentTick, mult, player, kind });
}

// ===========================================================================
//  技定義
// ===========================================================================
export const TECH = {
  // ---- 戦闘用ナイフ（一般隊員の標準装備。刀ではない） ------------------
  "kaiju8:combat_knife": [
    { id: "slash", name: "kaiju8.tech.slash", cd: 22, wear: 1, canon: false,
      // 斬撃 — 手首を二度返す。二の太刀は傾きを反転させるので必ず×に交差する。
      // 刀の太い三日月ではなく、極細の弧を7点で並べる。
      run(player, ctx) {
        const head = player.getHeadLocation();
        const dir = player.getViewDirection();
        const origin = { x: head.x, y: head.y - 0.25, z: head.z };
        const struck = [];
        fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 1.15));
        fxArc(player.dimension, "kaiju8:cut_arc_white", origin, dir, 1.35, 95, 7, 0.30);
        for (const h of cone(player, 3.2, 0.45)) {
          if (!hit(player, h.entity, 5 * ctx.mult)) continue;
          bleed(h.entity);
          struck.push(h.entity);
          knockback(h.entity, h.dx, h.dz, 0.25, 0.2);
          fxScatter(player.dimension, "kaiju8:blade_dust",
                    { x: h.entity.location.x, y: h.entity.location.y + 1,
                      z: h.entity.location.z }, 3, 0.5);
        }
        sound(player.dimension, "mob.ravager.bite", player.location,
              { pitch: 1.9, volume: 0.5 });
        sound(player.dimension, "random.click", player.location,
              { pitch: 2.0, volume: 0.4 });
        shake(player, 0.06, 0.10, "rotational");
        later(3, () => {
          const h2 = player.getHeadLocation();
          const d2 = player.getViewDirection();
          fxArc(player.dimension, "kaiju8:cut_arc_white",
                { x: h2.x, y: h2.y - 0.25, z: h2.z }, d2, 1.5, 105, 7, -0.34);
          for (const h of cone(player, 3.6, 0.35)) {
            if (!hit(player, h.entity, 6 * ctx.mult)) continue;
            bleed(h.entity);
            struck.push(h.entity);
            knockback(h.entity, h.dx, h.dz, 0.6, 0.15);
          }
          sound(player.dimension, "mob.ravager.bite", player.location,
                { pitch: 1.55, volume: 0.7 });
          shake(player, 0.11, 0.16, "rotational");
        });
        later(5, () => {
          // 空振りなら音も揺れも出さない。外したことが読めるように
          for (const target of struck) {
            try {
              fxScatter(player.dimension, "kaiju8:blood_splash",
                        { x: target.location.x, y: target.location.y + 1.1,
                          z: target.location.z }, 4, 0.5);
            } catch (_) { }
          }
        });
      } },
    { id: "thrust", name: "kaiju8.tech.thrust", cd: 34, wear: 1, canon: false,
      // 刺突 — 間合いを測る → 体重を乗せて刺す → 抜いた瞬間に噴く。
      // 指向マークが突き線上に積み上がり、体液は必ず貫通方向の向こう側へ出る。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:chevron_white", ahead(player, 1.0));
        fx(player.dimension, "kaiju8:chevron_white", ahead(player, 1.7));
        sound(player.dimension, "random.click", player.location,
              { pitch: 1.9, volume: 0.5 });
        dash(player, 1.15, 0.05, false);
        later(2, () => {
          fxLine(player.dimension, "kaiju8:chevron_white", eye, dir, 3.6, 0.9);
          let n = 0;
          for (const h of ray(player, 4.2, 0.9)) {
            if (!hit(player, h.entity, 13 * ctx.mult)) continue;
            bleed(h.entity);
            n++;
            const at = h.entity.location;
            fx(player.dimension, "kaiju8:pierce_hole",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fxScatter(player.dimension, "kaiju8:blood_splash",
                      forward(at, dir, 0.85), 7, 0.5);
          }
          sound(player.dimension, "item.trident.riptide_1", player.location,
                { pitch: 2.05, volume: 0.55 });
          if (n) {
            sound(player.dimension, "mob.ravager.bite", player.location,
                  { pitch: 0.85, volume: 0.5 });
            shake(player, 0.18, 0.14);
            later(2, () => {
              fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 1.35));
              fxScatter(player.dimension, "kaiju8:blade_dust",
                        ahead(player, 1.3), 4, 0.35);
            });
          }
        });
      } },
  ],

  // ---- DF-STD ライフル（ユニソケット弾） --------------------------------
  "kaiju8:df_rifle": [
    { id: "socket_burst", name: "kaiju8.tech.socket_burst", cd: 26, wear: 1,
      canon: true,
      // ユニソケット 炸裂弾 — 装填チットが落ち、弾が橙の線を引いて飛び、
      // 着弾のあとにもう一度炸ぜる。揺れは射手ではなく着弾点に置く。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:chit_he",
           forward({ x: eye.x, y: eye.y - 0.25, z: eye.z }, dir, 0.7));
        const origin = forward(eye, dir, 0.9);
        const proj = shoot(player, "kaiju8:df_bullet", 3.0, 0.03, null);
        fx(player.dimension, "kaiju8:muzzle_flash", origin);
        fx(player.dimension, "kaiju8:muzzle_he", origin);
        if (proj) trail(proj, "kaiju8:tracer_gold", 8, 1, 0.1);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.9, volume: 0.28 });
        sound(player.dimension, "note.hat", player.location,
              { pitch: 1.4, volume: 0.5 });
        shake(player, 0.05, 0.08, "rotational");
        later(3, () => {
          const h = ray(player, 26, 1.0)[0];
          const at = h ? h.entity.location : forward(eye, dir, 18);
          const spot = { x: at.x, y: at.y, z: at.z };
          fx(player.dimension, "kaiju8:tube_flash",
             { x: spot.x, y: spot.y + 1.0, z: spot.z });
          fxScatter(player.dimension, "kaiju8:steel_shard", spot, 8, 0.9);
          for (const t of targetsNear(player, 30)) {
            const d = Math.hypot(t.location.x - spot.x, t.location.z - spot.z);
            if (d <= 2.2 && hit(player, t, 8 * ctx.mult)) bleed(t);
          }
          later(2, () => {
            fx(player.dimension, "kaiju8:tube_flash",
               { x: spot.x + 0.35, y: spot.y + 1.25, z: spot.z - 0.2 });
            fxScatter(player.dimension, "kaiju8:steel_shard", spot, 4, 1.4);
            for (const t of targetsNear(player, 30)) {
              const d = Math.hypot(t.location.x - spot.x, t.location.z - spot.z);
              if (d <= 2.2 && hit(player, t, 6 * ctx.mult)) bleed(t);
            }
            sound(player.dimension, "random.explode", spot,
                  { pitch: 1.35, volume: 0.5 });
            shakeNearby(player.dimension, spot, 8, 0.16, 0.18);
          });
        });
      } },
    { id: "socket_freeze", name: "kaiju8.tech.socket_freeze", cd: 30, wear: 1,
      canon: true,
      // ユニソケット 凍結弾 — 冷気が輪で広がり、足元に霜柱が円で立ち、
      // 鈍足が効いているあいだずっと霜が見える。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:chit_ice",
           forward({ x: eye.x, y: eye.y - 0.25, z: eye.z }, dir, 0.7));
        const proj = shoot(player, "kaiju8:df_bullet", 2.8, 0, null);
        fx(player.dimension, "kaiju8:muzzle_frost", forward(eye, dir, 0.9));
        if (proj) trail(proj, "kaiju8:tracer_frost", 10, 1, 0.1);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.55, volume: 0.28 });
        sound(player.dimension, "random.glass", player.location,
              { pitch: 1.95, volume: 0.35 });
        shake(player, 0.05, 0.10, "rotational");
        later(3, () => {
          const struck = [];
          for (const h of ray(player, 26, 2.4)) {
            if (!hit(player, h.entity, 5 * ctx.mult)) continue;
            bleed(h.entity);
            struck.push(h.entity);
            const at = h.entity.location;
            try {
              h.entity.addEffect("slowness", 160, { amplifier: 3, showParticles: true });
              h.entity.addEffect("weakness", 120, { amplifier: 1, showParticles: false });
            } catch (_) { }
            fx(player.dimension, "kaiju8:halo_ice",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fxRing(player.dimension, "kaiju8:ice_spike", at, 1.3, 9, 0.1);
            fxScatter(player.dimension, "kaiju8:frost_dust",
                      { x: at.x, y: at.y + 1.1, z: at.z }, 10, 1.1);
            shakeNearby(player.dimension, at, 6, 0.10, 0.30);
          }
          const echo = (delay, radius, points) => later(delay, () => {
            for (const target of struck) {
              let at;
              try { at = target.location; } catch (_) { continue; }
              if (radius) {
                fxRing(player.dimension, "kaiju8:ice_spike", at, radius, points, 0.1);
                fx(player.dimension, "kaiju8:halo_ice",
                   { x: at.x, y: at.y + 1.0, z: at.z });
              } else {
                fxScatter(player.dimension, "kaiju8:frost_dust",
                          { x: at.x, y: at.y + 1.0, z: at.z }, 5, 0.9);
              }
            }
          });
          echo(3, 2.0, 12);
          later(6, () => sound(player.dimension, "random.glass", player.location,
                               { pitch: 1.1, volume: 0.7 }));
          echo(11, 0, 0);
          echo(23, 0, 0);
        });
      } },
    { id: "socket_thunder", name: "kaiju8.tech.socket_thunder", cd: 34, wear: 1,
      canon: true,
      // ユニソケット 発雷弾 — 刺さって帯電し、放電が敵から敵へ「歩く」。
      // 敵と敵のあいだに線を引くのはこの技だけ。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:chit_thunder",
           forward({ x: eye.x, y: eye.y - 0.25, z: eye.z }, dir, 0.7));
        const proj = shoot(player, "kaiju8:df_bullet", 3.2, 0, null);
        fx(player.dimension, "kaiju8:muzzle_star", forward(eye, dir, 0.9));
        if (proj) trail(proj, "kaiju8:tracer_volt", 8, 1, 0.1);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.7, volume: 0.26 });
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 1.8, volume: 0.4 });
        shake(player, 0.05, 0.10, "rotational");
        later(3, () => {
          const first = ray(player, 24, 2.0)[0];
          if (!first) return;
          const strike = (target, damage) => {
            let at;
            try { at = target.location; } catch (_) { return undefined; }
            fxColumn(player.dimension, "kaiju8:bolt_spit", at, 2.4, 5, 0.25);
            fx(player.dimension, "kaiju8:halo_gold",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fxScatter(player.dimension, "kaiju8:bolt_spit",
                      { x: at.x, y: at.y + 1.0, z: at.z }, 6, 0.7);
            if (hit(player, target, damage * ctx.mult)) bleed(target);
            return at;
          };
          strike(first.entity, 10);
          // 連鎖は2tickに1体ずつ。耳で数えられるよう音程が上がっていく
          let node = first.entity;
          const seen = new Set([node.id]);
          for (let i = 0; i < 4; i++) {
            later(i * 2 + 2, () => {
              let a;
              try { a = node.location; } catch (_) { return; }
              const next = targetsNear(node, 7.0).find((t) => !seen.has(t.id));
              if (!next) return;
              seen.add(next.id);
              const b = next.location;
              const d = { x: b.x - a.x, y: b.y - a.y, z: b.z - a.z };
              const L = Math.hypot(d.x, d.y, d.z) || 1;
              fxLine(player.dimension, "kaiju8:bolt_spit",
                     { x: a.x, y: a.y + 1.0, z: a.z },
                     { x: d.x / L, y: d.y / L, z: d.z / L }, L, 0.8);
              strike(next, Math.max(3, 10 - i * 1.5));
              sound(player.dimension, "ambient.weather.thunder", player.location,
                    { pitch: 1.35 + i * 0.15, volume: 0.35 });
              node = next;
            });
          }
          later(11, () => {
            try {
              shakeNearby(player.dimension, first.entity.location, 10, 0.20, 0.25);
            } catch (_) { }
          });
        });
      } },
  ],

  // ---- SW-2033 保科流 --------------------------------------------------
  "kaiju8:twin_sw2033": [
    { id: "karauchi", name: "kaiju8.tech.karauchi", cd: 20, wear: 1, canon: true,
      // 刀伐術1式「空討ち」— 刃が届いていない位置に斬撃が飛ぶ。
      // 斬撃が地面を渡っていくのが見えるよう、7tick かけて前へ伝播させる。
      run(player, ctx) {
        const eye0 = player.getHeadLocation();
        const dir0 = player.getViewDirection();
        const shots = ray(player, 8, 2.0);
        fx(player.dimension, "kaiju8:vacuum_edge", ahead(player, 1.6));
        fx(player.dimension, "kaiju8:twin_arc", ahead(player, 1.4));
        fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 1.4), 3, 0.4);
        // 手首の振りなので、当たりの音と揺れは自分ではなく着弾側に置く
        sound(player.dimension, "item.trident.throw", player.location,
              { pitch: 1.9, volume: 0.7 });
        shake(player, 0.06, 0.10);
        for (let step = 1; step <= 6; step++) {
          later(step, () => {
            const at = forward(eye0, dir0, 1.6 + step * 1.6);
            fx(player.dimension, "kaiju8:vacuum_edge", at);
            fx(player.dimension, "kaiju8:cut_line", at);
            if (step % 2) fx(player.dimension, "kaiju8:vacuum_wake", at);
            for (const h of shots) {
              if (Math.floor(h.along / 1.6) + 1 !== step) continue;
              if (!hit(player, h.entity, 10 * ctx.mult)) continue;
              bleed(h.entity);
              wound(player, h.entity, 2, 0.3);
              sound(player.dimension, "item.trident.hit", h.entity.location,
                    { pitch: 1.25, volume: 1.1 });
              shakeNearby(player.dimension, h.entity.location, 8, 0.18, 0.20);
            }
          });
        }
        later(7, () => {
          fx(player.dimension, "kaiju8:vacuum_edge", forward(eye0, dir0, 11));
          fxScatter(player.dimension, "kaiju8:blade_dust",
                    forward(eye0, dir0, 10), 4, 0.9);
        });
      } },
    { id: "kousa", name: "kaiju8.tech.kousa", cd: 30, wear: 1, canon: true,
      // 刀伐術2式「交差討ち」— 二刀を交差させて斬る。
      // 二度斬られた相手だけが交点でもう一度斬れる。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        const doubled = new Set();
        fxLine(player.dimension, "kaiju8:cut_line_ko", eye, dir, 5.0, 1.25);
        fx(player.dimension, "kaiju8:twin_arc", ahead(player, 2.6));
        for (const h of cone(player, 6.0, 0.05)) {
          if (!hit(player, h.entity, 5.4 * ctx.mult)) continue;
          bleed(h.entity);
          doubled.add(h.entity.id);
          knockback(h.entity, h.dx, h.dz, 0.25, 0.2);
        }
        sound(player.dimension, "mob.ravager.bite", player.location,
              { pitch: 1.55, volume: 0.9 });
        shake(player, 0.08, 0.12);
        later(2, () => {
          fxLine(player.dimension, "kaiju8:cut_line_gyaku", eye, dir, 5.0, 1.25);
          fx(player.dimension, "kaiju8:twin_arc", ahead(player, 2.6));
          for (const h of cone(player, 6.0, 0.05)) {
            if (hit(player, h.entity, 5.4 * ctx.mult)) bleed(h.entity);
          }
          sound(player.dimension, "mob.ravager.bite", player.location,
                { pitch: 1.30, volume: 0.9 });
        });
        later(3, () => {
          fx(player.dimension, "kaiju8:cross_flash", ahead(player, 2.5));
          fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 2.5), 5, 0.9);
          sound(player.dimension, "random.anvil_use", player.location,
                { pitch: 1.9, volume: 0.55 });
          let caught = 0;
          for (const h of cone(player, 6.0, 0.05)) {
            if (!doubled.has(h.entity.id)) continue;
            if (!hit(player, h.entity, 7.2 * ctx.mult)) continue;
            bleed(h.entity);
            caught++;
            knockback(h.entity, h.dx, h.dz, 0.9, 0.35);
            wound(player, h.entity, 3, 0.5);
            sound(player.dimension, "item.trident.hit", h.entity.location,
                  { pitch: 1.0, volume: 1.3 });
          }
          shake(player, 0.16, 0.22);
          if (caught) shakeNearby(player.dimension, player.location, 9, 0.24, 0.22);
        });
        later(5, () => {
          fx(player.dimension, "kaiju8:cut_line_ko", ahead(player, 1.8));
          fx(player.dimension, "kaiju8:cut_line_gyaku", ahead(player, 1.8));
        });
      } },
    { id: "kaeshi", name: "kaiju8.tech.kaeshi", cd: 44, wear: 2, canon: true,
      // 刀伐術3式「返し討ち」— 受けてから背後へ回り込んで斬り返す。
      // 受けの一瞬・無音のすり抜け・音源が場所ごと移る、の三段構え。
      run(player, ctx) {
        const from = { x: player.location.x, y: player.location.y, z: player.location.z };
        fxRing(player.dimension, "kaiju8:cut_line", player.location, 1.1, 6, 1.2);
        sound(player.dimension, "item.shield.block", player.location,
              { pitch: 1.4, volume: 0.8 });
        sound(player.dimension, "armor.equip_chain", player.location,
              { pitch: 1.2, volume: 0.6 });
        try { player.addEffect("resistance", 14, { amplifier: 4, showParticles: false }); }
        catch (_) { }
        shake(player, 0.05, 0.12);
        // すり抜けの4tickは意図的に無音
        for (let i = 1; i <= 4; i++) {
          later(i, () => {
            fx(player.dimension, "kaiju8:oboro_ghost",
               { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
            fxScatter(player.dimension, "kaiju8:blade_dust", player.location, 2, 0.5);
          });
        }
        later(5, () => {
          const best = cone(player, 6.5, -0.2)[0];
          if (!best) return;
          const b = best.entity.location;
          const dir = player.getViewDirection();
          try {
            player.teleport({ x: b.x - dir.x * 1.4, y: b.y, z: b.z - dir.z * 1.4 },
                            { facingLocation: { x: b.x, y: b.y + 1.0, z: b.z } });
          } catch (_) { }
          fx(player.dimension, "kaiju8:oboro_ghost",
             { x: from.x, y: from.y + 0.9, z: from.z });
          // 音源が置いていった位置と新しい位置に分かれる
          sound(player.dimension, "item.trident.return", from,
                { pitch: 1.5, volume: 0.7 });
          sound(player.dimension, "armor.equip_netherite", player.location,
                { pitch: 1.7, volume: 0.5 });
          later(1, () => {
            fxLine(player.dimension, "kaiju8:cut_line_gyaku",
                   player.getHeadLocation(), player.getViewDirection(), 3.5, 1.1);
            fx(player.dimension, "kaiju8:twin_arc", ahead(player, 1.8));
            if (hit(player, best.entity, 22 * ctx.mult)) {
              bleed(best.entity);
              wound(player, best.entity, 4, 0.5);
              sound(player.dimension, "item.trident.hit", best.entity.location,
                    { pitch: 0.8, volume: 1.5 });
              shakeNearby(player.dimension, best.entity.location, 10, 0.28, 0.26);
            }
          });
        });
        later(9, () => {
          fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 1.4), 4, 0.7);
          sound(player.dimension, "note.hat", player.location,
                { pitch: 0.9, volume: 0.3 });
        });
      } },
    { id: "midare", name: "kaiju8.tech.midare", cd: 46, wear: 2, canon: true,
      // 刀伐術4式「乱討ち」— 手数で押し切る。
      // 半径・粒の数・広がり・輪の高さ・音程が波ごとに上がっていく。
      run(player, ctx) {
        fx(player.dimension, "kaiju8:twin_arc", ahead(player, 1.8));
        sound(player.dimension, "item.trident.throw", player.location,
              { pitch: 2.0, volume: 0.45 });
        shake(player, 0.10, 0.16);
        for (let i = 0; i < 5; i++) {
          later(i * 2, () => {
            fxScatter(player.dimension, "kaiju8:midare_shard",
                      ahead(player, 2.2 + i * 0.45), 3 + i, 1.0 + i * 0.45);
            fxRing(player.dimension, "kaiju8:cut_line", player.location,
                   1.6 + i * 0.5, 4 + i, 0.8 + (i % 2) * 0.7);
            for (const h of cone(player, 5.0 + i * 0.5, -0.1)) {
              if (!hit(player, h.entity, 5 * ctx.mult)) continue;
              bleed(h.entity);
              knockback(h.entity, h.dx, h.dz, 0.15, 0.15);
              fxScatter(player.dimension, "kaiju8:blood_mist",
                        { x: h.entity.location.x, y: h.entity.location.y + 1.1,
                          z: h.entity.location.z }, 1, 0.4);
            }
            sound(player.dimension, "note.hat", player.location,
                  { pitch: 2.0 - i * 0.12, volume: 0.35 });
            if (i % 2 === 0) {
              sound(player.dimension, "mob.ravager.bite", player.location,
                    { pitch: 1.75 - i * 0.06, volume: 0.5 });
            }
            shake(player, 0.06 + i * 0.02, 0.10);
          });
        }
        later(10, () => {
          fx(player.dimension, "kaiju8:cross_flash", ahead(player, 2.4));
          fxScatter(player.dimension, "kaiju8:midare_shard", ahead(player, 2.4), 8, 2.6);
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 1.15, volume: 1.1 });
          shakeNearby(player.dimension, player.location, 11, 0.24, 0.35);
        });
      } },
    { id: "oboro", name: "kaiju8.tech.oboro", cd: 52, wear: 2, canon: true,
      // 抜討術1式「朧抜き」— 抜いた瞬間には、もう通り過ぎている。
      // 中盤5tickは完全に無音、斬撃線は通り過ぎた「後ろ」に出る。
      run(player, ctx) {
        const eye0 = player.getHeadLocation();
        const dir0 = player.getViewDirection();
        fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 0.9));
        sound(player.dimension, "armor.equip_netherite", player.location,
              { pitch: 1.65, volume: 0.8 });
        sound(player.dimension, "item.trident.throw", player.location,
              { pitch: 1.8, volume: 0.5 });
        shake(player, 0.08, 0.12, "rotational");
        later(1, () => dash(player, 3.2, 0.10, false));
        for (let i = 1; i <= 5; i++) {
          later(i, () => {
            fx(player.dimension, "kaiju8:oboro_ghost",
               { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
            fxScatter(player.dimension, "kaiju8:blade_dust", player.location, 1, 0.35);
          });
        }
        later(5, () => {
          // 斬撃線は自分が通ってきた道に置く
          fxLine(player.dimension, "kaiju8:cut_line", eye0, dir0, 6.0, 1.0);
          fx(player.dimension, "kaiju8:twin_arc", ahead(player, 1.6));
          let n = 0;
          for (const h of cone(player, 6.0, -0.2)) {
            if (!hit(player, h.entity, 16 * ctx.mult)) continue;
            bleed(h.entity);
            n++;
            knockback(h.entity, h.dx, h.dz, 0.2, 0.2);
            wound(player, h.entity, 3, 0.4);
            const where = h.entity.location;
            // 斬られたことに気づくのが3tick遅れる
            later(3, () => {
              sound(player.dimension, "item.trident.hit", where,
                    { pitch: 0.70, volume: 1.4 });
              sound(player.dimension, "random.fizz", where,
                    { pitch: 0.6, volume: 0.5 });
            });
          }
          later(3, () => {
            fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 0.8));
            sound(player.dimension, "armor.equip_chain", player.location,
                  { pitch: 1.4, volume: 0.5 });
            if (n) shakeNearby(player.dimension, player.location, 10, 0.24, 0.30);
          });
        });
      } },
    { id: "junihitoe", name: "kaiju8.tech.junihitoe", cd: 150, wear: 6, canon: true,
      requires: "kaiju8:numbers_10",
      // 刀伐術7式「十二単」— 十二の斬撃を一息に重ねる。
      // 輪が一枚ずつ閉じ、鐘が一音ずつ上がるので、十二枚を数えられる。
      run(player, ctx) {
        fx(player.dimension, "kaiju8:junihitoe_ring", ahead(player, 2.6));
        fxScatter(player.dimension, "kaiju8:blade_dust", player.location, 4, 0.8);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 0.70, volume: 0.8 });
        shake(player, 0.10, 0.20);
        for (let i = 1; i <= 12; i++) {
          later(i, () => {
            const at = ahead(player, 2.6);
            fx(player.dimension, "kaiju8:junihitoe_ring", at);
            fx(player.dimension,
               i % 2 ? "kaiju8:cut_line_ko" : "kaiju8:cut_line_gyaku", at);
            if (i % 3 === 0) fx(player.dimension, "kaiju8:slash_12", at);
            sound(player.dimension, "note.bell", player.location,
                  { pitch: 0.62 + i * 0.11, volume: 0.55 });
            for (const h of ray(player, 6.5, 1.6)) {
              if (!hit(player, h.entity, 4.5 * ctx.mult)) continue;
              bleed(h.entity);
              if (i % 4 === 0) wound(player, h.entity, 2, 0.4);
            }
            shake(player, 0.05 + i * 0.012, 0.08);
          });
        }
        later(13, () => {
          const at = ahead(player, 2.6);
          fx(player.dimension, "kaiju8:junihitoe_bloom", at);
          fx(player.dimension, "kaiju8:cross_flash", at);
          fxScatter(player.dimension, "kaiju8:sever_spurt", at, 6, 1.2);
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.62, volume: 1.7 });
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 0.90, volume: 1.3 });
          shakeNearby(player.dimension, player.location, 16, 0.42, 0.55);
        });
        later(16, () => {
          fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 2.2), 6, 1.0);
          sound(player.dimension, "note.bell", player.location,
                { pitch: 1.95, volume: 0.40 });
        });
      } },
  ],

  // ---- SW-1023 一刀（保科の予備） --------------------------------------
  "kaiju8:blade_sw1023": [
    { id: "kasumi", name: "kaiju8.tech.kasumi", cd: 40, wear: 2, canon: true,
      // 刀伐術5式「霞討ち」— 囮を二つ振ってから本命を通す。
      // 囮は薄く・軽く・揺れなし。空いた間を霞で満たし、本命がそれを斬り払う。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        const feint = (pitch, reach) => {
          fx(player.dimension, "kaiju8:feint_line", ahead(player, reach));
          fxLine(player.dimension, "kaiju8:feint_line", eye, dir, 3.0, 1.5);
          for (const h of cone(player, 5.4, 0.1)) {
            if (hit(player, h.entity, 5 * ctx.mult)) bleed(h.entity);
          }
          sound(player.dimension, "note.hat", player.location,
                { pitch, volume: 0.30 });
        };
        feint(1.45, 2.4);
        later(3, () => feint(1.30, 2.2));
        for (const t of [4, 6, 8]) {
          later(t, () => fxScatter(player.dimension, "kaiju8:kasumi_haze",
                                   ahead(player, 2.6), 3, 1.4));
        }
        later(6, () => {
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 1.7, volume: 0.35 });
          for (const h of cone(player, 6.0, 0.0)) {
            try { h.entity.addEffect("slowness", 30, { amplifier: 0, showParticles: false }); }
            catch (_) { }
          }
        });
        // 本命の一拍前に必ず出る予兆。ダメージは無い
        later(10, () => {
          fx(player.dimension, "kaiju8:cut_line_heavy", ahead(player, 2.6));
          sound(player.dimension, "random.click", player.location,
                { pitch: 0.5, volume: 0.6 });
        });
        later(11, () => {
          fxLine(player.dimension, "kaiju8:cut_line_heavy", eye, dir, 5.5, 1.1);
          fx(player.dimension, "kaiju8:haze_burst", ahead(player, 2.6));
          let n = 0;
          for (const h of cone(player, 5.8, 0.0)) {
            if (!hit(player, h.entity, 20 * ctx.mult)) continue;
            bleed(h.entity);
            n++;
            knockback(h.entity, h.dx, h.dz, 0.9, 0.3);
            wound(player, h.entity, 4, 0.6);
          }
          sound(player.dimension, "item.trident.hit", player.location,
                { pitch: 0.60, volume: 1.6 });
          sound(player.dimension, "mob.ravager.bite", player.location,
                { pitch: 0.62, volume: 1.0 });
          if (n) shakeNearby(player.dimension, player.location, 11, 0.30, 0.32);
        });
        later(14, () => {
          fxScatter(player.dimension, "kaiju8:kasumi_haze", ahead(player, 2.0), 2, 1.0);
          fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 1.8), 3, 0.6);
        });
      } },
    { id: "yae", name: "kaiju8.tech.yae", cd: 80, wear: 3, canon: true,
      // 刀伐術6式「八重討ち」— 八層を積む。
      // 一枚が0.75秒残るので、最後の一枚が落ちるとき八枚とも画面に在る。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:cut_line_heavy", ahead(player, 2.0));
        sound(player.dimension, "item.trident.throw", player.location,
              { pitch: 1.5, volume: 0.7 });
        shake(player, 0.08, 0.12);
        for (let i = 0; i < 8; i++) {
          later(1 + i * 2, () => {
            const base = ahead(player, 2.2);
            fx(player.dimension, "kaiju8:cut_slat",
               { x: base.x, y: base.y - 0.7 + i * 0.20, z: base.z });
            fx(player.dimension,
               i % 2 ? "kaiju8:cut_line_gyaku" : "kaiju8:cut_line_ko",
               ahead(player, 2.4));
            for (const h of cone(player, 5.2, 0.15)) {
              if (!hit(player, h.entity, 5.5 * ctx.mult)) continue;
              bleed(h.entity);
              const at = h.entity.location;
              fxScatter(player.dimension, "kaiju8:blade_dust",
                        { x: at.x, y: at.y + 1.0, z: at.z }, 2, 0.4);
              if (i % 2) {
                fx(player.dimension, "kaiju8:blood_mist",
                   { x: at.x, y: at.y + 1.1, z: at.z });
              }
            }
            // 十二単の上がる鐘に対して、こちらは下がる金物
            sound(player.dimension, "random.anvil_use", player.location,
                  { pitch: 1.95 - i * 0.09, volume: 0.45 });
            shake(player, 0.07, 0.10);
          });
        }
        later(17, () => {
          fxLine(player.dimension, "kaiju8:cut_line_heavy", eye, dir, 5.0, 1.0);
          fxScatter(player.dimension, "kaiju8:sever_spurt", ahead(player, 2.4), 5, 1.0);
          sound(player.dimension, "random.anvil_land", player.location,
                { pitch: 0.95, volume: 1.2 });
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 0.85, volume: 0.9 });
          shakeNearby(player.dimension, player.location, 12, 0.30, 0.40);
        });
      } },
    { id: "kazaana", name: "kaiju8.tech.kazaana", cd: 56, wear: 3, canon: true,
      // 抜討術2式「風穴」— 一直線に貫く。
      // 突きが伸びるにつれ射程が 3→6→9m と育ち、奥の敵ほど遅れて貫かれる。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 0.9));
        sound(player.dimension, "armor.equip_netherite", player.location,
              { pitch: 1.25, volume: 0.9 });
        sound(player.dimension, "item.trident.riptide_3", player.location,
              { pitch: 1.05, volume: 0.8 });
        shake(player, 0.10, 0.14);
        later(1, () => dash(player, 2.2, 0.06, false));
        [3.0, 6.0, 9.0].forEach((reach, i) => {
          later(1 + i, () => {
            fxLine(player.dimension, "kaiju8:cut_line", eye, dir, reach, 1.5);
            fxScatter(player.dimension, "kaiju8:blade_dust", player.location, 2, 0.3);
          });
        });
        later(4, () => {
          const hits = ray(player, 9, 1.4);
          inDepth(hits, 3, (h) => {
            if (!hit(player, h.entity, 26 * ctx.mult)) return;
            bleed(h.entity);
            const at = h.entity.location;
            fx(player.dimension, "kaiju8:wound_hole",
               { x: at.x, y: at.y + 1.0, z: at.z });
            // 噴出は貫いた向こう側から出る
            fxScatter(player.dimension, "kaiju8:sever_spurt",
                      forward(at, dir, 0.6), 4, 0.4);
            fx(player.dimension, "kaiju8:blood_mist",
               { x: at.x, y: at.y + 1.2, z: at.z });
            sound(player.dimension, "item.trident.hit_ground", at,
                  { pitch: 0.70, volume: 1.5 });
            sound(player.dimension, "random.fizz", at, { pitch: 0.50, volume: 0.7 });
            if (h === hits[0]) {
              shakeNearby(player.dimension, at, 12, 0.32, 0.30);
            }
          });
        });
        later(7, () => fxLine(player.dimension, "kaiju8:vacuum_wake", eye, dir, 9, 2.2));
      } },
    { id: "sakabyoshi", name: "kaiju8.tech.sakabyoshi", cd: 46, wear: 2, canon: true,
      // 抜討術3式「逆拍子」— 拍子を作ってから外す。
      // t4 は何も出さない。その「無い一拍」が技の本体。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:draw_gleam", ahead(player, 0.9));
        fxLine(player.dimension, "kaiju8:cut_line_ko", eye, dir, 4.0, 1.3);
        for (const h of cone(player, 5.0, 0.2)) {
          if (!hit(player, h.entity, 9 * ctx.mult)) continue;
          bleed(h.entity);
          knockback(h.entity, h.dx, h.dz, 0.5, 0.2);
        }
        sound(player.dimension, "armor.equip_iron", player.location,
              { pitch: 1.5, volume: 0.6 });
        sound(player.dimension, "mob.ravager.bite", player.location,
              { pitch: 1.55, volume: 0.9 });
        shake(player, 0.12, 0.16);
        later(2, () => {
          fxScatter(player.dimension, "kaiju8:blade_dust", ahead(player, 2.0), 2, 0.5);
          sound(player.dimension, "note.hat", player.location,
                { pitch: 1.7, volume: 0.25 });
        });
        // t4 — 相手も自分も次が来ると思っている拍。ここは空ける。
        later(7, () => {
          fxLine(player.dimension, "kaiju8:cut_line_gyaku", eye, dir, 4.0, 1.3);
          fx(player.dimension, "kaiju8:cross_flash", ahead(player, 2.0));
          for (const h of cone(player, 5.0, 0.2)) {
            if (!hit(player, h.entity, 15 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, h.dx, h.dz, 1.0, 0.3);
            wound(player, h.entity, 3, 0.5);
            sound(player.dimension, "item.trident.hit", h.entity.location,
                  { pitch: 0.90, volume: 1.3 });
          }
          sound(player.dimension, "random.anvil_use", player.location,
                { pitch: 0.80, volume: 0.9 });
          // 画面が「揺れる」のではなく「回る」のはこの技だけ
          shake(player, 0.26, 0.26, "rotational");
        });
        later(9, () => {
          fx(player.dimension, "kaiju8:cut_line_gyaku", ahead(player, 1.6));
          sound(player.dimension, "armor.equip_chain", player.location,
                { pitch: 1.3, volume: 0.4 });
        });
      } },
  ],

  // ---- DF-STD バズーカ ------------------------------------------------
  "kaiju8:df_bazooka": [
    { id: "he_shell", name: "kaiju8.tech.he_shell", cd: 70, wear: 3, canon: false,
      // 榴弾。後方爆風 → 弾が飛ぶのが見える → 白熱 → 破片 → 土柱 →
      // 遅れて土煙が二度広がる。射手の後ろへ噴くのはこの武器だけ。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fxCone(player.dimension, "kaiju8:backblast", eye,
               { x: -dir.x, y: -dir.y, z: -dir.z }, 3.4, 0.45, 10);
        fx(player.dimension, "kaiju8:tube_flash", ahead(player, 1.5));
        const proj = shoot(player, "kaiju8:rifle_beam", 2.2, 0, null);
        if (proj) trail(proj, "kaiju8:shell_smoke", 10, 1, 0.15);
        sound(player.dimension, "mob.ghast.fireball", player.location,
              { pitch: 0.55, volume: 1.4 });
        sound(player.dimension, "random.explode", player.location,
              { pitch: 0.85, volume: 0.7 });
        shake(player, 0.26, 0.22);
        later(5, () => {
          const first = ray(player, 34, 2.8)[0];
          const at = first ? first.entity.location : forward(eye, dir, 20);
          fx(player.dimension, "kaiju8:detonation_gold",
             { x: at.x, y: at.y + 0.8, z: at.z });
          fx(player.dimension, "kaiju8:quake_dust",
             { x: at.x, y: at.y + 0.1, z: at.z });
          fxScatter(player.dimension, "kaiju8:steel_shard", at, 14, 1.6);
          fxColumn(player.dimension, "kaiju8:dirt_column", at, 4.5, 8, 0.5);
          for (const t of targetsNear(player, 40)) {
            const dx = t.location.x - at.x;
            const dz = t.location.z - at.z;
            const d = Math.hypot(dx, dz);
            if (d > 5) continue;
            if (!hit(player, t, (26 - d * 3) * ctx.mult)) continue;
            bleed(t);
            const len = d || 1;
            knockback(t, dx / len, dz / len, 2.2, 0.55);
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.42, volume: 2.0 });
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.5, volume: 0.5 });
          shakeNearby(player.dimension, at, 18, 0.5, 0.55);
          later(2, () => sound(player.dimension, "random.explode", player.location,
                               { pitch: 0.28, volume: 0.9 }));
          // 土煙は二波に分けて残す
          later(4, () => {
            fxScatter(player.dimension, "kaiju8:blast_smoke", at, 10, 2.6);
            fxRing(player.dimension, "kaiju8:dust_wave", at, 4.0, 14, 0.15);
          });
          later(11, () => {
            fxRing(player.dimension, "kaiju8:dust_wave", at, 6.5, 18, 0.15);
            fxScatter(player.dimension, "kaiju8:blast_smoke", at, 6, 3.0);
          });
        });
      } },
    { id: "incendiary", name: "kaiju8.tech.incendiary", cd: 90, wear: 4, canon: false,
      // 焼夷弾。3発が別々の場所に落ち、炎の花弁が開き、ゲルが飛び散り、
      // そのあと4秒かけて火が這って広がる。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        for (let i = 0; i < 3; i++) {
          later(i * 5, () => {
            fxCone(player.dimension, "kaiju8:backblast", eye,
                   { x: -dir.x, y: -dir.y, z: -dir.z }, 2.4, 0.4, 6);
            fx(player.dimension, "kaiju8:tube_flash_hot", ahead(player, 1.5));
            const proj = shoot(player, "kaiju8:rifle_beam", 1.9, 0.11, null);
            if (proj) trail(proj, "kaiju8:fire_gel", 10, 2, 0.15);
            sound(player.dimension, "mob.ghast.fireball", player.location,
                  { pitch: 0.75 + i * 0.08, volume: 1.0 });
            shake(player, 0.16, 0.18);
            later(5, () => {
              const mark = cone(player, 14, 0.4)[i];
              const at = mark ? mark.entity.location
                              : forward(eye, dir, 8 + i * 2.5);
              for (let k = 0; k < 3; k++) {
                fx(player.dimension, "kaiju8:wound_fire", {
                  x: at.x + (Math.random() - 0.5) * 1.2,
                  y: at.y + 0.4,
                  z: at.z + (Math.random() - 0.5) * 1.2,
                });
              }
              fxScatter(player.dimension, "kaiju8:fire_gel", at, 9, 1.8);
              fxRing(player.dimension, "kaiju8:scorch_ring",
                     { x: at.x, y: at.y + 0.06, z: at.z }, 2.4, 9, 0);
              for (const t of targetsNear(player, 20)) {
                const d = Math.hypot(t.location.x - at.x, t.location.z - at.z);
                if (d > 3.2) continue;
                if (!hit(player, t, 9 * ctx.mult)) continue;
                bleed(t);
                try { t.setOnFire(8, true); } catch (_) { }
                fxScatter(player.dimension, "kaiju8:cauterize", t.location, 4, 0.7);
              }
              sound(player.dimension, "mob.ghast.fireball", player.location,
                    { pitch: 1.5, volume: 0.6 });
              sound(player.dimension, "random.explode", player.location,
                    { pitch: 1.1, volume: 0.55 });
              // 這って広がる火。この技の本体はここ。
              // 3発ぶんが同時に走るので、一発あたりの段数と粒数は絞ってある
              for (let k = 1; k <= 4; k++) {
                later(k * 10, () => {
                  fxRing(player.dimension, "kaiju8:scorch_ring", at,
                         2.4 + k * 0.22, 8, 0.06);
                  fxScatter(player.dimension, "kaiju8:ember_rain", at, 3, 2.0);
                  if (k % 2) {
                    fxScatter(player.dimension, "kaiju8:heat_smoke", at, 2, 1.6);
                  }
                  for (const t of targetsNear(player, 20)) {
                    const d = Math.hypot(t.location.x - at.x, t.location.z - at.z);
                    if (d <= 3.0) { try { t.setOnFire(4, true); } catch (_) { } }
                  }
                });
              }
            });
          });
        }
        later(18, () => shakeNearby(player.dimension, player.location, 12, 0.14, 0.9));
      } },
  ],

  // ---- DF-STD 自動拳銃 -------------------------------------------------
  "kaiju8:df_pistol": [
    { id: "rapid", name: "kaiju8.tech.rapid", cd: 5, wear: 1, canon: false,
      // 速射。毎発 薬莢が落ち、2発に1本だけ曳光が入り、銃口が左右に振れる。
      run(player) {
        const beat = ((pistolBeat.get(player.id) ?? 0) + 1) % 4;
        pistolBeat.set(player.id, beat);
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        const origin = forward(eye, dir, 0.9);
        fx(player.dimension, "kaiju8:pistol_flash", origin);
        fxScatter(player.dimension, "kaiju8:brass_case",
                  forward({ x: eye.x, y: eye.y - 0.35, z: eye.z }, dir, 0.4), 1, 0.25);
        const proj = shoot(player, "kaiju8:df_bullet", 3.35, 0.05, null);
        if (proj && beat % 2 === 0) trail(proj, "kaiju8:tracer_round", 6, 2, 0.05);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 2.35, volume: 0.20 });
        shake(player, beat % 2 === 0 ? 0.048 : 0.032, 0.06, "rotational");
        later(1, () => fx(player.dimension, "kaiju8:slide_puff",
                          forward({ x: eye.x, y: eye.y - 0.2, z: eye.z }, dir, 0.55)));
        later(2, () => sound(player.dimension, "random.click", player.location,
                             { pitch: 1.2, volume: 0.45 }));
        if (beat === 3) {
          // 4発ごとに銃が温まる
          fxScatter(player.dimension, "kaiju8:slide_puff", origin, 3, 0.3);
          sound(player.dimension, "random.click", player.location,
                { pitch: 0.9, volume: 0.6 });
        }
      } },
    { id: "aimed", name: "kaiju8.tech.aimed", cd: 30, wear: 1, canon: false,
      // 精密射撃。構える → 線が通る → 一発で抜ける、の三拍。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        const target = ray(player, 26, 1.1)[0];
        const mark = target
          ? { x: target.entity.location.x, y: target.entity.location.y + 1.0,
              z: target.entity.location.z }
          : ahead(player, 10);
        fx(player.dimension, "kaiju8:aim_lock", mark);
        fxLine(player.dimension, "kaiju8:aim_dot", eye, dir, 18, 1.5);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 2.0, volume: 0.35 });
        shake(player, 0.02, 0.20, "rotational");
        later(4, () => {
          const origin = forward(eye, dir, 0.9);
          fx(player.dimension, "kaiju8:muzzle_star", origin);
          fxScatter(player.dimension, "kaiju8:brass_case",
                    forward({ x: eye.x, y: eye.y - 0.35, z: eye.z }, dir, 0.4), 1, 0.2);
          shoot(player, "kaiju8:df_bullet", 4.0, 0, null);
          fxLine(player.dimension, "kaiju8:bullet_line", eye, dir, 24, 1.0);
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.45, volume: 0.75 });
          sound(player.dimension, "mob.wither.shoot", player.location,
                { pitch: 1.95, volume: 0.25 });
          shake(player, 0.13, 0.12, "rotational");
          if (target && hit(player, target.entity, 20 * ctx.mult)) {
            bleed(target.entity);
            const at = target.entity.location;
            fx(player.dimension, "kaiju8:round_impact",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fx(player.dimension, "kaiju8:pierce_hole",
               { x: at.x, y: at.y + 1.0, z: at.z });
            // 体液は弾道の向こう側へ抜ける
            fxScatter(player.dimension, "kaiju8:blood_splash",
                      forward(at, dir, 0.9), 8, 0.5);
            shakeNearby(player.dimension, at, 6, 0.14, 0.14);
          } else {
            fxScatter(player.dimension, "kaiju8:impact_dust",
                      forward(eye, dir, 24), 4, 0.5);
          }
          later(2, () => {
            fxScatter(player.dimension, "kaiju8:slide_puff", origin, 2, 0.25);
            sound(player.dimension, "random.click", player.location,
                  { pitch: 1.05, volume: 0.5 });
          });
        });
      } },
  ],

  // ---- 03Ax-0112 隊式斧術 ---------------------------------------------
  "kaiju8:axe_03ax": [
    { id: "rakurai", name: "kaiju8.tech.rakurai", cd: 60, wear: 3, canon: true,
      // 1式「落雷」— 名前どおり垂直。刃より先に雷が落ちる。
      // この武器で唯一「上から下へ」「地面に根を張る」技。
      run(player, ctx) {
        const P = ahead(player, 2.6);
        const G = { x: P.x, y: player.location.y + 0.1, z: P.z };
        fx(player.dimension, "kaiju8:charge_arc_ice", ahead(player, 1.4));
        fxScatter(player.dimension, "kaiju8:charge_arc_ice",
                  { x: P.x, y: P.y + 1.2, z: P.z }, 3, 0.5);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 0.60, volume: 0.50 });
        shake(player, 0.06, 0.20);
        later(2, () => {
          // 斧の背面から噴いて振りを加速させる
          const dir = player.getViewDirection();
          fxScatter(player.dimension, "kaiju8:axe_backblast",
                    forward(player.getHeadLocation(),
                            { x: -dir.x, y: -dir.y, z: -dir.z }, 1.3), 6, 0.7);
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 0.50, volume: 0.90 });
        });
        later(4, () => {
          // 刃が届く前に雷が落ちる
          fx(player.dimension, "kaiju8:bolt_strike",
             { x: P.x, y: G.y + 2.4, z: P.z });
          fxScatter(player.dimension, "kaiju8:bolt_fringe",
                    { x: P.x, y: G.y + 1.8, z: P.z }, 5, 0.7);
          sound(player.dimension, "ambient.weather.thunder", P,
                { pitch: 1.25, volume: 0.90 });
        });
        later(5, () => {
          let first = true;
          for (const h of cone(player, 5.6, 0.05)) {
            if (!hit(player, h.entity, 20 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, h.dx, h.dz, 1.2, 0.35);
            const at = h.entity.location;
            fxScatter(player.dimension, "kaiju8:axe_arc",
                      { x: at.x, y: at.y + 1, z: at.z }, 3, 0.6);
            if (first) {
              // 打たれた個体にも一本落ちる
              fx(player.dimension, "kaiju8:bolt_strike",
                 { x: at.x, y: at.y + 2.4, z: at.z });
              first = false;
            }
          }
          fx(player.dimension, "kaiju8:shock_ring_gold", G);
          fxRing(player.dimension, "kaiju8:ground_fissure", G, 1.2, 8, 0.15);
          sound(player.dimension, "random.anvil_land", player.location,
                { pitch: 0.45, volume: 1.6 });
          shakeNearby(player.dimension, P, 16, 0.40, 0.45);
        });
        // 地割れが外へ育つ
        later(7, () => fxRing(player.dimension, "kaiju8:ground_fissure", G, 2.6, 10, 0.15));
        later(8, () => {
          fxScatter(player.dimension, "kaiju8:impact_dust", G, 12, 1.8);
          fxScatter(player.dimension, "kaiju8:debris", G, 8, 1.0);
          sound(player.dimension, "dig.stone", P, { pitch: 0.60, volume: 0.80 });
        });
        later(14, () => {
          fxScatter(player.dimension, "kaiju8:charge_arc_ice", ahead(player, 1.6), 2, 0.4);
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 1.60, volume: 0.35 });
        });
      } },
    { id: "mizukiri", name: "kaiju8.tech.mizukiri", cd: 40, wear: 2, canon: true,
      // 2式「水切」— 石を投げて水面を跳ねさせるように、当たる場所が
      // 2.2m → 4.4m → 6.6m と歩いていく。この武器で唯一「動く着弾点」を持つ。
      run(player, ctx) {
        const d = player.getViewDirection();
        const L = Math.hypot(d.x, d.z) || 1;
        const flat = { x: d.x / L, y: 0, z: d.z / L };
        const G = { x: player.location.x, y: player.location.y + 0.1,
                    z: player.location.z };
        // 落雷が頭上なのに対し、こちらは足元で溜める
        fxRing(player.dimension, "kaiju8:charge_arc_ice", G, 1.1, 6, 0.25);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 1.50, volume: 0.40 });
        later(2, () => {
          fxLine(player.dimension, "kaiju8:skim_wake",
                 { x: player.location.x, y: player.location.y + 0.55,
                   z: player.location.z }, flat, 7.0, 0.9);
          sound(player.dimension, "item.trident.riptide_2", player.location,
                { pitch: 1.90, volume: 0.90 });
        });
        later(3, () => {
          for (const h of cone(player, 6.4, -0.05)) {
            if (!hit(player, h.entity, 14 * ctx.mult)) continue;
            bleed(h.entity);
            // 吹き飛びは水平に。跳ねる技なので上げない
            knockback(h.entity, h.dx, h.dz, 2.1, 0.10);
            fxScatter(player.dimension, "kaiju8:axe_arc",
                      { x: h.entity.location.x, y: h.entity.location.y + 1,
                        z: h.entity.location.z }, 3, 0.6);
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.55, volume: 0.80 });
          shake(player, 0.18, 0.26);
        });
        [2.2, 4.4, 6.6].forEach((D, i) => {
          later(3 + i * 2, () => {
            const at = forward(G, flat, D);
            fx(player.dimension, "kaiju8:axe_frontblast",
               { x: at.x, y: at.y + 0.5, z: at.z });
            fxScatter(player.dimension, "kaiju8:skim_bead",
                      { x: at.x, y: at.y + 0.35, z: at.z }, 8, 0.5);
            fxScatter(player.dimension, "kaiju8:impact_dust", at, 4, 0.7);
            sound(player.dimension, "random.glass", at,
                  { pitch: 1.90 - i * 0.25, volume: 0.50 });
            // 判定も跳ねに合わせて前へ移動する
            for (const h of ray(player, D + 1.0, 2.0)) {
              if (h.along < D - 1.2) continue;
              if (hit(player, h.entity, 6 * ctx.mult)) bleed(h.entity);
            }
          });
        });
        later(9, () => fxScatter(player.dimension, "kaiju8:skim_bead",
                                 forward(G, flat, 7.4), 6, 1.2));
      } },
    { id: "hangetsu", name: "kaiju8.tech.hangetsu", cd: 52, wear: 2, canon: true,
      // 3式「半月」— 半円を薙ぐ。溜めも地面の傷も、弧に沿って左右へ歩く。
      // 演出が「角度方向に移動する」のはこの技だけ。
      run(player, ctx) {
        const d = player.getViewDirection();
        const L = Math.hypot(d.x, d.z) || 1;
        const f = { x: d.x / L, z: d.z / L };
        const r = { x: -f.z, z: f.x };
        const arcPt = (rad, deg, h) => {
          const a = (deg * Math.PI) / 180;
          return {
            x: player.location.x + (f.x * Math.cos(a) + r.x * Math.sin(a)) * rad,
            y: player.location.y + h,
            z: player.location.z + (f.z * Math.cos(a) + r.z * Math.sin(a)) * rad,
          };
        };
        sound(player.dimension, "mob.enderdragon.flap", player.location,
              { pitch: 1.40, volume: 0.70 });
        for (let i = 0; i < 5; i++) {
          later(i, () => fx(player.dimension, "kaiju8:charge_arc_ice",
                            arcPt(2.4, -100 + i * 25, 1.2)));
        }
        later(5, () => {
          fx(player.dimension, "kaiju8:axe_crescent", ahead(player, 2.6));
          fx(player.dimension, "kaiju8:moon_arc", ahead(player, 2.9));
          // 落雷の輪は地面で太い。こちらは胸の高さで髪の毛のように細い
          fx(player.dimension, "kaiju8:air_ring",
             { x: player.location.x, y: player.location.y + 1.1, z: player.location.z });
          for (const h of cone(player, 7.2, -0.45)) {
            if (!hit(player, h.entity, 12 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, h.dx, h.dz, 1.6, 0.30);
            fxScatter(player.dimension, "kaiju8:axe_arc",
                      { x: h.entity.location.x, y: h.entity.location.y + 1,
                        z: h.entity.location.z }, 3, 0.6);
          }
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 0.80, volume: 1.20 });
          shakeNearby(player.dimension, player.location, 12, 0.24, 0.50);
        });
        // 地面の傷が振りの向きに沿って描かれていく
        for (let i = 0; i < 5; i++) {
          later(6 + i, () => {
            const at = arcPt(3.4, -100 + i * 50, 0.1);
            fxScatter(player.dimension, "kaiju8:impact_dust", at, 3, 0.6);
            fx(player.dimension, "kaiju8:charge_arc_ice",
               { x: at.x, y: at.y + 0.4, z: at.z });
          });
        }
      } },
    { id: "darumaotoshi", name: "kaiju8.tech.darumaotoshi", cd: 74, wear: 4,
      canon: true,
      // 4式「達磨落」— 一枚の平面で水平に断つ。溜めて、止めて、抜く。
      // 断面より「上」から埃が落ちてくるのが達磨落しの読み。
      run(player, ctx) {
        const d = player.getViewDirection();
        const L = Math.hypot(d.x, d.z) || 1;
        const flat = { x: d.x / L, y: 0, z: d.z / L };
        const W = { x: player.location.x, y: player.location.y + 1.1,
                    z: player.location.z };
        // 予兆が点ではなく「線」なのはこの技だけ
        fxLine(player.dimension, "kaiju8:charge_arc_ice", W, flat, 4.2, 1.4);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 0.95, volume: 0.55 });
        for (const t of [1, 2, 3]) {
          later(t, () => {
            fx(player.dimension, "kaiju8:charge_arc_ice", forward(W, flat, 2.0));
            if (t === 2) {
              sound(player.dimension, "note.bass", player.location,
                    { pitch: 0.50, volume: 0.25 });
            }
          });
        }
        later(4, () => {
          fx(player.dimension, "kaiju8:flat_slab", forward(W, flat, 2.8));
          fxLine(player.dimension, "kaiju8:flat_slab", W, flat, 4.8, 2.4);
          sound(player.dimension, "random.anvil_use", player.location,
                { pitch: 0.50, volume: 1.60 });
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 1.90, volume: 0.35 });
          const struck = [];
          for (const h of cone(player, 5.0, 0.2)) {
            if (!hit(player, h.entity, 26 * ctx.mult)) continue;
            bleed(h.entity);
            // 真横に飛ぶ。持ち上げない
            knockback(h.entity, h.dx, h.dz, 3.6, 0.0);
            const at = h.entity.location;
            struck.push({ x: at.x, y: at.y, z: at.z });
            fx(player.dimension, "kaiju8:flat_slab",
               { x: at.x, y: at.y + 1.1, z: at.z });
            fxScatter(player.dimension, "kaiju8:ejecta",
                      { x: at.x, y: at.y + 1.0, z: at.z }, 10, 0.6);
            fxScatter(player.dimension, "kaiju8:crack_burst",
                      { x: at.x, y: at.y + 1.0, z: at.z }, 5, 0.7);
          }
          shakeNearby(player.dimension, player.location, 14, 0.34, 0.40);
          later(1, () => {
            for (const at of struck) {
              fxScatter(player.dimension, "kaiju8:impact_dust",
                        { x: at.x, y: at.y + 2.0, z: at.z }, 5, 0.6);
            }
          });
          later(2, () => fxScatter(player.dimension, "kaiju8:ejecta",
                                   forward(W, flat, 3.2), 8, 1.0));
        });
      } },
  ],

  // ---- T-25101985 大型火砲 ---------------------------------------------
  "kaiju8:cannon_t25": [
    { id: "senkou", name: "kaiju8.tech.senkou", cd: 34, wear: 2, canon: false,
      // 砲撃「穿光」— 一点を撃ち抜く。三つの砲撃で唯一、撃つ前に照準線が通る。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fxLine(player.dimension, "kaiju8:aim_line", eye, dir, 24, 3.0);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 2.00, volume: 0.30 });
        later(2, () => {
          fx(player.dimension, "kaiju8:muzzle_flash", ahead(player, 1.1));
          fxScatter(player.dimension, "kaiju8:muzzle_brake", ahead(player, 1.2), 6, 0.3);
          fxLine(player.dimension, "kaiju8:pierce_lance", eye, dir, 24, 1.5);
          shoot(player, "kaiju8:rifle_beam", 4.2, 0, null);
          sound(player.dimension, "mob.blaze.shoot", player.location,
                { pitch: 0.55, volume: 1.30 });
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.90, volume: 0.50 });
          shake(player, 0.16, 0.14);
        });
        later(3, () => {
          const first = ray(player, 24, 1.0)[0];
          if (!first) return;
          if (!hit(player, first.entity, 22 * ctx.mult)) return;
          bleed(first.entity);
          const at = first.entity.location;
          fx(player.dimension, "kaiju8:pierce_hole",
             { x: at.x, y: at.y + 1.1, z: at.z });
          fxScatter(player.dimension, "kaiju8:beam_impact", at, 4, 0.4);
          sound(player.dimension, "random.explode", at, { pitch: 2.00, volume: 0.45 });
        });
        later(5, () => {
          fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, 1.0), 3, 0.4);
          fx(player.dimension, "kaiju8:aim_line", ahead(player, 1.2));
        });
      } },
    { id: "danmaku", name: "kaiju8.tech.danmaku", cd: 56, wear: 3, canon: false,
      // 砲撃「弾幕」— 11発を扇状に振りながら撃つ。一発ごとに蹴りが来て、
      // 薬莢が右へ跳ね、途中で二度だけ砲身を冷やす。
      run(player, ctx) {
        const d = player.getViewDirection();
        const L = Math.hypot(d.x, d.z) || 1;
        const rt = { x: -d.z / L, z: d.x / L };
        sound(player.dimension, "random.anvil_use", player.location,
              { pitch: 1.90, volume: 0.40 });
        fx(player.dimension, "kaiju8:barrel_vent", ahead(player, 0.9));
        for (let i = 0; i <= 10; i++) {
          later(1 + i * 2, () => {
            const a = Math.sin(i * 0.9) * 0.16;
            const p = Math.sin(i * 1.7) * 0.05;
            const sd = { x: d.x * Math.cos(a) - d.z * Math.sin(a),
                         y: d.y + p,
                         z: d.x * Math.sin(a) + d.z * Math.cos(a) };
            const org = forward(player.getHeadLocation(), sd, 0.9);
            let proj;
            try {
              proj = player.dimension.spawnEntity("kaiju8:rifle_beam", org);
              const pc = proj.getComponent("minecraft:projectile");
              if (pc) {
                pc.owner = player;
                pc.shoot({ x: sd.x * 3.2, y: sd.y * 3.2, z: sd.z * 3.2 });
              }
            } catch (_) { }
            fx(player.dimension, "kaiju8:muzzle_flash", org);
            fxScatter(player.dimension, "kaiju8:muzzle_brake", org, 4, 0.25);
            fxScatter(player.dimension, "kaiju8:brass_case",
                      { x: org.x + rt.x * 0.5, y: org.y - 0.15,
                        z: org.z + rt.z * 0.5 }, 1, 0.15);
            sound(player.dimension, "mob.wither.shoot", player.location,
                  { pitch: 1.25 + (i % 3) * 0.12, volume: 0.55 });
            shake(player, 0.07, 0.10);
            if (proj) trail(proj, "kaiju8:tracer_gold", 5, 1, 0);
          });
        }
        for (const t of [8, 16]) {
          later(t, () => {
            fx(player.dimension, "kaiju8:barrel_vent", ahead(player, 0.9));
            sound(player.dimension, "random.fizz", player.location,
                  { pitch: 1.30, volume: 0.45 });
          });
        }
        later(23, () => {
          fxScatter(player.dimension, "kaiju8:barrel_vent", ahead(player, 1.0), 8, 0.5);
          fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, 1.0), 5, 0.6);
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 0.90, volume: 0.70 });
        });
      } },
    { id: "raitei", name: "kaiju8.tech.raitei", cd: 120, wear: 5, charge: 30,
      canon: false,
      // 砲撃「雷霆」— 溜めの格子が砲口へ閉じていく。半径 3.0→0.8。
      // 撃つ前に地面の埃が浮き、撃った瞬間に後方へ爆風が抜ける。
      run(player, ctx) {
        const stages = [
          [0, 1.8, 3.0, 8, 0.55, 1.20, 0, 0],
          [6, 1.7, 2.3, 8, 0.80, 0.70, 8, 1.1],
          [12, 1.6, 1.7, 8, 1.00, 0.80, 3, 0.5],
          [18, 1.5, 1.2, 10, 1.25, 0.90, 10, 0.9],
          [26, 1.4, 0.8, 12, 1.60, 1.00, 7, 0.4],
        ];
        stages.forEach(([t, reach, rad, pts, pitch, vol, arcs, spread], i) => {
          later(t, () => {
            fxRing(player.dimension, "kaiju8:rail_lock", ahead(player, reach),
                   rad, pts, 0.0);
            if (arcs) {
              fxScatter(player.dimension,
                        i >= 2 ? "kaiju8:charge_arc_ice" : "kaiju8:cannon_charge",
                        ahead(player, reach - 0.1), arcs, spread);
            }
            sound(player.dimension, i ? "beacon.power_select" : "beacon.activate",
                  player.location, { pitch, volume: vol });
            if (t === 18) shake(player, 0.05, 0.35);
            if (t === 26) shake(player, 0.10, 0.25);
          });
        });
        later(22, () => {
          // 場に引かれて地面の埃が浮く
          fxRing(player.dimension, "kaiju8:impact_dust", ground(player), 2.2, 10, 0.05);
          fxRing(player.dimension, "kaiju8:cannon_charge", player.location, 2.6, 10, 0.4);
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 1.80, volume: 0.35 });
        });
        later(29, () => sound(player.dimension, "note.bass", player.location,
                              { pitch: 0.50, volume: 0.50 }));
        later(30, () => {
          const dir = player.getViewDirection();
          const eye = player.getHeadLocation();
          fx(player.dimension, "kaiju8:cannon_muzzle", ahead(player, 1.3));
          fxScatter(player.dimension, "kaiju8:backblast",
                    forward(eye, { x: -dir.x, y: -dir.y, z: -dir.z }, 1.6), 14, 1.0);
          // 芯の白と外側の淡青の二層で撃つ
          fxLine(player.dimension, "kaiju8:railgun_lance", eye, dir, 40, 1.6);
          fxLine(player.dimension, "kaiju8:rail_core", eye, dir, 40, 2.4);
          let n = 0;
          for (const h of ray(player, 40, 3.0)) {
            if (!hit(player, h.entity, 60 * ctx.mult)) continue;
            bleed(h.entity);
            n++;
            fx(player.dimension, "kaiju8:pierce_hole",
               { x: h.entity.location.x, y: h.entity.location.y + 1.1,
                 z: h.entity.location.z });
            fxScatter(player.dimension, "kaiju8:beam_impact", h.entity.location, 8, 0.8);
          }
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 0.70, volume: 2.0 });
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.45, volume: 1.6 });
          shakeNearby(player.dimension, player.location, 26, 0.60, 0.70);
          if (n) fx(player.dimension, "kaiju8:core_break", forward(eye, dir, 6));
        });
        // 撃ち終わってからしばらく砲身が冷えない
        for (const t of [34, 40, 48]) {
          later(t, () => {
            fxScatter(player.dimension, "kaiju8:barrel_vent", ahead(player, 1.0), 6, 0.5);
            fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, 1.1), 3, 0.5);
          });
        }
        later(36, () => sound(player.dimension, "random.fizz", player.location,
                              { pitch: 0.80, volume: 0.80 }));
      } },
  ],

  // ---- GS-3305 隊式銃剣術 ---------------------------------------------
  "kaiju8:gunblade_gs3305": [
    { id: "sakuretsuzan", name: "kaiju8.tech.sakuretsuzan", cd: 34, wear: 2,
      canon: true,
      // 1式「炸裂斬」— 斬ってから内部で撃つ。斬られた相手に「装填済み」の
      // 印が付き、4tick後にその場所で炸裂する。音も揺れも相手側で起きる。
      run(player, ctx) {
        fx(player.dimension, "kaiju8:chit_thunder", ahead(player, 0.9));
        sound(player.dimension, "random.click", player.location,
              { pitch: 1.6, volume: 0.8 });
        later(1, () => {
          fx(player.dimension, "kaiju8:cut_arc_white", ahead(player, 2.2));
          sound(player.dimension, "mob.ravager.bite", player.location,
                { pitch: 0.75, volume: 1.2 });
          shake(player, 0.10, 0.12);
          const primed = [];
          for (const h of cone(player, 5.2, 0.1)) {
            if (!hit(player, h.entity, 11 * ctx.mult)) continue;
            bleed(h.entity);
            primed.push(h.entity);
            const at = h.entity.location;
            fxScatter(player.dimension, "kaiju8:powder_burn",
                      { x: at.x, y: at.y + 1.0, z: at.z }, 5, 0.6);
          }
          later(4, () => {
            for (const target of primed) {
              let at;
              try { at = target.location; } catch (_) { continue; }
              const up = { x: at.x, y: at.y + 1.0, z: at.z };
              fx(player.dimension, "kaiju8:detonation_gold", up);
              fx(player.dimension, "kaiju8:halo_gold", up);
              fxScatter(player.dimension, "kaiju8:wound_fire", up, 6, 0.5);
              if (hit(player, target, 9 * ctx.mult)) bleed(target);
              sound(player.dimension, "random.explode", at,
                    { pitch: 1.35, volume: 0.9 });
              sound(player.dimension, "mob.ravager.stun", at,
                    { pitch: 1.5, volume: 0.6 });
              shakeNearby(player.dimension, at, 8, 0.28, 0.25);
              later(3, () => fxScatter(player.dimension, "kaiju8:cauterize", up, 4, 0.5));
            }
            fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, 1.2), 3, 0.6);
          });
        });
      } },
    { id: "zanmaku", name: "kaiju8.tech.zanmaku", cd: 56, wear: 3, canon: true,
      // 2式「斬幕砲火」— 斬撃と射撃で幕を張る。
      // 5枚の交差斬りが4.4mの壁になり、それが4回掃かれる。
      run(player, ctx) {
        const dir = player.getViewDirection();
        const rl = Math.hypot(dir.z, dir.x) || 1;
        const right = { x: -dir.z / rl, y: 0, z: dir.x / rl };
        const eye = player.getHeadLocation();
        sound(player.dimension, "mob.ravager.roar", player.location,
              { pitch: 1.25, volume: 1.0 });
        shake(player, 0.09, 0.75);
        for (let i = 0; i < 4; i++) {
          later(i * 3, () => {
            const c = ahead(player, 2.6);
            for (const k of [-2, -1, 0, 1, 2]) {
              fx(player.dimension, "kaiju8:cut_cross", {
                x: c.x + right.x * k * 1.1,
                y: c.y + (k % 2 ? 0.4 : -0.4),
                z: c.z + right.z * k * 1.1,
              });
            }
            fxLine(player.dimension, "kaiju8:tracer_gold", eye, dir, 12, 2.0);
            fx(player.dimension, "kaiju8:muzzle_star", ahead(player, 1.5));
            for (const h of cone(player, 5.4, -0.1)) {
              if (!hit(player, h.entity, 6 * ctx.mult)) continue;
              bleed(h.entity);
              knockback(h.entity, h.dx, h.dz, 0.2, 0.2);
              fxScatter(player.dimension, "kaiju8:powder_burn",
                        { x: h.entity.location.x, y: h.entity.location.y + 1,
                          z: h.entity.location.z }, 3, 0.6);
            }
            shoot(player, "kaiju8:df_bullet", 3.0, 0.10, null);
            sound(player.dimension, "random.explode", player.location,
                  { pitch: 1.9 + i * 0.05, volume: 0.35 });
            if (i % 2) {
              sound(player.dimension, "mob.ravager.bite", player.location,
                    { pitch: 1.5, volume: 0.7 });
            }
            later(1, () => {
              const at = ahead(player, 0.4);
              fxScatter(player.dimension, "kaiju8:brass_case",
                        { x: at.x + right.x * 0.5, y: at.y, z: at.z + right.z * 0.5 },
                        3, 0.35);
            });
          });
        }
        later(12, () => {
          fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, 1.2), 6, 1.0);
          fxScatter(player.dimension, "kaiju8:brass_case", ground(player), 6, 1.2);
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.9, volume: 0.5 });
        });
      } },
    { id: "raika", name: "kaiju8.tech.raika", cd: 62, wear: 3, canon: true,
      // 3式「雷火」— 帯電した刺突から斬り上げへ。
      // 刺した相手から隣へ電が跳ぶ。線は滑らかな光条ではなく折れた稲妻。
      run(player, ctx) {
        const dir = player.getViewDirection();
        const eye = player.getHeadLocation();
        fxLine(player.dimension, "kaiju8:coil_charge", ahead(player, 0.8), dir, 1.8, 0.45);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 0.7, volume: 0.8 });
        shake(player, 0.06, 0.2);
        later(1, () => {
          dash(player, 2.0, 0.05, false);
          fxScatter(player.dimension, "kaiju8:bolt_spit", player.location, 4, 0.8);
        });
        later(3, () => {
          fxLine(player.dimension, "kaiju8:bolt_strike", eye, dir, 7, 1.0);
          const struck = [];
          for (const h of ray(player, 7, 1.6)) {
            if (!hit(player, h.entity, 14 * ctx.mult)) continue;
            bleed(h.entity);
            struck.push(h.entity);
            const at = h.entity.location;
            fxScatter(player.dimension, "kaiju8:bolt_spit", at, 6, 0.9);
            fx(player.dimension, "kaiju8:halo_gold",
               { x: at.x, y: at.y + 1.0, z: at.z });
          }
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 1.9, volume: 0.5 });
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.5, volume: 0.5 });
          // 電が隣へ跳ぶ
          later(2, () => {
            for (const src of struck) {
              let from;
              try { from = src.location; } catch (_) { continue; }
              for (const near of targetsNear(src, 4.0)) {
                const dx = near.location.x - from.x;
                const dy = near.location.y - from.y;
                const dz = near.location.z - from.z;
                const len = Math.hypot(dx, dy, dz) || 1;
                fxLine(player.dimension, "kaiju8:bolt_spit",
                       { x: from.x, y: from.y + 1.0, z: from.z },
                       { x: dx / len, y: dy / len, z: dz / len }, len, 0.8);
                if (hit(player, near, 6 * ctx.mult)) bleed(near);
                break;
              }
            }
          });
        });
        later(7, () => {
          fx(player.dimension, "kaiju8:cut_arc_gold", ahead(player, 2.0));
          const up = ahead(player, 2.0);
          fx(player.dimension, "kaiju8:bolt_strike",
             { x: up.x, y: up.y + 0.5, z: up.z });
          for (const h of cone(player, 5.0, 0.1)) {
            if (!hit(player, h.entity, 12 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, h.dx, h.dz, 0.5, 0.9);
          }
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 1.1, volume: 1.2 });
          sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.15 });
        });
        later(9, () => {
          fxScatter(player.dimension, "kaiju8:bolt_spit", ahead(player, 1.6), 5, 1.4);
          shakeNearby(player.dimension, player.location, 12, 0.24, 0.3);
        });
      } },
    { id: "enu", name: "kaiju8.tech.enu", cd: 96, wear: 5, canon: true,
      // 4式「炎雨」— 上空から降り注ぐ。
      // 落ちる前に地面へ着弾点が描かれる。床に予兆を出すのはこの技だけ。
      run(player, ctx) {
        fx(player.dimension, "kaiju8:muzzle_star", ahead(player, 1.4));
        fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, -1.2), 5, 0.9);
        sound(player.dimension, "mob.ghast.fireball", player.location,
              { pitch: 0.7, volume: 1.4 });
        sound(player.dimension, "mob.wither.shoot", player.location,
              { pitch: 0.6, volume: 0.8 });
        const marks = cone(player, 14, 0.15).slice(0, 6).map((h) => ({
          x: h.entity.location.x, y: h.entity.location.y, z: h.entity.location.z,
        }));
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        if (!marks.length) {
          for (let i = 0; i < 4; i++) {
            const at = forward(eye, dir, 6 + i * 2.5);
            marks.push({ x: at.x, y: player.location.y, z: at.z });
          }
        }
        later(2, () => {
          for (const at of marks) {
            fxRing(player.dimension, "kaiju8:chevron_ember",
                   { x: at.x, y: at.y + 0.1, z: at.z }, 1.6, 8, 0.05);
          }
          sound(player.dimension, "beacon.power_select", player.location,
                { pitch: 1.9, volume: 0.4 });
        });
        for (let i = 0; i < 8; i++) {
          later(4 + i * 3, () => {
            const at = marks[i % marks.length];
            fxLine(player.dimension, "kaiju8:wound_fire",
                   { x: at.x, y: at.y + 7, z: at.z }, { x: 0, y: -1, z: 0 }, 7, 1.4);
            sound(player.dimension, "mob.ghast.fireball", at,
                  { pitch: 1.6, volume: 0.35 });
            later(1, () => {
              fx(player.dimension, "kaiju8:detonation_ember", at);
              fxScatter(player.dimension, "kaiju8:ember_rain", at, 5, 1.3);
              fxScatter(player.dimension, "kaiju8:impact_dust", at, 4, 1.2);
              for (const t of targetsNear(player, 24)) {
                const d = Math.hypot(t.location.x - at.x, t.location.z - at.z);
                if (d > 2.6) continue;
                if (!hit(player, t, 7 * ctx.mult)) continue;
                bleed(t);
                try { t.setOnFire(4, true); } catch (_) { }
              }
              const third = i % 3 === 2;
              sound(player.dimension, "random.explode", at,
                    { pitch: third ? 0.95 : 1.45, volume: third ? 0.9 : 0.55 });
              shakeNearby(player.dimension, at, 9, 0.26, 0.18);
            });
          });
        }
        later(34, () => {
          for (const at of marks) {
            fxScatter(player.dimension, "kaiju8:cauterize", at, 4, 1.6);
          }
          fxScatter(player.dimension, "kaiju8:ember_rain", player.location, 6, 6.0);
        });
      } },
    { id: "kaiten", name: "kaiju8.tech.kaiten", cd: 70, wear: 4, canon: true,
      // 5式「回天」— 三回転して薙ぎ払う。
      // 斬撃の先端が自分の周りを実際に回り、当たった相手は接線方向へ飛ぶ。
      run(player, ctx) {
        fx(player.dimension, "kaiju8:spin_wind", player.location);
        sound(player.dimension, "item.trident.riptide_3", player.location,
              { pitch: 0.8, volume: 1.1 });
        shake(player, 0.12, 0.55);
        for (let i = 0; i < 12; i++) {
          later(i, () => {
            const px = player.location.x, py = player.location.y, pz = player.location.z;
            for (const k of [0, 1, 2]) {
              const a = ((i * 30 + k * 12) * Math.PI) / 180;
              fx(player.dimension, "kaiju8:cut_arc_white", {
                x: px + Math.cos(a) * 3.2, y: py + 1.1, z: pz + Math.sin(a) * 3.2,
              });
            }
            if (i % 4 === 0) fx(player.dimension, "kaiju8:spin_wind", player.location);
            if (i % 4 === 0) {
              for (const t of targetsNear(player, 5.4)) {
                if (!hit(player, t, 10 * ctx.mult)) continue;
                bleed(t);
                const dx = t.location.x - px;
                const dz = t.location.z - pz;
                const len = Math.hypot(dx, dz) || 1;
                // 半径方向ではなく接線方向へ飛ばす
                knockback(t, -dz / len, dx / len, 1.3, 0.35);
                fxScatter(player.dimension, "kaiju8:cut_arc_white", t.location, 2, 0.6);
              }
            }
            if (i === 4 || i === 8) {
              fxScatter(player.dimension, "kaiju8:updraft", player.location, 6, 1.4);
            }
          });
        }
        later(10, () => {
          fx(player.dimension, "kaiju8:moon_arc", ahead(player, 2.4));
          fxRing(player.dimension, "kaiju8:updraft", player.location, 2.4, 10, 0.1);
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 0.85, volume: 1.3 });
          sound(player.dimension, "random.anvil_land", player.location,
                { pitch: 1.1, volume: 0.8 });
          shakeNearby(player.dimension, player.location, 14, 0.30, 0.35);
        });
      } },
    { id: "shichishitou", name: "kaiju8.tech.shichishitou", cd: 110, wear: 5,
      canon: true,
      // 6式「七支刀」— 七本に枝分かれする。
      // 撃つ前に砲口へ七つの灯が点くので、数が読める。
      run(player, ctx) {
        const dir = player.getViewDirection();
        const eye = player.getHeadLocation();
        const yaws = [-36, -24, -12, 0, 12, 24, 36];
        const tilts = [10, -6, 4, 0, -4, 6, -10];
        const branches = yaws.map((deg, i) => {
          const a = (deg * Math.PI) / 180;
          return {
            x: dir.x * Math.cos(a) - dir.z * Math.sin(a),
            y: dir.y + Math.sin((tilts[i] * Math.PI) / 180),
            z: dir.x * Math.sin(a) + dir.z * Math.cos(a),
          };
        });
        fxRing(player.dimension, "kaiju8:chit_thunder", ahead(player, 1.2), 0.55, 7, 0.0);
        sound(player.dimension, "mob.evocation_illager.prepare_summon", player.location,
              { pitch: 0.8, volume: 1.0 });
        shake(player, 0.10, 0.35);
        later(3, () => {
          for (const b of branches) {
            fxLine(player.dimension, "kaiju8:branch_lance", eye, b, 11, 1.1);
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.75, volume: 1.6 });
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 1.3, volume: 0.9 });
          for (const h of cone(player, 10, 0.05)) {
            if (!hit(player, h.entity, 22 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, h.dx, h.dz, 1.8, 0.5);
            const at = h.entity.location;
            fx(player.dimension, "kaiju8:branch_bloom",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fxScatter(player.dimension, "kaiju8:steel_shard", at, 5, 0.8);
          }
        });
        later(6, () => {
          for (const h of cone(player, 13, 0.35)) {
            if (hit(player, h.entity, 11 * ctx.mult)) bleed(h.entity);
          }
          for (const b of branches) {
            const tip = forward(eye, b, 9.5);
            fx(player.dimension, "kaiju8:detonation_ember", tip);
            fxScatter(player.dimension, "kaiju8:cauterize", tip, 3, 0.8);
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 1.05, volume: 1.1 });
          shakeNearby(player.dimension, player.location, 22, 0.22, 0.35);
        });
        later(8, () => fxScatter(player.dimension, "kaiju8:muzzle_smoke",
                                 ahead(player, 1.4), 8, 1.0));
      } },
  ],

  // ---- 怪獣8号の力 -----------------------------------------------------
  "kaiju8:no8_power": [
    { id: "fist", name: "kaiju8.tech.fist", cd: 26, energy: 6, form: true,
      canon: false,
      // 怪獣の一撃。拳へ光が集まり、抜けた先に圧の輪が並ぶ。
      // 体には衝撃、床には亀裂、と分けて出す。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fxScatter(player.dimension, "kaiju8:no8_charge", ahead(player, 1.0), 8, 0.7);
        sound(player.dimension, "mob.enderdragon.growl", player.location,
              { pitch: 1.6, volume: 0.5 });
        shake(player, 0.06, 0.12);
        later(2, () => {
          fx(player.dimension, "kaiju8:detonation_teal", ahead(player, 1.6));
          // 距離とともに広がる圧の輪
          for (const r of [2, 4, 6, 8]) {
            fxRing(player.dimension, "kaiju8:halo_teal", forward(eye, dir, r),
                   0.6 + r * 0.22, 8, 0.0);
          }
          fxLine(player.dimension, "kaiju8:chevron_teal", eye, dir, 9, 1.0);
          for (const h of ray(player, 9, 2.4)) {
            if (!hit(player, h.entity, 28 * ctx.mult)) continue;
            bleed(h.entity);
            const at = h.entity.location;
            knockback(h.entity, dir.x, dir.z, 2.4, 0.55);
            fx(player.dimension, "kaiju8:cut_cross",
               { x: at.x, y: at.y + 1.0, z: at.z });
            fxScatter(player.dimension, "kaiju8:crack_burst",
                      { x: at.x, y: at.y + 0.1, z: at.z }, 6, 1.0);
          }
          sound(player.dimension, "mob.ravager.stun", player.location,
                { pitch: 0.50, volume: 1.8 });
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.45, volume: 1.4 });
          sound(player.dimension, "mob.enderdragon.flap", player.location,
                { pitch: 0.5, volume: 0.9 });
          shakeNearby(player.dimension, player.location, 18, 0.44, 0.4);
        });
        later(4, () => {
          fxLine(player.dimension, "kaiju8:crack_burst", ground(player), dir, 8, 2.0);
          fxScatter(player.dimension, "kaiju8:impact_dust", ahead(player, 4.0), 10, 2.2);
        });
      } },
    { id: "boost", name: "kaiju8.tech.boost", cd: 40, energy: 8, form: true,
      canon: false,
      // 解放跳躍。足元から下向きに噴いて跳び、飛んでいる間ずっと継ぎ目の光が
      // 剥がれ落ちる。着地は tickSlams が 'boost' 用の演出で受ける。
      run(player, ctx) {
        fxRing(player.dimension, "kaiju8:chevron_teal", ground(player), 1.1, 10, 0.05);
        sound(player.dimension, "beacon.power_select", player.location,
              { pitch: 0.5, volume: 0.7 });
        dash(player, 2.6, 1.25, false);
        fx(player.dimension, "kaiju8:no8_launch", ground(player));
        fxScatter(player.dimension, "kaiju8:impact_dust", ground(player), 14, 1.8);
        fx(player.dimension, "kaiju8:halo_teal",
           { x: player.location.x, y: player.location.y + 0.4, z: player.location.z });
        sound(player.dimension, "mob.enderdragon.flap", player.location,
              { pitch: 0.55, volume: 1.4 });
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.1, volume: 0.7 });
        sound(player.dimension, "mob.enderdragon.growl", player.location,
              { pitch: 1.9, volume: 0.4 });
        shake(player, 0.30, 0.25);
        for (let i = 2; i <= 20; i += 2) {
          later(i, () => {
            fx(player.dimension, "kaiju8:afterimage",
               { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
            fxScatter(player.dimension, "kaiju8:no8_seam_trail", player.location, 2, 0.5);
            if (i % 6 === 0) {
              fx(player.dimension, "kaiju8:halo_teal", player.location);
            }
            if (i === 6 || i === 12) {
              sound(player.dimension, "mob.enderdragon.flap", player.location,
                    { pitch: 1.5, volume: 0.25 });
            }
          });
        }
        registerSlam(player, ctx.mult, "boost");
      } },
    { id: "energy_roar", name: "kaiju8.tech.energy_roar", cd: 90, energy: 22,
      form: true, charge: 12, canon: false,
      // エネルギー咆哮。喉の光が膨らみ、吸い込む輪が四段で狭まり、
      // 開いた口の一瞬だけ無音になってから撃つ。
      run(player, ctx) {
        const eye = player.getHeadLocation();
        const dir = player.getViewDirection();
        fxScatter(player.dimension, "kaiju8:seam_glow", player.location, 12, 1.1);
        fx(player.dimension, "kaiju8:no8_maw", forward(eye, dir, 0.5));
        sound(player.dimension, "mob.enderdragon.growl", player.location,
              { pitch: 0.40, volume: 2.4 });
        for (let i = 0; i < 4; i++) {
          later(i * 3, () => {
            fxRing(player.dimension, "kaiju8:no8_charge", player.location,
                   5.0 - i * 1.2, 10 + i * 2, 0.8);
            sound(player.dimension, "beacon.power_select", player.location,
                  { pitch: 0.8 + i * 0.25, volume: 0.6 });
            shake(player, 0.08 + i * 0.05, 0.25);
          });
        }
        // 口が開いてから撃つまでの2tickは意図的に無音
        later(10, () => fx(player.dimension, "kaiju8:detonation_teal",
                           forward(eye, dir, 0.8)));
        later(12, () => {
          const eye2 = player.getHeadLocation();
          const dir2 = player.getViewDirection();
          fxLine(player.dimension, "kaiju8:energy_roar", eye2, dir2, 26, 0.9);
          fxLine(player.dimension, "kaiju8:no8_coil", eye2, dir2, 26, 1.4);
          for (const r of [3, 8, 14, 20, 26]) {
            fx(player.dimension, "kaiju8:halo_teal", forward(eye2, dir2, r));
          }
          fxScatter(player.dimension, "kaiju8:no8_launch",
                    forward(player.location, { x: -dir2.x, y: 0, z: -dir2.z }, 1.5),
                    8, 1.0);
          for (const h of ray(player, 26, 3.0)) {
            if (!hit(player, h.entity, 30 * ctx.mult)) continue;
            bleed(h.entity);
            knockback(h.entity, dir2.x, dir2.z, 2.0, 0.4);
          }
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 0.55, volume: 2.0 });
          sound(player.dimension, "mob.enderdragon.growl", player.location,
                { pitch: 0.7, volume: 2.4 });
          shakeNearby(player.dimension, player.location, 26, 0.55, 0.7);
        });
      } },
  ],
};

// ===========================================================================
export function tickSlams() {
  if (!pendingSlams.size) return;
  for (const [id, info] of [...pendingSlams]) {
    if (system.currentTick - info.at > 120) { pendingSlams.delete(id); continue; }
    const player = info.player;
    if (!player) { pendingSlams.delete(id); continue; }
    if (system.currentTick - info.at < 8) continue;
    let onGround = false;
    try { onGround = player.isOnGround; } catch (_) { pendingSlams.delete(id); continue; }
    if (!onGround) continue;
    pendingSlams.delete(id);
    const g = { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
    for (const t of targetsNear(player, 7.0)) {
      const dx = t.location.x - player.location.x;
      const dz = t.location.z - player.location.z;
      const len = Math.hypot(dx, dz) || 1;
      if (hit(player, t, 24 * info.mult)) {
        bleed(t);
        knockback(t, dx / len, dz / len, 1.6, 0.7);
      }
    }
    // 解放跳躍からの着地は、ただの落下より一段大きく青い
    if (info.kind === "boost") {
      fx(player.dimension, "kaiju8:quake_teal", g);
      fxRing(player.dimension, "kaiju8:crack_burst", g, 2.6, 12, 0.05);
      fxScatter(player.dimension, "kaiju8:no8_seam_trail", g, 8, 1.5);
      sound(player.dimension, "mob.enderdragon.growl", player.location,
            { pitch: 0.6, volume: 1.2 });
    } else {
      fx(player.dimension, "kaiju8:shock_ring", g);
    }
    fxScatter(player.dimension, "kaiju8:impact_dust", g, 16, 2.2);
    fxScatter(player.dimension, "kaiju8:debris", g, 12, 1.6);
    sound(player.dimension, "random.explode", player.location,
          { pitch: 0.6, volume: 1.8 });
    shakeNearby(player.dimension, player.location, 18, 0.5, 0.55);
  }
}

// ===========================================================================
//  切り返し (technique selection)
//
//  識別怪獣兵器（ナンバーズ）を着ていると、その機体の固有能力が持っている武器の
//  技の後ろに並ぶ。つまり能力も同じスニークの切り返しで選び、同じ右クリックで
//  撃てる。技を持たない道具（怪獣探知機など）には割り込まない。
// ===========================================================================
function readSelection(player) {
  try {
    const raw = player.getDynamicProperty(SEL);
    if (typeof raw === "string" && raw) return JSON.parse(raw);
  } catch (_) { }
  return {};
}

/** ナンバーズの固有能力を技と同じ形にして返す。 */
function numbersEntries(player) {
  const id = wornNumbers(player);
  if (!id) return [];
  return (NUMBERS[id]?.abilities ?? []).map((a) => ({
    id: a.id, name: a.name, cd: a.cd, wear: 0, canon: true,
    numbers: id, ability: a.id, run: a.run,
  }));
}

/** その武器で今切り返せる一覧。技を持たない道具には undefined を返す。 */
export function listFor(player, typeId) {
  const base = TECH[typeId];
  if (!base) return undefined;
  const extra = numbersEntries(player);
  return extra.length ? base.concat(extra) : base;
}

export function selectedIndex(player, typeId) {
  const list = listFor(player, typeId);
  if (!list || !list.length) return 0;
  const map = readSelection(player);
  return ((map[typeId] ?? 0) % list.length + list.length) % list.length;
}

export function selected(player, typeId) {
  const list = listFor(player, typeId);
  return list ? list[selectedIndex(player, typeId)] : undefined;
}

export function cycle(player, typeId, step = 1) {
  const list = listFor(player, typeId);
  if (!list || list.length < 2) return undefined;
  const map = readSelection(player);
  const next = (((map[typeId] ?? 0) + step) % list.length + list.length) % list.length;
  map[typeId] = next;
  try { player.setDynamicProperty(SEL, JSON.stringify(map)); } catch (_) { }
  const picked = list[next];
  // ホイールが能力に乗ったら端末側の選択も合わせる。スニーク＋ジャンプの
  // 即時発動と食い違わないように。
  if (picked?.numbers) setAbilityById(player, picked.numbers, picked.ability);
  return picked;
}

/** 解放戦力の帯別カラー (仕様書 §2 の HUD カラーバンド)。 */
export function releaseColour(rate) {
  if (rate >= 90) return "§6";
  if (rate >= 60) return "§e";
  if (rate >= 30) return "§a";
  if (rate >= 10) return "§b";
  return "§7";
}

/** 技ホイールをアクションバーに描く。 */
export function showWheel(player, typeId, rate) {
  const list = listFor(player, typeId);
  if (!list || !list.length) return;
  const current = selectedIndex(player, typeId);
  const n = list.length;
  const parts = [{ translate: `item.${typeId}` },
                 { text: `  §8${current + 1}/${n}§r\n` }];
  // 技が増えたので、現在地とその前後だけを出す
  for (const off of (n <= 3 ? [...Array(n).keys()].map((i) => i - current) : [-1, 0, 1])) {
    const i = ((current + off) % n + n) % n;
    const entry = list[i];
    // ナンバーズの能力は紫、武器の技は水色で区別する
    const mark = entry.numbers ? (off === 0 ? "§d§l▸ " : "§5  ")
                               : (off === 0 ? "§b§l▸ " : "§8  ");
    parts.push({ text: mark });
    parts.push({ translate: entry.name });
    parts.push({ text: "§r  " });
  }
  parts.push({ text: `\n§7解放戦力 ${releaseColour(rate)}${rate}%` });
  actionbar(player, { rawtext: parts });
}
