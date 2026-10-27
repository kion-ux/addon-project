// ===========================================================================
//  NIGHT RUNNER: 感染都市 — スクリプトの入口（DESIGN §12「手書きスクリプトの構成」）
//
//  各モジュールを import して登録するだけ（ここに処理を書かない）。各フォルダの持ち主は
//  自分のフォルダの index.js だけを編集する（このファイルは触らない）。
//
//  起動の順（2.x の early execution。reference/script_api.md §1）:
//    1. core/  … 設定・予算・演出の包み・本当の体力・バス・カスタムコンポーネントの登録
//              （最上位は subscribe だけ。components.js は startup で BP の nr:* を全部登録し、
//               各モジュールが import の時に onBlockComponent / onItemComponent で足したフックへ配る）
//    2. gore/  … 部位判定・ゴア・gib・血・死亡（entityHurt / entityDie / entityHitEntity を購読）
//    3. 各フォルダ（zombies / player / combat / world / ui）
//  world を触る初期化は各モジュールの world.afterEvents.worldLoad か system.run の中で行う。
// ===========================================================================
import "./core/util.js";
import "./core/bus.js";
import "./core/settings.js";
import "./core/budget.js";
import "./core/fx.js";
import "./core/hp.js";
import "./core/components.js";
import "./gore/hitloc.js";
import "./gore/blood.js";
import "./gore/gibs.js";
import "./gore/death.js";
import "./gore/gore.js";
import "./zombies/index.js";
import "./player/index.js";
import "./combat/index.js";
import "./world/index.js";
import "./ui/index.js";
