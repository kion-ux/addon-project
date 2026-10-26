// 偽の @minecraft/server 2.3.0 — 手書きの部分（NIGHT RUNNER の挙動テスト用）。
//
// tools/nightrunner/test_nr.py がこのファイルの末尾に「d.ts から作る部分」（全 enum・定数・
// 偽物がまだ持っていないクラスの身代わり・ガードの取り付け）を足して、作業フォルダの
// node_modules/@minecraft/server/index.js に置く。テストの道具は harness.js（`nr-test`）。
//
// 約束: 実機に無い名前を公開しない（内部の状態は globalThis.__nr = S に置く。名前が _ で始まる
// メンバーは偽物の内部）。契約違反は violation() で記録してから投げる（握りつぶされても残る）。
import fs from "node:fs";
import { ArgumentOutOfBoundsError, InvalidArgumentError, EngineError } from "@minecraft/common";

const G = globalThis;
const ENV = JSON.parse(fs.readFileSync(new URL("../../../__nr_env.json", import.meta.url), "utf8"));
const API = ENV.api || { classes: {}, enums: {}, events: {} };
const DEFS = ENV.defs;
const ENUMS = API.enums || {};
const enumSet = (name) => new Set(Object.values(ENUMS[name] || {}));
const HAS_API = !!(API.classes && Object.keys(API.classes).length);
void HAS_API;

// ---- 決まった乱数（Math.random も差し替えてテストを再現できるように） -------------
let seed = (ENV.seed >>> 0) || 1234;
function rand() {
  seed = (seed + 0x6D2B79F5) >>> 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
Math.random = rand;

// ---- 状態 ----------------------------------------------------------------------
function newLog() {
  return { particles: new Map(), sounds: new Map(), anims: new Map(), events: new Map(), props: new Map(),
    spawned: new Map(), structures: new Map(), commands: [], messages: [], molangVars: new Map(),
    effects: new Map(), hurts: 0, deaths: 0, camera: 0, titles: 0, actionbars: 0, removed: 0 };
}
const S = G.__nr = {
  tick: 0, phase: "load", early: true, readOnly: 0,
  entities: new Map(), players: [], nextId: 1,
  queue: [], timers: [], jobs: [], nextRun: 1,
  blocks: new Map(), palette: [], paletteIdx: new Map(), lights: new Map(), groundY: 64, flat: true,
  time: 1000, absTime: 1000, day: 0, daylightCycle: true,
  worldDP: new Map(), worldStructures: new Map(),
  formQueue: [], forms: [],
  reg: { block: new Map(), item: new Map(), commands: new Map(), enums: new Map() },
  log: newLog(),
  perTick: 0, maxPerTick: 0, maxPerTickAt: 0, budget: ENV.particleBudget ?? 300, budgetHit: new Set(),
  violations: [], errors: [], limitations: new Map(), notices: new Map(),
  warns: [], consoleErrors: [], logs: [],
  light: null, pendingRemove: new Set(), stepState: new Map(), harness: 0,
  ENV, DEFS, API, rand,
};

const bump = (m, k, n = 1) => m.set(k, (m.get(k) ?? 0) + n);
const finite = (v) => typeof v === "number" && Number.isFinite(v);
function fmt(v) {
  try { return JSON.stringify(v, (k, x) => (x instanceof Entity ? `<${x._typeId}#${x._id}>` : x)); }
  catch { return String(v); }
}
function where() {
  const st = (new Error().stack || "").split("\n").slice(2);
  for (const ln of st) {
    const m = ln.match(/\/((?:scripts|tests)\/[^:)]+):(\d+):\d+\)?\s*$/);
    if (m) return `${m[1]}:${m[2]}`;
  }
  return "";
}
function shortStack(e) {
  const out = [];
  for (const ln of String(e?.stack || "").split("\n").slice(1)) {
    const m = ln.match(/\/((?:scripts|tests|node_modules\/@minecraft\/[\w-]+)\/[^:)]+):(\d+):\d+\)?\s*$/);
    if (m) out.push(`${m[1]}:${m[2]}`);
    if (out.length >= 5) break;
  }
  return out;
}
// 契約違反: 記録して（握りつぶされても残る）、投げる例外を返す
function violation(kind, msg, Err = Error) {
  S.violations.push({ kind, msg, where: where(), tick: S.tick });
  return new Err(`[fake:${kind}] ${msg}`);
}
function check(cond, kind, msg, Err) { if (!cond) throw violation(kind, msg, Err); }
function limitation(what) {
  bump(S.limitations, what);
  return new Error(`[偽物の限界] ${what} は偽の @minecraft/server に無い（実機にはある。アドオンの不具合ではない — test_nr.py に足すこと）`);
}
function notice(kind) { bump(S.notices, kind); }
function recordError(whereName, e) {
  S.errors.push({ where: whereName, msg: String(e?.message ?? e), stack: shortStack(e), tick: S.tick });
}
function checkVec3(v, what) {
  check(v && typeof v === "object" && finite(v.x) && finite(v.y) && finite(v.z), "vector",
    `${what} が有限の {x, y, z} でない: ${fmt(v)}`, InvalidArgumentError);
}
const nsId = (id) => (typeof id === "string" && id && !id.includes(":")) ? "minecraft:" + id : id;
const VAN = {
  items: new Set(DEFS.vanilla?.items || []), blocks: new Set(DEFS.vanilla?.blocks || []),
  entities: new Set(DEFS.vanilla?.entities || []),
};
function vanillaCheck(kind, id) {
  const set = VAN[kind];
  if (set.size && !set.has(id)) notice(`バニラの一覧に無い ${kind} ID: ${id}`);
}
const PARTICLES = new Set(DEFS.particles || []);
const SOUNDS = new Set(DEFS.sounds || []);
const ANIMS = new Set(DEFS.animations || []);
const EFFECTS = new Set(["speed", "slowness", "haste", "mining_fatigue", "strength", "instant_health",
  "instant_damage", "jump_boost", "nausea", "regeneration", "resistance", "fire_resistance", "water_breathing",
  "invisibility", "blindness", "night_vision", "hunger", "weakness", "poison", "wither", "health_boost",
  "absorption", "saturation", "levitation", "fatal_poison", "conduit_power", "slow_falling", "bad_omen",
  "village_hero", "darkness", "trial_omen", "wind_charged", "weaving", "oozing", "infested", "raid_omen"]);

// ---- エラーの型（d.ts の名前） ---------------------------------------------------------
function errClass(name) { return class extends Error { constructor(m) { super(m); this.name = name; } }; }
export const InvalidEntityError = errClass("InvalidEntityError");
export const InvalidItemStackError = errClass("InvalidItemStackError");
export const EntitySpawnError = errClass("EntitySpawnError");
export const InvalidContainerSlotError = errClass("InvalidContainerSlotError");
export const InvalidStructureError = errClass("InvalidStructureError");
export const CustomComponentNameError = errClass("CustomComponentNameError");
export const BlockCustomComponentAlreadyRegisteredError = errClass("BlockCustomComponentAlreadyRegisteredError");
export const ItemCustomComponentAlreadyRegisteredError = errClass("ItemCustomComponentAlreadyRegisteredError");
export const CustomComponentInvalidRegistryError = errClass("CustomComponentInvalidRegistryError");
export const NamespaceNameError = errClass("NamespaceNameError");
export const CommandError = errClass("CommandError");
export const LocationOutOfWorldBoundariesError = errClass("LocationOutOfWorldBoundariesError");

// ---- 小さな Molang の評価器（BP イベントの set_property・プロパティの既定値用） ----------------
function molangEval(src, ent) {
  const s = String(src); const toks = []; let i = 0;
  while (i < s.length) {
    const c = s[i];
    if (/\s/.test(c)) { i++; continue; }
    if (c === "'") { const j = s.indexOf("'", i + 1); if (j < 0) throw new Error("' が閉じていない"); toks.push({ t: "s", v: s.slice(i + 1, j) }); i = j + 1; continue; }
    let m = /^\d+(\.\d+)?/.exec(s.slice(i));
    if (m) { toks.push({ t: "n", v: parseFloat(m[0]) }); i += m[0].length; continue; }
    m = /^[A-Za-z_][\w.]*/.exec(s.slice(i));
    if (m) { toks.push({ t: "i", v: m[0].toLowerCase() }); i += m[0].length; continue; }
    m = /^(==|!=|<=|>=|&&|\|\||\?\?|[-+*/()<>!?:,;])/.exec(s.slice(i));
    if (m) { toks.push({ t: "o", v: m[0] }); i += m[0].length; continue; }
    throw new Error(`Molang の字 ${c}`);
  }
  let p = 0;
  const eat = (v) => (toks[p] && toks[p].t === "o" && toks[p].v === v ? (p++, true) : false);
  const num = (x) => (typeof x === "boolean" ? (x ? 1 : 0) : x);
  function prim() {
    const t = toks[p++];
    if (!t) throw new Error("式が途中で終わる");
    if (t.t === "n" || t.t === "s") return t.v;
    if (t.t === "o" && t.v === "(") { const v = tern(); if (!eat(")")) throw new Error(") が無い"); return v; }
    if (t.t === "o" && t.v === "-") return -num(prim());
    if (t.t === "o" && t.v === "!") return num(prim()) ? 0 : 1;
    if (t.t === "i") {
      const args = [];
      if (eat("(")) { if (!eat(")")) { do { args.push(tern()); } while (eat(",")); if (!eat(")")) throw new Error(") が無い"); } }
      return molangCall(t.v, args, ent);
    }
    throw new Error(`予期しない ${t.v}`);
  }
  function mul() { let v = prim(); for (;;) { if (eat("*")) v = num(v) * num(prim()); else if (eat("/")) v = num(v) / num(prim()); else return v; } }
  function add() { let v = mul(); for (;;) { if (eat("+")) v = num(v) + num(mul()); else if (eat("-")) v = num(v) - num(mul()); else return v; } }
  function cmp() { let v = add(); for (;;) { if (eat("<=")) v = +(v <= add()); else if (eat(">=")) v = +(v >= add()); else if (eat("<")) v = +(v < add()); else if (eat(">")) v = +(v > add()); else return v; } }
  function eq() { let v = cmp(); for (;;) { if (eat("==")) v = +(v === cmp()); else if (eat("!=")) v = +(v !== cmp()); else return v; } }
  function and() { let v = eq(); while (eat("&&")) { const r = eq(); v = +(!!num(v) && !!num(r)); } return v; }
  function or() { let v = and(); while (eat("||")) { const r = and(); v = +(!!num(v) || !!num(r)); } return v; }
  function coal() { let v = or(); while (eat("??")) { const r = or(); v = v ?? r; } return v; }
  function tern() { const c = coal(); if (eat("?")) { const a = tern(); if (!eat(":")) return num(c) ? a : 0; const b = tern(); return num(c) ? a : b; } return c; }
  const v = tern(); eat(";");
  if (p < toks.length) throw new Error("式の後ろに余り");
  return v;
}
function molangCall(name, a, ent) {
  const n = name.replace(/^query\./, "q.");
  const deg = Math.PI / 180;
  switch (n) {
    case "true": return 1;
    case "false": return 0;
    case "q.property": return ent?._props?.get(a[0]);
    case "q.has_property": return ent?._props?.has(a[0]) ? 1 : 0;
    case "q.had_component_group": return ent?._groups?.has(a[0]) ? 1 : 0;
    case "math.random": return a[0] + rand() * (a[1] - a[0]);
    case "math.random_integer": return Math.floor(a[0] + rand() * (a[1] - a[0] + 1));
    case "math.abs": return Math.abs(a[0]);
    case "math.min": return Math.min(a[0], a[1]);
    case "math.max": return Math.max(a[0], a[1]);
    case "math.clamp": return Math.min(Math.max(a[0], a[1]), a[2]);
    case "math.floor": return Math.floor(a[0]);
    case "math.ceil": return Math.ceil(a[0]);
    case "math.round": return Math.round(a[0]);
    case "math.trunc": return Math.trunc(a[0]);
    case "math.sqrt": return Math.sqrt(a[0]);
    case "math.pow": return Math.pow(a[0], a[1]);
    case "math.mod": return a[0] % a[1];
    case "math.sin": return Math.sin(a[0] * deg);
    case "math.cos": return Math.cos(a[0] * deg);
    case "math.lerp": return a[0] + (a[1] - a[0]) * a[2];
    case "math.pi": return Math.PI;
  }
  throw new Error(`偽物の Molang が知らない ${name}`);
}
S.molangEval = molangEval;
S.violation = violation; S.check = check; S.limitation = limitation; S.notice = notice; S.fmt = fmt;
S.recordError = recordError; S.checkVec3 = checkVec3; S.finite = finite; S.bump = bump; S.nsId = nsId;

// ---- イベントの信号 -------------------------------------------------------------------
class Signal {
  constructor(group, name) { this._group = group; this._name = name; this._subs = []; }
  subscribe(cb, options) {
    if (S.readOnly > 0 && !S.harness) throw violation("readonly", `${this._group}.${this._name}.subscribe を before イベントの中で呼んだ（read-only では subscribe できない）`);
    check(typeof cb === "function", "event", `${this._group}.${this._name}.subscribe に関数でないもの`);
    this._subs.push([cb, options]);
    return cb;
  }
  unsubscribe(cb) {
    if (S.readOnly > 0 && !S.harness) throw violation("readonly", `${this._group}.${this._name}.unsubscribe を before イベントの中で呼んだ`);
    const i = this._subs.findIndex((s) => s[0] === cb); if (i >= 0) this._subs.splice(i, 1); }
}
function makeEvents(group, clsName) {
  const names = API.events?.[clsName];
  if (names && names.length) {
    const o = {};
    for (const n of names) o[n] = new Signal(group, n);
    return Object.freeze(o);
  }
  return new Proxy({}, { get(t, n) { if (typeof n !== "string") return undefined; return (t[n] ??= new Signal(group, n)); } });
}
const SIG = {
  wa: makeEvents("world.afterEvents", "WorldAfterEvents"),
  wb: makeEvents("world.beforeEvents", "WorldBeforeEvents"),
  sa: makeEvents("system.afterEvents", "SystemAfterEvents"),
  sb: makeEvents("system.beforeEvents", "SystemBeforeEvents"),
};
function primaryEntity(d) {
  return d.hurtEntity ?? d.deadEntity ?? d.removedEntity ?? d.entity ?? d.damagingEntity ?? d.projectile ?? d.player ?? d.source;
}
// subscribe の options（EntityEventOptions / EntityDataDrivenTriggerEventOptions / InputEventOptions /
// HotbarEventOptions / ScriptEventMessageFilterOptions）
function passes(name, d, o) {
  if (!o) return true;
  // entityHit* の entityTypes は「攻撃した側」で絞る（script_api.md §3.2。要実機確認）
  const e = name === "entityHitEntity" || name === "entityHitBlock" ? d.damagingEntity : primaryEntity(d);
  const tid = e?._typeId ?? d.typeId;
  if (o.entityTypes && tid !== undefined && !o.entityTypes.includes(tid)) return false;
  if (o.entities && e && !o.entities.includes(e)) return false;
  if (o.eventTypes && name === "dataDrivenEntityTrigger" && !o.eventTypes.includes(d.eventId)) return false;
  if (o.buttons && name === "playerButtonInput" && !o.buttons.includes(d.button)) return false;
  if (o.state !== undefined && name === "playerButtonInput" && o.state !== d.newButtonState) return false;
  if (o.allowedSlots && name === "playerHotbarSelectedSlotChange" && !o.allowedSlots.includes(d.newSlotSelected)) return false;
  if (o.namespaces && name === "scriptEventReceive" && !o.namespaces.includes(String(d.id).split(":")[0])) return false;
  return true;
}
// before イベントは read-only（startup だけは早期実行だが書ける: registerCommand が 〔RO✗〕 なのに startup で呼ぶ API）
function dispatch(sig, name, d) {
  if (!sig) return;
  const ro = sig._group.includes("before") && name !== "startup";
  for (const [cb, o] of [...sig._subs]) {
    if (!passes(name, d, o)) continue;
    if (ro) S.readOnly++;
    try { cb(d); } catch (e) { recordError(`${sig._group}.${name}`, e); }
    finally { if (ro) S.readOnly--; }
  }
}
function queueAfter(name, d) { S.queue.push([name, d]); }
function flush() {
  let guard = 0;
  while (S.queue.length) {
    if (++guard > 200000) { recordError("flush", new Error("after イベントが止まらない（無限ループ？）")); S.queue.length = 0; break; }
    const [name, d] = S.queue.shift();
    const sig = name === "scriptEventReceive" ? SIG.sa.scriptEventReceive : SIG.wa[name];
    dispatch(sig, name, d);
  }
}
function fireBefore(name, d) { dispatch(SIG.wb[name], name, d); return d; }
S.queueAfter = queueAfter; S.flush = flush; S.fireBefore = fireBefore; S.SIG = SIG;

