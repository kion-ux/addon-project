// ===========================================================================
//  技の実行エンジン（惑星の技はここと fx.js・combat.js の関数だけで書く）
//
//  * 入力の状況（スニーク／空中／ダッシュ）から 惑星技・機動技・空中技・必殺・バリア を選ぶ
//  * 再使用時間（同調率で短縮）・星力の消費・超新星ゲージ・「技の最中」ロック
//  * 技は ctx.at(tick, fn) で時間割を組む。死亡・退出・解除・次元移動で以降は走らない
//  * 共通の動き（突進・ホバー・急降下・ワープ・背後・投射物・設置範囲・隕石・連鎖雷）
//  * 惑星の技がまだ無い形態のための汎用の技一式（genericMoves）
//
//  惑星の登録:  register("earth", { skill(ctx){…; return 何tick;}, dash, air, ult, combo3(ctx, target),
//                                   burst(ctx), passive: { tick, onHit, onHurt, onKill, dmgMul } })
//  詳しくは planets/_template.js と tools/astro/planets/_template/README_moves.md。
// ===========================================================================
import { system } from "@minecraft/server";
import { COMMON, PLANETS, MOVE_LABEL } from "./data.js";
import {
  S, isBusy, setBusy, cdLeft, setCd, cdMul, energy, addEnergy, novaFull, lockNova, level,
  addRecord,
} from "./state.js";
import {
  P, body, bodyStop, cutin, flash, sound, white, mix, shake, line, ring, arc, burst, shock, beam,
  emblem, announce, glyph, afterimage, slash, fxScale,
} from "./fx.js";
import {
  hit, enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy, isTarget, setNova, damageMul,
  freeze, launch, push, pull, isHostile, hostilesNear, nearestHostile,
} from "./combat.js";
import { markAirborne, barrier, reflectProjectiles } from "./mobility.js";
import { shoot } from "./projectiles.js";
import { zone as placeZone } from "./zones.js";
import {
  valid, alive, knock, flatDir, viewDir, effect, add, now, dist, norm, sub, rightOf, chest as chestOf,
  blocked, onGround, groundY, report, rand, yawRotate, yawDeg, dirTo, clamp, removeEffect, lerp3,
  finite, supported, clearLine,
} from "./util.js";

// ---------------------------------------------------------------------------
//  惑星の登録
// ---------------------------------------------------------------------------
/** 惑星キー → 技の実装（register で入る）。 */
export const MOVES = {};

/**
 * 惑星の技を登録する（planets/<key>.js の一番下で 1 回だけ呼ぶ）。
 * 足りない技（skill/dash/air/ult/combo3/burst）は汎用の技で補う。
 * @param {string} key  惑星キー（"earth" など）
 * @param {object} impl { skill, dash, air, ult, combo3, burst, passive, meta }
 *   meta.noDamage: ["dash"] のように、ダメージを与えない技を書く（テストがダメージを求めない）
 */
export function register(key, impl) {
  if (!PLANETS[key]) { report("register", new Error(`unknown planet ${key}`)); return; }
  MOVES[key] = impl ?? {};
}

/** key の kind の実装（無ければ汎用）。 */
export function moveImpl(key, kind) {
  const m = MOVES[key];
  const fn = m?.[kind];
  if (typeof fn === "function") return fn;
  return genericMoves(key)[kind];
}

// ---------------------------------------------------------------------------
//  技の選択と実行
// ---------------------------------------------------------------------------
/** 状況から技の種類を選ぶ: "ult" | "barrier" | "air" | "dash" | "skill"。 */
export function chooseKind(p) {
  let sneak = false, ground = true, water = false, sprint = false;
  try { sneak = !!p.isSneaking; ground = !!p.isOnGround; water = !!p.isInWater; sprint = !!p.isSprinting; } catch (_) { }
  if (sneak) {
    // ゲージが満タンでも必殺が再使用待ちならバリア（バリアが使えなくならないように）
    const key = S(p).form;
    return novaFull(p) && !(key && cdLeft(p, key, "ult") > 0) ? "ult" : "barrier";
  }
  if (!ground && !water) return "air";
  if (sprint) return "dash";
  return "skill";
}

const denied = new Map();   // playerId -> 最後に断りの音を鳴らした tick

/** 出せない時の合図（itemUseOn が押しっぱなしで何度も来ても音は 1 秒に 1 回）。 */
function deny(p, text, pitch) {
  announce(p, text, 16);
  if ((denied.get(p.id) ?? -99) > now() - 20) return;
  denied.set(p.id, now());
  sound(p.dimension, "astro.alert", p.location, pitch, 0.35);
}

/**
 * 技を出す。出せたら true。
 * @param {Player} p
 * @param {"skill"|"dash"|"air"|"ult"|"barrier"} kind
 * @param {object} [extra] ctx.extra に入る（force: true で「技の最中」でも出す）
 */
