// 磁力エンジン / the magnetism engine
//
// このアドオンの根っこ。「何が金属か」「どれだけ強く効くか」を一箇所で決め、
// 技はすべてこの関数群の上に乗る。
//
// 走査コストについて（偽の Dimension を用意して getBlock の回数を実測した）
//   以前の間引き（r<=8:1 / r<=20:2 / それ以上:4）では
//     r=20 -> 4,169 回   r=40 -> 4,169 回
//   が 1 tick に丸ごと乗っていた。しかも打ち切りの break が最内の dz ループ
//   しか抜けないので、上限は実際には効いていなかった。
//
//   いまは中心からの相対座標を **近い順に並べた表** にして一本のループで辿る。
//     * 半径 6 までは 1 ブロック刻み（目の前の鉄柵を取りこぼさない）
//     * その外は半径に応じた粗い刻み（遠くは「塊」が分かればよい）
//     * 必要数が揃ったら本当に return する
//   実測した最悪値（金属がまったく無い場合の getBlock 回数）:
//     r=8 -> 2,109   r=12 -> 1,727   r=20 -> 2,116   r=40 -> 2,147
//   金属だらけの場所では早期に打ち切られ、いずれの半径でも 288 回で済む。
//   表は (半径, 刻み) ごとに一度だけ作って使い回す（初回のみ約 6ms、以降 0）。
//   さらに精度が欲しい必殺技は `scanMetalAsync()` を使うと
//   `system.runJob` で 800 回/tick に割れる（r=40 で約 5,000 回 = 約 7 tick）。
import { world, system, ItemStack } from "@minecraft/server";
import {
  MAGNETIC_BLOCKS, MAGNETIC_ITEMS, IMMUNE_ITEMS, FAMILY, FX, ENTITY,
} from "./config.js";
import {
  clamp, forward, hasFamily, normalise, parsePosKey, posKey,
  readJson, safe, sub, writeJson,
} from "./util.js";
import { fx, fxTrail, selfPush } from "./effects.js";

const EQUIP_SLOTS = ["Head", "Chest", "Legs", "Feet", "Mainhand", "Offhand"];

/** そのブロックが磁力に応えるか。0 なら無反応。 */
export function blockStrength(typeId) {
  return MAGNETIC_BLOCKS[typeId] ?? 0;
}

/** 装備品の磁化強度。アダマンチウムだけは 0（唯一の対抗手段）。 */
export function itemStrength(typeId) {
  if (!typeId) return 0;
  for (const immune of IMMUNE_ITEMS) if (typeId.includes(immune)) return 0;
  for (const [material, factor] of Object.entries(MAGNETIC_ITEMS)) {
    if (typeId.includes(material)) return factor;
  }
  return 0;
}

/** そのエンティティが身につけている金属の総量（0 ～ 約 6）。 */
export function metalOn(entity) {
  let total = 0;
  const eq = safe(() => entity.getComponent("minecraft:equippable"));
  if (eq) {
    for (const slot of EQUIP_SLOTS) {
      const item = safe(() => eq.getEquipment(slot));
      if (item) total += itemStrength(item.typeId);
    }
  }
  // センチネルは全身が金属。文字通り彼の玩具になる。
  if (hasFamily(entity, FAMILY.sentinel)) total += 4.0;
  if (hasFamily(entity, FAMILY.mrd)) total += 1.2;
  return total;
}

/**
 * 「掴みやすさ」の倍率。
 *
 * 金属を着ている相手ほど強く引かれる、という差が体感できないと
 * 磁力である意味がない。素手の相手は 1.0 のまま（弱くはしない）、
 * 全身金属のセンチネルは 1.9 倍まで持ち上がる。
 */
export function gripFactor(entity) {
  return 1 + clamp(metalOn(entity), 0, 4) * 0.225;
}

// ---------------------------------------------------------------- 磁化ペイント
// sneak + attract で普通のブロックを「磁化」して登録する。石の砦でも
// 自分で塗れば磁力戦場になる、という遊び（DIRECTION §7-3）。
//
// 台帳はワールドの動的プロパティに載せる。プレイヤーごとに 64 個まで、
// 全体で 256 個まで。上限を持たないと保存が黙って落ちる。
const PAINT_PROP = "marvel:painted";
const PAINT_PER_PLAYER = 64;
const PAINT_TOTAL = 256;
const PAINT_STRENGTH = 0.7;

