// ===========================================================================
//  NIGHT RUNNER: 感染都市 — 当たった部位の判定（DESIGN §4「当たった部位の判定」/ §12 の当たり箱）
//
//  data/zombie_shapes.js の SHAPES[key] = {height, width, stand: {部位: [{c, h}...]}, lie, prone, locators}
//  （nr_rig.hitboxes()）。箱は「ゾンビの足元が原点・r = 右 / u = 上 / f = 前」の直方体で、
//  ワールドへは yaw = getRotation().y から core/util.js の toWorld / toLocal で直す。
//  * 姿勢: nr:state が crawl → prone（うつ伏せ。無ければ lie）、down → lie（仰向け）、
//    dead → nr:pose が 1（前へ倒れた）・5（這ったまま）なら prone、他は lie。それ以外は stand。
//  * 近接 = 目から視線のレイ、飛び道具 = 着弾点に一番近い箱、外れたら「狙いの高さ」で決める。
//  * 2 箱の部位は sub = 0 が上（胸・上腕・太腿）、1 が下（腹・前腕と手・脛と足）。
//  * SHAPES に無い種類は spec の身長から作る人型の箱で代わりをする。
// ===========================================================================
import * as SHP_D from "../data/zombie_shapes.js";
import { zombieSpec } from "../core/hp.js";
import {
  toLocal, toWorld, dirToLocal, dirToWorld, yawOf, getProp, norm, valid, clamp,
} from "../core/util.js";

/** @typedef {import("@minecraft/server").Vector3} Vector3 */
/** @typedef {import("@minecraft/server").Entity} Entity */
/** @typedef {[number, number, number]} RUF */
/** @typedef {{c: number[], h: number[]}} Box */
/** @typedef {"stand" | "lie" | "prone"} Pose */
/**
 * @typedef {object} PartHit
 * @property {string} part   head / torso / arm_r / arm_l / leg_r / leg_l
 * @property {number} sub    0 = 上の箱、1 = 下の箱
 * @property {Vector3} point 当たった点（ワールド）
 * @property {RUF} local     当たった点（ゾンビの局所 [r, u, f]）
 * @property {Pose} pose
 * @property {string} how    "ray" | "near" | "point" | "height" | "given"
 * @property {number} [t]    レイの距離
 */
/** @typedef {{state?: string, pose?: number}} PoseOpts */

export const PARTS = Object.freeze(["head", "torso", "arm_r", "arm_l", "leg_r", "leg_l"]);

/** 部位 → 部位の系統（head / torso / arm / leg）。@param {string} part */
export function groupOf(part) {
  return part === "head" ? "head" : part === "torso" ? "torso" : part.startsWith("arm") ? "arm" : "leg";
}
/** 左右（"r" / "l" / ""）。@param {string} part */
export function sideOf(part) { return part.endsWith("_r") ? "r" : part.endsWith("_l") ? "l" : ""; }

// ---------------------------------------------------------------------------
//  形（SHAPES と代わりの人型）
// ---------------------------------------------------------------------------
/** @type {any} */
const SHD = SHP_D;
/** @type {Record<string, any>} */
const SHAPES = (SHD.SHAPES && typeof SHD.SHAPES === "object") ? SHD.SHAPES : {};

/**
 * @typedef {object} Shape
 * @property {number} height
 * @property {Record<Pose, Record<string, Box[]>>} boxes
 * @property {Record<string, number[]>} locators  立ち姿勢の [r, u, f]
 * @property {number} fBack
 * @property {number} fFront
 * @property {number} hipU
 * @property {boolean} generic
 */
/** @type {Map<string, Shape>} */
const cache = new Map();

/** @param {number} r @param {number} u @param {number} f @param {number} hr @param {number} hu @param {number} hf @returns {Box} */
function box(r, u, f, hr, hu, hf) { return { c: [r, u, f], h: [hr, hu, hf] }; }

