// 戦闘: data/weapons.js の全部の武器を一回ずつ使う通しテスト — 近接は殴る、銃は撃つ、弓は引いて放つ、
// クロスボウは撃つ、投げ物は投げる。どれもゾンビへの一撃は applyHit（武器の dtype・source）を通り、演出の ID は
// 登録簿のもの（違反なし）。弾・矢は持ち物から減る。
import { test, tick, expect, hit, use, startUse, releaseUse, give, aim, partPoint } from "nr-test";
import { arena, rec, hitsOn, stack, count } from "./combat_util.js";
import { WEAPONS } from "../scripts/data/weapons.js";

/** 投げ物ごとの確かめ方（ダメージの無い物は範囲・誘いの知らせ）。 */
const THROWN = {
  throwing_knife: { src: "projectile" }, throwing_star: { src: "projectile" },
  molotov: { dtype: "fire" }, pipe_bomb: { dtype: "blast" }, firecracker: { bus: "lure" }, uv_flare: { bus: "uv" },
};

for (const w of WEAPONS) {
  test(`全武器: ${w.ja}（${w.key}・${w.kind}）`, async () => {
    const far = w.kind === "melee" ? 2.6 : w.kind === "throwable" ? 3.8 : 5.5;
    const { p, z } = await arena({ item: w.stack > 1 ? stack(w.id, Math.min(4, w.stack)) : w.id, at: { x: 0.5, y: 64, z: far }, hp: 900 });
    if (w.ammo) give(p, stack(w.ammo, 10), 1);
    const ammo0 = w.ammo ? count(p, w.ammo) : 0;
    aim(p, partPoint(z, "torso"));
    if (w.kind === "melee") {
      await hit(p, z, { part: "torso" });
      await tick(2);
      const r = hitsOn(z)[0];
      expect(r).toBeDefined();
      expect(r.source).toBe("melee");
      expect([w.dtype, w.alt_dtype]).toContain(r.dtype);
      expect(r.hit.weapon.id).toBe(w.id);
      expect(rec.stamina.some((s) => s.reason === "melee" && s.amount === w.stamina_cost)).toBe(true);
      return;
    }
    if (w.kind === "gun") {
      // 散らばり（spread）で外れることがあるので 3 発まで
      for (let i = 0; i < 3 && !hitsOn(z).length; i++) { await use(p); await tick(Math.ceil(20 / w.attack_speed) + 1); }
      const hs = hitsOn(z);
      expect(hs.length).toBeGreaterThan(0);
      expect(hs[0].source).toBe("hitscan");
      expect(hs[0].hit.weapon.id).toBe(w.id);
      expect(rec.noise.some((n) => n.source === "gun")).toBe(true);
      return;
    }
    if (w.kind === "bow") {
      await startUse(p);
      await tick(w.charge_ticks);
      await releaseUse(p, undefined, w.charge_ticks);
      await tick(10);
      expect(count(p, w.ammo)).toBe(ammo0 - 1);
      expect(hitsOn(z)[0]?.source).toBe("projectile");
      return;
    }
    if (w.kind === "crossbow") {
      await use(p);                                          // 初めて見たクロスボウは装填済み
      await tick(10);
      expect(hitsOn(z)[0]?.source).toBe("projectile");
      expect(hitsOn(z)[0].hit.weapon.id).toBe(w.id);
      return;
    }
    // 投げ物: ゾンビの足元か胴へ
    const how = THROWN[/** @type {keyof typeof THROWN} */ (String(w.projectile).replace("nr:proj_", ""))] ?? {};
    if (!how.src) aim(p, { x: 0.5, y: 64.1, z: far - 0.6 });
    await use(p);
    await tick(how.dtype === "blast" ? (w.special.fuse_ticks ?? 50) + 10 : 40);
    expect(count(p, w.id)).toBe(Math.min(4, w.stack) - 1);
    if (how.src) expect(hitsOn(z)[0]?.source).toBe(how.src);
    if (how.dtype) expect(hitsOn(z, (r) => r.dtype === how.dtype).length).toBeGreaterThan(0);
    if (how.bus === "lure") expect(rec.lure.length).toBe(1);
    if (how.bus === "uv") expect(rec.uv.length).toBe(1);
  });
}
