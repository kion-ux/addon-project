// ===========================================================================
//  変身と解除
//
//  変身の時間割（astro_data.TRANSFORM、tick）:
//    0 core_rise    コアが浮かぶ。硬直（移動の入力ロック＋無敵）・演出カメラ・防具の退避・コアのロック
//    8 swarm_start  ナノマシンの奔流がコアから全身へ
//   14 suit_equip   頭スロットに astro:suit_<key>_on（組み上がり 1.8 秒）。部位ごとに粒が流れ込む
//   40 weapon_form  手のコア → ナノウェポン（同じスロット）
//   46 visor_flash  バイザー点灯
//   50 planet_burst planets/<key>.js の burst(ctx)。カットイン（紋章＋形態名）
//   52             suit_<key>_on → suit_<key>（装着中）に差し替え
//   60 camera_clear カメラを戻す / 64 freeze 終わり、操作が戻る
//
//  解除: 頭を astro:suit_<key>_off（分解）に差し替え 0.9 秒後に外す。ウェポン → コア。防具を戻す。
//  理由: manual（長押し・ターミナル・コマンド）/ depleted（星力切れ → オーバーヒート）/
//        death（リスポーン時）/ invalid（状態の食い違い）/ silent（再参加・再読み込みの後始末）
//
//  カメラと入力ロックは「付けたら必ず外す」: 動的プロパティに印を残し、解除・死亡・リスポーン・
//  再参加・スクリプトの再読み込み・毎秒の見張りのどこでも外す。
// ===========================================================================
import * as mc from "@minecraft/server";
import { ItemStack } from "@minecraft/server";
import {
  COMMON, TRANSFORM, ASSEMBLE_ORDER, PLANETS, CORE_TO_PLANET, WEAPON_TO_PLANET, SUIT_TO_PLANET,
} from "./data.js";
import {
  S, PROP, save, energy, setEnergy, maxEnergy, overheat, setOverheat, settings, addRecord, clearBusy,
} from "./state.js";
import {
  P, sound, title, glyph, body, bodyStop, white, mix, swarm, ring, emblem, shake, flash, announce,
} from "./fx.js";
import { makeCtx, moveImpl } from "./engine.js";
import { resetMobility } from "./mobility.js";
import { progressBar } from "./hud.js";
import { clearShots } from "./projectiles.js";
import { clearZones } from "./zones.js";
import {
  valid, alive, cmd, now, getProp, setProp, jsonProp, setJsonProp, container, getEquip, setEquip,
  selectedSlot, findSlots, firstEmpty, emptySlots, lockItem, lockModeOf, effect, removeEffect,
  flatDir, rightOf, add, up, blocked, lerp3, fmt, report, allPlayers, BUS, give, ARMOR_SLOTS, world,
  dist, getEffect, removeOwnEffect,
} from "./util.js";

const LOCK_SLOT = "slot";
const LOCK_INV = "inventory";
const LOCK_NONE = "none";

/** 解除の分解アニメの長さ（tick）。 */
export const OFF_TICKS = 18;
/** 組み上がり → 装着中へ差し替える時刻（tick）。 */
export const STEADY_AT = TRANSFORM.suit_equip + Math.round(TRANSFORM.assemble_len * 20) + 2;

// ---------------------------------------------------------------------------
//  アイテムの判定
// ---------------------------------------------------------------------------
export function headItem(p) { return getEquip(p, "Head"); }

function isOurSuit(it) { return !!(it && SUIT_TO_PLANET[it.typeId]); }

function makeItem(id, mode, keep) {
  try { return lockItem(new ItemStack(id, 1), mode, keep); } catch (e) { report("transform.item", e); return undefined; }
}

function markCoreless(it) {
  try { it?.setDynamicProperty?.("astro:coreless", true); } catch (_) { }
  return it;
}

