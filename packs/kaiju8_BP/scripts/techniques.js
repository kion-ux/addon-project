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
  fx, fxRing, fxLine, fxScatter, sound, shake, shakeNearby, cone, ray, hit,
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

function ground(player) {
  return { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
}

function shoot(player, typeId, speed, spread = 0) {
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
  fx(player.dimension, "kaiju8:muzzle_flash", origin);
  fxScatter(player.dimension, "kaiju8:muzzle_sparks", origin, 5, 0.25);
  return proj;
}

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
      run(player, ctx) {
        arcFx(player, 1.6);
        swing(player, ctx, { radius: 3.6, dot: 0.35, damage: 7, kb: 0.5 });
        sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.4 });
        shake(player, 0.08, 0.15);
      } },
    { id: "thrust", name: "kaiju8.tech.thrust", cd: 34, wear: 1, canon: false,
      run(player, ctx) {
        dash(player, 1.3, 0.08, false);
        later(2, () => {
          let n = 0;
          for (const t of ray(player, 4.5, 1.0)) {
            if (hit(player, t.entity, 12 * ctx.mult)) { bleed(t.entity); n++; }
          }
          fxLine(player.dimension, "kaiju8:slash_scatter",
                 player.getHeadLocation(), player.getViewDirection(), 4, 1.4);
          if (n) shake(player, 0.14, 0.2);
        });
        sound(player.dimension, "item.trident.riptide_1", player.location, { pitch: 1.7 });
      } },
  ],

  // ---- DF-STD アサルトライフル: ユニソケットで弾種を切り替える ----------
  "kaiju8:df_rifle": [
    { id: "socket_burst", name: "kaiju8.tech.socket_burst", cd: 8, wear: 1, canon: true,
      run(player) {
        const proj = shoot(player, "kaiju8:df_bullet", 3.0, 0.03);
        if (proj) fx(player.dimension, "kaiju8:socket_burst", proj.location);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.9, volume: 0.35 });
        shake(player, 0.05, 0.10);
      } },
    { id: "socket_freeze", name: "kaiju8.tech.socket_freeze", cd: 44, wear: 2, canon: true,
      run(player, ctx) {
        shoot(player, "kaiju8:df_bullet", 2.8);
        later(3, () => {
          let n = 0;
          for (const t of ray(player, 22, 2.2)) {
            if (hit(player, t.entity, 5 * ctx.mult)) {
              bleed(t.entity);
              try {
                t.entity.addEffect("slowness", 160, { amplifier: 3, showParticles: true });
              } catch (_) { }
              fxScatter(player.dimension, "kaiju8:socket_freeze",
                        t.entity.location, 8, 0.9);
              n++;
            }
          }
          if (n) sound(player.dimension, "random.glass", player.location, { pitch: 1.4 });
        });
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.6, volume: 0.4 });
      } },
    { id: "socket_thunder", name: "kaiju8.tech.socket_thunder", cd: 50, wear: 2, canon: true,
      run(player, ctx) {
        shoot(player, "kaiju8:df_bullet", 3.2);
        later(3, () => {
          const first = ray(player, 24, 2.0)[0];
          if (!first) return;
          let node = first.entity;
          for (let i = 0; i < 4 && node; i++) {
            if (hit(player, node, (10 - i * 1.5) * ctx.mult)) bleed(node);
            fxScatter(player.dimension, "kaiju8:socket_thunder", node.location, 5, 0.8);
            const near = targetsNear(node, 6).filter((e) => e.id !== node.id);
            node = near[0];
          }
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 1.6, volume: 0.5 });
        });
      } },
  ],

  // ---- SW-2033 保科流 --------------------------------------------------
  "kaiju8:twin_sw2033": [
    { id: "karauchi", name: "kaiju8.tech.karauchi", cd: 20, wear: 1, canon: true,
      // 刀伐術1式「空討ち」— 刃が届いていない位置に斬撃が飛ぶ
      run(player, ctx) {
        arcFx(player, 3.4, "kaiju8:slash_air");
        fxLine(player.dimension, "kaiju8:slash_air",
               player.getHeadLocation(), player.getViewDirection(), 7, 2.2);
        let n = 0;
        for (const t of ray(player, 8, 2.0)) {
          if (hit(player, t.entity, 10 * ctx.mult)) { bleed(t.entity); n++; }
        }
        sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.6 });
        if (n) shake(player, 0.10, 0.18);
      } },
    { id: "kousa", name: "kaiju8.tech.kousa", cd: 34, wear: 2, canon: true,
      // 刀伐術2式「交差討ち」— X字に交差した斬撃
      run(player, ctx) {
        for (const d of [0, 3]) {
          later(d, () => {
            arcFx(player, 2.8, "kaiju8:slash_cross");
            swing(player, ctx, { radius: 6.0, dot: 0.05, damage: 9, kb: 0.5 });
            sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.45 });
          });
        }
        shake(player, 0.14, 0.26);
      } },
    { id: "kaeshi", name: "kaiju8.tech.kaeshi", cd: 46, wear: 2, canon: true,
      // 刀伐術3式「返し討ち」— 攻撃をすり抜けて背後から斬る
      run(player, ctx) {
        try { player.addEffect("resistance", 16, { amplifier: 3, showParticles: false }); }
        catch (_) { }
        afterimages(player, 5);
        sound(player.dimension, "mob.endermen.portal", player.location, { pitch: 1.6 });
        later(5, () => {
          let best, bd = 99;
          for (const t of targetsNear(player, 6.5)) {
            const dx = t.location.x - player.location.x;
            const dz = t.location.z - player.location.z;
            const d = Math.hypot(dx, dz);
            if (d < bd) { bd = d; best = t; }
          }
          if (!best) return;
          const dx = best.location.x - player.location.x;
          const dz = best.location.z - player.location.z;
          const len = Math.hypot(dx, dz) || 1;
          try {
            player.teleport({ x: best.location.x + dx / len * 1.6,
                              y: best.location.y, z: best.location.z + dz / len * 1.6 },
                            { dimension: player.dimension });
          } catch (_) { }
          fx(player.dimension, "kaiju8:slash_cross",
             { x: best.location.x, y: best.location.y + 1.1, z: best.location.z });
          if (hit(player, best, 22 * ctx.mult)) bleed(best);
          sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.2 });
          shake(player, 0.2, 0.24);
        });
      } },
    { id: "midare", name: "kaiju8.tech.midare", cd: 60, wear: 3, canon: true,
      // 刀伐術4式「乱討ち」— 無数の斬撃を散弾状にばら撒く
      run(player, ctx) {
        for (let i = 0; i < 5; i++) {
          later(i * 2, () => {
            fxScatter(player.dimension, "kaiju8:slash_scatter", ahead(player, 3), 1, 2.2);
            swing(player, ctx, { radius: 7.0, dot: -0.1, damage: 5, kb: 0.15 });
          });
        }
        sound(player.dimension, "mob.ravager.roar", player.location, { pitch: 1.7 });
        shake(player, 0.16, 0.5);
      } },
    { id: "oboro", name: "kaiju8.tech.oboro", cd: 56, wear: 2, canon: true,
      // 抜討術1式「朧抜き」— 対象を突き抜けながらの居合抜き
      run(player, ctx) {
        sound(player.dimension, "item.trident.riptide_2", player.location, { pitch: 1.6 });
        dash(player, 3.2, 0.10, false);
        afterimages(player, 8);
        later(4, () => {
          arcFx(player, 1.8, "kaiju8:slash_air");
          const n = swing(player, ctx, { radius: 6.0, dot: -0.2, damage: 16, kb: 0.2 });
          if (n) shakeNearby(player.dimension, player.location, 10, 0.24, 0.3);
        });
      } },
    { id: "junihitoe", name: "kaiju8.tech.junihitoe", cd: 150, wear: 6, canon: true,
      requires: "kaiju8:numbers_10",
      // 刀伐術7式「十二単」— 一点集中の12連撃。解放戦力が高いほど本領を発揮
      run(player, ctx) {
        sound(player.dimension, "mob.ravager.roar", player.location,
              { pitch: 1.8, volume: 1.4 });
        for (let i = 0; i < 12; i++) {
          later(i, () => {
            fx(player.dimension, "kaiju8:slash_12", ahead(player, 2.6));
            for (const t of ray(player, 6.5, 1.6)) {
              if (hit(player, t.entity, 4.5 * ctx.mult)) bleed(t.entity);
            }
          });
        }
        later(13, () => {
          fx(player.dimension, "kaiju8:fist_shock", ahead(player, 2.6));
          shakeNearby(player.dimension, player.location, 16, 0.38, 0.5);
        });
        shake(player, 0.22, 0.8);
      } },
  ],

  // ---- SW-1023 一刀（保科の予備・兄の流儀） ------------------------------
  "kaiju8:blade_sw1023": [
    { id: "kasumi", name: "kaiju8.tech.kasumi", cd: 48, wear: 2, canon: true,
      // 刀伐術5式「霞討ち」— 交差2撃を囮に、遅れて本命の第3撃が入る
      run(player, ctx) {
        for (const d of [0, 3]) {
          later(d, () => {
            arcFx(player, 2.6, "kaiju8:slash_cross");
            swing(player, ctx, { radius: 5.4, dot: 0.1, damage: 5, kb: 0.2 });
            sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.6 });
          });
        }
        later(11, () => {
          arcFx(player, 2.2, "kaiju8:slash_air");
          const n = swing(player, ctx, { radius: 5.8, dot: 0.0, damage: 20, kb: 0.9 });
          sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 0.85 });
          if (n) shakeNearby(player.dimension, player.location, 10, 0.26, 0.3);
        });
      } },
    { id: "yae", name: "kaiju8.tech.yae", cd: 80, wear: 4, canon: true,
      // 刀伐術6式「八重討ち」— 層状に重なる八分割の多重斬
      run(player, ctx) {
        for (let i = 0; i < 8; i++) {
          later(i * 2, () => {
            fx(player.dimension, "kaiju8:slash_air",
               forward(player.getHeadLocation(), player.getViewDirection(),
                       1.6 + i * 0.22));
            swing(player, ctx, { radius: 5.2, dot: 0.15, damage: 5.5, kb: 0.1 });
          });
        }
        sound(player.dimension, "mob.ravager.roar", player.location, { pitch: 1.5 });
        shake(player, 0.18, 0.7);
      } },
    { id: "kazaana", name: "kaiju8.tech.kazaana", cd: 62, wear: 3, canon: true,
      // 抜討術2式「風穴」— 抜刀と刺突の複合。対象を貫通して穴を開ける
      run(player, ctx) {
        sound(player.dimension, "item.trident.riptide_3", player.location, { pitch: 1.3 });
        dash(player, 2.2, 0.06, false);
        afterimages(player, 6);
        later(4, () => {
          const dir = player.getViewDirection();
          const eye = player.getHeadLocation();
          fxLine(player.dimension, "kaiju8:slash_air", eye, dir, 9, 1.5);
          let n = 0;
          for (const t of ray(player, 9, 1.4)) {
            if (hit(player, t.entity, 26 * ctx.mult)) {
              bleed(t.entity);
              fxScatter(player.dimension, "kaiju8:kaiju_blood", t.entity.location, 6, 0.7);
              n++;
            }
          }
          if (n) shakeNearby(player.dimension, player.location, 12, 0.3, 0.3);
        });
      } },
    { id: "sakabyoshi", name: "kaiju8.tech.sakabyoshi", cd: 44, wear: 2, canon: true,
      // 抜討術3式「逆拍子」— 振りの途中で方向を反転させ拍子を崩す
      run(player, ctx) {
        arcFx(player, 2.2, "kaiju8:slash_air");
        swing(player, ctx, { radius: 5.0, dot: 0.2, damage: 9, kb: 0.5 });
        sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.4 });
        later(4, () => {
          arcFx(player, 2.0, "kaiju8:slash_cross");
          const n = swing(player, ctx, { radius: 5.0, dot: 0.2, damage: 15 * 1.0,
                                         kb: 1.0, up: 0.3 });
          sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 0.95 });
          if (n) shake(player, 0.2, 0.24);
        });
      } },
  ],

  // ---- DF-STD バズーカ / 自動拳銃 ---------------------------------------
  "kaiju8:df_bazooka": [
    { id: "he_shell", name: "kaiju8.tech.he_shell", cd: 70, wear: 3, canon: false,
      run(player, ctx) {
        shoot(player, "kaiju8:rifle_beam", 2.4);
        fx(player.dimension, "kaiju8:cannon_muzzle", ahead(player, 1.4));
        fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, -1.4), 8, 1.0);
        later(4, () => {
          const t0 = ray(player, 30, 2.6)[0];
          const at = t0 ? t0.entity.location : ahead(player, 16);
          fxScatter(player.dimension, "kaiju8:socket_burst", at, 12, 1.4);
          fx(player.dimension, "kaiju8:shock_ring", at);
          for (const t of targetsNear(player, 40)) {
            const d = Math.hypot(t.location.x - at.x, t.location.z - at.z);
            if (d > 5) continue;
            if (hit(player, t, (26 - d * 3) * ctx.mult)) bleed(t);
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.7, volume: 1.6 });
          shakeNearby(player.dimension, at, 14, 0.38, 0.45);
        });
      } },
    { id: "incendiary", name: "kaiju8.tech.incendiary", cd: 90, wear: 4, canon: false,
      run(player, ctx) {
        for (let i = 0; i < 3; i++) {
          later(i * 5, () => {
            shoot(player, "kaiju8:kaiju_acid", 2.0, 0.12);
            fx(player.dimension, "kaiju8:cannon_muzzle", ahead(player, 1.4));
          });
        }
        later(10, () => {
          for (const t of cone(player, 14, 0.4)) {
            if (hit(player, t.entity, 10 * ctx.mult)) {
              bleed(t.entity);
              try { t.entity.setOnFire(6, true); } catch (_) { }
              fxScatter(player.dimension, "kaiju8:cauterize", t.entity.location, 5, 0.9);
            }
          }
        });
        sound(player.dimension, "random.explode", player.location, { pitch: 0.9 });
        shake(player, 0.2, 0.7);
      } },
  ],
  "kaiju8:df_pistol": [
    { id: "rapid", name: "kaiju8.tech.rapid", cd: 5, wear: 1, canon: false,
      run(player) {
        shoot(player, "kaiju8:df_bullet", 3.2, 0.06);
        sound(player.dimension, "random.explode", player.location,
              { pitch: 2.1, volume: 0.3 });
        shake(player, 0.04, 0.08);
      } },
    { id: "aimed", name: "kaiju8.tech.aimed", cd: 30, wear: 1, canon: false,
      run(player, ctx) {
        const t0 = ray(player, 26, 1.1)[0];
        fxLine(player.dimension, "kaiju8:slash_scatter",
               player.getHeadLocation(), player.getViewDirection(), 12, 2.0);
        fx(player.dimension, "kaiju8:muzzle_flash", ahead(player, 1.0));
        if (t0 && hit(player, t0.entity, 18 * ctx.mult)) {
          bleed(t0.entity);
          fxScatter(player.dimension, "kaiju8:socket_burst", t0.entity.location, 5, 0.6);
        }
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.7, volume: 0.6 });
        shake(player, 0.10, 0.16);
      } },
  ],

  // ---- 03Ax-0112 隊式斧術 ---------------------------------------------
  "kaiju8:axe_03ax": [
    { id: "rakurai", name: "kaiju8.tech.rakurai", cd: 60, wear: 3, canon: true,
      // 1式「落雷」— 斧の背面から衝撃波を噴射し、振りを加速させる
      run(player, ctx) {
        fxScatter(player.dimension, "kaiju8:axe_backblast",
                  forward(player.getHeadLocation(), player.getViewDirection(), -1.2),
                  4, 0.6);
        fx(player.dimension, "kaiju8:axe_arc", ahead(player, 2.2));
        const n = swing(player, ctx, { radius: 5.6, dot: 0.05, damage: 20, kb: 1.2,
                                       up: 0.35, particle: "kaiju8:axe_arc" });
        fx(player.dimension, "kaiju8:shock_ring_gold", ground(player));
        fxScatter(player.dimension, "kaiju8:impact_dust", ground(player), 10, 1.6);
        sound(player.dimension, "random.anvil_land", player.location,
              { pitch: 0.55, volume: 1.5 });
        shakeNearby(player.dimension, player.location, 14, 0.34, 0.42);
        return n;
      } },
    { id: "mizukiri", name: "kaiju8.tech.mizukiri", cd: 48, wear: 3, canon: true,
      // 2式「水切」— 命中の瞬間に前方へ放電
      run(player, ctx) {
        fx(player.dimension, "kaiju8:axe_frontblast", ahead(player, 2.4));
        swing(player, ctx, { radius: 6.4, dot: -0.05, damage: 14, kb: 2.1, up: 0.25,
                             particle: "kaiju8:axe_arc" });
        sound(player.dimension, "random.explode", player.location,
              { pitch: 1.3, volume: 1.1 });
        shake(player, 0.24, 0.3);
      } },
    { id: "hangetsu", name: "kaiju8.tech.hangetsu", cd: 56, wear: 3, canon: true,
      // 3式「半月」— 三日月軌道で薙ぎ、軌跡全体から衝撃波
      run(player, ctx) {
        fx(player.dimension, "kaiju8:axe_crescent", ahead(player, 2.6));
        fxRing(player.dimension, "kaiju8:axe_arc", player.location, 3.4, 12, 1.0);
        swing(player, ctx, { radius: 7.2, dot: -0.45, damage: 12, kb: 1.6, up: 0.3 });
        sound(player.dimension, "mob.ravager.roar", player.location, { pitch: 0.95 });
        shake(player, 0.2, 0.34);
      } },
    { id: "darumaotoshi", name: "kaiju8.tech.darumaotoshi", cd: 90, wear: 4, canon: true,
      // 4式「達磨落」— 帯電した水平打で一段だけを横に叩き飛ばす
      run(player, ctx) {
        fx(player.dimension, "kaiju8:axe_arc", ahead(player, 2.0));
        const hits = cone(player, 5.0, 0.2);
        for (const h of hits) {
          if (!hit(player, h.entity, 26 * ctx.mult)) continue;
          bleed(h.entity);
          knockback(h.entity, h.dx, h.dz, 3.2, 0.05);   // 真横に吹き飛ばす
          fxScatter(player.dimension, "kaiju8:crack_burst", h.entity.location, 6, 0.8);
        }
        sound(player.dimension, "random.anvil_land", player.location,
              { pitch: 0.75, volume: 1.4 });
        shakeNearby(player.dimension, player.location, 12, 0.3, 0.4);
      } },
  ],

  // ---- T-25101985 亜白ミナ（原作に技名なし＝本アドオンの創作） -----------
  "kaiju8:cannon_t25": [
    { id: "senkou", name: "kaiju8.tech.senkou", cd: 28, wear: 2, canon: false,
      run(player) {
        shoot(player, "kaiju8:rifle_beam", 3.6);
        fx(player.dimension, "kaiju8:cannon_muzzle", ahead(player, 1.2));
        fxScatter(player.dimension, "kaiju8:muzzle_smoke", ahead(player, -1.0), 5, 0.8);
        fxLine(player.dimension, "kaiju8:beam_trail",
               player.getHeadLocation(), player.getViewDirection(), 10, 1.8);
        sound(player.dimension, "mob.wither.shoot", player.location,
              { pitch: 0.7, volume: 1.4 });
        shake(player, 0.22, 0.24);
      } },
    { id: "danmaku", name: "kaiju8.tech.danmaku", cd: 66, wear: 4, canon: false,
      run(player) {
        for (let i = 0; i < 5; i++) {
          later(i * 4, () => {
            shoot(player, "kaiju8:rifle_beam", 3.2, 0.05);
            sound(player.dimension, "mob.wither.shoot", player.location,
                  { pitch: 1.0, volume: 0.85 });
          });
        }
        shake(player, 0.16, 0.9);
      } },
    { id: "raitei", name: "kaiju8.tech.raitei", cd: 130, wear: 8, charge: 30, canon: false,
      // ケラウノス相当のチャージ砲撃
      run(player, ctx) {
        fxScatter(player.dimension, "kaiju8:cannon_charge", ahead(player, 1.6), 12, 1.4);
        sound(player.dimension, "beacon.activate", player.location, { pitch: 0.65 });
        later(30, () => {
          const dir = player.getViewDirection();
          const eye = player.getHeadLocation();
          fxLine(player.dimension, "kaiju8:railgun_lance", eye, dir, 48, 1.2);
          fxLine(player.dimension, "kaiju8:beam_impact", eye, dir, 48, 5.0);
          let n = 0;
          for (const t of ray(player, 48, 2.0)) {
            if (hit(player, t.entity, 34 * ctx.mult)) { bleed(t.entity); n++; }
          }
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 1.1, volume: 1.6 });
          shakeNearby(player.dimension, player.location, 20, 0.45, 0.6);
          if (n) fx(player.dimension, "kaiju8:core_break", ahead(player, 4));
        });
      } },
  ],

  // ---- GS-3305 隊式銃剣術 ---------------------------------------------
  "kaiju8:gunblade_gs3305": [
    { id: "sakuretsuzan", name: "kaiju8.tech.sakuretsuzan", cd: 34, wear: 2, canon: true,
      // 1式「炸裂斬」— 斬撃の着弾点が遅れて爆裂する
      run(player, ctx) {
        arcFx(player, 2.2, "kaiju8:slash_air");
        const hits = cone(player, 5.2, 0.1);
        for (const h of hits) {
          if (!hit(player, h.entity, 11 * ctx.mult)) continue;
          bleed(h.entity);
          fxScatter(player.dimension, "kaiju8:cauterize", h.entity.location, 4, 0.7);
          const target = h.entity;
          later(4, () => {
            try {
              fx(player.dimension, "kaiju8:burst_slash", target.location);
              hit(player, target, 9 * ctx.mult);
              sound(player.dimension, "random.explode", player.location,
                    { pitch: 1.2, volume: 0.9 });
            } catch (_) { }
          });
        }
        sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 0.9 });
        shake(player, 0.16, 0.3);
      } },
    { id: "zanmaku", name: "kaiju8.tech.zanmaku", cd: 70, wear: 4, canon: true,
      // 2式「斬幕砲火」— 斬撃の幕を張りつつ銃撃を重ねる面制圧
      run(player, ctx) {
        for (let i = 0; i < 4; i++) {
          later(i * 3, () => {
            arcFx(player, 2.4, "kaiju8:slash_air");
            swing(player, ctx, { radius: 5.4, dot: -0.1, damage: 6, kb: 0.2,
                                 particle: "kaiju8:cauterize" });
            shoot(player, "kaiju8:df_bullet", 3.0, 0.10);
          });
        }
        shake(player, 0.18, 0.7);
      } },
    { id: "raika", name: "kaiju8.tech.raika", cd: 52, wear: 3, canon: true,
      // 3式「雷火」— 帯電した高速の刺突から斬り上げ
      run(player, ctx) {
        dash(player, 2.0, 0.05, false);
        fxScatter(player.dimension, "kaiju8:socket_thunder", ahead(player, 1.6), 6, 0.8);
        later(3, () => {
          let n = 0;
          for (const t of ray(player, 7, 1.6)) {
            if (hit(player, t.entity, 14 * ctx.mult)) { bleed(t.entity); n++; }
            fxScatter(player.dimension, "kaiju8:socket_thunder", t.entity.location, 5, 0.8);
          }
          later(4, () => {
            arcFx(player, 2.0, "kaiju8:slash_heavy");
            swing(player, ctx, { radius: 5.0, dot: 0.1, damage: 12, kb: 0.5, up: 0.9 });
          });
          if (n) shake(player, 0.2, 0.3);
        });
        sound(player.dimension, "ambient.weather.thunder", player.location,
              { pitch: 1.5, volume: 0.6 });
      } },
    { id: "enu", name: "kaiju8.tech.enu", cd: 96, wear: 5, canon: true,
      // 4式「炎雨」— 上空から降り注ぐ多数の射撃／斬撃
      run(player, ctx) {
        sound(player.dimension, "mob.ghast.fireball", player.location, { pitch: 0.9 });
        const marks = cone(player, 14, 0.15).slice(0, 6).map((h) => h.entity);
        for (let i = 0; i < 10; i++) {
          later(i * 3, () => {
            const target = marks[i % Math.max(1, marks.length)];
            const at = target ? target.location : ahead(player, 8);
            fx(player.dimension, "kaiju8:branch_blast",
               { x: at.x, y: at.y + 4, z: at.z });
            fxScatter(player.dimension, "kaiju8:burst_slash", at, 4, 1.0);
            for (const t of targetsNear(player, 16)) {
              if (Math.hypot(t.location.x - at.x, t.location.z - at.z) > 2.6) continue;
              if (hit(player, t, 7 * ctx.mult)) bleed(t);
            }
            sound(player.dimension, "random.explode", player.location,
                  { pitch: 1.3, volume: 0.5 });
          });
        }
        shake(player, 0.22, 1.2);
      } },
    { id: "kaiten", name: "kaiju8.tech.kaiten", cd: 78, wear: 4, canon: true,
      // 5式「回天」— 全身回転を伴う円環斬
      run(player, ctx) {
        for (let i = 0; i < 3; i++) {
          later(i * 4, () => {
            fxRing(player.dimension, "kaiju8:slash_scatter", player.location, 3.2, 12, 1.1);
            for (const t of targetsNear(player, 5.4)) {
              if (hit(player, t, 10 * ctx.mult)) {
                bleed(t);
                const dx = t.location.x - player.location.x;
                const dz = t.location.z - player.location.z;
                const len = Math.hypot(dx, dz) || 1;
                knockback(t, dx / len, dz / len, 1.2, 0.3);
              }
            }
          });
        }
        sound(player.dimension, "mob.ravager.roar", player.location, { pitch: 1.1 });
        shake(player, 0.2, 0.6);
      } },
    { id: "shichishitou", name: "kaiju8.tech.shichishitou", cd: 140, wear: 6, canon: true,
      // 6式「七支刀」— 7方向に枝分かれする放射爆風
      run(player, ctx) {
        const dir = player.getViewDirection();
        const eye = player.getHeadLocation();
        fxLine(player.dimension, "kaiju8:branch_blast", eye, dir, 9, 1.6);
        for (const t of cone(player, 10.0, 0.15)) {
          if (hit(player, t.entity, 22 * ctx.mult)) {
            bleed(t.entity);
            knockback(t.entity, t.dx, t.dz, 1.8, 0.5);
            fxScatter(player.dimension, "kaiju8:burst_slash", t.entity.location, 4, 1.0);
          }
        }
        sound(player.dimension, "random.explode", player.location,
              { pitch: 0.75, volume: 1.6 });
        shakeNearby(player.dimension, player.location, 18, 0.4, 0.55);
      } },
  ],

  // ---- 怪獣8号 ---------------------------------------------------------
  "kaiju8:no8_power": [
    { id: "fist", name: "kaiju8.tech.fist", cd: 40, energy: 6, form: true, canon: false,
      run(player, ctx) {
        const dir = player.getViewDirection();
        fx(player.dimension, "kaiju8:fist_shock", ahead(player, 2.0));
        fxLine(player.dimension, "kaiju8:energy_boost",
               player.getHeadLocation(), dir, 9, 1.2);
        let n = 0;
        for (const t of ray(player, 9, 2.4)) {
          if (hit(player, t.entity, 28 * ctx.mult)) {
            bleed(t.entity);
            knockback(t.entity, dir.x, dir.z, 2.4, 0.55);
            fxScatter(player.dimension, "kaiju8:crack_burst", t.entity.location, 6, 1.0);
            n++;
          }
        }
        sound(player.dimension, "mob.ravager.stun", player.location,
              { pitch: 0.55, volume: 1.6 });
        shakeNearby(player.dimension, player.location, 18, 0.44, 0.4);
        return n;
      } },
    { id: "boost", name: "kaiju8.tech.boost", cd: 40, energy: 4, form: true, canon: false,
      run(player) {
        dash(player, 2.6, 1.25);
        afterimages(player, 10);
        fxScatter(player.dimension, "kaiju8:energy_boost", player.location, 6, 0.9);
        sound(player.dimension, "mob.enderdragon.flap", player.location, { pitch: 0.7 });
        registerSlam(player, 1.0, "boost");
      } },
    { id: "energy_roar", name: "kaiju8.tech.energy_roar", cd: 140, energy: 14,
      form: true, charge: 12, canon: false,
      run(player, ctx) {
        fxScatter(player.dimension, "kaiju8:seam_glow", player.location, 10, 1.0);
        sound(player.dimension, "mob.enderdragon.growl", player.location,
              { pitch: 0.45, volume: 2.4 });
        later(12, () => {
          const dir = player.getViewDirection();
          const eye = player.getHeadLocation();
          fxLine(player.dimension, "kaiju8:energy_roar", eye, dir, 26, 1.0);
          for (const t of ray(player, 26, 3.0)) {
            if (hit(player, t.entity, 30 * ctx.mult)) {
              bleed(t.entity);
              knockback(t.entity, dir.x, dir.z, 2.0, 0.4);
            }
          }
          fx(player.dimension, "kaiju8:fist_shock", ahead(player, 3.0));
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 0.8, volume: 2.0 });
          shakeNearby(player.dimension, player.location, 26, 0.55, 0.9);
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
    fx(player.dimension, "kaiju8:shock_ring", g);
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
