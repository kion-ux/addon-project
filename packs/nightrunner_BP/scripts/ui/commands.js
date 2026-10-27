// ===========================================================================
//  ui/commands.js — 遊ぶ・試すための /scriptevent コマンド
//
//   /scriptevent nr:help                 コマンドの一覧
//   /scriptevent nr:kit [melee|ranged]   武器と回復・弾・道具を一式もらう（省略で全部。あふれた分は足元へ）
//   /scriptevent nr:gore <0-100>         ゴアレベル（既定 100）
//   /scriptevent nr:settings             いまの設定の一覧
//   /scriptevent nr:set <鍵> <値>        設定を一つ変える（例: nr:set max_gibs 80）
//   /scriptevent nr:spawn <種類> [数]    目の前にゾンビを出す（種類 = 鍵 / nr:z_ の ID /
//                                         common viral special night boss / all = 50 体を並べる）
//   /scriptevent nr:clear [all]          ちぎれた部位と死体を片付ける（all はゾンビも全部）
// ===========================================================================
import { world, system, ItemStack } from "@minecraft/server";
import { WEAPONS } from "../data/weapons.js";
import { ITEMS } from "../data/items.js";
import { ZOMBIES } from "../data/zombies.js";
import * as settings from "../core/settings.js";
import { clearGibs } from "../gore/gibs.js";

const CLASSES = ["common", "viral", "special", "night", "boss"];

/** 一式に入れる道具と消耗品（ID, 数）。近接の一式と飛び道具の一式で分ける。 @type {Record<string, [string, number][]>} */
const KIT_EXTRAS = {
  melee: [["nr:survivor_terminal", 1], ["nr:grappling_hook", 1], ["nr:paraglider", 1], ["nr:uv_flashlight", 1],
    ["nr:bandage", 8], ["nr:medkit", 4], ["nr:immunity_booster", 4], ["nr:energy_drink", 4]],
  ranged: [["nr:ammo_pistol", 64], ["nr:ammo_shotgun", 64], ["nr:ammo_rifle", 64], ["nr:bolt", 64], ["nr:survivor_arrow", 64]],
};

/** @param {any} e @returns {e is import("@minecraft/server").Player} */
function isPlayer(e) { return !!e && e.typeId === "minecraft:player" && e.isValid; }

/** @param {import("@minecraft/server").Entity | undefined} src @param {string} text */
function reply(src, text) {
  if (isPlayer(src)) src.sendMessage(text);
  else world.sendMessage(text);
}

/**
 * 持ち物に入れる（あふれた分は足元に落とす）。無い ID は飛ばして返す。
 * @param {import("@minecraft/server").Player} p @param {[string, number][]} list @returns {string[]} 入れられなかった ID
 */
export function giveItems(p, list) {
  const missing = [];
  const container = p.getComponent("minecraft:inventory")?.container;
  for (const [id, count] of list) {
    let left = Math.max(1, Math.floor(count));
    while (left > 0) {
      let stack;
      try { stack = new ItemStack(id, 1); } catch { missing.push(id); break; }
      const n = Math.min(left, stack.maxAmount);
      stack.amount = n;
      left -= n;
      const rest = container ? container.addItem(stack) : stack;
      if (rest) p.dimension.spawnItem(rest, p.location);
    }
  }
  return missing;
}

/**
 * 一式。which = "melee"（近接武器 + 道具・回復）/ "ranged"（飛び道具 + 弾）/ "all"（両方。道具が先で、あふれた武器は足元へ）。
 * @param {import("@minecraft/server").Player} p @param {string} [which]
 */
export function giveKit(p, which = "all") {
  const known = new Set(ITEMS.map((i) => i.id));
  /** @type {[string, number][]} */
  const list = [];
  for (const part of ["melee", "ranged"]) {
    if (which !== "all" && which !== part) continue;
    for (const [id, n] of KIT_EXTRAS[part]) if (known.has(id)) list.push([id, n]);
  }
  for (const part of ["melee", "ranged"]) {
    if (which !== "all" && which !== part) continue;
    for (const w of WEAPONS) if ((w.kind === "melee") === (part === "melee")) list.push([w.id, 1]);
  }
  return giveItems(p, list);
}

/** 種類の指定をゾンビの ID の並びに。 @param {string} what @param {number} n @returns {string[]} */
export function resolveZombies(what, n) {
  const w = String(what || "").trim().toLowerCase();
  if (w === "all") return ZOMBIES.map((z) => z.id);
  if (CLASSES.includes(w)) {
    const pool = ZOMBIES.filter((z) => z.cls === w).map((z) => z.id);
    return Array.from({ length: n }, (_, i) => pool[i % pool.length]);
  }
  const z = ZOMBIES.find((x) => x.key === w || x.id === w || x.id === `nr:z_${w}`);
  return z ? Array.from({ length: n }, () => z.id) : [];
}

