// 仮の街: 平らな地面と箱の建物が少し。データは空に近い。
export class City {
  constructor(game) { this.game = game; }
  init() {
    const { THREE, scene, collision } = this.game;
    this.root = new THREE.Group(); scene.add(this.root);
    this.bounds = { minX: -210, maxX: 210, minZ: -210, maxZ: 210 };
    this.seaLevel = -1.2;
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(420, 420).rotateX(-Math.PI / 2), new THREE.MeshLambertMaterial({ color: 0x8c8172 }));
    this.root.add(ground);
    collision.addBox({ x: -210, y: -2, z: -210 }, { x: 210, y: 0, z: 210 }, { kind: 'ground' });
    this.buildings = [];
    const mat = new THREE.MeshLambertMaterial({ color: 0xefe6d8 });
    const add = (x, z, w, d, h) => {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, h / 2, z); this.root.add(m);
      const min = { x: x - w / 2, y: 0, z: z - d / 2 }, max = { x: x + w / 2, y: h, z: z + d / 2 };
      collision.addBox(min, max, { kind: 'building', climbable: true });
      this.buildings.push({ id: 'b' + this.buildings.length, min, max, roofY: h, roofType: 'flat', district: 'market' });
    };
    add(0, -14, 10, 8, 7); add(12, -14, 8, 8, 9); add(-12, -16, 8, 10, 6); add(4, 10, 6, 6, 1.1);
    this.districts = [{ id: 'market', name: '市場区', nameEn: 'Market', rect: { ...this.bounds }, center: { x: 0, z: 0 } }];
    const w = 210, cs = 2;
    this.navGrid = { cellSize: cs, originX: -w, originZ: -w, w: w, h: w, walk: new Uint8Array(w * w).fill(1), height: new Float32Array(w * w) };
    this.spawnPoints = { player: { x: 0, y: 0, z: 0, yaw: 0 }, civilians: [] };
    for (const k of ['patrols', 'guardPosts', 'archerPosts', 'towers', 'targets', 'hidingSpots', 'chests', 'collectibles', 'shops', 'races', 'ziplines', 'restricted', 'landmarks']) this[k] = [];
  }
  update() {}
  isRestricted() { return false; }
  districtAt() { return this.districts[0]; }
  applyQuality() {}
}