// ===========================================================================
//  エンティティ
// ===========================================================================
const DAMAGE_CAUSES = enumSet("EntityDamageCause");
function propDefaults(def, ent) {
  const m = new Map();
  for (const [k, pd] of Object.entries(def?.props ?? {})) {
    let d = pd.default;
    if (typeof d === "string" && pd.type !== "enum") {
      try { d = molangEval(d, ent); } catch { d = undefined; }
    }
    if (d === undefined) d = pd.type === "enum" ? pd.values[0] : pd.type === "bool" ? false : (pd.range?.[0] ?? 0);
    if (pd.type === "bool") d = !!d;
    m.set(k, d);
  }
  return m;
}
function hpOf(comps) {
  const h = comps["minecraft:health"];
  if (!h) return null;
  const v = typeof h.value === "number" ? h.value : (h.value?.range_max ?? h.max ?? 20);
  const mx = typeof h.max === "number" ? h.max : v;
  return [v, mx];
}
function dirFromRot(r) {
  const yaw = r.y * Math.PI / 180, pit = r.x * Math.PI / 180;
  return { x: -Math.sin(yaw) * Math.cos(pit), y: -Math.sin(pit), z: Math.cos(yaw) * Math.cos(pit) };
}
function rotToward(from, to) {
  const dx = to.x - from.x, dy = to.y - from.y, dz = to.z - from.z;
  const h = Math.hypot(dx, dz);
  return { x: -Math.atan2(dy, h) * 180 / Math.PI, y: Math.atan2(-dx, dz) * 180 / Math.PI };
}
S.dirFromRot = dirFromRot; S.rotToward = rotToward;

export class Entity {
  constructor(dim, typeId, loc, opts = {}) {
    this._id = String(-4294967296 + S.nextId++);
    this._typeId = typeId;
    this._dim = dim;
    this._loc = { x: loc.x, y: loc.y, z: loc.z };
    this._vel = { x: 0, y: 0, z: 0 };
    this._rot = { x: 0, y: opts.yaw ?? 0 };
    this._valid = true; this._dead = false; this._deathTick = 0;
    this._def = DEFS.entities[typeId];
    this._groups = new Set();
    this._tags = new Set(); this._dp = new Map(); this._effects = new Map();
    this._props = new Map();
    this._props = propDefaults(this._def, this);
    this._isPlayer = false;
    this._onGround = true; this._fall = 0; this._fireTicks = 0;
    this._sneaking = false; this._sprinting = false;
    this._lastHurtTick = -100; this._lastHurtAmount = 0;
    this._nameTag = "";
    this._item = opts.item;
    this._owner = undefined;
    const hp = hpOf(this._comps()) ?? (typeId === "minecraft:item" ? [5, 5] : [20, 20]);
    this._hp = hp[0]; this._maxHp = hp[1];
    S.entities.set(this._id, this);
  }
  _comps() {
    if (!this.__cc) {
      const c = Object.assign({}, this._def?.components ?? {});
      for (const g of this._groups) Object.assign(c, this._def?.groups?.[g] ?? {});
      this.__cc = c;
    }
    return this.__cc;
  }
  _size() {
    if (this._isPlayer) return { w: 0.6, h: this._sneaking ? 1.5 : 1.8 };
    if (this._typeId === "minecraft:item") return { w: 0.25, h: 0.25 };
    const cb = this._comps()["minecraft:collision_box"];
    if (cb && typeof cb === "object" && !Array.isArray(cb)) return { w: cb.width ?? 0.6, h: cb.height ?? 1.8 };
    return { w: 0.6, h: 1.8 };
  }
  _aabb() {
    const { w, h } = this._size(); const l = this._loc;
    return { min: { x: l.x - w / 2, y: l.y, z: l.z - w / 2 }, max: { x: l.x + w / 2, y: l.y + h, z: l.z + w / 2 } };
  }
  _families() {
    if (this._isPlayer) return ["player", "mob"];
    return this._comps()["minecraft:type_family"]?.family ?? (this._typeId.startsWith("minecraft:") ? [this._typeId.slice(10), "mob"] : []);
  }
  _hasPhysics() {
    const c = this._comps();
    return this._isPlayer || this._typeId === "minecraft:item" || !!c["minecraft:physics"] || !!c["minecraft:projectile"] || !this._def;
  }
  _invalidate() { this.__cc = null; }

  // ---- 読み出し ----
  get id() { return this._id; }
  get typeId() { return this._typeId; }
  get isValid() { return this._valid; }
  get dimension() { return this._dim; }
  get location() { return { ...this._loc }; }
  get isOnGround() { return this._onGround; }
  get isFalling() { return !this._onGround && this._vel.y < 0; }
  get isInWater() { return false; }
  get isClimbing() { return false; }
  get isSleeping() { return false; }
  get isSwimming() { return false; }
  get isSprinting() { return this._sprinting; }
  get isSneaking() { return this._sneaking; }
  set isSneaking(v) { this._sneaking = !!v; }
  get nameTag() { return this._nameTag; }
  set nameTag(v) { check(typeof v === "string", "type", "nameTag は文字列"); this._nameTag = v; }
  get localizationKey() { return `entity.${this._typeId}.name`; }
  get scoreboardIdentity() { return undefined; }

  // ---- 体力・ダメージ ----
  applyDamage(amount, options) {
    check(finite(amount) && amount >= 0, "damage", `applyDamage の量 ${amount}`, ArgumentOutOfBoundsError);
    let cause = "override", damager, proj;
    if (options) {
      check(typeof options === "object", "damage", "applyDamage の options は辞書");
      if (options.damagingProjectile) { cause = "projectile"; proj = options.damagingProjectile; damager = options.damagingEntity; }
      else {
        cause = options.cause;
        check(DAMAGE_CAUSES.size === 0 || DAMAGE_CAUSES.has(cause), "damage", `EntityDamageCause に無い cause ${fmt(cause)}`);
        damager = options.damagingEntity;
      }
    }
    return this._hurt(amount, { cause, damagingEntity: damager, damagingProjectile: proj });
  }
  _hurt(amount, src) {
    if (this._dead || !this._valid) return false;
    if (this._isPlayer && (this._mode === "Creative" || this._mode === "Spectator")) return false;
    const sensor = this._comps()["minecraft:damage_sensor"];
    for (const t of [].concat(sensor?.triggers ?? [])) {
      if (!t || t.on_damage?.filters) continue;
      const c = t.cause ?? "all";
      if ((c === "all" || c === src.cause) && (t.deals_damage === false || t.deals_damage === "no")) return false;
    }
    if (src.cause === "fire" || src.cause === "fireTick" || src.cause === "lava") {
      if (this._comps()["minecraft:fire_immune"]) return false;
    }
    let applied = amount;
    if (S.tick - this._lastHurtTick < 10) {
      if (amount <= this._lastHurtAmount) return false;
      applied = amount - this._lastHurtAmount;
    }
    this._lastHurtTick = S.tick; this._lastHurtAmount = amount;
    const old = this._hp;
    this._hp = Math.max(0, this._hp - applied);
    S.log.hurts++;
    queueAfter("entityHurt", { hurtEntity: this, damage: applied, damageSource: { ...src } });
    queueAfter("entityHealthChanged", { entity: this, oldValue: old, newValue: this._hp });
    if (this._hp <= 0) this._die(src);
    return true;
  }
  _die(src) {
    if (this._dead) return;
    this._dead = true; this._deathTick = S.tick; this._hp = 0;
    S.log.deaths++;
    queueAfter("entityDie", { deadEntity: this, damageSource: { ...src } });
  }
  kill() { if (!this._valid || this._dead) return false; this._lastHurtTick = -100; this._hp = 0; this._die({ cause: "selfDestruct" }); return true; }
  remove() {
    if (this._isPlayer) throw violation("player", "player.remove() は実機で例外（プレイヤーは消せない）");
    this._removeNow(false);
  }
  _removeNow(silent) {
    if (!this._valid) return;
    if (!silent) fireBefore("entityRemove", { removedEntity: this });
    this._valid = false;
    S.entities.delete(this._id);
    S.log.removed++;
    if (!silent) queueAfter("entityRemove", { removedEntityId: this._id, typeId: this._typeId });
  }

  // ---- 動き ----
  applyImpulse(v) {
    if (this._isPlayer) throw violation("player", "applyImpulse はプレイヤーに効かない（実機で例外）。applyKnockback を使う", ArgumentOutOfBoundsError);
    checkVec3(v, "applyImpulse");
    this._vel.x += v.x; this._vel.y += v.y; this._vel.z += v.z;
    if (v.y > 0) this._onGround = false;
  }
  applyKnockback(h, vertical) {
    if (arguments.length !== 2 || typeof h !== "object") {
      throw violation("api", "applyKnockback は 2.x では ({x, z}, vertical)。1.x の (dirX, dirZ, h, v) ではない", TypeError);
    }
    check(h && finite(h.x) && finite(h.z) && finite(vertical), "vector", `applyKnockback(${fmt(h)}, ${vertical})`, InvalidArgumentError);
    this._vel.x = h.x; this._vel.z = h.z; this._vel.y = vertical;
    if (vertical > 0) this._onGround = false;
  }
  getVelocity() { return { ...this._vel }; }
  clearVelocity() { this._vel = { x: 0, y: 0, z: 0 }; }
  getRotation() { return { ...this._rot }; }
  setRotation(r) {
    check(r && finite(r.x) && finite(r.y), "vector", `setRotation(${fmt(r)})`, InvalidArgumentError);
    this._rot = { x: Math.max(-90, Math.min(90, r.x)), y: r.y };
  }
  getViewDirection() { return dirFromRot(this._rot); }
  getHeadLocation() {
    const h = this._isPlayer ? (this._sneaking ? 1.27 : 1.62) : this._size().h * 0.88;
    return { x: this._loc.x, y: this._loc.y + h, z: this._loc.z };
  }
  lookAt(t) { checkVec3(t, "lookAt"); this._rot = rotToward(this.getHeadLocation(), t); }
  teleport(loc, o = {}) {
    checkVec3(loc, "teleport");
    if (o.rotation) check(finite(o.rotation.x) && finite(o.rotation.y), "vector", "teleport の rotation", InvalidArgumentError);
    if (o.facingLocation) checkVec3(o.facingLocation, "teleport の facingLocation");
    if (o.dimension) this._dim = o.dimension;
    this._loc = { x: loc.x, y: loc.y, z: loc.z };
    if (o.rotation) this.setRotation(o.rotation);
    if (o.facingLocation) this.lookAt(o.facingLocation);
    if (!o.keepVelocity) this._vel = { x: 0, y: 0, z: 0 };
    this._fall = 0;
  }
  tryTeleport(loc, o) { this.teleport(loc, o); return true; }
  _physicsStep() {
    if (!this._hasPhysics() || this._dead && !this._def) return;
    const c = this._comps();
    const proj = c["minecraft:projectile"];
    const g = c["minecraft:physics"]?.has_gravity === false ? 0 : proj ? (proj.gravity ?? 0.05) : 0.08;
    if (this._isPlayer && this._mode === "Creative" && this._flying) return;
    const was = this._onGround;
    if (!this._onGround || this._vel.y > 0) this._vel.y -= g;
    const L = this._loc, V = this._vel;
    if (proj && !this._stuck) { this._projectileStep(proj); return; }
    const nx = L.x + V.x, nz = L.z + V.z;
    if (solidAt(nx, L.y + 0.4, L.z)) V.x = 0; else L.x = nx;
    if (solidAt(L.x, L.y + 0.4, nz)) V.z = 0; else L.z = nz;
    let ny = L.y + V.y;
    if (V.y <= 0 && solidAt(L.x, ny - 1e-4, L.z)) {
      ny = Math.floor(ny - 1e-4) + 1;
      const fell = this._fall;
      V.y = 0; this._onGround = true; this._fall = 0;
      if (!was) this._land(fell);
    } else if (V.y > 0 && solidAt(L.x, ny + this._size().h, L.z)) {
      V.y = 0; this._onGround = false; ny = L.y;
    } else {
      if (V.y < 0) this._fall += -V.y;
      this._onGround = false;
    }
    L.y = ny;
    const f = this._onGround ? 0.546 : 0.91;
    V.x *= f; V.z *= f; V.y *= 0.98;
    if (Math.abs(V.x) < 1e-4) V.x = 0;
    if (Math.abs(V.z) < 1e-4) V.z = 0;
    if (L.y < -128) this._removeNow(false);
  }
  _land(fell) {
    if (fell > 3.0 && !this._dead && this._typeId !== "minecraft:item") {
      const sensor = this._comps()["minecraft:damage_sensor"];
      this._hurt(Math.floor(fell - 3.0), { cause: "fall" });
      void sensor;
    }
    const b = blockKey(this._loc.x, this._loc.y - 0.5, this._loc.z);
    blockHook(b, "onEntityFallOn", { entity: this, fallDistance: fell });
  }
  _projectileStep(proj) {
    const L = this._loc, V = this._vel;
    const len = Math.hypot(V.x, V.y, V.z);
    if (len < 1e-6) return;
    const d = { x: V.x / len, y: V.y / len, z: V.z / len };
    const owner = this._owner;
    let best = null;
    for (const e of S.entities.values()) {
      if (e === this || e === owner || !e._valid || e._dead || e._comps()["minecraft:projectile"]) continue;
      const t = rayAabb(L, d, e._aabb());
      if (t !== null && t <= len && (!best || t < best.t)) best = { t, e };
    }
    const bh = raycastBlocks(L, d, len, {});
    if (best && (!bh || best.t <= bh.t)) {
      const at = { x: L.x + d.x * best.t, y: L.y + d.y * best.t, z: L.z + d.z * best.t };
      const target = best.e;
      queueAfter("projectileHitEntity", { dimension: this._dim, hitVector: d, location: at, projectile: this,
        source: owner, getEntityHit: () => ({ entity: target }) });
      const dmg = proj.on_hit?.impact_damage?.damage;
      if (dmg) target._hurt(Array.isArray(dmg) ? dmg[0] : dmg, { cause: "projectile", damagingEntity: owner, damagingProjectile: this });
      this._loc = at;
      if (proj.on_hit?.remove_on_hit || proj.on_hit?.impact_damage?.destroy_on_hit) S.pendingRemove.add(this);
      else { this._vel = { x: 0, y: 0, z: 0 }; this._stuck = true; }
      return;
    }
    if (bh) {
      const at = { x: L.x + d.x * bh.t, y: L.y + d.y * bh.t, z: L.z + d.z * bh.t };
      const blk = new Block(this._dim, bh.x, bh.y, bh.z);
      queueAfter("projectileHitBlock", { dimension: this._dim, hitVector: d, location: at, projectile: this,
        source: owner, getBlockHit: () => ({ block: blk, face: bh.face, faceLocation: { x: at.x - bh.x, y: at.y - bh.y, z: at.z - bh.z } }) });
      this._loc = at; this._vel = { x: 0, y: 0, z: 0 }; this._stuck = true; this._onGround = true;
      if (proj.on_hit?.remove_on_hit) S.pendingRemove.add(this);
      return;
    }
    L.x += V.x; L.y += V.y; L.z += V.z;
    V.x *= 0.99; V.y *= 0.99; V.z *= 0.99;
    if (L.y < -128) this._removeNow(false);
  }
  _statusStep() {
    for (const [k, ef] of this._effects) if (S.tick >= ef.end) this._effects.delete(k);
    if (this._fireTicks > 0) {
      this._fireTicks--;
      if (this._fireTicks % 20 === 0) this._hurt(1, { cause: "fireTick" });
    }
    if (this._dead && !this._isPlayer && S.tick - this._deathTick >= 20) this._removeNow(false);
    if (this._dead && this._isPlayer && S.tick - this._deathTick >= 20) {
      this._dead = false; this._hp = this._maxHp; this._loc = { x: 0, y: S.groundY, z: 0 };
      queueAfter("playerSpawn", { player: this, initialSpawn: false });
    }
  }

  // ---- 部品 ----
  getComponent(id) {
    const n = nsId(String(id));
    const c = this._comps();
    const e = this;
    switch (n) {
      case "minecraft:health": return new EntityHealthComponent(e, n);
      case "minecraft:movement": return (this._isPlayer || c[n]) ? new EntityMovementComponent(e, n) : undefined;
      case "minecraft:equippable": return (this._isPlayer || c[n] || c["minecraft:equipment"]) ? new EntityEquippableComponent(e, n) : undefined;
      case "minecraft:inventory": return (this._isPlayer || c[n]) ? new EntityInventoryComponent(e, n) : undefined;
      case "minecraft:projectile": return c[n] ? new EntityProjectileComponent(e, n) : undefined;
      case "minecraft:type_family": return new EntityTypeFamilyComponent(e, n);
      case "minecraft:onfire": return this._fireTicks > 0 ? new EntityOnFireComponent(e, n) : undefined;
      case "minecraft:item": return this._typeId === "minecraft:item" ? new EntityItemComponent(e, n) : undefined;
    }
    if (c[n]) return new EntityComponent(e, n);
    return undefined;
  }
  hasComponent(id) { return this.getComponent(id) !== undefined; }
  getComponents() {
    const out = [];
    for (const k of ["minecraft:health", "minecraft:type_family", "minecraft:movement", "minecraft:inventory",
      "minecraft:equippable", "minecraft:projectile", ...Object.keys(this._comps())]) {
      const comp = this.getComponent(k);
      if (comp && !out.some((x) => x.typeId === comp.typeId)) out.push(comp);
    }
    return out;
  }

