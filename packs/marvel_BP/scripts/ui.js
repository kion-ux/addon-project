// UI / セレブロ端末・技選択・姿選択
import { world, system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import {
  PROP, TECH, TECH_ORDER, HERO, HERO_ORDER, ITEM, ALLY_TECH, FX, SOUND, ENTITY,
} from "./config.js";
import { safe, setProp, str, num, tell, tr, allPlayers } from "./util.js";
import { fx, sound } from "./effects.js";
import { give, heroOf, isTransformed, magOf, stageOf } from "./transform.js";
import { revealMetal } from "./magnetism.js";

function show(player, form) {
  return safe(() => form.show(player));
}

/** 技を選ぶ。段階が足りない技は理由つきで灰色に見せる。 */
export function pickTechnique(player) {
  const form = new ActionFormData()
    .title({ translate: "marvel.ui.pick_tech" })
    .body({ translate: "marvel.ui.terminal_body" });
  const stage = stageOf(player);
  const keys = TECH_ORDER;
  for (const key of keys) {
    const spec = TECH[key];
    const locked = stage < spec.stage;
    const label = locked
      ? { rawtext: [{ text: "§8" }, { translate: `marvel.tech.${key}` }, { text: `  §8[${spec.stage}]` }] }
      : { rawtext: [{ translate: `marvel.tech.${key}` }, { text: `  §7${spec.cost}` }] };
    form.button(label, `textures/items/${spec.item.split(":")[1]}`);
  }
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const key = keys[res.selection];
    if (stageOf(player) < TECH[key].stage) {
      tell(player, tr("msg.locked"));
      return;
    }
    setProp(player, PROP.tech, key);
    give(player, TECH[key].item);
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.4 });
    tell(player, { rawtext: [{ translate: "marvel.msg.tech_set" }, { translate: `marvel.tech.${key}` }] });
  });
}

/** 変身する姿を選ぶ。 */
export function pickHero(player) {
  const form = new ActionFormData().title({ translate: "marvel.ui.pick_hero" });
  for (const key of HERO_ORDER) {
    form.button({ rawtext: [{ translate: `marvel.hero.${key}` }] });
  }
  show(player, form)?.then((res) => {
    if (res?.canceled || res?.selection === undefined) return;
    const key = HERO_ORDER[res.selection];
    setProp(player, PROP.hero, key);
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.2 });
    tell(player, { rawtext: [{ translate: "marvel.msg.hero_set" }, { translate: `marvel.hero.${key}` }] });
  });
}

/** セレブロ端末。 */
export function openTerminal(player) {
  const form = new ActionFormData()
    .title({ translate: "marvel.ui.terminal" })
    .body(statusText(player))
    .button({ translate: "marvel.ui.pick_tech" })
    .button({ translate: "marvel.ui.pick_hero" })
    .button({ translate: "marvel.ui.scan_metal" })
    .button({ translate: "marvel.ui.scan_mutant" })
    .button({ translate: "marvel.ui.summon" })
    .button({ translate: "marvel.ui.give_tech" })
    .button({ translate: "marvel.ui.close" });
  sound(player.dimension, SOUND.ui_open, player.location, { pitch: 1.1 });
  show(player, form)?.then((res) => {
    if (res?.canceled) return;
    switch (res.selection) {
      case 0: pickTechnique(player); break;
      case 1: pickHero(player); break;
      case 2: scanMetal(player); break;
      case 3: scanMutants(player); break;
      case 4: summonAlly(player); break;
      case 5: grantTechItems(player); break;
      default: break;
    }
  });
}

function statusText(player) {
  const stage = stageOf(player);
  return {
    rawtext: [
      { translate: `marvel.hero.${heroOf(player)}` },
      { text: "\n§7" },
      { translate: `marvel.class.stage${stage}` },
      { text: `\n§r${Math.ceil(magOf(player))} / 100  §7(§d${num(player, PROP.mastery, 0)}§7)` },
    ],
  };
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
    const key = e.typeId.split(":")[1];
    const d = Math.round(Math.hypot(e.location.x - player.location.x,
                                    e.location.y - player.location.y,
                                    e.location.z - player.location.z));
    lines.push({ rawtext: [{ text: "\n§7- " }, { translate: `entity.${e.typeId}.name` }, { text: ` §8${d}m` }] });
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
    if (ally) {
      safe(() => ally.getComponent("minecraft:tameable")?.tame(player));
      fx(player.dimension, FX.transform_ring, at);
      sound(player.dimension, SOUND.transform_2, at, { pitch: 1.0 });
      tell(player, tr("msg.ally_summoned"));
    }
  });
}

/** 解禁済みの技アイテムを一式配る。 */
export function grantTechItems(player) {
  const stage = stageOf(player);
  let n = 0;
  for (const key of TECH_ORDER) {
    if (TECH[key].stage > stage) continue;
    give(player, TECH[key].item);
    n++;
  }
  sound(player.dimension, SOUND.ui_select, player.location, { pitch: 1.6 });
  tell(player, { rawtext: [{ translate: "marvel.ui.give_tech" }, { text: ` §7x${n}` }] });
}
