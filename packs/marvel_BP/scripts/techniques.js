// マグニートーの技 15 / Magneto's fifteen techniques
//
// 一つの技は、必ず次の四つを揃える。どれが欠けても安っぽくなる。
//   1. 三人称の構え   pose() で体アイテムを差し替える（＝技クリップの再生）
//   2. 一人称の手元   技アイテムの attachable が itemStartUse で反応する
//   3. 画面の演出     世界側のパーティクル・音・画面揺れ・fog・（必殺なら）暗転
//   4. 実際の効果     ダメージ・ノックバック・ブロック操作
//
// 演出の分担
// ----------
// **体に付く VFX は技クリップ側（担当 6/7）が locator から出している。**
//   例: repulse は 0.25 秒に marvel:repulse_wave を体から出す。
// だからスクリプトが同じものを足元へもう一度撒くと二重になる。
// ここが出すのは **世界側だけ** — 着弾点・敵の位置・環・磁力線・破片、
// そして音・画面揺れ・fog・fade。クリップに無いものだけを足す。
//
// 拍の合わせ方
// ------------
// 効果の発生は **撃発 t_d に一致させる**（DIRECTION §4-2）。
// 旧実装の `hold * 0.32` は crush で 0.19 秒、uprising で 0.39 秒早く、
// 絵が振り下ろされる前にダメージが出ていた。
//
// 地形について（REVIEW_BASELINE の最大の指摘）
// -------------------------------------------
// `ripBlock` は磁性ブロックを air にしたまま戻さない。実際に遊ぶと
// storm / uprising / sphere で世界が穴だらけになる。ここでは三段で塞いだ:
//   * shard_storm は **一切剥がさない**。周囲の金属は「弾数」としてだけ数える。
//   * uprising / sphere は `ripTemp()` を通し、**8 秒後に必ず置き直す**。
//     一度に剥がせる数にも上限を置く（uprising 8 / sphere 24）。
//   * 磁力採掘（磁力視 + uprising）は鉱石を **母岩に置換** して中身だけ抜く。
//     穴が一つも空かないので、これが一番「マグニートーらしい」採掘になった。
import { system, ItemStack } from "@minecraft/server";
import {
  PROP, TECH, TECH_ORDER, FX, SOUND, ENTITY, FAMILY, TAG, MAGNETIC_BLOCKS,
} from "./config.js";
import {
  Cooldowns, add, allPlayers, distance, forward, hasFamily, isPlayer,
  normalise, num, safe, scale, setProp, sub, tell, title, tr,
} from "./util.js";
import {
  chord, fade, fog, fogPop, fx, fxRing, fxScatter, fxSphere, fxSpiral, fxTrail,
  hit, hitstop, knock, lookTarget, selfPush, shake, shakeNearby, sound,
} from "./effects.js";
import {
  blockStrength, drag, drawFieldLines, launchShard, metalOn, projectileCount,
  pullItems, revealMetal, ripBlock, scanMetal, stripEquipment,
} from "./magnetism.js";
import { isTransformed, magOf, pose, spendMag, stageOf } from "./transform.js";

export const cooldowns = new Cooldowns();

const DAMAGE_SCALE = { 1: 0.7, 2: 1.0, 3: 1.35 };

//: 飛んでいる鉄片の総数の上限。storm と sphere が同時に走ると
//: 毎 tick 全弾の teleport + getEntities が効いてくるので、撃つ側で止める。
const PROJECTILE_CAP = 60;

//: プライム・センチネルのフェーズで使う一時タグ。
//: contract.TAGS に無いので、既存の "marvel_bound" 等と同じ流儀で直書きする。
export const T_EXPOSED = "marvel_exposed";     // コア露出（物理 2 倍）
export const T_ADAPTED = "marvel_adapted";     // 磁力に適応（metalOn 1/4）
export const T_JAMMED = "marvel_jammed";       // プレイヤーの cd +50%
export const T_ADAMANTIUM = "marvel_adamantium"; // 磁力が一切効かない敵
export const T_TOWED = "marvel_towed";         // attract で牽引された直後

function power(player) {
  return DAMAGE_SCALE[stageOf(player)] ?? 1.0;
}

// ===========================================================================
//  0. 拍 — アニメと tick 単位で噛み合わせる
// ===========================================================================
//: 系統ごとの拍。`gen_anim_tech.py` の FAMILIES と **同じ式** を持たせてある。
//: 数式で持つのは、L を変えたときに片方だけ直し忘れる事故を防ぐため。
const BEAT = {
  light: { wind: 0.28, still: 0, strike: 0.06 },
  heavy: { wind: 0.46, still: 0, strike: 0.09 },
  ult: { wind: 0.50, still: 0.60, strike: 0.08 },
};

//: 技 -> [系統, クリップ長 L 秒]。DIRECTION §4-2 の正典表。
//: **本来は contract.TECHNIQUES の length / strike から来るべき値**で、
//: 担当 10 がそれを足したら、この表は消して config.js を読むこと。
const CLIP = {
  repulse: ["light", 0.72], attract: ["light", 0.75], disarm: ["light", 0.70],
  lance: ["light", 0.68], flight: ["light", 0.62], sight: ["light", 0.78],
  barrier: ["light", 0.86], iron_bind: ["heavy", 1.06], emp: ["heavy", 1.10],
  crush: ["heavy", 1.16], throne: ["heavy", 1.24], shard_storm: ["heavy", 1.30],
  polarity: ["heavy", 1.36], uprising: ["heavy", 1.50], sphere: ["ult", 3.00],
};

//: 構えを保ち続ける技。hold はクリップ長ではなく **効果の持続** に従う
//: （クリップ側は "hold_on_last_frame"）。
const SUSTAIN = { barrier: 120, sight: 0, flight: 0 };

function round2(v) { return Math.round(v * 100) / 100; }

/**
 * 任意のクリップの拍。ブラザーフッド側（powers.js）も同じ式で数えるため、
 * ここを唯一の出どころにする。表を二箇所に置くと必ず片方が腐る。
 */
export function clipBeat(family, length) {
  const beat = BEAT[family] ?? BEAT.light;
  const base = beat.still ? round2(beat.still * length) : round2(beat.wind * length);
  const strike = round2(base + beat.strike);
  return {
    strike,
    delay: Math.max(1, Math.round(strike * 20)),
    hold: Math.ceil(length * 20) + 6,
  };
}

/** 撃発 t_d（秒）。§4-2 の実キー時刻表そのまま。 */
export function strikeOf(key) {
  const spec = CLIP[key];
  if (!spec) return 0.25;
  const [family, length] = spec;
  const beat = BEAT[family];
  const base = beat.still ? round2(beat.still * length) : round2(beat.wind * length);
  return round2(base + beat.strike);
}

/** 効果を出す tick。絵の撃発とここが揃っていないと、全ての技が嘘に見える。 */
export function delayFor(key) {
  return Math.max(1, Math.round(strikeOf(key) * 20));
}

/**
 * 構えを保つ tick 数。`hold = ceil(L*20) + 6`（§4-2）。
 *
 * 段階 3 の ×0.85（§7-4）は **余韻の 6 tick だけを削る**。
 * クリップ長そのものを割ると、sphere（60 tick）が 56 tick で打ち切られて
 * 撃発の前に構えが解ける — 旧実装が踏んだのと同じ穴になる。
 */
export function holdFor(key, stage) {
  const length = CLIP[key]?.[1] ?? 1.1;
  const clip = Math.ceil(length * 20);
  const full = clip + 6;
  return stage >= 3 ? Math.max(clip + 1, Math.round(full * 0.85)) : full;
}

// ===========================================================================
//  1. 敵味方の判定
// ===========================================================================
//  effects.targetsNear() は `!isPlayer(e)` で **全プレイヤーを弾く** ので、
//  PvP だと技が一切当たらない（DIRECTION §7-6 #7、担当 8 の直し待ち）。
//  技側が待つ理由は無いので、ここは自前で引く。
export function hostile(entity, player) {
  if (!entity || entity.id === player.id) return false;
  if (hasFamily(entity, FAMILY.prop)) return false;
  if (hasFamily(entity, FAMILY.brotherhood)) return false;
  // 変身中の味方プレイヤーは撃たない。素の相手は普通の PvP として通す。
  if (isPlayer(entity) && safe(() => entity.hasTag(TAG.form)) === true) return false;
  return true;
}