export function perform(p, kind, extra = {}) {
  if (!alive(p)) return false;
  const st = S(p);
  const key = st.form;
  if (!key || st.seq) return false;
  if (kind === "barrier") return barrier(p);
  if (isBusy(p) && !extra.force) return false;
  const pl = PLANETS[key];
  const mv = pl.moves[kind];
  if (!mv) return false;
  const left = cdLeft(p, key, kind);
  if (left > 0) {
    if (kind === "ult") return barrier(p);
    deny(p, `§r${glyph(["move", key, kind, "wait"], "")}§r §7${MOVE_LABEL[kind]}「${mv.ja}」 §cあと ${(left / 20).toFixed(1)} 秒`, 0.7);
    return false;
  }
  const cost = mv.cost ?? 0;
  if (cost > 0 && energy(p) < cost) {
    deny(p, `§r${glyph("icon.energy", "")}§r §c星力が足りない（${MOVE_LABEL[kind]} ${cost}）`, 0.6);
    return false;
  }
  if (kind === "ult") {
    if (!novaFull(p)) return barrier(p);
    setNova(p, 0);
  }
  const impl = moveImpl(key, kind);
  if (!impl) return false;
  const ctx = makeCtx(p, key, kind, extra);
  let dur = 10;
  try { dur = impl(ctx) ?? 10; } catch (e) { report(`${key}.${kind}`, e); }
  dur = clamp(Math.round(Number(dur) || 10), 1, 200);
  setBusy(p, dur);
  if (kind === "ult") lockNova(p, dur + 10);
  setCd(p, key, kind, Math.round(mv.cd * cdMul(p, key)));
  if (cost > 0) addEnergy(p, -cost);
  st.revertHold = 0;
  addRecord(p, "moves", 1, key);
  if (kind === "ult") addRecord(p, "ults", 1, key);
  return true;
}

// ---------------------------------------------------------------------------
//  技の文脈（ctx）
// ---------------------------------------------------------------------------
/**
 * 技の文脈を作る（engine・combo・transform が使う。planets からは受け取るだけ）。
 *
 * ctx のメンバー:
 *   p プレイヤー / key 惑星キー / planet PLANETS[key] / kind "skill"|"dash"|"air"|"ult"|"combo3"|"burst" /
 *   extra / dim 次元 / c 発光色 / light 芯の色 / deep 影の色 / accent 差し色 / plate 主装甲 / plate2 副装甲 /
 *   hot 白寄りの発光色 / tc テキスト色コード / f 水平前方（開始時）/ r 右方向 / v 視線（開始時）/
 *   start 開始位置 / level 同調率 Lv
 *   at(t, fn)            t tick 後に fn（t <= 0 なら今すぐ）。死亡・退出・解除・次元移動で止まる
 *   every(t0, n, step, fn(i))  t0 から step tick おきに n 回
 *   once(e, max = 1, tag = "")  同じ技で同じ相手に当てる回数を制限（tag ごとに別に数える）
 *   alive()              技を続けてよいか
 *   loc() chest() head() 今の足元・胸・頭 / front(d = 1.6, y = 1.0) 開始時の前方 d m・高さ y
 *   local(fwd, right = 0, upY = 0)  今の足元から（開始時の向きで）前・右・上へずらした点
 *   liveDir() 今の水平前方 / liveView() 今の視線
 *   dmg(base)            同調率・惑星・パッシブの補正を掛けた値（hit() は自動で掛けるので表示・計算用）
 *   hit(e, base, o)      = combat.hit(ctx, e, base, o)
 *   foes(radius, at = chest())  周りの攻撃してよい相手（範囲技用）/ cone(range, deg, from?, dir?) 扇形
 *   hostiles(radius, at = chest())  周りの敵対的な相手だけ（標的を選ぶ時。村人・動物・中立の mob を選ばない）
 *   nearest(radius, deg = 180, los = true)  一番近い敵対的な相手（deg で視線の扇に、los で頭から見通せる相手に絞る）
 *   aimed(maxD = 16)     視線の先の相手（意図して狙った相手。敵対的でなくてもよい）
 *   pick(radius, deg = 40)  aimed → nearest の順に一人選ぶ
 *   aim(maxD = 20)       狙っている地点（見ている敵の足元 → 見ているブロックの上 → 前方の地面）
 *   ground(loc)          loc の真下の地面の高さに合わせた点
 */