// 保存は「ディメンション名」ではなく番号で持つ。台帳が 256 行あると
// 名前をそのまま書くだけで 5 KB 近くを食い、動的プロパティの上限に当たる。
const DIMS = ["minecraft:overworld", "minecraft:nether", "minecraft:the_end"];
const dimCode = (id) => Math.max(0, DIMS.indexOf(id));
const dimName = (code) => DIMS[code] ?? DIMS[0];

//: "dimId|x,y,z" -> { strength, owner, at }
const painted = new Map();
let paintLoaded = false;

function loadPaint() {
  if (paintLoaded) return;
  paintLoaded = true;
  const rows = readJson(world, PAINT_PROP, []);
  if (!Array.isArray(rows)) return;
  for (const row of rows) {
    if (!Array.isArray(row) || row.length < 6) continue;
    const key = posKey(dimName(row[0]), { x: row[1], y: row[2], z: row[3] });
    painted.set(key, { strength: row[4] ?? PAINT_STRENGTH, owner: row[5] ?? "", at: 0 });
  }
}

function savePaint() {
  const rows = [];
  for (const [k, v] of painted) {
    const p = parsePosKey(k);
    if (!p) continue;
    rows.push([dimCode(p.dimensionId), p.x, p.y, p.z, v.strength, v.owner]);
  }
  writeJson(world, PAINT_PROP, rows);
}

function countPaint(ownerId) {
  let n = 0;
  for (const v of painted.values()) if (v.owner === ownerId) n++;
  return n;
}

/** ブロックを磁化する。上限を超えたら、その人の一番古い塗りを剥がす。 */
export function paintMagnetic(player, pos, strength = PAINT_STRENGTH) {
  loadPaint();
  const key = posKey(player.dimension.id, pos);
  if (painted.has(key)) return false;
  // 自分の枠が一杯なら自分の一番古い塗り、世界の枠が一杯なら世界で一番古い塗り。
  // Map は挿入順を保つので、先頭がそのまま「一番古い」になる。
  while (countPaint(player.id) >= PAINT_PER_PLAYER || painted.size >= PAINT_TOTAL) {
    const mineFull = countPaint(player.id) >= PAINT_PER_PLAYER;
    const victim = mineFull
      ? [...painted.entries()].find(([, v]) => v.owner === player.id)
      : [...painted.entries()][0];
    if (!victim) break;
    painted.delete(victim[0]);
  }
  painted.set(key, { strength, owner: player.id, at: system.currentTick });
  savePaint();
  fx(player.dimension, FX.mag_glyph,
     { x: Math.floor(pos.x) + 0.5, y: Math.floor(pos.y) + 1.05, z: Math.floor(pos.z) + 0.5 });
  return true;
}

export function unpaintMagnetic(player, pos) {
  loadPaint();
  const removed = painted.delete(posKey(player.dimension.id, pos));
  if (removed) savePaint();
  return removed;
}

/** その人の塗りを全部剥がす。 */
export function clearPaint(player) {
  loadPaint();
  let n = 0;
  for (const [k, v] of [...painted]) if (v.owner === player.id) { painted.delete(k); n++; }
  if (n) savePaint();
  return n;
}

export function paintedCount(player) {
  loadPaint();
  return countPaint(player.id);
}

/** そこが塗られているか。塗られていれば磁性ブロック扱いにする。 */
export function paintedStrength(dimension, pos) {
  loadPaint();
  return painted.get(posKey(dimension.id, pos))?.strength ?? 0;
}

/** 走査結果に混ぜるための、半径内の塗り。数が少ないので全部見てよい。 */
function paintedNear(dimension, centre, radius) {
  loadPaint();
  const out = [];
  for (const [key, v] of painted) {
    const p = parsePosKey(key);
    if (!p || p.dimensionId !== dimension.id) continue;
    const d = Math.hypot(p.x + 0.5 - centre.x, p.y + 0.5 - centre.y, p.z + 0.5 - centre.z);
    if (d > radius) continue;
    out.push({ x: p.x, y: p.y, z: p.z, typeId: "", strength: v.strength, distance: d, painted: true });
  }
  return out;
}

/** その座標の実効磁力（普通の磁性ブロック or 塗られたブロック）。 */
export function strengthAt(dimension, pos) {
  const block = safe(() => dimension.getBlock(pos));
  if (!block) return 0;
  const natural = blockStrength(block.typeId);
  if (natural > 0) return natural;
  if (safe(() => block.isAir) === true) return 0;
  return paintedStrength(dimension, pos);
}

