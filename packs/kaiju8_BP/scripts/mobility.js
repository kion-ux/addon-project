// 機動力 / mobility: 技の切り返し, 空中機動, 着地衝撃, オーラ
import { system } from "@minecraft/server";
import { PROP, RELEASE_SAFE } from "./config.js";
import { num, allPlayers, knockback } from "./util.js";
import { fx, fxScatter, sound, shakeNearby, targetsNear, hit, bleed } from "./effects.js";
import { container, selectedSlot, isTransformed } from "./transform.js";
import { listFor, cycle } from "./techniques.js";
import { cycleTechnique, releaseRate, wearsFullSuit } from "./weapons.js";
import { wornNumbers, activate } from "./numbers.js";

const sneakState = new Map();     // playerId -> was sneaking
const jumpState = new Map();      // playerId -> was holding jump
const airJump = new Map();        // playerId -> already used this airtime
const falling = new Map();        // playerId -> most negative y velocity seen

function heldTypeId(player) {
  try { return container(player)?.getItem(selectedSlot(player))?.typeId; }
  catch (_) { return undefined; }
}

/** Runs every 2 ticks. */
export function tickMobility() {
  for (const player of allPlayers()) {
    const id = player.id;
    const held = heldTypeId(player);
    const transformed = isTransformed(player);
    const suited = wearsFullSuit(player);
    const rate = releaseRate(player);

    // ---- 切り返し: sneak edge while holding a technique weapon -------
    const sneaking = !!player.isSneaking;
    const wasSneaking = sneakState.get(id) ?? false;
    sneakState.set(id, sneaking);
    const wheel = held ? listFor(player, held) : undefined;
    const canCycle = !!wheel && wheel.length > 1 &&
      (held !== "kaiju8:no8_power" || transformed);
    if (sneaking && !wasSneaking && canCycle) {
      // スニークで技を切り返す。ダッシュ中なら逆順に戻す
      cycle(player, held, player.isSprinting ? -1 : 1);
      cycleTechnique(player, held, undefined);
    }

    // ---- 空中機動 ----------------------------------------------------
    let vel = { x: 0, y: 0, z: 0 };
    try { vel = player.getVelocity(); } catch (_) { }
    const onGround = !!player.isOnGround;

    // ---- ナンバーズ能力: 地上でスニーク＋ジャンプ ----------------------
    const jumping = player.isJumping === true;
    const wasJumping = jumpState.get(id) ?? false;
    jumpState.set(id, jumping);
    const numbers = wornNumbers(player);
    if (numbers && sneaking && jumping && !wasJumping && onGround) {
      activate(player);
      continue;   // 同じ入力でジャンプ機動まで走らせない
    }

    if (onGround) {
      airJump.delete(id);
      const drop = falling.get(id) ?? 0;
      falling.delete(id);
      if (transformed && drop < -1.05) {
        heavyLanding(player, Math.min(3.0, -drop));
      }
    } else {
      falling.set(id, Math.min(falling.get(id) ?? 0, vel.y));
      const canAir = transformed || (suited && rate >= 25);
      if (canAir && !airJump.get(id) && player.isJumping === true && vel.y < 0.35) {
        airJump.set(id, true);
        const dir = player.getViewDirection();
        knockback(player, dir.x, dir.z, transformed ? 1.5 : 1.0,
                  transformed ? 0.85 : 0.62);
        fxScatter(player.dimension, "kaiju8:dash_dust", player.location, 8, 0.8);
        fx(player.dimension, "kaiju8:shock_ring",
           { x: player.location.x, y: player.location.y, z: player.location.z });
        sound(player.dimension, "mob.enderdragon.flap", player.location,
              { pitch: transformed ? 0.8 : 1.4, volume: 0.7 });
      }
    }

    // ---- 常時オーラ --------------------------------------------------
    if (transformed && system.currentTick % 6 === 0) {
      fx(player.dimension, "kaiju8:no8_aura",
         { x: player.location.x, y: player.location.y + 0.9, z: player.location.z });
    } else if (suited && rate > RELEASE_SAFE && system.currentTick % 10 === 0) {
      fx(player.dimension, "kaiju8:release_aura",
         { x: player.location.x, y: player.location.y + 0.8, z: player.location.z });
    }
  }
}

/** 怪獣の体で高所から落ちれば、地面のほうが負ける。 */
function heavyLanding(player, force) {
  const g = { x: player.location.x, y: player.location.y + 0.1, z: player.location.z };
  fx(player.dimension, "kaiju8:shock_ring", g);
  fxScatter(player.dimension, "kaiju8:heavy_land", g, Math.round(6 + force * 5), 1.6);
  fxScatter(player.dimension, "kaiju8:debris", g, Math.round(4 + force * 4), 1.2);
  sound(player.dimension, "random.explode", player.location,
        { pitch: 0.7, volume: Math.min(1.6, 0.6 + force * 0.4) });
  shakeNearby(player.dimension, player.location, 12, Math.min(0.45, force * 0.16), 0.4);
  const damage = Math.round(force * 6);
  if (damage <= 0) return;
  for (const t of targetsNear(player, 3.2 + force)) {
    const dx = t.location.x - player.location.x;
    const dz = t.location.z - player.location.z;
    const len = Math.hypot(dx, dz) || 1;
    if (hit(player, t, damage)) {
      bleed(t);
      knockback(t, dx / len, dz / len, 1.1, 0.45);
    }
  }
}

/** 戦闘服とその解放戦力ぶんの身体能力。 */
export function tickSuitBuffs() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    if (!wearsFullSuit(player)) continue;
    const rate = releaseRate(player);
    const speed = Math.min(2, Math.floor(rate / 30));
    try {
      player.addEffect("speed", 60, { amplifier: speed, showParticles: false });
      player.addEffect("jump_boost", 60, { amplifier: Math.min(2, Math.floor(rate / 40)),
                                           showParticles: false });
    } catch (_) { }
    if (rate >= 60) {
      try { player.addEffect("haste", 60, { amplifier: 1, showParticles: false }); }
      catch (_) { }
    }
  }
}
