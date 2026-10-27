// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 経験値・レベル・スキル（DESIGN §7、data/skills.js）
//
//  * 経験値はパルクールと戦闘の 2 本立て（PROGRESSION）。レベルは XP_TO_NEXT の累計で決まり、
//    レベルが 1 上がるごとにその木のスキルポイントが points_per_level 増える。スキルはその木のポイントで買う。
//  * 保存はプレイヤーの動的プロパティ: `nr:skills`（JSON {鍵: 1}。combat/common.js の既定の読み方と同じ形）、
//    `nr:xp`（JSON {parkour: 数, combat: 数}）。ポイントは保存しない（レベル − 使った分で毎回出す）。
//  * 戦闘の経験値: バス EV.KILL（種類 cls の点 × 夜は night_mult）と、ゴアの出来事（EV.SEVER / DECAP / CRUSH /
//    HEADSHOT / GUTTED / HALVED、combat の "finisher"）。1 tick 分をゾンビごとにまとめて二重に数えない
//    （首が飛ぶ一撃は SEVER(head) + DECAP + HEADSHOT + KILL が同時に来る → 斬首だけ）。まとめた結果は
//    バス "gore_combo" {player, list, xp, kills}（HUD が見出しにする）。
//  * パルクールの経験値: バス "parkour" {player, move}（PROGRESSION.parkour_xp の鍵。climb_block / glide_s は 1 ブロック・1 秒ごと）。
//  * 他のモジュールからの経験値: バス "xp" {player, tree, amount, reason}。
//  * デバッグ: `/scriptevent nr:skill <鍵 | all | reset | list>`、`/scriptevent nr:xp <parkour | combat> <量>`。
// ===========================================================================
import { world, system } from "@minecraft/server";
import { on, emit, EV } from "../core/bus.js";
import { valid, now, isPlayer, dist } from "../core/util.js";
import { playerSound } from "../core/fx.js";
import { zombieSpec } from "../core/hp.js";
import * as SKILLS_D from "../data/skills.js";
import * as SETTINGS_D from "../data/settings.js";
import { PEV, nv, playerMap, onWorldTick, isNight, guard } from "./common.js";

/** @typedef {import("@minecraft/server").Player} Player */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {"parkour" | "combat"} Tree */

/** @type {any} */
const SK = SKILLS_D;
/** @type {any} */
const SD = SETTINGS_D;
/** @type {any[]} */
const SKILLS = Array.isArray(SK.SKILLS) ? SK.SKILLS : [];
/** @type {Record<string, any>} */
const SKILL_BY_KEY = SK.SKILL_BY_KEY ?? Object.fromEntries(SKILLS.map((s) => [s.key, s]));
/** @type {any} */
const PROG = SK.PROGRESSION ?? {};
/** @type {number[]} */
const XP_TO_NEXT = Array.isArray(SK.XP_TO_NEXT) ? SK.XP_TO_NEXT : [];
/** @type {Record<string, {ja: string, en: string, xp: number}>} */
export const GORE_COMBOS = SD.GORE_COMBOS ?? {};

export const TREES = /** @type {const} */ (["parkour", "combat"]);
export const SKILLS_KEY = "nr:skills";
export const XP_KEY = "nr:xp";
export const MAX_LEVEL = nv(PROG.max_level, 24);
const PPL = nv(PROG.points_per_level, 1);
/** @type {Record<string, number>} */
const CXP = PROG.combat_xp ?? {};
/** @type {Record<string, number>} */
const PXP = PROG.parkour_xp ?? {};
const MULTI_KILL_N = 3;          // この数を MULTI_KILL_TICKS 以内に仕留めると「まとめて仕留めた」
const MULTI_KILL_TICKS = 60;
const CREDIT_RANGE = 24;         // 攻撃者が分からない死（罠など）を近くのプレイヤーの手柄にする距離

// ---------------------------------------------------------------------------
//  保存と控え
// ---------------------------------------------------------------------------
/** @typedef {{skills: Record<string, number>, xp: Record<Tree, number>, dirty: boolean}} Prog */
/** @type {Map<string, Prog>} */
const progs = playerMap();

