// 自己テスト用の小さな偽アドオン（test_nr.py の自己テストが作業フォルダの scripts/ に置く）。
// 本物のアドオンが使う形（DESIGN.md §4 の体力プール・部位判定・ゴアのプロパティ・演出・フォーム・街づくり）を
// 一通り「正しく」使う。selftest.mjs がこれを動かして偽物の振る舞いを確かめる。
import {
  world, system, Player, MolangVariableMap, EntityDamageCause, InputButton, ButtonState, StructureRotation,
  CommandPermissionLevel, CustomCommandParamType, CustomCommandStatus, EntityInitializationCause,
} from "@minecraft/server";
import { ActionFormData, ModalFormData, MessageFormData } from "@minecraft/server-ui";
import { hitPart, norm, sub, clamp } from "./lib.js";

const ZT = ["nr:z_test"];
export const STATE = {
  startupOk: false, worldLoaded: false, ticks: 0, hits: [], formResults: [], buttons: [], scriptEvents: [],
  used: 0, weaponHits: 0, weaponParams: undefined, stepped: 0, trapTicks: 0, jobDone: 0, waited: undefined,
  died: 0, deadEvents: 0, projHits: 0, projLoc: undefined, spawnedCauses: [], removed: [], early: system.currentTick,
};

// ---- 起動 -------------------------------------------------------------------------------
system.beforeEvents.startup.subscribe((ev) => {
  ev.itemComponentRegistry.registerCustomComponent("nr:test_weapon", {
    onUse(e) { STATE.used++; e.source.playSound("nr.test.swing"); },
    onHitEntity(e, p) { STATE.weaponHits++; STATE.weaponParams = p.params; },
    onBeforeDurabilityDamage(e) { e.durabilityDamage = 2; },
  });
  ev.blockComponentRegistry.registerCustomComponent("nr:test_trap", {
    onStepOn(e, p) {
      const params = /** @type {{damage?: number}} */ (p.params);
      e.entity?.applyDamage(params.damage ?? 1, { cause: EntityDamageCause.contact });
      STATE.stepped++;
    },
    onTick() { STATE.trapTicks++; },
  });
  ev.customCommandRegistry.registerCommand(
    { name: "nr:selftest", description: "self test", permissionLevel: CommandPermissionLevel.Any, cheatsRequired: false,
      mandatoryParameters: [{ name: "n", type: CustomCommandParamType.Integer }] },
    (origin, n) => {
      system.run(() => world.setDynamicProperty("nr:cmd", n));   // コールバックは書けない文脈
      return { status: CustomCommandStatus.Success };
    });
  STATE.startupOk = true;
});

world.afterEvents.worldLoad.subscribe(() => {
  world.setDynamicProperty("nr:settings", JSON.stringify({ gore: 100 }));
  STATE.worldLoaded = true;
});

system.runInterval(() => { STATE.ticks++; }, 1);

// ---- 出現・体力・部位・ゴア --------------------------------------------------------------
world.afterEvents.entitySpawn.subscribe((ev) => {
  STATE.spawnedCauses.push(ev.cause);
  if (ev.entity.typeId === "nr:z_test" && ev.cause === EntityInitializationCause.Spawned) ev.entity.setDynamicProperty("nr:hp", 20);
});

world.afterEvents.entityHurt.subscribe((ev) => {
  const z = ev.hurtEntity;
  if (!z.isValid) return;
  const by = ev.damageSource.damagingEntity;
  const hp = Number(z.getDynamicProperty("nr:hp") ?? 20) - ev.damage;
  z.setDynamicProperty("nr:hp", hp);
  z.getComponent("minecraft:health")?.resetToMaxValue();          // プールを戻す（DESIGN.md §4）
  let part = "torso";
  if (by instanceof Player && ev.damageSource.cause === EntityDamageCause.entityAttack) part = hitPart(z, by.getHeadLocation(), by.getViewDirection());
  STATE.hits.push({ part, damage: ev.damage, cause: ev.damageSource.cause, by: by?.typeId });
  const vars = new MolangVariableMap();
  vars.setFloat("variable.size", 1.5);
  vars.setColorRGB("variable.color", { red: 0.6, green: 0, blue: 0 });
  z.dimension.spawnParticle("nr:test_blood", z.location, vars);
  z.dimension.playSound("nr.test.hit", z.location, { volume: 1, pitch: 1 });
  z.setProperty("nr:blood", clamp(Number(z.getProperty("nr:blood")) + 1, 0, 3));
  if (part === "head" && ev.damage >= 10) z.setProperty("nr:head", "severed");
  if (part === "arm_r" && ev.damage >= 10) z.setProperty("nr:arm_r", "cut_upper");
  const d = by ? norm(sub(z.location, by.location)) : { x: 0, y: 0, z: 1 };
  z.applyImpulse({ x: d.x * 0.6, y: 0.35, z: d.z * 0.6 });
  if (by instanceof Player) by.applyKnockback({ x: -d.x * 0.3, z: -d.z * 0.3 }, 0.1);
  z.playAnimation("animation.nr.z.test_react", { controller: "nr.oneshot", stopExpression: "q.any_animation_finished", nextState: "none", blendOutTime: 0.1 });
  if (hp <= 0 && z.getProperty("nr:state") !== "dead") {
    z.triggerEvent("nr:on_death");
    STATE.deadEvents++;
  }
}, { entityTypes: ZT });

