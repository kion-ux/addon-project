// ===========================================================================
//  HUD（アクションバー、4 tick ごと）— DESIGN §2.5
//
//   [紋章] 形態名  Lv3  │ ⚡[星力バー 16 セル] 72  │ ✦[超新星バー 10 セル] 100%
//   [技アイコン] 1.2s  [技アイコン] ✔  [技アイコン] ✔  [必殺アイコン] READY
//
//  グリフは glyphs.js の G（gen_astro_ui が書き出す）。§ の色はグリフの絵には効かないので、
//  グリフの並びの前後には必ず §r を置き、§l をグリフの隣に付けない。
//  無いグリフは文字の代わり（色付きの | や ◆）に落とす。
//  2 行目は 解除の長押し／バリア／溜め（fx.status）の間は状態表示に差し替える。
//  変身していなくてもコアを持っていればコアの情報（星力・オーバーヒート・「右クリックで変身」）。
// ===========================================================================
import { COMMON, PLANETS, MOVE_LABEL, MOVE_KINDS, CORE_TO_PLANET } from "./data.js";
import {
  S, level, maxEnergy, cdLeft, isBusy, novaFull, settings,
} from "./state.js";
import { glyph, hudHeld, statusOf } from "./fx.js";
import { G } from "./glyphs.js";
import { comboStep } from "./combo.js";
import { heldItem, now, allPlayers, report } from "./util.js";

const SEP = " §8│ ";

/** グリフの組（無ければ文字の代わり）。 */
function cellSet(obj, fallbackColour) {
  const ok = obj && typeof obj.full === "string" && typeof obj.empty === "string";
  if (ok) return { glyph: true, full: obj.full, half: obj.half ?? obj.full, empty: obj.empty,
                   flow: obj.flow ?? obj.full, capL: obj.capL ?? "", capR: obj.capR ?? "" };
  return { glyph: false, full: `${fallbackColour}|`, half: `${fallbackColour}:`, empty: "§8|",
           flow: "§f|", capL: "§7[", capR: "§7]" };
}

function wrap(set, cells) {
  return `§r${set.capL}${cells}${set.capR}§r`;
}

/** 星力バー（16 セル）。20% 未満で赤く点滅。 */
export function energyBar(key, e, max) {
  const n = 16;
  const frac = Math.max(0, Math.min(1, e / Math.max(1, max)));
  let set = cellSet(G.energy?.[key], "§a");
  const low = frac < 0.2;
  const blink = low && Math.floor(now() / 6) % 2 === 0;
  if (low) {
    const warn = G.energy?.warn ?? G.energy?.low;
    if (warn) set = cellSet(warn, "§c");
    else if (!set.glyph) set = cellSet(null, "§c");
  }
  let s = "";
  for (let i = 0; i < n; i++) {
    const v = frac * n - i;
    let c = v >= 1 ? set.full : v >= 0.5 ? set.half : set.empty;
    if (blink && c !== set.empty) c = set.empty;   // 点滅: 残りのセルが一瞬消える
    s += c;
  }
  return wrap(set, s);
}

/** 超新星バー（10 セル）。満タンで光が流れる。 */
export function novaBar(v) {
  const n = 10;
  const set = cellSet(G.nova, "§6");
  const frac = Math.max(0, Math.min(1, v / COMMON.nova_max));
  let s = "";
  if (frac >= 1) {
    const phase = Math.floor(now() / 3) % (n + 3);
    for (let i = 0; i < n; i++) s += Math.abs(i - phase) <= 0 ? set.flow : set.full;
  } else {
    const k = Math.floor(frac * n + 1e-6);
    for (let i = 0; i < n; i++) s += i < k ? set.full : set.empty;
  }
  return wrap(set, s);
}

/** 進み具合のバー（解除の長押しなど。sync のグリフ）。 */
export function progressBar(frac, n = 10) {
  const set = cellSet(G.sync, "§b");
  const k = Math.round(Math.max(0, Math.min(1, frac)) * n);
  let s = "";
  for (let i = 0; i < n; i++) s += i < k ? set.full : set.empty;
  return wrap(set, s);
}

function moveIcon(key, kind, ready) {
  const g = G.move?.[key]?.[kind]?.[ready ? "ready" : "wait"];
  if (typeof g === "string") return `§r${g}§r`;
  return ready ? `§f${MOVE_LABEL[kind]}` : `§8${MOVE_LABEL[kind]}`;
}