  // ---- プロパティ・イベント ----
  getProperty(name) {
    if (this._props.has(name)) return this._props.get(name);
    if (this._def && String(name).startsWith("nr:")) throw violation("property", `${this._typeId} に無いプロパティ ${name} を読んだ`);
    return undefined;
  }
  setProperty(name, value) {
    const pd = this._def?.props?.[name];
    check(pd, "property", `${this._typeId} に無いプロパティ ${name} を書こうとした`, InvalidArgumentError);
    this._checkProp(name, pd, value);
    this._props.set(name, value);
    bump(S.log.props, `${name}=${value}`);
  }
  _checkProp(name, pd, value) {
    if (pd.type === "enum") check(typeof value === "string" && pd.values.includes(value), "property", `${this._typeId} の ${name} に enum に無い値 ${fmt(value)}（${pd.values.join(" / ")}）`, InvalidArgumentError);
    else if (pd.type === "int") check(Number.isInteger(value) && value >= pd.range[0] && value <= pd.range[1], "property", `${this._typeId} の ${name} に ${fmt(value)}（整数 ${pd.range[0]}〜${pd.range[1]}）`, ArgumentOutOfBoundsError);
    else if (pd.type === "float") check(finite(value) && value >= pd.range[0] && value <= pd.range[1], "property", `${this._typeId} の ${name} に ${fmt(value)}（${pd.range[0]}〜${pd.range[1]}）`, ArgumentOutOfBoundsError);
    else if (pd.type === "bool") check(typeof value === "boolean", "property", `${this._typeId} の ${name} に ${fmt(value)}（bool）`, InvalidArgumentError);
  }
  resetProperty(name) {
    const pd = this._def?.props?.[name];
    check(pd, "property", `${this._typeId} に無いプロパティ ${name}`, InvalidArgumentError);
    const d = propDefaults({ props: { [name]: pd } }, this).get(name);
    this._props.set(name, d);
    return d;
  }
  triggerEvent(name) {
    if (!this._def) { notice(`バニラのエンティティへの triggerEvent（${this._typeId} ${name}）は確かめない`); return; }
    const ev = this._def.events?.[name];
    check(ev, "event", `${this._typeId} に BP イベント ${name} が無い`, InvalidArgumentError);
    bump(S.log.events, name);
    this._applyEvent(ev, name, 0);
    queueAfter("dataDrivenEntityTrigger", { entity: this, eventId: name, getModifiers: () => [] });
  }
  _applyEvent(ev, name, depth) {
    if (!ev || depth > 16) return;
    if (ev.filters && !this._filter(ev.filters)) return;
    for (const g of ev.remove?.component_groups ?? []) { this._groups.delete(g); this._invalidate(); }
    for (const g of ev.add?.component_groups ?? []) {
      check(this._def.groups?.[g], "event", `${this._typeId} のイベント ${name} が無い component_group ${g} を足す`);
      this._groups.delete(g); this._groups.add(g); this._invalidate();
      const grp = this._def.groups[g];
      if (grp["minecraft:instant_despawn"]) S.pendingRemove.add(this);
      const hp = hpOf(grp);
      if (hp) { this._maxHp = hp[1]; this._hp = Math.min(this._hp, this._maxHp); }
    }
    for (const [k, v] of Object.entries(ev.set_property ?? {})) {
      const pd = this._def.props?.[k];
      check(pd, "event", `${this._typeId} のイベント ${name} が無いプロパティ ${k} を set_property`);
      let val = v;
      if (typeof v === "string" && pd.type !== "enum") {
        try { val = molangEval(v, this); } catch (e) { notice(`set_property の Molang を評価できない: ${v}`); continue; }
        if (pd.type === "int") val = Math.trunc(val);
        if (pd.type === "bool") val = !!val;
      } else if (typeof v === "string" && pd.type === "enum" && !pd.values.includes(v)) {
        try { val = molangEval(v, this); } catch { /* 下で違反になる */ }
      }
      this._checkProp(k, pd, val);
      this._props.set(k, val);
    }
    for (const sub of ev.sequence ?? []) this._applyEvent(sub, name, depth + 1);
    if (ev.randomize?.length) {
      const total = ev.randomize.reduce((a, r) => a + (r.weight ?? 1), 0);
      let x = rand() * total;
      for (const r of ev.randomize) { x -= r.weight ?? 1; if (x <= 0) { this._applyEvent(r, name, depth + 1); break; } }
    }
    if (ev.first_valid?.length) {
      for (const r of ev.first_valid) if (!r.filters || this._filter(r.filters)) { this._applyEvent(r, name, depth + 1); break; }
    }
    const trig = ev.trigger;
    if (trig) {
      const tn = typeof trig === "string" ? trig : trig.event;
      const target = typeof trig === "string" ? "self" : (trig.target ?? "self");
      if (target === "self") {
        check(this._def.events?.[tn], "event", `${this._typeId} のイベント ${name} が無いイベント ${tn} を trigger`);
        this._applyEvent(this._def.events[tn], tn, depth + 1);
      }
    }
    if (ev.queue_command) S.log.commands.push(...[].concat(ev.queue_command.command ?? []));
  }
  _filter(f) {
    if (Array.isArray(f)) return f.every((x) => this._filter(x));
    if (!f || typeof f !== "object") return true;
    if (f.all_of) return [].concat(f.all_of).every((x) => this._filter(x));
    if (f.any_of) return [].concat(f.any_of).some((x) => this._filter(x));
    if (f.none_of) return ![].concat(f.none_of).some((x) => this._filter(x));
    const op = f.operator ?? "equals";
    const cmp = (a, b) => (op === "equals" || op === "==" || op === "=") ? a === b : (op === "not" || op === "!=" || op === "<>") ? a !== b
      : op === "<" ? a < b : op === "<=" ? a <= b : op === ">" ? a > b : op === ">=" ? a >= b : a === b;
    switch (f.test) {
      case "has_component": return cmp(!!this._comps()[f.value], true);
      case "is_family": return cmp(this._families().includes(f.value), true);
      case "has_tag": return cmp(this._tags.has(f.value), true);
      case "enum_property": case "int_property": case "float_property": case "bool_property":
        return cmp(this._props.get(f.domain), f.value);
      case "is_daytime": return cmp(S.time < 13000 || S.time >= 23000, f.value ?? true);
    }
    notice(`偽物が評価しないフィルタ ${f.test}（真として扱う）`);
    return true;
  }

  // ---- 効果・タグ・火 ----
  addEffect(type, duration, o = {}) {
    const id = String(typeof type === "string" ? type : type?.getName?.() ?? type).replace(/^minecraft:/, "");
    check(EFFECTS.has(id), "effect", `知らない効果 ${fmt(type)}`, InvalidArgumentError);
    check(Number.isInteger(duration) && duration >= 1 && duration <= 20000000, "effect", `addEffect の duration ${duration}（整数 1〜20000000 tick）`, ArgumentOutOfBoundsError);
    const amp = o.amplifier ?? 0;
    check(Number.isInteger(amp) && amp >= 0 && amp <= 255, "effect", `amplifier ${amp}（0〜255）`, ArgumentOutOfBoundsError);
    const ef = { typeId: id, amplifier: amp, end: S.tick + duration, duration };
    this._effects.set(id, ef);
    bump(S.log.effects, id);
    queueAfter("effectAdd", { entity: this, effect: makeEffect(this, ef) });
    return makeEffect(this, ef);
  }
  getEffect(type) {
    const id = String(typeof type === "string" ? type : type?.getName?.()).replace(/^minecraft:/, "");
    const ef = this._effects.get(id);
    return ef ? makeEffect(this, ef) : undefined;
  }
  getEffects() { return [...this._effects.values()].map((ef) => makeEffect(this, ef)); }
  removeEffect(type) {
    const id = String(typeof type === "string" ? type : type?.getName?.()).replace(/^minecraft:/, "");
    return this._effects.delete(id);
  }
  addTag(t) { check(typeof t === "string" && t.length > 0, "tag", "addTag の値"); const had = this._tags.has(t); this._tags.add(t); return !had; }
  removeTag(t) { return this._tags.delete(t); }
  hasTag(t) { return this._tags.has(t); }
  getTags() { return [...this._tags]; }
  setOnFire(sec, useEffects = true) {
    check(finite(sec) && sec >= 0, "fire", `setOnFire(${sec})`);
    if (this._comps()["minecraft:fire_immune"]) return false;
    this._fireTicks = Math.max(this._fireTicks, Math.round(sec * 20));
    return true;
  }
  extinguishFire() { const was = this._fireTicks > 0; this._fireTicks = 0; return was; }

  // ---- 動的プロパティ ----
  getDynamicProperty(k) { return this._dp.get(k); }
  setDynamicProperty(k, v) { dpSet(this._dp, k, v, this._typeId); }
  setDynamicProperties(o) { for (const [k, v] of Object.entries(o)) dpSet(this._dp, k, v, this._typeId); }
  getDynamicPropertyIds() { return [...this._dp.keys()]; }
  clearDynamicProperties() { this._dp.clear(); }
  getDynamicPropertyTotalByteCount() { return dpBytes(this._dp); }

  // ---- 演出・その他 ----
  playAnimation(name, o = {}) {
    check(typeof name === "string", "anim", "playAnimation の名前");
    if (name.startsWith("animation.nr.")) check(ANIMS.has(name), "anim", `RP に無いアニメーション ${name}`, InvalidArgumentError);
    if (o.blendOutTime !== undefined) check(finite(o.blendOutTime) && o.blendOutTime >= 0, "anim", `blendOutTime ${o.blendOutTime}`);
    if (o.controller !== undefined) check(typeof o.controller === "string" && o.controller.length > 0, "anim", "controller は文字列");
    if (o.stopExpression !== undefined) check(typeof o.stopExpression === "string", "anim", "stopExpression は Molang の文字列");
    if (o.nextState !== undefined) check(typeof o.nextState === "string", "anim", "nextState は文字列");
    if (o.players !== undefined) check(Array.isArray(o.players) && o.players.every((p) => p instanceof Player), "anim", "players は Player の配列");
    if (name.startsWith("animation.nr.")) {
      // rendering.md の P1 / P2（DESIGN.md §13）: NR の一発ものは controller（nr. で始まる）・stopExpression・nextState を必ず渡す
      check(typeof o.controller === "string" && o.controller.startsWith("nr."), "anim", `${name}: controller を "nr." で始まる名前で渡す（rendering.md P1）。今は ${fmt(o.controller)}`);
      check(o.stopExpression !== undefined && o.nextState !== undefined, "anim", `${name}: stopExpression と nextState を必ず渡す（rendering.md P2。止めるなら nextState: "none"）`);
    }
    bump(S.log.anims, name);
  }
  runCommand(cmd) { check(typeof cmd === "string", "command", "runCommand の値"); S.log.commands.push(cmd); return { successCount: 1 }; }
  matches(q) { return matchQuery(this, q ?? {}, null); }
  getEntitiesFromViewDirection(o = {}) {
    const head = this.getHeadLocation();
    return entitiesFromRay(this._dim, head, this.getViewDirection(), o, this);
  }
  getBlockFromViewDirection(o = {}) {
    return blockFromRay(this._dim, this.getHeadLocation(), this.getViewDirection(), o);
  }
}
S.Entity = Entity;

function makeEffect(ent, ef) {
  return { typeId: ef.typeId, amplifier: ef.amplifier, get duration() { return Math.max(0, ef.end - S.tick); },
    displayName: ef.typeId, get isValid() { return ent._valid && ent._effects.get(ef.typeId) === ef; } };
}
function dpSet(map, k, v, owner) {
  check(typeof k === "string" && k.length > 0, "dynprop", `動的プロパティの名前 ${fmt(k)}`);
  if (v === undefined) { map.delete(k); return; }
  const ok = typeof v === "boolean" || (typeof v === "number" && Number.isFinite(v)) || (typeof v === "string" && v.length <= 32767)
    || (v && typeof v === "object" && !Array.isArray(v) && finite(v.x) && finite(v.y) && finite(v.z) && Object.keys(v).length === 3);
  check(ok, "dynprop", `${owner} の動的プロパティ ${k} に入れられない値 ${fmt(v)?.slice(0, 80)}（bool / 有限の数 / 32767 字以内の文字列 / {x,y,z} だけ）`, TypeError);
  map.set(k, typeof v === "object" ? { x: v.x, y: v.y, z: v.z } : v);
}
function dpBytes(map) { let n = 0; for (const [k, v] of map) n += k.length + (typeof v === "string" ? v.length : 8); return n; }

// ===========================================================================
//  プレイヤーと部品
// ===========================================================================
const GAME_MODES = enumSet("GameMode");
const INPUT_BUTTONS = enumSet("InputButton");
export class Player extends Entity {
  constructor(dim, loc, name) {
    super(dim, "minecraft:player", loc, {});
    this._isPlayer = true;
    this._name = name;
    this._mode = "Survival";
    this._inv = new Container(36, this);
    this._equip = { Head: undefined, Chest: undefined, Legs: undefined, Feet: undefined, Offhand: undefined };
    this._slot = 0;
    this._buttons = { Jump: "Released", Sneak: "Released" };
    this._move = { x: 0, y: 0 };
    this._jumping = false;
    this._camera = new Camera(this);
    this._screen = new ScreenDisplay(this);
    this._input = new InputInfo(this);
    this._perms = new PlayerInputPermissions(this);
    this._level = 0; this._xp = 0; this._cooldowns = new Map(); this._overrides = new Map();
    this._hp = 20; this._maxHp = 20;
    S.players.push(this);
  }
  get name() { return this._name; }
  get camera() { return this._camera; }
  get onScreenDisplay() { return this._screen; }
  get inputInfo() { return this._input; }
  get inputPermissions() { return this._perms; }
  get clientSystemInfo() { return { maxRenderDistance: 12, platformType: "Desktop", memoryTier: "High" }; }
  get graphicsMode() { return "Fancy"; }
  get commandPermissionLevel() { return "Admin"; }
  set commandPermissionLevel(v) { }
  get playerPermissionLevel() { return "Operator"; }
  get isEmoting() { return false; }
  get isFlying() { return !!this._flying; }
  get isGliding() { return !!this._gliding; }
  get isJumping() { return this._jumping; }
  get level() { return this._level; }
  get totalXpNeededForNextLevel() { return 7 + this._level * 2; }
  get xpEarnedAtCurrentLevel() { return this._xp; }
  get selectedSlotIndex() { return this._slot; }
  set selectedSlotIndex(v) {
    check(Number.isInteger(v) && v >= 0 && v <= 8, "player", `selectedSlotIndex ${v}（0〜8）`, ArgumentOutOfBoundsError);
    const prev = this._slot; this._slot = v;
    if (prev !== v) queueAfter("playerHotbarSelectedSlotChange", { player: this, previousSlotSelected: prev, newSlotSelected: v, itemStack: this._inv.getItem(v) });
  }
  getGameMode() { return this._mode; }
  setGameMode(m) { check(m === undefined || GAME_MODES.size === 0 || GAME_MODES.has(m), "player", `GameMode に無い ${fmt(m)}`); this._mode = m ?? "Survival"; }
  playSound(id, o = {}) {
    checkSound(id);
    if (o.location) checkVec3(o.location, "playSound の location");
    checkVolPitch(o);
    bump(S.log.sounds, id);
  }
  spawnParticle(id, loc, vars) { spawnParticleImpl(id, loc, vars); }
  sendMessage(m) { S.log.messages.push(textOf(m)); }
  addExperience(n) { check(Number.isInteger(n), "player", "addExperience は整数"); this._xp += n; return this._xp; }
  addLevels(n) { check(Number.isInteger(n), "player", "addLevels は整数"); this._level = Math.max(0, this._level + n); return this._level; }
  getTotalXp() { return this._xp; }
  resetLevel() { this._level = 0; this._xp = 0; }
  startItemCooldown(cat, ticks) { check(typeof cat === "string" && Number.isInteger(ticks) && ticks >= 0, "player", "startItemCooldown"); this._cooldowns.set(cat, S.tick + ticks); }
  getItemCooldown(cat) { return Math.max(0, (this._cooldowns.get(cat) ?? 0) - S.tick); }
  setPropertyOverrideForEntity(target, id, value) {
    check(target instanceof Entity, "property", "setPropertyOverrideForEntity の相手");
    const pd = target._def?.props?.[id];
    check(pd, "property", `${target._typeId} に無いプロパティ ${id}`);
    target._checkProp(id, pd, value);
    this._overrides.set(`${target._id}|${id}`, value);
  }
  removePropertyOverrideForEntity(target, id) { this._overrides.delete(`${target._id}|${id}`); }
  clearPropertyOverridesForEntity(target) { for (const k of [...this._overrides.keys()]) if (k.startsWith(target._id + "|")) this._overrides.delete(k); }
  getSpawnPoint() { return this._spawn; }
  setSpawnPoint(p) { this._spawn = p; }
  playMusic() { } queueMusic() { } stopMusic() { }
}
S.Player = Player;

function textOf(m) {
  if (typeof m === "string") return m;
  if (Array.isArray(m)) return m.map(textOf).join("");
  if (m && typeof m === "object") return m.text ?? m.translate ?? (m.rawtext ? textOf(m.rawtext) : fmt(m));
  return String(m);
}
function checkVolPitch(o) {
  if (o.volume !== undefined) check(finite(o.volume) && o.volume >= 0, "sound", `volume ${o.volume}`);
  if (o.pitch !== undefined) check(finite(o.pitch) && o.pitch >= 0, "sound", `pitch ${o.pitch}`);
}
function checkSound(id) {
  check(typeof id === "string" && id.length > 0, "sound", `効果音 ID ${fmt(id)}`);
  if (id.startsWith("nr.")) check(SOUNDS.has(id), "sound", `sound_definitions に無い効果音 ${id}`, InvalidArgumentError);
}

