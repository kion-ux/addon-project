// ゴアのテストの補助（tests/gore_*.mjs が使う。.js はテストではなく補助として一緒に写される）
import { locate, partCenter, pointPart, heightPart, rayPart, boxesOf, shapesReady, PARTS } from "../scripts/gore/hitloc.js";
import { toLocal, yawOf } from "../scripts/core/util.js";
import { set as setSetting, reset as resetSettings } from "../scripts/core/settings.js";

export { locate, partCenter, pointPart, heightPart, rayPart, boxesOf, shapesReady, PARTS };

/** ワールドの点 → ゾンビの局所 [r, u, f]。 */
export function toLocalPoint(z, p) { return toLocal(z.location, yawOf(z), p); }

/** ゴアレベル（0..100）。 */
export function setGore(v) { setSetting("gore_level", v); }

/** 設定を既定に戻す（テストの頭で）。 */
export function defaults() { resetSettings(); }

/** 部位の状態をまとめて（prop は書いた最新の値）。 */
export function partsNow(prop, z) {
  const o = {};
  for (const p of PARTS) o[p] = prop(z, `nr:${p}`);
  return o;
}

export const CUT = new Set(["cut_lower", "cut_upper", "severed", "crushed", "halved"]);
