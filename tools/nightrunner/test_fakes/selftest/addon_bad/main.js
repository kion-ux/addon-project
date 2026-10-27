// 自己テスト用の「壊れた」偽アドオン。/scriptevent nr:bad <種類> で、わざと契約違反をする。
// ほとんどを try/catch で握りつぶす — それでもテストは失敗にならなければいけない（selftest_bad.mjs）。
import { world, system, ItemStack, MolangVariableMap } from "@minecraft/server";
import { ModalFormData, ActionFormData } from "@minecraft/server-ui";

let MODE = "";
const swallow = (fn) => { try { fn(); } catch { /* わざと握りつぶす */ } };
const zombie = () => world.getDimension("overworld").getEntities({ type: "nr:z_test" })[0];
const player = () => world.getAllPlayers()[0];

system.beforeEvents.startup.subscribe((ev) => {
  ev.itemComponentRegistry.registerCustomComponent("nr:test_weapon", {});
  ev.blockComponentRegistry.registerCustomComponent("nr:test_trap", {});
});

const CASES = {
  particle: () => world.getDimension("overworld").spawnParticle("nr:no_such_particle", { x: 0, y: 65, z: 0 }),
  sound: () => player().playSound("nr.no.such_sound"),
  anim: () => zombie().playAnimation("animation.nr.z.no_such", { controller: "nr.oneshot", stopExpression: "1", nextState: "none" }),
  anim_opts: () => zombie().playAnimation("animation.nr.z.test_react"),
  entity: () => world.getDimension("overworld").spawnEntity("nr:z_no_such", { x: 0, y: 64, z: 0 }),
  item: () => new ItemStack("nr:no_such_item"),
  block: () => world.getDimension("overworld").setBlockType({ x: 0, y: 64, z: 0 }, "nr:no_such_block"),
  structure: () => world.structureManager.place("nr:no_such", world.getDimension("overworld"), { x: 0, y: 64, z: 0 }),
  event: () => zombie().triggerEvent("nr:no_such_event"),
  prop_enum: () => zombie().setProperty("nr:head", "gone"),
  prop_range: () => zombie().setProperty("nr:blood", 9),
  prop_name: () => zombie().setProperty("nr:no_such", 1),
  vector: () => zombie().applyImpulse({ x: NaN, y: 0, z: 0 }),
  molang: () => new MolangVariableMap().setFloat("size", 1),
  player_impulse: () => player().applyImpulse({ x: 0, y: 1, z: 0 }),
  player_remove: () => player().remove(),
  knockback_v1: () => zombie().applyKnockback(1, 0, 0.5, 0.3),
  dynprop_stack: () => new ItemStack("nr:test_pebble", 4).setDynamicProperty("nr:mods", "fire"),
  ui_toggle_v1: () => new ModalFormData().toggle("血", true),
  ui_slider_v1: () => new ModalFormData().slider("ゴア", 0, 100, 5, 100),
  ui_layout: () => new ActionFormData().title("x").label("説明").button("a").button("b").show(player()),
  budget: () => { for (let i = 0; i < 320; i++) world.getDimension("overworld").spawnParticle("nr:test_spark", { x: 0, y: 65, z: 0 }); },
  global: () => setTimeout(() => {}, 1),
  dimension_query: () => world.getDimension("overworld").getEntities({ maxDistance: 5 }),
  molang_nan: () => new MolangVariableMap().setFloat("variable.size", NaN),
  ui_layout_modal: () => new ModalFormData().title("m").slider("a", 0, 10).divider().toggle("b").show(player()),
  ui_dropdown_v1: () => new ModalFormData().dropdown("d", ["a", "b"], 1),
  struct_palette: () => world.structureManager.place("nr:test_bad_hut", world.getDimension("overworld"), { x: 0, y: 64, z: 0 }),
  effect: () => zombie().addEffect("no_such_effect", 20),
  spawn_event: () => world.getDimension("overworld").spawnEntity("nr:z_test", { x: 0, y: 64, z: 3 }, { spawnEvent: "nr:no_such" }),
  prop_typo: () => zombie().getProperty("nr:hed"),
  lore: () => new ItemStack("nr:w_test").setLore(["§7" + "x".repeat(49)]),
  options_query: () => world.getDimension("overworld").getEntities({ location: { x: 0, y: 64, z: 0 }, maxDistance: 5, famillies: ["nr_zombie"] }),
  options_anim: () => zombie().playAnimation("animation.nr.z.test_react", { controller: "nr.os", stopExpression: "q.any_animation_finished", nextState: "none", blendOuttime: 0.1 }),
};

system.afterEvents.scriptEventReceive.subscribe((ev) => {
  if (ev.id === "nr:mode") { MODE = ev.message; return; }
  if (ev.id === "nr:throw") throw new Error("購読者の中の捕まらない例外（わざと）");
  if (ev.id === "nr:console") { console.error("[nr] わざと console.error"); return; }
  if (ev.id === "nr:run_throw") { system.run(() => { throw new Error("system.run の中の捕まらない例外（わざと）"); }); return; }
  if (ev.id === "nr:reject") { void Promise.reject(new Error("捕まらない Promise の reject（わざと）")); return; }
  if (ev.id !== "nr:bad") return;
  const f = CASES[ev.message];
  if (!f) throw new Error(`知らない種類 ${ev.message}`);
  swallow(f);
}, { namespaces: ["nr"] });

// before イベント（read-only）の中でやってはいけないこと
world.beforeEvents.itemUse.subscribe((ev) => {
  const p = ev.source;
  if (MODE === "write") swallow(() => p.applyDamage(1));
  if (MODE === "form") swallow(() => { new ActionFormData().title("x").button("a").show(p); });
  if (MODE === "subscribe") swallow(() => world.afterEvents.entityHurt.subscribe(() => {}));
  if (MODE === "setter") swallow(() => { p.selectedSlotIndex = 1; });
  if (MODE === "property") swallow(() => p.dimension.getEntities({ type: "nr:z_test" })[0]?.setProperty("nr:blood", 1));
});
