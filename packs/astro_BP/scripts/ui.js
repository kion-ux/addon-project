// ===========================================================================
//  星核ターミナル（server-ui）— DESIGN §2.6
//   トップ: 状態 / 惑星図鑑 / 変身解除（変身中のみ）/ 設定 / 操作説明 / 記録
//   惑星図鑑: 9 形態（紋章アイコン textures/ui/astro/emblem_<key>）→ 形態ページ
//   設定（ModalForm）: 変身カメラ演出・HUD・演出の量・ダメージ数字（プレイヤーごとに保存）
//  フォームは UserBusy の間 1 秒おきに数回やり直す。Promise の失敗は全部ここで受け止める。
// ===========================================================================
import { system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import {
  COMMON, PLANETS, PLANET_KEYS, MOVE_KINDS, MOVE_LABEL, MOVE_INPUT, CORE_TO_PLANET, ADDON,
} from "./data.js";
import {
  S, level, xpOf, nextLevelXp, maxEnergy, settings, setSettings, records, FX_LEVELS,
} from "./state.js";
import { glyph, sound } from "./fx.js";
import { revert } from "./transform.js";
import { container, findSlots, valid, report, BUS } from "./util.js";

const wait = (t) => new Promise((r) => system.runTimeout(r, t));

/** フォームを出す。UserBusy なら 1 秒おきに tries 回まで。閉じられたら undefined。 */
export async function show(form, p, tries = 6) {
  for (let i = 0; i < tries; i++) {
    if (!valid(p)) return undefined;
    let res;
    try { res = await form.show(p); } catch (_) { return undefined; }
    if (res?.cancelationReason === "UserBusy") { await wait(20); continue; }
    return res;
  }
  return undefined;
}

const open = new Set();   // フォームを開いている（開こうとしている）プレイヤー

function run(page, p, ...args) {
  if (open.has(p.id)) return;          // 押しっぱなしで何枚も重ねて開かない
  open.add(p.id);
  const done = () => open.delete(p.id);
  try {
    const r = page(p, ...args);
    if (r && typeof r.then === "function") r.then(done, (e) => { done(); report("ui", e); });
    else done();
  } catch (e) { done(); report("ui", e); }
}

export function forgetUi(id) { open.delete(id); }

function click(p) { sound(p.dimension, "astro.ui_select", p.location, 1.0, 0.6); }
function back(p) { sound(p.dimension, "astro.ui_back", p.location, 1.0, 0.6); }

function emblemIcon(key) { return `textures/ui/astro/emblem_${key}`; }
/** トップのボタンの絵（status / codex / revert / settings / guide / records / back。gen_astro_ui が描く）。 */
function uiIcon(name) { return `textures/ui/astro/${name}`; }

// ---------------------------------------------------------------------------
//  トップ
// ---------------------------------------------------------------------------
function statusText(p) {
  const st = S(p);
  const lines = [];
  if (st.form) {
    const pl = PLANETS[st.form];
    lines.push(`§r${glyph(["emblem", st.form], pl.symbol)}§r ${pl.tc}${pl.form_ja}§r §7（${pl.suit_ja}）`);
    lines.push(`§7同調率 §bLv${level(p, st.form)}`);
  } else {
    lines.push("§7変身していない");
  }
  lines.push(`§r${glyph("icon.energy", "")}§r §e星力 §f${Math.floor(st.energy)} / ${maxEnergy(p)}`);
  lines.push(`§r${glyph("icon.nova", "")}§r §6超新星ゲージ §f${Math.floor(st.nova)}%`);
  if (st.overheat > 0) lines.push(`§r${glyph("icon.overheat", "")}§r §cオーバーヒート §fあと ${(st.overheat / 20).toFixed(1)} 秒`);
  return lines.join("\n");
}

/** ターミナルを開く（astro:terminal を右クリック）。 */
export function openTerminal(p) {
  if (open.has(p.id)) return;
  sound(p.dimension, "astro.ui_open", p.location, 1.0, 0.7);
  run(top, p);
}

async function top(p) {
  const st = S(p);
  const items = [["惑星図鑑", planetList, "codex"]];
  if (st.form) items.push(["§c変身解除", doRevert, "revert"]);
  items.push(["設定", settingsPage, "settings"], ["操作説明", controlsPage, "guide"], ["記録", recordsPage, "records"]);
  const form = new ActionFormData()
    .title(`${ADDON.ja} 星核ターミナル`)
    .body(statusText(p));
  for (const [label, , icon] of items) form.button(label, uiIcon(icon));
  const res = await show(form, p);
  if (!res || res.canceled || res.selection === undefined) return;
  const pick = items[res.selection];
  if (!pick) return;
  click(p);
  await pick[1](p);
}

async function doRevert(p) {
  if (!S(p).form) return;
  revert(p, "manual");
}

// ---------------------------------------------------------------------------
//  惑星図鑑
// ---------------------------------------------------------------------------
/** そのコアの場所（持っていなければ null）。 */
export function coreWhere(p, key) {
  const pl = PLANETS[key];
  const st = S(p);
  if (st.form === key) return "変身中（ナノウェポン）";
  const inv = container(p);
  const slots = findSlots(inv, (it) => it.typeId === pl.core);
  if (!slots.length) return null;
  const i = slots[0];
  return i < 9 ? `ホットバー ${i + 1}` : `インベントリ ${i - 8}`;
}

async function planetList(p) {
  const form = new ActionFormData()
    .title("惑星図鑑")
    .body("§79 つの星核と、それぞれの形態。コアを持って右クリックで変身する。");
  for (const key of PLANET_KEYS) {
    const pl = PLANETS[key];
    const where = coreWhere(p, key);
    form.button(`${pl.tc}${pl.ja} ${pl.form_ja}\n§8${where ? "所持" : "未入手"}  Lv${level(p, key)}`, emblemIcon(key));
  }
  form.button("§7戻る", uiIcon("back"));
  const res = await show(form, p);
  if (!res || res.canceled || res.selection === undefined) return;
  if (res.selection >= PLANET_KEYS.length) { back(p); await top(p); return; }
  click(p);
  await planetPage(p, PLANET_KEYS[res.selection]);
}

export function planetText(p, key) {
  const pl = PLANETS[key];
  const lv = level(p, key);
  const xp = xpOf(p, key);
  const nx = nextLevelXp(p, key);
  const where = coreWhere(p, key);
  const L = [];
  L.push(`§r${glyph(["emblemBig", key], pl.symbol)}§r`);
  L.push(`${pl.tc}${pl.ja} ${pl.symbol} ${pl.form_ja} §7/ ${pl.form_en}`);
  L.push(`§7${pl.suit_ja} ・ ${pl.weapon.ja}`);
  L.push("");
  L.push(`§f${pl.motif}`);
  L.push("");
  L.push(`§e防御 §f${pl.defense}  §e攻撃 §f${pl.damage}  §e空中ジャンプ §f${pl.mobility.air_jumps}  §eブースト §f${pl.mobility.air_dash}`);
  L.push(`§6パッシブ §f${pl.passive.ja}`);
  L.push("");
  for (const kind of MOVE_KINDS) {
    const mv = pl.moves[kind];
    const cd = (mv.cd / 20).toFixed(1);
    const cost = mv.cost ? ` §e星力 ${mv.cost}` : "";
    L.push(`§r${glyph(["move", key, kind, "ready"], "")}§r ${pl.tc}${MOVE_LABEL[kind]}「${mv.ja}」§r §8${mv.en}`);
    L.push(`  §7${MOVE_INPUT[kind]} ・ 再使用 ${cd} 秒${cost}`);
    L.push(`  §f${mv.desc}`);
  }
  L.push(`§r ${pl.tc}三段目「${pl.combo3.ja}」§r §f${pl.combo3.desc}`);
  L.push("");
  L.push(`§b同調率 Lv${lv}§r §7XP ${Math.floor(xp)}${nx ? ` / ${nx[1]}` : "（最大）"}`);
  L.push(`§7与ダメージ +${Math.round(COMMON.sync_damage_per_level * (lv - 1) * 100)}% ・ 最大星力 ${maxEnergy(p, key)} ・ 再使用 -${Math.round(COMMON.sync_cd_per_level * (lv - 1) * 100)}%`);
  L.push(where ? `§aコア: ${where}` : "§8コア: 持っていない");
  return L.join("\n");
}

async function planetPage(p, key) {
  const pl = PLANETS[key];
  const form = new ActionFormData()
    .title(`${pl.ja} ${pl.form_ja}`)
    .body(planetText(p, key))
    .button("§7図鑑へ戻る", emblemIcon(key))
    .button("§7閉じる", uiIcon("back"));
  const res = await show(form, p);
  if (!res || res.canceled) return;
  if (res.selection === 0) { back(p); await planetList(p); }
}

// ---------------------------------------------------------------------------
//  設定
// ---------------------------------------------------------------------------
async function settingsPage(p) {
  const s = settings(p);
  const form = new ModalFormData()
    .title("設定")
    .toggle("変身カメラ演出", s.cam !== false)
    .toggle("HUD 表示", s.hud !== false)
    .dropdown("演出の量（パーティクル）", FX_LEVELS, s.fx ?? 1)
    .toggle("ダメージ数字", s.dmg !== false);
  const res = await show(form, p);
  if (!res || res.canceled || !Array.isArray(res.formValues)) return;
  const [cam, hud, fx, dmg] = res.formValues;
  setSettings(p, { cam: cam !== false, hud: hud !== false, fx: Number(fx) || 0, dmg: dmg !== false });
  click(p);
  try { p.sendMessage?.(`§b設定を保存した §7（カメラ ${cam ? "ON" : "OFF"} / HUD ${hud ? "ON" : "OFF"} / 演出 ${FX_LEVELS[Number(fx) || 0]} / 数字 ${dmg ? "ON" : "OFF"}）`); } catch (_) { }
  BUS.emit("settings", p);
}

// ---------------------------------------------------------------------------
//  操作説明・記録
// ---------------------------------------------------------------------------
export const CONTROLS = [
  "§6■ 変身",
  "§f惑星コアを持って右クリック §7… 変身（約 3 秒。星力 30 以上が必要、オーバーヒート中は不可）",
  "§fスニークしたまま 2 秒静止 §7… 変身解除（HUD に進み具合）",
  "§7変身すると防具はインベントリにしまわれ、解除で着せ直される",
  "",
  "§6■ 攻撃（ナノウェポンを持って）",
  "§f攻撃 §7… 三段コンボ（1.3 秒あくと 1 段目へ）。三段目は惑星ごとの追撃",
  "§f右クリック §7… 惑星技",
  "§fダッシュ中に右クリック §7… 機動技",
  "§f空中で右クリック §7… 空中技",
  "§fスニーク＋右クリック §7… 超新星ゲージ 100% で必殺技、未満ならナノ・バリア（0.7 秒ほぼ無敵）",
  "",
  "§6■ スラスター機動（変身中）",
  "§f空中でジャンプ §7… 二段ジャンプ（形態ごとに回数）",
  "§f空中でジャンプ長押し §7… ホバー（星力を消費。離すとゆっくり降下、スニークで降りる）",
  "§f空中でスニーク §7… ブースト・ダッシュ",
  "§f地上でスニークを素早く 2 回 §7… 回避ステップ（直後は無敵。そこで攻撃を受けるとジャスト回避）",
  "§fダッシュ §7… 加速と足元の噴射。機動の後の落下ダメージは無効",
  "",
  "§6■ ゲージ",
  "§e星力 §7… 変身中は毎秒少し減り、技・ホバーで減る。0 で強制解除＋オーバーヒート 20 秒",
  "§6超新星ゲージ §7… 攻撃を当てる・被弾・ジャスト回避で溜まる。100% で必殺技",
  "§b同調率 §7… 形態ごと。命中と撃破で上がり、与ダメージ・最大星力・再使用短縮が伸びる",
];

async function controlsPage(p) {
  const form = new ActionFormData()
    .title("操作説明")
    .body(CONTROLS.join("\n"))
    .button("§7戻る", uiIcon("back"));
  const res = await show(form, p);
  if (res && !res.canceled && res.selection === 0) { back(p); await top(p); }
}

export function recordsText(p) {
  const r = records(p);
  const L = [
    `§f撃破 §e${r.kills ?? 0}`,
    `§f変身 §e${r.transforms ?? 0}  §f技 §e${r.moves ?? 0}  §f必殺 §e${r.ults ?? 0}`,
    `§fジャスト回避 §e${r.justDodges ?? 0}  §f最大の一撃 §e${r.maxHit ?? 0}`,
    `§f変身していた時間 §e${Math.floor((r.ticks ?? 0) / 20 / 60)} 分`,
    `§fオーバーヒート §e${r.overheats ?? 0}  §f戦闘不能 §e${r.deaths ?? 0}`,
    "",
    "§6■ 同調率",
  ];
  for (const key of PLANET_KEYS) {
    const pl = PLANETS[key];
    const pp = r.perPlanet?.[key] ?? {};
    L.push(`§r${glyph(["emblem", key], pl.symbol)}§r ${pl.tc}${pl.form_ja}§r §bLv${level(p, key)} §7XP ${Math.floor(xpOf(p, key))} ・ 撃破 ${pp.kills ?? 0} ・ 技 ${pp.moves ?? 0}`);
  }
  return L.join("\n");
}

async function recordsPage(p) {
  const form = new ActionFormData()
    .title("記録")
    .body(recordsText(p))
    .button("§7戻る", uiIcon("back"));
  const res = await show(form, p);
  if (res && !res.canceled && res.selection === 0) { back(p); await top(p); }
}

export { CORE_TO_PLANET };