/** @param {Player} p @returns {Prog} */
function prog(p) {
  let g = progs.get(p.id);
  if (g) return g;
  g = { skills: {}, xp: { parkour: 0, combat: 0 }, dirty: false };
  try {
    const raw = p.getDynamicProperty(SKILLS_KEY);
    if (typeof raw === "string" && raw) {
      const v = JSON.parse(raw);
      if (Array.isArray(v)) for (const k of v) g.skills[String(k)] = 1;
      else if (v && typeof v === "object") for (const [k, n] of Object.entries(v)) if (n) g.skills[k] = 1;
    }
  } catch { /* 壊れた JSON は空から */ }
  try {
    const raw = p.getDynamicProperty(XP_KEY);
    if (typeof raw === "string" && raw) {
      const v = JSON.parse(raw);
      g.xp.parkour = Math.max(0, nv(v?.parkour, 0));
      g.xp.combat = Math.max(0, nv(v?.combat, 0));
    }
  } catch { /* 同上 */ }
  progs.set(p.id, g);
  return g;
}
/** スキルはすぐ書く（combat が動的プロパティを直接読むことがあるので）。 @param {Player} p @param {Prog} g */
function saveSkills(p, g) {
  try { p.setDynamicProperty(SKILLS_KEY, JSON.stringify(g.skills)); } catch { /* 抜けた */ }
}
/** @param {Player} p @param {Prog} g */
function saveXp(p, g) {
  g.dirty = false;
  try { p.setDynamicProperty(XP_KEY, JSON.stringify({ parkour: Math.round(g.xp.parkour * 100) / 100, combat: Math.round(g.xp.combat * 100) / 100 })); } catch { /* 抜けた */ }
}
// 経験値はまとめて 1 秒ごとに書く
onWorldTick("skills.save", 20, () => {
  for (const p of world.getAllPlayers()) {
    const g = progs.get(p.id);
    if (g?.dirty) saveXp(p, g);
  }
});

// ---------------------------------------------------------------------------
//  スキル
// ---------------------------------------------------------------------------
/** スキルを持っているか。 @param {Player} p @param {string} key */
export function hasSkill(p, key) { return valid(p) && !!prog(p).skills[key]; }
/** 持っているスキルの効果（data/skills.js の effect）。持っていなければ undefined。 @param {Player} p @param {string} key @returns {any} */
export function skillEff(p, key) { return hasSkill(p, key) ? (SKILL_BY_KEY[key]?.effect ?? {}) : undefined; }
/**
 * 持っているスキルの効果の数値（例 "stamina_max_add"）。`_add` で終わる鍵は足し合わせ、`_mult` は掛け合わせ、他は最初の値。
 * @param {Player} p @param {string} effKey @param {number} def
 */
export function skillNum(p, effKey, def) {
  if (!valid(p)) return def;
  const g = prog(p);
  let found = false, v = effKey.endsWith("_add") ? 0 : effKey.endsWith("_mult") ? 1 : def;
  for (const k of Object.keys(g.skills)) {
    const e = SKILL_BY_KEY[k]?.effect;
    if (!e || typeof e[effKey] !== "number") continue;
    if (effKey.endsWith("_add")) v += e[effKey];
    else if (effKey.endsWith("_mult")) v *= e[effKey];
    else if (!found) v = e[effKey];
    found = true;
  }
  return found ? v : def;
}
/** 持っているスキルの鍵。 @param {Player} p @returns {string[]} */
export function ownedSkills(p) { return valid(p) ? Object.keys(prog(p).skills) : []; }

/** その木で使ったポイント。 @param {Player} p @param {Tree} tree */
function spent(p, tree) {
  let n = 0;
  for (const k of Object.keys(prog(p).skills)) { const s = SKILL_BY_KEY[k]; if (s && s.tree === tree) n += nv(s.cost, 1); }
  return n;
}
/**
 * 買えるか。 @param {Player} p @param {string} key @returns {{ok: boolean, reason: string}}
 */