// ---------------------------------------------------------------- 走査
// 中心から近い順に並べたオフセット表。半径と step ごとに一度だけ作って使い回す。
const offsetTables = new Map();
const OFFSET_CACHE_MAX = 8;

// 近くは 1 ブロック刻みで正確に見る範囲。目の前の鉄柵が「間引きの網から
// 漏れて反応しない」のが一番いけないので、ここだけは絶対に飛ばさない。
const FINE_RADIUS = 6;

/**
 * 遠くの間引き幅。半径が伸びても総数が増え続けないように選ぶ。
 * 近傍球（905 点）と合わせて、どの半径でも 2,150 点以内に収まる値。
 */
function stepFor(radius) {
  if (radius <= 8) return 1;
  if (radius <= 12) return 2;
  if (radius <= 20) return 3;
  if (radius <= 24) return 4;
  if (radius <= 32) return 5;
  return 6;
}

/**
 * 中心からの相対座標の表。**近い順**に並べてあるので、途中で打ち切っても
 * 「一番近い金属」から順に手に入る。半径 6 までは 1 刻み、その外は粗い刻み。
 */
function offsetsFor(radius, step) {
  const r = Math.ceil(radius);
  const key = `${r}/${step}`;
  const cached = offsetTables.get(key);
  if (cached) return cached;
  const table = [];
  const seen = new Set();
  const push = (dx, dy, dz) => {
    const d = Math.hypot(dx, dy, dz);
    if (d > r) return;
    const k = `${dx},${dy},${dz}`;
    if (seen.has(k)) return;
    seen.add(k);
    table.push({ dx, dy, dz, d });
  };
  const fine = Math.min(r, FINE_RADIUS);
  for (let dy = -fine; dy <= fine; dy++) {
    for (let dx = -fine; dx <= fine; dx++) {
      for (let dz = -fine; dz <= fine; dz++) {
        if (Math.hypot(dx, dy, dz) > fine) continue;   // 立方体で拾うと角の分だけ無駄に重い
        push(dx, dy, dz);
      }
    }
  }
  if (step > 0) {
    for (let dy = -r; dy <= r; dy += step) {
      for (let dx = -r; dx <= r; dx += step) {
        for (let dz = -r; dz <= r; dz += step) push(dx, dy, dz);
      }
    }
  }
  table.sort((a, b) => a.d - b.d);
  if (offsetTables.size >= OFFSET_CACHE_MAX) {
    offsetTables.delete(offsetTables.keys().next().value);
  }
  offsetTables.set(key, table);
  return table;
}

function rank(a, b) {
  return (b.strength / (1 + b.distance)) - (a.strength / (1 + a.distance));
}

/**
 * 周囲の磁性ブロックを探す。
 * @returns [{x,y,z,typeId,strength,distance}] を強度×近さの順に。
 *
 * 三重ループを一本に潰してあるので、必要数が揃った時点で本当に抜ける
 * （以前は最内ループしか抜けず、上限が効いていなかった）。
 */
export function scanMetal(dimension, centre, radius, limit = 48, opts = {}) {
  const step = opts.step ?? stepFor(radius);
  const budget = opts.budget ?? 2400;   // 表より大きい＝黙って射程が縮まらない
  const table = offsetsFor(radius, step);
  const cx = Math.floor(centre.x), cy = Math.floor(centre.y), cz = Math.floor(centre.z);
  const found = [];
  let visits = 0;
  for (const o of table) {
    if (visits >= budget) break;
    const y = cy + o.dy;
    if (y < -64 || y > 320) continue;
    visits++;
    const block = safe(() => dimension.getBlock({ x: cx + o.dx, y, z: cz + o.dz }));
    if (!block) continue;
    const strength = blockStrength(block.typeId);
    if (strength <= 0) continue;
    found.push({
      x: cx + o.dx, y, z: cz + o.dz, typeId: block.typeId, strength, distance: o.d,
    });
    if (found.length >= limit * 2) break;      // ここで本当に走査を終える
  }
  // 塗ったブロックは間引きの網に関係なく必ず拾う。自分で作った戦場が
  // 「たまたま網から漏れて反応しない」のでは磁化ペイントの意味がない。
  for (const p of paintedNear(dimension, centre, radius)) found.push(p);
  found.sort(rank);
  return found.slice(0, limit);
}

