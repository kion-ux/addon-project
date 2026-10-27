// ===========================================================================
//  ui/welcome.js — 初めて入ったプレイヤーへ: 最初の持ち物・基本のパルクール技・あいさつ
//
//  壁走り・壁蹴り・ドロップキックはスキルの木の奥にあるが、このアドオンの看板なので
//  最初から使えるように、そこまでの前提ごと与える（ポイントは減らない）。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { STARTER_KIT } from "../data/settings.js";
import { grantSkill } from "../player/skills.js";
import { giveItems } from "./commands.js";

const WELCOMED = "nr:welcomed";
/** 最初から使えるパルクールの技（前提の順）。 */
export const STARTER_SKILLS = ["speed_vault", "wall_run", "wall_jump", "second_wind", "safe_roll", "slide_tackle", "dropkick"];

/** @param {import("@minecraft/server").Player} p */
export function welcome(p) {
  if (!p.isValid || p.getDynamicProperty(WELCOMED)) return false;
  p.setDynamicProperty(WELCOMED, true);
  giveItems(p, STARTER_KIT.map(([id, n]) => /** @type {[string, number]} */ ([id, n])));
  for (const k of STARTER_SKILLS) grantSkill(p, k);
  p.onScreenDisplay.setTitle("§4NIGHT RUNNER", { subtitle: "§7感染都市へようこそ", fadeInDuration: 10, stayDuration: 60, fadeOutDuration: 20 });
  p.sendMessage("§c§lNIGHT RUNNER: 感染都市§r — 走れ。斬れ。夜を生き延びろ。\n" +
    "§7壁に向かってジャンプ長押しで登る・ダッシュ中にスニークでスライディング・空中でスニーク＋攻撃でドロップキック。\n" +
    "§7コマンドの一覧は §e/scriptevent nr:help§7（チート ON のワールド）");
  return true;
}

world.afterEvents.playerSpawn.subscribe((ev) => {
  if (!ev.initialSpawn) return;
  const p = ev.player;
  system.runTimeout(() => { if (p.isValid) welcome(p); }, 40);
});