export function makeCtx(p, key, kind, extra = {}) {
  const pl = PLANETS[key];
  const st = S(p);
  const gen = st.gen;
  const dim = p.dimension;
  const dimId = dim.id;
  const f = flatDir(p);
  const ctx = {
    p, key, planet: pl, kind, extra, dim,
    c: pl.color, light: pl.light, deep: pl.deep, accent: pl.accent, plate: pl.plate, plate2: pl.plate2,
    hot: white(pl.color, 0.45), tc: pl.tc,
    f, r: rightOf(f), v: viewDir(p), start: { ...p.location }, level: level(p, key),
    struck: new Map(), gain: { nova: 0, xp: 0 }, novaCap: kind === "combo3" ? 6 : 14, xpCap: 12,
    alive() {
      if (!valid(p) || !alive(p)) return false;
      if (S(p).gen !== gen) return false;
      try { return p.dimension.id === dimId; } catch (_) { return false; }
    },
    at(t, fn) {
      const go = () => {
        if (!ctx.alive()) return;
        try { fn(); } catch (e) { report(`${key}.${kind}@${t}`, e); }
      };
      if (!(t > 0)) go(); else system.runTimeout(go, Math.round(t));
    },
    every(t0, n, step, fn) {
      for (let i = 0; i < n; i++) ctx.at(t0 + i * step, () => fn(i));
    },
    once(e, max = 1, tag = "") {
      const k = `${tag}|${e.id}`;
      const c = ctx.struck.get(k) ?? 0;
      if (c >= max) return false;
      ctx.struck.set(k, c + 1);
      return true;
    },
    loc() { return { ...p.location }; },
    chest() { const l = p.location; return { x: l.x, y: l.y + 1.0, z: l.z }; },
    head() { const l = p.location; return { x: l.x, y: l.y + 1.62, z: l.z }; },
    front(d = 1.6, y = 1.0) {
      const l = p.location;
      return { x: l.x + ctx.f.x * d, y: l.y + y, z: l.z + ctx.f.z * d };
    },
    local(fwd, right = 0, upY = 0) {
      const l = p.location;
      return { x: l.x + ctx.f.x * fwd + ctx.r.x * right, y: l.y + upY, z: l.z + ctx.f.z * fwd + ctx.r.z * right };
    },
    liveDir() { return flatDir(p); },
    liveView() { return viewDir(p); },
    dmg(base) { return base * damageMul(p, key); },
    hit(e, base, o) { return hit(ctx, e, base, o); },
    foes(radius, at) { return enemiesNear(ctx, at ?? ctx.chest(), radius); },
    hostiles(radius, at) { return hostilesNear(ctx, at ?? ctx.chest(), radius); },
    cone(range, deg, from, dir) { return enemiesInCone(ctx, from ?? ctx.chest(), dir ?? ctx.liveView(), range, deg); },
    nearest(radius, deg = 180, los = true) {
      return nearestHostile(ctx, ctx.chest(), radius, ctx.liveView(), deg, { los: los ? ctx.head() : null });
    },
    aimed(maxD = 16) { return aimedEntity(p, maxD); },
    pick(radius, deg = 40) { return ctx.aimed(radius) ?? ctx.nearest(radius, deg); },
    aim(maxD = 20) { return aimPoint(p, maxD); },
    ground(loc) { return onGround(ctx.dim, loc); },
  };
  return ctx;
}

/** p の視線の先の、攻撃してよい相手（ブロックに遮られたら無し）。 */
export function aimedEntity(p, maxD = 16) {
  try {
    for (const h of p.getEntitiesFromViewDirection?.({ maxDistance: maxD }) ?? []) {
      if (h?.entity && isTarget(p, h.entity)) return h.entity;
    }
  } catch (_) { }
  return undefined;
}

/** p が狙っている地点（地面の高さ）。 */
export function aimPoint(p, maxD = 20) {
  const dim = p.dimension;
  try {
    const hits = p.getEntitiesFromViewDirection?.({ maxDistance: maxD }) ?? [];
    for (const h of hits) {
      if (h?.entity && isTarget(p, h.entity)) return onGround(dim, h.entity.location);
    }
  } catch (_) { }
  try {
    const b = p.getBlockFromViewDirection?.({ maxDistance: maxD });
    if (b?.block) {
      const l = b.block.location;
      const q = { x: l.x + 0.5, y: l.y + 1, z: l.z + 0.5 };
      if (finite(q)) return onGround(dim, q, 4);
    }
  } catch (_) { }
  const f = flatDir(p);
  const d = Math.min(10, maxD);
  const l = p.location;
  return onGround(dim, { x: l.x + f.x * d, y: l.y + 1, z: l.z + f.z * d }, 12);
}

// ---------------------------------------------------------------------------
//  共通の動き
// ---------------------------------------------------------------------------
/** 前へ突進。power は水平速度（block/tick 相当、1.0〜1.8 くらい）。 */
export function lunge(ctx, dir, power, upv = 0.12) {
  knock(ctx.p, dir.x, dir.z, power, upv);
  markAirborne(ctx.p);
}