/**
 * 走査を複数 tick に割る版。半径 40 の必殺技のように
 * 「粗くしたくないが 1 tick では重い」ときに使う。
 * `system.runJob` が無い環境では同期版に落ちる。
 */
export function scanMetalAsync(dimension, centre, radius, limit, done, opts = {}) {
  const perTick = opts.perTick ?? 800;
  const step = opts.step ?? Math.max(1, stepFor(radius) - 2);
  const table = offsetsFor(radius, step);
  const cx = Math.floor(centre.x), cy = Math.floor(centre.y), cz = Math.floor(centre.z);
  const found = [];

  function* walk() {
    let visits = 0;
    for (const o of table) {
      const y = cy + o.dy;
      if (y < -64 || y > 320) continue;
      const block = safe(() => dimension.getBlock({ x: cx + o.dx, y, z: cz + o.dz }));
      if (block) {
        const strength = blockStrength(block.typeId);
        if (strength > 0) {
          found.push({
            x: cx + o.dx, y, z: cz + o.dz, typeId: block.typeId, strength, distance: o.d,
          });
          if (found.length >= limit * 2) break;
        }
      }
      if (++visits % perTick === 0) yield;      // ここで次の tick へ譲る
    }
    for (const p of paintedNear(dimension, centre, radius)) found.push(p);
    found.sort(rank);
    safe(() => done(found.slice(0, limit)));
  }

  const job = safe(() => system.runJob(walk()));
  if (job !== undefined) return job;
  safe(() => done(scanMetal(dimension, centre, radius, limit, opts)));
  return undefined;
}

/**
 * 周りにどれだけ金属があるか（0 ～ 1.5 程度）。
 * 技の威力を「その場の金属の量」で変えるための目安。鉄の要塞の中と
 * 草原の真ん中で同じ威力しか出ないなら、磁力を操っている気がしない。
 */
export function metalDensity(found) {
  let sum = 0;
  for (const m of found) sum += m.strength / (1 + m.distance * 0.25);
  return clamp(sum / 12, 0, 1.5);
}

/** その場の磁界の濃さを直接測る。走査結果が要らないときの近道。 */
export function fieldStrength(dimension, centre, radius = 12) {
  return metalDensity(scanMetal(dimension, centre, radius, 32));
}

// ---------------------------------------------------------------- 剥がし
// 引き剥がしたブロックは **必ず戻す**。戻さないと storm / uprising / sphere を
// 撃つたびに地形が穴だらけになり、拠点が数分で崩壊する。
//
//   * 剥がした座標・ブロックの状態を台帳に積む
//   * 8 秒後、そこがまだ空気なら元に戻す（誰かが建てていたら手を出さない）
//   * 同時に剥がせるのは 96 個まで。超えたら古い順に即座に戻す
//   * ワールドを開き直したときは、残っていた分を全部戻す
const RIP_TTL = 160;          // 8 秒
const RIP_MAX = 96;
const RIP_PROP = "marvel:ripped";

//: { dimId, x, y, z, typeId, permutation, due }
const ripped = [];
let ripLoaded = false;
// 保存は「変わった」印を立てるだけにして、実際の書き出しは巡回にまとめる。
// 嵐のように 1 tick で十数個剥がす技があるので、剥がすたびに JSON へ
// 起こしていると、そこだけで無駄に tick を食う。
let ripDirty = false;

function saveRipped() {
  const rows = ripped.slice(-RIP_MAX).map(
    (r) => [dimCode(r.dimId), r.x, r.y, r.z, r.typeId]);
  writeJson(world, RIP_PROP, rows);
}

function placeBack(entry) {
  const dimension = safe(() => world.getDimension(entry.dimId));
  if (!dimension) return false;
  const block = safe(() => dimension.getBlock({ x: entry.x, y: entry.y, z: entry.z }));
  if (!block) return false;                       // 未読み込み。次の巡回でまた見る
  // 空気でなければ、その後で誰かが置いたということ。上書きしない。
  if (safe(() => block.isAir) !== true) return true;
  const ok = entry.permutation
    ? safe(() => { block.setPermutation(entry.permutation); return true; })
    : undefined;
  if (!ok) safe(() => block.setType(entry.typeId));
  fx(dimension, FX.metal_glint, { x: entry.x + 0.5, y: entry.y + 0.5, z: entry.z + 0.5 });
  return true;
}