export function enemiesNear(player, radius, from) {
  const centre = from ?? player.location;
  const found = safe(() => player.dimension.getEntities({
    location: centre, maxDistance: radius,
    excludeTypes: ["minecraft:item", "minecraft:xp_orb"],
  })) ?? [];
  return found.filter((e) => hostile(e, player));
}

/** 正面の扇。`dot` は 1 が真正面、-1 が全周。 */
export function coneOf(player, radius, dot) {
  const dir = player.getViewDirection();
  const eye = safe(() => player.getHeadLocation()) ?? player.location;
  const out = [];
  for (const entity of enemiesNear(player, radius)) {
    const to = sub({ x: entity.location.x, y: entity.location.y + 0.8, z: entity.location.z }, eye);
    const n = normalise(to);
    if (n.x * dir.x + n.y * dir.y + n.z * dir.z < dot) continue;
    out.push({ entity, dir: n, distance: Math.hypot(to.x, to.y, to.z) });
  }
  return out.sort((a, b) => a.distance - b.distance);
}

/** 視線上の直線。貫通技に使う。 */
export function rayOf(player, length, width) {
  const dir = player.getViewDirection();
  const eye = safe(() => player.getHeadLocation()) ?? player.location;
  const out = [];
  for (const entity of enemiesNear(player, length + 2)) {
    const to = sub({ x: entity.location.x, y: entity.location.y + 0.8, z: entity.location.z }, eye);
    const along = to.x * dir.x + to.y * dir.y + to.z * dir.z;
    if (along < 0 || along > length) continue;
    const perp = Math.hypot(to.x - dir.x * along, to.y - dir.y * along, to.z - dir.z * along);
    if (perp > width) continue;
    out.push({ entity, along });
  }
  return out.sort((a, b) => a.along - b.along);
}

/** アダマンチウムの相手。**効かない相手がいて初めて、効く快感が立つ**。 */
export function isAdamantium(entity) {
  return safe(() => entity.hasTag(T_ADAMANTIUM)) === true;
}

/**
 * 磁化量。`metalOn` に「適応」と「アダマンチウム」を掛けた実効値。
 * プライム・センチネルはフェーズ 2 で 4.0 -> 1.0 に落ちる（§7-5）。
 */
export function metalOf(entity) {
  if (!entity) return 0;
  if (isAdamantium(entity)) return 0;
  const base = metalOn(entity);
  return safe(() => entity.hasTag(T_ADAPTED)) === true ? base * 0.25 : base;
}

/** 磁力視の間、金属を持つ相手への与ダメが +20%（§7-1）。 */
export function damageBonus(player, target) {
  if (num(player, PROP.sight, 0) <= system.currentTick) return 1.0;
  return metalOf(target) > 0 ? 1.2 : 1.0;
}

function strikeDamage(player, target, base) {
  return hit(player, target, base * damageBonus(player, target));
}

/** 弾数の天井。超えている間は撃たない（撃てないより、重いほうが悪い）。 */
export function launchCapped(player, origin, dir, speed, damage, typeId, life) {
  if (projectileCount() >= PROJECTILE_CAP) return undefined;
  return launchShard(player, origin, dir, speed, damage, typeId, life);
}

// ===========================================================================
//  2. 地形を戻す
// ===========================================================================
const RESTORE_DELAY = 160;      // 8 秒
const RESTORE_LIMIT = 320;      // 保留の上限。溢れたら古い順に即戻す
const restoring = [];

function putBack(job, force = false) {
  const block = safe(() => job.dim.getBlock({ x: job.x, y: job.y, z: job.z }));
  if (!block) {
    // チャンクが寝ている。穴を残すより待つほうが良いので 3 回まで粘る。
    // ただし溢れて捨てるとき（force）は積み直さない。同じ長さのまま
    // shift と push を繰り返して無限に回るため。
    if (!force && job.tries < 3) {
      job.tries++;
      job.at = system.currentTick + 100;
      restoring.push(job);
    }
    return;
  }
  // 誰かが埋めた／建てた後なら上書きしない。復元が破壊になっては本末転倒。
  if (!block.isAir) return;
  safe(() => block.setType(job.typeId));
  fx(job.dim, FX.metal_glint, { x: job.x + 0.5, y: job.y + 0.5, z: job.z + 0.5 });
}

/** 剥がすが、必ず戻す。戻せない剥がし方はこの作品ではしない。 */
export function ripTemp(dim, pos, ownerId) {
  const block = safe(() => dim.getBlock(pos));
  if (!block) return undefined;
  const typeId = block.typeId;
  const shard = ripBlock(dim, pos, ownerId);
  if (!shard) return undefined;
  restoring.push({
    dim, x: pos.x, y: pos.y, z: pos.z, typeId, tries: 0,
    at: system.currentTick + RESTORE_DELAY,
  });
  while (restoring.length > RESTORE_LIMIT) putBack(restoring.shift(), true);
  return shard;
}

/** 毎 tick。期限の来たものだけ戻す。 */
export function tickRestore() {
  if (!restoring.length) return;
  const now = system.currentTick;
  let done = 0;
  while (restoring.length && restoring[0].at <= now && done < 24) {
    putBack(restoring.shift());
    done++;
  }
}

export function pendingRestores() { return restoring.length; }

// ===========================================================================
//  3. 走査を tick に分ける
// ===========================================================================
//  `scanMetal` は 3 重ループの break が最内しか抜けないので、r=40 だと
//  1 tick で約 4,850 回の getBlock になる（21³ の球内 = 0.524）。
//  必殺の溜めは 38 tick あるのだから、そこへ配ればいい。
//
//  **実測（走査の実回数を数えた）**
//    半径  step  getBlock 回数
//      8    1     2,109      <- uprising の旧値。必殺より重い
//      9    2       360
//     10    2       515      <- shard_storm
//     18    2     3,071      <- 磁力視の旧値。1 秒ごとに 19 秒間これが走る
//     20    2     4,169
//     21    4       597
//     22    4       672      <- 磁力視（現）
//     40    4     4,169      <- sphere。800/yield なら 6 yield で捌ける
//
//  `scanMetal` の step は `r<=8:1 / r<=20:2 / それ以上:4` で切り替わるので、
//  **半径を 1 増やすだけで 7 分の 1 になる境界がある**（20 -> 21、8 -> 9）。
//  旧実装は 8 / 18 / 20 と、どれも境界の高い側に張り付いていた。
//  広く見せたいなら、境界の安い側へ **広げる** のが正しい。
const SCAN_BUDGET = 800;        // 1 yield あたりの getBlock 回数

function scanMetalSpread(dim, centre, radius, limit, onDone) {
  const found = [];
  const step = radius <= 8 ? 1 : radius <= 20 ? 2 : 4;
  const r = Math.ceil(radius);
  const cx = Math.floor(centre.x), cy = Math.floor(centre.y), cz = Math.floor(centre.z);

  function* run() {
    let budget = 0;
    for (let dy = -r; dy <= r; dy += step) {
      const y = cy + dy;
      if (y < -64 || y > 320) continue;
      for (let dx = -r; dx <= r; dx += step) {
        for (let dz = -r; dz <= r; dz += step) {
          const d = Math.hypot(dx, dy, dz);
          if (d > radius) continue;
          const block = safe(() => dim.getBlock({ x: cx + dx, y, z: cz + dz }));
          if (++budget >= SCAN_BUDGET) { budget = 0; yield; }
          if (!block) continue;
          const strength = blockStrength(block.typeId);
          if (strength <= 0) continue;
          found.push({ x: cx + dx, y, z: cz + dz, typeId: block.typeId, strength, distance: d });
          if (found.length >= limit * 2) {
            found.sort((a, b) => (b.strength / (1 + b.distance)) - (a.strength / (1 + a.distance)));
            onDone(found.slice(0, limit));
            return;
          }
        }
      }
    }
    found.sort((a, b) => (b.strength / (1 + b.distance)) - (a.strength / (1 + a.distance)));
    onDone(found.slice(0, limit));
  }

  let started = false;
  try { system.runJob(run()); started = true; } catch (_) { started = false; }
  // runJob が無い環境では従来どおり一括で走らせる（重いが動かないよりよい）
  if (!started) onDone(scanMetal(dim, centre, radius, limit));
}

