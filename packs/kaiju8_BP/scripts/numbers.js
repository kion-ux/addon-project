// ===========================================================================
//  識別怪獣兵器（ナンバーズ）
//  「持つ」武器ではなく「着る」武器。頭スロットに装備すると全身モデルが
//  差し替わり、常時能力に加えて機体ごとの固有能力が使えるようになる。
//
//  能力の発動: 地上で スニーク＋ジャンプ
//  能力の切替: 怪獣探知機の討伐隊端末 →「ナンバーズ能力」
// ===========================================================================
import { world, system, EquipmentSlot } from "@minecraft/server";
import {
  tr, tell, actionbar, allPlayers, knockback, hasFamily, distance, forward,
  onCooldown, setCooldown, cooldownLeft,
} from "./util.js";
import {
  fx, fxRing, fxLine, fxScatter, fxArc, fxSpiral, fxColumn, fxCone,
  sound, shake, shakeNearby, targetsNear, ray, cone, hit, bleed, later, trail,
} from "./effects.js";

const SEL = "kaiju8:numbers_select";
const RELEASE_UNTIL = "kaiju8:full_release_until";

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
  return proj;
}

function ground(player) {
  return { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
}

function chest(entity, y = 1.0) {
  return { x: entity.location.x, y: entity.location.y + y, z: entity.location.z };
}

function unit(from, to) {
  const d = { x: to.x - from.x, y: to.y - from.y, z: to.z - from.z };
  const L = Math.hypot(d.x, d.y, d.z) || 1;
  return { x: d.x / L, y: d.y / L, z: d.z / L, len: L };
}

function nearestKaiju(player, radius) {
  let best, bd = 1e9;
  for (const t of targetsNear(player, radius)) {
    const d = distance(player.location, t.location);
    if (d < bd) { bd = d; best = t; }
  }
  return best;
}

// ===========================================================================
//  機体ごとの能力
// ===========================================================================
export const NUMBERS = {
  // ---- ナンバーズ1 Rt-0001（鳴海弦）---------------------------------
  "kaiju8:numbers_1": {
    id: "1",
    tick(player) {
      try {
        player.addEffect("night_vision", 260, { amplifier: 0, showParticles: false });
        player.addEffect("speed", 60, { amplifier: 0, showParticles: false });
      } catch (_) { }
    },
    onHit(player, target) { hit(player, target, 4); },
    abilities: [
      { id: "kaigan", name: "kaiju8.na.kaigan", cd: 240,
        // 「開眼」— 全身のねじ穴から眼球が突出し、床を走査して一体ずつ捉える。
        // 対象を等間隔でロックしていくのはこの能力だけ。
        run(player) {
          fxRing(player.dimension, "kaiju8:eye_open", player.location, 0.9, 8, 1.1);
          fx(player.dimension, "kaiju8:eye_flash", player.getHeadLocation());
          sound(player.dimension, "mob.endermen.scream", player.location,
                { pitch: 0.55, volume: 0.7 });
          try {
            player.addEffect("speed", 240, { amplifier: 2, showParticles: true });
            player.addEffect("strength", 240, { amplifier: 1, showParticles: false });
            player.addEffect("night_vision", 400, { amplifier: 0, showParticles: false });
          } catch (_) { }
          later(2, () => {
            fxScatter(player.dimension, "kaiju8:eye_open", chest(player), 10, 0.8);
            shake(player, 0.12, 0.20);
          });
          later(4, () => {
            fxRing(player.dimension, "kaiju8:scan_grid", ground(player), 3.0, 16, 0.06);
            sound(player.dimension, "beacon.power_select", player.location,
                  { pitch: 1.9, volume: 0.55 });
          });
          const marks = targetsNear(player, 32).filter((t) => hasFamily(t, "kaiju"));
          marks.forEach((t, i) => {
            later(6 + i * 2, () => {
              try {
                fx(player.dimension, "kaiju8:lock_reticle", chest(t, 1.8));
                fxRing(player.dimension, "kaiju8:scan_grid", t.location, 1.2, 6, 0.06);
                t.addEffect("glowing", 240, { amplifier: 0, showParticles: false });
                sound(player.dimension, "random.click", player.location,
                      { pitch: 1.8, volume: 0.45 });
              } catch (_) { }
            });
          });
          later(6 + marks.length * 2, () => {
            fxColumn(player.dimension, "kaiju8:eye_flash", player.location, 2.4, 5, 0.25);
            shake(player, 0.18, 0.6);
          });
        } },
      { id: "inuki", name: "kaiju8.na.inuki", cd: 120,
        // 「射抜き」— 先に赤い照準線が張られ、それから抜く。
        // 血飛沫が敵の「向こう側」へ円錐で飛ぶのはこの能力だけ。
        run(player) {
          const target = nearestKaiju(player, 24);
          if (!target) return;
          const head = player.getHeadLocation();
          const dir = unit(head, chest(target, 1.0));
          fxLine(player.dimension, "kaiju8:aim_dot", head, dir, dir.len, 1.0);
          fx(player.dimension, "kaiju8:lock_reticle", chest(target, 1.6));
          sound(player.dimension, "random.click", player.location,
                { pitch: 0.5, volume: 0.55 });
          later(3, () => fxScatter(player.dimension, "kaiju8:eye_flash",
                                   forward(head, dir, 0.8), 4, 0.3));
          later(5, () => {
            fxLine(player.dimension, "kaiju8:pierce_lance", head, dir, dir.len, 0.6);
            if (!hit(player, target, 42)) return;
            bleed(target);
            const back = forward(target.location, dir, 2.5);
            fxScatter(player.dimension, "kaiju8:blood_splash",
                      { x: back.x, y: back.y + 1.0, z: back.z }, 10, 1.0);
            fxCone(player.dimension, "kaiju8:kaiju_blood", chest(target),
                   dir, 3.0, 0.35, 8);
            sound(player.dimension, "mob.wither.shoot", player.location,
                  { pitch: 1.9, volume: 1.4 });
            sound(player.dimension, "random.explode", player.location,
                  { pitch: 2.0, volume: 0.35 });
            later(2, () => {
              try {
                fx(player.dimension, "kaiju8:core_break", chest(target, 1.2));
                shakeNearby(player.dimension, target.location, 14, 0.34, 0.30);
              } catch (_) { }
            });
          });
        } },
    ],
  },

  // ---- ナンバーズ2 FS-1002（四ノ宮功）--------------------------------
  "kaiju8:numbers_2": {
    id: "2",
    tick(player) {
      try { player.addEffect("strength", 60, { amplifier: 1, showParticles: false }); }
      catch (_) { }
    },
    onHit(player, target) {
      fx(player.dimension, "kaiju8:fist_shock",
         { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
      for (const t of targetsNear(target, 3.4)) {
        if (t.id === target.id) continue;
        if (hit(player, t, 7)) bleed(t);
      }
      sound(player.dimension, "mob.ravager.stun", player.location,
            { pitch: 0.7, volume: 1.0 });
      shake(player, 0.14, 0.2);
    },
    abilities: [
      { id: "main_burst", name: "kaiju8.na.main_burst", cd: 120,
        // 「メインバースト」— 拳から放つ指向性エネルギー弾。
        // 直線ではなく螺旋にねじれ、射手自身が反動で後退する。
        run(player) {
          const eye = player.getHeadLocation();
          const dir = player.getViewDirection();
          const back = { x: -dir.x, y: -dir.y, z: -dir.z };
          fxScatter(player.dimension, "kaiju8:burst_charge",
                    forward(eye, back, 0.6), 8, 0.5);
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 0.5, volume: 0.9 });
          later(3, () => {
            fx(player.dimension, "kaiju8:detonation_gold", forward(eye, dir, 1.6));
            fxSpiral(player.dimension, "kaiju8:burst_core", eye, dir, 20, 2, 22, 0.55);
            fxCone(player.dimension, "kaiju8:sonic_wake", eye, dir, 20, 0.10, 14);
            let n = 0;
            for (const h of ray(player, 20, 2.8)) {
              if (!hit(player, h.entity, 40)) continue;
              bleed(h.entity);
              knockback(h.entity, dir.x, dir.z, 3.0, 0.7);
              n++;
            }
            sound(player.dimension, "mob.wither.death", player.location,
                  { pitch: 0.75, volume: 2.0 });
            sound(player.dimension, "mob.ravager.roar", player.location,
                  { pitch: 0.40, volume: 1.6 });
            shakeNearby(player.dimension, player.location, 24, 0.55, 0.7);
            if (n) fx(player.dimension, "kaiju8:core_break", forward(eye, dir, 4));
            later(1, () => {
              knockback(player, back.x, back.z, 0.9, 0.05);
              fxScatter(player.dimension, "kaiju8:burst_charge",
                        forward(eye, back, 1.0), 6, 0.7);
            });
            later(2, () => {
              for (const k of [0, 1, 2]) {
                fx(player.dimension, "kaiju8:quake_teal", forward(eye, dir, 3 + k * 4));
              }
            });
            later(5, () => fxScatter(player.dimension, "kaiju8:muzzle_smoke",
                                     forward(eye, dir, 2.0), 8, 1.2));
          });
        } },
      { id: "impact", name: "kaiju8.na.impact", cd: 90,
        // 「衝撃拳」— 内から外へ時間差で二段に広がる同心波と、四本の土柱。
        run(player) {
          fxColumn(player.dimension, "kaiju8:impact_wind", player.location, 2.2, 6, 0.3);
          sound(player.dimension, "mob.ravager.stun", player.location,
                { pitch: 0.50, volume: 0.8 });
          shake(player, 0.06, 0.15);
          later(3, () => {
            const g = ground(player);
            fx(player.dimension, "kaiju8:quake_dust", g);
            fxRing(player.dimension, "kaiju8:ground_fissure", g, 2.2, 10, 0.05);
            fxRing(player.dimension, "kaiju8:ground_fissure", g, 4.4, 14, 0.05);
            fxScatter(player.dimension, "kaiju8:debris", g, 14, 2.2);
            for (const a of [0, 90, 180, 270]) {
              const r = (a * Math.PI) / 180;
              fxColumn(player.dimension, "kaiju8:updraft",
                       { x: g.x + Math.cos(r) * 3.0, y: g.y, z: g.z + Math.sin(r) * 3.0 },
                       3.0, 6, 0.3);
            }
            for (const t of targetsNear(player, 7.5)) {
              const dx = t.location.x - g.x;
              const dz = t.location.z - g.z;
              const len = Math.hypot(dx, dz) || 1;
              if (!hit(player, t, 24)) continue;
              bleed(t);
              knockback(t, dx / len, dz / len, 2.4, 0.6);
            }
            sound(player.dimension, "random.explode", player.location,
                  { pitch: 0.50, volume: 2.0 });
            sound(player.dimension, "random.anvil_land", player.location,
                  { pitch: 0.40, volume: 1.2 });
            shakeNearby(player.dimension, g, 20, 0.50, 0.55);
            // 遅れて外側の帯だけを叩く二次波
            later(5, () => {
              fxRing(player.dimension, "kaiju8:ground_fissure", g, 6.6, 18, 0.05);
              for (const t of targetsNear(player, 12)) {
                const dx = t.location.x - g.x;
                const dz = t.location.z - g.z;
                const len = Math.hypot(dx, dz) || 1;
                if (len < 7.5) continue;
                if (!hit(player, t, 8)) continue;
                bleed(t);
                knockback(t, dx / len, dz / len, 1.2, 0.35);
              }
              sound(player.dimension, "random.explode", player.location,
                    { pitch: 0.35, volume: 1.0 });
              shakeNearby(player.dimension, g, 14, 0.22, 0.40);
            });
          });
        } },
    ],
  },

  // ---- ナンバーズ4（四ノ宮キコル）------------------------------------
  "kaiju8:numbers_4": {
    id: "4",
    tick(player) {
      try {
        player.addEffect("slow_falling", 60, { amplifier: 0, showParticles: false });
        player.addEffect("jump_boost", 60, { amplifier: 2, showParticles: false });
      } catch (_) { }
      let onGround = true;
      try { onGround = player.isOnGround; } catch (_) { }
      if (!onGround && system.currentTick % 6 === 0) {
        fxScatter(player.dimension, "kaiju8:release_aura", player.location, 4, 0.7);
      }
    },
    onHit(player, target) {
      fxScatter(player.dimension, "kaiju8:socket_burst", target.location, 6, 0.8);
      for (const t of targetsNear(target, 3.0)) if (hit(player, t, 6)) bleed(t);
      sound(player.dimension, "random.explode", player.location,
            { pitch: 1.4, volume: 0.7 });
    },
    abilities: [
      { id: "flight", name: "kaiju8.na.flight", cd: 200,
        // 「飛行」— ナンバーズ唯一の飛行能力。
        // 発動後ずっと足元から噴射炎が出続けるのはこの能力だけ。
        run(player) {
          try {
            player.addEffect("levitation", 120, { amplifier: 2, showParticles: false });
            player.addEffect("slow_falling", 300, { amplifier: 0, showParticles: false });
            player.addEffect("speed", 300, { amplifier: 1, showParticles: false });
          } catch (_) { }
          fxRing(player.dimension, "kaiju8:halo_sky", player.location, 1.1, 10, 0.15);
          fxColumn(player.dimension, "kaiju8:thrust_flame",
                   { x: player.location.x, y: player.location.y + 0.1,
                     z: player.location.z }, 1.2, 5, 0.15);
          sound(player.dimension, "mob.enderdragon.flap", player.location,
                { pitch: 1.5, volume: 0.7 });
          sound(player.dimension, "random.fizz", player.location,
                { pitch: 1.8, volume: 0.5 });
          later(2, () => {
            fxRing(player.dimension, "kaiju8:halo_sky", player.location, 1.6, 12, 0.9);
            shake(player, 0.16, 0.30);
          });
          for (let i = 0; i < 18; i++) {
            later(4 + i * 6, () => {
              try {
                fxScatter(player.dimension, "kaiju8:thrust_flame",
                          { x: player.location.x, y: player.location.y + 0.1,
                            z: player.location.z }, 3, 0.35);
                if (i % 3 === 0) {
                  fx(player.dimension, "kaiju8:spin_wind",
                     forward(chest(player), player.getViewDirection(), 1.2));
                }
                if (i % 6 === 0) {
                  sound(player.dimension, "mob.enderdragon.flap", player.location,
                        { pitch: 1.7, volume: 0.25 });
                }
              } catch (_) { }
            });
          }
          later(120, () => {
            try {
              fxRing(player.dimension, "kaiju8:halo_sky", player.location, 1.4, 12, 0.2);
              sound(player.dimension, "mob.enderdragon.flap", player.location,
                    { pitch: 0.9, volume: 0.8 });
            } catch (_) { }
          });
        } },
      { id: "repulsor", name: "kaiju8.na.repulsor", cd: 100,
        // 「リパルサー連射」— 7発。過熱で一発ごとに音程が下がり、
        // 撃ち終わりに排熱煙が出る。
        run(player) {
          const eye = player.getHeadLocation();
          const dir = player.getViewDirection();
          fxRing(player.dimension, "kaiju8:repulsor_iris",
                 forward(eye, dir, 1.0), 0.5, 8, 0);
          sound(player.dimension, "beacon.power_select", player.location,
                { pitch: 2.0, volume: 0.5 });
          for (let i = 0; i < 7; i++) {
            later(2 + i * 3, () => {
              const e = player.getHeadLocation();
              const d = player.getViewDirection();
              fx(player.dimension, "kaiju8:repulsor_iris", forward(e, d, 1.0));
              fxCone(player.dimension, "kaiju8:chevron_sky", e, d, 3.0, 0.06, 2);
              fxLine(player.dimension, "kaiju8:chevron_sky", e, d, 12, 1.5);
              shoot(player, "kaiju8:rifle_beam", 3.0, 0.05);
              sound(player.dimension, "mob.wither.shoot", player.location,
                    { pitch: 1.95 - i * 0.06, volume: 0.55 });
              shake(player, 0.06, 0.10);
            });
          }
          later(20, () => {
            const e = player.getHeadLocation();
            const d = player.getViewDirection();
            fx(player.dimension, "kaiju8:overheat_vent", forward(e, d, 0.8));
            fxScatter(player.dimension, "kaiju8:muzzle_smoke", forward(e, d, 0.8), 6, 0.6);
          });
          later(26, () => {
            fxScatter(player.dimension, "kaiju8:overheat_vent", chest(player), 8, 0.8);
            sound(player.dimension, "random.fizz", player.location,
                  { pitch: 1.2, volume: 0.6 });
          });
        } },
      { id: "launch", name: "kaiju8.na.launch", cd: 120,
        // 「電磁射出」— レールが展開してから射出される。
        // 飛んでいる間ずっと体に螺旋で電弧が絡み、掠めた時だけ音が鳴る。
        run(player) {
          const dir = player.getViewDirection();
          fxLine(player.dimension, "kaiju8:charge_arc_ice",
                 { x: player.location.x, y: player.location.y + 0.8, z: player.location.z },
                 dir, 3.0, 0.6);
          fxRing(player.dimension, "kaiju8:charge_arc_ice", player.location, 1.2, 8, 0.9);
          sound(player.dimension, "ambient.weather.thunder", player.location,
                { pitch: 2.0, volume: 0.5 });
          later(2, () => {
            const d = player.getViewDirection();
            knockback(player, d.x, d.z, 4.8, 0.55);
            fxScatter(player.dimension, "kaiju8:dash_dust", player.location, 12, 1.2);
            fx(player.dimension, "kaiju8:launch_bloom", chest(player, 0.9));
            sound(player.dimension, "beacon.activate", player.location,
                  { pitch: 2.0, volume: 1.2 });
            shake(player, 0.30, 0.25);
          });
          for (let i = 0; i < 10; i++) {
            later(2 + i * 2, () => {
              try {
                fx(player.dimension, "kaiju8:charge_arc_ice", chest(player, 0.9));
                fxSpiral(player.dimension, "kaiju8:charge_arc_ice", player.location,
                         player.getViewDirection(), 1.2, 1, 5, 0.7);
                if (i % 3 === 0) fx(player.dimension, "kaiju8:afterimage",
                                    chest(player, 0.9));
                for (const t of targetsNear(player, 2.6)) {
                  if (!hit(player, t, 12)) continue;
                  bleed(t);
                  fxScatter(player.dimension, "kaiju8:launch_bloom", t.location, 5, 0.7);
                  sound(player.dimension, "random.explode", player.location,
                        { pitch: 1.9, volume: 0.5 });
                }
              } catch (_) { }
            });
          }
          later(22, () => {
            fxScatter(player.dimension, "kaiju8:overheat_vent", chest(player), 6, 0.8);
            fxRing(player.dimension, "kaiju8:charge_arc_ice", player.location, 1.0, 6, 0.3);
            shake(player, 0.18, 0.25);
          });
        } },
    ],
  },

  // ---- ナンバーズ6 FN-0006（市川レノ）--------------------------------
  "kaiju8:numbers_6": {
    id: "6",
    tick(player) {
      try {
        player.addEffect("fire_resistance", 60, { amplifier: 0, showParticles: false });
      } catch (_) { }
    },
    onHit(player, target) {
      try {
        target.addEffect("slowness", 140, { amplifier: 3, showParticles: true });
        target.addEffect("weakness", 140, { amplifier: 0, showParticles: false });
      } catch (_) { }
      fxScatter(player.dimension, "kaiju8:socket_freeze",
                { x: target.location.x, y: target.location.y + 0.8, z: target.location.z },
                8, 0.9);
      sound(player.dimension, "random.glass", player.location, { pitch: 1.6 });
    },
    abilities: [
      { id: "ice_shot", name: "kaiju8.na.ice_shot", cd: 60,
        // 「氷結弾」— 霜の尾が段階的に伸びて「弾が飛んでいる時間」が見える。
        // 着弾は殻で閉じ込めてから崩す二段。
        run(player) {
          const eye = player.getHeadLocation();
          const dir = player.getViewDirection();
          fx(player.dimension, "kaiju8:muzzle_frost", forward(eye, dir, 1.0));
          fxScatter(player.dimension, "kaiju8:frost_mist", forward(eye, dir, 1.0), 5, 0.4);
          sound(player.dimension, "random.bow", player.location,
                { pitch: 0.6, volume: 0.9 });
          sound(player.dimension, "random.glass", player.location,
                { pitch: 2.0, volume: 0.35 });
          shoot(player, "kaiju8:df_bullet", 3.2);
          for (let i = 0; i < 4; i++) {
            later(1 + i, () => fxLine(player.dimension, "kaiju8:frost_trail",
                                      eye, dir, 6 + i * 6, 2.0));
          }
          later(4, () => {
            const struck = [];
            for (const h of ray(player, 26, 2.4)) {
              if (!hit(player, h.entity, 14)) continue;
              bleed(h.entity);
              struck.push(h.entity);
              try {
                h.entity.addEffect("slowness", 200, { amplifier: 4, showParticles: true });
              } catch (_) { }
              fx(player.dimension, "kaiju8:freeze_shell", chest(h.entity));
              fxScatter(player.dimension, "kaiju8:ice_shard", h.entity.location, 8, 0.9);
            }
            if (struck.length) {
              sound(player.dimension, "random.glass", player.location,
                    { pitch: 1.5, volume: 0.8 });
              shake(player, 0.08, 0.12);
            }
            later(4, () => {
              for (const t of struck) {
                try {
                  fxScatter(player.dimension, "kaiju8:ice_shard", t.location, 5, 1.1);
                } catch (_) { }
              }
              if (struck.length) {
                sound(player.dimension, "random.break", player.location,
                      { pitch: 1.8, volume: 0.5 });
              }
            });
          });
        } },
      { id: "absolute_zero", name: "kaiju8.na.absolute_zero", cd: 220,
        // 「絶対零度」— 接地点から外へ5波が伝播する。敵は距離順に凍り、
        // 波が外へ行くほど音程が上がるので広がりが耳で分かる。
        run(player) {
          const g = ground(player);
          fx(player.dimension, "kaiju8:halo_ice", g);
          sound(player.dimension, "random.glass", player.location,
                { pitch: 0.35, volume: 1.8 });
          sound(player.dimension, "mob.enderdragon.growl", player.location,
                { pitch: 2.0, volume: 0.5 });
          shake(player, 0.10, 1.4);
          const waves = [[0, 0, 1.6, 10], [3, 1.6, 3.2, 14], [6, 3.2, 4.8, 18],
                         [9, 4.8, 6.4, 22], [12, 6.4, 8.0, 26]];
          for (const [tick, inner, outer, pts] of waves) {
            later(tick, () => {
              fxRing(player.dimension, "kaiju8:frost_creep", g, outer, pts, 0.06);
              fxRing(player.dimension, "kaiju8:frost_mist", g, outer,
                     Math.round(pts / 2), 0.9);
              for (const t of targetsNear(player, outer + 1)) {
                const d = Math.hypot(t.location.x - g.x, t.location.z - g.z);
                if (d < inner || d > outer) continue;
                if (!hit(player, t, 18)) continue;
                bleed(t);
                try {
                  t.addEffect("slowness", 320, { amplifier: 5, showParticles: true });
                  t.addEffect("weakness", 320, { amplifier: 1, showParticles: false });
                } catch (_) { }
                fx(player.dimension, "kaiju8:freeze_shell", chest(t));
                fxColumn(player.dimension, "kaiju8:ice_spike", t.location, 2.6, 6, 0.3);
              }
              sound(player.dimension, "random.glass", player.location,
                    { pitch: 0.6 + tick * 0.05, volume: 0.8 });
            });
          }
          later(15, () => {
            fxColumn(player.dimension, "kaiju8:ice_spike", g, 3.4, 8, 0.5);
            fx(player.dimension, "kaiju8:shock_ring", g);
            sound(player.dimension, "random.break", player.location,
                  { pitch: 0.5, volume: 1.2 });
            shakeNearby(player.dimension, g, 16, 0.34, 0.5);
          });
        } },
      { id: "remote", name: "kaiju8.na.remote", cd: 140,
        // 「遠隔兵器」— 4基が肩から外れて展開し、照準リンクを同時に張ってから
        // 斉射する。プレイヤーから離れた4点が発射元になるのはこの能力だけ。
        run(player) {
          const marks = targetsNear(player, 20).slice(0, 4);
          fxRing(player.dimension, "kaiju8:chit_drone", player.location, 1.0, 4, 1.5);
          sound(player.dimension, "random.click", player.location,
                { pitch: 1.2, volume: 0.8 });
          if (!marks.length) return;
          const from = chest(player, 1.4);
          const pods = [];
          marks.forEach((t, i) => {
            later(2 + i * 2, () => {
              try {
                const d = unit(from, chest(t));
                fxLine(player.dimension, "kaiju8:chit_drone", from, d, 3.0, 1.0);
                sound(player.dimension, "random.click", player.location,
                      { pitch: 1.2 + i * 0.12, volume: 0.6 });
              } catch (_) { }
            });
          });
          later(10, () => {
            marks.forEach((t, i) => {
              try {
                const d = unit(from, chest(t));
                const pod = forward(from, d, 3.0);
                pods[i] = pod;
                fxLine(player.dimension, "kaiju8:drone_link", pod,
                       unit(pod, chest(t)), unit(pod, chest(t)).len, 1.2);
              } catch (_) { }
            });
            sound(player.dimension, "beacon.power_select", player.location,
                  { pitch: 1.9, volume: 0.5 });
          });
          marks.forEach((t, i) => {
            later(14 + i * 3, () => {
              try {
                const pod = pods[i] ?? from;
                const d = unit(pod, chest(t));
                fxLine(player.dimension, "kaiju8:drone_beam", pod, d, d.len, 1.4);
                fx(player.dimension, "kaiju8:drone_beam", chest(t, 1.2));
                if (hit(player, t, 16)) {
                  bleed(t);
                  t.addEffect("slowness", 180, { amplifier: 3, showParticles: true });
                }
                fxScatter(player.dimension, "kaiju8:ice_shard", t.location, 6, 0.8);
                sound(player.dimension, "mob.wither.shoot", player.location,
                      { pitch: 2.0, volume: 0.45 });
                shake(player, 0.05, 0.08);
              } catch (_) { }
            });
          });
          later(28, () => {
            for (const pod of pods) {
              if (!pod) continue;
              fxLine(player.dimension, "kaiju8:chit_drone", pod,
                     unit(pod, player.location), 3.0, 1.0);
            }
            sound(player.dimension, "random.click", player.location,
                  { pitch: 0.9, volume: 0.6 });
          });
        } },
    ],
  },

  // ---- ナンバーズ10（保科宗四郎）--------------------------------------
  "kaiju8:numbers_10": {
    id: "10",
    tick(player) {
      if (system.currentTick % 40 !== 0) return;
      const target = nearestKaiju(player, 6.0);
      if (!target) return;
      if (hit(player, target, 9)) bleed(target);
      fx(player.dimension, "kaiju8:slash_air",
         { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
      sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 1.5 });
    },
    onHit() { },
    abilities: [
      { id: "tail_strike", name: "kaiju8.na.tail_strike", cd: 70,
        // 「尾撃」— 半径と掃引角が段ごとに大きくなるので、尾がしなって
        // 伸びていくように見える。円ではなく「しなり」。
        run(player) {
          const dir = player.getViewDirection();
          const from = chest(player);
          fxArc(player.dimension, "kaiju8:cut_arc_green", from,
                { x: -dir.x, y: -dir.y, z: -dir.z }, 1.4, 60, 4, 0.2);
          sound(player.dimension, "mob.ravager.roar", player.location,
                { pitch: 1.9, volume: 0.4 });
          [[2, 2.0, 90, 7, -0.20], [3, 3.4, 130, 9, -0.05], [4, 4.8, 170, 11, 0.10]]
            .forEach(([tick, r, sweep, steps, tilt]) => {
              later(tick, () => fxArc(player.dimension, "kaiju8:cut_arc_green",
                                      chest(player), player.getViewDirection(),
                                      r, sweep, steps, tilt));
            });
          later(2, () => sound(player.dimension, "mob.ravager.bite", player.location,
                               { pitch: 0.65, volume: 1.2 }));
          later(4, () => {
            const d = player.getViewDirection();
            fx(player.dimension, "kaiju8:tail_edge",
               forward(chest(player), d, 4.4));
            for (const h of cone(player, 7.5, -0.35)) {
              if (!hit(player, h.entity, 20)) continue;
              bleed(h.entity);
              knockback(h.entity, h.dx, h.dz, 1.6, 0.35);
              fxScatter(player.dimension, "kaiju8:tail_edge", chest(h.entity), 3, 0.8);
            }
            sound(player.dimension, "item.trident.riptide_1", player.location,
                  { pitch: 0.70, volume: 0.8 });
            shake(player, 0.22, 0.28);
            shakeNearby(player.dimension, player.location, 10, 0.20, 0.25);
          });
          later(5, () => fxCone(player.dimension, "kaiju8:tail_gust", chest(player),
                                player.getViewDirection(), 6.0, 0.35, 10));
          later(6, () => fxArc(player.dimension, "kaiju8:cut_arc_green", chest(player),
                               player.getViewDirection(), 2.4, 70, 5, 0.6));
        } },
      { id: "full_release", name: "kaiju8.na.full_release", cd: 400,
        // 「全開放」— 吸気 → 見得(光柱) → 解放 の三段起動。
        // 400tick のあいだ解放戦力100%が固定され、7式「十二単」が解禁される。
        run(player) {
          fxScatter(player.dimension, "kaiju8:release_intake", chest(player), 12, 1.6);
          sound(player.dimension, "mob.enderdragon.growl", player.location,
                { pitch: 1.7, volume: 0.8 });
          shake(player, 0.08, 0.5);
          later(6, () => {
            fxColumn(player.dimension, "kaiju8:release_pillar", player.location,
                     4.0, 10, 0.35);
            sound(player.dimension, "beacon.activate", player.location,
                  { pitch: 0.55, volume: 1.6 });
          });
          later(10, () => {
            try {
              player.setDynamicProperty(RELEASE_UNTIL, system.currentTick + 400);
              player.addEffect("speed", 400, { amplifier: 2, showParticles: false });
              player.addEffect("strength", 400, { amplifier: 1, showParticles: false });
              player.addEffect("resistance", 400, { amplifier: 1, showParticles: false });
            } catch (_) { }
            [[0, 1.2, 12], [1, 3.0, 16], [2, 5.0, 20]].forEach(([d, r, pts]) => {
              later(d, () => fxRing(player.dimension, "kaiju8:quake_green",
                                    player.location, r, pts, 0.10));
            });
            fxScatter(player.dimension, "kaiju8:release_ember", player.location, 16, 1.8);
            sound(player.dimension, "mob.enderdragon.growl", player.location,
                  { pitch: 0.50, volume: 2.4 });
            sound(player.dimension, "random.explode", player.location,
                  { pitch: 0.45, volume: 1.4 });
            shakeNearby(player.dimension, player.location, 24, 0.50, 0.9);
            tell(player, tr("kaiju8.msg.full_release"));
          });
          later(400, () => {
            try {
              fxScatter(player.dimension, "kaiju8:release_intake", player.location, 8, 1.2);
              sound(player.dimension, "beacon.deactivate", player.location,
                    { pitch: 0.8, volume: 1.0 });
            } catch (_) { }
          });
        } },
    ],
  },
};

const worn = new Map();

export function wornNumbers(player) {
  try {
    const eq = player.getComponent("minecraft:equippable");
    const id = eq?.getEquipment(EquipmentSlot.Head)?.typeId;
    return id && NUMBERS[id] ? id : undefined;
  } catch (_) { return undefined; }
}

export function liftsReleaseCap(player) {
  return wornNumbers(player) !== undefined;
}

/** 全開放中は解放戦力が100%に固定される。 */
export function fullReleaseActive(player) {
  try {
    const until = player.getDynamicProperty(RELEASE_UNTIL);
    return typeof until === "number" && system.currentTick < until;
  } catch (_) { return false; }
}

// --- 能力の選択 -------------------------------------------------------
function readSel(player) {
  try {
    const raw = player.getDynamicProperty(SEL);
    if (typeof raw === "string" && raw) return JSON.parse(raw);
  } catch (_) { }
  return {};
}

export function abilityIndex(player, id) {
  const list = NUMBERS[id]?.abilities ?? [];
  if (!list.length) return 0;
  const map = readSel(player);
  return ((map[id] ?? 0) % list.length + list.length) % list.length;
}

export function selectedAbility(player, id) {
  const list = NUMBERS[id]?.abilities ?? [];
  return list[abilityIndex(player, id)];
}

export function setAbility(player, id, index) {
  const list = NUMBERS[id]?.abilities ?? [];
  if (!list.length) return undefined;
  const next = ((Math.round(index) % list.length) + list.length) % list.length;
  const map = readSel(player);
  map[id] = next;
  try { player.setDynamicProperty(SEL, JSON.stringify(map)); } catch (_) { }
  return list[next];
}

/** 能力 id を指定して選ぶ。技ホイールから呼ばれる。 */
export function setAbilityById(player, id, abilityId) {
  const list = NUMBERS[id]?.abilities ?? [];
  const at = list.findIndex((a) => a.id === abilityId);
  return at < 0 ? undefined : setAbility(player, id, at);
}

export function cycleAbility(player, id, step = 1) {
  const list = NUMBERS[id]?.abilities ?? [];
  if (list.length < 2) return undefined;
  return setAbility(player, id, abilityIndex(player, id) + step);
}

/** 残りクールダウン（秒）。端末の表示用。 */
export function abilityCooldown(player) {
  return Math.ceil(cooldownLeft(player.id, "numbers") / 20);
}

/** 地上でスニーク＋ジャンプ。mobility から呼ばれる。 */
export function activate(player) {
  const id = wornNumbers(player);
  if (!id) return false;
  const ability = selectedAbility(player, id);
  if (!ability) return false;
  if (onCooldown(player.id, "numbers")) {
    sound(player.dimension, "note.bass", player.location, { pitch: 0.6, volume: 0.4 });
    return true;
  }
  setCooldown(player.id, "numbers", ability.cd);
  try { ability.run(player); } catch (_) { }
  actionbar(player, {
    rawtext: [{ text: "§b" }, { translate: ability.name },
              { text: "  §7" }, { translate: `item.${id}` }],
  });
  return true;
}

export function tickNumbers() {
  for (const player of allPlayers()) {
    const id = wornNumbers(player);
    const before = worn.get(player.id);
    if (id !== before) {
      if (id) {
        worn.set(player.id, id);
        tell(player, {
          rawtext: [{
            translate: "kaiju8.msg.numbers_on",
            with: { rawtext: [{ translate: `item.${id}` }] },
          }],
        });
        tell(player, tr(`kaiju8.numbers.${NUMBERS[id].id}`));
        tell(player, tr("kaiju8.msg.numbers_hint"));
        sound(player.dimension, "beacon.activate", player.location, { pitch: 1.2 });
        fxRing(player.dimension, "kaiju8:release_burst", player.location, 1.4, 10, 0.6);
        shake(player, 0.22, 0.4);
      } else {
        worn.delete(player.id);
        tell(player, tr("kaiju8.msg.numbers_off"));
      }
    }
    if (!id) continue;
    try { NUMBERS[id].tick(player); } catch (_) { }
  }
}

world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  const target = ev.hitEntity;
  if (!target) return;
  const id = wornNumbers(player);
  if (!id) return;
  system.run(() => {
    try { NUMBERS[id].onHit(player, target); } catch (_) { }
  });
});
