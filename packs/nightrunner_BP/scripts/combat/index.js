// ===========================================================================
//  NIGHT RUNNER: 感染都市 — combat/ の入口（main.js が import する）
//
//  近接・飛び道具・投擲・改造・耐久・とどめ。各モジュールは import の時に subscribe と
//  onItemComponent("nr:weapon") / setMeleeResolver / setProjectileResolver を登録するだけ
//  （world を触るのは worldLoad の後の tick の中）。ゾンビへのダメージは全部 gore/gore.js の applyHit。
//
//  他のフォルダとの約束（バス core/bus.js の名前。中身の形）:
//    出す  "stamina_cost"   {player, amount, reason}        攻撃・投擲・溜め攻撃のスタミナ（負 = 回復: 処刑）。reason は
//                           melee / power_attack / heavy / stomp / bash（銃床）/ throw / bow / crossbow / finisher
//          "noise"          {pos, radius, dim, source, player?}   銃声・爆発・近接・爆竹・パイプ爆弾のビープ
//          "weapon_state"   {player, id, key, name, kind, durability(0..1 / -1), broken, ammo(-1 = 無し),
//                            mag(-1 = 無し), magMax, reloading, mods}   手の武器が変わった・撃った・減った時（HUD）
//          "finisher"       {player, zombie, kind: "stomp" | "decap", result}   とどめ（HUD のコンボ「処刑」）
//          "immunity_restore" {player, seconds, source}     UV の改造で仕留めた・UV 発煙筒の光の中
//          "uv_zone" / "fire_zone" / "lure"  {dim, pos, radius, until, …}   投げ物の範囲（AI・追跡）
//          "hud_notice"     {player, text, ticks}            短い知らせ（壊れた・弾が無い…。聞く者が無ければアクションバーへ直接）
//    聞く  "stamina"        {player, value, max, exhausted?}   player/stamina.js が出す（息切れ = 遅く弱い攻撃）
//    差し込み口: setSkillQuery(fn(player, key) → bool)（無ければプレイヤーの動的プロパティ nr:skills の JSON）、
//               setStaminaQuery(fn(player) → {value, max, exhausted?})。
//    端末（ui/）: canApplyMod / applyMod / removeMod / modsFor（改造）、repair（修理）。
// ===========================================================================
import "./common.js";
import "./durability.js";
import "./mods.js";
import "./finishers.js";
import "./melee.js";
import "./ranged.js";
import "./throwables.js";

export {
  CEV, weaponOf, heldInfo, weaponState, publishWeaponState, setSkillQuery, hasSkill, skillEff, setStaminaQuery,
  isExhausted, readMods, refreshLore, notify,
} from "./common.js";
export { durabilityOf, isBroken, brokenMult, wear, repair, DUR } from "./durability.js";
export { MOD_KEYS, modTier, effectiveMods, modDamageMult, canApplyMod, applyMod, removeMod, writeMods, startDot, dotsOn, modsFor, onModHit } from "./mods.js";
export { canStomp, stompHit, canExecute, decapHit } from "./finishers.js";
export { resolveMelee, weaponHit, bashHit, swingOf, heavyAttack, strike, groundSlam, afterMeleeHit, cooldownTicks, HEAVY } from "./melee.js";
export { fireGun, hitscan, startReload, cancelReload, isReloading, isScoped, magOf, fireProjectile, launch, resolveProjectileHit, drawFraction } from "./ranged.js";
export { throwHeld, explode, activeZones, flyingCount } from "./throwables.js";
