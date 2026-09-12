// 状態 / ゲーム状態と見た目の同期
//
// 企画書 §13 の層分けをそのまま守る。ここが「正しい状態」を決め、
// 見た目（アタッチャブル）はその状態を受けて再生されるだけ。
//
//   normal → transforming → active → attacking → recovering → active
//   解除時は reverting → normal、異常時は safe_reset → normal
//
// 企画書 §14 で最優先に挙がっている「変身すると本体が透明で、エフェクトだけ出る」
// を防ぐため、透明化は "形態アイテムが実際に頭スロットに載っている間だけ" 掛ける。
// アイテムが何かの理由で消えたら、次の tick で透明も外れる。
import { world, system, ItemStack, EquipmentSlot } from "@minecraft/server";
import {
  PROP, PHASES, FORMS, FORM_BY_KEY, FORM_ORDER, FORM_ITEMS, TAG_ACTIVE,
  ENERGY_MAX, ENERGY_REGEN, ENERGY_REGEN_IDLE, LOW_ENERGY, DEFAULTS,
  SHOWPIECE, SHOWPIECE_TICKS, SHOWPIECE_SHORT_TICKS, TECHS_BY_FORM, TECHS,
} from "./data.js";
import {
  tr, tell, actionbar, title, num, bool, str, setProp, allPlayers, bar,
  later, onForget, clamp, cooldownLeft,
} from "./util.js";
import {
  makeContext, playStage, playSfx, shake, spawn, claimBigFx, releaseBigFx,
} from "./fx.js";

const ARMOR_SLOTS = [
  EquipmentSlot.Head, EquipmentSlot.Chest, EquipmentSlot.Legs, EquipmentSlot.Feet,
];

/** 形態ごとの効果は毎秒掛け直す。切れ目を作らないよう寿命は少し長めに取る。 */
const EFFECT_TICKS = 140;

/** 形態を一目で分からせる常在演出。技の演出とは別に、薄く出し続ける。
 *  企画書 §06「効果が消えても形態が分かる」の裏返しで、静止中でも形態が読める。 */
const AMBIENT = {
  gear2: "gla:steam_idle",
  gear3: null,
  gear4_bound: "gla:haki_idle",
  gear4_snake: "gla:haki_idle",
  gear5: "gla:cloud_idle",
  normal: null,
};

// 演出中のタイマーなど「保存してはいけない」状態はここに置く。
// 企画書 §13 保存用と描画用を分ける。
const runtime = new Map();       // playerId -> {showpiece, busyUntil, lastFight}

function rt(player) {
  let r = runtime.get(player.id);
  if (!r) {
    r = { showpiece: null, cast: null, busyUntil: 0, lastFight: 0 };
    runtime.set(player.id, r);
  }
  return r;
}

// ---------------------------------------------------------------------------
//  発動ごとの印
//
//  技は windup / active / recover を tick 予約で進める。予約は取り消せないので、
//  「この予約は今も自分のものか」を印で確かめる。これが無いと、長い技
//  （巨人化は 430 tick 予約する）の予約が、後から出した別の技の phase を
//  勝手に書き換えてしまう。
//  企画書 §14 の復旧が「予約された技処理」を解除することを求めているのは
//  まさにこれ。safeReset は印を捨てるので、以後の予約はすべて空振りする。
// ---------------------------------------------------------------------------
export function beginCast(player) {
  const token = Symbol("cast");
  rt(player).cast = token;
  return token;
}

export function castIs(player, token) {
  return runtime.get(player.id)?.cast === token;
}

export function endCast(player, token) {
  const r = runtime.get(player.id);
  if (r && r.cast === token) r.cast = null;
}

onForget((id) => { runtime.delete(id); releaseBigFx(id); });

// ---------------------------------------------------------------------------
//  読み書き
// ---------------------------------------------------------------------------
export function hasPower(player) {
  return bool(player, PROP.power, false);
}

