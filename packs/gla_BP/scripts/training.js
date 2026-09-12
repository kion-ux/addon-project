// 訓練場 / 港島 (企画書 §12)
//
// 「初期の遊び場を小さく作り込み、戦闘と映像の品質が分かる場所を用意する」。
// 区画は企画書の表のとおり4つ:
//
//   訓練広場     標準距離で技を確認する / 距離目盛り・単体と群れの標的・遮蔽物
//   撮影エリア   形態とアニメの比較     / 昼夜を揃えた背景・正面と斜めの基準位置
//   負荷テスト   同時戦闘時の重さを測る / 人数と敵数を固定できる配置
//   移動コース   見た目の追従を確認     / 段差・狭い入口・坂・ジャンプ・水際
//
// 建築は1tickにまとめて流すと確実に固まるので、小分けにして順に置く。
import { system } from "@minecraft/server";
import { MOB, TRAINING } from "./data.js";
import { tr, tell, later, clamp } from "./util.js";

const AIR = "minecraft:air";
const SAND = "minecraft:sand";
const STONE = "minecraft:stone";
const SMOOTH = "minecraft:smooth_stone";
const PLANK = "minecraft:oak_planks";
const LOG = "minecraft:oak_log";
const FENCE = "minecraft:oak_fence";
const COBBLE = "minecraft:cobblestone";
const WATER = "minecraft:water";
const GLOW = "minecraft:glowstone";
const BARREL = "minecraft:barrel";
const WOOL = {
  red: "minecraft:red_wool",
  yellow: "minecraft:yellow_wool",
  white: "minecraft:white_wool",
  blue: "minecraft:light_blue_wool",
  black: "minecraft:black_wool",
};

const SIZE = TRAINING.size;            // 企画書の 128 を基準に、半分を陸地にする
const HALF = Math.floor(SIZE / 2);
const LAND = 44;                       // 陸地の半径。目盛りの 25 ブロックが余裕で入る

// 一度に置くブロック数。多すぎると確実にカクつく。
const PER_TICK = 900;

const building = new Set();            // playerId

// ---------------------------------------------------------------------------
//  低レベル
// ---------------------------------------------------------------------------
function setBlock(dimension, x, y, z, type) {
  try {
    const b = dimension.getBlock({ x, y, z });
    if (!b) return false;
    b.setType(type);
    return true;
  } catch (_) { return false; }
}

/** 置く場所を job の配列として溜め、tick をまたいで流す。 */
class Plan {
  constructor(dimension, origin) {
    this.dim = dimension;
    this.o = origin;
    this.jobs = [];
  }

  at(dx, dy, dz, type) {
    this.jobs.push([this.o.x + dx, this.o.y + dy, this.o.z + dz, type]);
  }

  box(x0, y0, z0, x1, y1, z1, type) {
    const [ax, bx] = x0 <= x1 ? [x0, x1] : [x1, x0];
    const [ay, by] = y0 <= y1 ? [y0, y1] : [y1, y0];
    const [az, bz] = z0 <= z1 ? [z0, z1] : [z1, z0];
    for (let y = ay; y <= by; y++) {
      for (let z = az; z <= bz; z++) {
        for (let x = ax; x <= bx; x++) this.at(x, y, z, type);
      }
    }
  }

  disc(cx, cz, y, radius, type) {
    const r2 = radius * radius;
    for (let z = -radius; z <= radius; z++) {
      for (let x = -radius; x <= radius; x++) {
        if (x * x + z * z <= r2) this.at(cx + x, y, cz + z, type);
      }
    }
  }

  ring(cx, cz, y, radius, type, thickness = 1) {
    const outer = radius * radius;
    const inner = (radius - thickness) * (radius - thickness);
    for (let z = -radius; z <= radius; z++) {
      for (let x = -radius; x <= radius; x++) {
        const d = x * x + z * z;
        if (d <= outer && d > inner) this.at(cx + x, y, cz + z, type);
      }
    }
  }

  get size() { return this.jobs.length; }
}

function runPlan(player, plan, onDone) {
  let i = 0;
  const total = plan.jobs.length;
  const step = () => {
    if (!building.has(player.id)) return;          // 途中で片付けられた
    const end = Math.min(total, i + PER_TICK);
    for (; i < end; i++) {
      const [x, y, z, t] = plan.jobs[i];
      setBlock(plan.dim, x, y, z, t);
    }
    if (i < total) {
      const pct = Math.round((i / total) * 100);
      try {
        player.onScreenDisplay.setActionBar({
          rawtext: [{ translate: "gla.msg.training_progress", with: [String(pct)] }],
        });
      } catch (_) { }
      later(1, step);
    } else {
      building.delete(player.id);
      onDone?.();
    }
  };
  step();
}

