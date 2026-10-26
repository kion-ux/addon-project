// 組み込みの通しテスト（smoke）。アドオンの中身を知らなくても言える「壊れていない」ことだけを見る。
// test_nr.py が main.js のあるときに tests/__builtin_smoke.mjs として走らせる（自己テストでは偽アドオンに対して走る）。
// 失敗の中身は「アドオンの購読者・カスタムコンポーネントの捕まらない例外」と「契約違反」。
import { test, tick, spawn, spawnPlayer, spawnZombie, hit, setTime, setGround, despawn, placeBlock, breakBlock,
  zombieTypes, PARTS, S, mc } from "nr-test";

const NR_ENTITIES = Object.keys(S.DEFS.entities).filter((x) => x.startsWith("nr:")).sort();
const NR_BLOCKS = Object.keys(S.DEFS.blocks).filter((x) => x.startsWith("nr:")).sort();
const STRUCTURES = Object.keys(S.DEFS.structures ?? {}).sort();
const grid = (i, step = 4) => ({ x: (i % 16) * step, y: 64, z: 6 + Math.floor(i / 16) * step });

test("smoke: プレイヤーが入って夕方から夜明けまで（12000 tick を早回し）", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  setTime(11800);
  for (let i = 0; i < 40; i++) {          // 夕方 → 夜 → 明け方を 300 tick ずつ飛ばしながら
    await tick(30);
    S.time = (S.time + 270) % 24000;
  }
  await tick(20);
  if (!p.isValid) throw new Error("プレイヤーが無効になった");
});

test("smoke: BP の nr: エンティティを全部出して 60 tick", async () => {
  spawnPlayer({ x: 0, y: 64, z: 0 });
  NR_ENTITIES.forEach((id, i) => spawn(id, grid(i)));
  await tick(60);
});

test("smoke: 全ゾンビの全部位を一度ずつ殴る", async () => {
  const p = spawnPlayer({ x: 0, y: 64, z: 0 });
  for (const id of zombieTypes()) {
    for (const part of PARTS) {
      const z = spawnZombie(id, { x: 0, y: 64, z: 2.2 });
      await hit(p, z, { part, damage: 6 });
      await tick(2);
      if (z.isValid) despawn(z);
    }
  }
  await tick(5);
});

test("smoke: BP のイベントを全部呼べる（component_groups・set_property・trigger の参照）", async () => {
  spawnPlayer({ x: 0, y: 64, z: 0 });
  let i = 0;
  for (const id of NR_ENTITIES) {
    for (const ev of Object.keys(S.DEFS.entities[id].events ?? {}).sort()) {
      const e = spawn(id, grid(i++ % 64));
      if (e.isValid) e.triggerEvent(ev);
      await tick(1);
      if (e.isValid) despawn(e);
    }
  }
});

test("smoke: nr: ブロックを置いて乗って 40 tick、壊す", async () => {
  setGround(64);
  const p = spawnPlayer({ x: 0.5, y: 64, z: 0.5 });
  for (const [i, id] of NR_BLOCKS.entries()) {
    const pos = { x: 2 + i * 2, y: 64, z: 0 };
    await placeBlock(p, pos, id);
    if (p.isValid) p.teleport({ x: pos.x + 0.5, y: 65, z: 0.5 });   // 乗る（onStepOn）
    await tick(3);
  }
  await tick(40);
  for (const [i] of NR_BLOCKS.entries()) await breakBlock(p, { x: 2 + i * 2, y: 64, z: 0 });
  await tick(2);
});

test("smoke: BP の構造物を全部置ける", async () => {
  const dim = mc.world.getDimension("overworld");
  STRUCTURES.forEach((id, i) => mc.world.structureManager.place(id, dim, { x: i * 64, y: 64, z: 64 }));
  await tick(2);
});