// ===========================================================================
//  4. 小道具
// ===========================================================================
/** 縦の環。水平の環だけだと真横から見たとき消える（§5-2）。 */
function fxRingUpright(dim, id, centre, radius, count, dir) {
  const side = normalise({ x: -dir.z, y: 0, z: dir.x });
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    fx(dim, id, {
      x: centre.x + side.x * Math.cos(a) * radius,
      y: centre.y + Math.sin(a) * radius,
      z: centre.z + side.z * Math.cos(a) * radius,
    });
  }
}

/** 磁力線の束。1 標的に 3 本、真ん中の 1 本だけ別色にすると立体に見える。 */
function fieldBundle(dim, from, to) {
  fxTrail(dim, FX.mag_line, from, to, 0.8);
  const side = normalise({ x: -(to.z - from.z), y: 0, z: to.x - from.x });
  for (const off of [-0.4, 0.4]) {
    fxTrail(dim, FX.mag_pull, add(from, scale(side, off)), add(to, scale(side, off)), 1.1);
  }
}

function eyeOf(player) {
  return safe(() => player.getHeadLocation()) ?? player.location;
}

function above(entity, dy = 1.0) {
  return { x: entity.location.x, y: entity.location.y + dy, z: entity.location.z };
}

/** 相手が磁力に応えない、と伝える一拍。無反応より遥かに親切。 */
function refuse(player, entity) {
  fx(player.dimension, FX.mag_glyph, above(entity, 1.4));
  sound(player.dimension, SOUND.ui_select, entity.location, { pitch: 0.5, volume: 0.8 });
  tell(player, tr("msg.immune"));
}

// ===========================================================================
//  5. 技の本体
// ===========================================================================
//  CHARGE = 発動の瞬間（予兆）。まだ何も起きない。音は鳴らさない。
//  ACTION = 撃発 t_d の瞬間。ここで全部が起きる。
const CHARGE = {};
const ACTION = {};

// --- 1. 磁力斥力 — 緊急離脱・面の押し返し ------------------------------------
CHARGE.repulse = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.4, pitch: 1.9 });
};

ACTION.repulse = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const dir = player.getViewDirection();
  const p = power(player);

  chord(dim, at, [[SOUND.repulse, 0, { volume: 1.0, pitch: 1.5 }],
                  [SOUND.mag_release, 2, { volume: 0.6, pitch: 1.8 }]]);
  shake(player, 0.08, 0.12, "rotational");
  shakeNearby(dim, at, 12, 0.22, 0.20);

  // 決め絵: 地面すれすれの薄い環 + 縦に一枚（§5-5）
  fxRing(dim, FX.mag_ring_wide, at, 2.6, 14, 0.15);
  fxRingUpright(dim, FX.mag_push, forward(at, dir, 2.0), 1.8, 10, dir);

  for (const { entity, dir: to, distance: d } of coneOf(player, 10, 0.1)) {
    const metal = metalOf(entity);
    const force = (1.1 + metal * 0.55) * p * Math.max(0.25, 1 - d / 14);
    strikeDamage(player, entity, (6 + metal * 2.5) * p);
    knock(entity, to, force * 2.4, 0.55 + metal * 0.08);
    fx(dim, FX.mag_push, above(entity, 0.9));
  }
  // 役割は「緊急離脱」。押した反動で自分も後ろへ抜ける。
  selfPush(player, -dir.x, -dir.z, 0.9, 0.42);
  pullItems(dim, at, 8, forward(at, dir, 10), 0.5);
  return true;
};

// --- 2. 磁力引力 — 牽引 ＋ 磁力ジップ ----------------------------------------
//  視線の先が **金属ブロック（距離 6〜24）** なら、引くのは相手ではなく自分。
//  地形と建築物がそのままグラップルの遊具になる（§7-3）。
const ZIP_MIN = 6, ZIP_MAX = 24, ZIP_TICKS = 18;   // 0.9 秒で着弾
const zipping = new Map();

CHARGE.attract = (player) => {
  sound(player.dimension, SOUND.attract, player.location, { volume: 0.5, pitch: 1.6 });
};

function zipTarget(player) {
  const look = safe(() => player.getBlockFromViewDirection({ maxDistance: ZIP_MAX }));
  const block = look?.block;
  if (!block) return undefined;
  if (blockStrength(block.typeId) <= 0) return undefined;
  const at = { x: block.location.x + 0.5, y: block.location.y + 0.5, z: block.location.z + 0.5 };
  const d = distance(at, player.location);
  return d >= ZIP_MIN && d <= ZIP_MAX ? at : undefined;
}

ACTION.attract = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const hand = eyeOf(player);
  const p = power(player);

  const anchor = zipTarget(player);
  if (anchor) {
    // --- 磁力ジップ: 自分を引く
    zipping.set(player.id, { to: anchor, left: ZIP_TICKS });
    fieldBundle(dim, hand, anchor);
    chord(dim, at, [[SOUND.attract, 0, { volume: 1.0, pitch: 0.7 }],
                    [SOUND.metal_hit, 3, { volume: 0.5, pitch: 1.8 }]]);
    fx(dim, FX.metal_glint, anchor);
    shake(player, 0.08, 0.16, "rotational");
    return true;
  }

  // --- 牽引: 敵・アイテムを手元へ
  sound(dim, SOUND.attract, at, { volume: 0.9, pitch: 0.9 });
  const lines = [];
  for (const { entity, distance: d } of coneOf(player, 16, -0.25)) {
    const metal = metalOf(entity);
    if (isAdamantium(entity)) { fx(dim, FX.mag_glyph, above(entity, 1.4)); continue; }
    drag(entity, at, 0.9 + metal * 0.28, 0.28);
    lines.push(above(entity, 0.8));
    // 牽引された機械には印を残す。ドローンを本体へぶつける遊びに使う（§7-5）。
    if (hasFamily(entity, FAMILY.sentinel)) {
      safe(() => entity.addTag(T_TOWED));
      system.runTimeout(() => safe(() => entity.removeTag(T_TOWED)), 60);
    }
    if (metal > 0) strikeDamage(player, entity, 2 * p);
    if (d < 3.0) fx(dim, FX.metal_glint, above(entity, 0.8));
  }
  pullItems(dim, at, 16, at, 0.85);
  // 漏斗の口は自分の顔。粒が顔へ向かって加速して見えるのが決め絵（§5-5）。
  fxSpiral(dim, FX.mag_pull, forward(hand, player.getViewDirection(), 5.0), 3.4, -2.4, 2, 20);
  for (const to of lines.slice(0, 4)) fieldBundle(dim, hand, to);
  drawFieldLines(dim, hand, lines, FX.mag_line, 6);
  return true;
};

/** ジップの牽引は毎 tick 効かせる。着いたら止める。 */
function tickZip() {
  if (!zipping.size) return;
  for (const player of allPlayers()) {
    const job = zipping.get(player.id);
    if (!job) continue;
    if (--job.left <= 0 || !isTransformed(player)) {
      zipping.delete(player.id);
      continue;
    }
    const d = sub(job.to, player.location);
    const len = Math.hypot(d.x, d.y, d.z) || 1;
    if (len < 2.6) {
      zipping.delete(player.id);
      fxRing(player.dimension, FX.metal_glint, player.location, 1.0, 8, 0.4);
      sound(player.dimension, SOUND.metal_hit, player.location, { volume: 0.7, pitch: 1.5 });
      safe(() => player.addEffect("slow_falling", 30, { amplifier: 0, showParticles: false }));
      continue;
    }
    const n = { x: d.x / len, y: d.y / len, z: d.z / len };
    // 残り距離を残り tick で割った速度。0.9 秒で着く見当になる。
    const need = Math.min(2.4, len / Math.max(1, job.left) * 1.6);
    selfPush(player, n.x, n.z, need, n.y * need * 0.9 + 0.16);
    fx(player.dimension, FX.mag_pull, player.location);
  }
}