/** 宙に浮いて静止気味にする（空中技の溜め）。 */
export function hover(ctx, ticks, lift = 0.35) {
  knock(ctx.p, 0, 0, 0, lift);
  effect(ctx.p, "slow_falling", ticks, 0);
  markAirborne(ctx.p);
}

/**
 * 真下へ叩きつけ、着地した瞬間に onLand(loc)。着地しなければ maxT tick で強制。
 * 落下中は惑星色の軌跡が出る。
 */
export function plunge(ctx, onLand, maxT = 34, speed = 2.6) {
  const p = ctx.p;
  removeEffect(p, "slow_falling");
  removeEffect(p, "levitation");
  knock(p, 0, 0, 0, -speed);
  markAirborne(p);
  let landed = false;
  for (let t = 1; t <= maxT; t++) {
    ctx.at(t, () => {
      if (landed) return;
      let g = false;
      try { g = !!p.isOnGround; } catch (_) { }
      if (g || t === maxT) {
        landed = true;
        let at = { ...p.location };
        if (!g) {
          // 着地しないまま時間切れ: すぐ下に地面があればそこで弾ける。無ければ空中に陣や噴火口を置かない
          const gy = groundY(ctx.dim, at, 6, 0);
          if (!blocked(ctx.dim, { x: at.x, y: gy - 1, z: at.z })) return;
          at = { ...at, y: gy };
        }
        onLand(at);
      } else {
        if (t % 3 === 0) knock(p, 0, 0, 0, -speed);
        const l = p.location;
        P(ctx.dim, "trail", { x: l.x, y: l.y + 1.0, z: l.z }, { color: ctx.c, size: 1.4, life: 0.25 });
        if (t % 2 === 0) {
          P(ctx.dim, "speedline", { x: l.x, y: l.y + 1.6, z: l.z }, { color: ctx.hot, count: 3, dir: { x: 0, y: 1, z: 0 }, speed: 10, spread: 0.6 });
        }
      }
    });
  }
}

/**
 * その場所に立てるか（体の下半分と上半分のマスが空いているか）。足元は y + 0.5 で調べるので、
 * ハーフブロック・土の道・耕地・ソウルサンドの上に立っている時に足元のブロックを壁とみなさない。
 */
export function standable(dim, loc) {
  return !blocked(dim, { x: loc.x, y: loc.y + 0.5, z: loc.z }) && !blocked(dim, { x: loc.x, y: loc.y + 1.5, z: loc.z });
}

/** 壁にめり込まない範囲で from から dir へ最大 maxD 進んだ地点。 */
export function safeAhead(dim, from, dir, maxD) {
  let last = { ...from };
  for (let d = 0.5; d <= maxD; d += 0.5) {
    const q = { x: from.x + dir.x * d, y: from.y, z: from.z + dir.z * d };
    if (!standable(dim, q)) {
      // 1 段の段差なら乗り越える（段の上面へ）
      const top = Math.floor(q.y + 0.5) + 1;
      const q2 = { ...q, y: top };
      if (top - from.y <= 1.25 && standable(dim, q2)) { last = q2; from = { ...from, y: top }; continue; }
      break;
    }
    last = q;
  }
  return last;
}

/**
 * 瞬間移動。立てない場所（ブロックの中）なら少し上・手前を探し、無理なら移動しない。
 * @param pOrCtx プレイヤーか ctx / loc 行き先 / facing 向く点（任意）
 * @param o      ground: true（か深さ）で、足元の下 3 ブロック（か深さ）以内に地面の無い場所（虚空・崖の外）へは跳ばない
 * @returns 移動できたら true
 */
export function warp(pOrCtx, loc, facing, o = {}) {
  const p = pOrCtx?.p ?? pOrCtx;
  if (!valid(p) || !loc || !finite(loc)) return false;
  const dim = p.dimension;
  const depth = o.ground === true ? 3 : Number(o.ground) || 0;
  const ok = (c) => standable(dim, c) && (!depth || supported(dim, c, depth));
  let q = null;
  for (const dy of [0, 1, 2, -1]) {
    const c = { x: loc.x, y: loc.y + dy, z: loc.z };
    if (ok(c)) { q = c; break; }
  }
  if (!q) {
    // 手前へ戻りながら探す
    const from = p.location;
    const d = dirTo(from, loc);
    const D = Math.hypot(loc.x - from.x, loc.z - from.z);
    q = safeAhead(dim, { ...from }, d, D);
    if (dist(q, from) < 0.3) return false;
    if (depth && !supported(dim, q, depth)) return false;
  }
  try {
    const opts = { dimension: dim, keepVelocity: false };
    if (facing && finite(facing)) opts.facingLocation = facing;
    p.teleport(q, opts);
    markAirborne(p);
    return true;
  } catch (_) { return false; }
}