export function canBuy(p, key) {
  const s = SKILL_BY_KEY[key];
  if (!s) return { ok: false, reason: "unknown" };
  if (hasSkill(p, key)) return { ok: false, reason: "owned" };
  for (const r of s.requires ?? []) if (!hasSkill(p, r)) return { ok: false, reason: `requires:${r}` };
  if (pointsOf(p, s.tree) < nv(s.cost, 1)) return { ok: false, reason: "points" };
  return { ok: true, reason: "" };
}
/** ポイントで買う（端末から）。 @param {Player} p @param {string} key */
export function buySkill(p, key) {
  const c = canBuy(p, key);
  if (!c.ok) return c;
  const g = prog(p);
  g.skills[key] = 1;
  saveSkills(p, g);
  playerSound(p, "nr.ui.craft");
  return c;
}
/** ポイント・前提を見ずに与える（デバッグ・報酬）。 @param {Player} p @param {string} key */
export function grantSkill(p, key) {
  if (!valid(p) || !SKILL_BY_KEY[key]) return false;
  const g = prog(p);
  g.skills[key] = 1;
  saveSkills(p, g);
  return true;
}
/** スキルを外す（key 省略で全部。ポイントは戻る）。 @param {Player} p @param {string} [key] */
export function resetSkills(p, key) {
  if (!valid(p)) return false;
  const g = prog(p);
  if (key) delete g.skills[key]; else g.skills = {};
  saveSkills(p, g);
  return true;
}

// ---------------------------------------------------------------------------
//  経験値・レベル
// ---------------------------------------------------------------------------
/**
 * 経験値 → レベル（1..MAX_LEVEL）・そのレベルで貯めた分・次までに要る分。
 * @param {number} xp @returns {{level: number, into: number, need: number}}
 */
export function levelFromXp(xp) {
  let level = 1, rest = Math.max(0, xp);
  while (level < MAX_LEVEL) {
    const need = nv(XP_TO_NEXT[level], Math.round(100 * Math.pow(level, 1.4)));
    if (rest < need) return { level, into: rest, need };
    rest -= need;
    level++;
  }
  return { level, into: rest, need: 0 };
}
/** @param {Player} p @param {Tree} tree */
export function xpOf(p, tree) { return valid(p) ? prog(p).xp[tree] ?? 0 : 0; }
/** @param {Player} p @param {Tree} tree */
export function levelOf(p, tree) { return levelFromXp(xpOf(p, tree)).level; }
/** 使えるスキルポイント。 @param {Player} p @param {Tree} tree */
export function pointsOf(p, tree) { return Math.max(0, (levelOf(p, tree) - 1) * PPL - spent(p, tree)); }
/** 端末・HUD 用のまとめ。 @param {Player} p */
export function progressOf(p) {
  /** @type {Record<string, any>} */
  const out = { skills: ownedSkills(p) };
  for (const t of TREES) out[t] = { xp: xpOf(p, t), ...levelFromXp(xpOf(p, t)), points: pointsOf(p, t) };
  return out;
}

/**
 * 経験値を足す（レベルが上がれば "level_up" と音）。足した量を返す。
 * @param {Player} p @param {Tree} tree @param {number} amount @param {string} [reason]
 */
export function addXp(p, tree, amount, reason) {
  if (!valid(p) || !(amount > 0) || !Number.isFinite(amount) || (tree !== "parkour" && tree !== "combat")) return 0;
  const g = prog(p);
  const before = levelFromXp(g.xp[tree]).level;
  g.xp[tree] += amount;
  g.dirty = true;
  const after = levelFromXp(g.xp[tree]).level;
  if (after > before) {
    saveXp(p, g);
    playerSound(p, "nr.pl.levelup");
    emit(PEV.LEVEL_UP, { player: p, tree, level: after, points: pointsOf(p, tree), reason });
  }
  return amount;
}

/** パルクールの技 → 経験値（PROGRESSION.parkour_xp）。 @param {string} move */
export function parkourXp(move) {
  if (move === "climb_block") return nv(PXP.climb_per_block, 0.5);
  if (move === "glide_s") return nv(PXP.glide_per_s, 0.2);
  return nv(PXP[move], 0);
}