/** 人型の代わりの箱（身長 H ブロック）。@param {number} H @param {number} bulk */
function genericStand(H, bulk) {
  const w = 0.2 * bulk;
  return {
    head: [box(0, 0.935 * H, 0.04, 0.13, 0.065 * H, 0.15)],
    torso: [box(0, 0.75 * H, 0.03, w, 0.085 * H, 0.15 * bulk), box(0, 0.575 * H, 0, w * 0.95, 0.09 * H, 0.14 * bulk)],
    arm_r: [box(w + 0.07, 0.715 * H, 0.03, 0.08, 0.11 * H, 0.08), box(w + 0.09, 0.5 * H, 0.03, 0.07, 0.13 * H, 0.08)],
    arm_l: [box(-(w + 0.07), 0.715 * H, 0.03, 0.08, 0.11 * H, 0.08), box(-(w + 0.09), 0.5 * H, 0.03, 0.07, 0.13 * H, 0.08)],
    leg_r: [box(0.1, 0.4 * H, 0, 0.1, 0.13 * H, 0.11), box(0.08, 0.14 * H, 0.03, 0.08, 0.14 * H, 0.12)],
    leg_l: [box(-0.1, 0.4 * H, 0, 0.1, 0.13 * H, 0.11), box(-0.08, 0.14 * H, 0.03, 0.08, 0.14 * H, 0.12)],
  };
}
/** @param {number} H @param {number} w */
function genericLocators(H, w) {
  return {
    loc_neck: [0, 0.87 * H, 0.02], loc_head: [0, 0.94 * H, 0.04], loc_mouth: [0, 0.9 * H, 0.15],
    loc_chest: [0, 0.75 * H, 0.17], loc_waist: [0, 0.55 * H, 0], loc_belly: [0, 0.63 * H, 0.15],
    loc_shoulder_r: [w + 0.05, 0.8 * H, 0], loc_shoulder_l: [-(w + 0.05), 0.8 * H, 0],
    loc_elbow_r: [w + 0.08, 0.61 * H, 0.02], loc_elbow_l: [-(w + 0.08), 0.61 * H, 0.02],
    loc_hand_r: [w + 0.1, 0.38 * H, 0.02], loc_hand_l: [-(w + 0.1), 0.38 * H, 0.02],
    loc_hip_r: [0.1, 0.52 * H, 0], loc_hip_l: [-0.1, 0.52 * H, 0],
    loc_knee_r: [0.08, 0.28 * H, 0], loc_knee_l: [-0.08, 0.28 * H, 0],
  };
}

/** 立ち姿勢の箱から寝た姿勢を作る（nr_rig.hitboxes と同じ式）。@param {Record<string, Box[]>} stand @param {number} fBack @param {number} fFront @param {number} hipU */
function derivePoses(stand, fBack, fFront, hipU) {
  /** @type {Record<string, Box[]>} */ const lie = {};
  /** @type {Record<string, Box[]>} */ const prone = {};
  for (const [p, list] of Object.entries(stand)) {
    lie[p] = list.map((b) => box(b.c[0], b.c[2] - fBack, -b.c[1], b.h[0], b.h[2], b.h[1]));
    prone[p] = list.map((b) => box(b.c[0], fFront - b.c[2], b.c[1] - hipU, b.h[0], b.h[2], b.h[1]));
  }
  return { lie, prone };
}

/** 形を引く（無ければ人型の代わり）。@param {string} key @returns {Shape} */
export function shapeOf(key) {
  const hit = cache.get(key);
  if (hit) return hit;
  const raw = SHAPES[key];
  /** @type {Shape} */
  let s;
  if (raw && raw.stand && raw.stand.head) {
    const all = Object.values(raw.stand).flat();
    const fBack = Math.min(...all.map((b) => b.c[2] - b.h[2]));
    const fFront = Math.max(...all.map((b) => b.c[2] + b.h[2]));
    const thighs = [...(raw.stand.leg_r ?? []), ...(raw.stand.leg_l ?? [])];
    const hipU = thighs.length ? Math.max(...thighs.map((b) => b.c[1] + b.h[1])) : Number(raw.height) * 0.52;
    const der = derivePoses(raw.stand, fBack, fFront, hipU);
    s = {
      height: Number(raw.height) || Math.max(...all.map((b) => b.c[1] + b.h[1])),
      boxes: { stand: raw.stand, lie: raw.lie ?? der.lie, prone: raw.prone ?? der.prone },
      locators: raw.locators ?? {}, fBack, fFront, hipU, generic: false,
    };
  } else {
    const sp = zombieSpec(key);
    const H = clamp((Number(sp?.height_cm) || 180) / 100 * (1 - (Number(sp?.hunch) || 0) / 300), 1.2, 4.5);
    const bulk = clamp(Number(sp?.bulk) || 1, 0.7, 2.2);
    const stand = genericStand(H, bulk);
    const fBack = -0.15 * bulk, fFront = 0.2 * bulk, hipU = 0.52 * H;
    const der = derivePoses(stand, fBack, fFront, hipU);
    s = { height: H, boxes: { stand, lie: der.lie, prone: der.prone }, locators: genericLocators(H, 0.2 * bulk), fBack, fFront, hipU, generic: true };
  }
  cache.set(key, s);
  return s;
}