/** 標的の背後（標的から見て後ろ）に立つ位置。 */
export function behind(target, d = 1.4) {
  let fd = { x: 0, y: 0, z: 1 };
  try { fd = target.getViewDirection(); } catch (_) { }
  const l = Math.hypot(fd.x, fd.z) || 1;
  const t = target.location;
  return { x: t.x - fd.x / l * d, y: t.y, z: t.z - fd.z / l * d };
}

/** 突進の当たり: ticks の間、毎 tick 前方 radius m の敵に 1 回ずつ hit。 */
export function dashHits(ctx, ticks, radius, base, o = {}) {
  ctx.every(0, ticks, 1, () => {
    for (const e of ctx.foes(radius, ctx.local(0.9, 0, 1.0))) {
      if (ctx.once(e, 1, o.tag ?? "dash")) hit(ctx, e, base, { dir: ctx.liveDir(), ...o });
    }
  });
}

/**
 * 必殺技の開幕: カットイン・フラッシュ・無敵・時間停止（周りの敵の足止め）・紋章の陣。
 * @param ticks 無敵の長さ（技の長さに合わせる）/ freezeRadius 時間停止の半径
 */
export function ultOpen(ctx, ticks = 80, freezeRadius = 12) {
  const { p, dim, planet: pl } = ctx;
  const mv = pl.moves.ult;
  cutin(p, pl, mv.ja, mv.en);
  flash(dim, p.location, 26, white(ctx.c, 0.4), 0.06, 0.3);
  sound(dim, "astro.cutin", p.location, 1.0, 1.4);
  sound(dim, "astro.time_stop", p.location, 1.0, 1.0);
  effect(p, "resistance", ticks, 4);
  for (const e of enemiesNear(ctx, p.location, freezeRadius)) {
    effect(e, "slowness", Math.min(ticks, 60), 9);
    effect(e, "weakness", Math.min(ticks, 60), 2);
    P(dim, "hex", chestOf(e), { color: white(ctx.c, 0.3), size: 1.2, life: 0.5 });
  }
  body(p, "ult_rise");
  const g = { ...p.location, y: p.location.y + 0.05 };
  emblem(dim, g, pl, { size: 3.2, life: 2.4, spin: 50 });
  P(dim, "circle", g, { color: ctx.c, size: 4.6, life: 2.2, spin: -30 });
  P(dim, "lens", ctx.chest(), { color: white(ctx.c, 0.5), size: 1.4, life: 0.5 });
  P(dim, "converge", ctx.chest(), { color: ctx.hot, count: 26, spread: 3.2, life: 0.6, size: 1.2 });
  markAirborne(p);
}

// ---------------------------------------------------------------------------
//  投射物・設置範囲・隕石・連鎖雷
// ---------------------------------------------------------------------------
/** スクリプト弾。引数は projectiles.js の shoot() を見ること。 */
export function projectile(ctx, from, dir, o = {}) { return shoot(ctx, from, dir, o); }

/** 設置範囲。引数は zones.js の zone() を見ること。 */
export function zone(ctx, loc, o = {}) { return placeZone(ctx, loc, o); }

/**
 * 隕石（落下物）: 予告の陣 → 空から落ちる → 着弾の爆発とダメージ。
 * @param target 落とす地点 {x,y,z} かエンティティ（地面に合わせる）
 * @param o delay 予告 tick（16）/ fall 落下 tick（8）/ height 高さ（14）/ from 落ちてくる向きのずれ {x,z}（既定 後ろ上）/
 *          radius 爆発の半径（3.5）/ damage 素のダメージ（12）/ hit hit() の追加オプション /
 *          color 色（ctx.c）/ size 大きさ（2）/ particle 落下中のパーティクル（"meteor"）/ warn false で予告なし /
 *          onImpact(loc) 着弾の追加演出 / quiet true で既定の着弾演出なし
 * @returns 着弾までの tick
 */