export class Component {
  constructor(owner, typeId) { this._owner = owner; this._typeId = typeId; }
  get typeId() { return this._typeId; }
  get isValid() { return this._owner instanceof Entity ? this._owner._valid : true; }
}
export class EntityComponent extends Component { get entity() { return this._owner; } }
export class EntityAttributeComponent extends EntityComponent {
  get currentValue() { return this._get(); }
  get defaultValue() { return this._max(); }
  get effectiveMax() { return this._max(); }
  get effectiveMin() { return 0; }
  _get() { return 0; } _max() { return 0; } _set() { }
  setCurrentValue(v) {
    check(finite(v), "component", `${this._typeId}.setCurrentValue(${v})`, ArgumentOutOfBoundsError);
    if (v < 0 || v > this._max()) return false;
    this._set(v); return true;
  }
  resetToDefaultValue() { this._set(this._max()); }
  resetToMaxValue() { this._set(this._max()); }
  resetToMinValue() { this._set(0); }
}
export class EntityHealthComponent extends EntityAttributeComponent {
  _get() { return this._owner._hp; }
  _max() { return this._owner._maxHp; }
  _set(v) {
    const e = this._owner; const old = e._hp; e._hp = v;
    if (old !== v) queueAfter("entityHealthChanged", { entity: e, oldValue: old, newValue: v });
    if (v <= 0) e._die({ cause: "override" });
  }
}
export class EntityMovementComponent extends EntityAttributeComponent {
  _get() { return this._owner._speed ?? this._owner._comps()["minecraft:movement"]?.value ?? 0.1; }
  _max() { return 10; }
  _set(v) { this._owner._speed = v; }
}
export class EntityTypeFamilyComponent extends EntityComponent {
  getTypeFamilies() { return [...this._owner._families()]; }
  hasTypeFamily(f) { return this._owner._families().includes(f); }
}
export class EntityOnFireComponent extends EntityComponent { get onFireTicksRemaining() { return this._owner._fireTicks; } }
export class EntityItemComponent extends EntityComponent { get itemStack() { return this._owner._item?.clone(); } }
export class EntityInventoryComponent extends EntityComponent {
  get container() { return this._owner._isPlayer ? this._owner._inv : (this._owner._inv ??= new Container(this._owner._comps()["minecraft:inventory"]?.inventory_size ?? 27, this._owner)); }
  get inventorySize() { return this.container.size; }
  get additionalSlotsPerStrength() { return 0; }
  get canBeSiphonedFrom() { return false; }
  get containerType() { return "inventory"; }
  get restrictToOwner() { return false; }
}
const EQUIP_SLOTS = enumSet("EquipmentSlot");
export class EntityEquippableComponent extends EntityComponent {
  get totalArmor() { return 0; }
  get totalToughness() { return 0; }
  _chk(slot) { check(EQUIP_SLOTS.size === 0 || EQUIP_SLOTS.has(slot), "equip", `EquipmentSlot に無い ${fmt(slot)}`, InvalidArgumentError); }
  getEquipment(slot) {
    this._chk(slot); const e = this._owner;
    if (slot === "Mainhand") return e._isPlayer ? e._inv.getItem(e._slot) : e._mainhand?.clone();
    return (e._equip ??= {})[slot]?.clone();
  }
  setEquipment(slot, item) {
    this._chk(slot); const e = this._owner;
    if (item !== undefined) check(item instanceof ItemStack, "equip", "setEquipment に ItemStack でないもの");
    if (slot === "Mainhand") { if (e._isPlayer) e._inv.setItem(e._slot, item); else e._mainhand = item?.clone(); }
    else (e._equip ??= {})[slot] = item?.clone();
    return true;
  }
  getEquipmentSlot(slot) {
    this._chk(slot); const e = this._owner;
    if (slot === "Mainhand" && e._isPlayer) return e._inv.getSlot(e._slot);
    const store = e._equip ??= {};
    return new ContainerSlot({ get: () => store[slot], set: (v) => { store[slot] = v; } }, this._owner);
  }
}
export class EntityProjectileComponent extends EntityComponent {
  constructor(o, t) { super(o, t); const c = o._comps()["minecraft:projectile"] ?? {};
    this.airInertia = 0.99; this.catchFireOnHurt = !!c.catch_fire; this.critParticlesOnProjectileHurt = false;
    this.destroyOnProjectileHurt = false; this.gravity = c.gravity ?? 0.05; this.liquidInertia = 0.6; this.lightningStrikeOnHit = false;
    this.onFireTime = 0; this.shouldBounceOnHit = false; this.stopOnHit = false; }
  get owner() { return this._owner._owner; }
  set owner(v) { this._owner._owner = v; }
  shoot(v, o = {}) {
    checkVec3(v, "projectile.shoot");
    if (o.uncertainty !== undefined) check(finite(o.uncertainty) && o.uncertainty >= 0, "projectile", "uncertainty");
    this._owner._vel = { x: v.x, y: v.y, z: v.z }; this._owner._onGround = false; this._owner._stuck = false;
  }
}

export class Camera {
  constructor(p) { this._p = p; }
  get isValid() { return this._p._valid; }
  fade(o = {}) {
    const t = o.fadeTime;
    if (t) for (const k of ["fadeInTime", "holdTime", "fadeOutTime"]) check(finite(t[k]) && t[k] >= 0 && t[k] <= 10, "camera", `fade の ${k} ${t[k]}（0〜10 秒）`, ArgumentOutOfBoundsError);
    const c = o.fadeColor;
    if (c) for (const k of ["red", "green", "blue"]) check(finite(c[k]) && c[k] >= 0 && c[k] <= 1, "camera", `fade の色 ${k} ${c[k]}（0〜1）`, ArgumentOutOfBoundsError);
    S.log.camera++;
  }
  clear() { S.log.camera++; }
  setCamera(preset, o) { check(typeof preset === "string" && preset.includes(":"), "camera", `カメラのプリセット ${fmt(preset)}`); S.log.camera++; }
  setDefaultCamera(preset) { check(typeof preset === "string", "camera", "setDefaultCamera"); S.log.camera++; }
  setFov(o = {}) { if (o.fov !== undefined) check(finite(o.fov) && o.fov >= 30 && o.fov <= 110, "camera", `fov ${o.fov}（30〜110）`); S.log.camera++; }
}
export class ScreenDisplay {
  constructor(p) { this._p = p; this._hidden = new Set(); this.actionBar = ""; this.title = ""; this.subtitle = ""; }
  get isValid() { return this._p._valid; }
  setActionBar(t) { this.actionBar = textOf(t); S.log.actionbars++; }
  setTitle(t, o) {
    if (o) for (const k of ["fadeInDuration", "stayDuration", "fadeOutDuration"]) check(Number.isInteger(o[k]) && o[k] >= 0, "title", `setTitle の ${k} ${o[k]}（0 以上の整数 tick。三つとも要る）`, ArgumentOutOfBoundsError);
    this.title = textOf(t); this.subtitle = o?.subtitle !== undefined ? textOf(o.subtitle) : ""; S.log.titles++;
  }
  updateSubtitle(t) { this.subtitle = textOf(t); }
  hideAllExcept(els = []) { this._hidden = new Set(Object.values(ENUMS.HudElement ?? {}).filter((x) => !els.includes(x))); }
  setHudVisibility(vis, els) { const all = els ?? Object.values(ENUMS.HudElement ?? {}); for (const e of all) { if (vis === "Hide" || vis === 0) this._hidden.add(e); else this._hidden.delete(e); } }
  resetHudElementsVisibility() { this._hidden.clear(); }
  getHiddenHudElements() { return [...this._hidden]; }
  isForcedHidden(e) { return this._hidden.has(e); }
}
export class InputInfo {
  constructor(p) { this._p = p; }
  get lastInputModeUsed() { return "KeyboardAndMouse"; }
  get touchOnlyAffectsHotbar() { return false; }
  getButtonState(b) {
    check(INPUT_BUTTONS.size === 0 || INPUT_BUTTONS.has(b), "input", `InputButton に無い ${fmt(b)}`, InvalidArgumentError);
    return this._p._buttons[b] ?? "Released";
  }
  getMovementVector() { return { ...this._p._move }; }
}
export class PlayerInputPermissions {
  constructor(p) { this._p = p; this._off = new Set(); }
  isPermissionCategoryEnabled(c) { return !this._off.has(c); }
  setPermissionCategory(c, on) { if (on) this._off.delete(c); else this._off.add(c); }
}

// ===========================================================================
//  アイテム・入れ物
// ===========================================================================
function itemDef(id) { return DEFS.items[id] ?? (DEFS.blocks[id] ? { components: {}, block: true } : undefined); }
function maxStackOf(id) {
  const c = itemDef(id)?.components ?? {};
  const m = c["minecraft:max_stack_size"];
  if (typeof m === "number") return m;
  if (m && typeof m === "object") return m.value ?? 64;
  if (c["minecraft:durability"]) return 1;
  return 64;
}
export class ItemStack {
  constructor(type, amount = 1) {
    if (S.early && !S.harness) throw violation("early", "new ItemStack は worldLoad の前（early execution）には使えない（script_api.md §1）");
    const id = nsId(typeof type === "string" ? type : type?.id);
    check(typeof id === "string" && id.length > 0, "item", `ItemStack の種類 ${fmt(type)}`, InvalidArgumentError);
    if (id.startsWith("nr:")) check(itemDef(id), "item", `BP に無いアイテム ${id}`, InvalidArgumentError);
    else if (id.startsWith("minecraft:")) vanillaCheck("items", id);
    check(Number.isInteger(amount) && amount >= 1 && amount <= 255, "item", `ItemStack の数 ${amount}（1〜255）`, ArgumentOutOfBoundsError);
    this._typeId = id; this._amount = Math.min(amount, maxStackOf(id));   // 実機は最大スタック数に丸める
    this._lore = []; this._dp = new Map(); this._nameTag = undefined;
    this._dmg = 0; this._canDestroy = []; this._canPlaceOn = [];
    this.lockMode = "none"; this.keepOnDeath = false;
  }
  get typeId() { return this._typeId; }
  get type() { return { id: this._typeId }; }
  get amount() { return this._amount; }
  set amount(v) { check(Number.isInteger(v) && v >= 1 && v <= 255, "item", `amount ${v}（1〜255）`, ArgumentOutOfBoundsError); this._amount = v; }
  get maxAmount() { return maxStackOf(this._typeId); }
  get isStackable() { return this.maxAmount > 1; }
  get nameTag() { return this._nameTag; }
  set nameTag(v) { check(v === undefined || (typeof v === "string" && v.length <= 255), "item", "nameTag は 255 字以内の文字列"); this._nameTag = v; }
  get localizationKey() { return `item.${this._typeId}.name`; }
  get weight() { return 1; }
  clone() {
    const c = new ItemStack(this._typeId, this._amount);
    c._lore = [...this._lore]; c._dp = new Map(this._dp); c._nameTag = this._nameTag; c._dmg = this._dmg;
    c._canDestroy = [...this._canDestroy]; c._canPlaceOn = [...this._canPlaceOn]; c.lockMode = this.lockMode; c.keepOnDeath = this.keepOnDeath;
    return c;
  }
  getLore() { return this._lore.map(textOf); }
  getRawLore() { return this._lore.map((x) => (typeof x === "string" ? { text: x } : x)); }
  setLore(list) {
    if (list === undefined) { this._lore = []; return; }
    check(Array.isArray(list), "item", "setLore は配列", InvalidArgumentError);
    check(list.length <= 100, "item", `lore が ${list.length} 行（100 行まで）`, ArgumentOutOfBoundsError);
    for (const x of list) check((typeof x === "string" && x.length <= 1000) || (x && typeof x === "object"), "item", `lore の行 ${fmt(x)?.slice(0, 60)}`, ArgumentOutOfBoundsError);
    this._lore = [...list];
  }
  _dpOk() { check(!this.isStackable, "dynprop", `重ねられるアイテム ${this._typeId}（最大 ${this.maxAmount}）に動的プロパティは付けられない（実機で例外）`, ArgumentOutOfBoundsError); }
  getDynamicProperty(k) { return this._dp.get(k); }
  setDynamicProperty(k, v) { this._dpOk(); dpSet(this._dp, k, v, this._typeId); }
  setDynamicProperties(o) { this._dpOk(); for (const [k, v] of Object.entries(o)) dpSet(this._dp, k, v, this._typeId); }
  getDynamicPropertyIds() { return [...this._dp.keys()]; }
  clearDynamicProperties() { this._dp.clear(); }
  getDynamicPropertyTotalByteCount() { return dpBytes(this._dp); }
  getComponent(id) {
    const n = nsId(String(id)); const c = itemDef(this._typeId)?.components ?? {};
    if (!c[n]) return undefined;
    switch (n) {
      case "minecraft:durability": return new ItemDurabilityComponent(this, n);
      case "minecraft:cooldown": return new ItemCooldownComponent(this, n);
      case "minecraft:food": return new ItemFoodComponent(this, n);
      case "minecraft:enchantable": return new ItemEnchantableComponent(this, n);
    }
    return new ItemComponent(this, n);
  }
  hasComponent(id) { return this.getComponent(id) !== undefined; }
  getComponents() { return Object.keys(itemDef(this._typeId)?.components ?? {}).filter((k) => k.startsWith("minecraft:")).map((k) => this.getComponent(k)).filter(Boolean); }
  getTags() { return [...(itemDef(this._typeId)?.components?.["minecraft:tags"]?.tags ?? [])]; }
  hasTag(t) { return this.getTags().includes(t); }
  isStackableWith(o) { return o instanceof ItemStack && o._typeId === this._typeId && this.isStackable && fmt(o._lore) === fmt(this._lore) && o._nameTag === this._nameTag; }
  matches(name, states) { return nsId(name) === this._typeId; }
  getCanDestroy() { return [...this._canDestroy]; }
  getCanPlaceOn() { return [...this._canPlaceOn]; }
  setCanDestroy(l) { this._canDestroy = [...(l ?? [])]; }
  setCanPlaceOn(l) { this._canPlaceOn = [...(l ?? [])]; }
}
S.ItemStack = ItemStack;
export class ItemComponent extends Component { }
export class ItemDurabilityComponent extends ItemComponent {
  get maxDurability() { const d = itemDef(this._owner._typeId).components["minecraft:durability"]; return d.max_durability ?? d.value ?? 0; }
  get damage() { return this._owner._dmg; }
  set damage(v) {
    check(Number.isInteger(v) && v >= 0 && v <= this.maxDurability, "durability", `${this._owner._typeId} の damage ${v}（整数 0〜${this.maxDurability}。壊すときは自分で消す）`, ArgumentOutOfBoundsError);
    this._owner._dmg = v;
  }
  getDamageChance(level = 0) { check(Number.isInteger(level) && level >= 0, "durability", "unbreaking の段階"); return 100 / (level + 1); }
  getDamageChanceRange() { return { min: 0, max: 100 }; }
}
export class ItemCooldownComponent extends ItemComponent {
  _c() { return itemDef(this._owner._typeId).components["minecraft:cooldown"]; }
  get cooldownCategory() { return this._c().category ?? ""; }
  get cooldownTicks() { return Math.round((this._c().duration ?? 0) * 20); }
  getCooldownTicksRemaining(p) { return p.getItemCooldown(this.cooldownCategory); }
  isCooldownCategory(c) { return c === this.cooldownCategory; }
  startCooldown(p) { p.startItemCooldown(this.cooldownCategory, this.cooldownTicks); }
}
export class ItemFoodComponent extends ItemComponent {
  _c() { return itemDef(this._owner._typeId).components["minecraft:food"]; }
  get canAlwaysEat() { return !!this._c().can_always_eat; }
  get nutrition() { return this._c().nutrition ?? 0; }
  get saturationModifier() { return this._c().saturation_modifier ?? 0; }
  get usingConvertsTo() { return this._c().using_converts_to ?? ""; }
}
export class ItemEnchantableComponent extends ItemComponent {
  get slots() { return []; }
  getEnchantments() { return []; }
  hasEnchantment() { return false; }
  getEnchantment() { return undefined; }
  canAddEnchantment() { return false; }
  addEnchantment() { throw limitation("ItemEnchantableComponent.addEnchantment"); }
  addEnchantments() { throw limitation("ItemEnchantableComponent.addEnchantments"); }
  removeEnchantment() { } removeAllEnchantments() { }
}

