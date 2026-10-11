// 演出 / particles, sound, camera work, hit detection
//
// 「映画のような」を担っているのは、実はパーティクル単体ではなく
//   画面の揺れ・一瞬の暗転・タイトル・音の重ね方
// の組み合わせ。ここにその語彙をまとめる。
//
// 層の規約（DIRECTION §5-1）を関数の形にしてある。技を書く側は
//   白＝撃発（1〜3 tick） / 紫＝場 / 鋼＝物体
// の三つを `strike()` に渡すだけでよく、重ね順と間合いはここが持つ。
import { system } from "@minecraft/server";
import {
  clamp, distance, forward, hasFamily, normalise, safe, sub, title,
} from "./util.js";
import { FAMILY, TAG } from "./config.js";

// ---------------------------------------------------------------- particles
// 一 tick に撒ける粒の上限。技が重なると spawnParticle は簡単に数百発になり、
// そこだけで tick を食い潰す。上限を超えた分は黙って捨てる（落ちるより軽い方を取る）。
const FX_BUDGET = 360;
let fxTick = -1;
let fxSpent = 0;

function overBudget() {
  const now = safe(() => system.currentTick);
  if (typeof now !== "number") return false;   // tick が読めない環境では制限しない
  if (now !== fxTick) { fxTick = now; fxSpent = 0; }
  return ++fxSpent > FX_BUDGET;
}

export function fx(dimension, id, location) {
  if (overBudget()) return false;
  try { dimension.spawnParticle(id, location); return true; } catch (_) { return false; }
}

export function fxRing(dimension, id, centre, radius, count, y = 0.2) {
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * radius,
      y: centre.y + y,
      z: centre.z + Math.sin(a) * radius,
    });
  }
}

export function fxLine(dimension, id, origin, dir, length, step = 1.1) {
  for (let d = 0; d <= length; d += step) fx(dimension, id, forward(origin, dir, d));
}

export function fxScatter(dimension, id, centre, count, spread = 1.0) {
  for (let i = 0; i < count; i++) {
    fx(dimension, id, {
      x: centre.x + (Math.random() - 0.5) * spread * 2,
      y: centre.y + Math.random() * spread,
      z: centre.z + (Math.random() - 0.5) * spread * 2,
    });
  }
}

/** 球殻に撒く。障壁・磁界の棺のように「面」を見せたいとき。 */
export function fxSphere(dimension, id, centre, radius, count) {
  for (let i = 0; i < count; i++) {
    const u = Math.random() * 2 - 1;
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(1 - u * u);
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * r * radius,
      y: centre.y + u * radius,
      z: centre.z + Math.sin(a) * r * radius,
    });
  }
}

/** 上半球だけ。障壁は地面から生えるので、下半分を撒くと地中に消えて損をする。 */
export function fxDome(dimension, id, centre, radius, count, lift = 0) {
  for (let i = 0; i < count; i++) {
    const u = Math.random();                       // 0..1 = 上半球
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(1 - u * u);
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * r * radius,
      y: centre.y + u * radius + lift,
      z: centre.z + Math.sin(a) * r * radius,
    });
  }
}

/** 二点間を結ぶ。磁力線の表現。 */
export function fxTrail(dimension, id, from, to, step = 0.7) {
  const d = sub(to, from);
  const len = Math.hypot(d.x, d.y, d.z);
  if (len < 0.01) return;
  const dir = { x: d.x / len, y: d.y / len, z: d.z / len };
  for (let t = 0; t <= len; t += step) fx(dimension, id, forward(from, dir, t));
}

/**
 * 二点を弧で結ぶ。直線の `fxTrail` と混ぜて使うと磁力線が「張っている」
 * ように見える。まっすぐな線だけだとレーザーに見えてしまう。
 */
export function fxArc(dimension, id, from, to, arc = 1.6, steps = 12) {
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const lift = Math.sin(t * Math.PI) * arc;      // 中央で最大に膨らむ
    fx(dimension, id, {
      x: from.x + (to.x - from.x) * t,
      y: from.y + (to.y - from.y) * t + lift,
      z: from.z + (to.z - from.z) * t,
    });
  }
}

/** 柱。地面から立ち上がる系（uprising / throne）の芯。 */
export function fxColumn(dimension, id, base, height, count, jitter = 0.35) {
  for (let i = 0; i < count; i++) {
    const t = i / Math.max(1, count - 1);
    fx(dimension, id, {
      x: base.x + (Math.random() - 0.5) * jitter * 2,
      y: base.y + height * t,
      z: base.z + (Math.random() - 0.5) * jitter * 2,
    });
  }
}

