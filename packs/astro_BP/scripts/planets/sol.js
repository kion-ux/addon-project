// ===========================================================================
//  太陽 ソル・オーバードライブ — 仮の技（TODO）
//
//  TODO(sol の担当): この形態の技をここに書く。今は engine.js の genericMoves("sol")
//  （惑星の色で描く汎用の技一式）で動いているので、変身・4 技・三段目・変身の締めは一通り遊べる。
//  * 書き方: planets/_template.js（雛形）と planets/earth.js（見本）、
//    tools/astro/planets/_template/README_moves.md（ctx と演出・当たりの関数の説明）
//  * 技の名前・説明・再使用・コストは data.js の PLANETS.sol.moves（astro_data.py が出所）
//  * パッシブの special は "corona"（効果 effects は passives.js が自動で掛ける）
//  * 確かめる: python3 tools/astro/test_astro.py --planet sol
// ===========================================================================
import { register, genericMoves } from "../engine.js";

const KEY = "sol";
const TEMP = genericMoves(KEY);   // TODO: 自前の技に置き換えたら消す

register(KEY, {
  skill: TEMP.skill,     // TODO: sol の惑星技
  dash: TEMP.dash,       // TODO: sol の機動技
  air: TEMP.air,         // TODO: sol の空中技
  ult: TEMP.ult,         // TODO: sol の必殺
  combo3: TEMP.combo3,   // TODO: sol の三段目
  burst: TEMP.burst,     // TODO: sol の変身の締め
  passive: {},           // TODO: special "corona"（tick / onHit / onHurt / onKill / dmgMul）
  meta: { stub: true },
});