export class Container {
  constructor(size, owner) { this._slots = new Array(size).fill(undefined); this._owner = owner; }
  get size() { return this._slots.length; }
  get isValid() { return !this._owner || this._owner._valid !== false; }
  get emptySlotsCount() { return this._slots.filter((x) => !x).length; }
  get weight() { return 0; }
  get containerRules() { return undefined; }
  _idx(i) { check(Number.isInteger(i) && i >= 0 && i < this._slots.length, "container", `スロット ${i}（0〜${this._slots.length - 1}）`, ArgumentOutOfBoundsError); }
  getItem(i) { this._idx(i); return this._slots[i]?.clone(); }
  setItem(i, item) {
    this._idx(i);
    if (item !== undefined) check(item instanceof ItemStack, "container", "setItem に ItemStack でないもの", InvalidArgumentError);
    this._slots[i] = item?.clone();
  }
  getSlot(i) { this._idx(i); const c = this; return new ContainerSlot({ get: () => c._slots[i], set: (v) => { c._slots[i] = v; } }, this._owner); }
  addItem(item) {
    check(item instanceof ItemStack, "container", "addItem に ItemStack でないもの", InvalidArgumentError);
    let left = item.amount;
    for (let i = 0; i < this._slots.length && left > 0; i++) {
      const s = this._slots[i];
      if (s && s.isStackableWith(item) && s.amount < s.maxAmount) { const n = Math.min(left, s.maxAmount - s.amount); s._amount += n; left -= n; }
    }
    for (let i = 0; i < this._slots.length && left > 0; i++) {
      if (!this._slots[i]) { const c = item.clone(); const n = Math.min(left, item.maxAmount); c._amount = n; this._slots[i] = c; left -= n; }
    }
    if (left <= 0) return undefined;
    const r = item.clone(); r._amount = left; return r;
  }
  clearAll() { this._slots.fill(undefined); }
  contains(item) { return this._slots.some((s) => s && s._typeId === item._typeId && s.amount >= item.amount); }
  find(item) { const i = this._slots.findIndex((s) => s && s._typeId === item._typeId); return i < 0 ? undefined : i; }
  findLast(item) { for (let i = this._slots.length - 1; i >= 0; i--) if (this._slots[i]?._typeId === item._typeId) return i; return undefined; }
  firstEmptySlot() { const i = this._slots.findIndex((s) => !s); return i < 0 ? undefined : i; }
  firstItem() { const i = this._slots.findIndex((s) => s); return i < 0 ? undefined : i; }
  moveItem(from, to, other) { this._idx(from); other._idx(to); other._slots[to] = this._slots[from]; this._slots[from] = undefined; }
  swapItems(a, b, other) { this._idx(a); other._idx(b); const t = this._slots[a]; this._slots[a] = other._slots[b]; other._slots[b] = t; }
  transferItem(from, other) { this._idx(from); const it = this._slots[from]; this._slots[from] = undefined; return it ? other.addItem(it) : undefined; }
}
export class ContainerSlot {
  constructor(ref, owner) { this._ref = ref; this._owner = owner; }
  _it() { const it = this._ref.get(); check(it, "container", "空のスロットの中身を触った", InvalidContainerSlotError); return it; }
  get isValid() { return !this._owner || this._owner._valid !== false; }
  get typeId() { return this._ref.get()?._typeId; }
  get amount() { return this._it().amount; }
  set amount(v) { this._it().amount = v; }
  get maxAmount() { return this._it().maxAmount; }
  get isStackable() { return this._it().isStackable; }
  get nameTag() { return this._it().nameTag; }
  set nameTag(v) { this._it().nameTag = v; }
  get lockMode() { return this._it().lockMode; }
  set lockMode(v) { this._it().lockMode = v; }
  get keepOnDeath() { return this._it().keepOnDeath; }
  set keepOnDeath(v) { this._it().keepOnDeath = v; }
  hasItem() { return !!this._ref.get(); }
  getItem() { return this._ref.get()?.clone(); }
  setItem(it) { if (it !== undefined) check(it instanceof ItemStack, "container", "setItem に ItemStack でないもの"); this._ref.set(it?.clone()); }
  getLore() { return this._it().getLore(); }
  getRawLore() { return this._it().getRawLore(); }
  setLore(l) { this._it().setLore(l); }
  getTags() { return this._it().getTags(); }
  hasTag(t) { return this._it().hasTag(t); }
  isStackableWith(o) { return this._it().isStackableWith(o); }
  getDynamicProperty(k) { return this._it().getDynamicProperty(k); }
  setDynamicProperty(k, v) { this._it().setDynamicProperty(k, v); }
  setDynamicProperties(o) { this._it().setDynamicProperties(o); }
  getDynamicPropertyIds() { return this._it().getDynamicPropertyIds(); }
  clearDynamicProperties() { this._it().clearDynamicProperties(); }
  getDynamicPropertyTotalByteCount() { return this._it().getDynamicPropertyTotalByteCount(); }
  getCanDestroy() { return this._it().getCanDestroy(); }
  getCanPlaceOn() { return this._it().getCanPlaceOn(); }
  setCanDestroy(l) { this._it().setCanDestroy(l); }
  setCanPlaceOn(l) { this._it().setCanPlaceOn(l); }
}

// ---- Molang の変数（パーティクルへ渡す） ----
const VAR_RE = /^variable\.[a-z_][a-z0-9_]*$/i;
export class MolangVariableMap {
  constructor() { this._vars = new Map(); }
  _name(n) { check(typeof n === "string" && VAR_RE.test(n), "molang", `Molang 変数名 ${fmt(n)} は "variable.<名前>" の形で`, InvalidArgumentError); }
  setFloat(n, v) { this._name(n); check(finite(v), "molang", `${n} = ${v}（有限の数でない）`, InvalidArgumentError); this._vars.set(n, v); }
  setColorRGB(n, c) {
    this._name(n);
    for (const k of ["red", "green", "blue"]) check(c && finite(c[k]) && c[k] >= 0 && c[k] <= 1, "molang", `${n}.${k} = ${c?.[k]}（0〜1）`, ArgumentOutOfBoundsError);
    this._vars.set(n, { ...c });
  }
  setColorRGBA(n, c) {
    this._name(n);
    for (const k of ["red", "green", "blue", "alpha"]) check(c && finite(c[k]) && c[k] >= 0 && c[k] <= 1, "molang", `${n}.${k} = ${c?.[k]}（0〜1）`, ArgumentOutOfBoundsError);
    this._vars.set(n, { ...c });
  }
  setSpeedAndDirection(n, speed, dir) {
    this._name(n);
    check(finite(speed), "molang", `${n} の speed ${speed}`, InvalidArgumentError);
    checkVec3(dir, `${n} の direction`);
    this._vars.set(n, { speed, dir: { ...dir } });
  }
}

// ---- 種類の登録簿 ----
export class ItemType { constructor(id) { this._id = id; } get id() { return this._id; } }
export class BlockType { constructor(id) { this._id = id; } get id() { return this._id; } }
export class EntityType { constructor(id) { this._id = id; } get id() { return this._id; } }
export class EffectType { constructor(id) { this._id = id; } getName() { return this._id; } }
export class ItemTypes {
  static get(id) { const n = nsId(id); return (n.startsWith("nr:") ? itemDef(n) : true) ? new ItemType(n) : undefined; }
  static getAll() { return [...Object.keys(DEFS.items), ...Object.keys(DEFS.blocks)].map((x) => new ItemType(x)); }
}
export class BlockTypes {
  static get(id) { const n = nsId(id); return (n.startsWith("nr:") ? DEFS.blocks[n] : true) ? new BlockType(n) : undefined; }
  static getAll() { return Object.keys(DEFS.blocks).map((x) => new BlockType(x)); }
}
export class EntityTypes {
  static get(id) { const n = nsId(id); return (n.startsWith("nr:") ? DEFS.entities[n] : true) ? new EntityType(n) : undefined; }
  static getAll() { return Object.keys(DEFS.entities).map((x) => new EntityType(x)); }
}
export class EffectTypes {
  static get(id) { const n = String(id).replace(/^minecraft:/, ""); return EFFECTS.has(n) ? new EffectType(n) : undefined; }
  static getAll() { return [...EFFECTS].map((x) => new EffectType(x)); }
}

// ===========================================================================
//  ブロックと偽の地形
// ===========================================================================
const AIR = "minecraft:air";
function packKey(x, y, z) { return ((x + 1048576) * 1024 + (y + 512)) * 2097152 + (z + 1048576); }
function unpackKey(k) {
  const z = (k % 2097152) - 1048576; const r = Math.floor(k / 2097152);
  return { x: Math.floor(r / 1024) - 1048576, y: (r % 1024) - 512, z };
}
function blockKey(x, y, z) { return packKey(Math.floor(x), Math.floor(y), Math.floor(z)); }
function paletteIndex(typeId, states) {
  const key = typeId + (states && Object.keys(states).length ? JSON.stringify(states) : "");
  let i = S.paletteIdx.get(key);
  if (i === undefined) { i = S.palette.length; S.palette.push({ typeId, states: states ?? {} }); S.paletteIdx.set(key, i); }
  return i;
}
function terrainAt(y) { return S.flat && y < S.groundY ? (y === S.groundY - 1 ? "minecraft:grass_block" : "minecraft:stone") : AIR; }
function blockAt(x, y, z) {
  const i = S.blocks.get(packKey(x, y, z));
  return i === undefined ? { typeId: terrainAt(y), states: {} } : S.palette[i];
}
const LIQUIDS = new Set(["minecraft:water", "minecraft:lava", "minecraft:flowing_water", "minecraft:flowing_lava"]);
const PASSABLE = new Set([AIR, "minecraft:short_grass", "minecraft:tall_grass", "minecraft:light_block", "minecraft:structure_void",
  "minecraft:torch", "minecraft:ladder", "minecraft:vine", "minecraft:rail", ...LIQUIDS]);
function isSolidType(t) {
  if (PASSABLE.has(t)) return false;
  const d = DEFS.blocks[t];
  if (d) return d.solid !== false;
  return true;
}
function solidAt(x, y, z) { return isSolidType(blockAt(Math.floor(x), Math.floor(y), Math.floor(z)).typeId); }
const VANILLA_LIGHT = { "minecraft:torch": 14, "minecraft:lantern": 15, "minecraft:glowstone": 15, "minecraft:sea_lantern": 15, "minecraft:redstone_lamp": 0, "minecraft:lava": 15, "minecraft:fire": 15, "minecraft:campfire": 15, "minecraft:soul_lantern": 10, "minecraft:shroomlight": 15 };
function setBlockAt(x, y, z, typeId, states) {
  x = Math.floor(x); y = Math.floor(y); z = Math.floor(z);
  const k = packKey(x, y, z);
  S.blocks.set(k, paletteIndex(typeId, states));
  const le = DEFS.blocks[typeId]?.light ?? VANILLA_LIGHT[typeId] ?? 0;
  if (le > 0) S.lights.set(k, le); else S.lights.delete(k);
}
function checkBlockId(id, what) {
  const n = nsId(typeof id === "string" ? id : id?.id ?? id?.typeId);
  check(typeof n === "string", "block", `${what} の種類 ${fmt(id)}`, InvalidArgumentError);
  if (n.startsWith("nr:")) check(DEFS.blocks[n], "block", `BP に無いブロック ${n}`, InvalidArgumentError);
  else if (n.startsWith("minecraft:") && n !== AIR) vanillaCheck("blocks", n);
  return n;
}
function skyOpen(x, y, z) {
  for (let yy = Math.floor(y) + 1; yy < Math.floor(y) + 48; yy++) if (isSolidType(blockAt(Math.floor(x), yy, Math.floor(z)).typeId)) return false;
  return true;
}
function lightAt(loc) {
  if (typeof S.light === "function") return S.light(loc);
  if (typeof S.light === "number") return S.light;
  const night = S.time >= 13000 && S.time < 23000;
  let lv = skyOpen(loc.x, loc.y, loc.z) ? (night ? 4 : 15) : 0;
  const bx = Math.floor(loc.x), by = Math.floor(loc.y), bz = Math.floor(loc.z);
  for (const [k, le] of S.lights) {
    const p = unpackKey(k);
    const d = Math.abs(p.x - bx) + Math.abs(p.y - by) + Math.abs(p.z - bz);
    if (le - d > lv) lv = le - d;
  }
  return Math.max(0, Math.min(15, lv));
}

export class BlockPermutation {
  constructor(typeId, states = {}) { this._typeId = typeId; this._states = { ...states }; }
  static resolve(name, states) {
    if (S.early && !S.harness) throw violation("early", "BlockPermutation.resolve は worldLoad の前（early execution）には使えない（script_api.md §1）");
    const n = checkBlockId(name, "BlockPermutation.resolve"); if (states) blockStatesOk(n, states); return new BlockPermutation(n, { ...defaultStates(n), ...(states ?? {}) });
  }
  get type() { return new BlockType(this._typeId); }
  getState(k) { return this._states[k]; }
  getAllStates() { return { ...this._states }; }
  withState(k, v) { blockStatesOk(this._typeId, { [k]: v }); return new BlockPermutation(this._typeId, { ...this._states, [k]: v }); }
  matches(name, states) { if (nsId(name) !== this._typeId) return false; for (const [k, v] of Object.entries(states ?? {})) if (this._states[k] !== v) return false; return true; }
  getTags() { return blockTags(this._typeId); }
  hasTag(t) { return blockTags(this._typeId).includes(t); }
  getItemStack(n = 1) { return new ItemStack(this._typeId, n); }
  canBeDestroyedByLiquidSpread() { return false; } canContainLiquid() { return false; } isLiquidBlocking() { return true; } liquidSpreadCausesSpawn() { return false; }
}
function defaultStates(id) {
  const st = DEFS.blocks[id]?.states ?? {};
  const out = {};
  for (const [k, v] of Object.entries(st)) out[k] = Array.isArray(v) ? v[0] : (v?.values?.min ?? v?.values?.[0] ?? 0);
  return out;
}
function blockStatesOk(id, states) {
  const def = DEFS.blocks[id];
  if (!def) return;
  for (const [k, v] of Object.entries(states)) {
    const allowed = def.states?.[k];
    check(allowed !== undefined, "block", `${id} に状態 ${k} が無い`, InvalidArgumentError);
    if (Array.isArray(allowed)) check(allowed.includes(v), "block", `${id} の状態 ${k} に無い値 ${fmt(v)}`, InvalidArgumentError);
  }
}
function blockTags(id) { return Object.keys(DEFS.blocks[id]?.components ?? {}).filter((k) => k.startsWith("tag:")).map((k) => k.slice(4)); }

export class Block {
  constructor(dim, x, y, z) { this._dim = dim; this._x = Math.floor(x); this._y = Math.floor(y); this._z = Math.floor(z); }
  _b() { return blockAt(this._x, this._y, this._z); }
  get dimension() { return this._dim; }
  get x() { return this._x; } get y() { return this._y; } get z() { return this._z; }
  get location() { return { x: this._x, y: this._y, z: this._z }; }
  get typeId() { return this._b().typeId; }
  get type() { return new BlockType(this.typeId); }
  get permutation() { const b = this._b(); return new BlockPermutation(b.typeId, b.states); }
  get isAir() { return this.typeId === AIR; }
  get isLiquid() { return LIQUIDS.has(this.typeId); }
  get isValid() { return true; }
  get isWaterlogged() { return false; }
  get localizationKey() { return `tile.${this.typeId}.name`; }
  _rel(dx, dy, dz) { const y = this._y + dy; if (y < -64 || y > 319) return undefined; return new Block(this._dim, this._x + dx, y, this._z + dz); }
  above(n = 1) { return this._rel(0, n, 0); }
  below(n = 1) { return this._rel(0, -n, 0); }
  north(n = 1) { return this._rel(0, 0, -n); }
  south(n = 1) { return this._rel(0, 0, n); }
  east(n = 1) { return this._rel(n, 0, 0); }
  west(n = 1) { return this._rel(-n, 0, 0); }
  offset(o) { checkVec3(o, "Block.offset"); return this._rel(Math.floor(o.x), Math.floor(o.y), Math.floor(o.z)); }
  center() { return { x: this._x + 0.5, y: this._y + 0.5, z: this._z + 0.5 }; }
  bottomCenter() { return { x: this._x + 0.5, y: this._y, z: this._z + 0.5 }; }
  setType(t) { this._dim.setBlockType(this.location, t); }
  setPermutation(p) { this._dim.setBlockPermutation(this.location, p); }
  setWaterlogged() { }
  getTags() { return blockTags(this.typeId); }
  hasTag(t) { return this.getTags().includes(t); }
  matches(name, states) { return this.permutation.matches(name, states); }
  getLightLevel() { return lightAt(this.location); }
  getSkyLightLevel() { return skyOpen(this._x, this._y, this._z) ? 15 : 0; }
  getComponent() { return undefined; }
  getItemStack(n = 1) { return this.isAir ? undefined : new ItemStack(this.typeId, n); }
  getRedstonePower() { return 0; }
  canBeDestroyedByLiquidSpread() { return false; } canContainLiquid() { return false; } isLiquidBlocking() { return true; }
  liquidCanFlowFromDirection() { return false; } liquidSpreadCausesSpawn() { return false; }
}

