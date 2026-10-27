// 偽物の自己テスト（正しい使い方は通ること）。scripts/ には selftest/addon/（小さな偽アドオン）が入る。
// test_nr.py が main.js の有無にかかわらず走らせる。ここが落ちたら偽物（test_fakes/*.js）の不具合。
import {
  test, tick, spawn, spawnZombie, spawnPlayer, give, held, hit, shoot, use, press, setInput, interact, breakBlock,
  placeBlock, scriptEvent, command, setBlock, fill, blockAt, setGround, setTime, setLight, answerForm, lastForm,
  partPoint, aim, prop, entities, zombieTypes, used, mark, since, expect, expectViolation, despawn, leave, randomTick,
  DATA, mc, ui, S, PARTS,
} from "nr-test";
import { STATE } from "../scripts/main.js";
import { hitPart } from "../scripts/lib.js";

// ---------------------------------------------------------------------------
//  起動・時間
// ---------------------------------------------------------------------------
test("起動: startup で登録、worldLoad で world を触れる", async () => {
  expect(STATE.startupOk).toBe(true);
  expect(STATE.worldLoaded).toBe(true);
  expect(STATE.early).toBe(0);
  expect(mc.world.getDynamicProperty("nr:settings")).toBe(JSON.stringify({ gore: 100 }));
  expect(S.reg.item.has("nr:test_weapon")).toBe(true);
  expect(S.reg.commands.has("nr:selftest")).toBe(true);
});

test("runInterval は tick ごと、waitTicks は tick で進む", async () => {
  const t0 = STATE.ticks;
  await tick(7);
  expect(STATE.ticks - t0).toBe(7);
  await scriptEvent("nr:wait");
  const at = mc.system.currentTick;
  await tick(4);
  expect(STATE.waited).not.toBe(at + 5);
  await tick(2);
  expect(STATE.waited).toBe(at + 5);
});

test("DATA に scripts/data/*.js が入る", async () => {
  expect(typeof DATA.shapes.SHAPES.test.height).toBe("number");
  expect(DATA.zombie_shapes).toBe(DATA.shapes);
  expect(zombieTypes()).toEqual(["nr:z_test"]);
});

// ---------------------------------------------------------------------------
//  部位・ダメージ・ゴア
// ---------------------------------------------------------------------------
test("部位を狙って殴ると、アドオンの視線レイの判定も同じ部位になる（向きを変えても）", async () => {
  const spots = [[{ x: 0, y: 64, z: 0 }, { x: 0, y: 64, z: 2.2 }], [{ x: 3, y: 64, z: -1 }, { x: 0.5, y: 64, z: 1.5 }],
    [{ x: -2, y: 64, z: 5 }, { x: 0, y: 64, z: 3 }]];
  for (const [pp, zp] of spots) {
    for (const part of PARTS) {
      S.resetWorld();
      const p = spawnPlayer(pp);
      const z = spawnZombie("test", zp);
      const r = await hit(p, z, { part, damage: 2 });
      expect(r.hurt).toBe(true);
      expect(STATE.hits.at(-1).part).toBe(part);
      // 目の位置と視線から、部位の点が本当に視線の上にある
      expect(hitPart(z, p.getHeadLocation(), p.getViewDirection())).toBe(part);
    }
  }
});

test("体力プール・プロパティ・演出（パーティクル・音・アニメ・Molang 変数）", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:w_test");
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  expect(z.getDynamicProperty("nr:hp")).toBe(20);
  await hit(p, z, { part: "head", damage: 12 });
  expect(prop(z, "head")).toBe("severed");
  expect(prop(z, "nr:blood")).toBe(1);
  expect(z.getComponent("minecraft:health").currentValue).toBe(1000);
  expect(z.getDynamicProperty("nr:hp")).toBe(8);
  const u = used();
  expect(u.particles["nr:test_blood"]).toBe(1);
  expect(u.sounds["nr.test.hit"]).toBe(1);
  expect(u.anims["animation.nr.z.test_react"]).toBe(1);
  expect(u.molangVars["nr:test_blood variable.size"]).toBe(1);
  expect(u.props["nr:head=severed"]).toBe(1);
  expect(u.particles["nr:never_used"]).toBe(0);
  expect(u.hurts).toBe(1);
});