/** 螺旋。引き寄せ・巻き上げの「流れ」を見せる。 */
export function fxSpiral(dimension, id, centre, radius, height, turns, count) {
  for (let i = 0; i < count; i++) {
    const t = i / count;
    const a = t * Math.PI * 2 * turns;
    const r = radius * (1 - t * 0.75);
    fx(dimension, id, {
      x: centre.x + Math.cos(a) * r,
      y: centre.y + height * t,
      z: centre.z + Math.sin(a) * r,
    });
  }
}

// ---------------------------------------------------------------- sound
export function sound(dimension, id, location, opts) {
  try { dimension.playSound(id, location, opts); } catch (_) { }
}

/** 音を少しずらして重ねる。単発より遥かに「厚く」なる。 */
export function chord(dimension, location, layers) {
  for (const [id, delay, opts] of layers) {
    if (delay <= 0) sound(dimension, id, location, opts);
    else safe(() => system.runTimeout(() => sound(dimension, id, location, opts), delay));
  }
}

// ---------------------------------------------------------------- camera
/**
 * 画面を揺らす。
 *
 * 既定を `rotational` にしてあるのは、`positional` が距離で減衰する
 * ＝ **揺らした本人には効かない** ため。自分に効かせたいときは必ず回転。
 * 周囲へ配るときだけ `shakeNearby()` が `positional` を使う。
 */
export function shake(player, intensity = 0.2, seconds = 0.3, type = "rotational") {
  try {
    player.runCommand(
      `camerashake add @s ${clamp(intensity, 0.01, 1).toFixed(2)} ${clamp(seconds, 0.05, 4).toFixed(2)} ${type}`);
  } catch (_) { }
}

/** 揺れの強さの正典（DIRECTION §5-7）。数値をここ以外に散らかさない。 */
export const PUNCH = {
  light: [0.08, 0.12],
  medium: [0.14, 0.20],
  heavy: [0.22, 0.30],
  ultimate: [0.35, 0.40],
};

/** 自分の画面を殴る。強さは名前で指定する。 */
export function screenPunch(player, weight = "medium") {
  const [i, s] = PUNCH[weight] ?? PUNCH.medium;
  shake(player, i, s, "rotational");
}

export function shakeNearby(dimension, centre, radius, intensity, seconds, except) {
  let players = [];
  try {
    players = dimension.getEntities({
      location: centre, maxDistance: radius, type: "minecraft:player",
    });
  } catch (_) { return; }
  for (const p of players) {
    if (except && p.id === except.id) continue;
    const d = distance(p.location, centre);
    shake(p, Math.max(0.05, intensity * (1 - d / radius)), seconds, "positional");
  }
}

/** 地響き。撃った本人は `screenPunch`、周りは距離減衰の `positional`。 */
export function quake(dimension, centre, radius, weight = "medium", except) {
  const [i] = PUNCH[weight] ?? PUNCH.medium;
  shakeNearby(dimension, centre, radius, i, 0.20, except);
}

/**
 * 一瞬の暗転／発光。
 * `fadeInTime` は 0.08 秒を上限にする。これを超えると「演出」ではなく
 * 「操作が奪われた」に変わり、手応えを殺す（DIRECTION §5-7）。
 * 使ってよいのは 必殺の撃発 / 変身 / 段階昇格 の三箇所だけ。
 */
export function fade(player, colour = { red: 0.55, green: 0.30, blue: 0.95 },
                     inSec = 0.06, holdSec = 0.05, outSec = 0.35) {
  try {
    player.camera.fade({
      fadeColor: colour,
      fadeTime: {
        fadeInTime: clamp(inSec, 0.01, 0.08),
        holdTime: clamp(holdSec, 0, 0.5),
        fadeOutTime: clamp(outSec, 0.05, 1.2),
      },
    });
  } catch (_) { }
}

// ---------------------------------------------------------------- fog
//: プレイヤー -> いま push してある霧の名前。pop の取りこぼしがそのまま
//: 「霧が抜けないワールド」になるので、押した分を必ず覚えておく。
const fogsOn = new Map();

/**
 * 視界を色で染める。一人称で「磁界の中にいる」感じを出す。
 * `ticks` を渡すと自動で pop する。**押しっぱなしは禁止**。
 */