/** 状態 → 当たり箱の姿勢。@param {string} [state] @param {number} [pose] @returns {Pose} */
export function poseFor(state, pose) {
  if (state === "crawl") return "prone";
  if (state === "down") return "lie";
  if (state === "dead") return pose === 1 || pose === 5 ? "prone" : "lie";
  return "stand";
}

/** @param {Entity} z @param {PoseOpts} [o] @returns {Pose} */
function poseOf(z, o) {
  const state = o?.state ?? String(getProp(z, "nr:state", "normal"));
  const pose = o?.pose ?? Number(getProp(z, "nr:pose", 0));
  return poseFor(state, pose);
}
/** @param {Entity} z */
function keyOf(z) { return z.typeId.startsWith("nr:z_") ? z.typeId.slice(5) : z.typeId; }

/** その姿勢の部位の箱。@param {Entity} z @param {PoseOpts} [o] */
export function boxesOf(z, o) {
  const s = shapeOf(keyOf(z));
  const pose = poseOf(z, o);
  return { pose, boxes: s.boxes[pose] ?? s.boxes.stand, shape: s };
}

// ---------------------------------------------------------------------------
//  幾何
// ---------------------------------------------------------------------------
/** レイと箱（局所）。当たれば距離、外れれば null。@param {number[]} o @param {number[]} d @param {Box} b */
function rayBox(o, d, b) {
  let t0 = 0, t1 = Infinity;
  for (let k = 0; k < 3; k++) {
    const lo = b.c[k] - b.h[k], hi = b.c[k] + b.h[k];
    if (Math.abs(d[k]) < 1e-9) { if (o[k] < lo || o[k] > hi) return null; continue; }
    let a = (lo - o[k]) / d[k], c = (hi - o[k]) / d[k];
    if (a > c) { const tmp = a; a = c; c = tmp; }
    if (a > t0) t0 = a;
    if (c < t1) t1 = c;
    if (t0 > t1) return null;
  }
  return t0;
}
/** 点と箱の距離（中なら 0）。@param {number[]} p @param {Box} b */
function pointBoxDist(p, b) {
  let s = 0;
  for (let k = 0; k < 3; k++) { const d = Math.max(Math.abs(p[k] - b.c[k]) - b.h[k], 0); s += d * d; }
  return Math.sqrt(s);
}
/** 箱の中へ寄せた点。@param {number[]} p @param {Box} b @returns {RUF} */
function clampToBox(p, b) {
  return [clamp(p[0], b.c[0] - b.h[0], b.c[0] + b.h[0]), clamp(p[1], b.c[1] - b.h[1], b.c[1] + b.h[1]), clamp(p[2], b.c[2] - b.h[2], b.c[2] + b.h[2])];
}
/** 箱の中心からの正規化座標（-1..1）での「中心らしさ」（小さいほど中）。@param {number[]} p @param {Box} b */
function centrality(p, b) {
  let s = 0;
  for (let k = 0; k < 3; k++) s = Math.max(s, Math.abs(p[k] - b.c[k]) / Math.max(1e-3, b.h[k]));
  return s;
}

/** @param {Entity} z @param {Pose} pose @param {string} part @param {number} sub @param {RUF} local @param {string} how @param {number} [t] @returns {PartHit} */
function mk(z, pose, part, sub, local, how, t) {
  return { part, sub, local, pose, how, t, point: toWorld(z.location, yawOf(z), local) };
}

// ---------------------------------------------------------------------------
//  判定
// ---------------------------------------------------------------------------
/**
 * レイ（目から視線など）で部位を選ぶ。当たり箱に当たらなければ一番近い箱（how = "near"）。
 * @param {Entity} z @param {Vector3} origin @param {Vector3} dir @param {PoseOpts & {maxDist?: number}} [o]
 * @returns {PartHit | undefined}
 */
