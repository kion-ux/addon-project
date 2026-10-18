// ===========================================================================
//  HUD（アクションバー、4 tick ごと）— DESIGN §2.5 / tools/astro/UI.md §3
//
//   [紋章] 形態名  Lv3  ／ ⚡[星力バー 16 セル] 72  ／ ✦[超新星バー 10 セル] 100%
//   [技アイコン] 1.2s  [技アイコン] ✔  [技アイコン] ✔  [必殺アイコン] READY
//
//  グリフは glyphs.js（gen_astro_ui が書き出す G と bar() などの関数）。関数があればそれを使い、
//  無ければ（古い・仮の glyphs.js）ここで同じ形を組む。G に無いキーは文字の代わり（色付きの | や ◆）。
//  § の色はグリフの絵には効かないので、グリフの並びの前後には §r を置き、§l をグリフの隣に付けない。
//  2 行目は 解除の長押し／バリア／溜め（fx.status）の間は状態表示に差し替える。
//  変身していなくてもコアを持っていればコアの情報（星力・オーバーヒート・「右クリックで変身」）。
// ===========================================================================
import * as GLY from "./glyphs.js";
import { COMMON, PLANETS, MOVE_LABEL, MOVE_KINDS, CORE_TO_PLANET } from "./data.js";
import {
  S, level, maxEnergy, cdLeft, isBusy, novaFull, settings,
} from "./state.js";
import { glyph, hudHeld, statusOf } from "./fx.js";
import { comboStep } from "./combo.js";
import { heldItem, now, allPlayers, report } from "./util.js";

const G = GLY.G ?? {};
const lib = (name) => (typeof GLY[name] === "function" ? GLY[name] : null);

function sep() {
  const s = G.icon?.sep;
  return typeof s === "string" ? ` §r${s}§r ` : " §8│§r ";
}

function ok() { return typeof G.icon?.check === "string" ? `§r${G.icon.check}§r` : "§a✔"; }

/** グリフの組（無ければ文字の代わり）。 */
function cellSet(obj, colour) {
  if (obj && typeof obj.full === "string" && typeof obj.empty === "string") {
    return { full: obj.full, half: obj.half, empty: obj.empty, flow: obj.flow ?? obj.full,
             capL: obj.capL ?? "", capR: obj.capR ?? "" };
  }
  return { full: `${colour}|`, half: `${colour}:`, empty: "§8|", flow: "§f|", capL: "§7[", capR: "§7]" };
}

/** glyphs.bar() と同じ規則（0 < frac なら最低半セル、frac < 1 なら最後のセルは空ける）。 */
function ownBar(set, frac, cells) {
  const f = Math.max(0, Math.min(1, frac));
  const step = set.half ? 0.5 : 1;
  let u = Math.round((f * cells) / step) * step;
  if (f > 0 && u <= 0) u = step;
  if (f < 1 && u >= cells) u = cells - step;
  let s = set.capL;
  for (let i = 0; i < cells; i++) s += u >= i + 1 ? set.full : (u >= i + 0.5 && set.half) ? set.half : set.empty;
  return s + set.capR;
}

function safe(fn, fallback) {
  try { const r = fn(); return typeof r === "string" ? r : fallback(); } catch (_) { return fallback(); }
}

/** 星力バー（16 セル）。20% 未満で赤と惑星色が点滅。 */
export function energyBar(key, e, max, cells = 16) {
  const frac = Math.max(0, Math.min(1, e / Math.max(1, max)));
  const f = lib("energyBar");
  const t = now();
  return `§r${safe(() => (f && G.energy?.[key] ? f(key, frac, cells, t) : null), () => {
    const low = frac < 0.2 && Math.floor(t / 8) % 2 === 0;
    const set = low ? cellSet(G.energyLow ?? G.energy?.low, "§c") : cellSet(G.energy?.[key], "§a");
    return ownBar(set, frac, cells);
  })}§r`;
}

/** 超新星バー（10 セル）。満タンで白熱のセルが流れる。 */
export function novaBar(v, cells = 10) {
  const frac = Math.max(0, Math.min(1, v / COMMON.nova_max));
  const f = lib("novaBar");
  const t = now();
  return `§r${safe(() => (f && G.nova ? f(frac, cells, t) : null), () => {
    const set = cellSet(G.nova, "§6");
    if (frac < 1) return ownBar(set, frac, cells);
    const head = Math.floor(t / 4) % (cells + 4);
    let s = set.capL;
    for (let i = 0; i < cells; i++) { const d = head - i; s += d >= 0 && d < 3 ? set.flow : set.full; }
    return s + set.capR;
  })}§r`;
}

