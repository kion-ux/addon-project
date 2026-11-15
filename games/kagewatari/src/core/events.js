// 小さなイベントバス。名前と中身は ARCHITECTURE.md の「イベント」に一覧がある。
export class Events {
  constructor() {
    this.map = new Map();
  }
  on(name, fn) {
    let set = this.map.get(name);
    if (!set) this.map.set(name, (set = new Set()));
    set.add(fn);
    return () => set.delete(fn);
  }
  once(name, fn) {
    const off = this.on(name, (p) => {
      off();
      fn(p);
    });
    return off;
  }
  off(name, fn) {
    this.map.get(name)?.delete(fn);
  }
  emit(name, payload = {}) {
    const set = this.map.get(name);
    if (!set) return;
    for (const fn of [...set]) {
      try {
        fn(payload);
      } catch (err) {
        console.error(`[events] ${name} handler failed`, err);
      }
    }
  }
}
