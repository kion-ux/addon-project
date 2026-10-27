// 偽の @minecraft/server-ui 2.0.0（NIGHT RUNNER の挙動テスト用。test_nr.py が node_modules に置く）。
//
// * 2.0.0 の形だけ受け付ける: slider(label, min, max, {defaultValue, valueStep, tooltip}) /
//   toggle(label, {defaultValue, tooltip}) / dropdown(label, items, {defaultValueIndex, tooltip}) /
//   textField(label, placeholder, {defaultValue, tooltip})。1.x の位置引数の形は契約違反（kind "ui"）。
// * show() は before イベントの中（read-only）・early execution では違反。答えはテストが
//   answerForm() で前もって積んでおく（S.formQueue）。答えは次の tick に返る（実機も非同期）。
// * 入力の間（ボタンの間）に label / header / divider を挟むのは違反（script_api.md §15:
//   formValues の番号がずれるかは要実機確認なので、挟まない約束）。
// * 答えが積まれていなければ「プレイヤーが閉じた」（canceled + UserClosed）として返し、注意を数える。
import { Player } from "@minecraft/server";

const S = globalThis.__nr;
const UI = S.ENV.apiUi || { classes: {}, enums: {} };
const { violation, check, fmt, textOf, notice } = S;

export const FormCancelationReason = Object.freeze(UI.enums?.FormCancelationReason ?? { UserBusy: "UserBusy", UserClosed: "UserClosed" });
export const FormRejectReason = Object.freeze(UI.enums?.FormRejectReason ?? { MalformedResponse: "MalformedResponse", PlayerQuit: "PlayerQuit", ServerShutdown: "ServerShutdown" });

export class FormRejectError extends Error {
  constructor(reason) { super(`[fake] フォームが拒否された: ${reason}`); this.name = "FormRejectError"; this.reason = reason; }
}

// ---- 応答 ----------------------------------------------------------------------------
export class FormResponse {
  constructor(canceled, reason) { this._canceled = canceled; this._reason = reason; }
  get canceled() { return this._canceled; }
  get cancelationReason() { return this._reason; }
}
export class ActionFormResponse extends FormResponse {
  constructor(canceled, reason, sel) { super(canceled, reason); this._sel = sel; }
  get selection() { return this._sel; }
}
export class MessageFormResponse extends FormResponse {
  constructor(canceled, reason, sel) { super(canceled, reason); this._sel = sel; }
  get selection() { return this._sel; }
}
export class ModalFormResponse extends FormResponse {
  constructor(canceled, reason, values) { super(canceled, reason); this._values = values; }
  get formValues() { return this._values ? [...this._values] : undefined; }
}

// ---- 入力の確かめ -------------------------------------------------------------------------
function rawOk(t, what) {
  const ok = typeof t === "string" || (t && typeof t === "object" && !Array.isArray(t) &&
    ["rawtext", "text", "translate", "score", "with"].some((k) => k in t));
  check(ok, "ui", `${what} は文字列か RawMessage（{text} / {translate} / {rawtext}）: ${fmt(t)}`, TypeError);
  return t;
}
function optsOk(o, keys, what) {
  if (o === undefined) return {};
  check(o && typeof o === "object" && !Array.isArray(o), "ui", `${what} の最後はオプションの辞書（server-ui 2.0.0 の形）: ${fmt(o)}`, TypeError);
  for (const k of Object.keys(o)) check(keys.includes(k), "ui", `${what} のオプションに無いキー ${k}（使えるのは ${keys.join(" / ")}）`, TypeError);
  if (o.tooltip !== undefined) rawOk(o.tooltip, `${what} の tooltip`);
  return o;
}
// オプションの辞書のキーは d.ts（ModalFormData*Options）から。読めなければ 2.0.0 の値
const uiKeys = (n, fb) => (UI.interfaces?.[n]?.length ? UI.interfaces[n] : fb);
const INPUTS = new Set(["slider", "toggle", "dropdown", "textField"]);
const DECOR = new Set(["label", "header", "divider"]);
function layoutOk(f) {
  // 入力（ボタン）より前に label / header / divider があれば違反
  const isInput = (c) => (f.type === "action" ? c.type === "button" : INPUTS.has(c.type));
  let lastInput = -1;
  f.controls.forEach((c, i) => { if (isInput(c)) lastInput = i; });
  const bad = f.controls.findIndex((c, i) => DECOR.has(c.type) && i < lastInput);
  check(bad < 0, "ui", `${f.title || f.type} のフォーム: ${f.controls[bad]?.type} を入力${f.type === "action" ? "（ボタン）" : ""}より前に置かない（formValues / selection の番号がずれうる。置くなら全部の後ろ。script_api.md §15）`);
}

