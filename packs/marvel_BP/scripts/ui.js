// UI / セレブロ端末・技選択・姿選択
//
// 「戦闘中に 15 種を切り替えられるか」がこの作品の遊びやすさを決める。
// 答えは **技アイテム = ホットバー** で、フォームはその補助でしかない。
// 戦闘の最中にフォームを開かせたら、それだけで手が止まる。
//
// だからここは三段構えにしてある。
//   1. `layoutHotbar()`  解禁済みの技を **TECH_ORDER の順にホットバーへ並べる**。
//                        以降の切り替えはスロット選択だけで済む（最速）。
//   2. `pickTechnique()` 一覧から選ぶと **その場で手に持つ**（swap するので
//                        持っていた物は落ちない）。戦闘の合間用。
//   3. `openTerminal()`  設定と索敵。戦闘外用。
import { ActionFormData } from "@minecraft/server-ui";
import {
  PROP, TECH, TECH_ORDER, HERO, HERO_ORDER, ALLY_TECH, FX, SOUND,
  STAGE_THRESHOLDS,
} from "./config.js";
import { safe, setProp, str, num, tell, tr } from "./util.js";
import { fx, sound } from "./effects.js";
import {
  container, give, heroOf, magOf, selectedSlot, stageOf,
} from "./transform.js";
import { revealMetal } from "./magnetism.js";
import { cooldowns } from "./techniques.js";
import { allyCooldowns } from "./powers.js";

function show(player, form) {
  return safe(() => form.show(player));
}

/** 次の段階まで、あと何体か。 */
function nextThreshold(stage) {
  for (const [kills, value] of STAGE_THRESHOLDS) {
    if (value > stage) return kills;
  }
  return undefined;
}

// ---------------------------------------------------------------- ホットバー
//: ブラザーフッドの 3 枠に割り当てる技アイテム。
//: 姿ごとに専用アイテムを作らず、この 3 種を「1 番・2 番・3 番」として使う。
//: main.js の割り当てとここは **必ず同じ表を見る**。
export const ALLY_SLOT_ITEMS = [
  TECH.repulse.item, TECH.attract.item, TECH.lance.item,
];

/** 指定のアイテムを手に持つ。既に持っているものは捨てずに入れ替える。 */
function equipToHand(player, typeId) {
  const inv = container(player);
  if (!inv) return false;
  const hand = selectedSlot(player);
  let from = -1;
  for (let i = 0; i < inv.size; i++) {
    if (safe(() => inv.getItem(i))?.typeId === typeId) { from = i; break; }
  }
  if (from < 0) {
    give(player, typeId);
    for (let i = 0; i < inv.size; i++) {
      if (safe(() => inv.getItem(i))?.typeId === typeId) { from = i; break; }
    }
  }
  if (from < 0) return false;
  if (from === hand) return true;
  const held = safe(() => inv.getItem(hand));
  safe(() => inv.setItem(hand, safe(() => inv.getItem(from))));
  safe(() => inv.setItem(from, held));
  return true;
}

/**
 * 解禁済みの技をホットバーへ並べる。
 * **これが 15 技を戦闘中に使うための本線。** 並べてしまえば、
 * あとは数字キー / ホイールだけで切り替えられる。
 */
export function layoutHotbar(player) {
  const inv = container(player);
  if (!inv) return 0;
  const hero = heroOf(player);
  const wanted = hero === "magneto"
    ? TECH_ORDER.filter((k) => TECH[k].stage <= stageOf(player)).map((k) => TECH[k].item)
    : (ALLY_TECH[hero] ?? []).map((_, i) => ALLY_SLOT_ITEMS[i]).filter(Boolean);

  const find = (typeId) => {
    for (let i = 0; i < inv.size; i++) {
      if (safe(() => inv.getItem(i))?.typeId === typeId) return i;
    }
    return -1;
  };

  let placed = 0;
  for (const typeId of wanted) {
    if (placed >= 9) break;
    let at = find(typeId);
    if (at < 0) { give(player, typeId); at = find(typeId); }
    if (at < 0) continue;                    // 鞄が一杯。詰めずに次へ
    if (at !== placed) {
      const held = safe(() => inv.getItem(placed));
      safe(() => inv.setItem(placed, safe(() => inv.getItem(at))));
      safe(() => inv.setItem(at, held));
    }
    placed++;
  }
  sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.6 });
  tell(player, { rawtext: [{ translate: "marvel.ui.give_tech" }, { text: ` §7x${placed}` }] });
  return placed;
}