function loadRipped() {
  if (ripLoaded) return;
  ripLoaded = true;
  const rows = readJson(world, RIP_PROP, []);
  if (!Array.isArray(rows) || !rows.length) return;
  // 開き直した時点で「8 秒」はとうに過ぎている。残っていた穴は全部塞ぐ。
  // ただし未読み込みのチャンクには書けないので、失敗した分は台帳に戻して
  // 巡回で追いかける。ここで捨てると穴が永久に残る。
  for (const row of rows) {
    if (!Array.isArray(row) || row.length < 5) continue;
    const entry = {
      dimId: dimName(row[0]), x: row[1], y: row[2], z: row[3],
      typeId: row[4], permutation: undefined, due: system.currentTick,
    };
    if (!placeBack(entry)) ripped.push(entry);
  }
  ripDirty = true;
}

/** 期限の来たものを戻す。強制すると台帳を空にするまで戻し切る。 */
export function restoreRipped(force = false) {
  loadRipped();
  const now = system.currentTick;
  let restored = 0;
  for (let i = ripped.length - 1; i >= 0; i--) {
    if (!force && now < ripped[i].due) continue;
    if (placeBack(ripped[i])) { ripped.splice(i, 1); restored++; }
  }
  if (restored) ripDirty = true;
  return restored;
}

export function ripCount() { return ripped.length; }

/**
 * 磁性ブロックを引き剥がして鉄片エンティティに変える。
 * ブロックは台帳に積まれ、8 秒後に元へ戻る。
 */
export function ripBlock(dimension, pos, ownerId) {
  loadRipped();
  const block = safe(() => dimension.getBlock(pos));
  if (!block) return undefined;
  const typeId = block.typeId;
  const strength = blockStrength(typeId) || paintedStrength(dimension, pos);
  if (strength <= 0) return undefined;
  if (safe(() => block.isAir) === true) return undefined;

  // 上限に達したら、一番古い穴を先に塞いでから新しく剥がす。
  // まだ書けない（チャンクが読まれていない）ものは列の後ろへ回す。
  // ここで捨てると、その穴は二度と塞がれない。
  for (let guard = 0; ripped.length >= RIP_MAX && guard < RIP_MAX; guard++) {
    const oldest = ripped.shift();
    if (!oldest) break;
    if (!placeBack(oldest)) ripped.push(oldest);
  }
  const permutation = safe(() => block.permutation);
  const centre = { x: Math.floor(pos.x) + 0.5, y: Math.floor(pos.y) + 0.5, z: Math.floor(pos.z) + 0.5 };
  if (!safe(() => { block.setType("minecraft:air"); return true; })) return undefined;
  ripped.push({
    dimId: dimension.id,
    x: Math.floor(pos.x), y: Math.floor(pos.y), z: Math.floor(pos.z),
    typeId, permutation, due: system.currentTick + RIP_TTL,
  });
  ripDirty = true;

  fx(dimension, FX.metal_rip, centre);
  const shard = safe(() => dimension.spawnEntity(ENTITY.metal_shard, centre));
  if (shard && ownerId) safe(() => shard.setDynamicProperty("marvel:owner", ownerId));
  return shard;
}

// 鉱石 -> 母岩。抜いたあとに穴が開かないよう、石で埋め戻すために持つ。
const ORE_HOST = {
  "minecraft:iron_ore": "minecraft:stone",
  "minecraft:deepslate_iron_ore": "minecraft:deepslate",
  "minecraft:gold_ore": "minecraft:stone",
  "minecraft:deepslate_gold_ore": "minecraft:deepslate",
  "minecraft:copper_ore": "minecraft:stone",
  "minecraft:deepslate_copper_ore": "minecraft:deepslate",
  "minecraft:ancient_debris": "minecraft:netherrack",
};
const ORE_DROP = {
  "minecraft:iron_ore": "minecraft:raw_iron",
  "minecraft:deepslate_iron_ore": "minecraft:raw_iron",
  "minecraft:gold_ore": "minecraft:raw_gold",
  "minecraft:deepslate_gold_ore": "minecraft:raw_gold",
  "minecraft:copper_ore": "minecraft:raw_copper",
  "minecraft:deepslate_copper_ore": "minecraft:raw_copper",
  "minecraft:ancient_debris": "minecraft:ancient_debris",
};

