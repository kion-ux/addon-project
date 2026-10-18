// ===========================================================================
//  プレイヤーごとの状態と保存
//
//  * 変身中の惑星（form）・星力（energy）・超新星ゲージ（nova）・オーバーヒート残り tick
//  * 惑星ごとの同調率 XP（sync）・設定（settings）・記録（records）
//  * 実行中だけの値（再使用時間・技の最中ロック・バリア・解除の長押し…）
//
//  保存先は動的プロパティ（再参加・再読み込みでも残る）。数値は数秒おきにまとめて書き、
//  変身／解除や設定の変更のような大事な変化はその場で書く。
// ===========================================================================
import { COMMON, PLANETS } from "./data.js";
import {
  numProp, getProp, setProp, jsonProp, setJsonProp, now, clamp, valid, allPlayers,
} from "./util.js";

export const PROP = {
  form: "astro:form",          // 変身中の惑星キー（"" なら未変身）
  seq: "astro:seq",            // 変身の演出中の惑星キー（中断の検出用）
  energy: "astro:energy",
  nova: "astro:nova",
  overheat: "astro:overheat",  // 残り tick
  sync: "astro:sync",          // JSON {key: xp}
  settings: "astro:settings",  // JSON
  records: "astro:records",    // JSON
  armor: "astro:armor",        // JSON 退避した防具 [{slot, id, inv}]
  frozen: "astro:frozen",      // 変身の硬直中（再参加・再読み込みで必ず戻す）
  cam: "astro:cam",            // 演出カメラ中（同上）
  coreless: "astro:coreless",  // コア無しで変身した（解除でコアを渡さない）
  deadForm: "astro:dead_form", // 変身中に死んだ（リスポーンで解除）
  last: "astro:last",          // 最後に変身した惑星（未変身時の最大星力）
  gotTerminal: "astro:got_terminal",
};

/** 演出の量の段階（設定のドロップダウンの順）と粒の予算倍率。 */
export const FX_LEVELS = ["多い", "標準", "少ない"];
export const FX_SCALE = [1.5, 1.0, 0.5];

export const DEFAULT_SETTINGS = { cam: true, hud: true, fx: 1, dmg: true };

const DEFAULT_RECORDS = {
  kills: 0, transforms: 0, ults: 0, moves: 0, justDodges: 0, maxHit: 0, ticks: 0,
  deaths: 0, overheats: 0, perPlanet: {},
};

const states = new Map();   // playerId -> state

function load(p) {
  const st = {
    id: p.id,
    form: null,
    seq: null,
    energy: numProp(p, PROP.energy, COMMON.energy_max),
    nova: numProp(p, PROP.nova, 0),
    overheat: numProp(p, PROP.overheat, 0),
    sync: jsonProp(p, PROP.sync, {}),
    settings: { ...DEFAULT_SETTINGS, ...jsonProp(p, PROP.settings, {}) },
    records: { ...DEFAULT_RECORDS, ...jsonProp(p, PROP.records, {}) },
    coreless: getProp(p, PROP.coreless, false) === true,
    deadForm: null,
    last: null,
    gen: 0,
    busyUntil: -1,
    cd: {},
    novaLock: -1,
    revertHold: 0,
    barrierUntil: -1,
    barrierCd: -1,
    offUntil: -1,
    offKey: null,
    passive: {},
    dirty: false,
    readyAnnounced: false,
  };
  const f = getProp(p, PROP.form, "");
  if (typeof f === "string" && PLANETS[f]) st.form = f;
  const d = getProp(p, PROP.deadForm, "");
  if (typeof d === "string" && PLANETS[d]) st.deadForm = d;
  const l = getProp(p, PROP.last, "");
  if (typeof l === "string" && PLANETS[l]) st.last = l;
  if (typeof st.sync !== "object" || !st.sync) st.sync = {};
  if (typeof st.records.perPlanet !== "object" || !st.records.perPlanet) st.records.perPlanet = {};
  st.settings.fx = clamp(Math.round(Number(st.settings.fx) || 0), 0, FX_LEVELS.length - 1);
  return st;
}

/** プレイヤーの状態（初めて触れた時に動的プロパティから読み込む）。 */
export function S(p) {
  let st = states.get(p.id);
  if (!st) {
    st = load(p);
    states.set(p.id, st);
  }
  return st;
}

export function hasState(id) { return states.has(id); }
export function forgetState(id) { states.delete(id); }

/** 状態を動的プロパティへ書く。 */
export function save(p) {
  if (!valid(p)) return;
  const st = states.get(p.id);
  if (!st) return;
  setProp(p, PROP.form, st.form ?? "");
  setProp(p, PROP.energy, Math.round(st.energy * 100) / 100);
  setProp(p, PROP.nova, Math.round(st.nova * 100) / 100);
  setProp(p, PROP.overheat, Math.max(0, Math.round(st.overheat)));
  setJsonProp(p, PROP.sync, st.sync);
  setJsonProp(p, PROP.settings, st.settings);
  setJsonProp(p, PROP.records, st.records);
  setProp(p, PROP.coreless, st.coreless === true);
  setProp(p, PROP.deadForm, st.deadForm ?? "");
  setProp(p, PROP.last, st.last ?? "");
  st.dirty = false;
}

export function saveAll() {
  for (const p of allPlayers()) {
    if (states.has(p.id)) save(p);
  }
}