test("無敵時間: 10 tick 以内の同じか小さい一撃は来ない（実機と同じ）", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  expect((await hit(p, z, { damage: 3 })).hurt).toBe(true);
  expect((await hit(p, z, { damage: 3 })).hurt).toBe(false);
  expect((await hit(p, z, { damage: 5 })).hurt).toBe(true);   // 大きい一撃は差分だけ通る
  expect(STATE.hits.at(-1).damage).toBe(2);
  await tick(10);
  expect((await hit(p, z, { damage: 1 })).hurt).toBe(true);
});

test("applyImpulse でゾンビが飛んで地面に戻り、applyKnockback でプレイヤーが押される", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  await hit(p, z, { damage: 2 });
  await tick(1);
  expect(z.location.y).toBeGreaterThan(64);
  expect(z.isOnGround).toBe(false);
  expect(p.getVelocity().z).toBeLessThan(0);
  await tick(40);
  expect(z.location.y).toBeCloseTo(64, 3);
  expect(z.isOnGround).toBe(true);
  expect(z.location.z).toBeGreaterThan(3);
});

test("体力が尽きると nr:on_death → nr:dead（damage_sensor で以後の entityHurt は来ない）", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  for (let i = 0; i < 3; i++) { await hit(p, z, { damage: 8 }); await tick(10); }
  expect(STATE.deadEvents).toBeGreaterThan(0);
  expect(prop(z, "state")).toBe("dead");
  expect(z._groups.has("nr:dead")).toBe(true);
  expect(used().events["nr:on_death"]).toBe(1);
  const n = STATE.hits.length;
  expect((await hit(p, z, { damage: 50 })).hurt).toBe(false);
  expect(STATE.hits.length).toBe(n);
  // 寝た姿勢の当たり箱
  const head = partPoint(z, "head");
  expect(head.y).toBeLessThan(z.location.y + 0.5);
});

test("プール以上の一撃はバニラの死（entityDie）。20 tick で消えて entityRemove", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  const d0 = STATE.died;
  await hit(p, z, { damage: 5000 });
  expect(STATE.died).toBe(d0 + 1);
  await tick(21);
  expect(z.isValid).toBe(false);
  expect(STATE.removed).toContain("nr:z_test");
  expect(() => z.location).toThrow(/無効なエンティティ/);
});

test("飛び道具: projectileHitEntity（着弾点）と entityHurt(projectile)", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 0, y: 64, z: 6 });
  const r = await shoot(p, z, { part: "head", projectile: "nr:proj_test", damage: 4 });
  expect(STATE.projHits).toBeGreaterThan(0);
  expect(STATE.projLoc.y).toBeCloseTo(r.point.y, 5);
  expect(STATE.hits.at(-1).cause).toBe("projectile");
  expect(entities("nr:proj_test")).toHaveLength(1);
});

test("MolangVariableMap: 2.3.0 の set 5 種（setVector3 も実機にある）と変数の数え方", async () => {
  const mv = new mc.MolangVariableMap();
  mv.setFloat("variable.size", 1.5);
  mv.setColorRGB("variable.tint", { red: 0.4, green: 0, blue: 0 });
  mv.setColorRGBA("variable.tint2", { red: 0.4, green: 0, blue: 0, alpha: 0.5 });
  mv.setSpeedAndDirection("variable.spray", 4, { x: 0, y: 1, z: 0 });
  mv.setVector3("variable.dir", { x: 0, y: 0, z: 1 });
  const lim0 = [...S.limitations.values()].reduce((a, n) => a + n, 0);
  mc.world.getDimension("overworld").spawnParticle("nr:test_blood", { x: 0, y: 65, z: 0 }, mv);
  const u = used();
  for (const v of ["size", "tint", "tint2", "spray", "dir"]) expect(u.molangVars[`nr:test_blood variable.${v}`]).toBe(1);
  expect([...S.limitations.values()].reduce((a, n) => a + n, 0)).toBe(lim0);
  await expectViolation(() => mv.setVector3("variable.dir", { x: NaN, y: 0, z: 0 }), "molang");
  await expectViolation(() => mv.setColorRGB("variable.tint", { red: 2, green: 0, blue: 0 }), "molang");
});