export function fog(player, id, name = "marvel_field", ticks = 0) {
  try { player.runCommand(`fog @s push ${id} ${name}`); } catch (_) { return; }
  let set = fogsOn.get(player.id);
  if (!set) { set = new Set(); fogsOn.set(player.id, set); }
  set.add(name);
  if (ticks > 0) {
    safe(() => system.runTimeout(() => fogPop(player, name), ticks));
  }
}

export function fogPop(player, name = "marvel_field") {
  try { player.runCommand(`fog @s pop ${name}`); } catch (_) { }
  const set = fogsOn.get(player.id);
  if (set) {
    set.delete(name);
    if (!set.size) fogsOn.delete(player.id);
  }
}

/** 押した霧を全部剥がす。変身解除・死亡・退出のときに必ず通す。 */
export function fogPopAll(player) {
  const set = fogsOn.get(player.id);
  if (!set) return;
  for (const name of [...set]) fogPop(player, name);
  fogsOn.delete(player.id);
}

/** 退出したプレイヤーの記録を捨てる（残すと Map が延々太る）。 */
export function forgetFog(playerId) {
  fogsOn.delete(playerId);
}

// ---------------------------------------------------------------- 撃発
/**
 * 撃発の一撃。DIRECTION §5-1 の層をそのまま関数にしたもの。
 *
 *   white … 撃発。中心に短く濃く。1〜3 tick で消える粒を渡すこと
 *   field … 場。輪で広がる紫
 *   steel … 物体。散る鋼片
 *
 * 三層のうち二層でも渡せば「厚み」が出る。音・揺れ・地響きも一緒に置ける。
 * 技ごとに粒の名前を変えるだけで別の絵になる、というのが狙い。
 */
export function strike(dimension, at, opts = {}) {
  const {
    white, field, steel,
    radius = 1.8, ringCount = 12, whiteCount = 6, steelCount = 8,
    sounds, self, weight = "medium", quakeRadius = 0,
  } = opts;
  if (white) fxScatter(dimension, white, at, whiteCount, 0.35);
  if (field) fxRing(dimension, field, at, radius, ringCount, 0.35);
  if (steel) fxScatter(dimension, steel, at, steelCount, radius * 0.6);
  if (sounds?.length) chord(dimension, at, sounds);
  if (self) screenPunch(self, weight);
  if (quakeRadius > 0) quake(dimension, at, quakeRadius, weight, self);
}

/**
 * 見出し。変身・昇格・必殺のように「間を取ってよい」場面だけで使う。
 * 暗転を伴うので、技の合間に挟むと確実にうるさくなる。
 */
export function announce(player, main, sub, colour, weight = "heavy") {
  title(player, main, sub, 4, 34, 16);
  if (colour) fade(player, colour, 0.06, 0.05, 0.55);
  screenPunch(player, weight);
}

/** ヒットストップ。一瞬だけ相手を止めると、当たった重みが出る。 */
export function hitstop(entity, ticks = 3) {
  try {
    entity.addEffect("slowness", ticks, { amplifier: 6, showParticles: false });
  } catch (_) { }
}

export function hitstopAll(entities, ticks = 3) {
  for (const e of entities) hitstop(e.entity ?? e, ticks);
}

// ---------------------------------------------------------------- targeting
/**
 * 味方かどうか。
 *
 * 以前はここが「プレイヤーは全部除外」だったので、**PvP で技が一切
 * 当たらなかった**。プレイヤーも普通に的にする。味方の印を持つ者
 * （ブラザーフッド family / `marvel_ally` タグ）だけを外す。
 */
export function isAlly(entity, source) {
  if (!entity) return true;
  if (source && entity.id === source.id) return true;
  if (hasFamily(entity, FAMILY.brotherhood)) return true;
  try { if (entity.hasTag?.(TAG.ally)) return true; } catch (_) { }
  return false;
}

export function targetsNear(entity, radius, includeAllies = false) {
  try {
    return entity.dimension.getEntities({
      location: entity.location, maxDistance: radius,
      excludeTypes: ["minecraft:item", "minecraft:xp_orb", "minecraft:arrow"],
    }).filter((e) => e.id !== entity.id
      && !hasFamily(e, FAMILY.prop)
      && (includeAllies || !isAlly(e, entity)));
  } catch (_) { return []; }
}

