// ===========================================================================
//  武器が纏う気配 — 持っているだけで武器の周りに属性の粒が漂う
//  大剣は星、双剣は風、斧は火の粉、ダガーは影、弓は光の羽、盾は雪、鞭は花弁、
//  かぎ爪は火花。ゲージが満タンの時は足元から闘気が立ち昇る。
// ===========================================================================
import { GAUGE_MAX } from "./config.js";
import { gauge } from "./combat.js";
import { P, white } from "./fx.js";
import { allPlayers, rand } from "./util.js";

/** 右手のおおよその位置（体の向きから）。 */
function handPos(p) {
  let yaw = 0;
  try { yaw = (p.getRotation?.().y ?? 0) * Math.PI / 180; } catch (_) { }
  // Minecraft の yaw: 0 で +Z（南）を向く。右手は向きの右側
  const fx = -Math.sin(yaw), fz = Math.cos(yaw);
  const rx = -fz, rz = fx;
  const l = p.location;
  return { x: l.x + rx * 0.38 + fx * 0.35, y: l.y + 0.85, z: l.z + rz * 0.38 + fz * 0.35, fx, fz };
}

const KIND = {
  greatsword: (d, h, c) => P(d, "star", { x: h.x, y: h.y + rand(0.2, 1.2), z: h.z }, { color: white(c, 0.3), count: 1, spread: 0.5, life: 1.2 }),
  twinblades: (d, h, c) => P(d, "wind", h, { color: c, count: 1, dir: { x: h.fx, y: 0.3, z: h.fz }, speed: 1.5, size: 0.5 }),
  greataxe: (d, h, c) => P(d, "ember", { x: h.x, y: h.y + 0.6, z: h.z }, { color: c, count: 2, spread: 0.4, speed: 0.6 }),
  dagger: (d, h, c) => P(d, "smoke", h, { color: [0.18, 0.08, 0.26], count: 1, spread: 0.25, size: 0.6, speed: 0.3 }),
  bow: (d, h, c) => P(d, "feather", { x: h.x, y: h.y + 0.8, z: h.z }, { color: [1, 0.97, 0.86], count: 1, spread: 0.5, life: 1.6 }),
  shield: (d, h, c) => P(d, "snow", { x: h.x, y: h.y + 0.6, z: h.z }, { color: c, count: 2, spread: 0.6 }),
  whip: (d, h, c) => P(d, "petal", { x: h.x, y: h.y - 0.2, z: h.z }, { color: c, count: 1, spread: 0.4, speed: 0.4 }),
  claws: (d, h, c) => P(d, "spark", { x: h.x, y: h.y - 0.3, z: h.z }, { color: c, count: 2, speed: 2.0, size: 0.6 }),
};

export function tickAmbient(heldWeapon) {
  for (const p of allPlayers()) {
    const w = heldWeapon(p);
    if (!w) continue;
    const h = handPos(p);
    try { KIND[w.key]?.(p.dimension, h, w.color); } catch (_) { }
    if (gauge(p) >= GAUGE_MAX) {
      P(p.dimension, "aura", p.location, { color: w.color, count: 3, spread: 0.5, size: 1.1 });
    }
  }
}