test("setProperty / triggerEvent の値は次の tick まで getProperty に出ない（d.ts server:L7592）。prop() は最新", async () => {
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  z.setProperty("nr:blood", 2);
  expect(z.getProperty("nr:blood")).toBe(0);
  expect(prop(z, "blood")).toBe(2);
  z.triggerEvent("nr:to_crawl");
  expect(z.getProperty("nr:state")).toBe("normal");
  expect(prop(z, "state")).toBe("crawl");
  await tick(1);
  expect(z.getProperty("nr:blood")).toBe(2);
  expect(z.getProperty("nr:state")).toBe("crawl");
  // 名前空間の無いイベント名は minecraft: とみなす（d.ts）
  const m0 = mark();
  z.triggerEvent("entity_spawned");
  expect(since(m0).events["minecraft:entity_spawned"]).toBe(1);
  // 別の種類（gib）が持つプロパティは、ゾンビで読むと実機どおり undefined（違反にしない）
  expect(z.getProperty("nr:part")).toBeUndefined();
  // 出現時のイベント（minecraft:entity_spawned の set_property）はすぐ見える
  expect(Number.isInteger(z.getProperty("nr:variant"))).toBe(true);
});

test("空中に出したもの・足元が消えたものは落ちる", async () => {
  const z = spawnZombie("test", { x: 0, y: 70, z: 2 }, { yaw: 0 });
  await tick(1);
  expect(z.isOnGround).toBe(false);
  await tick(40);
  expect(z.location.y).toBeCloseTo(64, 3);
  expect(z.isOnGround).toBe(true);
  setBlock({ x: 5, y: 70, z: 5 }, "minecraft:stone");
  const g = spawn("nr:gib", { x: 5.5, y: 71, z: 5.5 });
  await tick(3);
  expect(g.location.y).toBeCloseTo(71, 3);
  setBlock({ x: 5, y: 70, z: 5 }, "minecraft:air");
  await tick(40);
  expect(g.location.y).toBeCloseTo(64, 3);
});

test("プレイヤーが抜ける: before で読める、after は名前だけ、開きかけのフォームは PlayerQuit で reject", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:test_terminal");
  answerForm(0);
  await use(p);
  await tick(1);                       // system.run でフォームが開く（答えは次の tick）
  expect(lastForm().type).toBe("action");
  await leave(p);
  expect(p.isValid).toBe(false);
  expect(STATE.leftBefore.at(-1)).toBe("Runner");
  expect(STATE.leftAfter.at(-1)).toBe("Runner");
  await tick(2);
  expect(STATE.formErrors.at(-1)).toBe("PlayerQuit");
  expect(mc.world.getAllPlayers()).toHaveLength(0);
});

test("randomTick() でブロックの onRandomTick（偽物は自分では起こさない）", async () => {
  const n = STATE.randomTicks;
  setBlock({ x: 3, y: 64, z: 3 }, "nr:test_trap");
  expect(await randomTick({ x: 3, y: 64, z: 3 })).toBe(true);
  expect(await randomTick({ x: 4, y: 64, z: 3 })).toBe(false);
  expect(STATE.randomTicks).toBe(n + 1);
});

test("オプションの辞書は d.ts の interface のキーだけ（正しいものは通る）", async () => {
  const dim = mc.world.getDimension("overworld");
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  dim.getEntities({ location: { x: 0, y: 64, z: 0 }, maxDistance: 8, families: ["nr_zombie"], excludeTypes: ["nr:gib"], closest: 1 });
  z.teleport({ x: 0, y: 64, z: 3 }, { keepVelocity: true, rotation: { x: 0, y: 90 } });
  z.addEffect("slowness", 20, { amplifier: 1, showParticles: false });
  dim.playSound("nr.test.hit", z.location, { volume: 0.5, pitch: 1.2 });
  const it = new mc.ItemStack("nr:w_test");
  it.setLore(["§7改造: §6電撃", "x".repeat(50)]);
  expect(it.getLore()).toHaveLength(2);
  await expectViolation(() => z.teleport({ x: 0, y: 64, z: 3 }, { keepVelocty: true }), "options");
  await expectViolation(() => it.setLore(new Array(21).fill("a")), "item");
});