// ---------------------------------------------------------------- 技を選ぶ
function techLabel(player, key) {
  const spec = TECH[key];
  const locked = stageOf(player) < spec.stage;
  if (locked) {
    return { rawtext: [{ text: "§8" }, { translate: `marvel.tech.${key}` },
                       { text: `  §8[${spec.stage}]` }] };
  }
  const cd = Math.ceil(cooldowns.remaining(player.id, key) / 20);
  const tail = cd > 0
    ? `  §c${cd}s`
    : (magOf(player) < spec.cost ? `  §8${spec.cost}` : `  §7${spec.cost}`);
  return { rawtext: [{ translate: `marvel.tech.${key}` }, { text: tail }] };
}

/** 技を選ぶ。段階が足りない技は理由つきで灰色に見せる。 */
export function pickTechnique(player) {
  const hero = heroOf(player);
  if (hero !== "magneto") { pickAllyTechnique(player); return; }

  const form = new ActionFormData()
    .title({ translate: "marvel.ui.pick_tech" })
    .body(statusText(player));
  for (const key of TECH_ORDER) {
    form.button(techLabel(player, key),
                `textures/items/${TECH[key].item.split(":")[1]}`);
  }
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const key = TECH_ORDER[res.selection];
    if (stageOf(player) < TECH[key].stage) {
      tell(player, tr("msg.locked"));
      sound(player.dimension, SOUND.ui_select, player.location, { pitch: 0.5 });
      return;
    }
    setProp(player, PROP.tech, key);
    // 選んだら **その場で手に持つ**。持ち替えのためにもう一度画面を開かせない。
    equipToHand(player, TECH[key].item);
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.4 });
    tell(player, { rawtext: [{ translate: "marvel.msg.tech_set" },
                             { translate: `marvel.tech.${key}` }] });
  });
}

/** ブラザーフッドは 3 種。どのアイテムがどれかも一緒に見せる。 */
export function pickAllyTechnique(player) {
  const hero = heroOf(player);
  const kit = ALLY_TECH[hero] ?? [];
  if (!kit.length) return;
  const form = new ActionFormData()
    .title({ translate: "marvel.ui.pick_tech" })
    .body(statusText(player));
  for (let i = 0; i < kit.length; i++) {
    const cd = Math.ceil(allyCooldowns.remaining(player.id, kit[i].key) / 20);
    form.button({
      rawtext: [{ text: `§7${i + 1}. §r` }, { translate: `marvel.tech.${kit[i].key}` },
                { text: cd > 0 ? `  §c${cd}s` : `  §7${kit[i].cost}` }],
    });
  }
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const slot = ALLY_SLOT_ITEMS[res.selection];
    setProp(player, PROP.tech, kit[res.selection].key);
    if (slot) equipToHand(player, slot);
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.4 });
    tell(player, { rawtext: [{ translate: "marvel.msg.tech_set" },
                             { translate: `marvel.tech.${kit[res.selection].key}` }] });
  });
}

/** 変身する姿を選ぶ。 */
export function pickHero(player) {
  const form = new ActionFormData().title({ translate: "marvel.ui.pick_hero" });
  for (const key of HERO_ORDER) {
    form.button({
      rawtext: [{ translate: `marvel.hero.${key}` },
                { text: `  §7${HERO[key].health}§8/§7${HERO[key].damage}` }],
    });
  }
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const key = HERO_ORDER[res.selection];
    setProp(player, PROP.hero, key);
    // 姿を変えたら持ち技も変わる。手元も一緒に並べ直す。
    layoutHotbar(player);
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.2 });
    tell(player, { rawtext: [{ translate: "marvel.msg.hero_set" },
                             { translate: `marvel.hero.${key}` }] });
  });
}

/** セレブロ端末。 */
export function openTerminal(player) {
  const form = new ActionFormData()
    .title({ translate: "marvel.ui.terminal" })
    .body(statusText(player))
    .button({ translate: "marvel.ui.pick_tech" })
    .button({ translate: "marvel.ui.give_tech" })
    .button({ translate: "marvel.ui.pick_hero" })
    .button({ translate: "marvel.ui.scan_metal" })
    .button({ translate: "marvel.ui.scan_mutant" })
    .button({ translate: "marvel.ui.summon" })
    .button({ translate: "marvel.ui.close" });
  sound(player.dimension, SOUND.ui_open, player.location, { pitch: 1.1 });
  show(player, form)?.then((res) => {
    if (res?.canceled) return;
    switch (res.selection) {
      case 0: pickTechnique(player); break;
      case 1: layoutHotbar(player); break;
      case 2: pickHero(player); break;
      case 3: scanMetal(player); break;
      case 4: scanMutants(player); break;
      case 5: summonAlly(player); break;
      default: break;
    }
  });
}

