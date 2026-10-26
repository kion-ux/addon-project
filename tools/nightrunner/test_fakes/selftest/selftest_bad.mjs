// 偽物の自己テスト（負の側）。scripts/ には selftest/addon_bad/（わざと壊れた偽アドオン）が入る。
// ここのテストは**全部失敗しなければいけない**。名前の bad[種類] が、失敗の中身として期待するもの:
//   違反の kind（particle / sound / … ）か、error（購読者・system.run の捕まらない例外）、console（console.error）、
//   expect（expect の失敗）、throw（テストが投げた）、stuck（await が終わらない）。
// test_nr.py の自己テストが「失敗したこと」と「期待どおりの理由で失敗したこと」を確かめる。
import { test, tick, spawnZombie, spawnPlayer, scriptEvent, use, expect, expectViolation } from "nr-test";

function setup() {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:test_terminal");
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  return { p, z };
}
const BAD = {
  particle: ["particle", "RP に無いパーティクル"],
  sound: ["sound", "sound_definitions に無い効果音"],
  anim: ["anim", "RP に無いアニメ"],
  anim_opts: ["anim", "controller / stopExpression / nextState の無い playAnimation"],
  entity: ["entity", "BP に無いエンティティを出す"],
  item: ["item", "BP に無いアイテム"],
  block: ["block", "BP に無いブロック"],
  structure: ["structure", "無い構造物を置く"],
  event: ["event", "BP に無いイベント"],
  prop_enum: ["property", "enum に無い値"],
  prop_range: ["property", "int の範囲の外"],
  prop_name: ["property", "無いプロパティ"],
  vector: ["vector", "NaN の applyImpulse"],
  molang: ["molang", "variable. の無い Molang 変数名"],
  player_impulse: ["player", "プレイヤーへの applyImpulse"],
  player_remove: ["player", "player.remove()"],
  knockback_v1: ["api", "1.x の形の applyKnockback"],
  dynprop_stack: ["dynprop", "重ねられるアイテムへの動的プロパティ"],
  ui_toggle_v1: ["ui", "server-ui 1.x の toggle(label, true)"],
  ui_slider_v1: ["ui", "server-ui 1.x の slider(…, step, default)"],
  ui_layout: ["ui", "ボタンの前の label"],
  budget: ["budget", "1 tick にパーティクル 320 個"],
  global: ["global", "setTimeout（ゲームに無い）"],
  dimension_query: ["query", "location の無い maxDistance"],
};
for (const [c, [kind, what]] of Object.entries(BAD)) {
  test(`bad[${kind}] ${c}: ${what}（アドオンが握りつぶしても失敗）`, async () => {
    setup();
    await scriptEvent("nr:bad", c);
    await tick(1);
  });
}

for (const [mode, what] of [["write", "applyDamage"], ["form", "フォームの show"], ["subscribe", "subscribe"]]) {
  test(`bad[readonly] before イベントの中で ${what}`, async () => {
    const { p } = setup();
    await scriptEvent("nr:mode", mode);
    await use(p);
    await tick(2);
    await scriptEvent("nr:mode", "");
  });
}

test("bad[error] 購読者の中の捕まらない例外", async () => { setup(); await scriptEvent("nr:throw"); });
test("bad[error] system.run の中の捕まらない例外", async () => { setup(); await scriptEvent("nr:run_throw"); await tick(1); });
test("bad[console] アドオンの console.error", async () => { setup(); await scriptEvent("nr:console"); });
test("bad[expect] expect の失敗", async () => { expect(1 + 1).toBe(3); });
test("bad[expect] 起きなかった違反を expectViolation で待つ", async () => { await expectViolation(() => {}, "particle"); });
test("bad[property] テストのコードが直接した違反（expectViolation なし）", async () => {
  const { z } = setup();
  try { z.setProperty("nr:head", "nope"); } catch { /* 握りつぶしても記録は残る */ }
});
test("bad[throw] テストが投げる", async () => { throw new Error("わざと"); });
test("bad[stuck] tick を進めずに来ないものを待つ", async () => { await new Promise(() => {}); });
