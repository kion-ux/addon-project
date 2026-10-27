// ===========================================================================
//  NIGHT RUNNER: 感染都市 — player/ の入口（main.js が import する）
//
//  パルクール（parkour.js）・スタミナ（stamina.js）・免疫（immunity.js）・HUD（hud.js）・経験値とスキル（skills.js）。
//  共通の部品（バスの名前・tick の登録・地形の判定）は common.js。感知（sense.js）はまだ無い。
//  各モジュールの最上位は subscribe・onBlockComponent・runInterval の登録だけ（world を触るのは worldLoad の後の tick の中）。
//  共通の API は tools/nightrunner/reference/nr_scripts.md（applyHit・バス・演出の包み・設定）。
//
//  他のフォルダとの約束（バス core/bus.js の名前。中身の形は common.js の PEV が正）:
//    聞く  "stamina_cost"     {player, amount, reason}            攻撃・投擲など（負は回復）
//          "weapon_state"     {player, id, key, name, kind, durability, broken, ammo, mag, magMax, reloading, mods}   HUD
//          "finisher"         {player, zombie, kind, result}      とどめ（コンボ「処刑」・経験値）
//          "immunity_restore" {player, seconds, source}           免疫を戻す
//          "uv_zone"          {dim, pos, radius, until, source}   UV の光の範囲（免疫が減らず戻る）
//          "grabbed"          {player, zombie}                    掴まれた → 動けない・もがく・連打
//          "grab_end"         {player, zombie?}                   ゾンビ側が離した
//          "xp"               {player, tree, amount, reason}      他のモジュールからの経験値（追跡を振り切った など）
//          "hud_notice"       {player, text, ticks?}              HUD の短い知らせ
//          EV.KILL / SEVER / DECAP / CRUSH / HEADSHOT / GUTTED / HALVED（経験値・コンボの見出し）
//    出す  "stamina"          {player, value, max, exhausted}     変わった時（combat の息切れ）
//          "shove"            {player, zombie, dir, presses, by}  連打で振りほどいた（zombies/ が離す）
//          "parkour"          {player, move, ...}                 技が決まった（vault / climb_block / wallrun / walljump / slide /
//                                                                 roll / hard_land / landing_pile / dropkick / grapple / glide_s / shove）
//          "level_up"         {player, tree, level, points}
//          "gore_combo"       {player, list: [{key, ja, en, xp, n}], xp, kills, night}
//          "immunity"         {player, value, max, kind: "warn" | "zero" | "restore" | "full", threshold?}
//          "noise"            {pos, radius, dim, source: "landing", player}   重い着地（zombies/noise.js）
//    保存（プレイヤーの動的プロパティ）: nr:skills（JSON {鍵: 1}）・nr:xp（JSON {parkour, combat}）・nr:immunity（秒）・
//          nr:stamina_bonus（数。最大スタミナの上乗せ。端末が書く）
//    デバッグ: /scriptevent nr:skill <鍵 | all | reset | list>、/scriptevent nr:xp <parkour | combat> <量>
// ===========================================================================
import "./common.js";
import "./skills.js";
import "./stamina.js";
import "./immunity.js";
import "./parkour.js";
import "./hud.js";

export { PEV, PT, onPlayerTick, onWorldTick, isActive, isNight } from "./common.js";
export {
  hasSkill, skillEff, skillNum, ownedSkills, canBuy, buySkill, grantSkill, resetSkills, addXp, xpOf, levelOf, pointsOf,
  levelFromXp, progressOf, parkourXp, TREES, MAX_LEVEL, SKILLS_KEY, XP_KEY,
} from "./skills.js";
export { consumeStamina, restoreStamina, setStamina, staminaOf, maxStamina, canAfford, isExhausted, boostRegen, STAMINA, STAMINA_BONUS_KEY } from "./stamina.js";
export { immunityOf, restoreImmunity, setImmunity, lightInfo, uvAt, immunityEnabled, IMMUNITY, IMMUNITY_KEY } from "./immunity.js";
export { parkourState, isGrabbed, grabInfo, grab, release, fireGrapple, toggleGlide, fallDamage, COST, SKILL_GATES, GRAB } from "./parkour.js";
export { composeHud, hudText, lastTitle, notice, popup, bar, fmtTime, hudEnabled, HUD } from "./hud.js";
