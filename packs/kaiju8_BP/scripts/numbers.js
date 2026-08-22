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
  fx, fxRing, fxLine, fxScatter, sound, shake, shakeNearby, targetsNear, ray,
  cone, hit, bleed, later,
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
        // 全身のねじ穴から眼球が突出し、視界外の敵まで捉える
        run(player) {
          try {
            player.addEffect("speed", 240, { amplifier: 2, showParticles: true });
            player.addEffect("strength", 240, { amplifier: 1, showParticles: false });
            player.addEffect("night_vision", 400, { amplifier: 0, showParticles: false });
          } catch (_) { }
          for (const t of targetsNear(player, 32)) {
            if (!hasFamily(t, "kaiju")) continue;
            fxScatter(player.dimension, "kaiju8:regen_knit",
                      { x: t.location.x, y: t.location.y + 1.4, z: t.location.z }, 6, 0.8);
            try { t.addEffect("glowing", 240, { amplifier: 0, showParticles: false }); }
            catch (_) { }
          }
          fxRing(player.dimension, "kaiju8:release_burst", player.location, 2.0, 14, 0.8);
          sound(player.dimension, "beacon.power_select", player.location, { pitch: 1.4 });
          shake(player, 0.2, 0.5);
        } },
      { id: "inuki", name: "kaiju8.na.inuki", cd: 120,
        // 眼で捉えた一点を撃ち抜く
        run(player) {
          const target = nearestKaiju(player, 24);
          if (!target) return;
          const dir = {
            x: target.location.x - player.location.x,
            y: target.location.y - player.location.y,
            z: target.location.z - player.location.z,
          };
          const len = Math.hypot(dir.x, dir.y, dir.z) || 1;
          fxLine(player.dimension, "kaiju8:slash_scatter", player.getHeadLocation(),
                 { x: dir.x / len, y: dir.y / len, z: dir.z / len }, len, 1.4);
          if (hit(player, target, 42)) bleed(target);
          fxScatter(player.dimension, "kaiju8:socket_burst", target.location, 10, 1.0);
          sound(player.dimension, "mob.wither.shoot", player.location, { pitch: 1.5 });
          shakeNearby(player.dimension, target.location, 12, 0.3, 0.35);
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
        // 「メインバースト」— 拳から放つ指向性エネルギー弾＋ソニックブーム
        run(player) {
          const dir = player.getViewDirection();
          const eye = player.getHeadLocation();
          fx(player.dimension, "kaiju8:fist_shock", forward(eye, dir, 2.0));
          fxLine(player.dimension, "kaiju8:energy_boost", eye, dir, 20, 1.2);
          fxLine(player.dimension, "kaiju8:beam_impact", eye, dir, 20, 4.0);
          let n = 0;
          for (const t of ray(player, 20, 2.8)) {
            if (hit(player, t.entity, 40)) {
              bleed(t.entity);
              knockback(t.entity, dir.x, dir.z, 3.0, 0.7);
              n++;
            }
          }
          sound(player.dimension, "mob.wither.death", player.location,
                { pitch: 0.9, volume: 1.8 });
          shakeNearby(player.dimension, player.location, 22, 0.5, 0.6);
          if (n) fx(player.dimension, "kaiju8:core_break", forward(eye, dir, 4));
        } },
      { id: "impact", name: "kaiju8.na.impact", cd: 90,
        run(player) {
          const g = { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
          fx(player.dimension, "kaiju8:shock_ring_gold", g);
          fxScatter(player.dimension, "kaiju8:impact_dust", g, 14, 2.0);
          for (const t of targetsNear(player, 7.5)) {
            const dx = t.location.x - player.location.x;
            const dz = t.location.z - player.location.z;
            const len = Math.hypot(dx, dz) || 1;
            if (hit(player, t, 24)) {
              bleed(t);
              knockback(t, dx / len, dz / len, 2.4, 0.6);
            }
          }
          sound(player.dimension, "random.explode", player.location,
                { pitch: 0.6, volume: 1.6 });
          shakeNearby(player.dimension, player.location, 16, 0.42, 0.5);
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
        // ナンバーズ唯一の飛行能力
        run(player) {
          try {
            player.addEffect("levitation", 120, { amplifier: 2, showParticles: false });
            player.addEffect("slow_falling", 300, { amplifier: 0, showParticles: false });
            player.addEffect("speed", 300, { amplifier: 1, showParticles: false });
          } catch (_) { }
          fxScatter(player.dimension, "kaiju8:release_aura", player.location, 12, 1.2);
          fxRing(player.dimension, "kaiju8:release_burst", player.location, 1.6, 12, 0.6);
          sound(player.dimension, "mob.enderdragon.flap", player.location, { pitch: 1.2 });
        } },
      { id: "repulsor", name: "kaiju8.na.repulsor", cd: 100,
        run(player) {
          for (let i = 0; i < 5; i++) {
            later(i * 3, () => {
              shoot(player, "kaiju8:rifle_beam", 3.0, 0.08);
              fx(player.dimension, "kaiju8:muzzle_flash",
                 forward(player.getHeadLocation(), player.getViewDirection(), 1.0));
              sound(player.dimension, "random.explode", player.location,
                    { pitch: 1.5, volume: 0.6 });
            });
          }
          shake(player, 0.16, 0.6);
        } },
      { id: "launch", name: "kaiju8.na.launch", cd: 120,
        // 専用の電磁射出装置による超高速射出
        run(player) {
          const dir = player.getViewDirection();
          knockback(player, dir.x, dir.z, 4.6, 0.6);
          fxScatter(player.dimension, "kaiju8:dash_dust", player.location, 12, 1.2);
          for (let i = 0; i < 10; i++) {
            later(i * 2, () => {
              try {
                fx(player.dimension, "kaiju8:afterimage",
                   { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
                for (const t of targetsNear(player, 2.6)) {
                  if (hit(player, t, 12)) bleed(t);
                }
              } catch (_) { }
            });
          }
          sound(player.dimension, "beacon.activate", player.location, { pitch: 1.6 });
          shake(player, 0.24, 0.5);
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
        run(player) {
          shoot(player, "kaiju8:df_bullet", 3.0);
          later(3, () => {
            for (const t of ray(player, 26, 2.4)) {
              if (hit(player, t.entity, 14)) {
                bleed(t.entity);
                try {
                  t.entity.addEffect("slowness", 200, { amplifier: 4, showParticles: true });
                } catch (_) { }
                fxScatter(player.dimension, "kaiju8:socket_freeze",
                          t.entity.location, 10, 1.0);
              }
            }
            sound(player.dimension, "random.glass", player.location, { pitch: 1.2 });
          });
        } },
      { id: "absolute_zero", name: "kaiju8.na.absolute_zero", cd: 220,
        // 触れた箇所を瞬時に広範囲凍結させる
        run(player) {
          fxRing(player.dimension, "kaiju8:socket_freeze", player.location, 5.0, 20, 0.4);
          fx(player.dimension, "kaiju8:shock_ring", player.location);
          for (const t of targetsNear(player, 11)) {
            if (hit(player, t, 18)) bleed(t);
            try {
              t.addEffect("slowness", 320, { amplifier: 5, showParticles: true });
              t.addEffect("weakness", 320, { amplifier: 1, showParticles: false });
            } catch (_) { }
            fxScatter(player.dimension, "kaiju8:socket_freeze", t.location, 8, 1.0);
          }
          sound(player.dimension, "random.glass", player.location,
                { pitch: 0.7, volume: 1.6 });
          shakeNearby(player.dimension, player.location, 16, 0.32, 0.6);
        } },
      { id: "remote", name: "kaiju8.na.remote", cd: 140,
        // 分離式の小型遠隔兵器
        run(player) {
          const marks = targetsNear(player, 20).slice(0, 4);
          marks.forEach((t, i) => {
            later(i * 6, () => {
              try {
                fx(player.dimension, "kaiju8:beam_impact",
                   { x: t.location.x, y: t.location.y + 1.2, z: t.location.z });
                fxScatter(player.dimension, "kaiju8:socket_freeze", t.location, 8, 0.9);
                if (hit(player, t, 16)) bleed(t);
                t.addEffect("slowness", 180, { amplifier: 3, showParticles: true });
                sound(player.dimension, "random.glass", player.location, { pitch: 1.4 });
              } catch (_) { }
            });
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
        // 尾を第3の刃として振るう
        run(player) {
          fxRing(player.dimension, "kaiju8:slash_air", player.location, 3.6, 12, 1.0);
          for (const h of cone(player, 7.0, -0.35)) {
            if (hit(player, h.entity, 20)) {
              bleed(h.entity);
              knockback(h.entity, h.dx, h.dz, 1.4, 0.4);
            }
          }
          sound(player.dimension, "mob.ravager.bite", player.location, { pitch: 0.9 });
          shake(player, 0.2, 0.3);
        } },
      { id: "full_release", name: "kaiju8.na.full_release", cd: 400,
        // 全開放。解放戦力100%となり7式「十二単」が本領を発揮する
        run(player) {
          try {
            player.setDynamicProperty(RELEASE_UNTIL, system.currentTick + 400);
            player.addEffect("speed", 400, { amplifier: 2, showParticles: false });
            player.addEffect("strength", 400, { amplifier: 1, showParticles: false });
            player.addEffect("resistance", 400, { amplifier: 1, showParticles: false });
          } catch (_) { }
          fxRing(player.dimension, "kaiju8:release_aura", player.location, 1.8, 16, 0.8);
          fx(player.dimension, "kaiju8:shock_ring_gold", player.location);
          sound(player.dimension, "beacon.activate", player.location, { pitch: 0.8 });
          sound(player.dimension, "mob.enderdragon.growl", player.location,
                { pitch: 1.4, volume: 1.2 });
          shake(player, 0.34, 0.8);
          tell(player, tr("kaiju8.msg.full_release"));
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