function statusText(player) {
  const stage = stageOf(player);
  const mastery = num(player, PROP.mastery, 0);
  const next = nextThreshold(stage);
  const parts = [
    { translate: `marvel.hero.${heroOf(player)}` },
    { text: "\n§7" },
    { translate: `marvel.class.stage${stage}` },
    { text: `\n§r${Math.ceil(magOf(player))} / 100  §7(§d${mastery}§7)` },
  ];
  // 「あと何体で次の段階か」を出す。ここが無いと段階 3 が遠すぎて見えない。
  if (next !== undefined) parts.push({ text: `  §8→ §d${Math.max(0, next - mastery)}` });
  return { rawtext: parts };
}

export function scanMetal(player) {
  const n = revealMetal(player, 24);
  sound(player.dimension, SOUND.sight, player.location, { pitch: 1.3 });
  tell(player, { rawtext: [{ translate: "marvel.msg.scan" }, { text: ` §b${n}` }] });
}

export function scanMutants(player) {
  const found = safe(() => player.dimension.getEntities({
    location: player.location, maxDistance: 48,
  })) ?? [];
  const lines = [];
  for (const e of found) {
    if (!e.typeId?.startsWith("marvel:")) continue;
    const d = Math.round(Math.hypot(e.location.x - player.location.x,
                                    e.location.y - player.location.y,
                                    e.location.z - player.location.z));
    lines.push({ rawtext: [{ text: "\n§7- " }, { translate: `entity.${e.typeId}.name` },
                           { text: ` §8${d}m` }] });
    if (lines.length >= 10) break;
  }
  sound(player.dimension, SOUND.sight, player.location, { pitch: 1.5 });
  tell(player, {
    rawtext: [{ translate: "marvel.msg.scan" }, { text: ` §b${lines.length}` },
              ...lines.flatMap((l) => l.rawtext)],
  });
}

export function summonAlly(player) {
  const form = new ActionFormData().title({ translate: "marvel.ui.summon" });
  const roster = HERO_ORDER.filter((k) => k !== "magneto");
  for (const key of roster) form.button({ translate: `marvel.hero.${key}` });
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const key = roster[res.selection];
    const dir = player.getViewDirection();
    const at = {
      x: player.location.x + dir.x * 2.5,
      y: player.location.y + 0.4,
      z: player.location.z + dir.z * 2.5,
    };
    const ally = safe(() => player.dimension.spawnEntity(`marvel:${key}`, at));
    if (!ally) return;
    safe(() => ally.getComponent("minecraft:tameable")?.tame(player));
    fx(player.dimension, FX.transform_ring, at);
    sound(player.dimension, SOUND.transform_2, at, { pitch: 1.0 });
    tell(player, tr("msg.ally_summoned"));
  });
}

/** 解禁済みの技アイテムを一式配る（端末からの「受け取る」）。 */
export function grantTechItems(player) {
  return layoutHotbar(player);
}

/**
 * HUD の右端に出す一行。
 * 手に持っている技の再充填と、効いている持続効果を短く出す。
 * ここが無いと、撃てない理由が「クールダウン」なのか「磁力切れ」なのか
 * プレイヤーには一切判らない。
 */
export function hudExtra(player) {
  const bits = [];
  const key = str(player, PROP.tech, "");
  if (key && TECH[key]) {
    const cd = Math.ceil(cooldowns.remaining(player.id, key) / 20);
    if (cd > 0) bits.push(`§c${cd}s`);
    else if (magOf(player) < TECH[key].cost) bits.push("§8" + TECH[key].cost);
  }
  if (num(player, PROP.flying, 0) === 1) bits.push("§d✈");
  if (num(player, PROP.sight, 0) > 0) bits.push("§b◉");
  if (num(player, PROP.barrier, 0) > 0) bits.push("§a◇");
  return bits.length ? bits.join(" ") : undefined;
}
