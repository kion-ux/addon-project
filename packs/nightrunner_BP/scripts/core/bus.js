// ===========================================================================
//  NIGHT RUNNER: 感染都市 — モジュール間の通知（小さな pub/sub）
//
//  ゴア・死亡・装甲などの出来事を HUD・経験値・コンボ・能力へ知らせる。購読者の例外は
//  他の購読者を止めない。出来事の名前と中身は reference/nr_scripts.md の表が正。
// ===========================================================================

/** 出来事の名前（打ち間違い防止の定数）。 */
export const EV = Object.freeze({
  HIT: "hit",                   // ゾンビ（死体も）に applyHit が当たった
  SEVER: "sever",               // 四肢・下半身・頭がちぎれた
  DECAP: "decap",               // 首が飛んだ
  HEADSHOT: "headshot",         // 頭に命中（飛び道具・ヒットスキャン・頭が弾けた近接）
  CRUSH: "crush",               // 頭が潰れた（頭蓋粉砕）
  GUTTED: "gutted",             // 腹が裂けて内臓がこぼれた
  HALVED: "halved",             // 胴が真っ二つ
  KILL: "kill",                 // 死んだ（nr:hp <= 0・即死部位・オーバーキル）
  ARMOR_BREAK: "armor_break",   // nr:armor が 1 段下がった
  WEAKSPOT: "weakspot",         // gore.weak_spots の弱点に当たった（能力の発動は zombies/abilities.js）
  STAGGER: "stagger",           // よろめいた
  KNOCKDOWN: "knockdown",       // 倒れた（nr:state down）
  CRAWL: "crawl",               // 這う状態になった（nr:to_crawl）
  REGROW: "regrow",             // gore.regrow で部位が生え戻った
  CORPSE: "corpse",             // 死体ができた・消えた
  GIB: "gib",                   // gib が出た
  SETTINGS: "settings",         // 設定が変わった
});

/** @type {Map<string, Set<(data: any) => void>>} */
const subs = new Map();

/**
 * 購読する。戻り値を呼ぶと解除。
 * @param {string} name @param {(data: any) => void} fn @returns {() => void}
 */
export function on(name, fn) {
  let s = subs.get(name);
  if (!s) { s = new Set(); subs.set(name, s); }
  s.add(fn);
  return () => off(name, fn);
}

/** @param {string} name @param {(data: any) => void} fn */
export function off(name, fn) { subs.get(name)?.delete(fn); }

/** 一度だけ受け取る。 @param {string} name @param {(data: any) => void} fn */
export function once(name, fn) {
  const un = on(name, (d) => { un(); fn(d); });
  return un;
}

/**
 * 知らせる（同期）。購読者の例外は握って警告だけ出す。
 * @param {string} name @param {any} [data]
 */
export function emit(name, data) {
  const s = subs.get(name);
  if (!s || !s.size) return;
  for (const fn of [...s]) {
    try { fn(data); } catch (err) { console.warn("[nr] bus", name, err instanceof Error ? err.message : err); }
  }
}

/** 購読者の数（テスト・デバッグ用）。 @param {string} name */
export function listeners(name) { return subs.get(name)?.size ?? 0; }