export function phase(player) {
  const p = str(player, PROP.phase, "normal");
  return PHASES.includes(p) ? p : "normal";
}

export function setPhase(player, next) {
  if (!PHASES.includes(next)) return;
  setProp(player, PROP.phase, next);
}

export function formKey(player) {
  const f = str(player, PROP.form, "");
  return FORM_BY_KEY[f] ? f : "";
}

export function currentForm(player) {
  const k = formKey(player);
  return k ? FORM_BY_KEY[k] : null;
}

export function isTransformed(player) {
  return !!formKey(player) && phase(player) !== "normal";
}

export function energy(player) {
  return num(player, PROP.energy, ENERGY_MAX);
}

export function setEnergy(player, v) {
  setProp(player, PROP.energy, clamp(v, 0, ENERGY_MAX));
}

export function infinite(player) {
  return bool(player, PROP.infinite, DEFAULTS.infinite);
}

export function quality(player) {
  return str(player, PROP.quality, DEFAULTS.quality);
}

export function shortFx(player) {
  return bool(player, PROP.shortfx, DEFAULTS.shortfx);
}

export function cameraFx(player) {
  return bool(player, PROP.camerafx, DEFAULTS.camerafx);
}

export function hits(player) {
  return num(player, PROP.hits, 0);
}

export function addHits(player, n = 1) {
  const before = hits(player);
  const after = before + n;
  setProp(player, PROP.hits, after);
  // 解放の瞬間だけ知らせる。毎回の命中では何も出さない。
  for (const f of FORMS) {
    if (f.unlock > before && f.unlock <= after) {
      tell(player, tr("gla.msg.unlocked", ""));
      tell(player, { rawtext: [{ translate: "gla.msg.unlocked_form" },
                               { text: " §e" }, { translate: f.name }] });
      try {
        spawn(player.dimension, "gla:unlock_spark",
              { x: player.location.x, y: player.location.y + 1.2, z: player.location.z });
      } catch (_) { }
    }
  }
}

export function unlocked(player, key) {
  const f = FORM_BY_KEY[key];
  if (!f) return false;
  return hits(player) >= f.unlock;
}

/** 素の「使う」で入る形態。前に使っていたものを覚えておく。 */
export function preferredForm(player) {
  const last = str(player, PROP.lastform, "");
  if (last && FORM_BY_KEY[last] && unlocked(player, last)) return last;
  return FORM_ORDER[0];
}

/** 看板演出が走っているか。入力側がスキップを出し分けるために使う。 */
export function inShowpiece(player) {
  return !!runtime.get(player.id)?.showpiece;
}

export function unlockedForms(player) {
  return FORM_ORDER.filter((k) => unlocked(player, k));
}

// ---------------------------------------------------------------------------
//  選択中の技（形態ごとに別々に覚える）
// ---------------------------------------------------------------------------
export function techIndex(player, form) {
  let map = {};
  try { map = JSON.parse(str(player, PROP.tech, "{}")) ?? {}; } catch (_) { map = {}; }
  const list = TECHS_BY_FORM[form] ?? [];
  if (!list.length) return 0;
  const raw = Number(map[form] ?? 0);
  return ((Math.trunc(raw) % list.length) + list.length) % list.length;
}

export function setTechIndex(player, form, index) {
  let map = {};
  try { map = JSON.parse(str(player, PROP.tech, "{}")) ?? {}; } catch (_) { map = {}; }
  map[form] = index;
  setProp(player, PROP.tech, JSON.stringify(map));
}

export function selectedTech(player) {
  const form = formKey(player);
  if (!form) return null;
  const list = TECHS_BY_FORM[form] ?? [];
  if (!list.length) return null;
  return list[techIndex(player, form)];
}