export function rayPart(z, origin, dir, o) {
  if (!valid(z)) return undefined;
  const { pose, boxes } = boxesOf(z, o);
  const yaw = yawOf(z), feet = z.location;
  const lo = toLocal(feet, yaw, origin);
  const ld = dirToLocal(yaw, norm(dir));
  const maxDist = o?.maxDist ?? 16;
  /** @type {{part: string, sub: number, t: number} | undefined} */
  let best;
  for (const part of PARTS) {
    const list = boxes[part] ?? [];
    for (let i = 0; i < list.length; i++) {
      const t = rayBox(lo, ld, list[i]);
      if (t !== null && t <= maxDist && (!best || t < best.t)) best = { part, sub: i, t };
    }
  }
  if (best) {
    const p = /** @type {RUF} */ ([lo[0] + ld[0] * best.t, lo[1] + ld[1] * best.t, lo[2] + ld[2] * best.t]);
    return mk(z, pose, best.part, best.sub, p, "ray", best.t);
  }
  // 外れた: レイに一番近い箱
  /** @type {{part: string, sub: number, d: number, p: RUF} | undefined} */
  let near;
  for (const part of PARTS) {
    const list = boxes[part] ?? [];
    for (let i = 0; i < list.length; i++) {
      const b = list[i];
      const tc = clamp((b.c[0] - lo[0]) * ld[0] + (b.c[1] - lo[1]) * ld[1] + (b.c[2] - lo[2]) * ld[2], 0, maxDist);
      const q = [lo[0] + ld[0] * tc, lo[1] + ld[1] * tc, lo[2] + ld[2] * tc];
      const d = pointBoxDist(q, b);
      if (!near || d < near.d) near = { part, sub: i, d, p: clampToBox(q, b) };
    }
  }
  if (near && near.d < 1.0) return mk(z, pose, near.part, near.sub, near.p, "near");
  return undefined;
}

/**
 * 点（飛び道具の着弾点など）に一番近い箱の部位。
 * @param {Entity} z @param {Vector3} point @param {PoseOpts} [o] @returns {PartHit | undefined}
 */
export function pointPart(z, point, o) {
  if (!valid(z)) return undefined;
  const { pose, boxes } = boxesOf(z, o);
  const p = toLocal(z.location, yawOf(z), point);
  /** @type {{part: string, sub: number, d: number, c: number, q: RUF} | undefined} */
  let best;
  for (const part of PARTS) {
    const list = boxes[part] ?? [];
    for (let i = 0; i < list.length; i++) {
      const d = pointBoxDist(p, list[i]);
      const c = centrality(p, list[i]);
      if (!best || d < best.d - 1e-4 || (Math.abs(d - best.d) <= 1e-4 && c < best.c)) best = { part, sub: i, d, c, q: clampToBox(p, list[i]) };
    }
  }
  return best ? mk(z, pose, best.part, best.sub, best.q, "point") : undefined;
}

/**
 * 狙いの高さ（ワールドの y）と左右の手がかりで決める最後の手段。
 * @param {Entity} z @param {number} y @param {number} [rHint] 局所の r（+ = ゾンビの右）
 * @param {PoseOpts} [o] @returns {PartHit}
 */
export function heightPart(z, y, rHint = 0, o) {
  const { pose, boxes, shape } = boxesOf(z, o);
  const side = rHint < 0 ? "l" : "r";
  let part = "torso", sub = 0;
  if (pose === "stand") {
    const f = (y - z.location.y) / Math.max(0.5, shape.height);
    if (f > 0.82) part = "head";
    else if (f > 0.47) {
      const tw = Math.max(...(boxes.torso ?? []).map((b) => b.h[0]), 0.2);
      part = Math.abs(rHint) > tw ? `arm_${side}` : "torso";
      sub = f > 0.65 ? 0 : 1;
    } else { part = `leg_${side}`; sub = f > 0.25 ? 0 : 1; }
  }
  const b = (boxes[part] ?? boxes.torso ?? [])[sub] ?? (boxes[part] ?? boxes.torso)[0];
  return mk(z, pose, part, b === (boxes[part] ?? [])[sub] ? sub : 0, /** @type {RUF} */ ([...b.c]), "height");
}