on(PEV.PARKOUR, (d) => {
  const p = d?.player;
  if (!valid(p)) return;
  const xp = parkourXp(String(d.move ?? ""));
  if (xp > 0) addXp(p, "parkour", xp * nv(d.mult, 1), d.move);
});
on(PEV.XP, (d) => {
  if (valid(d?.player)) addXp(d.player, d.tree, nv(d.amount, 0), d.reason);
});

// ---------------------------------------------------------------------------
//  ゴアのコンボ（1 tick 分をまとめる）
// ---------------------------------------------------------------------------
/** @typedef {{decap: boolean, crush: boolean, headshot: boolean, sever: number, gutted: boolean, halved: boolean, kill: boolean, cls: string, overkill: boolean, environment: boolean, finisher: boolean}} ZAgg */
/** @typedef {{player: Player, z: Map<string, ZAgg>}} PAgg */
/** @type {Map<string, PAgg>} */
const pending = new Map();
/** @type {Map<string, number[]>} */
const killTimes = playerMap();

/** その出来事の手柄のプレイヤー（攻撃者がプレイヤーならその人、byPlayer なら近くの人）。 @param {any} d @returns {Player | undefined} */
function creditOf(d) {
  const a = d?.attacker;
  if (isPlayer(a) && valid(a)) return /** @type {Player} */ (a);
  if (!d?.byPlayer) return undefined;
  const pos = d.pos ?? (valid(d.zombie) ? d.zombie.location : undefined);
  if (!pos) return undefined;
  /** @type {Player | undefined} */
  let best;
  let bd = CREDIT_RANGE;
  for (const p of world.getAllPlayers()) {
    try { const dd = dist(p.location, pos); if (dd < bd) { bd = dd; best = p; } } catch { /* 抜けた */ }
  }
  return best;
}
/** @param {Player} p @param {any} z @returns {ZAgg} */
function aggOf(p, z) {
  let pa = pending.get(p.id);
  if (!pa) { pa = { player: p, z: new Map() }; pending.set(p.id, pa); }
  const zid = String(safeId(z));
  let a = pa.z.get(zid);
  if (!a) {
    a = { decap: false, crush: false, headshot: false, sever: 0, gutted: false, halved: false, kill: false, cls: "", overkill: false, environment: false, finisher: false };
    pa.z.set(zid, a);
  }
  return a;
}
/** @param {any} z */
function safeId(z) { try { return z?.id ?? "?"; } catch { return "?"; } }

/** 出来事 → まとめ（死体への一撃は数えない）。 @param {any} d @param {(a: ZAgg) => void} fn */
function note(d, fn) {
  if (!d || d.corpse === true) return;
  const p = creditOf(d);
  if (!p) return;
  fn(aggOf(p, d.zombie));
}
on(EV.SEVER, (d) => note(d, (a) => { if (d.part !== "head" && d.part !== "torso") a.sever++; }));
on(EV.DECAP, (d) => note(d, (a) => { a.decap = true; }));
on(EV.CRUSH, (d) => note(d, (a) => { a.crush = true; }));
on(EV.HEADSHOT, (d) => note(d, (a) => { a.headshot = true; }));
on(EV.GUTTED, (d) => note(d, (a) => { a.gutted = true; }));
on(EV.HALVED, (d) => note(d, (a) => { a.halved = true; }));
on(PEV.FINISHER, (d) => note({ ...d, attacker: d?.player }, (a) => { a.finisher = true; }));
on(EV.KILL, (d) => {
  if (!d) return;
  const p = creditOf(d);
  if (!p) return;
  const a = aggOf(p, d.zombie);
  a.kill = true;
  a.overkill = a.overkill || !!d.overkill;
  a.environment = a.environment || !!d.environment;
  a.decap = a.decap || !!d.decap;
  a.crush = a.crush || !!d.crushed;
  const spec = guard("skills.spec", () => zombieSpec(d.key ?? d.zombie));
  a.cls = String(spec?.cls ?? "common");
});