// ---------------------------------------------------------------------------
//  インベントリ（企画書 §14 アイテム増殖を防ぐ構造）
//
//  形態アイテムは「装備する／外す」だけで、配布処理を一切通らない。
//  消費して配り直す循環も作らない。
// ---------------------------------------------------------------------------
export function container(player) {
  try { return player.getComponent("minecraft:inventory")?.container; } catch (_) { return undefined; }
}

function equippable(player) {
  try { return player.getComponent("minecraft:equippable"); } catch (_) { return undefined; }
}

function wearingFormItem(player) {
  const eq = equippable(player);
  if (!eq) return "";
  try {
    const head = eq.getEquipment(EquipmentSlot.Head);
    const id = head?.typeId ?? "";
    return FORM_ITEMS.includes(id) ? id : "";
  } catch (_) { return ""; }
}

function wearFormItem(player, itemId) {
  const eq = equippable(player);
  if (!eq) return false;
  try {
    eq.setEquipment(EquipmentSlot.Head, new ItemStack(itemId, 1));
    return true;
  } catch (_) { return false; }
}

function removeFormItem(player) {
  const eq = equippable(player);
  if (!eq) return;
  try {
    const head = eq.getEquipment(EquipmentSlot.Head);
    if (head && FORM_ITEMS.includes(head.typeId)) {
      eq.setEquipment(EquipmentSlot.Head, undefined);
    }
  } catch (_) { }
}

/**
 * 変身中は普段の兜をしまう。戻すときに同じものを探して着せ直す。
 *
 * しまえなかったら false を返し、呼び出し側は変身をやめる。ここで「入らな
 * かったけど被せたまま進む」を選ぶと、直後の wearFormItem が頭スロットを
 * 上書きして兜が消える — 企画書 §17 QA-03「意図しない消失がない」に反する。
 */
function stashArmor(player) {
  const eq = equippable(player);
  const inv = container(player);
  if (!eq || !inv) return true;
  let worn;
  try { worn = eq.getEquipment(EquipmentSlot.Head); } catch (_) { return true; }
  if (!worn || FORM_ITEMS.includes(worn.typeId)) return true;
  const left = inv.addItem(worn);
  if (left) return false;                 // 持ち物がいっぱい。変身しない。
  try { eq.setEquipment(EquipmentSlot.Head, undefined); } catch (_) { return false; }
  setProp(player, PROP.stored_armor, worn.typeId);
  return true;
}

function restoreArmor(player) {
  const id = str(player, PROP.stored_armor, "");
  if (!id) return;
  setProp(player, PROP.stored_armor, "");
  const eq = equippable(player);
  const inv = container(player);
  if (!eq || !inv) return;
  try { if (eq.getEquipment(EquipmentSlot.Head)) return; } catch (_) { return; }
  for (let slot = 0; slot < inv.size; slot++) {
    const item = inv.getItem(slot);
    if (item?.typeId !== id) continue;
    try {
      eq.setEquipment(EquipmentSlot.Head, item);
      inv.setItem(slot, undefined);
    } catch (_) { }
    return;
  }
}

/**
 * 手に持っている特定のアイテムを1つ減らす。
 *
 * 悪魔の実は食べたら消えるべきだが、消費と配布を同じ処理にすると
 * 企画書 §14 が禁じている「使用時に消費して再配布する循環」になる。
 * ここは **減らすだけ** で、代わりに何も渡さない。
 */
export function consumeHeld(player, typeId) {
  const inv = container(player);
  if (!inv) return false;
  let slot;
  try {
    slot = typeof player.selectedSlotIndex === "number"
      ? player.selectedSlotIndex : (player.selectedSlot ?? 0);
  } catch (_) { slot = 0; }
  const item = inv.getItem(slot);
  if (item?.typeId !== typeId) return false;
  try {
    if (item.amount > 1) { item.amount -= 1; inv.setItem(slot, item); }
    else inv.setItem(slot, undefined);
  } catch (_) { return false; }
  return true;
}

