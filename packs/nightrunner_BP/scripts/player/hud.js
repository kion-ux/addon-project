// ===========================================================================
//  NIGHT RUNNER: 感染都市 — HUD（DESIGN §7。今は素の Unicode。独自グリフ RP font/glyph_XX.png は後で）
//
//  * アクションバー 1 行: 体力 ❤・スタミナ ⚡（■□ の棒。息切れは赤く点滅）・免疫 ☣ 残り m:ss（暗がり・UV・
//    減っている間だけ。▼ 減っている / ▲ 戻っている / ‖ 止まっている）・手の武器（バス "weapon_state": 名前・耐久・弾・装填中）。
//    掴まれている間は「振りほどけ」の連打の棒に替わる。短い知らせ（バス "hud_notice" / notice()）は後ろに付く。
//  * ちらつかせない: EVERY tick ごとに組み立て、文が変わった時か KEEPALIVE tick たった時だけ出し直す。
//  * 見出し（setTitle）: ゴアのコンボ（バス "gore_combo"。skills.js が 1 tick 分をまとめたもの。名前は
//    data/settings.js の GORE_COMBOS）と効果音（nr.ui.headshot / nr.ui.combo）、レベルアップ、免疫の 0・10 秒。
//    優先度の低い見出しは、高いものが出ている間は出さない。
//  * 設定 hud_enabled が false なら何も出さない。クリエイティブ・スペクテイターにも出さない。
// ===========================================================================
import { on } from "../core/bus.js";
import { valid, now } from "../core/util.js";
import { playerSound } from "../core/fx.js";
import { get as setting } from "../core/settings.js";
import { PEV, playerMap, onPlayerTick, isActive, healthOf } from "./common.js";
import { staminaOf } from "./stamina.js";
import { immunityOf, immunityEnabled } from "./immunity.js";
import { grabInfo } from "./parkour.js";

/** @typedef {import("@minecraft/server").Player} Player */

export const HUD = Object.freeze({ every: 4, keepAlive: 40, noticeTicks: 50, titleStay: 18 });
const SEP = " §8|§r ";

/** 見出しの色（GORE_COMBOS の鍵）。 @type {Record<string, string>} */
const COMBO_COLOR = {
  headshot: "§6", decapitated: "§4", skull_crush: "§4", dismember: "§c", gutted: "§2", bisected: "§5",
  overkill: "§5", finisher: "§4", multi_kill: "§e", environment: "§3",
};

/**
 * @typedef {{text: string, sentT: number, weapon: any, notice: string, noticeUntil: number, titleUntil: number, titlePrio: number,
 *   title: string, subtitle: string, hidden: boolean}} HState
 */
/** @type {Map<string, HState>} */
const states = playerMap();
/** @param {Player} p @returns {HState} */
function hst(p) {
  let s = states.get(p.id);
  if (!s) { s = { text: "", sentT: -9999, weapon: undefined, notice: "", noticeUntil: -1, titleUntil: -1, titlePrio: 0, title: "", subtitle: "", hidden: false }; states.set(p.id, s); }
  return s;
}

/** HUD が有効か（設定）。 */
export function hudEnabled() { return setting("hud_enabled") !== false; }

/**
 * 割合の棒（width 文字）。 @param {number} frac 0..1 @param {number} width @param {string} [full] @param {string} [empty]
 */