/** 正面の扇。`dot` は 1 が真正面、-1 が全周。 */
export function cone(attacker, radius, dot, includeAllies = false) {
  const dir = attacker.getViewDirection();
  const from = attacker.getHeadLocation ? attacker.getHeadLocation() : attacker.location;
  const out = [];
  for (const target of targetsNear(attacker, radius, includeAllies)) {
    const to = sub({ x: target.location.x, y: target.location.y + 0.8, z: target.location.z }, from);
    const n = normalise(to);
    if (n.x * dir.x + n.y * dir.y + n.z * dir.z < dot) continue;
    out.push({ entity: target, dir: n, distance: Math.hypot(to.x, to.y, to.z) });
  }
  return out.sort((a, b) => a.distance - b.distance);
}

/** 視線上の直線。貫通技に使う。 */
export function ray(attacker, length, width, includeAllies = false) {
  const dir = attacker.getViewDirection();
  const eye = attacker.getHeadLocation ? attacker.getHeadLocation() : attacker.location;
  const out = [];
  for (const target of targetsNear(attacker, length + 2, includeAllies)) {
    const to = sub({ x: target.location.x, y: target.location.y + 0.8, z: target.location.z }, eye);
    const along = to.x * dir.x + to.y * dir.y + to.z * dir.z;
    if (along < 0 || along > length) continue;
    const perp = Math.hypot(to.x - dir.x * along, to.y - dir.y * along, to.z - dir.z * along);
    if (perp > width) continue;
    out.push({ entity: target, along });
  }
  return out.sort((a, b) => a.along - b.along);
}

/** 視線の先で最初に当たるもの（エンティティ優先、無ければブロック）。 */
export function lookTarget(player, range = 32) {
  const hitEntity = safe(() => player.getEntitiesFromViewDirection({ maxDistance: range })
    ?.filter((h) => h.entity?.id !== player.id)?.[0]?.entity);
  if (hitEntity) return { entity: hitEntity, location: hitEntity.location };
  const hitBlock = safe(() => player.getBlockFromViewDirection({ maxDistance: range }));
  if (hitBlock?.block) {
    const b = hitBlock.block.location;
    return { block: hitBlock.block, location: { x: b.x + 0.5, y: b.y + 0.5, z: b.z + 0.5 } };
  }
  const dir = player.getViewDirection();
  const eye = player.getHeadLocation();
  return { location: forward(eye, dir, range * 0.6) };
}

/**
 * ダメージ。
 *
 * `entityAttack` は殴られた側に 10 tick の無敵を張る。連射する技
 * （鉄片の嵐など）をこの cause で撃つと、**撃った弾のほとんどが
 * 無敵時間に吸われて消える**。間隔が 5 tick より短い技は必ず
 * `hitRapid()` を使うこと。
 */
export function hit(attacker, target, damage, cause = "entityAttack") {
  try {
    target.applyDamage(Math.max(1, Math.round(damage)),
      { cause, damagingEntity: attacker });
    return true;
  } catch (_) { return false; }
}

/** 連射用。無敵時間を踏まない cause で入れる。撃破の手柄は撃った側に残る。 */
export function hitRapid(attacker, target, damage) {
  return hit(attacker, target, damage, "magic");
}

/**
 * ノックバック。
 *
 * `applyKnockback` の引数は Bedrock のバージョンで二通りある
 * （新: `(水平ベクトル, 縦の強さ)` / 旧: `(dx, dz, 水平, 縦)`）。
 * どちらの環境でも動くよう順に試し、最後にプレイヤー以外向けの
 * `applyImpulse` へ落とす。ここを決め打ちにすると、
 * 片方の環境で**全ての技のノックバックが無言で効かなくなる**。
 */
export function knock(entity, dir, power, vertical = 0.5) {
  const hx = dir.x * power;
  const hz = dir.z * power;
  try { entity.applyKnockback({ x: hx, z: hz }, vertical); return true; } catch (_) { }
  try { entity.applyKnockback(dir.x, dir.z, power, vertical); return true; } catch (_) { }
  try { entity.applyImpulse({ x: hx * 0.4, y: vertical, z: hz * 0.4 }); return true; } catch (_) { }
  return false;
}

/** 自分自身を押す（突進・跳躍・飛行）。knock と同じ理由で二通り試す。 */
export function selfPush(entity, dirX, dirZ, horizontal, vertical) {
  try { entity.applyKnockback({ x: dirX * horizontal, z: dirZ * horizontal }, vertical); return true; } catch (_) { }
  try { entity.applyKnockback(dirX, dirZ, horizontal, vertical); return true; } catch (_) { }
  try { entity.applyImpulse({ x: dirX * horizontal * 0.4, y: vertical, z: dirZ * horizontal * 0.4 }); return true; } catch (_) { }
  return false;
}