/**
 * 形態表示体の後始末。
 *
 * 表示体は頭スロットに載っているだけで全身が描かれるので、変身していない
 * プレイヤーが被っていると「自分の体＋もう一体」の二重表示になる
 * （企画書 §14 が禁じているもの）。持ち物だけでなく **頭スロットも** 見る。
 * 変身中でも、いま選んでいる形態と食い違う表示体なら外す。
 */
export function sweepFormItems(player) {
  const form = currentForm(player);
  const eq = equippable(player);
  if (eq) {
    try {
      const head = eq.getEquipment(EquipmentSlot.Head);
      if (head && FORM_ITEMS.includes(head.typeId)
          && (!form || head.typeId !== form.item)) {
        eq.setEquipment(EquipmentSlot.Head, undefined);
      }
    } catch (_) { }
  }
  if (form) return;               // 変身中は持ち物の掃除まではしない
  const inv = container(player);
  if (!inv) return;
  for (let i = 0; i < inv.size; i++) {
    const it = inv.getItem(i);
    if (it && FORM_ITEMS.includes(it.typeId)) inv.setItem(i, undefined);
  }
}

/**
 * 地面に落ちた形態表示体を拾って消す。
 *
 * keep_on_death と上の掃除で漏れ口はほぼ塞がっているが、他のパックや
 * コマンドで世界に出ることはありうる。1つでも残ると変身のたびに増えるので、
 * プレイヤーの近くだけを定期的に見る（全ディメンション走査はしない）。
 */
export function sweepDroppedForms() {
  for (const player of allPlayers()) {
    let items = [];
    try {
      items = player.dimension.getEntities({
        location: player.location, maxDistance: 24, type: "minecraft:item",
      });
    } catch (_) { continue; }
    for (const e of items) {
      try {
        const stack = e.getComponent("minecraft:item")?.itemStack;
        if (stack && FORM_ITEMS.includes(stack.typeId)) e.remove();
      } catch (_) { }
    }
  }
}

// ---------------------------------------------------------------------------
//  効果
// ---------------------------------------------------------------------------
function applyEffect(player, id, amp, ticks = EFFECT_TICKS) {
  try {
    player.addEffect(id, ticks, { amplifier: amp, showParticles: false });
  } catch (_) { }
}

/** 技が自分に掛ける効果。巨人化や高速回避が解除後も残らないようにする。 */
const TECH_EFFECTS = [...new Set(
  TECHS.flatMap((t) => (t.buffs ?? []).map(([id]) => id)))];

/**
 * 変身に由来する効果をまとめて落とす。形態の常時効果だけでなく、
 * 技が掛けた自己強化と透明化も含める — 企画書 §14 の必須の復旧経路は
 * 「変身専用効果」を全部解除することを求めている。
 */
function clearFormEffects(player) {
  const ids = new Set(TECH_EFFECTS);
  for (const f of FORMS) for (const [id] of f.effects) ids.add(id);
  ids.add("invisibility");
  for (const id of ids) {
    try { player.removeEffect(id); } catch (_) { }
  }
}

/**
 * 形態の効果と透明化を掛け直す。毎秒呼ばれる。
 *
 * 透明化は「形態アイテムを実際に着ている」ことが条件。これで、何かの理由で
 * アタッチャブルが外れたときに透明なプレイヤーだけが残る事故を防ぐ
 * （企画書 §14 透明化を有効にする条件）。
 */
function refreshBody(player) {
  const form = currentForm(player);
  if (!form) return;
  for (const [id, amp] of form.effects) applyEffect(player, id, amp);
  if (wearingFormItem(player) === form.item) {
    applyEffect(player, "invisibility", 0);
  } else {
    try { player.removeEffect("invisibility"); } catch (_) { }
  }
}

