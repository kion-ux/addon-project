// core/components.js: BP のカスタムコンポーネントを startup で全部登録し、足したハンドラへ配る
import { test, expect, DATA, S } from "nr-test";
import {
  componentStatus, onBlockComponent, onItemComponent, dispatch, hasHandler, BLOCK_HOOKS, ITEM_HOOKS,
} from "../scripts/core/components.js";

test("components: BP（data/components.js）の全部が startup で登録されている", () => {
  const st = componentStatus();
  expect(st.started).toBe(true);
  const blocks = DATA.components.BLOCK_COMPONENTS;
  const items = DATA.components.ITEM_COMPONENTS;
  expect(blocks.length).toBeGreaterThan(0);
  for (const n of blocks) {
    expect(`${n} ${n in st.block}`).toBe(`${n} true`);
    expect(`${n} ${S.reg.block.has(n)}`).toBe(`${n} true`);
  }
  for (const n of items) {
    expect(`${n} ${n in st.item}`).toBe(`${n} true`);
    expect(`${n} ${S.reg.item.has(n)}`).toBe(`${n} true`);
  }
  // 登録したフックはハンドラのあるものだけ（無いフックは登録しない = 何も起きない）
  for (const [kind, table] of [["block", st.block], ["item", st.item]]) {
    for (const [name, hooks] of Object.entries(table)) {
      for (const h of hooks) expect(`${kind} ${name}.${h} ${hasHandler(/** @type {any} */ (kind), name, h)}`).toBe(`${kind} ${name}.${h} true`);
    }
  }
});

test("components: dispatch は足した順に全部呼び、(event, params, name) を渡す。外すと呼ばれない", () => {
  /** @type {string[]} */
  const log = [];
  const ev = { block: { typeId: "nr:bear_trap" } };
  const un1 = onBlockComponent("nr:trap", { onStepOn: (e, p, n) => { log.push(`a ${e.block.typeId} ${p.damage} ${n}`); } });
  const un2 = onBlockComponent("nr:trap", { onStepOn: (e, p) => { log.push(`b ${p.damage}`); } });
  expect(dispatch("block", "nr:trap", "onStepOn", ev, { damage: 6 })).toBe(2);
  expect(log).toEqual(["a nr:bear_trap 6 nr:trap", "b 6"]);
  un1();
  expect(dispatch("block", "nr:trap", "onStepOn", ev, { damage: 2 })).toBe(1);
  un2();
  expect(dispatch("block", "nr:trap", "onStepOn", ev, {})).toBe(0);
  expect(hasHandler("block", "nr:trap", "onStepOn")).toBe(false);
  // アイテム
  let got = 0;
  const un3 = onItemComponent("nr:weapon", { onHitEntity: (e, p) => { got += p.n; } });
  expect(dispatch("item", "nr:weapon", "onHitEntity", {}, { n: 3 })).toBe(1);
  expect(got).toBe(3);
  un3();
});

test("components: d.ts に無いフック名・名前の形が違うものは足さない（警告だけ）", () => {
  const un = onBlockComponent("nr:trap", /** @type {any} */ ({ onBreak: () => {}, onTick: "x" }));
  expect(hasHandler("block", "nr:trap", "onBreak")).toBe(false);
  expect(hasHandler("block", "nr:trap", "onTick")).toBe(false);
  un();
  const un2 = onItemComponent("Bad Name", { onUse: () => {} });
  expect(hasHandler("item", "Bad Name", "onUse")).toBe(false);
  un2();
  expect(BLOCK_HOOKS).toContain("onStepOn");
  expect(BLOCK_HOOKS).not.toContain("onBreak");          // ベータ専用
  expect(ITEM_HOOKS).toContain("onBeforeDurabilityDamage");
});
