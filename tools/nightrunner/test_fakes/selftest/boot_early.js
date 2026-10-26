// 自己テスト: 起動で壊れるアドオン（1）— 最上位（early execution）で world を触る。握りつぶしても違反 "early"。
import { world, ItemStack, system } from "@minecraft/server";

try { world.getDimension("overworld"); } catch { /* わざと握りつぶす */ }
try { new ItemStack("nr:test_pebble"); } catch { /* 同上 */ }
system.beforeEvents.startup.subscribe((ev) => {
  ev.itemComponentRegistry.registerCustomComponent("nr:test_weapon", {});
  ev.blockComponentRegistry.registerCustomComponent("nr:test_trap", {});
});