world.afterEvents.entityDie.subscribe(() => { STATE.died++; }, { entityTypes: ZT });
world.afterEvents.entityRemove.subscribe((ev) => { STATE.removed.push(ev.typeId); });
world.afterEvents.projectileHitEntity.subscribe((ev) => {
  if (!ev.projectile.typeId.startsWith("nr:proj_")) return;
  STATE.projHits++;
  STATE.projLoc = ev.location;
});

// ---- 入力 ----------------------------------------------------------------------------------
world.afterEvents.playerButtonInput.subscribe((ev) => {
  STATE.buttons.push(`${ev.button}:${ev.newButtonState}`);
  if (ev.button === InputButton.Jump && ev.newButtonState === ButtonState.Pressed) ev.player.applyKnockback({ x: 0, z: 0.5 }, 0.5);
}, { buttons: [InputButton.Jump] });

// ---- フォーム（before では開かず system.run へ） -------------------------------------------
world.beforeEvents.itemUse.subscribe((ev) => {
  if (ev.itemStack.typeId !== "nr:test_terminal") return;
  ev.cancel = true;
  const p = ev.source;
  system.run(() => { terminal(p).catch((e) => console.warn("[nr] form", e)); });
});

/** @param {Player} p */
async function terminal(p) {
  const a = await new ActionFormData().title("端末").body("選ぶ")
    .button("設定", "textures/nr/ui/settings").button("確認").show(p);
  if (a.canceled) { STATE.formResults.push({ canceled: true, reason: a.cancelationReason }); return; }
  if (a.selection === 0) {
    const m = await new ModalFormData().title("設定")
      .slider("ゴアレベル", 0, 100, { defaultValue: 100, valueStep: 5 })
      .toggle("血しぶき", { defaultValue: true })
      .dropdown("難易度", ["Easy", "Normal", "Hard"], { defaultValueIndex: 1 })
      .textField("名前", "Runner", { defaultValue: "" })
      .label("（入力の後ろの説明は置いてよい）")
      .submitButton("保存").show(p);
    if (m.canceled || !m.formValues) { STATE.formResults.push({ canceled: true, reason: m.cancelationReason }); return; }
    world.setDynamicProperty("nr:gore", Number(m.formValues[0]));
    STATE.formResults.push({ values: m.formValues });
  } else {
    const yn = await new MessageFormData().title("確認").body("リセット？").button1("はい").button2("いいえ").show(p);
    STATE.formResults.push({ message: yn.selection });
  }
}

// ---- /scriptevent → 構造物と runJob、waitTicks --------------------------------------------
system.afterEvents.scriptEventReceive.subscribe((ev) => {
  STATE.scriptEvents.push(ev.id);
  if (ev.id === "nr:build") build(JSON.parse(ev.message || "{}"));
  if (ev.id === "nr:wait") waitAndMark();
}, { namespaces: ["nr"] });

/** @param {{x?: number, z?: number}} o */
function build(o) {
  const dim = world.getDimension("overworld");
  world.structureManager.place("nr:test_hut", dim, { x: o.x ?? 10, y: 64, z: o.z ?? 10 }, { rotation: StructureRotation.Rotate90, includeEntities: false });
  system.runJob((function* () {
    for (let i = 0; i < 20; i++) { dim.setBlockType({ x: 20 + i, y: 64, z: 0 }, "nr:test_lamp"); yield; }
    STATE.jobDone++;
  })());
}
async function waitAndMark() {
  await system.waitTicks(5);
  STATE.waited = system.currentTick;
}