// --- 3. 金属剥奪 — 剥いで着る／剥いで撃つ ------------------------------------
CHARGE.disarm = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.35, pitch: 2.0 });
};

ACTION.disarm = (player) => {
  const dim = player.dimension;
  const p = power(player);
  let stripped = 0;
  const victims = [];

  for (const { entity } of coneOf(player, 12, 0.25)) {
    if (isAdamantium(entity)) { fx(dim, FX.mag_glyph, above(entity, 1.4)); continue; }
    const n = stripEquipment(entity, dim);
    if (n <= 0) {
      if (metalOf(entity) === 0) fx(dim, FX.mag_glyph, above(entity, 1.4));
      continue;
    }
    stripped += n;
    victims.push(entity);
    // 決め絵: 胴から鎧の輪郭が黄白に一瞬光って剥がれ落ちる（§5-5）
    fx(dim, FX.disarm_flash, above(entity, 1.1));
    fxRingUpright(dim, FX.metal_rip, above(entity, 1.0), 0.9, 8, player.getViewDirection());
    strikeDamage(player, entity, 4 * p);
    hitstop(entity, 6);
  }

  if (!stripped) {
    tell(player, tr("msg.no_target"));
    sound(dim, SOUND.ui_select, player.location, { pitch: 0.6 });
    return true;
  }

  chord(dim, player.location, [[SOUND.disarm, 0, { pitch: 0.9 }],
                               [SOUND.metal_hit, 4, { volume: 0.6, pitch: 1.4 }]]);
  shake(player, 0.08, 0.14, "rotational");

  // 剥いで着る: 落ちた装備を自分の足元へ手繰り寄せる。拾えばそのまま着られる。
  for (const e of victims) pullItems(dim, e.location, 4, player.location, 1.1);
  system.runTimeout(() => {
    for (const e of victims) pullItems(dim, e.location, 6, player.location, 1.3);
  }, 8);

  // 剥いで撃つ: 削り取った鉄が、そのまま相手へ返る。1 点 = 12 ダメージ。
  let shot = 0;
  const fire = () => {
    if (shot >= stripped) return;
    const target = victims[shot % victims.length];
    shot++;
    if (safe(() => target.isValid?.() !== false)) {
      const from = forward(eyeOf(player), player.getViewDirection(), 1.2);
      const dir = normalise(sub(above(target, 0.9), from));
      launchCapped(player, from, dir, 1.9, 12 * p);
      sound(dim, SOUND.shard, from, { volume: 0.5, pitch: 1.5 });
    }
    system.runTimeout(fire, 5);
  };
  system.runTimeout(fire, 6);
  return true;
};

// --- 4. 磁界斬 — 単発貫通（3 体まで、0.75 倍ずつ減衰）------------------------
CHARGE.lance = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.4, pitch: 2.0 });
};

ACTION.lance = (player) => {
  const dim = player.dimension;
  const eye = eyeOf(player);
  const dir = player.getViewDirection();
  const p = power(player);

  chord(dim, player.location, [[SOUND.lance, 0, { volume: 1.0, pitch: 1.1 }],
                               [SOUND.shard, 3, { volume: 0.7, pitch: 1.6 }]]);
  shake(player, 0.08, 0.12, "rotational");

  // 決め絵は「細く長い一本線」。束ねて撃つのは鉄片嵐の仕事なので、弾は 1 本。
  launchCapped(player, forward(eye, dir, 1.2), dir, 2.4, 18 * p);
  for (let d = 2; d <= 20; d += 2.4) fx(dim, FX.lance_streak, forward(eye, dir, d));

  let n = 0;
  for (const { entity } of rayOf(player, 20, 1.3)) {
    if (n >= 3) break;                       // 3 体で止める。無限貫通は強すぎる
    const falloff = Math.pow(0.75, n);
    strikeDamage(player, entity, 18 * p * falloff);
    knock(entity, dir, 0.9 * falloff, 0.25);
    // 当たった一点だけ白く弾ける
    fx(dim, FX.lance_impact, above(entity, 1.0));
    hitstop(entity, 3);
    n++;
  }
  return true;
};

// --- 5. 鉄片嵐 — 面制圧 ------------------------------------------------------
//  1 発 9 ダメージ × 14 発。**ブロックは一つも剥がさない**（弾数だけ数える）。
//  連射間隔は 5 tick — hit() の cause が 10 tick の無敵を張るので、
//  同じ相手を撃ち続けると 6 発しか通らない。だから **標的を順に回す**。
CHARGE.shard_storm = (player) => {
  const dim = player.dimension;
  sound(dim, SOUND.mag_charge, player.location, { volume: 1.0, pitch: 1.5 });
  fxRing(dim, FX.storm_swirl, player.location, 2.2, 10, 1.1);
};

ACTION.shard_storm = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const p = power(player);

  // 周囲の金属は「弾数」。剥がさないので地形は無傷のまま。
  const ammo = Math.min(4, scanMetal(dim, at, 10, 8).length);
  const shots = 10 + ammo;
  const damage = (9 + ammo * 0.5) * p;

  chord(dim, at, [[SOUND.shard, 0, { volume: 0.8, pitch: 1.2 }],
                  [SOUND.mag_release, 3, { volume: 0.5, pitch: 1.7 }]]);
  shake(player, 0.14, 0.20, "rotational");

  let fired = 0;
  let cursor = 0;
  const step = () => {
    if (fired >= shots || !isTransformed(player)) return;
    const eye = eyeOf(player);
    const dir = player.getViewDirection();
    // 自分を巡る水平の鉄片環。そこから 1 発ずつ抜けて飛ぶ（§5-5）。
    const a = (fired / shots) * Math.PI * 4;
    const muzzle = {
      x: eye.x + Math.cos(a) * 1.3, y: eye.y - 0.2, z: eye.z + Math.sin(a) * 1.3,
    };
    fx(dim, FX.shard_spark, muzzle);

    // 面制圧: 標的を順に回す。単体に集中させない。
    const targets = enemiesNear(player, 18).filter((e) => {
      const to = normalise(sub(above(e, 0.9), eye));
      return to.x * dir.x + to.y * dir.y + to.z * dir.z > 0.0;
    });
    let aim;
    if (targets.length) {
      const t = targets[cursor++ % targets.length];
      aim = normalise(sub(above(t, 0.9), muzzle));
    } else {
      const spread = 0.16;
      aim = normalise({
        x: dir.x + (Math.random() - 0.5) * spread,
        y: dir.y + (Math.random() - 0.5) * spread * 0.6,
        z: dir.z + (Math.random() - 0.5) * spread,
      });
    }
    launchCapped(player, muzzle, aim, 2.0, damage);
    if (fired % 3 === 0) {
      sound(dim, SOUND.shard, at, { volume: 0.5, pitch: 1.2 + Math.random() * 0.5 });
    }
    fired++;
    system.runTimeout(step, 5);
  };
  step();
  return true;
};

// --- 6. 磁力障壁 — 据え置きの被弾軽減 ----------------------------------------
const BARRIER_TICKS = 120;      // 固定。段階で伸ばすと段階 3 が硬すぎる

CHARGE.barrier = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.5, pitch: 1.3 });
};

