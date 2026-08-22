// 討伐隊端末 / Defense Force terminal
import { system } from "@minecraft/server";
import { ActionFormData, ModalFormData, MessageFormData } from "@minecraft/server-ui";
import { PROP, ENERGY_MAX, RELEASE_CAP_NO_SUIT } from "./config.js";
import { tr, tell, num, distance } from "./util.js";
import { releaseRate, setReleaseRate, wearsFullSuit } from "./weapons.js";
import { TECH, selectedIndex } from "./techniques.js";
import { rankKey } from "./kaiju.js";
import { hasPower, isTransformed } from "./transform.js";
import { alertsEnabled, setAlerts } from "./alert.js";

async function show(form, player, tries = 6) {
  for (let i = 0; i < tries; i++) {
    const res = await form.show(player);
    if (res.cancelationReason === "UserBusy") {
      await new Promise((r) => system.runTimeout(r, 20));
      continue;
    }
    return res;
  }
  return undefined;
}

export function scan(player, radius = 64) {
  let found = [];
  try {
    found = player.dimension.getEntities({
      location: player.location, maxDistance: radius, families: ["kaiju"],
    });
  } catch (_) { }
  found.sort((a, b) => distance(player.location, a.location) - distance(player.location, b.location));
  return found;
}

export function quickScan(player) {
  const found = scan(player);
  if (!found.length) {
    tell(player, tr("kaiju8.msg.scan_clear"));
    return;
  }
  const lines = [{ translate: "kaiju8.msg.scan_header", with: [String(found.length)] }];
  for (const k of found.slice(0, 5)) {
    lines.push({ text: "\n §7- §r" });
    lines.push({ translate: `entity.${k.typeId}.name` });
    lines.push({ text: ` §8${Math.round(distance(player.location, k.location))}m` });
  }
  tell(player, { rawtext: lines });
}

export function openTerminal(player) {
  const kills = num(player, PROP.kills, 0);
  const form = new ActionFormData()
    .title(tr("kaiju8.ui.terminal"))
    .body({
      rawtext: [
        { translate: "kaiju8.ui.body", with: [String(kills), String(releaseRate(player))] },
        { text: "\n§7" }, { translate: rankKey(kills) },
      ],
    })
    .button(tr("kaiju8.ui.set_release"))
    .button(tr("kaiju8.ui.techlist"))
    .button(tr("kaiju8.ui.record"))
    .button(tr("kaiju8.ui.scan"))
    .button(alertsEnabled() ? tr("kaiju8.ui.alerts_on") : tr("kaiju8.ui.alerts_off"));

  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    switch (res.selection) {
      case 0: return openRelease(player);
      case 1: return openTechList(player);
      case 2: return openRecord(player);
      case 3: return quickScan(player);
      case 4:
        setAlerts(!alertsEnabled());
        tell(player, tr(alertsEnabled() ? "kaiju8.msg.alerts_on" : "kaiju8.msg.alerts_off"));
        return;
    }
  }).catch(() => { });
}

function openRelease(player) {
  const cap = wearsFullSuit(player) ? 100 : RELEASE_CAP_NO_SUIT;
  const form = new ModalFormData()
    .title(tr("kaiju8.ui.set_release"))
    .slider(tr("kaiju8.ui.release_label"), 1, 100, 1, releaseRate(player));
  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    const value = Array.isArray(res.formValues) ? Number(res.formValues[0]) : 10;
    setReleaseRate(player, value);
    tell(player, tr("kaiju8.msg.release_set", String(value)));
    if (value > cap) tell(player, tr("kaiju8.msg.release_capped", String(cap)));
  }).catch(() => { });
}

function openTechList(player) {
  const lines = [{ translate: "kaiju8.ui.techlist_hint" }, { text: "\n" }];
  for (const [itemId, list] of Object.entries(TECH)) {
    const current = selectedIndex(player, itemId);
    lines.push({ text: "\n§e" });
    lines.push({ translate: `item.${itemId}` });
    lines.push({ text: "§r\n" });
    list.forEach((t, i) => {
      lines.push({ text: i === current ? "  §b▸ " : "  §8- " });
      lines.push({ translate: t.name });
      lines.push({ text: "§r\n" });
    });
  }
  const form = new MessageFormData()
    .title(tr("kaiju8.ui.techlist"))
    .body({ rawtext: lines })
    .button1(tr("kaiju8.ui.close"))
    .button2(tr("kaiju8.ui.close"));
  show(form, player).catch(() => { });
}

function openRecord(player) {
  const kills = num(player, PROP.kills, 0);
  const energy = Math.round(num(player, PROP.energy, ENERGY_MAX));
  const body = {
    rawtext: [
      { translate: "kaiju8.ui.record_kills", with: [String(kills)] },
      { text: "\n" }, { translate: "kaiju8.ui.record_rank" }, { text: " §b" },
      { translate: rankKey(kills) }, { text: "§r\n" },
      { translate: "kaiju8.ui.record_release", with: [String(releaseRate(player))] },
      { text: "\n" },
      { translate: "kaiju8.ui.record_suit", with: [wearsFullSuit(player) ? "§a○" : "§c×"] },
      { text: "\n" },
      {
        translate: "kaiju8.ui.record_no8",
        with: [hasPower(player) ? (isTransformed(player) ? "§c変身中" : `§b${energy}%`) : "§7—"],
      },
    ],
  };
  const form = new MessageFormData()
    .title(tr("kaiju8.ui.record"))
    .body(body)
    .button1(tr("kaiju8.ui.close"))
    .button2(tr("kaiju8.ui.close"));
  show(form, player).catch(() => { });
}