test("expectViolation で契約違反を確かめられる（記録から消える）", async () => {
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  const v = await expectViolation(() => z.setProperty("nr:head", "gone"), "property");
  expect(v[0].msg).toContain("gone");
  await expectViolation(() => z.triggerEvent("nr:nope"), "event");
  expect(() => mc.world.getDimension("overworld").spawnParticle("nr:test_spark", { x: 0, y: 64, z: 0 })).not.toThrow();
});

// ---------------------------------------------------------------------------
//  アイテム・カスタムコンポーネント・入力
// ---------------------------------------------------------------------------
test("武器のカスタムコンポーネント: onHitEntity（params）・onBeforeDurabilityDamage・onUse", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:w_test");
  const z = spawnZombie("test", { x: 0, y: 64, z: 2.2 });
  await hit(p, z, { part: "torso" });
  expect(STATE.hits.at(-1).damage).toBe(7);                     // minecraft:damage
  expect(STATE.weaponParams).toEqual({ dtype: "slash", weight: "medium" });
  expect(held(p).getComponent("minecraft:durability").damage).toBe(2);
  const n = STATE.used;
  expect(await use(p)).toBe(true);
  expect(STATE.used).toBe(n + 1);
  expect(used().sounds["nr.test.swing"]).toBe(1);
  const stack = give(p, "nr:test_pebble", 3);
  expect(stack.amount).toBe(1);
  expect(held(p).typeId).toBe("nr:w_test");
  p.selectedSlotIndex = 3;
  expect(held(p).typeId).toBe("nr:test_pebble");
});

test("ボタン入力（フィルタ付き）とジャンプ・移動の入力", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  await press(p, "Sneak");
  expect(p.isSneaking).toBe(true);
  expect(STATE.buttons).not.toContain("Sneak:Pressed");     // { buttons: [Jump] } で絞っている
  await press(p, "Sneak", false);
  await press(p, "Jump");
  expect(STATE.buttons.at(-1)).toBe("Jump:Pressed");
  expect(p.inputInfo.getButtonState("Jump")).toBe("Pressed");
  await tick(1);
  expect(p.location.y).toBeGreaterThan(64);
  await press(p, "Jump", false);
  await tick(30);
  expect(p.isOnGround).toBe(true);
  const z0 = p.location.z;
  await setInput(p, { y: 1, sprint: true });
  await tick(10);
  expect(p.location.z - z0).toBeGreaterThan(2.5);
  expect(p.inputInfo.getMovementVector()).toEqual({ x: 0, y: 1 });
  await setInput(p, { y: 0, sprint: false });
});

test("罠ブロック: 踏むと onStepOn（params のダメージ）、minecraft:tick で onTick", async () => {
  const p = spawnPlayer({ x: 5.5, y: 64, z: 5.5 });
  const t0 = STATE.trapTicks;
  setBlock({ x: 0, y: 63, z: 0 }, "nr:test_trap");
  await tick(20);
  expect(STATE.trapTicks - t0).toBe(2);
  p.teleport({ x: 0.5, y: 64, z: 0.5 });
  await tick(1);
  expect(STATE.stepped).toBeGreaterThan(0);
  expect(p.getComponent("minecraft:health").currentValue).toBe(18);
});

test("置く・壊す・触る（イベントとブロックの状態）", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  expect(await placeBlock(p, { x: 2, y: 64, z: 0 }, "nr:test_crate")).toBe(true);
  expect(blockAt({ x: 2, y: 64, z: 0 })).toBe("nr:test_crate");
  const b = mc.world.getDimension("overworld").getBlock({ x: 2, y: 64, z: 0 });
  expect(b.permutation.getState("nr:open")).toBe(false);
  b.setPermutation(b.permutation.withState("nr:open", true));
  expect(b.permutation.getState("nr:open")).toBe(true);
  await expectViolation(() => b.permutation.withState("nr:open", 3), "block");
  expect(await interact(p, { x: 2, y: 64, z: 0 })).toBe(true);
  expect(await breakBlock(p, { x: 2, y: 64, z: 0 })).toBe(true);
  expect(blockAt({ x: 2, y: 64, z: 0 })).toBe("minecraft:air");
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  expect(await interact(p, z)).toBe(true);
});