ACTION.barrier = (player) => {
  const dim = player.dimension;
  const at = player.location;

  const dome = safe(() => dim.spawnEntity(ENTITY.barrier_dome,
    { x: at.x, y: at.y + 0.2, z: at.z }));
  setProp(player, PROP.barrier, system.currentTick + BARRIER_TICKS);
  fxSphere(dim, FX.barrier_hex, { x: at.x, y: at.y + 1.4, z: at.z }, 3.2, 22);
  chord(dim, at, [[SOUND.barrier, 0, { volume: 1.0, pitch: 1.2 }],
                  [SOUND.mag_charge, 4, { volume: 0.6, pitch: 1.6 }]]);
  safe(() => player.addEffect("resistance", BARRIER_TICKS, { amplifier: 2, showParticles: false }));

  if (!dome) return true;
  let left = BARRIER_TICKS;
  const follow = system.runInterval(() => {
    left -= 4;
    if (left <= 0 || !isTransformed(player)) {
      safe(() => dome.remove());
      setProp(player, PROP.barrier, 0);
      fx(dim, FX.barrier_break, player.location);
      sound(dim, SOUND.barrier_hit, player.location, { pitch: 1.4, volume: 0.6 });
      system.clearRun(follow);
      return;
    }
    safe(() => dome.teleport({ x: player.location.x, y: player.location.y + 0.2, z: player.location.z }));
    const shots = safe(() => dim.getEntities({
      location: player.location, maxDistance: 3.6,
    })) ?? [];
    for (const s of shots) {
      if (!s.typeId?.includes("arrow") && !s.typeId?.includes("fireball")
          && !s.typeId?.includes("_bolt") && !s.typeId?.includes("beam")) continue;
      const away = normalise(sub(s.location, player.location));
      safe(() => s.applyImpulse(scale(away, 1.4)));
      // 被弾した六角だけ白く割れる（§5-5）
      fx(dim, FX.barrier_break, s.location);
      sound(dim, SOUND.barrier_hit, s.location, { volume: 0.5, pitch: 1.8 });
    }
  }, 4);
  return true;
};

// --- 7. 鋼鉄拘束 — 単体拘束 --------------------------------------------------
//  旧実装は cage と相手を **相互に teleport** していて座標が発散し、
//  プレイヤー相手だとカメラが暴れた。**檻だけが追う**、拘束は効果で表す。
const BIND_TICKS = 100;

CHARGE.iron_bind = (player) => {
  const target = lookTarget(player, 24);
  if (target.entity) fieldBundle(player.dimension, eyeOf(player), above(target.entity, 0.9));
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.5, pitch: 0.9 });
};

ACTION.iron_bind = (player) => {
  const dim = player.dimension;
  const target = lookTarget(player, 24);
  if (!target.entity || !hostile(target.entity, player)) {
    tell(player, tr("msg.no_target"));
    return false;
  }
  const e = target.entity;
  const cage = safe(() => dim.spawnEntity(ENTITY.iron_cage, e.location));
  safe(() => e.addTag(TAG.bound));
  safe(() => e.addEffect("slowness", BIND_TICKS, { amplifier: 6, showParticles: false }));
  safe(() => e.addEffect("weakness", BIND_TICKS, { amplifier: 2, showParticles: false }));
  // levitation 0 は「浮かせる」ためではなく **落下と移動を殺す** ために掛ける。
  safe(() => e.addEffect("levitation", BIND_TICKS, { amplifier: 0, showParticles: false }));

  // 決め絵: 足元から縦の鉄格子が編み上がり、交点で溶接火花（§5-5）
  const base = { x: e.location.x, y: e.location.y, z: e.location.z };
  for (let i = 0; i < 5; i++) {
    system.runTimeout(() => {
      fxRing(dim, FX.bind_weld, base, 1.15, 6, 0.35 * i);
      fxRing(dim, FX.mag_spark, base, 1.15, 3, 0.35 * i + 0.1);
      sound(dim, SOUND.metal_hit, base, { volume: 0.4, pitch: 1.1 + i * 0.12 });
    }, i * 2);
  }
  chord(dim, e.location, [[SOUND.bind, 0, { volume: 1.0, pitch: 0.8 }],
                          [SOUND.metal_hit, 6, { volume: 0.7, pitch: 1.1 }]]);

  if (!cage) return true;
  let left = BIND_TICKS;
  const keep = system.runInterval(() => {
    left -= 5;
    if (left <= 0 || !safe(() => e.isValid?.() !== false)) {
      safe(() => cage.remove());
      safe(() => e.removeTag(TAG.bound));
      fx(dim, FX.barrier_break, cage.location);
      system.clearRun(keep);
      return;
    }
    safe(() => cage.teleport(e.location));      // 追うのは檻だけ
    fx(dim, FX.bind_weld, e.location);
  }, 5);
  return true;
};

// --- 8. 磁気圧壊 — 金属装備者への特効 ----------------------------------------
CHARGE.crush = (player) => {
  const target = lookTarget(player, 22);
  if (target.entity) fieldBundle(player.dimension, eyeOf(player), above(target.entity, 0.9));
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.7, pitch: 0.75 });
};

ACTION.crush = (player) => {
  const dim = player.dimension;
  const target = lookTarget(player, 22);
  if (!target.entity || !hostile(target.entity, player)) {
    tell(player, tr("msg.no_target"));
    return false;
  }
  const e = target.entity;
  const p = power(player);
  const metal = metalOf(e);

  if (metal <= 0) {
    // 金属を持たない相手には通らない。これが役割の輪郭になる。
    refuse(player, e);
    strikeDamage(player, e, 3 * p);
    return true;
  }

  const damage = (8 + metal * 6) * p;
  // 決め絵: 輪郭が内へ凹み、赤 chevron が内向きに収束（§5-5）
  for (let i = 3; i >= 1; i--) {
    system.runTimeout(() => fxSphere(dim, FX.crush_implode, above(e, 1.0), i * 0.75, 8),
                      (3 - i) * 2);
  }
  fx(dim, FX.crush_blood, above(e, 1.0));
  chord(dim, e.location, [[SOUND.crush, 0, { volume: 1.2, pitch: 0.7 }],
                          [SOUND.metal_hit, 3, { volume: 0.9, pitch: 0.9 }]]);
  strikeDamage(player, e, damage);
  hitstop(e, 8);
  shake(player, 0.14, 0.20, "rotational");
  shakeNearby(dim, e.location, 10, 0.28, 0.20);

  // センチネルは装甲を握り潰されるとコアが出る。剥いでから殴る二段構え（§7-5）。
  if (hasFamily(e, FAMILY.sentinel)) expose(dim, e);
  return true;
};

/** コア露出。20 秒だけ物理が 2 倍通る。 */
export function expose(dim, entity) {
  if (safe(() => entity.hasTag(T_EXPOSED)) === true) return;
  safe(() => entity.addTag(T_EXPOSED));
  fx(dim, FX.sentinel_spark, above(entity, 1.6));
  fx(dim, FX.core_break, above(entity, 1.2));
  sound(dim, SOUND.metal_hit, entity.location, { volume: 1.0, pitch: 0.6 });
  system.runTimeout(() => safe(() => entity.removeTag(T_EXPOSED)), 400);
}

// --- 9. 大地隆起 — 地形攻撃 ＋ 磁力採掘 --------------------------------------
//  磁力視が効いている間は **採掘** になる。鉱石は母岩に置き換えるので、
//  穴が一つも空かないまま中身だけが手に入る。透視 → 抜く、の二段。
const ORE_YIELD = {
  "minecraft:iron_ore": ["minecraft:stone", "minecraft:raw_iron", 2],
  "minecraft:deepslate_iron_ore": ["minecraft:deepslate", "minecraft:raw_iron", 2],
  "minecraft:gold_ore": ["minecraft:stone", "minecraft:raw_gold", 2],
  "minecraft:deepslate_gold_ore": ["minecraft:deepslate", "minecraft:raw_gold", 2],
  "minecraft:copper_ore": ["minecraft:stone", "minecraft:raw_copper", 3],
  "minecraft:deepslate_copper_ore": ["minecraft:deepslate", "minecraft:raw_copper", 3],
  "minecraft:ancient_debris": ["minecraft:netherrack", "minecraft:ancient_debris", 1],
  "minecraft:redstone_ore": ["minecraft:stone", "minecraft:redstone", 4],
};

CHARGE.uprising = (player) => {
  const dim = player.dimension;
  const centre = forward(player.location, player.getViewDirection(), 6);
  // **先に地面が割れ**、遅れて土柱。この順序が命（§5-5）。
  fxRing(dim, FX.quake_crack, centre, 2.4, 10, 0.05);
  sound(dim, SOUND.mag_charge, centre, { volume: 0.6, pitch: 0.7 });
};