export function meteor(ctx, target, o = {}) {
  const dim = ctx.dim;
  const raw = target?.location ?? target;
  if (!raw || !finite(raw)) return 0;
  const g = onGround(dim, raw);
  const delay = o.delay ?? 16, fall = Math.max(1, o.fall ?? 8), h = o.height ?? 14;
  const c = o.color ?? ctx.c;
  const off = o.from ?? { x: -ctx.f.x * 0.45, z: -ctx.f.z * 0.45 };
  const top = { x: g.x + off.x * h, y: g.y + h, z: g.z + off.z * h };
  const R = o.radius ?? 3.5;
  if (o.warn !== false) {
    for (let t = 0; t < delay; t += 4) {
      ctx.at(t, () => {
        P(dim, "warning", { ...g, y: g.y + 0.06 }, { color: [1, 0.25, 0.2], size: R / 1.2, life: 0.25 });
        if (t === 0) P(dim, "circle", { ...g, y: g.y + 0.05 }, { color: c, size: R / 1.1, life: (delay + fall) / 20, spin: 90 });
      });
    }
  }
  // astro.meteor の着弾音は鳴らしてから 1.15 秒（23 tick）後
  ctx.at(Math.max(0, delay + fall - 23), () => sound(dim, "astro.meteor", top, 1.0, 1.2));
  const dir = norm(sub(g, top));
  for (let i = 0; i <= fall; i++) {
    ctx.at(delay + i, () => {
      const q = lerp3(top, g, i / fall);
      P(dim, o.particle ?? "meteor", q, { color: c, dir, size: o.size ?? 2, life: 0.12 });
      P(dim, "trail", q, { color: white(c, 0.3), size: (o.size ?? 2) * 0.8, life: 0.3 });
      if (i % 2 === 0) P(dim, "ember", q, { color: c, count: 3, speed: 2, size: 0.6 });
    });
  }
  ctx.at(delay + fall, () => {
    if (!o.quiet) {
      P(dim, "flare", { ...g, y: g.y + 0.8 }, { color: white(c, 0.5), size: R * 0.55, life: 0.25 });
      P(dim, "impact", { ...g, y: g.y + 0.6 }, { color: white(c, 0.3), size: R * 0.8, life: 0.2 });
      shock(dim, g, c, R, { debris: 12 });
      P(dim, "smoke", { ...g, y: g.y + 0.5 }, { count: 10, speed: 2, size: 2, spread: R * 0.3 });
      P(dim, "ember", { ...g, y: g.y + 0.4 }, { color: c, count: 14, speed: 6, size: 0.7 });
      sound(dim, "astro.explosion_big", g, rand(0.9, 1.1), 1.3);
      shake(dim, g, 18, 0.5, 0.4);
    }
    for (const e of enemiesNear(ctx, { ...g, y: g.y + 0.8 }, R)) {
      hit(ctx, e, o.damage ?? 12, { color: c, kb: 0.8, up: 0.55, dir: dirTo(g, e.location), power: 1.8, ...(o.hit ?? {}) });
    }
    try { o.onImpact?.(g); } catch (e) { report("meteor.onImpact", e); }
  });
  return delay + fall;
}

/**
 * 連鎖する雷: first から近くの敵へ次々と飛び移る。
 * @param o max 最大の数（5）/ range 飛び移る距離（6）/ damage 素のダメージ（6）/ falloff 1 回ごとの減衰（0.85）/
 *          delay 1 回ごとの tick（2）/ from 最初の雷の出どころ（ctx.chest()）/ color / hit 追加オプション /
 *          sound（"astro.zap"）/ onHit(e, i) /
 *          filter(e) 飛び移ってよい相手（既定: 敵対的な相手だけ。村人・動物・中立の mob へは飛ばない）
 * @returns 連鎖が終わるまでの tick
 */
export function chain(ctx, first, o = {}) {
  if (!first || !valid(first)) return 0;
  const dim = ctx.dim;
  const c = o.color ?? ctx.c;
  const max = o.max ?? 5, range = o.range ?? 6, delay = o.delay ?? 2;
  const may = o.filter ?? ((e) => isHostile(e, ctx.p));
  const seen = new Set();
  let cur = first;
  let prev = o.from ?? ctx.chest();
  let i = 0;
  const step = () => {
    if (!cur || !valid(cur) || i >= max) return;
    seen.add(cur.id);
    const to = chestOf(cur);
    const d = sub(to, prev);
    const L = Math.hypot(d.x, d.y, d.z);
    if (L > 0.05) {
      P(dim, "bolt", prev, { color: c, dir: norm(d), len: L, size: 0.6, life: 0.2 });
      P(dim, "bolt", prev, { color: white(c, 0.6), dir: norm(d), len: L, size: 0.3, life: 0.15 });
    }
    P(dim, "arc", to, { color: c, size: 1.2, life: 0.3 });
    P(dim, "spark", to, { color: white(c, 0.4), count: 8, speed: 6 });
    sound(dim, o.sound ?? "astro.zap", to, 1.0 + i * 0.08, 0.9);
    hit(ctx, cur, (o.damage ?? 6) * Math.pow(o.falloff ?? 0.85, i), { color: c, power: 1.2, ...(o.hit ?? {}) });
    try { o.onHit?.(cur, i); } catch (e) { report("chain.onHit", e); }
    // 次の相手
    let best, bd = Infinity;
    for (const e of enemiesNear(ctx, to, range)) {
      if (seen.has(e.id) || !may(e)) continue;
      const dd = dist(e.location, cur.location);
      if (dd < bd) { bd = dd; best = e; }
    }
    prev = to;
    cur = best;
    i++;
    if (cur) ctx.at(delay, step);
  };
  ctx.at(0, step);
  return max * delay;
}

