// UI / 形態選択と設定
//
// 企画書 §12「通常プレイでは形態名、選択中の技、気力、再使用待ちだけを簡潔に
// 表示。詳細説明はメニューへ分ける」。画面に出しっぱなしにするものと、
// ここで開くものを分けている。
//
// スマホの読みやすさ（§12）のため、ボタンは短い表示名だけにし、説明は本文へ回す。
import { system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";
import { FORM_ORDER, FORM_BY_KEY, TECHS_BY_FORM, TECH_BY_ID, QUALITY_ORDER,
  PROP,
} from "./data.js";
import { tr, tell, setProp, clamp } from "./util.js";
import { formKey, transform, revert, safeReset, unlocked, hits, energy,
  quality, shortFx, cameraFx, infinite, techIndex, setTechIndex, hasPower,
} from "./state.js";
import { terrainAllowed, pvpAllowed, setTerrain, setPvp } from "./combat.js";
import { buildTrainingGround, removeTrainingGround } from "./training.js";

/** UserBusy で弾かれたら少し待って出し直す。タッチ端末では普通に起きる。 */
async function show(form, player, tries = 6) {
  for (let i = 0; i < tries; i++) {
    let res;
    try { res = await form.show(player); } catch (_) { return undefined; }
    if (res?.cancelationReason === "UserBusy") {
      await new Promise((r) => system.runTimeout(r, 20));
      continue;
    }
    return res;
  }
  return undefined;
}

// ---------------------------------------------------------------------------
//  形態選択（麦わら帽子 + しゃがみ）
// ---------------------------------------------------------------------------
export function openForms(player) {
  if (!hasPower(player)) { tell(player, tr("gla.msg.no_power")); return; }
  const cur = formKey(player);
  const body = {
    rawtext: [
      { translate: "gla.ui.forms_body",
        with: [String(hits(player)), String(Math.round(energy(player)))] },
    ],
  };
  const form = new ActionFormData().title(tr("gla.ui.forms")).body(body);
  const keys = [];
  for (const key of FORM_ORDER) {
    const f = FORM_BY_KEY[key];
    const open = unlocked(player, key);
    keys.push(open ? key : null);
    const mark = key === cur ? "§a> " : open ? "§f" : "§8";
    form.button({
      rawtext: [
        { text: mark }, { translate: f.name },
        open ? { text: "" }
             : { translate: "gla.ui.locked_at", with: [String(f.unlock)] },
      ],
    });
  }
  form.button(tr("gla.ui.revert"));

  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    if (res.selection === keys.length) { revert(player); return; }
    const key = keys[res.selection];
    if (!key) { tell(player, tr("gla.msg.locked")); return; }
    if (key === formKey(player)) { tell(player, tr("gla.msg.already_form")); return; }
    transform(player, key);
  });
}

// ---------------------------------------------------------------------------
//  技一覧（形態選択から辿れる詳細。HUD には出さない）
// ---------------------------------------------------------------------------
export function openTechList(player) {
  const key = formKey(player);
  if (!key) { tell(player, tr("gla.msg.not_transformed")); return; }
  const list = TECHS_BY_FORM[key] ?? [];
  const cur = techIndex(player, key);
  const form = new ActionFormData()
    .title(tr("gla.ui.techlist"))
    .body({ rawtext: [{ translate: FORM_BY_KEY[key].name }] });
  for (let i = 0; i < list.length; i++) {
    const t = TECH_BY_ID[list[i]];
    form.button({
      rawtext: [
        { text: i === cur ? "§a> " : "§f" }, { translate: t.name },
        { text: `\n§7${Math.round(t.damage)}dmg §8/ §7${t.cost}§8気力` },
      ],
    });
  }
  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    setTechIndex(player, key, res.selection);
    const t = TECH_BY_ID[list[res.selection]];
    tell(player, { rawtext: [{ translate: "gla.msg.tech_selected" },
                             { text: " §e" }, { translate: t.name }] });
  });
}

