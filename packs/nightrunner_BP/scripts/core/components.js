// ===========================================================================
//  NIGHT RUNNER: 感染都市 — カスタムコンポーネントの登録（Custom Components V2。reference/script_api.md §2）
//
//  BP のブロック・アイテムの JSON が使う nr:* のカスタムコンポーネント（data/components.js。gen_nr_data_js が
//  BP の blocks/ items/ を走査して書く）を system.beforeEvents.startup で**全部**登録する（JSON が使うのに
//  登録が無いと、実機ではそのブロック／アイテムが読み込みエラー）。振る舞いは各モジュールが
//  **import の時（モジュールの最上位）**に足す:
//
//    import { onBlockComponent, onItemComponent } from "../core/components.js";
//    onBlockComponent("nr:trap", {
//      onStepOn(e, params, name) { ... },          // e = BlockComponentStepOnEvent、params = JSON の値（unknown）
//      onTick(e, params) { ... },
//    });
//    onItemComponent("nr:weapon", { onHitEntity(e, params) { ... } });
//
//  * 登録するフックは「startup の時点でハンドラが 1 つ以上あるもの」だけ。ハンドラの無いフックは登録しない
//    （= 何も起きない）。onPlayerInteract を登録するとブロックが「触れる」ブロックになり手のブロックを
//    その面に置けなくなる、onTick は minecraft:tick の無いブロックでコンテンツエラー、などの副作用を避けるため。
//  * startup の後に足したハンドラは、そのフックが登録済みなら次の呼び出しから届く。未登録のフックには
//    届かない（警告を 1 回）。だから足すのは必ず import の時に。
//  * 同じ（名前, フック）に複数のハンドラ: 足した順に全部呼ぶ。1 つの例外は他を止めない（console.error に出す）。
//  * ハンドラの引数は (event, params, name)。params は JSON に書いた値の辞書（CustomComponentParameters.params。
//    型は unknown なので JSDoc で付けて読む）、name はコンポーネントの名前（1 つの関数を複数の名前で使う時）。
//  * beforeOnPlayerPlace は before イベント（読み取り専用）: ワールドを書き換えず system.run へ。
//    e.cancel = true で置くのを止められる。onBeforeDurabilityDamage は e.durabilityDamage を書き換えられる。
//  * data に無い名前でも onBlockComponent / onItemComponent すれば登録する（登録だけして JSON で使わないのは無害）。
//  * onTick を足す名前を minecraft:tick の無いブロックが使っていたら（data の UNTICKED_BLOCKS）startup で警告する。
// ===========================================================================
import { system } from "@minecraft/server";
import { BLOCK_COMPONENTS, ITEM_COMPONENTS, UNTICKED_BLOCKS } from "../data/components.js";
import { warnOnce } from "./util.js";

/** @typedef {import("@minecraft/server").BlockCustomComponent} BlockCustomComponent */
/** @typedef {import("@minecraft/server").ItemCustomComponent} ItemCustomComponent */
/** @typedef {"block" | "item"} Kind */
/**
 * ブロックのハンドラ（全部省略可）。引数は (event, params = JSON の値, name = コンポーネントの名前)。
 * @typedef {object} BlockHandlers
 * @property {(e: import("@minecraft/server").BlockComponentPlayerPlaceBeforeEvent, params: any, name: string) => void} [beforeOnPlayerPlace]
 * @property {(e: import("@minecraft/server").BlockComponentEntityFallOnEvent, params: any, name: string) => void} [onEntityFallOn]
 * @property {(e: import("@minecraft/server").BlockComponentOnPlaceEvent, params: any, name: string) => void} [onPlace]
 * @property {(e: import("@minecraft/server").BlockComponentPlayerBreakEvent, params: any, name: string) => void} [onPlayerBreak]
 * @property {(e: import("@minecraft/server").BlockComponentPlayerInteractEvent, params: any, name: string) => void} [onPlayerInteract]
 * @property {(e: import("@minecraft/server").BlockComponentRandomTickEvent, params: any, name: string) => void} [onRandomTick]
 * @property {(e: import("@minecraft/server").BlockComponentStepOffEvent, params: any, name: string) => void} [onStepOff]
 * @property {(e: import("@minecraft/server").BlockComponentStepOnEvent, params: any, name: string) => void} [onStepOn]
 * @property {(e: import("@minecraft/server").BlockComponentTickEvent, params: any, name: string) => void} [onTick]
 */