ACTION.uprising = (player) => {
  const dim = player.dimension;
  const at = player.location;
  const dir = player.getViewDirection();
  const p = power(player);
  const centre = forward({ x: at.x, y: at.y, z: at.z }, dir, 6);
  const mining = num(player, PROP.sight, 0) > system.currentTick;

  chord(dim, centre, [[SOUND.uprising, 0, { volume: 1.3, pitch: 0.75 }],
                      [SOUND.metal_hit, 8, { volume: 0.9, pitch: 0.8 }]]);
  shake(player, 0.14, 0.20, "rotational");
  shakeNearby(dim, centre, 16, 0.34, 0.20);
  fxRing(dim, FX.uprising_pillar, centre, 2.6, 8, 0.2);

  // 半径 9。8 だと step が 1 に落ちて 2,109 回の getBlock になる（上表）。
  const found = scanMetal(dim, centre, 9, 20);

  if (mining) {
    // --- 磁力採掘: 鉱脈を壊さず、中身だけ抜く
    let taken = 0;
    for (const m of found) {
      if (taken >= 12) break;
      const recipe = ORE_YIELD[m.typeId];
      if (!recipe) continue;
      const block = safe(() => dim.getBlock({ x: m.x, y: m.y, z: m.z }));
      if (!block || block.typeId !== m.typeId) continue;
      const [matrix, drop, amount] = recipe;
      if (!safe(() => { block.setType(matrix); return true; })) continue;
      const spot = { x: m.x + 0.5, y: m.y + 0.5, z: m.z + 0.5 };
      fx(dim, FX.metal_rip, spot);
      safe(() => dim.spawnItem(new ItemStack(drop, amount), spot));
      taken++;
    }
    if (taken) {
      pullItems(dim, centre, 12, { x: at.x, y: at.y + 1.0, z: at.z }, 1.2);
      system.runTimeout(() => pullItems(dim, centre, 14, at, 1.4), 10);
      sound(dim, SOUND.metal_hit, at, { volume: 0.9, pitch: 1.4 });
      tell(player, { rawtext: [{ translate: "marvel.msg.scan" }, { text: ` §b${taken}` }] });
    } else {
      tell(player, tr("msg.no_target"));
    }
    return true;
  }

  // --- 地形攻撃: 鉄塊の柱を突き上げる。剥がした穴は 8 秒で必ず塞がる。
  let raised = 0;
  for (const m of found) {
    if (raised >= 8) break;
    const shard = ripTemp(dim, { x: m.x, y: m.y, z: m.z }, player.id);
    if (!shard) continue;
    safe(() => shard.applyImpulse({
      x: (Math.random() - 0.5) * 0.3, y: 1.4, z: (Math.random() - 0.5) * 0.3,
    }));
    system.runTimeout(() => safe(() => shard.remove()), 70);
    raised++;
  }
  for (const e of enemiesNear(player, 7, centre)) {
    strikeDamage(player, e, (14 + raised * 1.6) * p);
    knock(e, { x: 0, y: 1, z: 0 }, 0.5, 1.35);
    fx(dim, FX.debris_chunk, above(e, 0.4));
  }
  return true;
};

// --- 10. EMP — ダメージ 0 の機械専用スタン -----------------------------------
CHARGE.emp = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.6, pitch: 1.9 });
};

ACTION.emp = (player) => {
  const dim = player.dimension;
  const at = player.location;

  chord(dim, at, [[SOUND.emp, 0, { volume: 1.2, pitch: 1.3 }],
                  [SOUND.mag_release, 8, { volume: 0.8, pitch: 1.9 }]]);
  shake(player, 0.14, 0.20, "rotational");
  // 決め絵: 無彩色に近い薄い波紋が一瞬で 26 まで。細い二重リング（§5-5）。
  for (const r of [7, 13, 20, 26]) {
    system.runTimeout(() => {
      fxRing(dim, FX.emp_wave, at, r, Math.min(28, 8 + r), 0.6);
      fxRing(dim, FX.emp_wave, at, r * 0.92, Math.min(24, 6 + r), 1.4);
    }, Math.round((r - 7) * 0.35));
  }

  let machines = 0;
  for (const e of enemiesNear(player, 26)) {
    const machine = hasFamily(e, FAMILY.sentinel) || hasFamily(e, FAMILY.mrd);
    if (!machine) continue;
    // フェーズ 3 のプライムは EMP が効かない（§7-5）
    if (safe(() => e.hasTag(T_JAMMED)) === true) { fx(dim, FX.mag_glyph, above(e, 2.0)); continue; }
    // **ダメージは 0**。止めるだけの技という輪郭をぼかさない。
    safe(() => e.addTag(TAG.emp));
    safe(() => e.addEffect("slowness", 160, { amplifier: 5, showParticles: false }));
    safe(() => e.addEffect("weakness", 160, { amplifier: 3, showParticles: false }));
    safe(() => e.addEffect("mining_fatigue", 160, { amplifier: 3, showParticles: false }));
    system.runTimeout(() => safe(() => e.removeTag(TAG.emp)), 160);
    fx(dim, FX.emp_arc, above(e, 1.2));
    fx(dim, FX.sentinel_spark, above(e, 1.6));
    if (hasFamily(e, FAMILY.sentinel)) expose(dim, e);
    machines++;
  }
  if (!machines) tell(player, tr("msg.no_target"));
  return true;
};

// --- 11. 磁極反転 — 対環境 ---------------------------------------------------
//  敵ではなく **矢・落下アイテム・TNT・トロッコ** が天井へ吸われる。
//  飛来物が全部逸れる防御であって、拘束ではない（それは iron_bind の役）。
const POLARITY_TICKS = 120;
const FLYING_JUNK = ["arrow", "fireball", "snowball", "egg", "trident",
                     "shulker_bullet", "small_fireball", "dragon_fireball",
                     "wither_skull", "llama_spit", "_bolt", "beam"];
const HEAVY_JUNK = ["tnt", "minecart", "boat", "falling_block", "item"];

CHARGE.polarity = (player) => {
  sound(player.dimension, SOUND.mag_charge, player.location, { volume: 0.6, pitch: 1.1 });
};

ACTION.polarity = (player) => {
  const dim = player.dimension;
  const at = player.location;

  chord(dim, at, [[SOUND.polarity, 0, { volume: 1.0, pitch: 0.8 }],
                  [SOUND.mag_charge, 6, { volume: 0.8, pitch: 1.7 }]]);
  shake(player, 0.14, 0.20, "rotational");
  // 決め絵: 空中に格子が浮き、周囲の物が「同時に」ふわりと上へ（§5-5）
  for (let y = 1; y <= 4; y++) {
    fxRing(dim, FX.polarity_field, at, 4.0 + y * 0.9, 12, y * 1.5);
  }

  let left = POLARITY_TICKS;
  const field = system.runInterval(() => {
    left -= 4;
    if (left <= 0 || !isTransformed(player)) {
      system.clearRun(field);
      fxRing(dim, FX.levitate_dust, player.location, 4.0, 10, 0.2);
      return;
    }
    const here = player.location;
    const junk = safe(() => dim.getEntities({ location: here, maxDistance: 14 })) ?? [];
    for (const e of junk) {
      const id = e.typeId ?? "";
      if (e.id === player.id) continue;
      const light = FLYING_JUNK.some((k) => id.includes(k));
      const heavy = !light && HEAVY_JUNK.some((k) => id.includes(k));
      if (!light && !heavy) continue;
      safe(() => e.applyImpulse({
        x: (Math.random() - 0.5) * 0.1,
        y: light ? 0.9 : 0.42,
        z: (Math.random() - 0.5) * 0.1,
      }));
      fx(dim, FX.tk_lift, e.location);
    }
    if (left % 20 === 0) fxRing(dim, FX.polarity_field, here, 5.5, 10, 2.5);
  }, 4);
  return true;
};