// ---------------------------------------------------------------------------
//  能力の獲得（悪魔の実を食べる）
//
//  企画書 §14 の「アイテム増殖を防ぐ構造」に従い、ここは *何も配らない*。
//  実は food として消費されるだけで、代わりのアイテムを渡す循環を作らない。
//  麦わら帽子・拳の包帯・ログポースはレシピで作る（配布と使用の分離）。
// ---------------------------------------------------------------------------
export function grantPower(player, quiet = false, consume = "") {
  if (hasPower(player)) {
    if (!quiet) tell(player, tr("gla.msg.already_power"));
    return false;
  }
  // 食べて得たときは実を消す。開発用コマンドからは何も消さない。
  if (consume && !consumeHeld(player, consume)) return false;
  setProp(player, PROP.power, true);
  setEnergy(player, ENERGY_MAX);
  setPhase(player, "normal");
  const ctx = makeContext(player, quality(player));
  spawn(player.dimension, "gla:transform_burst", ctx.chest);
  playSfx(player.dimension, player.location, { id: "random.levelup", v: 0.9, p: 0.7 });
  playAnim(player, "animation.gla.form.transform_in");
  title(player, tr("gla.title.awaken"), {
    fadeInDuration: 8, stayDuration: 46, fadeOutDuration: 18,
    subtitle: tr("gla.title.awaken_sub"),
  });
  tell(player, tr("gla.msg.power_gained"));
  tell(player, tr("gla.msg.welcome_hint"));
  return true;
}


// ---------------------------------------------------------------------------
//  変身・解除
// ---------------------------------------------------------------------------
export function canTransform(player, key) {
  if (!hasPower(player)) return "gla.msg.no_power";
  const form = FORM_BY_KEY[key];
  if (!form) return "gla.msg.no_form";
  if (!unlocked(player, key)) return "gla.msg.locked";
  if (!infinite(player) && energy(player) < form.enter) return "gla.msg.too_tired";
  return "";
}

export function transform(player, key) {
  const why = canTransform(player, key);
  if (why) { tell(player, tr(why)); return false; }
  const form = FORM_BY_KEY[key];
  const already = formKey(player);
  if (already === key) return false;

  stopShowpiece(player);
  rt(player).cast = null;        // 形態を変えたら、前の形態の技は続けない
  // 形態を変えるときも必ず通す。stashArmor は頭が空か形態表示体のときは
  // 何もしないので、形態切替は素通りする。プレイヤーが自分で表示体を外して
  // 兜をかぶり直していた場合だけ、その兜をしまう（上書きして消さない）。
  if (!stashArmor(player)) {
    tell(player, tr("gla.msg.no_room"));
    return false;
  }
  if (!wearFormItem(player, form.item)) {
    tell(player, tr("gla.msg.no_room"));
    return false;
  }
  setProp(player, PROP.form, key);
  setProp(player, PROP.lastform, key);      // 素の「使う」はここへ戻る
  setPhase(player, "transforming");
  try { player.addTag(TAG_ACTIVE); } catch (_) { }
  if (!infinite(player)) setEnergy(player, energy(player) - form.enter);
  refreshBody(player);

  const ctx = makeContext(player, quality(player));
  spawn(player.dimension, "gla:transform_burst", ctx.chest);
  playSfx(player.dimension, player.location, { id: "mob.slime.big", v: 0.8, p: 0.7 });
  // 登場ポーズと看板演出の「身体の動き」は、アタッチャブル側の
  // animation controller が initial_state で必ず1回再生する。
  // 表示体は装備した瞬間に作られるので、ここから鳴らす必要はない
  // （スクリプトの playAnimation に頼ると、対象版次第で目玉の演出が消える）。
  // ここで面倒を見るのは、時間表に沿った粒子・音・操作の戻しだけ。
  if (cameraFx(player)) shake(player, 0.22, 0.4);
  title(player, { rawtext: [{ translate: form.name }] },
        { fadeInDuration: 4, stayDuration: 22, fadeOutDuration: 10 });

  const r = rt(player);
  if (key === "gear5") {
    startShowpiece(player);
  } else {
    r.busyUntil = system.currentTick + 16;
    later(16, () => { if (phase(player) === "transforming") setPhase(player, "active"); });
  }
  return true;
}