// ---------------------------------------------------------------------------
//  区画
// ---------------------------------------------------------------------------
function layIsland(p) {
  // 海 → 砂浜 → 内陸の順に重ねる。遠景の海と空が見える構図にしたい。
  p.disc(0, 0, -1, HALF, WATER);
  p.disc(0, 0, 0, HALF, AIR);
  p.disc(0, 0, -1, LAND + 6, SAND);
  p.disc(0, 0, 0, LAND + 6, AIR);
  p.disc(0, 0, -1, LAND, STONE);
  p.disc(0, 0, -1, LAND - 3, SMOOTH);
  // 岩場 — 輪郭に変化を付ける
  for (const [ox, oz, r] of [[-34, 26, 5], [30, -30, 6], [-28, -34, 4], [36, 22, 4]]) {
    p.disc(ox, oz, 0, r, COBBLE);
    p.disc(ox, oz, 1, Math.max(1, r - 2), COBBLE);
    p.disc(ox, oz, 2, Math.max(1, r - 4), COBBLE);
  }
}

function layPier(p) {
  // 桟橋と木箱。遠景の抜けを作る。
  p.box(-3, 0, LAND - 2, 3, 0, LAND + 14, PLANK);
  for (let z = LAND; z <= LAND + 14; z += 4) {
    for (const x of [-3, 3]) {
      p.at(x, -1, z, LOG);
      p.at(x, 1, z, FENCE);
    }
  }
  for (const [x, z] of [[-2, LAND + 4], [2, LAND + 5], [-2, LAND + 10], [1, LAND + 12]]) {
    p.at(x, 1, z, BARREL);
  }
  p.at(0, 1, LAND + 13, BARREL);
  p.at(0, 2, LAND + 13, BARREL);
}

/**
 * 訓練広場 — 標準距離で技を確認する。
 * 距離目盛りは spec.TRAINING.markers（5/10/15/20/25 ブロック）。
 * 壁越し判定用の遮蔽物も置く（QA-07 壁越しに当たらないこと）。
 */
function layPlaza(p) {
  const z0 = -6;
  p.box(-16, 0, z0 - 4, 16, 0, z0 + 34, SMOOTH);
  // 射線の基準（ここに立って撃つ）
  p.box(-1, 0, z0, 1, 0, z0, WOOL.white);
  p.at(0, 1, z0 - 1, FENCE);
  for (const m of TRAINING.markers) {
    const z = z0 + m;
    const colour = m <= 10 ? WOOL.blue : m <= 20 ? WOOL.yellow : WOOL.red;
    p.box(-14, 0, z, 14, 0, z, colour);
    // 5ブロックごとに高さの目印も置く（縦の距離感がないと判定がずれて見える）
    p.at(-14, 1, z, FENCE);
    p.at(14, 1, z, FENCE);
  }
  // 遮蔽物 — 壁越しに当たらないことを確かめるための壁
  p.box(6, 1, z0 + 12, 10, 4, z0 + 12, COBBLE);
  p.box(-10, 1, z0 + 18, -6, 4, z0 + 18, COBBLE);
  // 背面 — 貫通して遠くへ飛ばないように
  p.box(-16, 1, z0 + 34, 16, 5, z0 + 34, STONE);
}

/**
 * 撮影エリア — 形態とアニメの比較。
 * 昼夜で色が変わらないよう、背景と足元の明るさを固定する。
 */
function layStudio(p) {
  const x0 = -40;
  p.box(x0 - 8, 0, -8, x0 + 8, 0, 8, SMOOTH);
  // 背景（無地）と、夜でも同じ明るさにするための光源
  p.box(x0 - 8, 1, 8, x0 + 8, 8, 8, WOOL.white);
  p.box(x0 - 8, 1, -8, x0 - 8, 8, 8, WOOL.white);
  for (const dz of [-6, -2, 2, 6]) {
    p.at(x0 - 7, 7, dz, GLOW);
    p.at(x0 + 7, 7, dz, GLOW);
  }
  // 全身が収まる床目印（正面・斜め・横）
  p.box(x0 - 1, 0, 0, x0 + 1, 0, 0, WOOL.red);          // 立ち位置
  p.box(x0 - 1, 0, -5, x0 + 1, 0, -5, WOOL.yellow);     // 正面カメラ
  p.box(x0 - 5, 0, -4, x0 - 4, 0, -4, WOOL.blue);       // 斜め
  p.box(x0 + 4, 0, -4, x0 + 5, 0, -4, WOOL.blue);
  p.box(x0 - 6, 0, 0, x0 - 6, 0, 1, WOOL.black);        // 真横
}

/** 負荷テスト区画 — 人数と敵数を固定できる配置。 */
function layLoadYard(p) {
  const x0 = 34;
  p.box(x0 - 10, 0, -12, x0 + 10, 0, 12, SMOOTH);
  p.box(x0 - 10, 1, -12, x0 + 10, 3, -12, COBBLE);
  p.box(x0 - 10, 1, 12, x0 + 10, 3, 12, COBBLE);
  p.box(x0 - 10, 1, -12, x0 - 10, 3, 12, COBBLE);
  p.box(x0 + 10, 1, -12, x0 + 10, 3, 12, COBBLE);
  // 標的の定位置（20体ぶんの印）
  let n = 0;
  for (let z = -8; z <= 8 && n < 20; z += 4) {
    for (let x = -8; x <= 8 && n < 20; x += 4) {
      p.at(x0 + x, 0, z, WOOL.yellow);
      n++;
    }
  }
  // プレイヤーの定位置（4人ぶん）
  for (const [dx, dz] of [[-9, -10], [-9, 10], [9, -10], [9, 10]]) {
    p.at(x0 + dx, 0, dz, WOOL.white);
  }
}

