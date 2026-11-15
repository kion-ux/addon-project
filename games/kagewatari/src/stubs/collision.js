// 仮の CollisionWorld（本物が読めない時の代役）。総当たりで単純に判定する。
export class CollisionWorld {
  constructor(game) { this.game = game; this.colliders = []; this.waters = []; this._id = 0; }
  init() {}
  addBox(min, max, opts = {}) {
    const c = { id: ++this._id, type: 'box', min: { ...min }, max: { ...max }, axis: 'x', rise: 1, kind: opts.kind || 'prop', climbable: !!opts.climbable, soft: !!opts.soft, data: opts.data };
    this.colliders.push(c); return c;
  }
  addWedge(min, max, axis, rise, opts = {}) { const c = this.addBox(min, max, opts); c.type = 'wedge'; c.axis = axis; c.rise = rise; return c; }
  addWater(min, max) { const w = { min: { ...min }, max: { ...max } }; this.waters.push(w); return w; }
  topAt(c, x, z) {
    if (c.type !== 'wedge') return c.max.y;
    const a = c.axis, t = ((a === 'x' ? x : z) - c.min[a]) / (c.max[a] - c.min[a] || 1);
    const k = Math.min(1, Math.max(0, c.rise > 0 ? t : 1 - t));
    return c.min.y + (c.max.y - c.min.y) * k;
  }
  queryAABB(x0, y0, z0, x1, y1, z1, out = []) {
    out.length = 0;
    for (const c of this.colliders) if (c.max.x > x0 && c.min.x < x1 && c.max.y > y0 && c.min.y < y1 && c.max.z > z0 && c.min.z < z1) out.push(c);
    return out;
  }
  groundAt(x, z, fromY, radius = 0) {
    let best = null;
    for (const c of this.colliders) {
      if (x < c.min.x - radius || x > c.max.x + radius || z < c.min.z - radius || z > c.max.z + radius) continue;
      const top = this.topAt(c, x, z);
      if (top <= fromY + 0.05 && (!best || top > best.y)) best = { y: top, collider: c };
    }
    return best;
  }
  moveCapsule(pos, radius, height, delta, opts = {}) {
    const step = opts.stepHeight ?? 0.45;
    const r = { onGround: false, groundY: -Infinity, ground: null, hitWall: false, wallNormal: { x: 0, z: 0 }, wallCollider: null, hitCeiling: false, stepped: false };
    pos.x += delta.x; pos.z += delta.z;
    for (const c of this.colliders) {
      const top = this.topAt(c, pos.x, pos.z);
      if (top <= pos.y + step || c.min.y >= pos.y + height) continue;
      const cx = Math.max(c.min.x, Math.min(pos.x, c.max.x)), cz = Math.max(c.min.z, Math.min(pos.z, c.max.z));
      const dx = pos.x - cx, dz = pos.z - cz, d = Math.hypot(dx, dz);
      if (d >= radius) continue;
      if (d > 1e-5) { pos.x = cx + (dx / d) * radius; pos.z = cz + (dz / d) * radius; r.wallNormal = { x: dx / d, z: dz / d }; }
      else { pos.x = c.max.x + radius; r.wallNormal = { x: 1, z: 0 }; }
      r.hitWall = true; r.wallCollider = c;
    }
    pos.y += delta.y;
    const g = this.groundAt(pos.x, pos.z, pos.y + step, radius * 0.5);
    if (g && pos.y <= g.y + 0.02) { r.stepped = pos.y < g.y - 0.02; pos.y = g.y; r.onGround = true; r.groundY = g.y; r.ground = g.collider; }
    return r;
  }
  raycast(o, d, maxDist, opts = {}) {
    let best = null;
    for (const c of this.colliders) {
      if (opts.ignoreSoft !== false && c.soft) continue;
      let t0 = 0, t1 = maxDist, n = null;
      for (const a of ['x', 'y', 'z']) {
        if (Math.abs(d[a]) < 1e-9) { if (o[a] < c.min[a] || o[a] > c.max[a]) { t0 = Infinity; break; } continue; }
        let ta = (c.min[a] - o[a]) / d[a], tb = (c.max[a] - o[a]) / d[a];
        if (ta > tb) [ta, tb] = [tb, ta];
        if (ta > t0) { t0 = ta; n = { x: 0, y: 0, z: 0 }; n[a] = d[a] > 0 ? -1 : 1; }
        t1 = Math.min(t1, tb);
        if (t0 > t1) { t0 = Infinity; break; }
      }
      if (t0 < Infinity && t0 <= maxDist && (!best || t0 < best.distance)) {
        best = { distance: t0, point: { x: o.x + d.x * t0, y: o.y + d.y * t0, z: o.z + d.z * t0 }, normal: n || { x: 0, y: 1, z: 0 }, collider: c };
      }
    }
    return best;
  }
  lineOfSight(a, b) {
    const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z, L = Math.hypot(dx, dy, dz) || 1;
    return !this.raycast(a, { x: dx / L, y: dy / L, z: dz / L }, L - 0.05);
  }
  wallProbe(pos, yaw, distance, h) {
    const o = { x: pos.x, y: pos.y + h, z: pos.z }, d = { x: -Math.sin(yaw), y: 0, z: -Math.cos(yaw) };
    const hit = this.raycast(o, d, distance);
    if (!hit) return null;
    return { collider: hit.collider, normal: { x: -d.x, z: -d.z }, point: hit.point, topY: this.topAt(hit.collider, hit.point.x, hit.point.z), climbable: hit.collider.climbable };
  }
  waterAt(x, z) { for (const w of this.waters) if (x >= w.min.x && x <= w.max.x && z >= w.min.z && z <= w.max.z) return w.max.y; return null; }
  pointInside(x, y, z) { for (const c of this.colliders) if (x > c.min.x && x < c.max.x && z > c.min.z && z < c.max.z && y > c.min.y && y < this.topAt(c, x, z)) return c; return null; }
}