// ---------------------------------------------------------------------------
//  設定（ログポース）
//
//  企画書 §09: 気力無限は「消費だけ無効」。クールダウン・被ダメージ・解放条件は
//  ここからは触れない。地形破壊と PvP はホスト向けの別項目にしてある。
// ---------------------------------------------------------------------------
export function openSettings(player) {
  const form = new ActionFormData()
    .title(tr("gla.ui.settings"))
    .body(tr("gla.ui.settings_body"))
    .button(tr("gla.ui.display"))
    .button(tr("gla.ui.play"))
    .button(tr("gla.ui.training"))
    .button(tr("gla.ui.host"))
    .button(tr("gla.ui.recover"))
    .button(tr("gla.ui.help"));

  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    switch (res.selection) {
      case 0: openDisplay(player); break;
      case 1: openPlay(player); break;
      case 2: openTraining(player); break;
      case 3: openHost(player); break;
      case 4: safeReset(player); break;
      case 5: openHelp(player); break;
    }
  });
}

function openDisplay(player) {
  const qKeys = QUALITY_ORDER;
  const qLabels = qKeys.map((k) => ({ rawtext: [{ translate: `gla.quality.${k}` }] }));
  const cur = Math.max(0, qKeys.indexOf(quality(player)));
  const form = new ModalFormData()
    .title(tr("gla.ui.display"))
    .dropdown(tr("gla.ui.quality"), qLabels, cur)
    .toggle(tr("gla.ui.shortfx"), shortFx(player))
    .toggle(tr("gla.ui.camerafx"), cameraFx(player));

  show(form, player).then((res) => {
    if (!res || res.canceled || !res.formValues) return;
    const [q, short, cam] = res.formValues;
    setProp(player, PROP.quality, qKeys[clamp(Number(q) | 0, 0, qKeys.length - 1)]);
    setProp(player, PROP.shortfx, !!short);
    setProp(player, PROP.camerafx, !!cam);
    tell(player, tr("gla.msg.saved"));
  });
}

function openPlay(player) {
  // 気力無限は「消費だけ無効」。ここからクールダウンや被ダメージには触らない
  // （企画書 §09 / QA-09）。
  const form = new ModalFormData()
    .title(tr("gla.ui.play"))
    .toggle(tr("gla.ui.infinite"), infinite(player));
  show(form, player).then((res) => {
    if (!res || res.canceled || !res.formValues) return;
    const on = !!res.formValues[0];
    setProp(player, PROP.infinite, on);
    tell(player, on ? tr("gla.msg.infinite_on") : tr("gla.msg.infinite_off"));
  });
}

function openTraining(player) {
  const form = new ActionFormData()
    .title(tr("gla.ui.training"))
    .body(tr("gla.ui.training_body"))
    .button(tr("gla.ui.training_build"))
    .button(tr("gla.ui.training_clear"));
  show(form, player).then((res) => {
    if (!res || res.canceled) return;
    if (res.selection === 0) buildTrainingGround(player);
    else removeTrainingGround(player);
  });
}

function openHost(player) {
  const form = new ModalFormData()
    .title(tr("gla.ui.host"))
    .toggle(tr("gla.ui.terrain"), terrainAllowed())
    .toggle(tr("gla.ui.pvp"), pvpAllowed());
  show(form, player).then((res) => {
    if (!res || res.canceled || !res.formValues) return;
    setTerrain(!!res.formValues[0]);
    setPvp(!!res.formValues[1]);
    tell(player, tr("gla.msg.saved"));
  });
}

function openHelp(player) {
  const form = new ActionFormData()
    .title(tr("gla.ui.help"))
    .body({
      rawtext: [
        { translate: "gla.help.hat" }, { text: "\n\n" },
        { translate: "gla.help.wrap" }, { text: "\n\n" },
        { translate: "gla.help.pose" }, { text: "\n\n" },
        { translate: "gla.help.unlock" }, { text: "\n\n" },
        { translate: "gla.help.energy" },
      ],
    })
    .button(tr("gla.ui.close"));
  show(form, player);
}