/**
 * 磁力採掘 — 鉱脈を壊さず、金属だけを抜き取る（DIRECTION §7-3）。
 * 抜いた跡は母岩で埋まるので、地形はそのまま残る。
 * @returns 抜き取った ItemStack。鉱石でなければ undefined。
 */
export function siphonOre(dimension, pos) {
  const block = safe(() => dimension.getBlock(pos));
  if (!block) return undefined;
  const drop = ORE_DROP[block.typeId];
  if (!drop) return undefined;
  const host = ORE_HOST[block.typeId] ?? "minecraft:stone";
  if (!safe(() => { block.setType(host); return true; })) return undefined;
  fx(dimension, FX.metal_glint,
     { x: Math.floor(pos.x) + 0.5, y: Math.floor(pos.y) + 0.5, z: Math.floor(pos.z) + 0.5 });
  return safe(() => new ItemStack(drop, 1));
}

// ---------------------------------------------------------------- 引く・押す
/**
 * 対象を `to` の方向へ動かす。引き寄せ・押し出しの共通処理。
 * 既定では金属の量で効きが変わる（`gripFactor`）。金属を持たない相手でも
 * 弱くはならず、鎧の重い相手ほど強く持っていかれる。
 */
export function drag(entity, toward, power, vertical = 0.15, opts = {}) {
  const from = entity.location;
  const d = sub(toward, from);
  const len = Math.hypot(d.x, d.y, d.z) || 1;
  const n = { x: d.x / len, y: d.y / len, z: d.z / len };
  const k = power * (opts.grip === false ? 1 : gripFactor(entity));
  try {
    entity.applyImpulse({
      x: n.x * k, y: n.y * k * 0.6 + vertical, z: n.z * k,
    });
    return true;
  } catch (_) {
    // プレイヤーには applyImpulse が効かないので knockback へ落とす
    return selfPush(entity, n.x, n.z, k, n.y * k * 0.4 + vertical);
  }
}

/** 相手の金属装備を剥ぎ取って地面に落とす。剥がした数を返す。 */
export function stripEquipment(target, dimension) {
  const eq = safe(() => target.getComponent("minecraft:equippable"));
  if (!eq) return 0;
  let stripped = 0;
  for (const slot of EQUIP_SLOTS) {
    const item = safe(() => eq.getEquipment(slot));
    if (!item || itemStrength(item.typeId) <= 0) continue;
    if (!safe(() => { eq.setEquipment(slot, undefined); return true; })) continue;
    safe(() => dimension.spawnItem(new ItemStack(item.typeId, item.amount ?? 1),
      { x: target.location.x, y: target.location.y + 1.0, z: target.location.z }));
    stripped++;
  }
  return stripped;
}

/**
 * 圧壊 — 着ている金属を内側から潰す。
 * ダメージだけだと「なぜ金属持ちに強いのか」が画面に出ないので、
 * 装備そのものを傷める。壊れた数と傷めた数を返す。
 */
export function crushEquipment(target, severity = 1) {
  const eq = safe(() => target.getComponent("minecraft:equippable"));
  if (!eq) return { damaged: 0, broken: 0 };
  let damaged = 0, broken = 0;
  for (const slot of EQUIP_SLOTS) {
    const item = safe(() => eq.getEquipment(slot));
    if (!item) continue;
    const factor = itemStrength(item.typeId);
    if (factor <= 0) continue;                    // アダマンチウムは潰れない
    const dur = safe(() => item.getComponent("minecraft:durability"));
    if (!dur) continue;
    const max = safe(() => dur.maxDurability) ?? 0;
    const cost = Math.max(1, Math.round(max * 0.18 * severity * factor));
    const now = (safe(() => dur.damage) ?? 0) + cost;
    if (max > 0 && now >= max) {
      safe(() => eq.setEquipment(slot, undefined));
      broken++;
    } else if (safe(() => { dur.damage = now; return true; })) {
      safe(() => eq.setEquipment(slot, item));
      damaged++;
    }
  }
  if (broken) {
    fx(target.dimension, FX.crush_implode,
       { x: target.location.x, y: target.location.y + 1.0, z: target.location.z });
  }
  return { damaged, broken };
}

