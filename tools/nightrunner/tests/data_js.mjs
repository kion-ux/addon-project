// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 生成データ scripts/data/*.js（gen_nr_data_js.py）の約束（DESIGN §12）と、
//  BP のアイテム（gen_nr_items.py）との突き合わせ。アドオンの挙動には触らない（表だけを見る）。
// ===========================================================================
import { test, expect, DATA, S } from "nr-test";

// DESIGN §12 の表と、手書き JS が使う export（無いと import の時点で落ちる）
const NEED = {
  zombies: ["ZOMBIES", "ZTYPE", "ZOMBIE_BY_KEY", "ZOMBIE_BY_ID", "ABILITIES", "ATTACKS", "LOCOMOTIONS", "VOICES",
    "GORE_KEYS", "ABILITY_STATES"],
  weapons: ["WEAPONS", "WEAPON_BY_ID", "PROJECTILES", "PROJECTILE_BY_ID"],
  items: ["ITEMS", "ITEM_BY_ID"],
  mods: ["MODS", "MOD_BY_KEY"],
  traps: ["TRAPS", "TRAP_BY_ID", "TRAP_BLOCKS"],
  blocks: ["BLOCKS", "BLOCK_BY_ID"],
  props: ["PROPS", "PROP_BY_ID"],
  skills: ["SKILLS", "SKILL_BY_KEY", "XP_TO_NEXT"],
  crafting: ["CRAFTING"],
  settings: ["SETTINGS_DEFAULTS", "SETTINGS_SCHEMA", "PARKOUR_TUNING", "COMBAT_TUNING", "GORE_TUNING", "DIFFICULTY",
    "GORE_COMBOS", "STARTER_KIT", "LOOT_TABLES", "DTYPE_OUTCOMES", "ABILITY_STATES"],
  fx: ["PARTICLES", "SOUNDS", "PLAYER_ANIMS", "ZOMBIE_ONESHOTS", "ZOMBIE_ANIMATIONS"],
};

/** @param {any[]} xs */
const dups = (xs) => xs.filter((x, i) => xs.indexOf(x) !== i);

test("data: DESIGN §12 の export が全部ある", () => {
  const missing = [];
  for (const [file, names] of Object.entries(NEED)) {
    for (const n of names) if (!DATA[file] || DATA[file][n] === undefined) missing.push(`${file}.${n}`);
  }
  expect(missing).toEqual([]);
});

test("data: ZOMBIES は ztype の順（ZTYPE・id・索引が揃う）", () => {
  const { ZOMBIES, ZTYPE, ZOMBIE_BY_KEY, ZOMBIE_BY_ID } = DATA.zombies;
  expect(ZOMBIES.length).toBe(50);
  const bad = [];
  ZOMBIES.forEach((z, i) => {
    if (z.ztype !== i || ZTYPE[z.key] !== i || z.id !== `nr:z_${z.key}`) bad.push(z.key);
    if (ZOMBIE_BY_KEY[z.key] !== z || ZOMBIE_BY_ID[z.id] !== z) bad.push(`${z.key}(索引)`);
    if (!(z.hp > 0) || typeof z.ja !== "string" || typeof z.en !== "string") bad.push(`${z.key}(項目)`);
  });
  expect(bad).toEqual([]);
  expect(Object.keys(ZTYPE).length).toBe(50);
});

test("data: ability_states は 1..7 で、settings.js と zombies.js が同じ", () => {
  const bad = [];
  for (const z of DATA.zombies.ZOMBIES) {
    const st = z.ability_states;
    const vals = Object.values(st);
    if (vals.some((v) => !Number.isInteger(v) || v < 1 || v > 7) || dups(vals).length) bad.push(z.key);
    if (JSON.stringify(DATA.settings.ABILITY_STATES[z.key]) !== JSON.stringify(st)) bad.push(`${z.key}(settings)`);
    if (JSON.stringify(DATA.zombies.ABILITY_STATES[z.key]) !== JSON.stringify(st)) bad.push(`${z.key}(zombies)`);
  }
  expect(bad).toEqual([]);
});

test("data: 設定の既定（ゴアレベル 100）とスキーマが揃う", () => {
  const { SETTINGS_DEFAULTS, SETTINGS_SCHEMA } = DATA.settings;
  expect(SETTINGS_DEFAULTS.gore_level).toBe(100);
  const gore = SETTINGS_SCHEMA.find((s) => s.key === "gore_level");
  expect(gore && [gore.min, gore.max, gore.default]).toEqual([0, 100, 100]);
  expect(SETTINGS_SCHEMA.map((s) => s.key).sort()).toEqual(Object.keys(SETTINGS_DEFAULTS).sort());
});

