// 数学の小道具。向きの約束: yaw=0 で北 (-Z) を向く。前 = (-sin yaw, 0, -cos yaw)。
// Object3D.rotation.y = yaw とすれば、ローカル -Z を前にしたモデルがその向きを向く。

export const TAU = Math.PI * 2;

export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const invLerp = (a, b, v) => (b === a ? 0 : (v - a) / (b - a));
export const smoothstep = (a, b, v) => {
  const t = clamp(invLerp(a, b, v), 0, 1);
  return t * t * (3 - 2 * t);
};
// フレームレートに依存しない指数的な追従。lambda が大きいほど速い。
export const damp = (a, b, lambda, dt) => lerp(a, b, 1 - Math.exp(-lambda * dt));
export const approach = (cur, target, delta) =>
  cur < target ? Math.min(cur + delta, target) : Math.max(cur - delta, target);

export const wrapAngle = (a) => {
  a = (a + Math.PI) % TAU;
  if (a < 0) a += TAU;
  return a - Math.PI;
};
export const angleDiff = (from, to) => wrapAngle(to - from);
export const dampAngle = (a, b, lambda, dt) => a + angleDiff(a, b) * (1 - Math.exp(-lambda * dt));
export const approachAngle = (a, b, delta) => {
  const d = angleDiff(a, b);
  return Math.abs(d) <= delta ? b : a + Math.sign(d) * delta;
};

// yaw から前方向・右方向
export const forwardX = (yaw) => -Math.sin(yaw);
export const forwardZ = (yaw) => -Math.cos(yaw);
export const rightX = (yaw) => Math.cos(yaw);
export const rightZ = (yaw) => -Math.sin(yaw);
export function forwardFromYaw(yaw, out) {
  out.x = -Math.sin(yaw);
  out.y = 0;
  out.z = -Math.cos(yaw);
  return out;
}
export function rightFromYaw(yaw, out) {
  out.x = Math.cos(yaw);
  out.y = 0;
  out.z = -Math.sin(yaw);
  return out;
}
// 水平方向ベクトル (dx, dz) が指す yaw
export const yawFromDir = (dx, dz) => Math.atan2(-dx, -dz);

export const distXZ = (a, b) => Math.hypot(a.x - b.x, a.z - b.z);
export const distSqXZ = (a, b) => (a.x - b.x) ** 2 + (a.z - b.z) ** 2;

export const easeOutCubic = (t) => 1 - (1 - t) ** 3;
export const easeInOutSine = (t) => -(Math.cos(Math.PI * t) - 1) / 2;
export const easeOutBack = (t) => {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2;
};

// 再現できる乱数 (mulberry32)。rng() は [0,1)。
export function makeRng(seed) {
  let a = seed >>> 0;
  const rng = () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  rng.range = (lo, hi) => lo + (hi - lo) * rng();
  rng.int = (lo, hi) => Math.floor(lo + (hi - lo + 1) * rng()); // lo..hi を含む
  rng.pick = (arr) => arr[Math.floor(rng() * arr.length)];
  rng.chance = (p) => rng() < p;
  rng.fork = (salt = 1) => makeRng((Math.floor(rng() * 4294967296) ^ Math.imul(salt, 0x9e3779b1)) >>> 0);
  return rng;
}

// 座標から決まる 0..1 のハッシュ
export function hash2(x, z, seed = 0) {
  let h = Math.imul((x | 0) ^ 0x27d4eb2d, 0x165667b1) ^ Math.imul((z | 0) ^ seed, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

// 点 p が中心 c・向き yaw・半角 half・距離 range の扇に入るか（水平のみ）
export function inCone(c, yaw, half, range, p) {
  const dx = p.x - c.x, dz = p.z - c.z;
  const d = Math.hypot(dx, dz);
  if (d > range) return false;
  if (d < 1e-4) return true;
  return Math.abs(angleDiff(yaw, yawFromDir(dx, dz))) <= half;
}