/** 移動コース — 段差・狭い入口・坂・ジャンプ・水際。見た目の追従を確認する。 */
function layCourse(p) {
  const z0 = -34;
  p.box(-18, 0, z0 - 6, 18, 0, z0 + 6, SMOOTH);
  // 段差
  for (let i = 1; i <= 4; i++) p.box(-18 + i * 2, i, z0 - 2, -17 + i * 2, i, z0 + 2, STONE);
  // 狭い入口
  p.box(-6, 1, z0 - 3, -6, 4, z0 + 3, COBBLE);
  p.box(-6, 1, z0, -6, 2, z0, AIR);
  // 坂
  for (let i = 0; i < 8; i++) p.box(-2 + i, Math.floor(i / 2), z0 - 2, -2 + i, Math.floor(i / 2), z0 + 2, STONE);
  // ジャンプの隙間
  p.box(7, 3, z0 - 2, 9, 3, z0 + 2, STONE);
  p.box(12, 3, z0 - 2, 14, 3, z0 + 2, STONE);
  // 水際
  p.box(15, 0, z0 - 6, 18, 0, z0 + 6, AIR);
  p.box(15, -1, z0 - 6, 18, -1, z0 + 6, WATER);
}

function layFlags(p) {
  for (const [x, z] of [[-20, -20], [20, -20], [-20, 20], [20, 20]]) {
    for (let y = 1; y <= 5; y++) p.at(x, y, z, FENCE);
    p.at(x, 6, z, WOOL.red);
    p.at(x, 5, z + 1, WOOL.white);
  }
  // 展望地点
  p.disc(0, -44, 0, 5, COBBLE);
  for (let y = 1; y <= 6; y++) p.ring(0, -44, y, 5, COBBLE, 1);
  p.disc(0, -44, 7, 5, PLANK);
  p.at(0, 8, -44, GLOW);
}

// ---------------------------------------------------------------------------
//  組み立て
// ---------------------------------------------------------------------------
export function buildTrainingGround(player) {
  if (building.has(player.id)) { tell(player, tr("gla.msg.training_busy")); return; }
  const loc = player.location;
  const origin = {
    x: Math.floor(loc.x), y: Math.floor(loc.y) - 1, z: Math.floor(loc.z),
  };
  const plan = new Plan(player.dimension, origin);
  layIsland(plan);
  layPlaza(plan);
  layStudio(plan);
  layLoadYard(plan);
  layCourse(plan);
  layPier(plan);
  layFlags(plan);

  building.add(player.id);
  tell(player, tr("gla.msg.training_start", String(plan.size)));
  runPlan(player, plan, () => {
    placeTargets(player, origin);
    tell(player, tr("gla.msg.training_done"));
    for (const z of TRAINING.zones) {
      tell(player, { rawtext: [{ text: "§7- §r" }, { translate: `gla.zone.${z.key}` }] });
    }
  });
}

/** 単体の標的1体と、群れの標的を並べる。 */
function placeTargets(player, origin) {
  const dim = player.dimension;
  const spawnAt = (dx, dy, dz, type) => {
    try {
      return dim.spawnEntity(type, {
        x: origin.x + dx + 0.5, y: origin.y + dy + 1, z: origin.z + dz + 0.5,
      });
    } catch (_) { return undefined; }
  };
  // 訓練広場: 距離目盛りの 10 / 20 ブロック地点に単体の標的
  spawnAt(0, 0, -6 + 10, MOB.training_dummy);
  spawnAt(0, 0, -6 + 20, MOB.training_dummy);
  // 壁の裏 — 壁越しに当たらないことを確かめる
  spawnAt(8, 0, -6 + 13, MOB.training_dummy);
  // 群れ
  for (let i = 0; i < 6; i++) {
    spawnAt(-8 + i * 3, 0, -6 + 26, MOB.training_swarm);
  }
  // 負荷テスト区画
  for (let i = 0; i < 8; i++) {
    spawnAt(34 - 8 + (i % 4) * 4, 0, -8 + Math.floor(i / 4) * 4, MOB.training_swarm);
  }
}

/**
 * 標的だけを片付ける。地形は消さない — 一度置いた建物を黙って消すのは
 * 取り返しがつかないので、やらない。
 */
export function removeTrainingGround(player) {
  building.delete(player.id);
  let removed = 0;
  try {
    const found = player.dimension.getEntities({
      location: player.location, maxDistance: 128,
      families: ["gla_target"],
    });
    for (const e of found) {
      try { e.remove(); removed++; } catch (_) { }
    }
  } catch (_) { }
  tell(player, tr("gla.msg.training_cleared", String(removed)));
}

export function isBuilding(id) {
  return building.has(id);
}
