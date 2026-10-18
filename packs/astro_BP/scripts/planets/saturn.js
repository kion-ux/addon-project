// ===========================================================================
//  土星 クロノス — 仮の技（TODO）
//
//  TODO(saturn の担当): この形態の技をここに書く。今は engine.js の genericMoves("saturn")
//  （惑星の色で描く汎用の技一式）で動いているので、変身・4 技・三段目・変身の締めは一通り遊べる。
//  * 書き方: planets/_template.js（雛形）と planets/earth.js（見本）、
//    tools/astro/planets/_template/README_moves.md（ctx と演出・当たりの関数の説明）
//  * 技の名前・説明・再使用・コストは data.js の PLANETS.saturn.moves（astro_data.py が出所）
//  * パッシブの special は "ring_orbit"（効果 effects は passives.js が自動で掛ける）
//  * 確かめる: python3 tools/astro/test_astro.py --planet saturn
// ===========================================================================
import { register, genericMoves } from "../engine.js";

const KEY = "saturn";
const TEMP = genericMoves(KEY);   // TODO: 自前の技に置き換えたら消す

register(KEY, {
  skill: TEMP.skill,     // TODO: saturn の惑星技
  dash: TEMP.dash,       // TODO: saturn の機動技
  air: TEMP.air,         // TODO: saturn の空中技
  ult: TEMP.ult,         // TODO: saturn の必殺
  combo3: TEMP.combo3,   // TODO: saturn の三段目
  burst: TEMP.burst,     // TODO: saturn の変身の締め
  passive: {},           // TODO: special "ring_orbit"（tick / onHit / onHurt / onKill / dmgMul）
  meta: { stub: true },
});