// ---------------------------------------------------------------------------
//  フォーム
// ---------------------------------------------------------------------------
test("フォーム: ActionForm → ModalForm（2.0 のオプション辞書）の答えが world に入る", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:test_terminal");
  answerForm(0);
  answerForm([50, false, 2, "A"]);
  expect(await use(p)).toBe(false);                 // before で取り消し、system.run で開く
  await tick(3);
  expect(mc.world.getDynamicProperty("nr:gore")).toBe(50);
  expect(STATE.formResults.at(-1)).toEqual({ values: [50, false, 2, "A"] });
  const f = lastForm();
  expect(f.type).toBe("modal");
  expect(f.inputs.map((c) => c.type)).toEqual(["slider", "toggle", "dropdown", "textField"]);
  expect(f.inputs[0].defaultValue).toBe(100);
  expect(S.forms[0].buttons).toEqual(["設定", "確認"]);
});

test("フォーム: 既定値で送る・MessageForm・UserBusy・答えが無ければ閉じた扱い", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 }, "nr:test_terminal");
  answerForm(0); answerForm("defaults");
  await use(p); await tick(3);
  expect(STATE.formResults.at(-1)).toEqual({ values: [100, true, 1, ""] });
  answerForm((f) => f.buttons.indexOf("確認")); answerForm(1);
  await use(p); await tick(3);
  expect(STATE.formResults.at(-1)).toEqual({ message: 1 });
  answerForm({ canceled: true, reason: ui.FormCancelationReason.UserBusy });
  await use(p); await tick(2);
  expect(STATE.formResults.at(-1)).toEqual({ canceled: true, reason: "UserBusy" });
  await use(p); await tick(2);
  expect(STATE.formResults.at(-1)).toEqual({ canceled: true, reason: "UserClosed" });
});

// ---------------------------------------------------------------------------
//  構造物・runJob・コマンド・光
// ---------------------------------------------------------------------------
test("scriptevent → structureManager.place（Rotate90）と runJob", async () => {
  await scriptEvent("nr:build", JSON.stringify({ x: 10, z: 10 }));
  expect(STATE.scriptEvents.at(-1)).toBe("nr:build");
  expect(used().structures["nr:test_hut"]).toBe(1);
  // nr:test_hut は 3x2x3。床が石、(0,1,0) にランプ。Rotate90 で (x, z) → (2 - z, x)
  expect(blockAt({ x: 10, y: 64, z: 10 })).toBe("minecraft:stone");
  expect(blockAt({ x: 12, y: 65, z: 10 })).toBe("nr:test_lamp");
  expect(blockAt({ x: 10, y: 65, z: 10 })).toBe("minecraft:air");
  await tick(25);
  expect(STATE.jobDone).toBeGreaterThan(0);
  expect(blockAt({ x: 39, y: 64, z: 0 })).toBe("nr:test_lamp");
  const s = mc.world.structureManager.get("nr:test_hut");
  expect(s.size).toEqual({ x: 3, y: 2, z: 3 });
  expect(s.getBlockPermutation({ x: 0, y: 1, z: 0 }).type.id).toBe("nr:test_lamp");
});

test("カスタムコマンド（コールバックは read-only、書くのは system.run）", async () => {
  const r = await command("nr:selftest", [7]);
  expect(r.status).toBe(mc.CustomCommandStatus.Success);
  await tick(1);
  expect(mc.world.getDynamicProperty("nr:cmd")).toBe(7);
});

test("時刻と光（空・夜・光るブロック・固定）", async () => {
  const dim = mc.world.getDimension("overworld");
  setTime(6000);
  expect(dim.getLightLevel({ x: 0, y: 64, z: 0 })).toBe(15);
  setTime(18000);
  expect(dim.getLightLevel({ x: 0, y: 64, z: 0 })).toBe(4);
  setBlock({ x: 3, y: 64, z: 0 }, "nr:test_lamp");
  expect(dim.getLightLevel({ x: 0, y: 64, z: 0 })).toBe(12);
  fill({ x: -2, y: 70, z: -2 }, { x: 2, y: 70, z: 2 }, "minecraft:stone");
  expect(dim.getSkyLightLevel({ x: 0, y: 64, z: 0 })).toBe(0);
  setLight(7);
  expect(dim.getLightLevel({ x: 0, y: 64, z: 0 })).toBe(7);
  setGround(null);
  const z = spawnZombie("test", { x: 0, y: 64, z: 0 }, { yaw: 0 });
  z.applyImpulse({ x: 0, y: 0.1, z: 0 });
  await tick(5);
  expect(z.location.y).toBeLessThan(64);
});

