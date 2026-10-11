// ===========================================================================
//  調査兵団の手帳（フォーム UI）と、画面下の HUD
// ===========================================================================
import { world, ItemStack } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import { GAS_MAX, ITEM, PROP, rankOf, TITAN_TYPES } from "./config.js";
import { gas, holdsBlades, state as odmState, wearsGear, anchorPos } from "./odm.js";
import { sound } from "./fx.js";
import {
  boolProp, container, count, dist, isCreative, numProp, rt, setProp, tell, tr, actionbar, heldItem,
} from "./util.js";

// ---------------------------------------------------------------------------
//  HUD（アクションバー）
// ---------------------------------------------------------------------------
function gauge(ratio, width = 10) {
  const n = Math.max(0, Math.min(width, Math.round(ratio * width)));
  return "▮".repeat(n) + "▯".repeat(width - n);
}

export function hud(p) {
  if (boolProp(p, PROP.hud, false)) return;
  const blades = holdsBlades(p);
  const gear = wearsGear(p);
  const held = heldItem(p);
  if (!blades && !gear && held?.typeId !== ITEM.spear) return;
  const g = gas(p) / GAS_MAX;
  const gc = g > 0.5 ? "§b" : g > 0.2 ? "§e" : "§c";
  const parts = [];
  if (gear) parts.push(gc, { t: "aot.hud.gas" }, ` ${gauge(g)} ${Math.round(g * 100)}%`);
  if (blades) {
    let wear = 0;
    try {
      const d = held.getComponent("minecraft:durability");
      wear = d ? 1 - d.damage / Math.max(1, d.maxDurability) : 1;
    } catch (_) { }
    const bc = wear > 0.5 ? "§f" : wear > 0.2 ? "§e" : "§c";
    parts.push("  ", bc, { t: "aot.hud.blade" }, ` ${gauge(wear, 5)}`,
               "  §7", { t: "aot.hud.spare", w: [count(p, ITEM.spare)] });
  }
  if (held?.typeId === ITEM.spear) parts.push("  §6", { t: "aot.hud.spear", w: [held.amount] });
  const s = odmState(p);
  if (s.anchor) {
    const at = anchorPos(s);
    if (at) parts.push("  §a⚓ ", `${dist(p.location, at).toFixed(1)}m`);
  }
  parts.push("  §e", { t: "aot.hud.kills", w: [numProp(p, PROP.kills, 0)] });
  actionbar(p, rt(...parts));
}

// ---------------------------------------------------------------------------
//  手帳
// ---------------------------------------------------------------------------
export function openJournal(p) {
  const kills = numProp(p, PROP.kills, 0);
  const body = rt(
    "§l", { t: "aot.ui.rank" }, "§r ", { t: rankOf(kills) }, "\n",
    { t: "aot.ui.kills", w: [kills] }, "\n",
    { t: "aot.ui.gas", w: [Math.round(gas(p))] }, "\n",
    { t: "aot.ui.spares", w: [count(p, ITEM.spare)] }, "\n\n",
    "§7", { t: "aot.ui.motto" });
  const f = new ActionFormData()
    .title(tr("aot.ui.title"))
    .body(body)
    .button(tr("aot.ui.btn.controls"))
    .button(tr("aot.ui.btn.titans"))
    .button(tr("aot.ui.btn.corps"))
    .button(tr("aot.ui.btn.kit"))
    .button(tr("aot.ui.btn.settings"));
  f.show(p).then((r) => {
    if (r.canceled) return;
    [controls, titans, corps, kit, settings][r.selection]?.(p);
  }).catch(() => { });
}

function page(p, titleKey, bodyKeys) {
  const parts = [];
  for (const k of bodyKeys) parts.push({ t: k }, "\n\n");
  new ActionFormData().title(tr(titleKey)).body(rt(...parts)).button(tr("aot.ui.back"))
    .show(p).then((r) => { if (!r.canceled) openJournal(p); }).catch(() => { });
}

function controls(p) {
  page(p, "aot.ui.btn.controls", ["aot.ui.ctl.anchor", "aot.ui.ctl.release", "aot.ui.ctl.boost",
                                  "aot.ui.ctl.spin", "aot.ui.ctl.nape", "aot.ui.ctl.pass",
                                  "aot.ui.ctl.ankle", "aot.ui.ctl.land", "aot.ui.ctl.blades",
                                  "aot.ui.ctl.gas", "aot.ui.ctl.spear", "aot.ui.ctl.grab",
                                  "aot.ui.ctl.flare"]);
}

function titans(p) {
  const keys = ["aot.ui.titan.intro"];
  for (const id of Object.keys(TITAN_TYPES)) keys.push(`aot.ui.titan.${TITAN_TYPES[id].key}`);
  keys.push("aot.ui.titan.night", "aot.ui.titan.regen");
  page(p, "aot.ui.btn.titans", keys);
}

function corps(p) {
  page(p, "aot.ui.btn.corps", ["aot.ui.corps.intro", "aot.ui.corps.levi", "aot.ui.corps.mikasa",
                               "aot.ui.corps.eren", "aot.ui.corps.armin", "aot.ui.corps.erwin",
                               "aot.ui.corps.hange", "aot.ui.corps.others", "aot.ui.corps.recruit"]);
}

export function giveKit(p, force = false) {
  if (!force && !isCreative(p) && boolProp(p, PROP.kit, false)) {
    tell(p, rt("§7", { t: "aot.msg.kit_taken" }));
    return;
  }
  const inv = container(p);
  if (!inv) return;
  const items = [[ITEM.gear, 1], [ITEM.jacket, 1], [ITEM.boots, 1], [ITEM.blades, 1],
                 [ITEM.spare, 16], [ITEM.gas, 4], [ITEM.spear, 4], [ITEM.flare, 1]];
  for (const [id, n] of items) {
    try {
      const left = inv.addItem(new ItemStack(id, n));
      if (left) p.dimension.spawnItem(left, p.location);
    } catch (_) { }
  }
  setProp(p, PROP.kit, true);
  setProp(p, PROP.gas, GAS_MAX);
  sound(p.dimension, "random.levelup", p.location, 1.2, 0.8);
  tell(p, rt("§a", { t: "aot.msg.kit_given" }));
}

function kit(p) { giveKit(p); }

function settings(p) {
  const f = new ModalFormData()
    .title(tr("aot.ui.btn.settings"))
    .toggle(tr("aot.ui.set.spawns"), !boolProp(world, PROP.spawns, false))
    .toggle(tr("aot.ui.set.grab"), !boolProp(world, PROP.grab, false))
    .toggle(tr("aot.ui.set.hud"), !boolProp(p, PROP.hud, false));
  f.show(p).then((r) => {
    if (r.canceled || !r.formValues) return;
    const [spawns, grab, hudOn] = r.formValues;
    setProp(world, PROP.spawns, !spawns);
    setProp(world, PROP.grab, !grab);
    setProp(p, PROP.hud, !hudOn);
    tell(p, rt("§7", { t: "aot.msg.saved" }));
  }).catch(() => { });
}
