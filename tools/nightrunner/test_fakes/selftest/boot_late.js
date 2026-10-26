// 自己テスト: 起動で壊れるアドオン（2）— カスタムコンポーネントの登録の誤り。違反 "startup"。
//  * 無いフック名（onSwing）を持つコンポーネント
//  * startup の外（worldLoad の後）での登録
import { world, system } from "@minecraft/server";

/** @type {any} */
let keep;
system.beforeEvents.startup.subscribe((ev) => {
  keep = ev.blockComponentRegistry;
  try { ev.itemComponentRegistry.registerCustomComponent("nr:test_weapon", { onSwing() {} }); } catch { /* わざと */ }
});
world.afterEvents.worldLoad.subscribe(() => {
  try { keep.registerCustomComponent("nr:test_trap", { onTick() {} }); } catch { /* わざと */ }
});