/**
 * hit から部位を決める（applyHit が使う）。順に: hit.part（点があれば箱の上下も）→ hit.point →
 * 攻撃者の目からのレイ（プレイヤーは視線、他は自分の方へ）→ 狙いの高さ。必ず何か返す。
 * @param {Entity} z @param {{part?: string, sub?: number, point?: Vector3, attacker?: Entity, dir?: Vector3}} hit @param {PoseOpts} [o]
 * @returns {PartHit}
 */
export function locate(z, hit, o) {
  const { pose, boxes } = boxesOf(z, o);
  if (hit.part && PARTS.includes(hit.part)) {
    const list = boxes[hit.part] ?? [];
    let sub = Number.isInteger(hit.sub) ? clamp(Number(hit.sub), 0, Math.max(0, list.length - 1)) : 0;
    let local = /** @type {RUF} */ (list[sub] ? [...list[sub].c] : [0, 1, 0]);
    if (hit.point && list.length) {
      const p = toLocal(z.location, yawOf(z), hit.point);
      let bd = Infinity;
      list.forEach((b, i) => { const d = pointBoxDist(p, b); if (d < bd) { bd = d; sub = i; } });
      local = clampToBox(p, list[sub]);
    }
    return mk(z, pose, hit.part, sub, local, "given");
  }
  if (hit.point) { const r = pointPart(z, hit.point, o); if (r) return r; }
  const a = hit.attacker;
  if (valid(a)) {
    try {
      const eye = a.getHeadLocation();
      const dir = a.typeId === "minecraft:player" ? a.getViewDirection() : norm({ x: z.location.x - eye.x, y: z.location.y + 1.2 - eye.y, z: z.location.z - eye.z });
      const r = rayPart(z, eye, dir, { ...(o ?? {}), maxDist: 12 });
      if (r) return r;
      const rl = toLocal(z.location, yawOf(z), eye)[0];
      return heightPart(z, eye.y + dir.y * Math.hypot(z.location.x - eye.x, z.location.z - eye.z), -rl, o);
    } catch { /* 攻撃者が読めない */ }
  }
  return heightPart(z, z.location.y + 1.0, 0, o);
}

// ---------------------------------------------------------------------------
//  位置（部位の中心・ロケータ）
// ---------------------------------------------------------------------------
/** 部位の箱の中心（ワールド）。@param {Entity} z @param {string} part @param {number} [sub] @param {PoseOpts} [o] */
export function partCenter(z, part, sub = 0, o) {
  const { boxes } = boxesOf(z, o);
  const list = boxes[part] ?? boxes.torso ?? [];
  const b = list[Math.min(sub, list.length - 1)] ?? { c: [0, 1, 0] };
  return toWorld(z.location, yawOf(z), b.c);
}

/** 立ち姿勢の局所座標を、姿勢に合わせて直す。@param {Shape} s @param {Pose} pose @param {ArrayLike<number>} p @returns {RUF} */
function posePoint(s, pose, p) {
  if (pose === "lie") return [p[0], p[2] - s.fBack, -p[1]];
  if (pose === "prone") return [p[0], s.fFront - p[2], p[1] - s.hipU];
  return [p[0], p[1], p[2]];
}
/** 向きも同じように。@param {Pose} pose @param {ArrayLike<number>} d @returns {RUF} */
function poseDir(pose, d) {
  if (pose === "lie") return [d[0], d[2], -d[1]];
  if (pose === "prone") return [d[0], -d[2], d[1]];
  return [d[0], d[1], d[2]];
}

// 断面ロケータの「外向き」（立ち姿勢の局所の向き。噴水・しぶきの向き）
/** @type {Record<string, number[]>} */
const LOC_DIR = {
  loc_neck: [0, 1, 0.15], loc_head: [0, 1, 0], loc_mouth: [0, -0.3, 1], loc_chest: [0, 0, 1], loc_belly: [0, -0.3, 1],
  loc_waist: [0, -1, 0], loc_shoulder_r: [1, 0.4, 0], loc_shoulder_l: [-1, 0.4, 0], loc_elbow_r: [0.3, -1, 0.2],
  loc_elbow_l: [-0.3, -1, 0.2], loc_hand_r: [0, -1, 0], loc_hand_l: [0, -1, 0], loc_hip_r: [0.2, -1, 0],
  loc_hip_l: [-0.2, -1, 0], loc_knee_r: [0, -1, 0.2], loc_knee_l: [0, -1, 0.2],
};

