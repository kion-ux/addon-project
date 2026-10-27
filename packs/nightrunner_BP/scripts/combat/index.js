// ===========================================================================
//  NIGHT RUNNER: 感染都市 — combat/ の入口（main.js が import する）
//
//  このファイルは combat/ の持ち主が埋める: 近接・飛び道具・投擲・改造・耐久・とどめ（combat/melee.js ranged.js throwables.js mods.js durability.js finishers.js）。
//  main.js は編集しない。このフォルダのモジュールはここで import して登録する（最上位は subscribe と
//  system.beforeEvents.startup の登録だけ。world を触るのは worldLoad の後）。
//  共通の API は tools/nightrunner/reference/nr_scripts.md（applyHit・バス・演出の包み・設定）。
// ===========================================================================
export {};