// ---------------------------------------------------------------------------
//  変身
// ---------------------------------------------------------------------------
/** 変身中の惑星キー（演出中も含む）。未変身なら null。 */
export function formOf(p) { return S(p).form; }
/** 変身が完了していて技・機動が使える。 */
export function isReady(p) { const st = S(p); return !!st.form && !st.seq; }
/** 変身の演出の最中。 */
export function inSequence(p) { return !!S(p).seq; }
export function planetOf(p) { const k = S(p).form; return k ? PLANETS[k] : null; }

// ---------------------------------------------------------------------------
//  同調率
// ---------------------------------------------------------------------------
export function xpOf(p, key) { return Math.max(0, Number(S(p).sync[key]) || 0); }

export function levelFromXp(xp) {
  let lv = 1;
  const t = COMMON.sync_xp;
  for (let i = 1; i < t.length; i++) if (xp >= t[i]) lv = i + 1;
  return lv;
}

export function level(p, key = S(p).form) {
  if (!key) return 1;
  return levelFromXp(xpOf(p, key));
}

/** 次の Lv までの [今の Lv の下限, 次の Lv の閾値]（最大なら null）。 */
export function nextLevelXp(p, key) {
  const lv = level(p, key);
  const t = COMMON.sync_xp;
  return lv >= t.length ? null : [t[lv - 1], t[lv]];
}

/** XP を足す。Lv が上がったら新しい Lv を返す（上がらなければ 0）。 */
export function addXpRaw(p, key, n) {
  if (!key || !PLANETS[key]) return 0;
  const st = S(p);
  const before = level(p, key);
  const max = COMMON.sync_xp[COMMON.sync_xp.length - 1];
  st.sync[key] = Math.min(max, xpOf(p, key) + n);
  st.dirty = true;
  const after = level(p, key);
  return after > before ? after : 0;
}

export function setXp(p, key, xp) {
  S(p).sync[key] = Math.max(0, xp);
  S(p).dirty = true;
}

// ---------------------------------------------------------------------------
//  星力・超新星ゲージ・オーバーヒート
// ---------------------------------------------------------------------------
/** 最大星力（変身中／最後に使った形態の同調率で決まる）。 */
export function maxEnergy(p, key) {
  const st = S(p);
  const k = key ?? st.form ?? st.last;
  return COMMON.energy_max + COMMON.energy_per_level * (level(p, k) - 1);
}

export function energy(p) { return S(p).energy; }

export function setEnergy(p, v, key) {
  const st = S(p);
  st.energy = clamp(Number.isFinite(v) ? v : 0, 0, maxEnergy(p, key));
  st.dirty = true;
  return st.energy;
}

export function addEnergy(p, dv) { return setEnergy(p, S(p).energy + dv); }

export function nova(p) { return S(p).nova; }

export function setNovaRaw(p, v) {
  const st = S(p);
  st.nova = clamp(Number.isFinite(v) ? v : 0, 0, COMMON.nova_max);
  st.dirty = true;
  return st.nova;
}

export function novaFull(p) { return S(p).nova >= COMMON.nova_max - 1e-6; }

export function lockNova(p, ticks) { S(p).novaLock = now() + ticks; }
export function novaLocked(p) { return S(p).novaLock > now(); }

export function overheat(p) { return S(p).overheat; }
export function setOverheat(p, ticks) { S(p).overheat = Math.max(0, ticks); S(p).dirty = true; }

// ---------------------------------------------------------------------------
//  再使用時間と「技の最中」
// ---------------------------------------------------------------------------
export function cdLeft(p, key, kind) {
  return Math.max(0, (S(p).cd[`${key}.${kind}`] ?? 0) - now());
}
export function setCd(p, key, kind, ticks) { S(p).cd[`${key}.${kind}`] = now() + Math.max(0, ticks); }
export function clearCds(p) { S(p).cd = {}; }
export function isBusy(p) { return S(p).busyUntil > now(); }
export function setBusy(p, ticks) { S(p).busyUntil = Math.max(S(p).busyUntil, now() + ticks); }
export function clearBusy(p) { S(p).busyUntil = -1; }

/** 再使用時間の倍率（同調率 Lv ごとに -5%）。 */
export function cdMul(p, key) {
  return Math.max(0.5, 1 - COMMON.sync_cd_per_level * (level(p, key) - 1));
}

// ---------------------------------------------------------------------------
//  設定と記録
// ---------------------------------------------------------------------------
export function settings(p) { return S(p).settings; }

export function setSettings(p, patch) {
  const st = S(p);
  st.settings = { ...st.settings, ...patch };
  st.settings.fx = clamp(Math.round(Number(st.settings.fx) || 0), 0, FX_LEVELS.length - 1);
  save(p);
}

export function records(p) { return S(p).records; }

export function addRecord(p, field, n = 1, key) {
  const r = S(p).records;
  r[field] = (Number(r[field]) || 0) + n;
  if (key) {
    const pp = r.perPlanet[key] ?? (r.perPlanet[key] = {});
    pp[field] = (Number(pp[field]) || 0) + n;
  }
  S(p).dirty = true;
}

export function maxRecord(p, field, v) {
  const r = S(p).records;
  if (v > (Number(r[field]) || 0)) { r[field] = Math.round(v * 10) / 10; S(p).dirty = true; }
}
