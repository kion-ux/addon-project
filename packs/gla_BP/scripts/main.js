// ===========================================================================
//  GRAND LINE AWAKENING  /  ワンピース統合版アドオン（非公式ファン制作）
//
//  入力 → ゲーム状態 → 戦闘処理 → 表示用の状態 の順に一方向で流す
//  （企画書 §13）。ここは入力の受け口と、各層の tick を回すだけの薄い層。
//
//  操作（企画書 §09）:
//    麦わら帽子を使う       変身／解除
//    しゃがみ＋麦わら帽子   形態を選ぶ
//    拳の包帯を使う         選択中の技を1回発動
//    しゃがみ＋拳の包帯     次の技へ切替（発動とは排他）
//    ログポースを使う       設定・訓練場・復旧
// ===========================================================================
import { world, system } from "@minecraft/server";
import { ITEM, PROP, ENERGY_MAX, FORM_ORDER } from "./data.js";
import { tr, tell, allPlayers, forget, setProp } from "./util.js";
import {
  hasPower, grantPower, transform, revert, safeReset, restore, tick as tickState,
  formKey, sweepFormItems, isTransformed, markFight, preferredForm,
  inShowpiece, skipShowpiece,
} from "./state.js";
import { useSelected, cycleTech, forgetPlayer, forgetImpact } from "./skills.js";
import { openForms, openSettings, openTechList } from "./ui.js";
import { stopBuilding } from "./training.js";

// ---------------------------------------------------------------------------
//  入力 — 1つの経路に正規化する（企画書 §13 入力層 / §18 増殖・二重発動）
// ---------------------------------------------------------------------------
export function handleUse(player, itemStack) {
  const id = itemStack?.typeId;
  if (!id) return;

  if (id === ITEM.hat) {
    if (player.isSneaking) { openForms(player); return; }
    // 看板演出の最中は「解除」ではなく「スキップ」。状態が確定する前は
    // skipShowpiece 側が弾くので、技の連発には繋がらない（企画書 §08）。
    if (inShowpiece(player)) { skipShowpiece(player); return; }
    if (formKey(player)) revert(player);
    else transformDefault(player);
    return;
  }
  if (id === ITEM.wrap) {
    // 切替と発動は排他。しゃがみ中は絶対に技を出さない。
    if (player.isSneaking) cycleTech(player, 1);
    else useSelected(player);
    return;
  }
  if (id === ITEM.pose) {
    if (player.isSneaking) openTechList(player);
    else openSettings(player);
  }
}

/** 素の「使う」で変身するときは、前に使っていた形態へ戻る。 */
export function transformDefault(player) {
  if (!hasPower(player)) { tell(player, tr("gla.msg.no_power")); return; }
  transform(player, preferredForm(player));
}

world.afterEvents.itemUse.subscribe((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  if (ev.itemStack?.typeId === ITEM.fruit) return;      // 食べ終わりで処理する
  handleUse(player, ev.itemStack);
});

// 悪魔の実は「食べ終わったら」能力を得る。
// itemCompleteUse が無い版のために、時間切れの保険も持つ。
const eating = new Map();

if (world.afterEvents.itemCompleteUse) {
  world.afterEvents.itemCompleteUse.subscribe((ev) => {
    const player = ev.source;
    if (player?.typeId !== "minecraft:player") return;
    if (ev.itemStack?.typeId !== ITEM.fruit) return;
    eating.delete(player.id);
    system.run(() => grantPower(player));
  });
}

world.afterEvents.itemStartUse?.subscribe?.((ev) => {
  const player = ev.source;
  if (player?.typeId !== "minecraft:player") return;
  if (ev.itemStack?.typeId !== ITEM.fruit) return;
  eating.set(player.id, system.currentTick);
});

system.runInterval(() => {
  if (!eating.size) return;
  for (const player of allPlayers()) {
    const started = eating.get(player.id);
    if (started === undefined) continue;
    if (system.currentTick - started < 44) continue;
    eating.delete(player.id);
    if (!hasPower(player)) grantPower(player);
  }
}, 10);

// ---------------------------------------------------------------------------
//  命中数（解放条件）— 変身中の素手の殴打も習熟に数える
// ---------------------------------------------------------------------------
world.afterEvents.entityHitEntity.subscribe((ev) => {
  const player = ev.damagingEntity;
  if (player?.typeId !== "minecraft:player") return;
  if (!isTransformed(player)) return;
  system.run(() => {
    try { markFight(player); } catch (_) { }
  });
});

// ---------------------------------------------------------------------------
//  参加・退出・世界
// ---------------------------------------------------------------------------
world.afterEvents.playerSpawn.subscribe((ev) => {
  const player = ev.player;
  system.run(() => {
    try {
      restore(player);
      if (ev.initialSpawn) {
        tell(player, tr("gla.msg.welcome"));
        tell(player, tr("gla.msg.welcome_hint"));
        tell(player, tr("gla.msg.welcome_unofficial"));
      }
    } catch (_) { }
  });
});

world.afterEvents.playerLeave.subscribe((ev) => {
  const id = ev.playerId;
  forget(id);
  forgetPlayer(id);
  forgetImpact(id);
  stopBuilding(id);            // 建築中のまま抜けても、次の tick で止まる
});

// ---------------------------------------------------------------------------
//  ループ
// ---------------------------------------------------------------------------
let second = 0;
system.runInterval(() => {
  second++;
  try { tickState(); } catch (e) { console.warn(`[gla] tick: ${e}`); }
  if (second % 5 === 0) {
    // 変身していないのに形態アイテムを持っていたら捨てる（増殖・持ち出し防止）
    for (const player of allPlayers()) {
      try { sweepFormItems(player); } catch (_) { }
    }
  }
}, 20);

// ---------------------------------------------------------------------------
//  開発・検証用コマンド
//  企画書 §12「開発用の取得手段を製品ルールと分けて用意する」。
//  製品の進行（解放条件・レシピ）はこれらに依存しない。
// ---------------------------------------------------------------------------
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  const src = ev.sourceEntity;
  if (src?.typeId !== "minecraft:player") return;
  switch (ev.id) {
    case "gla:power":
      grantPower(src, true);
      break;
    case "gla:unlock": {
      // 全形態を解放する（検証用）
      const need = Math.max(...FORM_ORDER.map(() => 0), 320);
      setProp(src, PROP.hits, Math.max(need, 9999));
      tell(src, tr("gla.msg.dev_unlocked"));
      break;
    }
    case "gla:reset":
      safeReset(src);
      setProp(src, PROP.power, false);
      setProp(src, PROP.hits, 0);
      setProp(src, PROP.energy, ENERGY_MAX);
      tell(src, tr("gla.msg.dev_reset"));
      break;
    case "gla:recover":
      safeReset(src);
      break;
    case "gla:form":
      if (ev.message && FORM_ORDER.includes(ev.message)) transform(src, ev.message);
      else openForms(src);
      break;
    default:
      break;
  }
}, { namespaces: ["gla"] });

world.afterEvents.worldLoad?.subscribe?.(() => {
  console.warn("[gla] GRAND LINE AWAKENING loaded / 非公式ファン制作アドオン");
});
