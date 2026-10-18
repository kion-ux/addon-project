// ===========================================================================
//  侵略者とホログラム標的 — main.js から呼ばれる窓口
//
//  中身は invaders.js（ヴォイド・ドローン／センチネル／虚星王ネメシスの行動と攻撃、ホログラム標的の
//  DPS 表示、ヴォイド・シグナルによる召喚）。main.js はこのファイルの次の関数だけを呼ぶ:
//    initEnemies()                         起動時に 1 回
//    tickEnemies(tick)                     毎 tick
//    onEntitySpawn(entity)                 entitySpawn
//    onEntityHurt(entity, damage, source)  entityHurt。true を返すとダメージ表示を出さない
//    onEntityDie(entity, source)           entityDie
//    summonTarget(player)                  /scriptevent astro:target
//    summonBoss(player)                    /scriptevent astro:boss（条件を無視して呼ぶ）
//    useVoidSignal(player)                 astro:void_signal を使った（夜の地上だけ）
//    isEnemy(entity)                       侵略者か
// ===========================================================================
import {
  INVADER, isInvader, onInvaderSpawn, tickInvaders, summonNemesis, summonHologram,
  onInvaderHurt, onInvaderDie, setInvaderDamageFilter,
} from "./invaders.js";
import { barrierActive, isDodging } from "./mobility.js";
import { valid, report } from "./util.js";

export const TYPES = {
  drone: INVADER.drone,
  sentinel: INVADER.sentinel,
  boss: INVADER.boss,
  target: INVADER.target,
  bolt: "astro:void_bolt",
};

export function isEnemy(e) {
  try { return isInvader(e); } catch (_) { return false; }
}

export function initEnemies() {
  // ナノ・バリアと回避ステップの無敵の間は、侵略者のスクリプト攻撃（レーザー・衝撃波・隕石）を受けない
  setInvaderDamageFilter((p) => {
    try {
      if (!valid(p) || p.typeId !== "minecraft:player") return undefined;
      if (barrierActive(p) || isDodging(p)) return false;
    } catch (e) { report("enemies.filter", e); }
    return undefined;
  });
}

export function tickEnemies() { tickInvaders(); }

export function onEntitySpawn(e) { onInvaderSpawn(e); }

/** true を返すと main はダメージ表示を出さない（侵略者・標的とも数字は出す）。 */
export function onEntityHurt(e, damage, source) {
  return onInvaderHurt(e, damage, source) === true;
}

export function onEntityDie(e, source) { onInvaderDie(e, source); }

export function summonTarget(p) { return summonHologram(p); }

export function summonBoss(p) { return summonNemesis(p, { force: true }); }

export function useVoidSignal(p) { return summonNemesis(p); }