// ---- show の本体 -----------------------------------------------------------------------------
function describe(f, player) {
  return {
    type: f.type, title: f.title, body: f.body, player: player._name, tick: S.tick,
    buttons: f.controls.filter((c) => c.type === "button").map((c) => c.text),
    icons: f.controls.filter((c) => c.type === "button").map((c) => c.icon),
    controls: f.controls.map((c) => ({ ...c })),
    inputs: f.controls.filter((c) => INPUTS.has(c.type)).map((c) => ({ ...c })),
    submit: f.submit, button1: f.button1, button2: f.button2,
  };
}
function defaultsOf(desc) {
  return desc.inputs.map((c) => (c.type === "slider" ? c.defaultValue ?? c.min : c.type === "toggle" ? c.defaultValue ?? false
    : c.type === "dropdown" ? c.defaultValueIndex ?? 0 : c.defaultValue ?? ""));
}
function answerError(msg) {
  // テストの書き方の誤り（アドオンの不具合ではない）
  return new Error(`[answerForm] ${msg}`);
}
function resolveAnswer(f, desc) {
  let ans = S.formQueue.length ? S.formQueue.shift() : undefined;
  if (typeof ans === "function") ans = ans(desc);
  if (ans === undefined) {
    notice("フォームに答えが積まれていない（answerForm）→ プレイヤーが閉じた扱い");
    return { canceled: true, reason: FormCancelationReason.UserClosed };
  }
  if (ans && typeof ans === "object" && !Array.isArray(ans)) {
    if (ans.reject) return { reject: ans.reject };
    if (ans.canceled) return { canceled: true, reason: ans.reason ?? FormCancelationReason.UserClosed };
    throw answerError(`知らない答え ${fmt(ans)}（番号・配列・{canceled:true, reason}・{reject}・"defaults"・関数）`);
  }
  if (f.type === "modal") {
    const vals = ans === "defaults" ? defaultsOf(desc) : ans;
    if (!Array.isArray(vals)) throw answerError(`ModalFormData の答えは配列（入力 ${desc.inputs.length} 個の値）: ${fmt(ans)}`);
    if (vals.length !== desc.inputs.length) throw answerError(`ModalFormData「${desc.title}」の入力は ${desc.inputs.length} 個、答えは ${vals.length} 個`);
    desc.inputs.forEach((c, i) => {
      const v = vals[i];
      const ok = c.type === "toggle" ? typeof v === "boolean"
        : c.type === "textField" ? typeof v === "string"
        : c.type === "dropdown" ? Number.isInteger(v) && v >= 0 && v < c.items.length
        : typeof v === "number" && v >= c.min && v <= c.max;
      if (!ok) throw answerError(`「${desc.title}」の ${i} 番目（${c.type} ${c.label}）に ${fmt(v)} は入らない`);
    });
    return { values: [...vals] };
  }
  const n = f.type === "action" ? desc.buttons.length : 2;
  if (!(Number.isInteger(ans) && ans >= 0 && ans < n)) throw answerError(`「${desc.title}」のボタンは ${n} 個。答え ${fmt(ans)}`);
  return { selection: ans };
}
function show(f, player) {
  if (!S.harness) {
    if (S.early) throw violation("early", `${f.type} フォームの show は worldLoad の前には使えない`);
    if (S.readOnly > 0) throw violation("readonly", "フォームの show は before イベント（read-only）の中では使えない — system.run で開く");
  }
  check(player instanceof Player, "ui", `show の相手が Player でない: ${fmt(player)}`, TypeError);
  layoutOk(f);
  if (f.type === "action" && !f.controls.some((c) => c.type === "button")) notice("ボタンの無い ActionFormData を開いた");
  const desc = describe(f, player);
  S.forms.push(desc);
  S.bump(S.uiShown, f.type);
  return new Promise((resolve, reject) => {
    S.timers.push({ id: S.nextRun++, kind: "form", due: S.tick + 1, every: 0, cb: () => {
      if (!player._valid) { reject(new FormRejectError(FormRejectReason.PlayerQuit)); return; }
      if (desc.closedAt !== undefined) { resolve(mk(f, { canceled: true, reason: FormCancelationReason.UserClosed })); return; }
      let r;
      try { r = resolveAnswer(f, desc); } catch (e) { S.errors.push({ where: "answerForm", msg: e.message, stack: [], tick: S.tick }); r = { canceled: true, reason: FormCancelationReason.UserClosed }; }
      desc.answer = r;
      if (r.reject) reject(new FormRejectError(r.reject));
      else resolve(mk(f, r));
    } });
  });
}
function mk(f, r) {
  if (f.type === "modal") return new ModalFormResponse(!!r.canceled, r.reason, r.canceled ? undefined : r.values);
  if (f.type === "message") return new MessageFormResponse(!!r.canceled, r.reason, r.canceled ? undefined : r.selection);
  return new ActionFormResponse(!!r.canceled, r.reason, r.canceled ? undefined : r.selection);
}

