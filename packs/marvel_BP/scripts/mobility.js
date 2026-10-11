// 移動 / magnetic flight, sight, barrier upkeep
//
// 磁気飛行は「視線の方向へ、ゆるやかに引かれ続ける」という実装にしている。
// 直接速度を書き換えるより、慣性が残って *乗っている* 感じが出る。
//
// 一人称と三人称の作り分け（DIRECTION §6）
// ---------------------------------------
//   一人称 : fog と camera。視界の縁で動く圧。**カメラから 0.3〜2.5m に
//            通常合成の大きい粒を置かない** — 置くと視界が全部潰れる。
//   三人称 : 姿勢（pose の掛け直し）とマント後方の帯。輪郭と翻りで見せる。
// 拍は共有し、割り当てるチャンネルだけを変える。
//
// fog は **必ず pop する**。push しっぱなしはワールドを壊す。
// ここでは「今どの層を押しているか」を Set で持ち、状態が変わった
// 一度だけ push / pop する。毎 tick push すると層が積み上がって戻せなくなる。
import { system } from "@minecraft/server";
import { PROP, TECH, FX, SOUND, MAG_MAX } from "./config.js";
import { allPlayers, forward, normalise, num, safe, setProp } from "./util.js";
import { fog, fogPop, fx, fxRing, selfPush, sound } from "./effects.js";
import { revealMetal } from "./magnetism.js";
import { isTransformed, magOf, pose, spendMag, stageOf } from "./transform.js";

const FOG_FIELD = "marvel_field";
const FOG_SIGHT = "marvel_sight";

//: いま fog を押しているプレイヤー。二重 push を防ぐ。
const fogging = { field: new Set(), sight: new Set() };

let phase = 0;

function pushFog(player, layer, id, name) {
  if (fogging[layer].has(player.id)) return;
  fogging[layer].add(player.id);
  fog(player, id, name);
}

function popFog(player, layer, name) {
  if (!fogging[layer].has(player.id)) return;
  fogging[layer].delete(player.id);
  fogPop(player, name);
}

/** 変身解除・死亡・退出のときに必ず呼ぶ。押しっぱなしを残さない。 */
export function clearMobility(player) {
  popFog(player, "field", FOG_FIELD);
  popFog(player, "sight", FOG_SIGHT);
}

// ---------------------------------------------------------------- 磁気飛行
//: マント後方の帯 2 本（§5-5）。左右に振り分けると「飛んでいる」に見える。
function flightTrail(player) {
  const dir = player.getViewDirection();
  const side = normalise({ x: -dir.z, y: 0, z: dir.x });
  const back = forward(player.location, { x: -dir.x, y: 0, z: -dir.z }, 0.9);
  for (const off of [-0.42, 0.42]) {
    fx(player.dimension, FX.flight_trail, {
      x: back.x + side.x * off, y: back.y + 1.0, z: back.z + side.z * off,
    });
  }
}

function tickFlight(player) {
  if (magOf(player) <= 1) {
    setProp(player, PROP.flying, 0);
    popFog(player, "field", FOG_FIELD);
    sound(player.dimension, SOUND.revert, player.location, { pitch: 1.3 });
    return;
  }
  const dir = player.getViewDirection();
  const lift = safe(() => player.isSneaking) ? -0.22 : 0.16;
  selfPush(player, dir.x, dir.z, 0.62, lift + dir.y * 0.30);
  safe(() => player.addEffect("slow_falling", 20, { amplifier: 0, showParticles: false }));

  // 一人称: 紫の場の中にいる。三人称: 帯とマント。
  pushFog(player, "field", "marvel:field", FOG_FIELD);
  if (phase % 2 === 0) flightTrail(player);

  // 三人称の構えを保つ。飛行クリップは hold_on_last_frame なので、
  // 掛け直さないと 3 秒で普通の立ち姿に戻って「飛んでいる絵」が消える。
  if (phase % 8 === 0) pose(player, TECH.flight.form, 24);

  if (phase % 5 === 0) {
    // 維持コスト 0.9 / 10 tick（§7-2）。2 tick ごとの呼び出しなので 5 回に一度。
    spendMag(player, 0.9);
    fxRing(player.dimension, FX.mag_dust, player.location, 0.9, 5, 0.05);
  }
}

// ---------------------------------------------------------------- 毎 2 tick
export function tickMobility() {
  phase++;
  for (const player of allPlayers()) {
    if (!isTransformed(player)) {
      if (num(player, PROP.flying, 0) === 1) setProp(player, PROP.flying, 0);
      clearMobility(player);
      continue;
    }

    // --- 磁気飛行 ---------------------------------------------------
    if (num(player, PROP.flying, 0) === 1) {
      tickFlight(player);
    } else {
      popFog(player, "field", FOG_FIELD);
    }

    // --- 磁力視 ------------------------------------------------------
    const sightUntil = num(player, PROP.sight, 0);
    if (sightUntil > system.currentTick) {
      // 遠景を沈め、金属だけ浮かせる。ここが一人称の楽しさの中心。
      pushFog(player, "sight", "marvel:sight", FOG_SIGHT);
      // 走査は 1 秒に一度で足りる。毎 tick 撒くと画面が光の壁になる。
      // 半径は 18 ではなく **21**。scanMetal の間引き step は 20 を境に
      // 2 -> 4 へ落ちるので、21 のほうが広くて **5 分の 1 の走査回数** で済む
      // （実測 3,071 -> 597 回。19 秒間ずっと走る処理なのでここが効く）。
      if (phase % 10 === 0) revealMetal(player, 21);
    } else {
      popFog(player, "sight", FOG_SIGHT);
      if (sightUntil !== 0) setProp(player, PROP.sight, 0);
    }

    // --- 障壁の後始末 --------------------------------------------------
    //  展開そのものは techniques.js の interval が持つ。ここは
    //  死亡・変身解除で取り残された残り時間を落とすだけ。
    const barrierUntil = num(player, PROP.barrier, 0);
    if (barrierUntil !== 0 && barrierUntil <= system.currentTick) {
      setProp(player, PROP.barrier, 0);
    }

    // --- 段階 3 のオーラ ------------------------------------------------
    if (phase % 6 === 0 && stageOf(player) >= 3) {
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