export function revert(player, exhausted = false) {
  if (!formKey(player)) return;
  stopShowpiece(player);
  rt(player).cast = null;        // 解除で、進行中の技の予約も無効にする
  setPhase(player, "reverting");
  removeFormItem(player);
  setProp(player, PROP.form, "");
  clearFormEffects(player);
  restoreArmor(player);
  try { player.removeTag(TAG_ACTIVE); } catch (_) { }
  playAnim(player, "animation.gla.form.revert");
  const ctx = makeContext(player, quality(player));
  spawn(player.dimension, "gla:revert_puff", ctx.chest);
  playSfx(player.dimension, player.location, { id: "mob.slime.small", v: 0.6, p: 0.8 });
  if (exhausted) {
    tell(player, tr("gla.msg.exhausted"));
    try { player.addEffect("slowness", 120, { amplifier: 0, showParticles: false }); } catch (_) { }
  }
  later(10, () => { if (phase(player) === "reverting") setPhase(player, "normal"); });
  rt(player).busyUntil = system.currentTick + 10;
}

/**
 * 通常状態へ復旧（企画書 §14 必須の復旧経路）。
 * カメラ・入力制限・変身専用効果・予約された技処理をすべて解除する。
 * ワールドを作り直さずに直せることが要件。
 */
export function safeReset(player, quiet = false) {
  setPhase(player, "safe_reset");
  stopShowpiece(player);
  removeFormItem(player);
  setProp(player, PROP.form, "");
  clearFormEffects(player);
  restoreArmor(player);
  sweepFormItems(player);
  try { player.removeTag(TAG_ACTIVE); } catch (_) { }
  try { player.runCommand("camerashake stop @s"); } catch (_) { }
  const r = rt(player);
  r.showpiece = null;
  r.cast = null;                 // 予約済みの技処理は印が合わず空振りになる
  r.busyUntil = 0;
  setPhase(player, "normal");
  if (!quiet) tell(player, tr("gla.msg.recovered"));
}

export function busy(player) {
  return system.currentTick < rt(player).busyUntil;
}

export function setBusy(player, ticks) {
  rt(player).busyUntil = system.currentTick + ticks;
}

export function markFight(player) {
  rt(player).lastFight = system.currentTick;
}