test("mark / since と aim・getEntitiesFromViewDirection", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  const z = spawnZombie("test", { x: 4, y: 64, z: 4 });
  aim(p, partPoint(z, "torso"));
  const hits = p.getEntitiesFromViewDirection({ maxDistance: 10 });
  expect(hits[0].entity).toBe(z);
  const m = mark();
  mc.world.getDimension("overworld").spawnParticle("nr:test_spark", { x: 0, y: 64, z: 0 });
  expect(since(m).particles["nr:test_spark"]).toBe(1);
  despawn(z);
  expect(z.isValid).toBe(false);
  const g = spawn("nr:gib", { x: 0, y: 64, z: 0 });
  g.setProperty("nr:part", 3);
  expect(prop(g, "part")).toBe(3);
});

// ---------------------------------------------------------------------------
//  偽物の表面（d.ts と同じ名前だけ・実機に無いメソッドは無い）
// ---------------------------------------------------------------------------
function runtimeNames(api) {
  const names = new Set([...Object.keys(api.classes ?? {}), ...Object.keys(api.enums ?? {}), ...Object.keys(api.consts ?? {})]);
  return [...names].sort();
}
test("偽の @minecraft/server の export は d.ts の実行時の名前と一致する", async () => {
  const want = runtimeNames(S.API);
  const have = Object.keys(mc).sort();
  expect(want.length).toBeGreaterThan(300);
  expect(have.filter((n) => !want.includes(n))).toEqual([]);
  expect(want.filter((n) => !have.includes(n))).toEqual([]);
});
test("偽の @minecraft/server-ui の export は d.ts の実行時の名前と一致する", async () => {
  const want = runtimeNames(S.ENV.apiUi);
  const have = Object.keys(ui).sort();
  expect(have).toEqual(want);
});
test("手書きのクラスに d.ts に無い公開メンバーが無い", async () => {
  expect(S.surfaceExtras(S.IMPLEMENTED)).toEqual([]);
  expect(S.surfaceExtras(S.UI_IMPLEMENTED, S.ENV.apiUi)).toEqual([]);
  expect(mc.Entity.prototype.getAABB).toBeUndefined();          // 2.4.0-beta だけ
  expect(mc.Player.prototype.stopSound).toBeUndefined();         // 同上
  expect(mc.Dimension.prototype.getWeather).toBeUndefined();     // 同上
  expect(mc.WorldAfterEvents).toBeDefined();
  expect(mc.world.afterEvents.playerSwingStart).toBeUndefined(); // ベータ専用のイベント
  expect(mc.world.afterEvents.entityHurt).toBeDefined();
});
test("enum・定数・componentId は d.ts の値", async () => {
  expect(mc.EntityDamageCause.entityAttack).toBe("entityAttack");
  expect(mc.TicksPerSecond).toBe(20);
  expect(mc.TicksPerDay).toBe(24000);
  expect(mc.EntityHealthComponent.componentId).toBe("minecraft:health");
  expect(mc.ItemDurabilityComponent.componentId).toBe("minecraft:durability");
  expect(mc.GameMode.Survival).toBe("Survival");
  expect(Object.isFrozen(mc.Direction)).toBe(true);
});
test("d.ts にあって偽物に無いものは「偽物の限界」と分かる例外", async () => {
  const dim = mc.world.getDimension("overworld");
  expect(() => dim.placeFeature("x", { x: 0, y: 0, z: 0 })).toThrow(/偽物の限界/);
  expect(() => new mc.BiomeType()).toThrow();
  expect(() => mc.BlockStates.get("x")).toThrow(/偽物の限界/);
  expect(S.limitations.get("Dimension.placeFeature")).toBe(1);
  S.limitations.clear();
});
test("無効なエンティティを触ると InvalidEntityError（id・typeId・isValid は読める）", async () => {
  const z = spawnZombie("test", { x: 0, y: 64, z: 2 });
  despawn(z);
  expect(z.isValid).toBe(false);
  expect(z.typeId).toBe("nr:z_test");
  expect(() => z.getProperty("nr:head")).toThrow(mc.InvalidEntityError);
});
