// 起動して数秒動かし、例外が出ないこと・描画できることを確かめる。
export default async function (t) {
  const g = await t.open({ query: 'seed=1' });
  let s = await g.snapshot();
  t.eq(s.state, 'playing', 'test モードではすぐ playing になる');
  t.ok(s.player && Number.isFinite(s.player.y), 'プレイヤーの位置がある');
  s = await g.step(120);
  t.ok(s.player.y > -5, `地面を突き抜けて落ちない (y=${s.player.y})`);
  // 前へ歩く
  const before = s.player;
  s = await g.hold({ move: { x: 0, y: 1 } }, 60);
  const moved = Math.hypot(s.player.x - before.x, s.player.z - before.z);
  t.ok(moved > 1.5, `スティックを倒すと動く (${moved.toFixed(2)}m)`);
  await g.clearInject();
  await g.screenshot('smoke-landscape');
  s = await g.snapshot();
  t.ok(s.stats.drawCalls > 0, `描画している (draw calls ${s.stats.drawCalls})`);
  t.log(`draw calls ${s.stats.drawCalls}, triangles ${s.stats.triangles}`);
}