// ---------------------------------------------------------------------------
//  汎用の技一式（惑星の技がまだ無い形態用。惑星の色で描く）
// ---------------------------------------------------------------------------
const genericCache = new Map();

/**
 * 惑星の色で描く汎用の技一式 { skill, dash, air, ult, combo3, burst, passive }。
 * planets/<key>.js がまだ仮の間はこれを register する（TODO の印）。
 */
export function genericMoves(key) {
  if (genericCache.has(key)) return genericCache.get(key);
  const set = {
    /** 惑星技（仮）: 惑星色の斬撃波を飛ばす。14m・貫通。 */
    skill(ctx) {
      const { p, dim, c, hot } = ctx;
      body(p, "cast");
      sound(dim, "astro.beam_charge", p.location, 1.2, 0.8);
      ctx.every(0, 4, 2, () => P(dim, "converge", ctx.front(1.0, 1.3), { color: hot, count: 6, spread: 1.4, life: 0.25 }));
      ctx.at(8, () => {
        const f = ctx.liveDir();
        body(p, "throw");
        sound(dim, "astro.swing_heavy", p.location, 0.9, 1.0);
        sound(dim, "astro.beam_fire", p.location, 1.1, 0.8);
        arc(dim, ctx.chest(), f, 1.8, -70, 70, 0, c, { size: 1.0, steps: 12 });
        projectile(ctx, ctx.front(1.2, 1.1), f, {
          speed: 1.0, range: 14, radius: 1.3, pierce: Infinity, damage: 9,
          hitOpts: { color: c, kb: 0.9, up: 0.25, power: 1.3 },
          trail(d, pos, prev, age) {
            P(d, "slash_flat", pos, { color: c, size: 0.85, rot: yawDeg(f), life: 0.12 });
            P(d, "trail", pos, { color: white(c, 0.3), size: 1.2, life: 0.18 });
            if (age % 2 === 0) P(d, "spark", pos, { color: hot, count: 2, speed: 2 });
          },
          onEnd(pos) { burst(dim, pos, c, 1.2); },
        });
      });
      return 18;
    },
    /** 機動技（仮）: 惑星色の流星になって突進する。突進中はほぼ無敵。 */
    dash(ctx) {
      const { p, dim, c, hot } = ctx;
      const f = ctx.f;
      body(p, "thrust");
      sound(dim, "astro.boost", p.location, 0.9, 1.0);
      effect(p, "resistance", 12, 3);
      lunge(ctx, f, 1.45, 0.08);
      P(dim, "ring", ctx.chest(), { color: c, size: 1.8, life: 0.25 });
      ctx.every(0, 9, 1, (i) => {
        const l = p.location;
        afterimage(dim, l, c, 0.35);
        P(dim, "trail", ctx.local(1.4, 0, 1.1), { color: hot, size: 1.6, life: 0.2 });
        P(dim, "speedline", { x: l.x, y: l.y + 1, z: l.z }, { color: c, count: 3, dir: { x: -f.x, y: 0, z: -f.z }, speed: 14 });
      });
      dashHits(ctx, 9, 2.3, 7, { color: c, kb: 1.1, up: 0.3 });
      ctx.at(10, () => {
        const at = ctx.local(1.4, 0, 1.0);
        burst(dim, at, c, 1.8);
        P(dim, "ring_flat", { ...p.location, y: p.location.y + 0.1 }, { color: c, size: 2.7 });
        sound(dim, "astro.explosion", at, 1.4, 0.6);
        for (const e of ctx.foes(3.0, at)) hit(ctx, e, 4, { color: c, kb: 0.8, up: 0.4, dir: f });
      });
      return 16;
    },
    /** 空中技（仮）: 宙で止まり、真下へ叩きつけて衝撃波と光の柱。 */
    air(ctx) {
      const { p, dim, c, hot } = ctx;
      hover(ctx, 8, 0.4);
      body(p, "slam");
      sound(dim, "astro.beam_charge", p.location, 1.3, 0.7);
      P(dim, "circle", { ...p.location, y: p.location.y - 0.5 }, { color: c, size: 1.8, life: 0.6, spin: -200 });
      ctx.at(7, () => {
        sound(dim, "astro.swing_heavy", p.location, 0.7, 1.0);
        plunge(ctx, (l) => {
          body(p, "land", "astro.move");
          sound(dim, "astro.impact_heavy", l, 1.0, 1.0);
          shake(dim, l, 16, 0.45, 0.4);
          shock(dim, l, c, 5, { debris: 10 });
          for (let k = 0; k < 6; k++) {
            const q = add(l, yawRotate({ x: 1, y: 0, z: 0 }, k * 60 + 30), 3.4);
            ctx.at(k, () => P(dim, "pillar", { ...q, y: q.y + 0.05 }, { color: c, size: 0.9, height: 5, life: 0.5 }));
          }
          for (const e of ctx.foes(5.2, { ...l, y: l.y + 0.8 })) {
            hit(ctx, e, 10, { color: c, kb: 0.7, up: 0.65, power: 1.6 });
          }
        });
      });
      return 30;
    },
    /** 必殺（仮）: 時を止め、惑星の隕石を三つ落とし、最後に星の爆発。 */
    ult(ctx) {
      const { p, dim, c, hot } = ctx;
      ultOpen(ctx, 70, 14);
      const centre = { ...p.location };
      ctx.every(0, 10, 3, () => {
        P(dim, "star", { x: centre.x + rand(-6, 6), y: centre.y + rand(0.5, 4), z: centre.z + rand(-6, 6) }, { color: hot, count: 2, spread: 0.3 });
      });
      for (let k = 0; k < 3; k++) {
        ctx.at(10 + k * 8, () => {
          const foes = ctx.hostiles(14, centre);
          const tgt = foes.length ? foes[k % foes.length].location
            : add(centre, yawRotate(ctx.f, k * 120), 5);
          meteor(ctx, tgt, { delay: 10, fall: 6, radius: 3.5, damage: 10, color: k % 2 ? ctx.accent : c });
        });
      }
      // astro.supernova は鳴らしてから 1.66 秒（33 tick）後に弾ける
      ctx.at(17, () => sound(dim, "astro.supernova", centre, 1.0, 1.4));
      ctx.at(50, () => {
        const g = onGround(dim, centre);
        P(dim, "lens", { ...g, y: g.y + 1.5 }, { color: white(c, 0.5), size: 3, life: 0.5 });
        P(dim, "flare", { ...g, y: g.y + 1.2 }, { color: white(c, 0.6), size: 2.4, life: 0.35 });
        shock(dim, g, c, 10, { debris: 16 });
        flash(dim, g, 30, [1, 1, 1], 0.1, 0.5);
        sound(dim, "astro.explosion_big", g, 0.9, 1.4);
        shake(dim, g, 24, 0.7, 0.6);
        for (const e of ctx.foes(10.5, { ...g, y: g.y + 1 })) {
          hit(ctx, e, 14, { color: c, kb: 1.4, up: 0.6, power: 2.2, crit: true });
        }
      });
      return 60;
    },
    /** 三段目（仮）: 前方へ惑星色の扇の斬撃。 */
    combo3(ctx, target) {
      const { p, dim, c, hot } = ctx;
      const f = ctx.liveDir();
      for (const a of [-30, 0, 30]) arc(dim, ctx.chest(), yawRotate(f, a), 2.2, -50, 50, 10, c, { size: 0.9, steps: 8, sparks: false });
      P(dim, "slash_big", ctx.local(1.8, 0, 1.1), { color: c, rot: yawDeg(f), size: 0.9, life: 0.3 });
      sound(dim, "astro.swing_heavy", p.location, 1.1, 0.9);
      for (const e of ctx.cone(4.2, 55, ctx.chest(), f)) hit(ctx, e, 4, { color: c, kb: 0.9, up: 0.3, dir: f });
      if (target && valid(target)) burst(dim, chestOf(target), hot, 1.4);
      return 10;
    },
    /** 変身の締め（仮）: 惑星色の輪と紋章、光の柱。 */
    burst(ctx) {
      const { p, dim, c, hot } = ctx;
      const g = { ...p.location, y: p.location.y + 0.05 };
      emblem(dim, g, ctx.planet, { size: 1.6, life: 1.8 });
      P(dim, "pillar", g, { color: c, size: 1.2, height: 7, life: 0.6 });
      P(dim, "flare", ctx.chest(), { color: white(c, 0.5), size: 1.4, life: 0.3 });
      ctx.every(0, 4, 3, (i) => {
        P(dim, "ring_flat", g, { color: i % 2 ? ctx.accent : c, size: 0.9 + i * 0.8, life: 0.5 });
        ring(dim, "star", g, 1.5 + i * 1.2, 8, { color: hot, count: 1, spread: 0.1, life: 0.8 }, 0.6);
      });
      P(dim, "aura", ctx.loc(), { color: c, size: 1.4, life: 1.0 });
      return 12;
    },
    passive: {},
  };
  genericCache.set(key, set);
  return set;
}

export {
  body, bodyStop, add, dist, sub, now, dirTo, P, white, mix, line, ring, arc, burst, shock, beam, emblem,
  flash, shake, sound, afterimage, slash, hit, enemiesNear, enemiesInCone, enemiesOnLine, nearestEnemy,
  freeze, launch, push, pull, reflectProjectiles, markAirborne, onGround, groundY, fxScale,
  hostilesNear, nearestHostile, supported, clearLine,
};
