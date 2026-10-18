// ===========================================================================
//  惑星の技の雛形（このファイルは読み込まれない。planets/<key>.js にコピーして使う）
//
//  手順:
//   1. このファイルを planets/<key>.js に上書きコピーし、KEY を惑星キーに変える
//      （mercury / venus / mars / jupiter / saturn / uranus / neptune / sol）
//   2. 技の名前・説明・再使用（cd）・星力（cost）は data.js の PLANETS[KEY].moves を見る
//      （出所は tools/astro/astro_data.py。数値を変えるならそちらを直して gen_astro_packs.py）
//   3. 見本は planets/earth.js。説明は tools/astro/planets/_template/README_moves.md
//   4. python3 tools/astro/test_astro.py --planet <key> で確かめる（例外・ダメージ・ID の実在）
//
//  約束:
//   * 使ってよいのは engine.js / fx.js / combat.js / util.js / data.js の export だけ
//     （mobility.js の reflectProjectiles・state.js の読み取りも可）。@minecraft/server を直接触らない
//   * パーティクル ID は DESIGN §4.7、効果音 ID は §4.9、全身モーションは §4.6 の名前だけ
//     （惑星の全身モーションは "<key>.<名前>"。anim_meta.js に無い名前は body() が黙って何もしない）
//   * 時間は tick（20 tick = 1 秒）。技の関数は「技の最中」の長さ（tick）を返す
//     （その間は他の技が出ない。再使用時間は別に data.js の cd が掛かる）
//   * 予約した処理は ctx.at / ctx.every で。system.runTimeout を直接使わない
//     （ctx.at は死亡・退出・解除・次元移動で止まる）
//   * ダメージは hit(ctx, e, 素の値, {...})。同調率・惑星の補正は hit() の中で掛かる（ctx.dmg は表示用）
//   * 多段の技は ctx.once(e, 回数, "タグ") で当たる回数を決める
//   * 1 tick に大量のパーティクルを出さない（予算 約 110 回/tick。超えた分は捨てられる）
// ===========================================================================
import {
  register,          // register(KEY, { skill, dash, air, ult, combo3, burst, passive, meta })
  lunge,             // lunge(ctx, dir, power, up)          前へ突進（power 1.0〜1.8）
  hover,             // hover(ctx, ticks, lift)             宙で止まる（空中技の溜め）
  plunge,            // plunge(ctx, onLand(loc), maxT, speed) 真下へ叩きつけ、着地で onLand
  warp,              // warp(ctx, loc, facing)              瞬間移動（ブロックの中には入らない）
  behind,            // behind(target, d)                   相手の背後の位置
  safeAhead,         // safeAhead(dim, from, dir, maxD)     壁の手前までの位置
  ultOpen,           // ultOpen(ctx, ticks, radius)         必殺の開幕（カットイン・時間停止・無敵）
  projectile,        // projectile(ctx, from, dir, {...})   スクリプト弾（貫通・追尾・ブーメラン）
  zone,              // zone(ctx, loc, {...})               設置範囲（雲・嵐・陣・噴火口）
  meteor,            // meteor(ctx, target, {...})          予告つきの落下物
  chain,             // chain(ctx, first, {...})            連鎖する雷
  dashHits,          // dashHits(ctx, ticks, radius, base, o) 突進中の当たり
  dirTo,             // dirTo(from, to)                     水平の向き
} from "../engine.js";
import {
  P,                 // P(dim, id, loc, {color, size, life, rot, count, speed, spread, dir, var, height, spin, rate, grav, len})
  line, ring, arc, burst, shock, beam, swarm, emblem, slash, afterimage,
  flash, shake, sound, body, white, mix, status, fxScale,
} from "../fx.js";
import {
  hit, enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy, nearestHostile, hostilesNear,
  freeze, pull, push, launch, alliesNear, heal,
} from "../combat.js";
import { add, up, yawRotate, yawDeg, rightOf, chest, rand, effect, onGround } from "../util.js";

const KEY = "template";   // ← 惑星キーに変える

// 惑星の色（data.js の PLANETS[KEY] にもある: ctx.c 発光 / ctx.light 芯 / ctx.deep 影 / ctx.accent 差し色）
const SUB = [1, 1, 1];