export function playAnim(player, id) {
  // 技ごとの専用クリップは対応版でないと再生されない。落ちないことだけ保証し、
  // 演出は VFX 側で成立するようにしてある（企画書 §01 完成の判定）。
  try { player.playAnimation(id); return true; } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
//  看板演出 — ニカ変身後の浮遊・大笑い（企画書 §08）
//
//  見た目の root を上げるのはアニメーション側の仕事で、ここは時間表に沿って
//  粒子と音を出し、途中で止められるようにするだけ。プレイヤーの実座標は
//  一切動かさないので、落下や壁抜けは増えない。
// ---------------------------------------------------------------------------
export function startShowpiece(player) {
  const q = quality(player);
  // 同時に何本もフル演出が走ると一番重い。枠が取れなければ短縮版に落とす
  // （企画書 §15 大技のフル演出・同時数）。判定も操作も変わらない。
  const short = shortFx(player)
    || !claimBigFx(player, q, SHOWPIECE_TICKS);
  const span = short ? SHOWPIECE_SHORT_TICKS : SHOWPIECE_TICKS;
  const r = rt(player);
  r.busyUntil = system.currentTick + span;
  playAnim(player, short ? "animation.gla.gear5.laugh_short"
                         : "animation.gla.gear5.laugh");

  // token は「この演出は今も自分のものか」を確かめる印。変身しなおしや中断で
  // 差し替わると、予約済みの処理が自分から降りる。
  const token = Symbol("showpiece");
  r.showpiece = token;
  // スキップは状態が確定してからしか受け付けない（企画書 §08 技の連発防止）
  r.skipFrom = system.currentTick + Math.min(20, span);
  const handles = [];
  if (!short) {
    for (const step of SHOWPIECE) {
      for (const st of step.stages) {
        handles.push(later(step.t + st.t + 1, () => {
          if (!alive(player) || rt(player).showpiece !== token) return;
          playStage(makeContext(player, q), st);
        }));
      }
      for (const s of step.sfx) {
        handles.push(later(step.t + s.t + 1, () => {
          if (!alive(player) || rt(player).showpiece !== token) return;
          playSfx(player.dimension, player.location, s);
        }));
      }
    }
  } else {
    handles.push(later(2, () => {
      if (!alive(player) || rt(player).showpiece !== token) return;
      const ctx = makeContext(player, q);
      playStage(ctx, { t: 0, layer: 3, fx: "gla:nika_flash", form: "point", at: "chest" });
      playStage(ctx, { t: 0, layer: 4, fx: "gla:wind_ring", form: "ring", n: 12, r: 2.0, at: "feet" });
    }));
  }
  handles.push(later(span, () => {
    if (rt(player).showpiece !== token) return;
    rt(player).showpiece = null;
    if (phase(player) === "transforming") setPhase(player, "active");
  }));
  r.handles = handles;
}

export function stopShowpiece(player) {
  const r = runtime.get(player.id);
  if (!r || !r.showpiece) return;
  r.showpiece = null;                 // 予約済みの処理は token 不一致で自分から降りる
  r.busyUntil = 0;
  releaseBigFx(player.id);
  try { player.runCommand("camerashake stop @s"); } catch (_) { }
  if (phase(player) === "transforming") setPhase(player, "active");
}

/** 演出のスキップ。状態が確定してからしか受け付けない（技の連発防止・企画書 §08）。 */
export function skipShowpiece(player) {
  const r = runtime.get(player.id);
  if (!r?.showpiece) return false;
  if (system.currentTick < (r.skipFrom ?? 0)) return false;
  stopShowpiece(player);
  return true;
}

function alive(player) {
  try { return player.isValid?.() !== false && !!player.dimension; } catch (_) { return false; }
}

// ---------------------------------------------------------------------------
//  毎秒の維持処理
// ---------------------------------------------------------------------------
export function tick() {
  for (const player of allPlayers()) {
    if (!hasPower(player)) continue;
    const form = currentForm(player);
    let e = energy(player);

    if (form) {
      refreshBody(player);
      if (!infinite(player)) {
        e -= form.upkeep;
        if (e <= 0) { setEnergy(player, 0); revert(player, true); continue; }
      }
    } else {
      const idleFor = system.currentTick - (runtime.get(player.id)?.lastFight ?? -9999);
      e += idleFor > 160 ? ENERGY_REGEN_IDLE : ENERGY_REGEN;
    }
    setEnergy(player, e);

    if (form) {
      hud(player, form, e);
      ambient(player, form, e);
      if (!infinite(player) && e < LOW_ENERGY) {
        // 予告なく解除されないよう、割ったときだけ知らせる
        if (Math.floor(e) === Math.floor(LOW_ENERGY) - 1) tell(player, tr("gla.msg.low_energy"));
      }
    }
  }
}

/** 形態の常在演出と、気力切れの予告。どちらも軽量設定では出さない。 */
function ambient(player, form, e) {
  const q = quality(player);
  if (q === "light") return;
  const ctx = makeContext(player, q);
  const id = AMBIENT[form.key];
  if (id) spawn(player.dimension, id, ctx.chest);
  if (!infinite(player) && e < LOW_ENERGY) {
    spawn(player.dimension, "gla:low_energy", ctx.chest);
  }
}

/**
 * 通常プレイ中の表示は 形態名 / 選択中の技 / 気力 / 再使用待ち の4つだけ。
 * 詳しい説明はメニューへ分ける（企画書 §12 UIの方向性）。
 */
function hud(player, form, e) {
  const ratio = clamp(e / ENERGY_MAX, 0, 1);
  const colour = ratio > 0.5 ? "§a" : ratio > 0.2 ? "§e" : "§c";
  const tech = selectedTech(player);
  const parts = [{ translate: form.name }, { text: " §8|§r " }];
  if (tech) parts.push({ translate: `gla.tech.${tech}` });
  // 再使用待ちは、待っている間だけ出す。待っていないときに 0 を出しても
  // 情報にならないので、4つ目の欄はそのとき空になる（企画書 §12）。
  if (tech) {
    const left = cooldownLeft(player.id, tech);
    if (left > 0) parts.push({ text: ` §8${(left / 20).toFixed(1)}s` });
  }
  parts.push({ text: `  ${colour}${bar(ratio, 10)}§r ${Math.ceil(e)}` });
  if (infinite(player)) parts.push({ text: " §b∞" });
  actionbar(player, { rawtext: parts });
}

export function spend(player, amount) {
  if (infinite(player)) return true;
  const e = energy(player);
  if (e < amount) return false;
  setEnergy(player, e - amount);
  return true;
}

// ---------------------------------------------------------------------------
//  再接続・死亡・次元移動（企画書 §14 所有者と寿命）
// ---------------------------------------------------------------------------
export function restore(player) {
  // 初期値を埋める
  if (typeof player.getDynamicProperty(PROP.energy) !== "number") {
    setEnergy(player, ENERGY_MAX);
  }
  for (const [key, val] of Object.entries(DEFAULTS)) {
    const prop = PROP[key];
    if (!prop) continue;
    const cur = player.getDynamicProperty(prop);
    if (typeof cur !== typeof val) setProp(player, prop, val);
  }
  // 再接続時は、前のセッションの演出を必ず捨てる
  const ph = phase(player);
  if (ph === "transforming" || ph === "attacking" || ph === "recovering"
      || ph === "reverting" || ph === "safe_reset") {
    setPhase(player, formKey(player) ? "active" : "normal");
  }
  if (formKey(player)) {
    const form = currentForm(player);
    // 頭に別のものが載っているなら上書きしない。上書きするとそれが消える。
    let head;
    try { head = equippable(player)?.getEquipment(EquipmentSlot.Head); } catch (_) { }
    const slotFree = !head || FORM_ITEMS.includes(head.typeId);
    if (form && slotFree && wearingFormItem(player) !== form.item) {
      wearFormItem(player, form.item);
    }
    try { player.addTag(TAG_ACTIVE); } catch (_) { }
    refreshBody(player);
  } else {
    safeReset(player, true);
  }
}

world.afterEvents.entityDie.subscribe((ev) => {
  const e = ev.deadEntity;
  if (e?.typeId !== "minecraft:player") return;
  system.run(() => {
    try {
      safeReset(e, true);
      setEnergy(e, ENERGY_MAX * 0.4);
    } catch (_) { }
  });
});

world.afterEvents.entityHurt?.subscribe?.((ev) => {
  const player = ev.hurtEntity;
  if (player?.typeId !== "minecraft:player") return;
  const key = formKey(player);
  if (!key) return;
  // 殴られている最中に4.5秒笑い続けない。演出を打ち切って操作を返す
  // （企画書 §08 被弾では残留カメラや操作制限を解除する）。
  stopShowpiece(player);
  playAnim(player, `animation.gla.${key}.hurt`);
});

world.afterEvents.playerDimensionChange?.subscribe?.((ev) => {
  const player = ev.player;
  system.run(() => {
    try {
      stopShowpiece(player);
      if (formKey(player)) refreshBody(player);
    } catch (_) { }
  });
});