function moveCell(p, key, kind) {
  const pl = PLANETS[key];
  if (kind === "ult") {
    const full = novaFull(p);
    const label = full ? (now() % 10 < 5 ? "§6READY" : "§eREADY") : `§7${Math.floor(S(p).nova)}%`;
    return `${moveIcon(key, kind, full)} ${label}`;
  }
  const left = cdLeft(p, key, kind);
  const cost = pl.moves[kind]?.cost ?? 0;
  if (left > 0) return `${moveIcon(key, kind, false)} §7${(left / 20).toFixed(1)}s`;
  if (cost > S(p).energy) return `${moveIcon(key, kind, false)} §c${cost}`;
  return `${moveIcon(key, kind, true)} §a✔`;
}

/** 変身中の 2 行。 */
export function hudTransformed(p) {
  const st = S(p);
  const key = st.form;
  const pl = PLANETS[key];
  const lv = level(p, key);
  const max = maxEnergy(p, key);
  const em = glyph(["emblem", key], pl.symbol);
  const parts = [
    `§r${em}§r ${pl.tc}${pl.form_ja}§r §7Lv${lv}`,
    `§r${glyph("icon.energy", "§e⚡")}§r${energyBar(key, st.energy, max)} §f${Math.floor(st.energy)}`,
    `§r${glyph("icon.nova", "§6✦")}§r${novaBar(st.nova)} §f${Math.floor(st.nova)}%`,
  ];
  const combo = comboStep(p);
  let line1 = parts.join(SEP);
  if (combo) line1 += ` §eCOMBO ${combo}`;
  let line2;
  const t = now();
  const custom = statusOf(p);
  if (st.revertHold > 0) {
    const frac = st.revertHold / COMMON.revert_hold_ticks;
    line2 = `§r${glyph("icon.revert", "§7⟲")}§r §f変身解除 ${progressBar(frac)} §7${Math.round(frac * 100)}%`;
  } else if (st.barrierUntil > t) {
    line2 = `§r${glyph("icon.barrier", "§b⬡")}§r ${pl.tc}ナノ・バリア §f${((st.barrierUntil - t) / 20).toFixed(1)}s`;
  } else if (custom) {
    line2 = custom;
  } else {
    line2 = MOVE_KINDS.map((k) => moveCell(p, key, k)).join("  ");
    if (isBusy(p)) line2 = `§7${line2}`;
  }
  return `${line1}\n${line2}`;
}

/** コアを持っている（変身していない）時の 2 行。 */
export function hudCore(p, key) {
  const st = S(p);
  const pl = PLANETS[key];
  const max = maxEnergy(p, key);
  const em = glyph(["emblem", key], pl.symbol);
  const line1 = `§r${em}§r ${pl.tc}${pl.core_ja}§r${SEP}§r${glyph("icon.energy", "§e⚡")}§r${energyBar(key, st.energy, max)} §f${Math.floor(st.energy)}/${max}`;
  let line2;
  if (st.overheat > 0) {
    line2 = `§r${glyph("icon.overheat", "§c♨")}§r §cオーバーヒート §f${(st.overheat / 20).toFixed(1)}s`;
  } else if (st.energy < COMMON.energy_to_transform) {
    line2 = `§c星力が足りない §7（変身に ${COMMON.energy_to_transform} 必要）`;
  } else {
    line2 = `§a右クリックで変身 §7同調率 Lv${level(p, key)}`;
  }
  return `${line1}\n${line2}`;
}

/** 1 人分の HUD を出す（4 tick ごと）。 */
export function showHud(p) {
  if (hudHeld(p)) return;
  const st = S(p);
  if (st.seq) return;                       // 変身の演出中はタイトルが主役
  if (settings(p).hud === false) return;
  let text;
  if (st.form) text = hudTransformed(p);
  else {
    const key = CORE_TO_PLANET[heldItem(p)?.typeId];
    if (!key) return;
    text = hudCore(p, key);
  }
  try { p.onScreenDisplay.setActionBar(text); } catch (_) { }
}

export function tickHud() {
  for (const p of allPlayers()) {
    try { showHud(p); } catch (e) { report("hud", e); }
  }
}
