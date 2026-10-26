// 自己テスト用の偽アドオンの補助（モジュールの相対 import と、テストからの直接 import を確かめる）。
import { SHAPES } from "./data/zombie_shapes.js";

export const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y, z: a.z - b.z });
export function norm(v) { const l = Math.hypot(v.x, v.y, v.z) || 1; return { x: v.x / l, y: v.y / l, z: v.z / l }; }

function rayBox(o, d, b) {
  let t0 = 0, t1 = Infinity;
  for (const [k, i] of [["r", 0], ["u", 1], ["f", 2]]) {
    const lo = b.c[i] - b.h[i], hi = b.c[i] + b.h[i];
    if (Math.abs(d[k]) < 1e-9) { if (o[k] < lo || o[k] > hi) return null; continue; }
    let a = (lo - o[k]) / d[k], c = (hi - o[k]) / d[k];
    if (a > c) [a, c] = [c, a];
    t0 = Math.max(t0, a); t1 = Math.min(t1, c);
    if (t0 > t1) return null;
  }
  return t0;
}

/**
 * 視線（目の位置 o・向き d）がゾンビのどの部位の箱に最初に当たるか（DESIGN.md §4 の部位判定の縮小版）。
 * @param {{location: {x:number,y:number,z:number}, getRotation(): {x:number,y:number}, getProperty(n: string): any}} z
 */
export function hitPart(z, o, d) {
  const shape = SHAPES.test;
  const st = String(z.getProperty("nr:state"));
  const pose = st === "dead" || st === "down" || st === "crawl" ? "lie" : "stand";
  const yaw = z.getRotation().y * Math.PI / 180;
  const F = { x: -Math.sin(yaw), z: Math.cos(yaw) }, R = { x: -Math.cos(yaw), z: -Math.sin(yaw) };
  const L = z.location;
  const lo = { r: (o.x - L.x) * R.x + (o.z - L.z) * R.z, u: o.y - L.y, f: (o.x - L.x) * F.x + (o.z - L.z) * F.z };
  const ld = { r: d.x * R.x + d.z * R.z, u: d.y, f: d.x * F.x + d.z * F.z };
  let best = null;
  for (const [part, boxes] of Object.entries(shape[pose])) {
    for (const b of boxes) {
      const t = rayBox(lo, ld, b);
      if (t !== null && (!best || t < best.t)) best = { t, part };
    }
  }
  return best ? best.part : "miss";
}