// ---- フォーム ----------------------------------------------------------------------------------
export class ActionFormData {
  constructor() { this._f = { type: "action", title: "", body: "", controls: [] }; }
  title(t) { this._f.title = textOf(rawOk(t, "ActionFormData.title")); return this; }
  body(t) { this._f.body = textOf(rawOk(t, "ActionFormData.body")); return this; }
  button(text, iconPath) {
    rawOk(text, "ActionFormData.button");
    if (iconPath !== undefined) {
      check(typeof iconPath === "string" && iconPath.length > 0, "ui", `button の iconPath は文字列: ${fmt(iconPath)}`, TypeError);
      if (/\.(png|tga|jpe?g)$/i.test(iconPath)) notice("フォームのボタンの絵は拡張子なしのパスで書く");
    }
    this._f.controls.push({ type: "button", text: textOf(text), icon: iconPath });
    return this;
  }
  divider() { this._f.controls.push({ type: "divider" }); return this; }
  header(t) { this._f.controls.push({ type: "header", text: textOf(rawOk(t, "ActionFormData.header")) }); return this; }
  label(t) { this._f.controls.push({ type: "label", text: textOf(rawOk(t, "ActionFormData.label")) }); return this; }
  show(player) { return show(this._f, player); }
}

export class MessageFormData {
  constructor() { this._f = { type: "message", title: "", body: "", controls: [] }; }
  title(t) { this._f.title = textOf(rawOk(t, "MessageFormData.title")); return this; }
  body(t) { this._f.body = textOf(rawOk(t, "MessageFormData.body")); return this; }
  button1(t) { this._f.button1 = textOf(rawOk(t, "MessageFormData.button1")); return this; }
  button2(t) { this._f.button2 = textOf(rawOk(t, "MessageFormData.button2")); return this; }
  show(player) { return show(this._f, player); }
}

