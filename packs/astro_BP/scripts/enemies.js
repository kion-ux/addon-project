// ===========================================================================
//  侵略者とホログラム標的 — 最小版
//
//  TODO(enemies agent): ヴォイド・ドローン／センチネル／ネメシスの攻撃パターンをここに書く。
//  main.js はこのファイルの次の関数（フック）だけを呼ぶ。名前と引数は変えずに中身を差し替えること:
//    initEnemies()                         起動時に 1 回
//    tickEnemies(tick)                     毎 tick（重い処理は自分で間引く）
//    onEntitySpawn(entity)                 entitySpawn（astro: の敵・標的が現れた）
//    onEntityHurt(entity, damage, source)  entityHurt（source = damageSource）。true を返すとダメージ表示を出さない
//    onEntityDie(entity, source)           entityDie
//    summonTarget(player)                  /scriptevent astro:target
//    summonBoss(player)                    /scriptevent astro:boss と ヴォイド・シグナルの使用
//    useVoidSignal(player)                 astro:void_signal を使った（夜だけボスを呼ぶ等）
//    isEnemy(entity)                       侵略者か
// ===========================================================================
import { ENEMIES } from "./data.js";
import { P, sound, announce } from "./fx.js";
import { valid, health, now, flatDir, report, cmd } from "./util.js";

export const TYPES = {
  drone: "astro:void_drone",
  sentinel: "astro:void_sentinel",
  boss: "astro:nemesis",
  target: "astro:hologram_target",
  bolt: "astro:void_bolt",
};
const ENEMY_SET = new Set([TYPES.drone, TYPES.sentinel, TYPES.boss]);

export function isEnemy(e) {
  try { return ENEMY_SET.has(e.typeId); } catch (_) { return false; }
}

export function initEnemies() { }

// ---------------------------------------------------------------------------
//  ホログラム標的: 倒れない。直近 5 秒の合計と DPS を頭上に出す
// ---------------------------------------------------------------------------
const logs = new Map();   // entityId -> { e, log: [{t, d}] }
const WINDOW = 100;

function targetName(sum, dps) {
  const name = ENEMIES.hologram_target?.ja ?? "ホログラム標的";
  return `§b${name}\n§f5秒合計 §c${sum.toFixed(1)} §7| §fDPS §6${dps.toFixed(1)}`;
}

function targetHurt(e, dmg) {
  const t = now();
  const rec = logs.get(e.id) ?? { e, log: [] };
  rec.log = rec.log.filter((x) => t - x.t <= WINDOW);
  rec.log.push({ t, d: dmg });
  rec.e = e;
  logs.set(e.id, rec);
  const h = health(e);
  try { if (h) h.setCurrentValue(h.effectiveMax); } catch (_) { }
  const sum = rec.log.reduce((a, x) => a + x.d, 0);
  const span = Math.max(20, t - rec.log[0].t) / 20;
  try { e.nameTag = targetName(sum, sum / span); } catch (_) { }
  try { P(e.dimension, "hex", { x: e.location.x, y: e.location.y + 1.0, z: e.location.z }, { color: [0.4, 0.9, 1], size: 1.0, life: 0.2 }); } catch (_) { }
}

export function tickEnemies(tick) {
  if (tick % 10 !== 0 || !logs.size) return;
  const t = now();
  for (const [id, rec] of logs) {
    if (!valid(rec.e)) { logs.delete(id); continue; }
    rec.log = rec.log.filter((x) => t - x.t <= WINDOW);
    if (!rec.log.length) {
      try { rec.e.nameTag = targetName(0, 0); } catch (_) { }
      logs.delete(id);
    }
  }
}

export function onEntitySpawn(e) {
  try {
    if (e.typeId === TYPES.target) e.nameTag = targetName(0, 0);
  } catch (_) { }
}

/** true を返すと main はダメージ表示を出さない。 */
export function onEntityHurt(e, damage, source) {
  try {
    if (e.typeId === TYPES.target) { targetHurt(e, damage); return false; }
  } catch (err) { report("enemies.hurt", err); }
  return false;
}

export function onEntityDie(e, source) { }

function spawnInFront(p, type, d = 3) {
  const f = flatDir(p);
  const l = p.location;
  const at = { x: l.x + f.x * d, y: l.y, z: l.z + f.z * d };
  try { return p.dimension.spawnEntity(type, at); } catch (_) {
    cmd(p, `summon ${type} ^ ^ ^${d}`);
    return undefined;
  }
}

export function summonTarget(p) {
  const e = spawnInFront(p, TYPES.target, 3);
  if (e) onEntitySpawn(e);
  sound(p.dimension, "astro.ui_select", p.location, 1.0, 0.8);
  return e;
}

export function summonBoss(p) {
  const e = spawnInFront(p, TYPES.boss, 8);
  sound(p.dimension, "astro.nemesis_spawn", p.location, 1.0, 1.0);
  announce(p, "§5虚星王 ネメシス 降臨", 60);
  return e;
}

export function useVoidSignal(p) {
  return summonBoss(p);
}