// --- 12. 磁気飛行 — 三次元移動 -----------------------------------------------
//  段階 1 は **跳躍**、段階 2 以降が **真の飛行**（§7-4）。
ACTION.flight = (player) => {
  const dim = player.dimension;
  const stage = stageOf(player);

  if (stage < 2) {
    const dir = player.getViewDirection();
    selfPush(player, dir.x, dir.z, 1.5, 1.05);
    safe(() => player.addEffect("slow_falling", 90, { amplifier: 0, showParticles: false }));
    fxRing(dim, FX.levitate_dust, player.location, 1.4, 10, 0.1);
    sound(dim, SOUND.flight, player.location, { volume: 0.9, pitch: 1.3 });
    return true;
  }

  const flying = num(player, PROP.flying, 0) === 1;
  if (flying) {
    setProp(player, PROP.flying, 0);
    sound(dim, SOUND.revert, player.location, { pitch: 1.4, volume: 0.6 });
    return true;
  }
  setProp(player, PROP.flying, 1);
  // 離陸の瞬間だけ足元に円い塵（§5-5）。飛行中の帯は mobility.js が出す。
  fxRing(dim, FX.levitate_dust, player.location, 1.4, 10, 0.1);
  chord(dim, player.location, [[SOUND.flight, 0, { volume: 1.0, pitch: 1.1 }],
                               [SOUND.mag_charge, 4, { volume: 0.5, pitch: 1.6 }]]);
  safe(() => player.applyImpulse({ x: 0, y: 0.9, z: 0 }));
  return true;
};

// --- 13. 鋼鉄の玉座 — 足場設置 -----------------------------------------------
//  移動そのものは flight の役。こちらは **置いて残る**（建築・拠点）。
const THRONE_LIMIT = 4;
const thrones = new Map();

CHARGE.throne = (player) => {
  sound(player.dimension, SOUND.metal_hit, player.location, { volume: 0.5, pitch: 1.6 });
};

ACTION.throne = (player) => {
  const dim = player.dimension;
  const dir = player.getViewDirection();
  // 足元ではなく **視線の少し先** に置く。空中足場として繋げられる。
  const at = forward(player.location, { x: dir.x, y: 0, z: dir.z }, 1.6);
  const platform = safe(() => dim.spawnEntity(ENTITY.steel_platform,
    { x: at.x, y: player.location.y + (dir.y > 0.35 ? 1.6 : -0.2), z: at.z }));
  if (!platform) return false;

  // 足元へ鉄板が音を立てて集まり、土埃が外へ逃げる（§5-5）
  fxRing(dim, FX.throne_dust, at, 2.0, 12, 0.1);
  fxRing(dim, FX.debris_chunk, at, 1.2, 6, 0.5);
  chord(dim, at, [[SOUND.metal_hit, 0, { volume: 0.9, pitch: 0.8 }],
                  [SOUND.metal_hit, 4, { volume: 0.6, pitch: 1.1 }],
                  [SOUND.mag_charge, 6, { volume: 0.7, pitch: 1.3 }]]);
  shake(player, 0.08, 0.14, "rotational");

  const mine = thrones.get(player.id) ?? [];
  mine.push(platform);
  // 置きっぱなしで世界を埋めないよう、古いものから消す。
  while (mine.length > THRONE_LIMIT) {
    const old = mine.shift();
    fx(dim, FX.debris_dust, old.location);
    safe(() => old.remove());
  }
  thrones.set(player.id, mine);
  system.runTimeout(() => {
    const list = thrones.get(player.id);
    if (list) thrones.set(player.id, list.filter((e) => e.id !== platform.id));
    fx(dim, FX.debris_dust, platform.location);
    safe(() => platform.remove());
  }, 1200);
  return true;
};

// --- 14. 磁力視 — 索敵 ＋ 与ダメ +20% ----------------------------------------
ACTION.sight = (player) => {
  const dim = player.dimension;
  const duration = 200 + stageOf(player) * 60;
  setProp(player, PROP.sight, system.currentTick + duration);
  const found = revealMetal(player, 22);
  safe(() => player.addEffect("night_vision", duration + 40, { amplifier: 0, showParticles: false }));
  // 遠景を沈め金属だけ浮かせる fog は **mobility.js が押して降ろす**。
  // ここで押すと層が二重になり、片方が永久に残る。
  sound(dim, SOUND.sight, player.location, { volume: 0.8, pitch: 1.4 });
  // 波紋は自分から **一度だけ**（§5-5）。毎 tick 撒くと索敵の緊張が消える。
  for (const r of [3, 8, 14, 20]) {
    system.runTimeout(() => fxRing(dim, FX.sight_ping, player.location, r, 10 + r, 0.8),
                      Math.round(r * 0.6));
  }
  tell(player, { rawtext: [{ translate: "marvel.msg.scan" }, { text: ` §b${found}` }] });
  return true;
};

// --- 15. 磁界の棺（必殺技）---------------------------------------------------
//  animation.marvel.tech.sphere は L=3.00 秒。
//    溜め 0.00–1.50 / **完全静止 1.50–1.80** / **撃発 1.88** / 戻り 2.06
//  つまり tick では 溜め 0–30 / 静止 30–36 / 撃発 38 / 炸裂 40。
//  スクリプトは **この tick 表に釘で留める**。ここがずれると必殺が必殺でなくなる。
const SPH = {
  charge: 2, still: 30, flash: 30, collapse: 38, detonate: 40,
  debris: 41, white: 43, clear: 70,
};

