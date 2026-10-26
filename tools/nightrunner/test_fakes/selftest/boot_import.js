// 自己テスト: 起動で壊れるアドオン（3）— 2.3.0 安定版に無い（ベータ専用の）名前を import する。
// 実機でもモジュールの読み込みで失敗する。偽物も d.ts の名前しか export しないので Node が SyntaxError を出す。
import { world, AABB } from "@minecraft/server";

world.afterEvents.worldLoad.subscribe(() => { void AABB; });