export class BlockVolumeBase {
  _box() { const a = this.from ?? this._from, b = this.to ?? this._to; return { min: { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), z: Math.min(a.z, b.z) }, max: { x: Math.max(a.x, b.x), y: Math.max(a.y, b.y), z: Math.max(a.z, b.z) } }; }
  getMin() { return this._box().min; }
  getMax() { return this._box().max; }
  getSpan() { const { min, max } = this._box(); return { x: max.x - min.x + 1, y: max.y - min.y + 1, z: max.z - min.z + 1 }; }
  getCapacity() { const s = this.getSpan(); return s.x * s.y * s.z; }
  isInside(p) { const { min, max } = this._box(); return p.x >= min.x && p.x <= max.x && p.y >= min.y && p.y <= max.y && p.z >= min.z && p.z <= max.z; }
  translate(d) { for (const k of ["x", "y", "z"]) { this.from[k] += d[k]; this.to[k] += d[k]; } }
  *_locs() { const { min, max } = this._box(); for (let x = min.x; x <= max.x; x++) for (let y = min.y; y <= max.y; y++) for (let z = min.z; z <= max.z; z++) yield { x, y, z }; }
  getBlockLocationIterator() { return this._locs(); }
}
export class BlockVolume extends BlockVolumeBase {
  constructor(from, to) { super(); checkVec3(from, "BlockVolume from"); checkVec3(to, "BlockVolume to"); this.from = { ...from }; this.to = { ...to }; }
  doesLocationTouchFaces(p) { const { min, max } = this._box(); return this.isInside(p) && (p.x === min.x || p.x === max.x || p.y === min.y || p.y === max.y || p.z === min.z || p.z === max.z); }
  doesVolumeTouchFaces() { throw limitation("BlockVolume.doesVolumeTouchFaces"); }
  intersects() { throw limitation("BlockVolume.intersects"); }
}
export class ListBlockVolume extends BlockVolumeBase {
  constructor(locs = []) { super(); this._list = locs.map((p) => ({ x: Math.floor(p.x), y: Math.floor(p.y), z: Math.floor(p.z) })); }
  add(l) { this._list.push(...l.map((p) => ({ ...p }))); }
  remove(l) { const s = new Set(l.map((p) => `${p.x},${p.y},${p.z}`)); this._list = this._list.filter((p) => !s.has(`${p.x},${p.y},${p.z}`)); }
  _box() { const xs = this._list; if (!xs.length) return { min: { x: 0, y: 0, z: 0 }, max: { x: -1, y: -1, z: -1 } }; const m = (k, f) => f(...xs.map((p) => p[k])); return { min: { x: m("x", Math.min), y: m("y", Math.min), z: m("z", Math.min) }, max: { x: m("x", Math.max), y: m("y", Math.max), z: m("z", Math.max) } }; }
  getCapacity() { return this._list.length; }
  *_locs() { yield* this._list; }
  translate(d) { for (const p of this._list) { p.x += d.x; p.y += d.y; p.z += d.z; } }
}

// ---- 光線 --------------------------------------------------------------------------------
function rayAabb(o, d, b) {
  let t0 = 0, t1 = Infinity;
  for (const k of ["x", "y", "z"]) {
    if (Math.abs(d[k]) < 1e-12) { if (o[k] < b.min[k] || o[k] > b.max[k]) return null; continue; }
    let a = (b.min[k] - o[k]) / d[k], c = (b.max[k] - o[k]) / d[k];
    if (a > c) [a, c] = [c, a];
    t0 = Math.max(t0, a); t1 = Math.min(t1, c);
    if (t0 > t1) return null;
  }
  return t0;
}
S.rayAabb = rayAabb;
function norm(d) { const l = Math.hypot(d.x, d.y, d.z); return l > 1e-12 ? { x: d.x / l, y: d.y / l, z: d.z / l } : null; }
function raycastBlocks(o, dIn, maxDist, opts) {
  const d = norm(dIn); if (!d) return null;
  let x = Math.floor(o.x), y = Math.floor(o.y), z = Math.floor(o.z);
  const sx = Math.sign(d.x), sy = Math.sign(d.y), sz = Math.sign(d.z);
  const nx = (v, s, p) => (s > 0 ? (Math.floor(p) + 1 - p) : (p - Math.floor(p))) / Math.abs(v || 1e-12);
  let tx = d.x ? nx(d.x, sx, o.x) : Infinity, ty = d.y ? nx(d.y, sy, o.y) : Infinity, tz = d.z ? nx(d.z, sz, o.z) : Infinity;
  const dx = d.x ? 1 / Math.abs(d.x) : Infinity, dy = d.y ? 1 / Math.abs(d.y) : Infinity, dz = d.z ? 1 / Math.abs(d.z) : Infinity;
  let t = 0, face = "Up";
  const hits = (t2) => {
    if (opts.includeLiquidBlocks && LIQUIDS.has(t2)) return true;
    if (opts.includePassableBlocks && t2 !== AIR && !LIQUIDS.has(t2)) return true;
    return isSolidType(t2);
  };
  for (let i = 0; i < 4096; i++) {
    if (t > maxDist) return null;
    const b = blockAt(x, y, z);
    if (hits(b.typeId)) {
      if (opts.blockFilter?.includeTypes && !opts.blockFilter.includeTypes.includes(b.typeId)) { /* 素通り */ }
      else if (opts.blockFilter?.excludeTypes?.includes(b.typeId)) { /* 素通り */ }
      else return { x, y, z, t, face, typeId: b.typeId, d };
    }
    if (tx < ty && tx < tz) { x += sx; t = tx; tx += dx; face = sx > 0 ? "West" : "East"; }
    else if (ty < tz) { y += sy; t = ty; ty += dy; face = sy > 0 ? "Down" : "Up"; }
    else { z += sz; t = tz; tz += dz; face = sz > 0 ? "North" : "South"; }
    if (y < -64 || y > 319) return null;
  }
  return null;
}
S.raycastBlocks = raycastBlocks;
function blockFromRay(dim, o, d, opts = {}) {
  checkVec3(o, "ray の始点"); checkVec3(d, "ray の向き");
  const md = opts.maxDistance ?? 64;
  check(finite(md) && md >= 0, "query", `maxDistance ${md}`, InvalidArgumentError);
  const h = raycastBlocks(o, d, md, opts);
  if (!h) return undefined;
  const at = { x: o.x + h.d.x * h.t, y: o.y + h.d.y * h.t, z: o.z + h.d.z * h.t };
  return { block: new Block(dim, h.x, h.y, h.z), face: h.face, faceLocation: { x: at.x - h.x, y: at.y - h.y, z: at.z - h.z } };
}
function entitiesFromRay(dim, o, dIn, opts = {}, self) {
  checkVec3(o, "ray の始点"); checkVec3(dIn, "ray の向き");
  const d = norm(dIn); if (!d) return [];
  const md = opts.maxDistance ?? 64;
  check(finite(md) && md >= 0, "query", `maxDistance ${md}`, InvalidArgumentError);
  let limit = md;
  if (!opts.ignoreBlockCollision) { const h = raycastBlocks(o, d, md, opts); if (h) limit = h.t; }
  const out = [];
  for (const e of S.entities.values()) {
    if (!e._valid || e === self || e._dim !== dim) continue;
    if (!matchQuery(e, opts, null)) continue;
    const t = rayAabb(o, d, e._aabb());
    if (t !== null && t <= limit) out.push({ entity: e, distance: t });
  }
  return out.sort((a, b) => a.distance - b.distance);
}

// ---- 問い合わせ -----------------------------------------------------------------------------
function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z); }
function matchQuery(e, q, loc) {
  const t = e._typeId;
  if (q.type !== undefined && nsId(q.type) !== t) return false;
  if (q.excludeTypes?.map(nsId).includes(t)) return false;
  const fam = e._families();
  if (q.families && !q.families.every((f) => fam.includes(f))) return false;
  if (q.excludeFamilies?.some((f) => fam.includes(f))) return false;
  if (q.tags && !q.tags.every((x) => e._tags.has(x))) return false;
  if (q.excludeTags?.some((x) => e._tags.has(x))) return false;
  const nm = e._isPlayer ? e._name : e._nameTag;
  if (q.name !== undefined && nm !== q.name) return false;
  if (q.excludeNames?.includes(nm)) return false;
  if (q.gameMode !== undefined && (!e._isPlayer || e._mode !== q.gameMode)) return false;
  if (q.excludeGameModes && e._isPlayer && q.excludeGameModes.includes(e._mode)) return false;
  if (q.minLevel !== undefined && (!e._isPlayer || e._level < q.minLevel)) return false;
  if (q.maxLevel !== undefined && (!e._isPlayer || e._level > q.maxLevel)) return false;
  for (const po of q.propertyOptions ?? []) {
    const has = e._props.has(po.propertyId);
    let ok = has;
    if (has && po.value) {
      const v = e._props.get(po.propertyId), f = po.value;
      if ("equals" in f) ok = v === f.equals;
      if ("notEquals" in f) ok = v !== f.notEquals;
      if ("lowerBound" in f) ok = ok && v >= f.lowerBound;
      if ("upperBound" in f) ok = ok && v <= f.upperBound;
    }
    if (po.exclude ? ok : !ok) return false;
  }
  if (loc) {
    const dd = dist(e._loc, loc);
    if (q.maxDistance !== undefined && dd > q.maxDistance) return false;
    if (q.minDistance !== undefined && dd < q.minDistance) return false;
    if (q.volume) {
      const v = q.volume;
      if (e._loc.x < loc.x || e._loc.x > loc.x + v.x || e._loc.y < loc.y || e._loc.y > loc.y + v.y || e._loc.z < loc.z || e._loc.z > loc.z + v.z) return false;
    }
  }
  return true;
}
function queryEntities(dim, q = {}, playersOnly = false) {
  check(q && typeof q === "object", "query", "getEntities の options は辞書");
  if (q.location !== undefined) checkVec3(q.location, "getEntities の location");
  for (const k of ["maxDistance", "minDistance", "closest", "farthest"]) if (q[k] !== undefined) check(finite(q[k]) && q[k] >= 0, "query", `getEntities の ${k} = ${q[k]}`, InvalidArgumentError);
  if ((q.maxDistance !== undefined || q.closest !== undefined || q.farthest !== undefined) && !q.location) throw violation("query", "maxDistance / closest / farthest には location が要る", InvalidArgumentError);
  if (q.volume !== undefined) checkVec3(q.volume, "getEntities の volume");
  let out = [...S.entities.values()].filter((e) => e._valid && e._dim === dim && (!playersOnly || e._isPlayer) && matchQuery(e, q, q.location));
  if (q.location && (q.closest !== undefined || q.farthest !== undefined)) {
    out.sort((a, b) => dist(a._loc, q.location) - dist(b._loc, q.location));
    if (q.farthest !== undefined) out = out.reverse().slice(0, q.farthest);
    else out = out.slice(0, q.closest);
  }
  return out;
}

// ---- パーティクル --------------------------------------------------------------------------------
function spawnParticleImpl(id, loc, vars) {
  check(typeof id === "string" && id.length > 0, "particle", `パーティクル ID ${fmt(id)}`);
  if (id.startsWith("nr:")) check(PARTICLES.has(id), "particle", `RP に無いパーティクル ${id}`, InvalidArgumentError);
  checkVec3(loc, `spawnParticle(${id}) の位置`);
  if (vars !== undefined) {
    check(vars instanceof MolangVariableMap, "particle", `spawnParticle(${id}) の 3 つめは MolangVariableMap`, InvalidArgumentError);
    for (const k of vars._vars.keys()) bump(S.log.molangVars, `${id} ${k}`);
  }
  bump(S.log.particles, id);
  S.perTick++;
  if (S.perTick > S.budget && !S.budgetHit.has(S.tick)) {
    S.budgetHit.add(S.tick);
    S.violations.push({ kind: "budget", msg: `1 tick のパーティクルが ${S.budget} 個を超えた（tick ${S.tick}。DESIGN.md §11。スクリプトの予算で抑える）`, where: where(), tick: S.tick });
  }
}

// ===========================================================================
//  ディメンション
// ===========================================================================
export class Dimension {
  constructor(id) { this._id = id; }
  get id() { return this._id; }
  get localizationKey() { return `dimension.${this._id.replace("minecraft:", "")}`; }
  get heightRange() { return { min: -64, max: 320 }; }
  getBlock(loc) {
    checkVec3(loc, "getBlock");
    if (loc.y < -64 || loc.y >= 320) return undefined;
    return new Block(this, loc.x, loc.y, loc.z);
  }
  getBlockAbove(loc, o = {}) { checkVec3(loc, "getBlockAbove"); for (let y = Math.floor(loc.y) + 1; y < 320; y++) { const b = blockAt(Math.floor(loc.x), y, Math.floor(loc.z)); if (b.typeId !== AIR) return new Block(this, loc.x, y, loc.z); } return undefined; }
  getBlockBelow(loc, o = {}) { checkVec3(loc, "getBlockBelow"); for (let y = Math.floor(loc.y) - 1; y >= -64; y--) { const b = blockAt(Math.floor(loc.x), y, Math.floor(loc.z)); if (b.typeId !== AIR) return new Block(this, loc.x, y, loc.z); } return undefined; }
  getTopmostBlock(xz, minH = -64) {
    check(xz && finite(xz.x) && finite(xz.z), "vector", "getTopmostBlock の {x, z}");
    for (let y = 319; y >= minH; y--) if (blockAt(Math.floor(xz.x), y, Math.floor(xz.z)).typeId !== AIR) return new Block(this, xz.x, y, xz.z);
    return undefined;
  }
  getBlockFromRay(loc, dir, o) { return blockFromRay(this, loc, dir, o); }
  getEntitiesFromRay(loc, dir, o) { return entitiesFromRay(this, loc, dir, o, null); }
  getEntities(q) { return queryEntities(this, q ?? {}); }
  getPlayers(q) { return queryEntities(this, q ?? {}, true); }
  getEntitiesAtBlockLocation(loc) {
    checkVec3(loc, "getEntitiesAtBlockLocation");
    const bx = Math.floor(loc.x), by = Math.floor(loc.y), bz = Math.floor(loc.z);
    return [...S.entities.values()].filter((e) => e._valid && Math.floor(e._loc.x) === bx && Math.floor(e._loc.y) === by && Math.floor(e._loc.z) === bz);
  }
  getLightLevel(loc) { checkVec3(loc, "getLightLevel"); return lightAt(loc); }
  getSkyLightLevel(loc) { checkVec3(loc, "getSkyLightLevel"); return skyOpen(loc.x, loc.y, loc.z) ? 15 : 0; }
  getBiome(loc) { return { id: "minecraft:plains", getTags: () => ["overworld"], hasTags: () => false }; }
  isChunkLoaded() { return true; }
  setBlockType(loc, type) {
    checkVec3(loc, "setBlockType");
    check(loc.y >= -64 && loc.y < 320, "block", `setBlockType の高さ ${loc.y}`, LocationOutOfWorldBoundariesError);
    const id = checkBlockId(type, "setBlockType");
    setBlockAt(loc.x, loc.y, loc.z, id, defaultStates(id));
  }
  setBlockPermutation(loc, perm) {
    checkVec3(loc, "setBlockPermutation");
    check(perm instanceof BlockPermutation, "block", "setBlockPermutation に BlockPermutation でないもの", InvalidArgumentError);
    setBlockAt(loc.x, loc.y, loc.z, perm._typeId, perm._states);
  }
  fillBlocks(vol, block, o = {}) {
    check(vol instanceof BlockVolumeBase, "block", "fillBlocks の範囲は BlockVolume", InvalidArgumentError);
    const perm = block instanceof BlockPermutation ? block : BlockPermutation.resolve(typeof block === "string" ? block : block.id);
    const cap = vol.getCapacity();
    check(cap <= 4000000, "block", `fillBlocks が ${cap} ブロック（偽物の暴走よけ 400 万まで）`);
    const done = [];
    for (const p of vol.getBlockLocationIterator()) {
      const cur = blockAt(p.x, p.y, p.z).typeId;
      if (o.blockFilter?.includeTypes && !o.blockFilter.includeTypes.map(nsId).includes(cur)) continue;
      if (o.blockFilter?.excludeTypes?.map(nsId).includes(cur)) continue;
      setBlockAt(p.x, p.y, p.z, perm._typeId, perm._states);
      done.push(p);
    }
    return new ListBlockVolume(done);
  }
  containsBlock(vol, filter) { for (const p of vol.getBlockLocationIterator()) { const t = blockAt(p.x, p.y, p.z).typeId; if (!filter?.includeTypes || filter.includeTypes.map(nsId).includes(t)) if (!filter?.excludeTypes?.map(nsId).includes(t)) return true; } return false; }
  getBlocks(vol, filter) { const out = []; for (const p of vol.getBlockLocationIterator()) { const t = blockAt(p.x, p.y, p.z).typeId; if (filter?.includeTypes && !filter.includeTypes.map(nsId).includes(t)) continue; if (filter?.excludeTypes?.map(nsId).includes(t)) continue; out.push(p); } return new ListBlockVolume(out); }
  spawnEntity(type, loc, o = {}) {
    const id = nsId(typeof type === "string" ? type : type?.id);
    check(typeof id === "string" && id.length > 0, "entity", `spawnEntity の種類 ${fmt(type)}`, InvalidArgumentError);
    if (id.startsWith("nr:")) check(DEFS.entities[id], "entity", `BP に無いエンティティ ${id}`, EntitySpawnError);
    else if (id === "minecraft:player") throw violation("entity", "プレイヤーは spawnEntity できない", EntitySpawnError);
    else vanillaCheck("entities", id);
    checkVec3(loc, `spawnEntity(${id}) の位置`);
    if (o.initialRotation !== undefined) check(finite(o.initialRotation), "entity", `initialRotation ${o.initialRotation}`, InvalidArgumentError);
    if (o.spawnEvent !== undefined && id.startsWith("nr:")) check(DEFS.entities[id].events?.[o.spawnEvent], "event", `${id} に spawnEvent ${o.spawnEvent} が無い`, InvalidArgumentError);
    check(S.entities.size < 6000, "entity", `エンティティが ${S.entities.size} 体（生成が止まらない？ gib・死体の上限を確かめる）`);
    const e = new Entity(this, id, loc, { yaw: o.initialRotation ?? 0 });
    const ev = o.spawnEvent ?? (e._def?.events?.["minecraft:entity_spawned"] ? "minecraft:entity_spawned" : undefined);
    if (ev && e._def) { e._applyEvent(e._def.events[ev], ev, 0); bump(S.log.events, ev); }
    bump(S.log.spawned, id);
    queueAfter("entitySpawn", { entity: e, cause: "Spawned" });
    return e;
  }
  spawnItem(item, loc) {
    check(item instanceof ItemStack, "item", "spawnItem に ItemStack でないもの", InvalidArgumentError);
    checkVec3(loc, "spawnItem の位置");
    const e = new Entity(this, "minecraft:item", loc, { item: item.clone() });
    bump(S.log.spawned, `minecraft:item(${item.typeId})`);
    queueAfter("entitySpawn", { entity: e, cause: "Spawned" });
    return e;
  }
  spawnParticle(id, loc, vars) { spawnParticleImpl(id, loc, vars); }
  playSound(id, loc, o = {}) { checkSound(id); checkVec3(loc, `playSound(${id}) の位置`); checkVolPitch(o); bump(S.log.sounds, id); }
  createExplosion(loc, radius, o = {}) {
    checkVec3(loc, "createExplosion の位置");
    check(finite(radius) && radius > 0 && radius <= 1000, "explosion", `爆発の半径 ${radius}`, ArgumentOutOfBoundsError);
    const ev = fireBefore("explosion", { cancel: false, dimension: this, source: o.source, getImpactedBlocks: () => [], setImpactedBlocks: () => { } });
    if (ev.cancel) return false;
    for (const e of [...S.entities.values()]) {
      if (!e._valid || e._dead) continue;
      const d = dist(e._loc, loc);
      if (d > radius * 2) continue;
      const dmg = Math.max(0, Math.floor((1 - d / (radius * 2)) * (radius * 7 + 1)));
      if (dmg > 0) e._hurt(dmg, { cause: o.source ? "entityExplosion" : "blockExplosion", damagingEntity: o.source });
      const k = norm({ x: e._loc.x - loc.x, y: 0.4, z: e._loc.z - loc.z }) ?? { x: 0, y: 1, z: 0 };
      e._vel.x += k.x * 0.6; e._vel.y += 0.4; e._vel.z += k.z * 0.6; e._onGround = false;
    }
    const impacted = [];
    if (o.breaksBlocks) {
      const r = Math.ceil(radius);
      for (let x = -r; x <= r; x++) for (let y = -r; y <= r; y++) for (let z = -r; z <= r; z++) {
        if (x * x + y * y + z * z > radius * radius) continue;
        const bx = Math.floor(loc.x) + x, by = Math.floor(loc.y) + y, bz = Math.floor(loc.z) + z;
        if (blockAt(bx, by, bz).typeId !== AIR && blockAt(bx, by, bz).typeId !== "minecraft:bedrock") { setBlockAt(bx, by, bz, AIR); impacted.push(new Block(this, bx, by, bz)); }
      }
    }
    queueAfter("explosion", { dimension: this, source: o.source, getImpactedBlocks: () => impacted });
    return true;
  }
  runCommand(cmd) { check(typeof cmd === "string", "command", "runCommand の値"); S.log.commands.push(cmd); return { successCount: 1 }; }
  setWeather(t, d) { S.weather = t; }
  placeFeature() { throw limitation("Dimension.placeFeature"); }
  placeFeatureRule() { throw limitation("Dimension.placeFeatureRule"); }
}
const DIMS = { "minecraft:overworld": new Dimension("minecraft:overworld"), "minecraft:nether": new Dimension("minecraft:nether"), "minecraft:the_end": new Dimension("minecraft:the_end") };
S.overworld = DIMS["minecraft:overworld"];