/**
 * アイテムのハンドラ（全部省略可）。引数は (event, params, name)。
 * @typedef {object} ItemHandlers
 * @property {(e: import("@minecraft/server").ItemComponentBeforeDurabilityDamageEvent, params: any, name: string) => void} [onBeforeDurabilityDamage]
 * @property {(e: import("@minecraft/server").ItemComponentCompleteUseEvent, params: any, name: string) => void} [onCompleteUse]
 * @property {(e: import("@minecraft/server").ItemComponentConsumeEvent, params: any, name: string) => void} [onConsume]
 * @property {(e: import("@minecraft/server").ItemComponentHitEntityEvent, params: any, name: string) => void} [onHitEntity]
 * @property {(e: import("@minecraft/server").ItemComponentMineBlockEvent, params: any, name: string) => void} [onMineBlock]
 * @property {(e: import("@minecraft/server").ItemComponentUseEvent, params: any, name: string) => void} [onUse]
 * @property {(e: import("@minecraft/server").ItemComponentUseOnEvent, params: any, name: string) => void} [onUseOn]
 */
/** @typedef {(e: any, params: any, name: string) => void} AnyHandler */

/** d.ts（@minecraft/server 2.3.0）の BlockCustomComponent のフック。onBreak はベータ専用なので無い。 */
export const BLOCK_HOOKS = Object.freeze(["beforeOnPlayerPlace", "onEntityFallOn", "onPlace", "onPlayerBreak",
  "onPlayerInteract", "onRandomTick", "onStepOff", "onStepOn", "onTick"]);
/** d.ts の ItemCustomComponent のフック。 */
export const ITEM_HOOKS = Object.freeze(["onBeforeDurabilityDamage", "onCompleteUse", "onConsume", "onHitEntity",
  "onMineBlock", "onUse", "onUseOn"]);

const NAME_RE = /^[a-z0-9_]+:[a-z0-9_]+$/;

/** 足されたハンドラ: kind → 名前 → フック → 関数の並び（足した順）。 @type {Record<Kind, Map<string, Map<string, AnyHandler[]>>>} */
const handlers = { block: new Map(), item: new Map() };
/** startup で登録したもの: kind → 名前 → 登録したフック。 @type {Record<Kind, Map<string, Set<string>>>} */
const registered = { block: new Map(), item: new Map() };
let started = false;

/**
 * @param {Kind} kind @param {string} name @param {Record<string, any>} obj @returns {() => void}
 */
function addHandlers(kind, name, obj) {
  const label = `${kind === "block" ? "onBlockComponent" : "onItemComponent"}(${name})`;
  if (typeof name !== "string" || !NAME_RE.test(name) || name.startsWith("minecraft:")) {
    warnOnce(`comp-name:${kind}:${name}`, `${label}: 名前は "nr:xxx"（小文字・数字・_）`);
    return () => {};
  }
  const hooks = kind === "block" ? BLOCK_HOOKS : ITEM_HOOKS;
  let byHook = handlers[kind].get(name);
  if (!byHook) { byHook = new Map(); handlers[kind].set(name, byHook); }
  /** @type {(() => void)[]} */
  const undo = [];
  for (const [hook, fn] of Object.entries(obj ?? {})) {
    if (!hooks.includes(hook)) { warnOnce(`comp-hook:${kind}:${name}:${hook}`, `${label}: ${kind} のカスタムコンポーネントに無いフック ${hook}（d.ts 2.3.0 の名前だけ）`); continue; }
    if (typeof fn !== "function") continue;
    let list = byHook.get(hook);
    if (!list) { list = []; byHook.set(hook, list); }
    const l = list;
    l.push(fn);
    if (started && !registered[kind].get(name)?.has(hook)) {
      warnOnce(`comp-late:${kind}:${name}:${hook}`, `${label}.${hook}: startup の後に足したので届かない（モジュールの最上位で足す）`);
    }
    undo.push(() => { const i = l.indexOf(fn); if (i >= 0) l.splice(i, 1); });
  }
  return () => { for (const u of undo) u(); };
}