/** @param {string} key @param {number} [n] */
function comboRow(key, n = 1) {
  const c = GORE_COMBOS[key] ?? { ja: key, en: key.toUpperCase(), xp: 0 };
  const fb = key === "decapitated" ? CXP.decapitate : key === "dismember" ? CXP.dismember : key === "environment" ? CXP.trap_kill : CXP[key];
  return { key, ja: c.ja, en: c.en, xp: nv(c.xp, nv(fb, 0)) * n, n };
}

/** 見出しの優先（強い順）。 */
export const COMBO_ORDER = ["multi_kill", "bisected", "decapitated", "skull_crush", "overkill", "finisher", "gutted", "environment", "dismember", "headshot"];

onWorldTick("skills.combo", 1, (t) => {
  if (!pending.size) return;
  const night = isNight();
  const nightMult = night ? nv(CXP.night_mult, 2) : 1;
  for (const [pid, pa] of [...pending]) {
    pending.delete(pid);
    const p = pa.player;
    if (!valid(p)) continue;
    /** @type {Map<string, {key: string, ja: string, en: string, xp: number, n: number}>} */
    const rows = new Map();
    const add = (/** @type {string} */ key, n = 1) => {
      const r = rows.get(key);
      const nr = comboRow(key, n);
      if (r) { r.n += n; r.xp += nr.xp; } else rows.set(key, nr);
    };
    let kills = 0, killXp = 0;
    for (const a of pa.z.values()) {
      if (a.halved) add("bisected");
      if (a.decap) add("decapitated");
      else if (a.crush) add("skull_crush");
      else if (a.headshot) add("headshot");
      if (a.sever > 0) add("dismember", a.sever);
      if (a.gutted) add("gutted");
      if (a.overkill) add("overkill");
      if (a.environment) add("environment");
      if (a.finisher) add("finisher");
      if (a.kill) { kills++; killXp += nv(CXP[a.cls], nv(CXP.common, 8)); }
    }
    if (kills) {
      const arr = killTimes.get(p.id) ?? [];
      for (let i = 0; i < kills; i++) arr.push(t);
      while (arr.length && t - arr[0] > MULTI_KILL_TICKS) arr.shift();
      if (arr.length >= MULTI_KILL_N) { add("multi_kill"); arr.length = 0; }
      killTimes.set(p.id, arr);
    }
    const list = [...rows.values()].sort((x, y) => COMBO_ORDER.indexOf(x.key) - COMBO_ORDER.indexOf(y.key));
    const xp = (list.reduce((s, r) => s + r.xp, 0) + killXp) * nightMult;
    if (xp > 0) addXp(p, "combat", xp, "kill");
    if (list.length || kills) emit(PEV.COMBO, { player: p, list, xp, kills, night });
  }
});

// ---------------------------------------------------------------------------
//  デバッグのコマンド（/scriptevent nr:skill … / nr:xp …）
// ---------------------------------------------------------------------------
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id !== "nr:skill" && ev.id !== "nr:xp") return;
  const src = ev.sourceEntity;
  const targets = isPlayer(src) && valid(src) ? [/** @type {Player} */ (src)] : world.getAllPlayers();
  const args = String(ev.message ?? "").trim().split(/\s+/).filter(Boolean);
  for (const p of targets) {
    if (ev.id === "nr:xp") {
      const tree = args[0] === "combat" ? "combat" : "parkour";
      addXp(p, tree, nv(args[1], 100), "command");
      continue;
    }
    const a = args[0] ?? "list";
    if (a === "all") for (const s of SKILLS) grantSkill(p, s.key);
    else if (a === "reset") resetSkills(p);
    else if (a !== "list") grantSkill(p, a);
    try { p.sendMessage(`§7[NR] skills: ${ownedSkills(p).join(", ") || "-"}  §7parkour Lv${levelOf(p, "parkour")} (${pointsOf(p, "parkour")}pt)  combat Lv${levelOf(p, "combat")} (${pointsOf(p, "combat")}pt)`); } catch { /* 抜けた */ }
  }
}, { namespaces: ["nr"] });

/** テスト用: その tick のまとめを待たずに捨てる。 */
export function _clearPending() { pending.clear(); }
/** テスト用: 時刻（未使用の import を避ける）。 */
export function _now() { return now(); }