// ===========================================================================
//  構造物・スコアボード・ゲームルール
// ===========================================================================
const ROTS = enumSet("StructureRotation"), MIRRORS = enumSet("StructureMirrorAxis"), ANIM_MODES = enumSet("StructureAnimationMode");
export class Structure {
  constructor(id, data) { this._id = id; this._data = data; this._valid = true; }
  get id() { return this._id; }
  get size() { return { ...this._data.size }; }
  get isValid() { return this._valid; }
  _idx(p) { const s = this._data.size; check(p.x >= 0 && p.y >= 0 && p.z >= 0 && p.x < s.x && p.y < s.y && p.z < s.z, "structure", `構造物の外 ${fmt(p)}`, ArgumentOutOfBoundsError); return (p.x * s.y + p.y) * s.z + p.z; }
  getBlockPermutation(p) { const d = this._load(); const i = d.indices[this._idx(p)]; if (i < 0) return undefined; const b = d.palette[i]; return new BlockPermutation(b.name, b.states); }
  setBlockPermutation(p, perm) { const d = this._load(); const i = this._idx(p); if (!perm) { d.indices[i] = -1; return; } d.palette.push({ name: perm._typeId, states: perm._states }); d.indices[i] = d.palette.length - 1; }
  getIsWaterlogged() { return false; }
  saveAs(id) { const s = new Structure(id, JSON.parse(JSON.stringify(this._load()))); S.worldStructures.set(id, s); return s; }
  saveToWorld() { }
  _load() {
    if (!this._data.indices) {
      const raw = JSON.parse(fs.readFileSync(new URL("../../../" + this._data.file, import.meta.url), "utf8"));
      this._data.indices = raw.indices; this._data.palette = raw.palette;
    }
    return this._data;
  }
}
function getStructure(id) {
  if (S.worldStructures.has(id)) return S.worldStructures.get(id);
  const d = DEFS.structures?.[id];
  if (!d) return undefined;
  return new Structure(id, { size: { x: d.size[0], y: d.size[1], z: d.size[2] }, file: d.file });
}
export class StructureManager {
  get(id) { return getStructure(id); }
  getWorldStructureIds() { return [...S.worldStructures.keys()]; }
  delete(s) { const id = typeof s === "string" ? s : s.id; return S.worldStructures.delete(id); }
  createEmpty(id, size) {
    check(typeof id === "string" && id.includes(":"), "structure", `構造物 ID ${fmt(id)}（"ns:name"）`, InvalidArgumentError);
    checkVec3(size, "createEmpty の大きさ");
    const n = size.x * size.y * size.z;
    const s = new Structure(id, { size: { ...size }, indices: new Array(n).fill(-1), palette: [] });
    S.worldStructures.set(id, s); return s;
  }
  createFromWorld(id, dim, from, to) {
    checkVec3(from, "createFromWorld from"); checkVec3(to, "createFromWorld to");
    const mn = { x: Math.min(from.x, to.x), y: Math.min(from.y, to.y), z: Math.min(from.z, to.z) };
    const size = { x: Math.abs(to.x - from.x) + 1, y: Math.abs(to.y - from.y) + 1, z: Math.abs(to.z - from.z) + 1 };
    const s = this.createEmpty(id, size); const d = s._data;
    for (let x = 0; x < size.x; x++) for (let y = 0; y < size.y; y++) for (let z = 0; z < size.z; z++) {
      const b = blockAt(mn.x + x, mn.y + y, mn.z + z); d.palette.push({ name: b.typeId, states: b.states }); d.indices[(x * size.y + y) * size.z + z] = d.palette.length - 1;
    }
    return s;
  }
  place(structure, dim, loc, o = {}) {
    const id = typeof structure === "string" ? structure : structure?.id;
    const st = structure instanceof Structure ? structure : getStructure(id);
    check(st, "structure", `BP にもワールドにも無い構造物 ${fmt(id)}`, InvalidStructureError);
    check(dim instanceof Dimension, "structure", "place の dimension", InvalidArgumentError);
    checkVec3(loc, `place(${id}) の位置`);
    if (o.rotation !== undefined) check(ROTS.size === 0 || ROTS.has(o.rotation), "structure", `StructureRotation に無い ${fmt(o.rotation)}`, InvalidArgumentError);
    if (o.mirror !== undefined) check(MIRRORS.size === 0 || MIRRORS.has(o.mirror), "structure", `StructureMirrorAxis に無い ${fmt(o.mirror)}`, InvalidArgumentError);
    if (o.animationMode !== undefined) check(ANIM_MODES.size === 0 || ANIM_MODES.has(o.animationMode), "structure", `StructureAnimationMode に無い ${fmt(o.animationMode)}`, InvalidArgumentError);
    if (o.integrity !== undefined) check(finite(o.integrity) && o.integrity >= 0 && o.integrity <= 1, "structure", `integrity ${o.integrity}`, ArgumentOutOfBoundsError);
    const d = st._load(); const s = d.size;
    for (const b of new Set(d.palette.map((x) => x.name))) {
      if (String(b).startsWith("nr:")) check(DEFS.blocks[b], "structure", `構造物 ${id} のパレットに BP に無いブロック ${b}`);
    }
    const rot = o.rotation ?? "None", mir = o.mirror ?? "None";
    const ox = Math.floor(loc.x), oy = Math.floor(loc.y), oz = Math.floor(loc.z);
    const rx = rot === "Rotate90" || rot === "Rotate270" ? s.z : s.x;
    for (let x = 0; x < s.x; x++) for (let y = 0; y < s.y; y++) for (let z = 0; z < s.z; z++) {
      const i = d.indices[(x * s.y + y) * s.z + z];
      if (i === undefined || i < 0) continue;
      let px = (mir === "X" || mir === "XZ") ? s.x - 1 - x : x;
      let pz = (mir === "Z" || mir === "XZ") ? s.z - 1 - z : z;
      let qx = px, qz = pz;
      if (rot === "Rotate90") { qx = s.z - 1 - pz; qz = px; }
      else if (rot === "Rotate180") { qx = s.x - 1 - px; qz = s.z - 1 - pz; }
      else if (rot === "Rotate270") { qx = pz; qz = s.x - 1 - px; }
      const b = d.palette[i];
      if (b.name === "minecraft:structure_void") continue;
      if (o.integrity !== undefined && o.integrity < 1 && rand() > o.integrity) continue;
      if (o.includeBlocks === false) continue;
      setBlockAt(ox + qx, oy + y, oz + qz, b.name, b.states);
    }
    void rx;
    bump(S.log.structures, id);
  }
  placeJigsaw() { throw limitation("StructureManager.placeJigsaw"); }
  placeJigsawStructure() { throw limitation("StructureManager.placeJigsawStructure"); }
}
export class ScoreboardObjective {
  constructor(id, name) { this._id = id; this._name = name ?? id; this._scores = new Map(); this._valid = true; }
  get id() { return this._id; } get displayName() { return this._name; } get isValid() { return this._valid; }
  _k(p) { return typeof p === "string" ? p : p?._id ?? p?.id; }
  setScore(p, v) { check(Number.isInteger(v), "scoreboard", `スコア ${v}`); this._scores.set(this._k(p), v); }
  addScore(p, v) { const n = (this._scores.get(this._k(p)) ?? 0) + v; this._scores.set(this._k(p), n); return n; }
  getScore(p) { return this._scores.get(this._k(p)); }
  hasParticipant(p) { return this._scores.has(this._k(p)); }
  removeParticipant(p) { return this._scores.delete(this._k(p)); }
  getScores() { return [...this._scores].map(([k, v]) => ({ participant: { id: k, displayName: k }, score: v })); }
  getParticipants() { return [...this._scores.keys()].map((k) => ({ id: k, displayName: k })); }
}
export class Scoreboard {
  constructor() { this._obj = new Map(); }
  addObjective(id, name) { check(!this._obj.has(id), "scoreboard", `スコアボード ${id} は既にある`); const o = new ScoreboardObjective(id, name); this._obj.set(id, o); return o; }
  getObjective(id) { return this._obj.get(id); }
  getObjectives() { return [...this._obj.values()]; }
  removeObjective(o) { return this._obj.delete(typeof o === "string" ? o : o.id); }
  getParticipants() { return []; }
  setObjectiveAtDisplaySlot() { return undefined; }
  getObjectiveAtDisplaySlot() { return undefined; }
  clearObjectiveAtDisplaySlot() { return undefined; }
}
export class GameRules {
  constructor() {
    Object.assign(this, { commandBlockOutput: true, commandBlocksEnabled: true, doDayLightCycle: true, doEntityDrops: true,
      doFireTick: true, doImmediateRespawn: false, doInsomnia: true, doLimitedCrafting: false, doMobLoot: true, doMobSpawning: true,
      doTileDrops: true, doWeatherCycle: true, drowningDamage: true, fallDamage: true, fireDamage: true, freezeDamage: true,
      functionCommandLimit: 10000, keepInventory: false, maxCommandChainLength: 65536, mobGriefing: true, naturalRegeneration: true,
      playersSleepingPercentage: 100, projectilesCanBreakBlocks: true, pvp: true, randomTickSpeed: 1, recipesUnlock: true,
      respawnBlocksExplode: true, sendCommandFeedback: true, showBorderEffect: true, showCoordinates: false, showDaysPlayed: false,
      showDeathMessages: true, showRecipeMessages: true, showTags: true, spawnRadius: 5, tntExplodes: true, tntExplosionDropDecay: false });
  }
}

// ===========================================================================
//  ワールドとシステム
// ===========================================================================
const TIME_OF_DAY = ENUMS.TimeOfDay ?? {};
export class World {
  constructor() { this._rules = new GameRules(); this._score = new Scoreboard(); this._sm = new StructureManager(); this._spawn = { x: 0, y: 64, z: 0 }; this._diff = "Normal"; }
  get afterEvents() { return SIG.wa; }
  get beforeEvents() { return SIG.wb; }
  get gameRules() { return this._rules; }
  get isHardcore() { return false; }
  get scoreboard() { return this._score; }
  get structureManager() { return this._sm; }
  getAllPlayers() { return S.players.filter((p) => p._valid); }
  getPlayers(q) { return queryEntities(S.overworld, q ?? {}, true); }
  getDimension(id) {
    const n = nsId(String(id));
    check(DIMS[n], "world", `知らないディメンション ${fmt(id)}`, InvalidArgumentError);
    return DIMS[n];
  }
  getEntity(id) { const e = S.entities.get(String(id)); return e && e._valid ? e : undefined; }
  getTimeOfDay() { return S.time; }
  setTimeOfDay(t) { const v = typeof t === "number" ? t : TIME_OF_DAY[t] ?? t; check(Number.isInteger(v) && v >= 0, "world", `setTimeOfDay(${fmt(t)})`); S.time = v % 24000; }
  getAbsoluteTime() { return S.absTime; }
  setAbsoluteTime(t) { check(Number.isInteger(t) && t >= 0, "world", `setAbsoluteTime(${t})`); S.absTime = t; }
  getDay() { return Math.floor(S.absTime / 24000); }
  getMoonPhase() { return "FullMoon"; }
  getDefaultSpawnLocation() { return { ...this._spawn }; }
  setDefaultSpawnLocation(p) { checkVec3(p, "setDefaultSpawnLocation"); this._spawn = { ...p }; }
  getDifficulty() { return this._diff; }
  setDifficulty(d) { this._diff = d; }
  getDynamicProperty(k) { return S.worldDP.get(k); }
  setDynamicProperty(k, v) { dpSet(S.worldDP, k, v, "world"); }
  setDynamicProperties(o) { for (const [k, v] of Object.entries(o)) dpSet(S.worldDP, k, v, "world"); }
  getDynamicPropertyIds() { return [...S.worldDP.keys()]; }
  clearDynamicProperties() { S.worldDP.clear(); }
  getDynamicPropertyTotalByteCount() { return dpBytes(S.worldDP); }
  sendMessage(m) { S.log.messages.push(textOf(m)); }
  playMusic() { } queueMusic() { } stopMusic() { }
  getLootTableManager() {
    notice("getLootTableManager は空の結果を返す（偽物）");
    return { generateLootFromEntity: () => [], generateLootFromBlock: () => [], generateLootFromTable: () => [], getLootTable: () => undefined };
  }
}
export const world = new World();