test("data: ITEMS（素材 + その他）と索引、BP アイテムとの突き合わせ", () => {
  const { ITEMS, ITEM_BY_ID } = DATA.items;
  expect(dups(ITEMS.map((i) => i.id))).toEqual([]);
  expect(Object.keys(ITEM_BY_ID).length).toBe(ITEMS.length);
  const bp = (S && S.DEFS && S.DEFS.items) || {};
  const haveBp = Object.keys(bp).some((id) => id.startsWith("nr:") && !id.startsWith("nr:w_"));
  const bad = [];
  for (const it of ITEMS) {
    if (ITEM_BY_ID[it.id] !== it) bad.push(`${it.key}(索引)`);
    if (typeof it.engine_consumes !== "boolean" || typeof it.use_seconds !== "number") bad.push(`${it.key}(派生)`);
    if (!it.engine_consumes && it.use_seconds !== 0) bad.push(`${it.key}(use_seconds)`);
    if (!haveBp) continue;          // BP がまだ無い（gen_nr_items の前）なら表だけ
    const def = bp[it.id];
    if (!def) { bad.push(`${it.key}(BP に無い)`); continue; }
    const c = def.components || {};
    if (!!c["minecraft:food"] !== it.engine_consumes) bad.push(`${it.key}(food)`);
    const dur = (c["minecraft:use_modifiers"] || {}).use_duration ?? 0;
    if (Math.abs(dur - it.use_seconds) > 1e-6) bad.push(`${it.key}(use_duration)`);
    if (c["minecraft:max_stack_size"] !== it.stack) bad.push(`${it.key}(stack)`);
    if (c["minecraft:icon"] !== `nr_${it.key}`) bad.push(`${it.key}(icon)`);
  }
  expect(bad).toEqual([]);
});

test("data: 初期装備・クラフト・ルートの nr: ID が実在する", () => {
  const known = new Set([
    ...Object.keys(DATA.items.ITEM_BY_ID), ...Object.keys(DATA.weapons.WEAPON_BY_ID),
    ...Object.keys(DATA.blocks.BLOCK_BY_ID), ...Object.keys(DATA.traps.TRAP_BY_ID),
  ]);
  const refs = [];
  for (const [id] of DATA.settings.STARTER_KIT) refs.push(["STARTER_KIT", id]);
  for (const c of DATA.crafting.CRAFTING) {
    refs.push([`CRAFTING.${c.key}`, c.output]);
    for (const [id] of c.inputs) refs.push([`CRAFTING.${c.key}`, id]);
  }
  for (const [name, rows] of Object.entries(DATA.settings.LOOT_TABLES)) {
    for (const r of /** @type {any[]} */ (rows)) refs.push([`LOOT_TABLES.${name}`, r[0]]);
  }
  for (const z of DATA.zombies.ZOMBIES) for (const r of z.loot) refs.push([`ZOMBIES.${z.key}.loot`, r[0]]);
  const bad = refs.filter(([, id]) => typeof id === "string" && id.startsWith("nr:") && !known.has(id))
    .map(([where, id]) => `${where}: ${id}`);
  expect(bad).toEqual([]);
});

test("data: fx の表（登録簿 + spec から決まる声・能力・一発アニメ）", () => {
  const { PARTICLES, SOUNDS, PLAYER_ANIMS, ZOMBIE_ONESHOTS, ZOMBIE_ANIMATIONS } = DATA.fx;
  expect(dups(PARTICLES)).toEqual([]);
  expect(PARTICLES.filter((p) => p.startsWith("nr:"))).toEqual([]);     // 名前だけ（ID は nr:<名前>）
  expect(dups(SOUNDS)).toEqual([]);
  const snd = new Set(SOUNDS);
  const missing = [];
  for (const z of DATA.zombies.ZOMBIES) {
    for (const ev of ["idle", "alert", "attack", "hurt", "death"]) {
      if (!snd.has(`nr.z.${z.voice}.${ev}`)) missing.push(`nr.z.${z.voice}.${ev}`);
    }
    for (const a of z.ability_keys) if (!snd.has(`nr.ab.${a}`)) missing.push(`nr.ab.${a}`);
    for (const full of Object.values(ZOMBIE_ANIMATIONS[z.key] || {})) {
      const n = String(full).replace("animation.nr.z.", "");
      if ((n.startsWith("atk_") || n.startsWith("ab_")) && !(n in ZOMBIE_ONESHOTS)) missing.push(full);
    }
  }
  expect([...new Set(missing)]).toEqual([]);
  expect(Object.values(PLAYER_ANIMS).filter((v) => v !== null && !(v > 0))).toEqual([]);
  expect(Object.keys(ZOMBIE_ANIMATIONS).length).toBe(50);
});