export class ModalFormData {
  constructor() { this._f = { type: "modal", title: "", controls: [] }; }
  title(t) { this._f.title = textOf(rawOk(t, "ModalFormData.title")); return this; }
  divider() { this._f.controls.push({ type: "divider" }); return this; }
  header(t) { this._f.controls.push({ type: "header", text: textOf(rawOk(t, "ModalFormData.header")) }); return this; }
  label(t) { this._f.controls.push({ type: "label", text: textOf(rawOk(t, "ModalFormData.label")) }); return this; }
  submitButton(t) { this._f.submit = textOf(rawOk(t, "ModalFormData.submitButton")); return this; }
  dropdown(label, items, opts) {
    rawOk(label, "dropdown の label");
    if (arguments.length > 3 || typeof opts === "number") throw violation("ui", `dropdown(${fmt(textOf(label))}, items, ${fmt(opts)}) は server-ui 1.x の形。2.0.0 は dropdown(label, items, {defaultValueIndex})`, TypeError);
    check(Array.isArray(items) && items.length > 0, "ui", `dropdown の items は空でない配列: ${fmt(items)}`, TypeError);
    items.forEach((x) => rawOk(x, "dropdown の項目"));
    const o = optsOk(opts, uiKeys("ModalFormDataDropdownOptions", ["defaultValueIndex", "tooltip"]), "dropdown");
    if (o.defaultValueIndex !== undefined) check(Number.isInteger(o.defaultValueIndex) && o.defaultValueIndex >= 0 && o.defaultValueIndex < items.length, "ui", `dropdown の defaultValueIndex ${o.defaultValueIndex}（0〜${items.length - 1}）`);
    this._f.controls.push({ type: "dropdown", label: textOf(label), items: items.map(textOf), defaultValueIndex: o.defaultValueIndex });
    return this;
  }
  slider(label, min, max, opts) {
    rawOk(label, "slider の label");
    if (arguments.length > 4 || typeof opts === "number") throw violation("ui", `slider(${fmt(textOf(label))}, ${min}, ${max}, ${fmt(opts)}, …) は server-ui 1.x の形（step, default）。2.0.0 は slider(label, min, max, {defaultValue, valueStep})`, TypeError);
    check(Number.isFinite(min) && Number.isFinite(max) && min < max, "ui", `slider の範囲 ${min}〜${max}`);
    const o = optsOk(opts, uiKeys("ModalFormDataSliderOptions", ["defaultValue", "tooltip", "valueStep"]), "slider");
    if (o.valueStep !== undefined) check(Number.isFinite(o.valueStep) && o.valueStep > 0, "ui", `slider の valueStep ${o.valueStep}`);
    if (o.defaultValue !== undefined) check(Number.isFinite(o.defaultValue) && o.defaultValue >= min && o.defaultValue <= max, "ui", `slider の defaultValue ${o.defaultValue}（${min}〜${max}）`);
    this._f.controls.push({ type: "slider", label: textOf(label), min, max, defaultValue: o.defaultValue, valueStep: o.valueStep ?? 1 });
    return this;
  }
  textField(label, placeholder, opts) {
    rawOk(label, "textField の label"); rawOk(placeholder, "textField の placeholder");
    if (arguments.length > 3 || typeof opts === "string") throw violation("ui", `textField(label, placeholder, ${fmt(opts)}) は server-ui 1.x の形。2.0.0 は textField(label, placeholder, {defaultValue})`, TypeError);
    const o = optsOk(opts, uiKeys("ModalFormDataTextFieldOptions", ["defaultValue", "tooltip"]), "textField");
    if (o.defaultValue !== undefined) check(typeof o.defaultValue === "string", "ui", `textField の defaultValue は文字列: ${fmt(o.defaultValue)}`);
    this._f.controls.push({ type: "textField", label: textOf(label), placeholder: textOf(placeholder), defaultValue: o.defaultValue });
    return this;
  }
  toggle(label, opts) {
    rawOk(label, "toggle の label");
    if (arguments.length > 2 || typeof opts === "boolean") throw violation("ui", `toggle(${fmt(textOf(label))}, ${fmt(opts)}) は server-ui 1.x の形。2.0.0 は toggle(label, {defaultValue})`, TypeError);
    const o = optsOk(opts, uiKeys("ModalFormDataToggleOptions", ["defaultValue", "tooltip"]), "toggle");
    if (o.defaultValue !== undefined) check(typeof o.defaultValue === "boolean", "ui", `toggle の defaultValue は bool: ${fmt(o.defaultValue)}`);
    this._f.controls.push({ type: "toggle", label: textOf(label), defaultValue: o.defaultValue });
    return this;
  }
  show(player) { return show(this._f, player); }
}

export class UIManager {
  closeAllForms(player) {
    check(player instanceof Player, "ui", "closeAllForms の相手が Player でない", TypeError);
    for (const d of S.forms) if (d.player === player._name && d.answer === undefined) d.closedAt = S.tick;
  }
}
export const uiManager = new UIManager();

S.uiShown = new Map();
S.UI_IMPLEMENTED = { ActionFormData, ActionFormResponse, FormResponse, MessageFormData, MessageFormResponse,
  ModalFormData, ModalFormResponse, UIManager };
S.installGuards(S.UI_IMPLEMENTED, UI);