export function bar(frac, width, full = "■", empty = "□") {
  const f = Number.isFinite(frac) ? Math.min(1, Math.max(0, frac)) : 0;
  const n = Math.round(f * width);
  return full.repeat(n) + empty.repeat(Math.max(0, width - n));
}
/** 秒 → m:ss。 @param {number} sec */
export function fmtTime(sec) {
  const s = Math.max(0, Math.ceil(Number.isFinite(sec) ? sec : 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
/** 耐久の色。 @param {number} d 0..1 */
function durColor(d) { return d > 0.5 ? "§a" : d > 0.2 ? "§e" : "§c"; }

/**
 * アクションバーの文を組み立てる（出さない）。
 * @param {Player} p @param {number} [t]
 */
export function composeHud(p, t = now()) {
  const hs = hst(p);
  const g = grabInfo(p);
  if (g) return `§c§l! 振りほどけ !§r §f[ジャンプ・攻撃 連打] §e${bar(g.presses / Math.max(1, g.need), 8)}`;
  /** @type {string[]} */
  const parts = [];
  const h = healthOf(p);
  parts.push(`§c❤ ${Math.ceil(h.cur)}§7/${Math.round(h.max)}`);
  const s = staminaOf(p);
  const blink = Math.floor(t / 8) % 2 === 0;
  const sc = s.exhausted ? (blink ? "§c" : "§4") : s.value / s.max < 0.3 ? "§6" : "§e";
  parts.push(`${sc}⚡ ${bar(s.value / s.max, 10)}`);
  if (immunityEnabled()) {
    const im = immunityOf(p);
    if (im.draining || im.uv || im.dark || im.value < im.max - 0.01) {
      const col = im.value <= 0 ? (blink ? "§4" : "§c") : im.value <= 10 ? "§c" : im.value <= 30 ? "§6" : im.uv ? "§b" : "§d";
      const arrow = im.draining ? " §5▼" : (im.uv || im.sun) && im.value < im.max ? " §b▲" : im.paused && im.dark ? " §a‖" : "";
      parts.push(`${col}☣ ${fmtTime(im.value)}${arrow}`);
    }
  }
  const w = hs.weapon;
  if (w && w.name) {
    let ws = `§f${w.name}`;
    if (w.broken) ws += " §c破損";
    else if (Number(w.durability) >= 0) ws += ` ${durColor(w.durability)}${Math.round(w.durability * 100)}%`;
    if (Number(w.mag) >= 0) ws += ` §f${w.mag}§7/${Number(w.ammo) >= 0 ? w.ammo : w.magMax}`;
    else if (Number(w.ammo) >= 0) ws += ` §7×${w.ammo}`;
    if (w.reloading) ws += " §e装填中";
    parts.push(ws);
  }
  if (hs.notice && t < hs.noticeUntil) parts.push(hs.notice);
  return parts.join(SEP);
}

/** 最後に出したアクションバーの文（テスト・デバッグ）。 @param {Player} p */
export function hudText(p) { return valid(p) ? hst(p).text : ""; }
/** 最後に出した見出し {title, subtitle, until}。 @param {Player} p */
export function lastTitle(p) { const s = hst(p); return { title: s.title, subtitle: s.subtitle, until: s.titleUntil }; }

/** アクションバーに短い知らせを付ける。 @param {Player} p @param {string} text @param {number} [ticks] */
export function notice(p, text, ticks = HUD.noticeTicks) {
  if (!valid(p)) return;
  const s = hst(p);
  s.notice = String(text ?? "");
  s.noticeUntil = now() + Math.max(1, Math.floor(ticks));
  refresh(p, true);
}

/**
 * 見出しを出す（優先度の高いものが出ている間は低いものを出さない）。出したら true。
 * @param {Player} p @param {string} title @param {string} [subtitle]
 * @param {{prio?: number, stay?: number, sound?: string}} [o]
 */
export function popup(p, title, subtitle = "", o = {}) {
  if (!valid(p) || !hudEnabled()) return false;
  const s = hst(p);
  const t = now();
  const prio = o.prio ?? 1;
  if (t < s.titleUntil && prio < s.titlePrio) return false;
  const stay = Math.max(1, Math.floor(o.stay ?? HUD.titleStay));
  try {
    p.onScreenDisplay.setTitle(title, { fadeInDuration: 2, stayDuration: stay, fadeOutDuration: 6, subtitle });
  } catch { return false; }
  s.title = title; s.subtitle = subtitle; s.titleUntil = t + stay + 8; s.titlePrio = prio;
  if (o.sound) playerSound(p, o.sound);
  return true;
}

/** 出し直す（force なら同じ文でも）。 @param {Player} p @param {boolean} [force] */
function refresh(p, force = false) {
  const s = hst(p);
  const t = now();
  if (!hudEnabled() || !isActive(p, true)) {
    if (!s.hidden) { s.hidden = true; s.text = ""; try { p.onScreenDisplay.setActionBar(""); } catch { /* 抜けた */ } }
    return;
  }
  s.hidden = false;
  const text = composeHud(p, t);
  if (!force && text === s.text && t - s.sentT < HUD.keepAlive) return;
  try { p.onScreenDisplay.setActionBar(text); } catch { return; }
  s.text = text; s.sentT = t;
}

onPlayerTick("hud", HUD.every, (p) => refresh(p));

// ---------------------------------------------------------------------------
//  バス
// ---------------------------------------------------------------------------
on(PEV.WEAPON_STATE, (d) => {
  if (!valid(d?.player)) return;
  hst(d.player).weapon = d;
});
on(PEV.NOTICE, (d) => { if (valid(d?.player)) notice(d.player, String(d.text ?? ""), Number(d.ticks) || HUD.noticeTicks); });

on(PEV.COMBO, (d) => {
  const p = d?.player;
  if (!valid(p) || !Array.isArray(d.list)) return;
  const top = d.list[0];
  const xp = Math.round(Number(d.xp) || 0);
  if (!top) { if (xp > 0) notice(p, `§a+${xp} XP`, 30); return; }
  const more = d.list.length > 1 ? ` §7+${d.list.slice(1).map((/** @type {any} */ r) => r.en).join(" + ")}` : "";
  const title = `${COMBO_COLOR[top.key] ?? "§c"}§l${top.en}${top.n > 1 ? ` x${top.n}` : ""}`;
  const sub = `§f${top.ja}${more}${xp > 0 ? `  §a+${xp} XP` : ""}${d.night ? " §5(夜 x2)" : ""}`;
  popup(p, title, sub, { prio: 1, sound: top.key === "headshot" ? "nr.ui.headshot" : "nr.ui.combo" });
});

on(PEV.LEVEL_UP, (d) => {
  const p = d?.player;
  if (!valid(p)) return;
  const tree = d.tree === "combat" ? "戦闘" : "パルクール";
  popup(p, "§6§lLEVEL UP", `§e${tree} Lv ${d.level} §7(スキルポイント ${d.points})`, { prio: 3, stay: 40 });
});

on(PEV.IMMUNITY, (d) => {
  const p = d?.player;
  if (!valid(p)) return;
  if (d.kind === "warn") {
    const w = Number(d.threshold) || Math.ceil(Number(d.value) || 0);
    notice(p, `§5免疫 残り ${w} 秒`, 60);
    if (w <= 10) popup(p, "§5§l免疫低下", "§dUV ライトか免疫アンプルを", { prio: 2, stay: 30 });
  } else if (d.kind === "zero") {
    popup(p, "§4§l感染進行", "§cUV ライトか免疫アンプルを探せ", { prio: 4, stay: 40 });
  } else if (d.kind === "restore") {
    notice(p, `§b免疫 ${fmtTime(Number(d.value) || 0)}`, 40);
  } else if (d.kind === "full") {
    notice(p, "§b免疫 全快", 40);
  }
});