register(KEY, {
  // -------------------------------------------------------------------------
  //  惑星技（右クリック）。ctx.kind === "skill"
  // -------------------------------------------------------------------------
  skill(ctx) {
    const { p, dim, c, hot } = ctx;
    body(p, `${KEY}.skill_pose`);            // 惑星の全身モーション（無ければ何もしない）
    sound(dim, "astro.beam_charge", p.location, 1.4, 0.8);
    // 溜め: 0〜6 tick
    ctx.every(0, 4, 2, () => P(dim, "converge", ctx.front(1.0, 1.3), { color: hot, count: 6, spread: 1.2, life: 0.25 }));
    // 放つ: 8 tick 目
    ctx.at(8, () => {
      const f = ctx.liveDir();               // 今の向き（溜めの間に振り向いても追う）
      sound(dim, "astro.beam_fire", p.location, 1.0, 1.0);
      projectile(ctx, ctx.front(1.2, 1.1), f, {
        speed: 1.0, range: 14, radius: 1.0, pierce: Infinity,
        damage: 9, hitOpts: { color: c, kb: 0.8, up: 0.2 },
        trail(d, pos) { P(d, "trail", pos, { color: c, size: 1.2, life: 0.2 }); },
        onEnd(pos) { burst(dim, pos, c, 1.2); },
      });
    });
    return 18;                               // 技の最中（tick）
  },

  // -------------------------------------------------------------------------
  //  機動技（ダッシュ中に右クリック）。ctx.kind === "dash"
  // -------------------------------------------------------------------------
  dash(ctx) {
    const { p, dim, c } = ctx;
    lunge(ctx, ctx.f, 1.4, 0.08);
    effect(p, "resistance", 10, 3);          // 突進中は硬く
    dashHits(ctx, 8, 2.2, 7, { color: c, kb: 1.0, up: 0.3 });
    ctx.every(0, 8, 1, () => afterimage(dim, p.location, c, 0.3));
    return 14;
  },

  // -------------------------------------------------------------------------
  //  空中技（空中で右クリック）。ctx.kind === "air"
  // -------------------------------------------------------------------------
  air(ctx) {
    const { p, dim, c } = ctx;
    hover(ctx, 8, 0.4);
    ctx.at(6, () => plunge(ctx, (l) => {
      shock(dim, l, c, 4, { debris: 8 });
      sound(dim, "astro.impact_heavy", l, 1.0, 1.0);
      for (const e of ctx.foes(4.5, up(l, 0.8))) hit(ctx, e, 10, { color: c, up: 0.6, power: 1.6 });
    }));
    return 26;
  },

  // -------------------------------------------------------------------------
  //  必殺（スニーク＋右クリック、超新星ゲージ 100%）。ctx.kind === "ult"
  //  必ず ultOpen から始める（カットイン・時間停止・無敵）。ゲージは engine が 0 にする
  // -------------------------------------------------------------------------
  ult(ctx) {
    const { p, dim, c } = ctx;
    ultOpen(ctx, 70, 14);
    const centre = ctx.ground(ctx.loc());
    ctx.at(20, () => meteor(ctx, ctx.aim(20), { damage: 14, radius: 4 }));
    ctx.at(50, () => {
      flash(dim, centre, 30, [1, 1, 1], 0.1, 0.5);
      shake(dim, centre, 24, 0.7, 0.6);
      for (const e of ctx.foes(10, up(centre, 1))) hit(ctx, e, 14, { color: c, kb: 1.2, up: 0.6, power: 2.2 });
    });
    return 60;
  },

  // -------------------------------------------------------------------------
  //  三段目の追撃（通常攻撃の 3 段目）。ctx.kind === "combo3"。target は殴った相手
  //  ダメージそのものはバニラの攻撃。ここは追加の当たりと演出だけ（控えめに: 4〜6）
  // -------------------------------------------------------------------------
  combo3(ctx, target) {
    const { dim, c } = ctx;
    for (const e of ctx.cone(4, 50)) hit(ctx, e, 4, { color: c, kb: 0.8 });
    return 10;
  },

  // -------------------------------------------------------------------------
  //  変身の締め（TRANSFORM.planet_burst = 50 tick 目。まだ硬直中）。ダメージは与えない
  // -------------------------------------------------------------------------
  burst(ctx) {
    const { dim, c } = ctx;
    emblem(dim, up(ctx.loc(), 0.05), KEY, { size: 3.6, life: 1.6 });
    ctx.every(0, 4, 3, (i) => P(dim, "ring_flat", up(ctx.loc(), 0.06), { color: i % 2 ? SUB : c, size: 2 + i * 1.5 }));
    return 12;
  },

  // -------------------------------------------------------------------------
  //  パッシブ（変身中ずっと）。effects（data.js の passive.effects）は passives.js が自動で掛ける
  // -------------------------------------------------------------------------
  passive: {
    /** 5 tick ごと。st は作業用（st.n 呼ばれた回数 / st.t 今の tick。変身のたびに空に戻る）。 */
    tick(p, st) { },
    /** 自分の攻撃が当たった（ctx は技の文脈。通常攻撃なら null）。ここで hit() しても onHit は再入しない。 */
    onHit(p, target, dmg, ctx) { },
    /** 攻撃を受けた（attacker は無いこともある）。 */
    onHurt(p, attacker, dmg) { },
    /** 敵を倒した。 */
    onKill(p, victim) { },
    /** 与ダメージの倍率（任意。既定 1）。 */
    dmgMul(p) { return 1; },
  },

  // テスト用の印: ダメージを与えない技を書く（例: 回避だけの機動技）
  meta: { noDamage: [] },
});