ACTION.sphere = (player) => {
  const dim = player.dimension;
  const p = power(player);
  const centreOf = () => ({
    x: player.location.x, y: player.location.y + 3.4, z: player.location.z,
  });

  // --- tick 0: 暗転と fog。まだ音は「充電」だけ。
  fog(player, "marvel:sphere", "marvel_sphere");
  fade(player, { red: 0.23, green: 0.11, blue: 0.35 }, 0.06, 0.05, 0.30);
  chord(dim, player.location, [
    [SOUND.sphere_charge, 0, { volume: 1.4, pitch: 0.8 }],
    [SOUND.mag_charge, 10, { volume: 1.0, pitch: 1.2 }],
    [SOUND.mag_charge, 24, { volume: 1.0, pitch: 1.5 }],
  ]);

  const sphere = safe(() => dim.spawnEntity(ENTITY.ruin_sphere, centreOf()));
  const dragged = [];
  let tick = 0;

  // 走査は 38 tick の溜めに撒く。一括だと r=40 で 1 tick 4,169 回の getBlock。
  scanMetalSpread(dim, player.location, 40, 48, (found) => {
    // 溜めが終わってから結果が返ってきたら、もう剥がさない。
    // 炸裂した後に穴だけ開くのが一番みっともない。
    const late = tick >= SPH.still;
    let ripped = 0;
    for (const m of found) {
      const spot = { x: m.x + 0.5, y: m.y + 0.5, z: m.z + 0.5 };
      if (late || ripped >= 24) {            // ここから先は「光るだけ」
        fx(dim, FX.metal_glint, spot);
        continue;
      }
      const shard = ripTemp(dim, { x: m.x, y: m.y, z: m.z }, player.id);
      if (shard) { dragged.push(shard); ripped++; }
    }
    if (!late) pullItems(dim, player.location, 40, centreOf(), 1.2);
  });

  const run = system.runInterval(() => {
    tick++;
    const centre = centreOf();
    safe(() => sphere?.teleport(centre));

    // ---- 収束 (2–30): 半径 3.6 -> 2.0 へ絞り込む
    if (tick >= SPH.charge && tick < SPH.still) {
      const r = Math.max(0.6, 3.6 - tick * 0.055);
      fxSphere(dim, FX.sphere_orbit, centre, r, 6);
      if (tick % 6 === 0) fx(dim, FX.sphere_core, centre);
      for (const s of dragged) {
        if (!safe(() => s.isValid?.() !== false)) continue;
        drag(s, centre, 1.1, 0.3);
        if (tick % 4 === 0) fx(dim, FX.metal_glint, s.location);
      }
      if (tick % 3 === 0) {
        for (const e of enemiesNear(player, 30)) {
          if (metalOf(e) <= 0) continue;
          drag(e, centre, 0.55, 0.2);
          fieldBundle(dim, above(e, 0.9), centre);
        }
      }
      if (tick === 27) shake(player, 0.35, 0.40, "rotational");
      else if (tick % 5 === 0) shake(player, 0.10 + tick * 0.004, 0.25, "rotational");
    }

    // ---- 完全静止 (30–36): 全エミッタを止める。**この無音が効く**
    if (tick === SPH.flash) {
      title(player, tr("title.ultimate"), tr("title.ultimate_sub"), 3, 34, 12);
      fx(dim, FX.mag_spark, centre);            // 白い一枚だけ
      for (const e of enemiesNear(player, 24)) hitstop(e, 10);
    }

    // ---- 撃発 (38): 内向きに潰れる
    if (tick === SPH.collapse) {
      fx(dim, FX.sphere_collapse, centre);
      fxSphere(dim, FX.sphere_collapse, centre, 2.2, 16);
      sound(dim, SOUND.mag_release, centre, { volume: 1.4, pitch: 0.5 });
      for (const s of dragged) {
        if (!safe(() => s.isValid?.() !== false)) continue;
        safe(() => s.teleport(centre));
      }
    }

    // ---- 炸裂 (40)
    if (tick === SPH.detonate) {
      fx(dim, FX.sphere_detonate, centre);
      chord(dim, centre, [
        [SOUND.sphere_blast, 0, { volume: 1.6, pitch: 0.7 }],
        [SOUND.repulse, 2, { volume: 1.2, pitch: 0.8 }],
        [SOUND.metal_hit, 5, { volume: 1.0, pitch: 0.6 }],
      ]);
      shake(player, 0.35, 0.40, "rotational");
      shakeNearby(dim, centre, 40, 0.7, 0.20);
      // 厚い衝撃 + 縦リング 2 枚（§5-5）
      fxRing(dim, FX.mag_ring_wide, centre, 6.0, 24, -1.0);
      const view = player.getViewDirection();
      fxRingUpright(dim, FX.sphere_detonate, centre, 5.0, 18, view);
      fxRingUpright(dim, FX.sphere_detonate, centre, 5.0, 18,
                    { x: view.z, y: 0, z: -view.x });

      for (const e of enemiesNear(player, 22, centre)) {
        const metal = metalOf(e);
        const d = distance(e.location, centre);
        strikeDamage(player, e, (60 + metal * 20) * p * Math.max(0.25, 1 - d / 24));
        knock(e, normalise(sub(e.location, centre)), 3.2, 1.1);
        fx(dim, FX.crush_implode, above(e, 1.0));
      }
    }

    // ---- 破片は通常合成。ここだけが最後まで画面に残ってよい層。
    if (tick === SPH.debris) {
      fxSphere(dim, FX.shard_burst, centre, 3.0, 30);
      fxScatter(dim, FX.debris_chunk, centre, 20, 4.0);
      for (const s of dragged) {
        if (!safe(() => s.isValid?.() !== false)) continue;
        safe(() => s.applyImpulse({
          x: (Math.random() - 0.5) * 3.4, y: Math.random() * 1.6,
          z: (Math.random() - 0.5) * 3.4,
        }));
        system.runTimeout(() => safe(() => s.remove()), 50);
      }
      safe(() => sphere?.remove());
    }

    if (tick === SPH.white) {
      fade(player, { red: 1.0, green: 0.95, blue: 0.98 }, 0.05, 0.05, 0.80);
      fogPop(player, "marvel_sphere");
    }

    // ---- 余韻: 塵だけを 2 秒。光り物はゼロ。
    if (tick > SPH.white && tick % 6 === 0) {
      fxScatter(dim, FX.debris_dust, centre, 4, 5.0);
      fxScatter(dim, FX.mag_dust, player.location, 3, 3.0);
    }
    if (tick >= SPH.clear) {
      system.clearRun(run);
      fogPop(player, "marvel_sphere");
    }
  }, 1);
  return true;
};

// ===========================================================================
//  6. 発動口
// ===========================================================================
/** フェーズ 3 のプライムは、プレイヤーの再充填を 1.5 倍に伸ばす（§7-5）。 */
function cdOf(player, spec) {
  const jam = safe(() => player.hasTag(T_JAMMED)) === true ? 1.5 : 1.0;
  return Math.round(spec.cd * jam);
}

/**
 * 保持系は「効果が続く間」構えたままにする（§4-2）。それ以外はクリップ長 + 余韻。
 *
 * ただし **磁力視だけは持続に従わせない**。効果は 19 秒あるが、
 * tech clip は `override_previous_animation: true` なので、その間ずっと
 * 歩行が上書きされて棒立ちで滑ることになる。
 * 磁力視が続いていることは fog（一人称）と ping（三人称）が見せるので、
 * 構えは「視た瞬間」だけでよい。
 */
function holdOf(player, key, stage) {
  if (!(key in SUSTAIN)) return holdFor(key, stage);
  if (key === "barrier") return BARRIER_TICKS;      // 6 秒。構えている絵が正しい
  if (key === "sight") return holdFor(key, stage) + 20;
  // 段階 1 の飛行は「跳躍」なので一度きり。段階 2 以降は飛んでいる間ずっと
  // mobility.js が掛け直す。
  if (stage < 2) return holdFor(key, stage);
  return num(player, PROP.flying, 0) === 1 ? 20 : 60;
}

export function useTechnique(player, techKey) {
  const spec = TECH[techKey];
  if (!spec) return false;
  if (!isTransformed(player)) {
    tell(player, tr("msg.no_power"));
    return false;
  }
  const stage = stageOf(player);
  if (stage < spec.stage) {
    tell(player, tr("msg.locked"));
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 0.5 });
    return false;
  }
  if (!cooldowns.ready(player.id, techKey)) {
    const left = Math.ceil(cooldowns.remaining(player.id, techKey) / 20);
    tell(player, { rawtext: [{ translate: "marvel.msg.cooldown" }, { text: ` §7${left}s` }] });
    return false;
  }
  if (magOf(player) < spec.cost) {
    tell(player, tr("msg.no_mag"));
    sound(player.dimension, SOUND.ui_select, player.location, { pitch: 0.4 });
    return false;
  }

  // 1. 三人称の構えへ差し替える（＝技クリップの再生）
  pose(player, spec.form, holdOf(player, techKey, stage));
  setProp(player, PROP.tech, techKey);

  // 2. 予兆。まだ何も起きない一拍が、撃発を撃発にする。
  safe(() => CHARGE[techKey]?.(player));

  // 3. 撃発 t_d ちょうどで効果を出す。絵と効果はここで初めて一致する。
  //
  //    必殺だけは別。ACTION.sphere は「溜め → 静止 → 撃発 → 炸裂」の
  //    3 秒の段取りそのもので、内部の tick は **クリップの絶対時刻**
  //    （静止 30 / 撃発 38 / 炸裂 40）。ここで撃発ぶんの 38 tick を
  //    足してから走らせると、段取り全体が 1.9 秒後ろへずれて、
  //    静止が終わった後に暗転が始まる。だからクリップの頭から、
  //    **runTimeout を挟まずに** 回す。1 tick 遅らせるだけで
  //    撃発が 38 -> 39 になり、0.05 秒の遅れが必殺の切れ味を削る。
  if (spec.ultimate) {
    safe(() => ACTION[techKey]?.(player));
  } else {
    system.runTimeout(() => {
      safe(() => ACTION[techKey]?.(player));
    }, delayFor(techKey));
  }

  cooldowns.set(player.id, techKey, cdOf(player, spec));
  spendMag(player, spec.cost);
  return true;
}

export function techniqueOf(itemId) {
  for (const key of TECH_ORDER) {
    if (TECH[key]?.item === itemId) return key;
  }
  return undefined;
}

/** 毎 tick: 地形の戻しと磁力ジップ。 */
export function tickTechniques() {
  tickRestore();
  tickZip();
}

/** 変身解除・死亡時の後始末。押しっぱなしの fog を残さない。 */
export function clearTechniqueState(player) {
  zipping.delete(player.id);
  // 押したのが自分の層（必殺）だけなので、pop するのもそれだけ。
  // field / sight は mobility.js が状態ごと持っている。
  fogPop(player, "marvel_sphere");
  const mine = thrones.get(player.id);
  if (mine) {
    for (const e of mine) safe(() => e.remove());
    thrones.delete(player.id);
  }
}

/** そのブロックが磁力に応えるか（UI からの問い合わせ用）。 */
export function isMagnetic(typeId) {
  return (MAGNETIC_BLOCKS[typeId] ?? 0) > 0;
}