export class System {
  get currentTick() { return S.tick; }
  get afterEvents() { return SIG.sa; }
  get beforeEvents() { return SIG.sb; }
  get isEditorWorld() { return false; }
  get serverSystemInfo() { return { memoryTier: "High" }; }
  _add(kind, cb, delay, every) {
    check(typeof cb === "function", "system", `system.${kind} に関数でないもの`, TypeError);
    if (delay !== undefined) check(finite(delay) && delay >= 0, "system", `system.${kind} の tick ${delay}`, ArgumentOutOfBoundsError);
    const id = S.nextRun++;
    S.timers.push({ id, kind, cb, due: S.tick + Math.max(1, Math.floor(every ?? delay ?? 1)), every: every !== undefined ? Math.max(1, Math.floor(every)) : 0 });
    return id;
  }
  run(cb) { return this._add("run", cb); }
  runTimeout(cb, t = 1) { return this._add("runTimeout", cb, t); }
  runInterval(cb, t = 1) { check(finite(t) && t >= 0, "system", `runInterval の間隔 ${t}`, ArgumentOutOfBoundsError); return this._add("runInterval", cb, undefined, t); }
  clearRun(id) { for (const t of S.timers) if (t.id === id) t.cleared = true; }
  runJob(gen) {
    check(gen && typeof gen.next === "function", "system", "runJob にはジェネレータ（function* の戻り値）を渡す", TypeError);
    const id = S.nextRun++; S.jobs.push({ id, gen }); return id;
  }
  clearJob(id) { S.jobs = S.jobs.filter((j) => j.id !== id); }
  waitTicks(n) {
    check(Number.isInteger(n) && n >= 1, "system", `waitTicks(${n})（1 以上の整数）`, ArgumentOutOfBoundsError);
    return new Promise((res) => { S.timers.push({ id: S.nextRun++, kind: "waitTicks", cb: res, due: S.tick + n, every: 0 }); });
  }
  sendScriptEvent(id, message) {
    check(typeof id === "string" && /^[a-z0-9_.-]+:[\w.-]+$/i.test(id) && !id.startsWith("minecraft:"), "scriptevent", `scriptevent の ID ${fmt(id)}（"ns:name"、minecraft 以外）`, NamespaceNameError);
    queueAfter("scriptEventReceive", { id, message: String(message ?? ""), sourceType: "Server" });
  }
}
export const system = new System();

// ---- カスタムコンポーネント・カスタムコマンドの登録 ----
const BLOCK_HOOKS = new Set(["beforeOnPlayerPlace", "onEntityFallOn", "onPlace", "onPlayerBreak", "onPlayerInteract", "onRandomTick", "onStepOff", "onStepOn", "onTick", "onRedstoneUpdate", "onBreak"]);
const ITEM_HOOKS = new Set(["onBeforeDurabilityDamage", "onCompleteUse", "onConsume", "onHitEntity", "onMineBlock", "onUse", "onUseOn"]);
function regCheck(kind, name, comp, hooks, map, DupErr) {
  check(S.phase === "startup", "startup", `${kind}ComponentRegistry.registerCustomComponent は system.beforeEvents.startup の中だけ（今は ${S.phase}）`, CustomComponentInvalidRegistryError);
  check(typeof name === "string" && /^[a-z0-9_]+:[a-z0-9_]+$/.test(name) && !name.startsWith("minecraft:"), "startup", `カスタムコンポーネントの名前 ${fmt(name)}`, CustomComponentNameError);
  check(comp && typeof comp === "object", "startup", `${name} の中身が辞書でない`);
  for (const k of Object.keys(comp)) check(hooks.has(k), "startup", `${name}: ${kind} のカスタムコンポーネントに無いフック ${k}`);
  check(!map.has(name), "startup", `${name} を二重に登録`, DupErr);
  map.set(name, comp);
}
export class BlockComponentRegistry { registerCustomComponent(name, c) { regCheck("block", name, c, BLOCK_HOOKS, S.reg.block, BlockCustomComponentAlreadyRegisteredError); } }
export class ItemComponentRegistry { registerCustomComponent(name, c) { regCheck("item", name, c, ITEM_HOOKS, S.reg.item, ItemCustomComponentAlreadyRegisteredError); } }
export class CustomCommandRegistry {
  registerCommand(cmd, cb) {
    check(S.phase === "startup", "startup", "registerCommand は startup の中だけ");
    check(cmd && typeof cmd.name === "string" && /^[a-z0-9_]+:[a-z0-9_]+$/.test(cmd.name), "startup", `カスタムコマンドの名前 ${fmt(cmd?.name)}`, CustomComponentNameError);
    check(typeof cmd.description === "string", "startup", `${cmd.name} の description`);
    check(typeof cb === "function", "startup", `${cmd.name} の関数`);
    S.reg.commands.set(cmd.name, { cmd, cb });
  }
  registerEnum(name, values) { check(Array.isArray(values), "startup", "registerEnum の値"); S.reg.enums.set(name, values); }
}
export class StartupEvent {
  constructor() { this._b = new BlockComponentRegistry(); this._i = new ItemComponentRegistry(); this._c = new CustomCommandRegistry(); }
  get blockComponentRegistry() { return this._b; }
  get itemComponentRegistry() { return this._i; }
  get customCommandRegistry() { return this._c; }
}
function customOf(def) { return def?.custom ?? {}; }
function callHook(map, compName, hook, ev, params) {
  const comp = map.get(compName);
  if (!comp || typeof comp[hook] !== "function") return false;
  try { comp[hook](ev, { params }); } catch (e) { recordError(`custom component ${compName}.${hook}`, e); }
  return true;
}
function blockHookAt(typeId, p, hook, extra) {
  const def = DEFS.blocks[typeId];
  if (!def) return false;
  let any = false;
  for (const [name, params] of Object.entries(customOf(def))) {
    any = callHook(S.reg.block, name, hook, { block: new Block(S.overworld, p.x, p.y, p.z), dimension: S.overworld, ...extra }, params) || any;
  }
  return any;
}
function blockHook(key, hook, extra) {
  const p = unpackKey(key);
  return blockHookAt(blockAt(p.x, p.y, p.z).typeId, p, hook, extra);
}
function itemHook(item, hook, ev) {
  if (!item) return false;
  const def = DEFS.items[item.typeId];
  let any = false;
  for (const [name, params] of Object.entries(customOf(def))) any = callHook(S.reg.item, name, hook, ev, params) || any;
  return any;
}
S.blockHook = (pos, hook, extra) => blockHook(blockKey(pos.x, pos.y, pos.z), hook, extra);
// 置く前・壊した後など「今そこに無いブロック」の種類で呼ぶ
S.blockHookFor = (typeId, pos, hook, extra) => blockHookAt(typeId, { x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z) }, hook, extra);
S.itemHook = itemHook;
S.unregisteredCustomComponents = () => {
  const miss = [];
  for (const [id, d] of Object.entries(DEFS.blocks)) for (const n of Object.keys(customOf(d))) if (!S.reg.block.has(n)) miss.push(`block ${id}: ${n}`);
  for (const [id, d] of Object.entries(DEFS.items)) for (const n of Object.keys(customOf(d))) if (!S.reg.item.has(n)) miss.push(`item ${id}: ${n}`);
  return miss;
};

// ===========================================================================
//  tick の進行・起動・後片付け（テストの道具から使う）
// ===========================================================================
function stepBlocks() {
  // onStepOn / onStepOff / 地面のブロックの onTick
  for (const e of S.entities.values()) {
    if (!e._valid) continue;
    const k = e._onGround ? blockKey(e._loc.x, e._loc.y - 0.01, e._loc.z) : null;
    const prev = S.stepState.get(e._id) ?? null;
    if (k !== prev) {
      if (prev !== null) blockHook(prev, "onStepOff", { entity: e });
      if (k !== null) blockHook(k, "onStepOn", { entity: e });
      S.stepState.set(e._id, k);
    }
  }
  if (S.reg.block.size) {
    for (const [k, idx] of [...S.blocks]) {
      const def = DEFS.blocks[S.palette[idx].typeId];
      if (!def?.tick) continue;
      const every = Math.max(1, def.tick[0] ?? 20);
      if (S.tick % every === 0) blockHook(k, "onTick", {});
    }
  }
}
// プレイヤーの入力（setInput の移動・ジャンプ長押し）。プレイヤーは実機ではクライアントが動かす
const WALK = 0.215, SPRINT = 0.28, SNEAK = 0.065, JUMP_V = 0.42;
function stepInput(p) {
  if (!p._valid || p._dead) return;
  const m = p._move;
  if (m.x || m.y) {
    const yaw = p._rot.y * Math.PI / 180;
    const F = { x: -Math.sin(yaw), z: Math.cos(yaw) }, R = { x: -Math.cos(yaw), z: -Math.sin(yaw) };
    let dx = F.x * m.y + R.x * m.x, dz = F.z * m.y + R.z * m.x;
    const l = Math.hypot(dx, dz) || 1;
    const sp = p._sneaking ? SNEAK : (p._sprinting ? SPRINT : WALK);
    dx = dx / Math.max(1, l) * sp; dz = dz / Math.max(1, l) * sp;
    const V = p._vel;
    if (p._onGround) {
      // ノックバックの方が速ければそちらを残す
      if (Math.hypot(V.x, V.z) <= sp + 1e-9) { V.x = dx; V.z = dz; }
    } else { V.x += dx * 0.1; V.z += dz * 0.1; }
  }
  if (p._jumping && p._onGround && p._vel.y <= 0) { p._vel.y = JUMP_V; p._onGround = false; }
}
function runTimers() {
  const due = S.timers.filter((t) => !t.cleared && t.due <= S.tick).sort((a, b) => a.due - b.due || a.id - b.id);
  for (const t of due) {
    if (t.cleared) continue;
    if (t.every) t.due += t.every; else t.cleared = true;
    try { t.cb(); } catch (e) { recordError(`system.${t.kind}`, e); }
    flush();   // V2: タスクごとに after イベントを流す
  }
  S.timers = S.timers.filter((t) => !t.cleared);
}
function runJobs() {
  for (const j of [...S.jobs]) {
    for (let i = 0; i < 256; i++) {
      let r;
      try { r = j.gen.next(); } catch (e) { recordError("system.runJob", e); r = { done: true }; }
      if (r.done) { S.jobs = S.jobs.filter((x) => x !== j); break; }
    }
  }
}
S.__tick = function () {
  S.tick++;
  S.perTick = 0;
  if (world.gameRules.doDayLightCycle && S.daylightCycle) { S.time = (S.time + 1) % 24000; S.absTime++; }
  for (const p of S.players) stepInput(p);
  for (const e of [...S.entities.values()]) if (e._valid) { try { e._physicsStep(); } catch (err) { recordError("physics", err); } }
  for (const e of [...S.entities.values()]) if (e._valid) e._statusStep();
  stepBlocks();
  flush();
  runTimers();
  runJobs();
  flush();
  for (const e of S.pendingRemove) e._removeNow(false);
  S.pendingRemove.clear();
  flush();
  if (S.perTick > S.maxPerTick) { S.maxPerTick = S.perTick; S.maxPerTickAt = S.tick; }
};
S.__startup = function () {
  S.phase = "startup";
  const ev = new StartupEvent();
  dispatch(SIG.sb.startup, "startup", ev);
  S.phase = "early";
};
S.__worldLoad = function () {
  S.early = false; S.phase = "world";
  queueAfter("worldLoad", {});
  flush();
};
S.createPlayer = function (name, loc) {
  const p = new Player(S.overworld, loc, name);
  queueAfter("playerJoin", { playerId: p._id, playerName: name });
  queueAfter("playerSpawn", { player: p, initialSpawn: true });
  return p;
};
S.resetWorld = function () {
  for (const e of [...S.entities.values()]) { e._valid = false; }
  S.entities.clear(); S.players.length = 0; S.queue.length = 0; S.pendingRemove.clear(); S.stepState.clear();
  S.blocks.clear(); S.lights.clear(); S.groundY = 64; S.flat = true; S.time = 1000; S.light = null;
  S.formQueue.length = 0; S.forms.length = 0; S.budgetHit.clear();
};
S.blockAt = blockAt; S.setBlockAt = setBlockAt; S.lightAt = lightAt; S.solidAt = solidAt; S.checkBlockId = checkBlockId;
S.getStructure = getStructure; S.textOf = textOf; S.newLog = newLog; S.blockKey = blockKey;

// ---- 実機の制限（d.ts の注記から）: read-only・early-execution・無効なエンティティ ----
// d.ts の @remarks の定型文を test_nr.py が拾って API.classes[クラス].members[名前] = {kind, static, ro, early} にしている。
const VALID_FREE = new Set(["id", "typeId", "isValid", "constructor"]);
const EARLY_GUARDED = new Set(["World", "Dimension", "StructureManager", "Scoreboard", "ScoreboardObjective", "GameRules"]);
function guardOne(api, clsName, proto, name, desc) {
  const m = api.classes?.[clsName]?.members?.[name];
  const roBlocked = !!m?.ro;
  const earlyOk = !!m?.early;
  const earlyGuard = EARLY_GUARDED.has(clsName) && !earlyOk;
  const isEnt = proto === Entity.prototype || proto instanceof Entity;
  const need = (kind) => {
    if (S.harness > 0) return;   // テストの道具が中身を触るとき
    if ((kind === "call" || kind === "set") && roBlocked && S.readOnly > 0) {
      throw violation("readonly", `${clsName}.${name} は before イベント（read-only）の中では使えない — system.run へ逃がす`);
    }
    if (earlyGuard && S.early) throw violation("early", `${clsName}.${name} は worldLoad の前（early execution）には使えない — world.afterEvents.worldLoad か system.run の中で`);
  };
  const invalid = function (self) {
    if (isEnt && !VALID_FREE.has(name) && self && self._valid === false && !S.harness) {
      notice("無効なエンティティを触った（InvalidEntityError）");
      throw new InvalidEntityError(`[fake] 無効なエンティティ ${self._typeId}#${self._id} の ${name}（先に isValid を見る）`);
    }
  };
  if (typeof desc.value === "function") {
    const f = desc.value;
    Object.defineProperty(proto, name, { ...desc, value: function (...a) { need("call"); invalid(this); return f.apply(this, a); } });
  } else if (desc.get || desc.set) {
    const g = desc.get, st = desc.set;
    Object.defineProperty(proto, name, { ...desc,
      get: g ? function () { need("get"); invalid(this); return g.call(this); } : undefined,
      set: st ? function (v) { need("set"); invalid(this); return st.call(this, v); } : undefined });
  }
}
// classes = {d.ts のクラス名: 偽物のクラス}。手書きのメンバーにガードを付け、d.ts にあって偽物に無いメンバーは
// 「偽物の限界」と分かる例外にする（プロパティは読むと例外。コンストラクタで代入した値はそのまま持てる）
function installGuards(classes, api = API) {
  for (const [clsName, cls] of Object.entries(classes)) {
    const proto = cls.prototype;
    for (const name of Object.getOwnPropertyNames(proto)) {
      if (name === "constructor" || name.startsWith("_")) continue;
      guardOne(api, clsName, proto, name, Object.getOwnPropertyDescriptor(proto, name));
    }
    for (const [name, m] of Object.entries(api.classes?.[clsName]?.members ?? {})) {
      if (name === "constructor") continue;
      const target = m.static ? cls : proto;
      // static は自分のものだけ（親の componentId を引き継がない）。インスタンスのメンバーは継承した実装でよい
      if (m.static ? Object.prototype.hasOwnProperty.call(target, name) : name in target) continue;
      const what = `${clsName}.${name}`;
      if (m.value !== undefined) {
        Object.defineProperty(target, name, { value: m.value, enumerable: true, configurable: true });
      } else if (m.kind === "method") {
        Object.defineProperty(target, name, { value: function () { throw limitation(what); }, configurable: true, writable: true });
      } else {
        Object.defineProperty(target, name, { configurable: true,
          get() { throw limitation(what); },
          set(v) { Object.defineProperty(this, name, { value: v, writable: true, enumerable: true, configurable: true }); } });
      }
    }
  }
}
S.installGuards = installGuards;
// 偽物にあって d.ts に無い（実機に無い）公開メンバー。自己テストで空であることを確かめる
S.surfaceExtras = function (classes, api = API) {
  const out = [];
  const membersOf = (n) => { const ms = new Set(); let c = n; while (c && api.classes?.[c]) { for (const k of Object.keys(api.classes[c].members ?? {})) ms.add(k); c = api.classes[c].extends; } return ms; };
  for (const [clsName, cls] of Object.entries(classes)) {
    if (!api.classes?.[clsName]) { out.push(`${clsName}（d.ts に無いクラス）`); continue; }
    const ms = membersOf(clsName);
    for (const name of Object.getOwnPropertyNames(cls.prototype)) if (name !== "constructor" && !name.startsWith("_") && !ms.has(name)) out.push(`${clsName}.${name}`);
    for (const name of Object.getOwnPropertyNames(cls)) if (!["length", "name", "prototype"].includes(name) && !name.startsWith("_") && !ms.has(name)) out.push(`${clsName}.${name} (static)`);
  }
  return out;
};
const IMPLEMENTED = { Entity, Player, Component, EntityComponent, EntityAttributeComponent, EntityHealthComponent,
  EntityMovementComponent, EntityTypeFamilyComponent, EntityOnFireComponent, EntityItemComponent, EntityInventoryComponent,
  EntityEquippableComponent, EntityProjectileComponent, Camera, ScreenDisplay, InputInfo, PlayerInputPermissions, ItemStack,
  ItemComponent, ItemDurabilityComponent, ItemCooldownComponent, ItemFoodComponent, ItemEnchantableComponent, Container,
  ContainerSlot, MolangVariableMap, ItemType, BlockType, EntityType, EffectType, ItemTypes, BlockTypes, EntityTypes, EffectTypes,
  BlockPermutation, Block, BlockVolumeBase, BlockVolume, ListBlockVolume, Dimension, Structure, StructureManager,
  ScoreboardObjective, Scoreboard, GameRules, World, System, BlockComponentRegistry, ItemComponentRegistry,
  CustomCommandRegistry, StartupEvent };
S.IMPLEMENTED = IMPLEMENTED;
