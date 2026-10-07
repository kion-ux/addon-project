// ===========================================================================
//  HUD（アクションバー）: 武器名・コンボ・超次元ゲージ・技の再使用・溜め／ガード
// ===========================================================================
import { GAUGE_MAX, MOVE_LABEL } from "./config.js";
import { gauge } from "./combat.js";
import { comboStep } from "./combo.js";
import { cdLeft, isBusy } from "./engine.js";
import { isDrawing, isGuarding } from "./hold.js";
import { now } from "./util.js";

function gaugeBar(g) {
  const n = 20;
  const filled = Math.round((g / GAUGE_MAX) * n);
  if (g >= GAUGE_MAX) {
    // 満タンは金と白が流れる
    const phase = Math.floor(now() / 4) % n;
    let s = "";
    for (let i = 0; i < n; i++) s += (Math.abs(i - phase) <= 1 ? "§f" : "§6") + "|";
    return s;
  }
  return "§b" + "|".repeat(filled) + "§8" + "|".repeat(n - filled);
}

function moveCell(player, w, kind) {
  const left = cdLeft(player, w, kind);
  const label = MOVE_LABEL[kind];
  if (kind === "ult") {
    return gauge(player) >= GAUGE_MAX
      ? (now() % 10 < 5 ? "§6§l必殺 READY" : "§e§l必殺 READY")
      : `§8${label} ✖`;
  }
  return left > 0 ? `§8${label} §7${(left / 20).toFixed(1)}s` : `§f${label} §a✔`;
}

export function hudFor(player, w) {
  const g = gauge(player);
  const combo = comboStep(player);
  const parts = [`${w.tc}§l◆${w.short}§r`];
  if (combo) parts.push(`§eCOMBO §l${combo}§r`);
  parts.push(`${gaugeBar(g)} §f${Math.floor(g)}%`);
  let line2;
  const d = isDrawing(player);
  const gd = isGuarding(player);
  if (d) {
    const age = now() - d.start;
    const lv = age >= 20 ? 2 : age >= 8 ? 1 : 0;
    line2 = `§e溜め ${"▰".repeat(lv + 1)}${"▱".repeat(2 - lv)} LV${lv}` +
      (lv === 2 ? " §6§lMAX" : "");
  } else if (gd) {
    const just = now() - gd.start < 6;
    line2 = `${w.tc}§lガード${just ? " §f§lJUST" : ""}§r §7吸収 §f${Math.round(gd.absorbed)}`;
  } else {
    line2 = ["skill", "dash", "air", "ult"].map((k) => moveCell(player, w, k)).join(" §8| ");
    if (isBusy(player)) line2 = `§7${line2}`;
  }
  return `${parts.join(" §8| ")}\n${line2}`;
}

const hold = new Map();   // playerId -> 他のメッセージを優先する期限

export function holdHud(player, ticks) { hold.set(player.id, now() + ticks); }

export function showHud(player, w) {
  if ((hold.get(player.id) ?? 0) > now()) return;
  try { player.onScreenDisplay.setActionBar(hudFor(player, w)); } catch (_) { }
}