function isCoreless(it) {
  try { return it?.getDynamicProperty?.("astro:coreless") === true; } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
//  入力ロックとカメラ
// ---------------------------------------------------------------------------
function setMovement(p, enabled) {
  let ok = false;
  try {
    const ip = p.inputPermissions;
    if (ip && typeof ip.movementEnabled === "boolean") { ip.movementEnabled = enabled; ok = true; }
  } catch (_) { }
  if (!ok) ok = cmd(p, `inputpermission set @s movement ${enabled ? "enabled" : "disabled"}`);
  return ok;
}

function freezePlayer(p, ticks) {
  setProp(p, PROP.frozen, true);
  effect(p, "resistance", ticks + 6, 4);
  if (!setMovement(p, false)) effect(p, "slowness", ticks, 9);
}

/** 入力ロックを外す（印があれば。force で印が無くても）。 */
export function unfreeze(p, force = false) {
  if (!valid(p)) return;
  if (!force && getProp(p, PROP.frozen, false) !== true) return;
  setMovement(p, true);
  removeOwnEffect(p, "slowness", TRANSFORM.freeze + 6, 9);   // 入力ロックの代わりに掛けた鈍化だけ
  setProp(p, PROP.frozen, false);
}

// ---------------------------------------------------------------------------
//  透明化（DESIGN §4.3b）
//  7 頭身のスーツはプレイヤーの 4 頭身の肌を覆わないので、スーツ（組み上がり・装着中・分解中）が頭に
//  ある間は本体を透明にする（粒なし。スーツのアタッチャブルは透明でも描かれる）。60 tick を毎秒掛け直す。
//  掛けた印を動的プロパティに残し、外す時は残りが掛け直しの長さ以下の時だけ外す（自分で飲んだ透明化の
//  薬は残す）。
// ---------------------------------------------------------------------------
/** 透明化の 1 回の長さ（tick）。 */
export const CLOAK_TICKS = 60;

/** 透明化を掛ける（掛け直す）。プレイヤー自身のもっと長い透明化は短くしない。 */
export function cloak(p) {
  if (!valid(p)) return;
  if (getProp(p, PROP.invis, false) !== true) setProp(p, PROP.invis, true);
  const cur = getEffect(p, "invisibility");
  if (cur && cur.duration > CLOAK_TICKS + 5) return;
  effect(p, "invisibility", CLOAK_TICKS, 0, false);
}

/** 掛けた透明化を外す（掛けていなければ何もしない。長い薬の透明化は残す）。 */
export function uncloak(p) {
  if (!valid(p) || getProp(p, PROP.invis, false) !== true) return;
  setProp(p, PROP.invis, false);
  removeOwnEffect(p, "invisibility", CLOAK_TICKS + 5);
}

/** 毎秒（main から）: 頭にスーツがあれば掛け直し、無ければ外す。 */
export function tickCloak(p) {
  if (!alive(p)) return;
  if (isOurSuit(headItem(p))) cloak(p);
  else uncloak(p);
}

function easeType() {
  try { return mc.EasingType?.InOutSine ?? "InOutSine"; } catch (_) { return "InOutSine"; }
}

/** 演出カメラを置く（API → コマンドの順に試す）。 */
function camSet(p, pos, facing, ease = 0) {
  setProp(p, PROP.cam, true);
  try {
    if (typeof p.camera?.setCamera === "function") {
      const o = { location: pos, facingLocation: facing };
      if (ease > 0) o.easeOptions = { easeTime: ease, easeType: easeType() };
      p.camera.setCamera("minecraft:free", o);
      return true;
    }
  } catch (_) { /* コマンドへ */ }
  const e = ease > 0 ? `ease ${fmt(ease)} in_out_sine ` : "";
  return cmd(p, `camera @s set minecraft:free ${e}pos ${fmt(pos.x)} ${fmt(pos.y)} ${fmt(pos.z)} facing ${fmt(facing.x)} ${fmt(facing.y)} ${fmt(facing.z)}`);
}

/** 画面のフェード（合計 0.5 秒以上にそろえる）。color は 0..1。 */
function camFade(p, fin, hold, fout, color = [1, 1, 1]) {
  if (fin + hold + fout < 0.5) fout = 0.5 - fin - hold;
  try {
    if (typeof p.camera?.fade === "function") {
      p.camera.fade({ fadeTime: { fadeInTime: fin, holdTime: hold, fadeOutTime: fout },
                      fadeColor: { red: color[0], green: color[1], blue: color[2] } });
      return;
    }
  } catch (_) { }
  const [r, g, b] = color.map((c) => Math.round(c * 255));
  cmd(p, `camera @s fade time ${fmt(fin)} ${fmt(hold)} ${fmt(fout)} color ${r} ${g} ${b}`);
}

/** 演出カメラを外す（印があれば。force で印が無くても）。 */
export function camClear(p, force = false) {
  if (!valid(p)) return;
  if (!force && getProp(p, PROP.cam, false) !== true) return;
  let ok = false;
  try { if (typeof p.camera?.clear === "function") { p.camera.clear(); ok = true; } } catch (_) { }
  if (!ok) cmd(p, "camera @s clear");
  setProp(p, PROP.cam, false);
}

// ---------------------------------------------------------------------------
//  防具の退避
// ---------------------------------------------------------------------------
function wornArmor(p) {
  const out = [];
  for (const slot of ARMOR_SLOTS) {
    const it = getEquip(p, slot);
    if (it && !isOurSuit(it)) out.push([slot, it]);
  }
  return out;
}

/** 頭・胴・脚・足の防具をインベントリへ移して記録する。入りきらなければ false（何も動かさない）。 */
function stashArmor(p) {
  const inv = container(p);
  const worn = wornArmor(p);
  if (!worn.length) return true;
  if (!inv || emptySlots(inv) < worn.length) return false;
  const rec = jsonProp(p, PROP.armor, []) || [];
  for (const [slot, it] of worn) {
    const i = firstEmpty(inv);
    if (i < 0) break;
    try {
      inv.setItem(i, it);
      setEquip(p, slot, undefined);
      rec.push({ slot, id: it.typeId, inv: i });
    } catch (e) { report("transform.stash", e); }
  }
  setJsonProp(p, PROP.armor, rec);
  return true;
}

/**
 * 退避の後に着けられた防具を外してインベントリへ（入らなければ足元へ）移し、退避の記録に足す
 * （解除の時に restoreArmor が着せ直す）。外せたら true。
 */
function stowWorn(p, slot, it) {
  if (!it || isOurSuit(it)) return false;
  if (!setEquip(p, slot, undefined)) return false;   // 先に外す（失敗しても増えない）
  const inv = container(p);
  const i = firstEmpty(inv);
  let placed = false;
  if (i >= 0) { try { inv.setItem(i, it); placed = true; } catch (_) { } }
  if (!placed) give(p, it);
  const rec = jsonProp(p, PROP.armor, []) || [];
  rec.push({ slot, id: it.typeId, inv: placed ? i : -1 });
  setJsonProp(p, PROP.armor, rec);
  return true;
}

/** 変身中に着けられない装備（防御点の無いエリトラは着けたままでよい）。 */
const STOW_EXEMPT = new Set(["minecraft:elytra"]);

/** 退避した防具を着せ直す（同じスロット → 同じ種類の順に探す）。 */
export function restoreArmor(p) {
  const rec = jsonProp(p, PROP.armor, null);
  if (!Array.isArray(rec) || !rec.length) { setProp(p, PROP.armor, undefined); return; }
  const inv = container(p);
  if (!inv) return;
  for (const r of rec) {
    if (!r || !ARMOR_SLOTS.includes(r.slot) || typeof r.id !== "string") continue;
    const worn = getEquip(p, r.slot);
    if (worn) continue;
    let idx = -1;
    try { if (typeof r.inv === "number" && inv.getItem(r.inv)?.typeId === r.id) idx = r.inv; } catch (_) { }
    if (idx < 0) idx = findSlots(inv, (it) => it.typeId === r.id)[0] ?? -1;
    if (idx < 0) continue;
    try {
      const it = inv.getItem(idx);
      if (setEquip(p, r.slot, it)) inv.setItem(idx, undefined);
    } catch (e) { report("transform.restore", e); }
  }
  setProp(p, PROP.armor, undefined);
}

// ---------------------------------------------------------------------------
//  コア ⇔ ウェポン
// ---------------------------------------------------------------------------
/** key のウェポンを全部コアへ戻す（2 本目以降は消す）。戻せたら true。 */
function weaponsToCores(p, key, giveIfMissing) {
  const pl = PLANETS[key];
  const inv = container(p);
  const st = S(p);
  let found = false;
  if (inv) {
    const slots = findSlots(inv, (it) => it.typeId === pl.weaponId);
    slots.forEach((i, n) => {
      try {
        const it = inv.getItem(i);
        const free = st.coreless || isCoreless(it);
        inv.setItem(i, n === 0 && !free ? makeItem(pl.core, LOCK_NONE, false) : undefined);
        found = true;
      } catch (e) { report("transform.weapon", e); }
    });
  }
  const off = getEquip(p, "Offhand");
  if (off?.typeId === pl.weaponId) {
    setEquip(p, "Offhand", found || st.coreless ? undefined : makeItem(pl.core, LOCK_NONE, false));
    found = true;
  }
  if (!found && giveIfMissing && !st.coreless) {
    const g = makeItem(pl.core, LOCK_NONE, false);
    if (g) give(p, g);
  }
  return found;
}

/** ロックの残ったコアを戻す（変身の演出中以外）。 */
function unlockCores(p) {
  const inv = container(p);
  for (const i of findSlots(inv, (it) => !!CORE_TO_PLANET[it.typeId] &&
       (lockModeOf(it) !== LOCK_NONE || it.keepOnDeath === true))) {
    try {
      const it = inv.getItem(i);
      inv.setItem(i, lockItem(it, LOCK_NONE, false));
    } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  変身できるか
// ---------------------------------------------------------------------------
/** 変身できるか。{ ok, why } */
export function canTransform(p, key, o = {}) {
  const st = S(p);
  if (!PLANETS[key]) return { ok: false, why: "§c不明な形態" };
  if (st.form || st.seq) return { ok: false, why: "§7すでに変身中" };
  if (st.offUntil > now()) return { ok: false, why: "§7解除の最中" };
  if (!alive(p)) return { ok: false, why: "" };
  try { if (p.isGliding) return { ok: false, why: "§7滑空中は変身できない" }; } catch (_) { }
  if (!o.coreless) {
    if (overheat(p) > 0) return { ok: false, why: `§r${glyph("icon.overheat", "")}§r §cオーバーヒート中 §fあと ${(overheat(p) / 20).toFixed(1)} 秒` };
    if (energy(p) < COMMON.energy_to_transform) return { ok: false, why: `§r${glyph("icon.energy", "")}§r §c星力が足りない §f${Math.floor(energy(p))}/${COMMON.energy_to_transform}` };
  }
  const inv = container(p);
  const need = wornArmor(p).length;
  if (need > 0 && emptySlots(inv) < need) return { ok: false, why: `§c防具をしまう場所がない（インベントリの空き ${need} 個が必要）` };
  return { ok: true, why: "" };
}

// ---------------------------------------------------------------------------
//  変身
// ---------------------------------------------------------------------------
const seqs = new Map();   // playerId -> { p, key, age, steps, idx, ... }

/**
 * 変身を始める。
 * @param p
 * @param key  惑星キー
 * @param o    coreless: true でコア無し（/scriptevent astro:transform）/ slot コアのスロット
 * @returns 始まったら true
 */
export function startTransform(p, key, o = {}) {
  const chk = canTransform(p, key, o);
  if (!chk.ok) {
    if (chk.why) announce(p, chk.why, 40);
    sound(p.dimension, "astro.alert", p.location, 0.8, 0.5);
    return false;
  }
  const st = S(p);
  const pl = PLANETS[key];
  const inv = container(p);
  let slot = -1;
  if (!o.coreless) {
    const sel = typeof o.slot === "number" ? o.slot : selectedSlot(p);
    try { if (inv?.getItem(sel)?.typeId === pl.core) slot = sel; } catch (_) { }
    if (slot < 0) slot = findSlots(inv, (it) => it.typeId === pl.core)[0] ?? -1;
    if (slot < 0) { announce(p, "§cコアが見つからない", 30); return false; }
  }
  if (!stashArmor(p)) { announce(p, "§c防具をしまう場所がない", 40); return false; }
  // ここから先は revert() がどの段階からでも元に戻せる
  st.gen++;
  st.form = key;
  st.coreless = !!o.coreless;
  st.last = key;
  st.revertHold = 0;
  st.passive = {};
  if (o.coreless && energy(p) < COMMON.energy_to_transform) setEnergy(p, maxEnergy(p, key), key);
  setProp(p, PROP.seq, key);
  if (slot >= 0) {
    try { inv.setItem(slot, lockItem(inv.getItem(slot), LOCK_SLOT, true)); } catch (_) { }
  }
  const seq = buildSequence(p, key, slot, !!o.coreless);
  st.seq = seq;
  seqs.set(p.id, seq);
  save(p);
  runSteps(seq);   // 0 tick の段
  return true;
}

/** 体の部位の位置（足元からの前・右・上のずれ）。組み上がりの粒の行き先。 */
const PART_POS = {
  boots: [[0, -0.14, 0.15], [0, 0.14, 0.15]],
  legs: [[0.02, -0.13, 0.55], [0.02, 0.13, 0.55]],
  waist: [[0.05, 0, 0.85]],
  torso: [[0.12, 0, 1.2]],
  back: [[-0.28, 0, 1.25]],
  arms: [[0, -0.38, 1.05], [0, 0.38, 1.05]],
  shoulders: [[0, -0.36, 1.42], [0, 0.36, 1.42]],
  helmet: [[0, 0, 1.75]],
  visor: [[0.22, 0, 1.65]],
  extra: [[-0.35, 0, 1.0], [0, 0, 2.05]],
};

function buildSequence(p, key, slot, coreless) {
  const pl = PLANETS[key];
  const T = TRANSFORM;
  const base = { ...p.location };
  const f = flatDir(p);
  const r = rightOf(f);
  const dim = p.dimension;
  const at = (fw, rt, u) => ({ x: base.x + f.x * fw + r.x * rt, y: base.y + u, z: base.z + f.z * fw + r.z * rt });
  const hand = at(0.45, 0.38, 0.85);
  const coreAt = at(0.65, 0, 1.25);
  const head = at(0, 0, 1.62);
  const cam = settings(p).cam !== false;
  const c = pl.color, hot = white(pl.color, 0.45);
  const seq = { p, key, slot, coreless, age: 0, idx: 0, steps: [], formed: false, cam, done: false, dimId: dim.id };
  const add_ = (t, name, fn) => seq.steps.push([t, name, fn]);

  // カメラの位置がブロックに埋まるなら頭の方へ寄せる
  const camPos = (q) => {
    let s = q;
    for (let k = 0; k < 6 && blocked(dim, s); k++) s = lerp3(s, head, 0.25);
    return s;
  };
  const shot = (q, facing, ease) => { if (cam) camSet(p, camPos(q), facing, ease); };

  // ---- 0: コアが浮かぶ ------------------------------------------------------
  add_(T.core_rise, "core_rise", () => {
    freezePlayer(p, T.freeze);
    shot(at(3.4, 1.8, 1.9), at(0, 0, 1.1), 0);
    body(p, "henshin", "astro.pose");
    sound(dim, "astro.core_on", coreAt, 1.0, 1.0);
    sound(dim, "astro.core_ring", coreAt, 1.0, 0.8);
    title(p, `${pl.tc}CORE SYNC`, progressText(0), { fadeIn: 0, stay: T.freeze + 6, fadeOut: 6 });
    P(dim, "circle", { ...base, y: base.y + 0.05 }, { color: c, size: 1.6, life: 3.0, spin: 60 });
    P(dim, "scan", { ...base, y: base.y + 0.05 }, { color: c, size: 1.4, height: 2.1, life: 0.8 });
  });
  for (let t = 0; t <= 8; t += 2) {
    add_(t, "rise", () => {
      const q = lerp3(hand, coreAt, t / 8);
      P(dim, "glow", q, { color: white(c, 0.4), size: 0.7 + t * 0.06, life: 0.15 });
      P(dim, "ring", q, { color: c, size: 0.5 + t * 0.05, life: 0.18, rot: t * 20 });
      P(dim, "orbit", q, { color: hot, count: 3, spread: 0.4, life: 0.25, size: 0.4 });
    });
  }
  // ---- 8: ナノマシンの奔流 --------------------------------------------------
  add_(T.swarm_start, "swarm", () => {
    sound(dim, "astro.swarm", coreAt, 1.0, 1.0);
    P(dim, "vortex", { ...base, y: base.y + 0.1 }, { color: c, size: 1.4, life: 1.6, height: 2.2, spin: 240 });
    P(dim, "hex_circle", { ...base, y: base.y + 0.06 }, { color: hot, size: 2.0, life: 2.6, spin: -40 });
  });
  for (let t = T.swarm_start; t < T.suit_equip; t += 2) {
    add_(t, "spiral", () => {
      const a = (t - T.swarm_start) * 0.9;
      for (let k = 0; k < 3; k++) {
        const q = at(Math.cos(a + k * 2.1) * 0.7, Math.sin(a + k * 2.1) * 0.7, 0.3 + (t - T.swarm_start) * 0.25);
        swarm(dim, coreAt, q, c, { count: 6, life: 0.25 });
      }
      P(dim, "glow", coreAt, { color: white(c, 0.5), size: 0.9, life: 0.12 });
    });
  }
  // ---- カメラの周回 ---------------------------------------------------------
  const orbit = [[T.swarm_start, at(3.0, -2.2, 1.3)], [16, at(0.6, -3.0, 1.6)], [24, at(-3.0, 0, 2.2)], [32, at(0.5, 3.0, 1.4)]];
  for (const [t, q] of orbit) add_(t, "cam", () => shot(q, at(0, 0, 1.1), 0.4));
  add_(38, "cam", () => shot(at(1.25, 0.15, 1.67), head, 0.35));
  add_(48, "cam", () => shot(at(5.5, 0.6, 2.6), at(0, 0, 1.0), 0.3));
  add_(56, "fade", () => { if (cam) camFade(p, 0.15, 0.1, 0.35, white(c, 0.6)); });
  add_(T.camera_clear, "camera_clear", () => camClear(p));

  // ---- 進み具合（CORE SYNC n%） ---------------------------------------------
  for (let t = 2; t <= T.planet_burst - 2; t += 2) {
    add_(t, "progress", () => {
      try { p.onScreenDisplay.updateSubtitle(progressText(Math.min(100, Math.round(t / T.planet_burst * 100)))); } catch (_) { }
    });
  }
  // ---- 14: スーツを置く（組み上がり） -------------------------------------
  add_(T.suit_equip, "suit_equip", () => {
    const it = makeItem(pl.suitOn ?? pl.suit, LOCK_SLOT, true);
    // 0〜13 tick の間に頭へ着け直された防具は、上書きで消さずにしまい直す
    const worn = getEquip(p, "Head");
    if (it && worn && !isOurSuit(worn)) stowWorn(p, "Head", worn);
    if (it && setEquip(p, "Head", it)) cloak(p);
    else report("transform.suit_equip", new Error(`could not put ${pl.suitOn ?? pl.suit} on the head (item ${it ? "ok" : "missing"})`));
    sound(dim, "astro.armor_lock", p.location, 1.2, 0.6);
    P(dim, "scan", { ...base, y: base.y + 0.05 }, { color: hot, size: 1.6, height: 2.2, life: 1.8 });
  });
  for (const [part, sec] of Object.entries(ASSEMBLE_ORDER)) {
    const tp = T.suit_equip + Math.round(sec * 20);
    const spots = PART_POS[part] ?? [[0, 0, 1]];
    add_(Math.max(T.swarm_start, tp - 3), "stream", () => {
      for (const s of spots) swarm(dim, coreAt, at(...s), c, { count: 8, life: 0.15 });
    });
    add_(tp, "pop", () => {
      for (const s of spots) {
        const q = at(...s);
        P(dim, "nano", q, { color: white(c, 0.3), count: 8, spread: 0.25, life: 0.3, size: 0.4 });
        P(dim, "spark", q, { color: hot, count: 3, speed: 2, size: 0.5 });
      }
      sound(dim, "astro.assemble_click", at(...spots[0]), 0.9 + sec * 0.25, 0.8);
    });
  }
  add_(T.suit_equip + Math.round((ASSEMBLE_ORDER.helmet ?? 1.2) * 20), "lock", () => {
    sound(dim, "astro.armor_lock", head, 1.0, 1.0);
  });
  // ---- 40: コア → ナノウェポン --------------------------------------------
  add_(T.weapon_form, "weapon_form", () => {
    formWeapon(seq);
    sound(dim, "astro.weapon_form", hand, 1.0, 1.0);
    P(dim, "converge", hand, { color: hot, count: 14, spread: 1.2, life: 0.3 });
    P(dim, "flare", hand, { color: white(c, 0.5), size: 1.2, life: 0.2 });
    P(dim, "slash", hand, { color: c, size: 1.0, rot: 90, life: 0.25 });
  });
  // ---- 46: バイザー --------------------------------------------------------
  add_(T.visor_flash, "visor_flash", () => {
    sound(dim, "astro.visor_on", head, 1.0, 1.0);
    P(dim, "flare", at(0.28, 0, 1.65), { color: white(c, 0.6), size: 0.9, life: 0.25 });
    P(dim, "lens", at(0.3, 0, 1.65), { color: c, size: 0.5, life: 0.3 });
  });
  // ---- 50: 惑星の力が弾ける -----------------------------------------------
  add_(T.planet_burst - 2, "burst_sound", () => sound(dim, "astro.transform_burst", p.location, 1.0, 1.2));
  add_(T.planet_burst, "planet_burst", () => {
    title(p, `§r${glyph("banner.wingL", "")}${glyph(["emblemBig", key], pl.symbol)}${glyph("banner.wingR", "")}`,
      `§r${glyph("banner.lineL", "")}§r ${pl.tc}${pl.form_ja} §7| ${pl.tc}${pl.form_en} §r${glyph("banner.lineR", "")}`,
      { fadeIn: 0, stay: 40, fadeOut: 14 });
    P(dim, "flare", { ...base, y: base.y + 1.1 }, { color: white(c, 0.6), size: 1.6, life: 0.3 });
    P(dim, "shock_flat", { ...base, y: base.y + 0.06 }, { color: c, size: 2.2, life: 0.5 });
    shake(dim, base, 14, 0.35, 0.35);
    try {
      const ctx = makeCtx(p, key, "burst");
      moveImpl(key, "burst")?.(ctx);
    } catch (e) { report(`${key}.burst`, e); }
    // 周りのプレイヤーにもカットイン
    for (const o of allPlayers()) {
      if (o.id === p.id) continue;
      try {
        if (o.dimension.id !== dim.id || dist(o.location, base) > 24) continue;
        title(o, " ", `§r${glyph(["emblem", key], pl.symbol)}§r ${pl.tc}${p.name} §7— ${pl.form_ja}`, { fadeIn: 2, stay: 30, fadeOut: 10 });
      } catch (_) { }
    }
  });
  // ---- 52: 組み上がり → 装着中 ---------------------------------------------
  add_(STEADY_AT, "steady", () => steadySuit(p, key));
  // ---- 64: 操作が戻る ------------------------------------------------------
  add_(T.freeze, "unfreeze", () => finishSequence(seq));
  seq.steps.sort((a, b) => a[0] - b[0]);
  return seq;
}

function progressText(pct) {
  return `${progressBar(pct / 100, 20)} §f${pct}%`;
}

/** 頭の組み上がり中のスーツを装着中のスーツに差し替える。 */
function steadySuit(p, key) {
  const pl = PLANETS[key];
  const head = headItem(p);
  if (pl.suitOn && head?.typeId === pl.suitOn) {
    const it = makeItem(pl.suit, LOCK_SLOT, true);
    if (it) setEquip(p, "Head", it);
  }
}

/** 手のコア → ナノウェポン（同じスロット。動いていたら探し直す）。 */
function formWeapon(seq) {
  const { p, key } = seq;
  const pl = PLANETS[key];
  const inv = container(p);
  if (!inv) return;
  if (seq.coreless) {
    const i = firstEmpty(inv, selectedSlot(p));
    const it = markCoreless(makeItem(pl.weaponId, LOCK_INV, true));
    if (i >= 0 && it) { try { inv.setItem(i, it); } catch (_) { } }
    seq.formed = true;
    return;
  }
  let slot = -1;
  try { if (seq.slot >= 0 && inv.getItem(seq.slot)?.typeId === pl.core) slot = seq.slot; } catch (_) { }
  if (slot < 0) slot = findSlots(inv, (it) => it.typeId === pl.core && lockModeOf(it) === LOCK_SLOT)[0] ?? -1;
  if (slot < 0) slot = findSlots(inv, (it) => it.typeId === pl.core)[0] ?? -1;
  if (slot < 0) {
    // コアが無い（落とした等）: ウェポンは作らずに中止（増殖を防ぐ）
    report("transform", new Error("core vanished during the sequence"));
    seq.abort = true;
    return;
  }
  const w = makeItem(pl.weaponId, LOCK_INV, true);
  if (!w) { seq.abort = true; return; }
  try { inv.setItem(slot, w); seq.formed = true; seq.slot = slot; } catch (e) { report("transform.form", e); seq.abort = true; }
}

function finishSequence(seq) {
  const { p, key } = seq;
  const st = S(p);
  seq.done = true;
  seqs.delete(p.id);
  st.seq = null;
  setProp(p, PROP.seq, "");
  unfreeze(p);
  camClear(p);
  steadySuit(p, key);
  addRecord(p, "transforms", 1, key);
  clearBusy(p);
  save(p);
  BUS.emit("transformed", p, key);
  const pl = PLANETS[key];
  try { p.sendMessage?.(`${pl.tc}${pl.form_ja}§r 変身完了 §7（スニークしたまま 2 秒静止で解除）`); } catch (_) { }
}

function runSteps(seq) {
  while (seq.idx < seq.steps.length && seq.steps[seq.idx][0] <= seq.age) {
    const [, name, fn] = seq.steps[seq.idx++];
    try { fn(); } catch (e) { report(`transform.${name}`, e); }
    if (seq.abort) break;
  }
}

/** 毎 tick（main から）: 変身の時間割と、解除の分解の締め。 */
export function tickTransforms() {
  for (const [id, seq] of [...seqs]) {
    const p = seq.p;
    if (!valid(p)) { seqs.delete(id); continue; }   // 退出: 再参加の時に片付ける
    if (!alive(p)) continue;                        // 死亡: entityDie が片付ける
    let dimId = seq.dimId;
    try { dimId = p.dimension.id; } catch (_) { }
    if (dimId !== seq.dimId) {                      // 次元移動: 演出を打ち切って元に戻す
      seqs.delete(id);
      revert(p, "invalid", { instant: true });
      continue;
    }
    seq.age++;
    runSteps(seq);
    if (seq.abort) {
      seqs.delete(id);
      revert(p, "invalid", { instant: true });
      continue;
    }
    // 何かあっても必ず終わらせる
    if (!seq.done && seq.age > TRANSFORM.freeze + 40) finishSequence(seq);
  }
}

// ---------------------------------------------------------------------------
//  解除
// ---------------------------------------------------------------------------
/**
 * 変身を解く。どの段階（演出中・装着中・分解中・死亡後）からでも呼べる。
 * @param reason "manual" | "depleted" | "death" | "invalid" | "silent"
 * @param o      instant: true で分解アニメなしにすぐ外す
 * @returns 何か戻したら true
 */
export function revert(p, reason = "manual", o = {}) {
  if (!valid(p)) return false;
  const st = S(p);
  const head = headItem(p);
  const headKey = isOurSuit(head) ? SUIT_TO_PLANET[head.typeId] : null;
  const seqProp = getProp(p, PROP.seq, "");
  const key = st.form ?? st.seq?.key ?? (PLANETS[seqProp] ? seqProp : null) ?? headKey ?? st.deadForm;
  if (!key) {
    unfreeze(p); camClear(p);
    if (!headKey) uncloak(p);
    return false;
  }
  const pl = PLANETS[key];
  const seq = seqs.get(p.id) ?? st.seq;
  const formed = seq ? seq.formed : true;
  seqs.delete(p.id);
  if (seq) seq.done = true;
  st.seq = null;
  setProp(p, PROP.seq, "");
  st.gen++;
  unfreeze(p);
  camClear(p);
  // ウェポン → コア（死亡・再参加の後始末では、無くなったコアを作り直さない）
  const give_ = (reason === "manual" || reason === "depleted") && formed;
  weaponsToCores(p, key, give_);
  unlockCores(p);
  // 状態
  st.form = null;
  st.last = key;
  st.deadForm = null;
  st.coreless = false;
  st.barrierUntil = -1;
  st.revertHold = 0;
  st.passive = {};
  clearBusy(p);
  // このアドオンが掛けた効果だけを外す（同じ強さで、残りが掛け直しの長さ以下）。プレイヤーが自分で
  // 飲んだ薬・ビーコン・金リンゴの長い効果は残す
  for (const [id, amp] of pl.passive?.effects ?? []) removeOwnEffect(p, id, (id === "night_vision" ? 400 : 260) + 5, amp);
  removeOwnEffect(p, "levitation", 10);
  removeOwnEffect(p, "resistance", 200);
  resetMobility(p);
  clearShots(p.id);
  clearZones(p.id);
  bodyStop(p, "astro.pose");
  bodyStop(p, "astro.act");
  // スーツ
  const animated = !o.instant && (reason === "manual" || reason === "depleted") && headKey && head.typeId !== pl.suitOff;
  if (animated) {
    const it = makeItem(pl.suitOff, LOCK_SLOT, true);
    if (it) setEquip(p, "Head", it);
    st.offUntil = now() + OFF_TICKS;
    st.offKey = key;
  } else {
    if (headKey) setEquip(p, "Head", undefined);
    st.offUntil = -1;
    uncloak(p);
    restoreArmor(p);
  }
  if (reason !== "silent") revertFx(p, pl, reason);
  if (reason === "depleted") {
    setOverheat(p, COMMON.overheat_ticks);
    setEnergy(p, 0);
    effect(p, "weakness", COMMON.overheat_ticks, 0, true);
    effect(p, "slowness", Math.round(COMMON.overheat_ticks / 2), 0, true);
    sound(p.dimension, "astro.overheat", p.location, 1.0, 1.0);
    addRecord(p, "overheats", 1, key);
    title(p, `§r${glyph("iconBig.overheat", glyph("icon.overheat", "§c♨"))}`, "§cOVERHEAT §f星力切れ — 20 秒は再変身できない", { fadeIn: 2, stay: 40, fadeOut: 10 });
  }
  save(p);
  BUS.emit("reverted", p, key, reason);
  return true;
}

function revertFx(p, pl, reason) {
  const dim = p.dimension;
  const l = p.location;
  const f = flatDir(p);
  const hand = { x: l.x + f.x * 0.45 + rightOf(f).x * 0.38, y: l.y + 0.9, z: l.z + f.z * 0.45 + rightOf(f).z * 0.38 };
  if (reason !== "death") body(p, "revert", "astro.pose");
  sound(dim, "astro.revert", l, 1.0, 1.0);
  sound(dim, "astro.power_down", l, 1.0, 0.8);
  for (const part of ["helmet", "torso", "arms", "legs", "boots"]) {
    const s = PART_POS[part][0];
    const q = { x: l.x + f.x * s[0], y: l.y + s[2], z: l.z + f.z * s[0] };
    swarm(dim, q, hand, pl.color, { count: 8, life: 0.4 });
  }
  P(dim, "scan", { ...l, y: l.y + 0.05 }, { color: pl.color, size: 1.4, height: 2.1, life: 0.8 });
  P(dim, "smoke", { ...l, y: l.y + 1.0 }, { count: 6, spread: 0.5, size: 1.0 });
  P(dim, "glow", hand, { color: white(pl.color, 0.5), size: 0.9, life: 0.6 });
  if (reason === "manual") {
    try { p.sendMessage?.(`§7${pl.form_ja} 解除`); } catch (_) { }
  }
}

/** 分解中のスーツを外す（毎 tick）。 */
export function tickOff() {
  for (const p of allPlayers()) {
    const st = S(p);
    if (st.offUntil < 0 || st.offUntil > now()) continue;
    finishOff(p);
  }
}

function finishOff(p) {
  const st = S(p);
  st.offUntil = -1;
  const head = headItem(p);
  if (isOurSuit(head) && !st.form) setEquip(p, "Head", undefined);
  if (!isOurSuit(headItem(p))) uncloak(p);
  restoreArmor(p);
  st.offKey = null;
}

// ---------------------------------------------------------------------------
//  保険の掃除（毎秒）
// ---------------------------------------------------------------------------
export function sweep(p) {
  const st = S(p);
  if (st.seq || seqs.has(p.id) || !alive(p)) return;
  const inv = container(p);
  const head = headItem(p);
  const headKey = isOurSuit(head) ? SUIT_TO_PLANET[head.typeId] : null;
  // 見張り: 演出中でないのに入力ロック／カメラの印が残っている
  if (getProp(p, PROP.frozen, false) === true) unfreeze(p);
  if (getProp(p, PROP.cam, false) === true) camClear(p);
  if (st.form) {
    const pl = PLANETS[st.form];
    if (headKey !== st.form || head.typeId === pl.suitOff) {
      report("transform.sweep", new Error(`form ${st.form} but head holds ${head?.typeId ?? "nothing"}: reverting`));
      revert(p, "invalid", { instant: true });
      return;
    }
    if (pl.suitOn && head.typeId === pl.suitOn) steadySuit(p, st.form);
    // 変身中は胴・脚・足の防具を着けられない（§2.3。スーツの防御点と重ねない）→ 外して退避の記録に足す
    let stowed = 0;
    for (const slot of ARMOR_SLOTS) {
      if (slot === "Head") continue;
      const it = getEquip(p, slot);
      if (it && !STOW_EXEMPT.has(it.typeId) && stowWorn(p, slot, it)) stowed++;
    }
    if (stowed) announce(p, "§7変身中は防具を着けられない §8（解除で着せ直す）", 30);
    // 別の形態のウェポン → それぞれのコア／自分のウェポンの 2 本目以降は消す
    let mine = 0;
    for (const i of findSlots(inv, (it) => !!WEAPON_TO_PLANET[it.typeId])) {
      try {
        const it = inv.getItem(i);
        const k = WEAPON_TO_PLANET[it.typeId];
        if (k === st.form) { if (mine++ > 0) inv.setItem(i, undefined); continue; }
        inv.setItem(i, isCoreless(it) ? undefined : makeItem(PLANETS[k].core, LOCK_NONE, false));
      } catch (_) { }
    }
    return;
  }
  // 変身していない
  if (headKey && !(st.offUntil > now())) { setEquip(p, "Head", undefined); uncloak(p); }
  for (const i of findSlots(inv, (it) => !!WEAPON_TO_PLANET[it.typeId] || isOurSuit(it))) {
    try {
      const it = inv.getItem(i);
      const k = WEAPON_TO_PLANET[it.typeId];
      inv.setItem(i, k && !isCoreless(it) ? makeItem(PLANETS[k].core, LOCK_NONE, false) : undefined);
    } catch (_) { }
  }
  const off = getEquip(p, "Offhand");
  if (off && (WEAPON_TO_PLANET[off.typeId] || isOurSuit(off))) {
    const k = WEAPON_TO_PLANET[off.typeId];
    setEquip(p, "Offhand", k && !isCoreless(off) ? makeItem(PLANETS[k].core, LOCK_NONE, false) : undefined);
  }
  unlockCores(p);
  if (!(st.offUntil > now()) && !isOurSuit(headItem(p)) && getProp(p, PROP.armor, undefined)) restoreArmor(p);
}

/** 地面に落ちたウェポン・スーツ（item エンティティ）を直す。直したら true。 */
export function fixDroppedItem(e) {
  try {
    if (!valid(e) || e.typeId !== "minecraft:item") return false;
    const it = e.getComponent("minecraft:item")?.itemStack;
    if (!it) return false;
    const wk = WEAPON_TO_PLANET[it.typeId];
    if (wk) {
      const loc = { ...e.location };
      const dim = e.dimension;
      const free = isCoreless(it);
      e.remove();
      if (!free) {
        const core = makeItem(PLANETS[wk].core, LOCK_NONE, false);
        if (core) dim.spawnItem(core, loc);
      }
      return true;
    }
    if (SUIT_TO_PLANET[it.typeId]) { e.remove(); return true; }
  } catch (_) { }
  return false;
}

/** プレイヤーの周りの落ちたアイテムを調べる（毎秒）。 */
export function sweepDropped(p, radius = 16) {
  let list = [];
  try { list = p.dimension.getEntities({ type: "minecraft:item", location: p.location, maxDistance: radius }); } catch (_) { }
  for (const e of list) fixDroppedItem(e);
}

// ---------------------------------------------------------------------------
//  星力（毎秒）
// ---------------------------------------------------------------------------
export function tickEnergy(p) {
  const st = S(p);
  if (st.seq) return;
  if (st.form) {
    st.energy = Math.max(0, st.energy - COMMON.energy_drain);
    st.records.ticks = (st.records.ticks ?? 0) + 20;
    st.dirty = true;
    if (st.energy <= 0) revert(p, "depleted");
    return;
  }
  if (st.overheat > 0) {
    st.overheat = Math.max(0, st.overheat - 20);
    st.dirty = true;
    if (st.overheat === 0 && valid(p)) {
      sound(p.dimension, "astro.core_ring", p.location, 1.2, 0.6);
      announce(p, "§bオーバーヒート解除 §7— 再び変身できる", 40);
    }
  }
  if (st.energy < maxEnergy(p)) setEnergy(p, st.energy + COMMON.energy_regen);
}

// ---------------------------------------------------------------------------
//  死亡・リスポーン・再参加・再読み込み
// ---------------------------------------------------------------------------
/** 変身中（演出中を含む）に死んだ。リスポーンで解除する印を付ける。 */
export function onDeath(p) {
  const st = S(p);
  const key = st.form ?? st.seq?.key;
  addRecord(p, "deaths", 1);
  if (!key) return;
  const seq = seqs.get(p.id);
  seqs.delete(p.id);
  if (seq) seq.done = true;
  st.seq = null;
  setProp(p, PROP.seq, "");
  st.gen++;
  camClear(p, true);
  unfreeze(p);
  st.deadForm = key;
  st.form = null;
  // keepOnDeath で残ったウェポンは、その場でコアに戻す（リスポーン後もコアが手元に残る）
  const pl = PLANETS[key];
  const inv = container(p);
  for (const i of findSlots(inv, (it) => it.typeId === pl.weaponId)) {
    try { inv.setItem(i, st.coreless ? undefined : makeItem(pl.core, LOCK_NONE, true)); } catch (_) { }
    break;
  }
  clearShots(p.id);
  clearZones(p.id);
  save(p);
}

/** playerSpawn から。initial = 参加した時。 */
export function onSpawn(p, initial) {
  const st = S(p);
  // カメラと入力ロックは印があれば必ず戻す（/reload やエラーを越えて残るため）
  camClear(p);
  unfreeze(p);
  if (initial) { restoreOnJoin(p); return; }
  if (st.deadForm) revert(p, "death", { instant: true });
}

/** 再参加・再読み込みの後で状態を合わせる。 */
export function restoreOnJoin(p) {
  const st = S(p);
  camClear(p);
  unfreeze(p);
  const seqKey = getProp(p, PROP.seq, "");
  if (PLANETS[seqKey]) {
    // 演出の途中で抜けた: きれいに解除して最初からやり直せるようにする
    revert(p, "silent", { instant: true });
    return;
  }
  if (st.deadForm) { revert(p, "death", { instant: true }); return; }
  const head = headItem(p);
  const headKey = isOurSuit(head) ? SUIT_TO_PLANET[head.typeId] : null;
  if (headKey) {
    const pl = PLANETS[headKey];
    if (head.typeId === pl.suitOff) {
      st.form = null;
      finishOff(p);
      return;
    }
    // スーツが頭にある → 変身中として戻す
    st.form = headKey;
    st.last = headKey;
    st.gen++;
    if (head.typeId === pl.suitOn) steadySuit(p, headKey);
    if (energy(p) <= 0) setEnergy(p, 1);
    cloak(p);
    save(p);
    BUS.emit("transformed", p, headKey);
    try { p.sendMessage?.(`${pl.tc}${pl.form_ja}§r の変身状態を復元した`); } catch (_) { }
    return;
  }
  if (st.form) revert(p, "silent", { instant: true });
  uncloak(p);
}

/** スクリプトの読み込み直後: いるプレイヤー全員の後始末。 */
export function startupCleanup() {
  for (const p of allPlayers()) {
    try { restoreOnJoin(p); } catch (e) { report("transform.startup", e); }
  }
}

export function forgetTransform(id) { seqs.delete(id); }
export function sequenceOf(p) { return seqs.get(p.id); }

export { world };