/**
 * プレイヤーの前に並べて出す（10 体ごとに列を下げる）。出した数を返す。
 * @param {import("@minecraft/server").Player} p @param {string[]} ids
 */
export function spawnInFront(p, ids) {
  const v = p.getViewDirection();
  const h = Math.hypot(v.x, v.z) || 1;
  const fx = v.x / h, fz = v.z / h;          // 前
  const rx = -fz, rz = fx;                   // 横
  let n = 0;
  ids.forEach((id, i) => {
    const row = Math.floor(i / 10), col = (i % 10) - Math.min(ids.length - 1, 9) / 2;
    const d = 5 + row * 3.5, s = col * 2.5;
    const loc = { x: p.location.x + fx * d + rx * s, y: p.location.y, z: p.location.z + fz * d + rz * s };
    try { p.dimension.spawnEntity(id, loc); n++; } catch (err) { console.warn("[nr] spawn", id, err instanceof Error ? err.message : err); }
  });
  return n;
}

/** 片付ける。all = true ならゾンビも全部。 @param {boolean} all @returns {number} 消した数 */
export function clearWorld(all) {
  clearGibs();
  let n = 0;
  for (const dimId of ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"]) {
    let list = [];
    try { list = world.getDimension(dimId).getEntities(); } catch { continue; }
    for (const e of list) {
      if (!e.isValid || !e.typeId.startsWith("nr:z_")) continue;
      let dead = false;
      try { dead = e.getProperty("nr:state") === "dead"; } catch { /* 定義の無い版 */ }
      if (all || dead) { e.remove(); n++; }
    }
  }
  return n;
}

const HELP = [
  "§c§lNIGHT RUNNER§r のコマンド（/scriptevent）",
  "§enr:kit [melee|ranged]§r 武器と道具の一式 / §enr:gore <0-100>§r ゴアレベル / §enr:settings§r 設定の一覧",
  "§enr:set <鍵> <値>§r 設定を変える / §enr:spawn <種類|common|viral|special|night|boss|all> [数]§r",
  "§enr:clear [all]§r 部位と死体を片付ける（all はゾンビも） / §enr:skill all§r パルクールと戦闘のスキルを全部",
];

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (!ev.id.startsWith("nr:")) return;
  const src = ev.sourceEntity;
  const args = ev.message.trim().split(/\s+/).filter(Boolean);
  switch (ev.id) {
    case "nr:help":
      reply(src, HELP.join("\n"));
      break;
    case "nr:kit": {
      if (!isPlayer(src)) { reply(src, "nr:kit はプレイヤーが打ってください"); break; }
      const which = ["melee", "ranged"].includes(args[0]) ? args[0] : "all";
      const missing = giveKit(src, which);
      reply(src, `§a一式を渡しました§r（${which}。まだ無い物 ${missing.length}）`);
      break;
    }
    case "nr:gore": {
      const v = Number(args[0]);
      if (!Number.isFinite(v)) { reply(src, `ゴアレベル: §c${settings.get("gore_level")}§r（nr:gore <0-100> で変更）`); break; }
      settings.set("gore_level", Math.round(Math.max(0, Math.min(100, v))));
      reply(src, `ゴアレベルを §c${settings.get("gore_level")}§r にしました`);
      break;
    }
    case "nr:settings": {
      const all = settings.all();
      reply(src, ["§l設定§r", ...Object.keys(all).sort().map((k) => `  ${k} = §e${all[k]}§r`)].join("\n"));
      break;
    }
    case "nr:set": {
      const [key, value] = args;
      if (!key || value === undefined) { reply(src, "使い方: nr:set <鍵> <値>（鍵は nr:settings で確認）"); break; }
      reply(src, settings.set(key, value) ? `${key} = §e${settings.get(key)}§r` : `§c受け付けません§r: ${key} = ${value}`);
      break;
    }
    case "nr:spawn": {
      if (!isPlayer(src)) { reply(src, "nr:spawn はプレイヤーが打ってください"); break; }
      const n = Math.max(1, Math.min(50, Math.floor(Number(args[1]) || 1)));
      const ids = resolveZombies(args[0] ?? "", n);
      if (!ids.length) { reply(src, "§c種類が分かりません§r（例: nr:spawn office_worker 3 / nr:spawn viral 5 / nr:spawn all）"); break; }
      reply(src, `ゾンビを ${spawnInFront(src, ids)} 体出しました`);
      break;
    }
    case "nr:clear": {
      const n = clearWorld(args[0] === "all");
      reply(src, `片付けました（ゾンビ・死体 ${n}）`);
      break;
    }
  }
});