/** 進み具合のバー（解除の長押し・CORE SYNC。G.progress = G.sync）。 */
export function progressBar(frac, cells = 20) {
  const f = lib("progressBar");
  return `§r${safe(() => (f && G.progress ? f(frac, cells) : null),
    () => ownBar(cellSet(G.progress ?? G.sync, "§b"), frac, cells))}§r`;
}

function moveIconText(key, kind, ready) {
  const f = lib("moveIcon");
  const g = safe(() => (f && G.move?.[key] ? f(key, kind, ready) : G.move?.[key]?.[kind]?.[ready ? "ready" : "wait"] ?? null), () => null);
  if (typeof g === "string" && g) return `§r${g}§r`;
  return ready ? `§f${MOVE_LABEL[kind]}` : `§8${MOVE_LABEL[kind]}`;
}

function moveCell(p, key, kind) {
  const pl = PLANETS[key];
  const st = S(p);
  if (kind === "ult") {
    const full = novaFull(p);
    const left = cdLeft(p, key, kind);
    // 再使用待ちの間はゲージが満タンでも残り時間（その間のスニーク＋右クリックはバリア）
    const tail = left > 0 ? `§7${(left / 20).toFixed(1)}s`
      : full ? (now() % 10 < 5 ? "§6READY" : "§eREADY") : `§7${Math.floor(st.nova)}%`;
    return `${moveIconText(key, kind, full && left <= 0)} ${tail}`;
  }
  const left = cdLeft(p, key, kind);
  const cost = pl.moves[kind]?.cost ?? 0;
  if (left > 0) return `${moveIconText(key, kind, false)} §7${(left / 20).toFixed(1)}s`;
  if (cost > st.energy) return `${moveIconText(key, kind, false)} §c${cost}`;
  return `${moveIconText(key, kind, true)} ${ok()}`;
}

/** 変身中の 2 行。 */
export function hudTransformed(p) {
  const st = S(p);
  const key = st.form;
  const pl = PLANETS[key];
  const lv = level(p, key);
  const max = maxEnergy(p, key);
  const em = glyph(["emblem", key], pl.symbol);
  const lowWarn = st.energy / max < 0.2 ? ` §r${glyph("icon.warn", "§c!")}§r` : "";
  let line1 = `§r${em}§r ${pl.tc}${pl.form_ja} §fLv${lv}` + sep() +
    `§r${glyph("icon.energy", "§e⚡")}${energyBar(key, st.energy, max)} §f${Math.floor(st.energy)}${lowWarn}` + sep() +
    `§r${glyph("icon.nova", "§6✦")}${novaBar(st.nova)} ${novaFull(p) ? "§e" : "§7"}${Math.floor(st.nova)}%`;
  const combo = comboStep(p);
  if (combo) line1 += ` §eCOMBO ${combo}`;
  let line2;
  const t = now();
  const custom = statusOf(p);
  if (st.revertHold > 0) {
    const frac = st.revertHold / COMMON.revert_hold_ticks;
    line2 = `§r${glyph("icon.revert", "§7⟲")}§r §c変身解除 ${progressBar(frac)} §f${Math.round(frac * 100)}%`;
  } else if (st.barrierUntil > t) {
    const frac = (st.barrierUntil - t) / COMMON.barrier_ticks;
    line2 = `§r${glyph("icon.barrier", "§b⬡")}§r §bナノ・バリア ${progressBar(frac, 10)}`;
  } else if (custom) {
    line2 = custom;
  } else {
    line2 = `§r${MOVE_KINDS.map((k) => moveCell(p, key, k)).join("  ")}`;
    if (isBusy(p)) line2 += " §7…";
  }
  return `${line1}\n${line2}`;
}

/** コアを持っている（変身していない）時の 2 行。 */
export function hudCore(p, key) {
  const st = S(p);
  const pl = PLANETS[key];
  const max = maxEnergy(p, key);
  const em = glyph(["emblem", key], pl.symbol);
  const line1 = `§r${em}§r ${pl.tc}${pl.core_ja}` + sep() +
    `§r${glyph("icon.energy", "§e⚡")}${energyBar(key, st.energy, max)} §f${Math.floor(st.energy)}/${max}`;
  let line2;
  if (st.overheat > 0) {
    line2 = `§r${glyph("icon.overheat", "§c♨")}§r §cオーバーヒート §f${(st.overheat / 20).toFixed(1)}s §r${glyph("icon.lock", "")}`;
  } else if (st.energy < COMMON.energy_to_transform) {
    line2 = `§c星力が足りない §7（変身に ${COMMON.energy_to_transform} 必要）`;
  } else {
    line2 = `§a右クリックで変身 §7同調率 Lv${level(p, key)}`;
  }
  return `${line1}\n${line2}`;
}

/** 1 人分の HUD を出す（4 tick ごと。アクションバーは 40 tick 以内に送り直さないと消える）。 */
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