/**
 * ブロックのカスタムコンポーネントにハンドラを足す（モジュールの最上位で）。戻り値を呼ぶと外す。
 * @param {string} name 例 "nr:trap" @param {BlockHandlers} h @returns {() => void}
 */
export function onBlockComponent(name, h) { return addHandlers("block", name, /** @type {Record<string, any>} */ (h)); }

/**
 * アイテムのカスタムコンポーネントにハンドラを足す（モジュールの最上位で）。戻り値を呼ぶと外す。
 * @param {string} name 例 "nr:weapon" @param {ItemHandlers} h @returns {() => void}
 */
export function onItemComponent(name, h) { return addHandlers("item", name, /** @type {Record<string, any>} */ (h)); }

/** そのフックに今ハンドラがあるか。 @param {Kind} kind @param {string} name @param {string} hook */
export function hasHandler(kind, name, hook) { return (handlers[kind].get(name)?.get(hook)?.length ?? 0) > 0; }

/**
 * 登録の様子（テスト・デバッグ用）: {started, block: {名前: [登録したフック]}, item: {...}}。
 * @returns {{started: boolean, block: Record<string, string[]>, item: Record<string, string[]>}}
 */
export function componentStatus() {
  /** @param {Map<string, Set<string>>} m */
  const out = (m) => Object.fromEntries([...m].map(([k, v]) => [k, [...v].sort()]));
  return { started, block: out(registered.block), item: out(registered.item) };
}

/**
 * 1 つのフックの呼び出しを、足されたハンドラ全部へ配る（startup で登録する関数の中身。テストからも呼べる）。
 * @param {Kind} kind @param {string} name @param {string} hook @param {any} ev @param {any} params
 * @returns {number} 呼んだハンドラの数
 */
export function dispatch(kind, name, hook, ev, params) {
  const list = handlers[kind].get(name)?.get(hook);
  if (!list || !list.length) return 0;
  let n = 0;
  for (const fn of [...list]) {
    n++;
    try { fn(ev, params, name); } catch (err) {
      console.error(`[nr] ${kind} コンポーネント ${name}.${hook} の例外:`, err instanceof Error ? `${err.message}\n${err.stack ?? ""}` : String(err));
    }
  }
  return n;
}

/** @param {Kind} kind @param {string} name @param {string} hook @returns {(ev: any, p: any) => void} */
function relay(kind, name, hook) {
  return (ev, p) => { dispatch(kind, name, hook, ev, p?.params); };
}

/** startup で登録する中身（ハンドラのあるフックだけ）。 @param {Kind} kind @param {string} name */
function buildComponent(kind, name) {
  /** @type {Record<string, (ev: any, p: any) => void>} */
  const comp = {};
  for (const [hook, list] of handlers[kind].get(name) ?? []) if (list.length) comp[hook] = relay(kind, name, hook);
  return comp;
}

system.beforeEvents.startup.subscribe((ev) => {
  started = true;
  /** @type {[Kind, string[]][]} */
  const kinds = [["block", /** @type {string[]} */ (BLOCK_COMPONENTS ?? [])], ["item", /** @type {string[]} */ (ITEM_COMPONENTS ?? [])]];
  for (const [kind, listed] of kinds) {
    const names = [...new Set([...listed, ...handlers[kind].keys()])].sort();
    for (const name of names) {
      const comp = buildComponent(kind, name);
      if (kind === "block" && comp.onTick && /** @type {Record<string, string[]>} */ (UNTICKED_BLOCKS ?? {})[name]?.length) {
        warnOnce(`comp-untick:${name}`, `${name} に onTick を登録したが minecraft:tick の無いブロックがある（実機はコンテンツエラー）:`,
          /** @type {Record<string, string[]>} */ (UNTICKED_BLOCKS)[name].join(", "));
      }
      try {
        if (kind === "block") ev.blockComponentRegistry.registerCustomComponent(name, /** @type {BlockCustomComponent} */ (comp));
        else ev.itemComponentRegistry.registerCustomComponent(name, /** @type {ItemCustomComponent} */ (comp));
        registered[kind].set(name, new Set(Object.keys(comp)));
      } catch (err) {
        console.error(`[nr] カスタムコンポーネント ${name}（${kind}）を登録できない:`, err instanceof Error ? err.message : String(err));
      }
    }
  }
});