/** ロケータが無い形で、箱から近い位置を作る。@param {Shape} s @param {string} name @returns {number[]} */
function locFromBoxes(s, name) {
  const B = s.boxes.stand;
  const side = name.endsWith("_r") ? "r" : "l";
  const top = (/** @type {Box | undefined} */ b) => (b ? [b.c[0], b.c[1] + b.h[1], b.c[2]] : [0, s.height * 0.5, 0]);
  const bot = (/** @type {Box | undefined} */ b) => (b ? [b.c[0], b.c[1] - b.h[1], b.c[2]] : [0, s.height * 0.5, 0]);
  if (name === "loc_neck" || name === "loc_mouth") return bot(B.head?.[0]);
  if (name === "loc_head") return B.head?.[0]?.c ?? [0, s.height * 0.93, 0];
  if (name.startsWith("loc_shoulder")) return top(B[`arm_${side}`]?.[0]);
  if (name.startsWith("loc_elbow")) return bot(B[`arm_${side}`]?.[0]);
  if (name.startsWith("loc_hand")) return bot(B[`arm_${side}`]?.[1]);
  if (name.startsWith("loc_hip")) return top(B[`leg_${side}`]?.[0]);
  if (name.startsWith("loc_knee")) return bot(B[`leg_${side}`]?.[0]);
  if (name === "loc_waist") return top(B.torso?.[1]);
  if (name === "loc_chest" || name === "loc_belly") return B.torso?.[name === "loc_chest" ? 0 : 1]?.c ?? [0, s.height * 0.65, 0.1];
  return [0, s.height * 0.6, 0];
}

/**
 * ロケータ（loc_neck・loc_shoulder_r など。nr_rig の LOCATOR_BONES）のワールド位置。姿勢に合わせる。
 * @param {Entity} z @param {string} name @param {PoseOpts} [o]
 */
export function locatorPos(z, name, o) {
  const s = shapeOf(keyOf(z));
  const pose = poseOf(z, o);
  const raw = s.locators[name] ?? locFromBoxes(s, name);
  return toWorld(z.location, yawOf(z), posePoint(s, pose, raw));
}

/** ロケータの外向き（ワールドの単位ベクトル）。@param {Entity} z @param {string} name @param {PoseOpts} [o] */
export function locatorDir(z, name, o) {
  const pose = poseOf(z, o);
  const d = LOC_DIR[name] ?? [0, 1, 0];
  return norm(dirToWorld(yawOf(z), poseDir(pose, d)), { x: 0, y: 1, z: 0 });
}

// ---------------------------------------------------------------------------
//  弱点のゾーン（spec の WEAK_ZONES）
// ---------------------------------------------------------------------------
/**
 * 当たった点が弱点のゾーンか。ranged = 射撃・刺突の命中（nodes はどこでも可）。
 * @param {Entity} z @param {PartHit} ph @param {string} zone @param {boolean} [ranged]
 */
export function inZone(z, ph, zone, ranged = false) {
  if (zone === "any") return true;
  const s = shapeOf(keyOf(z));
  const list = s.boxes[ph.pose]?.[ph.part] ?? [];
  const b = list[ph.sub] ?? list[0];
  if (!b) return false;
  // 箱の中の正規化座標 → 立ち姿勢の体の向き（nr = 右、nu = 上、nf = 前）に戻す
  const n = [0, 1, 2].map((k) => clamp((ph.local[k] - b.c[k]) / Math.max(1e-3, b.h[k]), -1, 1));
  let nr = n[0], nu = n[1], nf = n[2];
  if (ph.pose === "lie") { nf = n[1]; nu = -n[2]; } else if (ph.pose === "prone") { nf = -n[1]; nu = n[2]; }
  void nr;
  switch (zone) {
    case "throat": return (ph.part === "head" && nu < -0.2 && nf > -0.4) || (ph.part === "torso" && ph.sub === 0 && nu > 0.6 && nf > 0);
    case "back": return ph.part === "torso" && nf < 0;
    case "belly": return ph.part === "torso" && nf > 0 && (ph.sub === 1 || nu < 0);
    case "nodes": return ranged || (ph.part === "torso" && nf > -0.2);
    case "heads": return (ph.part === "torso" && nf < 0 && (ph.sub === 0 || nu > 0)) || ((ph.part === "arm_r" || ph.part === "arm_l") && ph.sub === 0 && nu > 0.3);
    default: return false;
  }
}
