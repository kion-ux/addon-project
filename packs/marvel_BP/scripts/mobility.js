// 移動 / magnetic flight, sight, barrier upkeep
//
// 磁気飛行は「視線の方向へ、ゆるやかに引かれ続ける」という実装にしている。
// 直接速度を書き換えるより、慣性が残って *乗っている* 感じが出る。
import { system } from "@minecraft/server";
import { PROP, FX, SOUND, MAG_MAX } from "./config.js";
import { allPlayers, forward, num, safe, setProp, str } from "./util.js";
import { fx, fxRing, selfPush, sound } from "./effects.js";
import { revealMetal } from "./magnetism.js";
import { isTransformed, magOf, spendMag } from "./transform.js";

let phase = 0;

/** 毎 2 tick: 飛行・磁力視・障壁の維持。 */
export function tickMobility() {
  phase++;
  for (const player of allPlayers()) {
    if (!isTransformed(player)) {
      if (num(player, PROP.flying, 0) === 1) setProp(player, PROP.flying, 0);
      continue;
    }

    // --- 磁気飛行 ---------------------------------------------------
    if (num(player, PROP.flying, 0) === 1) {
      if (magOf(player) <= 1) {
        setProp(player, PROP.flying, 0);
        sound(player.dimension, SOUND.revert, player.location, { pitch: 1.3 });
      } else {
        const dir = player.getViewDirection();
        const lift = safe(() => player.isSneaking) ? -0.22 : 0.16;
        selfPush(player, dir.x, dir.z, 0.62, lift + dir.y * 0.30);
        safe(() => player.addEffect("slow_falling", 20,
          { amplifier: 0, showParticles: false }));
        if (phase % 2 === 0) {
          fx(player.dimension, FX.flight_trail,
             { x: player.location.x, y: player.location.y + 0.2, z: player.location.z });
        }
        if (phase % 10 === 0) {
          spendMag(player, 0.6);
          fxRing(player.dimension, FX.mag_dust, player.location, 0.9, 5, 0.05);
        }
      }
    }

    // --- 磁力視 ------------------------------------------------------
    const sightUntil = num(player, PROP.sight, 0);
    if (sightUntil > system.currentTick) {
      if (phase % 10 === 0) revealMetal(player, 18);
    } else if (sightUntil !== 0) {
      setProp(player, PROP.sight, 0);
    }

    // --- 段階3のオーラ ------------------------------------------------
    if (phase % 6 === 0 && num(player, PROP.stage, 1) >= 3) {
      fx(player.dimension, FX.mag_aura_max,
         { x: player.location.x, y: player.location.y + 1.0, z: player.location.z });
    }
  }
}

/** 変身していない間もミュータントには僅かに磁力が漂う（存在感の演出）。 */
export function tickAmbient() {
  for (const player of allPlayers()) {
    if (isTransformed(player)) continue;
    if (num(player, PROP.mag, MAG_MAX) < MAG_MAX) {
      fx(player.dimension, FX.mag_dust,
         { x: player.location.x, y: player.location.y + 1.2, z: player.location.z });
    }
  }
}