/** 落ちているアイテムのうち、磁力に応えるものを引き寄せる。 */
export function pullItems(dimension, centre, radius, toward, power = 0.55) {
  let moved = 0;
  const items = safe(() => dimension.getEntities({
    location: centre, maxDistance: radius, type: "minecraft:item",
  })) ?? [];
  for (const item of items) {
    const stack = safe(() => item.getComponent("minecraft:item")?.itemStack);
    if (stack && itemStrength(stack.typeId) <= 0
        && !MAGNETIC_BLOCKS[stack.typeId]) continue;
    if (drag(item, toward, power, 0.25, { grip: false })) moved++;
  }
  return moved;
}

/** 磁力線を描く。技の説得力は、この線が出るかどうかで随分変わる。 */
export function drawFieldLines(dimension, from, targets, id = FX.mag_line, max = 8) {
  let n = 0;
  for (const t of targets) {
    if (n++ >= max) break;
    fxTrail(dimension, id, from, t, 1.0);
  }
}

/** 磁力視 — 壁越しに金属を光らせる。一人称の楽しさはここ。 */
export function revealMetal(player, radius = 20) {
  const found = scanMetal(player.dimension, player.location, radius, 60);
  for (const m of found) {
    fx(player.dimension, m.painted ? FX.mag_glyph : FX.sight_ping,
       { x: m.x + 0.5, y: m.y + 0.5, z: m.z + 0.5 });
  }
  const wearers = safe(() => player.dimension.getEntities({
    location: player.location, maxDistance: radius,
  })) ?? [];
  for (const e of wearers) {
    if (e.id === player.id) continue;
    if (metalOn(e) <= 0) continue;
    fx(player.dimension, FX.mag_glyph,
       { x: e.location.x, y: e.location.y + 1.2, z: e.location.z });
  }
  return found.length;
}

// ---------------------------------------------------------------- 鉄片
// 鉄片を撃ち出す。当たり判定はスクリプト側で毎 tick 見るので、
// 総数に上限を置かないと嵐を撃つたびに tick が伸びていく。
const PROJECTILE_MAX = 60;
const projectiles = [];

export function launchShard(player, origin, dir, speed, damage,
                           typeId = ENTITY.metal_shard, life = 60) {
  // 上限を超えたら古い弾から消す。撃ちたてが消えるより自然。
  while (projectiles.length >= PROJECTILE_MAX) {
    const old = projectiles.shift();
    safe(() => old?.entity?.remove());
  }
  const e = safe(() => player.dimension.spawnEntity(typeId, origin));
  if (!e) return undefined;
  safe(() => e.setRotation({ x: 0, y: 0 }));
  projectiles.push({
    entity: e, dir: normalise(dir), speed, damage, life,
    ownerId: player.id, born: system.currentTick,
  });
  return e;
}

/** 毎 tick: 飛んでいる鉄片を進め、当たったら処理する。 */
export function tickProjectiles(onHit) {
  for (let i = projectiles.length - 1; i >= 0; i--) {
    const p = projectiles[i];
    const e = p.entity;
    if (!safe(() => e.isValid?.() !== false) || system.currentTick - p.born > p.life) {
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    const here = e.location;
    const next = forward(here, p.dir, p.speed);
    // ブロックに当たったか
    const block = safe(() => e.dimension.getBlock(next));
    if (block && !block.isAir && !block.isLiquid) {
      fx(e.dimension, FX.lance_impact, here);
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    // エンティティに当たったか
    const near = safe(() => e.dimension.getEntities({
      location: next, maxDistance: 1.4,
    })) ?? [];
    let struck = false;
    for (const t of near) {
      if (t.id === e.id || t.id === p.ownerId) continue;
      if (hasFamily(t, FAMILY.prop)) continue;
      if (hasFamily(t, FAMILY.brotherhood)) continue;
      onHit?.(p, t);
      struck = true;
      break;
    }
    if (struck) {
      safe(() => e.remove());
      projectiles.splice(i, 1);
      continue;
    }
    safe(() => e.teleport(next, { facingLocation: forward(next, p.dir, 2) }));
    fx(e.dimension, FX.shard_trail, here);
  }
}

export function projectileCount() {
  return projectiles.length;
}

// ---------------------------------------------------------------- 巡回
// 剥がした地形の復元は、技を撃った本人がログアウトしても続ける必要がある。
// main.js のループに依存させず、この engine が自分で持つ。
safe(() => system.runInterval(() => {
  try {
    restoreRipped();
    if (ripDirty) { saveRipped(); ripDirty = false; }
  } catch (_) { }
}, 20));
